from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random
import string

db = SQLAlchemy()


def generate_inspection_number(prefix):
    suffix = ''.join(random.choices(
        string.ascii_uppercase + string.digits, k=12))
    return f"{prefix}-{suffix}"


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String(100), nullable=False)
    lastname = db.Column(db.String(100), nullable=False)
    mail = db.Column(db.String(255), unique=True, nullable=False)
    phone = db.Column(db.String(50))
    job = db.Column(db.String(100))
    role = db.Column(db.String(50))  # ex: Administrator, Manager

    # Relations
    checkout_vehicles = db.relationship(
        "CheckoutVehicle", backref="responsible_user", lazy=True)

    @property
    def role_lower(self):
        return self.role.lower() if self.role else 'user'

    def __repr__(self):
        return f"<User {self.firstname} {self.lastname}>"


class Production(db.Model):
    __tablename__ = "productions"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(255), nullable=False)
    adresse = db.Column(db.String(500))
    mail = db.Column(db.String(255))
    phone = db.Column(db.String(50))

    # Relations
    projects = db.relationship("Project", backref="production", lazy=True)
    contacts = db.relationship("Contact", backref="production_rel", lazy=True)

    def __repr__(self):
        return f"<Production {self.nom}>"


class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)
    prenom = db.Column(db.String(100), nullable=False)
    nom = db.Column(db.String(100), nullable=False)
    telephone = db.Column(db.String(50))
    mail = db.Column(db.String(255))
    production_id = db.Column(
        db.Integer, db.ForeignKey("productions.id"), nullable=True, index=True)
    metier = db.Column(db.String(150))

    def __repr__(self):
        return f"<Contact {self.prenom} {self.nom}>"


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.String(50), unique=True, default=lambda: generate_inspection_number("BVPR"))
    nom = db.Column(db.String(255), nullable=False)
    production_id = db.Column(db.Integer, db.ForeignKey(
        "productions.id"), nullable=False, index=True)
    contact_pilote_id = db.Column(db.Integer, db.ForeignKey(
        "contacts.id"), nullable=True, index=True)
    contact_production_id = db.Column(db.Integer, db.ForeignKey(
        "contacts.id"), nullable=True, index=True)
    date_depart = db.Column(db.Date)
    date_debut_tournage = db.Column(db.Date)
    date_fin_tournage = db.Column(db.Date)
    date_retour = db.Column(db.Date)
    # liste séparée par virgules ex: "eCar, eBike"
    vehicules_a_controler = db.Column(db.String(500))

    # Relations
    checkout_vehicles = db.relationship(
        "CheckoutVehicle", backref="project", lazy=True)
    checkin_vehicles = db.relationship(
        "CheckinVehicle", backref="project", lazy=True)
    contact_pilote_rel = db.relationship(
        "Contact", foreign_keys=[contact_pilote_id], backref="projects_as_pilote", lazy=True)
    contact_production_rel = db.relationship(
        "Contact", foreign_keys=[contact_production_id], backref="projects_as_production", lazy=True)
    pilot_waiver = db.relationship(
        "PilotWaiver", backref="project", uselist=False, lazy=True)
    production_waiver = db.relationship(
        "ProductionWaiver", backref="project", uselist=False, lazy=True)

    def __repr__(self):
        return f"<Project {self.nom}>"


