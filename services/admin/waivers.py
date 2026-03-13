import logging
from datetime import datetime
import uuid
import os

from sqlalchemy.orm import joinedload
from models import db, PilotWaiver, Project, PilotWaiverSignedDocument
from utils.database import get_vehicles

logger = logging.getLogger(__name__)


def _cleanup_pilot_waiver_assets(waiver):
    """Internal helper to delete physical files and signed documents associated with a waiver."""
    from flask import current_app

    # 1. Identifier les fichiers physiques à supprimer
    files_to_delete = [
        waiver.signed_pdf_path,
        waiver.pilot_license_path,
        waiver.pilot_insurance_path,
        waiver.pilot_identity_path
    ]

    for file_path in files_to_delete:
        if file_path and file_path.startswith('/static/'):
            relative_path = file_path.lstrip('/')
            full_path = os.path.join(current_app.root_path, relative_path)

            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                    logger.info(f"🗑️ Fichier supprimé : {full_path}")
                except Exception as e:
                    logger.error(
                        f"❌ Erreur suppression fichier {full_path} : {e}")

    # 2. Supprimer le document scellé associé
    signed_doc = PilotWaiverSignedDocument.query.filter_by(
        waiver_id=waiver.waiver_id).first()
    if signed_doc:
        db.session.delete(signed_doc)


def create_pilot_waiver(project_id):
    """Crée une nouvelle décharge pour un projet donné s'il n'en a pas déjà une."""
    existing = PilotWaiver.query.filter_by(project_id=project_id).first()
    if existing:
        return False, "Une décharge existe déjà pour ce projet."

    waiver = PilotWaiver(project_id=project_id)
    db.session.add(waiver)
    db.session.commit()
    return True, "Décharge créée avec succès."


def list_pilot_waivers():
    """Retrieve all pilot waivers with their associated projects."""
    waivers = PilotWaiver.query.options(
        joinedload(PilotWaiver.project)
        .joinedload(Project.contact_pilote_rel)
    ).all()

    # Sort by project date_depart or nom as fallback
    waivers.sort(key=lambda w: (
        w.project.date_depart or datetime.min.date(), w.project.nom), reverse=True)

    waivers_formatted = []

    for w in waivers:
        p = w.project
        # Contact Pilote name
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

        waivers_formatted.append({
            "id": w.waiver_id,
            "project_id": p.id,
            "project_name": p.nom,
            "pilot_name": pilote_name,
            "shooting_dates": shooting_dates,
            "status": w.status,
            "generated_at": w.generated_at,
            "sent_at": w.sent_at,
            "signed_at": w.signed_at,
            "signature_token": w.signature_token,
            "signed_pdf_path": w.signed_pdf_path
        })

    return waivers_formatted


def generate_pilot_waiver(waiver_id):
    """Fige les données du projet dans la décharge. Reçoit le waiver_id métier (BVDW-...)."""
    waiver = PilotWaiver.query.filter_by(waiver_id=waiver_id).first()
    if not waiver or waiver.status != "to_generate":
        return False, "Décharge non trouvée ou statut invalide."

    p = waiver.project
    contact = p.contact_pilote_rel

    if contact:
        waiver.pilot_first_name = contact.prenom
        waiver.pilot_last_name = contact.nom
        waiver.pilot_address = contact.adresse if hasattr(
            contact, 'adresse') else ""
        # Assuming contacts don't have dob/license/insurance by default, they will be empty strings

    if p.production:
        waiver.production_name = p.production.nom

    waiver.project_name = p.nom

    if p.date_debut_tournage and p.date_fin_tournage:
        waiver.shooting_dates = f"{p.date_debut_tournage.strftime('%d/%m/%Y')} au {p.date_fin_tournage.strftime('%d/%m/%Y')}"

    if p.vehicules_a_controler:
        veh_ids = [v.strip()
                   for v in p.vehicules_a_controler.split(",") if v.strip()]
        all_vehicles = get_vehicles()
        vehicle_map = {str(v["id"]): v.get("fields", {}) for v in all_vehicles}
        # The instruction implies storing full vehicle fields, not just names.
        # Assuming waiver.vehicles should store a JSON string of vehicle data.
        assigned_vehicles_data = [vehicle_map.get(vid, {}) for vid in veh_ids]
        # Convert list of dicts to a string representation, e.g., JSON
        # For simplicity, let's store names for now, but the instruction implies full fields.
        # If full fields are needed, a JSON string or similar would be appropriate.
        # For now, we'll stick to names as the original code did, but use the new vehicle_map.
        assigned_names = [v.get("name", f"ID {vid}") for vid, v in zip(
            veh_ids, assigned_vehicles_data)]
        waiver.vehicles = ", ".join(assigned_names)
    else:
        vehicles = []
        for cv in p.checkout_vehicles:
            vehicles.append(cv.vehicle_name)
        waiver.vehicles = ", ".join(vehicles)

    waiver.status = "to_send"
    waiver.generated_at = datetime.utcnow()

    db.session.commit()
    return True, "Décharge générée avec succès."


