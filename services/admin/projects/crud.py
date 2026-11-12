import json
import logging
import os
import shutil
from datetime import date
from pathlib import Path
from typing import Optional

from flask import current_app
from sqlalchemy.orm import joinedload, selectinload

from models import Contact, Production, Project, ProjectReport, User, db
from models.db import _utcnow
from services.admin.projects.formatting import _format_project_admin
from services.admin.projects.intervals import (
    _parse_int,
    _parse_inter_shoot_statuses,
    _parse_shoot_dates,
)
from services.admin.projects.locations import _parse_shooting_locations
from services.admin.utils import handle_admin_service_error
from utils.database import get_heads, get_vehicles
from utils.entity_resolvers import resolve_project
from utils.formatting import parse_date
from utils.pagination import Pagination
from utils.storage import get_project_base_path

logger = logging.getLogger(__name__)


# Filtre « statut commercial » de la liste des projets : clé de statut, ou « untracked »
# pour les projets antérieurs au suivi commercial (statut NULL).
UNTRACKED_COMMERCIAL_FILTER = "untracked"


def filter_by_commercial_status(query, commercial_status: Optional[str]):
    from models.commercial_event import COMMERCIAL_STATUS_LABELS

    if commercial_status == UNTRACKED_COMMERCIAL_FILTER:
        return query.filter(Project.commercial_status.is_(None))
    if commercial_status in COMMERCIAL_STATUS_LABELS:
        return query.filter(Project.commercial_status == commercial_status)
    return query


def commercial_status_counts(is_archive: Optional[bool] = None, scope: Optional[int] = None) -> dict:
    """Nombre de projets par statut commercial (clé None = non suivi), sur le même périmètre que la liste."""
    from services.admin.project_access import scope_project_query

    query = scope_project_query(Project.query.filter(Project.deleted_at.is_(None)), scope)
    query = _filter_archive(query, is_archive)
    rows = (
        query.with_entities(Project.commercial_status, db.func.count(Project.id))
        .group_by(Project.commercial_status)
        .all()
    )
    return {status: count for status, count in rows}


def _filter_archive(query, is_archive: Optional[bool]):
    today = date.today()
    if is_archive is True:
        return query.filter(Project.return_date.isnot(None), Project.return_date < today)
    if is_archive is False:
        return query.filter(db.or_(Project.return_date.is_(None), Project.return_date >= today))
    return query


def list_projects(
    is_archive: Optional[bool] = None,
    q: Optional[str] = None,
    page: Optional[int] = None,
    per_page: int = 10,
    scope: Optional[int] = None,
    commercial_status: Optional[str] = None,
):
    """
    Récupère les projets et les formate pour la liste d'administration (avec chargement lié optimisé).
    `scope` (cf. services.admin.project_access) restreint aux projets de l'équipe BV d'un utilisateur.
    Supporte le filtrage SQL (archives, recherche textuelle) et la pagination serveur.
    Si `page` est spécifié, retourne une instance `Pagination`.
    Si `page` est None, retourne la liste complète (rétrocompatibilité totale).
    """
    from services.admin.project_access import scope_project_query

    query = scope_project_query(Project.query.filter(Project.deleted_at.is_(None)), scope)

    today = date.today()

    if is_archive is True:
        query = query.filter(Project.return_date.isnot(None), Project.return_date < today)
        order_clauses = [
            db.case((Project.departure_date.is_(None), 1), else_=0),
            Project.departure_date.desc(),
            Project.name.asc(),
        ]
    elif is_archive is False:
        query = query.filter(
            db.or_(Project.return_date.is_(None), Project.return_date >= today)
        )
        order_clauses = [
            db.case((Project.departure_date.is_(None), 1), else_=0),
            Project.departure_date.asc(),
            Project.name.asc(),
        ]
    else:
        order_clauses = [
            db.case((Project.departure_date.is_(None), 1), else_=0),
            Project.departure_date.desc(),
            Project.name.asc(),
        ]

    query = filter_by_commercial_status(query, commercial_status)

    if q:
        term = f"%{q.strip()}%"
        query = query.outerjoin(Production, Project.production_id == Production.id).filter(
            db.or_(
                Project.project_id.ilike(term),
                Project.name.ilike(term),
                Production.name.ilike(term),
                Project.notes.ilike(term),
            )
        )

    eager_options = (
        joinedload(Project.production),
        joinedload(Project.pilot_contact),
        joinedload(Project.production_contact),
        joinedload(Project.dop_contact),
        joinedload(Project.first_ac_contact),
        joinedload(Project.key_grip_contact),
        joinedload(Project.remote_head_operator_contact),
        selectinload(Project.waivers),
        selectinload(Project.checkout_vehicles),
        selectinload(Project.checkin_vehicles),
        selectinload(Project.incidents),
        selectinload(Project.reports),
        selectinload(Project.equipment_usage),
    )

    vehicles = get_vehicles()
    vehicle_map = {v["id"]: v.get("fields", {}) for v in vehicles}
    heads = get_heads()
    heads_map = {h["id"]: h.get("fields", {}) for h in heads}

    if page is not None:
        try:
            total = query.order_by(None).count()
        except Exception:
            total = query.count()

        page = max(1, int(page))
        per_page = max(1, min(int(per_page), 200))
        offset = (page - 1) * per_page
        projects = (
            query.options(*eager_options)
            .order_by(*order_clauses)
            .limit(per_page)
            .offset(offset)
            .all()
        )
        formatted = [_format_project_admin(p, vehicle_map, heads_map) for p in projects]
        return Pagination(items=formatted, page=page, per_page=per_page, total=total)

    projects = query.options(*eager_options).order_by(*order_clauses).all()
    return [_format_project_admin(p, vehicle_map, heads_map) for p in projects]


