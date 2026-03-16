import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.utils import make_msgid, formatdate
from itsdangerous import URLSafeSerializer
from flask import render_template, request, current_app
from utils.async_tasks import run_async


def send_magic_link_email(to_email, firstname, magic_link):
    """
    Sends a magic link for passwordless login to an administrator.
    Runs asynchronously in a background thread.
    """
    app = current_app._get_current_object()

    def _send():
        mail_server = os.getenv("MAIL_SERVER")
        mail_port = int(os.getenv("MAIL_PORT", 587))
        mail_user = os.getenv("MAIL_ADMIN_USERNAME")
        mail_password = os.getenv("MAIL_ADMIN_PASSWORD")
        mail_use_tls = os.getenv("MAIL_USE_TLS", "true").lower() == "true"

        if not all([mail_server, mail_user, mail_password]):
            app.logger.error(
                "❌ Email configuration missing in .env for magic link.")
            return

        try:
            app.logger.info(f"🚀 Sending magic link email to {to_email}")
            text_content = f"Bonjour {firstname},\n\nVoici votre lien de connexion temporaire à Belle Vitesse :\n{magic_link}\n\nCe lien va expirer dans 15 minutes.\n\nL'équipe Belle Vitesse."

            with app.app_context():
                html_content = render_template(
                    "emails/magic_link.html",
                    firstname=firstname,
                    magic_link=magic_link,
                    now_year=datetime.utcnow().year
                )

            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Connexion à Belle Vitesse"
            msg["From"] = f"Belle Vitesse <{mail_user}>"
            msg["To"] = to_email
            msg["Date"] = formatdate(localtime=True)
            msg["Message-ID"] = make_msgid(domain="bellevitesse.com")
            msg["Reply-To"] = mail_user

            msg.attach(MIMEText(text_content, "plain", "utf-8"))
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            server = smtplib.SMTP(mail_server, mail_port, timeout=10)
            if mail_use_tls:
                server.starttls()
            server.login(mail_user, mail_password)
            server.sendmail(mail_user, [to_email], msg.as_string())
            server.quit()
            app.logger.info(f"✅ Magic link email sent to {to_email}")
        except Exception as e:
            app.logger.error(
                f"❌ Erreur sending magic link email to {to_email}: {e}")

    run_async(app, _send)
    return True


def send_subscription_email(to_email):
    """Send a welcome email when someone subscribes to the newsletter asynchronously."""
    app = current_app._get_current_object()

    def _send():
        mail_server = os.getenv("MAIL_SERVER")
        mail_port = int(os.getenv("MAIL_PORT", 587))
        mail_user = os.getenv("MAIL_CONTACT_USERNAME")
        mail_password = os.getenv("MAIL_CONTACT_PASSWORD")
        mail_use_tls = os.getenv("MAIL_USE_TLS", "true").lower() == "true"

        if not all([mail_server, mail_user, mail_password]):
            app.logger.error("❌ Email configuration missing in .env")
            return

        try:
            app.logger.info(f"🚀 Démarrage de l'envoi d'email pour {to_email}")

            secret_key = app.config.get(
                "SECRET_KEY") or "bv_super_secret_key_2026"
            serializer = URLSafeSerializer(secret_key)
            token = serializer.dumps(to_email)

            # Note: request.host_url might not be available in a background thread
            # We assume a standard base URL for background emails
            base_url = os.getenv("BASE_URL", "https://bellevitesse.com")
            unsubscribe_url = f"{base_url}/unsubscribe/{token}"

            with app.app_context():
                html_content = render_template(
                    "emails/newsletter_welcome.html", unsubscribe_url=unsubscribe_url)

            text_content = f"Welcome to Belle Vitesse! Thank you for subscribing to our newsletter. To unsubscribe: {unsubscribe_url}"

            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Welcome to Belle Vitesse"
            msg["From"] = f"Belle Vitesse <{mail_user}>"
            msg["To"] = to_email
            msg["Date"] = formatdate(localtime=True)
            msg["Message-ID"] = make_msgid(domain="bellevitesse.com")
            msg["Precedence"] = "bulk"
            msg["List-Unsubscribe"] = f"<{unsubscribe_url}>"
            msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
            msg["List-Id"] = "Belle Vitesse Newsletter <newsletter.bellevitesse.com>"
            msg["X-Entity-Ref-ID"] = "newsletter-welcome"
            msg["Reply-To"] = mail_user
            msg["Return-Path"] = mail_user

            msg.attach(MIMEText(text_content, "plain", "utf-8"))
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            server = smtplib.SMTP(mail_server, mail_port, timeout=10)
            if mail_use_tls:
                server.starttls()
            server.login(mail_user, mail_password)
            server.sendmail(mail_user, [to_email], msg.as_string())
            server.quit()
            app.logger.info(
                f"✅ Email de bienvenue envoyé avec succès à {to_email}")
        except Exception as e:
            app.logger.error(
                f"❌ Erreur lors de l'envoi de l'email à {to_email}: {e}")

    run_async(app, _send)
    return True


