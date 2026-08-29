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
    first_ac_contact_id: Optional[int] = None,
    key_grip_contact_id: Optional[int] = None,
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
        "first_ac_contact_id": str(first_ac_contact_id) if first_ac_contact_id else "",
        "key_grip_contact_id": str(key_grip_contact_id) if key_grip_contact_id else "",
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
    name: Optional[str] = None,
    production_id: Optional[int] = None,
    pilot_contact_id: Optional[int] = None,
    production_contact_id: Optional[int] = None,
    dop_contact_id: Optional[int] = None,
    first_ac_contact_id: Optional[int] = None,
    key_grip_contact_id: Optional[int] = None,
    notes: Optional[str] = None,
    departure_date: Optional[str] = None,
    shoot_start: Optional[str] = None,
    shoot_end: Optional[str] = None,
    return_date: Optional[str] = None,
    vehicle_ids: Optional[List[str]] = None,
    head_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Met à jour un projet existant par son ID (mode patch : conserve les champs non spécifiés)."""
    from models import Project, db
    from services.admin.projects import update_project as _update_project

    project = db.session.get(Project, project_id)
    if not project:
        return {"success": False, "message": f"Projet #{project_id} introuvable."}

    # Récupérer les identifiants existants pour les véhicules et têtes
    existing_veh_ids = [v.strip() for v in (project.vehicles_to_check or "").split(",") if v.strip()]
    existing_head_ids = [h.strip() for h in (project.heads_to_check or "").split(",") if h.strip()]

    final_veh_ids = vehicle_ids if vehicle_ids is not None else existing_veh_ids
    final_head_ids = head_ids if head_ids is not None else existing_head_ids

    class MultiDictMock(dict):
        def getlist(self, key):
            if key == "vehicle_ids":
                return final_veh_ids
            if key == "head_ids":
                return final_head_ids
            return []

    # Dates existantes
    existing_dep = project.departure_date.strftime("%Y-%m-%d") if project.departure_date else ""
    existing_start = project.shoot_start_date.strftime("%Y-%m-%d") if project.shoot_start_date else ""
    existing_end = project.shoot_end_date.strftime("%Y-%m-%d") if project.shoot_end_date else ""
    existing_ret = project.return_date.strftime("%Y-%m-%d") if project.return_date else ""

    form_data = MultiDictMock({
        "name": name if name is not None else (project.name or ""),
        "production_id": str(production_id) if production_id is not None else (str(project.production_id) if project.production_id else ""),
        "pilot_contact_id": str(pilot_contact_id) if pilot_contact_id is not None else (str(project.pilot_contact_id) if project.pilot_contact_id else ""),
        "production_contact_id": str(production_contact_id) if production_contact_id is not None else (str(project.production_contact_id) if project.production_contact_id else ""),
        "dop_contact_id": str(dop_contact_id) if dop_contact_id is not None else (str(project.dop_contact_id) if project.dop_contact_id else ""),
        "first_ac_contact_id": str(first_ac_contact_id) if first_ac_contact_id is not None else (str(project.first_ac_contact_id) if project.first_ac_contact_id else ""),
        "key_grip_contact_id": str(key_grip_contact_id) if key_grip_contact_id is not None else (str(project.key_grip_contact_id) if project.key_grip_contact_id else ""),
        "notes": notes if notes is not None else (project.notes or ""),
        "departure_date": departure_date if departure_date is not None else existing_dep,
        "shoot_start": shoot_start if shoot_start is not None else existing_start,
        "shoot_end": shoot_end if shoot_end is not None else existing_end,
        "return_date": return_date if return_date is not None else existing_ret,
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
