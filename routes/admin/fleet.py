"""
Routes d'administration pour la flotte et l'historique des véhicules Belle Vitesse.
Fournit la vue du parc (/admin/fleet) et la timeline détaillée par véhicule (/admin/fleet/<vehicle_id>).
"""

import logging
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
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


def _pair_bilingual_rules(rules_fr_list, rules_en_list):
    """Apparie les consignes FR/EN ligne par ligne.

    Seules les lignes entièrement vides (FR et EN) sont retirées, afin qu'une
    traduction EN manquante ne décale pas les paires suivantes. Une seule
    valeur multiligne (ancien textarea) est découpée par lignes.
    """
    rules_fr_list = [r for r in (rules_fr_list or []) if isinstance(r, str)]
    rules_en_list = [r for r in (rules_en_list or []) if isinstance(r, str)]

    if len(rules_fr_list) <= 1 and len(rules_en_list) <= 1:
        rules_fr_list = (rules_fr_list[0] if rules_fr_list else "").split("\n")
        rules_en_list = (rules_en_list[0] if rules_en_list else "").split("\n")

    rules_fr, rules_en = [], []
    for i in range(max(len(rules_fr_list), len(rules_en_list))):
        fr = rules_fr_list[i].strip() if i < len(rules_fr_list) else ""
        en = rules_en_list[i].strip() if i < len(rules_en_list) else ""
        if fr or en:
            rules_fr.append(fr)
            rules_en.append(en)
    return rules_fr, rules_en


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
            return redirect(
                url_for(
                    "admin_fleet.admin_safety_rules_config",
                    _anchor="bvsr-section-equipment",
                )
            )

        # Support de la liste à puces dynamique (rules_fr[] ou rules_fr) ou textarea brut
        rules_fr_list = request.form.getlist("rules_fr[]") or request.form.getlist(
            "rules_fr"
        )
        rules_en_list = request.form.getlist("rules_en[]") or request.form.getlist(
            "rules_en"
        )

        rules_fr, rules_en = _pair_bilingual_rules(rules_fr_list, rules_en_list)

        anchor = None
        if is_bv_referents:
            anchor = "bvsr-section-referents"
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
            anchor = "bvsr-section-general"
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
                anchor = f"bvsr-vehicle-{vehicle_id}"
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
        return redirect(
            url_for("admin_fleet.admin_safety_rules_config", _anchor=anchor)
        )

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


@fleet_bp.route(
    "/fleet/safety-rules/preview",
    methods=["GET"],
    endpoint="admin_safety_rules_protocol_preview",
)
@require_roles("administrator", "manager")
def admin_safety_rules_protocol_preview():
    """Aperçu du protocole BVSR tel qu'il sera signé, pour une sélection de véhicules et de référents.

    Paramètres : ?vehicle=<id> (répétable), ?technicians=<noms séparés par des virgules>,
    ?format=pdf pour obtenir le PDF compilé. Le projet et le signataire sont fictifs.
    """
    from routes.admin.waivers import (
        render_safety_rules_document,
        safety_rules_pdf_response,
    )
    from services.admin.safety_rules_config import get_all_vehicle_safety_rules_catalog
    from services.admin.waivers.mock_data import MockSafetyRulesWaiver

    catalog = get_all_vehicle_safety_rules_catalog()
    selected = [catalog[v] for v in request.args.getlist("vehicle") if v in catalog]
    technicians = request.args.get("technicians", "").strip()

    waiver = MockSafetyRulesWaiver()
    waiver.vehicles_details = [
        {"id": c["id"], "name": c["name"], "slug": ""} for c in selected
    ]
    waiver.vehicles = ", ".join(c["name"] for c in selected)
    waiver.safety_technicians = technicians

    html_content = render_safety_rules_document(waiver, technicians or None)
    if request.args.get("format") == "pdf":
        return safety_rules_pdf_response(html_content, "apercu_protocole_bvsr.pdf")
    return html_content


