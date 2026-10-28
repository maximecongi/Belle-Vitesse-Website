from functools import wraps
import os

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for, current_app, Response

from models import (
    CglWaiver,
    SafetyRulesWaiver,
    Project,
)
from services.admin.waivers import (
    create_cgl,
    create_safety_rules_waiver,
    delete_cgl,
    delete_safety_rules_waiver,
    generate_cgl,
    generate_safety_rules_waiver,
    get_or_create_waiver_signing_url,
    list_cgl,
    list_safety_rules_waivers,
    reset_cgl,
    reset_safety_rules_waiver,
    send_cgl,
    send_safety_rules_waiver,
    countersign_safety_rules,
)
from utils.decorators import require_roles

waivers_bp = Blueprint('admin_waivers', __name__, url_prefix='/admin')


def require_preview_access(f):
    """
    Autorise l'accès direct en dev/testing sans login pour faciliter l'ajustement CSS/live-reload des PDF.
    En production, restreint l'accès aux utilisateurs authentifiés avec rôle valide.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_app.config.get("DEBUG") or current_app.config.get("TESTING") or os.environ.get("FLASK_ENV") != "production":
            return f(*args, **kwargs)
        if session.get("admin_authenticated"):
            return f(*args, **kwargs)
        return redirect(url_for("admin_auth.admin_login", next=request.url))
    return decorated


# ── CONDITIONS GÉNÉRALES DE LOCATION (CGL - BVRA) ────────────────────

@waivers_bp.route("/cgl/quick-create/<int:project_id>", methods=["GET", "POST"], endpoint='admin_cgl_quick_create')
@require_roles('administrator', 'manager', 'commercial')
def admin_cgl_quick_create(project_id):
    """Création en 1 clic des CGL depuis la fiche projet ou le dashboard."""
    success, msg = create_cgl(project_id)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    return_to = request.form.get("return_to") or request.args.get("return_to") or request.referrer
    if return_to:
        return redirect(return_to)
    return redirect(url_for('admin_projects.admin_project_detail', record_id=project_id))


@waivers_bp.route("/cgl/new", methods=["GET", "POST"], endpoint='admin_cgl_new')
@require_roles('administrator', 'manager', 'commercial')
def admin_cgl_new():
    if request.method == "POST":
        project_id = request.form.get("project_id")
        return_to = request.form.get("return_to") or request.args.get("return_to")
        if not project_id:
            flash("Veuillez sélectionner un projet.", "error")
        else:
            success, msg = create_cgl(project_id)
            if success:
                flash(msg, "success")
                if return_to:
                    return redirect(return_to)
                return redirect(url_for('admin_waivers.admin_cgl_list'))
            flash(msg, "error")

    from models import CglWaiver as CW
    projects_with_cgl = [w.project_id for w in CW.query.filter(CW.deleted_at == None).all()]
    available_projects = Project.query.filter(
        Project.deleted_at == None,
        ~Project.id.in_(projects_with_cgl)
    ).order_by(Project.departure_date.desc(), Project.name.asc()).all()

    projects_data = []
    for p in available_projects:
        prod_name = p.production.name if p.production else ""
        contact_name = f"{p.production_contact.first_name} {p.production_contact.last_name}".strip() if p.production_contact else ""
        dates = ""
        if p.shoot_start_date and p.shoot_end_date:
            dates = f"{p.shoot_start_date.strftime('%d/%m/%Y')} au {p.shoot_end_date.strftime('%d/%m/%Y')}"
        elif p.departure_date:
            dates = f"Départ : {p.departure_date.strftime('%d/%m/%Y')}"

        search_tokens = f"{p.name} {prod_name} {contact_name} {dates}".lower()
        projects_data.append({
            "id": p.id,
            "name": p.name,
            "production": prod_name or "Sans production",
            "contact": contact_name,
            "dates": dates or "Dates non définies",
            "search": search_tokens
        })

    return render_template("admin/cgl_form.html", projects=available_projects, projects_json=projects_data)


@waivers_bp.route("/cgl", endpoint='admin_cgl_list')
@require_roles('administrator', 'manager', 'commercial')
def admin_cgl_list():
    cgl_items = list_cgl()
    q = request.args.get('q', '').strip().lower()
    if q:
        cgl_items = [
            w for w in cgl_items
            if q in (w.get('waiver_id') or '').lower()
            or q in (w.get('project_name') or '').lower()
            or q in (w.get('production_name') or '').lower()
            or q in (w.get('production_contact_name') or '').lower()
            or q in str(w.get('db_id') or '')
        ]
    return render_template("admin/cgl_list.html", cgl_items=cgl_items)


@waivers_bp.route("/cgl/<string:waiver_id>/generate", methods=["POST"], endpoint='admin_cgl_generate')
@require_roles('administrator', 'manager', 'commercial')
def admin_cgl_generate(waiver_id):
    success, msg = generate_cgl(waiver_id)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    q = request.args.get('q', '')
    return redirect(url_for('admin_waivers.admin_cgl_list', q=q if q else None))


@waivers_bp.route("/cgl/<string:waiver_id>/send", methods=["GET", "POST"], endpoint='admin_cgl_send')
@require_roles('administrator', 'manager', 'commercial')
def admin_cgl_send(waiver_id):
    success, msg = send_cgl(waiver_id)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    return_to = request.form.get("return_to") or request.args.get("return_to") or request.referrer
    if return_to:
        return redirect(return_to)
    q = request.args.get('q', '')
    return redirect(url_for('admin_waivers.admin_cgl_list', q=q if q else None))


@waivers_bp.route("/cgl/preview", methods=["GET"], endpoint='admin_cgl_preview_direct')
@waivers_bp.route("/preview/pdf/cgl", methods=["GET"], endpoint='admin_cgl_preview_alias')
@waivers_bp.route("/cgl/<string:waiver_id>/preview", methods=["GET"], endpoint='admin_cgl_preview')
@require_preview_access
def admin_cgl_preview(waiver_id=None):
    """
    Prévisualisation directe du PDF CGL pour ajustement du design/CSS en direct.
    Si waiver_id est absent ou introuvable, injecte un mock représentatif complet.
    Supporte ?format=pdf pour compiler et servir le PDF WeasyPrint.
    """
    waiver = None
    target_id = waiver_id or request.args.get("waiver_id")
    if target_id:
        waiver = CglWaiver.query.filter(
            CglWaiver.waiver_id == target_id,
            CglWaiver.deleted_at.is_(None)
        ).first()

    if not waiver:
        from services.admin.waivers.mock_data import MockCglWaiver
        waiver = MockCglWaiver()

    from models import AppSetting
    company_name = AppSetting.get("company_name", "Belle Vitesse SAS")
    is_pdf_format = request.args.get("format") == "pdf"
    html_content = render_template(
        "pdf/cgl.html",
        cgl=waiver,
        waiver=waiver,
        company_name=company_name,
        company_representative=AppSetting.get("company_representative", "Maxime Congi"),
        company_siret=AppSetting.get("company_siret", "912 345 678 00012"),
        company_vat=AppSetting.get("company_vat", "FR 12 912345678"),
        company_address=AppSetting.get("company_address", "15 Rue de Turbigo, 75002 Paris"),
        company_capital=AppSetting.get("company_capital", "10 000 €"),
        company_rcs=AppSetting.get("company_rcs", "RCS Paris 912 345 678"),
        company_email=AppSetting.get("company_email", "contact@bellevitesse.com"),
        company_phone=AppSetting.get("company_phone", "+33 1 84 25 00 00"),
        is_preview=(not is_pdf_format),
    )

    if is_pdf_format:
        from utils.document_utils import render_pdf_from_template
        pdf_bytes = render_pdf_from_template(
            html_content=html_content,
            base_url=current_app.root_path,
            stylesheets=["css/styles.css", "css/admin/cgl-pdf.css"],
        )
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"inline; filename=cgl_preview_{waiver.waiver_id}.pdf"}
        )

    return html_content



@waivers_bp.route("/cgl/<string:waiver_id>/delete", methods=["POST"], endpoint='admin_cgl_delete')
@require_roles('administrator', 'manager', 'commercial')
def admin_cgl_delete(waiver_id):
    success, msg = delete_cgl(waiver_id)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    q = request.args.get('q', '')
    return redirect(url_for('admin_waivers.admin_cgl_list', q=q if q else None))


@waivers_bp.route("/cgl/<string:waiver_id>/reset", methods=["POST"], endpoint='admin_cgl_reset')
@require_roles('administrator', 'manager', 'commercial')
def admin_cgl_reset(waiver_id):
    success, msg = reset_cgl(waiver_id)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    q = request.args.get('q', '')
    return redirect(url_for('admin_waivers.admin_cgl_list', q=q if q else None))


@waivers_bp.route("/cgl/<string:waiver_id>/copy-link", methods=["POST"], endpoint='admin_cgl_copy_link')
@require_roles('administrator', 'manager', 'commercial')
def admin_cgl_copy_link(waiver_id):
    """Génère ou récupère l'URL de signature active pour les CGL."""
    success, result = get_or_create_waiver_signing_url(waiver_id, waiver_type="cgl")
    if not success:
        return jsonify({"success": False, "error": result}), 400
    return jsonify({"success": True, "url": result})


