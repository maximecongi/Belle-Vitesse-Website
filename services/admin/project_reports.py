import logging
import re
from datetime import datetime, timedelta, timezone, date

from flask import current_app, render_template
from sqlalchemy.orm import joinedload, selectinload

from models import (
    Project,
    ProjectReport,
    User,
    db
)
from models.db import _utcnow
from models.project_report import (
    DEFAULT_REPORT_CATEGORY,
    REPORT_CATEGORIES,
    REPORT_CATEGORY_LABELS,
    REPORT_MAX_PHOTOS,
)
from services.admin.incidents.media import _delete_stored_file, _output_base, _save_uploaded_files
from utils.document_utils import render_pdf_from_template
from utils.pagination import Pagination
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


REPORT_PHOTOS_ROOT = "reports"
REPORT_PHOTOS_PREFIX = f"{REPORT_PHOTOS_ROOT}/photos"

_WEEKDAYS_FR = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
_MONTHS_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
              "juil.", "août", "sept.", "oct.", "nov.", "déc."]
_MAX_SHOOT_DAYS = 90


def _format_day_fr(d):
    """« mar. 14 oct. 2026 »"""
    if not d:
        return ""
    return f"{_WEEKDAYS_FR[d.weekday()]} {d.day} {_MONTHS_FR[d.month - 1]} {d.year}"


def _validate_report_fields(title, content):
    """Nettoie et valide le titre et le contenu (tous deux obligatoires)."""
    title = (title or "").strip()
    content = (content or "").strip()
    if not title:
        raise ValueError("L'intitulé / titre du rapport est obligatoire.")
    if not content:
        raise ValueError("Le contenu du rapport ne peut pas être vide.")
    return title, content


def _parse_category(value):
    """Catégorie valide ou catégorie par défaut (« note »)."""
    value = (value or "").strip().lower()
    return value if value in REPORT_CATEGORY_LABELS else DEFAULT_REPORT_CATEGORY


def _parse_shoot_day(value):
    """Accepte une date ou une chaîne ISO (AAAA-MM-JJ) ; vide → None."""
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        raise ValueError("Jour de tournage invalide (format attendu : AAAA-MM-JJ).")


def project_shoot_days(project):
    """
    Jours proposés pour rattacher un rapport : dates ponctuelles de tournage,
    sinon période de tournage continue, sinon période départ → retour.
    """
    if not project:
        return []
    dates = []
    if getattr(project, "date_mode", None) == "punctual" and project.shoot_dates:
        for raw in project.shoot_dates:
            try:
                dates.append(_parse_shoot_day(raw))
            except ValueError:
                continue
    else:
        start = project.shoot_start_date or project.departure_date
        end = project.shoot_end_date or project.return_date
        if start and end and start <= end:
            current = start
            while current <= end and len(dates) < _MAX_SHOOT_DAYS:
                dates.append(current)
                current += timedelta(days=1)
    return sorted({d for d in dates if d})


def shoot_day_choices(project):
    """[(iso, « J1 · mar. 14 oct. 2026 »), ...] pour les listes déroulantes."""
    return [(d.isoformat(), f"J{i} · {_format_day_fr(d)}") for i, d in enumerate(project_shoot_days(project), start=1)]


