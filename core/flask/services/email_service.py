import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import make_msgid, formatdate
from itsdangerous import URLSafeSerializer
from flask import current_app, render_template, request

def send_subscription_email(to_email):
    """Send a welcome email when someone subscribes to the newsletter."""
    config = current_app.config
    mail_server = config.get("MAIL_SERVER")
    mail_port = config.get("MAIL_PORT", 587)
    mail_user = config.get("MAIL_USERNAME")
    mail_password = config.get("MAIL_PASSWORD")
    mail_use_tls = config.get("MAIL_USE_TLS")

    if not all([mail_server, mail_user, mail_password]):
        current_app.logger.error("❌ Email configuration missing in config")
        return False

    try:
        current_app.logger.info(f"🚀 Démarrage de l'envoi d'email pour {to_email}")
        
        # Generate unsubscribe token
        secret_key = config.get("SECRET_KEY")
        serializer = URLSafeSerializer(secret_key)
        token = serializer.dumps(to_email)
        
        # Use request.host_url to get the full base URL
        try:
            base_url = request.host_url.rstrip('/')
        except Exception:
            base_url = "https://www.bellevitesse.com" # Fallback
            
        unsubscribe_url = f"{base_url}/unsubscribe/{token}"
        current_app.logger.info(f"🔗 Unsubscribe URL générée: {unsubscribe_url}")

        # Load HTML template
        try:
            html_content = render_template("emails/newsletter_welcome.html", unsubscribe_url=unsubscribe_url)
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
        
        # Additional headers for better deliverability
        msg["Reply-To"] = mail_user
        msg["Return-Path"] = mail_user

        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        # Send email
        current_app.logger.info(f"🔌 Connexion au serveur SMTP {mail_server}:{mail_port}...")
        server = smtplib.SMTP(mail_server, mail_port, timeout=10)
        
        if mail_use_tls:
            current_app.logger.info("🔐 Démarrage TLS...")
            server.starttls()
        
        current_app.logger.info(f"🔑 Tentative de login pour {mail_user}...")
        server.login(mail_user, mail_password)
        
        current_app.logger.info("📤 Envoi du message...")
        server.sendmail(mail_user, [to_email], msg.as_string())
        
        server.quit()

        current_app.logger.info(f"✅ Email de bienvenue envoyé avec succès à {to_email}")
        return True

    except Exception as e:
        current_app.logger.error(f"❌ Erreur détaillée lors de l'envoi de l'email à {to_email} : {type(e).__name__}: {e}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return False