# ── RÈGLES DE SÉCURITÉ UNIVERSELLES (BVSR) ───────────────────────────

@waivers_bp.route("/safety-rules", endpoint='admin_safety_rules_list')
@waivers_bp.route("/waivers/safety-rules", endpoint='admin_safety_rules_list_alias')
@require_roles('administrator', 'manager', 'commercial')
def admin_safety_rules_list():
    """Liste globale de tous les engagements de sécurité signés ou en attente."""
    items = list_safety_rules_waivers()
    q = request.args.get('q', '').strip().lower()
    if q:
        items = [
            w for w in items
            if q in (w.get('waiver_id') or '').lower()
            or q in (w.get('project_name') or '').lower()
            or q in (w.get('signer_name') or '').lower()
            or q in (w.get('signer_email') or '').lower()
            or q in (w.get('signer_role_label') or '').lower()
            or q in str(w.get('db_id') or '')
        ]
    return render_template("admin/safety_rules_list.html", safety_rules_items=items)


@waivers_bp.route("/projects/<int:project_id>/safety-rules/create", methods=["POST"], endpoint='admin_safety_rules_create')
@require_roles('administrator', 'manager', 'commercial')
def admin_safety_rules_create(project_id):
    """Création d'un nouvel engagement aux règles de sécurité (BVSR) pour un intervenant."""
    signer_role = request.form.get("signer_role", "pilot").strip()
    signer_role_custom = request.form.get("signer_role_custom", "").strip()
    signer_first_name = request.form.get("signer_first_name", "").strip()
    signer_last_name = request.form.get("signer_last_name", "").strip()
    signer_email = request.form.get("signer_email", "").strip()
    signer_phone = request.form.get("signer_phone", "").strip()
    signer_company = request.form.get("signer_company", "").strip()
    safety_technicians = request.form.get("safety_technicians", "").strip()

    success, msg = create_safety_rules_waiver(
        project_id=project_id,
        signer_role=signer_role,
        signer_role_custom=signer_role_custom,
        signer_first_name=signer_first_name,
        signer_last_name=signer_last_name,
        signer_email=signer_email,
        signer_phone=signer_phone,
        signer_company=signer_company,
        safety_technicians=safety_technicians,
    )
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")

    return_to = request.form.get("return_to") or request.args.get("return_to") or request.referrer
    if return_to:
        return redirect(return_to)
    return redirect(url_for('admin_projects.admin_project_detail', record_id=project_id))


