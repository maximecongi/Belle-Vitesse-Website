import json
import logging
import os
import uuid
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

from models import db, Project, User, Vehicle
from models.incident import Incident
from models.db import _utcnow
from utils.document_utils import render_pdf_from_template

logger = logging.getLogger(__name__)

# ── Dictionnaires de Correspondance ──────────────────────────────

INCIDENT_CATEGORY_MAP = {
    "vehicule": "Véhicule",
    "materiel_camera": "Matériel Caméra / Tête",
    "mecanique": "Mécanique",
    "electrique": "Électrique / Batterie",
    "carrosserie": "Carrosserie",
    "accident_tiers": "Accident avec tiers",
    "meteo": "Intempéries / Météo",
    "securite": "Sécurité / Humain",
    "autre": "Autre incident",
}

INCIDENT_SEVERITY_MAP = {
    "mineur": "Mineur",
    "modere": "Modéré",
    "critique": "Critique",
}

INCIDENT_STATUS_MAP = {
    "signale": "Signalé",
    "en_expertise": "En expertise / Devis",
    "en_reparation": "En réparation atelier",
    "assurance": "Dossier assurance",
    "resolu": "Résolu / Réparé",
    "cloture": "Clôturé",
}

INCIDENT_STATUS_ICONS = {
    "signale": "📣",
    "en_expertise": "🔍",
    "en_reparation": "🔧",
    "assurance": "📋",
    "resolu": "✅",
    "cloture": "🔒",
}

INCIDENT_STATUS_BADGE_VALS = {
    "signale": "neutral",
    "en_expertise": "warning",
    "en_reparation": "in_progress",
    "assurance": "assurance",
    "resolu": "ok",
    "cloture": "cloture",
}

INCIDENT_IMPACT_MAP = {
    "aucun": "Aucun impact",
    "retard": "Retard sur planning",
    "interruption": "Interruption temporaire",
    "annulation": "Annulation de session",
}


def _clean_str(val):
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _parse_date(val):
    if not val:
        return None
    if isinstance(val, (date, datetime)):
        return val if isinstance(val, date) else val.date()
    val_str = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(val_str, fmt).date()
        except ValueError:
            pass
    return None


def _format_date(val):
    if not val:
        return "—"
    if isinstance(val, (date, datetime)):
        return val.strftime("%d/%m/%Y")
    return str(val)


# ── Services Métier Incidents ────────────────────────────────────

