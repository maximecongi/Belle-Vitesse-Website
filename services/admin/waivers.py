import logging
import os
import uuid
from datetime import datetime
from sqlalchemy.orm import joinedload

from models import (
    db,
    PilotWaiver,
    ProductionWaiver,
    Project,
    PilotWaiverSignedDocument,
    ProductionWaiverSignedDocument
)
from utils.database import get_vehicles
from utils.n8n import trigger_n8n_webhook
# Keep here for list view
from utils.document_utils import generate_pdf_access_token as generate_waiver_pdf_access_token

logger = logging.getLogger(__name__)

# ── Generic Internal Helpers ─────────────────────────────────────


def _get_waiver_config(mode):
    if mode == "pilot":
        return {
            "model": PilotWaiver,
            "signed_model": PilotWaiverSignedDocument,
            "webhook_env": "N8N_WEBHOOK_PILOT_WAIVER",
            "route_base": "pilot-waiver",
            "attachment_fields": ["pilot_license_path", "pilot_insurance_path", "pilot_identity_path"]
        }
    return {
        "model": ProductionWaiver,
        "signed_model": ProductionWaiverSignedDocument,
        "webhook_env": "N8N_WEBHOOK_PRODUCTION_WAIVER",
        "route_base": "production-waiver",
        "attachment_fields": ["production_insurance_path"]
    }


def _cleanup_waiver_assets(mode, waiver):
    """Internal helper to delete physical files and signed documents."""
    from flask import current_app
    config = _get_waiver_config(mode)

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

    signed_doc = config["signed_model"].query.filter_by(
        waiver_id=waiver.waiver_id).first()
    if signed_doc:
        db.session.delete(signed_doc)


def _reset_waiver_fields(mode, waiver):
    """Resets all snapshot and signature fields of a waiver."""
    waiver.status = "to_generate"
    waiver.generated_at = None
    waiver.sent_at = None
    waiver.signed_at = None
    waiver.signature_token = None
    waiver.signature_data = None
    waiver.signed_pdf_path = None
    waiver.signer_ip = None
    waiver.webhook_triggered_at = None

    # Snapshot cleanup
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


# ── Production Waivers ───────────────────────────────────────────

def create_production_waiver(project_id):
    existing = ProductionWaiver.query.filter_by(project_id=project_id).first()
    if existing:
        return False, "Une décharge production existe déjà pour ce projet."

    waiver = ProductionWaiver(project_id=project_id)
    db.session.add(waiver)
    db.session.commit()
    return True, "Décharge production créée avec succès."


def list_production_waivers():
    waivers = ProductionWaiver.query.options(
        joinedload(ProductionWaiver.project)).all()
    waivers.sort(key=lambda w: (
        w.project.date_depart or datetime.min.date(), w.project.nom), reverse=True)

    formatted = []
    for w in waivers:
        p = w.project

        def get_secured_url(path):
            if not path:
                return None
            # Extract path if it's already a full URL/tokenized
            clean_path = path.split('?')[0].split(
                '/production-waiver/document/')[-1]
            token = generate_waiver_pdf_access_token(clean_path)
            return f"/production-waiver/document/{clean_path}?t={token}"

        shooting_dates = "—"
        if p.date_debut_tournage and p.date_fin_tournage:
            shooting_dates = f"{p.date_debut_tournage.strftime('%d/%m/%Y')} → {p.date_fin_tournage.strftime('%d/%m/%Y')}"
        elif w.shooting_dates:
            shooting_dates = w.shooting_dates

        formatted.append({
            "id": w.waiver_id,
            "db_id": w.id,
            "waiver_id": w.waiver_id,
            "project_id": p.id,
            "project_name": p.nom,
            "production_name": (p.production.nom if p.production else w.production_name) or "—",
            "shooting_dates": shooting_dates,
            "status": w.status,
            "generated_at": w.generated_at,
            "sent_at": w.sent_at,
            "signed_at": w.signed_at,
            "signature_token": w.signature_token,
            "signed_pdf_path": get_secured_url(w.signed_pdf_path)
        })
    return formatted


