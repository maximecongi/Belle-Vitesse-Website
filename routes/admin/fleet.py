"""
Routes d'administration pour la flotte et l'historique des véhicules Belle Vitesse.
Fournit la vue du parc (/admin/fleet) et la timeline détaillée par véhicule (/admin/fleet/<vehicle_id>).
"""

import logging
from flask import Blueprint, flash, redirect, render_template, request, url_for
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
            "admin/fleet_list.html", vehicles=data["vehicles"], stats=data["stats"]
        )
    except Exception as e:
        logger.error(f"❌ Erreur lors du chargement de la flotte : {e}", exc_info=True)
        flash(f"Erreur lors du chargement du parc de véhicules : {e}", "error")
        return redirect(url_for("admin_dashboard.admin_dashboard"))


@fleet_bp.route(
    "/fleet/<vehicle_id>", methods=["GET"], endpoint="admin_vehicle_timeline"
)
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
            stats=timeline_data["stats"],
            public_safety_rules_url=timeline_data.get("public_safety_rules_url"),
            qr_code_base64=timeline_data.get("qr_code_base64"),
        )
    except Exception as e:
        logger.error(
            f"❌ Erreur lors du chargement de la timeline du véhicule {vehicle_id} : {e}",
            exc_info=True,
        )
        flash(f"Erreur lors de l'affichage de l'historique du véhicule : {e}", "error")
        return redirect(url_for("admin_fleet.admin_fleet_list"))


@fleet_bp.route(
    "/fleet/<vehicle_id>/safety-rules/sticker-pdf",
    methods=["GET"],
    endpoint="admin_vehicle_sticker_pdf",
)
@require_roles("administrator", "manager", "user", "commercial")
def admin_vehicle_sticker_pdf(vehicle_id):
    """Génération et téléchargement du sticker PDF (100x50mm) avec QR code haute définition pour le véhicule."""
    try:
        import base64
        from io import BytesIO
        import qrcode
        from flask import make_response
        from routes.public.safety_rules import _resolve_vehicle_data
        from utils.document_utils import render_pdf_from_template
        from utils.request_utils import resolve_base_url

        vehicle_info = _resolve_vehicle_data(vehicle_id)
        if not vehicle_info:
            flash("Véhicule introuvable pour la génération du sticker.", "error")
            return redirect(url_for("admin_fleet.admin_fleet_list"))

        safety_slug = vehicle_info.get("slug")
        if not safety_slug and vehicle_info.get("name"):
            safety_slug = vehicle_info["name"].lower().strip().replace(" ", "-")
        safety_slug = safety_slug or vehicle_id

        base_url = resolve_base_url().rstrip("/")
        public_url = f"{base_url}{url_for('public_safety_rules.view_vehicle_safety_rules', vehicle_id=safety_slug)}"

        # Génération QR code HD (optimisé pour impression 300 DPI)
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=12,
            border=2,
        )
        qr.add_data(public_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        qr_hd_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        rendered_html = render_template(
            "pdf/vehicle_safety_sticker.html",
            vehicle=vehicle_info,
            public_url=public_url,
            qr_hd_base64=qr_hd_base64,
        )

        pdf_bytes = render_pdf_from_template(
            html_content=rendered_html,
            base_url=request.url_root,
            stylesheets=["css/pdf/safety-sticker.css"],
            compress=True,
            filename=f"Sticker-Securite-{vehicle_info['name']}.pdf",
            continuous=False,
            include_base_pdf=False,
        )

        clean_slug = vehicle_info.get("slug") or vehicle_info["name"].replace(" ", "_")
        filename = f"Sticker-Securite-{clean_slug}.pdf"

        response = make_response(pdf_bytes)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        logger.error(
            f"❌ Erreur génération sticker PDF véhicule {vehicle_id} : {e}",
            exc_info=True,
        )
        flash(f"Erreur lors de la génération du sticker PDF : {e}", "error")
        return redirect(
            url_for("admin_fleet.admin_vehicle_timeline", vehicle_id=vehicle_id)
        )


@fleet_bp.route(
    "/fleet/safety-rules", methods=["GET", "POST"], endpoint="admin_safety_rules_config"
)
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
        is_general = (
            request.form.get("is_general") in ("1", "true", "True")
            or rule_scope == "general"
        )
        is_bv_referents = (
            request.form.get("is_bv_referents") in ("1", "true", "True")
            or rule_scope == "bv_referents"
        )
        is_equipment_catalog = (
            request.form.get("is_equipment_catalog") in ("1", "true", "True")
            or rule_scope == "equipment_catalog"
        )

        if is_equipment_catalog:
            eq_ids = request.form.getlist("equipment_id[]") or request.form.getlist(
                "equipment_id"
            )
            eq_frs = request.form.getlist("equipment_fr[]") or request.form.getlist(
                "equipment_fr"
            )
            eq_ens = request.form.getlist("equipment_en[]") or request.form.getlist(
                "equipment_en"
            )
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
                flash(
                    "Catalogue d'équipements de sécurité enregistré avec succès.",
                    "success",
                )
            else:
                flash(
                    "Erreur lors de l'enregistrement du catalogue d'équipements.",
                    "error",
                )
            return redirect(url_for("admin_fleet.admin_safety_rules_config"))

        # Support de la liste à puces dynamique (rules_fr[] ou rules_fr) ou textarea brut
        rules_fr_list = request.form.getlist("rules_fr[]") or request.form.getlist(
            "rules_fr"
        )
        rules_en_list = request.form.getlist("rules_en[]") or request.form.getlist(
            "rules_en"
        )

        if rules_fr_list and any(
            r.strip() for r in rules_fr_list if isinstance(r, str)
        ):
            if len(rules_fr_list) == 1 and "\n" in rules_fr_list[0]:
                rules_fr = rules_fr_list[0]
            else:
                rules_fr = [r.strip() for r in rules_fr_list if r.strip()]
        else:
            rules_fr = request.form.get("rules_fr", "")

        if rules_en_list and any(
            r.strip() for r in rules_en_list if isinstance(r, str)
        ):
            if len(rules_en_list) == 1 and "\n" in rules_en_list[0]:
                rules_en = rules_en_list[0]
            else:
                rules_en = [r.strip() for r in rules_en_list if r.strip()]
        else:
            rules_en = request.form.get("rules_en", "")

        if is_bv_referents:
            ok = save_bv_referents_safety_rules(rules_fr=rules_fr, rules_en=rules_en)
            if ok:
                flash(
                    "Règles spécifiques aux Référents Plateau BV enregistrées avec succès.",
                    "success",
                )
            else:
                flash(
                    "Erreur lors de l'enregistrement des règles Référents Plateau BV.",
                    "error",
                )
        elif is_general:
            ok = save_general_safety_rules(rules_fr=rules_fr, rules_en=rules_en)
            if ok:
                flash(
                    "Règles générales de sécurité enregistrées avec succès.", "success"
                )
            else:
                flash(
                    "Erreur lors de l'enregistrement des règles générales de sécurité.",
                    "error",
                )
        else:
            vehicle_id = (
                request.form.get("vehicle_id", "").strip()
                or request.form.get("vehicle_key", "").strip()
            )
            label = request.form.get("label", "").strip()
            checked_equipment_ids = request.form.getlist(
                "equipment_ids[]"
            ) or request.form.getlist("equipment_ids")

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
                    flash(
                        f"Règles et équipements de sécurité pour « {label or vehicle_id} » enregistrés avec succès.",
                        "success",
                    )
                else:
                    flash(
                        "Erreur lors de l'enregistrement des règles de sécurité.",
                        "error",
                    )
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
