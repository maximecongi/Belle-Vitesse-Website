"""Outils MCP : Domaine Inspections (Checkouts / Checkins)."""
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def list_checkouts() -> List[Dict[str, Any]]:
    """Liste tous les formulaires d'inspection Checkout (départ véhicule)."""
    from services.admin.checkouts import list_checkouts as _list
    return _list()


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def list_checkins() -> List[Dict[str, Any]]:
    """Liste tous les formulaires d'inspection Checkin (retour véhicule)."""
    from services.admin.checkins import list_checkins as _list
    return _list()


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_inspection_detail(mode: str, record_id: int) -> Optional[Dict[str, Any]]:
    """
    Récupère le détail complet d'une inspection.
    - mode: 'checkout' ou 'checkin'
    - record_id: ID de la fiche d'inspection
    """
    if mode.lower() == "checkout":
        from services.admin.checkouts import get_checkout_detail
        return get_checkout_detail(record_id)
    elif mode.lower() == "checkin":
        from services.admin.checkins import get_checkin_detail
        return get_checkin_detail(record_id)
    return None


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def delete_inspection(mode: str, record_id: int, confirm: bool = False) -> Dict[str, Any]:
    """
    Supprime définitivement un enregistrement d'inspection (checkout ou checkin).
    ATTENTION: Action destructrice (Scope 'admin' requis).
    L'IA doit obligatoirement l'exécuter d'abord avec confirm=False pour simuler l'impact et demander la confirmation à l'utilisateur humain.
    """
    from services.admin.inspections import delete_inspection_unified as _delete
    if mode.lower() not in ("checkout", "checkin"):
        return {"success": False, "message": "Mode invalide. Utilisez 'checkout' ou 'checkin'."}

    if not confirm:
        return {
            "success": False,
            "status": "requires_confirmation",
            "mode": mode,
            "record_id": record_id,
            "message": (
                f"⚠️ ATTENTION : Vous êtes sur le point de supprimer la fiche d'inspection {mode.upper()} #{record_id}. "
                "Veuillez demander la confirmation explicite à l'utilisateur humain devant son écran, "
                "puis ré-exécutez cet outil avec confirm=True."
            )
        }

    success = _delete(mode.lower(), record_id)
    return {"success": success, "message": f"Inspection {mode} #{record_id} supprimée avec succès." if success else "Échec de la suppression."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_inspection_form_context(mode: str = "checkout") -> Dict[str, Any]:
    """Récupère le contexte nécessaire à la création/édition d'un Checkout ou Checkin (véhicules, projets)."""
    from services.admin.checkouts import get_checkout_form_context
    return get_checkout_form_context()

