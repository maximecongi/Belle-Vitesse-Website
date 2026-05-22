from flask import current_app, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from models import User
from utils.mailer import send_magic_link_email


def get_auth_serializer():
    """Retourne un sérialiseur pour générer et valider les jetons de liens magiques (Magic Links)."""
    secret_key = current_app.config.get("SECRET_KEY", "fallback_secret")
    return URLSafeTimedSerializer(secret_key)


ALLOWED_DOMAINS = ("@bellevitesse.com", "@rvz.fr")


def request_magic_link(email):
    """
    1. Vérifie si l'e-mail se termine par un domaine autorisé.
    2. Recherche l'utilisateur dans la base de données.
    3. Génère un jeton et envoie un e-mail.
    """
    if not any(email.endswith(domain) for domain in ALLOWED_DOMAINS):
        current_app.logger.warning(
            f"⚠️ Magic link requested for non-domain email: {email}")
        return False

    try:
        user = User.query.filter_by(mail=email).first()
    except Exception as e:
        current_app.logger.error(f"❌ Error fetching user from DB: {e}")
        return False

    if not user:
        current_app.logger.warning(
            f"⚠️ Magic link requested for unknown domain email: {email}")
        return False

    # Génération du jeton
    serializer = get_auth_serializer()
    token = serializer.dumps(email, salt="magic-link-salt")

    # Génération de l'URL
    try:
        base_url = request.host_url.rstrip('/')
    except Exception:
        base_url = "https://www.bellevitesse.com"

    magic_link = f"{base_url}/admin/auth/{token}"

    # Envoi de l'e-mail
    success = send_magic_link_email(email, user.firstname, magic_link)

    if success:
        current_app.logger.info(f"✅ Magic link sent to {email}")
    else:
        current_app.logger.error(f"❌ Failed to send magic link to {email}")

    return success


def verify_magic_link(token):
    """
    1. Valide le jeton et son expiration.
    2. Vérifie à nouveau les données utilisateur en base.
    3. Retourne un dictionnaire utilisateur pour stockage en session.
    """
    serializer = get_auth_serializer()
    try:
        # Le jeton expire après 15 minutes (900 secondes)
        email = serializer.loads(token, salt="magic-link-salt", max_age=900)
    except SignatureExpired:
        current_app.logger.warning("⚠️ Jeton de lien magique expiré.")
        return None
    except BadSignature:
        current_app.logger.warning("⚠️ Jeton de lien magique invalide.")
        return None

    # Re-validation de l'utilisateur en base de données
    try:
        user = User.query.filter_by(mail=email).first()
    except Exception as e:
        current_app.logger.error(f"❌ Error verifying user from DB: {e}")
        return None

    if not user:
        current_app.logger.warning(
            f"⚠️ User found in token but no longer in DB: {email}")
        return None

    return {
        "id": user.id,
        "email": email,
        "firstname": user.firstname,
        "lastname": user.lastname,
        "role": user.role if user.role else "User"
    }
