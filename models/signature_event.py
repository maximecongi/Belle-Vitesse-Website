"""
Modèle d'audit immuable pour les événements de signature (Append-Only).
"""

from datetime import datetime, timezone
from sqlalchemy import event

from models.db import db, _utcnow


class SignatureEvent(db.Model):
    """
    Journal d'audit immuable consignant chaque événement lié au cycle de vie d'une signature
    (génération de lien, ouverture, consentement, déclaration de pouvoir, signature, écrasement).
    Toute tentative d'UPDATE ou de DELETE lève une exception RuntimeError.
    """
    __tablename__ = "signature_events"

    id = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"),
        primary_key=True,
        autoincrement=True
    )
    document_id = db.Column(db.String(100), nullable=False, index=True)
    mode = db.Column(db.String(30), nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    ip = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    details = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "mode": self.mode,
            "event_type": self.event_type,
            "ip": self.ip,
            "user_agent": self.user_agent,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def _prevent_signature_event_mutation(mapper, connection, target):
    raise RuntimeError(
        "Table immuable en écriture seule (Append-Only) : modification ou suppression interdite pour signature_events."
    )


event.listen(SignatureEvent, "before_update", _prevent_signature_event_mutation)
event.listen(SignatureEvent, "before_delete", _prevent_signature_event_mutation)
