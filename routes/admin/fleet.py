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


@fleet_bp.route("/fleet/safety-rules", methods=["GET", "POST"], endpoint="admin_safety_rules_config")
@require_roles("administrator", "manager")
def admin_safety_rules_config():
    """Gestion et personnalisation des règles de sécurité par véhicule dans la configuration de flotte."""
    from services.admin.safety_rules_config import (
        get_all_vehicle_safety_rules_catalog,
        save_vehicle_safety_rules,
    )
    if request.method == "POST":
        vehicle_id = request.form.get("vehicle_id", "").strip() or request.form.get("vehicle_key", "").strip()
        label = request.form.get("label", "").strip()
        # Support de la liste à puces dynamique (rules_fr[] ou rules_fr) ou textarea brut
        rules_fr_list = request.form.getlist("rules_fr[]") or request.form.getlist("rules_fr")
        rules_en_list = request.form.getlist("rules_en[]") or request.form.getlist("rules_en")

        if rules_fr_list and any(r.strip() for r in rules_fr_list if isinstance(r, str)):
            if len(rules_fr_list) == 1 and "\n" in rules_fr_list[0]:
                rules_fr = rules_fr_list[0]
            else:
                rules_fr = [r.strip() for r in rules_fr_list if r.strip()]
        else:
            rules_fr = request.form.get("rules_fr", "")

        if rules_en_list and any(r.strip() for r in rules_en_list if isinstance(r, str)):
            if len(rules_en_list) == 1 and "\n" in rules_en_list[0]:
                rules_en = rules_en_list[0]
            else:
                rules_en = [r.strip() for r in rules_en_list if r.strip()]
        else:
            rules_en = request.form.get("rules_en", "")

        if not vehicle_id:
            flash("Identifiant de véhicule manquant.", "error")
        else:
            ok = save_vehicle_safety_rules(
                vehicle_id=vehicle_id,
                rules_fr=rules_fr,
                rules_en=rules_en,
                label=label,
            )
            if ok:
                flash(f"Règles de sécurité pour « {label or vehicle_id} » enregistrées avec succès.", "success")
            else:
                flash("Erreur lors de l'enregistrement des règles de sécurité.", "error")
        return redirect(url_for("admin_fleet.admin_safety_rules_config"))

    catalog = get_all_vehicle_safety_rules_catalog()
    return render_template("admin/safety_rules_catalog.html", catalog=catalog)


def init_fleet_routes(app):
    """Enregistre le blueprint de la flotte admin (compatibilité ascendante)."""
    if "admin_fleet" not in app.blueprints:
        app.register_blueprint(fleet_bp)