def get_project_form_context():
    """
    Récupère le contexte nécessaire pour le formulaire de projet (listes de sélections).
    """
    prods = Production.query.order_by(Production.name).all()
    productions_formatted = [
        {"id": str(p.id), "fields": {"Nom": p.name}} for p in prods
    ]

    contacts = Contact.query.order_by(Contact.last_name).all()
    contacts_formatted = [
        {"id": str(c.id), "name": f"{c.first_name} {c.last_name} ({c.job_title})" if c.job_title else f"{c.first_name} {c.last_name}"} for c in contacts
    ]

    # Récupération avec réconciliation des enregistrements SQL locaux
    vehicles_list = list(get_vehicles() or [])
    vehicles_map = {str(v.get("id")): v for v in vehicles_list}
    try:
        from models import Vehicle
        for lv in Vehicle.query.all():
            lvid = str(lv.id)
            if lvid not in vehicles_map:
                lfields = lv.fields or {}
                vehicles_list.append({
                    "id": lvid,
                    "fields": {
                        "name": lfields.get("name") or getattr(lv, "name", lvid),
                        "slug": lfields.get("slug") or "",
                        "order": getattr(lv, "display_order", 999),
                        "daily_rate": float(lv.daily_rate) if getattr(lv, "daily_rate", None) is not None else None,
                        "unique_id": lfields.get("unique_id") or getattr(lv, "unique_id", None),
                    }
                })
    except Exception as e:
        logger.warning(f"Erreur réconciliation véhicules formulaire projet : {e}")

    heads_list = list(get_heads() or [])
    heads_map = {str(h.get("id")): h for h in heads_list}
    try:
        from models import Head
        for lh in Head.query.all():
            lhid = str(lh.id)
            if lhid not in heads_map:
                lhfields = lh.fields or {}
                heads_list.append({
                    "id": lhid,
                    "fields": {
                        "name": lhfields.get("name") or getattr(lh, "name", lhid),
                        "slug": lhfields.get("slug") or "",
                        "order": getattr(lh, "display_order", 999),
                        "daily_rate": float(lh.daily_rate) if getattr(lh, "daily_rate", None) is not None else None,
                    }
                })
    except Exception as e:
        logger.warning(f"Erreur réconciliation têtes formulaire projet : {e}")

    bv_users = User.query.order_by(User.firstname.asc(), User.lastname.asc()).all()
    bv_users_formatted = [
        {
            "id": u.id,
            "name": f"{u.firstname} {u.lastname}".strip(),
            "mail": u.mail,
            "job": u.job,
            "role_display": u.role_display,
        }
        for u in bv_users
        if getattr(u, "role_lower", (u.role or "").lower().strip()) != "commercial"
    ]

    # Sélecteur « Commercial » : tous les utilisateurs, les commerciaux en premier
    bv_all_users_formatted = sorted(
        [
            {
                "id": u.id,
                "name": f"{u.firstname} {u.lastname}".strip(),
                "job": u.job,
                "role_display": u.role_display,
                "is_commercial": getattr(u, "role_lower", (u.role or "").lower().strip()) == "commercial",
            }
            for u in bv_users
        ],
        key=lambda u: (not u["is_commercial"], u["name"].lower()),
    )

    return {
        "productions": productions_formatted,
        "contacts": contacts_formatted,
        "vehicles": vehicles_list,
        "heads": heads_list,
        "bv_users": bv_users_formatted,
        "bv_all_users": bv_all_users_formatted,
    }


