"""Outils MCP : Domaine Pré-Devis & Devis."""
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def list_pre_quotes(project_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Liste tous les pré-devis, facultativement filtrés par ID de projet."""
    from services.admin.pre_quotes import list_pre_quotes as _list
    return _list(project_id)


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_pre_quote(pre_quote_id: int) -> Optional[Dict[str, Any]]:
    """Récupère le détail d'un pré-devis par son ID."""
    from services.admin.pre_quotes import get_pre_quote_detail
    return get_pre_quote_detail(pre_quote_id)


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def create_pre_quote(
    project_id: int,
    version_label: Optional[str] = "V1",
    items: Optional[List[Dict[str, Any]]] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Crée un nouveau pré-devis pour un projet avec ses lignes d'équipements / prestations."""
    from services.admin.pre_quotes import create_pre_quote as _create
    form_data = {
        "project_id": project_id,
        "version_label": version_label or "V1",
        "items": items or [],
        "notes": notes or "",
    }
    pq_id = _create(form_data)
    return {"success": pq_id is not None, "pre_quote_id": pq_id}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_pre_quote(
    pre_quote_id: int,
    items: Optional[List[Dict[str, Any]]] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Met à jour les lignes ou notes d'un pré-devis existant."""
    from services.admin.pre_quotes import update_pre_quote as _update
    form_data = {"items": items or [], "notes": notes or ""}
    success = _update(pre_quote_id, form_data)
    return {"success": success, "message": "Pré-devis mis à jour." if success else "Échec."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def delete_pre_quote(pre_quote_id: int, confirm: bool = False) -> Dict[str, Any]:
    """
    Supprime un pré-devis par son ID.
    ATTENTION: Action destructrice (Scope 'admin' requis).
    """
    from services.admin.pre_quotes import get_pre_quote_detail, delete_pre_quote as _delete
    pq = get_pre_quote_detail(pre_quote_id)
    if not pq:
        return {"success": False, "message": f"Pré-devis #{pre_quote_id} introuvable."}

    if not confirm:
        return {
            "success": False,
            "status": "requires_confirmation",
            "pre_quote_id": pre_quote_id,
            "message": f"⚠️ ATTENTION : Vous êtes sur le point de supprimer le pré-devis #{pre_quote_id}. Confirmez avec confirm=True."
        }

    success = _delete(pre_quote_id)
    return {"success": success, "message": f"Pré-devis #{pre_quote_id} supprimé." if success else "Échec."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def create_pre_quote_version(pre_quote_id: int, version_label: str) -> Dict[str, Any]:
    """Duplique un pré-devis sous une nouvelle version (ex: V2, V3)."""
    from services.admin.pre_quotes import create_pre_quote_version as _version
    new_pq_id = _version(pre_quote_id, version_label)
    return {"success": new_pq_id is not None, "new_pre_quote_id": new_pq_id}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_pre_quote_form_context(project_id: Optional[int] = None) -> Dict[str, Any]:
    """Récupère le contexte du formulaire pré-devis (grilles de prix, projets)."""
    from services.admin.pre_quotes import get_pre_quote_form_context as _context
    return _context(project_id)
