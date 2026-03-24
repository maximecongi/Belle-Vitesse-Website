from flask import render_template

from utils.decorators import require_roles


def init_tools_routes(app):
    """Initialise les routes pour les outils administratifs."""

    @app.route("/admin/tools/signature-generator", endpoint='admin_signature_generator')
    @require_roles('administrator', 'manager', 'user')
    def admin_signature_generator():
        """Outil de génération de signature visuelle."""
        return render_template("admin/signature_generator.html")

    @app.route("/admin/tools/check-vehicles", endpoint='admin_check_vehicles')
    @require_roles('administrator', 'manager', 'user')
    def admin_check_vehicles():
        """Outil de vérification et protocole des véhicules."""
        return render_template("admin/check_vehicles.html")

    @app.route("/admin/api-docs", endpoint='admin_api_docs')
    @require_roles('administrator', 'manager')
    def admin_api_docs():
        """Documentation interactive de l'API (Swagger/OpenAPI)."""
        return render_template("admin/api_docs.html")

    # ── Documentation Technique (Premium) ─────────────────────────

    @app.route("/admin/docs", endpoint='admin_docs_index')
    @require_roles('administrator', 'manager')
    def admin_docs_index():
        """Page d'accueil de la documentation technique."""
        return render_template("admin/docs/index.html")

    @app.route("/admin/docs/<chapter>", endpoint='admin_docs_chapter')
    @require_roles('administrator', 'manager')
    def admin_docs_chapter(chapter):
        """Affiche un chapitre spécifique de la documentation."""
        return render_template(f"admin/docs/{chapter}.html")

