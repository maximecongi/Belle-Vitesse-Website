"""
Factures d'un projet, une à une (outils MCP) : lecture, ajout, modification, suppression et synthèse du CA.

Mêmes règles que la section Facturation du formulaire projet (services/admin/projects/crud.py) :
date d'émission et montant total HT requis, ventilation par véhicule / tête engagé sur le projet,
somme du matériel ≤ montant total, reste = « Autres prestations ». Le CA est compté à la date d'émission.
"""
from datetime import date
from typing import Any, Dict, Iterable, Optional

from models import Project, ProjectInvoice, db
from services.admin.projects.crud import (
    INVOICE_FILE_EXTENSIONS,
    _format_amount,
    _parse_invoice_row,
    _remove_local_file,
    _store_invoice_files,
)
from utils.formatting import get_today_paris, parse_date


class InvoiceError(ValueError):
    """Saisie de facture invalide (message destiné à l'utilisateur)."""


# ── Matériel ───────────────────────────────────────────────────

def _equipment_names() -> Dict[str, str]:
    """{"vehicle:<id>" | "head:<id>": nom} pour tout le catalogue."""
    from utils.database import get_heads, get_vehicles

    names = {}
    for kind, items in (("vehicle", get_vehicles()), ("head", get_heads())):
        for item in items:
            fields = item.get("fields") or {}
            names[f"{kind}:{item.get('id')}"] = fields.get("name") or str(item.get("id"))
    return names


def _engaged_keys(project) -> set:
    return {f"vehicle:{v}" for v in project.vehicle_ids_list} | {f"head:{h}" for h in project.head_ids_list}


def resolve_equipment(project, equipment: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Ventilation saisie → {"vehicle:<id>" | "head:<id>": montant}. Clé acceptée : « vehicle:<id> », « head:<id> »,
    id seul ou nom du matériel (insensible à la casse). Refuse le matériel non engagé sur le projet.
    """
    if not equipment:
        return {}
    engaged = _engaged_keys(project)
    names = _equipment_names()
    by_name = {names.get(k, k).strip().lower(): k for k in engaged}
    by_id = {k.split(":", 1)[1]: k for k in engaged}
    resolved = {}
    for raw_key, amount in equipment.items():
        key = str(raw_key).strip()
        found = key if key in engaged else by_id.get(key) or by_name.get(key.lower())
        if not found:
            available = ", ".join(sorted(names.get(k, k) for k in engaged)) or "aucun"
            raise InvoiceError(f"Matériel « {raw_key} » non engagé sur le projet (matériel du projet : {available}).")
        resolved[found] = amount
    return resolved


# ── Lecture ────────────────────────────────────────────────────

def invoice_to_dict(invoice: ProjectInvoice, names: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    names = names if names is not None else _equipment_names()
    return {
        "id": invoice.id,
        "project_id": invoice.project_id,
        "number": invoice.number,
        "label": invoice.label,
        "issued_on": invoice.issued_on.isoformat() if invoice.issued_on else None,
        "amount": round(invoice.total, 2),
        "equipment": [
            {"key": key, "name": names.get(key, key), "amount": round(amount, 2)}
            for key, amount in invoice.equipment_map.items()
        ],
        "equipment_total": invoice.equipment_total,
        "other": round(invoice.other, 2),
        "is_paid": bool(invoice.is_paid),
        "paid_on": invoice.paid_on.isoformat() if invoice.paid_on else None,
        "file_name": invoice.file_name,
        "has_file": bool(invoice.file_path),
    }


def _totals(invoices: Iterable[ProjectInvoice]) -> Dict[str, Any]:
    invoices = list(invoices)
    total = round(sum(i.total for i in invoices), 2)
    paid = round(sum(i.total for i in invoices if i.is_paid), 2)
    return {
        "count": len(invoices),
        "total": total,
        "paid": paid,
        "due": round(total - paid, 2),
        "paid_rate": round(100 * paid / total) if total else 0,
    }


def project_invoices_payload(project) -> Dict[str, Any]:
    names = _equipment_names()
    return {
        "invoices": [invoice_to_dict(i, names) for i in project.invoices],
        "totals": _totals(project.invoices),
    }


def revenue_summary(start: date, end: date) -> Dict[str, Any]:
    """CA facturé entre deux dates d'émission (incluses) : totaux, encaissé, par matériel, par mois et par projet."""
    invoices = (ProjectInvoice.query
                .join(Project, ProjectInvoice.project_id == Project.id)
                .filter(Project.deleted_at.is_(None),
                        ProjectInvoice.issued_on >= start, ProjectInvoice.issued_on <= end)
                .order_by(ProjectInvoice.issued_on.asc(), ProjectInvoice.id.asc())
                .all())
    names = _equipment_names()
    by_equipment, by_month, by_project = {}, {}, {}
    for inv in invoices:
        for key, amount in inv.equipment_map.items():
            by_equipment[key] = by_equipment.get(key, 0) + amount
        month = inv.issued_on.strftime("%Y-%m")
        by_month[month] = by_month.get(month, 0) + inv.total
        entry = by_project.setdefault(inv.project_id, {
            "id": inv.project_id, "project_id": inv.project.project_id, "name": inv.project.name,
            "total": 0.0, "paid": 0.0, "count": 0,
        })
        entry["total"] += inv.total
        entry["paid"] += inv.total if inv.is_paid else 0
        entry["count"] += 1
    totals = _totals(invoices)
    equipment_total = round(sum(by_equipment.values()), 2)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        **totals,
        "projects_count": len(by_project),
        "equipment_total": equipment_total,
        "other_total": round(max(totals["total"] - equipment_total, 0), 2),
        "by_equipment": sorted(
            ({"key": k, "name": names.get(k, k), "amount": round(v, 2)} for k, v in by_equipment.items()),
            key=lambda r: -r["amount"],
        ),
        "by_month": [{"month": m, "amount": round(v, 2)} for m, v in sorted(by_month.items())],
        "by_project": sorted(
            ({**p, "total": round(p["total"], 2), "paid": round(p["paid"], 2)} for p in by_project.values()),
            key=lambda p: -p["total"],
        ),
        "invoices": [invoice_to_dict(i, names) for i in invoices],
    }