_MONTHS_FULL_FR = ["janvier", "février", "mars", "avril", "mai", "juin",
                   "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def _shoot_day_heading(project, d):
    """Intitulé de groupe de la timeline : « J1 · mer. 25 novembre 2026 » (ou « Sans jour de tournage »)."""
    if not d:
        return "Sans jour de tournage"
    long_date = f"{_WEEKDAYS_FR[d.weekday()]} {d.day} {_MONTHS_FULL_FR[d.month - 1]} {d.year}"
    days = project_shoot_days(project)
    return f"J{days.index(d) + 1} · {long_date}" if d in days else long_date


def _format_datetime_short_fr(dt):
    """« 9 nov. à 19:09 » (l'année n'est ajoutée que si elle diffère de l'année en cours)."""
    if not dt:
        return ""
    year = f" {dt.year}" if dt.year != datetime.now().year else ""
    return f"{dt.day} {_MONTHS_FR[dt.month - 1]}{year} à {dt.strftime('%H:%M')}"


def group_reports_by_day(reports):
    """
    Regroupe des rapports sérialisés par jour de tournage pour la timeline :
    jours du plus récent au plus ancien, rapports non rattachés en dernier ;
    dans chaque groupe, du plus récent au plus ancien.
    """
    groups = {}
    for r in reports:
        groups.setdefault(r["shoot_day"], {"day": r["shoot_day"], "heading": r["shoot_day_heading"], "reports": []})
        groups[r["shoot_day"]]["reports"].append(r)
    ordered = sorted((g for k, g in groups.items() if k), key=lambda g: g["day"], reverse=True)
    if "" in groups:
        ordered.append(groups[""])
    for g in ordered:
        g["reports"].sort(key=lambda r: r["created_at"] or datetime.min, reverse=True)
    return ordered


def _shoot_day_label(project, d):
    if not d:
        return ""
    days = project_shoot_days(project)
    if d in days:
        return f"J{days.index(d) + 1} · {_format_day_fr(d)}"
    return _format_day_fr(d)


def _get_report(report_id, project_id=None, *, deleted=False):
    """
    Charge un rapport actif (ou supprimé si `deleted=True`). Si `project_id` est fourni
    (ID ou code BVPR), vérifie que le rapport appartient bien à ce projet.
    """
    report = db.session.get(ProjectReport, report_id)
    if not report or (report.deleted_at is not None) != deleted:
        raise ReportNotFoundError("Rapport introuvable.")
    if project_id is not None:
        project = resolve_project(project_id)
        if not project or project.id != report.project_id:
            raise ReportNotFoundError("Rapport introuvable pour ce projet.")
    return report


def _get_active_report(report_id, project_id=None):
    return _get_report(report_id, project_id)


def _save_report_photos(files, existing_count=0):
    """Enregistre les photos uploadées (optimisées) et retourne leurs chemins relatifs."""
    files = [f for f in (files or []) if f and getattr(f, "filename", None)]
    if not files:
        return []
    if existing_count + len(files) > REPORT_MAX_PHOTOS:
        raise ValueError(f"Un rapport ne peut pas contenir plus de {REPORT_MAX_PHOTOS} photos.")
    return _save_uploaded_files(files, subfolder="photos", root=REPORT_PHOTOS_ROOT)


def serialize_report(report, current_user_id=None, is_admin=False, now=None, with_permissions=False):
    """
    Sérialisation unique d'un rapport pour les vues (fiche projet, MCP, recherche, PDF).
    `with_permissions=True` ajoute can_edit / can_delete / editable_until pour l'utilisateur courant.
    """
    project = report.project
    data = {
        "id": report.id,
        "project_id": report.project_id,
        "user_id": report.user_id,
        "title": report.title,
        "author_name": report.display_author_name,
        "author_role": report.display_author_role,
        "author_job": report.author_job,
        "content": report.content,
        "category": report.category_key,
        "category_label": report.category_label,
        "category_variant": report.category_variant,
        "shoot_day": report.shoot_day.isoformat() if report.shoot_day else "",
        "shoot_day_label": _shoot_day_label(project, report.shoot_day),
        "shoot_day_heading": _shoot_day_heading(project, report.shoot_day),
        "photos": [{"url": f"/files/{p}", "rel_path": p} for p in report.photo_paths],
        "created_at": report.created_at,
        "created_at_fr": _format_datetime_fr(report.created_at),
        "created_at_short": _format_datetime_short_fr(report.created_at),
        "updated_at": report.updated_at,
        "is_edited": report.is_edited,
        "deleted_at": report.deleted_at,
        "deleted_at_fr": _format_datetime_fr(report.deleted_at) if report.deleted_at else "",
        "deleted_by_name": (
            f"{report.deleted_by.firstname} {report.deleted_by.lastname}".strip() if report.deleted_by else ""
        ),
    }
    if with_permissions:
        can_edit = report.can_be_edited_by(current_user_id, is_admin, now)
        data["can_edit"] = can_edit
        data["can_delete"] = report.can_be_deleted_by(current_user_id, is_admin)
        # Compte à rebours affiché uniquement pour l'auteur non administrateur
        data["editable_until"] = (
            report.editable_until.isoformat() if (can_edit and not is_admin) else ""
        )
    return data


@handle_admin_service_error
def add_project_report(project_id, user_id, content, title=None, author_name=None, author_role=None,
                       category=None, shoot_day=None, photos=None):
    """
    Ajoute un rapport / commentaire libre à un projet.
    Associe l'auteur (utilisateur connecté) et conserve un snapshot du nom et rôle.
    `author_name` / `author_role` permettent de surcharger ce snapshot (ex : agent MCP).
    `photos` : liste de fichiers uploadés (FileStorage). Le titre et le contenu sont obligatoires.
    """
    title, content = _validate_report_fields(title, content)
    category = _parse_category(category)
    shoot_day = _parse_shoot_day(shoot_day)

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
        category=category,
        shoot_day=shoot_day,
    )
    report.photo_paths = _save_report_photos(photos)
    db.session.add(report)
    db.session.commit()
    return report


_UNSET = object()


