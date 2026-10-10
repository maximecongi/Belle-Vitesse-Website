import json
import logging
import os

from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import joinedload, selectinload

from models import Contact, Production, Project, db
from services.admin.status_mapping import format_waiver_status
from utils.database import get_vehicles, get_heads
from utils.formatting import format_date_fr, get_today_paris
from utils.document_utils import generate_pdf_access_token
from services.admin.utils import handle_admin_service_error
from utils.entity_resolvers import resolve_project
from utils.pagination import Pagination

logger = logging.getLogger(__name__)


def _get_secured_document_url(path, doc_type):
    """
    Génère une URL sécurisée et tokenisée pour un document PDF.
    Le token est limité dans le temps pour garantir la sécurité des accès.
    """
    if not path:
        return None
    # Nettoie le chemin des éventuels paramètres de requête existants
    clean_path = path.split('?')[0]
    segment = f"/{doc_type}/document/"
    # Extrait uniquement le nom du fichier du chemin complet
    if segment in clean_path:
        clean_path = clean_path.split(segment)[-1]
    elif "/document/" in clean_path:
        clean_path = clean_path.split("/document/")[-1]
    # Génère le token HMAC-SHA256 pour ce fichier
    token = generate_pdf_access_token(clean_path)
    return f"/{doc_type}/document/{clean_path}?t={token}"


# ── Projets (Gestion métier) ─────────────────────────────────────


def _format_vehicle_state(project, vehicle_id, vehicle_map):
    """
    Formate l'état des contrôles (départ/retour) pour un véhicule spécifique au sein d'un projet.
    """
    from services.admin.status_mapping import get_inspection_key, format_inspection_status

    # Recherche des enregistrements correspondants non supprimés dans les collections pré-chargées du projet
    active_c_outs = [
        c for c in (project.checkout_vehicles or [])
        if str(c.vehicle_id) == str(vehicle_id) and getattr(c, "deleted_at", None) is None
    ]
    c_out = max(active_c_outs, key=lambda x: x.id) if active_c_outs else None

    active_c_ins = [
        c for c in (project.checkin_vehicles or [])
        if str(c.vehicle_id) == str(vehicle_id) and getattr(c, "deleted_at", None) is None
    ]
    c_in = max(active_c_ins, key=lambda x: x.id) if active_c_ins else None

    v_data = vehicle_map.get(vehicle_id, {})
    brand = v_data.get("brand") or ""
    model = v_data.get("model") or ""
    brand_model = f"{brand} {model}".strip()

    raw_type = v_data.get("type") or ""
    type_map = {
        "car": "Véhicule",
        "precision": "Véhicule de précision",
        "bike": "Deux-roues",
        "tracking": "Véhicule de travelling",
        "van": "Fourgon technique",
        "rickshaw": "Rickshaw de travelling",
        "segway": "Gyropode / Segway",
        "trike": "Trike électrique",
    }
    type_fr = type_map.get(
        raw_type.lower(), brand_model or "Véhicule de tournage")

    return {
        "id": vehicle_id,
        "fields": vehicle_map.get(vehicle_id, {}),
        "type_fr": type_fr,
        "checkout_status": format_inspection_status(c_out.status) if c_out else "À contrôler",
        "checkout_status_id": get_inspection_key(c_out.status) if c_out else "to_check",
        "checkout_id": c_out.id if c_out else "",
        "checkout_pdf": _get_secured_document_url(c_out.signed_pdf_path, "checkout") if c_out else None,
        "checkout_conform": "true" if (c_out and c_out.vehicle_ready) else "false",
        "checkout_ready": "true" if (c_out and c_out.vehicle_ready) else ("false" if c_out else "—"),
        "checkin_status": format_inspection_status(c_in.status) if c_in else "À contrôler",
        "checkin_status_id": get_inspection_key(c_in.status) if c_in else "to_check",
        "checkin_id": c_in.id if c_in else "",
        "checkin_pdf": _get_secured_document_url(c_in.signed_pdf_path, "checkin") if c_in else None,
        "checkin_conform": "true" if (c_in and c_in.vehicle_ready) else "false",
        "checkin_ready": "true" if (c_in and c_in.vehicle_ready) else ("false" if c_in else "—"),
    }