# ── Écriture ───────────────────────────────────────────────────

def _apply(invoice: ProjectInvoice, project, values: Dict[str, Any], paid_on=None):
    """Valide via les règles du formulaire et applique les valeurs à la facture."""
    row = {
        "number": values.get("number"),
        "label": values.get("label"),
        "issued_on": values.get("issued_on"),
        "amount": values.get("amount"),
        "is_paid": "1" if values.get("is_paid") else "",
        "equipment": {k: str(v) for k, v in (values.get("equipment") or {}).items() if v not in (None, "")},
    }
    try:
        parsed = _parse_invoice_row(row, invoice.position or len(project.invoices), _engaged_keys(project))
    except ValueError as err:
        raise InvoiceError(str(err)) from err
    if not parsed:
        raise InvoiceError("Facture vide : date d'émission et montant total requis.")
    parsed.pop("position", None)
    was_paid = bool(invoice.is_paid)
    for key, value in parsed.items():
        setattr(invoice, key, value)
    if invoice.is_paid:
        explicit = parse_date(paid_on) if paid_on else None
        if paid_on and not explicit:
            raise InvoiceError(f"Date de paiement invalide : {paid_on}")
        invoice.paid_on = explicit or (invoice.paid_on if was_paid else None) or get_today_paris()
    else:
        invoice.paid_on = None


def create_invoice(project, *, issued_on, amount, number=None, label=None, equipment=None,
                   is_paid=False, paid_on=None) -> ProjectInvoice:
    # Validée avant d'être rattachée au projet : une saisie refusée ne laisse rien en session
    invoice = ProjectInvoice(position=len(project.invoices))
    _apply(invoice, project, {
        "number": number, "label": label, "issued_on": issued_on, "amount": amount,
        "equipment": resolve_equipment(project, equipment), "is_paid": is_paid,
    }, paid_on=paid_on)
    project.invoices.append(invoice)
    db.session.commit()
    return invoice


_UNSET = object()


