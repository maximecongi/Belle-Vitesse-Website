"""
Checkout utilities — Airtable data access for vehicle inspections.
"""

import os
import logging
import hashlib
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


def generate_qr_code(data):
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


def compute_file_hash(file_bytes):
    """Compute SHA-256 hash of file bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


def generate_checkout_pdf(html_content, base_url):
    """
    Generate PDF bytes from HTML content using WeasyPrint.

    ✅ IMPORTANT: Passe le fichier CSS externe pour formater correctement.
    """
    html = HTML(string=html_content, base_url=base_url)

    css_list = []
    css_path = Path(current_app.static_folder) / "css" / "checkout.css"

    if css_path.exists():
        css_list.append(CSS(filename=str(css_path)))
        logger.info(f"✅ CSS chargé : {css_path}")
    else:
        logger.warning(f"⚠️ CSS non trouvé : {css_path}")

    pdf_bytes = html.write_pdf(stylesheets=css_list)
    return pdf_bytes


def get_checkout_record(record_id):
    """Fetch a single checkout record from Airtable by record ID."""
    try:
        record = TABLE_CHECKOUT.get(record_id)
        return record
    except Exception as e:
        logger.error(f"❌ get_checkout_record error: {e}")
        return None


def get_checkout_by_inspection_id(inspection_id):
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


def format_date_fr(date_str):
    """Convert a date string to French format (ex: 16 février 2026)."""
    if not date_str or date_str == "—":
        return "—"
    try:
        # Airtable format: d/m/yyyy
        if "/" in date_str:
            parts = date_str.split("/")
            day, month, year = int(parts[0]), int(parts[1]), parts[2]
        # ISO format: yyyy-mm-dd
        elif "-" in date_str:
            parts = date_str.split("-")
            year, month, day = parts[0], int(parts[1]), int(parts[2])
        else:
            return date_str
        return f"{day} {MOIS_FR[month]} {year}"
    except (ValueError, IndexError):
        return date_str


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


def format_checkout_data(record):
    """
    Transform raw Airtable record into a flat dict
    matching the checkout.html template variables.
    """
    fields = record.get("fields", {})

    def extract_photos(field_value):
        """Extract photo URLs from Airtable attachment fields."""
        if not field_value:
            return []
        return [
            {
                "url": att.get("url", ""),
                "label": att.get("filename", ""),
            }
            for att in field_value
        ]

    def extract_first_photo(field_value):
        """Extract the URL of the first photo, or None."""
        if not field_value or len(field_value) == 0:
            return None
        return field_value[0].get("url")

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
        "vehicle": _resolve_vehicle(fields.get("Véhicule contrôlé")),
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
        # Signature (filled later or from record)
        "signed_at": None,  # Can be parsed from "Signature" attachment timestamp if needed, but often not accurate
        "signed_ip": None,
        "hash": fields.get("Hash", None),
        "pdf_url": fields.get("PDF scellé"),
    }
