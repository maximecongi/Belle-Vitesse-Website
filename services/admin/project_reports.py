import logging
from datetime import datetime, timezone, date
from sqlalchemy.orm import joinedload, selectinload

from models import (
    Contact,
    Production,
    Project,
    ProjectReport,
    User,
    PreQuote,
    Incident,
    db
)
from services.admin.status_mapping import format_waiver_status
from services.admin.projects import _format_vehicle_state, _get_secured_document_url
from utils.database import get_vehicles, get_heads
from utils.formatting import format_date_fr

logger = logging.getLogger(__name__)


def _format_datetime_fr(dt):
    """Formate une date/heure pour un affichage lisible en français."""
    if not dt:
        return ""
    months = [
        "janv.", "févr.", "mars", "avr.", "mai", "juin",
        "juil.", "août", "sept.", "oct.", "nov.", "déc."
    ]
    month_str = months[dt.month - 1]
    return f"{dt.day} {month_str} {dt.year} à {dt.strftime('%H:%M')}"


def add_project_report(project_id, user_id, content):
    """
    Ajoute un rapport / commentaire libre à un projet.
    Associe l'auteur (utilisateur connecté) et conserve un snapshot du nom et rôle.
    """
    content = (content or "").strip()
    if not content:
        raise ValueError("Le contenu du commentaire ne peut pas être vide.")

    project = Project.query.filter(Project.id == project_id, Project.deleted_at.is_(None)).first()
    if not project:
        raise ValueError("Projet introuvable.")

    author_name = "Collaborateur"
    author_role = "Équipe"

    if user_id:
        user = db.session.get(User, user_id)
        if user:
            author_name = f"{user.firstname} {user.lastname}".strip()
            author_role = user.job or user.role_display

    report = ProjectReport(
        project_id=project.id,
        user_id=user_id,
        author_name=author_name,
        author_role=author_role,
        content=content,
    )
    db.session.add(report)
    db.session.commit()
    return report


def delete_project_report(report_id, current_user_id, is_admin=False):
    """
    Supprime un rapport / commentaire.
    Seul l'auteur ou un administrateur est autorisé à supprimer.
    """
    report = db.session.get(ProjectReport, report_id)
    if not report:
        raise ValueError("Commentaire introuvable.")

    # Vérification des droits : auteur ou administrateur
    is_author = (current_user_id is not None and report.user_id == current_user_id)
    if not is_author and not is_admin:
        raise PermissionError("Vous n'êtes pas autorisé à supprimer ce commentaire.")

    db.session.delete(report)
    db.session.commit()
    return True


def list_project_reports(project_id):
    """
    Retourne la liste ordonnée chronologiquement des rapports d'un projet avec métadonnées formatées.
    """
    reports = ProjectReport.query.filter_by(project_id=project_id).order_by(
        ProjectReport.created_at.asc()
    ).all()

    return [{
        "id": r.id,
        "project_id": r.project_id,
        "user_id": r.user_id,
        "author_name": r.author_name or (f"{r.user.firstname} {r.user.lastname}" if r.user else "Collaborateur"),
        "author_role": r.author_role or (r.user.role_display if r.user else "Équipe"),
        "author_job": (r.user.job if (r.user and r.user.job) else (r.author_role or "Équipe")),
        "content": r.content,
        "created_at": r.created_at,
        "created_at_fr": _format_datetime_fr(r.created_at),
        "updated_at": r.updated_at,
    } for r in reports]