def list_incidents(status=None, severity=None, category=None, project_id=None, query=None, limit=None, offset=None):
    """
    Récupère la liste des incidents actifs (non supprimés) avec calcul des indicateurs KPI et filtres.
    """
    base_query = Incident.query.filter(Incident.deleted_at.is_(None))

    # Calcul des statistiques globales sur l'ensemble des incidents actifs
    all_active = base_query.all()
    stats = {
        "total": len(all_active),
        "in_progress": sum(1 for i in all_active if i.is_active),
        "critical": sum(1 for i in all_active if i.is_critical and i.status != "cloture"),
        "reparation": sum(1 for i in all_active if i.status == "en_reparation"),
        "total_estimated_cost": sum(float(i.estimated_cost or 0) for i in all_active if i.is_active),
        "total_actual_cost": sum(float(i.actual_cost or 0) for i in all_active),
    }

    # Application des filtres
    q = base_query
    if status:
        q = q.filter(Incident.status == status)
    if severity:
        q = q.filter(Incident.severity == severity)
    if category:
        q = q.filter(Incident.category == category)
    if project_id:
        try:
            p_id = int(project_id)
            q = q.filter(Incident.project_id == p_id)
        except (ValueError, TypeError):
            pass

    # Recherche textuelle insensible
    if query:
        term = f"%{query.strip()}%"
        q = q.filter(
            db.or_(
                Incident.incident_number.ilike(term),
                Incident.title.ilike(term),
                Incident.location.ilike(term),
                Incident.description.ilike(term),
                Incident.equipment_name.ilike(term),
            )
        )

    q = q.order_by(Incident.incident_date.desc(), Incident.created_at.desc())

    if offset:
        q = q.offset(offset)
    if limit:
        q = q.limit(limit)

    records = q.all()

    # Enrichissement pour l'affichage
    formatted_incidents = []
    for inc in records:
        vehicle_obj = None
        if inc.vehicle_id:
            vehicle_obj = db.session.get(Vehicle, inc.vehicle_id)

        v_name = (vehicle_obj.fields.get("name") or inc.vehicle_id) if (vehicle_obj and vehicle_obj.fields) else (inc.vehicle_id or "—")

        reporter_name = f"{inc.reporter.firstname} {inc.reporter.lastname}" if inc.reporter else "—"
        project_name = inc.project.name if inc.project else "—"

        photos = inc.photos_list
        primary_photo = photos[0] if photos else None
        if primary_photo and not primary_photo.startswith("/"):
            primary_photo = f"/files/{primary_photo}"

        search_tokens = [
            inc.incident_number,
            inc.title,
            project_name,
            v_name,
            inc.equipment_name or "",
            reporter_name,
            inc.location or "",
            INCIDENT_STATUS_MAP.get(inc.status, inc.status),
            INCIDENT_SEVERITY_MAP.get(inc.severity, inc.severity),
            INCIDENT_CATEGORY_MAP.get(inc.category, inc.category),
        ]

        formatted_incidents.append({
            "id": inc.id,
            "incident_number": inc.incident_number,
            "title": inc.title,
            "date": _format_date(inc.incident_date),
            "date_raw": inc.incident_date.isoformat() if inc.incident_date else "",
            "project_name": project_name,
            "project_id": inc.project_id,
            "vehicle_name": v_name,
            "vehicle_id": inc.vehicle_id,
            "equipment_name": inc.equipment_name or "—",
            "reporter_name": reporter_name,
            "category": inc.category,
            "category_label": INCIDENT_CATEGORY_MAP.get(inc.category, inc.category),
            "severity": inc.severity,
            "severity_label": INCIDENT_SEVERITY_MAP.get(inc.severity, inc.severity),
            "status": inc.status,
            "status_label": INCIDENT_STATUS_MAP.get(inc.status, inc.status),
            "status_icon": INCIDENT_STATUS_ICONS.get(inc.status, "📣"),
            "status_badge_val": INCIDENT_STATUS_BADGE_VALS.get(inc.status, "neutral"),
            "status_display": f"{INCIDENT_STATUS_ICONS.get(inc.status, '📣')} {INCIDENT_STATUS_MAP.get(inc.status, inc.status)}",
            "shooting_impact": inc.shooting_impact,
            "shooting_impact_label": INCIDENT_IMPACT_MAP.get(inc.shooting_impact, inc.shooting_impact),
            "estimated_cost": float(inc.estimated_cost) if inc.estimated_cost is not None else None,
            "actual_cost": float(inc.actual_cost) if inc.actual_cost is not None else None,
            "insurance_declared": inc.insurance_declared,
            "photos_count": len(photos),
            "primary_photo": primary_photo,
            "is_critical": inc.is_critical,
            "is_active": inc.is_active,
            "search_text": " ".join(t.lower() for t in search_tokens if t),
        })

    return {
        "incidents": formatted_incidents,
        "stats": stats,
    }


