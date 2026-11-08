"""
services/admin/waivers/risk_assessment.py — Logique métier et administration de l'Analyse des Risques (BVRA).
"""
import logging
from datetime import datetime

from sqlalchemy.orm import joinedload

from models import Project, RiskAssessmentWaiver, WaiverToken, db
from models.db import _utcnow
from services.admin.status_mapping import format_waiver_status
from services.admin.utils import handle_admin_service_error
from utils.entity_resolvers import (
    resolve_project,
    resolve_risk_assessment_waiver,
)

from .common import (
    _format_project_shooting_dates,
    format_waiver_shooting_dates,
    get_secured_waiver_pdf_url,
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


def create_risk_assessment_waiver(project_id, **kwargs):
    """Crée une analyse des risques (BVRA) pour un signataire individuel d'un projet."""
    return create_waiver(project_id, waiver_type="risk_assessment", **kwargs)


def delete_risk_assessment_waiver(waiver_id):
    """Supprime logiquement une analyse des risques BVRA (soft-delete et nettoyage assets)."""
    return delete_waiver(waiver_id, waiver_type="risk_assessment")


def generate_risk_assessment_waiver(waiver_id):
    """Génère (fige les données de snapshot) une analyse des risques BVRA."""
    return generate_waiver(waiver_id, waiver_type="risk_assessment")


def send_risk_assessment_waiver(waiver_id, base_url=None):
    """Envoie l'invitation de signature par e-mail au signataire de l'analyse des risques BVRA."""
    return send_waiver(waiver_id, waiver_type="risk_assessment", base_url=base_url)


def reset_risk_assessment_waiver(waiver_id):
    """Réinitialise complètement une analyse des risques BVRA (supprime signatures et PDF)."""
    return reset_waiver(waiver_id, waiver_type="risk_assessment")


def delete_risk_assessment_waiver_internal(project_id):
    """Supprime proprement les BVRA en interne lors de la suppression d'un projet."""
    delete_waiver_internal(project_id, waiver_type="risk_assessment")


delete_risk_assessment_internal = delete_risk_assessment_waiver_internal


def list_risk_assessment_waivers(project_id=None):
    """Liste et formate les analyses des risques (BVRA) d'un projet ou de tous les projets."""
    query = RiskAssessmentWaiver.query.outerjoin(Project).filter(
        RiskAssessmentWaiver.deleted_at.is_(None)
    ).options(joinedload(RiskAssessmentWaiver.project))

    if project_id:
        p = resolve_project(project_id)
        if p:
            query = query.filter(RiskAssessmentWaiver.project_id == p.id)

    waivers = query.all()
    waivers.sort(key=lambda w: (
        (w.project.departure_date or datetime.min.date()) if (
            w.project and w.project.departure_date) else datetime.min.date(),
        w.generated_at or datetime.min
    ), reverse=True)

    formatted = []
    for w in waivers:
        p = w.project

        raw_shooting_dates = w.shooting_dates or (
            _format_project_shooting_dates(p, default_sep=" → ") if p else "—")
        shooting_dates = format_waiver_shooting_dates(
            raw_shooting_dates, default_sep=" → ")

        now_dt = _utcnow()
        active_token = WaiverToken.query.filter(
            WaiverToken.waiver_id == w.waiver_id,
            WaiverToken.expires_at > now_dt
        ).order_by(WaiverToken.created_at.desc()).first()

        formatted.append({
            "id": w.waiver_id,
            "db_id": w.id,
            "waiver_id": w.waiver_id,
            "project_id": p.id if p else w.project_id,
            "project_name": p.name if p else (w.project_name or "—"),
            "signer_name": w.signer_name,
            "signer_role": w.signer_role,
            "signer_role_label": w.signer_role_label,
            "signer_email": w.signer_email,
            "signer_phone": w.signer_phone,
            "signer_company": w.signer_company,
            "shooting_dates": shooting_dates,
            "status": format_waiver_status(w.status),
            "raw_status": w.status,
            "generated_at": w.generated_at,
            "sent_at": w.sent_at,
            "signed_at": w.signed_at,
            "signature_token": active_token.token if active_token else None,
            "signed_pdf_path": get_secured_waiver_pdf_url(w.signed_pdf_path, "risk-assessment"),
            "reminder_count": w.reminder_count or 0,
            "last_reminded_at": w.last_reminded_at
        })
    return formatted

