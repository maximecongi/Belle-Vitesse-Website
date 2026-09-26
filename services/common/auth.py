import time
import uuid
from typing import Dict, Optional
from flask import current_app, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from models import User
from utils.mailer import send_magic_link_email

_in_memory_used_jtis: Dict[str, float] = {}


def _get_auth_redis_client():
    try:
        from services.common.session_manager import get_session_redis_client
        return get_session_redis_client()
    except Exception:
        return None


def is_jti_consumed(jti: str) -> bool:
    """Vérifie si un jeton JTI a déjà été consommé (Redis ou fallback mémoire)."""
    if not jti:
        return False

    client = _get_auth_redis_client()
    if client:
        try:
            return bool(client.exists(f"bv_magic_link_used:{jti}"))
        except Exception as err:
            current_app.logger.warning(f"Erreur vérification Redis JTI: {err}")

    # Fallback mémoire locale
    now = time.time()
    expire_time = _in_memory_used_jtis.get(jti)
    if expire_time:
        if now < expire_time:
            return True
        else:
            _in_memory_used_jtis.pop(jti, None)
    return False


def mark_jti_consumed(jti: str, ttl: int = 900) -> None:
    """Marque un jeton JTI comme consommé avec un TTL de 15 minutes."""
    if not jti:
        return

    client = _get_auth_redis_client()
    if client:
        try:
            client.setex(f"bv_magic_link_used:{jti}", ttl, "1")
            client.delete(f"bv_magic_link_pending:{jti}")
            return
        except Exception as err:
            current_app.logger.warning(f"Erreur enregistrement Redis JTI: {err}")

    # Fallback mémoire locale
    _in_memory_used_jtis[jti] = time.time() + ttl
    now = time.time()
    for k in list(_in_memory_used_jtis.keys()):
        if _in_memory_used_jtis[k] <= now:
            _in_memory_used_jtis.pop(k, None)


def get_auth_serializer():
    """Retourne un sérialiseur pour générer et valider les jetons de liens magiques (Magic Links)."""
    secret_key = current_app.config.get("SECRET_KEY", "fallback_secret")
    return URLSafeTimedSerializer(secret_key)


ALLOWED_DOMAINS = ("@bellevitesse.com", "@rvz.fr")


def request_magic_link(email):
    """
    1. Vérifie si l'e-mail se termine par un domaine autorisé.
    2. Recherche l'utilisateur dans la base de données.
    3. Génère un jeton à usage unique avec un identifiant cryptographique (JTI).
    4. Envoie un e-mail ou consigne le lien dans les logs en développement.
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

    # Génération du jeton à usage unique avec JTI
    jti = uuid.uuid4().hex
    payload = {"email": email, "jti": jti}

    serializer = get_auth_serializer()
    token = serializer.dumps(payload, salt="magic-link-salt")

    # Mémoriser le jeton en attente dans Redis (optionnel pour audit/monitoring)
    client = _get_auth_redis_client()
    if client:
        try:
            client.setex(f"bv_magic_link_pending:{jti}", 900, email)
        except Exception:
            pass

    # Génération de l'URL
    try:
        base_url = request.host_url.rstrip('/')
    except Exception:
        base_url = "https://bellevitesse.com"

    magic_link = f"{base_url}/admin/auth/{token}"

    if current_app.config.get("FLASK_ENV") == "development":
        current_app.logger.info(f"🔗 [DEV] Lien magique direct généré pour {email} : {magic_link}")

    # Envoi de l'e-mail
    success = send_magic_link_email(email, user.firstname, magic_link)

    if success:
        current_app.logger.info(f"✅ Magic link sent to {email} (JTI={jti})")
    else:
        current_app.logger.error(f"❌ Failed to send magic link to {email}")

    return success


def verify_magic_link(token):
    """
    1. Valide le jeton et son expiration (15 minutes).
    2. Vérifie que le jeton n'a pas déjà été consommé (JTI à usage unique).
    3. Marque immédiatement le JTI comme consommé.
    4. Vérifie à nouveau les données utilisateur en base.
    5. Retourne un dictionnaire utilisateur pour stockage en session.
    """
    serializer = get_auth_serializer()
    try:
        data = serializer.loads(token, salt="magic-link-salt", max_age=900)
    except SignatureExpired:
        current_app.logger.warning("⚠️ Jeton de lien magique expiré.")
        return None
    except BadSignature:
        current_app.logger.warning("⚠️ Jeton de lien magique invalide.")
        return None

    # Extraction des données du jeton (support dict moderne ou chaîne legacy)
    if isinstance(data, dict):
        email = data.get("email")
        jti = data.get("jti")
    else:
        email = data
        jti = None

    # Vérification et invalidation d'usage unique
    if jti:
        if is_jti_consumed(jti):
            current_app.logger.warning(
                f"⚠️ Tentative de réutilisation d'un lien magique déjà consommé (JTI={jti}, email={email})."
            )
            return None
        mark_jti_consumed(jti, ttl=900)

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
