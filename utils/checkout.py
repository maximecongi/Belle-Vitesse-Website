"""
Checkout utilities — PDF generation, sealing and verification logic.
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

def make_url_fetcher(app):
    from weasyprint import default_url_fetcher
    from urllib.parse import urlparse, unquote

    import unicodedata

    def fetcher(url):
        parsed = urlparse(url)
        path = parsed.path

        # Resolve /static/ to local filesystem
        if path.startswith("/static/"):
            rel_path = path[len("/static/"):].lstrip("/")
            full_path = Path(app.static_folder) / rel_path
            if full_path.exists():
                return default_url_fetcher(full_path.as_uri())

        # Resolve /files/ to local filesystem
        if path.startswith("/files/"):
            rel_path = unquote(path[len("/files/"):].lstrip("/"))

            # Try OUTPUT_FOLDER (New hierarchical storage)
            output_base = app.config.get("OUTPUT_FOLDER")
            if output_base:
                full_path = Path(output_base) / rel_path

                # MacOS Unicode Normalization handling (NFC/NFD)
                if not full_path.exists():
                    nfd_path = unicodedata.normalize('NFD', str(full_path))
                    if os.path.exists(nfd_path):
                        full_path = Path(nfd_path)

                if full_path.exists():
                    logger.info(f"✅ Fetcher found file in OUTPUT: {full_path}")
                    return default_url_fetcher(full_path.as_uri())
                else:
                    logger.warning(
                        f"❌ Fetcher NOT found in OUTPUT: {full_path}")

        return default_url_fetcher(url)
    return fetcher


def generate_checkout_pdf(html_content: str, base_url: str) -> bytes:
    """
    Generate PDF bytes from HTML content using WeasyPrint.
    """
    fetcher = make_url_fetcher(current_app)
    html = HTML(string=html_content, base_url=base_url, url_fetcher=fetcher)

    css_list = []
    static_path = Path(current_app.static_folder)

    # 1. Base styles (variables, reset)
    styles_css = static_path / "css" / "styles.css"
    if styles_css.exists():
        css_list.append(CSS(filename=str(styles_css), url_fetcher=fetcher))

    # 2. Specific checkout styles
    checkout_css = static_path / "css" / "checkout.css"
    if checkout_css.exists():
        css_list.append(CSS(filename=str(checkout_css), url_fetcher=fetcher))
        logger.info(f"✅ CSS chargé : {checkout_css}")
    else:
        logger.warning(f"⚠️ CSS non trouvé : {checkout_css}")

    return html.write_pdf(stylesheets=css_list)
