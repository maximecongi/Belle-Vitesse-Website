"""
Checkin service layer — business logic for the checkin document flow.
Consolidated to use shared signature service.
"""

import logging
from models import db, CheckinVehicle, CheckinSignedDocument
from utils.database import get_vehicles
from services.shared.signatures import (
    validate_inspection_token,
    generate_inspection_token,
    process_inspection_signature,
    generate_pdf_access_token as gen_token,
    validate_pdf_access_token as val_token
)
from utils.document_utils import verify_document_seal, verify_pdf_hash

logger = logging.getLogger(__name__)

# ── Re-exports for backward compatibility / routes ────────────────


def validate_signing_token(token):
    return validate_inspection_token(token, "checkin")


def generate_signing_token(record_id):
    return generate_inspection_token(record_id, "checkin")


def process_signature(token, signature_data, signed_ip):
    return process_inspection_signature(token, "checkin", signature_data, signed_ip)


def generate_pdf_access_token(path):
    return gen_token(path)


def validate_pdf_access_token(path, token):
    return val_token(path, token)

# ── Verification ─────────────────────────────────────────────────


def verify_checkin_document(inspection_id, uploaded_file=None):
    signed_doc = db.session.get(CheckinSignedDocument, inspection_id)

    if not signed_doc:
        record = CheckinVehicle.query.filter_by(
            numero_inspection=inspection_id).first()
        if not record:
            return None

        from services.admin.inspections import _format_base_inspection_admin
        vehicles = get_vehicles()
        vehicle_map = {v["id"]: v.get("fields", {}) for v in vehicles}
        data = _format_base_inspection_admin(record, vehicle_map)

        return {
            "data": data, "seal_valid": False, "pdf_valid": None,
            "source": "mysql", "inspection_id": inspection_id, "has_pdf_hash": False,
        }

    data = signed_doc.data_snapshot
    stored_hash = signed_doc.hash
    stored_signature = signed_doc.signature
    stored_pdf_file_hash = signed_doc.pdf_file_hash

    seal_vehicle_id = data.get("_seal_vehicle_id", data.get("vehicle_id", "—"))
    seal_signed_at = data.get("_seal_signed_at", "")

    # Note: we removed 'km' from the new seal logic,
    # but old documents might still have it in their hash.
    # For now, we assume the new seal logic.
    seal_valid = verify_document_seal(
        inspection_id=inspection_id,
        vehicle_id=seal_vehicle_id,
        signature_data=stored_signature,
        signed_at=seal_signed_at,
        expected_hash=stored_hash,
    )

    data["hash"] = stored_hash
    pdf_url = signed_doc.pdf_url
    if pdf_url:
        path_part = pdf_url.split("/document/")[-1].split("?")[0]
        token = gen_token(path_part)
        import os
        base_url = os.getenv("BASE_URL", "https://bellevitesse.com")
        data["pdf_url"] = f"{base_url}/checkin/document/{path_part}?t={token}"
    else:
        data["pdf_url"] = None

    context = {
        "data": data, "seal_valid": seal_valid, "pdf_valid": None,
        "source": "mysql", "inspection_id": inspection_id, "has_pdf_hash": bool(stored_pdf_file_hash),
    }

    if uploaded_file:
        if not uploaded_file.filename.lower().endswith(".pdf"):
            context["pdf_error"] = "Le fichier doit être un PDF."
        elif not stored_pdf_file_hash:
            context["pdf_error"] = "Ce document a été signé avant l'introduction de la vérification PDF."
        else:
            pdf_valid = verify_pdf_hash(
                uploaded_file.read(), stored_pdf_file_hash)
            context["pdf_valid"] = pdf_valid

    return context
