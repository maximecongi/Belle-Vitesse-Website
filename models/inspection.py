from models.db import db, generate_inspection_number, _utcnow


class InspectionCheckpoint(db.Model):
    """Résultat d'évaluation d'un point de contrôle pour une inspection spécifique (départ ou retour)."""
    __tablename__ = "inspection_checkpoints"

    id = db.Column(db.Integer, primary_key=True)

    # Clé étrangère vers le départ OU le retour (avec suppression en cascade)
    checkout_id = db.Column(
        db.Integer,
        db.ForeignKey("checkout_vehicles.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    checkin_id = db.Column(
        db.Integer,
        db.ForeignKey("checkin_vehicles.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    # Clé canonique (ex: 'tires', 'brakes')
    checkpoint_key = db.Column(db.String(100), nullable=False, index=True)

    # Référence optionnelle à la définition formelle
    checkpoint_id = db.Column(
        db.Integer,
        db.ForeignKey("checkpoint_definitions.id", ondelete="SET NULL"),
        nullable=True
    )

    # Statut ('ok', 'warning', 'critical', 'not_applicable', 'pending')
    status = db.Column(db.String(50), nullable=True)

    # Valeur textuelle ou mesure (ex: niveau batterie ou relevé de pression)
    value = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    # Relation vers la définition de point de contrôle
    definition = db.relationship("CheckpointDefinition", lazy="joined")

    __table_args__ = (
        db.UniqueConstraint("checkout_id", "checkpoint_key", name="uq_checkout_checkpoint"),
        db.UniqueConstraint("checkin_id", "checkpoint_key", name="uq_checkin_checkpoint"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "checkout_id": self.checkout_id,
            "checkin_id": self.checkin_id,
            "checkpoint_key": self.checkpoint_key,
            "checkpoint_id": self.checkpoint_id,
            "status": self.status,
            "value": self.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        target = f"checkout={self.checkout_id}" if self.checkout_id else f"checkin={self.checkin_id}"
        return f"<InspectionCheckpoint {self.checkpoint_key}={self.status} ({target})>"


class CheckoutVehicle(db.Model):
    """Modèle représentant le contrôle de sécurité (Inspection) au départ d'un véhicule."""
    __tablename__ = "checkout_vehicles"

    id = db.Column(db.Integer, primary_key=True)
    inspection_number = db.Column(
        db.String(50), unique=True, default=lambda: generate_inspection_number("BVCO"))
    status = db.Column(db.String(50))
    project_id = db.Column(
        db.Integer, db.ForeignKey("projects.id"), index=True)
    controller_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), index=True)
    inspection_date = db.Column(db.Date)
    vehicle_id = db.Column(db.String(100), index=True)
    battery_level = db.Column(db.Integer)

    # Relation dynamique avec les résultats des points de contrôle
    checkpoints = db.relationship(
        "InspectionCheckpoint",
        backref="checkout",
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="[InspectionCheckpoint.checkout_id]"
    )

    # Stockage JSON des chemins de photos intérieures
    interior_photos = db.Column(db.Text)
    # Stockage JSON des chemins de photos extérieures
    exterior_photos = db.Column(db.Text)
    notes = db.Column(db.Text)
    # Indique si le véhicule est prêt pour le départ
    vehicle_ready = db.Column(db.Boolean, default=False)
    # Chemin du PDF d'inspection généré après signature
    signed_pdf_path = db.Column(db.String(500))

    hash = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=_utcnow, index=True)

    # Soft-delete support
    deleted_at = db.Column(db.DateTime, nullable=True)

    @property
    def checkpoint_statuses(self) -> dict:
        """Retourne un dictionnaire {checkpoint_key: status}."""
        return {cp.checkpoint_key: cp.status for cp in self.checkpoints}

    def get_checkpoint_status(self, key: str, default: str = "—") -> str:
        """Récupère la valeur d'un statut par sa clé."""
        return self.checkpoint_statuses.get(key, default)

    @property
    def checkpoint_values(self) -> dict:
        """Retourne un dictionnaire {checkpoint_key: value} pour les points de type mesure/valeur."""
        return {cp.checkpoint_key: cp.value for cp in self.checkpoints if cp.value is not None}

    def get_checkpoint_value(self, key: str, default: str = None) -> str:
        """Récupère la valeur mesurée ou saisie d'un point par sa clé."""
        return self.checkpoint_values.get(key, default)

    def set_checkpoint_status(self, key: str, status: str, value: str = None, checkpoint_id: int = None):
        """Met à jour ou ajoute un statut de point de contrôle."""
        for cp in self.checkpoints:
            if cp.checkpoint_key == key:
                cp.status = status
                if value is not None:
                    cp.value = value
                if checkpoint_id is not None:
                    cp.checkpoint_id = checkpoint_id
                return cp

        new_cp = InspectionCheckpoint(
            checkpoint_key=key,
            status=status,
            value=value,
            checkpoint_id=checkpoint_id
        )
        self.checkpoints.append(new_cp)
        return new_cp

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
            "checkpoints": self.checkpoint_statuses,
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

    # Relation dynamique avec les résultats des points de contrôle
    checkpoints = db.relationship(
        "InspectionCheckpoint",
        backref="checkin",
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="[InspectionCheckpoint.checkin_id]"
    )

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

    @property
    def checkpoint_statuses(self) -> dict:
        """Retourne un dictionnaire {checkpoint_key: status}."""
        return {cp.checkpoint_key: cp.status for cp in self.checkpoints}

    def get_checkpoint_status(self, key: str, default: str = "—") -> str:
        """Récupère la valeur d'un statut par sa clé."""
        return self.checkpoint_statuses.get(key, default)

    @property
    def checkpoint_values(self) -> dict:
        """Retourne un dictionnaire {checkpoint_key: value} pour les points de type mesure/valeur."""
        return {cp.checkpoint_key: cp.value for cp in self.checkpoints if cp.value is not None}

    def get_checkpoint_value(self, key: str, default: str = None) -> str:
        """Récupère la valeur mesurée ou saisie d'un point par sa clé."""
        return self.checkpoint_values.get(key, default)

    def set_checkpoint_status(self, key: str, status: str, value: str = None, checkpoint_id: int = None):
        """Met à jour ou ajoute un statut de point de contrôle."""
        for cp in self.checkpoints:
            if cp.checkpoint_key == key:
                cp.status = status
                if value is not None:
                    cp.value = value
                if checkpoint_id is not None:
                    cp.checkpoint_id = checkpoint_id
                return cp

        new_cp = InspectionCheckpoint(
            checkpoint_key=key,
            status=status,
            value=value,
            checkpoint_id=checkpoint_id
        )
        self.checkpoints.append(new_cp)
        return new_cp

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
            "checkpoints": self.checkpoint_statuses,
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
