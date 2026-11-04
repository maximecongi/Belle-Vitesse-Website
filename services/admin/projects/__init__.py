"""
Package modulaire de gestion des projets / tournages Belle Vitesse.
Re-exporte l'ensemble des fonctions du service d'administration pour garantir 100% de rétro-compatibilité.
"""

from services.admin.projects.crud import (
    create_project,
    delete_project,
    get_project_for_duplicate,
    get_project_for_edit,
    get_project_form_context,
    list_projects,
    update_project,
    update_project_notes,
)
from services.admin.projects.formatting import (
    _extract_head_image,
    _extract_vehicle_image,
    _format_project_admin,
    _format_vehicle_state,
    _get_secured_document_url,
)
from services.admin.projects.intervals import (
    _parse_int,
    _parse_inter_shoot_statuses,
    _parse_shoot_dates,
    get_project_shoot_status,
)
from services.admin.projects.locations import _parse_shooting_locations
from utils.database import get_heads, get_vehicles
from utils.formatting import parse_date as _parse_date

__all__ = [
    "create_project",
    "delete_project",
    "get_project_for_duplicate",
    "get_project_for_edit",
    "get_project_form_context",
    "list_projects",
    "update_project",
    "update_project_notes",
    "get_project_shoot_status",
    "_parse_shoot_dates",
    "_parse_int",
    "_parse_inter_shoot_statuses",
    "_parse_shooting_locations",
    "_format_project_admin",
    "_format_vehicle_state",
    "_get_secured_document_url",
    "_extract_vehicle_image",
    "_extract_head_image",
    "_parse_date",
    "get_vehicles",
    "get_heads",
]

