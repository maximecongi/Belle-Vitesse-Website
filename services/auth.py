from flask import current_app, request
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from models import User
from utils.mailer import send_magic_link_email


def get_auth_serializer():
    """Returns a serializer for generating and validating magic link tokens."""
    secret_key = current_app.config.get("SECRET_KEY", "fallback_secret")
    return URLSafeTimedSerializer(secret_key)


def request_magic_link(email):
    """
    1. Checks if email ends with @bellevitesse.com.
    2. Looks up the user in the database.
    3. Generates a token and sends an email.
    """
    if not email.endswith("@bellevitesse.com"):
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

    # Generate token
    serializer = get_auth_serializer()
    token = serializer.dumps(email, salt="magic-link-salt")

    # Generate URL
    try:
        base_url = request.host_url.rstrip('/')
    except Exception:
        base_url = "https://www.bellevitesse.com"

    magic_link = f"{base_url}/admin/auth/{token}"

    # Send email
    success = send_magic_link_email(email, user.firstname, magic_link)

    if success:
        current_app.logger.info(f"✅ Magic link sent to {email}")
    else:
        current_app.logger.error(f"❌ Failed to send magic link to {email}")

    return success


def verify_magic_link(token):
    """
    1. Validates the token and expiration.
    2. Re-checks the DB for the user's latest data.
    3. Returns the user dict to store in the session.
    """
    serializer = get_auth_serializer()
    try:
        # Token expires in 15 minutes (900 seconds)
        email = serializer.loads(token, salt="magic-link-salt", max_age=900)
    except SignatureExpired:
        current_app.logger.warning("⚠️ Magic link token expired.")
        return None
    except BadSignature:
        current_app.logger.warning("⚠️ Invalid magic link token.")
        return None

    # Re-validate user in the database
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