def get_incident_detail(record_id):
    """
    Récupère le détail exhaustif d'un incident par son ID ou numéro.
    """
    inc = None
    if isinstance(record_id, int) or (isinstance(record_id, str) and record_id.isdigit()):
        inc = db.session.get(Incident, int(record_id))
    if not inc:
        inc = Incident.query.filter_by(incident_number=str(record_id)).first()

    if not inc or inc.deleted_at is not None:
        return None

    # Enrichissement Véhicule
    vehicle_obj = None
    if inc.vehicle_id:
        vehicle_obj = db.session.get(Vehicle, inc.vehicle_id)

    vehicle_data = None
    if vehicle_obj:
        fields = vehicle_obj.fields or {}
        vehicle_data = {
            "id": vehicle_obj.id,
            "name": fields.get("name") or vehicle_obj.id,
            "unique_id": fields.get("unique_id", ""),
            "daily_rate": float(vehicle_obj.daily_rate or 0),
        }

    # Photos avec URL publiques complètes
    photos_display = []
    for p in inc.photos_list:
        clean_path = p.lstrip("/")
        if not clean_path.startswith("files/"):
            url = f"/files/{clean_path}"
        else:
            url = f"/{clean_path}"
        photos_display.append({
            "rel_path": p,
            "url": url,
            "filename": os.path.basename(p),
        })

    # Documents joints
    docs_display = []
    for d in inc.documents_list:
        clean_path = d.lstrip("/")
        if not clean_path.startswith("files/"):
            url = f"/files/{clean_path}"
        else:
            url = f"/{clean_path}"
        docs_display.append({
            "rel_path": d,
            "url": url,
            "filename": os.path.basename(d),
        })

    return {
        "id": inc.id,
        "incident_number": inc.incident_number,
        "title": inc.title,
        "incident_date": _format_date(inc.incident_date),
        "incident_date_raw": inc.incident_date.isoformat() if inc.incident_date else "",
        "incident_time": inc.incident_time or "—",
        "location": inc.location or "—",
        "category": inc.category,
        "category_label": INCIDENT_CATEGORY_MAP.get(inc.category, inc.category),
        "severity": inc.severity,
        "severity_label": INCIDENT_SEVERITY_MAP.get(inc.severity, inc.severity),
        "status": inc.status,
        "status_label": INCIDENT_STATUS_MAP.get(inc.status, inc.status),
        "status_icon": INCIDENT_STATUS_ICONS.get(inc.status, "📣"),
        "status_badge_val": INCIDENT_STATUS_BADGE_VALS.get(inc.status, "neutral"),
        "status_display": f"{INCIDENT_STATUS_ICONS.get(inc.status, '📣')} {INCIDENT_STATUS_MAP.get(inc.status, inc.status)}",
        "shooting_impact": inc.shooting_impact,
        "shooting_impact_label": INCIDENT_IMPACT_MAP.get(inc.shooting_impact, inc.shooting_impact),
        "description": inc.description or "",
        "immediate_actions": inc.immediate_actions or "",
        "project": {
            "id": inc.project.id,
            "name": inc.project.name,
            "production_name": inc.project.production.name if inc.project.production else "—",
            "start_date": _format_date(inc.project.shoot_start_date),
            "end_date": _format_date(inc.project.shoot_end_date),
            "location": getattr(inc.project, "location", "—") or "—",
        } if inc.project else None,
        "vehicle": vehicle_data,
        "equipment_name": inc.equipment_name or "",
        "reporter": {
            "id": inc.reporter.id,
            "name": f"{inc.reporter.firstname} {inc.reporter.lastname}",
            "role": inc.reporter.role_display if hasattr(inc.reporter, "role_display") else inc.reporter.role,
            "mail": inc.reporter.mail,
            "phone": inc.reporter.phone or "—",
        } if inc.reporter else None,
        "checkout": {
            "id": inc.checkout.id,
            "inspection_number": inc.checkout.inspection_number,
            "inspection_date": _format_date(inc.checkout.inspection_date),
        } if inc.checkout else None,
        "checkin": {
            "id": inc.checkin.id,
            "inspection_number": inc.checkin.inspection_number,
            "inspection_date": _format_date(inc.checkin.inspection_date),
        } if inc.checkin else None,
        "estimated_cost": float(inc.estimated_cost) if inc.estimated_cost is not None else None,
        "actual_cost": float(inc.actual_cost) if inc.actual_cost is not None else None,
        "insurance_declared": inc.insurance_declared,
        "insurance_reference": inc.insurance_reference or "—",
        "insurance_notes": inc.insurance_notes or "",
        "photos": photos_display,
        "documents": docs_display,
        "resolution_notes": inc.resolution_notes or "",
        "resolved_at": _format_date(inc.resolved_at) if inc.resolved_at else None,
        "created_at": _format_date(inc.created_at),
        "updated_at": _format_date(inc.updated_at),
        "is_critical": inc.is_critical,
        "is_active": inc.is_active,
    }


