"""Outils MCP : Domaine Flotte, Véhicules & Détection de Conflits."""
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union

from mcp_server.core import mcp
from mcp_server.decorators import require_mcp_scope, run_in_flask_context


def _make_json_safe(data: Any) -> Any:
    """Convertit récursivement les objets date et datetime en chaînes ISO pour la sérialisation JSON."""
    if isinstance(data, dict):
        return {k: _make_json_safe(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_make_json_safe(v) for v in data]
    elif isinstance(data, (date, datetime)):
        return data.isoformat()
    return data


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_fleet_overview() -> Dict[str, Any]:
    """
    Récupère la vue d'ensemble de la flotte de véhicules Belle Vitesse enrichie en direct :
    - Statut opérationnel (disponible, sur tournage, incident / révision)
    - Dernier niveau de batterie mesuré
    - Compteurs de tournages, checkouts, checkins, incidents
    - Projet actif en cours de tournage
    - Statistiques globales de la flotte
    """
    from services.admin.fleet import get_fleet_overview as _get
    raw_data = _get()
    return _make_json_safe(raw_data)


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_vehicle_timeline(vehicle_id: str) -> Optional[Dict[str, Any]]:
    """
    Agrège la timeline opérationnelle complète d'un véhicule spécifique :
    - Missions de tournage et sous-événements ordonnés (Départs -> Incidents -> Retours)
    - Statistiques clés : taux de conformité, incidents ouverts, batterie
    - Informations détaillées sur le véhicule
    - vehicle_id: ID du véhicule (ex: 'rec1Rcg1rWWyzL9Qy' ou slug/numérique)
    """
    from services.admin.fleet import get_vehicle_timeline as _get
    raw_data = _get(vehicle_id)
    if not raw_data:
        return None
    return _make_json_safe(raw_data)


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def check_booking_conflicts(
    start_date: str,
    end_date: str,
    vehicle_ids: Optional[List[str]] = None,
    head_ids: Optional[List[str]] = None,
    exclude_project_id: Optional[Union[int, str]] = None,
) -> Dict[str, Any]:
    """
    Vérifie les conflits de réservation multi-matériels (véhicules et têtes gyrostabilisées) sur une période.
    - start_date: Date de début au format 'YYYY-MM-DD' ou 'DD/MM/YYYY'
    - end_date: Date de fin au format 'YYYY-MM-DD' ou 'DD/MM/YYYY'
    - vehicle_ids: Liste optionnelle d'identifiants de véhicules à vérifier
    - head_ids: Liste optionnelle d'identifiants de têtes gyrostabilisées à vérifier
    - exclude_project_id: ID optionnel du projet en cours à exclure de l'analyse (int ou 'BVPR-...')
    """
    from services.admin.conflicts import check_booking_conflicts as _check
    from mcp_server.utils import parse_flexible_date

    parsed_start = parse_flexible_date(start_date)
    parsed_end = parse_flexible_date(end_date)

    if not parsed_start or not parsed_end:
        return {
            "has_conflicts": False,
            "total_conflicts": 0,
            "message": "Format de date invalide. Utilisez 'YYYY-MM-DD' ou 'DD/MM/YYYY'.",
        }

    raw = _check(
        start_date_val=parsed_start,
        end_date_val=parsed_end,
        vehicle_ids=vehicle_ids,
        head_ids=head_ids,
        exclude_project_id=exclude_project_id,
    )
    return _make_json_safe(raw)


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def check_vehicle_availability(
    vehicle_id: str,
    start_date: str,
    end_date: str,
) -> Dict[str, Any]:
    """
    Vérifie la disponibilité d'un véhicule spécifique sur une période de dates donnée.
    Détecte tout conflit avec des tournages planifiés existants.
    - vehicle_id: ID Airtable/MySQL ou nom du véhicule (ex: 'rec1Rcg1rWWyzL9Qy')
    - start_date: Date de début (ex: '2026-09-15' ou '15/09/2026')
    - end_date: Date de fin (ex: '2026-09-20' ou '20/09/2026')
    """
    from mcp_server.utils import parse_flexible_date
    from services.admin.conflicts import check_booking_conflicts as _check
    from utils.database import get_vehicles

    parsed_start = parse_flexible_date(start_date)
    parsed_end = parse_flexible_date(end_date)

    if not parsed_start or not parsed_end:
        return {
            "success": False,
            "available": False,
            "message": "Format de date invalide pour start_date ou end_date. Utilisez 'YYYY-MM-DD' ou 'DD/MM/YYYY'.",
        }

    from datetime import datetime
    req_start = datetime.strptime(parsed_start, "%Y-%m-%d").date()
    req_end = datetime.strptime(parsed_end, "%Y-%m-%d").date()
    if req_end < req_start:
        return {
            "success": False,
            "available": False,
            "message": "La date de fin ne peut pas être antérieure à la date de début.",
        }

    all_v = {v.get("id"): v for v in get_vehicles()}
    if vehicle_id not in all_v:
        by_name = next((v for v in all_v.values() if v.get("fields", {}).get("name") == vehicle_id), None)
        if by_name:
            v_data = by_name
            actual_vid = by_name.get("id")
        else:
            return {
                "success": False,
                "available": False,
                "message": f"Véhicule '{vehicle_id}' introuvable dans le catalogue.",
            }
    else:
        v_data = all_v[vehicle_id]
        actual_vid = vehicle_id

    vehicle_name = v_data.get("fields", {}).get("name") or actual_vid

    conflict_data = _check(
        start_date_val=parsed_start,
        end_date_val=parsed_end,
        vehicle_ids=[actual_vid],
    )

    conflicts = conflict_data.get("conflicts_list", [])
    is_available = not conflict_data.get("has_conflicts", False)

    return {
        "success": True,
        "vehicle_id": actual_vid,
        "vehicle_name": vehicle_name,
        "requested_period": {"start": parsed_start, "end": parsed_end},
        "available": is_available,
        "conflicts_count": len(conflicts),
        "conflicts": _make_json_safe(conflicts),
        "message": (
            f"✅ Le véhicule '{vehicle_name}' est disponible du {parsed_start} au {parsed_end}."
            if is_available
            else f"⚠️ Conflit détecté : '{vehicle_name}' est déjà réservé sur {len(conflicts)} tournage(s)."
        ),
    }


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
    from utils.database import get_vehicles

    all_v = get_vehicles()
    matching_v = next(
        (v for v in all_v if v.get("id") == vehicle_id or v.get("fields", {}).get("name") == vehicle_id),
        None,
    )
    if not matching_v:
        return {"success": False, "message": f"Véhicule '{vehicle_id}' introuvable."}

    actual_id = matching_v.get("id") or vehicle_id
    success = _save(actual_id, enabled_keys)
    return {"success": success, "message": "Configuration sauvegardée." if success else "Échec de sauvegarde."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_checkpoints_for_vehicle(vehicle_id: str) -> List[Dict[str, Any]]:
    """
    Récupère la liste des points de contrôle applicables pour un véhicule spécifique.
    Retourne une liste vide si le véhicule est introuvable ou invalide.
    """
    from utils.checkpoints import get_checkpoints_for_vehicle as _get
    from utils.database import get_vehicles

    all_v = get_vehicles()
    matching_v = next(
        (v for v in all_v if v.get("id") == vehicle_id or v.get("fields", {}).get("name") == vehicle_id),
        None,
    )
    if not matching_v:
        return []

    actual_id = matching_v.get("id") or vehicle_id
    vehicle_name = matching_v.get("fields", {}).get("name") or vehicle_id
    return _get(actual_id, vehicle_name=vehicle_name)
