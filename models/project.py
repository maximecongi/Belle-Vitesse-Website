from models.db import db, generate_inspection_number


class Production(db.Model):
    """Modèle représentant une société de production cliente."""
    __tablename__ = "productions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.String(500))
    mail = db.Column(db.String(255))
    phone = db.Column(db.String(50))

    # Relations
    # Liste des projets associés à cette production
    projects = db.relationship("Project", backref="production", lazy=True)
    # Liste des contacts professionnels rattachés à cette production
    contacts = db.relationship("Contact", backref="production_rel", lazy=True)

    def to_dict(self):
        """Convertit l'objet en dictionnaire pour les réponses API."""
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "mail": self.mail,
            "phone": self.phone,
        }

    def __repr__(self):
        return f"<Production {self.name}>"


class Contact(db.Model):
    """Modèle représentant un contact physique (Pilote, Chargé de prod, etc.)."""
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(50))
    mail = db.Column(db.String(255))
    production_id = db.Column(
        db.Integer, db.ForeignKey("productions.id"), nullable=True, index=True)
    job_title = db.Column(db.String(150))

    def to_dict(self):
        """Convertit l'objet en dictionnaire pour les réponses API."""
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "phone": self.phone,
            "mail": self.mail,
            "production_id": self.production_id,
            "job_title": self.job_title,
        }

    def __repr__(self):
        return f"<Contact {self.first_name} {self.last_name}>"


class Project(db.Model):
    """Modèle central représentant un projet (tournage)."""
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.String(50), unique=True, default=lambda: generate_inspection_number("BVPR"))
    name = db.Column(db.String(255), nullable=False)
    production_id = db.Column(db.Integer, db.ForeignKey(
        "productions.id"), nullable=False, index=True)
    pilot_contact_id = db.Column(db.Integer, db.ForeignKey(
        "contacts.id"), nullable=True, index=True)
    production_contact_id = db.Column(db.Integer, db.ForeignKey(
        "contacts.id"), nullable=True, index=True)
    dop_contact_id = db.Column(db.Integer, db.ForeignKey(
        "contacts.id"), nullable=True, index=True)
    first_ac_contact_id = db.Column(db.Integer, db.ForeignKey(
        "contacts.id"), nullable=True, index=True)
    key_grip_contact_id = db.Column(db.Integer, db.ForeignKey(
        "contacts.id"), nullable=True, index=True)
    departure_date = db.Column(db.Date)  # Date de départ (enlèvement)
    shoot_start_date = db.Column(db.Date)  # Date de début de tournage
    shoot_end_date = db.Column(db.Date)  # Date de fin de tournage
    return_date = db.Column(db.Date)  # Date de retour prévu
    # Liste des identifiants de véhicules séparés par virgules ex: "3,5"
    vehicles_to_check = db.Column(db.String(500))
    # Liste des identifiants de têtes séparés par virgules ex: "recXX,recYY"
    heads_to_check = db.Column(db.String(500))
    notes = db.Column(db.Text)  # Demandes spécifiques

    # Soft-delete support
    deleted_at = db.Column(db.DateTime, nullable=True)

    # Tracking de la dernière action
    last_action_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    # Relations
    # Liste des contrôles au départ effectués pour ce projet
    checkout_vehicles = db.relationship(
        "CheckoutVehicle", backref="project", lazy=True)
    # Liste des contrôles au retour effectués pour ce projet
    checkin_vehicles = db.relationship(
        "CheckinVehicle", backref="project", lazy=True)
    # Contact pilote principal du projet
    pilot_contact = db.relationship(
        "Contact", foreign_keys=[pilot_contact_id], backref="pilot_projects", lazy=True)
    # Contact production référent pour le projet
    production_contact = db.relationship(
        "Contact", foreign_keys=[production_contact_id], backref="production_projects", lazy=True)
    # Contact DOP du projet
    dop_contact = db.relationship(
        "Contact", foreign_keys=[dop_contact_id], backref="dop_projects", lazy=True)
    # Contact 1er Assistant Caméra du projet
    first_ac_contact = db.relationship(
        "Contact", foreign_keys=[first_ac_contact_id], backref="first_ac_projects", lazy=True)
    # Contact Chef Machiniste du projet
    key_grip_contact = db.relationship(
        "Contact", foreign_keys=[key_grip_contact_id], backref="key_grip_projects", lazy=True)
    # Décharge pilote associée (unique pour le projet)
    pilot_waiver = db.relationship(
        "PilotWaiver", backref="project", uselist=False, lazy=True)
    # Décharge production associée (unique pour le projet)
    production_waiver = db.relationship(
        "ProductionWaiver", backref="project", uselist=False, lazy=True)
    # Utilisateur ayant effectué la dernière action
    last_action_by = db.relationship(
        "User", foreign_keys=[last_action_by_id], lazy=True)

    def to_dict(self):
        """Convertit l'objet en dictionnaire pour les réponses API."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "production_id": self.production_id,
            "pilot_contact_id": self.pilot_contact_id,
            "production_contact_id": self.production_contact_id,
            "dop_contact_id": self.dop_contact_id,
            "first_ac_contact_id": self.first_ac_contact_id,
            "key_grip_contact_id": self.key_grip_contact_id,
            "departure_date": self.departure_date.isoformat() if self.departure_date else None,
            "shoot_start_date": self.shoot_start_date.isoformat() if self.shoot_start_date else None,
            "shoot_end_date": self.shoot_end_date.isoformat() if self.shoot_end_date else None,
            "return_date": self.return_date.isoformat() if self.return_date else None,
            "vehicles_to_check": self.vehicles_to_check,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }

    def __repr__(self):
        return f"<Project {self.name}>"
