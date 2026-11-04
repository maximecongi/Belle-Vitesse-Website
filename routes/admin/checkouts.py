"""
Routes d'administration pour les départs (Check-outs) — couche HTTP légère.

Délègue l'enregistrement des routes au contrôleur factorisé routes.admin.inspections.
"""

from flask import Blueprint
from routes.admin.inspections import register_admin_inspection_routes

checkouts_bp = Blueprint("admin_checkouts", __name__, url_prefix="/admin")
register_admin_inspection_routes(checkouts_bp, "checkout")
