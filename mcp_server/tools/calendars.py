"""Outils MCP : Domaine Calendriers & Flux iCal."""
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def list_calendar_subscriptions() -> List[Dict[str, Any]]:
    """Liste tous les abonnements et tokens de synchronisation iCal actifs."""
    from services.admin.calendars import list_calendar_subscriptions as _list
    return _list()


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def create_calendar_subscription(
    user_id: int,
    calendar_type: str = "all",
    label: Optional[str] = None,
) -> Dict[str, Any]:
    """Génère une URL d'abonnement iCal personnalisée pour Google Calendar / Apple Calendar."""
    from services.admin.calendars import create_calendar_subscription as _create
    token = _create(user_id, calendar_type, label or "Abonnement iCal IA")
    return {"success": token is not None, "token": token}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def revoke_calendar_subscription(token_id: int, confirm: bool = False) -> Dict[str, Any]:
    """
    Révoque un token d'abonnement de calendrier iCal.
    ATTENTION: Action destructrice (Scope 'admin' requis).
    """
    from services.admin.calendars import revoke_calendar_subscription as _revoke
    if not confirm:
        return {
            "success": False,
            "status": "requires_confirmation",
            "token_id": token_id,
            "message": f"⚠️ ATTENTION : Vous allez révoquer l'abonnement iCal #{token_id}. Confirmez avec confirm=True."
        }
    success = _revoke(token_id)
    return {"success": success, "message": f"Abonnement #{token_id} révoqué." if success else "Échec."}
