from flask import render_template, flash, redirect, url_for

from utils.decorators import require_roles
from services.admin.waivers import list_pilot_waivers, generate_pilot_waiver, send_pilot_waiver


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
