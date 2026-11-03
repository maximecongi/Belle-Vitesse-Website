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
    """Gestion et personnalisation des règles de sécurité (générales et par véhicule) dans la configuration de flotte."""
    from services.admin.safety_rules_config import (
        get_all_vehicle_safety_rules_catalog,
        save_vehicle_safety_rules,
        get_general_safety_rules,
        save_general_safety_rules,
        get_bv_referents_safety_rules,
        save_bv_referents_safety_rules,
        get_safety_equipment_catalog,
        save_safety_equipment_catalog,
    )
    if request.method == "POST":
        rule_scope = request.form.get("rule_scope", "").strip()
        is_general = request.form.get("is_general") in ("1", "true", "True") or rule_scope == "general"
        is_bv_referents = request.form.get("is_bv_referents") in ("1", "true", "True") or rule_scope == "bv_referents"
        is_equipment_catalog = request.form.get("is_equipment_catalog") in ("1", "true", "True") or rule_scope == "equipment_catalog"

        if is_equipment_catalog:
            eq_ids = request.form.getlist("equipment_id[]") or request.form.getlist("equipment_id")
            eq_frs = request.form.getlist("equipment_fr[]") or request.form.getlist("equipment_fr")
            eq_ens = request.form.getlist("equipment_en[]") or request.form.getlist("equipment_en")
            max_len = max(len(eq_ids), len(eq_frs), len(eq_ens))
            items = []
            for i in range(max_len):
                cid = eq_ids[i].strip() if i < len(eq_ids) else ""
                cfr = eq_frs[i].strip() if i < len(eq_frs) else ""
                cen = eq_ens[i].strip() if i < len(eq_ens) else ""
                if cfr or cen:
                    items.append({"id": cid, "label_fr": cfr, "label_en": cen})
            ok = save_safety_equipment_catalog(items)
            if ok:
                flash("Catalogue d'équipements de sécurité enregistré avec succès.", "success")
            else:
                flash("Erreur lors de l'enregistrement du catalogue d'équipements.", "error")
            return redirect(url_for("admin_fleet.admin_safety_rules_config"))

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

        if is_bv_referents:
            ok = save_bv_referents_safety_rules(rules_fr=rules_fr, rules_en=rules_en)
            if ok:
                flash("Règles spécifiques aux Référents Plateau BV enregistrées avec succès.", "success")
            else:
                flash("Erreur lors de l'enregistrement des règles Référents Plateau BV.", "error")
        elif is_general:
            ok = save_general_safety_rules(rules_fr=rules_fr, rules_en=rules_en)
            if ok:
                flash("Règles générales de sécurité enregistrées avec succès.", "success")
            else:
                flash("Erreur lors de l'enregistrement des règles générales de sécurité.", "error")
        else:
            vehicle_id = request.form.get("vehicle_id", "").strip() or request.form.get("vehicle_key", "").strip()
            label = request.form.get("label", "").strip()
            checked_equipment_ids = request.form.getlist("equipment_ids[]") or request.form.getlist("equipment_ids")

            if not vehicle_id:
                flash("Identifiant de véhicule manquant.", "error")
            else:
                ok = save_vehicle_safety_rules(
                    vehicle_id=vehicle_id,
                    rules_fr=rules_fr,
                    rules_en=rules_en,
                    label=label,
                    equipment_ids=checked_equipment_ids,
                )
                if ok:
                    flash(f"Règles et équipements de sécurité pour « {label or vehicle_id} » enregistrés avec succès.", "success")
                else:
                    flash("Erreur lors de l'enregistrement des règles de sécurité.", "error")
        return redirect(url_for("admin_fleet.admin_safety_rules_config"))

    catalog = get_all_vehicle_safety_rules_catalog()
    general_rules = get_general_safety_rules()
    bv_referents_rules = get_bv_referents_safety_rules()
    equipment_catalog = get_safety_equipment_catalog()
    return render_template(
        "admin/safety_rules_catalog.html",
        catalog=catalog,
        general_rules=general_rules,
        bv_referents_rules=bv_referents_rules,
        equipment_catalog=equipment_catalog,
    )


def init_fleet_routes(app):
    """Enregistre le blueprint de la flotte admin (compatibilité ascendante)."""
    if "admin_fleet" not in app.blueprints:
        app.register_blueprint(fleet_bp)

