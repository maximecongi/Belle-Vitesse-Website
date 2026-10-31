"""
Utilitaires partagés pour les inspections (check-in/check-out) — PDF, scellement et codes QR.
"""

import base64
import hashlib
import hmac
import logging
import os
import unicodedata
from datetime import date, datetime, timezone
from io import BytesIO
import json
from pathlib import Path
from typing import Union
from urllib.parse import unquote, urlparse

import qrcode
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Constantes Métier & Versions ────────────────────────────────
CGL_VERSION = "2026.1"

# ── Scellement HMAC & Sceau Canonique ────────────────────────────


def _get_hmac_secret(kid: str = "v1") -> bytes:
    """Récupère la clé secrète HMAC depuis l'environnement, avec support de rotation via kid."""
    kid_clean = str(kid).strip()
    secret = None
    if kid_clean:
        secret = os.getenv(f"SEAL_SECRET_KEY_{kid_clean.upper()}") or os.getenv(f"HASH_SECRET_KEY_{kid_clean.upper()}")
    if not secret:
        secret = os.getenv("SEAL_SECRET_KEY") or os.getenv("HASH_SECRET_KEY")

    flask_env = os.getenv("FLASK_ENV", "production")
    if not secret or secret == "fallback_secret_for_dev_only":
        if flask_env == "production":
            raise RuntimeError(
                "❌ SEAL_SECRET_KEY ou HASH_SECRET_KEY doit impérativement être définie avec un secret robuste en production ! "
                "L'utilisation de la SECRET_KEY de session Flask est interdite pour le scellement cryptographique des documents juridiques."
            )
        # Fallback to SECRET_KEY pour les environnements de développement et de test
        secret = os.getenv("SECRET_KEY") or "fallback_secret_for_dev_only"

    return secret.encode("utf-8")


