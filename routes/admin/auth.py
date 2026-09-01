from datetime import datetime, timezone

from flask import (
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from extensions import cache, limiter
from models import User, db
from services.common.auth import ALLOWED_DOMAINS, request_magic_link, verify_magic_link


def init_auth_routes(app):
    # ── Connexion / Déconnexion ───────────────────────────────────

    @app.route("/admin/login", methods=["GET", "POST"])
    @limiter.limit("20 per minute")
    def admin_login():
        if session.get("admin_authenticated"):
            return redirect(url_for("admin_dashboard"))

        if app.config.get("FLASK_ENV") == "development" and app.config.get("DEBUG") is True:
            dev_user = User.query.first()
            session["admin_authenticated"] = True
            session["admin_user_id"] = dev_user.id if dev_user else None
            session["admin_user_firstname"] = dev_user.firstname if dev_user else "Dev"
            session["admin_user_lastname"] = dev_user.lastname if dev_user else "User"
            session["admin_user_role"] = "super administrator"
            return redirect(url_for("admin_dashboard"))

        if request.method == "POST":
            email = request.form.get("email")
            if not email:
                flash("L'adresse email est requise.", "error")
                return render_template("admin/login.html")

            if request_magic_link(email) or any(email.endswith(d) for d in ALLOWED_DOMAINS):
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

    @app.route("/admin/dev/switch-role", methods=["POST", "GET"], endpoint="admin_dev_switch_role")
    def admin_dev_switch_role():
        """
        Permet de simuler un autre rôle en mode développement/testing sans toucher à la base de données.
        Désactivé en production.
        """
        if app.config.get("FLASK_ENV") == "production":
            flash("Cette fonctionnalité est désactivée en production.", "error")
            return redirect(url_for("admin_dashboard"))

        if not session.get("admin_authenticated"):
            return redirect(url_for("admin_login"))

        target_role = request.values.get("role", "").strip()
        valid_roles = {
            "super administrator": "Super Administrator",
            "administrator": "Administrator",
            "manager": "Manager",
            "commercial": "Commercial",
            "user": "User",
        }

        user_id = session.get("admin_user_id")

        if target_role.lower() in valid_roles:
            new_role = valid_roles[target_role.lower()]
            session["admin_user_role"] = new_role

            if user_id:
                cache.delete(f"user:{user_id}")
                for r in list(valid_roles.keys()) + ["default"]:
                    cache.delete(f"user:{user_id}:{r}")

            flash(f"🛠️ Rôle simulé : {new_role} (session temporaire)", "info")
        elif target_role.lower() == "reset":
            if user_id:
                user = db.session.get(User, user_id)
                if user and user.role:
                    session["admin_user_role"] = user.role
                    cache.delete(f"user:{user_id}")
                    for r in list(valid_roles.keys()) + ["default"]:
                        cache.delete(f"user:{user_id}:{r}")
                    flash(f"Rôle réinitialisé : {user.role}", "info")
        else:
            flash("Rôle invalide spécifié.", "warning")

        next_url = request.values.get("next") or request.referrer or url_for("admin_dashboard")
        if not next_url.startswith("/") or next_url.startswith("//"):
            next_url = url_for("admin_dashboard")

        return redirect(next_url)

