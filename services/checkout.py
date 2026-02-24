"""
Checkout service layer — business logic for the checkout document flow.

Handles: token generation, signature processing (seal, PDF, MySQL, webhook),
and document verification. No Flask request/response handling.
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

from services.admin import _format_checkout_admin
from utils.airtable import get_vehicles

from utils.checkout import (
    compute_document_seal,
    verify_document_seal,
    generate_qr_code,
    generate_checkout_pdf,
    compute_pdf_hash,
    verify_pdf_hash,
)
from models import db, CheckoutVehicle, CheckoutToken, CheckoutSignedDocument

logger = logging.getLogger(__name__)


# ── Token Management ─────────────────────────────────────────────


def validate_signing_token(token):
    """
    Validate a signing token and return the entry if valid.

    Returns:
        tuple (entry, error_code) — entry is the token object if valid,
        error_code is an HTTP status code if invalid (404, 410, 400), or None.
    """
    entry = db.session.get(CheckoutToken, token)
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


def generate_signing_token(record_id):
    """
    Create a one-time signing token for a checkout record.

    Steps:
      1. Fetch record from MySQL
      2. Create token in MySQL
      3. Update status to "À signer"

    Returns:
        dict with 'inspection_id', 'token', 'sign_url' on success.
        None if record not found.
    """
    record = db.session.get(CheckoutVehicle, record_id)
    if not record:
        return None

    vehicles = get_vehicles()
    vehicle_names = {v["id"]: v.get("fields", {}).get(
        "name", "—") for v in vehicles}
    data = _format_checkout_admin(record, vehicle_names)

    token = str(uuid.uuid4())

    new_token = CheckoutToken(
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
        "sign_url": f"{base_url}/checkout/sign/{token}",
    }


def abandon_signature(token):
    """
    Called when the user closes the signature page without signing.
    Sets the state back to "En cours".
    We don't delete the token so that if the user just reloaded the page,
    the GET request can seamlessly restore it to 'À signer'.
    """
    entry = db.session.get(CheckoutToken, token)
    if not entry or entry.signature:
        return False

    try:
        record = db.session.get(CheckoutVehicle, int(entry.record_id))
        if record:
            record.etat_controle = "En cours"
            db.session.commit()
        logger.info(f"🔙 Signature abandoned for {entry.inspection_id}")
    except Exception as e:
        logger.error(f"❌ Failed to abandon signature: {e}")
    return True


def resume_signature(token):
    """
    Called if the user's browser restores the page from bfcache (tab switch).
    Sets the state to "À signer" just in case it was abandoned.
    """
    entry = db.session.get(CheckoutToken, token)
    if not entry or entry.signature:
        return False

    try:
        record = db.session.get(CheckoutVehicle, int(entry.record_id))
        if record:
            record.etat_controle = "À signer"
            db.session.commit()
    except Exception as e:
        logger.error(f"❌ Failed to resume signature: {e}")
    return True

# ── Signature Processing ─────────────────────────────────────────


def process_signature(token, signature_data, signed_ip):
    """
    Process a checkout signature: seal, PDF, MySQL, webhook.

    Args:
        token: the signing token string
        signature_data: base64 signature image data
        signed_ip: IP address of the signer

    Returns:
        dict with 'inspection_id', 'pdf_url', 'hash' on success.
        Raises on critical failure.
    """
    entry = db.session.get(CheckoutToken, token)
    if not entry:
        raise ValueError("Token invalide ou introuvable.")

    record_id = int(entry.record_id)
    inspection_id = entry.inspection_id
    signed_at = datetime.now(timezone.utc)

    from services.admin import _format_checkout_admin
    from utils.airtable import get_vehicles

    record = db.session.get(CheckoutVehicle, record_id)
    if not record:
        raise ValueError(f"Record {record_id} not found after signing")

    try:
        record.etat_controle = "Signé"
        vehicles = get_vehicles()
        vehicle_names = {v["id"]: v.get("fields", {}).get(
            "name", "—") for v in vehicles}
        data = _format_checkout_admin(record, vehicle_names)
        data["signed_at"] = signed_at.strftime("%d/%m/%Y %H:%M")
        data["signed_ip"] = signed_ip

        # 3. Compute HMAC-SHA256 digital seal
        current_hash = compute_document_seal(
            inspection_id=inspection_id,
            vehicle_id=data["vehicle_id"],
            km=str(data["km"]),
            signature_data=signature_data,
            signed_at=signed_at.isoformat(),
        )

        # 4. Generate QR code → verification page
        base_url = os.getenv("BASE_URL", "https://bellevitesse.com")
        verification_url = f"{base_url}/checkout/verify/{inspection_id}"
        qr_code_img = generate_qr_code(verification_url)

        # 5. Render HTML & generate PDF
        html_content = render_template(
            "checkout.html",
            data=data,
            signature=signature_data,
            qr=qr_code_img,
            hash=current_hash,
            verification_url=verification_url,
        )
        pdf_bytes = generate_checkout_pdf(html_content, base_url=base_url)

        # 6. Save PDF to private storage
        random_token = secrets.token_hex(8)
        filename = f"{inspection_id}_{random_token}.pdf"
        private_folder = current_app.config.get("PRIVATE_FOLDER")
        file_path = os.path.join(private_folder, "checkout_pdfs", filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(pdf_bytes)

        pdf_public_url = f"{base_url}/checkout/document/{filename}"
        pdf_file_hash = compute_pdf_hash(pdf_bytes)

        # 7. Update Token, Record and save Immutable Document in DB (All at once)
        entry.signature = signature_data
        record.pdf_scelle = pdf_public_url
        record.hash = current_hash

        signed_doc = CheckoutSignedDocument(
            inspection_id=inspection_id,
            hash=current_hash,
            pdf_file_hash=pdf_file_hash,
            data_snapshot={
                **data,
                "_seal_vehicle_id": data["vehicle_id"],
                "_seal_km": str(data["km"]),
                "_seal_signed_at": signed_at.isoformat(),
            },
            signature=signature_data,
            pdf_url=pdf_public_url,
            # store naive datetime if needed or timezone-aware if supported. UTC is fine.
            signed_at=signed_at.replace(tzinfo=None)
        )

        db.session.add(signed_doc)
        db.session.delete(entry)
        db.session.commit()

        logger.info(
            f"✅ Signature processed for {inspection_id}. PDF saved at {file_path}")

        # 9. Trigger n8n webhook
        _trigger_n8n_webhook(inspection_id, filename,
                             base_url, current_hash, data)

        return {
            "inspection_id": inspection_id,
            "pdf_url": pdf_public_url,
            "hash": current_hash,
        }

    except Exception as e:
        db.session.rollback()
        logger.error(
            f"❌ Transaction failed during checkout signature {inspection_id}: {e}")
        raise


def _trigger_n8n_webhook(inspection_id, filename, base_url, current_hash, data):
    try:
        n8n_webhook_url = os.getenv("N8N_WEBHOOK_CHECKOUT_SIGN")
        if not n8n_webhook_url:
            logger.warning(
                "⚠️ N8N_WEBHOOK_CHECKOUT_SIGN not set in environment.")
            return

        logger.info(f"🚀 Triggering n8n webhook for {inspection_id}...")

        secret_raw = os.getenv("HASH_SECRET_KEY")
        if not secret_raw:
            logger.error("❌ HASH_SECRET_KEY not set.")
            return
        secret = secret_raw.encode()

        ts = int(datetime.now(timezone.utc).timestamp() // 60)
        token_payload = f"{filename}:{ts}".encode()
        token_n8n = hmac.new(secret, token_payload, hashlib.sha256).hexdigest()
        pdf_url_signed = f"{base_url}/checkout/document/{filename}?t={token_n8n}"

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

        response = http_requests.post(
            n8n_webhook_url, json=webhook_payload, timeout=10)
        if response.status_code in [200, 201]:
            logger.info(f"✅ n8n webhook triggered for {inspection_id}")
        else:
            logger.error(
                f"❌ n8n webhook failed for {inspection_id}: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(
            f"❌ n8n webhook exception for {inspection_id}: {e}")


# ── Verification ─────────────────────────────────────────────────


def verify_checkout_document(inspection_id, uploaded_file=None):
    """
    Verify the integrity of a signed checkout document.

    Two-level verification:
      1. HMAC seal  — proves inspection data fields were not altered
      2. PDF hash   — proves the uploaded file is the signed original

    Args:
        inspection_id: the inspection number
        uploaded_file: optional FileStorage from Flask (for PDF verification)

    Returns:
        dict with template context: data, seal_valid, pdf_valid, source, etc.
    """
    signed_doc = db.session.get(CheckoutSignedDocument, inspection_id)

    # ── No MySQL snapshot → fallback to CheckoutVehicle ─────────────────
    if not signed_doc:
        record = CheckoutVehicle.query.filter_by(
            numero_inspection=inspection_id).first()
        if not record:
            return None  # 404

        from services.admin import _format_checkout_admin
        from utils.airtable import get_vehicles
        vehicles = get_vehicles()
        vehicle_names = {v["id"]: v.get("fields", {}).get(
            "name", "—") for v in vehicles}
        data = _format_checkout_admin(record, vehicle_names)

        logger.warning(
            f"⚠️ Verify fallback to MySQL (via format) for {inspection_id} — no signed snapshot."
        )
        return {
            "data": data,
            "seal_valid": False,
            "pdf_valid": None,
            "source": "mysql",
            "inspection_id": inspection_id,
            "has_pdf_hash": False,
        }

    # ── Retrieve stored values ────────────────────────────────────
    data = signed_doc.data_snapshot

    stored_hash = signed_doc.hash
    stored_signature = signed_doc.signature
    stored_pdf_file_hash = signed_doc.pdf_file_hash

    seal_vehicle_id = data.get("_seal_vehicle_id", data.get("vehicle_id", "—"))
    seal_km = data.get("_seal_km", str(data.get("km", "")))
    seal_signed_at = data.get("_seal_signed_at", "")

    # ── 1. Verify HMAC seal ───────────────────────────────────────
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

    # Generate an access token for the PDF download link
    pdf_url = signed_doc.pdf_url
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

    # ── No file uploaded → GET request ────────────────────────────
    if uploaded_file is None:
        return context

    # ── 2. Verify uploaded PDF ────────────────────────────────────
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
