from models.db import db, generate_inspection_number, _utcnow


class CheckoutVehicle(db.Model):
    """Modèle représentant le contrôle de sécurité (Inspection) au départ d'un véhicule."""
    __tablename__ = "checkout_vehicles"

    id = db.Column(db.Integer, primary_key=True)
    inspection_number = db.Column(
        db.String(50), unique=True, default=lambda: generate_inspection_number("BVCO"))
    # in_progress (en cours), pending (en attente), signed (signé), etc.
    status = db.Column(db.String(50))
    project_id = db.Column(
        db.Integer, db.ForeignKey("projects.id"), index=True)
    controller_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), index=True)
    inspection_date = db.Column(db.Date)
    # Identifiant du véhicule concerné (eCar, eBike, eTrike, etc.)
    vehicle_id = db.Column(db.String(100), index=True)
    battery_level = db.Column(db.Integer)

    # États des points de contrôle (ok, damage, missing, N/A)
    tire_status = db.Column(db.String(50))
    brake_status = db.Column(db.String(50))
    exterior_lighting_status = db.Column(db.String(50))
    horn_status = db.Column(db.String(50))
    gearbox_status = db.Column(db.String(50))
    engine_assistance_status = db.Column(db.String(50))
    driving_test_status = db.Column(db.String(50))
    wheel_tightness_status = db.Column(db.String(50))
    chain_tension_status = db.Column(db.String(50))
    roll_bar_tightness_status = db.Column(db.String(50))
    seat_plate_tightness_status = db.Column(db.String(50))
    seat_belt_status = db.Column(db.String(50))
    passenger_helmets_status = db.Column(db.String(50))
    pilot_protections_status = db.Column(db.String(50))
    communication_system_status = db.Column(db.String(50))
    accessories_case_status = db.Column(db.String(50))

    # Stockage JSON des chemins de photos intérieures
    interior_photos = db.Column(db.Text)
    # Stockage JSON des chemins de photos extérieures
    exterior_photos = db.Column(db.Text)
    notes = db.Column(db.Text)
    # Indique si le véhicule est prêt pour le départ
    vehicle_ready = db.Column(db.Boolean, default=False)
    # Chemin du PDF d'inspection généré après signature
    signed_pdf_path = db.Column(db.String(500))

    hash = db.Column(db.String(255))  # Empreinte numérique pour l'intégrité
    created_at = db.Column(db.DateTime, default=_utcnow, index=True)

    # Soft-delete support
    deleted_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        """Convertit l'objet en dictionnaire pour les réponses API."""
        return {
            "id": self.id,
            "inspection_number": self.inspection_number,
            "status": self.status,
            "project_id": self.project_id,
            "controller_id": self.controller_id,
            "inspection_date": self.inspection_date.isoformat() if self.inspection_date else None,
            "vehicle_id": self.vehicle_id,
            "battery_level": self.battery_level,
            "vehicle_ready": self.vehicle_ready,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }

    def __repr__(self):
        return f"<CheckoutVehicle {self.inspection_number}>"


class CheckinVehicle(db.Model):
    """Modèle représentant le contrôle de sécurité (Inspection) au retour d'un véhicule."""
    __tablename__ = "checkin_vehicles"

    id = db.Column(db.Integer, primary_key=True)
    inspection_number = db.Column(
        db.String(50), unique=True, default=lambda: generate_inspection_number("BVCI"))
    status = db.Column(db.String(50))
    project_id = db.Column(
        db.Integer, db.ForeignKey("projects.id"), index=True)
    controller_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), index=True)
    inspection_date = db.Column(db.Date)
    vehicle_id = db.Column(db.String(100), index=True)
    battery_level = db.Column(db.Integer)

    # États des points de contrôle
    tire_status = db.Column(db.String(50))
    brake_status = db.Column(db.String(50))
    exterior_lighting_status = db.Column(db.String(50))
    horn_status = db.Column(db.String(50))
    gearbox_status = db.Column(db.String(50))
    engine_assistance_status = db.Column(db.String(50))
    driving_test_status = db.Column(db.String(50))
    wheel_tightness_status = db.Column(db.String(50))
    chain_tension_status = db.Column(db.String(50))
    roll_bar_tightness_status = db.Column(db.String(50))
    seat_plate_tightness_status = db.Column(db.String(50))
    seat_belt_status = db.Column(db.String(50))
    passenger_helmets_status = db.Column(db.String(50))
    pilot_protections_status = db.Column(db.String(50))
    communication_system_status = db.Column(db.String(50))
    accessories_case_status = db.Column(db.String(50))

    interior_photos = db.Column(db.Text)
    exterior_photos = db.Column(db.Text)
    notes = db.Column(db.Text)
    vehicle_ready = db.Column(db.Boolean, default=False)
    signed_pdf_path = db.Column(db.String(500))

    hash = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=_utcnow, index=True)

    # Soft-delete support
    deleted_at = db.Column(db.DateTime, nullable=True)

    # Relation vers l'utilisateur responsable du contrôle
    controller = db.relationship(
        "User", backref="controller_checkins", lazy=True)

    def to_dict(self):
        """Convertit l'objet en dictionnaire pour les réponses API."""
        return {
            "id": self.id,
            "inspection_number": self.inspection_number,
            "status": self.status,
            "project_id": self.project_id,
            "controller_id": self.controller_id,
            "inspection_date": self.inspection_date.isoformat() if self.inspection_date else None,
            "vehicle_id": self.vehicle_id,
            "battery_level": self.battery_level,
            "vehicle_ready": self.vehicle_ready,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }

    def __repr__(self):
        return f"<CheckinVehicle {self.inspection_number}>"


class VehicleCheckpointConfig(db.Model):
    """Configuration personnalisée des points de contrôle par véhicule."""
    __tablename__ = "vehicle_checkpoint_configs"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.String(100), unique=True, nullable=False)
    # Stocke les clés activées : {"tires": true, "brakes": false, ...}
    config = db.Column(db.JSON, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=_utcnow, onupdate=_utcnow)

    def __repr__(self):
        return f"<VehicleCheckpointConfig {self.vehicle_id}>"
