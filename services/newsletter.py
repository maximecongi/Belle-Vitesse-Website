from models import NewsletterSubscriber, db
from datetime import datetime


def add_newsletter_subscriber(email):
    """Add a new subscriber to MySQL database."""
    # Check if subscriber already exists
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
    """Remove a subscriber from MySQL database."""
    subscriber = NewsletterSubscriber.query.filter_by(email=email).first()
    if subscriber:
        db.session.delete(subscriber)
        db.session.commit()
        return True
    return False
