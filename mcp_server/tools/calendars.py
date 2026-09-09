"""Outils MCP : Domaine Calendriers & Flux iCal."""
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def list_calendar_subscriptions(
    is_active: Optional[bool] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Liste les abonnements et tokens de synchronisation de calendrier iCal.
    - is_active: Filtrer par état d'activation (True = actifs uniquement, False = inactifs/révoqués, None = tous)
    - user_id: Filtrer par identifiant utilisateur
    """
    from services.admin.calendar_subscriptions import list_all_subscriptions
    subs = list_all_subscriptions()

    formatted = [
        {
            "id": s.id,
            "user_id": s.user_id,
            "user_name": f"{s.user.firstname} {s.user.lastname}" if s.user else "Inconnu",
            "user_email": s.user.mail if s.user else "",
            "token": s.token,
            "is_active": s.is_active,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in subs
    ]

    filtered = formatted
    if is_active is not None:
        filtered = [s for s in filtered if s["is_active"] == is_active]
    if user_id is not None:
        filtered = [s for s in filtered if s["user_id"] == user_id]

    active_count = sum(1 for s in formatted if s["is_active"])
    inactive_count = sum(1 for s in formatted if not s["is_active"])

    return {
        "total": len(filtered),
        "active_count": active_count,
        "inactive_count": inactive_count,
        "subscriptions": filtered,
    }


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def create_calendar_subscription(
    user_id: int,
    calendar_type: str = "all",
    label: Optional[str] = None,
) -> Dict[str, Any]:
    """Génère une URL d'abonnement iCal personnalisée pour Google Calendar / Apple Calendar."""
    from services.admin.calendar_subscriptions import create_subscription
    sub = create_subscription(user_id)
    if sub:
        return {
            "success": True,
            "token_id": sub.id,
            "token": sub.token,
            "user_id": sub.user_id,
            "is_active": sub.is_active,
        }
    return {"success": False, "message": f"Impossible de créer un abonnement pour l'utilisateur #{user_id}."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def revoke_calendar_subscription(token_id: int, confirm: bool = False) -> Dict[str, Any]:
    """
    Révoque un token d'abonnement de calendrier iCal.
    ATTENTION: Action destructrice (Scope 'admin' requis).
    """
    from models import CalendarSubscription, db
    sub = db.session.get(CalendarSubscription, token_id)
    if not sub:
        return {"success": False, "message": f"Abonnement #{token_id} introuvable."}

    if not confirm:
        return {
            "success": False,
            "status": "requires_confirmation",
            "token_id": token_id,
            "message": f"⚠️ ATTENTION : Vous allez révoquer l'abonnement iCal #{token_id} (Utilisateur #{sub.user_id}). Confirmez avec confirm=True."
        }

    sub.is_active = False
    db.session.commit()
    return {"success": True, "message": f"Abonnement #{token_id} révoqué avec succès."}

