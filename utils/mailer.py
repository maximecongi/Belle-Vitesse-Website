import base64
from datetime import datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
import io
import os
import smtplib
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
            sender_type
        )

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

    @classmethod
    def send_templated_email(
        cls,
        to_email,
        subject,
        template_name,
        context=None,
        text_content=None,
        sender_type="contact",
        cc=None,
        attachments=None,
        extra_headers=None,
        timeout=10,
    ):
        """
        Helper générique pour construire et expédier un e-mail transactionnel (HTML + fallback texte).
        Injecte automatiquement l'année en cours et prend en charge les pièces jointes.
        """
        try:
            ctx = dict(context or {})
            if "now_year" not in ctx:
                ctx["now_year"] = datetime.now(timezone.utc).year

            html_content = render_template(template_name, **ctx)

            has_attachments = bool(attachments)
            if has_attachments:
                msg = MIMEMultipart("mixed")
                body = MIMEMultipart("alternative")
                if text_content:
                    body.attach(MIMEText(text_content, "plain", "utf-8"))
                body.attach(MIMEText(html_content, "html", "utf-8"))
                msg.attach(body)

                for att in attachments:
                    att_path = att if isinstance(att, str) else att.get("path")
                    att_name = att.get("name") if isinstance(att, dict) else os.path.basename(att_path)
                    if att_path and os.path.exists(att_path):
                        with open(att_path, "rb") as f:
                            part = MIMEApplication(f.read(), Name=att_name)
                        part["Content-Disposition"] = f'attachment; filename="{att_name}"'
                        msg.attach(part)
                    else:
                        current_app.logger.error(f"❌ Attachment not found at {att_path}")
            else:
                msg = MIMEMultipart("alternative")
                if text_content:
                    msg.attach(MIMEText(text_content, "plain", "utf-8"))
                msg.attach(MIMEText(html_content, "html", "utf-8"))

            msg["Subject"] = subject
            msg["To"] = to_email
            msg["Date"] = formatdate(localtime=True)
            msg["Message-ID"] = make_msgid(domain="bellevitesse.com")

            if cc:
                if isinstance(cc, list):
                    msg["Cc"] = ", ".join(cc)
                else:
                    msg["Cc"] = str(cc)

            if extra_headers:
                for header_key, header_val in extra_headers.items():
                    msg[header_key] = header_val

            recipients = [to_email]
            if cc:
                if isinstance(cc, list):
                    recipients.extend(cc)
                else:
                    recipients.append(cc)

            return cls._send_smtp_message(msg, recipients, sender_type=sender_type, timeout=timeout)

        except Exception as e:
            current_app.logger.error(
                f"❌ Erreur sending templated email '{subject}' to {to_email}: {e}"
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
                app.logger.error(
                    f"❌ Erreur lors de l'envoi d'email en arrière-plan : {err}"
                )

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return True


def send_magic_link_email(to_email, firstname, magic_link):
    """Envoie un lien magique pour une connexion sans mot de passe à un administrateur."""
    current_app.logger.info(f"🚀 Sending magic link email to {to_email}")
    text_content = (
        f"Bonjour {firstname},\n\nVoici votre lien de connexion temporaire à Belle Vitesse :\n"
        f"{magic_link}\n\nCe lien va expirer dans 15 minutes.\n\nL'équipe Belle Vitesse."
    )
    return EmailService.send_templated_email(
        to_email=to_email,
        subject="Connexion à Belle Vitesse",
        template_name="emails/magic_link.html",
        context={"firstname": firstname, "magic_link": magic_link},
        text_content=text_content,
        sender_type="admin",
    )


def send_subscription_email(to_email):
    """Envoie un email de bienvenue lors de l'inscription à la newsletter."""
    try:
        current_app.logger.info(
            f"🚀 Démarrage de l'envoi d'email de bienvenue pour {to_email}"
        )

        secret_key = current_app.config.get("SECRET_KEY")
        serializer = URLSafeSerializer(secret_key)
        token = serializer.dumps(to_email)

        try:
            base_url = request.host_url.rstrip("/")
        except Exception:
            base_url = "https://bellevitesse.com"

        unsubscribe_url = f"{base_url}/unsubscribe/{token}"
        current_app.logger.info(f"🔗 Unsubscribe URL générée: {unsubscribe_url}")

        text_content = (
            f"Welcome to Belle Vitesse! Thank you for subscribing to our newsletter. "
            f"To unsubscribe: {unsubscribe_url}"
        )

        extra_headers = {
            "Precedence": "bulk",
            "List-Unsubscribe": f"<{unsubscribe_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            "List-Id": "Belle Vitesse Newsletter <newsletter.bellevitesse.com>",
            "X-Entity-Ref-ID": "newsletter-welcome",
        }
        mail_user = os.getenv("MAIL_CONTACT_USERNAME")
        if mail_user:
            extra_headers["Return-Path"] = mail_user

        return EmailService.send_templated_email(
            to_email=to_email,
            subject="Welcome to Belle Vitesse",
            template_name="emails/newsletter_welcome.html",
            context={"unsubscribe_url": unsubscribe_url},
            text_content=text_content,
            sender_type="contact",
            extra_headers=extra_headers,
        )

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
        "contact"
    )

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
                token = serializer.dumps(sub.email)
                if not base_url:
                    try:
                        base_url = request.host_url.rstrip("/")
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
            base_url = request.host_url.rstrip("/")
        except Exception:
            base_url = "https://bellevitesse.com"
    return run_async_email(send_newsletter_campaign, subject, body, subscribers, base_url=base_url)


