"""
Service de détection des conflits de réservation de matériel.
Permet d'identifier les chevauchements de dates entre projets pour les véhicules et têtes gyrostabilisées.
"""
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import joinedload

from models import Project
from utils.database import get_heads, get_vehicles

logger = logging.getLogger(__name__)


def _parse_date(val: Optional[Union[str, date]]) -> Optional[date]:
    """Convertit une chaîne ISO ou objet date en instance de date."""
    if not val:
        return None
    if isinstance(val, date):
        return val
    try:
        return datetime.strptime(str(val).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def check_booking_conflicts(
    start_date_val: Optional[Union[str, date]],
    end_date_val: Optional[Union[str, date]],
    vehicle_ids: Optional[List[str]] = None,
    head_ids: Optional[List[str]] = None,
    exclude_project_id: Optional[Union[int, str]] = None,
) -> Dict[str, Any]:
    """
    Vérifie si un ou plusieurs matériels (véhicules, têtes) sont déjà réservés
    sur une période chevauchante par d'autres projets non supprimés.

    Args:
        start_date_val: Date de début (enlèvement ou tournage).
        end_date_val: Date de fin (retour ou fin tournage).
        vehicle_ids: Liste des identifiants de véhicules à vérifier.
        head_ids: Liste des identifiants de têtes à vérifier.
        exclude_project_id: ID du projet en cours d'édition (int ou string BVPR-...).

    Returns:
        Dictionnaire détaillant les conflits détectés.
    """
    start_date = _parse_date(start_date_val)
    end_date = _parse_date(end_date_val)

    if not start_date and not end_date:
        return {
            "has_conflicts": False,
            "total_conflicts": 0,
            "conflicting_vehicle_ids": [],
            "conflicting_head_ids": [],
            "conflicts_by_item": {},
            "conflicts_list": [],
        }

    # Si une seule date est renseignée, la période est d'un jour
    if start_date and not end_date:
        end_date = start_date
    elif end_date and not start_date:
        start_date = end_date

    # Normalisation si inversé
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    vehicle_set = set(str(v).strip() for v in (vehicle_ids or []) if v)
    head_set = set(str(h).strip() for h in (head_ids or []) if h)

    if not vehicle_set and not head_set:
        return {
            "has_conflicts": False,
            "total_conflicts": 0,
            "conflicting_vehicle_ids": [],
            "conflicting_head_ids": [],
            "conflicts_by_item": {},
            "conflicts_list": [],
        }

    # Récupération des noms de matériels depuis la base de catalogue
    vehicle_catalog = {
        v["id"]: v.get("fields", {}).get("name", f"Véhicule {v['id']}")
        for v in get_vehicles()
    }
    head_catalog = {
        h["id"]: h.get("fields", {}).get("name", f"Tête {h['id']}")
        for h in get_heads()
    }

    # Recherche des projets candidats
    query = Project.query.filter(Project.deleted_at.is_(None)).options(
        joinedload(Project.production)
    )

    if exclude_project_id is not None:
        clean_exclude = str(exclude_project_id).strip()
        if clean_exclude and clean_exclude not in ("None", "null", "undefined", "0", ""):
            if clean_exclude.isdigit():
                query = query.filter(Project.id != int(clean_exclude))
            else:
                query = query.filter(Project.project_id != clean_exclude)

    projects = query.all()

    conflicts_by_item: Dict[str, List[Dict[str, Any]]] = {}
    conflicting_vehicle_ids = set()
    conflicting_head_ids = set()
    conflicts_list = []

    for p in projects:
        # Double sécurité stricte contre l'auto-conflit sur le projet en cours
        if exclude_project_id is not None:
            clean_ex = str(exclude_project_id).strip()
            if clean_ex and clean_ex not in ("None", "null", "undefined", "0", ""):
                if str(p.id) == clean_ex or (p.project_id and str(p.project_id).strip() == clean_ex):
                    continue
        p_start = p.departure_date or p.shoot_start_date
        p_end = p.return_date or p.shoot_end_date or p_start

        if not p_start:
            continue
        if not p_end:
            p_end = p_start

        # Vérification du chevauchement : start1 <= end2 and end1 >= start2
        is_overlapping = (start_date <= p_end) and (end_date >= p_start)
        if not is_overlapping:
            continue

        # Extraction des IDs assignés
        raw_v = getattr(p, "vehicles_to_check", "") or ""
        p_vehicles = set(v.strip() for v in raw_v.split(",") if v.strip())

        raw_h = getattr(p, "heads_to_check", "") or ""
        p_heads = set(h.strip() for h in raw_h.split(",") if h.strip())

        prod_name = p.production.name if p.production else "—"
        period_label = (
            f"du {p_start.strftime('%d/%m/%Y')} au {p_end.strftime('%d/%m/%Y')}"
            if p_start != p_end
            else f"le {p_start.strftime('%d/%m/%Y')}"
        )

        # Vérifier conflits véhicules
        for vid in vehicle_set.intersection(p_vehicles):
            item_name = vehicle_catalog.get(vid, f"Véhicule {vid}")
            conflict_info = {
                "item_type": "vehicle",
                "item_id": vid,
                "item_name": item_name,
                "project_id": p.id,
                "project_code": p.project_id,
                "project_name": p.name or "Sans titre",
                "production": prod_name,
                "start_date": p_start.isoformat(),
                "end_date": p_end.isoformat(),
                "period_label": period_label,
            }
            conflicting_vehicle_ids.add(vid)
            conflicts_by_item.setdefault(vid, []).append(conflict_info)
            conflicts_list.append(conflict_info)

        # Vérifier conflits têtes
        for hid in head_set.intersection(p_heads):
            item_name = head_catalog.get(hid, f"Tête {hid}")
            conflict_info = {
                "item_type": "head",
                "item_id": hid,
                "item_name": item_name,
                "project_id": p.id,
                "project_code": p.project_id,
                "project_name": p.name or "Sans titre",
                "production": prod_name,
                "start_date": p_start.isoformat(),
                "end_date": p_end.isoformat(),
                "period_label": period_label,
            }
            conflicting_head_ids.add(hid)
            conflicts_by_item.setdefault(hid, []).append(conflict_info)
            conflicts_list.append(conflict_info)

    return {
        "has_conflicts": len(conflicts_list) > 0,
        "total_conflicts": len(conflicts_list),
        "conflicting_vehicle_ids": sorted(list(conflicting_vehicle_ids)),
        "conflicting_head_ids": sorted(list(conflicting_head_ids)),
        "conflicts_by_item": conflicts_by_item,
        "conflicts_list": conflicts_list,
    }