def create_incident(form_data, uploaded_photos=None, uploaded_documents=None):
    """
    Crée un nouvel incident de tournage avec téléversement sécurisé de photos et pièces.
    """
    title = form_data.get("title", "").strip()
    if not title:
        raise ValueError("Le titre de l'incident est obligatoire.")

    raw_date = form_data.get("incident_date")
    parsed_date = _parse_date(raw_date) or date.today()

    # Conversion des clés relationnelles
    project_id = form_data.get("project_id")
    project_id = int(project_id) if project_id and str(project_id).isdigit() else None

    reported_by_id = form_data.get("reported_by_id")
    if not reported_by_id:
        from flask import session
        try:
            reported_by_id = session.get("admin_user_id")
        except Exception:
            reported_by_id = None
    if not reported_by_id:
        from models import User
        u = User.query.first()
        if u:
            reported_by_id = u.id
    else:
        try:
            reported_by_id = int(reported_by_id)
        except Exception:
            reported_by_id = None

    checkout_id = form_data.get("checkout_id")
    checkout_id = int(checkout_id) if checkout_id and str(checkout_id).isdigit() else None

    checkin_id = form_data.get("checkin_id")
    checkin_id = int(checkin_id) if checkin_id and str(checkin_id).isdigit() else None

    # Montants financiers
    est_cost = form_data.get("estimated_cost")
    try:
        estimated_cost = Decimal(str(est_cost).replace(",", ".")) if est_cost else None
    except Exception:
        estimated_cost = None

    act_cost = form_data.get("actual_cost")
    try:
        actual_cost = Decimal(str(act_cost).replace(",", ".")) if act_cost else None
    except Exception:
        actual_cost = None

    ins_declared = form_data.get("insurance_declared") in (True, "true", "True", "1", "on", "yes")

    # Enregistrement initial
    incident = Incident(
        title=title,
        project_id=project_id,
        vehicle_id=_clean_str(form_data.get("vehicle_id")),
        equipment_name=_clean_str(form_data.get("equipment_name")),
        reported_by_id=reported_by_id,
        incident_date=parsed_date,
        incident_time=_clean_str(form_data.get("incident_time")),
        location=_clean_str(form_data.get("location")),
        category=form_data.get("category") or "vehicule",
        severity=form_data.get("severity") or "modere",
        status=form_data.get("status") or "signale",
        shooting_impact=form_data.get("shooting_impact") or "aucun",
        description=_clean_str(form_data.get("description")),
        immediate_actions=_clean_str(form_data.get("immediate_actions")),
        checkout_id=checkout_id,
        checkin_id=checkin_id,
        estimated_cost=estimated_cost,
        actual_cost=actual_cost,
        insurance_declared=ins_declared,
        insurance_reference=_clean_str(form_data.get("insurance_reference")),
        insurance_notes=_clean_str(form_data.get("insurance_notes")),
        resolution_notes=_clean_str(form_data.get("resolution_notes")),
    )

    if incident.status in ("resolu", "cloture"):
        incident.resolved_at = _utcnow()

    # Traitement des fichiers téléversés
    photos_paths = _save_uploaded_files(uploaded_photos, subfolder="photos")
    if photos_paths:
        incident.photos = json.dumps(photos_paths)

    docs_paths = _save_uploaded_files(uploaded_documents, subfolder="docs")
    if docs_paths:
        incident.documents = json.dumps(docs_paths)

    db.session.add(incident)
    db.session.commit()

    logger.info(f"✅ Incident créé : {incident.incident_number} - {incident.title}")
    return incident