@fleet_bp.route(
    "/fleet/risk-assessment", methods=["GET", "POST"], endpoint="admin_risk_assessment_config"
)
@require_roles("administrator", "manager")
def admin_risk_assessment_config():
    """Vue d'ensemble et catalogue complet de l'Analyse des Risques (BVRS)."""
    import json
    from services.admin.risk_assessment_config import (
        get_all_vehicle_risk_assessment_catalog,
        get_general_risk_assessment,
        get_risks_stats,
        annotate_translation_status,
        group_risks_by_category,
        save_general_risk_assessment,
        save_vehicle_risk_assessment,
    )

    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "save_general":
            risks_json = request.form.get("risks_json")
            if risks_json:
                try:
                    risks_data = json.loads(risks_json)
                    ok, msg = save_general_risk_assessment(risks_data)
                    flash(msg, "success" if ok else "error")
                except Exception as e:
                    flash(f"Erreur format JSON : {e}", "error")
            return redirect(url_for("admin_fleet.admin_risk_assessment_config"))

        elif action == "save_vehicle":
            vehicle_key = request.form.get("vehicle_key", "").strip()
            risks_json = request.form.get("risks_json")
            label = request.form.get("label", "").strip()
            if vehicle_key and risks_json:
                try:
                    risks_data = json.loads(risks_json)
                    ok, msg = save_vehicle_risk_assessment(
                        vehicle_key, {"label": label, "risks": risks_data}
                    )
                    flash(msg, "success" if ok else "error")
                except Exception as e:
                    flash(f"Erreur format JSON : {e}", "error")
            return redirect(url_for("admin_fleet.admin_risk_assessment_config"))

    general_risks = annotate_translation_status(get_general_risk_assessment())
    general_stats = get_risks_stats(general_risks)
    general_categories = group_risks_by_category(general_risks)

    # Le catalogue indexe un même véhicule sous plusieurs clés (id + clé par défaut) :
    # on ne garde que la première occurrence de chaque véhicule.
    vehicles = []
    seen_ids = set()
    vehicles_stats = {"vehicles": 0, "total": 0, "major": 0, "standard": 0}
    for v_key, v_data in get_all_vehicle_risk_assessment_catalog().items():
        v_id = str(v_data.get("id") or v_key)
        if v_id in seen_ids:
            continue
        seen_ids.add(v_id)
        v_risks = annotate_translation_status(v_data.get("risks", []))
        v_stats = get_risks_stats(v_risks)
        vehicles.append({
            "key": v_key,
            "data": v_data,
            "stats": v_stats,
            "categories": group_risks_by_category(v_risks),
        })
        vehicles_stats["vehicles"] += 1
        for k in ("total", "major", "standard"):
            vehicles_stats[k] += v_stats[k]

    return render_template(
        "admin/risk_assessment_catalog.html",
        general_risks=general_risks,
        general_stats=general_stats,
        general_categories=general_categories,
        vehicles=vehicles,
        vehicles_stats=vehicles_stats,
    )


@fleet_bp.route(
    "/fleet/risk-assessment/edit/general",
    methods=["GET"],
    endpoint="admin_risk_assessment_edit_general",
)
@require_roles("administrator", "manager")
def admin_risk_assessment_edit_general():
    """Écran d'édition Master-Detail des Risques Généraux Travelling."""
    from services.admin.risk_assessment_config import (
        get_general_risk_assessment,
        get_risks_stats,
        annotate_translation_status,
        get_shared_risk_categories,
    )

    general_risks = annotate_translation_status(get_general_risk_assessment())
    stats = get_risks_stats(general_risks)

    return render_template(
        "admin/risk_assessment_edit.html",
        scope="general",
        vehicle_key="",
        vehicle_data=None,
        page_title="Modifier les Risques Généraux",
        risks=general_risks,
        stats=stats,
        categories=get_shared_risk_categories(),
    )