@handle_admin_service_error
def update_project_report(report_id, current_user_id, content, title=None, is_admin=False, project_id=None,
                          category=_UNSET, shoot_day=_UNSET, new_photos=None, remove_photos=None):
    """
    Met à jour un rapport d'équipe existant (titre, contenu, catégorie, jour, photos).
    Seul l'auteur dans les 3 heures suivant la publication ou un administrateur peut modifier.
    Les champs catégorie / jour ne sont modifiés que s'ils sont fournis.
    """
    report = _get_active_report(report_id, project_id)

    if not report.can_be_edited_by(current_user_id, is_admin):
        if not report.is_authored_by(current_user_id):
            raise PermissionError("Vous n'êtes pas autorisé à modifier ce rapport.")
        raise PermissionError(
            "La modification de ce rapport n'est plus autorisée (délai de 3 heures dépassé).")

    title, content = _validate_report_fields(title, content)
    if category is not _UNSET:
        report.category = _parse_category(category)
    if shoot_day is not _UNSET:
        report.shoot_day = _parse_shoot_day(shoot_day)

    # Photos : retraits (uniquement parmi les photos du rapport) puis ajouts
    current = report.photo_paths
    to_remove = [p for p in (remove_photos or []) if p in current]
    kept = [p for p in current if p not in to_remove]
    added = _save_report_photos(new_photos, existing_count=len(kept))
    report.photo_paths = kept + added

    report.content = content
    report.title = title
    report.updated_at = _utcnow()
    db.session.commit()

    for rel in to_remove:
        _delete_stored_file(rel, REPORT_PHOTOS_PREFIX)
    return report


@handle_admin_service_error
def delete_project_report(report_id, current_user_id, is_admin=False, project_id=None):
    """
    Supprime (soft-delete) un rapport / commentaire. Les photos sont conservées pour permettre
    la restauration. Seul l'auteur ou un administrateur est autorisé à supprimer.
    """
    report = _get_active_report(report_id, project_id)

    if not report.can_be_deleted_by(current_user_id, is_admin):
        raise PermissionError("Vous n'êtes pas autorisé à supprimer ce commentaire.")

    report.deleted_at = _utcnow()
    report.deleted_by_id = current_user_id
    db.session.commit()
    return True


@handle_admin_service_error
def restore_project_report(report_id, current_user_id, is_super_admin=False, project_id=None):
    """
    Restaure un rapport supprimé. Autorisé uniquement à la personne qui l'a créé puis
    supprimé elle-même, ou au super administrateur.
    """
    report = _get_report(report_id, project_id, deleted=True)
    if not report.can_be_restored_by(current_user_id, is_super_admin):
        raise PermissionError(
            "Seule la personne qui a rédigé puis supprimé ce rapport, ou le super administrateur, peut le restaurer.")
    report.deleted_at = None
    report.deleted_by_id = None
    db.session.commit()
    return report


def list_project_reports(project_id):
    """
    Retourne la liste antéchronologique des rapports actifs d'un projet avec métadonnées formatées.
    """
    reports = ProjectReport.active().filter_by(project_id=project_id).order_by(
        ProjectReport.created_at.desc()
    ).all()
    return [serialize_report(r) for r in reports]


def list_deleted_reports(project_id, current_user_id=None, is_super_admin=False):
    """
    Corbeille d'un projet, limitée aux rapports que l'utilisateur peut restaurer :
    tous pour le super administrateur, sinon ceux qu'il a rédigés puis supprimés lui-même.
    """
    q = ProjectReport.query.filter(
        ProjectReport.project_id == project_id,
        ProjectReport.deleted_at.isnot(None),
    )
    if not is_super_admin:
        if not current_user_id:
            return []
        q = q.filter(
            ProjectReport.user_id == current_user_id,
            ProjectReport.deleted_by_id == current_user_id,
        )
    return [serialize_report(r) for r in q.order_by(ProjectReport.deleted_at.desc()).all()]


def report_item_context(report, current_user_id=None, is_admin=False):
    """Contexte du partial `admin/_report_item.html` (rendu serveur et réponses AJAX)."""
    return {
        "report": serialize_report(report, current_user_id, is_admin, with_permissions=True),
        "project_id": report.project_id,
        "report_categories": [(k, label) for k, label, _ in REPORT_CATEGORIES],
        "report_days": shoot_day_choices(report.project),
        "report_max_photos": REPORT_MAX_PHOTOS,
    }


# ── Recherche transversale ──────────────────────────────────────

_MD_NOISE = re.compile(r"[#>*`_~\[\]]|^\s*[-+]\s+|^\s*\d+\.\s+|\((?:https?|mailto):[^)]*\)", re.MULTILINE)