class PilotWaiver(db.Model):
    __tablename__ = "pilot_waivers"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey(
        "projects.id"), unique=True, nullable=False, index=True)
    waiver_id = db.Column(
        db.String(50), unique=True, default=lambda: generate_inspection_number("BVDW"))

    project_name = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default="to_generate", nullable=False)
    generated_at = db.Column(db.DateTime, nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    signed_at = db.Column(db.DateTime, nullable=True)

    # Snapshot data
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
    signature_token = db.Column(
        db.String(36), unique=True, nullable=True, index=True)
    signature_data = db.Column(
        db.Text(length=16777215), nullable=True)  # MEDIUMTEXT
    signed_pdf_path = db.Column(db.String(500), nullable=True)

    # Signature Traceability
    signer_ip = db.Column(db.String(45), nullable=True)

    # Attachments
    pilot_license_path = db.Column(db.String(500), nullable=True)
    pilot_insurance_path = db.Column(db.String(500), nullable=True)
    pilot_identity_path = db.Column(db.String(500), nullable=True)

    # Webhook
    webhook_triggered_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<PilotWaiver {self.project_id} - {self.status}>"


class ProductionWaiver(db.Model):
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

    # Snapshot data
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
    signature_token = db.Column(
        db.String(36), unique=True, nullable=True, index=True)
    signature_data = db.Column(
        db.Text(length=16777215), nullable=True)  # MEDIUMTEXT
    signed_pdf_path = db.Column(db.String(500), nullable=True)

    # Signature Traceability
    signer_ip = db.Column(db.String(45), nullable=True)

    # Attachments
    production_insurance_path = db.Column(db.String(500), nullable=True)

    # Webhook
    webhook_triggered_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<ProductionWaiver {self.project_id} - {self.status}>"


class CheckoutVehicle(db.Model):
    """Inspection au départ du véhicule"""
    __tablename__ = "checkout_vehicles"

    id = db.Column(db.Integer, primary_key=True)
    numero_inspection = db.Column(
        db.String(50), unique=True, default=lambda: generate_inspection_number("BVCO"))
    etat_controle = db.Column(db.String(50))  # En cours, Validé, etc.
    project_id = db.Column(
        db.Integer, db.ForeignKey("projects.id"), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    date_controle = db.Column(db.Date)
    # eCar, eBike, eTrike...
    vehicule_controle = db.Column(db.String(100), index=True)
    kilometrage_depart = db.Column(db.Float)
    charge_batterie_depart = db.Column(db.Float)
    etat_pneus = db.Column(db.String(50))
    roue_secours = db.Column(db.String(50))
    niveau_huile = db.Column(db.String(50))
    niveau_liquide_refroidissement = db.Column(db.String(50))
    etat_freins = db.Column(db.String(50))
    etat_eclairage_exterieur = db.Column(db.String(50))
    demarrage_moteur = db.Column(db.String(50))
    etat_essuie_glaces = db.Column(db.String(50))
    etat_klaxon = db.Column(db.String(50))
    presence_triangle_gilet = db.Column(db.String(50))
    presence_extincteur = db.Column(db.String(50))
    photos_interieur = db.Column(db.Text)  # JSON ou chemins séparés
    photos_exterieur = db.Column(db.Text)
    observations = db.Column(db.Text)
    vehicule_pret_depart = db.Column(db.Boolean, default=False)
    pdf_scelle = db.Column(db.String(500))
    hash = db.Column(db.String(255))
    message_action = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<CheckoutVehicle {self.numero_inspection}>"


class CheckinVehicle(db.Model):
    """Inspection au retour du véhicule"""
    __tablename__ = "checkin_vehicles"

    id = db.Column(db.Integer, primary_key=True)
    numero_inspection = db.Column(
        db.String(50), unique=True, default=lambda: generate_inspection_number("BVCI"))
    etat_controle = db.Column(db.String(50))
    project_id = db.Column(
        db.Integer, db.ForeignKey("projects.id"), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    date_controle = db.Column(db.Date)
    vehicule_controle = db.Column(db.String(100), index=True)
    kilometrage_retour = db.Column(db.Float)
    charge_batterie_retour = db.Column(db.Float)
    etat_pneus = db.Column(db.String(50))
    roue_secours = db.Column(db.String(50))
    niveau_huile = db.Column(db.String(50))
    niveau_liquide_refroidissement = db.Column(db.String(50))
    etat_freins = db.Column(db.String(50))
    etat_eclairage_exterieur = db.Column(db.String(50))
    demarrage_moteur = db.Column(db.String(50))
    etat_essuie_glaces = db.Column(db.String(50))
    etat_klaxon = db.Column(db.String(50))
    presence_triangle_gilet = db.Column(db.String(50))
    presence_extincteur = db.Column(db.String(50))
    photos_interieur = db.Column(db.Text)
    photos_exterieur = db.Column(db.Text)
    observations = db.Column(db.Text)
    vehicule_pret_retour = db.Column(db.Boolean, default=False)
    pdf_scelle = db.Column(db.String(500))
    hash = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relation vers user (responsable du contrôle)
    responsible = db.relationship(
        "User", backref="checkin_vehicles", lazy=True)

    def __repr__(self):
        return f"<CheckinVehicle {self.numero_inspection}>"


class NewsletterSubscriber(db.Model):
    __tablename__ = "newsletter_subscribers"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    subscribed_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<NewsletterSubscriber {self.email}>"


class PilotWaiverSignedDocument(db.Model):
    __tablename__ = "pilot_waiver_signed_documents"

    waiver_id = db.Column(db.String(50), primary_key=True)  # Format BVDW-...
    hash = db.Column(db.String(255), nullable=False)
    pdf_file_hash = db.Column(db.String(64))
    data_snapshot = db.Column(db.JSON, nullable=False)
    signature = db.Column(db.Text(length=16777215))  # MEDIUMTEXT
    pdf_url = db.Column(db.Text)
    signed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ProductionWaiverSignedDocument(db.Model):
    __tablename__ = "production_waiver_signed_documents"

    waiver_id = db.Column(db.String(50), primary_key=True)  # Format BVPW-...
    hash = db.Column(db.String(255), nullable=False)
    pdf_file_hash = db.Column(db.String(64))
    data_snapshot = db.Column(db.JSON, nullable=False)
    signature = db.Column(db.Text(length=16777215))  # MEDIUMTEXT
    pdf_url = db.Column(db.Text)
    signed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CheckoutSignedDocument(db.Model):
    __tablename__ = "checkout_signed_documents"

    inspection_id = db.Column(db.String(255), primary_key=True)
    hash = db.Column(db.String(255), nullable=False)
    pdf_file_hash = db.Column(db.String(64))
    data_snapshot = db.Column(db.JSON, nullable=False)
    signature = db.Column(db.Text(length=16777215))  # MEDIUMTEXT equivalent
    pdf_url = db.Column(db.Text)
    signed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CheckoutToken(db.Model):
    __tablename__ = "checkout_tokens"

    token = db.Column(db.String(36), primary_key=True)
    record_id = db.Column(db.String(255), nullable=False)
    inspection_id = db.Column(db.String(255), nullable=False)
    signature = db.Column(db.Text(length=16777215))
    created_at = db.Column(db.DateTime, nullable=False,
                           default=datetime.utcnow)
    # expires_at is a virtual generated column in MySQL (created_at + 24h)
    # We mark it as FetchedValue so SQLAlchemy doesn't try to INSERT/UPDATE it.
    expires_at = db.Column(db.DateTime, server_default=db.FetchedValue())


class CheckinSignedDocument(db.Model):
    __tablename__ = "checkin_signed_documents"

    inspection_id = db.Column(db.String(255), primary_key=True)
    hash = db.Column(db.String(255), nullable=False)
    pdf_file_hash = db.Column(db.String(64))
    data_snapshot = db.Column(db.JSON, nullable=False)
    signature = db.Column(db.Text(length=16777215))  # MEDIUMTEXT equivalent
    pdf_url = db.Column(db.Text)
    signed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CheckinToken(db.Model):
    __tablename__ = "checkin_tokens"

    token = db.Column(db.String(36), primary_key=True)
    record_id = db.Column(db.String(255), nullable=False)
    inspection_id = db.Column(db.String(255), nullable=False)
    signature = db.Column(db.Text(length=16777215))
    created_at = db.Column(db.DateTime, nullable=False,
                           default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, server_default=db.FetchedValue())


class VehicleCheckpointConfig(db.Model):
    __tablename__ = "vehicle_checkpoint_configs"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.String(100), unique=True, nullable=False)
    # Stores enabled keys: {"tires": true, "brakes": false, ...}
    config = db.Column(db.JSON, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<VehicleCheckpointConfig {self.vehicle_id}>"


class SqlQueryLog(db.Model):
    __tablename__ = "sql_query_logs"

    # BigInteger for ID, DateTime for timestamp
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime(
        6), primary_key=True, default=datetime.utcnow)
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
