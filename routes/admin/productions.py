from utils.decorators import require_roles
from datetime import datetime, timezone
from flask import (
    render_template,
    abort,
    jsonify,
    request,
    current_app,
    session,
    redirect,
    url_for,
    flash,
)

from extensions import csrf
from extensions import limiter
from utils.mailer import send_newsletter_campaign

from services.admin import (
    list_checkouts,
    get_checkout_detail,
    get_checkout_form_context,
    create_checkout,
    update_checkout,
    delete_checkout,
    list_checkins,
    get_checkin_detail,
    get_checkin_form_context,
    create_checkin,
    update_checkin,
    delete_checkin,
    list_projects,
    get_project_form_context,
    create_project,
    update_project,
    get_project_for_edit,
    delete_project,
    list_productions,
    create_production,
    update_production,
    get_production_for_edit,
    delete_production,
    get_calendar_events,
    get_checkout_stats,
)
from services.auth import request_magic_link, verify_magic_link
from services.newsletter import (
    list_newsletter_subscribers,
    remove_newsletter_subscriber_by_id,
)


def init_productions_routes(app):
    # ── Productions CRUD ──────────────────────────────────────────

    @app.route("/admin/productions")
    @require_roles('administrator', 'manager')
    def admin_productions_list():
        try:
            productions = list_productions()
            return render_template("admin/productions_list.html", productions=productions)
        except Exception as e:
            current_app.logger.error(f"❌ Error fetching productions: {e}")
            flash(
                f"Erreur lors de la récupération des productions : {str(e)}", "error")
            return render_template("admin/productions_list.html", productions=[])

    @app.route("/admin/productions/new", methods=["GET", "POST"])
    @require_roles('administrator', 'manager')
    def admin_production_new():
        if request.method == "POST":
            try:
                create_production(request.form)
                flash("Production créée avec succès !", "success")
                return redirect(url_for("admin_productions_list"))
            except Exception as e:
                current_app.logger.error(f"❌ Error creating production: {e}")
                flash(f"Erreur lors de la création : {str(e)}", "error")
                return render_template(
                    "admin/production_form.html", data=request.form, is_edit=False
                )
        return render_template("admin/production_form.html", is_edit=False)

    @app.route("/admin/productions/<record_id>/edit", methods=["GET", "POST"])
    @require_roles('administrator', 'manager')
    def admin_production_edit(record_id):
        try:
            if request.method == "POST":
                update_production(record_id, request.form)
                flash("Production modifiée avec succès !", "success")
                return redirect(url_for("admin_productions_list"))

            data = get_production_for_edit(record_id)
            if not data:
                abort(404)
            return render_template("admin/production_form.html", data=data, is_edit=True)
        except Exception as e:
            current_app.logger.error(f"❌ Error editing production: {e}")
            flash(f"Erreur lors de la modification : {str(e)}", "error")
            return redirect(url_for("admin_productions_list"))

    @app.route("/admin/productions/<record_id>/delete", methods=["POST"])
    @require_roles('administrator', 'manager')
    def admin_production_delete(record_id):
        try:
            delete_production(record_id)
            flash("Production supprimée avec succès.", "success")
            return redirect(url_for("admin_productions_list"))
        except Exception as e:
            current_app.logger.error(f"❌ Error deleting production: {e}")
            flash(f"Erreur lors de la suppression : {str(e)}", "error")
            return redirect(url_for("admin_productions_list"))