def _apply_bv_team_roles(project, form):
    """
    Affecte les rôles nominatifs de l'équipe BV (Commercial, Techniciens BV) et le contact
    Opérateur Remote Head (indépendant du matériel loué).
    """
    project.commercial_user_id = _parse_int(form.get("commercial_user_id"))
    technician_ids = [
        _parse_int(uid) for uid in (form.getlist("bv_technician_ids") if hasattr(form, 'getlist') else [])
    ]
    technician_ids = [uid for uid in technician_ids if uid is not None]
    project.bv_technicians = (
        User.query.filter(User.id.in_(technician_ids)).all() if technician_ids else []
    )
    project.remote_head_operator_contact_id = _parse_int(form.get("remote_head_operator_contact_id"))


@handle_admin_service_error
def create_project(form, user_id=None):
    """Crée un nouvel enregistrement de projet en base de données."""
    veh_ids = form.getlist("vehicle_ids") if hasattr(form, 'getlist') else []
    head_ids = form.getlist("head_ids") if hasattr(form, 'getlist') else []

    date_mode = form.get("date_mode", "continuous")
    shoot_dates = _parse_shoot_dates(form) if date_mode == "punctual" else None
    is_immob_raw = form.get("is_immobilized_between")
    if date_mode == "continuous":
        is_immobilized = True
    else:
        is_immobilized = True if is_immob_raw in (
            "true", "True", "1", True, "on") or is_immob_raw is None else False

    shoot_start_date = parse_date(form.get("shoot_start"))
    shoot_end_date = parse_date(form.get("shoot_end"))
    if date_mode == "punctual" and shoot_dates:
        if not shoot_start_date:
            shoot_start_date = parse_date(shoot_dates[0])
        if not shoot_end_date:
            shoot_end_date = parse_date(shoot_dates[-1])

    departure_date = parse_date(form.get("departure_date"))
    return_date = parse_date(form.get("return_date"))
    if date_mode == "punctual" and shoot_dates:
        if not departure_date:
            departure_date = shoot_start_date
        if not return_date:
            return_date = shoot_end_date

    prod_id = _parse_int(form.get("production_id"))
    if not prod_id:
        raise ValueError("Veuillez sélectionner une société de production valide.")

    pilot_contact_id = _parse_int(form.get("pilot_contact_id"))
    production_contact_id = _parse_int(form.get("production_contact_id"))
    dop_contact_id = _parse_int(form.get("dop_contact_id"))
    first_ac_contact_id = _parse_int(form.get("first_ac_contact_id"))
    key_grip_contact_id = _parse_int(form.get("key_grip_contact_id"))
    inter_shoot_statuses = _parse_inter_shoot_statuses(form) if date_mode == "punctual" else None

    project = Project(
        name=form.get("name"),
        production_id=prod_id,
        pilot_contact_id=pilot_contact_id,
        production_contact_id=production_contact_id,
        dop_contact_id=dop_contact_id,
        first_ac_contact_id=first_ac_contact_id,
        key_grip_contact_id=key_grip_contact_id,
        notes=form.get("notes"),
        departure_date=departure_date,
        shoot_start_date=shoot_start_date,
        shoot_end_date=shoot_end_date,
        return_date=return_date,
        date_mode=date_mode,
        is_immobilized_between=is_immobilized,
        shoot_dates=shoot_dates,
        inter_shoot_statuses=inter_shoot_statuses,
        shooting_locations=_parse_shooting_locations(form),
        vehicles_to_check=",".join(veh_ids),
        heads_to_check=",".join(head_ids),
        last_action_by_id=user_id,
    )
    _apply_bv_team_roles(project, form)
    bv_referent_ids = [
        _parse_int(uid) for uid in (form.getlist("bv_referent_ids") if hasattr(form, 'getlist') else [])
    ]
    bv_referent_ids = [uid for uid in bv_referent_ids if uid is not None]
    if bv_referent_ids:
        eligible_users = User.query.filter(User.id.in_(bv_referent_ids)).all()
        project.bv_referents = [
            u for u in eligible_users
            if getattr(u, "role_lower", (u.role or "").lower().strip()) != "commercial"
        ]

    db.session.add(project)
    db.session.flush()  # Permet d'obtenir l'ID du projet avant le commit final

    db.session.commit()

    # Déclenchement de la création de l'arborescence kDrive (post-commit)
    from services.common.kdrive import dispatch_create_project_tree
    dispatch_create_project_tree(project.id)

    return project


