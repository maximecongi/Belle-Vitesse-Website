"""Outils MCP : factures des projets (lecture, ajout, modification, suppression) et chiffre d'affaires facturé."""
from typing import Any, Dict, Optional

from mcp_server.core import mcp
from mcp_server.decorators import require_mcp_scope, run_in_flask_context
from mcp_server.tools.projects import _resolve_project



def _get_invoice(invoice_id: int):
    from models import ProjectInvoice, db

    invoice = db.session.get(ProjectInvoice, invoice_id)
    if not invoice or not invoice.project or invoice.project.deleted_at:
        return None
    return invoice


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_project_invoices(project_id: Any) -> Dict[str, Any]:
    """
    Factures d'un projet : n°, libellé, date d'émission, montant total HT, ventilation par matériel,
    autres prestations (montant total − matériel), statut payé et fichier joint ; totaux facturé / encaissé / reste.
    - project_id: Identifiant numérique du projet ou code BVPR (ex: 'BVPR-0RLY80RD5LZB' ou 46)
    """
    from services.admin.projects.invoices import project_invoices_payload

    p = _resolve_project(project_id)
    if not p:
        return {"status": "error", "message": f"Projet '{project_id}' introuvable."}
    return {
        "status": "success",
        "project": {"id": p.id, "project_id": p.project_id, "name": p.name},
        **project_invoices_payload(p),
    }


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_revenue_stats(period: Optional[str] = None, start_date: Optional[str] = None,
                      end_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Chiffre d'affaires facturé (HT), compté à la date d'émission des factures, comme la page Indicateurs :
    total, encaissé, reste à encaisser, nombre de factures et de projets, répartition par matériel
    (+ autres prestations), par mois et par projet, liste des factures.
    - period: '30d', 'quarter', '12m' (défaut) ou 'year' (depuis le 1er janvier) ; ignoré si start_date est fourni
    - start_date / end_date: bornes incluses (YYYY-MM-DD ou JJ/MM/AAAA) ; end_date par défaut = aujourd'hui
    Avec period, la période précédente équivalente est aussi fournie (previous) pour comparaison.
    """
    from services.admin.indicators import resolve_period
    from services.admin.projects.invoices import revenue_summary
    from utils.formatting import get_today_paris, parse_date

    if start_date:
        start = parse_date(start_date)
        end = parse_date(end_date) if end_date else get_today_paris()
        if not start or not end:
            return {"status": "error", "message": "Dates invalides (format attendu YYYY-MM-DD ou JJ/MM/AAAA)."}
        if end < start:
            return {"status": "error", "message": "end_date précède start_date."}
        return {"status": "success", **revenue_summary(start, end)}

    p = resolve_period(period or "12m")
    current = revenue_summary(p["start"], p["end"])
    previous = revenue_summary(p["prev_start"], p["prev_end"])
    previous.pop("invoices", None)
    return {
        "status": "success",
        "period": p["key"],
        "period_label": p["label"],
        **current,
        "previous": {k: previous[k] for k in ("start", "end", "count", "total", "paid", "due", "projects_count")},
        "delta_total": round(current["total"] - previous["total"], 2),
    }


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def add_project_invoice(
    project_id: Any,
    issued_on: str,
    amount: float,
    number: Optional[str] = None,
    label: Optional[str] = None,
    equipment: Optional[Dict[str, float]] = None,
    is_paid: bool = False,
    paid_on: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ajoute une facture à un projet. Le CA est compté à la date d'émission.
    - project_id: Identifiant numérique du projet ou code BVPR
    - issued_on: date d'émission (YYYY-MM-DD ou JJ/MM/AAAA)
    - amount: montant total HT de la facture
    - number: n° de facture (ex. 'F-2026-11-1') ; label: libellé (ex. 'Semaine 1', 'Acompte', 'Solde')
    - equipment: ventilation par matériel engagé sur le projet, ex. {"eRover": 3500, "vehicle:rec123": 2205} (clé = nom du matériel, id, ou « vehicle:<id> » / « head:<id> ») ; la somme ne peut pas dépasser amount,
      le reste forme les « Autres prestations »
    - is_paid / paid_on: facture encaissée et date de paiement (défaut : aujourd'hui)
    Le fichier de la facture se joint ensuite avec attach_project_invoice_file (ou depuis le formulaire projet).
    """
    from services.admin.projects.invoices import InvoiceError, create_invoice, invoice_to_dict

    p = _resolve_project(project_id)
    if not p:
        return {"status": "error", "message": f"Projet '{project_id}' introuvable."}
    try:
        invoice = create_invoice(p, issued_on=issued_on, amount=amount, number=number, label=label,
                                 equipment=equipment, is_paid=is_paid, paid_on=paid_on)
    except InvoiceError as err:
        return {"status": "error", "message": str(err)}
    return {"status": "success", "invoice": invoice_to_dict(invoice)}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_project_invoice(
    invoice_id: int,
    issued_on: Optional[str] = None,
    amount: Optional[float] = None,
    number: Optional[str] = None,
    label: Optional[str] = None,
    equipment: Optional[Dict[str, float]] = None,
    is_paid: Optional[bool] = None,
    paid_on: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Modifie une facture ; les champs non fournis gardent leur valeur. Sert aussi à marquer une facture payée
    (is_paid=true, paid_on facultatif, défaut : aujourd'hui) ou non payée (is_paid=false).
    - invoice_id: identifiant de la facture (cf. get_project_invoices)
    - number / label: passer "" pour les vider
    - equipment: remplace toute la ventilation ({} pour la vider) ; ventilation par matériel engagé sur le projet, ex. {"eRover": 3500, "vehicle:rec123": 2205} (clé = nom du matériel, id, ou « vehicle:<id> » / « head:<id> »)
    """
    from services.admin.projects.invoices import _UNSET, InvoiceError, invoice_to_dict, update_invoice

    invoice = _get_invoice(invoice_id)
    if not invoice:
        return {"status": "error", "message": f"Facture #{invoice_id} introuvable."}
    given = lambda v: _UNSET if v is None else v  # noqa: E731
    try:
        update_invoice(invoice, issued_on=given(issued_on), amount=given(amount), number=given(number),
                       label=given(label), equipment=given(equipment), is_paid=given(is_paid), paid_on=paid_on)
    except InvoiceError as err:
        return {"status": "error", "message": str(err)}
    return {"status": "success", "invoice": invoice_to_dict(invoice)}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def delete_project_invoice(invoice_id: int, confirm: bool = False) -> Dict[str, Any]:
    """
    Supprime une facture (et son fichier joint, y compris dans 2_FACTURES sur kDrive).
    - invoice_id: identifiant de la facture
    - confirm: doit valoir true pour exécuter la suppression
    """
    from services.admin.projects.invoices import delete_invoice

    invoice = _get_invoice(invoice_id)
    if not invoice:
        return {"status": "error", "message": f"Facture #{invoice_id} introuvable."}
    if not confirm:
        name = invoice.number or invoice.label or f"#{invoice.id}"
        return {
            "status": "confirmation_required",
            "message": f"Confirmez la suppression de la facture {name} ({invoice.total:.2f} € HT, émise le "
                       f"{invoice.issued_on.strftime('%d/%m/%Y')}) en relançant avec confirm=true."
                       + (" Son fichier sera aussi supprimé de kDrive." if invoice.file_path else ""),
        }
    delete_invoice(invoice)
    return {"status": "success", "deleted_id": invoice_id}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def attach_project_invoice_file(invoice_id: int, filename: str, content_base64: str) -> Dict[str, Any]:
    """
    Joint le fichier d'une facture (remplace le précédent s'il existe). Il est conservé sur le serveur,
    téléchargeable depuis le formulaire projet, et déposé dans le dossier 2_FACTURES du projet sur kDrive.
    - invoice_id: identifiant de la facture (cf. get_project_invoices ; créer la facture avant avec add_project_invoice)
    - filename: nom du fichier avec son extension (.pdf, .png, .jpg ou .jpeg), ex. 'F-2026-11-1.pdf'
    - content_base64: contenu du fichier encodé en base64 (préfixe « data:...;base64, » accepté), 10 Mo maximum
    """
    import base64
    import binascii

    from services.admin.projects.invoices import InvoiceError, attach_file, invoice_to_dict

    invoice = _get_invoice(invoice_id)
    if not invoice:
        return {"status": "error", "message": f"Facture #{invoice_id} introuvable."}
    raw = str(content_base64 or "").strip()
    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        content = base64.b64decode("".join(raw.split()), validate=True)
    except (binascii.Error, ValueError):
        return {"status": "error", "message": "Contenu base64 invalide."}
    replaced = invoice.file_name
    try:
        attach_file(invoice, filename, content)
    except InvoiceError as err:
        return {"status": "error", "message": str(err)}
    return {
        "status": "success",
        "invoice": invoice_to_dict(invoice),
        "replaced_file": replaced,
        "kdrive_folder": "2_FACTURES",
        "message": "Fichier enregistré ; dépôt sur kDrive en cours (2_FACTURES).",
    }


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def remove_project_invoice_file(invoice_id: int, confirm: bool = False) -> Dict[str, Any]:
    """
    Retire le fichier joint d'une facture (la facture est conservée) : copie serveur et fichier
    dans 2_FACTURES sur kDrive.
    - invoice_id: identifiant de la facture
    - confirm: doit valoir true pour exécuter le retrait
    """
    from services.admin.projects.invoices import InvoiceError, invoice_to_dict, remove_file

    invoice = _get_invoice(invoice_id)
    if not invoice:
        return {"status": "error", "message": f"Facture #{invoice_id} introuvable."}
    if not invoice.file_path:
        return {"status": "error", "message": "Cette facture n'a pas de fichier joint."}
    if not confirm:
        return {
            "status": "confirmation_required",
            "message": f"Confirmez le retrait du fichier « {invoice.file_name} » (également supprimé de kDrive) "
                       "en relançant avec confirm=true.",
        }
    try:
        remove_file(invoice)
    except InvoiceError as err:
        return {"status": "error", "message": str(err)}
    return {"status": "success", "invoice": invoice_to_dict(invoice)}
