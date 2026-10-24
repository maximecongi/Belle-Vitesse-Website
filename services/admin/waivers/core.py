"""
services/admin/waivers/core.py — Gestion du cycle de vie unifié des décharges (création, génération, envoi, suppression, reset).
"""
import logging
import uuid
from datetime import datetime, timezone

from models import (
    CglWaiver,
    SafetyRulesWaiver,
    Waiver,
    WaiverToken,
    db,
)
from models.db import _utcnow
from services.admin.utils import handle_admin_service_error
from utils.database import get_vehicles
from utils.entity_resolvers import (
    resolve_cgl,
    resolve_project,
    resolve_safety_rules_waiver,
    resolve_waiver,
)

from .common import (
    _cleanup_waiver_assets,
    _format_project_shooting_dates,
    _get_waiver_config,
    _reset_waiver_fields,
)

logger = logging.getLogger(__name__)


@handle_admin_service_error
def create_waiver(project_id, waiver_type: str = "cgl", **kwargs):
    """
    Crée un contrat (CGL) ou un engagement (Règles de sécurité) pour un projet.
    """
    p = resolve_project(project_id)
    if not p:
        return False, "Projet introuvable."
    project_id = p.id

    config = _get_waiver_config(waiver_type)
    model = config["model"]

    # CGL : un seul contrat actif par projet
    if waiver_type == "cgl":
        existing = model.query.filter_by(project_id=project_id).first()
        if existing:
            if existing.deleted_at is None:
                return False, "Des Conditions Générales de Location (CGL) existent déjà pour ce projet."
            _cleanup_waiver_assets(waiver_type, existing)
            db.session.delete(existing)
            db.session.flush()

    waiver = model(project_id=project_id)
    waiver.project_name = p.name
    if p.production:
        waiver.production_name = p.production.name
        if waiver_type == "cgl":
            waiver.production_address = p.production.address
            if p.production_contact:
                waiver.production_representative = f"{p.production_contact.first_name} {p.production_contact.last_name}".strip()
                waiver.signer_phone = getattr(p.production_contact, "tel", "") or getattr(p.production_contact, "phone", "")
                waiver.signer_email = getattr(p.production_contact, "mail", "")
                waiver.signer_role_custom = getattr(p.production_contact, "job_title", "")
    elif waiver_type == "cgl" and p.production_contact:
        waiver.production_representative = f"{p.production_contact.first_name} {p.production_contact.last_name}".strip()
        waiver.signer_phone = getattr(p.production_contact, "tel", "") or getattr(p.production_contact, "phone", "")
        waiver.signer_email = getattr(p.production_contact, "mail", "")
        waiver.signer_role_custom = getattr(p.production_contact, "job_title", "")

    if waiver_type == "safety_rules":
        waiver.signer_role = kwargs.get("signer_role", "pilot")
        waiver.signer_role_custom = kwargs.get("signer_role_custom")
        waiver.signer_first_name = kwargs.get("signer_first_name")
        waiver.signer_last_name = kwargs.get("signer_last_name")
        waiver.signer_email = kwargs.get("signer_email")
        waiver.signer_phone = kwargs.get("signer_phone")
        waiver.signer_company = kwargs.get("signer_company")
        waiver.safety_technicians = (kwargs.get("safety_technicians") or "").strip() or None
        waiver.helmets_inventory = kwargs.get("helmets_inventory")

        # Auto-complétion si coordonnées non fournies
        if waiver.signer_role == "pilot" and not waiver.signer_first_name and p.pilot_contact:
            waiver.signer_first_name = p.pilot_contact.first_name
            waiver.signer_last_name = p.pilot_contact.last_name
            waiver.signer_email = p.pilot_contact.mail
            waiver.signer_phone = getattr(p.pilot_contact, "tel", "")
        elif waiver.signer_role == "production" and not waiver.signer_first_name and p.production_contact:
            waiver.signer_first_name = p.production_contact.first_name
            waiver.signer_last_name = p.production_contact.last_name
            waiver.signer_email = p.production_contact.mail
            waiver.signer_company = p.production.name if p.production else ""

    waiver.shooting_dates = _format_project_shooting_dates(p, default_sep=" au ")

    if p.vehicles_to_check:
        veh_ids = [v.strip() for v in p.vehicles_to_check.split(",") if v.strip()]
        all_vehicles = get_vehicles()
        vehicle_map = {str(v["id"]): v.get("fields", {}).get("name", f"ID {v['id']}") for v in all_vehicles}
        waiver.vehicles = ", ".join([vehicle_map.get(vid, vid) for vid in veh_ids])
    elif p.active_checkout_vehicles:
        waiver.vehicles = ", ".join([cv.vehicle_name for cv in p.active_checkout_vehicles if cv.vehicle_name])

    waiver.status = "to_send"
    waiver.generated_at = _utcnow()

    db.session.add(waiver)
    db.session.commit()

    if waiver_type == "cgl":
        msg = "Conditions Générales de Location (CGL) créées avec succès."
    else:
        msg = f"Règles de sécurité BVSR créées avec succès pour {waiver.signer_name} ({waiver.signer_role_label})."
    return True, msg


