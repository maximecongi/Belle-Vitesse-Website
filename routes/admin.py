"""
Admin routes — thin HTTP layer.

Each handler: parse request → call service → render/redirect.
All business logic lives in services.admin.
"""

import os
import secrets
from functools import wraps
from datetime import datetime, timezone
import requests

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

from utils.formatting import format_date_slash
from extensions import limiter
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


def init_admin_routes(app):
    """Admin authentication, dashboard, CRUD operations, calendar & API."""

    # ── Auth Decorator ────────────────────────────────────────────

    def require_admin(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("admin_authenticated"):
                return redirect(url_for("admin_login", next=request.url))
            return f(*args, **kwargs)
        return decorated_function

    # ── Login / Logout ────────────────────────────────────────────

    @app.route("/admin/login", methods=["GET", "POST"])
    @limiter.limit("5 per minute")
    def admin_login():
        if session.get("admin_authenticated"):
            return redirect(url_for("admin_dashboard"))

        if request.method == "POST":
            password = request.form.get("password")
            expected_password = os.getenv("ADMIN_PASSWORD")

            if not expected_password:
                current_app.logger.error("❌ ADMIN_PASSWORD is not set in .env")
                flash("Erreur de configuration serveur.", "error")
                return render_template("admin/login.html")

            if secrets.compare_digest(password, expected_password):
                session.permanent = True
                session["admin_authenticated"] = True
                session["admin_login_time"] = datetime.now(
                    timezone.utc).isoformat()
                next_page = request.args.get("next")
                return redirect(next_page or url_for("admin_dashboard"))
            else:
                flash("Mot de passe incorrect.", "error")

        return render_template("admin/login.html")

    @app.route("/admin/logout")
    def admin_logout():
        session.pop("admin_authenticated", None)
        session.pop("admin_login_time", None)
        flash("Vous avez été déconnecté.", "info")
        return redirect(url_for("admin_login"))

    # ── Dashboard ─────────────────────────────────────────────────

    @app.route("/admin")
    @app.route("/admin/dashboard")
    @require_admin
    def admin_dashboard():
        try:
            projects_data = list_projects()
            today_projects = [p for p in projects_data
                              if format_date_slash(p["departure_date"]) == datetime.now().strftime('%d/%m/%Y')]

        except Exception as e:
            current_app.logger.error(f"❌ Error loading dashboard data: {e}")
            today_projects = []
            projects_data = []

        return render_template("admin/dashboard.html", today_projects=today_projects)

    # ── Checkouts CRUD ────────────────────────────────────────────

    @app.route("/admin/checkouts")
    @require_admin
    def admin_checkouts_list():
        try:
            result = list_checkouts()
            return render_template(
                "admin/checkouts_list.html",
                checkouts=result["checkouts"],
            )
        except Exception as e:
            current_app.logger.error(f"❌ Error in admin_checkouts_list: {e}")
            flash("Erreur lors de la récupération de la liste.", "error")
            return render_template(
                "admin/checkouts_list.html",
                checkouts=[],
            )

    @app.route("/admin/checkouts/<record_id>")
    @require_admin
    def admin_checkout_detail(record_id):
        try:
            data = get_checkout_detail(record_id)
            if not data:
                abort(404)
            return render_template("admin/checkout_detail.html", data=data, record_id=record_id)
        except Exception as e:
            current_app.logger.error(f"❌ Error in admin_checkout_detail: {e}")
            flash("Erreur lors de la récupération du détail.", "error")
            return redirect(url_for("admin_checkouts_list"))

    @app.route("/admin/checkouts/new", methods=["GET", "POST"])
    @require_admin
    def admin_checkout_new():
        context = get_checkout_form_context()

        initial_data = {}
        if request.method == "GET":
            # Prefill from URL params if provided
            if request.args.get("project_id"):
                initial_data["project_id"] = request.args.get("project_id")
            if request.args.get("vehicle_id"):
                initial_data["vehicle_id"] = request.args.get("vehicle_id")

        if request.method == "POST":
            try:
                create_checkout(request.form, request.files)
                flash("Checkout créé avec succès !", "success")
                return redirect(url_for("admin_checkouts_list"))
            except Exception as e:
                current_app.logger.error(f"❌ Error creating checkout: {e}")
                flash(f"Erreur lors de la création : {str(e)}", "warning")
                return render_template(
                    "admin/checkout_form.html",
                    data=request.form.to_dict(),
                    is_edit=False,
                    **context,
                )

        return render_template("admin/checkout_form.html", data=initial_data, is_edit=False, **context)

    @app.route("/admin/checkouts/<record_id>/edit", methods=["GET", "POST"])
    @require_admin
    def admin_checkout_edit(record_id):
        context = get_checkout_form_context()

        try:
            data = get_checkout_detail(record_id)
            if not data:
                abort(404)

            if request.method == "POST":
                update_checkout(record_id, request.form, request.files)
                flash("Checkout modifié avec succès !", "success")
                return redirect(url_for("admin_checkout_detail", record_id=record_id))

            return render_template(
                "admin/checkout_form.html", data=data, is_edit=True, **context
            )
        except Exception as e:
            current_app.logger.error(f"❌ Error editing checkout: {e}")
            flash(f"Erreur lors de la modification : {str(e)}", "error")
            return redirect(url_for("admin_checkout_detail", record_id=record_id))

    @app.route("/admin/checkouts/<record_id>/delete", methods=["POST"])
    @require_admin
    def admin_checkout_delete(record_id):
        try:
            delete_checkout(record_id)
            flash("Checkout supprimé définitivement.", "success")
            return redirect(url_for("admin_checkouts_list"))
        except Exception as e:
            current_app.logger.error(f"❌ Error deleting checkout: {e}")
            flash(f"Erreur lors de la suppression : {str(e)}", "error")
            return redirect(url_for("admin_checkout_detail", record_id=record_id))

    @app.route("/admin/checkouts/<record_id>/seal", methods=["POST"])
    @require_admin
    def admin_checkout_seal(record_id):
        try:
            webhook_url = os.getenv("N8N_WEBHOOK_CHECKOUT_GENERATE_TOKEN")
            if not webhook_url:
                flash("URL du webhook non configurée dans le fichier .env", "error")
                return redirect(url_for("admin_checkout_detail", record_id=record_id))

            data = get_checkout_detail(record_id)
            if not data:
                flash("Checkout introuvable.", "error")
                return redirect(url_for("admin_checkouts_list"))

            controller_email = data.get("controller", {}).get(
                "mail", "") if isinstance(data.get("controller"), dict) else ""
            inspection_id = data.get("inspection_id", "")

            payload = {
                "record_id": record_id,
                "inspection_id": inspection_id,
                "controller_email": controller_email
            }

            response = requests.post(webhook_url, json=payload, timeout=10)

            if response.status_code in [200, 201]:
                # Update Airtable state immediately so refreshing the page doesn't re-enable the button
                from utils.checkout import TABLE_CHECKOUT
                try:
                    TABLE_CHECKOUT.update(
                        record_id, {"État du contrôle": "À signer"})
                except Exception as update_err:
                    current_app.logger.error(
                        f"❌ Failed to update status to 'À signer': {update_err}")

                flash(
                    "La demande de scellement a été envoyée avec succès au webhook !", "success")
            else:
                flash(
                    f"Le webhook a retourné une erreur {response.status_code}", "warning")

        except Exception as e:
            current_app.logger.error(f"❌ Error sealing checkout: {e}")
            flash(
                f"Erreur technique lors de l'appel au webhook : {str(e)}", "error")

        return redirect(url_for("admin_checkout_detail", record_id=record_id))

# ── Checkins CRUD ────────────────────────────────────────────

    @app.route("/admin/checkins")
    @require_admin
    def admin_checkins_list():
        try:
            result = list_checkins()
            return render_template(
                "admin/checkins_list.html",
                checkins=result["checkins"],
            )
        except Exception as e:
            current_app.logger.error(f"❌ Error in admin_checkins_list: {e}")
            flash("Erreur lors de la récupération de la liste.", "error")
            return render_template(
                "admin/checkins_list.html",
                checkins=[],
            )

    @app.route("/admin/checkins/<record_id>")
    @require_admin
    def admin_checkin_detail(record_id):
        try:
            data = get_checkin_detail(record_id)
            if not data:
                abort(404)
            return render_template("admin/checkin_detail.html", data=data, record_id=record_id)
        except Exception as e:
            current_app.logger.error(f"❌ Error in admin_checkin_detail: {e}")
            flash("Erreur lors de la récupération du détail.", "error")
            return redirect(url_for("admin_checkins_list"))

    @app.route("/admin/checkins/new", methods=["GET", "POST"])
    @require_admin
    def admin_checkin_new():
        context = get_checkin_form_context()

        initial_data = {}
        if request.method == "GET":
            # Prefill from URL params if provided
            if request.args.get("project_id"):
                initial_data["project_id"] = request.args.get("project_id")
            if request.args.get("vehicle_id"):
                initial_data["vehicle_id"] = request.args.get("vehicle_id")

        if request.method == "POST":
            try:
                create_checkin(request.form, request.files)
                flash("Checkin créé avec succès !", "success")
                return redirect(url_for("admin_checkins_list"))
            except Exception as e:
                current_app.logger.error(f"❌ Error creating checkin: {e}")
                flash(f"Erreur lors de la création : {str(e)}", "warning")
                return render_template(
                    "admin/checkin_form.html",
                    data=request.form.to_dict(),
                    is_edit=False,
                    **context,
                )

        return render_template("admin/checkin_form.html", data=initial_data, is_edit=False, **context)

    @app.route("/admin/checkins/<record_id>/edit", methods=["GET", "POST"])
    @require_admin
    def admin_checkin_edit(record_id):
        context = get_checkin_form_context()

        try:
            data = get_checkin_detail(record_id)
            if not data:
                abort(404)

            if request.method == "POST":
                update_checkin(record_id, request.form, request.files)
                flash("Checkin modifié avec succès !", "success")
                return redirect(url_for("admin_checkin_detail", record_id=record_id))

            return render_template(
                "admin/checkin_form.html", data=data, is_edit=True, **context
            )
        except Exception as e:
            current_app.logger.error(f"❌ Error editing checkin: {e}")
            flash(f"Erreur lors de la modification : {str(e)}", "error")
            return redirect(url_for("admin_checkin_detail", record_id=record_id))

    @app.route("/admin/checkins/<record_id>/delete", methods=["POST"])
    @require_admin
    def admin_checkin_delete(record_id):
        try:
            delete_checkin(record_id)
            flash("Checkin supprimé définitivement.", "success")
            return redirect(url_for("admin_checkins_list"))
        except Exception as e:
            current_app.logger.error(f"❌ Error deleting checkin: {e}")
            flash(f"Erreur lors de la suppression : {str(e)}", "error")
            return redirect(url_for("admin_checkin_detail", record_id=record_id))

    @app.route("/admin/checkins/<record_id>/seal", methods=["POST"])
    @require_admin
    def admin_checkin_seal(record_id):
        try:
            from services.checkin import generate_signing_token

            result = generate_signing_token(record_id)
            if not result:
                flash(
                    "Checkin introuvable ou erreur lors de la création du lien de signature.", "error")
                return redirect(url_for("admin_checkin_detail", record_id=record_id))

            token = result["token"]

            # The generate_signing_token already sets status to "À signer"
            flash("La demande de scellement a été initiée et vous avez été redirigé vers la page de signature.", "success")
            return redirect(url_for("checkin_sign_page", token=token))

        except Exception as e:
            current_app.logger.error(f"❌ Error sealing checkin: {e}")
            flash(
                f"Erreur technique lors de la création du lien de signature : {str(e)}", "error")
            return redirect(url_for("admin_checkin_detail", record_id=record_id))


    # ── Projects CRUD ─────────────────────────────────────────────

    @app.route("/admin/projects")
    @require_admin
    def admin_projects_list():
        try:
            projects = list_projects()
            return render_template("admin/projects_list.html", projects=projects)
        except Exception as e:
            current_app.logger.error(f"❌ Error in admin_projects_list: {e}")
            flash("Erreur lors de la récupération des projets.", "error")
            return render_template("admin/projects_list.html", projects=[])

    @app.route("/admin/projects/new", methods=["GET", "POST"])
    @require_admin
    def admin_project_new():
        context = get_project_form_context()

        if request.method == "POST":
            try:
                if not request.form.get("name"):
                    flash("Le nom du projet est requis.", "error")
                    return render_template(
                        "admin/project_form.html", data=request.form, is_edit=False, **context
                    )
                create_project(request.form)
                flash("Projet créé avec succès !", "success")
                return redirect(url_for("admin_projects_list"))
            except Exception as e:
                current_app.logger.error(f"❌ Error creating project: {e}")
                flash(f"Erreur lors de la création : {str(e)}", "error")
                return render_template(
                    "admin/project_form.html", data=request.form, is_edit=False, **context
                )

        return render_template("admin/project_form.html", is_edit=False, **context)

    @app.route("/admin/projects/<record_id>/edit", methods=["GET", "POST"])
    @require_admin
    def admin_project_edit(record_id):
        context = get_project_form_context()

        try:
            if request.method == "POST":
                update_project(record_id, request.form)
                flash("Projet modifié avec succès !", "success")
                return redirect(url_for("admin_projects_list"))

            data = get_project_for_edit(record_id)
            if not data:
                abort(404)
            return render_template("admin/project_form.html", data=data, is_edit=True, **context)
        except Exception as e:
            current_app.logger.error(f"❌ Error editing project: {e}")
            flash(f"Erreur lors de la modification : {str(e)}", "error")
            return redirect(url_for("admin_projects_list"))

    @app.route("/admin/projects/<record_id>/delete", methods=["POST"])
    @require_admin
    def admin_project_delete(record_id):
        try:
            delete_project(record_id)
            flash("Projet supprimé avec succès.", "success")
            return redirect(url_for("admin_projects_list"))
        except Exception as e:
            current_app.logger.error(f"❌ Error deleting project: {e}")
            flash(f"Erreur lors de la suppression : {str(e)}", "error")
            return redirect(url_for("admin_project_edit", record_id=record_id))

    # ── Productions CRUD ──────────────────────────────────────────

    @app.route("/admin/productions")
    @require_admin
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
    @require_admin
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
    @require_admin
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
    @require_admin
    def admin_production_delete(record_id):
        try:
            delete_production(record_id)
            flash("Production supprimée avec succès.", "success")
            return redirect(url_for("admin_productions_list"))
        except Exception as e:
            current_app.logger.error(f"❌ Error deleting production: {e}")
            flash(f"Erreur lors de la suppression : {str(e)}", "error")
            return redirect(url_for("admin_productions_list"))

    # ── Admin API ─────────────────────────────────────────────────

    @app.route("/admin/api/events")
    @require_admin
    def admin_api_events():
        try:
            events = get_calendar_events()
            return jsonify(events)
        except Exception as e:
            current_app.logger.error(f"❌ Error in admin_api_events: {e}")
            return jsonify([]), 500

    @app.route("/admin/api/stats")
    @require_admin
    def admin_api_stats():
        try:
            stats = get_checkout_stats()
            return jsonify(stats)
        except Exception as e:
            current_app.logger.error(f"❌ Error in admin_api_stats: {e}")
            return jsonify({"error": str(e)}), 500
