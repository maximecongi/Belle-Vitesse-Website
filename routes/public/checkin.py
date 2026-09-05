"""
Routes de retour (Check-in) — couche HTTP légère.

Délègue l'enregistrement des routes au contrôleur factorisé routes.public.inspections.
"""

from routes.public.inspections import register_inspection_routes


def init_checkin_routes(app):
    """Flux de retour public : affichage, génération, signature, vérification, téléchargement."""
    register_inspection_routes(app, "checkin")
