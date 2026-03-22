from datetime import datetime, timezone

from flask import (
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from extensions import limiter
from services.common.auth import request_magic_link, verify_magic_link


def init_auth_routes(app):
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

