"""
Routes admin pour la gestion des abonnements calendrier ICS.
Accessible aux administrateurs et managers.
"""
import base64
import io

import qrcode
from flask import flash, redirect, render_template, request, session, url_for

from models import User, db
from services.admin.calendar_subscriptions import (
    create_subscription,
    get_subscription_for_user,
    list_all_subscriptions,
    regenerate_subscription,
    revoke_subscription,
)
from utils.decorators import require_roles
from utils.mailer import send_calendar_invitation_email


def _get_target_user_id(request_form):
    """
    Détermine l'ID utilisateur cible pour les actions calendrier.
    Seul le Super Administrator peut cibler un autre utilisateur.
    Pour les autres rôles, force l'ID de l'utilisateur connecté en session.
    """
    user_role = (session.get("admin_user_role") or "").lower()
    if user_role == "super administrator":
        return request_form.get("user_id", type=int)
    return session.get("admin_user_id")


def init_calendar_routes(app):
    """Initialise les routes de gestion des abonnements calendrier."""

    @app.route("/admin/calendar", endpoint="admin_calendar")
    @require_roles("administrator", "manager", "commercial")
    def admin_calendar():
        """Page de gestion des abonnements calendrier ICS."""
        user_role = (session.get("admin_user_role") or "").lower()
        is_super_admin = (user_role == "super administrator")

        if is_super_admin:
            users = User.query.order_by(User.firstname).all()
            subscriptions = list_all_subscriptions()
        else:
            current_user_id = session.get("admin_user_id")
            user = db.session.get(User, current_user_id) if current_user_id else None
            users = [user] if user else []
            sub = get_subscription_for_user(current_user_id) if current_user_id else None
            subscriptions = [sub] if sub else []

        # Construire un dict {user_id: subscription} pour accès rapide
        sub_map = {}
        for sub in subscriptions:
            if sub and sub.is_active:
                sub_map[sub.user_id] = sub

        # Générer les URLs et QR codes pour les abonnements actifs
        sub_data = {}
        for user_id, sub in sub_map.items():
            feed_url = url_for("cal_feed.calendar_feed",
                               token=sub.token, _external=True)
            # Générer le QR code en base64
            qr_b64 = _generate_qr_base64(feed_url)
            sub_data[user_id] = {
                "subscription": sub,
                "feed_url": feed_url,
                "qr_base64": qr_b64,
            }

        return render_template(
            "admin/calendar.html",
            users=users,
            sub_data=sub_data,
            is_super_admin=is_super_admin,
        )

    @app.route("/admin/calendar/generate", methods=["POST"], endpoint="admin_calendar_generate")
    @require_roles("administrator", "manager", "commercial")
    def admin_calendar_generate():
        """Crée un nouveau token calendrier pour un utilisateur."""
        user_id = _get_target_user_id(request.form)
        if not user_id:
            flash("Utilisateur invalide.", "error")
            return redirect(url_for("admin_calendar"))

        sub = create_subscription(user_id)
        if sub:
            user = db.session.get(User, user_id)
            name = f"{user.firstname} {user.lastname}" if user else f"ID {user_id}"
            flash(f"Lien calendrier généré pour {name}.", "success")

            # Envoyer l'email d'invitation automatiquement à la génération
            if user and user.mail:
                feed_url = url_for("cal_feed.calendar_feed",
                                   token=sub.token, _external=True)
                if send_calendar_invitation_email(user.mail, f"{user.firstname} {user.lastname}", feed_url):
                    flash(f"Email d'invitation envoyé à {user.mail}.", "info")
                else:
                    flash("Erreur lors de l'envoi de l'email d'invitation.", "warning")
        else:
            flash("Erreur lors de la génération du lien calendrier.", "error")

        return redirect(url_for("admin_calendar"))

    @app.route("/admin/calendar/revoke", methods=["POST"], endpoint="admin_calendar_revoke")
    @require_roles("administrator", "manager", "commercial")
    def admin_calendar_revoke():
        """Révoque le token calendrier actif d'un utilisateur."""
        user_id = _get_target_user_id(request.form)
        if not user_id:
            flash("Utilisateur invalide.", "error")
            return redirect(url_for("admin_calendar"))

        if revoke_subscription(user_id):
            user = db.session.get(User, user_id)
            name = f"{user.firstname} {user.lastname}" if user else f"ID {user_id}"
            flash(f"Lien calendrier révoqué pour {name}.", "success")
        else:
            flash("Aucun abonnement actif trouvé.", "error")

        return redirect(url_for("admin_calendar"))

    @app.route("/admin/calendar/regenerate", methods=["POST"], endpoint="admin_calendar_regenerate")
    @require_roles("administrator", "manager", "commercial")
    def admin_calendar_regenerate():
        """Régénère le token calendrier d'un utilisateur (révoque + recrée)."""
        user_id = _get_target_user_id(request.form)
        if not user_id:
            flash("Utilisateur invalide.", "error")
            return redirect(url_for("admin_calendar"))

        sub = regenerate_subscription(user_id)
        if sub:
            user = db.session.get(User, user_id)
            name = f"{user.firstname} {user.lastname}" if user else f"ID {user_id}"
            flash(
                f"Lien calendrier régénéré pour {name}. L'ancien lien ne fonctionne plus.", "success")
        else:
            flash("Erreur lors de la régénération du lien calendrier.", "error")

        return redirect(url_for("admin_calendar"))

    @app.route("/admin/calendar/send-email", methods=["POST"], endpoint="admin_calendar_send_email")
    @require_roles("administrator", "manager", "commercial")
    def admin_calendar_send_email():
        """Envoie manuellement le lien calendrier par email."""
        user_id = _get_target_user_id(request.form)
        if not user_id:
            flash("Utilisateur invalide.", "error")
            return redirect(url_for("admin_calendar"))

        user = db.session.get(User, user_id)
        sub = get_subscription_for_user(user_id)

        if not user or not user.mail:
            flash("Utilisateur sans adresse email.", "error")
        elif not sub or not sub.is_active:
            flash("Aucun abonnement actif trouvé.", "error")
        else:
            feed_url = url_for("cal_feed.calendar_feed",
                               token=sub.token, _external=True)
            if send_calendar_invitation_email(user.mail, f"{user.firstname} {user.lastname}", feed_url):
                flash(f"Lien calendrier envoyé à {user.mail}.", "success")
            else:
                flash("Erreur lors de l'envoi de l'email.", "error")

        return redirect(url_for("admin_calendar"))


def _generate_qr_base64(url):
    """Génère un QR code en base64 pour l'URL donnée."""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#1a1a2e", back_color="#ffffff")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode("utf-8")
    except Exception:
        return None
