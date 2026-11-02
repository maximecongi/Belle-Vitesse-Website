"""
Routes d'administration pour les départs (Check-outs) — couche HTTP légère.

Délègue l'enregistrement des routes au contrôleur factorisé routes.admin.inspections.
"""

from flask import Blueprint
from routes.admin.inspections import register_admin_inspection_routes

checkouts_bp = Blueprint("admin_checkouts", __name__, url_prefix="/admin")
register_admin_inspection_routes(checkouts_bp, "checkout")


def init_checkouts_routes(app):
    """Initialise les routes d'administration pour les départs (Check-outs)."""
    if "admin_checkouts" not in app.blueprints:
        app.register_blueprint(checkouts_bp)

    from utils.decorators import require_preview_access

    @app.route("/preview/pdf/checkout", methods=["GET"], endpoint="preview_pdf_checkout_alias")
    @app.route("/preview/pdf/checkout/<int:record_id>", methods=["GET"], endpoint="preview_pdf_checkout_id_alias")
    @require_preview_access
    def preview_pdf_checkout_alias(record_id=None):
        from routes.admin.inspections import handle_inspection_preview_route
        return handle_inspection_preview_route("checkout", record_id=record_id)