@handle_admin_service_error
def update_project(record_id, form, user_id=None):
    """Met à jour un projet existant en base de données."""
    project = resolve_project(record_id)
    if not project or project.deleted_at is not None:
        return False

    # Capture de l'ancien état pour détecter un éventuel déplacement kDrive
    old_date = project.departure_date or project.shoot_start_date
    old_year = old_date.strftime("%Y") if old_date else None
    old_month = old_date.strftime("%m") if old_date else None
    old_prod = project.production.name if project.production else "SANS_PRODUCTION"
    old_name = project.name

    veh_ids = form.getlist("vehicle_ids") if hasattr(form, 'getlist') else []
    head_ids = form.getlist("head_ids") if hasattr(form, 'getlist') else []

    date_mode = form.get("date_mode", project.date_mode or "continuous")
    shoot_dates = _parse_shoot_dates(form) if date_mode == "punctual" else None
    is_immob_raw = form.get("is_immobilized_between")
    if date_mode == "continuous":
        is_immobilized = True
    else:
        is_immobilized = True if is_immob_raw in (
            "true", "True", "1", True, "on") or is_immob_raw is None else False

    shoot_start_date = parse_date(form.get("shoot_start"))
    shoot_end_date = parse_date(form.get("shoot_end"))
    if date_mode == "punctual" and shoot_dates:
        if not shoot_start_date:
            shoot_start_date = parse_date(shoot_dates[0])
        if not shoot_end_date:
            shoot_end_date = parse_date(shoot_dates[-1])

    departure_date = parse_date(form.get("departure_date"))
    return_date = parse_date(form.get("return_date"))
    if date_mode == "punctual" and shoot_dates:
        if not departure_date:
            departure_date = shoot_start_date
        if not return_date:
            return_date = shoot_end_date

    prod_id = _parse_int(form.get("production_id"))
    if not prod_id:
        raise ValueError("Veuillez sélectionner une société de production valide.")

    project.name = form.get("name")
    project.production_id = prod_id
    project.pilot_contact_id = _parse_int(form.get("pilot_contact_id"))
    project.production_contact_id = _parse_int(form.get("production_contact_id"))
    project.dop_contact_id = _parse_int(form.get("dop_contact_id"))
    project.first_ac_contact_id = _parse_int(form.get("first_ac_contact_id"))
    project.key_grip_contact_id = _parse_int(form.get("key_grip_contact_id"))
    project.notes = form.get("notes")
    project.departure_date = departure_date
    project.shoot_start_date = shoot_start_date
    project.shoot_end_date = shoot_end_date
    project.return_date = return_date
    project.date_mode = date_mode
    project.is_immobilized_between = is_immobilized
    project.shoot_dates = shoot_dates
    project.inter_shoot_statuses = _parse_inter_shoot_statuses(form) if date_mode == "punctual" else None
    if "shooting_locations" in form:
        project.shooting_locations = _parse_shooting_locations(form)
    project.vehicles_to_check = ",".join(veh_ids)
    project.heads_to_check = ",".join(head_ids)
    _apply_bv_team_roles(project, form)
    project.last_action_by_id = user_id

    # Mise à jour des référents BV du projet
    bv_referent_ids = [
        _parse_int(uid) for uid in (form.getlist("bv_referent_ids") if hasattr(form, 'getlist') else [])
    ]
    bv_referent_ids = [uid for uid in bv_referent_ids if uid is not None]
    if bv_referent_ids:
        eligible_users = User.query.filter(User.id.in_(bv_referent_ids)).all()
        project.bv_referents = [
            u for u in eligible_users
            if getattr(u, "role_lower", (u.role or "").lower().strip()) != "commercial"
        ]
    else:
        project.bv_referents = []

    # Synchronisation des documents non signés avec les nouvelles dates et métadonnées du projet
    from services.admin.waivers import _format_project_shooting_dates
    formatted_dates = _format_project_shooting_dates(project, default_sep=" au ")
    waivers_to_sync = (
        ([project.active_cgl] if project.active_cgl else [])
        + list(project.active_safety_rules or [])
        + list(project.active_pilot_waivers or [])
    )
    for w in waivers_to_sync:
        if w and w.status in ("to_generate", "to_send"):
            w.project_name = project.name
            w.shooting_dates = formatted_dates
            if project.production:
                w.production_name = project.production.name
            if getattr(w, "waiver_type", None) == "safety_rules":
                w.safety_technicians = project.bv_referents_names or None

    db.session.commit()

    # Détection de renommage / déplacement kDrive
    new_date = project.departure_date or project.shoot_start_date
    new_year = new_date.strftime("%Y") if new_date else None
    new_month = new_date.strftime("%m") if new_date else None
    new_prod = project.production.name if project.production else "SANS_PRODUCTION"
    new_name = project.name

    if (old_name != new_name or old_prod != new_prod or old_year != new_year or old_month != new_month):
        from services.common.kdrive import dispatch_move_project
        dispatch_move_project(
            project.id,
            old_year=old_year,
            old_month=old_month,
            old_prod_name=old_prod,
            old_proj_name=old_name,
        )

    return True