def _parse_date(d):
    """Utilitaire pour parser les dates (gère les vides, chaînes ISO et objets date)."""
    if not d:
        return None
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        d_str = d.strip()
        if not d_str:
            return None
        try:
            return datetime.strptime(d_str[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def get_project_shoot_status(p, today_date=None):
    """
    Détermine le statut opérationnel d'un projet (in_progress, completed, upcoming),
    son libellé, son identifiant, sa couleur sémantique et le libellé de ses dates de tournage.
    """
    if today_date is None:
        today_date = get_today_paris()

    is_punctual = (getattr(p, "date_mode", None) == "punctual")
    shoot_dates = getattr(p, "shoot_dates", None) or []
    is_immob = getattr(p, "is_immobilized_between", True)

    if is_punctual and shoot_dates:
        today_iso = today_date.isoformat()
        first_shoot = _parse_date(shoot_dates[0])
        last_shoot = _parse_date(shoot_dates[-1])
        ret_d = p.return_date or last_shoot

        if today_iso in shoot_dates:
            shoot_status = "in_progress"
            shoot_status_label = "En tournage"
            shoot_status_id = "in_progress"
            shoot_status_color = "var(--entity-project, #F59E0B)"
        elif first_shoot and last_shoot and (first_shoot <= today_date <= last_shoot):
            # Vérifier l'état d'immobilisation spécifique à l'intervalle du jour
            inter_intervals = p.get_inter_shoot_intervals() if hasattr(
                p, "get_inter_shoot_intervals") else []
            current_inter = None
            for inter in inter_intervals:
                if today_iso in inter.get("days", []):
                    current_inter = inter
                    break
            day_immob = current_inter.get(
                "is_immobilized") if current_inter else is_immob

            if day_immob:
                shoot_status = "standby"
                shoot_status_label = "Immobilisé"
                shoot_status_id = "standby"
                shoot_status_color = "var(--status-warning, #F59E0B)"
            else:
                shoot_status = "upcoming"
                shoot_status_label = "À venir"
                shoot_status_id = "upcoming"
                shoot_status_color = "var(--status-info, #0284C7)"
        elif ret_d and today_date > ret_d:
            shoot_status = "completed"
            shoot_status_label = "Clôturé"
            shoot_status_id = "completed"
            shoot_status_color = "var(--status-neutral, #64748B)"
        else:
            shoot_status = "upcoming"
            shoot_status_label = "À venir"
            shoot_status_id = "upcoming"
            shoot_status_color = "var(--status-info, #0284C7)"

        if len(shoot_dates) == 1:
            shoot_dates_label = f"Le {format_date_fr(shoot_dates[0])}"
        elif len(shoot_dates) <= 3:
            shoot_dates_label = f"Les {', '.join(format_date_fr(d) for d in shoot_dates)}"
        else:
            shoot_dates_label = f"{len(shoot_dates)} dates ({format_date_fr(shoot_dates[0])} → {format_date_fr(shoot_dates[-1])})"
    elif p.shoot_start_date and p.shoot_end_date:
        if p.shoot_start_date <= today_date <= p.shoot_end_date:
            shoot_status = "in_progress"
            shoot_status_label = "En tournage"
            shoot_status_id = "in_progress"
            shoot_status_color = "var(--entity-project, #F59E0B)"
        elif today_date > p.shoot_end_date:
            shoot_status = "completed"
            shoot_status_label = "Clôturé"
            shoot_status_id = "completed"
            shoot_status_color = "var(--status-neutral, #64748B)"
        else:
            shoot_status = "upcoming"
            shoot_status_label = "À venir"
            shoot_status_id = "upcoming"
            shoot_status_color = "var(--status-info, #0284C7)"
        shoot_dates_label = f"Du {format_date_fr(str(p.shoot_start_date))} au {format_date_fr(str(p.shoot_end_date))}"
    elif p.departure_date and p.return_date:
        if p.departure_date <= today_date <= p.return_date:
            shoot_status = "in_progress"
            shoot_status_label = "En tournage"
            shoot_status_id = "in_progress"
            shoot_status_color = "var(--entity-project, #F59E0B)"
        elif today_date > p.return_date:
            shoot_status = "completed"
            shoot_status_label = "Clôturé"
            shoot_status_id = "completed"
            shoot_status_color = "var(--status-neutral, #64748B)"
        else:
            shoot_status = "upcoming"
            shoot_status_label = "À venir"
            shoot_status_id = "upcoming"
            shoot_status_color = "var(--status-info, #0284C7)"
        shoot_dates_label = f"Du {format_date_fr(str(p.departure_date))} au {format_date_fr(str(p.return_date))}"
    else:
        shoot_status = "upcoming"
        shoot_status_label = "À venir"
        shoot_status_id = "upcoming"
        shoot_status_color = "var(--status-info, #0284C7)"
        shoot_dates_label = "Dates à confirmer"

    return {
        "status": shoot_status,
        "label": shoot_status_label,
        "id": shoot_status_id,
        "color": shoot_status_color,
        "dates_label": shoot_dates_label,
    }


def _format_project_admin(p, vehicle_map, heads_map):
    """
    Formate un enregistrement de projet pour l'affichage dans la liste d'administration.
    """
    veh_ids = [v.strip()
               for v in (p.vehicles_to_check or "").split(",") if v.strip()]
    head_ids = [h.strip()
                for h in (p.heads_to_check or "").split(",") if h.strip()]

    today_date = get_today_paris()
    status_info = get_project_shoot_status(p, today_date)
    shoot_status = status_info["status"]
    shoot_status_label = status_info["label"]
    shoot_status_id = status_info["id"]
    shoot_status_color = status_info["color"]
    shoot_dates_label = status_info["dates_label"]

    return {
        "id": p.id,
        "project_id": p.project_id,
        "name": p.name,
        "shoot_status": shoot_status,
        "shoot_status_label": shoot_status_label,
        "shoot_status_id": shoot_status_id,
        "shoot_status_color": shoot_status_color,
        "production": p.production.name if p.production else "—",
        "departure_date": format_date_fr(str(p.departure_date)) if p.departure_date else "—",
        "raw_departure_date": str(p.departure_date) if p.departure_date else "",
        "shoot_start": format_date_fr(str(p.shoot_start_date)) if p.shoot_start_date else "—",
        "raw_shoot_start": str(p.shoot_start_date) if p.shoot_start_date else "",
        "shoot_end": format_date_fr(str(p.shoot_end_date)) if p.shoot_end_date else "—",
        "raw_shoot_end": str(p.shoot_end_date) if p.shoot_end_date else "",
        "return_date": format_date_fr(str(p.return_date)) if p.return_date else "—",
        "raw_return_date": str(p.return_date) if p.return_date else "",
        "raw_checkin_date": str(p.return_date) if p.return_date else "",
        "date_mode": getattr(p, "date_mode", "continuous") or "continuous",
        "is_immobilized_between": bool(getattr(p, "is_immobilized_between", True)),
        "shoot_dates": getattr(p, "shoot_dates", None) or [],
        "shoot_dates_count": len(getattr(p, "shoot_dates", None) or []),
        "shoot_dates_label": shoot_dates_label,
        "notes": p.notes or "",
        "pilot_contact_name": f"{p.pilot_contact.first_name} {p.pilot_contact.last_name}" if p.pilot_contact else "—",
        "production_contact_name": f"{p.production_contact.first_name} {p.production_contact.last_name}" if p.production_contact else "—",
        "dop_contact_name": f"{p.dop_contact.first_name} {p.dop_contact.last_name}" if p.dop_contact else "—",
        "first_ac_contact_name": f"{p.first_ac_contact.first_name} {p.first_ac_contact.last_name}" if p.first_ac_contact else "—",
        "key_grip_contact_name": f"{p.key_grip_contact.first_name} {p.key_grip_contact.last_name}" if p.key_grip_contact else "—",
        "vehicles": [_format_vehicle_state(p, vid, vehicle_map) for vid in veh_ids],
        "heads": [{
            "id": hid,
            "name": heads_map.get(hid, {}).get("name", "Sans nom"),
            "brand": heads_map.get(hid, {}).get("brand", ""),
            "model": heads_map.get(hid, {}).get("model", "")
        } for hid in head_ids],
        "pilot_waiver": {
            "id": p.pilot_waiver.id if (p.pilot_waiver and not p.pilot_waiver.deleted_at) else None,
            "waiver_num": p.pilot_waiver.waiver_id if (p.pilot_waiver and not p.pilot_waiver.deleted_at) else "",
            "pilot_name": f"{p.pilot_waiver.pilot_first_name or ''} {p.pilot_waiver.pilot_last_name or ''}".strip() if (p.pilot_waiver and not p.pilot_waiver.deleted_at and (p.pilot_waiver.pilot_first_name or p.pilot_waiver.pilot_last_name)) else (f"{p.pilot_contact.first_name} {p.pilot_contact.last_name}" if p.pilot_contact else ""),
            "status": format_waiver_status(p.pilot_waiver.status) if (p.pilot_waiver and not p.pilot_waiver.deleted_at) else "",
            "raw_status": p.pilot_waiver.status if (p.pilot_waiver and not p.pilot_waiver.deleted_at) else "",
            "pdf_path": _get_secured_document_url(p.pilot_waiver.signed_pdf_path, "pilot-waiver") if (p.pilot_waiver and not p.pilot_waiver.deleted_at) else None,
        },
        "production_waiver": {
            "id": p.production_waiver.id if (p.production_waiver and not p.production_waiver.deleted_at) else None,
            "waiver_num": p.production_waiver.waiver_id if (p.production_waiver and not p.production_waiver.deleted_at) else "",
            "production_name": p.production_waiver.production_name if (p.production_waiver and not p.production_waiver.deleted_at and p.production_waiver.production_name) else (p.production.name if p.production else ""),
            "status": format_waiver_status(p.production_waiver.status) if (p.production_waiver and not p.production_waiver.deleted_at) else "",
            "raw_status": p.production_waiver.status if (p.production_waiver and not p.production_waiver.deleted_at) else "",
            "pdf_path": _get_secured_document_url(p.production_waiver.signed_pdf_path, "production-waiver") if (p.production_waiver and not p.production_waiver.deleted_at) else None,
        },
        "reports_count": len(p.reports) if hasattr(p, 'reports') and p.reports else 0,
        "incidents": [
            {
                "id": inc.id,
                "incident_number": inc.incident_number,
                "title": inc.title,
                "severity": inc.severity,
                "severity_label": inc.severity_label,
                "status": inc.status,
                "status_label": inc.status_label,
                "signature_status": inc.signature_status,
                "is_fully_signed": inc.is_fully_signed,
                "signature_status_label": inc.signature_status_label,
            }
            for inc in (getattr(p, "incidents", []) or [])
            if not getattr(inc, "deleted_at", None)
        ],
        "incidents_count": len([inc for inc in (getattr(p, "incidents", []) or []) if not getattr(inc, "deleted_at", None)]),
    }


def list_projects(
    is_archive: Optional[bool] = None,
    q: Optional[str] = None,
    page: Optional[int] = None,
    per_page: int = 10,
):
    """
    Récupère les projets et les formate pour la liste d'administration (avec chargement lié optimisé).
    Supporte le filtrage SQL (archives, recherche textuelle) et la pagination serveur.
    Si `page` est spécifié, retourne une instance `Pagination`.
    Si `page` est None, retourne la liste complète (rétrocompatibilité totale).
    """
    query = Project.query.filter(Project.deleted_at.is_(None))

    today = date.today()

    if is_archive is True:
        query = query.filter(Project.return_date.isnot(
            None), Project.return_date < today)
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
        selectinload(Project.checkout_vehicles),
        selectinload(Project.checkin_vehicles),
        joinedload(Project.pilot_contact),
        joinedload(Project.production_contact),
        joinedload(Project.dop_contact),
        joinedload(Project.first_ac_contact),
        joinedload(Project.key_grip_contact),
        joinedload(Project.pilot_waiver),
        joinedload(Project.production_waiver),
        selectinload(Project.incidents),
        selectinload(Project.reports),
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
        formatted = [_format_project_admin(
            p, vehicle_map, heads_map) for p in projects]
        return Pagination(items=formatted, page=page, per_page=per_page, total=total)

    projects = query.options(*eager_options).order_by(*order_clauses).all()
    return [_format_project_admin(p, vehicle_map, heads_map) for p in projects]


def get_project_form_context():
    """
    Récupère le contexte nécessaire pour le formulaire de projet (listes de sélections).
    """
    prods = Production.query.order_by(Production.name).all()
    productions_formatted = [
        {"id": str(p.id), "fields": {"Nom": p.name}} for p in prods]

    contacts = Contact.query.order_by(Contact.last_name).all()
    contacts_formatted = [
        {"id": str(c.id), "name": f"{c.first_name} {c.last_name} ({c.job_title})" if c.job_title else f"{c.first_name} {c.last_name}"} for c in contacts
    ]

    return {
        "productions": productions_formatted,
        "contacts": contacts_formatted,
        "vehicles": get_vehicles(),
        "heads": get_heads(),
    }


def _parse_shoot_dates(form):
    """Parse et trie la liste des dates de tournage transmises par le formulaire."""
    val = form.get("shoot_dates") if hasattr(form, "get") else None
    if isinstance(val, str) and val.strip():
        try:
            dates = json.loads(val)
            if not isinstance(dates, list):
                dates = [s.strip() for s in val.split(",") if s.strip()]
        except Exception:
            dates = [s.strip() for s in val.split(",") if s.strip()]
    elif isinstance(val, list):
        dates = val
    else:
        dates = []

    valid_dates = []
    for d in dates:
        if isinstance(d, str) and d.strip():
            valid_dates.append(d.strip())
    return sorted(list(set(valid_dates)))


def _parse_int(val):
    """Convertit en entier ou None si non numérique ou vide."""
    if val is None:
        return None
    try:
        s = str(val).strip()
        return int(s) if s.isdigit() else None
    except (ValueError, TypeError):
        return None


def _parse_inter_shoot_statuses(form):
    """Parse la liste des statuts d'immobilisation personnalisés par intervalle."""
    val = form.get("inter_shoot_statuses") if hasattr(form, "get") else None
    if isinstance(val, str) and val.strip():
        try:
            parsed = json.loads(val)
        except Exception:
            parsed = []
    elif isinstance(val, (list, dict)):
        parsed = val
    else:
        parsed = []

    valid = []
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict) and "start" in item and "end" in item:
                valid.append({
                    "start": str(item["start"]).strip(),
                    "end": str(item["end"]).strip(),
                    "is_immobilized": bool(item.get("is_immobilized", True)),
                })
    elif isinstance(parsed, dict):
        for k, v in parsed.items():
            if "_" in k:
                parts = k.split("_")
                is_immob = bool(v.get("is_immobilized", True)
                                ) if isinstance(v, dict) else bool(v)
                valid.append({
                    "start": parts[0].strip(),
                    "end": parts[1].strip(),
                    "is_immobilized": is_immob,
                })
    return valid


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

    shoot_start_date = _parse_date(form.get("shoot_start"))
    shoot_end_date = _parse_date(form.get("shoot_end"))
    if date_mode == "punctual" and shoot_dates:
        if not shoot_start_date:
            shoot_start_date = _parse_date(shoot_dates[0])
        if not shoot_end_date:
            shoot_end_date = _parse_date(shoot_dates[-1])

    departure_date = _parse_date(form.get("departure_date"))
    return_date = _parse_date(form.get("return_date"))
    if date_mode == "punctual" and shoot_dates:
        if not departure_date:
            departure_date = shoot_start_date
        if not return_date:
            return_date = shoot_end_date

    prod_id = _parse_int(form.get("production_id"))
    if not prod_id:
        raise ValueError(
            "Veuillez sélectionner une société de production valide.")

    pilot_contact_id = _parse_int(form.get("pilot_contact_id"))
    production_contact_id = _parse_int(form.get("production_contact_id"))
    dop_contact_id = _parse_int(form.get("dop_contact_id"))
    first_ac_contact_id = _parse_int(form.get("first_ac_contact_id"))
    key_grip_contact_id = _parse_int(form.get("key_grip_contact_id"))
    inter_shoot_statuses = _parse_inter_shoot_statuses(
        form) if date_mode == "punctual" else None

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
        vehicles_to_check=",".join(veh_ids),
        heads_to_check=",".join(head_ids),
        last_action_by_id=user_id
    )
    db.session.add(project)
    db.session.flush()  # Permet d'obtenir l'ID du projet avant le commit final

    db.session.commit()

    # Déclenchement de la création de l'arborescence kDrive (post-commit)
    from services.common.kdrive import dispatch_create_project_tree
    dispatch_create_project_tree(project.id)

    # Création automatique des décharges si les entités associées existent
    try:
        from services.admin.waivers import create_production_waiver, create_pilot_waiver
        if project.production_id:
            create_production_waiver(project.id)
        if project.pilot_contact_id:
            create_pilot_waiver(project.id)
    except Exception as e_w:
        logger.warning(
            f"⚠️ Erreur lors de l'auto-création des décharges pour le projet {project.id}: {e_w}")

    return True


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

    shoot_start_date = _parse_date(form.get("shoot_start"))
    shoot_end_date = _parse_date(form.get("shoot_end"))
    if date_mode == "punctual" and shoot_dates:
        if not shoot_start_date:
            shoot_start_date = _parse_date(shoot_dates[0])
        if not shoot_end_date:
            shoot_end_date = _parse_date(shoot_dates[-1])

    departure_date = _parse_date(form.get("departure_date"))
    return_date = _parse_date(form.get("return_date"))
    if date_mode == "punctual" and shoot_dates:
        if not departure_date:
            departure_date = shoot_start_date
        if not return_date:
            return_date = shoot_end_date

    prod_id = _parse_int(form.get("production_id"))
    if not prod_id:
        raise ValueError(
            "Veuillez sélectionner une société de production valide.")

    project.name = form.get("name")
    project.production_id = prod_id
    project.pilot_contact_id = _parse_int(form.get("pilot_contact_id"))
    project.production_contact_id = _parse_int(
        form.get("production_contact_id"))
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
    project.inter_shoot_statuses = _parse_inter_shoot_statuses(
        form) if date_mode == "punctual" else None
    project.vehicles_to_check = ",".join(veh_ids)
    project.heads_to_check = ",".join(head_ids)
    project.last_action_by_id = user_id

    # Synchronisation des décharges non signées avec les nouvelles dates et métadonnées du projet
    from services.admin.waivers import _format_project_shooting_dates
    formatted_dates = _format_project_shooting_dates(project, default_sep=" au ")
    for w in [project.pilot_waiver, project.production_waiver]:
        if w and w.status in ("to_generate", "to_send"):
            w.project_name = project.name
            w.shooting_dates = formatted_dates
            if project.production:
                w.production_name = project.production.name

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

    # Auto-création des décharges si non encore existantes et nouvelles entités assignées
    try:
        from services.admin.waivers import create_production_waiver, create_pilot_waiver
        from models import PilotWaiver, ProductionWaiver
        if project.production_id and not ProductionWaiver.query.filter_by(project_id=project.id, deleted_at=None).first():
            create_production_waiver(project.id)
        if project.pilot_contact_id and not PilotWaiver.query.filter_by(project_id=project.id, deleted_at=None).first():
            create_pilot_waiver(project.id)
    except Exception as e_w:
        logger.warning(
            f"⚠️ Erreur lors de l'auto-création des décharges à la mise à jour du projet {project.id}: {e_w}")

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

    veh_ids = [v.strip() for v in (p.vehicles_to_check or "").split(
        ",")] if p.vehicles_to_check else []
    head_ids = [h.strip() for h in (p.heads_to_check or "").split(
        ",")] if p.heads_to_check else []

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
        "production_id": str(p.production_id) if p.production_id else "",
        "pilot_contact_id": str(p.pilot_contact_id) if p.pilot_contact_id else "",
        "production_contact_id": str(p.production_contact_id) if p.production_contact_id else "",
        "dop_contact_id": str(p.dop_contact_id) if p.dop_contact_id else "",
        "first_ac_contact_id": str(p.first_ac_contact_id) if p.first_ac_contact_id else "",
        "key_grip_contact_id": str(p.key_grip_contact_id) if p.key_grip_contact_id else "",
        "notes": p.notes or "",
        "vehicle_ids": veh_ids,
        "head_ids": head_ids,
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
        import shutil
        from pathlib import Path
        from flask import current_app
        from models import ProjectReport
        from models.db import _utcnow
        from services.admin.inspections import delete_inspection_unified
        from services.admin.waivers import (
            delete_pilot_waiver_internal,
            delete_production_waiver_internal,
        )
        from utils.storage import get_project_base_path

        project_db_id = p.id
        folder_id = p.kdrive_folder_id

        # 1. Calcul du chemin physique local avant modification
        local_proj_path = None
        try:
            local_proj_path = get_project_base_path(p)
        except Exception as path_err:
            logger.warning(
                f"⚠️ Impossible de déterminer le chemin local du projet {p.id} : {path_err}")

        # 2. Supprime d'abord les décharges liées (assets locaux, jetons, archivage et soft-delete)
        try:
            delete_pilot_waiver_internal(p.id)
            delete_production_waiver_internal(p.id)
        except Exception as waiver_err:
            logger.error(
                f"❌ Erreur suppression décharges pour projet {p.id} : {waiver_err}")

        # 3. Supprime les contrôles départ et retour liés (photos, PDF locaux, jetons et soft-delete)
        try:
            for co in list(p.checkout_vehicles or []):
                if getattr(co, "deleted_at", None) is None:
                    delete_inspection_unified("checkout", co.id)
            for ci in list(p.checkin_vehicles or []):
                if getattr(ci, "deleted_at", None) is None:
                    delete_inspection_unified("checkin", ci.id)
        except Exception as insp_err:
            logger.error(
                f"❌ Erreur suppression inspections pour projet {p.id} : {insp_err}")

        # 4. Supprime les rapports d'équipe contextuels
        try:
            ProjectReport.query.filter_by(project_id=p.id).delete()
        except Exception as rep_err:
            logger.warning(
                f"⚠️ Erreur suppression rapports d'équipe projet {p.id} : {rep_err}")

        # 5. Nettoyage du dossier physique local du projet sur le serveur
        if local_proj_path and local_proj_path.exists():
            try:
                shutil.rmtree(local_proj_path, ignore_errors=True)
                logger.info(f"🗑️ Dossier physique local supprimé : {local_proj_path}")

                # Élagage des dossiers parents vides éventuels dans output/ (prod, mois, année)
                output_base = Path(current_app.config.get(
                    "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output")))
                parent = local_proj_path.parent
                while parent != output_base and parent.exists():
                    if not any(parent.iterdir()):
                        parent.rmdir()
                        parent = parent.parent
                    else:
                        break
            except Exception as cleanup_err:
                logger.warning(
                    f"⚠️ Erreur nettoyage dossier local projet {project_db_id} : {cleanup_err}")

        # 6. Soft-delete du projet
        p.deleted_at = _utcnow()
        p.last_action_by_id = user_id
        db.session.commit()

        # 7. Déclenchement de la suppression sur kDrive (post-commit)
        try:
            from services.common.kdrive import dispatch_delete_project
            dispatch_delete_project(project_db_id, folder_id)
        except Exception as k_err:
            logger.error(
                f"❌ Erreur dispatch suppression kDrive projet {project_db_id} : {k_err}")
    return True
