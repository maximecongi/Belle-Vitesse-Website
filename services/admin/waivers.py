import logging
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import joinedload

from models import (
    PilotWaiver,
    PilotWaiverSignedDocument,
    PilotWaiverToken,
    ProductionWaiver,
    ProductionWaiverSignedDocument,
    ProductionWaiverToken,
    Project,
    db,
)
from services.admin.status_mapping import format_waiver_status
from utils.database import get_vehicles

# Keep here for list view
from utils.document_utils import (
    generate_pdf_access_token as generate_waiver_pdf_access_token,
)
from utils.n8n import trigger_n8n_webhook

logger = logging.getLogger(__name__)

# ── Aides Internes Génériques ──────────────────────────────────────


def _get_waiver_config(mode):
    """
    Retourne la configuration (modèles, webhooks, routes) selon le type de décharge (pilote ou production).
    """
    if mode == "pilot":
        return {
            "model": PilotWaiver,
            "signed_model": PilotWaiverSignedDocument,
            "token_model": PilotWaiverToken,
            "webhook_env": "N8N_WEBHOOK_PILOT_WAIVER",
            "route_base": "pilot-waiver",
            "attachment_fields": ["pilot_license_path", "pilot_insurance_path", "pilot_identity_path"]
        }
    return {
        "model": ProductionWaiver,
        "signed_model": ProductionWaiverSignedDocument,
        "token_model": ProductionWaiverToken,
        "webhook_env": "N8N_WEBHOOK_PRODUCTION_WAIVER",
        "route_base": "production-waiver",
        "attachment_fields": ["production_insurance_path"]
    }


