"""
services/admin/waivers/cgl.py — Logique métier et administration des Conditions Générales de Location (CGL - BVRA).
"""
import logging
from datetime import datetime

from sqlalchemy.orm import joinedload

from models import CglWaiver, Project, WaiverToken
from models.db import _utcnow
from services.admin.status_mapping import format_waiver_status
from utils.document_utils import (
    generate_pdf_access_token as generate_waiver_pdf_access_token,
)

from .common import (
    _format_project_shooting_dates,
    format_waiver_shooting_dates,
)
from .core import (
    create_waiver,
    delete_waiver,
    delete_waiver_internal,
    generate_waiver,
    reset_waiver,
    send_waiver,
)

logger = logging.getLogger(__name__)


def create_cgl(project_id):
    """Crée des CGL pour un projet s'il n'en existe pas déjà d'actives."""
    return create_waiver(project_id, waiver_type="cgl")


def delete_cgl(waiver_id):
    """Supprime logiquement des CGL (soft-delete et nettoyage assets)."""
    return delete_waiver(waiver_id, waiver_type="cgl")


def generate_cgl(waiver_id):
    """Génère (fige les données de snapshot) des CGL."""
    return generate_waiver(waiver_id, waiver_type="cgl")


def send_cgl(waiver_id, base_url=None):
    """Envoie l'invitation de signature des CGL par e-mail au contact production."""
    return send_waiver(waiver_id, waiver_type="cgl", base_url=base_url)


def reset_cgl(waiver_id):
    """Réinitialise complètement des CGL (supprime signature et PDF)."""
    return reset_waiver(waiver_id, waiver_type="cgl")


def delete_cgl_internal(project_id):
    """Supprime proprement des CGL en interne lors de suppression de projet."""
    delete_waiver_internal(project_id, waiver_type="cgl")


def list_cgl():
    """Liste et formate toutes les CGL pour l'administration."""
    waivers = CglWaiver.query.outerjoin(Project).filter(
        CglWaiver.deleted_at == None
    ).options(joinedload(CglWaiver.project)).all()

    waivers.sort(key=lambda w: (
        (w.project.departure_date or datetime.min.date()) if (w.project and w.project.departure_date) else datetime.min.date(),
        w.project.name if w.project else (w.project_name or "")
    ), reverse=True)

    formatted = []
    for w in waivers:
        p = w.project

        def get_secured_url(path):
            if not path:
                return None
            clean_path = path.split('?')[0].split('/cgl/document/')[-1]
            token = generate_waiver_pdf_access_token(clean_path)
            return f"/cgl/document/{clean_path}?t={token}"

        raw_shooting_dates = w.shooting_dates or (_format_project_shooting_dates(p, default_sep=" → ") if p else "—")
        shooting_dates = format_waiver_shooting_dates(raw_shooting_dates, default_sep=" → ")

        now_dt = _utcnow()
        active_token = WaiverToken.query.filter(
            WaiverToken.waiver_id == w.waiver_id,
            WaiverToken.expires_at > now_dt
        ).order_by(WaiverToken.created_at.desc()).first()

        production_contact_name = "—"
        if p and p.production_contact:
            production_contact_name = f"{p.production_contact.first_name} {p.production_contact.last_name}"

        formatted.append({
            "id": w.waiver_id,
            "db_id": w.id,
            "waiver_id": w.waiver_id,
            "project_id": p.id if p else w.project_id,
            "project_name": p.name if p else (w.project_name or "—"),
            "production_name": ((p.production.name if p.production else None) if p else w.production_name) or w.production_name or "—",
            "production_contact_name": production_contact_name,
            "shooting_dates": shooting_dates,
            "status": format_waiver_status(w.status),
            "raw_status": w.status,
            "generated_at": w.generated_at,
            "sent_at": w.sent_at,
            "signed_at": w.signed_at,
            "signature_token": active_token.token if active_token else None,
            "signed_pdf_path": get_secured_url(w.signed_pdf_path),
            "reminder_count": w.reminder_count or 0,
            "last_reminded_at": w.last_reminded_at
        })
    return formatted
