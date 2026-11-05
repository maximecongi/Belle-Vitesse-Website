from flask import Blueprint, Response, abort, render_template, request
from jinja2.exceptions import TemplateNotFound

from extensions import csrf
from utils.decorators import require_roles



tools_bp = Blueprint('admin_tools', __name__, url_prefix='/admin')
"""Initialise les routes pour les outils administratifs."""

@tools_bp.route("/tools/meeting-report", methods=["GET"], endpoint='admin_meeting_report')
@require_roles('administrator', 'manager', 'commercial', 'user')
def admin_meeting_report():
    """Outil de mise en forme et génération de comptes-rendus de réunion."""
    return render_template("admin/meeting_report.html")

@tools_bp.route("/tools/meeting-report/pdf", methods=["POST"], endpoint='admin_meeting_report_pdf')
@csrf.exempt
@require_roles('administrator', 'manager', 'commercial', 'user')
def admin_meeting_report_pdf():
    """Génération et téléchargement du compte-rendu au format PDF WeasyPrint."""
    from services.admin.meeting_report_service import generate_meeting_report_pdf, parse_meeting_report

    data = request.get_json(silent=True) or {}
    markdown_text = data.get("markdown", "")
    custom_title = data.get("title")
    custom_date = data.get("date_str")
    custom_ref = data.get("ref")
    custom_doc_type = data.get("doc_type")

    report_data = parse_meeting_report(
        markdown_text=markdown_text,
        custom_title=custom_title,
        custom_date=custom_date,
        custom_ref=custom_ref,
        custom_doc_type=custom_doc_type,
    )

    pdf_bytes = generate_meeting_report_pdf(report_data, base_url=request.host_url)
    filename = f"{report_data.get('doc_id', 'BVMR')}.pdf"

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Document-Id": report_data.get("doc_id", "BVMR"),
        },
    )

@tools_bp.route("/tools/signature-generator", endpoint='admin_signature_generator')
@require_roles('administrator', 'manager', 'commercial', 'user')
def admin_signature_generator():
    """Outil de génération de signature visuelle."""
    return render_template("admin/signature_generator.html")

@tools_bp.route("/tools/check-vehicles", strict_slashes=False, endpoint='admin_check_vehicles')
@tools_bp.route("/check-vehicles", strict_slashes=False, endpoint='admin_check_vehicles_alias')
@require_roles('administrator', 'manager', 'commercial', 'user')
def admin_check_vehicles():
    """Outil de vérification et protocole des véhicules avec pré-génération différée du PDF."""
    from pathlib import Path
    from flask import current_app
    from services.admin.vehicle_config import get_protocol_data, dispatch_sync_check_vehicles_pdf

    # Pré-génération différée en tâche de fond si le PDF statique est absent
    static_pdf_path = Path(current_app.static_folder) / "pdfs" / "check_vehicles.pdf"
    if not static_pdf_path.exists() or static_pdf_path.stat().st_size < 1000:
        dispatch_sync_check_vehicles_pdf(current_app._get_current_object())

    protocol_data = get_protocol_data()
    return render_template("admin/check_vehicles.html", protocol_data=protocol_data, is_pdf=False)

@tools_bp.route("/tools/check-vehicles/pdf", strict_slashes=False, endpoint='admin_check_vehicles_pdf')
@tools_bp.route("/check-vehicles/pdf", strict_slashes=False, endpoint='admin_check_vehicles_pdf_alias')
@require_roles('administrator', 'manager', 'commercial', 'user')
def admin_check_vehicles_pdf():
    """Sert instantanément le protocole technique des véhicules au format PDF (pré-généré en différé)."""
    from flask import request, send_file, Response, current_app
    from pathlib import Path
    from services.admin.vehicle_config import sync_check_vehicles_static_pdf

    force_refresh = request.args.get("refresh") in ("1", "true") or request.args.get("force") in ("1", "true")
    static_pdf_path = Path(current_app.static_folder) / "pdfs" / "check_vehicles.pdf"

    # 1. Service instantané si le fichier est déjà pré-généré sur disque
    if not force_refresh and static_pdf_path.exists() and static_pdf_path.stat().st_size > 1000:
        return send_file(
            static_pdf_path,
            mimetype="application/pdf",
            as_attachment=False,
            download_name="protocole_controle_technique_belle_vitesse.pdf"
        )

    # 2. Génération synchrone de repli si le fichier est manquant ou rafraîchissement forcé
    sync_check_vehicles_static_pdf(current_app._get_current_object())

    if static_pdf_path.exists() and static_pdf_path.stat().st_size > 1000:
        return send_file(
            static_pdf_path,
            mimetype="application/pdf",
            as_attachment=False,
            download_name="protocole_controle_technique_belle_vitesse.pdf"
        )

    # 3. Repli d'urgence en mémoire
    from services.admin.vehicle_config import get_protocol_data
    from utils.document_utils import render_pdf_from_template

    protocol_data = get_protocol_data()
    html_content = render_template(
        "admin/check_vehicles.html",
        protocol_data=protocol_data,
        is_pdf=True
    )
    pdf_bytes = render_pdf_from_template(
        html_content=html_content,
        base_url=request.host_url,
        stylesheets=["css/admin/admin-check-vehicles.css"],
        filename="protocole_controle_technique_belle_vitesse.pdf",
        continuous=True
    )

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": "inline; filename=protocole_controle_technique_belle_vitesse.pdf"
        }
    )

@tools_bp.route("/api-docs", endpoint='admin_api_docs')
@require_roles('administrator')
def admin_api_docs():
    """Documentation interactive de l'API (Swagger/OpenAPI)."""
    return render_template("admin/api_docs.html")

# ── Documentation Technique (Premium) ─────────────────────────

@tools_bp.route("/docs", endpoint='admin_docs_index')
@require_roles('administrator')
def admin_docs_index():
    """Page d'accueil de la documentation technique."""
    return render_template("admin/docs/index.html")

@tools_bp.route("/docs/<chapter>", endpoint='admin_docs_chapter')
@require_roles('administrator')
def admin_docs_chapter(chapter):
    """Affiche un chapitre spécifique de la documentation."""
    try:
        return render_template(f"admin/docs/{chapter}.html")
    except TemplateNotFound:
        abort(404)



def init_tools_routes(app):
    """Enregistre le blueprint admin_tools (compatibilité ascendante)."""
    if "admin_tools" not in app.blueprints:
        app.register_blueprint(tools_bp)
