import os
import smtplib
from datetime import datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
import io
import base64
import threading

from flask import current_app, render_template, request
from itsdangerous import URLSafeSerializer
import qrcode


class EmailService:
    """Service centralisé pour l'envoi d'emails via SMTP."""

    @staticmethod
    def _get_credentials(sender_type="contact"):
        """Récupère la configuration et les identifiants SMTP selon le type d'expéditeur."""
        mail_server = os.getenv("MAIL_SERVER")
        mail_port = int(os.getenv("MAIL_PORT", 587))
        mail_use_tls = os.getenv("MAIL_USE_TLS", "true").lower() == "true"

        if sender_type == "admin":
            mail_user = os.getenv("MAIL_ADMIN_USERNAME")
            mail_password = os.getenv("MAIL_ADMIN_PASSWORD")
        else:
            mail_user = os.getenv("MAIL_CONTACT_USERNAME")
            mail_password = os.getenv("MAIL_CONTACT_PASSWORD")

        return mail_server, mail_port, mail_user, mail_password, mail_use_tls

    @classmethod
    def _send_smtp_message(cls, msg, recipients, sender_type="contact", timeout=10):
        """Crée une connexion SMTP temporaire, s'authentifie et envoie le message."""
        # En mode test, interdire tout appel SMTP réel vers les boîtes mail
        if (
            os.getenv("FLASK_ENV") == "testing"
            or os.getenv("TESTING") == "True"
            or (current_app and current_app.config.get("TESTING"))
            or (current_app and getattr(current_app, "testing", False))
        ):
            if current_app:
                current_app.logger.info(
                    f"🧪 [TESTING] Email SMTP intercepté (non envoyé) pour : {recipients}"
                )
            return True

        mail_server, mail_port, mail_user, mail_password, mail_use_tls = cls._get_credentials(
            sender_type)

        if not all([mail_server, mail_user, mail_password]):
            current_app.logger.error(
                f"❌ Email configuration missing in .env for '{sender_type}' sender."
            )
            return False

        try:
            if "From" not in msg:
                msg["From"] = f"Belle Vitesse <{mail_user}>"
            if "Reply-To" not in msg:
                msg["Reply-To"] = mail_user

            server = smtplib.SMTP(mail_server, mail_port, timeout=timeout)

            if mail_use_tls:
                server.starttls()

            server.login(mail_user, mail_password)
            server.sendmail(mail_user, recipients, msg.as_string())
            server.quit()
            return True

        except Exception as e:
            current_app.logger.error(
                f"❌ Error sending email to {recipients}: {e}"
            )
            return False


def run_async_email(target_func, *args, **kwargs):
    """
    Exécute une fonction d'envoi d'email dans un thread d'arrière-plan avec le contexte applicatif Flask.
    En mode de test (testing), l'envoi s'exécute de manière synchrone.
    """
    if (
        os.getenv("FLASK_ENV") == "testing"
        or os.getenv("TESTING") == "True"
        or (current_app and current_app.config.get("TESTING"))
        or (current_app and getattr(current_app, "testing", False))
    ):
        return target_func(*args, **kwargs)

    app = current_app._get_current_object()

    def _worker():
        with app.app_context():
            try:
                target_func(*args, **kwargs)
            except Exception as err:
                app.logger.error(f"❌ Erreur lors de l'envoi d'email en arrière-plan : {err}")

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return True


def send_magic_link_email(to_email, firstname, magic_link):
    """
    Envoie un lien magique pour une connexion sans mot de passe à un administrateur.
    """
    try:
        current_app.logger.info(f"🚀 Sending magic link email to {to_email}")

        # Text fallback content
        text_content = (
            f"Bonjour {firstname},\n\nVoici votre lien de connexion temporaire à Belle Vitesse :\n"
            f"{magic_link}\n\nCe lien va expirer dans 15 minutes.\n\nL'équipe Belle Vitesse."
        )

        # Premium HTML content via template
        html_content = render_template(
            "emails/magic_link.html",
            firstname=firstname,
            magic_link=magic_link,
            now_year=datetime.now(timezone.utc).year
        )

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Connexion à Belle Vitesse"
        msg["To"] = to_email
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="bellevitesse.com")

        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        return EmailService._send_smtp_message(msg, [to_email], sender_type="admin")

    except Exception as e:
        current_app.logger.error(
            f"❌ Erreur sending magic link email to {to_email}: {e}"
        )
        return False