@handle_admin_service_error
def update_project_notes(record_id, notes, user_id=None):
    """
    Met à jour spécifiquement les notes / consignes d'un projet.
    """
    project = resolve_project(record_id)
    if not project or project.deleted_at is not None:
        return None

    cleaned_notes = notes.strip() if notes else None
    project.notes = cleaned_notes
    if user_id:
        project.last_action_by_id = user_id

    db.session.commit()
    return project


def get_project_for_edit(record_id):
    """
    Récupère un projet et le formate spécifiquement pour le pré-remplissage du formulaire d'édition.
    """
    p = resolve_project(record_id)
    if not p or p.deleted_at is not None:
        return None

    veh_ids = [v.strip() for v in (p.vehicles_to_check or "").split(",")] if p.vehicles_to_check else []
    head_ids = [h.strip() for h in (p.heads_to_check or "").split(",")] if p.heads_to_check else []

    return {
        "id": p.id,
        "record_id": p.id,
        "project_id": p.project_id,
        "name": p.name,
        "departure_date_raw": str(p.departure_date) if p.departure_date else "",
        "shoot_start_raw": str(p.shoot_start_date) if p.shoot_start_date else "",
        "shoot_end_raw": str(p.shoot_end_date) if p.shoot_end_date else "",
        "return_date_raw": str(p.return_date) if p.return_date else "",
        "date_mode": p.date_mode or "continuous",
        "is_punctual": p.is_punctual,
        "is_immobilized_between": p.is_immobilized_between if p.is_immobilized_between is not None else True,
        "shoot_dates": p.shoot_dates or [],
        "shoot_dates_json": json.dumps(p.shoot_dates or []),
        "inter_shoot_statuses": p.inter_shoot_statuses or [],
        "inter_shoot_statuses_json": json.dumps(p.inter_shoot_statuses or []),
        "inter_shoot_intervals": p.get_inter_shoot_intervals() if p.is_punctual else [],
        "shooting_locations": p.locations_list,
        "locations_list": p.locations_list,
        "shooting_locations_json": json.dumps(p.locations_list),
        "production_id": str(p.production_id) if p.production_id else "",
        "pilot_contact_id": str(p.pilot_contact_id) if p.pilot_contact_id else "",
        "production_contact_id": str(p.production_contact_id) if p.production_contact_id else "",
        "dop_contact_id": str(p.dop_contact_id) if p.dop_contact_id else "",
        "first_ac_contact_id": str(p.first_ac_contact_id) if p.first_ac_contact_id else "",
        "key_grip_contact_id": str(p.key_grip_contact_id) if p.key_grip_contact_id else "",
        "commercial_user_id": str(p.commercial_user_id) if p.commercial_user_id else "",
        "remote_head_operator_contact_id": str(p.remote_head_operator_contact_id) if p.remote_head_operator_contact_id else "",
        "notes": p.notes or "",
        "vehicle_ids": veh_ids,
        "head_ids": head_ids,
        "bv_referent_ids": [u.id for u in (p.bv_referents or [])],
        "bv_technician_ids": [u.id for u in (p.bv_technicians or [])],
    }


