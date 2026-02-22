"""
Admin routes — thin HTTP layer.

Each handler: parse request → call service → render/redirect.
All business logic lives in services.admin.
"""

from functools import wraps
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
from services.auth import request_magic_link, verify_magic_link


def init_admin_routes(app):
    """Admin authentication, dashboard, CRUD operations, calendar & API."""

    # ── Auth Decorator ────────────────────────────────────────────

    def require_admin(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("admin_authenticated"):
                return redirect(url_for("admin_login", next=request.url))

            # Session repair: if authenticated but missing ID, try to recover it
            if not session.get("admin_user_id") and session.get("admin_user_firstname"):
                try:
                    # If we don't have the email in session yet, we can't easily repair
                    # but we can at least try to find the user by firstname/lastname (risky)
                    # Better: let's ensure email is always in session for next time.
                    pass
                except Exception:
                    pass

            return f(*args, **kwargs)
        return decorated_function

    # ── Login / Logout ────────────────────────────────────────────

    @app.route("/admin/login", methods=["GET", "POST"])
    @limiter.limit("20 per minute")
    def admin_login():
        if session.get("admin_authenticated"):
            return redirect(url_for("admin_dashboard"))

        if request.method == "POST":
            email = request.form.get("email")
            if not email:
                flash("L'adresse email est requise.", "error")
                return render_template("admin/login.html")

            if request_magic_link(email) or email.endswith('@bellevitesse.com'):
                flash("Un lien de connexion vous a été envoyé par email.", "success")

            else:
                flash("Email non reconnu ou erreur d'envoi.", "error")

        return render_template("admin/login.html")

    @app.route("/admin/auth/<token>")
    def admin_verify_magic_link(token):
        user_data = verify_magic_link(token)
        if user_data:
            session.permanent = True
            session["admin_authenticated"] = True
            session["admin_user_id"] = user_data.get("id")
            session["admin_user_firstname"] = user_data.get("firstname", "")
            session["admin_user_lastname"] = user_data.get("lastname", "")
            session["admin_user_role"] = user_data.get("role", "admin")
            session["admin_login_time"] = datetime.now(
                timezone.utc).isoformat()
            flash(
                f"Bienvenue, {user_data.get('firstname', 'Admin')} !", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Lien de connexion invalide ou expiré.", "error")
            return redirect(url_for("admin_login"))

    @app.route("/admin/logout")
    def admin_logout():
        session.pop("admin_authenticated", None)
        session.pop("admin_user_id", None)
        session.pop("admin_user_firstname", None)
        session.pop("admin_user_lastname", None)
        session.pop("admin_user_role", None)
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
            today_iso = datetime.now().strftime('%Y-%m-%d')
            today_checkouts = [p for p in projects_data
                               if p.get("raw_departure_date") == today_iso]
            today_checkins = [p for p in projects_data
                              if p.get("raw_checkin_date") == today_iso]

        except Exception as e:
            current_app.logger.error(f"❌ Error loading dashboard data: {e}")
            today_checkouts = []
            today_checkins = []
            projects_data = []

        return render_template("admin/dashboard.html", today_checkouts=today_checkouts, today_checkins=today_checkins)

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
            from services.checkout import generate_signing_token

            result = generate_signing_token(record_id)
            if not result:
                flash(
                    "Checkout introuvable ou erreur lors de la création du lien de signature.", "error")
                return redirect(url_for("admin_checkout_detail", record_id=record_id))

            token = result["token"]

            flash("La demande de scellement a été initiée et vous avez été redirigé vers la page de signature.", "success")
            return redirect(url_for("checkout_sign_page", token=token))

        except Exception as e:
            current_app.logger.error(f"❌ Error sealing checkout: {e}")
            flash(
                f"Erreur technique lors de la création du lien de signature : {str(e)}", "error")
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
            today_iso = datetime.now().strftime('%Y-%m-%d')
            upcoming_projects = [p for p in projects
                                 if p.get("raw_return_date") >= today_iso]
            past_projects = [p for p in projects
                             if p.get("raw_return_date") < today_iso]
            return render_template("admin/projects_list.html", upcoming_projects=upcoming_projects, past_projects=past_projects)
        except Exception as e:
            current_app.logger.error(f"❌ Error in admin_projects_list: {e}")
            flash("Erreur lors de la récupération des projets.", "error")
            return render_template("admin/projects_list.html", upcoming_projects=[], past_projects=[])

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
