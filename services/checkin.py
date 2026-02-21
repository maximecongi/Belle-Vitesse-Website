"""
Checkin service layer — business logic for the checkin document flow.
"""

import os
import uuid
import hmac
import hashlib
import secrets
import logging
import requests as http_requests
from datetime import datetime, timezone, timedelta

from flask import current_app, render_template

from utils.checkin import (
    get_checkin_record,
    get_checkin_by_inspection_id,
    format_checkin_data,
    compute_document_seal,
    verify_document_seal,
    generate_qr_code,
    generate_checkin_pdf,
    compute_pdf_hash,
    verify_pdf_hash,
    TABLE_CHECKIN,
    _resolve_controller,
)
from utils.database import (
    store_checkin_signed_document,
    get_checkin_signed_document,
    store_checkin_token,
    get_checkin_token,
    update_checkin_token_signature,
    delete_checkin_token,
)

logger = logging.getLogger(__name__)


# ── Token Management ─────────────────────────────────────────────


def validate_signing_token(token):
    entry = get_checkin_token(token)
    if not entry:
        return None, 404

    created_at = entry["created_at"]
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) - created_at > timedelta(hours=24):
        delete_checkin_token(token)
        return None, 410

    if entry["signature"]:
        return None, 400

    return entry, None


def generate_signing_token(record_id):
    record = get_checkin_record(record_id)
    if not record:
        return None

    data = format_checkin_data(record)
    token = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)

    store_checkin_token(
        token=token,
        record_id=record_id,
        inspection_id=data["inspection_id"],
        created_at=created_at,
    )

    try:
        TABLE_CHECKIN.update(record_id, {"État du contrôle": "À signer"})
    except Exception as e:
        logger.error(
            f"❌ Failed to update Airtable for {data['inspection_id']}: {e}")

    base_url = os.getenv("BASE_URL", "https://bellevitesse.com")
    return {
        "inspection_id": data["inspection_id"],
        "token": token,
        "sign_url": f"{base_url}/checkin/sign/{token}",
    }


# ── Signature Processing ─────────────────────────────────────────


def process_signature(token, signature_data, signed_ip):
    entry = get_checkin_token(token)
    record_id = entry["record_id"]
    inspection_id = entry["inspection_id"]
    signed_at = datetime.now(timezone.utc).isoformat()

    update_checkin_token_signature(token, signature_data)

    try:
        TABLE_CHECKIN.update(record_id, {"État du contrôle": "Signé"})
    except Exception as e:
        logger.error(f"❌ Failed to update Airtable for {inspection_id}: {e}")

    record = get_checkin_record(record_id)
    if not record:
        raise ValueError(f"Record {record_id} not found after signing")

    data = format_checkin_data(record)
    data["signed_at"] = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
    data["signed_ip"] = signed_ip

    current_hash = compute_document_seal(
        inspection_id=inspection_id,
        vehicle_id=data["vehicle_id"],
        km=str(data["km"]),
        signature_data=signature_data,
        signed_at=signed_at,
    )

    base_url = os.getenv("BASE_URL", "https://bellevitesse.com")
    verification_url = f"{base_url}/checkin/verify/{inspection_id}"
    qr_code_img = generate_qr_code(verification_url)

    html_content = render_template(
        "checkin.html",
        data=data,
        signature=signature_data,
        qr=qr_code_img,
        hash=current_hash,
        verification_url=verification_url,
    )
    pdf_bytes = generate_checkin_pdf(html_content, base_url=base_url)

    random_token = secrets.token_hex(8)
    filename = f"{inspection_id}_{random_token}.pdf"
    private_folder = current_app.config.get("PRIVATE_FOLDER")
    file_path = os.path.join(private_folder, "checkin_pdfs", filename)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    pdf_public_url = f"{base_url}/checkin/document/{filename}"
    pdf_file_hash = compute_pdf_hash(pdf_bytes)

    store_success = store_checkin_signed_document(
        inspection_id=inspection_id,
        file_hash=current_hash,
        pdf_file_hash=pdf_file_hash,
        data_snapshot={
            **data,
            "_seal_vehicle_id": data["vehicle_id"],
            "_seal_km": str(data["km"]),
            "_seal_signed_at": signed_at,
        },
        signature=signature_data,
        pdf_url=pdf_public_url,
        signed_at=datetime.now(timezone.utc),
    )

    if store_success:
        logger.info(f"✅ Document {inspection_id} frozen in MySQL.")
    else:
        logger.error(f"❌ Failed to freeze document {inspection_id} in MySQL.")

    try:
        TABLE_CHECKIN.update(
            record_id,
            {
                "État du contrôle": "Signé",
                "PDF scellé": pdf_public_url,
                "Hash": current_hash,
            },
        )
    except Exception as e:
        logger.error(f"❌ Failed to update Airtable for {inspection_id}: {e}")

    logger.info(
        f"✅ Signature processed for {inspection_id}. PDF saved at {file_path}")

    _trigger_n8n_webhook(inspection_id, filename, base_url, current_hash, data)

    delete_checkin_token(token)

    return {
        "inspection_id": inspection_id,
        "pdf_url": pdf_public_url,
        "hash": current_hash,
    }


