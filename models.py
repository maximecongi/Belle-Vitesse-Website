import random
import string
import uuid
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def generate_inspection_number(prefix):
    """Génère un identifiant unique aléatoire avec un préfixe donné (ex: BVPR-XXXX)."""
    suffix = ''.join(random.choices(
        string.ascii_uppercase + string.digits, k=12))
    return f"{prefix}-{suffix}"


class User(db.Model):
    """Modèle représentant un utilisateur du système (Administrateur, Manager, etc.)."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String(100), nullable=False)
    lastname = db.Column(db.String(100), nullable=False)
    mail = db.Column(db.String(255), unique=True, nullable=False)
    phone = db.Column(db.String(50))
    job = db.Column(db.String(100))
    role = db.Column(db.String(50))  # ex: Administrateur, Manager

    # Relations
    # Liste des check-outs effectués par cet utilisateur (contrôleur)
    controller_checkouts = db.relationship(
        "CheckoutVehicle", backref="controller", lazy=True)

    @property
    def role_lower(self):
        """Retourne le rôle en minuscules (par défaut 'user')."""
        return self.role.lower() if self.role else 'user'

    def to_dict(self):
        """Convertit l'objet en dictionnaire pour les réponses API."""
        return {
            "id": self.id,
            "firstname": self.firstname,
            "lastname": self.lastname,
            "mail": self.mail,
            "phone": self.phone,
            "job": self.job,
            "role": self.role,
        }

    def __repr__(self):
        return f"<User {self.firstname} {self.lastname}>"


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
    departure_date = db.Column(db.Date) # Date de départ (enlèvement)
    shoot_start_date = db.Column(db.Date) # Date de début de tournage
    shoot_end_date = db.Column(db.Date) # Date de fin de tournage
    return_date = db.Column(db.Date) # Date de retour prévu
    # Liste des identifiants de véhicules séparés par virgules ex: "3,5"
    vehicles_to_check = db.Column(db.String(500))
    notes = db.Column(db.Text) # Demandes spécifiques

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
    # Décharge pilote associée (unique pour le projet)
    pilot_waiver = db.relationship(
        "PilotWaiver", backref="project", uselist=False, lazy=True)
    # Décharge production associée (unique pour le projet)
    production_waiver = db.relationship(
        "ProductionWaiver", backref="project", uselist=False, lazy=True)

    def to_dict(self):
        """Convertit l'objet en dictionnaire pour les réponses API."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "production_id": self.production_id,
            "pilot_contact_id": self.pilot_contact_id,
            "production_contact_id": self.production_contact_id,
            "departure_date": self.departure_date.isoformat() if self.departure_date else None,
            "shoot_start_date": self.shoot_start_date.isoformat() if self.shoot_start_date else None,
            "shoot_end_date": self.shoot_end_date.isoformat() if self.shoot_end_date else None,
            "return_date": self.return_date.isoformat() if self.return_date else None,
            "vehicles_to_check": self.vehicles_to_check,
        }

    def __repr__(self):
        return f"<Project {self.name}>"


class PilotWaiver(db.Model):
    """Modèle représentant une décharge de responsabilité pour un pilote."""
    __tablename__ = "pilot_waivers"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey(
        "projects.id"), unique=True, nullable=False, index=True)
    waiver_id = db.Column(
        db.String(50), unique=True, default=lambda: generate_inspection_number("BVDW"))

    project_name = db.Column(db.String(255), nullable=True) # Copie du nom du projet au moment de la génération
    status = db.Column(db.String(20), default="to_generate", nullable=False) # Statut (to_generate, to_send, to_sign, signed)
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
        db.Text(length=16777215), nullable=True)  # Données de signature manuscrite (Base64)
    signed_pdf_path = db.Column(db.String(500), nullable=True) # Chemin relatif du PDF signé

    # Traçabilité de la signature
    signer_ip = db.Column(db.String(45), nullable=True)

    # Pièces jointes (photos/scans)
    pilot_license_path = db.Column(db.String(500), nullable=True)
    pilot_insurance_path = db.Column(db.String(500), nullable=True)
    pilot_identity_path = db.Column(db.String(500), nullable=True)

    # Webhook (n8n)
    webhook_triggered_at = db.Column(db.DateTime, nullable=True)

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
        }

    def __repr__(self):
        return f"<ProductionWaiver {self.project_id} - {self.status}>"


class CheckoutVehicle(db.Model):
    """Modèle représentant le contrôle de sécurité (Inspection) au départ d'un véhicule."""
    __tablename__ = "checkout_vehicles"

    id = db.Column(db.Integer, primary_key=True)
    inspection_number = db.Column(
        db.String(50), unique=True, default=lambda: generate_inspection_number("BVCO"))
    status = db.Column(db.String(50))  # in_progress (en cours), pending (en attente), signed (signé), etc.
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

    interior_photos = db.Column(db.Text)  # Stockage JSON des chemins de photos intérieures
    exterior_photos = db.Column(db.Text) # Stockage JSON des chemins de photos extérieures
    notes = db.Column(db.Text)
    vehicle_ready = db.Column(db.Boolean, default=False) # Indique si le véhicule est prêt pour le départ
    signed_pdf_path = db.Column(db.String(500)) # Chemin du PDF d'inspection généré après signature

    hash = db.Column(db.String(255)) # Empreinte numérique pour l'intégrité
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

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
        }

    def __repr__(self):
        return f"<CheckinVehicle {self.inspection_number}>"


