import time
import logging
from flask import current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from models import NewsletterSubscriber, db, _utcnow

logger = logging.getLogger(__name__)

# Domaines jetables / temporaires connus
DISPOSABLE_EMAIL_DOMAINS = {
    "mailinator.com", "yopmail.com", "guerrillamail.com", "10minutemail.com",
    "tempmail.com", "trashmail.com", "sharklasers.com", "dispostable.com",
    "getairmail.com", "temp-mail.org", "throwawaymail.com", "fakeinbox.com",
    "emailondeck.com", "generator.email", "mohmal.com", "inboxkitten.com"
}


def generate_newsletter_token() -> str:
    """Génère un jeton horodaté et signé cryptographiquement pour sécuriser la soumission."""
    secret = current_app.config.get("SECRET_KEY", "bv_newsletter_default_secret")
    serializer = URLSafeTimedSerializer(secret, salt="newsletter-anti-bot")
    return serializer.dumps(time.time())


def validate_newsletter_submission(form_data, email: str, client_ip: str = ""):
    """
    Vérifie la légitimité d'une soumission à la newsletter.
    Retourne un tuple (is_valid: bool, reason: str, detail: str).

    Défenses :
    1. Honeypot : champ caché devant rester vide.
    2. Time-Trap : token signé horodaté, délai minimum de 1.5s entre affichage et soumission.
    3. Heuristiques email : dot-stuffing massif et domaines temporaires jetables.
    """
    # 1. Vérification du Honeypot
    hp_value = (form_data.get("website_hp") or "").strip()
    if hp_value:
        return False, "honeypot_triggered", f"Valeur honeypot détectée : '{hp_value[:50]}'"

    is_testing = current_app.config.get("TESTING", False)

    # 2. Vérification du Time-Trap (Token signé horodaté)
    token = (form_data.get("subscribe_token") or "").strip()
    if not token:
        if not is_testing:
            return False, "missing_token", "Jeton de sécurité absent (requête directe scriptée)"
    else:
        secret = current_app.config.get("SECRET_KEY", "bv_newsletter_default_secret")
        serializer = URLSafeTimedSerializer(secret, salt="newsletter-anti-bot")
        try:
            # Token valide max 24h
            gen_time = serializer.loads(token, max_age=86400, salt="newsletter-anti-bot")
            if not is_testing:
                elapsed = time.time() - float(gen_time)
                # Un humain met au minimum 1.5s pour lire et soumettre
                if elapsed < 1.5:
                    return False, "submitted_too_fast", f"Soumission trop rapide ({elapsed:.2f}s < 1.5s)"
        except (BadSignature, SignatureExpired, ValueError, TypeError) as e:
            if not is_testing:
                return False, "invalid_token", f"Jeton invalide ou expiré ({e})"

    # 3. Heuristiques sur l'adresse email
    if email and "@" in email:
        local_part, domain_part = email.rsplit("@", 1)
        domain_part = domain_part.lower()

        # Détection de dot-stuffing (ex: awes.o.m.e.s.a.u.c.em.7@gmail.com, to.bit.hrn@gmail.com)
        # Typique des bots de subscription bombing utilisant les alias Gmail/Yahoo
        segments = local_part.split(".")
        if len(segments) >= 3:
            short_segments = [s for s in segments if len(s) <= 2]
            has_single_char = any(len(s) == 1 for s in segments)
            if has_single_char or len(short_segments) >= 2 or len(segments) >= 4:
                return False, "dot_stuffing", f"Adresse avec injection artificielle de points ({len(segments)} segments)"

        # Détection d'adresses institutionnelles/gouvernementales ciblées par le subscription bombing
        if domain_part.endswith(".gov") or domain_part.endswith(".mil"):
            return False, "gov_mil_blocked", f"Domaine institutionnel non autorisé via formulaire public ({domain_part})"

        # Détection de domaines jetables
        if domain_part in DISPOSABLE_EMAIL_DOMAINS:
            return False, "disposable_domain", f"Domaine d'email jetable non autorisé ({domain_part})"

    return True, "ok", "Soumission légitime"



def add_newsletter_subscriber(email):
    """Ajoute un nouvel abonné à la base de données MySQL."""
    try:
        # Vérifie si l'abonné existe déjà
        existing = NewsletterSubscriber.query.filter_by(email=email).first()
        if existing:
            return False

        subscriber = NewsletterSubscriber(
            email=email,
            subscribed_at=_utcnow()
        )

        db.session.add(subscriber)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erreur lors de l'ajout d'un abonné newsletter ({email}) : {e}")
        raise e


def remove_newsletter_subscriber(email):
    """Supprime un abonné de la base de données MySQL."""
    try:
        subscriber = NewsletterSubscriber.query.filter_by(email=email).first()
        if subscriber:
            db.session.delete(subscriber)
            db.session.commit()
            return True
        return False
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erreur lors de la suppression de l'abonné newsletter ({email}) : {e}")
        raise e


def list_newsletter_subscribers():
    """Liste tous les abonnés triés par date décroissante."""
    return NewsletterSubscriber.query.order_by(NewsletterSubscriber.subscribed_at.desc()).all()


def remove_newsletter_subscriber_by_id(subscriber_id):
    """Supprime un abonné par son ID."""
    try:
        subscriber = db.session.get(NewsletterSubscriber, subscriber_id)
        if subscriber:
            db.session.delete(subscriber)
            db.session.commit()
            return True
        return False
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erreur lors de la suppression de l'abonné newsletter #{subscriber_id} : {e}")
        raise e
