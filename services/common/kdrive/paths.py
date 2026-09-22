import re
from datetime import date, datetime, timezone
from services.common.kdrive.config import KDRIVE_BASE_PATH

PROJECT_SUBFOLDERS = [
    "1_DEVIS",
    "2_FACTURES",
    "3_LISTES",
    "4_SÉCURITÉ",
    "5_BTS",
    "6_INCIDENTS",
]

DOC_FOLDERS = {
    "checkout": "4_SÉCURITÉ/1_CHECKOUT",
    "pilot_waiver": "4_SÉCURITÉ/2_DÉCHARGE_PILOTE",
    "production_waiver": "4_SÉCURITÉ/3_DÉCHARGE_PRODUCTION",
    "checkin": "4_SÉCURITÉ/4_CHECKIN",
    "incident": "6_INCIDENTS",
}

ROLE_SUBFOLDERS = {
    ("pilot_waiver", "pdf"): "1_DÉCHARGE",
    ("pilot_waiver", "insurance"): "2_ATTESTATION_ASSURANCE",
    ("pilot_waiver", "license"): "3_PERMIS_DE_CONDUIRE",
    ("pilot_waiver", "identity"): "4_CARTE_IDENTITÉ",
    ("production_waiver", "pdf"): "1_DÉCHARGE",
    ("production_waiver", "insurance"): "2_ATTESTATION_ASSURANCE",
    ("checkout", "photo"): "PHOTOS",
    ("checkout", "pdf"): "",
    ("checkin", "photo"): "PHOTOS",
    ("checkin", "pdf"): "",
    ("incident", "photo"): "PHOTOS",
    ("incident", "document"): "DOCUMENTS",
    ("incident", "pdf"): "",
}


def clean_segment(value, label: str = "segment") -> str:
    """
    Nettoie un segment de chemin :
    - Remplace les slashes / et \\ par des espaces (conforme aux spécifications de nommage)
    - Supprime les espaces multiples et les espaces en bordure
    - Refuse les segments vides ou dangereux (., ..)
    """
    if value is None:
        raise ValueError(f"Le segment '{label}' ne peut pas être vide ou None.")

    raw = str(value)
    # Remplacement des slashes par des espaces
    sanitized = re.sub(r"[/\\]", " ", raw)
    # Élimination des caractères de contrôle ou retours à la ligne
    sanitized = re.sub(r"[\r\n\t]", " ", sanitized)
    # Compression des espaces
    sanitized = re.sub(r"\s+", " ", sanitized).strip()

    if not sanitized or sanitized in {".", "..", "—", "-"}:
        raise ValueError(f"Segment invalide pour '{label}': '{value}'")

    return sanitized


def format_year(val) -> str:
    """
    Extrait ou formate une année sur 4 chiffres (ex: '2026').
    En cas de valeur absente ou invalide, utilise l'année UTC courante pour éviter les dossiers '—'.
    """
    if isinstance(val, (datetime, date)):
        return val.strftime("%Y")

    if val:
        s = str(val).strip()
        match = re.search(r"\b(20\d{2}|19\d{2})\b", s)
        if match:
            return match.group(1)

    return datetime.now(timezone.utc).strftime("%Y")


def format_month(val) -> str:
    """
    Extrait ou formate un mois sur 2 chiffres avec zéro initial (ex: '09').
    En cas de valeur absente ou invalide, utilise le mois UTC courant.
    """
    if isinstance(val, (datetime, date)):
        return val.strftime("%m")

    if val is not None:
        s = str(val).strip()
        if s.isdigit():
            m = int(s)
            if 1 <= m <= 12:
                return f"{m:02d}"

    return datetime.now(timezone.utc).strftime("%m")


def format_name(value, label: str) -> str:
    """Nettoie une chaîne et la passe en majuscules (conforme aux dossiers kDrive)."""
    return clean_segment(value, label).upper()


def get_project_date_reference(project) -> datetime:
    """Détermine la date de référence d'un projet pour le classement par année/mois."""
    if project:
        if getattr(project, "departure_date", None):
            return project.departure_date
        if getattr(project, "shoot_start_date", None):
            return project.shoot_start_date

    return datetime.now(timezone.utc)


def build_project_rel_path(year, month, production_name: str, project_name: str) -> str:
    """
    Construit le chemin relatif du parent du projet :
    ex: '2026/09/ACADEMY FILMS/PROJETS TEST'
    """
    y = format_year(year)
    m = format_month(month)
    prod = format_name(production_name, "production")
    proj = format_name(project_name, "project")
    return f"{y}/{m}/{prod}/{proj}"


def build_project_path(project) -> str:
    """
    Construit le chemin kDrive complet d'un projet :
    {KDRIVE_BASE_PATH}/<YEAR>/<MONTH>/<PRODUCTION>/<PROJET>/<PROJECT_ID>
    """
    date_ref = get_project_date_reference(project)
    prod_name = project.production.name if (project and getattr(project, "production", None)) else "SANS_PRODUCTION"
    proj_name = project.name if project else "PROJET"
    proj_id = clean_segment(project.project_id if project else "BVPR", "project_id")

    rel = build_project_rel_path(date_ref, date_ref, prod_name, proj_name)
    return f"{KDRIVE_BASE_PATH}/{rel}/{proj_id}"


def build_document_directory_path(project, entity_type: str, entity_id: str, role: str = None) -> str:
    """
    Construit le chemin kDrive relatif au projet pour un document ou une pièce jointe.
    """
    if entity_type not in DOC_FOLDERS:
        raise ValueError(f"Type d'entité inconnu pour kDrive : {entity_type}")

    doc_base = DOC_FOLDERS[entity_type]
    clean_id = clean_segment(entity_id, "entity_id")

    subfolder = ROLE_SUBFOLDERS.get((entity_type, role), "") if role else ""
    parts = [doc_base, clean_id]
    if subfolder:
        parts.append(subfolder)

    return "/".join(parts)