def get_project_detail_context(project_id, current_user_id=None, is_admin=False):
    """
    Assemble l'ensemble du contexte pour la vue Fiche / Hub Projet (Option 4).
    """
    project = Project.query.filter(
        Project.id == project_id,
        Project.deleted_at.is_(None)
    ).options(
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
        selectinload(Project.pre_quotes).selectinload(PreQuote.versions),
        selectinload(Project.incidents),
        selectinload(Project.reports).joinedload(ProjectReport.user)
    ).first()

    if not project:
        return None

    # Chargement cartes Airtable
    vehicles = get_vehicles()
    vehicle_map = {v["id"]: v.get("fields", {}) for v in vehicles}

    heads = get_heads()
    heads_map = {h["id"]: h.get("fields", {}) for h in heads}

    veh_ids = [v.strip() for v in (project.vehicles_to_check or "").split(",") if v.strip()]
    head_ids = [h.strip() for h in (project.heads_to_check or "").split(",") if h.strip()]

    # Statut opérationnel du projet : strictement aligné sur la Timeline Véhicule (in_progress -> "En tournage", completed -> "Clôturé", upcoming -> "À venir")
    today_date = date.today()
    if project.shoot_start_date and project.shoot_end_date:
        if project.shoot_start_date <= today_date <= project.shoot_end_date:
            shoot_status = "in_progress"
            shoot_status_label = "En tournage"
            shoot_status_id = "in_progress"
            shoot_status_color = "#3b82f6"
        elif today_date > project.shoot_end_date:
            shoot_status = "completed"
            shoot_status_label = "Clôturé"
            shoot_status_id = "cloture"
            shoot_status_color = "#64748b"
        else:
            shoot_status = "upcoming"
            shoot_status_label = "À venir"
            shoot_status_id = "neutral"
            shoot_status_color = "#8b5cf6"
    elif project.departure_date and project.return_date:
        if project.departure_date <= today_date <= project.return_date:
            shoot_status = "in_progress"
            shoot_status_label = "En tournage"
            shoot_status_id = "in_progress"
            shoot_status_color = "#3b82f6"
        elif today_date > project.return_date:
            shoot_status = "completed"
            shoot_status_label = "Clôturé"
            shoot_status_id = "cloture"
            shoot_status_color = "#64748b"
        else:
            shoot_status = "upcoming"
            shoot_status_label = "À venir"
            shoot_status_id = "neutral"
            shoot_status_color = "#8b5cf6"
    else:
        shoot_status = "upcoming"
        shoot_status_label = "À venir"
        shoot_status_id = "neutral"
        shoot_status_color = "#8b5cf6"

    # Formattage des rapports avec permissions de suppression
    formatted_reports = []
    for r in sorted(project.reports, key=lambda x: x.created_at):
        can_delete = (current_user_id is not None and r.user_id == current_user_id) or is_admin
        job = r.user.job if (r.user and r.user.job) else (r.author_role or "Équipe")
        formatted_reports.append({
            "id": r.id,
            "project_id": r.project_id,
            "user_id": r.user_id,
            "author_name": r.author_name or (f"{r.user.firstname} {r.user.lastname}" if r.user else "Collaborateur"),
            "author_role": r.author_role or (r.user.role_display if r.user else "Équipe"),
            "author_job": job,
            "content": r.content,
            "created_at": r.created_at,
            "created_at_fr": _format_datetime_fr(r.created_at),
            "can_delete": can_delete,
        })

    # Contacts enrichis
    def _format_contact(c, role_title):
        if not c:
            return None
        return {
            "id": c.id,
            "role_title": role_title,
            "full_name": f"{c.first_name} {c.last_name}".strip(),
            "phone": c.phone or "",
            "mail": c.mail or "",
            "job_title": c.job_title or role_title,
        }

    contacts_list = []
    if project.production_contact:
        contacts_list.append(_format_contact(project.production_contact, "Production"))
    if project.dop_contact:
        contacts_list.append(_format_contact(project.dop_contact, "Directeur de la Photo (DOP)"))
    if project.pilot_contact:
        contacts_list.append(_format_contact(project.pilot_contact, "Pilote de précision"))
    if project.first_ac_contact:
        contacts_list.append(_format_contact(project.first_ac_contact, "1er Assistant Caméra"))
    if project.key_grip_contact:
        contacts_list.append(_format_contact(project.key_grip_contact, "Chef Machiniste"))

    # Incidents
    incidents_list = [{
        "id": inc.id,
        "incident_number": inc.incident_number,
        "title": inc.title,
        "severity": inc.severity,
        "severity_label": inc.severity_label,
        "status": inc.status,
        "status_label": inc.status_label,
        "incident_date": format_date_fr(str(inc.incident_date)) if inc.incident_date else "",
    } for inc in (project.incidents or []) if not inc.deleted_at]

    return {
        "project": project,
        "shoot_status": shoot_status,
        "shoot_status_label": shoot_status_label,
        "shoot_status_id": shoot_status_id,
        "shoot_status_color": shoot_status_color,
        "departure_date_fr": format_date_fr(str(project.departure_date)) if project.departure_date else "—",
        "shoot_start_fr": format_date_fr(str(project.shoot_start_date)) if project.shoot_start_date else "—",
        "shoot_end_fr": format_date_fr(str(project.shoot_end_date)) if project.shoot_end_date else "—",
        "return_date_fr": format_date_fr(str(project.return_date)) if project.return_date else "—",
        "vehicles": [_format_vehicle_state(project, vid, vehicle_map) for vid in veh_ids],
        "heads": [{
            "id": hid,
            "name": heads_map.get(hid, {}).get("name", "Sans nom"),
            "brand": heads_map.get(hid, {}).get("brand", ""),
            "model": heads_map.get(hid, {}).get("model", ""),
            "image": heads_map.get(hid, {}).get("thumbnail", [{}])[0].get("thumbnails", {}).get("small", {}).get("url") if heads_map.get(hid, {}).get("thumbnail") else None
        } for hid in head_ids],
        "contacts": contacts_list,
        "reports": formatted_reports,
        "reports_count": len(formatted_reports),
        "incidents": incidents_list,
        "pilot_waiver": {
            "id": project.pilot_waiver.id if (project.pilot_waiver and not project.pilot_waiver.deleted_at) else None,
            "waiver_num": project.pilot_waiver.waiver_id if (project.pilot_waiver and not project.pilot_waiver.deleted_at) else "",
            "status": format_waiver_status(project.pilot_waiver.status) if (project.pilot_waiver and not project.pilot_waiver.deleted_at) else "",
            "raw_status": project.pilot_waiver.status if (project.pilot_waiver and not project.pilot_waiver.deleted_at) else "",
            "pdf_path": _get_secured_document_url(project.pilot_waiver.signed_pdf_path, "pilot-waiver") if (project.pilot_waiver and not project.pilot_waiver.deleted_at) else None,
        },
        "production_waiver": {
            "id": project.production_waiver.id if (project.production_waiver and not project.production_waiver.deleted_at) else None,
            "waiver_num": project.production_waiver.waiver_id if (project.production_waiver and not project.production_waiver.deleted_at) else "",
            "status": format_waiver_status(project.production_waiver.status) if (project.production_waiver and not project.production_waiver.deleted_at) else "",
            "raw_status": project.production_waiver.status if (project.production_waiver and not project.production_waiver.deleted_at) else "",
            "pdf_path": _get_secured_document_url(project.production_waiver.signed_pdf_path, "production-waiver") if (project.production_waiver and not project.production_waiver.deleted_at) else None,
        },
        "pre_quotes": [{
            "id": pq.id,
            "reference": pq.reference,
            "total_ht": float(pq.total_ht),
            "status": pq.status,
            "latest_version": max([v.version_number for v in pq.versions]) if pq.versions else None
        } for pq in project.pre_quotes] if getattr(project, 'pre_quotes', None) else []
    }
