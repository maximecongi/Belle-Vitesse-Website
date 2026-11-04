"""
Mixins partagés pour les modèles SQLAlchemy (jetons de signature et documents archivés).
"""

from datetime import datetime, timedelta, timezone

from models.db import _utcnow, db


class TokenMixin:
    """Base pour tous les jetons (tokens) de signature à durée limitée."""
    token = db.Column(db.String(36), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    expires_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: _utcnow() + timedelta(hours=24),
        server_default=db.FetchedValue()
    )

    def is_expired(self) -> bool:
        """Indique si le jeton a dépassé sa durée de validité (24h)."""
        now = datetime.now(timezone.utc)
        if self.expires_at:
            exp = self.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            return now > exp
        if self.created_at:
            created = self.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            return (now - created) > timedelta(hours=24)
        return False


class SignedDocumentMixin:
    """Base pour tous les documents signés archivés."""
    hash = db.Column(db.String(255), nullable=False)  # Empreinte de l'intégrité des données
    pdf_file_hash = db.Column(db.String(64))  # Hash SHA-256 du fichier PDF binaire
    data_snapshot = db.Column(db.JSON, nullable=False)  # Copie conforme des données au moment de la signature
    signature = db.Column(db.String(255), nullable=True)  # Chemin relatif du fichier signature PNG
    pdf_url = db.Column(db.Text)  # URL (ou chemin) vers le fichier PDF
    signed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=_utcnow)

    @property
    def signature_data_uri(self):
        """Retourne la Data URI de la signature pour injection directe dans les templates ou PDF."""
        from utils.signature_storage import load_signature_data_uri
        return load_signature_data_uri(self.signature)