def update_invoice(invoice: ProjectInvoice, *, issued_on=_UNSET, amount=_UNSET, number=_UNSET, label=_UNSET,
                   equipment=_UNSET, is_paid=_UNSET, paid_on=None) -> ProjectInvoice:
    """Modifie une facture ; les champs non fournis gardent leur valeur (equipment remplace toute la ventilation)."""
    project = invoice.project
    keep = lambda new, old: old if new is _UNSET else new  # noqa: E731
    current_equipment = {k: v for k, v in invoice.equipment_map.items()}
    values = {
        "number": keep(number, invoice.number),
        "label": keep(label, invoice.label),
        "issued_on": keep(issued_on, invoice.issued_on.isoformat() if invoice.issued_on else None),
        "amount": keep(amount, _format_amount(invoice.amount)),
        "equipment": current_equipment if equipment is _UNSET else resolve_equipment(project, equipment),
        "is_paid": keep(is_paid, invoice.is_paid),
    }
    try:
        _apply(invoice, project, values, paid_on=paid_on)
    except InvoiceError:
        db.session.rollback()
        raise
    db.session.commit()
    return invoice


def delete_invoice(invoice: ProjectInvoice) -> None:
    """Supprime la facture, sa copie locale et son fichier dans 2_FACTURES sur kDrive."""
    from services.common.kdrive.tasks import dispatch_sync_invoice_file

    project_id, entity_id, file_path = invoice.project_id, invoice.kdrive_entity_id, invoice.file_path
    db.session.delete(invoice)
    db.session.commit()
    if file_path:
        _remove_local_file(file_path)
        dispatch_sync_invoice_file(project_id, entity_id, None, None)


# ── Fichier de la facture ──────────────────────────────────────

INVOICE_FILE_MAX_BYTES = 10 * 1024 * 1024
_SIGNATURES = {
    ".pdf": (b"%PDF",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
}


class _BytesUpload:
    """Fichier en mémoire au format attendu par _store_invoice_files (filename + save)."""

    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self._content = content

    def save(self, dst: str) -> None:
        with open(dst, "wb") as fh:
            fh.write(self._content)


def check_document_file(filename: str, content: bytes, kind: str = "facture") -> str:
    """
    Contrôle un fichier joint (facture, devis) : PDF, PNG ou JPG, 10 Mo maximum, contenu conforme à
    l'extension. Retourne le nom de fichier nettoyé ; lève InvoiceError (ValueError) sinon.
    """
    from pathlib import Path

    name = Path(str(filename or "").replace("\\", "/")).name.strip()
    ext = Path(name).suffix.lower()
    if not name or ext not in INVOICE_FILE_EXTENSIONS:
        raise InvoiceError(f"Format de {kind} non accepté ({filename or 'sans nom'}) : PDF, PNG ou JPG.")
    if not content:
        raise InvoiceError("Fichier vide.")
    if len(content) > INVOICE_FILE_MAX_BYTES:
        raise InvoiceError(f"Fichier trop volumineux ({len(content) / 1048576:.1f} Mo, 10 Mo maximum).")
    if not content.startswith(_SIGNATURES[ext]):
        raise InvoiceError(f"Le contenu ne correspond pas à un fichier {ext.lstrip('.').upper()}.")
    return name[:255]


def attach_file(invoice: ProjectInvoice, filename: str, content: bytes) -> ProjectInvoice:
    """
    Joint (ou remplace) le fichier d'une facture : copie locale puis envoi dans 2_FACTURES sur kDrive,
    comme depuis le formulaire. PDF, PNG ou JPG, 10 Mo maximum, contenu contrôlé.
    """
    name = check_document_file(filename, content)
    project = invoice.project
    project._invoice_file_ops = [("upload", invoice, _BytesUpload(name, content))]
    _store_invoice_files(project)
    return invoice


def remove_file(invoice: ProjectInvoice) -> ProjectInvoice:
    """Retire le fichier joint (copie locale et fichier dans 2_FACTURES sur kDrive)."""
    if not invoice.file_path:
        raise InvoiceError("Cette facture n'a pas de fichier joint.")
    project = invoice.project
    project._invoice_file_ops = [("remove", invoice, None)]
    _store_invoice_files(project)
    return invoice