def _cleanup_waiver_assets(mode, waiver):
    """
    Supprime les fichiers physiques (PDF signés, pièces jointes) et les documents archivés associés.
    """
    from flask import current_app
    config = _get_waiver_config(mode)

    # Liste des fichiers à supprimer physiquement du serveur
    files_to_delete = [waiver.signed_pdf_path] + \
        [getattr(waiver, f) for f in config["attachment_fields"]]

    output_base = current_app.config.get(
        "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

    for file_path in files_to_delete:
        if file_path:
            full_path = os.path.join(output_base, file_path)
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                    logger.info(f"🗑️ Fichier supprimé : {full_path}")
                except Exception as e:
                    logger.error(
                        f"❌ Erreur suppression fichier {full_path} : {e}")

    # Supprime l'enregistrement du document signé archivé
    signed_doc = config["signed_model"].query.filter_by(
        waiver_id=waiver.waiver_id).first()
    if signed_doc:
        db.session.delete(signed_doc)

    # Supprime les jetons de signature actifs
    config["token_model"].query.filter_by(waiver_id=waiver.waiver_id).delete()


def _reset_waiver_fields(mode, waiver):
    """
    Réinitialise tous les champs de snapshot et de signature d'une décharge.
    """
    waiver.status = "to_generate"
    waiver.generated_at = None
    waiver.sent_at = None
    waiver.signed_at = None
    waiver.signature_data = None
    waiver.signed_pdf_path = None
    waiver.signer_ip = None
    waiver.webhook_triggered_at = None

    # Nettoyage des données figées (snapshot) communes
    common_fields = ["project_name", "vehicles", "shooting_dates"]
    for f in common_fields:
        setattr(waiver, f, None)

    if mode == "pilot":
        pilot_fields = [
            "pilot_first_name", "pilot_last_name", "pilot_dob", "pilot_license_number",
            "pilot_address", "pilot_insurance_company", "pilot_insurance_policy",
            "pilot_license_path", "pilot_insurance_path", "pilot_identity_path"
        ]
        for f in pilot_fields:
            setattr(waiver, f, None)
    else:
        prod_fields = [
            "production_name", "production_representative", "production_address",
            "production_siret", "production_vat", "production_insurance_company",
            "production_insurance_policy", "production_insurance_validity",
            "location_of_use", "production_insurance_path"
        ]
        for f in prod_fields:
            setattr(waiver, f, None)


# ── Décharges Production ───────────────────────────────────────────

def create_production_waiver(project_id):
    """Crée une décharge production pour un projet s'il n'en existe pas déjà une."""
    existing = ProductionWaiver.query.filter_by(project_id=project_id).first()
    if existing:
        return False, "Une décharge production existe déjà pour ce projet."

    waiver = ProductionWaiver(project_id=project_id)
    db.session.add(waiver)
    db.session.commit()
    return True, "Décharge production créée avec succès."


def list_production_waivers():
    """Liste et formate toutes les décharges production pour l'administration."""
    waivers = ProductionWaiver.query.join(Project).filter(
        ProductionWaiver.deleted_at == None,
        Project.deleted_at == None
    ).options(joinedload(ProductionWaiver.project)).all()
    # Tri par date de départ du projet (décroissant)
    waivers.sort(key=lambda w: (
        w.project.departure_date or datetime.min.date(), w.project.name), reverse=True)

    formatted = []
    for w in waivers:
        p = w.project

        def get_secured_url(path):
            """Génère l'URL sécurisée pour le document signé."""
            if not path:
                return None
            clean_path = path.split('?')[0].split(
                '/production-waiver/document/')[-1]
            token = generate_waiver_pdf_access_token(clean_path)
            return f"/production-waiver/document/{clean_path}?t={token}"

        shooting_dates = "—"
        if p.shoot_start_date and p.shoot_end_date:
            shooting_dates = f"{p.shoot_start_date.strftime('%d/%m/%Y')} → {p.shoot_end_date.strftime('%d/%m/%Y')}"
        elif w.shooting_dates:
            shooting_dates = w.shooting_dates

        # Récupère le jeton de signature actif si existant
        active_token = ProductionWaiverToken.query.filter_by(
            waiver_id=w.waiver_id).order_by(ProductionWaiverToken.created_at.desc()).first()

        production_contact_name = "—"
        if p.production_contact:
            production_contact_name = f"{p.production_contact.first_name} {p.production_contact.last_name}"

        formatted.append({
            "id": w.waiver_id,
            "db_id": w.id,
            "waiver_id": w.waiver_id,
            "project_id": p.id,
            "project_name": p.name,
            "production_name": (p.production.name if p.production else w.production_name) or "—",
            "production_contact_name": production_contact_name,
            "shooting_dates": shooting_dates,
            "status": format_waiver_status(w.status),
            "raw_status": w.status,
            "generated_at": w.generated_at,
            "sent_at": w.sent_at,
            "signed_at": w.signed_at,
            "signature_token": active_token.token if active_token else None,
            "signed_pdf_path": get_secured_url(w.signed_pdf_path)
        })
    return formatted


def generate_production_waiver(waiver_id):
    """
    Génère (fige les données de snapshot) une décharge production.
    Passe le statut de 'to_generate' à 'to_send'.
    """
    waiver = ProductionWaiver.query.filter_by(waiver_id=waiver_id).first()
    if not waiver or waiver.status != "to_generate":
        return False, "Décharge non trouvée ou statut invalide."

    if not waiver.project.production_contact:
        return False, "Aucun contact de production n'est assigné à ce projet."

    p = waiver.project
    waiver.project_name = p.name
    if p.production:
        waiver.production_name = p.production.name
        waiver.production_address = p.production.address

    if p.shoot_start_date and p.shoot_end_date:
        waiver.shooting_dates = f"{p.shoot_start_date.strftime('%d/%m/%Y')} au {p.shoot_end_date.strftime('%d/%m/%Y')}"

    if p.vehicles_to_check:
        veh_ids = [v.strip()
                   for v in p.vehicles_to_check.split(",") if v.strip()]
        all_vehicles = get_vehicles()
        vehicle_map = {str(v["id"]): v.get("fields", {}).get(
            "name", f"ID {v['id']}") for v in all_vehicles}
        waiver.vehicles = ", ".join(
            [vehicle_map.get(vid, vid) for vid in veh_ids])

    waiver.status = "to_send"
    waiver.generated_at = datetime.utcnow()
    db.session.commit()
    return True, "Décharge production générée avec succès."


def send_production_waiver(waiver_id):
    """Envoie l'invitation de signature par e-mail au contact production."""
    from flask import request
    from utils.mailer import send_production_waiver_invitation_email

    waiver = ProductionWaiver.query.filter_by(waiver_id=waiver_id).first()
    if not waiver:
        return False, "Décharge non trouvée."

    contact_prod = waiver.project.production_contact
    if not contact_prod or not contact_prod.mail:
        return False, "La production n'a pas d'adresse e-mail de contact renseignée dans le projet."

    # Crée un nouveau jeton de signature (validité 24h gérée en DB)
    new_token = str(uuid.uuid4())
    token_rec = ProductionWaiverToken(
        token=new_token, waiver_id=waiver.waiver_id)
    db.session.add(token_rec)

    base_url = request.host_url.rstrip('/')
    signature_link = f"{base_url}/sign/production-waiver/{new_token}"

    success = send_production_waiver_invitation_email(
        to_email=contact_prod.mail,
        prod_contact_name=f"{contact_prod.first_name} {contact_prod.last_name}",
        project_name=waiver.project.name,
        signature_link=signature_link
    )

    if not success:
        return False, "Échec de l'envoi de l'e-mail."

    waiver.status = "to_sign"
    waiver.sent_at = datetime.utcnow()
    db.session.commit()
    return True, f"Décharge envoyée à la production ({contact_prod.mail})."


def reset_production_waiver(waiver_id):
    """Réinitialise complètement une décharge production (supprime signature, PDF et notifie n8n)."""
    waiver = ProductionWaiver.query.filter_by(waiver_id=waiver_id).first()
    if not waiver:
        return False, "Décharge non trouvée."

    try:
        # Notifie n8n de la suppression/reset
        webhook_url = os.getenv("N8N_WEBHOOK_PRODUCTION_WAIVER")
        if webhook_url:
            trigger_n8n_webhook(webhook_url, method="DELETE",
                                waiver_id=waiver.waiver_id, project_id=waiver.project.project_id)

        _cleanup_waiver_assets("production", waiver)
        _reset_waiver_fields("production", waiver)
        db.session.commit()
        return True, "Décharge réinitialisée avec succès."
    except Exception as e:
        db.session.rollback()
        return False, f"Erreur lors du reset : {e}"


def delete_production_waiver_internal(project_id):
    """Supprime proprement une décharge production en interne (appelé lors de suppression de projet)."""
    waiver = ProductionWaiver.query.filter_by(project_id=project_id).first()
    if not waiver:
        return
    try:
        webhook_url = os.getenv("N8N_WEBHOOK_PRODUCTION_WAIVER")
        if webhook_url:
            trigger_n8n_webhook(webhook_url, method="DELETE",
                                waiver_id=waiver.waiver_id, project_id=waiver.project.project_id)
        _cleanup_waiver_assets("production", waiver)
        waiver.deleted_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception as e:
        logger.error(f"❌ Erreur suppression décharge production : {e}")
        db.session.rollback()


# ── Décharges Pilote ────────────────────────────────────────────────

def create_pilot_waiver(project_id):
    """Crée une décharge pilote pour un projet s'il n'en existe pas déjà une."""
    existing = PilotWaiver.query.filter_by(project_id=project_id).first()
    if existing:
        return False, "Une décharge existe déjà pour ce projet."

    waiver = PilotWaiver(project_id=project_id)
    db.session.add(waiver)
    db.session.commit()
    return True, "Décharge créée avec succès."


def list_pilot_waivers():
    """Liste et formate toutes les décharges pilote pour l'administration."""
    waivers = PilotWaiver.query.join(Project).filter(
        PilotWaiver.deleted_at == None,
        Project.deleted_at == None
    ).options(
        joinedload(PilotWaiver.project).joinedload(Project.pilot_contact)
    ).all()
    # Tri par date de départ du projet (décroissant)
    waivers.sort(key=lambda w: (
        w.project.departure_date or datetime.min.date(), w.project.name), reverse=True)

    formatted = []
    for w in waivers:
        p = w.project

        def get_secured_url(path, is_attachment=False):
            """Génère l'URL sécurisée pour le PDF signé ou les pièces jointes (permis, assurance, ID)."""
            if not path:
                return None
            clean_path = path.split('?')[0].split(
                '/pilot-waiver/document/')[-1].split('/pilot-waiver/attachment/')[-1]
            token = generate_waiver_pdf_access_token(clean_path)
            route = '/pilot-waiver/attachment/' if is_attachment else '/pilot-waiver/document/'
            return f"{route}{clean_path}?t={token}"

        pilote_name = "—"
        if p.pilot_contact:
            pilote_name = f"{p.pilot_contact.first_name} {p.pilot_contact.last_name}"
        elif w.pilot_first_name or w.pilot_last_name:
            pilote_name = f"{w.pilot_first_name or ''} {w.pilot_last_name or ''}".strip(
            )

        shooting_dates = "—"
        if p.shoot_start_date and p.shoot_end_date:
            shooting_dates = f"{p.shoot_start_date.strftime('%d/%m/%Y')} → {p.shoot_end_date.strftime('%d/%m/%Y')}"
        elif w.shooting_dates:
            shooting_dates = w.shooting_dates

        # Récupère le jeton de signature actif si existant
        active_token = PilotWaiverToken.query.filter_by(
            waiver_id=w.waiver_id).order_by(PilotWaiverToken.created_at.desc()).first()

        formatted.append({
            "id": w.waiver_id,
            "db_id": w.id,
            "waiver_id": w.waiver_id,
            "project_id": p.id,
            "project_name": p.name,
            "pilot_name": pilote_name,
            "shooting_dates": shooting_dates,
            "status": format_waiver_status(w.status),
            "raw_status": w.status,
            "generated_at": w.generated_at,
            "sent_at": w.sent_at,
            "signed_at": w.signed_at,
            "signature_token": active_token.token if active_token else None,
            "signed_pdf_path": get_secured_url(w.signed_pdf_path),
            "pilot_license_path": get_secured_url(w.pilot_license_path, is_attachment=True),
            "pilot_insurance_path": get_secured_url(w.pilot_insurance_path, is_attachment=True),
            "pilot_identity_path": get_secured_url(w.pilot_identity_path, is_attachment=True)
        })
    return formatted


def generate_pilot_waiver(waiver_id):
    """
    Génère (fige les données de snapshot) une décharge pilote.
    Passe le statut de 'to_generate' à 'to_send'.
    """
    waiver = PilotWaiver.query.filter_by(waiver_id=waiver_id).first()
    if not waiver or waiver.status != "to_generate":
        return False, "Décharge non trouvée ou statut invalide."

    if not waiver.project.pilot_contact:
        return False, "Aucun pilote n'est assigné à ce projet."

    p = waiver.project
    contact = p.pilot_contact
    if contact:
        waiver.pilot_first_name = contact.first_name
        waiver.pilot_last_name = contact.last_name
        waiver.pilot_address = getattr(contact, 'address', "")

    if p.production:
        waiver.production_name = p.production.name
    waiver.project_name = p.name

    if p.shoot_start_date and p.shoot_end_date:
        waiver.shooting_dates = f"{p.shoot_start_date.strftime('%d/%m/%Y')} au {p.shoot_end_date.strftime('%d/%m/%Y')}"

    if p.vehicles_to_check:
        veh_ids = [v.strip()
                   for v in p.vehicles_to_check.split(",") if v.strip()]
        all_vehicles = get_vehicles()
        vehicle_map = {str(v["id"]): v.get("fields", {}).get(
            "name", f"ID {v['id']}") for v in all_vehicles}
        waiver.vehicles = ", ".join(
            [vehicle_map.get(vid, vid) for vid in veh_ids])
    else:
        # Fallback sur les véhicules déjà contrôlés (checkout)
        waiver.vehicles = ", ".join(
            [cv.vehicle_name for cv in p.checkout_vehicles])

    waiver.status = "to_send"
    waiver.generated_at = datetime.utcnow()
    db.session.commit()
    return True, "Décharge générée avec succès."


def send_pilot_waiver(waiver_id):
    """Envoie l'invitation de signature par e-mail au pilote."""
    from flask import request
    from utils.mailer import send_waiver_invitation_email

    waiver = PilotWaiver.query.filter_by(waiver_id=waiver_id).first()
    if not waiver:
        return False, "Décharge non trouvée."
    if waiver.status not in ["to_send", "to_sign"]:
        return False, "Statut invalide pour l'envoi."

    pilot_contact = waiver.project.pilot_contact
    if not pilot_contact or not pilot_contact.mail:
        return False, "Le pilote n'a pas d'adresse e-mail renseignée dans le projet."

    # Crée un nouveau jeton de signature (validité 24h gérée en DB)
    new_token = str(uuid.uuid4())
    token_rec = PilotWaiverToken(token=new_token, waiver_id=waiver.waiver_id)
    db.session.add(token_rec)

    base_url = request.host_url.rstrip('/')
    signature_link = f"{base_url}/sign/waiver/{new_token}"

    success = send_waiver_invitation_email(
        to_email=pilot_contact.mail,
        pilot_name=f"{pilot_contact.first_name} {pilot_contact.last_name}",
        project_name=waiver.project.name,
        signature_link=signature_link
    )

    if not success:
        return False, "Échec de l'envoi de l'e-mail."

    waiver.status = "to_sign"
    waiver.sent_at = datetime.utcnow()
    db.session.commit()
    return True, f"Décharge envoyée au pilote ({pilot_contact.mail})."


def reset_pilot_waiver(waiver_id):
    """Réinitialise complètement une décharge pilote (supprime signature, PDF et notifie n8n)."""
    waiver = PilotWaiver.query.filter_by(waiver_id=waiver_id).first()
    if not waiver:
        return False, "Décharge non trouvée."

    try:
        # Notifie n8n de la suppression/reset
        webhook_url = os.getenv("N8N_WEBHOOK_PILOT_WAIVER")
        if webhook_url:
            trigger_n8n_webhook(webhook_url, method="DELETE",
                                waiver_id=waiver.waiver_id, project_id=waiver.project.project_id)

        _cleanup_waiver_assets("pilot", waiver)
        _reset_waiver_fields("pilot", waiver)
        db.session.commit()
        return True, "Décharge réinitialisée avec succès."
    except Exception as e:
        db.session.rollback()
        logger.error(
            f"❌ Erreur lors du reset de la décharge {waiver_id} : {e}")
        return False, f"Erreur lors de la réinitialisation : {str(e)}"


def delete_pilot_waiver_internal(project_id):
    """Supprime proprement une décharge pilote en interne (appelé lors de suppression de projet)."""
    waiver = PilotWaiver.query.filter_by(project_id=project_id).first()
    if not waiver:
        return
    try:
        webhook_url = os.getenv("N8N_WEBHOOK_PILOT_WAIVER")
        if webhook_url:
            trigger_n8n_webhook(webhook_url, method="DELETE",
                                waiver_id=waiver.waiver_id, project_id=waiver.project.project_id)
        _cleanup_waiver_assets("pilot", waiver)
        waiver.deleted_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception as e:
        logger.error(
            f"❌ Erreur lors de la suppression interne de la décharge pour projet {project_id} : {e}")
        db.session.rollback()
