"""Outils MCP : Domaine Projets."""
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def list_projects() -> List[Dict[str, Any]]:
    """Liste tous les projets actifs avec détails complets (véhicules, décharges, contacts, pré-devis)."""
    from services.admin.projects import list_projects as _list_projects
    return _list_projects()


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_project(project_id: int) -> Optional[Dict[str, Any]]:
    """Récupère les détails d'un projet par son ID pour édition/affichage."""
    from services.admin.projects import get_project_for_edit
    return get_project_for_edit(project_id)


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def create_project(
    name: str,
    production_id: Optional[int] = None,
    pilot_contact_id: Optional[int] = None,
    production_contact_id: Optional[int] = None,
    dop_contact_id: Optional[int] = None,
    notes: Optional[str] = None,
    departure_date: Optional[str] = None,
    shoot_start: Optional[str] = None,
    shoot_end: Optional[str] = None,
    return_date: Optional[str] = None,
    vehicle_ids: Optional[List[str]] = None,
    head_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Crée un nouveau projet et génère automatiquement ses décharges pilote/production."""
    from services.admin.projects import create_project as _create_project

    class MultiDictMock(dict):
        def getlist(self, key):
            if key == "vehicle_ids":
                return vehicle_ids or []
            if key == "head_ids":
                return head_ids or []
            return []

    if not production_id:
        from models import Production
        first_prod = Production.query.first()
        if first_prod:
            production_id = first_prod.id

    form_data = MultiDictMock({
        "name": name,
        "production_id": str(production_id) if production_id else "",
        "pilot_contact_id": str(pilot_contact_id) if pilot_contact_id else "",
        "production_contact_id": str(production_contact_id) if production_contact_id else "",
        "dop_contact_id": str(dop_contact_id) if dop_contact_id else "",
        "notes": notes or "",
        "departure_date": departure_date or "",
        "shoot_start": shoot_start or "",
        "shoot_end": shoot_end or "",
        "return_date": return_date or "",
    })

    success = _create_project(form_data)
    return {"success": success, "message": "Projet créé avec succès." if success else "Échec de la création."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_project(
    project_id: int,
    name: str,
    production_id: Optional[int] = None,
    pilot_contact_id: Optional[int] = None,
    production_contact_id: Optional[int] = None,
    dop_contact_id: Optional[int] = None,
    notes: Optional[str] = None,
    departure_date: Optional[str] = None,
    shoot_start: Optional[str] = None,
    shoot_end: Optional[str] = None,
    return_date: Optional[str] = None,
    vehicle_ids: Optional[List[str]] = None,
    head_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Met à jour un projet existant par son ID."""
    from services.admin.projects import update_project as _update_project

    class MultiDictMock(dict):
        def getlist(self, key):
            if key == "vehicle_ids":
                return vehicle_ids or []
            if key == "head_ids":
                return head_ids or []
            return []

    if not production_id:
        from models import Project
        existing = Project.query.get(project_id)
        if existing and existing.production_id:
            production_id = existing.production_id

    form_data = MultiDictMock({
        "name": name,
        "production_id": str(production_id) if production_id else "",
        "pilot_contact_id": str(pilot_contact_id) if pilot_contact_id else "",
        "production_contact_id": str(production_contact_id) if production_contact_id else "",
        "dop_contact_id": str(dop_contact_id) if dop_contact_id else "",
        "notes": notes or "",
        "departure_date": departure_date or "",
        "shoot_start": shoot_start or "",
        "shoot_end": shoot_end or "",
        "return_date": return_date or "",
    })

    success = _update_project(project_id, form_data)
    return {"success": success, "message": "Projet mis à jour." if success else "Projet introuvable."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def delete_project(project_id: int, confirm: bool = False) -> Dict[str, Any]:
    """
    Supprime un projet par soft-delete et nettoie ses décharges associées.
    ATTENTION: Action destructrice (Scope 'admin' requis).
    L'IA doit obligatoirement l'exécuter d'abord avec confirm=False pour simuler l'impact et demander la confirmation à l'utilisateur humain.
    """
    from services.admin.projects import get_project_for_edit, delete_project as _delete_project
    proj = get_project_for_edit(project_id)
    if not proj:
        return {"success": False, "message": f"Projet #{project_id} introuvable."}

    if not confirm:
        proj_name = proj.get("name", "Sans nom")
        return {
            "success": False,
            "status": "requires_confirmation",
            "project_id": project_id,
            "project_name": proj_name,
            "message": (
                f"⚠️ ATTENTION : Vous êtes sur le point de supprimer le projet #{project_id} '{proj_name}'. "
                "Veuillez demander la confirmation explicite à l'utilisateur humain devant son écran, "
                "puis ré-exécutez cet outil avec confirm=True."
            )
        }

    success = _delete_project(project_id)
    return {"success": success, "message": f"Projet #{project_id} supprimé avec succès." if success else "Échec de la suppression."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_project_form_context() -> Dict[str, Any]:
    """Récupère le contexte nécessaire aux formulaires de projet (listes de sélections)."""
    from services.admin.projects import get_project_form_context as _context
    return _context()