@waivers_bp.route("/safety-rules/<string:waiver_id>/send", methods=["GET", "POST"], endpoint='admin_safety_rules_send')
@require_roles('administrator', 'manager', 'commercial')
def admin_safety_rules_send(waiver_id):
    success, msg = send_safety_rules_waiver(waiver_id)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    return_to = request.form.get("return_to") or request.args.get("return_to") or request.referrer
    if return_to:
        return redirect(return_to)
    return redirect(url_for('admin_waivers.admin_safety_rules_list'))


@waivers_bp.route("/safety-rules/<string:waiver_id>/delete", methods=["POST"], endpoint='admin_safety_rules_delete')
@require_roles('administrator', 'manager', 'commercial')
def admin_safety_rules_delete(waiver_id):
    success, msg = delete_safety_rules_waiver(waiver_id)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    return_to = request.form.get("return_to") or request.args.get("return_to") or request.referrer
    if return_to:
        return redirect(return_to)
    return redirect(url_for('admin_waivers.admin_safety_rules_list'))


@waivers_bp.route("/safety-rules/<string:waiver_id>/reset", methods=["POST"], endpoint='admin_safety_rules_reset')
@require_roles('administrator', 'manager', 'commercial')
def admin_safety_rules_reset(waiver_id):
    success, msg = reset_safety_rules_waiver(waiver_id)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    return_to = request.form.get("return_to") or request.args.get("return_to") or request.referrer
    if return_to:
        return redirect(return_to)
    return redirect(url_for('admin_waivers.admin_safety_rules_list'))


@waivers_bp.route("/safety-rules/<string:waiver_id>/copy-link", methods=["POST"], endpoint='admin_safety_rules_copy_link')
@require_roles('administrator', 'manager', 'commercial')
def admin_safety_rules_copy_link(waiver_id):
    success, result = get_or_create_waiver_signing_url(waiver_id, waiver_type="safety_rules")
    if not success:
        return jsonify({"success": False, "error": result}), 400
    return jsonify({"success": True, "url": result})