@handle_admin_service_error
def generate_waiver(waiver_id, waiver_type: str = None):
    """
    Génère (fige les données de snapshot) un contrat CGL ou engagement BVSR.
    Passe le statut de 'to_generate' à 'to_send'.
    """
    if waiver_type == "safety_rules":
        waiver = resolve_safety_rules_waiver(waiver_id)
    elif waiver_type == "cgl":
        waiver = resolve_cgl(waiver_id)
    else:
        waiver = resolve_waiver(waiver_id)

    if not waiver or waiver.status != "to_generate":
        return False, "Document non trouvé ou statut invalide."

    mode = waiver.waiver_type
    p = waiver.project

    if mode == "cgl":
        contact_prod = p.production_contact if p else None
        if not contact_prod or not contact_prod.mail:
            return False, "La production n'a pas d'adresse e-mail de contact renseignée dans le projet."
        if p and p.production:
            waiver.production_name = p.production.name
            waiver.production_address = p.production.address
    elif mode == "safety_rules":
        if p and p.production:
            waiver.production_name = p.production.name

    if p:
        waiver.project_name = p.name
        waiver.shooting_dates = _format_project_shooting_dates(p, default_sep=" au ")
        if p.vehicles_to_check:
            veh_ids = [v.strip() for v in p.vehicles_to_check.split(",") if v.strip()]
            all_vehicles = get_vehicles()
            vehicle_map = {str(v["id"]): v.get("fields", {}).get("name", f"ID {v['id']}") for v in all_vehicles}
            waiver.vehicles = ", ".join([vehicle_map.get(vid, vid) for vid in veh_ids])
        elif p.active_checkout_vehicles:
            waiver.vehicles = ", ".join([cv.vehicle_name for cv in p.active_checkout_vehicles if cv.vehicle_name])

    waiver.status = "to_send"
    waiver.generated_at = _utcnow()
    db.session.commit()

    msg = "Conditions Générales de Location (CGL) générées avec succès." if mode == "cgl" else "Règles de sécurité BVSR générées avec succès."
    return True, msg


@handle_admin_service_error
def send_waiver(waiver_id, waiver_type: str = None, base_url: str = None):
    """
    Envoie l'invitation de signature par e-mail au signataire (CGL ou BVSR).
    """
    from flask import current_app, has_request_context, request
    from utils.mailer import (
        send_cgl_invitation_email,
        send_safety_rules_invitation_email,
    )

    if waiver_type == "safety_rules":
        waiver = resolve_safety_rules_waiver(waiver_id)
    elif waiver_type == "cgl":
        waiver = resolve_cgl(waiver_id)
    else:
        waiver = resolve_waiver(waiver_id)

    if not waiver:
        return False, "Document non trouvé."

    mode = waiver.waiver_type

    if waiver.status == "to_generate":
        generate_waiver(waiver.waiver_id, waiver_type=mode)

    if waiver.status not in ["to_send", "to_sign"]:
        return False, "Statut invalide pour l'envoi."

    p = waiver.project
    if mode == "safety_rules":
        recipient_mail = waiver.signer_email
        recipient_name = waiver.signer_name
        if not recipient_mail and waiver.signer_role == "pilot" and p and p.pilot_contact:
            recipient_mail = p.pilot_contact.mail
            recipient_name = f"{p.pilot_contact.first_name} {p.pilot_contact.last_name}"
        if not recipient_mail:
            return False, "Le signataire n'a pas d'adresse e-mail renseignée pour l'envoi."
        route_prefix = "safety-rules"
    else:
        contact = p.production_contact if p else None
        if not contact or not contact.mail:
            return False, "La production n'a pas d'adresse e-mail de contact renseignée dans le projet."
        recipient_mail = contact.mail
        recipient_name = f"{contact.first_name} {contact.last_name}"
        route_prefix = "cgl"

    new_token = str(uuid.uuid4())
    token_rec = WaiverToken(token=new_token, waiver_id=waiver.waiver_id)
    db.session.add(token_rec)

    if base_url:
        resolved_base_url = base_url.rstrip('/')
    elif has_request_context():
        resolved_base_url = request.host_url.rstrip('/')
    else:
        server_name = current_app.config.get("SERVER_NAME") if current_app else None
        resolved_base_url = f"http://{server_name}" if server_name else "http://localhost:5000"

    signature_link = f"{resolved_base_url}/sign/{route_prefix}/{new_token}"
    is_reminder = (waiver.status == "to_sign") or bool(waiver.sent_at) or ((waiver.reminder_count or 0) > 0)

    if mode == "safety_rules":
        success = send_safety_rules_invitation_email(
            to_email=recipient_mail,
            recipient_name=recipient_name,
            project_name=p.name if p else "",
            signature_link=signature_link,
            is_reminder=is_reminder,
            production_name=(p.production.name if p and p.production else getattr(waiver, "production_name", None)),
        )
    else:
        success = send_cgl_invitation_email(
            to_email=recipient_mail,
            prod_contact_name=recipient_name,
            project_name=p.name if p else "",
            signature_link=signature_link,
            is_reminder=is_reminder,
            production_name=(p.production.name if p and p.production else getattr(waiver, "production_name", None)),
        )

    if not success:
        return False, "Échec de l'envoi de l'e-mail."

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    waiver.status = "to_sign"
    waiver.sent_at = waiver.sent_at or now_utc
    if is_reminder:
        waiver.reminder_count = (waiver.reminder_count or 0) + 1
        waiver.last_reminded_at = now_utc
    db.session.commit()

    if is_reminder:
        msg_type = "Relance envoyée"
    elif mode == "safety_rules":
        msg_type = "Règles de sécurité (BVSR) envoyées"
    else:
        msg_type = "Conditions Générales de Location (CGL) envoyées"

    target_label = f"à {recipient_name} ({recipient_mail})"
    return True, f"{msg_type} {target_label}."


