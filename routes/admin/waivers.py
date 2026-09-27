import os

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from models import PilotWaiver, ProductionWaiver, Project
from services.admin.waivers import (
    create_pilot_waiver,
    create_production_waiver,
    delete_pilot_waiver,
    delete_production_waiver,
    generate_pilot_waiver,
    generate_production_waiver,
    list_pilot_waivers,
    list_production_waivers,
    reset_pilot_waiver,
    reset_production_waiver,
    send_pilot_waiver,
    send_production_waiver,
)
from utils.decorators import require_roles



waivers_bp = Blueprint('admin_waivers', __name__, url_prefix='/admin')
# --- DÉCHARGES PILOTES ---

@waivers_bp.route("/waivers/pilots/quick-create/<int:project_id>", methods=["GET", "POST"], endpoint='admin_pilot_waiver_quick_create')
@require_roles('administrator', 'manager')
def admin_pilot_waiver_quick_create(project_id):
    """Création en 1 clic d'une décharge pilote depuis la fiche projet ou le dashboard."""
    success, msg = create_pilot_waiver(project_id)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    return_to = request.form.get("return_to") or request.args.get("return_to") or request.referrer
    if return_to:
        return redirect(return_to)
    return redirect(url_for('admin_projects.admin_project_detail', record_id=project_id))


@waivers_bp.route("/waivers/pilots/new", methods=["GET", "POST"], endpoint='admin_pilot_waiver_new')
@require_roles('administrator', 'manager')
def admin_pilot_waiver_new():
    if request.method == "POST":
        project_id = request.form.get("project_id")
        return_to = request.form.get("return_to") or request.args.get("return_to")
        if not project_id:
            flash("Veuillez sélectionner un projet.", "error")
        else:
            success, msg = create_pilot_waiver(project_id)
            if success:
                flash(msg, "success")
                if return_to:
                    return redirect(return_to)
                return redirect(url_for('admin_waivers.admin_pilot_waivers_list'))
            flash(msg, "error")

    from models import PilotWaiver as PW
    projects_with_waiver = [w.project_id for w in PW.query.filter(PW.deleted_at == None).all()]
    available_projects = Project.query.filter(
        Project.deleted_at == None,
        ~Project.id.in_(projects_with_waiver)
    ).order_by(Project.departure_date.desc(), Project.name.asc()).all()

    projects_data = []
    for p in available_projects:
        prod_name = p.production.name if p.production else ""
        pilot_name = f"{p.pilot_contact.first_name} {p.pilot_contact.last_name}".strip() if p.pilot_contact else ""
        dates = ""
        if p.shoot_start_date and p.shoot_end_date:
            dates = f"{p.shoot_start_date.strftime('%d/%m/%Y')} au {p.shoot_end_date.strftime('%d/%m/%Y')}"
        elif p.departure_date:
            dates = f"Départ : {p.departure_date.strftime('%d/%m/%Y')}"

        search_tokens = f"{p.name} {prod_name} {pilot_name} {dates}".lower()
        projects_data.append({
            "id": p.id,
            "name": p.name,
            "production": prod_name or "Sans production",
            "pilot": pilot_name,
            "dates": dates or "Dates non définies",
            "search": search_tokens
        })

    return render_template("admin/pilot_waiver_form.html", projects=available_projects, projects_json=projects_data)

@waivers_bp.route("/waivers/pilots", endpoint='admin_pilot_waivers_list')
@require_roles('administrator', 'manager')
def admin_pilot_waivers_list():
    waivers = list_pilot_waivers()
    q = request.args.get('q', '').strip().lower()
    if q:
        waivers = [
            w for w in waivers
            if q in (w.get('waiver_id') or '').lower()
            or q in (w.get('project_name') or '').lower()
            or q in (w.get('pilot_name') or '').lower()
            or q in str(w.get('db_id') or '')
        ]
    return render_template("admin/pilots_waivers_list.html", waivers=waivers)

@waivers_bp.route("/waivers/pilots/<string:waiver_id>/generate", methods=["POST"], endpoint='admin_pilot_waiver_generate')
@require_roles('administrator', 'manager')
def admin_pilot_waiver_generate(waiver_id):
    success, msg = generate_pilot_waiver(waiver_id)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    q = request.args.get('q', '')
    return redirect(url_for('admin_waivers.admin_pilot_waivers_list', q=q if q else None))

@waivers_bp.route("/waivers/pilots/<string:waiver_id>/send", methods=["GET", "POST"], endpoint='admin_pilot_waiver_send')
@require_roles('administrator', 'manager')
def admin_pilot_waiver_send(waiver_id):
    success, msg = send_pilot_waiver(waiver_id)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    return_to = request.form.get("return_to") or request.args.get("return_to") or request.referrer
    if return_to:
        return redirect(return_to)
    q = request.args.get('q', '')
    return redirect(url_for('admin_waivers.admin_pilot_waivers_list', q=q if q else None))

@waivers_bp.route("/waivers/pilots/<string:waiver_id>/preview", endpoint='admin_pilot_waiver_preview')
@require_roles('administrator', 'manager')
def admin_pilot_waiver_preview(waiver_id):
    waiver = PilotWaiver.query.filter(
        PilotWaiver.waiver_id == waiver_id,
        PilotWaiver.deleted_at.is_(None)
    ).first_or_404()
    return render_template("pdf/pilot_waiver_pdf.html", waiver=waiver)