def send_subscription_email(to_email):
    """Envoie un email de bienvenue lors de l'inscription à la newsletter."""
    try:
        current_app.logger.info(
            f"🚀 Démarrage de l'envoi d'email de bienvenue pour {to_email}")

        # Generate unsubscribe token
        secret_key = current_app.config.get("SECRET_KEY")
        serializer = URLSafeSerializer(secret_key)
        token = serializer.dumps(to_email)

        # Use request.host_url to get the full base URL
        try:
            base_url = request.host_url.rstrip('/')
        except Exception:
            base_url = "https://bellevitesse.com"  # Fallback

        unsubscribe_url = f"{base_url}/unsubscribe/{token}"
        current_app.logger.info(
            f"🔗 Unsubscribe URL générée: {unsubscribe_url}")

        # Load HTML template
        html_content = render_template(
            "emails/newsletter_welcome.html", unsubscribe_url=unsubscribe_url
        )

        # Simple plain text fallback
        text_content = (
            f"Welcome to Belle Vitesse! Thank you for subscribing to our newsletter. "
            f"To unsubscribe: {unsubscribe_url}"
        )

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Welcome to Belle Vitesse"
        msg["To"] = to_email
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="bellevitesse.com")

        # ⭐ AJOUT DES EN-TÊTES ANTI-SPAM ⭐
        msg["Precedence"] = "bulk"
        msg["List-Unsubscribe"] = f"<{unsubscribe_url}>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
        msg["List-Id"] = "Belle Vitesse Newsletter <newsletter.bellevitesse.com>"
        msg["X-Entity-Ref-ID"] = "newsletter-welcome"

        mail_user = os.getenv("MAIL_CONTACT_USERNAME")
        if mail_user:
            msg["Return-Path"] = mail_user

        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        return EmailService._send_smtp_message(msg, [to_email], sender_type="contact")

    except Exception as e:
        current_app.logger.error(
            f"❌ Erreur lors de l'envoi de l'email de bienvenue à {to_email} : {type(e).__name__}: {e}"
        )
        return False


def send_newsletter_campaign(subject, body, subscribers, base_url=None):
    """
    Envoie une campagne newsletter groupée à une liste d'abonnés.
    'subscribers' est une liste d'objets NewsletterSubscriber.
    """
    if (
        os.getenv("FLASK_ENV") == "testing"
        or os.getenv("TESTING") == "True"
        or (current_app and current_app.config.get("TESTING"))
        or (current_app and getattr(current_app, "testing", False))
    ):
        if current_app:
            current_app.logger.info(
                f"🧪 [TESTING] Campagne newsletter interceptée (non envoyée) pour {len(subscribers)} abonnés"
            )
        return len(subscribers), 0

    mail_server, mail_port, mail_user, mail_password, mail_use_tls = EmailService._get_credentials(
        "contact")

    if not all([mail_server, mail_user, mail_password]):
        current_app.logger.error("❌ Email configuration missing in .env")
        return 0, len(subscribers)

    results = {"success": 0, "failed": 0}

    try:
        server = smtplib.SMTP(mail_server, mail_port, timeout=10)
        if mail_use_tls:
            server.starttls()
        server.login(mail_user, mail_password)

        secret_key = current_app.config.get("SECRET_KEY")
        serializer = URLSafeSerializer(secret_key)

        for sub in subscribers:
            try:
                # Generate unique unsubscribe for each
                token = serializer.dumps(sub.email)
                if not base_url:
                    try:
                        base_url = request.host_url.rstrip('/')
                    except Exception:
                        base_url = "https://bellevitesse.com"

                unsubscribe_url = f"{base_url}/unsubscribe/{token}"

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
                    f"⚠️ Failed to send to {sub.email}: {e}"
                )
                results["failed"] += 1

        server.quit()
        return results["success"], results["failed"]

    except Exception as e:
        current_app.logger.error(f"❌ critical SMTP error during campaign: {e}")
        return results["success"], results["failed"]


def send_newsletter_campaign_async(subject, body, subscribers, base_url=None):
    """Lance l'envoi d'une campagne newsletter groupée en arrière-plan."""
    if not base_url:
        try:
            base_url = request.host_url.rstrip('/')
        except Exception:
            base_url = "https://bellevitesse.com"
    return run_async_email(send_newsletter_campaign, subject, body, subscribers, base_url=base_url)


