"""Outils MCP : Domaine Système, Maintenance & Cache."""
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_system_status() -> Dict[str, Any]:
    """Récupère l'état général du serveur (connexion MySQL, espace disque, temps de réponse)."""
    from services.admin.system import get_system_status as _status
    return _status()


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def purge_system_cache(confirm: bool = False) -> Dict[str, Any]:
    """
    Vide les caches de l'application Flask et des templates.
    ATTENTION: Action système (Scope 'admin' requis).
    """
    from services.admin.system import purge_system_cache as _purge
    if not confirm:
        return {
            "success": False,
            "status": "requires_confirmation",
            "message": "⚠️ ATTENTION : Vous allez vider le cache système Flask. Confirmez avec confirm=True."
        }
    success = _purge()
    return {"success": success, "message": "Cache système purgé avec succès." if success else "Échec."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_newsletter_subscribers() -> List[Dict[str, Any]]:
    """Récupère la liste des inscrits à la newsletter."""
    from services.admin.system import get_newsletter_subscribers as _get
    return _get()