def send_newsletter_campaign(subject, body, subscribers):
    """
    Sends a bulk newsletter email to a list of subscribers.
    subscribers is a list of NewsletterSubscriber objects.
    """
    mail_server = os.getenv("MAIL_SERVER")
    mail_port = int(os.getenv("MAIL_PORT", 587))
    mail_user = os.getenv("MAIL_CONTACT_USERNAME")
    mail_password = os.getenv("MAIL_CONTACT_PASSWORD")
    mail_use_tls = os.getenv("MAIL_USE_TLS", "true").lower() == "true"

    if not all([mail_server, mail_user, mail_password]):
        current_app.logger.error("❌ Email configuration missing in .env")
        return 0, len(subscribers)

    results = {"success": 0, "failed": 0}

    try:
        server = smtplib.SMTP(mail_server, mail_port, timeout=10)
        if mail_use_tls:
            server.starttls()
        server.login(mail_user, mail_password)

        secret_key = current_app.config.get(
            "SECRET_KEY") or "bv_super_secret_key_2026"
        serializer = URLSafeSerializer(secret_key)

        for sub in subscribers:
            try:
                # Generate unique unsubscribe for each
                token = serializer.dumps(sub.email)
                try:
                    base_url = request.host_url.rstrip('/')
                except Exception:
                    base_url = "https://www.bellevitesse.com"

                unsubscribe_url = f"{base_url}/unsubscribe/{token}"

                # Wrap body in a basic HTML container or just use it as is
                # For now, let's keep it simple as the user asked for an editor
                # We can add a base template later if needed.
                html_content = f"""
                <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; color: #151515;">
                    <div style="padding: 2rem;">
                        {body.replace('\n', '<br>')}
                    </div>
                    <div style="padding: 1rem; border-top: 1px solid #eee; font-size: 0.8rem; color: #888; text-align: center;">
                        <p>Belle Vitesse &copy; 2026</p>
                        <p><a href="{unsubscribe_url}" style="color: #888;">Se désabonner de la newsletter</a></p>
                    </div>
                </div>
                """

                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = f"Belle Vitesse <{mail_user}>"
                msg["To"] = sub.email
                msg["Date"] = formatdate(localtime=True)
                msg["Message-ID"] = make_msgid(domain="bellevitesse.com")

                msg["Precedence"] = "bulk"
                msg["List-Unsubscribe"] = f"<{unsubscribe_url}>"

                msg.attach(MIMEText(body, "plain", "utf-8"))
                msg.attach(MIMEText(html_content, "html", "utf-8"))

                server.sendmail(mail_user, [sub.email], msg.as_string())
                results["success"] += 1
            except Exception as e:
                current_app.logger.warning(
                    f"⚠️ Failed to send to {sub.email}: {e}")
                results["failed"] += 1

        server.quit()
        return results["success"], results["failed"]

    except Exception as e:
        current_app.logger.error(f"❌ critical SMTP error during campaign: {e}")
        return results["success"], results["failed"]


def send_waiver_invitation_email(to_email, pilot_name, project_name, signature_link):
    """Sends an invitation to a pilot to sign their waiver asynchronously."""
    app = current_app._get_current_object()

    def _send():
        mail_server = os.getenv("MAIL_SERVER")
        mail_port = int(os.getenv("MAIL_PORT", 587))
        mail_user = os.getenv("MAIL_ADMIN_USERNAME")
        mail_password = os.getenv("MAIL_ADMIN_PASSWORD")
        mail_use_tls = os.getenv("MAIL_USE_TLS", "true").lower() == "true"

        if not all([mail_server, mail_user, mail_password]):
            app.logger.error(
                "❌ Email configuration missing in .env for waiver invitation.")
            return

        try:
            app.logger.info(f"🚀 Sending waiver invitation email to {to_email}")
            text_content = f"Bonjour {pilot_name},\n\nVous êtes invité à compléter et signer électroniquement la décharge pilote pour le projet : {project_name}.\n\nSuivez ce lien pour signer : {signature_link}\n\nL'équipe Belle Vitesse."

            with app.app_context():
                html_content = render_template(
                    "emails/waiver_invitation.html",
                    pilot_name=pilot_name,
                    project_name=project_name,
                    signature_link=signature_link,
                    now_year=datetime.utcnow().year
                )

            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Signature décharge pilote - {project_name}"
            msg["From"] = f"Belle Vitesse <{mail_user}>"
            msg["To"] = to_email
            msg["Date"] = formatdate(localtime=True)
            msg["Message-ID"] = make_msgid(domain="bellevitesse.com")
            msg["Reply-To"] = mail_user

            msg.attach(MIMEText(text_content, "plain", "utf-8"))
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            server = smtplib.SMTP(mail_server, mail_port, timeout=10)
            if mail_use_tls:
                server.starttls()
            server.login(mail_user, mail_password)
            server.sendmail(mail_user, [to_email], msg.as_string())
            server.quit()
            app.logger.info(f"✅ Waiver invitation email sent to {to_email}")
        except Exception as e:
            app.logger.error(
                f"❌ Erreur sending waiver email to {to_email}: {e}")

    run_async(app, _send)
    return True