@waivers_bp.route("/safety-rules/<string:waiver_id>/countersign", methods=["POST"], endpoint='admin_safety_rules_countersign')
@require_roles('administrator', 'manager', 'commercial')
def admin_safety_rules_countersign(waiver_id):
    """Enregistre la contre-signature du superviseur technique Belle Vitesse."""
    sig_data = request.form.get("signature_data")
    if not sig_data:
        return jsonify({"success": False, "error": "Signature manquante."}), 400

    from utils.signature_storage import validate_base64_png
    valid_sig, sig_err = validate_base64_png(sig_data, min_bytes=100, min_width=50, min_height=20)
    if not valid_sig:
        return jsonify({"success": False, "error": f"Signature invalide : {sig_err}"}), 400

    # L'identité du signataire provient strictement du compte authentifié en session
    admin_fn = session.get("admin_user_firstname") or ""
    admin_ln = session.get("admin_user_lastname") or ""
    session_user_name = f"{admin_fn} {admin_ln}".strip() or session.get("user") or session.get("admin_user_mail") or "Belle Vitesse"

    from utils.request_utils import get_client_ip
    signer_ip = get_client_ip()

    success, msg = countersign_safety_rules(
        waiver_id,
        sig_data,
        signer_name=session_user_name,
        signer_ip=signer_ip,
        user_agent=request.headers.get("User-Agent")
    )
    if success:
        flash(msg, "success")
        return jsonify({"success": True, "message": msg})
    return jsonify({"success": False, "error": msg}), 400


@waivers_bp.route("/safety-rules/preview", methods=["GET"], endpoint='admin_safety_rules_preview_direct')
@waivers_bp.route("/preview/pdf/safety-rules", methods=["GET"], endpoint='admin_safety_rules_preview_alias')
@waivers_bp.route("/safety-rules/<string:waiver_id>/preview", methods=["GET"], endpoint='admin_safety_rules_preview')
@require_preview_access
def admin_safety_rules_preview(waiver_id=None):
    """
    Prévisualisation directe du PDF des Règles de Sécurité (BVSR) pour ajustement du design/CSS en direct.
    Si waiver_id est absent ou introuvable, injecte un mock représentatif complet avec règles bilingues.
    Supporte ?format=pdf pour compiler et servir le PDF WeasyPrint.
    """
    from models import SafetyRulesWaiver as SRW, AppSetting
    from services.admin.safety_rules_config import (
        get_safety_rules_for_vehicles,
        get_general_safety_rules,
        get_merged_general_safety_rules,
        DEFAULT_HELMETS_INVENTORY,
    )

    waiver = None
    target_id = waiver_id or request.args.get("waiver_id")
    if target_id:
        waiver = SRW.query.filter(
            SRW.waiver_id == target_id,
            SRW.deleted_at.is_(None)
        ).first()

    if not waiver:
        from services.admin.waivers.mock_data import MockSafetyRulesWaiver
        waiver = MockSafetyRulesWaiver()

    safety_techs = getattr(waiver, "display_safety_technicians", None) or getattr(waiver, "safety_technicians", "") or None
    general_rules = get_merged_general_safety_rules(safety_techs)
    vehicle_rules = get_safety_rules_for_vehicles(getattr(waiver, "vehicles_details", []))
    helmets = getattr(waiver, "helmets_inventory", None) or DEFAULT_HELMETS_INVENTORY

    is_pdf_format = request.args.get("format") == "pdf"
    html_content = render_template(
        "pdf/safety_rules.html",
        waiver=waiver,
        general_rules=general_rules,
        vehicle_rules=vehicle_rules,
        helmets=helmets,
        safety_technicians=safety_techs,
        bv_signature=getattr(waiver, "bv_signature_data_uri", None),
        company_name=AppSetting.get("company_name", "Belle Vitesse SAS"),
        base_url=request.host_url.rstrip("/"),
        qr_data_uri="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 100 100'><rect width='100' height='100' fill='white'/><rect x='10' y='10' width='25' height='25' fill='black'/><rect x='65' y='10' width='25' height='25' fill='black'/><rect x='10' y='65' width='25' height='25' fill='black'/><rect x='45' y='45' width='10' height='10' fill='black'/></svg>",
        seal_hash=getattr(waiver, "hash", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        is_preview=(not is_pdf_format),
    )

    if is_pdf_format:
        from utils.document_utils import render_pdf_from_template
        pdf_bytes = render_pdf_from_template(
            html_content=html_content,
            base_url=current_app.root_path,
            stylesheets=["css/styles.css", "css/admin/safety-rules-pdf.css"],
        )
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"inline; filename=safety_rules_preview_{waiver.waiver_id}.pdf"}
        )

    return html_content


def init_waivers_routes(app):
    """Enregistre le blueprint admin_waivers et les routes directes de prévisualisation PDF."""
    if "admin_waivers" not in app.blueprints:
        app.register_blueprint(waivers_bp)

    @app.route("/preview/pdf/cgl", methods=["GET"], endpoint="preview_pdf_cgl_alias")
    @require_preview_access
    def preview_pdf_cgl_alias():
        return admin_cgl_preview()

    @app.route("/preview/pdf/safety-rules", methods=["GET"], endpoint="preview_pdf_safety_rules_alias")
    @require_preview_access
    def preview_pdf_safety_rules_alias():
        return admin_safety_rules_preview()

