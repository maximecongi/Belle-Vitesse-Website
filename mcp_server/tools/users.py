"""Outils MCP : Domaine Utilisateurs."""
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def list_users() -> List[Dict[str, Any]]:
    """Liste tous les utilisateurs du système avec leurs rôles."""
    from services.admin.users import list_users as _list
    users = _list()
    return [u.to_dict() if hasattr(u, "to_dict") else dict(u) for u in users]


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Récupère le profil d'un utilisateur par son ID."""
    from services.admin.users import get_user as _get_user
    u = _get_user(user_id)
    return u.to_dict() if u and hasattr(u, "to_dict") else None


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def create_user(
    firstname: str,
    lastname: str,
    mail: str,
    role: str = "user",
    phone: Optional[str] = None,
    job: Optional[str] = None,
) -> Dict[str, Any]:
    """Crée un nouvel utilisateur."""
    from services.admin.users import create_user as _create
    data = {"firstname": firstname, "lastname": lastname, "mail": mail, "role": role, "phone": phone, "job": job}
    u = _create(data)
    return {"success": u is not None, "user": u.to_dict() if u else None}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def update_user(
    user_id: int,
    firstname: Optional[str] = None,
    lastname: Optional[str] = None,
    mail: Optional[str] = None,
    role: Optional[str] = None,
    phone: Optional[str] = None,
    job: Optional[str] = None,
) -> Dict[str, Any]:
    """Met à jour les informations d'un utilisateur."""
    from services.admin.users import update_user as _update
    data = {}
    if firstname is not None: data["firstname"] = firstname
    if lastname is not None: data["lastname"] = lastname
    if mail is not None: data["mail"] = mail
    if role is not None: data["role"] = role
    if phone is not None: data["phone"] = phone
    if job is not None: data["job"] = job

    u = _update(user_id, data)
    return {"success": u is not None, "user": u.to_dict() if u else None}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def delete_user(user_id: int, confirm: bool = False) -> Dict[str, Any]:
    """
    Supprime un utilisateur du système.
    ATTENTION: Action destructrice (Scope 'admin' requis).
    L'IA doit obligatoirement l'exécuter d'abord avec confirm=False pour simuler l'impact et demander la confirmation à l'utilisateur humain.
    """
    from services.admin.users import get_user as _get_user, delete_user as _delete
    u = _get_user(user_id)
    if not u:
        return {"success": False, "message": f"Utilisateur #{user_id} introuvable."}

    if not confirm:
        u_mail = getattr(u, "mail", f"#{user_id}")
        return {
            "success": False,
            "status": "requires_confirmation",
            "user_id": user_id,
            "user_mail": u_mail,
            "message": (
                f"⚠️ ATTENTION : Vous êtes sur le point de supprimer l'utilisateur #{user_id} ({u_mail}). "
                "Veuillez demander la confirmation explicite à l'utilisateur humain devant son écran, "
                "puis ré-exécutez cet outil avec confirm=True."
            )
        }

    success = _delete(user_id)
    return {"success": success, "message": f"Utilisateur #{user_id} supprimé." if success else "Échec de suppression."}

