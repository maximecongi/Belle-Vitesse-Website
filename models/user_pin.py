from models.db import _utcnow, db


class UserPin(db.Model):
    """Page de l'ERP épinglée par un utilisateur (favori affiché en tête de la sidebar)."""
    __tablename__ = "user_pins"
    __table_args__ = (
        db.UniqueConstraint("user_id", "url", name="uq_user_pins_user_url"),
    )

    LABEL_MAX = 120
    URL_MAX = 512

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label = db.Column(db.String(LABEL_MAX), nullable=False)
    url = db.Column(db.String(URL_MAX), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=_utcnow)

    def to_dict(self):
        return {"id": self.id, "label": self.label, "url": self.url}

    def __repr__(self):
        return f"<UserPin {self.user_id} {self.url}>"
