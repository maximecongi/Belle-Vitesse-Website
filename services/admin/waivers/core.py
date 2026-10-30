"""
services/admin/waivers/core.py — Gestion du cycle de vie unifié des décharges (création, génération, envoi, suppression, reset).
"""
import hashlib
import logging
import uuid
from datetime import datetime, timezone

from models import (
    CglWaiver,
    SafetyRulesWaiver,
    PilotWaiver,
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
    resolve_pilot_waiver,
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
        existing_active = model.query.filter_by(project_id=project_id, deleted_at=None).first()
        if existing_active:
            return False, "Des Conditions Générales de Location (CGL) existent déjà pour ce projet."

        # Nettoyage des anciens brouillons non signés supprimés s'il y en a
        stale_drafts = model.query.filter_by(project_id=project_id).filter(model.deleted_at.isnot(None)).all()
        for stale in stale_drafts:
            from models import WaiverSignedDocument
            signed_doc = WaiverSignedDocument.query.filter_by(waiver_id=stale.waiver_id).first()
            if not signed_doc and stale.status not in ["signed", "completed"]:
                _cleanup_waiver_assets(waiver_type, stale)
                db.session.delete(stale)
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
        waiver.safety_technicians = (kwargs.get("safety_technicians") or "").strip() or getattr(p, "bv_referents_names", None) or None
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

    elif waiver_type == "pilot_waiver":
        waiver.signer_role = kwargs.get("signer_role", "pilot")
        waiver.signer_role_custom = kwargs.get("signer_role_custom")
        waiver.signer_first_name = kwargs.get("signer_first_name")
        waiver.signer_last_name = kwargs.get("signer_last_name")
        waiver.signer_email = kwargs.get("signer_email")
        waiver.signer_phone = kwargs.get("signer_phone")
        waiver.signer_company = kwargs.get("signer_company") or (p.production.name if p.production else "")
        if not waiver.signer_first_name and p.pilot_contact:
            waiver.signer_first_name = p.pilot_contact.first_name
            waiver.signer_last_name = p.pilot_contact.last_name
            waiver.signer_email = p.pilot_contact.mail
            waiver.signer_phone = getattr(p.pilot_contact, "tel", "")

    waiver.shooting_dates = _format_project_shooting_dates(p, default_sep=" au ")

    selected_v = kwargs.get("selected_vehicles")
    if "selected_vehicles" in kwargs and selected_v is not None:
        if isinstance(selected_v, list):
            cleaned_v = [str(v).strip() for v in selected_v if str(v).strip()]
            if waiver_type == "pilot_waiver" and not cleaned_v:
                return False, "Veuillez sélectionner au moins 1 véhicule pour l'attestation pilote."
            waiver.vehicles = ", ".join(cleaned_v)
        elif isinstance(selected_v, str):
            cleaned_str = selected_v.strip()
            if waiver_type == "pilot_waiver" and not cleaned_str:
                return False, "Veuillez sélectionner au moins 1 véhicule pour l'attestation pilote."
            waiver.vehicles = cleaned_str
        else:
            waiver.vehicles = str(selected_v).strip()
    elif p.vehicles_to_check:
        veh_ids = [v.strip() for v in p.vehicles_to_check.split(",") if v.strip()]
        all_vehicles = get_vehicles()
        vehicle_map = {str(v["id"]): v.get("fields", {}).get("name", f"ID {v['id']}") for v in all_vehicles}
        waiver.vehicles = ", ".join([vehicle_map.get(vid, vid) for vid in veh_ids])
    elif p.active_checkout_vehicles:
        waiver.vehicles = ", ".join([cv.vehicle_name for cv in p.active_checkout_vehicles if cv.vehicle_name])

    if waiver_type == "pilot_waiver" and not waiver.vehicles:
        return False, "Veuillez sélectionner au moins 1 véhicule pour l'attestation pilote."

    waiver.status = "to_send"
    waiver.generated_at = _utcnow()

    db.session.add(waiver)
    db.session.commit()

    if waiver_type == "cgl":
        msg = "Conditions Générales de Location (CGL) créées avec succès."
    elif waiver_type == "pilot_waiver":
        msg = f"Attestation Pilote (Annexe 3) créée avec succès pour {waiver.signer_name}."
    else:
        msg = f"Règles de sécurité BVSR créées avec succès pour {waiver.signer_name} ({waiver.signer_role_label})."
    return True, msg


@handle_admin_service_error
def generate_waiver(waiver_id, waiver_type: str = None):
    """
    Génère (fige les données de snapshot) un contrat CGL, engagement BVSR ou attestation pilote.
    Passe le statut de 'to_generate' à 'to_send'.
    """
    if waiver_type == "safety_rules":
        waiver = resolve_safety_rules_waiver(waiver_id)
    elif waiver_type == "pilot_waiver":
        waiver = resolve_pilot_waiver(waiver_id)
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
    elif mode in ("safety_rules", "pilot_waiver"):
        if p and p.production:
            waiver.production_name = p.production.name

    if p:
        waiver.project_name = p.name
        waiver.shooting_dates = _format_project_shooting_dates(p, default_sep=" au ")
        if not waiver.vehicles:
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

    if mode == "cgl":
        msg = "Conditions Générales de Location (CGL) générées avec succès."
    elif mode == "pilot_waiver":
        msg = "Attestation Pilote (Annexe 3) générée avec succès."
    else:
        msg = "Règles de sécurité BVSR générées avec succès."
    return True, msg


@handle_admin_service_error
def send_waiver(waiver_id, waiver_type: str = None, base_url: str = None):
    """
    Envoie l'invitation de signature par e-mail au signataire (CGL, BVSR ou Pilote).
    """
    from flask import current_app, has_request_context, request
    from utils.mailer import (
        send_cgl_invitation_email,
        send_safety_rules_invitation_email,
        send_pilot_waiver_invitation_email,
    )

    if waiver_type == "safety_rules":
        waiver = resolve_safety_rules_waiver(waiver_id)
    elif waiver_type == "pilot_waiver":
        waiver = resolve_pilot_waiver(waiver_id)
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
    if mode in ("safety_rules", "pilot_waiver"):
        recipient_mail = waiver.signer_email
        recipient_name = waiver.signer_name
        if not recipient_mail and waiver.signer_role == "pilot" and p and p.pilot_contact:
            recipient_mail = p.pilot_contact.mail
            recipient_name = f"{p.pilot_contact.first_name} {p.pilot_contact.last_name}"
        if not recipient_mail:
            return False, "Le signataire n'a pas d'adresse e-mail renseignée pour l'envoi."
        route_prefix = "safety-rules" if mode == "safety_rules" else "pilot-attestation"
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

    from utils.request_utils import resolve_base_url
    resolved_base_url = resolve_base_url(base_url)

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
    elif mode == "pilot_waiver":
        success = send_pilot_waiver_invitation_email(
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

    from services.common.signatures import log_signature_event
    log_signature_event(
        waiver.waiver_id,
        mode,
        "link_sent",
        {
            "recipient_email": recipient_mail,
            "recipient_name": recipient_name,
            "is_reminder": is_reminder,
            "token_preview": f"{new_token[:8]}..." if new_token else "",
            "token_sha256": hashlib.sha256(new_token.encode("utf-8")).hexdigest() if new_token else "",
        }
    )
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
    elif waiver_type == "pilot_waiver":
        waiver = resolve_pilot_waiver(waiver_id)
    else:
        waiver = resolve_waiver(waiver_id)

    if not waiver:
        label = f" {waiver_type}" if waiver_type else ""
        return False, f"Document{label} introuvable."

    mode = waiver.waiver_type

    try:
        from models import WaiverSignedDocument
        signed_doc = WaiverSignedDocument.query.filter_by(waiver_id=waiver.waiver_id).order_by(WaiverSignedDocument.version.desc()).first()
        is_signed = bool(waiver.status in ["signed", "completed"] or signed_doc)

        if is_signed:
            # Document signé : Préservation absolue de la preuve juridique en base SQL (WaiverSignedDocument)
            # Révocation des jetons actifs et suppression logique (soft delete).
            WaiverToken.query.filter_by(waiver_id=waiver.waiver_id).delete()
            waiver.deleted_at = datetime.now(timezone.utc)
            db.session.commit()

            from services.common.signatures import log_signature_event
            admin_user = "system"
            try:
                from flask import session
                admin_user = (
                    session.get("admin_user_mail")
                    or session.get("user")
                    or session.get("admin_user_firstname")
                    or "system"
                )
            except Exception:
                pass

            log_signature_event(
                waiver.waiver_id,
                mode,
                "waiver_archived_or_retired",
                {
                    "archive_hash": signed_doc.hash if signed_doc else "",
                    "pdf_file_hash": signed_doc.pdf_file_hash if signed_doc else "",
                    "admin_user": admin_user,
                    "action": "soft_delete_preserve_proof",
                }
            )
        else:
            # Document non signé : nettoyage normal des assets de travail locaux
            _cleanup_waiver_assets(mode, waiver)
            waiver.deleted_at = datetime.now(timezone.utc)
            db.session.commit()

        # Suppression kDrive native pour tout document supprimé (signé ou non)
        try:
            from services.common.kdrive import dispatch_delete_document
            dispatch_delete_document(mode, waiver.waiver_id)
        except Exception as k_err:
            logger.error(f"❌ Erreur dispatch suppression kDrive {mode} : {k_err}")

        logger.info(f"🗑️ Document {mode} {waiver.waiver_id} supprimé avec succès (conservé={is_signed}).")
        return True, "Document supprimé avec succès."
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erreur lors de la suppression {mode} {waiver_id} : {e}")
        return False, f"Erreur lors de la suppression : {str(e)}"


@handle_admin_service_error
def reset_waiver(waiver_id, waiver_type: str = None):
    """Réinitialise complètement un contrat ou engagement (autorisé UNIQUEMENT si non signé)."""
    if waiver_type == "safety_rules":
        waiver = resolve_safety_rules_waiver(waiver_id)
    elif waiver_type == "cgl":
        waiver = resolve_cgl(waiver_id)
    elif waiver_type == "pilot_waiver":
        waiver = resolve_pilot_waiver(waiver_id)
    else:
        waiver = resolve_waiver(waiver_id)

    if not waiver:
        return False, "Document non trouvé."

    from models import WaiverSignedDocument
    signed_doc = WaiverSignedDocument.query.filter_by(waiver_id=waiver.waiver_id).order_by(WaiverSignedDocument.version.desc()).first()
    if waiver.status in ["signed", "completed"] or signed_doc:
        return False, (
            "Impossible de réinitialiser un document déjà signé et scellé juridiquement. "
            "L'archive et la preuve d'origine sont protégées. Veuillez archiver ce document ou créer une nouvelle version."
        )

    mode = waiver.waiver_type

    try:
        _cleanup_waiver_assets(mode, waiver)
        _reset_waiver_fields(mode, waiver)
        db.session.commit()

        try:
            from services.common.kdrive import dispatch_delete_document
            dispatch_delete_document(mode, waiver.waiver_id)
        except Exception as k_err:
            logger.error(f"❌ Erreur dispatch suppression kDrive {mode} reset : {k_err}")

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
        waivers = CglWaiver.query.filter_by(project_id=p.id).all()
    elif waiver_type == "safety_rules":
        waivers = SafetyRulesWaiver.query.filter_by(project_id=p.id).all()
    elif waiver_type == "pilot_waiver":
        waivers = PilotWaiver.query.filter_by(project_id=p.id).all()
    else:
        waivers = Waiver.query.filter_by(project_id=p.id).all()

    for waiver in waivers:
        if not waiver:
            continue
        mode = waiver.waiver_type
        try:
            from models import WaiverSignedDocument
            signed_doc = WaiverSignedDocument.query.filter_by(waiver_id=waiver.waiver_id).order_by(WaiverSignedDocument.version.desc()).first()
            is_signed = bool(waiver.status in ["signed", "completed"] or signed_doc)

            if is_signed:
                WaiverToken.query.filter_by(waiver_id=waiver.waiver_id).delete()
                waiver.deleted_at = datetime.now(timezone.utc)
                db.session.commit()
            else:
                _cleanup_waiver_assets(mode, waiver)
                waiver.deleted_at = datetime.now(timezone.utc)
                db.session.commit()

            try:
                from services.common.kdrive import dispatch_delete_document
                dispatch_delete_document(mode, waiver.waiver_id)
            except Exception as k_err:
                logger.error(f"❌ Erreur dispatch suppression kDrive {mode} internal : {k_err}")
        except Exception as e:
            logger.error(f"❌ Erreur suppression {mode} pour projet {project_id} : {e}")
            db.session.rollback()
