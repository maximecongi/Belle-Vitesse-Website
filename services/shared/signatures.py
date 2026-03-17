"""
Shared signature and token service for both Check-in and Check-out (Technician flow).
"""

import os
import uuid
import hmac
import hashlib
import secrets
import logging
from datetime import datetime, timezone, timedelta

from flask import current_app, render_template
from models import (
    db,
    CheckoutVehicle, CheckoutToken, CheckoutSignedDocument,
    CheckinVehicle, CheckinToken, CheckinSignedDocument
)
from utils.database import get_vehicles
from utils.storage import get_checkout_path, get_checkin_path, ensure_dir
from utils.n8n import trigger_n8n_webhook
from utils.inspection_utils import (
    compute_document_seal,
    generate_qr_code,
    compute_pdf_hash,
    generate_inspection_pdf
)

logger = logging.getLogger(__name__)

# ── Model Mapping ──────────────────────────────────────────────

FLOW_CONFIG = {
    "checkout": {
        "model": CheckoutVehicle,
        "token_model": CheckoutToken,
        "signed_model": CheckoutSignedDocument,
        "prefix": "BVCO",
        "url_path": "checkout",
        "storage_func": get_checkout_path,
        "webhook_env": "N8N_WEBHOOK_CHECKOUT_SIGN"
    },
    "checkin": {
        "model": CheckinVehicle,
        "token_model": CheckinToken,
        "signed_model": CheckinSignedDocument,
        "prefix": "BVCI",
        "url_path": "checkin",
        "storage_func": get_checkin_path,
        "webhook_env": "N8N_WEBHOOK_CHECKIN_SIGN"
    }
}

# ── Token Management ─────────────────────────────────────────────


def validate_inspection_token(token_str, mode):
    config = FLOW_CONFIG[mode]
    token_model = config["token_model"]

    entry = db.session.get(token_model, token_str)
    if not entry:
        return None, 404

    created_at = entry.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) - created_at > timedelta(hours=24):
        db.session.delete(entry)
        db.session.commit()
        return None, 410

    if entry.signature:
        return None, 400

    return entry, None


def generate_inspection_token(record_id, mode):
    config = FLOW_CONFIG[mode]
    model = config["model"]
    token_model = config["token_model"]

    record = db.session.get(model, record_id)
    if not record:
        return None

    # Importing dynamically to avoid circular dependencies
    from services.admin.inspections import _format_base_inspection_admin

    vehicles = get_vehicles()
    vehicle_map = {v["id"]: v.get("fields", {}) for v in vehicles}
    data = _format_base_inspection_admin(record, vehicle_map)

    token = str(uuid.uuid4())
    new_token = token_model(
        token=token,
        record_id=str(record_id),
        inspection_id=data["inspection_id"],
        created_at=datetime.utcnow()
    )
    db.session.add(new_token)

    record.etat_controle = "À signer"
    db.session.commit()

    base_url = os.getenv("BASE_URL", "https://bellevitesse.com")
    return {
        "inspection_id": data["inspection_id"],
        "token": token,
        "sign_url": f"{base_url}/{config['url_path']}/sign/{token}",
    }


def abandon_inspection_signature(token_str, mode):
    config = FLOW_CONFIG[mode]
    token_model = config["token_model"]
    model = config["model"]

    entry = db.session.get(token_model, token_str)
    if not entry or entry.signature:
        return False

    try:
        record = db.session.get(model, int(entry.record_id))
        if record:
            record.etat_controle = "En cours"
            db.session.commit()
        logger.info(f"🔙 Signature abandoned for {entry.inspection_id}")
    except Exception as e:
        logger.error(f"❌ Failed to abandon signature: {e}")
    return True


def resume_inspection_signature(token_str, mode):
    config = FLOW_CONFIG[mode]
    token_model = config["token_model"]
    model = config["model"]

    entry = db.session.get(token_model, token_str)
    if not entry or entry.signature:
        return False

    try:
        record = db.session.get(model, int(entry.record_id))
        if record:
            record.etat_controle = "À signer"
            db.session.commit()
    except Exception as e:
        logger.error(f"❌ Failed to resume signature: {e}")
    return True


# ── Signature Processing ─────────────────────────────────────────

