import os
import requests
from datetime import datetime
from flask import current_app, render_template

from models import db, PilotWaiver
from weasyprint import HTML, CSS


def process_pilot_waiver_signature(waiver_id):
    """Generate PDF and trigger webhook after signature."""
    waiver = PilotWaiver.query.get(waiver_id)
    if not waiver:
        return

    waiver.status = "signed"
    waiver.signed_at = datetime.utcnow()

    # 1. Generate PDF Path
    pdf_dir = os.path.join(current_app.static_folder, "files", "waivers")
    os.makedirs(pdf_dir, exist_ok=True)

    filename = f"Decharge_Pilote_{waiver.project_id}_{waiver.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    pdf_path_system = os.path.join(pdf_dir, filename)
    pdf_path_url = f"/static/files/waivers/{filename}"

    # 2. Render PDF Template
    html_content = render_template("pdf/pilot_waiver_pdf.html", waiver=waiver)

    try:
        # 3. Generate PDF
        from flask import request
        try:
            base_url = request.host_url
        except RuntimeError:
            base_url = current_app.config.get("SERVER_NAME")
            if not base_url.startswith("https"):
                base_url = f"https://{base_url}"

        # Additional print styles for PDF
        css = CSS(string='''
            @page { size: A4; margin: 2cm; }
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; font-size: 11pt; line-height: 1.5; color: #000; }
            h1 { font-size: 16pt; text-align: center; margin-bottom: 5px; }
            h2 { font-size: 13pt; margin-top: 20px; border-bottom: 1px solid #ccc; padding-bottom: 5px; }
            p, ul { margin-bottom: 10px; }
            li { margin-bottom: 5px; }
            .signature-box { border: 1px solid #ccc; padding: 10px; min-height: 100px; max-width: 300px; text-align: center; }
            .signature-img { max-width: 100%; max-height: 150px; }
        ''')

        HTML(string=html_content, base_url=base_url).write_pdf(
            pdf_path_system, stylesheets=[css])
        waiver.signed_pdf_path = pdf_path_url

    except Exception as e:
        current_app.logger.error(f"Failed to generate waiver PDF: {e}")

    db.session.commit()

    # 4. Trigger Webhook
    webhook_url = os.getenv("N8N_WEBHOOK_PILOT_WAIVER")
    if webhook_url:
        try:
            domain = os.getenv("APP_DOMAIN", "http://localhost:5000")
            payload = {
                "event": "pilot_waiver_signed",
                "waiver_id": waiver.id,
                "project_id": waiver.project_id,
                "signed_at": waiver.signed_at.isoformat(),
                "pilot": {
                    "first_name": waiver.pilot_first_name,
                    "last_name": waiver.pilot_last_name,
                    "license_number": waiver.pilot_license_number
                },
                "production_name": waiver.production_name,
                "signed_pdf_url": f"{domain}{waiver.signed_pdf_path}" if waiver.signed_pdf_path else None
            }
            requests.post(webhook_url, json=payload, timeout=5)
            waiver.webhook_triggered_at = datetime.utcnow()
            db.session.commit()
        except Exception as e:
            current_app.logger.error(
                f"Failed to trigger N8N webhook for waiver {waiver.id}: {e}")
