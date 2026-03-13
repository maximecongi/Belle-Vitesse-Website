import re
import os
from pathlib import Path
from flask import current_app
from datetime import datetime


def sanitize_folder_name(name):
    """
    Sanitize a name to be safe for a folder.
    Removes accents, replaces spaces with underscores, removes special characters.
    """
    if not name:
        return "AUTRES"

    import unicodedata
    # Normalize to NFC and remove accents
    name = unicodedata.normalize('NFKD', name).encode(
        'ascii', 'ignore').decode('ascii')
    # Replace spaces and multiple underscores with a single underscore
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'[\s_]+', '_', name)
    return name.strip('_').upper()


def get_project_base_path(project):
    """
    Returns the base path for a project in the output directory:
    output / {year} / {month} / {production_name} / {project_name} /
    """
    output_base = current_app.config.get(
        "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

    # Use project start date if available, otherwise current date
    # project is a models.Project instance
    date = project.date_depart if (
        hasattr(project, 'date_depart') and project.date_depart) else None

    if not date:
        date = datetime.now()

    year = date.strftime("%Y")
    month = date.strftime("%m")

    prod_name = sanitize_folder_name(project.production.nom if (
        project.production and project.production.nom) else "SANS_PRODUCTION")
    proj_name = sanitize_folder_name(project.nom)

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
    doc_type: insurance, license, identity
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
    doc_type: insurance
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
    """Ensure directory exists."""
    os.makedirs(path, exist_ok=True)
    return path