@waivers_bp.route("/waivers/pilots/<string:waiver_id>/delete", methods=["POST"], endpoint='admin_pilot_waiver_delete')
@waivers_bp.route("/waivers/pilots/<string:waiver_id>/reset", methods=["POST"], endpoint='admin_pilot_waiver_reset')
@require_roles('administrator', 'manager')
def admin_pilot_waiver_delete(waiver_id):
    success, msg = delete_pilot_waiver(waiver_id)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    q = request.args.get('q', '')
    return redirect(url_for('admin_waivers.admin_pilot_waivers_list', q=q if q else None))

# --- DÉCHARGES PRODUCTIONS ---

@waivers_bp.route("/waivers/productions/quick-create/<int:project_id>", methods=["GET", "POST"], endpoint='admin_production_waiver_quick_create')
@require_roles('administrator', 'manager')
def admin_production_waiver_quick_create(project_id):
    """Création en 1 clic d'une décharge production depuis la fiche projet ou le dashboard."""
    success, msg = create_production_waiver(project_id)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    return_to = request.form.get("return_to") or request.args.get("return_to") or request.referrer
    if return_to:
        return redirect(return_to)
    return redirect(url_for('admin_projects.admin_project_detail', record_id=project_id))


@waivers_bp.route("/waivers/productions/new", methods=["GET", "POST"], endpoint='admin_production_waiver_new')
@require_roles('administrator', 'manager')
def admin_production_waiver_new():
    if request.method == "POST":
        project_id = request.form.get("project_id")
        return_to = request.form.get("return_to") or request.args.get("return_to")
        if not project_id:
            flash("Veuillez sélectionner un projet.", "error")
        else:
            success, msg = create_production_waiver(project_id)
            if success:
                flash(msg, "success")
                if return_to:
                    return redirect(return_to)
                return redirect(url_for('admin_waivers.admin_production_waivers_list'))
            flash(msg, "error")

    from models import ProductionWaiver as PW
    projects_with_waiver = [w.project_id for w in PW.query.filter(PW.deleted_at == None).all()]
    available_projects = Project.query.filter(
        Project.deleted_at == None,
        ~Project.id.in_(projects_with_waiver)
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

    return render_template("admin/production_waiver_form.html", projects=available_projects, projects_json=projects_data)

@waivers_bp.route("/waivers/productions", endpoint='admin_production_waivers_list')
@require_roles('administrator', 'manager')
def admin_production_waivers_list():
    waivers = list_production_waivers()
    q = request.args.get('q', '').strip().lower()
    if q:
        waivers = [
            w for w in waivers
            if q in (w.get('waiver_id') or '').lower()
            or q in (w.get('project_name') or '').lower()
            or q in (w.get('production_name') or '').lower()
            or q in (w.get('production_contact_name') or '').lower()
            or q in str(w.get('db_id') or '')
        ]
    return render_template("admin/productions_waivers_list.html", waivers=waivers)

@waivers_bp.route("/waivers/productions/<string:waiver_id>/generate", methods=["POST"], endpoint='admin_production_waiver_generate')
@require_roles('administrator', 'manager')
def admin_production_waiver_generate(waiver_id):
    success, msg = generate_production_waiver(waiver_id)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    q = request.args.get('q', '')
    return redirect(url_for('admin_waivers.admin_production_waivers_list', q=q if q else None))

@waivers_bp.route("/waivers/productions/<string:waiver_id>/send", methods=["GET", "POST"], endpoint='admin_production_waiver_send')
@require_roles('administrator', 'manager')
def admin_production_waiver_send(waiver_id):
    success, msg = send_production_waiver(waiver_id)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    return_to = request.form.get("return_to") or request.args.get("return_to") or request.referrer
    if return_to:
        return redirect(return_to)
    q = request.args.get('q', '')
    return redirect(url_for('admin_waivers.admin_production_waivers_list', q=q if q else None))

@waivers_bp.route("/waivers/productions/<string:waiver_id>/preview", endpoint='admin_production_waiver_preview')
@require_roles('administrator', 'manager')
def admin_production_waiver_preview(waiver_id):
    waiver = ProductionWaiver.query.filter(
        ProductionWaiver.waiver_id == waiver_id,
        ProductionWaiver.deleted_at.is_(None)
    ).first_or_404()
    return render_template("pdf/production_waiver_pdf.html", waiver=waiver)

@waivers_bp.route("/waivers/productions/<string:waiver_id>/delete", methods=["POST"], endpoint='admin_production_waiver_delete')
@waivers_bp.route("/waivers/productions/<string:waiver_id>/reset", methods=["POST"], endpoint='admin_production_waiver_reset')
@require_roles('administrator', 'manager')
def admin_production_waiver_delete(waiver_id):
    success, msg = delete_production_waiver(waiver_id)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    q = request.args.get('q', '')
    return redirect(url_for('admin_waivers.admin_production_waivers_list', q=q if q else None))

def init_waivers_routes(app):
    """Enregistre le blueprint admin_waivers (compatibilité ascendante)."""
    if "admin_waivers" not in app.blueprints:
        app.register_blueprint(waivers_bp)
