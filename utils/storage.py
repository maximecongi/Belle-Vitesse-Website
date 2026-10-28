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

    if not project:
        return Path(output_base) / "SANS_PROJET"

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
    """output / ... / 1_SÉCURITÉ / 1_CHECKOUTS"""
    return get_security_path(project) / "1_CHECKOUTS"


def get_checkout_photos_path(project, inspection_number):
    """output / ... / 1_SÉCURITÉ / 1_CHECKOUTS / PHOTOS / {inspection_number}"""
    return get_checkout_path(project) / "PHOTOS" / inspection_number


def get_cgl_path(project):
    """output / ... / 1_SÉCURITÉ / 0_CGL / 1_CGL"""
    return get_security_path(project) / "0_CGL" / "1_CGL"


def get_cgl_attachments_path(project, doc_type="insurance"):
    """output / ... / 1_SÉCURITÉ / 0_CGL / 2_ATTESTATION_ASSURANCE"""
    return get_security_path(project) / "0_CGL" / "2_ATTESTATION_ASSURANCE"


def get_safety_rules_path(project):
    """output / ... / 1_SÉCURITÉ / 2_RÈGLES_SÉCURITÉ"""
    return get_security_path(project) / "2_RÈGLES_SÉCURITÉ"


def get_pilot_waiver_path(project):
    """output / ... / 1_SÉCURITÉ / 4_ATTESTATIONS_PILOTES"""
    return get_security_path(project) / "4_ATTESTATIONS_PILOTES"


def get_checkin_path(project):
    """output / ... / 1_SÉCURITÉ / 5_CHECKINS"""
    return get_security_path(project) / "5_CHECKINS"


def get_checkin_photos_path(project, inspection_number):
    """output / ... / 1_SÉCURITÉ / 5_CHECKINS / PHOTOS / {inspection_number}"""
    return get_checkin_path(project) / "PHOTOS" / inspection_number


def get_incident_path(project):
    """output / ... / 1_SÉCURITÉ / 5_INCIDENTS"""
    if project:
        return get_security_path(project) / "5_INCIDENTS"
    output_base = current_app.config.get(
        "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))
    now = datetime.now()
    return Path(output_base) / now.strftime("%Y") / now.strftime("%m") / "INCIDENTS"


def get_incident_photos_path(project, incident_number):
    """output / ... / 1_SÉCURITÉ / 5_INCIDENTS / PHOTOS / {incident_number}"""
    return get_incident_path(project) / "PHOTOS" / incident_number


def ensure_dir(path):
    """S'assure que le répertoire existe."""
    os.makedirs(path, exist_ok=True)
    return path
