"""
Routes d'administration pour les retours (Check-ins) — couche HTTP légère.

Délègue l'enregistrement des routes au contrôleur factorisé routes.admin.inspections.
"""

from flask import Blueprint
from routes.admin.inspections import register_admin_inspection_routes

checkins_bp = Blueprint("admin_checkins", __name__, url_prefix="/admin")
register_admin_inspection_routes(checkins_bp, "checkin")


def init_checkins_routes(app):
    """Initialise les routes d'administration pour les retours (Check-ins)."""
    if "admin_checkins" not in app.blueprints:
        app.register_blueprint(checkins_bp)

