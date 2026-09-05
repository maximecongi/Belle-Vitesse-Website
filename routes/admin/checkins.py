"""
Routes d'administration pour les retours (Check-ins) — couche HTTP légère.

Délègue l'enregistrement des routes au contrôleur factorisé routes.admin.inspections.
"""

from routes.admin.inspections import register_admin_inspection_routes


def init_checkins_routes(app):
    """Initialise les routes d'administration pour les retours (Check-ins)."""
    register_admin_inspection_routes(app, "checkin")