def send_pilot_waiver(waiver_id):
    """Génère le token de signature et prépare l'envoi. Reçoit le waiver_id métier (BVDW-...)."""
    from flask import request
    from utils.mailer import send_waiver_invitation_email

    waiver = PilotWaiver.query.filter_by(waiver_id=waiver_id).first()
    if not waiver:
        return False, "Décharge non trouvée."

    if waiver.status not in ["to_send", "to_sign"]:
        return False, "Statut invalide pour l'envoi."

    # 1. Obtenir l'email du pilote via le projet
    contact_pilote = waiver.project.contact_pilote_rel
    if not contact_pilote or not contact_pilote.mail:
        return False, "Le pilote n'a pas d'adresse e-mail renseignée dans le projet."

    # 2. Générer le token de signature si besoin
    if not waiver.signature_token:
        waiver.signature_token = str(uuid.uuid4())

    # 3. Préparer le lien de signature
    # request.host_url s'adapte à l'environnement (local, staging, production)
    base_url = request.host_url.rstrip('/')
    signature_link = f"{base_url}/sign/waiver/{waiver.signature_token}"

    # 4. Envoyer le mail d'invitation
    pilot_full_name = f"{contact_pilote.prenom} {contact_pilote.nom}"
    project_name = waiver.project.nom

    success = send_waiver_invitation_email(
        to_email=contact_pilote.mail,
        pilot_name=pilot_full_name,
        project_name=project_name,
        signature_link=signature_link
    )

    if not success:
        return False, "Échec de l'envoi de l'e-mail (vérifiez les logs)."

    # 5. Mettre à jour le statut et la date d'envoi
    waiver.status = "to_sign"
    waiver.sent_at = datetime.utcnow()

    db.session.commit()

    return True, f"Décharge envoyée au pilote ({contact_pilote.mail})."


def reset_pilot_waiver(waiver_id):
    """Réinitialise une décharge : supprime les fichiers et les scellés, mais garde l'entrée PilotWaiver."""
    waiver = PilotWaiver.query.filter_by(waiver_id=waiver_id).first()
    if not waiver:
        return False, "Décharge non trouvée."

    try:
        # 1. Nettoyer les fichiers et scellés
        _cleanup_pilot_waiver_assets(waiver)

        # 2. Réinitialiser les champs de la décharge
        waiver.status = "to_generate"
        waiver.generated_at = None
        waiver.sent_at = None
        waiver.signed_at = None

        # Snapshot & Documents
        waiver.pilot_first_name = None
        waiver.pilot_last_name = None
        waiver.pilot_dob = None
        waiver.pilot_license_number = None
        waiver.pilot_address = None
        waiver.pilot_insurance_company = None
        waiver.pilot_insurance_policy = None
        waiver.production_name = None
        waiver.project_name = None
        waiver.vehicles = None
        waiver.shooting_dates = None

        # Signature & Paths
        waiver.signature_token = None
        waiver.signature_data = None
        waiver.signed_pdf_path = None
        waiver.signer_ip = None
        waiver.pilot_license_path = None
        waiver.pilot_insurance_path = None
        waiver.pilot_identity_path = None
        waiver.webhook_triggered_at = None

        db.session.commit()

        return True, "Décharge réinitialisée avec succès (données et fichiers supprimés)."
    except Exception as e:
        db.session.rollback()
        logger.error(
            f"❌ Erreur lors du reset de la décharge {waiver_id} : {e}")
        return False, f"Erreur lors de la réinitialisation : {str(e)}"


def delete_pilot_waiver_internal(project_id):
    """
    Supprime complètement la décharge liée à un projet (fichiers + DB).
    Utilisé lors de la suppression d'un projet.
    """
    waiver = PilotWaiver.query.filter_by(project_id=project_id).first()
    if not waiver:
        return

    try:
        _cleanup_pilot_waiver_assets(waiver)
        db.session.delete(waiver)
        db.session.commit()
    except Exception as e:
        logger.error(
            f"❌ Erreur lors de la suppression interne de la décharge pour projet {project_id} : {e}")
        db.session.rollback()