def generate_production_waiver(waiver_id):
    waiver = ProductionWaiver.query.filter_by(waiver_id=waiver_id).first()
    if not waiver or waiver.status != "to_generate":
        return False, "Décharge non trouvée ou statut invalide."

    p = waiver.project
    waiver.project_name = p.nom
    if p.production:
        waiver.production_name = p.production.nom
        waiver.production_address = p.production.adresse

    if p.date_debut_tournage and p.date_fin_tournage:
        waiver.shooting_dates = f"{p.date_debut_tournage.strftime('%d/%m/%Y')} au {p.date_fin_tournage.strftime('%d/%m/%Y')}"

    if p.vehicules_a_controler:
        veh_ids = [v.strip()
                   for v in p.vehicules_a_controler.split(",") if v.strip()]
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
    from flask import request
    from utils.mailer import send_production_waiver_invitation_email

    waiver = ProductionWaiver.query.filter_by(waiver_id=waiver_id).first()
    if not waiver:
        return False, "Décharge non trouvée."

    contact_prod = waiver.project.contact_production_rel
    if not contact_prod or not contact_prod.mail:
        return False, "La production n'a pas d'adresse e-mail de contact renseignée dans le projet."

    if not waiver.signature_token:
        waiver.signature_token = str(uuid.uuid4())

    base_url = request.host_url.rstrip('/')
    signature_link = f"{base_url}/sign/production-waiver/{waiver.signature_token}"

    success = send_production_waiver_invitation_email(
        to_email=contact_prod.mail,
        prod_contact_name=f"{contact_prod.prenom} {contact_prod.nom}",
        project_name=waiver.project.nom,
        signature_link=signature_link
    )

    if not success:
        return False, "Échec de l'envoi de l'e-mail."

    waiver.status = "to_sign"
    waiver.sent_at = datetime.utcnow()
    db.session.commit()
    return True, f"Décharge envoyée à la production ({contact_prod.mail})."


def reset_production_waiver(waiver_id):
    waiver = ProductionWaiver.query.filter_by(waiver_id=waiver_id).first()
    if not waiver:
        return False, "Décharge non trouvée."

    try:
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
    waiver = ProductionWaiver.query.filter_by(project_id=project_id).first()
    if not waiver:
        return
    try:
        webhook_url = os.getenv("N8N_WEBHOOK_PRODUCTION_WAIVER")
        if webhook_url:
            trigger_n8n_webhook(webhook_url, method="DELETE",
                                waiver_id=waiver.waiver_id, project_id=waiver.project.project_id)
        _cleanup_waiver_assets("production", waiver)
        db.session.delete(waiver)
        db.session.commit()
    except Exception as e:
        logger.error(f"❌ Erreur suppression décharge production : {e}")
        db.session.rollback()


# ── Pilot Waivers ────────────────────────────────────────────────

def create_pilot_waiver(project_id):
    existing = PilotWaiver.query.filter_by(project_id=project_id).first()
    if existing:
        return False, "Une décharge existe déjà pour ce projet."

    waiver = PilotWaiver(project_id=project_id)
    db.session.add(waiver)
    db.session.commit()
    return True, "Décharge créée avec succès."


def list_pilot_waivers():
    waivers = PilotWaiver.query.options(
        joinedload(PilotWaiver.project).joinedload(Project.contact_pilote_rel)
    ).all()
    waivers.sort(key=lambda w: (
        w.project.date_depart or datetime.min.date(), w.project.nom), reverse=True)

    formatted = []
    for w in waivers:
        p = w.project

        def get_secured_url(path, is_attachment=False):
            if not path:
                return None
            clean_path = path.split('?')[0].split(
                '/pilot-waiver/document/')[-1].split('/pilot-waiver/attachment/')[-1]
            token = generate_waiver_pdf_access_token(clean_path)
            route = '/pilot-waiver/attachment/' if is_attachment else '/pilot-waiver/document/'
            return f"{route}{clean_path}?t={token}"

        pilote_name = "—"
        if p.contact_pilote_rel:
            pilote_name = f"{p.contact_pilote_rel.prenom} {p.contact_pilote_rel.nom}"
        elif w.pilot_first_name or w.pilot_last_name:
            pilote_name = f"{w.pilot_first_name or ''} {w.pilot_last_name or ''}".strip(
            )

        shooting_dates = "—"
        if p.date_debut_tournage and p.date_fin_tournage:
            shooting_dates = f"{p.date_debut_tournage.strftime('%d/%m/%Y')} → {p.date_fin_tournage.strftime('%d/%m/%Y')}"
        elif w.shooting_dates:
            shooting_dates = w.shooting_dates

        formatted.append({
            "id": w.waiver_id,
            "db_id": w.id,
            "waiver_id": w.waiver_id,
            "project_id": p.id,
            "project_name": p.nom,
            "pilot_name": pilote_name,
            "shooting_dates": shooting_dates,
            "status": w.status,
            "generated_at": w.generated_at,
            "sent_at": w.sent_at,
            "signed_at": w.signed_at,
            "signature_token": w.signature_token,
            "signed_pdf_path": get_secured_url(w.signed_pdf_path),
            "pilot_license_path": get_secured_url(w.pilot_license_path, is_attachment=True),
            "pilot_insurance_path": get_secured_url(w.pilot_insurance_path, is_attachment=True),
            "pilot_identity_path": get_secured_url(w.pilot_identity_path, is_attachment=True)
        })
    return formatted