def _send_waiver_invitation_email(
    waiver_type: str,
    to_email: str,
    recipient_name: str,
    project_name: str,
    signature_link: str,
    is_reminder: bool = False,
):
    """
    Fonction unifiée interne pour l'envoi d'une invitation ou d'une relance
    de décharge de responsabilité (pilote ou production).
    """
    is_prod = (waiver_type == "production")
    type_label = "production" if is_prod else "pilote"

    current_app.logger.info(
        f"🚀 Sending {type_label} waiver {'reminder' if is_reminder else 'invitation'} email to {to_email}"
    )

    prefix = "Rappel : " if is_reminder else ""
    subject = f"{prefix}Signature décharge {type_label} - {project_name}"

    if is_reminder:
        text_content = (
            f"Bonjour {recipient_name},\n\n"
            f"RAPPEL : Le tournage approche et sauf erreur de notre part, votre décharge de responsabilité {type_label} "
            f"pour le projet : {project_name} n'a pas encore été signée.\n\n"
            f"Merci de la compléter et la signer dès maintenant via ce lien : {signature_link}\n\n"
            f"Ce document est indispensable avant le début du tournage.\n\n"
            f"L'équipe Belle Vitesse."
        )
    else:
        text_content = (
            f"Bonjour {recipient_name},\n\n"
            f"Vous êtes invité à compléter et signer électroniquement votre décharge de responsabilité {type_label} "
            f"pour le projet : {project_name}.\n\n"
            f"Suivez ce lien pour signer : {signature_link}\n\n"
            f"L'équipe Belle Vitesse."
        )

    context = {
        "waiver_type": waiver_type,
        "recipient_name": recipient_name,
        "pilot_name": recipient_name,
        "prod_contact_name": recipient_name,
        "project_name": project_name,
        "signature_link": signature_link,
        "is_reminder": is_reminder,
    }

    return EmailService.send_templated_email(
        to_email=to_email,
        subject=subject,
        template_name="emails/waiver_invitation.html",
        context=context,
        text_content=text_content,
        sender_type="admin",
    )


def send_waiver_invitation_email(to_email, pilot_name, project_name, signature_link, is_reminder=False):
    """Envoie une invitation (ou un rappel de relance) à un pilote pour signer sa décharge."""
    return _send_waiver_invitation_email(
        waiver_type="pilot",
        to_email=to_email,
        recipient_name=pilot_name,
        project_name=project_name,
        signature_link=signature_link,
        is_reminder=is_reminder,
    )


