from datetime import timezone
from models.db import db, _utcnow


class ProjectReport(db.Model):
    """
    Modèle représentant un rapport ou commentaire d'équipe affilié à un projet (tournage).
    Permet à l'équipe (pilotes, techniciens, administrateurs) de consigner des observations,
    faits marquants et débriefs techniques au fil de l'eau.
    """
    __tablename__ = "project_reports"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    author_name = db.Column(db.String(150), nullable=True)
    author_role = db.Column(db.String(100), nullable=True)
    content = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    # Relations
    project = db.relationship("Project", backref=db.backref("reports", cascade="all, delete-orphan", order_by="ProjectReport.created_at.asc()", lazy=True))
    user = db.relationship("User", backref=db.backref("project_reports", lazy=True))

    def to_dict(self):
        """Sérialise le rapport pour les réponses JSON / API."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "user_id": self.user_id,
            "author_name": self.author_name or (f"{self.user.firstname} {self.user.lastname}" if self.user else "Collaborateur"),
            "author_role": self.author_role or (self.user.role_display if self.user else "Équipe"),
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<ProjectReport #{self.id} for Project {self.project_id} by {self.author_name}>"
