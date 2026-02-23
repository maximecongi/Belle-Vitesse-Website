"""
Checkin utilities — Airtable data access for vehicle return inspections.
"""

import os
import hmac
import hashlib
import logging
import qrcode
import base64
from flask import current_app
from pathlib import Path
from io import BytesIO
from pyairtable import Table
from dotenv import load_dotenv
from utils.airtable import get_vehicle_by_id
from utils.formatting import format_date_fr

load_dotenv()

AIRTABLE_SECRET_TOKEN = os.getenv("AIRTABLE_SECRET_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")

TABLE_CHECKIN = Table(AIRTABLE_SECRET_TOKEN,
                      AIRTABLE_BASE_ID, "checkin_vehicles")
TABLE_PROJECTS = Table(AIRTABLE_SECRET_TOKEN, AIRTABLE_BASE_ID, "projects")
TABLE_PRODUCTIONS = Table(AIRTABLE_SECRET_TOKEN,
                          AIRTABLE_BASE_ID, "productions")
TABLE_USERS = Table(AIRTABLE_SECRET_TOKEN,
                    AIRTABLE_BASE_ID, "users")

logger = logging.getLogger(__name__)


# ── Cryptographic Seal ──────────────────────────────────────────

def _get_hmac_secret() -> bytes:
    """
    Return the HMAC secret key from environment.
    Must be distinct from Flask's SECRET_KEY.
    Raises at runtime if not set, to fail loudly rather than silently.
    """
    secret = os.getenv("HASH_SECRET_KEY")
    if not secret:
        raise EnvironmentError(
            "HASH_SECRET_KEY is not set. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    return secret.encode("utf-8")


def _build_seal_content(
    inspection_id: str,
    vehicle_id: str,
    km: str,
    signature_data: str,
    signed_at: str,
) -> str:
    """
    Build a canonical, stable string to be hashed for the document seal.
    """
    return f"{inspection_id}|{vehicle_id}|{km}|{signature_data}|{signed_at}"


def compute_document_seal(
    inspection_id: str,
    vehicle_id: str,
    km: str,
    signature_data: str,
    signed_at: str,
) -> str:
    """
    Compute an HMAC-SHA256 seal over critical document fields.
    """
    content = _build_seal_content(
        inspection_id, vehicle_id, km, signature_data, signed_at)
    secret = _get_hmac_secret()
    return hmac.new(secret, content.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_document_seal(
    inspection_id: str,
    vehicle_id: str,
    km: str,
    signature_data: str,
    signed_at: str,
    expected_hash: str,
) -> bool:
    """
    Verify a document seal by recomputing the HMAC and comparing in constant time.
    """
    actual_hash = compute_document_seal(
        inspection_id, vehicle_id, km, signature_data, signed_at
    )
    return hmac.compare_digest(actual_hash, expected_hash)


# ── PDF Binary Hash ──────────────────────────────────────────────

def compute_pdf_hash(pdf_bytes: bytes) -> str:
    """
    Compute a SHA-256 hash of the raw PDF binary.
    """
    return hashlib.sha256(pdf_bytes).hexdigest()


def verify_pdf_hash(pdf_bytes: bytes, expected_hash: str) -> bool:
    """
    Verify that a PDF file matches the hash stored at signing time.
    """
    actual_hash = compute_pdf_hash(pdf_bytes)
    return hmac.compare_digest(actual_hash, expected_hash)


# ── QR Code ──────────────────────────────────────────────────────

def generate_qr_code(data: str) -> str:
    """Generate a QR code and return it as a base64 data URI."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode()}"


# ── PDF ──────────────────────────────────────────────────────────

def generate_checkin_pdf(html_content: str, base_url: str) -> bytes:
    """
    Generate PDF bytes from HTML content using WeasyPrint.
    Loads the external checkin.css stylesheet if present.
    """
    from weasyprint import HTML, CSS
    html = HTML(string=html_content, base_url=base_url)

    css_list = []
    css_path = Path(current_app.static_folder) / "css" / "checkin.css"

    if css_path.exists():
        css_list.append(CSS(filename=str(css_path)))
        logger.info(f"✅ CSS chargé : {css_path}")
    else:
        logger.warning(f"⚠️ CSS non trouvé : {css_path}")

    return html.write_pdf(stylesheets=css_list)


# ── Airtable Helpers ─────────────────────────────────────────────

def get_checkin_record(record_id: str):
    """Fetch a single checkin record from Airtable by record ID."""
    try:
        return TABLE_CHECKIN.get(record_id)
    except Exception as e:
        logger.error(f"❌ get_checkin_record error: {e}")
        return None


def get_checkin_by_inspection_id(inspection_id: str):
    """Fetch a checkin record by its inspection number (N° d'inspection)."""
    try:
        record = TABLE_CHECKIN.first(
            formula=f"{{N° d'inspection}}='{inspection_id}'"
        )
        logger.info(
            f"🔎 Checkin lookup '{inspection_id}' → {'found' if record else 'not found'}"
        )
        return record
    except Exception as e:
        logger.error(f"❌ get_checkin_by_inspection_id error: {e}")
        return None


# ── Vehicle Resolution ────────────────────────────────────────────

def _resolve_vehicle(vehicle_field):
    """Safely resolve Airtable linked vehicle record."""
    if (
        not vehicle_field
        or not isinstance(vehicle_field, list)
        or len(vehicle_field) == 0
    ):
        return None
    try:
        return get_vehicle_by_id(vehicle_field[0])
    except Exception:
        return None


def _extract_vehicle_id(vehicle_field) -> str:
    """Extract the raw Airtable record ID from a linked vehicle field."""
    if (
        not vehicle_field
        or not isinstance(vehicle_field, list)
        or len(vehicle_field) == 0
    ):
        return "—"
    return vehicle_field[0]


def _resolve_controller(controller_field):
    """Resolve linked user record ID from the users table."""
    fallback = {"id": "", "name": "—", "firstname": "", "lastname": ""}
    if (
        not controller_field
        or not isinstance(controller_field, list)
        or len(controller_field) == 0
    ):
        return fallback
    try:
        user = TABLE_USERS.get(controller_field[0])
        f = user.get("fields", {})
        firstname = f.get("firstname", "")
        lastname = f.get("lastname", "")
        return {
            "id": user["id"],
            "name": f"{firstname} {lastname}".strip() or "—",
            "firstname": firstname,
            "lastname": lastname,
            "mail": f.get("mail", ""),
            "role": f.get("role", ""),
        }
    except Exception:
        return fallback


# ── Project Resolution ────────────────────────────────────────────

def _resolve_project(project_field):
    """Fetch the full project record from Airtable given a linked record field."""
    if (
        not project_field
        or not isinstance(project_field, list)
        or len(project_field) == 0
    ):
        return None
    try:
        return TABLE_PROJECTS.get(project_field[0])
    except Exception as e:
        logger.warning(f"⚠️ _resolve_project error: {e}")
        return None


def _extract_project_id(project_field) -> str:
    """Extract the raw Airtable record ID from a linked project field."""
    if (
        not project_field
        or not isinstance(project_field, list)
        or len(project_field) == 0
    ):
        return "—"
    return project_field[0]


def _resolve_production(production_field):
    """Fetch the full production record from Airtable given a linked record field."""
    if (
        not production_field
        or not isinstance(production_field, list)
        or len(production_field) == 0
    ):
        return None
    try:
        return TABLE_PRODUCTIONS.get(production_field[0])
    except Exception as e:
        logger.warning(f"⚠️ _resolve_production error: {e}")
        return None


# ── Data Formatting ───────────────────────────────────────────────

def format_checkin_data(record: dict) -> dict:
    """
    Transform raw Airtable record into a flat dict matching the templates.
    """
    fields = record.get("fields", {})

    def extract_photos(field_value):
        if not field_value:
            return []
        return [
            {"url": att.get("url", ""), "label": att.get("filename", "")}
            for att in field_value
        ]

    def extract_first_photo(field_value):
        if not field_value or len(field_value) == 0:
            return None
        return field_value[0].get("url")

    # ── Resolve vehicle ───────────────────────────────────────────
    vehicle_field = fields.get("Véhicule contrôlé")

    # ── Resolve project + derive its fields ──────────────────────
    project_field = fields.get("Projet")
    project_record = _resolve_project(project_field)
    project_fields = project_record.get("fields", {}) if project_record else {}

    project_name = project_fields.get("Nom", "—")
    departure_date = format_date_fr(project_fields.get("Date de départ", "—"))
    return_date = format_date_fr(project_fields.get("Date de retour", "—"))
    shoot_start = format_date_fr(
        project_fields.get("Date de début de tournage", "—"))
    shoot_end = format_date_fr(
        project_fields.get("Date de fin de tournage", "—"))

    production_record = _resolve_production(project_fields.get("Production"))
    production_name = (
        production_record.get("fields", {}).get("Nom", "—")
        if production_record else "—"
    )

    return {
        "inspection_id":  fields.get("N° d'inspection", "—"),
        "production":     production_name,
        "production_record": production_record,
        "project":        project_name,
        "departure_date": departure_date,
        "return_date":    return_date,
        "shoot_start":    shoot_start,
        "shoot_end":      shoot_end,
        "project_id":     _extract_project_id(project_field),

        "control_status": fields.get("État du contrôle", "—"),
        "control_date":   format_date_fr(fields.get("Date du contrôle", "—")),
        "control_date_raw": fields.get("Date du contrôle", ""),
        "controller":     _resolve_controller(fields.get("Reponsable du contrôle")),

        "vehicle":        _resolve_vehicle(vehicle_field),
        "vehicle_id":     _extract_vehicle_id(vehicle_field),
        "km":             fields.get("Kilométrage retour", ""),
        "battery":        fields.get("Charge de la batterie retour", ""),
        "odometer_photos": extract_photos(fields.get("Photo compteur")),

        "tires":           fields.get("État des pneus", "—"),
        "spare_tire":      fields.get("Roue de secours", "—"),
        "oil":             fields.get("Niveau huile", "—"),
        "coolant":         fields.get("Niveau liquide de refroidissement", "—"),
        "brakes":          fields.get("État des freins", "—"),
        "lights":          fields.get("État éclairage extérieur", "—"),
        "engine_start":    fields.get("Démarrage moteur", "—"),
        "wipers":          fields.get("État des essuie-glaces", "—"),
        "horn":            fields.get("État du klaxon", "—"),
        "safety_triangle": fields.get(
            "Présence Triangle de signalisation et gilet orange", "—"
        ),
        "fire_extinguisher": fields.get("Présence extincteur", "—"),

        "interior_photos": extract_photos(fields.get("Photos intérieur véhicule")),
        "exterior_photos": extract_photos(fields.get("Photos extérieur véhicule")),

        "notes": fields.get("Observations générales", ""),
        "ready": fields.get("Véhicule prêt au retour", "—"),

        "signed_at":  None,
        "signed_ip":  None,
        "hash":       fields.get("Hash", None),
        "pdf_url":    fields.get("PDF scellé"),
    }
