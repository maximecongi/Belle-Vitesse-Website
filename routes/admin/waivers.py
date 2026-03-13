import os
from flask import render_template, flash, redirect, url_for, request


from utils.decorators import require_roles
from services.admin.waivers import (
    list_pilot_waivers, generate_pilot_waiver, send_pilot_waiver, reset_pilot_waiver, create_pilot_waiver,
    list_production_waivers, generate_production_waiver, send_production_waiver, reset_production_waiver, create_production_waiver
)
from models import PilotWaiver, ProductionWaiver, Project


def init_waivers_routes(app):
    # --- PILOT WAIVERS ---
    # ... existing pilot routes ...
    @app.route("/admin/waivers/pilots/new", methods=["GET", "POST"], endpoint='admin_pilot_waiver_new')
    @require_roles('administrator', 'manager')
    def admin_pilot_waiver_new():
        if request.method == "POST":
            project_id = request.form.get("project_id")
            if not project_id:
                flash("Veuillez sélectionner un projet.", "error")
            else:
                success, msg = create_pilot_waiver(project_id)
                if success:
                    flash(msg, "success")
                    return redirect(url_for('admin_pilot_waivers_list'))
                flash(msg, "error")

        from models import PilotWaiver as PW
        projects_with_waiver = [w.project_id for w in PW.query.all()]
        available_projects = Project.query.filter(
            ~Project.id.in_(projects_with_waiver)).all()
        return render_template("admin/pilot_wai_form.html" if os.path.exists("templates/admin/pilot_wai_form.html") else "admin/pilot_waiver_form.html", projects=available_projects)

    @app.route("/admin/waivers/pilots", endpoint='admin_pilot_waivers_list')
    @require_roles('administrator', 'manager')
    def admin_pilot_waivers_list():
        waivers = list_pilot_waivers()
        return render_template("admin/pilots_waivers_list.html", waivers=waivers)

    @app.route("/admin/waivers/pilots/<string:waiver_id>/generate", methods=["POST"], endpoint='admin_pilot_waiver_generate')
    @require_roles('administrator', 'manager')
    def admin_pilot_waiver_generate(waiver_id):
        success, msg = generate_pilot_waiver(waiver_id)
        if success:
            flash(msg, "success")
        else:
            flash(msg, "error")
        return redirect(url_for('admin_pilot_waivers_list'))

    @app.route("/admin/waivers/pilots/<string:waiver_id>/send", methods=["POST"], endpoint='admin_pilot_waiver_send')
    @require_roles('administrator', 'manager')
    def admin_pilot_waiver_send(waiver_id):
        success, msg = send_pilot_waiver(waiver_id)
        if success:
            flash(msg, "success")
        else:
            flash(msg, "error")
        return redirect(url_for('admin_pilot_waivers_list'))

    @app.route("/admin/waivers/pilots/<string:waiver_id>/preview", endpoint='admin_pilot_waiver_preview')
    @require_roles('administrator', 'manager')
    def admin_pilot_waiver_preview(waiver_id):
        waiver = PilotWaiver.query.filter_by(
            waiver_id=waiver_id).first_or_404()
        return render_template("pdf/pilot_waiver_pdf.html", waiver=waiver)

    @app.route("/admin/waivers/pilots/<string:waiver_id>/reset", methods=["POST"], endpoint='admin_pilot_waiver_reset')
    @require_roles('administrator', 'manager')
    def admin_pilot_waiver_reset(waiver_id):
        success, msg = reset_pilot_waiver(waiver_id)
        if success:
            flash(msg, "success")
        else:
            flash(msg, "error")
        return redirect(url_for('admin_pilot_waivers_list'))

    # --- PRODUCTION WAIVERS ---

    @app.route("/admin/waivers/productions/new", methods=["GET", "POST"], endpoint='admin_production_waiver_new')
    @require_roles('administrator', 'manager')
    def admin_production_waiver_new():
        if request.method == "POST":
            project_id = request.form.get("project_id")
            if not project_id:
                flash("Veuillez sélectionner un projet.", "error")
            else:
                success, msg = create_production_waiver(project_id)
                if success:
                    flash(msg, "success")
                    return redirect(url_for('admin_production_waivers_list'))
                flash(msg, "error")

        from models import ProductionWaiver as PW
        projects_with_waiver = [w.project_id for w in PW.query.all()]
        available_projects = Project.query.filter(
            ~Project.id.in_(projects_with_waiver)).all()
        return render_template("admin/production_waiver_form.html", projects=available_projects)

    @app.route("/admin/waivers/productions", endpoint='admin_production_waivers_list')
    @require_roles('administrator', 'manager')
    def admin_production_waivers_list():
        waivers = list_production_waivers()
        return render_template("admin/productions_waivers_list.html", waivers=waivers)

    @app.route("/admin/waivers/productions/<string:waiver_id>/generate", methods=["POST"], endpoint='admin_production_waiver_generate')
    @require_roles('administrator', 'manager')
    def admin_production_waiver_generate(waiver_id):
        success, msg = generate_production_waiver(waiver_id)
        if success:
            flash(msg, "success")
        else:
            flash(msg, "error")
        return redirect(url_for('admin_production_waivers_list'))

    @app.route("/admin/waivers/productions/<string:waiver_id>/send", methods=["POST"], endpoint='admin_production_waiver_send')
    @require_roles('administrator', 'manager')
    def admin_production_waiver_send(waiver_id):
        success, msg = send_production_waiver(waiver_id)
        if success:
            flash(msg, "success")
        else:
            flash(msg, "error")
        return redirect(url_for('admin_production_waivers_list'))

    @app.route("/admin/waivers/productions/<string:waiver_id>/preview", endpoint='admin_production_waiver_preview')
    @require_roles('administrator', 'manager')
    def admin_production_waiver_preview(waiver_id):
        waiver = ProductionWaiver.query.filter_by(
            waiver_id=waiver_id).first_or_404()
        return render_template("pdf/production_waiver_pdf.html", waiver=waiver)

    @app.route("/admin/waivers/productions/<string:waiver_id>/reset", methods=["POST"], endpoint='admin_production_waiver_reset')
    @require_roles('administrator', 'manager')
    def admin_production_waiver_reset(waiver_id):
        success, msg = reset_production_waiver(waiver_id)
        if success:
            flash(msg, "success")
        else:
            flash(msg, "error")
        return redirect(url_for('admin_production_waivers_list'))
