from models.db import db, generate_inspection_number, _utcnow


# ── Mixins Partagés ──────────────────────────────────────────────

class TokenMixin:
    """Base pour tous les jetons (tokens) de signature à durée limitée."""
    token = db.Column(db.String(36), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False,
                           default=_utcnow)
    expires_at = db.Column(db.DateTime, nullable=False,
                           server_default=db.FetchedValue())


class SignedDocumentMixin:
    """Base pour tous les documents signés archivés."""
    hash = db.Column(
        db.String(255), nullable=False)  # Empreinte de l'intégrité des données
    # Hash SHA-256 du fichier PDF binaire
    pdf_file_hash = db.Column(db.String(64))
    # Copie conforme des données au moment de la signature
    data_snapshot = db.Column(db.JSON, nullable=False)
    # Données de la signature (MEDIUMTEXT)
    signature = db.Column(db.Text(length=16777215))
    pdf_url = db.Column(db.Text)  # URL (ou chemin) vers le fichier PDF
    signed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=_utcnow)


# ── Modèles de décharges ─────────────────────────────────────────

class PilotWaiver(db.Model):
    """Modèle représentant une décharge de responsabilité pour un pilote."""
    __tablename__ = "pilot_waivers"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey(
        "projects.id"), unique=True, nullable=False, index=True)
    waiver_id = db.Column(
        db.String(50), unique=True, default=lambda: generate_inspection_number("BVDW"))

    # Copie du nom du projet au moment de la génération
    project_name = db.Column(db.String(255), nullable=True)
    # Statut (to_generate, to_send, to_sign, signed)
    status = db.Column(db.String(20), default="to_generate", nullable=False)
    generated_at = db.Column(db.DateTime, nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    signed_at = db.Column(db.DateTime, nullable=True)

    # Données figées (Snapshot) lors de la signature
    pilot_first_name = db.Column(db.String(100), nullable=True)
    pilot_last_name = db.Column(db.String(100), nullable=True)
    pilot_dob = db.Column(db.Date, nullable=True)
    pilot_license_number = db.Column(db.String(100), nullable=True)
    pilot_address = db.Column(db.Text, nullable=True)
    pilot_insurance_company = db.Column(db.String(255), nullable=True)
    pilot_insurance_policy = db.Column(db.String(255), nullable=True)

    production_name = db.Column(db.String(255), nullable=True)
    vehicles = db.Column(db.Text, nullable=True)
    shooting_dates = db.Column(db.String(255), nullable=True)

    # Signature
    signature_data = db.Column(
        # Données de signature manuscrite (Base64)
        db.Text(length=16777215), nullable=True)
    # Chemin relatif du PDF signé
    signed_pdf_path = db.Column(db.String(500), nullable=True)

    # Traçabilité de la signature
    signer_ip = db.Column(db.String(45), nullable=True)

    # Pièces jointes (photos/scans)
    pilot_license_path = db.Column(db.String(500), nullable=True)
    pilot_insurance_path = db.Column(db.String(500), nullable=True)
    pilot_identity_path = db.Column(db.String(500), nullable=True)

    # Webhook (n8n)
    webhook_triggered_at = db.Column(db.DateTime, nullable=True)

    # Soft-delete support
    deleted_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        """Convertit l'objet en dictionnaire pour les réponses API."""
        return {
            "id": self.id,
            "waiver_id": self.waiver_id,
            "project_id": self.project_id,
            "status": self.status,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "signed_at": self.signed_at.isoformat() if self.signed_at else None,
            "pilot_first_name": self.pilot_first_name,
            "pilot_last_name": self.pilot_last_name,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }

    def __repr__(self):
        return f"<PilotWaiver {self.project_id} - {self.status}>"


class ProductionWaiver(db.Model):
    """Modèle représentant une décharge de responsabilité pour la production."""
    __tablename__ = "production_waivers"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey(
        "projects.id"), unique=True, nullable=False, index=True)
    waiver_id = db.Column(
        db.String(50), unique=True, default=lambda: generate_inspection_number("BVPW"))

    project_name = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default="to_generate", nullable=False)
    generated_at = db.Column(db.DateTime, nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    signed_at = db.Column(db.DateTime, nullable=True)

    # Données figées (Snapshot) lors de la signature
    production_name = db.Column(db.String(255), nullable=True)
    production_representative = db.Column(db.String(255), nullable=True)
    production_address = db.Column(db.Text, nullable=True)
    production_siret = db.Column(db.String(100), nullable=True)
    production_vat = db.Column(db.String(100), nullable=True)

    production_insurance_company = db.Column(db.String(255), nullable=True)
    production_insurance_policy = db.Column(db.String(255), nullable=True)
    production_insurance_validity = db.Column(db.String(100), nullable=True)

    vehicles = db.Column(db.Text, nullable=True)
    shooting_dates = db.Column(db.String(255), nullable=True)
    location_of_use = db.Column(db.Text, nullable=True)

    # Signature
    signature_data = db.Column(
        db.Text(length=16777215), nullable=True)  # MEDIUMTEXT
    signed_pdf_path = db.Column(db.String(500), nullable=True)

    # Traçabilité de la signature
    signer_ip = db.Column(db.String(45), nullable=True)

    # Pièces jointes
    production_insurance_path = db.Column(db.String(500), nullable=True)

    # Webhook
    webhook_triggered_at = db.Column(db.DateTime, nullable=True)

    # Soft-delete support
    deleted_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        """Convertit l'objet en dictionnaire pour les réponses API."""
        return {
            "id": self.id,
            "waiver_id": self.waiver_id,
            "project_id": self.project_id,
            "status": self.status,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "signed_at": self.signed_at.isoformat() if self.signed_at else None,
            "production_name": self.production_name,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }

    def __repr__(self):
        return f"<ProductionWaiver {self.project_id} - {self.status}>"


class PilotWaiverSignedDocument(db.Model, SignedDocumentMixin):
    """Archive d'une décharge pilote signée."""
    __tablename__ = "pilot_waiver_signed_documents"
    waiver_id = db.Column(db.String(50), primary_key=True)


class ProductionWaiverSignedDocument(db.Model, SignedDocumentMixin):
    """Archive d'une décharge production signée."""
    __tablename__ = "production_waiver_signed_documents"
    waiver_id = db.Column(db.String(50), primary_key=True)


class CheckoutSignedDocument(db.Model, SignedDocumentMixin):
    """Archive d'une inspection au départ signée."""
    __tablename__ = "checkout_signed_documents"
    inspection_id = db.Column(db.String(255), primary_key=True)


class CheckoutToken(db.Model, TokenMixin):
    """Jeton de session pour la signature d'un check-out."""
    __tablename__ = "checkout_tokens"
    record_id = db.Column(db.String(255), nullable=False)
    inspection_id = db.Column(db.String(255), nullable=False)
    signature = db.Column(db.Text(length=16777215))


class CheckinSignedDocument(db.Model, SignedDocumentMixin):
    """Archive d'une inspection au retour signée."""
    __tablename__ = "checkin_signed_documents"
    inspection_id = db.Column(db.String(255), primary_key=True)


class CheckinToken(db.Model, TokenMixin):
    """Jeton de session pour la signature d'un check-in."""
    __tablename__ = "checkin_tokens"
    record_id = db.Column(db.String(255), nullable=False)
    inspection_id = db.Column(db.String(255), nullable=False)
    signature = db.Column(db.Text(length=16777215))


class PilotWaiverToken(db.Model, TokenMixin):
    """Jeton de session pour la signature d'une décharge pilote."""
    __tablename__ = "pilot_waiver_tokens"
    waiver_id = db.Column(db.String(255), nullable=False)


class ProductionWaiverToken(db.Model, TokenMixin):
    """Jeton de session pour la signature d'une décharge production."""
    __tablename__ = "production_waiver_tokens"
    waiver_id = db.Column(db.String(255), nullable=False)
