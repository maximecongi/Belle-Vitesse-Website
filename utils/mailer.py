import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import make_msgid, formatdate
from itsdangerous import URLSafeSerializer
from flask import render_template, request, current_app


def send_magic_link_email(to_email, firstname, magic_link):
    """
    Sends a magic link for passwordless login to an administrator.
    """
    mail_server = os.getenv("MAIL_SERVER")
    mail_port = int(os.getenv("MAIL_PORT", 587))
    mail_user = os.getenv("MAIL_USERNAME")
    mail_password = os.getenv("MAIL_PASSWORD")
    mail_use_tls = os.getenv("MAIL_USE_TLS", "true").lower() == "true"

    if not all([mail_server, mail_user, mail_password]):
        current_app.logger.error(
            "❌ Email configuration missing in .env for magic link.")
        return False

    try:
        current_app.logger.info(f"🚀 Sending magic link email to {to_email}")

        # Text fallback content
        text_content = f"Bonjour {firstname},\n\nVoici votre lien de connexion temporaire à Belle Vitesse :\n{magic_link}\n\nCe lien va expirer dans 15 minutes.\n\nL'équipe Belle Vitesse."

        # Simple HTML content
        html_content = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; color: #151515; padding: 2rem;">
            <p style="font-size: 1.1rem;">Bonjour {firstname},</p>
            <p>Voici votre lien sécurisé pour vous connecter à l'espace d'administration Belle Vitesse :</p>
            <div style="text-align: center; margin: 3rem 0;">
                <a href="{magic_link}" style="background-color: #151515; color: white; text-decoration: none; padding: 1rem 2rem; border-radius: 4px; font-weight: bold; display: inline-block;">Se connecter</a>
            </div>
            <p style="font-size: 0.9rem; color: #555;"><i>Ce lien expire dans 15 minutes. N'hésitez pas à en redemander un si besoin.</i></p>
        </div>
        """

        # Create message
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

        return True

    except Exception as e:
        current_app.logger.error(
            f"❌ Erreur sending magic link email to {to_email}: {e}")
        return False


def send_subscription_email(to_email):
    """Send a welcome email when someone subscribes to the newsletter."""
    mail_server = os.getenv("MAIL_SERVER")
    mail_port = int(os.getenv("MAIL_PORT", 587))
    mail_user = os.getenv("MAIL_USERNAME")
    mail_password = os.getenv("MAIL_PASSWORD")
    mail_use_tls = os.getenv("MAIL_USE_TLS", "true").lower() == "true"

    if not all([mail_server, mail_user, mail_password]):
        current_app.logger.error("❌ Email configuration missing in .env")
        return False

    try:
        current_app.logger.info(
            f"🚀 Démarrage de l'envoi d'email pour {to_email}")

        # Generate unsubscribe token
        secret_key = current_app.config.get(
            "SECRET_KEY") or "bv_super_secret_key_2026"
        serializer = URLSafeSerializer(secret_key)
        token = serializer.dumps(to_email)

        # Use request.host_url to get the full base URL
        try:
            base_url = request.host_url.rstrip('/')
        except Exception:
            base_url = "https://www.bellevitesse.com"  # Fallback

        unsubscribe_url = f"{base_url}/unsubscribe/{token}"
        current_app.logger.info(
            f"🔗 Unsubscribe URL générée: {unsubscribe_url}")

        # Load HTML template
        try:
            html_content = render_template(
                "emails/newsletter_welcome.html", unsubscribe_url=unsubscribe_url)
        except Exception as e:
            current_app.logger.error(f"❌ Erreur render_template: {e}")
            raise e

        # Simple plain text fallback
        text_content = f"Welcome to Belle Vitesse! Thank you for subscribing to our newsletter. To unsubscribe: {unsubscribe_url}"

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Welcome to Belle Vitesse"
        msg["From"] = f"Belle Vitesse <{mail_user}>"
        msg["To"] = to_email
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="bellevitesse.com")

        # ⭐ AJOUT DES EN-TÊTES ANTI-SPAM ⭐
        msg["Precedence"] = "bulk"
        msg["List-Unsubscribe"] = f"<{unsubscribe_url}>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
        msg["List-Id"] = "Belle Vitesse Newsletter <newsletter.bellevitesse.com>"
        msg["X-Entity-Ref-ID"] = "newsletter-welcome"

        msg["Reply-To"] = mail_user
        msg["Return-Path"] = mail_user

        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        current_app.logger.info(
            f"🔌 Connexion au serveur SMTP {mail_server}:{mail_port}...")
        server = smtplib.SMTP(mail_server, mail_port, timeout=10)

        if mail_use_tls:
            current_app.logger.info("🔐 Démarrage TLS...")
            server.starttls()

        current_app.logger.info(f"🔑 Tentative de login pour {mail_user}...")
        server.login(mail_user, mail_password)

        current_app.logger.info("📤 Envoi du message...")
        server.sendmail(mail_user, [to_email], msg.as_string())

        server.quit()
        current_app.logger.info(
            f"✅ Email de bienvenue envoyé avec succès à {to_email}")
        return True

    except Exception as e:
        current_app.logger.error(
            f"❌ Erreur détaillée lors de l'envoi de l'email à {to_email} : {type(e).__name__}: {e}")
        return False


def send_newsletter_campaign(subject, body, subscribers):
    """
    Sends a bulk newsletter email to a list of subscribers.
    subscribers is a list of NewsletterSubscriber objects.
    """
    mail_server = os.getenv("MAIL_SERVER")
    mail_port = int(os.getenv("MAIL_PORT", 587))
    mail_user = os.getenv("MAIL_USERNAME")
    mail_password = os.getenv("MAIL_PASSWORD")
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
