"""
Utilitaires partagés pour les inspections (check-in/check-out) — PDF, scellement et codes QR.
"""

import base64
import hashlib
import hmac
import logging
import os
import unicodedata
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urlparse

import qrcode
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Scellement HMAC (Sealing) ────────────────────────────────────


def _get_hmac_secret() -> bytes:
    """Récupère la clé secrète HMAC depuis l'environnement."""
    secret = os.getenv("HASH_SECRET_KEY")
    if not secret:
        # Fallback to SECRET_KEY for dev, though distinct is better
        secret = os.getenv("SECRET_KEY", "fallback_secret_for_dev_only")
    return secret.encode("utf-8")


def compute_hmac_seal(prefix, *args) -> str:
    """
    Calcule un sceau cryptographique HMAC-SHA256 pour tout document.
    Args:
        prefix (str) : Ex: 'INSPECTION', 'WAIVER', 'WAIVER_PROD'
        *args : Nombre variable de chaînes formant le contenu du sceau.
    """
    # Join prefix and all args with a pipe
    content_parts = [prefix] + [str(arg) for arg in args]
    content = "|".join(content_parts)

    secret = _get_hmac_secret()
    return hmac.new(secret, content.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_hmac_seal(expected_hash, prefix, *args) -> bool:
    """
    Vérifie l'intégrité d'un sceau cryptographique HMAC-SHA256.
    """
    actual_hash = compute_hmac_seal(prefix, *args)
    return hmac.compare_digest(actual_hash, expected_hash)


# Alias de compatibilité descendante pour les inspections
def compute_document_seal(inspection_id, vehicle_id, signature_data, signed_at):
    return compute_hmac_seal("INSPECTION", inspection_id, vehicle_id, signature_data, signed_at)


def verify_document_seal(inspection_id, vehicle_id, signature_data, signed_at, expected_hash):
    return verify_hmac_seal(expected_hash, "INSPECTION", inspection_id, vehicle_id, signature_data, signed_at)


# ── Empreinte Binaire PDF (Hash) ─────────────────────────────────

def compute_pdf_hash(pdf_bytes: bytes) -> str:
    """Calcule une empreinte SHA-256 du binaire brut du PDF."""
    return hashlib.sha256(pdf_bytes).hexdigest()


def verify_pdf_hash(pdf_bytes: bytes, expected_hash: str) -> bool:
    """Vérifie qu'un fichier PDF correspond à l'empreinte enregistrée."""
    actual_hash = compute_pdf_hash(pdf_bytes)
    return hmac.compare_digest(actual_hash, expected_hash)


# ── QR Code ──────────────────────────────────────────────────────

def generate_qr_code(data: str) -> str:
    """Génère un code QR et le retourne sous forme d'URI de données base64."""
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


# ── Jetons d'Accès PDF ───────────────────────────────────────────

def generate_pdf_access_token(filename: str) -> str:
    """Génère un jeton d'accès signé HMAC, limité dans le temps, pour un nom de fichier PDF."""
    secret = _get_hmac_secret()
    now_minutes = int(datetime.now(timezone.utc).timestamp() // 60)
    payload = f"{filename}:{now_minutes}".encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def validate_pdf_access_token(filename: str, provided_token: str) -> bool:
    """Valide un jeton d'accès limité dans le temps pour un PDF."""
    if not provided_token:
        return False
    secret = _get_hmac_secret()
    ttl = int(os.getenv("PDF_ACCESS_TOKEN_TTL_MINUTES", "60"))
    now_minutes = int(datetime.now(timezone.utc).timestamp() // 60)

    for delta in range(ttl + 1):
        ts = now_minutes - delta
        payload = f"{filename}:{ts}".encode("utf-8")
        expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, provided_token):
            return True
    return False


# Compatibility aliases
def generate_waiver_pdf_access_token(filename):
    return generate_pdf_access_token(filename)


def validate_waiver_pdf_access_token(filename, token):
    return validate_pdf_access_token(filename, token)


# ── WeasyPrint Fetcher ──────────────────────────────────────────

def make_url_fetcher(app):
    """Générateur de fetcher d'URL personnalisé pour WeasyPrint (gestion des préfixes /static/ et /files/)."""
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


# ── Génération de PDF ────────────────────────────────────────────

def render_pdf_from_template(html_content: str, base_url: str, stylesheets: list[str] = None) -> bytes:
    """
    Générateur de PDF générique utilisant WeasyPrint.
    Args:
        html_content (str) : Contenu HTML rendu.
        base_url (str) : URL de base pour les ressources.
        stylesheets (list[str]) : Liste des fichiers statiques CSS (ex: ['css/styles.css']).
    """
    from flask import current_app
    from weasyprint import CSS, HTML
    fetcher = make_url_fetcher(current_app)
    html = HTML(string=html_content, base_url=base_url, url_fetcher=fetcher)

    css_list = []
    if stylesheets:
        static_path = Path(current_app.static_folder)
        for ss in stylesheets:
            css_file = static_path / ss.lstrip("/")
            if css_file.exists():
                css_list.append(CSS(filename=str(css_file), url_fetcher=fetcher))

    return html.write_pdf(stylesheets=css_list)


# Backward compatibility alias
def generate_inspection_pdf(html_content: str, base_url: str, mode: str) -> bytes:
    """Legacy helper for inspections."""
    stylesheets = ["css/styles.css", f"css/{mode}.css"]
    return render_pdf_from_template(html_content, base_url, stylesheets)
