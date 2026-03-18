import logging
from services.shared.signatures import (
    validate_inspection_token,
    generate_inspection_token,
    process_inspection_signature,
    abandon_inspection_signature,
    resume_inspection_signature
)

logger = logging.getLogger(__name__)

# ── Re-exports for backward compatibility / routes ────────────────


def validate_signing_token(token):
    return validate_inspection_token(token, "checkout")


def generate_signing_token(record_id):
    return generate_inspection_token(record_id, "checkout")


def process_signature(token, signature_data, signed_ip):
    return process_inspection_signature(token, "checkout", signature_data, signed_ip)


def abandon_signature(token):
    return abandon_inspection_signature(token, "checkout")


def resume_signature(token):
    return resume_inspection_signature(token, "checkout")