class NewsletterSubscriber(db.Model):
    """Modèle représentant un abonné à la newsletter."""
    __tablename__ = "newsletter_subscribers"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    subscribed_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<NewsletterSubscriber {self.email}>"


# ── Mixins Partagés ──────────────────────────────────────────────

class TokenMixin:
    """Base pour tous les jetons (tokens) de signature à durée limitée."""
    token = db.Column(db.String(36), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False,
                           default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False,
                           server_default=db.FetchedValue())


class SignedDocumentMixin:
    """Base pour tous les documents signés archivés."""
    hash = db.Column(db.String(255), nullable=False) # Empreinte de l'intégrité des données
    pdf_file_hash = db.Column(db.String(64)) # Hash SHA-256 du fichier PDF binaire
    data_snapshot = db.Column(db.JSON, nullable=False) # Copie conforme des données au moment de la signature
    signature = db.Column(db.Text(length=16777215)) # Données de la signature (MEDIUMTEXT)
    pdf_url = db.Column(db.Text) # URL (ou chemin) vers le fichier PDF
    signed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


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


# ── Modèles de synchronisation dynamique Airtable ───────────────

class SyncRecordMixin:
    """Base pour les tables synchronisées depuis Airtable."""
    id = db.Column(db.String(255), primary_key=True) # ID d'enregistrement Airtable
    createdTime = db.Column(db.DateTime)
    fields = db.Column(db.JSON) # Contenu brut des champs Airtable
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Vehicle(db.Model, SyncRecordMixin):
    """Véhicules synchronisés depuis Airtable."""
    __tablename__ = "vehicles"


class Head(db.Model, SyncRecordMixin):
    """Têtes de caméra synchronisées depuis Airtable."""
    __tablename__ = "heads"


class GripCategory(db.Model, SyncRecordMixin):
    """Catégories de matériel Grip (Airtable)."""
    __tablename__ = "grips_categories"


class GripProduct(db.Model, SyncRecordMixin):
    """Produits Grip individuels (Airtable)."""
    __tablename__ = "grip_products"


class Config(db.Model, SyncRecordMixin):
    """Configurations spécifiques (Airtable)."""
    __tablename__ = "configs"


class Static(db.Model, SyncRecordMixin):
    """Données statiques de contenu (Airtable)."""
    __tablename__ = "static"


