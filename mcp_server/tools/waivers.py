"""Outils MCP : Domaine Contrats de Location (CGL) & Règles de Sécurité Universelles (BVSR)."""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from mcp_server.core import mcp
from mcp_server.decorators import require_mcp_scope, run_in_flask_context


def _serialize_waiver(w: Dict[str, Any]) -> Dict[str, Any]:
    """Sérialise proprement les objets date et datetime pour la réponse JSON et sécurise les jetons."""
    item = dict(w)
    item["success"] = True
    # Masquer le jeton de signature actif pour la sécurité
    has_token = bool(item.pop("signature_token", None))
    item["has_signature_token"] = has_token
    for k in ("generated_at", "sent_at", "signed_at", "bv_signed_at", "last_reminded_at", "deleted_at"):
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
    Liste les contrats CGL et engagements aux règles de sécurité (BVSR) avec indicateurs d'état et de relance.
    - mode: 'all', 'cgl' ou 'safety_rules'
    - status: 'to_generate', 'to_send', 'to_sign', 'signed'
    - query: recherche textuelle (nom de projet, signataire, production, waiver_id)
    """
    from services.admin.waivers import list_cgl, list_safety_rules_waivers
    from mcp_server.utils import matches_search_query

    valid_modes = {"all", "cgl", "safety_rules"}
    mode_clean = (mode or "all").lower().strip()
    if mode_clean not in valid_modes:
        return {
            "error": f"Mode invalide '{mode}'. Modes acceptés : 'all', 'cgl', 'safety_rules'.",
            "allowed_modes": list(valid_modes),
        }

    cgl_list = []
    safety_list = []

    if mode_clean in ("all", "cgl"):
        raw_cgls = list_cgl()
        for w in raw_cgls:
            if status and w.get("raw_status") != status:
                continue
            if query and not matches_search_query(w, query, ["project_name", "production_name", "production_contact_name", "id", "waiver_id"]):
                continue
            cgl_list.append(_serialize_waiver(w))

    if mode_clean in ("all", "safety_rules"):
        raw_rules = list_safety_rules_waivers()
        for w in raw_rules:
            if status and w.get("raw_status") != status:
                continue
            if query and not matches_search_query(w, query, ["project_name", "signer_name", "signer_role_label", "signer_email", "id", "waiver_id"]):
                continue
            safety_list.append(_serialize_waiver(w))

    all_list = cgl_list + safety_list
    total = len(all_list)
    pending_count = sum(1 for w in all_list if w.get("raw_status") != "signed")

    selected_list = all_list
    if mode_clean == "cgl":
        selected_list = cgl_list
    elif mode_clean == "safety_rules":
        selected_list = safety_list

    return {
        "mode": mode_clean,
        "total": total,
        "pending_count": pending_count,
        "all_waivers": selected_list,
        "cgl_waivers": cgl_list,
        "safety_rules_waivers": safety_list,
    }


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_waiver_detail(mode: Optional[str] = None, waiver_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Récupère le détail exhaustif d'un contrat CGL ou engagement BVSR par son identifiant.
    - mode: 'cgl', 'safety_rules' ou 'all'
    - waiver_id: ID UUID ou numérique (ex: 'BVRA-xxx' ou 'BVSR-xxx')
    """
    from services.admin.waivers import list_cgl, list_safety_rules_waivers
    from utils.entity_resolvers import resolve_cgl, resolve_safety_rules_waiver, resolve_waiver
    from services.admin.status_mapping import format_waiver_status

    if waiver_id is None and mode is not None:
        candidate = str(mode).strip()
        if candidate.upper().startswith(("BVSR-", "BVRA-")) or candidate.isdigit():
            waiver_id = candidate
            mode = None

    if not waiver_id:
        return {
            "success": False,
            "error": "Identifiant manquant.",
        }

    wid_str = str(waiver_id).strip()
    mode_clean = (mode or "").lower().strip()

    if not mode_clean or mode_clean == "all":
        if wid_str.upper().startswith("BVSR-"):
            mode_clean = "safety_rules"
        elif wid_str.upper().startswith("BVRA-"):
            mode_clean = "cgl"
        else:
            mode_clean = "all"

    # 1. Recherche dans les listes formatées en mémoire
    items = []
    if mode_clean in ("all", "cgl"):
        items.extend(list_cgl())
    if mode_clean in ("all", "safety_rules"):
        items.extend(list_safety_rules_waivers())

    match = next(
        (w for w in items if str(w.get("waiver_id")) == wid_str or str(w.get("db_id")) == wid_str or str(w.get("id")) == wid_str),
        None,
    )
    if match:
        return _serialize_waiver(match)

    # 2. Résolution directe via entités
    w = None
    if mode_clean == "cgl":
        w = resolve_cgl(wid_str)
    elif mode_clean == "safety_rules":
        w = resolve_safety_rules_waiver(wid_str)
    else:
        w = resolve_waiver(wid_str)

    if w:
        p = w.project
        return _serialize_waiver({
            "id": w.waiver_id,
            "db_id": w.id,
            "waiver_id": w.waiver_id,
            "type": w.waiver_type,
            "project_id": p.id if p else w.project_id,
            "project_name": p.name if p else (w.project_name or "—"),
            "signer_name": w.signer_name,
            "signer_role": getattr(w, "signer_role", None),
            "signer_role_label": getattr(w, "signer_role_label", None),
            "production_name": w.display_production_name,
            "shooting_dates": w.shooting_dates or "—",
            "status": format_waiver_status(w.status),
            "raw_status": w.status,
            "generated_at": w.generated_at,
            "sent_at": w.sent_at,
            "signed_at": w.signed_at,
            "deleted_at": w.deleted_at,
            "is_deleted": w.deleted_at is not None,
            "signed_pdf_path": w.signed_pdf_path,
            "reminder_count": w.reminder_count or 0,
            "last_reminded_at": w.last_reminded_at,
        })

    return {
        "success": False,
        "error": f"Document '{wid_str}' introuvable.",
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
    Envoie ou relance un contrat CGL ou engagement BVSR par e-mail avec lien sécurisé.
    - mode: 'cgl' ou 'safety_rules'
    - waiver_id: identifiant (UUID ou ID DB)
    - base_url: URL de base optionnelle
    """
    from services.admin.waivers import send_cgl, send_safety_rules_waiver

    mode_clean = mode.lower().strip()
    if mode_clean == "cgl":
        success, msg = send_cgl(waiver_id, base_url=base_url)
    elif mode_clean == "safety_rules":
        success, msg = send_safety_rules_waiver(waiver_id, base_url=base_url)
    else:
        return {"success": False, "message": "Mode invalide. Utilisez 'cgl' ou 'safety_rules'."}

    return {"success": success, "message": msg, "mode": mode_clean, "waiver_id": waiver_id}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def auto_remind_waivers(
    days_before: int = 2,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Déclenche la procédure de relance automatique pour les contrats CGL et engagements BVSR non signés (tournage à J-N).
    - days_before: Nombre de jours d'anticipation avant le départ/tournage (défaut: 2)
    """
    from services.admin.waivers import auto_remind_pending_waivers

    results = auto_remind_pending_waivers(days_before=days_before, base_url=base_url)
    return {
        "success": True,
        "days_before": days_before,
        "cgl_reminders_sent": results.get("cgl_reminders_sent", 0),
        "safety_rules_reminders_sent": results.get("safety_rules_reminders_sent", 0),
        "total_reminders_sent": results.get("total_reminders_sent", 0),
        "details": results.get("details", []),
        "message": (
            f"Relances automatiques envoyées : "
            f"{results.get('cgl_reminders_sent', 0)} CGL, "
            f"{results.get('safety_rules_reminders_sent', 0)} règles de sécurité (BVSR)."
        ),
    }


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def reset_waiver(mode: str, waiver_id: str, confirm: bool = False) -> Dict[str, Any]:
    """
    Réinitialise complètement un contrat CGL ou engagement BVSR (supprime signature, PDF scellé et pièces jointes).
    ATTENTION : Action destructive (Scope 'admin' requis).
    Exiger confirm=True après confirmation explicite.
    - mode: 'cgl' ou 'safety_rules'
    - waiver_id: ID du document
    """
    from services.admin.waivers import reset_cgl, reset_safety_rules_waiver

    mode_clean = mode.lower().strip()
    if mode_clean not in ("cgl", "safety_rules"):
        return {"success": False, "message": "Mode invalide. Utilisez 'cgl' ou 'safety_rules'."}

    if not confirm:
        return {
            "success": False,
            "status": "requires_confirmation",
            "mode": mode_clean,
            "waiver_id": waiver_id,
            "message": (
                f"⚠️ ATTENTION : Vous êtes sur le point de réinitialiser le document {mode_clean.upper()} '{waiver_id}'. "
                "Toutes les signatures, PDF archivés et pièces jointes associées seront définitivement effacés. "
                "Demandez confirmation explicite à l'utilisateur, puis réexécutez avec confirm=True."
            ),
        }

    if mode_clean == "cgl":
        success, msg = reset_cgl(waiver_id)
    else:
        success, msg = reset_safety_rules_waiver(waiver_id)

    return {"success": success, "message": msg, "mode": mode_clean, "waiver_id": waiver_id}