def _plain_snippet(content, query=None, width=180):
    """Extrait texte (Markdown retiré) centré sur la première occurrence de la recherche."""
    plain = re.sub(r"\s+", " ", _MD_NOISE.sub(" ", content or "")).strip()
    if len(plain) <= width:
        return plain
    idx = plain.lower().find((query or "").lower()) if query else -1
    start = max(0, idx - width // 3) if idx >= 0 else 0
    snippet = plain[start:start + width].strip()
    return ("…" if start > 0 else "") + snippet + ("…" if start + width < len(plain) else "")


def search_reports(query=None, category=None, project_id=None, page=1, per_page=20):
    """
    Recherche plein texte dans les rapports actifs des projets non supprimés
    (titre, contenu, auteur, poste), filtrable par catégorie et par projet. Retourne une Pagination.
    """
    q = ProjectReport.active().join(Project).filter(Project.deleted_at.is_(None)).options(
        joinedload(ProjectReport.project), joinedload(ProjectReport.user)
    )
    if project_id:
        project = resolve_project(project_id)
        q = q.filter(ProjectReport.project_id == (project.id if project else -1))
    category = (category or "").strip().lower()
    if category in REPORT_CATEGORY_LABELS:
        q = q.filter(ProjectReport.category == category)
    term = (query or "").strip()
    if term:
        like = f"%{term}%"
        q = q.filter(
            ProjectReport.title.ilike(like)
            | ProjectReport.content.ilike(like)
            | ProjectReport.author_name.ilike(like)
            | ProjectReport.author_role.ilike(like)
            | Project.name.ilike(like)
        )

    total = q.count()
    page = max(1, int(page or 1))
    rows = q.order_by(ProjectReport.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    items = []
    for r in rows:
        data = serialize_report(r)
        data.update({
            "project_name": r.project.name if r.project else "Projet",
            "project_code": r.project.project_id if r.project else "",
            "snippet": _plain_snippet(r.content, term),
        })
        items.append(data)
    return Pagination(items=items, page=page, per_page=per_page, total=total)


# ── Export PDF du journal de bord ───────────────────────────────

def _report_photo_uri(rel_path):
    """URI fichier absolue d'une photo (WeasyPrint lit directement le disque)."""
    path = (_output_base() / rel_path).resolve()
    return path.as_uri() if path.exists() else None


def build_reports_export_context(project_id, category=None, shoot_day=None):
    """Données du journal de bord (filtrable par catégorie et par jour) pour le PDF."""
    project = resolve_project(project_id)
    if not project or project.deleted_at is not None:
        return None
    q = ProjectReport.active().filter(ProjectReport.project_id == project.id)
    category = (category or "").strip().lower()
    if category in REPORT_CATEGORY_LABELS:
        q = q.filter(ProjectReport.category == category)
    day = _parse_shoot_day(shoot_day) if shoot_day else None
    if day:
        q = q.filter(ProjectReport.shoot_day == day)
    # Ordre chronologique pour un journal de bord
    reports = []
    for r in q.order_by(ProjectReport.created_at.asc()).all():
        data = serialize_report(r)
        data["photo_uris"] = [u for u in (_report_photo_uri(p) for p in r.photo_paths) if u]
        reports.append(data)

    filters = []
    if category in REPORT_CATEGORY_LABELS:
        filters.append(f"Catégorie : {REPORT_CATEGORY_LABELS[category]}")
    if day:
        filters.append(f"Jour : {_shoot_day_label(project, day)}")
    return {
        "project": project,
        "reports": reports,
        "filters_label": " · ".join(filters),
        "generated_at_fr": _format_datetime_fr(datetime.now(timezone.utc)),
    }


def generate_project_reports_pdf(project_id, category=None, shoot_day=None, base_url=None):
    """Compile le journal de bord du projet en PDF (WeasyPrint). Retourne (bytes, nom de fichier)."""
    ctx = build_reports_export_context(project_id, category, shoot_day)
    if ctx is None:
        return None, None
    project = ctx["project"]
    company_name = current_app.config.get("COMPANY_NAME", "Belle Vitesse")
    html = render_template(
        "pdf/project_reports.html",
        company_name=company_name,
        doc_id=project.project_id,
        is_preview=False,
        **ctx,
    )
    filename = f"Journal-{project.project_id or project.id}.pdf"
    pdf = render_pdf_from_template(
        html_content=html,
        base_url=base_url or "http://localhost",
        stylesheets=["css/pdf/project-reports-pdf.css"],
        filename=filename,
        compress=True,
    )
    return pdf, filename


def get_project_detail_context(project_id, current_user_id=None, is_admin=False, is_super_admin=False):
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
        "report_groups": group_reports_by_day(formatted_reports),
        "deleted_reports": list_deleted_reports(project.id, current_user_id, is_super_admin),
        "report_categories": [(k, label) for k, label, _ in REPORT_CATEGORIES],
        "report_days": shoot_day_choices(project),
        "report_max_photos": REPORT_MAX_PHOTOS,
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