def update_incident(record_id, form_data, uploaded_photos=None, uploaded_documents=None, removed_photos=None):
    """
    Met à jour un incident existant, gère l'ajout/suppression de photos et les changements de statut.
    """
    incident = db.session.get(Incident, int(record_id))
    if not incident or incident.deleted_at is not None:
        raise ValueError(f"Incident #{record_id} introuvable.")

    if "title" in form_data:
        t = form_data.get("title", "").strip()
        if not t:
            raise ValueError("Le titre ne peut pas être vide.")
        incident.title = t

    if "incident_date" in form_data:
        parsed = _parse_date(form_data.get("incident_date"))
        if parsed:
            incident.incident_date = parsed

    if "incident_time" in form_data:
        incident.incident_time = _clean_str(form_data.get("incident_time"))

    if "project_id" in form_data:
        pid = form_data.get("project_id")
        incident.project_id = int(pid) if pid and str(pid).isdigit() else None

    if "vehicle_id" in form_data:
        incident.vehicle_id = _clean_str(form_data.get("vehicle_id"))

    if "equipment_name" in form_data:
        incident.equipment_name = _clean_str(form_data.get("equipment_name"))

    if "reported_by_id" in form_data:
        rid = form_data.get("reported_by_id")
        incident.reported_by_id = int(rid) if rid and str(rid).isdigit() else None

    if "location" in form_data:
        incident.location = _clean_str(form_data.get("location"))

    if "category" in form_data:
        incident.category = form_data.get("category", incident.category)

    if "severity" in form_data:
        incident.severity = form_data.get("severity", incident.severity)

    if "status" in form_data:
        new_status = form_data.get("status", incident.status)
        if new_status in ("resolu", "cloture") and incident.status not in ("resolu", "cloture"):
            incident.resolved_at = _utcnow()
        elif new_status not in ("resolu", "cloture"):
            incident.resolved_at = None
        incident.status = new_status

    if "shooting_impact" in form_data:
        incident.shooting_impact = form_data.get("shooting_impact", incident.shooting_impact)

    if "description" in form_data:
        incident.description = _clean_str(form_data.get("description"))

    if "immediate_actions" in form_data:
        incident.immediate_actions = _clean_str(form_data.get("immediate_actions"))

    if "estimated_cost" in form_data:
        est = form_data.get("estimated_cost")
        try:
            incident.estimated_cost = Decimal(str(est).replace(",", ".")) if est else None
        except Exception:
            incident.estimated_cost = None

    if "actual_cost" in form_data:
        act = form_data.get("actual_cost")
        try:
            incident.actual_cost = Decimal(str(act).replace(",", ".")) if act else None
        except Exception:
            incident.actual_cost = None

    if "insurance_declared" in form_data:
        incident.insurance_declared = form_data.get("insurance_declared") in (True, "true", "True", "1", "on", "yes")

    if "insurance_reference" in form_data:
        incident.insurance_reference = _clean_str(form_data.get("insurance_reference"))

    if "insurance_notes" in form_data:
        incident.insurance_notes = _clean_str(form_data.get("insurance_notes"))

    if "resolution_notes" in form_data:
        incident.resolution_notes = _clean_str(form_data.get("resolution_notes"))

    # Gestion des photos : suppression des demandées et ajout des nouvelles
    current_photos = incident.photos_list
    if removed_photos:
        current_photos = [p for p in current_photos if p not in removed_photos]

    new_photos = _save_uploaded_files(uploaded_photos, subfolder="photos")
    if new_photos:
        current_photos.extend(new_photos)
    incident.photos = json.dumps(current_photos) if current_photos else None

    # Gestion des documents joints
    current_docs = incident.documents_list
    new_docs = _save_uploaded_files(uploaded_documents, subfolder="docs")
    if new_docs:
        current_docs.extend(new_docs)
    incident.documents = json.dumps(current_docs) if current_docs else None

    db.session.commit()
    logger.info(f"✅ Incident mis à jour : {incident.incident_number}")
    return incident


def delete_incident(record_id, confirm=True):
    """
    Suppression logique (soft-delete) d'un incident.
    """
    if not confirm:
        return {"status": "requires_confirmation", "message": "Veuillez confirmer la suppression de cet incident."}

    incident = db.session.get(Incident, int(record_id))
    if not incident:
        return {"success": False, "message": "Incident introuvable."}

    incident.deleted_at = _utcnow()
    db.session.commit()
    logger.info(f"🗑️ Incident soft-deleted : {incident.incident_number}")
    return {"success": True, "message": f"Incident {incident.incident_number} supprimé avec succès."}