def send_waiver_invitation_email(to_email, pilot_name, project_name, signature_link):
    """Envoie une invitation à un pilote pour signer sa décharge."""
    try:
        current_app.logger.info(
            f"🚀 Sending waiver invitation email to {to_email}")

        # Text fallback content
        text_content = (
            f"Bonjour {pilot_name},\n\nVous êtes invité à compléter et signer électroniquement la décharge pilote "
            f"pour le projet : {project_name}.\n\nSuivez ce lien pour signer : {signature_link}\n\nL'équipe Belle Vitesse."
        )

        # Premium HTML content via template
        html_content = render_template(
            "emails/waiver_invitation.html",
            pilot_name=pilot_name,
            project_name=project_name,
            signature_link=signature_link,
            now_year=datetime.now(timezone.utc).year
        )

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Signature décharge pilote - {project_name}"
        msg["To"] = to_email
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="bellevitesse.com")

        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        return EmailService._send_smtp_message(msg, [to_email], sender_type="admin")

    except Exception as e:
        current_app.logger.error(
            f"❌ Erreur sending waiver email to {to_email}: {e}"
        )
        return False


def send_production_waiver_invitation_email(to_email, prod_contact_name, project_name, signature_link):
    """Envoie une invitation à un contact de production pour signer sa décharge."""
    try:
        current_app.logger.info(
            f"🚀 Sending production waiver invitation email to {to_email}")

        # Text fallback content
        text_content = (
            f"Bonjour {prod_contact_name},\n\nVous êtes invité à compléter et signer électroniquement "
            f"la décharge production pour le projet : {project_name}.\n\n"
            f"Suivez ce lien pour signer : {signature_link}\n\nL'équipe Belle Vitesse."
        )

        # Premium HTML content via template
        html_content = render_template(
            "emails/production_waiver_invitation.html",
            prod_contact_name=prod_contact_name,
            project_name=project_name,
            signature_link=signature_link,
            now_year=datetime.now(timezone.utc).year
        )

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Signature décharge production - {project_name}"
        msg["To"] = to_email
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="bellevitesse.com")

        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        return EmailService._send_smtp_message(msg, [to_email], sender_type="admin")

    except Exception as e:
        current_app.logger.error(
            f"❌ Erreur sending production waiver email to {to_email}: {e}"
        )
        return False


def send_waiver_signed_email(to_email, recipient_name, project_name, pdf_path):
    """
    Envoie un email avec le PDF signé en pièce jointe.
    """
    admin_mail = os.getenv("SUPER_ADMIN_MAIL", "contact@bellevitesse.com")

    try:
        current_app.logger.info(
            f"🚀 Sending signed waiver PDF to {to_email} and {admin_mail}")

        # Text fallback content
        text_content = (
            f"Bonjour {recipient_name},\n\nVeuillez trouver ci-joint la décharge signée "
            f"pour le projet : {project_name}.\n\nBelle journée,\nL'équipe Belle Vitesse."
        )

        # Premium HTML content via template
        html_content = render_template(
            "emails/waiver_signed_confirmation.html",
            recipient_name=recipient_name,
            project_name=project_name,
            now_year=datetime.now(timezone.utc).year
        )

        # Create message (mixed for attachments)
        msg = MIMEMultipart("mixed")
        msg["Subject"] = f"Décharge signée - {project_name}"
        msg["To"] = to_email
        msg["Cc"] = admin_mail
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="bellevitesse.com")

        # Create alternative container for body content
        body = MIMEMultipart("alternative")
        body.attach(MIMEText(text_content, "plain", "utf-8"))
        body.attach(MIMEText(html_content, "html", "utf-8"))
        msg.attach(body)

        # Attach PDF
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                part = MIMEApplication(
                    f.read(), Name=os.path.basename(pdf_path))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(pdf_path)}"'
            msg.attach(part)
        else:
            current_app.logger.error(f"❌ PDF file not found at {pdf_path}")

        recipients = [to_email, admin_mail]
        return EmailService._send_smtp_message(msg, recipients, sender_type="contact", timeout=15)

    except Exception as e:
        current_app.logger.error(
            f"❌ Erreur sending signed waiver email to {to_email}: {e}"
        )
        return False


def send_calendar_invitation_email(to_email, user_name, feed_url):
    """
    Envoie une invitation pour s'abonner au calendrier ICS Belle Vitesse.
    Inclut un QR code pour faciliter l'abonnement sur mobile.
    """
    try:
        current_app.logger.info(
            f"🚀 Sending calendar invitation email to {to_email}")

        # Generation du QR Code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(feed_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        qrcode_base64 = base64.b64encode(buffered.getvalue()).decode()

        # Text fallback content
        text_content = (
            f"Bonjour {user_name},\n\nVous pouvez désormais synchroniser le planning des projets Belle Vitesse "
            f"directement sur votre téléphone ou ordinateur.\n\nLien d'abonnement : {feed_url}\n\nL'équipe Belle Vitesse."
        )

        # Premium HTML content via template
        html_content = render_template(
            "emails/calendar_invitation.html",
            user_name=user_name,
            feed_url=feed_url,
            qrcode_base64=qrcode_base64,
            now_year=datetime.now(timezone.utc).year
        )

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Votre calendrier Belle Vitesse"
        msg["To"] = to_email
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="bellevitesse.com")

        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        return EmailService._send_smtp_message(msg, [to_email], sender_type="admin")

    except Exception as e:
        current_app.logger.error(
            f"❌ Erreur sending calendar invitation email to {to_email}: {e}"
        )
        return False


