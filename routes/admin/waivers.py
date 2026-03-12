from flask import render_template, flash, redirect, url_for

from utils.decorators import require_roles
from services.admin.waivers import list_pilot_waivers, generate_pilot_waiver, send_pilot_waiver
from models import PilotWaiver


def init_waivers_routes(app):

    @app.route("/admin/waivers/pilots")
    @require_roles('administrator', 'manager')
    def admin_pilot_waivers_list():
        waivers = list_pilot_waivers()
        return render_template("admin/pilots_waivers_list.html", waivers=waivers)

    @app.route("/admin/waivers/pilots/<int:waiver_id>/generate", methods=["POST"])
    @require_roles('administrator', 'manager')
    def admin_pilot_waiver_generate(waiver_id):
        success, msg = generate_pilot_waiver(waiver_id)
        if success:
            flash(msg, "success")
        else:
            flash(msg, "error")
        return redirect(url_for('admin_pilot_waivers_list'))

    @app.route("/admin/waivers/pilots/<int:waiver_id>/send", methods=["POST"])
    @require_roles('administrator', 'manager')
    def admin_pilot_waiver_send(waiver_id):
        success, msg = send_pilot_waiver(waiver_id)
        if success:
            flash(msg, "success")
        else:
            flash(msg, "error")
        return redirect(url_for('admin_pilot_waivers_list'))

    @app.route("/admin/waivers/pilots/<int:waiver_id>/preview")
    @require_roles('administrator', 'manager')
    def admin_pilot_waiver_preview(waiver_id):
        waiver = PilotWaiver.query.get_or_404(waiver_id)
        return render_template("pdf/pilot_waiver_pdf.html", waiver=waiver)
