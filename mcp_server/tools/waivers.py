"""Outils MCP : Domaine Décharges (Waivers) Pilotes & Production."""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from mcp_server.core import mcp
from mcp_server.decorators import require_mcp_scope, run_in_flask_context


def _serialize_waiver(w: Dict[str, Any]) -> Dict[str, Any]:
    """Sérialise proprement les objets date et datetime pour la réponse JSON."""
    item = dict(w)
    for k in ("generated_at", "sent_at", "signed_at", "last_reminded_at"):
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
    - query: recherche textuelle (nom de projet, pilote, production)
    """
    from services.admin.waivers import list_pilot_waivers, list_production_waivers
    from mcp_server.utils import matches_search_query

    pilot_list = []
    prod_list = []

    if mode in ("all", "pilot"):
        raw_pilots = list_pilot_waivers()
        for w in raw_pilots:
            if status and w.get("raw_status") != status:
                continue
            if query and not matches_search_query(w, query, ["project_name", "pilot_name", "waiver_id"]):
                continue
            pilot_list.append(_serialize_waiver(w))

    if mode in ("all", "production"):
        raw_prods = list_production_waivers()
        for w in raw_prods:
            if status and w.get("raw_status") != status:
                continue
            if query and not matches_search_query(w, query, ["project_name", "production_name", "production_contact_name", "waiver_id"]):
                continue
            prod_list.append(_serialize_waiver(w))

    total = len(pilot_list) + len(prod_list)
    pending_count = sum(
        1 for w in (pilot_list + prod_list) if w.get("raw_status") != "signed"
    )

    return {
        "mode": mode,
        "total": total,
        "pending_count": pending_count,
        "pilot_waivers": pilot_list if mode in ("all", "pilot") else [],
        "production_waivers": prod_list if mode in ("all", "production") else [],
    }


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_waiver_detail(mode: str, waiver_id: str) -> Optional[Dict[str, Any]]:
    """
    Récupère le détail exhaustif d'une décharge pilote ou production par son identifiant.
    - mode: 'pilot' ou 'production'
    - waiver_id: ID UUID ou numérique de la décharge
    """
    from services.admin.waivers import list_pilot_waivers, list_production_waivers

    mode_clean = mode.lower().strip()
    wid_str = str(waiver_id).strip()

    if mode_clean == "pilot":
        items = list_pilot_waivers()
    elif mode_clean == "production":
        items = list_production_waivers()
    else:
        return None

    match = next(
        (w for w in items if str(w.get("waiver_id")) == wid_str or str(w.get("db_id")) == wid_str or str(w.get("id")) == wid_str),
        None,
    )
    if not match:
        return None

    return _serialize_waiver(match)


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
