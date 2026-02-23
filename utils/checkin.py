"""
Checkin utilities — PDF generation, sealing and verification logic.
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
from dotenv import load_dotenv
from weasyprint import HTML, CSS

load_dotenv()

logger = logging.getLogger(__name__)


# ── Cryptographic Seal ──────────────────────────────────────────

def _get_hmac_secret() -> bytes:
    """
    Return the HMAC secret key from environment.
    Must be distinct from Flask's SECRET_KEY.
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
    """
    html = HTML(string=html_content, base_url=base_url)

    css_list = []
    css_path = Path(current_app.static_folder) / "css" / "checkin.css"

    if css_path.exists():
        css_list.append(CSS(filename=str(css_path)))
        logger.info(f"✅ CSS chargé : {css_path}")
    else:
        logger.warning(f"⚠️ CSS non trouvé : {css_path}")

    return html.write_pdf(stylesheets=css_list)