def generate_pilot_waiver(waiver_id):
    waiver = PilotWaiver.query.filter_by(waiver_id=waiver_id).first()
    if not waiver or waiver.status != "to_generate":
        return False, "Décharge non trouvée ou statut invalide."

    p = waiver.project
    contact = p.contact_pilote_rel
    if contact:
        waiver.pilot_first_name = contact.prenom
        waiver.pilot_last_name = contact.nom
        waiver.pilot_address = getattr(contact, 'adresse', "")

    if p.production:
        waiver.production_name = p.production.nom
    waiver.project_name = p.nom

    if p.date_debut_tournage and p.date_fin_tournage:
        waiver.shooting_dates = f"{p.date_debut_tournage.strftime('%d/%m/%Y')} au {p.date_fin_tournage.strftime('%d/%m/%Y')}"

    if p.vehicules_a_controler:
        veh_ids = [v.strip()
                   for v in p.vehicules_a_controler.split(",") if v.strip()]
        all_vehicles = get_vehicles()
        vehicle_map = {str(v["id"]): v.get("fields", {}).get(
            "name", f"ID {v['id']}") for v in all_vehicles}
        waiver.vehicles = ", ".join(
            [vehicle_map.get(vid, vid) for vid in veh_ids])
    else:
        waiver.vehicles = ", ".join(
            [cv.vehicle_name for cv in p.checkout_vehicles])

    waiver.status = "to_send"
    waiver.generated_at = datetime.utcnow()
    db.session.commit()
    return True, "Décharge générée avec succès."


def send_pilot_waiver(waiver_id):
    from flask import request
    from utils.mailer import send_waiver_invitation_email

    waiver = PilotWaiver.query.filter_by(waiver_id=waiver_id).first()
    if not waiver:
        return False, "Décharge non trouvée."
    if waiver.status not in ["to_send", "to_sign"]:
        return False, "Statut invalide pour l'envoi."

    contact_pilote = waiver.project.contact_pilote_rel
    if not contact_pilote or not contact_pilote.mail:
        return False, "Le pilote n'a pas d'adresse e-mail renseignée dans le projet."

    if not waiver.signature_token:
        waiver.signature_token = str(uuid.uuid4())

    base_url = request.host_url.rstrip('/')
    signature_link = f"{base_url}/sign/waiver/{waiver.signature_token}"

    success = send_waiver_invitation_email(
        to_email=contact_pilote.mail,
        pilot_name=f"{contact_pilote.prenom} {contact_pilote.nom}",
        project_name=waiver.project.nom,
        signature_link=signature_link
    )

    if not success:
        return False, "Échec de l'envoi de l'e-mail."

    waiver.status = "to_sign"
    waiver.sent_at = datetime.utcnow()
    db.session.commit()
    return True, f"Décharge envoyée au pilote ({contact_pilote.mail})."


def reset_pilot_waiver(waiver_id):
    waiver = PilotWaiver.query.filter_by(waiver_id=waiver_id).first()
    if not waiver:
        return False, "Décharge non trouvée."

    try:
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
    waiver = PilotWaiver.query.filter_by(project_id=project_id).first()
    if not waiver:
        return
    try:
        webhook_url = os.getenv("N8N_WEBHOOK_PILOT_WAIVER")
        if webhook_url:
            trigger_n8n_webhook(webhook_url, method="DELETE",
                                waiver_id=waiver.waiver_id, project_id=waiver.project.project_id)
        _cleanup_waiver_assets("pilot", waiver)
        db.session.delete(waiver)
        db.session.commit()
    except Exception as e:
        logger.error(
            f"❌ Erreur lors de la suppression interne de la décharge pour projet {project_id} : {e}")
        db.session.rollback()
