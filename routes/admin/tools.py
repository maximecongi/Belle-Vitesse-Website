from flask import Blueprint, abort, render_template
from jinja2.exceptions import TemplateNotFound

from utils.decorators import require_roles



tools_bp = Blueprint('admin_tools', __name__, url_prefix='/admin')
"""Initialise les routes pour les outils administratifs."""

@tools_bp.route("/tools/signature-generator", endpoint='admin_signature_generator')
@require_roles('administrator', 'manager', 'commercial', 'user')
def admin_signature_generator():
    """Outil de génération de signature visuelle."""
    return render_template("admin/signature_generator.html")

@tools_bp.route("/tools/check-vehicles", endpoint='admin_check_vehicles')
@require_roles('administrator', 'manager', 'commercial', 'user')
def admin_check_vehicles():
    """Outil de vérification et protocole des véhicules."""
    return render_template("admin/check_vehicles.html")

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