def send_production_waiver_invitation_email(to_email, prod_contact_name, project_name, signature_link):
    """Sends an invitation to a production contact to sign their waiver asynchronously."""
    app = current_app._get_current_object()

    def _send():
        mail_server = os.getenv("MAIL_SERVER")
        mail_port = int(os.getenv("MAIL_PORT", 587))
        mail_user = os.getenv("MAIL_ADMIN_USERNAME")
        mail_password = os.getenv("MAIL_ADMIN_PASSWORD")
        mail_use_tls = os.getenv("MAIL_USE_TLS", "true").lower() == "true"

        if not all([mail_server, mail_user, mail_password]):
            app.logger.error(
                "❌ Email configuration missing in .env for waiver invitation.")
            return

        try:
            app.logger.info(
                f"🚀 Sending production waiver invitation email to {to_email}")
            text_content = f"Bonjour {prod_contact_name},\n\nVous êtes invité à compléter et signer électroniquement la décharge production pour le projet : {project_name}.\n\nSuivez ce lien pour signer : {signature_link}\n\nL'équipe Belle Vitesse."

            with app.app_context():
                html_content = render_template(
                    "emails/production_waiver_invitation.html",
                    prod_contact_name=prod_contact_name,
                    project_name=project_name,
                    signature_link=signature_link,
                    now_year=datetime.utcnow().year
                )

            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Signature décharge production - {project_name}"
            msg["From"] = f"Belle Vitesse <{mail_user}>"
            msg["To"] = to_email
            msg["Date"] = formatdate(localtime=True)
            msg["Message-ID"] = make_msgid(domain="bellevitesse.com")
            msg["Reply-To"] = mail_user

            msg.attach(MIMEText(text_content, "plain", "utf-8"))
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            server = smtplib.SMTP(mail_server, mail_port, timeout=10)
            if mail_use_tls:
                server.starttls()
            server.login(mail_user, mail_password)
            server.sendmail(mail_user, [to_email], msg.as_string())
            server.quit()
            app.logger.info(
                f"✅ Production waiver invitation email sent to {to_email}")
        except Exception as e:
            app.logger.error(
                f"❌ Erreur sending production waiver email to {to_email}: {e}")

    run_async(app, _send)
    return True


def send_waiver_signed_email(to_email, recipient_name, project_name, pdf_path):
    """Sends an email with the signed PDF as an attachment asynchronously."""
    app = current_app._get_current_object()

    def _send():
        mail_server = os.getenv("MAIL_SERVER")
        mail_port = int(os.getenv("MAIL_PORT", 587))
        mail_user = os.getenv("MAIL_CONTACT_USERNAME")
        mail_password = os.getenv("MAIL_CONTACT_PASSWORD")
        mail_use_tls = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
        admin_mail = os.getenv("SUPER_ADMIN_MAIL", "contact@bellevitesse.com")

        if not all([mail_server, mail_user, mail_password]):
            app.logger.error(
                "❌ Email configuration missing in .env for signed waiver.")
            return

        try:
            app.logger.info(
                f"🚀 Sending signed waiver PDF to {to_email} and {admin_mail}")
            text_content = f"Bonjour {recipient_name},\n\nVeuillez trouver ci-joint la décharge signée pour le projet : {project_name}.\n\nBelle journée,\nL'équipe Belle Vitesse."

            with app.app_context():
                html_content = render_template(
                    "emails/waiver_signed_confirmation.html",
                    recipient_name=recipient_name,
                    project_name=project_name,
                    now_year=datetime.utcnow().year
                )

            msg = MIMEMultipart("mixed")
            msg["Subject"] = f"Décharge signée - {project_name}"
            msg["From"] = f"Belle Vitesse <{mail_user}>"
            msg["To"] = to_email
            msg["Cc"] = admin_mail
            msg["Date"] = formatdate(localtime=True)
            msg["Message-ID"] = make_msgid(domain="bellevitesse.com")

            body = MIMEMultipart("alternative")
            body.attach(MIMEText(text_content, "plain", "utf-8"))
            body.attach(MIMEText(html_content, "html", "utf-8"))
            msg.attach(body)

            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    part = MIMEApplication(
                        f.read(), Name=os.path.basename(pdf_path))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(pdf_path)}"'
                msg.attach(part)
            else:
                app.logger.error(f"❌ PDF file not found at {pdf_path}")

            server = smtplib.SMTP(mail_server, mail_port, timeout=15)
            if mail_use_tls:
                server.starttls()
            server.login(mail_user, mail_password)
            server.sendmail(mail_user, [to_email, admin_mail], msg.as_string())
            server.quit()
            app.logger.info(f"✅ Signed waiver email sent to {to_email}")
        except Exception as e:
            app.logger.error(
                f"❌ Erreur sending signed waiver email to {to_email}: {e}")

    run_async(app, _send)
    return True