def get_project_for_duplicate(record_id):
    """
    Récupère un projet existant et le formate pour la duplication dans le formulaire de création.
    Les identifiants propres au projet original (id, record_id, project_id) sont omis pour garantir
    la création d'un nouveau projet indépendant, tout en pré-remplissant le nom (suffixé par '(Copie)'),
    la production, les contacts de l'équipe, les véhicules, les têtes, les dates, les lieux de tournage et les notes.
    """
    p = resolve_project(record_id)
    if not p or p.deleted_at is not None:
        return None

    veh_ids = [v.strip() for v in (p.vehicles_to_check or "").split(",") if v.strip()] if p.vehicles_to_check else []
    head_ids = [h.strip() for h in (p.heads_to_check or "").split(",") if h.strip()] if p.heads_to_check else []
    locations = p.locations_list or []

    return {
        "id": None,
        "record_id": None,
        "project_id": None,
        "name": f"{p.name} (Copie)",
        "departure_date_raw": str(p.departure_date) if p.departure_date else "",
        "shoot_start_raw": str(p.shoot_start_date) if p.shoot_start_date else "",
        "shoot_end_raw": str(p.shoot_end_date) if p.shoot_end_date else "",
        "return_date_raw": str(p.return_date) if p.return_date else "",
        "date_mode": p.date_mode or "continuous",
        "is_punctual": p.is_punctual,
        "is_immobilized_between": p.is_immobilized_between if p.is_immobilized_between is not None else True,
        "shoot_dates": p.shoot_dates or [],
        "shoot_dates_json": json.dumps(p.shoot_dates or []),
        "inter_shoot_statuses": p.inter_shoot_statuses or [],
        "inter_shoot_statuses_json": json.dumps(p.inter_shoot_statuses or []),
        "inter_shoot_intervals": p.get_inter_shoot_intervals() if p.is_punctual else [],
        "shooting_locations": locations,
        "locations_list": locations,
        "shooting_locations_json": json.dumps(locations),
        "production_id": str(p.production_id) if p.production_id else "",
        "pilot_contact_id": str(p.pilot_contact_id) if p.pilot_contact_id else "",
        "production_contact_id": str(p.production_contact_id) if p.production_contact_id else "",
        "dop_contact_id": str(p.dop_contact_id) if p.dop_contact_id else "",
        "first_ac_contact_id": str(p.first_ac_contact_id) if p.first_ac_contact_id else "",
        "key_grip_contact_id": str(p.key_grip_contact_id) if p.key_grip_contact_id else "",
        "commercial_user_id": str(p.commercial_user_id) if p.commercial_user_id else "",
        "remote_head_operator_contact_id": str(p.remote_head_operator_contact_id) if p.remote_head_operator_contact_id else "",
        "notes": p.notes or "",
        "vehicle_ids": veh_ids,
        "head_ids": head_ids,
        "bv_referent_ids": [u.id for u in (p.bv_referents or [])],
        "bv_technician_ids": [u.id for u in (p.bv_technicians or [])],
        "source_project_id": p.id,
        "source_project_name": p.name,
    }