@handle_admin_service_error
def delete_waiver(waiver_id, waiver_type: str = None):
    """Supprime logiquement un contrat ou engagement (soft-delete et nettoyage assets)."""
    if waiver_type == "safety_rules":
        waiver = resolve_safety_rules_waiver(waiver_id)
    elif waiver_type == "cgl":
        waiver = resolve_cgl(waiver_id)
    else:
        waiver = resolve_waiver(waiver_id)

    if not waiver:
        label = f" {waiver_type}" if waiver_type else ""
        return False, f"Document{label} introuvable."

    mode = waiver.waiver_type
    doc_type = f"{mode}_waiver"

    try:
        _cleanup_waiver_assets(mode, waiver)
        waiver.deleted_at = datetime.now(timezone.utc)
        db.session.commit()

        try:
            from services.common.kdrive import dispatch_delete_document
            dispatch_delete_document(doc_type, waiver.waiver_id)
        except Exception as k_err:
            logger.error(f"❌ Erreur dispatch suppression kDrive {doc_type} : {k_err}")

        logger.info(f"🗑️ Document {mode} {waiver.waiver_id} supprimé avec succès.")
        return True, "Document supprimé avec succès."
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erreur lors de la suppression {mode} {waiver_id} : {e}")
        return False, f"Erreur lors de la suppression : {str(e)}"


@handle_admin_service_error
def reset_waiver(waiver_id, waiver_type: str = None):
    """Réinitialise complètement un contrat ou engagement (supprime signatures et PDF)."""
    if waiver_type == "safety_rules":
        waiver = resolve_safety_rules_waiver(waiver_id)
    elif waiver_type == "cgl":
        waiver = resolve_cgl(waiver_id)
    else:
        waiver = resolve_waiver(waiver_id)

    if not waiver:
        return False, "Document non trouvé."

    mode = waiver.waiver_type
    doc_type = f"{mode}_waiver"

    try:
        _cleanup_waiver_assets(mode, waiver)
        _reset_waiver_fields(mode, waiver)
        db.session.commit()

        try:
            from services.common.kdrive import dispatch_delete_document
            dispatch_delete_document(doc_type, waiver.waiver_id)
        except Exception as k_err:
            logger.error(f"❌ Erreur dispatch suppression kDrive {doc_type} reset : {k_err}")

        return True, "Document réinitialisé avec succès."
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erreur lors du reset du document {waiver_id} : {e}")
        return False, f"Erreur lors de la réinitialisation : {str(e)}"


@handle_admin_service_error
def delete_waiver_internal(project_id, waiver_type: str = None):
    """Supprime proprement les contrats/engagements lors de la suppression d'un projet."""
    p = resolve_project(project_id)
    if not p:
        return

    if waiver_type == "cgl":
        waivers = [CglWaiver.query.filter_by(project_id=p.id).first()]
    elif waiver_type == "safety_rules":
        waivers = SafetyRulesWaiver.query.filter_by(project_id=p.id).all()
    else:
        waivers = Waiver.query.filter_by(project_id=p.id).all()

    for waiver in waivers:
        if not waiver:
            continue
        mode = waiver.waiver_type
        doc_type = f"{mode}_waiver"
        try:
            _cleanup_waiver_assets(mode, waiver)
            waiver.deleted_at = datetime.now(timezone.utc)
            db.session.commit()

            try:
                from services.common.kdrive import dispatch_delete_document
                dispatch_delete_document(doc_type, waiver.waiver_id)
            except Exception as k_err:
                logger.error(f"❌ Erreur dispatch suppression kDrive {doc_type} internal : {k_err}")
        except Exception as e:
            logger.error(f"❌ Erreur suppression {mode} pour projet {project_id} : {e}")
            db.session.rollback()
