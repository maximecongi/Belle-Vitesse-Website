"""Outils MCP : Domaine Incidents de Tournage & Sinistres."""
from typing import Optional, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def list_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    project_id: Optional[int] = None,
    query: Optional[str] = None,
    limit: Optional[int] = 20,
) -> Dict[str, Any]:
    """
    Liste les incidents de tournage enregistrés avec indicateurs KPI et filtres.
    - status: 'signale', 'en_expertise', 'en_reparation', 'assurance', 'resolu', 'cloture'
    - severity: 'mineur', 'modere', 'critique'
    - category: 'vehicule', 'materiel_camera', 'mecanique', 'electrique', 'carrosserie', 'accident_tiers', etc.
    - project_id: ID du projet concerné
    - query: recherche textuelle
    """
    from services.admin.incidents import list_incidents as _list
    return _list(
        status=status,
        severity=severity,
        category=category,
        project_id=project_id,
        query=query,
        limit=limit,
    )


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_incident(incident_id: Any) -> Optional[Dict[str, Any]]:
    """Récupère le détail exhaustif d'un incident par son ID numérique ou son numéro BVIC-XXXX."""
    from services.admin.incidents import get_incident_detail
    return get_incident_detail(incident_id)


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def create_incident(
    title: str,
    incident_date: str,
    category: str = "vehicule",
    severity: str = "modere",
    status: str = "signale",
    shooting_impact: str = "aucun",
    project_id: Optional[int] = None,
    vehicle_id: Optional[str] = None,
    equipment_name: Optional[str] = None,
    location: Optional[str] = None,
    description: Optional[str] = None,
    immediate_actions: Optional[str] = None,
    estimated_cost: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Déclare un nouvel incident de tournage.
    - title: Intitulé court de l'incident (ex: 'Fissure pare-chocs avant')
    - incident_date: Date de survenance (YYYY-MM-DD ou DD/MM/YYYY)
    - category: 'vehicule', 'materiel_camera', 'mecanique', 'electrique', 'carrosserie', etc.
    - severity: 'mineur', 'modere', 'critique'
    - shooting_impact: 'aucun', 'retard', 'interruption', 'annulation'
    """
    from services.admin.incidents import create_incident as _create
    form_data = {
        "title": title,
        "incident_date": incident_date,
        "category": category,
        "severity": severity,
        "status": status,
        "shooting_impact": shooting_impact,
        "project_id": project_id,
        "vehicle_id": vehicle_id,
        "equipment_name": equipment_name,
        "location": location,
        "description": description,
        "immediate_actions": immediate_actions,
        "estimated_cost": estimated_cost,
    }
    incident = _create(form_data)
    return {
        "success": True,
        "incident_id": incident.id,
        "incident_number": incident.incident_number,
        "message": f"Incident {incident.incident_number} déclaré avec succès.",
    }


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_incident(
    incident_id: int,
    title: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    shooting_impact: Optional[str] = None,
    description: Optional[str] = None,
    immediate_actions: Optional[str] = None,
    estimated_cost: Optional[float] = None,
    actual_cost: Optional[float] = None,
    insurance_declared: Optional[bool] = None,
    insurance_reference: Optional[str] = None,
    resolution_notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Met à jour un incident existant (statut, coûts réels, notes de résolution)."""
    from services.admin.incidents import update_incident as _update
    form_data = {}
    if title is not None:
        form_data["title"] = title
    if status is not None:
        form_data["status"] = status
    if severity is not None:
        form_data["severity"] = severity
    if category is not None:
        form_data["category"] = category
    if shooting_impact is not None:
        form_data["shooting_impact"] = shooting_impact
    if description is not None:
        form_data["description"] = description
    if immediate_actions is not None:
        form_data["immediate_actions"] = immediate_actions
    if estimated_cost is not None:
        form_data["estimated_cost"] = estimated_cost
    if actual_cost is not None:
        form_data["actual_cost"] = actual_cost
    if insurance_declared is not None:
        form_data["insurance_declared"] = insurance_declared
    if insurance_reference is not None:
        form_data["insurance_reference"] = insurance_reference
    if resolution_notes is not None:
        form_data["resolution_notes"] = resolution_notes

    incident = _update(incident_id, form_data)
    return {
        "success": True,
        "incident_id": incident.id,
        "incident_number": incident.incident_number,
        "status": incident.status,
        "message": f"Incident {incident.incident_number} mis à jour.",
    }


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def delete_incident(incident_id: int, confirm: bool = False) -> Dict[str, Any]:
    """Supprime logiquement (soft-delete) un incident. Requiert confirm=True et scope admin."""
    from services.admin.incidents import delete_incident as _delete
    return _delete(incident_id, confirm=confirm)