def compute_canonical_seal(payload: dict) -> str:
    """
    Calcule un sceau cryptographique HMAC-SHA256 déterministe sur un dictionnaire JSON canonique.
    Les clés sont triées avec séparateurs stricts (sort_keys=True, separators=(',', ':')).
    Supporte la rotation de clé via le champ '_seal_kid' optionnel dans le payload (par défaut 'v1').
    """
    def _default_serializer(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return str(obj)

    canonical_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_default_serializer,
    )
    kid = payload.get("_seal_kid", "v1") if isinstance(payload, dict) else "v1"
    secret = _get_hmac_secret(kid=kid)
    return hmac.new(secret, canonical_json.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_canonical_seal(expected_hash: str, payload: dict) -> bool:
    """
    Vérifie l'intégrité d'un sceau cryptographique canonique en temps constant.
    """
    if not expected_hash or not payload:
        return False
    actual_hash = compute_canonical_seal(payload)
    return hmac.compare_digest(actual_hash, expected_hash)


def compute_file_sha256(filepath: Union[str, Path]) -> str:
    """Calcule l'empreinte SHA-256 d'un fichier sur disque."""
    p = Path(filepath)
    if not p.exists() or not p.is_file():
        return ""
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_hmac_seal(prefix, *args) -> str:
    """
    Calcule un sceau cryptographique HMAC-SHA256 pour tout document (compatibilité).
    """
    content_parts = [prefix] + [str(arg) for arg in args]
    content = "|".join(content_parts)
    secret = _get_hmac_secret()
    return hmac.new(secret, content.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_hmac_seal(expected_hash, prefix, *args) -> bool:
    """
    Vérifie l'intégrité d'un sceau cryptographique HMAC-SHA256.
    """
    if not expected_hash:
        return False
    actual_hash = compute_hmac_seal(prefix, *args)
    return hmac.compare_digest(actual_hash, expected_hash)


# Alias de compatibilité pour les inspections
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
    if not expected_hash:
        return False
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


# ── Jetons d'Accès PDF (Clé dérivée sécurisée) ────────────────────

def _get_pdf_access_secret() -> bytes:
    """Dérive une sous-clé spécifique pour les jetons de consultation PDF."""
    master = _get_hmac_secret()
    return hmac.new(master, b"belle-vitesse-pdf-access-token-key-derivation", hashlib.sha256).digest()


def generate_pdf_access_token(filename: str) -> str:
    """Génère un jeton d'accès signé HMAC, limité dans le temps, pour un nom de fichier PDF."""
    secret = _get_pdf_access_secret()
    now_minutes = int(datetime.now(timezone.utc).timestamp() // 60)
    payload = f"{filename}:{now_minutes}".encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def validate_pdf_access_token(filename: str, provided_token: str) -> bool:
    """Valide un jeton d'accès limité dans le temps pour un PDF."""
    if not provided_token:
        return False
    secret = _get_pdf_access_secret()
    ttl = int(os.getenv("PDF_ACCESS_TOKEN_TTL_MINUTES", "60"))
    now_minutes = int(datetime.now(timezone.utc).timestamp() // 60)

    for delta in range(ttl + 1):
        ts = now_minutes - delta
        payload = f"{filename}:{ts}".encode("utf-8")
        expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, provided_token):
            return True
    return False


def _get_document_verification_secret() -> bytes:
    """Dérive une clé dédiée aux liens publics de vérification des documents."""
    master = _get_hmac_secret()
    return hmac.new(
        master,
        b"belle-vitesse-document-verification-capability-v1",
        hashlib.sha256,
    ).digest()


def generate_document_verification_token(mode: str, document_id: str, version: int, document_hash: str) -> str:
    """Crée un jeton non devinable, lié à un document et à sa version précise."""
    payload = f"{mode}\0{document_id}\0{int(version)}\0{document_hash}".encode("utf-8")
    return hmac.new(_get_document_verification_secret(), payload, hashlib.sha256).hexdigest()


def validate_document_verification_token(
    mode: str,
    document_id: str,
    version: int,
    document_hash: str,
    provided_token: str,
) -> bool:
    """Vérifie en temps constant le jeton d'accès d'une version signée."""
    if not provided_token or not document_hash:
        return False
    expected = generate_document_verification_token(mode, document_id, version, document_hash)
    return hmac.compare_digest(expected, str(provided_token))


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

def render_pdf_from_template(
    html_content: str,
    base_url: str,
    stylesheets: list[str] = None,
    compress: bool = True,
    filename: str = "document.pdf",
    continuous: bool = False
) -> bytes:
    """
    Générateur de PDF générique utilisant WeasyPrint avec compression automatique.
    Args:
        html_content (str) : Contenu HTML rendu.
        base_url (str) : URL de base pour les ressources.
        stylesheets (list[str]) : Liste des fichiers statiques CSS (ex: ['css/styles.css']).
        compress (bool) : Si True (par défaut), applique la compression PDF locale haute performance.
        filename (str) : Nom indicatif du document pour le traitement de compression.
        continuous (bool) : Si True, génère une page continue sans saut de page (A4) à la hauteur exacte du contenu.
    """
    from flask import current_app
    dummy_pdf = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
    )
    try:
        import sys
        if sys.platform == "darwin":
            import ctypes.util
            if not getattr(ctypes.util, "_bv_macos_patched", False):
                _orig_find_library = ctypes.util.find_library
                def _macos_find_library(name):
                    res = _orig_find_library(name)
                    if res:
                        return res
                    for prefix in ("/opt/homebrew/lib", "/usr/local/lib"):
                        for candidate in (
                            f"{prefix}/{name}.dylib",
                            f"{prefix}/lib{name}.dylib",
                            f"{prefix}/{name}",
                        ):
                            if os.path.exists(candidate):
                                return candidate
                    return None
                ctypes.util.find_library = _macos_find_library
                ctypes.util._bv_macos_patched = True
        from weasyprint import CSS, HTML
        fetcher = make_url_fetcher(current_app)
        html = HTML(string=html_content, base_url=base_url, url_fetcher=fetcher)

        css_list = []
        effective_stylesheets = list(stylesheets) if stylesheets else []
        if not continuous and "css/pdf/base-pdf.css" not in effective_stylesheets:
            effective_stylesheets.insert(0, "css/pdf/base-pdf.css")

        static_path = Path(current_app.static_folder)
        for ss in effective_stylesheets:
            css_file = static_path / ss.lstrip("/")
            if css_file.exists():
                css_list.append(
                    CSS(filename=str(css_file), url_fetcher=fetcher))

        if continuous:
            doc = html.render(stylesheets=css_list)
            if hasattr(doc, "pages") and doc.pages:
                try:
                    p = doc.pages[0]
                    if hasattr(p, "_page_box") and hasattr(p._page_box, "children") and p._page_box.children:
                        html_box = p._page_box.children[0]
                        exact_height = getattr(html_box, "height", None)
                        if exact_height and isinstance(exact_height, (int, float)):
                            p.height = exact_height
                            p._page_box.height = exact_height
                            doc.pages = [p]
                except Exception as render_err:
                    if current_app:
                        current_app.logger.warning(
                            f"⚠️ Avertissement lors de l'ajustement du PDF continu : {render_err}"
                        )
            res = doc.write_pdf()
        else:
            res = html.write_pdf(stylesheets=css_list)
        if isinstance(res, bytes) and len(res) > 0:
            if compress:
                try:
                    from utils.pdf_compressor import compress_pdf
                    return compress_pdf(res, filename=filename)
                except Exception as comp_err:
                    if current_app:
                        current_app.logger.warning(
                            f"⚠️ Erreur lors de la compression automatique : {comp_err}"
                        )
            return res
        return dummy_pdf
    except Exception as e:
        if current_app.config.get("TESTING") or os.getenv("FLASK_ENV") == "testing":
            return dummy_pdf
        raise e


# Backward compatibility alias
def generate_inspection_pdf(html_content: str, base_url: str, mode: str) -> bytes:
    """Legacy helper for inspections."""
    stylesheets = ["css/styles.css", f"css/{mode}.css"]
    return render_pdf_from_template(html_content, base_url, stylesheets)
