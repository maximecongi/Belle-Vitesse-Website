"""
Routes de départ (Check-out) — couche HTTP légère.

Délègue l'enregistrement des routes au contrôleur factorisé routes.public.inspections.
"""

from routes.public.inspections import public_inspections_bp


def init_checkout_routes(app):
    """Flux de départ public : affichage, génération, signature, vérification, téléchargement."""
    if "public_inspections" not in app.blueprints:
        app.register_blueprint(public_inspections_bp)
