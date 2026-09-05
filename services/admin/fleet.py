"""
Module de service pour la gestion de la flotte et l'historique des véhicules Belle Vitesse.
Agrège les données catalogue, inspections (départs et retours), incidents et projets de tournage.
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from models import (
    CheckinVehicle,
    CheckoutVehicle,
    Incident,
    Project,
    User,
    db,
)
from models.catalog import Vehicle
from utils.checkpoints import ALL_POSSIBLE_CHECKPOINTS, CHECKPOINT_TO_MODEL_MAP
from utils.database import get_vehicles
from utils.formatting import format_date_fr

logger = logging.getLogger(__name__)


def _extract_vehicle_image(fields: Dict[str, Any]) -> str:
    """Extrait l'URL de l'image principale (thumbnail ou bannière) du véhicule."""
    if not fields:
        return "/static/imgs/logo-bv.svg"

    thumb = fields.get("thumbnail")
    if isinstance(thumb, list) and len(thumb) > 0 and isinstance(thumb[0], dict):
        # Chercher dans les tailles générées ou l'URL brute
        thumbnails = thumb[0].get("thumbnails", {})
        if isinstance(thumbnails, dict):
            large = thumbnails.get("large", {}).get("url")
            if large:
                return large
            full = thumbnails.get("full", {}).get("url")
            if full:
                return full
        url = thumb[0].get("url")
        if url:
            return url

    banner = fields.get("banner")
    if isinstance(banner, list) and len(banner) > 0 and isinstance(banner[0], dict):
        url = banner[0].get("url")
        if url:
            return url

    return "/static/imgs/logo-bv.svg"


def _detect_inspection_anomalies(record: Any) -> List[str]:
    """
    Détecte la liste des anomalies ou points non conformes sur une inspection (départ ou retour).
    """
    failures: List[str] = []
    if not record:
        return failures

    for cp in ALL_POSSIBLE_CHECKPOINTS:
        if cp.get("type") == "status":
            col = CHECKPOINT_TO_MODEL_MAP.get(cp.get("key"))
            if col:
                val = getattr(record, col, None)
                if val and str(val).lower() not in ("ok", "not_applicable", "none", ""):
                    failures.append(cp.get("label") or cp.get("key"))

    # Vérification batterie au départ (< 100%)
    is_checkout = isinstance(record, CheckoutVehicle) or getattr(
        record, "__tablename__", "") == "checkout_vehicles"
    battery = getattr(record, "battery_level", None)
    if is_checkout and battery is not None and battery < 100:
        failures.append(f"Batterie incomplète ({battery}%)")

    return failures


def get_fleet_overview() -> Dict[str, Any]:
    """
    Récupère la vue d'ensemble de la flotte de véhicules enrichie de leurs métriques opérationnelles :
    - Statut en direct (Disponible, Sur tournage, Incident / En révision)
    - Dernier niveau de batterie
    - Compteurs de projets, checkouts, checkins, incidents
    - Projet actif le cas échéant
    """
    today = date.today()

    # 1. Récupération des véhicules du catalogue
    catalog_vehicles = get_vehicles() or []
    vehicles_dict: Dict[str, Dict[str, Any]] = {}

    for v in catalog_vehicles:
        vid = str(v.get("id"))
        fields = v.get("fields") or {}
        name = fields.get("name") or fields.get("Nom") or "Véhicule sans nom"
        vehicles_dict[vid] = {
            "id": vid,
            "name": name,
            "slug": fields.get("slug") or "",
            "unique_id": fields.get("unique_id") or vid[:8].upper(),
            "brand": fields.get("brand") or "",
            "model": fields.get("model") or "",
            "order": fields.get("order", 999),
            "image_url": _extract_vehicle_image(fields),
            "daily_rate": fields.get("daily_rate"),
            "max_speed": fields.get("max_speed"),
            "battery_life": fields.get("battery_life"),
            "fields": fields,
            "checkouts_count": 0,
            "checkins_count": 0,
            "incidents_count": 0,
            "projects_count": 0,
            "latest_battery": None,
            "active_project": None,
            "operational_status": "disponible",
            "operational_status_label": "Disponible",
            "critical_incident": False,
        }

    # Compléter avec les véhicules en base locale le cas échéant
    try:
        local_vehicles = Vehicle.query.all()
        for lv in local_vehicles:
            lvid = str(lv.id)
            if lvid not in vehicles_dict:
                lfields = lv.fields or {}
                lname = lfields.get("name") or getattr(lv, "name", lvid)
                vehicles_dict[lvid] = {
                    "id": lvid,
                    "name": lname,
                    "slug": lfields.get("slug") or "",
                    "unique_id": lfields.get("unique_id") or lvid[:8].upper(),
                    "brand": lfields.get("brand") or "",
                    "model": lfields.get("model") or "",
                    "order": getattr(lv, "display_order", 999),
                    "image_url": _extract_vehicle_image(lfields),
                    "daily_rate": getattr(lv, "daily_rate", None),
                    "max_speed": lfields.get("max_speed"),
                    "battery_life": lfields.get("battery_life"),
                    "fields": lfields,
                    "checkouts_count": 0,
                    "checkins_count": 0,
                    "incidents_count": 0,
                    "projects_count": 0,
                    "latest_battery": None,
                    "active_project": None,
                    "operational_status": "disponible",
                    "operational_status_label": "Disponible",
                    "critical_incident": False,
                }
    except Exception as e:
        logger.warning(f"Impossible de charger les véhicules locaux : {e}")

    # 2. Chargement des enregistrements non archivés
    checkouts = CheckoutVehicle.query.filter(
        CheckoutVehicle.deleted_at == None).all()
    checkins = CheckinVehicle.query.filter(
        CheckinVehicle.deleted_at == None).all()
    incidents = Incident.query.filter(Incident.deleted_at == None).all()
    projects = Project.query.filter(Project.deleted_at == None).all()

    # Dictionnaire des projets
    project_map = {p.id: p for p in projects}

    # Suivi des batteries récentes par véhicule : {vid: (date_or_created, battery_val)}
    latest_batteries: Dict[str, tuple] = {}

    # Comptabilisation des checkouts
    # vid -> list of project_id
    open_checkout_projects: Dict[str, List[int]] = {}
    for co in checkouts:
        vid = str(co.vehicle_id) if co.vehicle_id else None
        if vid and vid in vehicles_dict:
            vehicles_dict[vid]["checkouts_count"] += 1
            if co.battery_level is not None:
                co_date = co.inspection_date or (
                    co.created_at.date() if co.created_at else date.min)
                prev = latest_batteries.get(vid)
                if not prev or co_date >= prev[0]:
                    latest_batteries[vid] = (co_date, co.battery_level)

            if co.status in ("in_progress", "signed"):
                open_checkout_projects.setdefault(
                    vid, []).append(co.project_id)

    # Comptabilisation des checkins
    closed_checkin_projects: Dict[str, set] = {}
    for ci in checkins:
        vid = str(ci.vehicle_id) if ci.vehicle_id else None
        if vid and vid in vehicles_dict:
            vehicles_dict[vid]["checkins_count"] += 1
            if ci.battery_level is not None:
                ci_date = ci.inspection_date or (
                    ci.created_at.date() if ci.created_at else date.min)
                prev = latest_batteries.get(vid)
                if not prev or ci_date >= prev[0]:
                    latest_batteries[vid] = (ci_date, ci.battery_level)

            if ci.status == "signed":
                closed_checkin_projects.setdefault(
                    vid, set()).add(ci.project_id)

    # Comptabilisation des incidents et détection des alertes critiques
    for inc in incidents:
        vid = str(inc.vehicle_id) if inc.vehicle_id else None
        if vid and vid in vehicles_dict:
            vehicles_dict[vid]["incidents_count"] += 1
            is_unresolved = inc.status not in ("cloture", "resolu")
            is_severe = inc.severity in ("critique", "majeur")
            if is_unresolved and is_severe:
                vehicles_dict[vid]["critical_incident"] = True

    # Comptabilisation des projets rattachés
    for p in projects:
        p_veh_ids = set()
        if p.vehicles_to_check:
            p_veh_ids.update(
                [v.strip() for v in p.vehicles_to_check.split(",") if v.strip()])

        for vid in p_veh_ids:
            if vid in vehicles_dict:
                vehicles_dict[vid]["projects_count"] += 1

                # Vérifier si ce projet est actuellement en cours pour ce véhicule
                is_current = False
                if p.shoot_start_date and p.shoot_end_date:
                    if p.shoot_start_date <= today <= p.shoot_end_date:
                        is_current = True
                elif p.departure_date and p.return_date:
                    if p.departure_date <= today <= p.return_date:
                        is_current = True

                if is_current and not vehicles_dict[vid]["active_project"]:
                    vehicles_dict[vid]["active_project"] = {
                        "id": p.id,
                        "project_id": p.project_id,
                        "name": p.name,
                        "production": p.production.name if p.production else "—",
                    }

    # Calcul final des statuts et batteries
    for vid, v_data in vehicles_dict.items():
        if vid in latest_batteries:
            v_data["latest_battery"] = latest_batteries[vid][1]

        # Si le véhicule a un départ non soldé par un retour signé
        open_projects = open_checkout_projects.get(vid, [])
        closed_set = closed_checkin_projects.get(vid, set())
        has_unreturned = any(pid not in closed_set for pid in open_projects)

        if v_data["critical_incident"]:
            v_data["operational_status"] = "incident"
            v_data["operational_status_label"] = "Incident / À réviser"
        elif has_unreturned or v_data["active_project"]:
            v_data["operational_status"] = "tournage"
            v_data["operational_status_label"] = "Sur tournage"
            if not v_data["active_project"] and open_projects:
                for pid in open_projects:
                    if pid not in closed_set and pid in project_map:
                        proj = project_map[pid]
                        v_data["active_project"] = {
                            "id": proj.id,
                            "project_id": proj.project_id,
                            "name": proj.name,
                            "production": proj.production.name if proj.production else "—",
                        }
                        break
        else:
            v_data["operational_status"] = "disponible"
            v_data["operational_status_label"] = "Disponible"

    # Liste triée par ordre d'affichage puis par nom
    sorted_vehicles = sorted(
        vehicles_dict.values(),
        key=lambda x: (x["order"] if x["order"]
                       is not None else 999, x["name"])
    )

    stats = {
        "total": len(sorted_vehicles),
        "available": sum(1 for v in sorted_vehicles if v["operational_status"] == "disponible"),
        "on_tournage": sum(1 for v in sorted_vehicles if v["operational_status"] == "tournage"),
        "incident": sum(1 for v in sorted_vehicles if v["operational_status"] == "incident"),
    }

    return {
        "vehicles": sorted_vehicles,
        "stats": stats,
    }


def get_vehicle_timeline(vehicle_id: str) -> Optional[Dict[str, Any]]:
    """
    Agrège chronologiquement tous les événements de vie d'un véhicule spécifique :
    - Départs (Checkouts)
    - Retours (Checkins)
    - Constats d'incidents (Incidents)
    - Tournages (Projets)
    Calcule également les statistiques et KPI de synthèse.
    """
    if not vehicle_id:
        return None

    # 1. Identification du véhicule
    vehicle_info: Optional[Dict[str, Any]] = None
    for v in get_vehicles() or []:
        if str(v.get("id")) == str(vehicle_id):
            fields = v.get("fields") or {}
            vehicle_info = {
                "id": str(v.get("id")),
                "name": fields.get("name") or fields.get("Nom") or "Véhicule",
                "slug": fields.get("slug") or "",
                "unique_id": fields.get("unique_id") or str(vehicle_id)[:8].upper(),
                "brand": fields.get("brand") or "",
                "model": fields.get("model") or "",
                "image_url": _extract_vehicle_image(fields),
                "banner_url": fields.get("banner", [{}])[0].get("url") if isinstance(fields.get("banner"), list) and fields.get("banner") else None,
                "daily_rate": fields.get("daily_rate"),
                "max_speed": fields.get("max_speed"),
                "battery_life": fields.get("battery_life"),
                "weight": fields.get("weight"),
                "passengers": fields.get("passengers"),
                "description": fields.get("description") or fields.get("description_fr") or "",
                "fields": fields,
            }
            break

    if not vehicle_info:
        try:
            lv = Vehicle.query.get(vehicle_id)
            if lv:
                lfields = lv.fields or {}
                vehicle_info = {
                    "id": str(lv.id),
                    "name": lfields.get("name") or getattr(lv, "name", str(lv.id)),
                    "slug": lfields.get("slug") or "",
                    "unique_id": lfields.get("unique_id") or str(lv.id)[:8].upper(),
                    "brand": lfields.get("brand") or "",
                    "model": lfields.get("model") or "",
                    "image_url": _extract_vehicle_image(lfields),
                    "banner_url": None,
                    "daily_rate": getattr(lv, "daily_rate", None),
                    "max_speed": lfields.get("max_speed"),
                    "battery_life": lfields.get("battery_life"),
                    "weight": lfields.get("weight"),
                    "passengers": lfields.get("passengers"),
                    "description": lfields.get("description") or "",
                    "fields": lfields,
                }
        except Exception as e:
            logger.warning(
                f"Erreur lors de la recherche du véhicule local {vehicle_id} : {e}")

    if not vehicle_info:
        return None

    # 2. Récupération des enregistrements associés
    checkouts = CheckoutVehicle.query.filter(
        CheckoutVehicle.vehicle_id == vehicle_id,
        CheckoutVehicle.deleted_at == None
    ).order_by(CheckoutVehicle.created_at.desc()).all()

    checkins = CheckinVehicle.query.filter(
        CheckinVehicle.vehicle_id == vehicle_id,
        CheckinVehicle.deleted_at == None
    ).order_by(CheckinVehicle.created_at.desc()).all()

    incidents = Incident.query.filter(
        Incident.vehicle_id == vehicle_id,
        Incident.deleted_at == None
    ).order_by(Incident.created_at.desc()).all()

    # Projets associés : par liste de véhicules ou par présence d'un checkout/checkin
    all_projects = Project.query.filter(Project.deleted_at == None).all()
    project_ids_with_inspections = {co.project_id for co in checkouts if co.project_id} | {
        ci.project_id for ci in checkins if ci.project_id} | {inc.project_id for inc in incidents if inc.project_id}

    vehicle_projects = []
    for p in all_projects:
        in_list = False
        if p.vehicles_to_check:
            ids = [v.strip()
                   for v in p.vehicles_to_check.split(",") if v.strip()]
            in_list = vehicle_id in ids

        if in_list or (p.id in project_ids_with_inspections):
            vehicle_projects.append(p)

    # 3. Construction des événements normalisés de la timeline
    events: List[Dict[str, Any]] = []

    # Événements Départs (Checkouts)
    for co in checkouts:
        evt_date = co.inspection_date or (
            co.created_at.date() if co.created_at else date.min)
        failures = _detect_inspection_anomalies(co)
        events.append({
            "id": f"checkout_{co.id}",
            "raw_id": co.id,
            "type": "checkout",
            "type_label": "Contrôle de départ",
            "icon": "truck",
            "reference": co.inspection_number,
            "date": evt_date,
            "date_formatted": format_date_fr(str(evt_date)) if evt_date != date.min else "—",
            "datetime": co.created_at,
            "title": f"Départ {co.inspection_number}",
            "status": co.status,
            "status_label": "Signé" if co.status == "signed" else "En cours" if co.status == "in_progress" else co.status,
            "battery": co.battery_level,
            "ready": co.vehicle_ready,
            "failures": failures,
            "failure_count": len(failures),
            "project_name": co.project.name if co.project else "—",
            "project_id": co.project_id,
            "project_unique_id": co.project.project_id if co.project else "",
            "production_name": co.project.production.name if co.project and co.project.production else "—",
            "controller_name": f"{co.controller.firstname} {co.controller.lastname}" if co.controller else "—",
            "notes": co.notes or "",
            "signed_pdf_path": co.signed_pdf_path,
        })

    # Événements Retours (Checkins)
    for ci in checkins:
        evt_date = ci.inspection_date or (
            ci.created_at.date() if ci.created_at else date.min)
        failures = _detect_inspection_anomalies(ci)
        events.append({
            "id": f"checkin_{ci.id}",
            "raw_id": ci.id,
            "type": "checkin",
            "type_label": "Contrôle de retour",
            "icon": "package",
            "reference": ci.inspection_number,
            "date": evt_date,
            "date_formatted": format_date_fr(str(evt_date)) if evt_date != date.min else "—",
            "datetime": ci.created_at,
            "title": f"Retour {ci.inspection_number}",
            "status": ci.status,
            "status_label": "Signé" if ci.status == "signed" else "En cours" if ci.status == "in_progress" else ci.status,
            "battery": ci.battery_level,
            "ready": ci.vehicle_ready,
            "failures": failures,
            "failure_count": len(failures),
            "project_name": ci.project.name if ci.project else "—",
            "project_id": ci.project_id,
            "project_unique_id": ci.project.project_id if ci.project else "",
            "production_name": ci.project.production.name if ci.project and ci.project.production else "—",
            "controller_name": f"{ci.controller.firstname} {ci.controller.lastname}" if ci.controller else "—",
            "notes": ci.notes or "",
            "signed_pdf_path": ci.signed_pdf_path,
        })

    # Événements Incidents
    for inc in incidents:
        evt_date = inc.incident_date or (
            inc.created_at.date() if inc.created_at else date.min)
        events.append({
            "id": f"incident_{inc.id}",
            "raw_id": inc.id,
            "type": "incident",
            "type_label": "Incident / Défaillance",
            "icon": "alert-triangle",
            "reference": inc.incident_number,
            "date": evt_date,
            "date_formatted": format_date_fr(str(evt_date)) if evt_date != date.min else "—",
            "datetime": inc.created_at,
            "title": f"Incident : {inc.title}",
            "status": inc.status,
            "status_label": inc.status_label if hasattr(inc, "status_label") else inc.status,
            "severity": inc.severity,
            "severity_label": inc.severity.capitalize() if inc.severity else "Modéré",
            "shooting_impact": inc.shooting_impact,
            "location": inc.location or "Lieu non précisé",
            "project_name": inc.project.name if inc.project else "—",
            "project_id": inc.project_id,
            "project_unique_id": inc.project.project_id if inc.project else "",
            "production_name": inc.project.production.name if inc.project and inc.project.production else "—",
            "reporter_name": f"{inc.reporter.firstname} {inc.reporter.lastname}" if getattr(inc, "reporter", None) else "—",
            "description": inc.description or "",
        })

    # Événements Tournages / Projets
    for p in vehicle_projects:
        evt_date = p.shoot_start_date or p.departure_date or (
            p.created_at.date() if hasattr(p, "created_at") and p.created_at else date.min)
        events.append({
            "id": f"project_{p.id}",
            "raw_id": p.id,
            "type": "project",
            "type_label": "Tournage & Projet",
            "icon": "film",
            "reference": p.project_id,
            "date": evt_date,
            "date_formatted": format_date_fr(str(evt_date)) if evt_date != date.min else "—",
            "datetime": getattr(p, "created_at", None),
            "title": f"Projet {p.project_id}",
            "project_name": p.name,
            "project_id": p.id,
            "project_unique_id": p.project_id,
            "status": "active" if (p.shoot_start_date and p.shoot_end_date and p.shoot_start_date <= date.today() <= p.shoot_end_date) else "completed",
            "status_label": "En tournage" if (p.shoot_start_date and p.shoot_end_date and p.shoot_start_date <= date.today() <= p.shoot_end_date) else "Projet clôturé",
            "production_name": p.production.name if p.production else "—",
            "pilot_name": f"{p.pilot_contact.first_name} {p.pilot_contact.last_name}" if p.pilot_contact else "—",
            "shoot_start_date": format_date_fr(str(p.shoot_start_date)) if p.shoot_start_date else None,
            "shoot_end_date": format_date_fr(str(p.shoot_end_date)) if p.shoot_end_date else None,
            "departure_date": format_date_fr(str(p.departure_date)) if p.departure_date else None,
            "return_date": format_date_fr(str(p.return_date)) if p.return_date else None,
            "notes": p.notes or "",
        })

    # Tri chronologique décroissant (le plus récent en premier)
    events.sort(
        key=lambda e: (
            e.get("date") or date.min,
            e.get("datetime") or datetime.min
        ),
        reverse=True
    )

    # 4. Calcul des KPI & métriques globales
    total_inspections = len(checkouts) + len(checkins)
    inspections_without_failures = sum(
        1 for e in events if e["type"] in ("checkout", "checkin") and e.get("failure_count", 0) == 0
    )
    conformance_rate = (
        round((inspections_without_failures / total_inspections) * 100)
        if total_inspections > 0 else 100
    )

    # Dernière batterie enregistrée
    latest_battery = None
    for e in events:
        if e["type"] in ("checkout", "checkin") and e.get("battery") is not None:
            latest_battery = e["battery"]
            break

    # Détection des incidents critiques ouverts
    open_critical_incidents = sum(
        1 for inc in incidents
        if inc.status not in ("cloture", "resolu") and inc.severity in ("critique", "majeur")
    )

    # Statut opérationnel actuel
    today = date.today()
    is_on_shoot = any(
        p.shoot_start_date and p.shoot_end_date and p.shoot_start_date <= today <= p.shoot_end_date
        for p in vehicle_projects
    )
    if open_critical_incidents > 0:
        current_status = "incident"
        current_status_label = "Incident / À réviser"
    elif is_on_shoot:
        current_status = "tournage"
        current_status_label = "Sur tournage"
    else:
        current_status = "disponible"
        current_status_label = "Disponible"

    stats = {
        "total_events": len(events),
        "total_projects": len(vehicle_projects),
        "total_checkouts": len(checkouts),
        "total_checkins": len(checkins),
        "total_incidents": len(incidents),
        "open_critical_incidents": open_critical_incidents,
        "latest_battery": latest_battery,
        "conformance_rate": conformance_rate,
        "current_status": current_status,
        "current_status_label": current_status_label,
    }

    return {
        "vehicle": vehicle_info,
        "events": events,
        "stats": stats,
    }
