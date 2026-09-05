"""
Routes de départ (Check-out) — couche HTTP légère.

Délègue l'enregistrement des routes au contrôleur factorisé routes.public.inspections.
"""

from routes.public.inspections import register_inspection_routes


def init_checkout_routes(app):
    """Flux de départ public : affichage, génération, signature, vérification, téléchargement."""
    register_inspection_routes(app, "checkout")