class VehicleCheckpointConfig(db.Model):
    """Configuration personnalisée des points de contrôle par véhicule."""
    __tablename__ = "vehicle_checkpoint_configs"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.String(100), unique=True, nullable=False)
    # Stocke les clés activées : {"tires": true, "brakes": false, ...}
    config = db.Column(db.JSON, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<VehicleCheckpointConfig {self.vehicle_id}>"


class SqlQueryLog(db.Model):
    """Journal des requêtes SQL (Monitoring de performance)."""
    __tablename__ = "sql_query_logs"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime(6), default=datetime.utcnow)
    user = db.Column(db.String(255), nullable=False, default='anonymous')
    ip_address = db.Column(db.String(50))
    endpoint = db.Column(db.String(255))
    method = db.Column(db.String(10))
    query = db.Column(db.Text, nullable=False)
    parameters = db.Column(db.Text)
    duration_ms = db.Column(db.Float)

    __table_args__ = (
        db.Index('idx_user_ts', 'user', 'timestamp'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8mb4',
        }
    )

    def __repr__(self):
        return f"<SqlQueryLog {self.id} user={self.user} endpoint={self.endpoint}>"


class EquipmentRate(db.Model):
    """Tarif jour HT pour un équipement (véhicule, tête, gimbal, grip, logistique)."""
    __tablename__ = "equipment_rates"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False, index=True)
    # Catégories : vehicle, head, gimbal, mount, logistics
    item_name = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    daily_rate = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    notes = db.Column(db.Text)
    source_record_id = db.Column(db.String(255), nullable=True)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """Convertit l'objet en dictionnaire pour les réponses API."""
        return {
            "id": self.id,
            "category": self.category,
            "item_name": self.item_name,
            "quantity": self.quantity,
            "daily_rate": float(self.daily_rate) if self.daily_rate else 0,
            "notes": self.notes or "",
            "display_order": self.display_order,
        }

    def __repr__(self):
        return f"<EquipmentRate {self.item_name} ({self.category})>"


class SalaryRate(db.Model):
    """Grille de salaire par position et type de contrat."""
    __tablename__ = "salary_rates"

    id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.String(100), nullable=False, index=True)
    position = db.Column(db.String(150), nullable=False)
    annexe = db.Column(db.String(255))
    base_hourly = db.Column(db.Numeric(10, 2))
    invoice_10h = db.Column(db.Numeric(10, 2))
    invoice_8h = db.Column(db.Numeric(10, 2))
    inter_10h = db.Column(db.Numeric(10, 2))
    inter_8h = db.Column(db.Numeric(10, 2))
    notes = db.Column(db.Text)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """Convertit l'objet en dictionnaire pour les réponses API."""
        return {
            "id": self.id,
            "group_name": self.group_name,
            "position": self.position,
            "annexe": self.annexe or "",
            "base_hourly": float(self.base_hourly) if self.base_hourly else 0,
            "invoice_10h": float(self.invoice_10h) if self.invoice_10h else 0,
            "invoice_8h": float(self.invoice_8h) if self.invoice_8h else 0,
            "inter_10h": float(self.inter_10h) if self.inter_10h else 0,
            "inter_8h": float(self.inter_8h) if self.inter_8h else 0,
            "notes": self.notes or "",
            "display_order": self.display_order,
        }

    def __repr__(self):
        return f"<SalaryRate {self.position} ({self.group_name})>"


class CalendarSubscription(db.Model):
    """Abonnement calendrier ICS sécurisé par token unique."""
    __tablename__ = "calendar_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(
        "users.id"), nullable=False, index=True)
    token = db.Column(db.String(36), unique=True,
                      nullable=False, default=lambda: str(uuid.uuid4()))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_accessed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", backref="calendar_subscriptions")

    def to_dict(self):
        """Convertit l'objet en dictionnaire pour les réponses API."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "token": self.token,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at else None,
        }

    def __repr__(self):
        return f"<CalendarSubscription user={self.user_id} active={self.is_active}>"
