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


def _resolve_equipment_ids(
    provided_ids: Optional[List[str]],
    catalog_items: List[Dict[str, Any]],
) -> List[str]:
    """Résout de manière tolérante les identifiants, slugs ou noms d'équipements transmis par l'agent IA."""
    if not provided_ids:
        return []
    resolved = []
    for item_input in provided_ids:
        if not item_input:
            continue
        item_str = str(item_input).strip()
        # 1. Correspondance exacte sur l'identifiant
        direct_match = next((c for c in catalog_items if str(c.get("id")) == item_str), None)
        if direct_match:
            resolved.append(str(direct_match.get("id")))
            continue
        # 2. Correspondance tolérante sur nom, slug ou unique_id
        norm_input = item_str.lower()
        named_match = next(
            (c for c in catalog_items if norm_input in (c.get("fields", {}).get("name") or "").lower()
             or norm_input in (c.get("fields", {}).get("slug") or "").lower()
             or norm_input in (c.get("fields", {}).get("unique_id") or "").lower()),
            None,
        )
        if named_match:
            resolved.append(str(named_match.get("id")))
        else:
            resolved.append(item_str)
    return resolved


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
    IMPORTANT : Si vehicle_ids ET head_ids sont omis ou vides, l'outil scanne AUTOMATIQUEMENT
    l'intégralité de la flotte (tous les véhicules et têtes du catalogue) pour éviter tout faux négatif.
    - start_date: Date de début au format 'YYYY-MM-DD' ou 'DD/MM/YYYY'
    - end_date: Date de fin au format 'YYYY-MM-DD' ou 'DD/MM/YYYY'
    - vehicle_ids: Liste optionnelle d'identifiants ou noms de véhicules (ex: ['mercedes-c63', 'Ford F150'])
    - head_ids: Liste optionnelle d'identifiants ou noms de têtes gyrostabilisées (ex: ['Shotover F1', 'Flight Head'])
    - exclude_project_id: ID optionnel du projet en cours à exclure de l'analyse (int ou 'BVPR-...')
    """
    from datetime import datetime
    from services.admin.conflicts import check_booking_conflicts as _check
    from mcp_server.utils import parse_flexible_date
    from utils.database import get_heads, get_vehicles

    parsed_start = parse_flexible_date(start_date)
    parsed_end = parse_flexible_date(end_date)

    if not parsed_start or not parsed_end:
        return {
            "has_conflicts": False,
            "total_conflicts": 0,
            "message": "Format de date invalide. Utilisez 'YYYY-MM-DD' ou 'DD/MM/YYYY'.",
            "conflicts_list": [],
        }

    req_start = datetime.strptime(parsed_start, "%Y-%m-%d").date()
    req_end = datetime.strptime(parsed_end, "%Y-%m-%d").date()
    if req_end < req_start:
        return {
            "has_conflicts": False,
            "total_conflicts": 0,
            "message": "La date de fin ne peut pas être antérieure à la date de début.",
            "conflicts_list": [],
        }

    all_v = get_vehicles() or []
    all_h = get_heads() or []

    target_vehicle_ids = _resolve_equipment_ids(vehicle_ids, all_v) if vehicle_ids else []
    target_head_ids = _resolve_equipment_ids(head_ids, all_h) if head_ids else []

    scanned_all = False
    # Si aucun équipement ciblé n'est fourni, scan automatique de l'ensemble de la flotte
    if not target_vehicle_ids and not target_head_ids:
        target_vehicle_ids = [str(v["id"]) for v in all_v if v.get("id")]
        target_head_ids = [str(h["id"]) for h in all_h if h.get("id")]
        scanned_all = True

    raw = _check(
        start_date_val=parsed_start,
        end_date_val=parsed_end,
        vehicle_ids=target_vehicle_ids,
        head_ids=target_head_ids,
        exclude_project_id=exclude_project_id,
    )
    result = _make_json_safe(raw)
    result["scanned_all_equipment"] = scanned_all
    result["scanned_vehicles_count"] = len(target_vehicle_ids)
    result["scanned_heads_count"] = len(target_head_ids)

    total_c = result.get("total_conflicts", 0)
    if scanned_all:
        result["scan_summary"] = (
            f"Scan global de l'ensemble de la flotte ({len(target_vehicle_ids)} véhicules, {len(target_head_ids)} têtes) : "
            f"{total_c} conflit(s) détecté(s) du {parsed_start} au {parsed_end}."
        )
    else:
        result["scan_summary"] = (
            f"Scan ciblé ({len(target_vehicle_ids)} véhicules, {len(target_head_ids)} têtes) : "
            f"{total_c} conflit(s) détecté(s) du {parsed_start} au {parsed_end}."
        )

    return result


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
def get_vehicles_with_config() -> Dict[str, Any]:
    """Liste tous les véhicules avec leur configuration actuelle de points de contrôle."""
    from services.admin.vehicle_config import get_vehicles_with_config as _get
    vehicles = _get()
    return {
        "total": len(vehicles),
        "vehicles": vehicles,
    }


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
def get_checkpoints_for_vehicle(vehicle_id: str) -> Dict[str, Any]:
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
        return {
            "vehicle_id": vehicle_id,
            "vehicle_name": vehicle_id,
            "total": 0,
            "checkpoints": [],
        }

    actual_id = matching_v.get("id") or vehicle_id
    vehicle_name = matching_v.get("fields", {}).get("name") or vehicle_id
    checkpoints = _get(actual_id, vehicle_name=vehicle_name)
    return {
        "vehicle_id": actual_id,
        "vehicle_name": vehicle_name,
        "total": len(checkpoints),
        "checkpoints": checkpoints,
    }
