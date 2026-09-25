from models import NewsletterSubscriber, db, _utcnow
import logging

logger = logging.getLogger(__name__)


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
