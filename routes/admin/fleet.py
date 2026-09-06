"""
Routes d'administration pour la flotte et l'historique des véhicules Belle Vitesse.
Fournit la vue du parc (/admin/fleet) et la timeline détaillée par véhicule (/admin/fleet/<vehicle_id>).
"""

import logging
from flask import abort, flash, redirect, render_template, request, url_for
from services.admin.fleet import get_fleet_overview, get_vehicle_timeline
from utils.decorators import require_roles

logger = logging.getLogger(__name__)


def init_fleet_routes(app):
    """Initialise les routes d'administration du parc et de la timeline flotte."""

    @app.route("/admin/fleet", methods=["GET"])
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
            return redirect(url_for("admin_dashboard"))

    @app.route("/admin/fleet/<vehicle_id>", methods=["GET"])
    @require_roles("administrator", "manager", "user", "commercial")
    def admin_vehicle_timeline(vehicle_id):
        """Fiche détaillée et timeline chronologique d'un véhicule."""
        try:
            timeline_data = get_vehicle_timeline(vehicle_id)
            if not timeline_data:
                flash("Véhicule introuvable ou inexistant.", "error")
                return redirect(url_for("admin_fleet_list"))

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
            return redirect(url_for("admin_fleet_list"))
