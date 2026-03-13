import os
import requests
import hmac
import hashlib
import secrets
from datetime import datetime, timezone
from flask import current_app, render_template

from models import db, PilotWaiver, PilotWaiverSignedDocument
from weasyprint import HTML
from utils.waiver_verification import (
    compute_waiver_seal,
    generate_qr_code,
    compute_pdf_hash,
)


def generate_waiver_pdf_access_token(filename):
    """Generate a time-limited, HMAC-signed access token for a waiver PDF filename."""
    secret = os.getenv("HASH_SECRET_KEY", "").encode("utf-8")
    now_minutes = int(datetime.now(timezone.utc).timestamp() // 60)
    payload = f"{filename}:{now_minutes}".encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def validate_waiver_pdf_access_token(filename, provided_token):
    """Validate a time-limited access token for a waiver PDF."""
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


def process_pilot_waiver_signature(waiver_id):
    """Generate PDF and trigger webhook after signature."""
    waiver = PilotWaiver.query.get(waiver_id)
    if not waiver:
        return

    waiver.status = "signed"
    waiver.signed_at = datetime.utcnow()

    # 1. Prepare Verification Data
    pilot_full_name = f"{waiver.pilot_first_name} {waiver.pilot_last_name}"

    # Compute HMAC-SHA256 digital seal (use waiver_id string for ID)
    current_hash = compute_waiver_seal(
        waiver_id=waiver.waiver_id,
        pilot_name=pilot_full_name,
        license_number=waiver.pilot_license_number or "",
        signature_data=waiver.signature_data,
        signed_at=waiver.signed_at.isoformat(),
    )

    # Generate QR code → verification page
    domain = os.getenv("APP_DOMAIN", "https://bellevitesse.com")
    verification_url = f"{domain}/verify/waiver/{waiver.waiver_id}"
    qr_code_img = generate_qr_code(verification_url)

    # 2. Generate PDF Path
    private_folder = current_app.config.get("PRIVATE_FOLDER")
    pdf_dir = os.path.join(private_folder, "pilot_waiver_pdfs")
    os.makedirs(pdf_dir, exist_ok=True)

    filename = f"Decharge_Pilote_{waiver.waiver_id}_{secrets.token_hex(4)}.pdf"
    pdf_path_system = os.path.join(pdf_dir, filename)

    # 3. Secure URL (for database reference and internal use)
    base_url = os.getenv("APP_DOMAIN", "https://bellevitesse.com")
    access_token = generate_waiver_pdf_access_token(filename)
    pdf_path_url = f"/pilot-waiver/document/{filename}?t={access_token}"

    # 3. Render PDF Template
    html_content = render_template(
        "pdf/pilot_waiver_pdf.html",
        waiver=waiver,
        qr=qr_code_img,
        document_hash=current_hash,
        verification_url=verification_url
    )

    try:
        # 4. Generate PDF
        from flask import request
        try:
            base_url = request.host_url
        except RuntimeError:
            base_url = current_app.config.get("SERVER_NAME")
            if base_url and not base_url.startswith("http"):
                base_url = f"https://{base_url}"

        # WeasyPrint PDF generation
        pdf_bytes = HTML(string=html_content, base_url=base_url).write_pdf()

        with open(pdf_path_system, "wb") as f:
            f.write(pdf_bytes)

        waiver.signed_pdf_path = pdf_path_url

        # 5. Compute PDF Hash and Save Snapshot
        pdf_file_hash = compute_pdf_hash(pdf_bytes)

        # Fallback for project_name if it was generated before the model update
        if not waiver.project_name and waiver.project:
            waiver.project_name = waiver.project.nom

        signed_doc = PilotWaiverSignedDocument(
            waiver_id=waiver.waiver_id,
            hash=current_hash,
            pdf_file_hash=pdf_file_hash,
            data_snapshot={
                "id": waiver.id,
                "waiver_id": waiver.waiver_id,
                "project_id": waiver.project_id,
                "project_name": waiver.project_name,
                "pilot_first_name": waiver.pilot_first_name,
                "pilot_last_name": waiver.pilot_last_name,
                "pilot_license_number": waiver.pilot_license_number,
                "pilot_address": waiver.pilot_address,
                "pilot_insurance_company": waiver.pilot_insurance_company,
                "pilot_insurance_policy": waiver.pilot_insurance_policy,
                "production_name": waiver.production_name,
                "vehicles": waiver.vehicles,
                "shooting_dates": waiver.shooting_dates,
                "signed_at": waiver.signed_at.isoformat(),
                "signer_ip": waiver.signer_ip,
                # Seal references for re-verification
                "_seal_pilot_name": pilot_full_name,
                "_seal_license": waiver.pilot_license_number or "",
                "_seal_signed_at": waiver.signed_at.isoformat(),
            },
            signature=waiver.signature_data,
            pdf_url=f"{domain}{pdf_path_url}",
            signed_at=waiver.signed_at
        )
        db.session.add(signed_doc)

    except Exception as e:
        current_app.logger.error(f"Failed to generate waiver PDF: {e}")

    db.session.commit()

    # 6. Trigger Webhook
    webhook_url = os.getenv("N8N_WEBHOOK_PILOT_WAIVER")
    if webhook_url:
        try:
            domain = os.getenv("APP_DOMAIN", "http://localhost:5000")
            payload = {
                "event": "pilot_waiver_signed",
                "waiver_id": waiver.id,
                "waiver_number": waiver.waiver_id,
                "project_id": waiver.project_id,
                "signed_at": waiver.signed_at.isoformat(),
                "pilot": {
                    "first_name": waiver.pilot_first_name,
                    "last_name": waiver.pilot_last_name,
                    "license_number": waiver.pilot_license_number
                },
                "attachments": {
                    "license_url": f"{domain}{waiver.pilot_license_path}" if waiver.pilot_license_path else None,
                    "insurance_url": f"{domain}{waiver.pilot_insurance_path}" if waiver.pilot_insurance_path else None,
                    "identity_url": f"{domain}{waiver.pilot_identity_path}" if waiver.pilot_identity_path else None
                },
                "production_name": waiver.production_name,
                "signed_pdf_url": f"{domain}/pilot-waiver/document/{filename}?t={generate_waiver_pdf_access_token(filename)}" if filename else None
            }
            requests.post(webhook_url, json=payload, timeout=5)
            waiver.webhook_triggered_at = datetime.utcnow()
            db.session.commit()
        except Exception as e:
            current_app.logger.error(
                f"Failed to trigger N8N webhook for waiver {waiver.id}: {e}")
