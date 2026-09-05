"""
Routes d'administration pour les départs (Check-outs) — couche HTTP légère.

Délègue l'enregistrement des routes au contrôleur factorisé routes.admin.inspections.
"""

from routes.admin.inspections import register_admin_inspection_routes


def init_checkouts_routes(app):
    """Initialise les routes d'administration pour les départs (Check-outs)."""
    register_admin_inspection_routes(app, "checkout")
