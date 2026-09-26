"""
Routes d'administration pour la flotte et l'historique des véhicules Belle Vitesse.
Fournit la vue du parc (/admin/fleet) et la timeline détaillée par véhicule (/admin/fleet/<vehicle_id>).
"""

import logging
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from services.admin.fleet import get_fleet_overview, get_vehicle_timeline
from utils.decorators import require_roles

logger = logging.getLogger(__name__)

fleet_bp = Blueprint("admin_fleet", __name__, url_prefix="/admin")


@fleet_bp.route("/fleet", methods=["GET"], endpoint="admin_fleet_list")
@require_roles("administrator", "manager", "user", "commercial")
def admin_fleet_list():
    """Tableau de bord de la flotte et état opérationnel du parc."""
    try:
        data = get_fleet_overview()
        return render_template(
            "admin/fleet_list.html",
            vehicles=data["vehicles"],
            stats=data["stats"]
        )
    except Exception as e:
        logger.error(
            f"❌ Erreur lors du chargement de la flotte : {e}", exc_info=True)
        flash(
            f"Erreur lors du chargement du parc de véhicules : {e}", "error")
        return redirect(url_for("admin_dashboard.admin_dashboard"))


@fleet_bp.route("/fleet/<vehicle_id>", methods=["GET"], endpoint="admin_vehicle_timeline")
@require_roles("administrator", "manager", "user", "commercial")
def admin_vehicle_timeline(vehicle_id):
    """Fiche détaillée et timeline chronologique d'un véhicule."""
    try:
        timeline_data = get_vehicle_timeline(vehicle_id)
        if not timeline_data:
            flash("Véhicule introuvable ou inexistant.", "error")
            return redirect(url_for("admin_fleet.admin_fleet_list"))

        return render_template(
            "admin/vehicle_timeline.html",
            vehicle=timeline_data["vehicle"],
            events=timeline_data["events"],
            missions=timeline_data.get("missions", []),
            stats=timeline_data["stats"]
        )
    except Exception as e:
        logger.error(
            f"❌ Erreur lors du chargement de la timeline du véhicule {vehicle_id} : {e}", exc_info=True)
        flash(
            f"Erreur lors de l'affichage de l'historique du véhicule : {e}", "error")
        return redirect(url_for("admin_fleet.admin_fleet_list"))


def init_fleet_routes(app):
    """Enregistre le blueprint de la flotte admin (compatibilité ascendante)."""
    if "admin_fleet" not in app.blueprints:
        app.register_blueprint(fleet_bp)