def process_inspection_signature(token_str, mode, signature_data, signed_ip):
    config = FLOW_CONFIG[mode]
    token_model = config["token_model"]
    model = config["model"]
    signed_model = config["signed_model"]

    entry = db.session.get(token_model, token_str)
    if not entry:
        raise ValueError("Token invalide ou introuvable.")

    record_id = int(entry.record_id)
    inspection_id = entry.inspection_id
    signed_at = datetime.now(timezone.utc)

    record = db.session.get(model, record_id)
    if not record:
        raise ValueError(f"Record {record_id} not found after signing")

    try:
        record.etat_controle = "Signé"

        # Format for PDF
        from services.admin.inspections import _format_base_inspection_admin
        vehicles = get_vehicles()
        vehicle_map = {v["id"]: v.get("fields", {}) for v in vehicles}
        data = _format_base_inspection_admin(record, vehicle_map)

        data["signed_at"] = signed_at.strftime("%d/%m/%Y %H:%M")
        data["signed_ip"] = signed_ip

        # 1. Compute HMAC seal
        current_hash = compute_document_seal(
            inspection_id=inspection_id,
            vehicle_id=data["vehicle_id"],
            signature_data=signature_data,
            signed_at=signed_at.isoformat(),
        )

        # 2. QR code & PDF
        base_url = os.getenv("BASE_URL", "https://bellevitesse.com")
        verification_url = f"{base_url}/{config['url_path']}/verify/{inspection_id}"
        qr_code_img = generate_qr_code(verification_url)

        html_content = render_template(
            f"{config['url_path']}.html",
            data=data,
            signature=signature_data,
            qr=qr_code_img,
            hash=current_hash,
            verification_url=verification_url,
        )
        pdf_bytes = generate_inspection_pdf(
            html_content, base_url=base_url, mode=config['url_path'])

        # 3. Storage
        pdf_dir = ensure_dir(config["storage_func"](record.project))
        random_token = secrets.token_hex(8)
        filename = f"{inspection_id}_{random_token}.pdf"
        file_path = os.path.join(pdf_dir, filename)

        output_base = current_app.config.get(
            "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))
        rel_pdf_path = os.path.relpath(file_path, output_base)

        with open(file_path, "wb") as f:
            f.write(pdf_bytes)

        pdf_public_url = f"{base_url}/{config['url_path']}/document/{rel_pdf_path}"
        pdf_file_hash = compute_pdf_hash(pdf_bytes)

        # 4. Persistence
        entry.signature = signature_data
        record.pdf_scelle = pdf_public_url
        record.hash = current_hash

        signed_doc = signed_model(
            inspection_id=inspection_id,
            hash=current_hash,
            pdf_file_hash=pdf_file_hash,
            data_snapshot={
                **data,
                "_seal_vehicle_id": data["vehicle_id"],
                "_seal_signed_at": signed_at.isoformat(),
            },
            signature=signature_data,
            pdf_url=pdf_public_url,
            signed_at=signed_at.replace(tzinfo=None)
        )

        db.session.add(signed_doc)
        db.session.delete(entry)
        db.session.commit()

        # 5. n8n Webhook
        _trigger_inspection_webhook(
            mode, inspection_id, rel_pdf_path, base_url, current_hash, data)

        return {
            "inspection_id": inspection_id,
            "pdf_url": pdf_public_url,
            "hash": current_hash,
        }

    except Exception as e:
        db.session.rollback()
        logger.error(
            f"❌ Transaction failed during {mode} signature {inspection_id}: {e}")
        raise


# ── Webhook Logic ──────────────────────────────────────────────

def _trigger_inspection_webhook(mode, inspection_id, rel_pdf_path, base_url, current_hash, data):
    config = FLOW_CONFIG[mode]
    try:
        n8n_webhook_url = os.getenv(config["webhook_env"])
        if not n8n_webhook_url:
            return

        secret_raw = os.getenv("HASH_SECRET_KEY")
        if not secret_raw:
            return
        secret = secret_raw.encode()

        ts = int(datetime.now(timezone.utc).timestamp() // 60)
        token_payload = f"{rel_pdf_path}:{ts}".encode()
        token_n8n = hmac.new(secret, token_payload, hashlib.sha256).hexdigest()
        pdf_url_signed = f"{base_url}/{config['url_path']}/document/{rel_pdf_path}?t={token_n8n}"

        # Date formatting for n8n filters
        date_parts = data.get("control_date", "").split()
        year = date_parts[2] if len(date_parts) >= 3 else "—"
        month_name = date_parts[1].lower() if len(date_parts) >= 3 else ""
        MOIS_NUM = {"janvier": "01", "février": "02", "mars": "03", "avril": "04", "mai": "05", "juin": "06",
                    "juillet": "07", "août": "08", "septembre": "09", "octobre": "10", "novembre": "11", "décembre": "12"}
        month = MOIS_NUM.get(month_name, "—")

        # Secured photo URLs
        def get_secured_photo_url(photo_item):
            if not photo_item or "url" not in photo_item:
                return None
            path = photo_item["url"].replace("/files/", "")
            # We'll use a local import to avoid circular dependencies if we move this later
            from services.shared.signatures import generate_pdf_access_token
            token = generate_pdf_access_token(path)
            return f"{base_url}/files/{path}?t={token}"

        interior_photos = [get_secured_photo_url(
            p) for p in data.get("interior_photos", [])]
        exterior_photos = [get_secured_photo_url(
            p) for p in data.get("exterior_photos", [])]

        webhook_payload = {
            "inspection_id": inspection_id,
            "project_id": data.get("project_id_unique", "—"),
            "pdf_url": pdf_url_signed,
            "hash": current_hash,
            "production": data.get("production", "—"),
            "project": data.get("project", "—"),
            "control_date": data.get("control_date", "—"),
            "year": year,
            "month": month,
            "photos": {
                "interior": [p for p in interior_photos if p],
                "exterior": [p for p in exterior_photos if p]
            }
        }
        trigger_n8n_webhook(n8n_webhook_url, **webhook_payload)
    except Exception as e:
        logger.error(f"❌ n8n webhook exception for {inspection_id}: {e}")


# ── PDF Access Token (Common for all secured downloads) ────────────────

def generate_pdf_access_token(path_or_filename):
    secret = os.getenv("HASH_SECRET_KEY", "").encode("utf-8")
    now_minutes = int(datetime.now(timezone.utc).timestamp() // 60)
    payload = f"{path_or_filename}:{now_minutes}".encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def validate_pdf_access_token(path_or_filename, provided_token):
    secret = os.getenv("HASH_SECRET_KEY", "").encode("utf-8")
    ttl = int(os.getenv("PDF_ACCESS_TOKEN_TTL_MINUTES", "60"))
    now_minutes = int(datetime.now(timezone.utc).timestamp() // 60)

    for delta in range(ttl + 1):
        ts = now_minutes - delta
        payload = f"{path_or_filename}:{ts}".encode("utf-8")
        expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, provided_token):
            return True
    return False
