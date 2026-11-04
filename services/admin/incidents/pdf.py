"""
Génération des fiches de constat d'incident au format PDF avec WeasyPrint et sceau contradictoire.
"""

import os
from datetime import date

from flask import current_app, render_template

from services.admin.incidents.crud import _format_date, get_incident_detail
from utils.document_utils import generate_qr_code, render_pdf_from_template
from utils.request_utils import resolve_base_url


def generate_incident_pdf(record_id):
    """
    Génère la fiche de constat d'incident officielle au format PDF selon la DA Belle Vitesse.
    Intègre les signatures réelles, le QR code et le sceau HMAC si le constat est finalisé.
    """
    incident_data = get_incident_detail(record_id)
    if not incident_data:
        raise ValueError(
            f"Incident #{record_id} introuvable pour la génération PDF.")

    company_address = ""
    company_name = "Belle Vitesse SAS"
    try:
        from models import AppSetting
        from utils.context_processors import DEFAULT_SETTINGS
        company_address = AppSetting.get(
            "company_address", DEFAULT_SETTINGS.get("company_address", ""))
        company_name = AppSetting.get(
            "company_name", DEFAULT_SETTINGS.get("company_name", "Belle Vitesse SAS"))
    except Exception:
        pass

    is_sealed = incident_data.get("is_fully_signed", False) or incident_data.get(
        "signature_status") == "signed"

    # Si le document est scellé et que le PDF signé existe sur le disque, servir l'exemplaire scellé original
    if is_sealed and incident_data.get("signed_pdf_path"):
        output_base = current_app.config.get(
            "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))
        sealed_file_path = os.path.join(
            output_base, incident_data["signed_pdf_path"])
        if os.path.exists(sealed_file_path):
            with open(sealed_file_path, "rb") as f:
                return f.read(), os.path.basename(sealed_file_path)

    qr_code_img = None
    verification_url = None
    if is_sealed and incident_data.get("hash"):
        base_url = resolve_base_url()
        verification_url = f"{base_url}/incidents/verify/{incident_data['incident_number']}"
        qr_code_img = generate_qr_code(verification_url)

    html = render_template(
        "pdf/incident_report.html",
        company_name=company_name,
        company_address=company_address,
        incident=incident_data,
        today=_format_date(date.today()),
        is_sealed=is_sealed,
        qr=qr_code_img,
        hash=incident_data.get("hash"),
        verification_url=verification_url,
        signed_at_str=incident_data.get(
            "prod_signed_at") or _format_date(date.today()),
    )

    filename = f"Belle_Vitesse_INCIDENT_{incident_data['incident_number']}.pdf"
    pdf_bytes = render_pdf_from_template(
        html_content=html,
        base_url=current_app.root_path,
        stylesheets=["css/styles.css",
                     "css/checkout.css", "css/incident_pdf.css"],
        filename=filename,
    )

    return pdf_bytes, filename

