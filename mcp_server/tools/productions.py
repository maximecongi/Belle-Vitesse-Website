"""Outils MCP : Domaine Productions."""
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def list_productions() -> List[Dict[str, Any]]:
    """Liste toutes les sociétés de production cliente enregistrées."""
    from services.admin.productions import list_productions as _list
    return _list()


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_production(production_id: int) -> Optional[Dict[str, Any]]:
    """Récupère les détails d'une société de production par son ID."""
    from services.admin.productions import get_production_for_edit
    return get_production_for_edit(production_id)


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def create_production(
    name: str,
    address: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> Dict[str, Any]:
    """Crée une nouvelle société de production."""
    from services.admin.productions import create_production as _create
    form = {"name": name, "address": address or "", "email": email or "", "phone": phone or ""}
    success = _create(form)
    return {"success": success, "message": "Production créée." if success else "Échec de création."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_production(
    production_id: int,
    name: str,
    address: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> Dict[str, Any]:
    """Met à jour une société de production."""
    from services.admin.productions import update_production as _update
    form = {"name": name, "address": address or "", "email": email or "", "phone": phone or ""}
    success = _update(production_id, form)
    return {"success": success, "message": "Production mise à jour." if success else "Production introuvable."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def delete_production(production_id: int, confirm: bool = False) -> Dict[str, Any]:
    """
    Supprime une société de production par son ID.
    ATTENTION: Action destructrice (Scope 'admin' requis).
    L'IA doit obligatoirement l'exécuter d'abord avec confirm=False pour simuler l'impact et demander la confirmation à l'utilisateur humain.
    """
    from services.admin.productions import get_production_for_edit, delete_production as _delete
    prod = get_production_for_edit(production_id)
    if not prod:
        return {"success": False, "message": f"Production #{production_id} introuvable."}

    if not confirm:
        prod_name = prod.get("name", "Sans nom")
        return {
            "success": False,
            "status": "requires_confirmation",
            "production_id": production_id,
            "production_name": prod_name,
            "message": (
                f"⚠️ ATTENTION : Vous êtes sur le point de supprimer la société de production #{production_id} '{prod_name}'. "
                "Veuillez demander la confirmation explicite à l'utilisateur humain devant son écran, "
                "puis ré-exécutez cet outil avec confirm=True."
            )
        }

    success = _delete(production_id)
    return {"success": success, "message": f"Production #{production_id} supprimée." if success else "Échec de suppression."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_production_form_context() -> Dict[str, Any]:
    """Récupère le contexte du formulaire de production."""
    from services.admin.productions import get_production_form_context as _context
    return _context()