def send_production_waiver_invitation_email(to_email, prod_contact_name, project_name, signature_link, is_reminder=False):
    """Envoie une invitation (ou un rappel de relance) à un contact de production pour signer sa décharge."""
    return _send_waiver_invitation_email(
        waiver_type="production",
        to_email=to_email,
        recipient_name=prod_contact_name,
        project_name=project_name,
        signature_link=signature_link,
        is_reminder=is_reminder,
    )


def send_waiver_signed_email(to_email, recipient_name, project_name, pdf_path):
    """Envoie un email avec le PDF de décharge signé en pièce jointe."""
    admin_mail = os.getenv("SUPER_ADMIN_MAIL", "contact@bellevitesse.com")
    current_app.logger.info(f"🚀 Sending signed waiver PDF to {to_email} and {admin_mail}")
    text_content = (
        f"Bonjour {recipient_name},\n\nVeuillez trouver ci-joint la décharge signée "
        f"pour le projet : {project_name}.\n\nBelle journée,\nL'équipe Belle Vitesse."
    )
    return EmailService.send_templated_email(
        to_email=to_email,
        subject=f"Décharge signée - {project_name}",
        template_name="emails/waiver_signed_confirmation.html",
        context={"recipient_name": recipient_name, "project_name": project_name},
        text_content=text_content,
        sender_type="contact",
        cc=admin_mail,
        attachments=[pdf_path] if pdf_path else None,
        timeout=15,
    )


def send_calendar_invitation_email(to_email, user_name, feed_url):
    """
    Envoie une invitation pour s'abonner au calendrier ICS Belle Vitesse.
    Inclut un QR code pour faciliter l'abonnement sur mobile.
    """
    try:
        current_app.logger.info(f"🚀 Sending calendar invitation email to {to_email}")

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

        text_content = (
            f"Bonjour {user_name},\n\nVous pouvez désormais synchroniser le planning des projets Belle Vitesse "
            f"directement sur votre téléphone ou ordinateur.\n\nLien d'abonnement : {feed_url}\n\nL'équipe Belle Vitesse."
        )

        return EmailService.send_templated_email(
            to_email=to_email,
            subject="Votre calendrier Belle Vitesse",
            template_name="emails/calendar_invitation.html",
            context={
                "user_name": user_name,
                "feed_url": feed_url,
                "qrcode_base64": qrcode_base64,
            },
            text_content=text_content,
            sender_type="admin",
        )

    except Exception as e:
        current_app.logger.error(
            f"❌ Erreur sending calendar invitation email to {to_email}: {e}"
        )
        return False


def send_incident_signature_request_email(incident, to_email, signing_url):
    """Envoie un email officiel à la Production l'invitant à viser et signer le constat d'incident."""
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

    context = {
        "incident": incident,
        "incident_number": incident_num,
        "incident_title": incident_title,
        "incident_date": incident.incident_date,
        "location": incident.location,
        "project_name": project_name,
        "signature_link": signing_url,
    }

    return EmailService.send_templated_email(
        to_email=to_email,
        subject=f"Action requise : Visa du constat d'incident {incident_num} ({project_name})",
        template_name="emails/incident_invitation.html",
        context=context,
        text_content=text_content,
        sender_type="admin",
    )


def send_incident_signed_confirmation_email(incident, to_email, pdf_path):
    """Envoie l'exemplaire certifié scellé du rapport d'incident avec le PDF en pièce jointe."""
    admin_mail = os.getenv("SUPER_ADMIN_MAIL", "contact@bellevitesse.com")
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

    context = {
        "incident": incident,
        "incident_number": incident_num,
        "incident_title": incident.title,
        "project_name": project_name,
    }

    return EmailService.send_templated_email(
        to_email=to_email,
        subject=f"Constat scellé et signé - {incident_num} ({project_name})",
        template_name="emails/incident_signed_confirmation.html",
        context=context,
        text_content=text_content,
        sender_type="contact",
        cc=admin_mail,
        attachments=[pdf_path] if pdf_path else None,
        timeout=15,
    )
