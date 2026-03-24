import os
import re
from datetime import datetime
from pathlib import Path

from flask import current_app


def sanitize_folder_name(name):
    """
    Assainit un nom pour qu'il soit sûr pour un dossier système.
    Supprime les accents, remplace les espaces par des underscores, supprime les caractères spéciaux.
    """
    if not name:
        return "AUTRES"

    import unicodedata
    # Normaliser en NFC et supprimer les accents
    name = unicodedata.normalize('NFKD', name).encode(
        'ascii', 'ignore').decode('ascii')
    # Remplacer les espaces et les underscores multiples par un seul underscore
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'[\s_]+', '_', name)
    return name.strip('_').upper()


def get_project_base_path(project):
    """
    Retourne le chemin de base pour un projet dans le répertoire de sortie :
    output / {année} / {mois} / {nom_production} / {nom_projet} /
    """
    output_base = current_app.config.get(
        "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

    # Utiliser la date de départ du projet si disponible, sinon la date actuelle
    # project est une instance de models.Project
    date = project.departure_date if (
        hasattr(project, 'departure_date') and project.departure_date) else None

    if not date:
        date = datetime.now()

    year = date.strftime("%Y")
    month = date.strftime("%m")

    prod_name = sanitize_folder_name(project.production.name if (
        project.production and project.production.name) else "SANS_PRODUCTION")
    proj_name = sanitize_folder_name(project.name)

    path = Path(output_base) / year / month / prod_name / proj_name
    return path


def get_security_path(project):
    """output / ... / 1_SÉCURITÉ /"""
    return get_project_base_path(project) / "1_SÉCURITÉ"


def get_checkout_path(project):
    """output / ... / 1_SÉCURITÉ / 1_CHECKOUT"""
    return get_security_path(project) / "1_CHECKOUT"


def get_checkout_photos_path(project, inspection_number):
    """output / ... / 1_SÉCURITÉ / 1_CHECKOUT / PHOTOS / {inspection_number}"""
    return get_checkout_path(project) / "PHOTOS" / inspection_number


def get_pilot_waiver_path(project):
    """output / ... / 1_SÉCURITÉ / 2_DÉCHARGE_PILOTE / 1_DÉCHARGE"""
    return get_security_path(project) / "2_DÉCHARGE_PILOTE" / "1_DÉCHARGE"


def get_pilot_attachments_path(project, doc_type):
    """
    doc_type : assurance, licence, identité
    """
    mapping = {
        "insurance": "2_ATTESTATION_ASSURANCE",
        "license": "3_PERMIS_DE_CONDUIRE",
        "identity": "4_CARTE_IDENTITÉ"
    }
    return get_security_path(project) / "2_DÉCHARGE_PILOTE" / mapping.get(doc_type, "AUTRES")


def get_production_waiver_path(project):
    """output / ... / 1_SÉCURITÉ / 3_DÉCHARGE_PRODUCTION / 1_DÉCHARGE"""
    return get_security_path(project) / "3_DÉCHARGE_PRODUCTION" / "1_DÉCHARGE"


def get_production_attachments_path(project, doc_type):
    """
    doc_type : assurance
    """
    mapping = {
        "insurance": "2_ATTESTATION_ASSURANCE"
    }
    return get_security_path(project) / "3_DÉCHARGE_PRODUCTION" / mapping.get(doc_type, "AUTRES")


def get_checkin_path(project):
    """output / ... / 1_SÉCURITÉ / 4_CHECKIN"""
    return get_security_path(project) / "4_CHECKIN"


def get_checkin_photos_path(project, inspection_number):
    """output / ... / 1_SÉCURITÉ / 4_CHECKIN / PHOTOS / {inspection_number}"""
    return get_checkin_path(project) / "PHOTOS" / inspection_number


def ensure_dir(path):
    """S'assure que le répertoire existe."""
    os.makedirs(path, exist_ok=True)
    return path