@handle_admin_service_error
def delete_project(record_id, user_id=None):
    """
    Supprime un projet et ses entités associées via soft-delete et purge physique :
    - Décharges (soft-delete, suppression des jetons, archivages et fichiers locaux)
    - Contrôles au départ et au retour (soft-delete, suppression des jetons, archivages et photos/PDF locaux)
    - Comptes-rendus d'équipe contextuels (suppression en base)
    - Nettoyage du dossier physique local du projet sous output/
    - Dossier distant kDrive et ses métadonnées
    Note : Les incidents éventuels sont préservés pour garantir l'historique d'entretien de la flotte.
    """
    p = resolve_project(record_id)
    if p and p.deleted_at is None:
        project_db_id = p.id
        folder_id = p.kdrive_folder_id

        # 1. Calcul du chemin physique local avant modification
        local_proj_path = None
        try:
            local_proj_path = get_project_base_path(p)
        except Exception as path_err:
            logger.warning(f"⚠️ Impossible de déterminer le chemin local du projet {p.id} : {path_err}")

        # 2. Supprime d'abord les décharges liées (assets locaux, jetons, archivage et soft-delete)
        try:
            from services.admin.waivers import (
                delete_cgl_internal,
                delete_safety_rules_internal,
            )
            from services.admin.waivers.pilot import delete_pilot_waiver_internal

            delete_cgl_internal(p.id)
            delete_safety_rules_internal(p.id)
            delete_pilot_waiver_internal(p.id)
        except Exception as waiver_err:
            logger.error(f"❌ Erreur suppression décharges pour projet {p.id} : {waiver_err}")

        # 3. Supprime les contrôles départ et retour liés (photos, PDF locaux, jetons et soft-delete)
        try:
            from services.admin.inspections import delete_inspection_unified

            for co in list(p.checkout_vehicles or []):
                if getattr(co, "deleted_at", None) is None:
                    delete_inspection_unified("checkout", co.id)
            for ci in list(p.checkin_vehicles or []):
                if getattr(ci, "deleted_at", None) is None:
                    delete_inspection_unified("checkin", ci.id)
        except Exception as insp_err:
            logger.error(f"❌ Erreur suppression inspections pour projet {p.id} : {insp_err}")

        # 4. Supprime les rapports d'équipe contextuels
        try:
            ProjectReport.query.filter_by(project_id=p.id).delete()
        except Exception as rep_err:
            db.session.rollback()
            logger.warning(f"⚠️ Erreur suppression rapports d'équipe projet {p.id} : {rep_err}")

        # 5. Nettoyage du dossier physique local du projet sur le serveur
        if local_proj_path and local_proj_path.exists():
            try:
                shutil.rmtree(local_proj_path, ignore_errors=True)
                logger.info(f"🗑️ Dossier physique local supprimé : {local_proj_path}")

                # Élagage des dossiers parents vides éventuels dans output/ (prod, mois, année)
                output_base = Path(current_app.config.get("OUTPUT_FOLDER", os.path.join(current_app.root_path, "output")))
                parent = local_proj_path.parent
                while parent != output_base and parent.exists():
                    if not any(parent.iterdir()):
                        parent.rmdir()
                        parent = parent.parent
                    else:
                        break
            except Exception as cleanup_err:
                logger.warning(f"⚠️ Erreur nettoyage dossier local projet {project_db_id} : {cleanup_err}")

        # 6. Soft-delete du projet
        p.deleted_at = _utcnow()
        p.last_action_by_id = user_id
        db.session.commit()

        # 7. Déclenchement de la suppression sur kDrive (post-commit)
        try:
            from services.common.kdrive import dispatch_delete_project
            dispatch_delete_project(project_db_id, folder_id)
        except Exception as k_err:
            logger.error(f"❌ Erreur dispatch suppression kDrive projet {project_db_id} : {k_err}")
    return True
