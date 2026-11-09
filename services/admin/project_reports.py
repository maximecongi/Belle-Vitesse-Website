import logging
from datetime import datetime, timezone, date
from sqlalchemy.orm import joinedload, selectinload

from models import (
    Project,
    ProjectReport,
    User,
    db
)
from models.db import _utcnow
from services.admin.status_mapping import format_waiver_status
from services.admin.projects import _format_vehicle_state, _get_secured_document_url
from services.admin.utils import handle_admin_service_error
from utils.database import get_vehicles, get_heads
from utils.formatting import format_date_fr
from utils.entity_resolvers import resolve_project

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


def _format_waiver_data(waiver, beneficiary_name: str, doc_type: str) -> dict:
    """Helper pour formater uniformément les données d'une décharge pour le contexte projet."""
    is_valid = waiver is not None and not getattr(waiver, "deleted_at", None)
    return {
        "id": waiver.id if is_valid else None,
        "waiver_num": waiver.waiver_id if (is_valid and waiver.waiver_id) else "",
        "pilot_name": beneficiary_name if (is_valid and doc_type == "pilot-waiver") else "",
        "production_name": beneficiary_name if (is_valid and doc_type in ("production-waiver", "cgl")) else "",
        "beneficiary_name": beneficiary_name if is_valid else "",
        "status": format_waiver_status(waiver.status) if is_valid else "",
        "raw_status": waiver.status if is_valid else "",
        "pdf_path": _get_secured_document_url(waiver.signed_pdf_path, doc_type) if is_valid else None,
    }


class ReportNotFoundError(ValueError):
    """Rapport inexistant, supprimé ou n'appartenant pas au projet indiqué."""


def _validate_report_fields(title, content):
    """Nettoie et valide le titre et le contenu (tous deux obligatoires)."""
    title = (title or "").strip()
    content = (content or "").strip()
    if not title:
        raise ValueError("L'intitulé / titre du rapport est obligatoire.")
    if not content:
        raise ValueError("Le contenu du rapport ne peut pas être vide.")
    return title, content


def _get_active_report(report_id, project_id=None):
    """
    Charge un rapport actif. Si `project_id` est fourni (ID ou code BVPR),
    vérifie que le rapport appartient bien à ce projet.
    """
    report = db.session.get(ProjectReport, report_id)
    if not report or report.deleted_at is not None:
        raise ReportNotFoundError("Rapport introuvable.")
    if project_id is not None:
        project = resolve_project(project_id)
        if not project or project.id != report.project_id:
            raise ReportNotFoundError("Rapport introuvable pour ce projet.")
    return report


def serialize_report(report, current_user_id=None, is_admin=False, now=None, with_permissions=False):
    """
    Sérialisation unique d'un rapport pour les vues (fiche projet, MCP).
    `with_permissions=True` ajoute can_edit / can_delete pour l'utilisateur courant.
    """
    data = {
        "id": report.id,
        "project_id": report.project_id,
        "user_id": report.user_id,
        "title": report.title,
        "author_name": report.display_author_name,
        "author_role": report.display_author_role,
        "author_job": report.author_job,
        "content": report.content,
        "created_at": report.created_at,
        "created_at_fr": _format_datetime_fr(report.created_at),
        "updated_at": report.updated_at,
        "is_edited": report.is_edited,
    }
    if with_permissions:
        data["can_edit"] = report.can_be_edited_by(current_user_id, is_admin, now)
        data["can_delete"] = report.can_be_deleted_by(current_user_id, is_admin)
    return data


@handle_admin_service_error
def add_project_report(project_id, user_id, content, title=None, author_name=None, author_role=None):
    """
    Ajoute un rapport / commentaire libre à un projet.
    Associe l'auteur (utilisateur connecté) et conserve un snapshot du nom et rôle.
    `author_name` / `author_role` permettent de surcharger ce snapshot (ex : agent MCP).
    Le titre et le contenu sont obligatoires.
    """
    title, content = _validate_report_fields(title, content)

    project = resolve_project(project_id)
    if not project or project.deleted_at is not None:
        raise ValueError("Projet introuvable.")

    snapshot_name = "Collaborateur"
    snapshot_role = "Équipe"

    if user_id:
        user = db.session.get(User, user_id)
        if user:
            snapshot_name = f"{user.firstname} {user.lastname}".strip()
            snapshot_role = user.job or user.role_display

    report = ProjectReport(
        project_id=project.id,
        user_id=user_id,
        title=title,
        author_name=author_name or snapshot_name,
        author_role=author_role or snapshot_role,
        content=content,
    )
    db.session.add(report)
    db.session.commit()
    return report