def get_incident_form_context():
    """
    Données de référence pour les sélecteurs de formulaires (projets, véhicules, utilisateurs, constantes).
    """
    # Projets actifs
    projects = (
        Project.query.filter(Project.deleted_at.is_(None))
        .order_by(Project.departure_date.desc())
        .all()
    )


    # Utilisateurs de l'équipe
    users = User.query.order_by(User.lastname, User.firstname).all()

    # Dictionnaire de référence pour tous les véhicules
    vehicle_map = {}
    try:
        from utils.database import get_vehicles
        for v in get_vehicles() or []:
            vid = str(v.get("id"))
            fields = v.get("fields") or {}
            name = fields.get("name") or fields.get("Nom") or vid
            vehicle_map[vid] = {"id": vid, "name": name}
    except Exception:
        pass
    try:
        for v in Vehicle.query.all():
            vid = str(v.id)
            fields = v.fields or {}
            name = fields.get("name") or fields.get("Nom") or getattr(v, "name", vid)
            if vid not in vehicle_map:
                vehicle_map[vid] = {"id": vid, "name": name}
    except Exception:
        pass

    # Dictionnaire de référence pour toutes les têtes
    head_map = {}
    try:
        from utils.database import get_heads
        for h in get_heads() or []:
            hid = str(h.get("id"))
            fields = h.get("fields") or {}
            name = fields.get("name") or fields.get("Nom") or hid
            head_map[hid] = {"id": hid, "name": name}
    except Exception:
        pass

    formatted_projects = []
    for p in projects:
        # Véhicules assignés à ce projet
        p_veh_ids = []
        if p.vehicles_to_check:
            p_veh_ids.extend([v.strip() for v in p.vehicles_to_check.split(",") if v.strip()])
        if hasattr(p, "checkout_vehicles") and p.checkout_vehicles:
            for cv in p.checkout_vehicles:
                if cv.vehicle_id and str(cv.vehicle_id) not in p_veh_ids:
                    p_veh_ids.append(str(cv.vehicle_id))

        p_vehicles = []
        for vid in p_veh_ids:
            v_item = vehicle_map.get(str(vid))
            if v_item:
                p_vehicles.append(v_item)
            else:
                p_vehicles.append({"id": str(vid), "name": f"Véhicule #{vid}"})

        # Têtes assignées à ce projet
        p_head_ids = []
        if p.heads_to_check:
            p_head_ids.extend([h.strip() for h in p.heads_to_check.split(",") if h.strip()])

        p_heads = []
        for hid in p_head_ids:
            h_item = head_map.get(str(hid))
            if h_item:
                p_heads.append(h_item)
            else:
                p_heads.append({"id": str(hid), "name": f"Tête #{hid}"})

        formatted_projects.append({
            "id": p.id,
            "name": p.name,
            "production_name": p.production.name if p.production else "",
            "start_date": _format_date(p.shoot_start_date),
            "end_date": _format_date(p.shoot_end_date),
            "vehicles": p_vehicles,
            "heads": p_heads,
        })

    return {
        "projects": formatted_projects,
        "vehicles": list(vehicle_map.values()),
        "heads": list(head_map.values()),
        "users": [{"id": u.id, "name": f"{u.firstname} {u.lastname}", "role": u.role_display if hasattr(u, "role_display") else u.role} for u in users],
        "categories": [(k, v) for k, v in INCIDENT_CATEGORY_MAP.items()],
        "severities": [(k, v) for k, v in INCIDENT_SEVERITY_MAP.items()],
        "statuses": [(k, v) for k, v in INCIDENT_STATUS_MAP.items()],
        "status_icons": INCIDENT_STATUS_ICONS,
        "status_badge_vals": INCIDENT_STATUS_BADGE_VALS,
        "shooting_impacts": [(k, v) for k, v in INCIDENT_IMPACT_MAP.items()],
    }


# ── Génération du Rapport PDF ────────────────────────────────────

def generate_incident_pdf(record_id):
    """
    Génère la fiche de constat d'incident officielle au format PDF selon la DA Belle Vitesse (checks et décharges).
    """
    from flask import render_template

    incident_data = get_incident_detail(record_id)
    if not incident_data:
        raise ValueError(f"Incident #{record_id} introuvable pour la génération PDF.")

    company_address = "128 Rue La Boétie, 75008 Paris"
    try:
        from models import AppSetting
        company_address = AppSetting.get("company_address", company_address)
    except Exception:
        pass

    html = render_template(
        "pdf/incident_report.html",
        company_name="Belle Vitesse",
        company_address=company_address,
        incident=incident_data,
        today=_format_date(date.today()),
    )

    filename = f"Belle_Vitesse_INCIDENT_{incident_data['incident_number']}.pdf"
    pdf_bytes = render_pdf_from_template(
        html_content=html,
        base_url=current_app.root_path,
        stylesheets=["css/styles.css", "css/checkout.css", "css/incident_pdf.css"],
        filename=filename,
    )

    return pdf_bytes, filename


# ── Helpers Internes ─────────────────────────────────────────────

def _save_uploaded_files(file_list, subfolder="photos"):
    """
    Sauvegarde une liste de fichiers uploadés dans output/incidents/<subfolder>/ et retourne leurs chemins relatifs.
    """
    if not file_list:
        return []

    output_base = Path(os.getenv("OUTPUT_FOLDER", Path(current_app.root_path) / "output"))
    dest_dir = output_base / "incidents" / subfolder
    dest_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    for f in file_list:
        if not f or not getattr(f, "filename", None):
            continue
        original_name = secure_filename(f.filename)
        if not original_name:
            continue

        unique_prefix = uuid.uuid4().hex[:8]
        safe_name = f"{unique_prefix}_{original_name}"
        target_path = dest_dir / safe_name

        try:
            f.save(target_path)
            # Enregistre le chemin relatif par rapport à output_base
            rel_path = os.path.relpath(target_path, output_base)
            saved_paths.append(rel_path)
        except Exception as err:
            logger.error(f"Erreur lors de la sauvegarde du fichier {original_name} : {err}")

    return saved_paths