def send_incident_signature_request_email(incident, to_email, signing_url):
    """
    Envoie un email officiel à la Production l'invitant à viser et signer le constat d'incident.
    """
    try:
        current_app.logger.info(
            f"🚀 Envoi de l'invitation à signer l'incident {incident.incident_number} vers {to_email}"
        )

        project_name = incident.project.name if incident.project else "Tournage"
        incident_num = incident.incident_number
        incident_title = incident.title

        text_content = (
            f"Bonjour,\n\n"
            f"Dans le cadre du projet '{project_name}', un constat d'incident ({incident_num} - {incident_title}) "
            f"a été établi par l'équipe technique Belle Vitesse.\n\n"
            f"Afin de valider contradictoirement ce constat, merci de bien vouloir apposer votre visa électronique "
            f"en cliquant sur le lien suivant (valide 48 heures) :\n"
            f"{signing_url}\n\n"
            f"L'équipe Belle Vitesse reste à votre disposition pour tout échange.\n\n"
            f"Bien cordialement,\n"
            f"L'équipe Belle Vitesse\n"
            f"https://bellevitesse.com"
        )

        html_content = render_template(
            "emails/incident_invitation.html",
            incident=incident,
            incident_number=incident_num,
            incident_title=incident_title,
            incident_date=incident.incident_date,
            location=incident.location,
            project_name=project_name,
            signature_link=signing_url,
            now_year=datetime.now(timezone.utc).year,
        )

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Action requise : Visa du constat d'incident {incident_num} ({project_name})"
        msg["To"] = to_email
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="bellevitesse.com")

        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        return EmailService._send_smtp_message(msg, [to_email], sender_type="admin")

    except Exception as e:
        current_app.logger.error(
            f"❌ Erreur lors de l'envoi de l'invitation de signature d'incident à {to_email}: {e}"
        )
        return False


def send_incident_signed_confirmation_email(incident, to_email, pdf_path):
    """
    Envoie l'exemplaire certifié scellé du rapport d'incident avec le PDF en pièce jointe.
    """
    admin_mail = os.getenv("SUPER_ADMIN_MAIL", "contact@bellevitesse.com")
    try:
        current_app.logger.info(
            f"🚀 Envoi de la confirmation d'incident scellé {incident.incident_number} à {to_email}"
        )

        project_name = incident.project.name if incident.project else "Tournage"
        incident_num = incident.incident_number

        text_content = (
            f"Bonjour,\n\n"
            f"Le constat d'incident {incident_num} relatif au projet '{project_name}' a été "
            f"visé par l'ensemble des parties et scellé électroniquement.\n\n"
            f"Veuillez trouver ci-joint l'exemplaire officiel certifié (PDF scellé avec sceau d'intégrité).\n\n"
            f"Bien cordialement,\n"
            f"L'équipe Belle Vitesse"
        )

        html_content = render_template(
            "emails/incident_signed_confirmation.html",
            incident=incident,
            incident_number=incident_num,
            incident_title=incident.title,
            project_name=project_name,
            now_year=datetime.now(timezone.utc).year,
        )

        msg = MIMEMultipart("mixed")
        msg["Subject"] = f"Constat scellé et signé - {incident_num} ({project_name})"
        msg["To"] = to_email
        msg["Cc"] = admin_mail
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="bellevitesse.com")

        body = MIMEMultipart("alternative")
        body.attach(MIMEText(text_content, "plain", "utf-8"))
        body.attach(MIMEText(html_content, "html", "utf-8"))
        msg.attach(body)

        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(pdf_path))
            part["Content-Disposition"] = f'attachment; filename="{os.path.basename(pdf_path)}"'
            msg.attach(part)

        recipients = [to_email, admin_mail]
        return EmailService._send_smtp_message(msg, recipients, sender_type="contact", timeout=15)

    except Exception as e:
        current_app.logger.error(
            f"❌ Erreur lors de l'envoi de la confirmation d'incident scellé à {to_email}: {e}"
        )
        return False

