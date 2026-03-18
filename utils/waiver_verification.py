"""
Waiver verification utilities — hashing, sealing and QR logic.
Delegates most logic to document_utils.py.
"""

from utils.document_utils import (
    compute_hmac_seal,
    verify_hmac_seal
)


def compute_waiver_seal(waiver_id, pilot_name, license_number, signature_data, signed_at):
    return compute_hmac_seal("WAIVER", waiver_id, pilot_name, license_number, signature_data, signed_at)


def verify_waiver_seal(waiver_id, pilot_name, license_number, signature_data, signed_at, expected_hash):
    return verify_hmac_seal(expected_hash, "WAIVER", waiver_id, pilot_name, license_number, signature_data, signed_at)


def compute_production_waiver_seal(waiver_id, production_name, representative, signature_data, signed_at):
    return compute_hmac_seal("WAIVER_PROD", waiver_id, production_name, representative, signature_data, signed_at)


def verify_production_waiver_seal(waiver_id, production_name, representative, signature_data, signed_at, expected_hash):
    return verify_hmac_seal(expected_hash, "WAIVER_PROD", waiver_id, production_name, representative, signature_data, signed_at)