@handle_admin_service_error
def update_project_report(report_id, current_user_id, content, title=None, is_admin=False, project_id=None):
    """
    Met à jour un rapport d'équipe existant (titre et contenu).
    Seul l'auteur dans les 3 heures suivant la publication ou un administrateur peut modifier.
    Le titre et le contenu sont obligatoires.
    """
    report = _get_active_report(report_id, project_id)

    if not report.can_be_edited_by(current_user_id, is_admin):
        if not report.is_authored_by(current_user_id):
            raise PermissionError("Vous n'êtes pas autorisé à modifier ce rapport.")
        raise PermissionError(
            "La modification de ce rapport n'est plus autorisée (délai de 3 heures dépassé).")

    title, content = _validate_report_fields(title, content)

    report.content = content
    report.title = title
    report.updated_at = _utcnow()
    db.session.commit()
    return report


@handle_admin_service_error
def delete_project_report(report_id, current_user_id, is_admin=False, project_id=None):
    """
    Supprime (soft-delete) un rapport / commentaire.
    Seul l'auteur ou un administrateur est autorisé à supprimer.
    """
    report = _get_active_report(report_id, project_id)

    if not report.can_be_deleted_by(current_user_id, is_admin):
        raise PermissionError("Vous n'êtes pas autorisé à supprimer ce commentaire.")

    report.deleted_at = _utcnow()
    db.session.commit()
    return True


def list_project_reports(project_id):
    """
    Retourne la liste antéchronologique des rapports actifs d'un projet avec métadonnées formatées.
    """
    reports = ProjectReport.active().filter_by(project_id=project_id).order_by(
        ProjectReport.created_at.desc()
    ).all()
    return [serialize_report(r) for r in reports]


