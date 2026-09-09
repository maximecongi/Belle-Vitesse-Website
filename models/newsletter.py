from models.db import db, _utcnow


class NewsletterSubscriber(db.Model):
    """Modèle représentant un abonné à la newsletter."""
    __tablename__ = "newsletter_subscribers"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    subscribed_at = db.Column(db.DateTime, default=_utcnow)

    @property
    def created_at(self):
        """Alias pour compatibilité avec les clients MCP/API."""
        return self.subscribed_at

    def to_dict(self):
        iso_date = self.subscribed_at.isoformat() if self.subscribed_at else None
        return {
            "id": self.id,
            "email": self.email,
            "subscribed_at": iso_date,
            "created_at": iso_date,
        }

    def __repr__(self):
        return f"<NewsletterSubscriber {self.email}>"

