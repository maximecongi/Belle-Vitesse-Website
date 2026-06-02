from models.db import db, _utcnow


class NewsletterSubscriber(db.Model):
    """Modèle représentant un abonné à la newsletter."""
    __tablename__ = "newsletter_subscribers"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    subscribed_at = db.Column(db.DateTime, default=_utcnow)

    def __repr__(self):
        return f"<NewsletterSubscriber {self.email}>"
