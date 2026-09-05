import json
import logging
import os
import uuid
import secrets
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from pathlib import Path

from flask import current_app, render_template
from werkzeug.utils import secure_filename

from sqlalchemy.exc import IntegrityError
from models import db, Project, User, Vehicle
from models.incident import Incident, IncidentToken, IncidentSignedDocument
from models.db import _utcnow
from utils.document_utils import (
    compute_hmac_seal,
    compute_pdf_hash,
    generate_pdf_access_token,
    generate_qr_code,
    render_pdf_from_template,
)
from utils.storage import get_incident_path, ensure_dir
from utils.image_utils import optimize_and_save_image

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
            inc.signature_status_label or "",
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
            "signature_status": inc.signature_status,
            "signature_status_label": inc.signature_status_label,
            "is_signed_bv": inc.is_signed_bv,
            "is_signed_prod": inc.is_signed_prod,
            "is_fully_signed": inc.is_fully_signed,
            "bv_signer_name": inc.bv_signer_name,
            "prod_signer_name": inc.prod_signer_name,
            "signed_pdf_path": inc.signed_pdf_path,
            "signed_pdf_url": (
                f"/incidents/document/{inc.signed_pdf_path}?t={generate_pdf_access_token(inc.signed_pdf_path)}"
                if inc.signed_pdf_path else None
            ),
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
    raw_time = ""
    if inc.incident_time:
        t_str = inc.incident_time.strip().replace("h", ":").replace("H", ":")
        if ":" in t_str:
            parts = t_str.split(":")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                raw_time = f"{int(parts[0]):02d}:{int(parts[1]):02d}"
            else:
                raw_time = t_str
        else:
            raw_time = t_str

    return {
        "id": inc.id,
        "incident_number": inc.incident_number,
        "title": inc.title,
        "incident_date": _format_date(inc.incident_date),
        "incident_date_raw": inc.incident_date.isoformat() if inc.incident_date else "",
        "incident_time": inc.incident_time or "—",
        "incident_time_raw": raw_time,
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
        "checkout_id": inc.checkout_id,
        "checkin_id": inc.checkin_id,
        "attached_inspection": f"checkout:{inc.checkout_id}" if inc.checkout_id else (f"checkin:{inc.checkin_id}" if inc.checkin_id else ""),
        "estimated_cost": float(inc.estimated_cost) if inc.estimated_cost is not None else None,
        "actual_cost": float(inc.actual_cost) if inc.actual_cost is not None else None,
        "insurance_declared": inc.insurance_declared,
        "insurance_reference": inc.insurance_reference or "—",
        "insurance_notes": inc.insurance_notes or "",
        "photos": photos_display,
        "documents": docs_display,
        "resolution_notes": inc.resolution_notes or "",
        "resolved_at": _format_date(inc.resolved_at) if inc.resolved_at else None,
        # Données de signature & Scellement
        "bv_signer_name": inc.bv_signer_name,
        "bv_signer_role": inc.bv_signer_role,
        "bv_signature_data": inc.bv_signature_data,
        "bv_signed_at": _format_date(inc.bv_signed_at) if inc.bv_signed_at else None,
        "bv_signed_at_raw": inc.bv_signed_at.isoformat() if inc.bv_signed_at else "",
        "bv_signer_ip": inc.bv_signer_ip,
        "prod_signer_name": inc.prod_signer_name,
        "prod_signer_role": inc.prod_signer_role,
        "prod_signature_data": inc.prod_signature_data,
        "prod_signed_at": _format_date(inc.prod_signed_at) if inc.prod_signed_at else None,
        "prod_signed_at_raw": inc.prod_signed_at.isoformat() if inc.prod_signed_at else "",
        "prod_signer_ip": inc.prod_signer_ip,
        "signature_status": inc.signature_status,
        "signature_status_label": inc.signature_status_label,
        "is_signed_bv": inc.is_signed_bv,
        "is_signed_prod": inc.is_signed_prod,
        "is_fully_signed": inc.is_fully_signed,
        "signed_pdf_path": inc.signed_pdf_path,
        "signed_pdf_url": (
            f"/incidents/document/{inc.signed_pdf_path}?t={generate_pdf_access_token(inc.signed_pdf_path)}"
            if inc.signed_pdf_path else None
        ),
        "hash": inc.hash,
        "pdf_file_hash": inc.pdf_file_hash,
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

    attached_inspection = form_data.get("attached_inspection")
    if attached_inspection is not None:
        if attached_inspection.startswith("checkout:"):
            cid = attached_inspection.split(":", 1)[1]
            checkout_id = int(cid) if cid.isdigit() else None
            checkin_id = None
        elif attached_inspection.startswith("checkin:"):
            cid = attached_inspection.split(":", 1)[1]
            checkin_id = int(cid) if cid.isdigit() else None
            checkout_id = None
        else:
            checkout_id = None
            checkin_id = None
    else:
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

    if "attached_inspection" in form_data:
        attached = form_data.get("attached_inspection", "")
        if attached.startswith("checkout:"):
            cid = attached.split(":", 1)[1]
            incident.checkout_id = int(cid) if cid.isdigit() else None
            incident.checkin_id = None
        elif attached.startswith("checkin:"):
            cid = attached.split(":", 1)[1]
            incident.checkin_id = int(cid) if cid.isdigit() else None
            incident.checkout_id = None
        else:
            incident.checkout_id = None
            incident.checkin_id = None
    else:
        if "checkout_id" in form_data:
            cid = form_data.get("checkout_id")
            incident.checkout_id = int(cid) if cid and str(cid).isdigit() else None
        if "checkin_id" in form_data:
            cid = form_data.get("checkin_id")
            incident.checkin_id = int(cid) if cid and str(cid).isdigit() else None

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
    Suppression logique (soft-delete) d'un incident et notification n8n si configuré.
    """
    if not confirm:
        return {"status": "requires_confirmation", "message": "Veuillez confirmer la suppression de cet incident."}

    incident = db.session.get(Incident, int(record_id))
    if not incident:
        return {"success": False, "message": "Incident introuvable."}

    incident_number = incident.incident_number
    project_unique_id = incident.project.project_id if incident.project else None

    # 1. Nettoyage des jetons d'invitation et documents signés archivés
    if incident_number:
        IncidentToken.query.filter_by(incident_id=incident.id).delete()
        IncidentSignedDocument.query.filter_by(incident_number=incident_number).delete()

    # 2. Notification n8n de la suppression (DELETE)
    webhook_url = os.getenv("N8N_WEBHOOK_INCIDENT") or os.getenv("N8N_WEBHOOK_INCIDENT_SIGN")
    if webhook_url and incident_number:
        try:
            from utils.n8n import trigger_n8n_webhook
            trigger_n8n_webhook(
                webhook_url,
                method="DELETE",
                incident_number=incident_number,
                document_id=incident_number,
                project_id=project_unique_id,
                project=incident.project.name if incident.project else None,
            )
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors du déclenchement du webhook DELETE incident : {e}")

    # 3. Soft-delete de l'incident
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
            "checkouts": [
                {
                    "id": co.id,
                    "inspection_number": co.inspection_number,
                    "vehicle_id": co.vehicle_id,
                    "date": _format_date(co.inspection_date),
                }
                for co in (p.checkout_vehicles or [])
                if getattr(co, "deleted_at", None) is None
            ],
            "checkins": [
                {
                    "id": ci.id,
                    "inspection_number": ci.inspection_number,
                    "vehicle_id": ci.vehicle_id,
                    "date": _format_date(ci.inspection_date),
                }
                for ci in (p.checkin_vehicles or [])
                if getattr(ci, "deleted_at", None) is None
            ],
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


# ── Double Signature & Scellement ─────────────────────────────────

def sign_incident_bv(incident_id, signer_name, signer_role, signature_data, ip_address=None):
    """
    Enregistre le visa et la signature manuscrite de Belle Vitesse pour un incident.
    """
    inc = db.session.get(Incident, int(incident_id)) if isinstance(incident_id, int) or (isinstance(incident_id, str) and incident_id.isdigit()) else Incident.query.filter_by(incident_number=str(incident_id)).first()
    if not inc or inc.deleted_at is not None:
        raise ValueError(f"Incident #{incident_id} introuvable.")

    if inc.is_fully_signed and inc.signed_pdf_path:
        return {
            "success": True,
            "message": "Le visa Belle Vitesse a déjà été enregistré et le constat est scellé.",
            "incident_number": inc.incident_number,
            "signature_status": inc.signature_status,
            "is_fully_signed": True,
            "signed_pdf_path": inc.signed_pdf_path,
            "pdf_url": f"/incidents/document/{inc.signed_pdf_path}",
            "file_path": None,
        }

    if not signer_name or not str(signer_name).strip():
        raise ValueError("Le nom du signataire Belle Vitesse est requis.")
    if not signature_data or not str(signature_data).strip():
        raise ValueError("Le tracé de signature est requis.")

    inc.bv_signer_name = str(signer_name).strip()
    inc.bv_signer_role = str(signer_role).strip() if signer_role else "Responsable Technique Belle Vitesse"
    inc.bv_signature_data = str(signature_data).strip()
    inc.bv_signed_at = datetime.now(timezone.utc)
    inc.bv_signer_ip = ip_address or "127.0.0.1"

    # Scellement contradictoire UNIQUEMENT si la Production a déjà signé
    if inc.is_signed_prod:
        res = finalize_incident_document(inc)
        message = "Visa Belle Vitesse enregistré et constat scellé contradictoirement avec succès."
        # Si un jeton avait été transmis par email, envoyer automatiquement l'exemplaire scellé au destinataire
        try:
            tokens = IncidentToken.query.filter_by(incident_id=inc.id).all()
            for tok in tokens:
                if tok.recipient_email:
                    from utils.mailer import send_incident_signed_confirmation_email
                    send_incident_signed_confirmation_email(inc, tok.recipient_email, res.get("file_path"))
        except Exception as mail_err:
            logger.warning(f"⚠️ Échec notification email post-visa BV : {mail_err}")
    else:
        inc.signature_status = "signed_bv"
        db.session.commit()
        res = {}
        message = "Visa Belle Vitesse enregistré avec succès (en attente de la signature Production pour scellement)."

    return {
        "success": True,
        "message": message,
        "incident_number": inc.incident_number,
        "signature_status": inc.signature_status,
        "is_fully_signed": inc.is_fully_signed,
        "signed_pdf_path": inc.signed_pdf_path,
        "pdf_url": res.get("pdf_url"),
        "file_path": res.get("file_path"),
    }


def sign_incident_prod(incident_id, signer_name, signer_role, signature_data, ip_address=None, token_str=None):
    """
    Enregistre le visa et la signature manuscrite de la Production (sur place ou via token).
    Déclenche le scellement contradictoire final UNIQUEMENT si Belle Vitesse a déjà signé.
    """
    inc = db.session.get(Incident, int(incident_id)) if isinstance(incident_id, int) or (isinstance(incident_id, str) and incident_id.isdigit()) else Incident.query.filter_by(incident_number=str(incident_id)).first()
    if not inc or inc.deleted_at is not None:
        raise ValueError(f"Incident #{incident_id} introuvable.")

    if inc.is_fully_signed and inc.signed_pdf_path:
        return {
            "success": True,
            "message": "La signature Production a déjà été enregistrée et le constat est scellé.",
            "incident_number": inc.incident_number,
            "signature_status": inc.signature_status,
            "is_fully_signed": True,
            "signed_pdf_path": inc.signed_pdf_path,
            "pdf_url": f"/incidents/document/{inc.signed_pdf_path}",
            "file_path": None,
        }

    if not signer_name or not str(signer_name).strip():
        raise ValueError("Le nom du représentant de la Production est requis.")
    if not signature_data or not str(signature_data).strip():
        raise ValueError("Le tracé de signature est requis.")

    inc.prod_signer_name = str(signer_name).strip()
    inc.prod_signer_role = str(signer_role).strip() if signer_role else "Représentant Production"
    inc.prod_signature_data = str(signature_data).strip()
    inc.prod_signed_at = datetime.now(timezone.utc)
    inc.prod_signer_ip = ip_address or "127.0.0.1"

    if token_str:
        tok = db.session.get(IncidentToken, token_str)
        if tok:
            tok.signature = inc.prod_signature_data

    # Scellement contradictoire UNIQUEMENT si Belle Vitesse a déjà signé
    if inc.is_signed_bv:
        res = finalize_incident_document(inc)
        message = "Signature Production enregistrée et constat scellé contradictoirement avec succès."
    else:
        inc.signature_status = "signed_prod"
        db.session.commit()
        res = {}
        message = "Signature Production enregistrée avec succès (en attente du visa Belle Vitesse pour scellement)."

    return {
        "success": True,
        "message": message,
        "incident_number": inc.incident_number,
        "signature_status": inc.signature_status,
        "is_fully_signed": inc.is_fully_signed,
        "signed_pdf_path": inc.signed_pdf_path,
        "pdf_url": res.get("pdf_url"),
        "file_path": res.get("file_path"),
    }


def generate_incident_token(incident_id, recipient_email=None):
    """
    Génère un jeton sécurisé temporaire (48h) pour la signature distante par la Production.
    """
    inc = db.session.get(Incident, int(incident_id)) if isinstance(incident_id, int) or (isinstance(incident_id, str) and incident_id.isdigit()) else Incident.query.filter_by(incident_number=str(incident_id)).first()
    if not inc or inc.deleted_at is not None:
        raise ValueError(f"Incident #{incident_id} introuvable.")

    token_str = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(hours=48)

    token_entry = IncidentToken(
        token=token_str,
        incident_id=inc.id,
        recipient_email=recipient_email.strip() if recipient_email else None,
        created_at=datetime.now(timezone.utc),
        expires_at=expires_at,
    )
    db.session.add(token_entry)

    if inc.signature_status != "signed":
        inc.signature_status = "pending_prod"

    db.session.commit()

    base_url = current_app.config.get("APP_BASE_URL", "https://bellevitesse.com").rstrip("/")
    try:
        from flask import request
        if request:
            base_url = request.host_url.rstrip("/")
    except Exception:
        pass

    signing_url = f"{base_url}/incidents/sign/{token_str}"

    # Expédition de l'invitation par email si une adresse est renseignée
    email_sent = False
    if recipient_email:
        try:
            from utils.mailer import send_incident_signature_request_email
            send_incident_signature_request_email(inc, recipient_email.strip(), signing_url)
            email_sent = True
        except Exception as mail_err:
            logger.warning(f"⚠️ Échec d'envoi de l'invitation email pour l'incident {inc.incident_number}: {mail_err}")

    return {
        "success": True,
        "token": token_str,
        "signing_url": signing_url,
        "recipient_email": recipient_email,
        "email_sent": email_sent,
        "expires_at": expires_at.isoformat(),
    }


def validate_incident_token(token_str):
    """
    Valide un jeton de signature publique pour incident.
    Retourne (token_entry, incident) ou (None, code_erreur).
    """
    token_entry = db.session.get(IncidentToken, token_str)
    if not token_entry:
        return None, 404

    now_utc = datetime.now(timezone.utc)
    exp = token_entry.expires_at
    if exp:
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now_utc:
            return None, 410  # Expiré

    incident = token_entry.incident
    if not incident or incident.deleted_at is not None:
        return None, 404

    return (token_entry, incident), 200


def finalize_incident_document(incident, base_url=None):
    """
    Finalise et scelle un constat d'incident contradictoirement signé :
    1. Calcule le sceau HMAC-SHA256 d'intégrité.
    2. Génère le QR code de vérification pointant vers /incidents/verify/<incident_number>.
    3. Rend et compresse le PDF scellé intégrant les 2 signatures et le cartouche de conformité.
    4. Enregistre le PDF dans output/.../1_SÉCURITÉ/5_INCIDENTS/.
    5. Persiste l'archive légale immuable IncidentSignedDocument.
    6. Déclenche le webhook n8n si configuré.
    """
    if not base_url:
        try:
            from flask import request
            if request:
                base_url = request.host_url.rstrip("/")
        except Exception:
            base_url = current_app.config.get("APP_BASE_URL", "https://bellevitesse.com").rstrip("/")

    verification_url = f"{base_url}/incidents/verify/{incident.incident_number}"
    qr_code_img = generate_qr_code(verification_url)

    # Calcul du sceau HMAC
    bv_signed_iso = incident.bv_signed_at.isoformat() if incident.bv_signed_at else ""
    prod_signed_iso = incident.prod_signed_at.isoformat() if incident.prod_signed_at else ""
    current_hash = compute_hmac_seal(
        "INCIDENT",
        incident.incident_number,
        incident.bv_signer_name or "",
        incident.bv_signature_data or "",
        bv_signed_iso,
        incident.prod_signer_name or "",
        incident.prod_signature_data or "",
        prod_signed_iso,
    )

    incident_data = get_incident_detail(incident.id)
    company_address = "128 Rue La Boétie, 75008 Paris"
    try:
        from models import AppSetting
        company_address = AppSetting.get("company_address", company_address)
    except Exception:
        pass

    filename = f"Belle_Vitesse_INCIDENT_{incident.incident_number}_{secrets.token_hex(4)}.pdf"
    pdf_dir = ensure_dir(get_incident_path(incident.project))
    file_path = os.path.join(pdf_dir, filename)

    render_ctx = {
        "company_name": "Belle Vitesse",
        "company_address": company_address,
        "incident": incident_data,
        "today": _format_date(date.today()),
        "is_sealed": True,
        "hash": current_hash,
        "qr": qr_code_img,
        "verification_url": verification_url,
        "signed_at_str": (incident.prod_signed_at or _utcnow()).strftime("%d/%m/%Y %H:%M"),
    }

    html = render_template("pdf/incident_report.html", **render_ctx)
    pdf_bytes = render_pdf_from_template(
        html_content=html,
        base_url=current_app.root_path,
        stylesheets=["css/styles.css", "css/checkout.css", "css/incident_pdf.css"],
        filename=filename,
    )

    output_base = current_app.config.get("OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))
    rel_pdf_path = os.path.relpath(file_path, output_base)

    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    pdf_file_hash = compute_pdf_hash(pdf_bytes)

    incident.signed_pdf_path = rel_pdf_path
    incident.hash = current_hash
    incident.pdf_file_hash = pdf_file_hash
    incident.signature_status = "signed"

    # Enregistrement ou mise à jour de l'archive légale
    try:
        signed_doc = IncidentSignedDocument.query.filter_by(incident_number=incident.incident_number).first()
        if not signed_doc:
            signed_doc = IncidentSignedDocument(
                incident_number=incident.incident_number,
                incident_id=incident.id,
                hash=current_hash,
                pdf_file_hash=pdf_file_hash,
                data_snapshot=incident.to_dict(),
                signature=incident.prod_signature_data or incident.bv_signature_data,
                pdf_url=f"/incidents/document/{rel_pdf_path}",
                signed_at=(incident.prod_signed_at or _utcnow()).replace(tzinfo=None)
            )
            db.session.add(signed_doc)
        else:
            signed_doc.incident_id = incident.id
            signed_doc.hash = current_hash
            signed_doc.pdf_file_hash = pdf_file_hash
            signed_doc.data_snapshot = incident.to_dict()
            signed_doc.signature = incident.prod_signature_data or incident.bv_signature_data
            signed_doc.pdf_url = f"/incidents/document/{rel_pdf_path}"
            signed_doc.signed_at = (incident.prod_signed_at or _utcnow()).replace(tzinfo=None)

        db.session.commit()
    except IntegrityError as commit_err:
        logger.warning(f"⚠️ Archive légale déjà présente pour {incident.incident_number} ({commit_err}), mise à jour de l'existant...")
        db.session.rollback()
        existing_doc = IncidentSignedDocument.query.filter_by(incident_number=incident.incident_number).first()
        if existing_doc:
            existing_doc.incident_id = incident.id
            existing_doc.hash = current_hash
            existing_doc.pdf_file_hash = pdf_file_hash
            existing_doc.data_snapshot = incident.to_dict()
            existing_doc.signature = incident.prod_signature_data or incident.bv_signature_data
            existing_doc.pdf_url = f"/incidents/document/{rel_pdf_path}"
            existing_doc.signed_at = (incident.prod_signed_at or _utcnow()).replace(tzinfo=None)
            db.session.commit()
        else:
            raise commit_err

    # 6. Webhook n8n (POST)
    webhook_url = os.getenv("N8N_WEBHOOK_INCIDENT") or os.getenv("N8N_WEBHOOK_INCIDENT_SIGN")
    if webhook_url:
        project_obj = incident.project
        project_id_unique = "—"
        if project_obj:
            project_id_unique = getattr(project_obj, "project_id", "—")

        # Date, année et mois de référence basés sur le projet rattaché
        project_date_obj = None
        if project_obj and project_obj.departure_date:
            project_date_obj = project_obj.departure_date
        elif project_obj and project_obj.shoot_start_date:
            project_date_obj = project_obj.shoot_start_date
        elif incident.incident_date:
            project_date_obj = incident.incident_date
        else:
            project_date_obj = datetime.utcnow()

        project_date_str = project_date_obj.strftime("%Y-%m-%d") if hasattr(project_date_obj, "strftime") else str(project_date_obj)
        year_str = project_date_obj.strftime("%Y")
        month_str = project_date_obj.strftime("%m")

        pdf_access_token = generate_pdf_access_token(rel_pdf_path)
        pdf_url_signed = f"{base_url}/incidents/document/{rel_pdf_path}?t={pdf_access_token}"

        def get_secured_file_url(file_path):
            if not file_path:
                return None
            clean = file_path.lstrip("/")
            if clean.startswith("files/"):
                clean = clean[6:]
            return f"{base_url}/files/{clean}?t={generate_pdf_access_token(clean)}"

        payload = {
            "event": "incident_signed",
            "document_id": incident.incident_number,
            "project_id": project_id_unique,
            "pdf_url": pdf_url_signed,
            "hash": current_hash,
            "production": project_obj.production.name if project_obj and project_obj.production else "—",
            "project": project_obj.name if project_obj else "—",
            "project_date": project_date_str,
            "year": year_str,
            "month": month_str,
            "incident": {
                "title": incident.title,
                "incident_number": incident.incident_number,
                "category": incident.category,
                "category_label": INCIDENT_CATEGORY_MAP.get(incident.category, incident.category),
                "severity": incident.severity,
                "severity_label": INCIDENT_SEVERITY_MAP.get(incident.severity, incident.severity),
                "status": incident.status,
                "status_label": INCIDENT_STATUS_MAP.get(incident.status, incident.status),
                "signature_status": incident.signature_status,
                "date": incident.incident_date.strftime("%Y-%m-%d") if incident.incident_date else None,
                "time": incident.incident_time,
                "location": incident.location,
                "shooting_impact": incident.shooting_impact,
                "shooting_impact_label": INCIDENT_IMPACT_MAP.get(incident.shooting_impact, incident.shooting_impact),
                "equipment_name": incident.equipment_name,
                "description": incident.description,
                "immediate_actions": incident.immediate_actions,
                "estimated_cost": float(incident.estimated_cost) if incident.estimated_cost is not None else None,
                "actual_cost": float(incident.actual_cost) if incident.actual_cost is not None else None,
                "insurance_declared": incident.insurance_declared,
                "insurance_reference": incident.insurance_reference,
                "declared_by": f"{incident.reporter.firstname} {incident.reporter.lastname}".strip() if incident.reporter else None,
            },
            "vehicle": incident_data.get("vehicle"),
            "signatures": {
                "bv_signer": incident.bv_signer_name or (f"{incident.reporter.firstname} {incident.reporter.lastname}".strip() if incident.reporter else "Belle Vitesse"),
                "bv_signer_role": incident.bv_signer_role,
                "bv_signed_at": incident.bv_signed_at.isoformat() if incident.bv_signed_at else None,
                "prod_signer": incident.prod_signer_name,
                "prod_signer_role": incident.prod_signer_role,
                "prod_signed_at": incident.prod_signed_at.isoformat() if incident.prod_signed_at else None,
            },
            "photos": [url for url in [get_secured_file_url(p) for p in incident.photos_list] if url],
            "documents": [url for url in [get_secured_file_url(d) for d in incident.documents_list] if url],
        }

        try:
            from utils.n8n import trigger_n8n_webhook
            trigger_n8n_webhook(webhook_url, method="POST", **payload)
        except Exception as err:
            logger.warning(f"⚠️ Échec webhook n8n incident : {err}")

    return {
        "document_id": incident.incident_number,
        "pdf_url": f"/incidents/document/{rel_pdf_path}",
        "hash": current_hash,
        "file_path": file_path,
    }


# ── Génération du Rapport PDF ────────────────────────────────────

def generate_incident_pdf(record_id):
    """
    Génère la fiche de constat d'incident officielle au format PDF selon la DA Belle Vitesse.
    Intègre les signatures réelles, le QR code et le sceau HMAC si le constat est finalisé.
    """
    incident_data = get_incident_detail(record_id)
    if not incident_data:
        raise ValueError(f"Incident #{record_id} introuvable pour la génération PDF.")

    company_address = "128 Rue La Boétie, 75008 Paris"
    try:
        from models import AppSetting
        company_address = AppSetting.get("company_address", company_address)
    except Exception:
        pass

    is_sealed = incident_data.get("is_fully_signed", False) or incident_data.get("signature_status") == "signed"

    # Si le document est scellé et que le PDF signé existe sur le disque, servir l'exemplaire scellé original
    if is_sealed and incident_data.get("signed_pdf_path"):
        output_base = current_app.config.get("OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))
        sealed_file_path = os.path.join(output_base, incident_data["signed_pdf_path"])
        if os.path.exists(sealed_file_path):
            with open(sealed_file_path, "rb") as f:
                return f.read(), os.path.basename(sealed_file_path)

    qr_code_img = None
    verification_url = None
    if is_sealed and incident_data.get("hash"):
        base_url = current_app.config.get("APP_BASE_URL", "https://bellevitesse.com").rstrip("/")
        try:
            from flask import request
            if request:
                base_url = request.host_url.rstrip("/")
        except Exception:
            pass
        verification_url = f"{base_url}/incidents/verify/{incident_data['incident_number']}"
        qr_code_img = generate_qr_code(verification_url)

    html = render_template(
        "pdf/incident_report.html",
        company_name="Belle Vitesse",
        company_address=company_address,
        incident=incident_data,
        today=_format_date(date.today()),
        is_sealed=is_sealed,
        qr=qr_code_img,
        hash=incident_data.get("hash"),
        verification_url=verification_url,
        signed_at_str=incident_data.get("prod_signed_at") or _format_date(date.today()),
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
            if subfolder == "photos":
                optimize_and_save_image(f, target_path)
            else:
                f.save(target_path)
            # Enregistre le chemin relatif par rapport à output_base
            rel_path = os.path.relpath(target_path, output_base)
            saved_paths.append(rel_path)
        except Exception as err:
            logger.error(f"Erreur lors de la sauvegarde du fichier {original_name} : {err}")

    return saved_paths
