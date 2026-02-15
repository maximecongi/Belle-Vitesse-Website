"""
Checkout utilities — Airtable data access for vehicle inspections.
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
from weasyprint import HTML, CSS
from utils.airtable import get_vehicle_by_id

load_dotenv()

AIRTABLE_SECRET_TOKEN = os.getenv("AIRTABLE_SECRET_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")

TABLE_CHECKOUT = Table(AIRTABLE_SECRET_TOKEN, AIRTABLE_BASE_ID, "checkout_vehicles")

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
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
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

    ⚠️  We use explicit, scalar fields only — never a dict like data['vehicle']
    whose str() representation could vary across Python versions or dict ordering.
    vehicle_id must be the Airtable record ID (stable string), not the full vehicle dict.
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

    Unlike a bare SHA-256, this seal cannot be forged without the server secret.
    Returns a hex digest string.
    """
    content = _build_seal_content(
        inspection_id, vehicle_id, km, signature_data, signed_at
    )
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

    Uses hmac.compare_digest to prevent timing attacks.
    Returns True only if the seal is valid.
    """
    actual_hash = compute_document_seal(
        inspection_id, vehicle_id, km, signature_data, signed_at
    )
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


def generate_checkout_pdf(html_content: str, base_url: str) -> bytes:
    """
    Generate PDF bytes from HTML content using WeasyPrint.
    Loads the external checkout.css stylesheet if present.
    """
    html = HTML(string=html_content, base_url=base_url)

    css_list = []
    css_path = Path(current_app.static_folder) / "css" / "checkout.css"

    if css_path.exists():
        css_list.append(CSS(filename=str(css_path)))
        logger.info(f"✅ CSS chargé : {css_path}")
    else:
        logger.warning(f"⚠️ CSS non trouvé : {css_path}")

    return html.write_pdf(stylesheets=css_list)


# ── Airtable Helpers ─────────────────────────────────────────────


def get_checkout_record(record_id: str):
    """Fetch a single checkout record from Airtable by record ID."""
    try:
        return TABLE_CHECKOUT.get(record_id)
    except Exception as e:
        logger.error(f"❌ get_checkout_record error: {e}")
        return None


def get_checkout_by_inspection_id(inspection_id: str):
    """Fetch a checkout record by its inspection number (N° d'inspection)."""
    try:
        record = TABLE_CHECKOUT.first(formula=f"{{N° d'inspection}}='{inspection_id}'")
        logger.info(
            f"🔎 Checkout lookup '{inspection_id}' → {'found' if record else 'not found'}"
        )
        return record
    except Exception as e:
        logger.error(f"❌ get_checkout_by_inspection_id error: {e}")
        return None


# ── Date Formatting ───────────────────────────────────────────────

MOIS_FR = [
    "",
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]


def format_date_fr(date_str: str) -> str:
    """Convert a date string to French format (ex: 16 février 2026)."""
    if not date_str or date_str == "—":
        return "—"
    try:
        if "/" in date_str:
            parts = date_str.split("/")
            day, month, year = int(parts[0]), int(parts[1]), parts[2]
        elif "-" in date_str:
            parts = date_str.split("-")
            year, month, day = parts[0], int(parts[1]), int(parts[2])
        else:
            return date_str
        return f"{day} {MOIS_FR[month]} {year}"
    except (ValueError, IndexError):
        return date_str


# ── Vehicle Resolution ────────────────────────────────────────────


def _resolve_vehicle(vehicle_field):
    """
    Safely resolve Airtable linked vehicle record.
    Returns the full vehicle record dict, or None.
    """
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
    """
    Extract the raw Airtable record ID from a linked vehicle field.
    Returns the ID string (e.g. 'recXXXXXXXXXXXXXX') or '—'.

    ⚠️  Use this — not str(data['vehicle']) — when building the document seal,
    to ensure a stable, scalar representation.
    """
    if (
        not vehicle_field
        or not isinstance(vehicle_field, list)
        or len(vehicle_field) == 0
    ):
        return "—"
    return vehicle_field[0]


# ── Data Formatting ───────────────────────────────────────────────


def format_checkout_data(record: dict) -> dict:
    """
    Transform raw Airtable record into a flat dict
    matching the checkout.html template variables.

    Adds 'vehicle_id' (stable scalar for seal computation) alongside
    'vehicle' (full resolved dict for display).
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

    vehicle_field = fields.get("Véhicule contrôlé")

    return {
        "inspection_id": fields.get("N° d'inspection", "—"),
        "production": fields.get("Production", "—"),
        "project": fields.get("Projet", "—"),
        "departure_date": format_date_fr(fields.get("Date de départ", "—")),
        "shoot_start": format_date_fr(fields.get("Date de début de tournage", "—")),
        "shoot_end": format_date_fr(fields.get("Date de fin de tournage", "—")),
        "control_status": fields.get("État du contrôle", "—"),
        "control_date": format_date_fr(fields.get("Date du contrôle", "—")),
        "controller": fields.get("Reponsable du contrôle", "—"),
        # Full vehicle record for display in templates
        "vehicle": _resolve_vehicle(vehicle_field),
        # Stable scalar ID for seal computation — never use str(vehicle) for hashing
        "vehicle_id": _extract_vehicle_id(vehicle_field),
        "km": fields.get("Kilométrage départ", ""),
        "battery": fields.get("Charge de la batterie départ", ""),
        "odometer_photo": extract_first_photo(fields.get("Photo compteur")),
        # Inspection items
        "tires": fields.get("État des pneus", "—"),
        "spare_tire": fields.get("Roue de secours", "—"),
        "oil": fields.get("Niveau huile", "—"),
        "coolant": fields.get("Niveau liquide de refroidissement", "—"),
        "brakes": fields.get("État des freins", "—"),
        "lights": fields.get("État éclairage extérieur", "—"),
        "engine_start": fields.get("Démarrage moteur", "—"),
        "wipers": fields.get("État des essuie-glaces", "—"),
        "horn": fields.get("État du klaxon", "—"),
        "safety_triangle": fields.get(
            "Présence Triangle de signalisation et gilet orange", "—"
        ),
        "fire_extinguisher": fields.get("Présence extincteur", "—"),
        # Photos
        "interior_photos": extract_photos(fields.get("Photos intérieur véhicule")),
        "exterior_photos": extract_photos(fields.get("Photos extérieur véhicule")),
        # Notes & verdict
        "notes": fields.get("Observations générales", ""),
        "ready": fields.get("Véhicule prêt au départ", "—"),
        # Signature metadata (populated later in routes)
        "signed_at": None,
        "signed_ip": None,
        "hash": fields.get("Hash", None),
        "pdf_url": fields.get("PDF scellé"),
    }
