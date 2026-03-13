"""
Waiver verification utilities — hashing, sealing and QR logic.
Copied and adapted from checkout.py.
"""

import os
import hmac
import hashlib
import qrcode
import base64
from io import BytesIO
from datetime import datetime, timezone


def _get_hmac_secret() -> bytes:
    secret = os.getenv("HASH_SECRET_KEY")
    if not secret:
        # Fallback to SECRET_KEY if HASH_SECRET_KEY is missing, though distinct is better
        secret = os.getenv("SECRET_KEY", "fallback_secret_for_dev_only")
    return secret.encode("utf-8")


def _build_waiver_seal_content(
    waiver_id: str,
    pilot_name: str,
    license_number: str,
    signature_data: str,
    signed_at: str,
) -> str:
    """Canonical string for hashing."""
    return f"WAIVER|{waiver_id}|{pilot_name}|{license_number}|{signature_data}|{signed_at}"


def compute_waiver_seal(
    waiver_id: str,
    pilot_name: str,
    license_number: str,
    signature_data: str,
    signed_at: str,
) -> str:
    content = _build_waiver_seal_content(
        waiver_id, pilot_name, license_number, signature_data, signed_at)
    secret = _get_hmac_secret()
    return hmac.new(secret, content.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_waiver_seal(
    waiver_id: str,
    pilot_name: str,
    license_number: str,
    signature_data: str,
    signed_at: str,
    expected_hash: str,
) -> bool:
    actual_hash = compute_waiver_seal(
        waiver_id, pilot_name, license_number, signature_data, signed_at)
    return hmac.compare_digest(actual_hash, expected_hash)


def compute_pdf_hash(pdf_bytes: bytes) -> str:
    return hashlib.sha256(pdf_bytes).hexdigest()


def verify_pdf_hash(pdf_bytes: bytes, expected_hash: str) -> bool:
    actual_hash = compute_pdf_hash(pdf_bytes)
    return hmac.compare_digest(actual_hash, expected_hash)


def generate_qr_code(data: str) -> str:
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


def generate_pdf_access_token(filename):
    secret = os.getenv("HASH_SECRET_KEY", os.getenv(
        "SECRET_KEY", "")).encode("utf-8")
    now_minutes = int(datetime.now(timezone.utc).timestamp() // 60)
    payload = f"{filename}:{now_minutes}".encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def validate_pdf_access_token(filename, provided_token):
    secret = os.getenv("HASH_SECRET_KEY", os.getenv(
        "SECRET_KEY", "")).encode("utf-8")
    ttl = int(os.getenv("PDF_ACCESS_TOKEN_TTL_MINUTES", "60"))
    now_minutes = int(datetime.now(timezone.utc).timestamp() // 60)

    for delta in range(ttl + 1):
        ts = now_minutes - delta
        payload = f"{filename}:{ts}".encode("utf-8")
        expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, provided_token):
            return True
    return False


def _build_production_waiver_seal_content(
    waiver_id: str,
    production_name: str,
    representative: str,
    signature_data: str,
    signed_at: str,
) -> str:
    """Canonical string for production hashing."""
    return f"WAIVER_PROD|{waiver_id}|{production_name}|{representative}|{signature_data}|{signed_at}"


def compute_production_waiver_seal(
    waiver_id: str,
    production_name: str,
    representative: str,
    signature_data: str,
    signed_at: str,
) -> str:
    content = _build_production_waiver_seal_content(
        waiver_id, production_name, representative, signature_data, signed_at)
    secret = _get_hmac_secret()
    return hmac.new(secret, content.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_production_waiver_seal(
    waiver_id: str,
    production_name: str,
    representative: str,
    signature_data: str,
    signed_at: str,
    expected_hash: str,
) -> bool:
    actual_hash = compute_production_waiver_seal(
        waiver_id, production_name, representative, signature_data, signed_at)
    return hmac.compare_digest(actual_hash, expected_hash)
