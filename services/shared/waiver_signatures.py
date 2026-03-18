"""
Shared waiver signature service — logic for both Pilot and Production waivers.
"""

import os
import logging
import secrets
import requests
from datetime import datetime

from flask import current_app, render_template
from models import (
    db,
    PilotWaiver,
    PilotWaiverSignedDocument,
    ProductionWaiver,
    ProductionWaiverSignedDocument
)
from utils.document_utils import (
    compute_hmac_seal,
    generate_qr_code,
    compute_pdf_hash,
    generate_pdf_access_token as generate_waiver_pdf_access_token
)
from utils.storage import get_pilot_waiver_path, get_production_waiver_path, ensure_dir
from utils.mailer import send_waiver_signed_email
from weasyprint import HTML

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────

FLOW_CONFIG = {
    "pilot": {
        "model": PilotWaiver,
        "signed_model": PilotWaiverSignedDocument,
        "prefix": "WAIVER",
        "template": "pdf/pilot_waiver_pdf.html",
        "storage_path_func": get_pilot_waiver_path,
        "webhook_env": "N8N_WEBHOOK_PILOT_WAIVER",
        "route_base": "pilot-waiver"
    },
    "production": {
        "model": ProductionWaiver,
        "signed_model": ProductionWaiverSignedDocument,
        "prefix": "WAIVER_PROD",
        "template": "pdf/production_waiver_pdf.html",
        "storage_path_func": get_production_waiver_path,
        "webhook_env": "N8N_WEBHOOK_PRODUCTION_WAIVER",
        "route_base": "production-waiver"
    }
}

# ── Core Logic ─────────────────────────────────────────────────


