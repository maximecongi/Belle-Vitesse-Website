"""
Service de détection des conflits de réservation de matériel.
Permet d'identifier les chevauchements de dates entre projets pour les véhicules et têtes gyrostabilisées.
"""
import logging
from datetime import date, datetime, timedelta
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


def _expand_date_range(d_start: date, d_end: date) -> set:
    """Retourne l'ensemble de tous les jours compris entre d_start et d_end inclus."""
    if not d_start or not d_end:
        return set([d_start] if d_start else ([d_end] if d_end else []))
    if d_start > d_end:
        d_start, d_end = d_end, d_start
    res = set()
    cur = d_start
    while cur <= d_end:
        res.add(cur)
        cur += timedelta(days=1)
    return res


def _get_project_active_dates(p: Project) -> set:
    """Retourne l'ensemble des dates où le matériel est effectivement réservé pour le projet p."""
    if hasattr(p, "effective_blocked_dates"):
        try:
            return p.effective_blocked_dates
        except Exception as e:
            logger.warning(f"Fallback effective_blocked_dates: {e}")

    p_start = p.departure_date or p.shoot_start_date
    p_end = p.return_date or p.shoot_end_date or p_start

    # Si le projet est en mode ponctuel et explicitement NON immobilisé entre les dates
    if getattr(p, "date_mode", None) == "punctual" and not getattr(p, "is_immobilized_between", True):
        dates = set()
        raw_shoot_dates = getattr(p, "shoot_dates", None) or []
        for d_str in raw_shoot_dates:
            parsed = _parse_date(d_str)
            if parsed:
                dates.add(parsed)
        if p.departure_date:
            dates.add(p.departure_date)
        if p.return_date:
            dates.add(p.return_date)
        if not dates and p_start:
            dates.add(p_start)
        return dates

    # Mode continu classique ou ponctuel immobilisé en continu
    if p_start and p_end:
        return _expand_date_range(p_start, p_end)
    elif p_start:
        return {p_start}
    elif p_end:
        return {p_end}
    return set()


def check_booking_conflicts(
    start_date_val: Optional[Union[str, date]],
    end_date_val: Optional[Union[str, date]],
    vehicle_ids: Optional[List[str]] = None,
    head_ids: Optional[List[str]] = None,
    exclude_project_id: Optional[Union[int, str]] = None,
    date_mode: Optional[str] = "continuous",
    is_immobilized_between: Optional[bool] = True,
    shoot_dates: Optional[List[Union[str, date]]] = None,
    inter_shoot_statuses: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Vérifie si un ou plusieurs matériels (véhicules, têtes) sont déjà réservés
    sur une période chevauchante par d'autres projets non supprimés.

    Supporte le mode continu, le mode dates ponctuelles, et la gestion d'immobilisation par intervalle.
    """
    start_date = _parse_date(start_date_val)
    end_date = _parse_date(end_date_val)

    # Détermination de l'ensemble des dates de réservation demandées
    req_active_dates = set()
    clean_date_mode = str(date_mode or "continuous").strip().lower()
    is_immob = True if is_immobilized_between in (True, "true", "True", "1", 1) or is_immobilized_between is None else False

    if clean_date_mode == "punctual" and shoot_dates:
        parsed_shoots = sorted(list(set([_parse_date(s) for s in shoot_dates if _parse_date(s)])))
        for s in parsed_shoots:
            req_active_dates.add(s)

        # Vérifier si des statuts d'intervalles sont spécifiés
        custom_statuses = {}
        if isinstance(inter_shoot_statuses, list):
            for item in inter_shoot_statuses:
                if isinstance(item, dict) and "start" in item and "end" in item:
                    k = f"{item['start']}_{item['end']}"
                    custom_statuses[k] = bool(item.get("is_immobilized", True))
        elif isinstance(inter_shoot_statuses, dict):
            for k, v in inter_shoot_statuses.items():
                if isinstance(v, dict):
                    custom_statuses[k] = bool(v.get("is_immobilized", True))
                else:
                    custom_statuses[k] = bool(v)

        for i in range(len(parsed_shoots) - 1):
            d1 = parsed_shoots[i]
            d2 = parsed_shoots[i + 1]
            diff = (d2 - d1).days
            if diff > 1:
                key = f"{d1.isoformat()}_{d2.isoformat()}"
                interval_immob = custom_statuses.get(key, is_immob)
                if interval_immob:
                    req_active_dates.update(_expand_date_range(d1 + timedelta(days=1), d2 - timedelta(days=1)))

        if start_date:
            req_active_dates.add(start_date)
        if end_date:
            req_active_dates.add(end_date)
    elif clean_date_mode == "punctual" and not is_immob:
        if start_date:
            req_active_dates.add(start_date)
        if end_date:
            req_active_dates.add(end_date)
    else:
        # Plage continue
        effective_start = start_date
        effective_end = end_date
        if not effective_start and shoot_dates:
            parsed_shoots = [_parse_date(s) for s in shoot_dates if _parse_date(s)]
            if parsed_shoots:
                effective_start = min(parsed_shoots)
                if not effective_end:
                    effective_end = max(parsed_shoots)
        if effective_start and not effective_end:
            effective_end = effective_start
        elif effective_end and not effective_start:
            effective_start = effective_end

        if effective_start and effective_end:
            req_active_dates = _expand_date_range(effective_start, effective_end)

    if not req_active_dates:
        return {
            "has_conflicts": False,
            "total_conflicts": 0,
            "conflicting_vehicle_ids": [],
            "conflicting_head_ids": [],
            "conflicts_by_item": {},
            "conflicts_list": [],
        }

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

        p_active_dates = _get_project_active_dates(p)
        if not p_active_dates:
            continue

        overlap_dates = req_active_dates.intersection(p_active_dates)
        if not overlap_dates:
            continue

        # Extraction des IDs assignés
        raw_v = getattr(p, "vehicles_to_check", "") or ""
        p_vehicles = set(v.strip() for v in raw_v.split(",") if v.strip())

        raw_h = getattr(p, "heads_to_check", "") or ""
        p_heads = set(h.strip() for h in raw_h.split(",") if h.strip())

        prod_name = p.production.name if p.production else "—"
        p_start = p.departure_date or p.shoot_start_date or min(p_active_dates)
        p_end = p.return_date or p.shoot_end_date or max(p_active_dates)

        sorted_overlaps = sorted(list(overlap_dates))
        if len(sorted_overlaps) == 1:
            overlap_str = f"le {sorted_overlaps[0].strftime('%d/%m/%Y')}"
        elif len(sorted_overlaps) <= 3:
            overlap_str = f"les {', '.join(d.strftime('%d/%m/%Y') for d in sorted_overlaps)}"
        else:
            overlap_str = f"du {sorted_overlaps[0].strftime('%d/%m/%Y')} au {sorted_overlaps[-1].strftime('%d/%m/%Y')} ({len(sorted_overlaps)} jours)"

        if getattr(p, "date_mode", None) == "punctual" and not getattr(p, "is_immobilized_between", True):
            period_label = f"Conflit {overlap_str} (dates ponctuelles, non immobilisé)"
        elif getattr(p, "date_mode", None) == "punctual":
            period_label = f"Conflit {overlap_str} (dates ponctuelles, immobilisé sur place)"
        else:
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
                "overlap_dates": [d.isoformat() for d in sorted_overlaps],
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
                "overlap_dates": [d.isoformat() for d in sorted_overlaps],
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
