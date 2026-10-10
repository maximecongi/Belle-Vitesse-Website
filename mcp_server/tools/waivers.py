"""Outils MCP : Domaine Décharges (Waivers) Pilotes & Production."""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from mcp_server.core import mcp
from mcp_server.decorators import require_mcp_scope, run_in_flask_context


def _serialize_waiver(w: Dict[str, Any]) -> Dict[str, Any]:
    """Sérialise proprement les objets date et datetime pour la réponse JSON et sécurise les jetons."""
    item = dict(w)
    item["success"] = True
    # Sécurité : masquer le jeton de signature actif pour éviter toute fuite non autorisée
    has_token = bool(item.pop("signature_token", None))
    item["has_signature_token"] = has_token
    for k in ("generated_at", "sent_at", "signed_at", "last_reminded_at", "deleted_at"):
        val = item.get(k)
        if isinstance(val, (datetime, date)):
            item[k] = val.isoformat()
    return item


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def list_waivers(
    mode: str = "all",
    status: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Liste les décharges (pilote, production ou toutes) avec indicateurs d'état et de relance.
    - mode: 'all', 'pilot' ou 'production'
    - status: 'to_generate', 'to_send', 'to_sign', 'signed'
    - query: recherche textuelle (nom de projet, pilote, production, waiver_id)
    """
    from services.admin.waivers import list_pilot_waivers, list_production_waivers
    from mcp_server.utils import matches_search_query

    valid_modes = {"all", "pilot", "production"}
    mode_clean = (mode or "all").lower().strip()
    if mode_clean not in valid_modes:
        return {
            "error": f"Mode de décharge invalide '{mode}'. Modes acceptés : 'all', 'pilot', 'production'.",
            "allowed_modes": list(valid_modes),
        }

    pilot_list = []
    prod_list = []

    if mode_clean in ("all", "pilot"):
        raw_pilots = list_pilot_waivers()
        for w in raw_pilots:
            if status and w.get("raw_status") != status:
                continue
            if query and not matches_search_query(w, query, ["project_name", "pilot_name", "waiver_id"]):
                continue
            pilot_list.append(_serialize_waiver(w))

    if mode_clean in ("all", "production"):
        raw_prods = list_production_waivers()
        for w in raw_prods:
            if status and w.get("raw_status") != status:
                continue
            if query and not matches_search_query(w, query, ["project_name", "production_name", "production_contact_name", "waiver_id"]):
                continue
            prod_list.append(_serialize_waiver(w))

    all_list = pilot_list + prod_list
    total = len(all_list)
    pending_count = sum(
        1 for w in all_list if w.get("raw_status") != "signed"
    )

    return {
        "mode": mode_clean,
        "total": total,
        "pending_count": pending_count,
        "all_waivers": all_list if mode_clean == "all" else (pilot_list if mode_clean == "pilot" else prod_list),
        "pilot_waivers": pilot_list if mode_clean in ("all", "pilot") else [],
        "production_waivers": prod_list if mode_clean in ("all", "production") else [],
    }


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_waiver_detail(mode: Optional[str] = None, waiver_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Récupère le détail exhaustif d'une décharge pilote ou production par son identifiant.
    - mode: 'pilot', 'production' ou 'all' (optionnel si waiver_id débute par 'BVDW-' ou 'BVPW-')
    - waiver_id: ID UUID ou numérique de la décharge (ex: 'BVDW-33YKZV3TBECF' ou 16)
    """
    from models import PilotWaiver, ProductionWaiver, Project
    from services.admin.status_mapping import format_waiver_status
    from services.admin.waivers import list_pilot_waivers, list_production_waivers

    # Tolérance sur l'inversion d'arguments ou omission de mode
    if waiver_id is None and mode is not None:
        wid_candidate = str(mode).strip()
        if wid_candidate.upper().startswith(("BVDW-", "BVPW-")) or wid_candidate.isdigit():
            waiver_id = wid_candidate
            mode = None

    if not waiver_id:
        return {
            "success": False,
            "message": "Identifiant de décharge manquant.",
            "error": "Identifiant de décharge manquant.",
        }

    wid_str = str(waiver_id).strip()
    mode_clean = (mode or "").lower().strip()

    if not mode_clean or mode_clean == "all":
        if wid_str.upper().startswith("BVDW-"):
            mode_clean = "pilot"
        elif wid_str.upper().startswith("BVPW-"):
            mode_clean = "production"
        else:
            mode_clean = "all"

    valid_modes = {"all", "pilot", "production"}
    if mode_clean not in valid_modes:
        return {
            "success": False,
            "message": f"Mode de décharge invalide '{mode}'. Modes acceptés : 'pilot', 'production', 'all'.",
            "error": f"Mode de décharge invalide '{mode}'. Modes acceptés : 'pilot', 'production', 'all'.",
            "allowed_modes": ["pilot", "production", "all"],
        }

    # 1. Recherche dans les listes formatées en mémoire
    items = []
    if mode_clean in ("all", "pilot"):
        items.extend(list_pilot_waivers())
    if mode_clean in ("all", "production"):
        items.extend(list_production_waivers())

    match = next(
        (w for w in items if str(w.get("waiver_id")) == wid_str or str(w.get("db_id")) == wid_str or str(w.get("id")) == wid_str),
        None,
    )
    if match:
        return _serialize_waiver(match)

    # 2. Recherche directe en base SQL si projet orphelin ou décharge archivée
    int_id = int(wid_str) if wid_str.isdigit() else -1

    if mode_clean in ("all", "pilot"):
        pw = PilotWaiver.query.filter(
            (PilotWaiver.waiver_id == wid_str) | (PilotWaiver.id == int_id)
        ).first()
        if pw:
            p = pw.project
            pilote_name = f"{pw.pilot_first_name or ''} {pw.pilot_last_name or ''}".strip() or "—"
            if p and p.pilot_contact:
                pilote_name = f"{p.pilot_contact.first_name} {p.pilot_contact.last_name}"
            return _serialize_waiver({
                "id": pw.waiver_id,
                "db_id": pw.id,
                "waiver_id": pw.waiver_id,
                "type": "pilot",
                "project_id": p.id if p else pw.project_id,
                "project_name": p.name if p else (pw.project_name or "—"),
                "pilot_name": pilote_name,
                "shooting_dates": pw.shooting_dates or "—",
                "status": format_waiver_status(pw.status),
                "raw_status": pw.status,
                "generated_at": pw.generated_at,
                "sent_at": pw.sent_at,
                "signed_at": pw.signed_at,
                "deleted_at": pw.deleted_at,
                "is_deleted": pw.deleted_at is not None,
                "is_project_deleted": p.deleted_at is not None if p else True,
                "signed_pdf_path": pw.signed_pdf_path,
                "reminder_count": pw.reminder_count or 0,
                "last_reminded_at": pw.last_reminded_at,
            })

    if mode_clean in ("all", "production"):
        prw = ProductionWaiver.query.filter(
            (ProductionWaiver.waiver_id == wid_str) | (ProductionWaiver.id == int_id)
        ).first()
        if prw:
            p = prw.project
            return _serialize_waiver({
                "id": prw.waiver_id,
                "db_id": prw.id,
                "waiver_id": prw.waiver_id,
                "type": "production",
                "project_id": p.id if p else prw.project_id,
                "project_name": p.name if p else (prw.project_name or "—"),
                "production_name": ((p.production.name if p.production else None) if p else prw.production_name) or prw.production_name or "—",
                "shooting_dates": prw.shooting_dates or "—",
                "status": format_waiver_status(prw.status),
                "raw_status": prw.status,
                "generated_at": prw.generated_at,
                "sent_at": prw.sent_at,
                "signed_at": prw.signed_at,
                "deleted_at": prw.deleted_at,
                "is_deleted": prw.deleted_at is not None,
                "is_project_deleted": p.deleted_at is not None if p else True,
                "signed_pdf_path": prw.signed_pdf_path,
                "reminder_count": prw.reminder_count or 0,
                "last_reminded_at": prw.last_reminded_at,
            })

    return {
        "success": False,
        "message": f"Décharge '{wid_str}' introuvable.",
        "error": f"Décharge '{wid_str}' introuvable.",
    }


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def send_waiver_invitation(
    mode: str,
    waiver_id: str,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Envoie ou relance une décharge (pilote ou production) par e-mail avec jeton de signature sécurisé.
    - mode: 'pilot' ou 'production'
    - waiver_id: identifiant de la décharge (UUID ou ID DB)
    - base_url: URL de base optionnelle (par défaut, l'hôte configuré du serveur)
    """
    from services.admin.waivers import send_pilot_waiver, send_production_waiver

    mode_clean = mode.lower().strip()
    if mode_clean == "pilot":
        success, msg = send_pilot_waiver(waiver_id, base_url=base_url)
    elif mode_clean == "production":
        success, msg = send_production_waiver(waiver_id, base_url=base_url)
    else:
        return {"success": False, "message": "Mode invalide. Utilisez 'pilot' ou 'production'."}

    return {"success": success, "message": msg, "mode": mode_clean, "waiver_id": waiver_id}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def auto_remind_waivers(
    days_before: int = 2,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Déclenche la procédure de relance automatique pour toutes les décharges non signées dont le tournage démarre à J-N.
    - days_before: Nombre de jours d'anticipation avant le début du tournage (défaut: 2)
    """
    from services.admin.waivers import auto_remind_pending_waivers

    results = auto_remind_pending_waivers(days_before=days_before, base_url=base_url)
    return {
        "success": True,
        "days_before": days_before,
        "production_reminders_sent": results.get("production_reminders_sent", 0),
        "pilot_reminders_sent": results.get("pilot_reminders_sent", 0),
        "details": results.get("details", []),
        "message": (
            f"Relances automatiques envoyées : "
            f"{results.get('pilot_reminders_sent', 0)} pilote(s), "
            f"{results.get('production_reminders_sent', 0)} production(s)."
        ),
    }


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def reset_waiver(mode: str, waiver_id: str, confirm: bool = False) -> Dict[str, Any]:
    """
    Réinitialise complètement une décharge (supprime la signature, les PDF scellés et les pièces jointes).
    ATTENTION : Action destructive (Scope 'admin' requis).
    Exiger confirm=True après confirmation explicite de l'utilisateur.
    - mode: 'pilot' ou 'production'
    - waiver_id: ID UUID de la décharge
    """
    from services.admin.waivers import reset_pilot_waiver, reset_production_waiver

    mode_clean = mode.lower().strip()
    if mode_clean not in ("pilot", "production"):
        return {"success": False, "message": "Mode invalide. Utilisez 'pilot' ou 'production'."}

    if not confirm:
        return {
            "success": False,
            "status": "requires_confirmation",
            "mode": mode_clean,
            "waiver_id": waiver_id,
            "message": (
                f"⚠️ ATTENTION : Vous êtes sur le point de réinitialiser la décharge {mode_clean.upper()} '{waiver_id}'. "
                "Toutes les signatures, PDF archivés et pièces jointes associées seront définitivement effacés. "
                "Demandez confirmation explicite à l'utilisateur, puis réexécutez avec confirm=True."
            ),
        }

    if mode_clean == "pilot":
        success, msg = reset_pilot_waiver(waiver_id)
    else:
        success, msg = reset_production_waiver(waiver_id)

    return {"success": success, "message": msg, "mode": mode_clean, "waiver_id": waiver_id}