def process_waiver_signature(mode, waiver_db_id):
    """
    Common logic to finalize a waiver after signature:
    - Update state
    - Compute HMAC seal
    - Generate QR Code
    - Generate PDF
    - Save snapshot
    - Trigger Webhook
    - Send Email
    """
    config = FLOW_CONFIG.get(mode)
    if not config:
        raise ValueError(f"Invalid waiver mode: {mode}")

    waiver = db.session.get(config["model"], waiver_db_id)
    if not waiver:
        logger.error(f"❌ Waiver {waiver_db_id} (mode={mode}) not found.")
        return False

    try:
        waiver.status = "signed"
        waiver.signed_at = datetime.utcnow()

        # 1. Verification Data & Seal
        seal_args = []
        if mode == "pilot":
            full_name = f"{waiver.pilot_first_name} {waiver.pilot_last_name}"
            seal_args = [full_name, waiver.pilot_license_number or ""]
        else:
            seal_args = [waiver.production_name or "",
                         waiver.production_representative or ""]

        seal_args += [waiver.signature_data, waiver.signed_at.isoformat()]

        current_hash = compute_hmac_seal(
            config["prefix"], waiver.waiver_id, *seal_args)

        # 2. QR Code
        domain = os.getenv("APP_BASE_URL", "https://bellevitesse.com")
        if not domain.startswith("http"):
            domain = f"https://{domain}"

        verification_url = f"{domain}/verify/{config['route_base']}/{waiver.waiver_id}"
        qr_code_img = generate_qr_code(verification_url)

        # 3. PDF Generation Path
        pdf_dir = ensure_dir(config["storage_path_func"](waiver.project))
        filename = f"{waiver.waiver_id}_{secrets.token_hex(4)}.pdf"
        pdf_path_system = os.path.join(pdf_dir, filename)

        output_base = current_app.config.get(
            "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))
        rel_pdf_path = os.path.relpath(pdf_path_system, output_base)

        # 4. Render and Generate PDF
        html_content = render_template(
            config["template"],
            waiver=waiver,
            qr=qr_code_img,
            document_hash=current_hash,
            verification_url=verification_url
        )

        from flask import request
        try:
            base_url_weasy = request.host_url
        except RuntimeError:
            base_url_weasy = current_app.config.get("SERVER_NAME")
            if base_url_weasy and not base_url_weasy.startswith("http"):
                base_url_weasy = f"https://{base_url_weasy}"

        pdf_bytes = HTML(string=html_content,
                         base_url=base_url_weasy).write_pdf()
        with open(pdf_path_system, "wb") as f:
            f.write(pdf_bytes)

        waiver.signed_pdf_path = rel_pdf_path
        pdf_file_hash = compute_pdf_hash(pdf_bytes)

        # 5. Save Snapshot
        snapshot = _build_snapshot(mode, waiver, current_hash, seal_args)

        access_token = generate_waiver_pdf_access_token(rel_pdf_path)
        pdf_url_signed = f"{domain}/{config['route_base']}/document/{rel_pdf_path}?t={access_token}"

        signed_doc = config["signed_model"](
            waiver_id=waiver.waiver_id,
            hash=current_hash,
            pdf_file_hash=pdf_file_hash,
            data_snapshot=snapshot,
            signature=waiver.signature_data,
            pdf_url=pdf_url_signed,
            signed_at=waiver.signed_at
        )
        db.session.add(signed_doc)
        db.session.commit()

        # 6. Webhook
        _trigger_waiver_webhook(
            mode, waiver, rel_pdf_path, domain, current_hash)

        # 7. Email
        _send_waiver_confirmation_email(mode, waiver, pdf_path_system)

        return True

    except Exception as e:
        db.session.rollback()
        logger.error(
            f"❌ Error processing {mode} waiver signature: {e}", exc_info=True)
        return False


def _build_snapshot(mode, waiver, current_hash, seal_args):
    """Build the data snapshot for the signed document."""
    snapshot = {
        "id": waiver.id,
        "waiver_id": waiver.waiver_id,
        "project_id": waiver.project_id,
        "project_name": waiver.project_name or (waiver.project.nom if waiver.project else "—"),
        "vehicles": waiver.vehicles,
        "shooting_dates": waiver.shooting_dates,
        "signed_at": waiver.signed_at.isoformat(),
        "signer_ip": waiver.signer_ip,
        "hash": current_hash,
    }

    if mode == "pilot":
        snapshot.update({
            "pilot_first_name": waiver.pilot_first_name,
            "pilot_last_name": waiver.pilot_last_name,
            "pilot_license_number": waiver.pilot_license_number,
            "pilot_address": waiver.pilot_address,
            "pilot_insurance_company": waiver.pilot_insurance_company,
            "pilot_license_path": waiver.pilot_license_path,
            "pilot_insurance_path": waiver.pilot_insurance_path,
            "pilot_identity_path": waiver.pilot_identity_path,
            "_seal_pilot_name": seal_args[0],
            "_seal_license": seal_args[1],
            "_seal_signed_at": seal_args[-1],
        })
    else:
        snapshot.update({
            "production_name": waiver.production_name,
            "representative": waiver.production_representative,
            "address": waiver.production_address,
            "siret": waiver.production_siret,
            "vat": waiver.production_vat,
            "insurance_company": waiver.production_insurance_company,
            "insurance_path": waiver.production_insurance_path,
            "location_of_use": waiver.location_of_use,
            "_seal_production_name": seal_args[0],
            "_seal_representative": seal_args[1],
            "_seal_signed_at": seal_args[-1],
        })
    return snapshot


def _trigger_waiver_webhook(mode, waiver, rel_pdf_path, domain, current_hash):
    """Triggers the appropriate n8n webhook."""
    config = FLOW_CONFIG[mode]
    webhook_url = os.getenv(config["webhook_env"])
    if not webhook_url:
        return

    access_token = generate_waiver_pdf_access_token(rel_pdf_path)
    pdf_url = f"{domain}/{config['route_base']}/document/{rel_pdf_path}?t={access_token}"

    ref_date = waiver.project.date_debut_tournage if (
        waiver.project and waiver.project.date_debut_tournage) else waiver.signed_at

    payload = {
        "event": f"{mode}_waiver_signed",
        "id": waiver.id,
        "waiver_id": waiver.waiver_id,
        "project_id": waiver.project.project_id if waiver.project else None,
        "year": ref_date.strftime("%Y"),
        "month": ref_date.strftime("%m"),
        "project": waiver.project_name or (waiver.project.nom if waiver.project else "—"),
        "pdf_url": pdf_url,
        "hash": current_hash
    }

    if mode == "pilot":
        def get_secured_attachment_url(path):
            if not path:
                return None
            t = generate_waiver_pdf_access_token(path)
            return f"{domain}/pilot-waiver/attachment/{path}?t={t}"

        payload.update({
            "pilot": {
                "first_name": waiver.pilot_first_name,
                "last_name": waiver.pilot_last_name,
                "license_number": waiver.pilot_license_number
            },
            "attachments": {
                "license_url": get_secured_attachment_url(waiver.pilot_license_path),
                "insurance_url": get_secured_attachment_url(waiver.pilot_insurance_path),
                "identity_url": get_secured_attachment_url(waiver.pilot_identity_path)
            },
            "production": waiver.production_name
        })
    else:
        payload.update({
            "production": {
                "name": waiver.production_name,
                "representative": waiver.production_representative,
                "siret": waiver.production_siret,
                "vat": waiver.production_vat,
                "insurance_url": f"{domain}/production-waiver/attachment/{waiver.production_insurance_path}?t={generate_waiver_pdf_access_token(waiver.production_insurance_path)}" if waiver.production_insurance_path else None
            }
        })

    try:
        requests.post(webhook_url, json=payload, timeout=5)
        waiver.webhook_triggered_at = datetime.utcnow()
        db.session.commit()
    except Exception as e:
        logger.error(f"❌ Webhook error ({mode} {waiver.id}): {e}")


def _send_waiver_confirmation_email(mode, waiver, pdf_path):
    """Sends confirmation email with PDF."""
    try:
        recipient_email = None
        recipient_name = None

        if mode == "pilot":
            if waiver.project and waiver.project.contact_pilote_rel:
                recipient_email = waiver.project.contact_pilote_rel.mail
            recipient_name = f"{waiver.pilot_first_name} {waiver.pilot_last_name}"
        else:
            if waiver.project and waiver.project.contact_production_rel:
                recipient_email = waiver.project.contact_production_rel.mail
            recipient_name = waiver.production_representative

        if recipient_email:
            send_waiver_signed_email(
                recipient_email,
                recipient_name,
                waiver.project_name or (
                    waiver.project.nom if waiver.project else "—"),
                pdf_path
            )
    except Exception as e:
        logger.error(f"❌ Email error ({mode} {waiver.id}): {e}")