def get_project_detail_context(project_id, current_user_id=None, is_admin=False):
    """
    Assemble l'ensemble du contexte pour la vue Fiche / Hub Projet (Option 4).
    """
    p = resolve_project(project_id)
    if not p or p.deleted_at is not None:
        return None

    project = Project.query.filter(
        Project.id == p.id,
        Project.deleted_at.is_(None)
    ).options(
        joinedload(Project.production),
        selectinload(Project.checkout_vehicles),
        selectinload(Project.checkin_vehicles),
        joinedload(Project.pilot_contact),
        joinedload(Project.production_contact),
        joinedload(Project.dop_contact),
        joinedload(Project.first_ac_contact),
        joinedload(Project.cgl),
        selectinload(Project.safety_rules),
        selectinload(Project.pilot_waivers),
        selectinload(Project.risk_assessments),
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

    veh_ids = [v.strip()
               for v in (project.vehicles_to_check or "").split(",") if v.strip()]
    head_ids = [h.strip()
                for h in (project.heads_to_check or "").split(",") if h.strip()]

    # Statut opérationnel du projet : strictement aligné sur la charte officielle BV
    from services.admin.conflicts import _parse_date
    today_date = date.today()
    is_punctual = (getattr(project, "date_mode", None) == "punctual")
    shoot_dates = getattr(project, "shoot_dates", None) or []
    is_immob = getattr(project, "is_immobilized_between", True)

    if is_punctual and shoot_dates:
        today_iso = today_date.isoformat()
        first_shoot = _parse_date(shoot_dates[0])
        last_shoot = _parse_date(shoot_dates[-1])
        ret_d = project.return_date or last_shoot

        if today_iso in shoot_dates:
            shoot_status = "in_progress"
            shoot_status_label = "En tournage"
            shoot_status_id = "in_progress"
            shoot_status_color = "var(--entity-project, #F59E0B)"
        elif first_shoot and last_shoot and (first_shoot <= today_date <= last_shoot):
            inter_intervals = project.get_inter_shoot_intervals() if hasattr(
                project, "get_inter_shoot_intervals") else []
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
            shoot_dates_summary = f"Le {format_date_fr(shoot_dates[0])}"
        elif len(shoot_dates) > 1:
            shoot_dates_summary = f"{format_date_fr(shoot_dates[0])} → {format_date_fr(shoot_dates[-1])}"
        else:
            shoot_dates_summary = "Dates à confirmer"
    elif project.shoot_start_date and project.shoot_end_date:
        if project.shoot_start_date <= today_date <= project.shoot_end_date:
            shoot_status = "in_progress"
            shoot_status_label = "En tournage"
            shoot_status_id = "in_progress"
            shoot_status_color = "var(--entity-project, #F59E0B)"
        elif today_date > project.shoot_end_date:
            shoot_status = "completed"
            shoot_status_label = "Clôturé"
            shoot_status_id = "completed"
            shoot_status_color = "var(--status-neutral, #64748B)"
        else:
            shoot_status = "upcoming"
            shoot_status_label = "À venir"
            shoot_status_id = "upcoming"
            shoot_status_color = "var(--status-info, #0284C7)"
        shoot_dates_summary = f"{format_date_fr(str(project.shoot_start_date))} → {format_date_fr(str(project.shoot_end_date))}"
    elif project.departure_date and project.return_date:
        if project.departure_date <= today_date <= project.return_date:
            shoot_status = "in_progress"
            shoot_status_label = "En tournage"
            shoot_status_id = "in_progress"
            shoot_status_color = "var(--entity-project, #F59E0B)"
        elif today_date > project.return_date:
            shoot_status = "completed"
            shoot_status_label = "Clôturé"
            shoot_status_id = "completed"
            shoot_status_color = "var(--status-neutral, #64748B)"
        else:
            shoot_status = "upcoming"
            shoot_status_label = "À venir"
            shoot_status_id = "upcoming"
            shoot_status_color = "var(--status-info, #0284C7)"
        shoot_dates_summary = f"{format_date_fr(str(project.departure_date))} → {format_date_fr(str(project.return_date))}"
    else:
        shoot_status = "upcoming"
        shoot_status_label = "À venir"
        shoot_status_id = "upcoming"
        shoot_status_color = "var(--status-info, #0284C7)"
        shoot_dates_summary = "Dates à confirmer"

    # Rapports actifs avec permissions de modification et suppression
    now = datetime.now(timezone.utc)
    formatted_reports = [
        serialize_report(r, current_user_id, is_admin, now=now, with_permissions=True)
        for r in sorted(project.active_reports, key=lambda x: x.created_at, reverse=True)
    ]

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
        contacts_list.append(_format_contact(
            project.production_contact, "Production"))
    if project.dop_contact:
        contacts_list.append(_format_contact(
            project.dop_contact, "Chef Opérateur"))
    if project.pilot_contact:
        contacts_list.append(_format_contact(
            project.pilot_contact, "Pilote"))
    if project.first_ac_contact:
        contacts_list.append(_format_contact(
            project.first_ac_contact, "1er Assistant Caméra"))
    if project.key_grip_contact:
        contacts_list.append(_format_contact(
            project.key_grip_contact, "Chef Machiniste"))

    # Incidents
    incidents_list = []
    for inc in (project.incidents or []):
        if inc.deleted_at:
            continue
        eq_label = inc.equipment_name or ""
        if not eq_label and inc.vehicle_id:
            eq_label = vehicle_map.get(
                inc.vehicle_id, {}).get("name", inc.vehicle_id)
        incidents_list.append({
            "id": inc.id,
            "incident_number": inc.incident_number,
            "title": inc.title,
            "severity": inc.severity,
            "severity_label": inc.severity_label,
            "status": inc.status,
            "status_label": inc.status_label,
            "incident_date": format_date_fr(str(inc.incident_date)) if inc.incident_date else "",
            "equipment_name": eq_label,
        })

    first_shoot_date = project.shoot_start_date
    last_shoot_date = project.shoot_end_date
    if is_punctual and shoot_dates:
        if not first_shoot_date:
            first_shoot_date = _parse_date(shoot_dates[0])
        if not last_shoot_date:
            last_shoot_date = _parse_date(shoot_dates[-1])

    return {
        "project": project,
        "shoot_status": shoot_status,
        "shoot_status_label": shoot_status_label,
        "shoot_status_id": shoot_status_id,
        "shoot_status_color": shoot_status_color,
        "departure_date_fr": format_date_fr(str(project.departure_date)) if project.departure_date else "—",
        "shoot_start_fr": format_date_fr(str(first_shoot_date)) if first_shoot_date else "—",
        "shoot_end_fr": format_date_fr(str(last_shoot_date)) if last_shoot_date else "—",
        "return_date_fr": format_date_fr(str(project.return_date)) if project.return_date else "—",
        "date_mode": getattr(project, "date_mode", "continuous") or "continuous",
        "is_punctual": is_punctual,
        "is_immobilized_between": bool(is_immob),
        "shoot_dates": shoot_dates,
        "shoot_dates_summary": shoot_dates_summary,
        "inter_shoot_intervals": project.get_inter_shoot_intervals() if is_punctual else [],
        "vehicles": [_format_vehicle_state(project, vid, vehicle_map) for vid in veh_ids],
        "heads": [{
            "id": hid,
            "name": heads_map.get(hid, {}).get("name", "Sans nom"),
            "brand": heads_map.get(hid, {}).get("brand", ""),
            "model": heads_map.get(hid, {}).get("model", ""),
            "image": heads_map.get(hid, {}).get("thumbnail", [{}])[0].get("thumbnails", {}).get("large", {}).get("url") if heads_map.get(hid, {}).get("thumbnail") else "/static/imgs/placeholders/head.svg"
        } for hid in head_ids],
        "contacts": contacts_list,
        "reports": formatted_reports,
        "reports_count": len(formatted_reports),
        "incidents": incidents_list,
        "cgl_waiver": _format_waiver_data(
            project.active_cgl,
            (
                project.active_cgl.production_name
                if (project.active_cgl and project.active_cgl.production_name)
                else (project.production.name if project.production else "")
            ),
            "cgl",
        ),
        "safety_rules_waivers": [
            {
                "id": sr.id,
                "waiver_id": sr.waiver_id,
                "signer_name": sr.signer_name,
                "signer_role": sr.signer_role,
                "signer_role_label": sr.signer_role_label,
                "signer_email": sr.signer_email,
                "signer_phone": sr.signer_phone,
                "signer_company": sr.signer_company,
                "safety_technicians": sr.display_safety_technicians,
                "status": format_waiver_status(sr.status),
                "raw_status": sr.status,
                "signed_at": sr.signed_at,
                "bv_signed_at": sr.bv_signed_at,
                "pdf_path": _get_secured_document_url(sr.signed_pdf_path, "safety-rules"),
            }
            for sr in (project.safety_rules or [])
            if getattr(sr, "deleted_at", None) is None
        ],
        "pilot_waivers": [
            {
                "id": pw.id,
                "waiver_id": pw.waiver_id,
                "signer_name": pw.signer_name,
                "signer_role": pw.signer_role,
                "signer_role_label": pw.pilot_function_label,
                "signer_email": pw.signer_email,
                "signer_phone": pw.signer_phone,
                "signer_company": pw.signer_company,
                "vehicles": pw.vehicles,
                "status": format_waiver_status(pw.status),
                "raw_status": pw.status,
                "signed_at": pw.signed_at,
                "pdf_path": _get_secured_document_url(pw.signed_pdf_path, "pilot-attestation"),
            }
            for pw in (project.pilot_waivers or [])
            if getattr(pw, "deleted_at", None) is None
        ],
        "risk_assessment_waivers": [
            {
                "id": ra.id,
                "waiver_id": ra.waiver_id,
                "signer_name": ra.signer_name,
                "signer_role": ra.signer_role,
                "signer_role_label": ra.signer_role_label,
                "signer_email": ra.signer_email,
                "signer_phone": ra.signer_phone,
                "signer_company": ra.signer_company,
                "status": format_waiver_status(ra.status),
                "raw_status": ra.status,
                "signed_at": ra.signed_at,
                "pdf_path": _get_secured_document_url(ra.signed_pdf_path, "risk-assessment"),
            }
            for ra in (project.risk_assessments or [])
            if getattr(ra, "deleted_at", None) is None
        ],
    }
