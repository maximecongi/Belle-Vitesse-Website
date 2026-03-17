"""
Shared utilities for inspections (check-in/check-out) — PDF, sealing and QR codes.
"""

import os
import hmac
import hashlib
import logging
import qrcode
import base64
import unicodedata
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse, unquote

from flask import current_app
from weasyprint import HTML, CSS
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Cryptographic Seal ──────────────────────────────────────────


def _get_hmac_secret() -> bytes:
    """Return the HMAC secret key from environment."""
    secret = os.getenv("HASH_SECRET_KEY")
    if not secret:
        raise EnvironmentError("HASH_SECRET_KEY is not set.")
    return secret.encode("utf-8")


def compute_document_seal(
    inspection_id: str,
    vehicle_id: str,
    signature_data: str,
    signed_at: str,
) -> str:
    """
    Compute an HMAC-SHA256 seal over critical document fields.
    Removed 'km' field as it is no longer used.
    """
    content = f"{inspection_id}|{vehicle_id}|{signature_data}|{signed_at}"
    secret = _get_hmac_secret()
    return hmac.new(secret, content.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_document_seal(
    inspection_id: str,
    vehicle_id: str,
    signature_data: str,
    signed_at: str,
    expected_hash: str,
) -> bool:
    """Verify a document seal by recomputing the HMAC."""
    actual_hash = compute_document_seal(
        inspection_id, vehicle_id, signature_data, signed_at
    )
    return hmac.compare_digest(actual_hash, expected_hash)


# ── PDF Binary Hash ──────────────────────────────────────────────

def compute_pdf_hash(pdf_bytes: bytes) -> str:
    """Compute a SHA-256 hash of the raw PDF binary."""
    return hashlib.sha256(pdf_bytes).hexdigest()


def verify_pdf_hash(pdf_bytes: bytes, expected_hash: str) -> bool:
    """Verify that a PDF file matches the stored hash."""
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


# ── WeasyPrint Fetcher ──────────────────────────────────────────

def make_url_fetcher(app):
    from weasyprint import default_url_fetcher

    def fetcher(url):
        parsed = urlparse(url)
        path = parsed.path

        # Resolve /static/
        if path.startswith("/static/"):
            rel_path = path[len("/static/"):].lstrip("/")
            full_path = Path(app.static_folder) / rel_path
            if full_path.exists():
                return default_url_fetcher(full_path.as_uri())

        # Resolve /files/
        if path.startswith("/files/"):
            rel_path = unquote(path[len("/files/"):].lstrip("/"))
            output_base = app.config.get("OUTPUT_FOLDER")
            if output_base:
                full_path = Path(output_base) / rel_path
                # MacOS Unicode Normalization
                if not full_path.exists():
                    nfd_path = unicodedata.normalize('NFD', str(full_path))
                    if os.path.exists(nfd_path):
                        full_path = Path(nfd_path)

                if full_path.exists():
                    return default_url_fetcher(full_path.as_uri())

        return default_url_fetcher(url)
    return fetcher


# ── PDF Generation ──────────────────────────────────────────────

def generate_inspection_pdf(html_content: str, base_url: str, mode: str) -> bytes:
    """
    Generate PDF bytes for either 'checkin' or 'checkout'.
    """
    fetcher = make_url_fetcher(current_app)
    html = HTML(string=html_content, base_url=base_url, url_fetcher=fetcher)

    css_list = []
    static_path = Path(current_app.static_folder)

    # 1. Base styles
    styles_css = static_path / "css" / "styles.css"
    if styles_css.exists():
        css_list.append(CSS(filename=str(styles_css), url_fetcher=fetcher))

    # 2. Specific styles
    spec_css = static_path / "css" / f"{mode}.css"
    if spec_css.exists():
        css_list.append(CSS(filename=str(spec_css), url_fetcher=fetcher))

    return html.write_pdf(stylesheets=css_list)
