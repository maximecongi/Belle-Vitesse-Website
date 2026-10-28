"""
services/admin/waivers/pilot.py — Logique métier et administration des Attestations Pilotes (Annexe 3 aux CGL - BVPA).
"""
import logging
from datetime import datetime

from sqlalchemy.orm import joinedload

from models import PilotWaiver, Project, WaiverToken, db
from models.db import _utcnow
from services.admin.status_mapping import format_waiver_status
from services.admin.utils import handle_admin_service_error
from utils.document_utils import (
    generate_pdf_access_token as generate_waiver_pdf_access_token,
)
from utils.entity_resolvers import (
    resolve_pilot_waiver,
    resolve_project,
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


def create_pilot_waiver(project_id, **kwargs):
    """Crée une attestation d'information et d'engagement du pilote (Annexe 3 - BVPA)."""
    return create_waiver(project_id, waiver_type="pilot_waiver", **kwargs)


def delete_pilot_waiver(waiver_id):
    """Supprime logiquement une attestation pilote BVPA (soft-delete et nettoyage assets)."""
    return delete_waiver(waiver_id, waiver_type="pilot_waiver")


def generate_pilot_waiver(waiver_id):
    """Génère (fige les données de snapshot) une attestation pilote BVPA."""
    return generate_waiver(waiver_id, waiver_type="pilot_waiver")


def send_pilot_waiver(waiver_id, base_url=None):
    """Envoie l'invitation de signature par e-mail au pilote (BVPA)."""
    return send_waiver(waiver_id, waiver_type="pilot_waiver", base_url=base_url)


def reset_pilot_waiver(waiver_id):
    """Réinitialise complètement une attestation pilote BVPA."""
    return reset_waiver(waiver_id, waiver_type="pilot_waiver")


def delete_pilot_waiver_internal(project_id):
    """Supprime proprement les attestations pilotes en interne lors de suppression d'un projet."""
    delete_waiver_internal(project_id, waiver_type="pilot_waiver")


def list_pilot_waivers(project_id=None):
    """Liste et formate les attestations d'information et d'engagement du pilote (Annexe 3 - BVPA)."""
    query = PilotWaiver.query.outerjoin(Project).filter(
        PilotWaiver.deleted_at == None
    ).options(joinedload(PilotWaiver.project))

    if project_id:
        p = resolve_project(project_id)
        if p:
            query = query.filter(PilotWaiver.project_id == p.id)

    waivers = query.all()
    waivers.sort(key=lambda w: (
        (w.project.departure_date or datetime.min.date()) if (w.project and w.project.departure_date) else datetime.min.date(),
        w.generated_at or datetime.min
    ), reverse=True)

    formatted = []
    for w in waivers:
        p = w.project

        def get_secured_url(path):
            if not path:
                return None
            clean_path = path.split('?')[0].split('/pilot-attestation/document/')[-1]
            token = generate_waiver_pdf_access_token(clean_path)
            return f"/pilot-attestation/document/{clean_path}?t={token}"

        raw_shooting_dates = w.shooting_dates or (_format_project_shooting_dates(p, default_sep=" → ") if p else "—")
        shooting_dates = format_waiver_shooting_dates(raw_shooting_dates, default_sep=" → ")

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
            "signer_role_label": getattr(w, "pilot_function_label", w.signer_role_label),
            "signer_email": w.signer_email,
            "signer_phone": w.signer_phone,
            "signer_company": w.signer_company,
            "vehicles": w.vehicles,
            "vehicles_details": getattr(w, "vehicles_details", []),
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
