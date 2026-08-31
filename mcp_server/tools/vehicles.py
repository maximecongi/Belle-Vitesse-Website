"""Outils MCP : Domaine Véhicules & Configuration Checkpoints."""
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_vehicles_with_config() -> List[Dict[str, Any]]:
    """Liste tous les véhicules avec leur configuration actuelle de points de contrôle."""
    from services.admin.vehicle_config import get_vehicles_with_config as _get
    return _get()


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def save_vehicle_checkpoint_config(vehicle_id: str, enabled_keys: List[str]) -> Dict[str, Any]:
    """Sauvegarde la configuration des points de contrôle activés pour un véhicule."""
    from services.admin.vehicle_config import save_vehicle_checkpoint_config as _save
    success = _save(vehicle_id, enabled_keys)
    return {"success": success, "message": "Configuration sauvegardée."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_checkpoints_for_vehicle(vehicle_id: str) -> List[Dict[str, Any]]:
    """Récupère la liste des points de contrôle applicables pour un véhicule spécifique."""
    from utils.checkpoints import get_checkpoints_for_vehicle as _get
    return _get(vehicle_id)


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def check_vehicle_availability(
    vehicle_id: str,
    start_date: str,
    end_date: str,
) -> Dict[str, Any]:
    """
    Vérifie la disponibilité d'un véhicule sur une période de dates donnée.
    Détecte tout conflit avec des tournages planifiés existants.
    - vehicle_id: ID Airtable/MySQL du véhicule (ex: 'rec1Rcg1rWWyzL9Qy')
    - start_date: Date de début (ex: '2026-09-15' ou '15/09/2026')
    - end_date: Date de fin (ex: '2026-09-20' ou '20/09/2026')
    """
    from datetime import datetime
    from models import Project
    from mcp_server.utils import parse_flexible_date
    from utils.database import get_vehicles

    parsed_start = parse_flexible_date(start_date)
    parsed_end = parse_flexible_date(end_date)

    if not parsed_start or not parsed_end:
        return {
            "success": False,
            "available": False,
            "message": "Format de date invalide pour start_date ou end_date. Utilisez 'YYYY-MM-DD' ou 'DD/MM/YYYY'.",
        }

    # Récupérer nom du véhicule
    all_v = {v.get("id"): v for v in get_vehicles()}
    v_data = all_v.get(vehicle_id, {})
    vehicle_name = v_data.get("fields", {}).get("name") or vehicle_id

    req_start = datetime.strptime(parsed_start, "%Y-%m-%d").date()
    req_end = datetime.strptime(parsed_end, "%Y-%m-%d").date()

    if req_end < req_start:
        return {
            "success": False,
            "available": False,
            "message": "La date de fin ne peut pas être antérieure à la date de début.",
        }

    all_projects = Project.query.filter(Project.deleted_at.is_(None)).all()
    conflicts = []

    for p in all_projects:
        v_list = [vid.strip() for vid in (p.vehicles_to_check or "").split(",") if vid.strip()]
        if vehicle_id not in v_list:
            continue

        p_start = p.departure_date or p.shoot_start_date
        p_end = p.return_date or p.shoot_end_date or p_start

        if not p_start:
            continue

        # Overlap check
        if p_start <= req_end and p_end >= req_start:
            conflicts.append({
                "project_id": p.id,
                "bvpr_id": p.project_id,
                "project_name": p.name,
                "production": p.production.name if p.production else "—",
                "departure_date": str(p.departure_date or ""),
                "shoot_start": str(p.shoot_start_date or ""),
                "shoot_end": str(p.shoot_end_date or ""),
                "return_date": str(p.return_date or ""),
            })

    is_available = len(conflicts) == 0
    return {
        "success": True,
        "vehicle_id": vehicle_id,
        "vehicle_name": vehicle_name,
        "requested_period": {"start": parsed_start, "end": parsed_end},
        "available": is_available,
        "conflicts_count": len(conflicts),
        "conflicts": conflicts,
        "message": (
            f"✅ Le véhicule '{vehicle_name}' est disponible du {parsed_start} au {parsed_end}."
            if is_available
            else f"⚠️ Conflit détecté : '{vehicle_name}' est déjà réservé sur {len(conflicts)} tournage(s)."
        ),
    }
