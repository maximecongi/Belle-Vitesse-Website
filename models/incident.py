import json
from models.db import db, generate_inspection_number, _utcnow


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
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Incident {self.incident_number} - {self.title}>"
