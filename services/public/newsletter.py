from datetime import datetime

from models import NewsletterSubscriber, db


def add_newsletter_subscriber(email):
    """Ajoute un nouvel abonné à la base de données MySQL."""
    # Vérifie si l'abonné existe déjà
    existing = NewsletterSubscriber.query.filter_by(email=email).first()
    if existing:
        return False

    subscriber = NewsletterSubscriber(
        email=email,
        subscribed_at=datetime.utcnow()
    )

    db.session.add(subscriber)
    db.session.commit()
    return True


def remove_newsletter_subscriber(email):
    """Supprime un abonné de la base de données MySQL."""
    subscriber = NewsletterSubscriber.query.filter_by(email=email).first()
    if subscriber:
        db.session.delete(subscriber)
        db.session.commit()
        return True
    return False


def list_newsletter_subscribers():
    """Liste tous les abonnés triés par date décroissante."""
    return NewsletterSubscriber.query.order_by(NewsletterSubscriber.subscribed_at.desc()).all()


def remove_newsletter_subscriber_by_id(subscriber_id):
    """Supprime un abonné par son ID."""
    subscriber = db.session.get(NewsletterSubscriber, subscriber_id)
    if subscriber:
        db.session.delete(subscriber)
        db.session.commit()
        return True
    return False
