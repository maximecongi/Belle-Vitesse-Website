from models.db import db, _utcnow


class KDriveObject(db.Model):
    """
    Modèle de suivi de synchronisation pour chaque document ou asset kDrive.
    Garantit l'idempotence des envois et stocke les IDs kDrive réels pour la suppression.
    """
    __tablename__ = "kdrive_objects"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    entity_type = db.Column(db.String(50), nullable=False, index=True)
    entity_id = db.Column(db.String(100), nullable=False, index=True)
    role = db.Column(db.String(50), nullable=False)
    source_key = db.Column(db.String(255), nullable=False)

    kdrive_file_id = db.Column(db.BigInteger, nullable=True, index=True)
    kdrive_dir_id = db.Column(db.BigInteger, nullable=True, index=True)

    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    last_error = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint(
            "entity_type", "entity_id", "role", "source_key",
            name="uq_kdrive_entity_role_source"
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "role": self.role,
            "source_key": self.source_key,
            "kdrive_file_id": self.kdrive_file_id,
            "kdrive_dir_id": self.kdrive_dir_id,
            "status": self.status,
            "attempts": self.attempts,
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<KDriveObject {self.entity_type}:{self.entity_id} ({self.role}) -> {self.status}>"