def _trigger_n8n_webhook(inspection_id, filename, base_url, current_hash, data):
    try:
        n8n_webhook_url = os.getenv("N8N_WEBHOOK_CHECKIN_SIGN")
        if not n8n_webhook_url:
            return

        secret = os.getenv("HASH_SECRET_KEY").encode()
        ts = int(datetime.now(timezone.utc).timestamp() // 60)
        token_payload = f"{filename}:{ts}".encode()
        token_n8n = hmac.new(secret, token_payload, hashlib.sha256).hexdigest()
        pdf_url_signed = f"{base_url}/checkin/document/{filename}?t={token_n8n}"

        date_parts = data.get("control_date", "").split()
        year = date_parts[2] if len(date_parts) >= 3 else "—"
        month_name = date_parts[1].lower() if len(date_parts) >= 3 else ""

        MOIS_NUM = {
            "janvier": "01", "février": "02", "mars": "03",
            "avril": "04", "mai": "05", "juin": "06",
            "juillet": "07", "août": "08", "septembre": "09",
            "octobre": "10", "novembre": "11", "décembre": "12",
        }
        month = MOIS_NUM.get(month_name, "—")

        webhook_payload = {
            "inspection_id": inspection_id,
            "pdf_url": pdf_url_signed,
            "hash": current_hash,
            "production": data.get("production", "—"),
            "project": data.get("project", "—"),
            "control_date": data.get("control_date", "—"),
            "year": year,
            "month": month,
        }

        response = http_requests.post(n8n_webhook_url, json=webhook_payload)
        if response.status_code == 200:
            logger.info(f"✅ n8n webhook triggered for {inspection_id}")
        else:
            logger.error(
                f"❌ n8n webhook failed for {inspection_id}: {response.status_code}"
            )
    except Exception as e:
        logger.error(f"❌ n8n webhook exception for {inspection_id}: {e}")


# ── Verification ─────────────────────────────────────────────────


def verify_checkin_document(inspection_id, uploaded_file=None):
    signed_doc = get_checkin_signed_document(inspection_id)

    if not signed_doc:
        record = get_checkin_by_inspection_id(inspection_id)
        if not record:
            return None

        data = format_checkin_data(record)
        logger.warning(
            f"⚠️ Verify fallback to Airtable for {inspection_id} — no MySQL snapshot."
        )
        return {
            "data": data,
            "seal_valid": False,
            "pdf_valid": None,
            "source": "airtable",
            "inspection_id": inspection_id,
            "has_pdf_hash": False,
        }

    data = signed_doc["data_snapshot"]

    if "controller" in data and isinstance(data["controller"], list):
        data["controller"] = _resolve_controller(data["controller"])

    stored_hash = signed_doc["hash"]
    stored_signature = signed_doc["signature"]
    stored_pdf_file_hash = signed_doc.get("pdf_file_hash")

    seal_vehicle_id = data.get("_seal_vehicle_id", data.get("vehicle_id", "—"))
    seal_km = data.get("_seal_km", str(data.get("km", "")))
    seal_signed_at = data.get("_seal_signed_at", "")

    seal_valid = verify_document_seal(
        inspection_id=inspection_id,
        vehicle_id=seal_vehicle_id,
        km=seal_km,
        signature_data=stored_signature,
        signed_at=seal_signed_at,
        expected_hash=stored_hash,
    )

    if not seal_valid:
        logger.warning(
            f"⚠️ Seal mismatch for {inspection_id} — data may have been tampered with."
        )

    data["hash"] = stored_hash
    pdf_url = signed_doc["pdf_url"]
    if pdf_url:
        filename = pdf_url.split("/")[-1]
        token = generate_pdf_access_token(filename)
        data["pdf_url"] = f"{pdf_url}?t={token}"
    else:
        data["pdf_url"] = None

    context = {
        "data": data,
        "seal_valid": seal_valid,
        "pdf_valid": None,
        "source": "mysql",
        "inspection_id": inspection_id,
        "has_pdf_hash": bool(stored_pdf_file_hash),
    }

    if uploaded_file is None:
        return context

    if not uploaded_file.filename.lower().endswith(".pdf"):
        context["pdf_error"] = "Le fichier doit être un PDF."
        return context

    if not stored_pdf_file_hash:
        context["pdf_error"] = (
            "Ce document a été signé avant l'introduction de la "
            "vérification PDF. Seul le sceau de données est disponible."
        )
        context["has_pdf_hash"] = False
        return context

    uploaded_bytes = uploaded_file.read()
    pdf_valid = verify_pdf_hash(uploaded_bytes, stored_pdf_file_hash)

    if not pdf_valid:
        logger.warning(
            f"⚠️ PDF hash mismatch for {inspection_id} — uploaded file differs."
        )
    else:
        logger.info(
            f"✅ PDF verified for {inspection_id} — file matches signed original."
        )

    context["pdf_valid"] = pdf_valid
    return context


# ── PDF Access Token ─────────────────────────────────────────────


def generate_pdf_access_token(filename):
    """
    Generate a time-limited, HMAC-signed access token for a PDF filename.
    """
    secret = os.getenv("HASH_SECRET_KEY", "").encode("utf-8")
    now_minutes = int(datetime.now(timezone.utc).timestamp() // 60)
    payload = f"{filename}:{now_minutes}".encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def validate_pdf_access_token(filename, provided_token):
    secret = os.getenv("HASH_SECRET_KEY", "").encode("utf-8")
    ttl = int(os.getenv("PDF_ACCESS_TOKEN_TTL_MINUTES", "60"))
    now_minutes = int(datetime.now(timezone.utc).timestamp() // 60)

    for delta in range(ttl + 1):
        ts = now_minutes - delta
        payload = f"{filename}:{ts}".encode("utf-8")
        expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, provided_token):
            return True
    return False
