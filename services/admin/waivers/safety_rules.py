"""
services/admin/waivers/safety_rules.py — Logique métier et administration des Règles de Sécurité Universelles (BVSR).
"""
import logging
from datetime import datetime

from sqlalchemy.orm import joinedload

from models import Project, SafetyRulesWaiver, WaiverToken, db
from models.db import _utcnow
from services.admin.status_mapping import format_waiver_status
from services.admin.utils import handle_admin_service_error
from utils.entity_resolvers import (
    resolve_project,
    resolve_safety_rules_waiver,
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


def create_safety_rules_waiver(project_id, **kwargs):
    """Crée un engagement aux règles de sécurité (BVSR) pour un intervenant d'un projet."""
    return create_waiver(project_id, waiver_type="safety_rules", **kwargs)


def delete_safety_rules_waiver(waiver_id):
    """Supprime logiquement un engagement BVSR (soft-delete et nettoyage assets)."""
    return delete_waiver(waiver_id, waiver_type="safety_rules")


def generate_safety_rules_waiver(waiver_id):
    """Génère (fige les données de snapshot) un engagement BVSR."""
    return generate_waiver(waiver_id, waiver_type="safety_rules")


def send_safety_rules_waiver(waiver_id, base_url=None):
    """Envoie l'invitation de signature par e-mail au signataire de l'engagement BVSR."""
    return send_waiver(waiver_id, waiver_type="safety_rules", base_url=base_url)


def reset_safety_rules_waiver(waiver_id):
    """Réinitialise complètement un engagement BVSR (supprime signatures et PDF)."""
    return reset_waiver(waiver_id, waiver_type="safety_rules")


def delete_safety_rules_waiver_internal(project_id):
    """Supprime proprement les engagements BVSR en interne lors de suppression d'un projet."""
    delete_waiver_internal(project_id, waiver_type="safety_rules")


delete_safety_rules_internal = delete_safety_rules_waiver_internal


@handle_admin_service_error
def countersign_safety_rules(waiver_id, signature_data, signer_name="Belle Vitesse", signer_ip=None, user_agent=None):
    """
    Enregistre la contre-signature du superviseur technique Belle Vitesse pour le BVSR.
    Régénère le PDF scellé final avec les deux signatures si le signataire a déjà signé.
    """
    waiver = resolve_safety_rules_waiver(waiver_id)
    if not waiver:
        return False, "Règles de sécurité BVSR introuvables."

    if waiver.bv_signed_at:
        return False, "Ce document a déjà été contre-signé par Belle Vitesse. Une nouvelle contre-signature est interdite."

    from utils.signature_storage import validate_base64_png
    valid_sig, sig_err = validate_base64_png(signature_data)
    if not valid_sig:
        return False, f"Signature invalide : {sig_err}"

    orig_bv_sig = waiver.bv_signature_data
    orig_bv_signed_at = waiver.bv_signed_at
    orig_bv_signer_name = waiver.bv_signer_name

    try:
        waiver.bv_signature_data = signature_data
        waiver.bv_signed_at = _utcnow()
        waiver.bv_signer_name = signer_name or "Belle Vitesse"
        db.session.flush()

        if waiver.status == "signed" and waiver.signature_data:
            from services.common.signatures import finalize_signed_document
            finalize_signed_document(
                "safety_rules",
                waiver.id,
                waiver.signature_data,
                waiver.signer_ip or signer_ip,
                user_agent=user_agent
            )

        from services.common.signatures import log_signature_event
        log_signature_event(
            waiver.waiver_id,
            "safety_rules",
            "bvsr_countersigned",
            {
                "bv_signer_name": waiver.bv_signer_name,
                "bv_signed_at": waiver.bv_signed_at.isoformat() if waiver.bv_signed_at else "",
            },
            ip=signer_ip,
            user_agent=user_agent
        )

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # Restaurer l'état in-memory du modèle pour ne laisser aucun état partiel empêchant de réessayer
        waiver.bv_signature_data = orig_bv_sig
        waiver.bv_signed_at = orig_bv_signed_at
        waiver.bv_signer_name = orig_bv_signer_name
        logger.error(f"❌ Échec de la contre-signature BVSR pour {waiver_id} : {e}")
        return False, f"Erreur lors de la contre-signature : {e}"

    return True, "Contre-signature Belle Vitesse enregistrée avec succès."


def list_safety_rules_waivers(project_id=None):
    """Liste et formate les engagements aux règles de sécurité (BVSR)."""
    query = SafetyRulesWaiver.query.outerjoin(Project).filter(
        SafetyRulesWaiver.deleted_at == None
    ).options(joinedload(SafetyRulesWaiver.project))

    if project_id:
        p = resolve_project(project_id)
        if p:
            query = query.filter(SafetyRulesWaiver.project_id == p.id)

    waivers = query.all()
    waivers.sort(key=lambda w: (
        (w.project.departure_date or datetime.min.date()) if (w.project and w.project.departure_date) else datetime.min.date(),
        w.generated_at or datetime.min
    ), reverse=True)

    formatted = []
    for w in waivers:
        p = w.project

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
            "signer_role_label": w.signer_role_label,
            "signer_email": w.signer_email,
            "signer_phone": w.signer_phone,
            "signer_company": w.signer_company,
            "safety_technicians": w.safety_technicians,
            "shooting_dates": shooting_dates,
            "status": format_waiver_status(w.status),
            "raw_status": w.status,
            "generated_at": w.generated_at,
            "sent_at": w.sent_at,
            "signed_at": w.signed_at,
            "bv_signed_at": w.bv_signed_at,
            "bv_signer_name": w.bv_signer_name,
            "signature_token": active_token.token if active_token else None,
            "signed_pdf_path": get_secured_waiver_pdf_url(w.signed_pdf_path, "safety-rules"),
            "reminder_count": w.reminder_count or 0,
            "last_reminded_at": w.last_reminded_at
        })
    return formatted
