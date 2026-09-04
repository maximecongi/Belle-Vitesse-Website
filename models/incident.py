import json
from models.db import db, generate_inspection_number, _utcnow
from models.waiver import TokenMixin, SignedDocumentMixin


class Incident(db.Model):
    """Modèle représentant un incident survenu lors d'un tournage ou lors d'un contrôle matériel."""
    __tablename__ = "incidents"

    id = db.Column(db.Integer, primary_key=True)
    incident_number = db.Column(
        db.String(50),
        unique=True,
        index=True,
        default=lambda: generate_inspection_number("BVIC")
    )
    title = db.Column(db.String(255), nullable=False)

    # Rattachements métier
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    vehicle_id = db.Column(db.String(100), nullable=True, index=True)
    equipment_name = db.Column(db.String(255), nullable=True)
    reported_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Date et lieu
    incident_date = db.Column(db.Date, nullable=False)
    incident_time = db.Column(db.String(10), nullable=True)
    location = db.Column(db.String(255), nullable=True)

    # Classification & Statut
    category = db.Column(db.String(50), nullable=False, default="vehicule")
    severity = db.Column(db.String(50), nullable=False, default="modere")
    status = db.Column(db.String(50), nullable=False, default="signale")
    shooting_impact = db.Column(db.String(50), nullable=False, default="aucun")

    # Circonstances & Actions
    description = db.Column(db.Text, nullable=True)
    immediate_actions = db.Column(db.Text, nullable=True)

    # Liens inspections (départ ou retour)
    checkout_id = db.Column(
        db.Integer,
        db.ForeignKey("checkout_vehicles.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    checkin_id = db.Column(
        db.Integer,
        db.ForeignKey("checkin_vehicles.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Suivi financier & Assurance
    estimated_cost = db.Column(db.Numeric(10, 2), nullable=True)
    actual_cost = db.Column(db.Numeric(10, 2), nullable=True)
    insurance_declared = db.Column(db.Boolean, default=False, nullable=False)
    insurance_reference = db.Column(db.String(100), nullable=True)
    insurance_notes = db.Column(db.Text, nullable=True)

    # Fichiers & Photos (stockage JSON)
    photos = db.Column(db.Text, nullable=True)
    documents = db.Column(db.Text, nullable=True)

    # Clôture & Résolution
    resolution_notes = db.Column(db.Text, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

    # ═══════════ DOUBLE SIGNATURE & SCELLEMENT ═══════════
    # 1. Visa & Signature Belle Vitesse (Technicien / Déclarant)
    bv_signer_name = db.Column(db.String(150), nullable=True)
    bv_signer_role = db.Column(db.String(150), nullable=True)
    bv_signature_data = db.Column(db.Text(length=16777215), nullable=True)
    bv_signed_at = db.Column(db.DateTime, nullable=True)
    bv_signer_ip = db.Column(db.String(45), nullable=True)

    # 2. Visa & Signature Production (Sur place ou à distance)
    prod_signer_name = db.Column(db.String(150), nullable=True)
    prod_signer_role = db.Column(db.String(150), nullable=True)
    prod_signature_data = db.Column(db.Text(length=16777215), nullable=True)
    prod_signed_at = db.Column(db.DateTime, nullable=True)
    prod_signer_ip = db.Column(db.String(45), nullable=True)

    # 3. Statut de signature, empreinte d'intégrité & archive
    # "unsigned" (non signé), "signed_bv" (signé BV), "pending_prod" (invitation envoyée), "signed" (scellé)
    signature_status = db.Column(db.String(30), default="unsigned", nullable=False)
    signed_pdf_path = db.Column(db.String(500), nullable=True)
    hash = db.Column(db.String(255), nullable=True)
    pdf_file_hash = db.Column(db.String(64), nullable=True)

    # Horodatages & Soft-Delete
    created_at = db.Column(db.DateTime, default=_utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)

    # Relations SQLAlchemy
    project = db.relationship("Project", backref=db.backref("incidents", lazy=True))
    reporter = db.relationship("User", backref=db.backref("reported_incidents", lazy=True))
    checkout = db.relationship("CheckoutVehicle", backref=db.backref("incidents", lazy=True))
    checkin = db.relationship("CheckinVehicle", backref=db.backref("incidents", lazy=True))

    @property
    def is_critical(self):
        return self.severity == "critique"

    @property
    def is_active(self):
        return self.status in ("signale", "en_expertise", "en_reparation", "assurance")

    @property
    def photos_list(self):
        if not self.photos:
            return []
        try:
            return json.loads(self.photos)
        except Exception:
            return []

    @property
    def documents_list(self):
        if not self.documents:
            return []
        try:
            return json.loads(self.documents)
        except Exception:
            return []

    @property
    def is_signed_bv(self) -> bool:
        """Indique si Belle Vitesse a visé et signé le constat."""
        return bool(self.bv_signed_at and self.bv_signature_data)

    @property
    def is_signed_prod(self) -> bool:
        """Indique si la Production a visé et signé le constat."""
        return bool(self.prod_signed_at and self.prod_signature_data)

    @property
    def is_fully_signed(self) -> bool:
        """Indique si la double signature contradictoire est complète."""
        return self.signature_status == "signed" or (self.is_signed_bv and self.is_signed_prod)

    @property
    def signature_status_label(self) -> str:
        if self.is_fully_signed:
            return "Signé & Scellé"
        if self.signature_status == "signed_bv":
            return "Visé BV (En attente Prod)"
        if self.signature_status == "signed_prod":
            return "Signé Prod (En attente BV)"
        if self.signature_status == "pending_prod":
            return "En attente Production"
        if self.is_signed_bv:
            return "Signé par BV"
        if self.is_signed_prod:
            return "Signé par la Production"
        return "Non signé"

    def to_dict(self):
        return {
            "id": self.id,
            "incident_number": self.incident_number,
            "title": self.title,
            "project_id": self.project_id,
            "project_name": self.project.name if self.project else None,
            "vehicle_id": self.vehicle_id,
            "equipment_name": self.equipment_name,
            "reported_by_id": self.reported_by_id,
            "reporter_name": f"{self.reporter.firstname} {self.reporter.lastname}" if self.reporter else None,
            "incident_date": self.incident_date.isoformat() if self.incident_date else None,
            "incident_time": self.incident_time,
            "location": self.location,
            "category": self.category,
            "severity": self.severity,
            "status": self.status,
            "shooting_impact": self.shooting_impact,
            "description": self.description,
            "immediate_actions": self.immediate_actions,
            "estimated_cost": float(self.estimated_cost) if self.estimated_cost is not None else None,
            "actual_cost": float(self.actual_cost) if self.actual_cost is not None else None,
            "insurance_declared": self.insurance_declared,
            "insurance_reference": self.insurance_reference,
            "insurance_notes": self.insurance_notes,
            "photos": self.photos_list,
            "documents": self.documents_list,
            "resolution_notes": self.resolution_notes,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            # Données de signature
            "bv_signer_name": self.bv_signer_name,
            "bv_signer_role": self.bv_signer_role,
            "bv_signature_data": self.bv_signature_data,
            "bv_signed_at": self.bv_signed_at.isoformat() if self.bv_signed_at else None,
            "prod_signer_name": self.prod_signer_name,
            "prod_signer_role": self.prod_signer_role,
            "prod_signature_data": self.prod_signature_data,
            "prod_signed_at": self.prod_signed_at.isoformat() if self.prod_signed_at else None,
            "signature_status": self.signature_status,
            "signature_status_label": self.signature_status_label,
            "is_signed_bv": self.is_signed_bv,
            "is_signed_prod": self.is_signed_prod,
            "is_fully_signed": self.is_fully_signed,
            "signed_pdf_path": self.signed_pdf_path,
            "hash": self.hash,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Incident {self.incident_number} - {self.title}>"


class IncidentToken(db.Model, TokenMixin):
    """Jeton de session sécurisé pour la signature d'un incident par la Production."""
    __tablename__ = "incident_tokens"

    incident_id = db.Column(
        db.Integer,
        db.ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    recipient_email = db.Column(db.String(255), nullable=True)
    signature = db.Column(db.Text(length=16777215), nullable=True)

    incident = db.relationship("Incident", backref=db.backref("tokens", lazy=True, cascade="all, delete-orphan"))


class IncidentSignedDocument(db.Model, SignedDocumentMixin):
    """Archive certifiée d'un incident contradictoirement signé et scellé."""
    __tablename__ = "incident_signed_documents"

    incident_number = db.Column(db.String(50), primary_key=True)
    incident_id = db.Column(db.Integer, nullable=True, index=True)