@fleet_bp.route(
    "/fleet/risk-assessment/edit/vehicle/<string:vehicle_key>",
    methods=["GET"],
    endpoint="admin_risk_assessment_edit_vehicle",
)
@require_roles("administrator", "manager")
def admin_risk_assessment_edit_vehicle(vehicle_key):
    """Écran d'édition Master-Detail des Risques Spécifiques par Véhicule."""
    from services.admin.risk_assessment_config import (
        get_all_vehicle_risk_assessment_catalog,
        get_risks_stats,
        annotate_translation_status,
        get_shared_risk_categories,
    )

    catalog = get_all_vehicle_risk_assessment_catalog()
    v_data = catalog.get(vehicle_key)
    if not v_data:
        flash("Véhicule introuvable dans le catalogue des risques.", "error")
        return redirect(url_for("admin_fleet.admin_risk_assessment_config"))

    v_risks = annotate_translation_status(v_data.get("risks", []))
    stats = get_risks_stats(v_risks)

    v_label = v_data.get("label") or v_data.get("name") or vehicle_key
    return render_template(
        "admin/risk_assessment_edit.html",
        scope="vehicle",
        vehicle_key=vehicle_key,
        vehicle_data=v_data,
        page_title=f"Modifier les Risques Spécifiques — {v_label}",
        risks=v_risks,
        stats=stats,
        categories=get_shared_risk_categories(catalog),
    )


@fleet_bp.route(
    "/fleet/risk-assessment/api/save-risk",
    methods=["POST"],
    endpoint="admin_risk_assessment_api_save_risk",
)
@require_roles("administrator", "manager")
def admin_risk_assessment_api_save_risk():
    """Enregistre ou met à jour un risque individuel en AJAX."""
    from services.admin.risk_assessment_config import (
        save_single_risk,
        check_risk_translation_status,
    )

    payload = request.get_json(silent=True) or {}
    scope = payload.get("scope", "general")
    vehicle_key = payload.get("vehicle_key")
    risk_data = payload.get("risk") or {}

    ok, msg, saved_risk, stats = save_single_risk(
        scope, risk_data, vehicle_key=vehicle_key
    )
    if not ok:
        return jsonify({"status": "error", "message": msg}), 400

    saved_risk["_translation_status"] = check_risk_translation_status(saved_risk)
    return jsonify({
        "status": "success",
        "message": msg,
        "risk": saved_risk,
        "stats": stats,
    })


@fleet_bp.route(
    "/fleet/risk-assessment/api/delete-risk",
    methods=["POST"],
    endpoint="admin_risk_assessment_api_delete_risk",
)
@require_roles("administrator", "manager")
def admin_risk_assessment_api_delete_risk():
    """Supprime un risque individuel en AJAX."""
    from services.admin.risk_assessment_config import delete_single_risk

    payload = request.get_json(silent=True) or {}
    scope = payload.get("scope", "general")
    vehicle_key = payload.get("vehicle_key")
    risk_id = payload.get("risk_id")

    ok, msg, stats = delete_single_risk(scope, risk_id, vehicle_key=vehicle_key)
    if not ok:
        return jsonify({"status": "error", "message": msg}), 400

    return jsonify({"status": "success", "message": msg, "stats": stats})


@fleet_bp.route(
    "/fleet/risk-assessment/api/reorder-risks",
    methods=["POST"],
    endpoint="admin_risk_assessment_api_reorder_risks",
)
@require_roles("administrator", "manager")
def admin_risk_assessment_api_reorder_risks():
    """Sauvegarde l'ordre des risques suite à un glisser-déposer."""
    from services.admin.risk_assessment_config import reorder_risks_list

    payload = request.get_json(silent=True) or {}
    scope = payload.get("scope", "general")
    vehicle_key = payload.get("vehicle_key")
    risk_ids = payload.get("risk_ids") or []

    ok, msg = reorder_risks_list(scope, risk_ids, vehicle_key=vehicle_key)
    if not ok:
        return jsonify({"status": "error", "message": msg}), 400

    return jsonify({"status": "success", "message": msg})


def init_fleet_routes(app):
    """Enregistre le blueprint de la flotte admin (compatibilité ascendante)."""
    if "admin_fleet" not in app.blueprints:
        app.register_blueprint(fleet_bp)
