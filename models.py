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
    controller_checkouts = db.relationship(
        "CheckoutVehicle", backref="controller", lazy=True)

    @property
    def role_lower(self):
        return self.role.lower() if self.role else 'user'

    def __repr__(self):
        return f"<User {self.firstname} {self.lastname}>"


class Production(db.Model):
    __tablename__ = "productions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.String(500))
    mail = db.Column(db.String(255))
    phone = db.Column(db.String(50))

    # Relations
    projects = db.relationship("Project", backref="production", lazy=True)
    contacts = db.relationship("Contact", backref="production_rel", lazy=True)

    def __repr__(self):
        return f"<Production {self.name}>"


class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(50))
    mail = db.Column(db.String(255))
    production_id = db.Column(
        db.Integer, db.ForeignKey("productions.id"), nullable=True, index=True)
    job_title = db.Column(db.String(150))

    def __repr__(self):
        return f"<Contact {self.first_name} {self.last_name}>"


class Project(db.Model):
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
    departure_date = db.Column(db.Date)
    shoot_start_date = db.Column(db.Date)
    shoot_end_date = db.Column(db.Date)
    return_date = db.Column(db.Date)
    # liste séparée par virgules ex: "eCar, eBike"
    vehicles_to_check = db.Column(db.String(500))

    # Relations
    checkout_vehicles = db.relationship(
        "CheckoutVehicle", backref="project", lazy=True)
    checkin_vehicles = db.relationship(
        "CheckinVehicle", backref="project", lazy=True)
    pilot_contact = db.relationship(
        "Contact", foreign_keys=[pilot_contact_id], backref="pilot_projects", lazy=True)
    production_contact = db.relationship(
        "Contact", foreign_keys=[production_contact_id], backref="production_projects", lazy=True)
    pilot_waiver = db.relationship(
        "PilotWaiver", backref="project", uselist=False, lazy=True)
    production_waiver = db.relationship(
        "ProductionWaiver", backref="project", uselist=False, lazy=True)

    def __repr__(self):
        return f"<Project {self.name}>"


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
    inspection_number = db.Column(
        db.String(50), unique=True, default=lambda: generate_inspection_number("BVCO"))
    status = db.Column(db.String(50))  # in_progress, pending, signed, etc.
    project_id = db.Column(
        db.Integer, db.ForeignKey("projects.id"), index=True)
    controller_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), index=True)
    inspection_date = db.Column(db.Date)
    # eCar, eBike, eTrike...
    vehicle_id = db.Column(db.String(100), index=True)
    battery_level = db.Column(db.Integer)
    tire_status = db.Column(db.String(50))
    brake_status = db.Column(db.String(50))
    exterior_lighting_status = db.Column(db.String(50))
    horn_status = db.Column(db.String(50))
    # New checkpoints
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

    interior_photos = db.Column(db.Text)  # JSON or paths
    exterior_photos = db.Column(db.Text)
    notes = db.Column(db.Text)
    vehicle_ready = db.Column(db.Boolean, default=False)
    signed_pdf_path = db.Column(db.String(500))

    hash = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<CheckoutVehicle {self.inspection_number}>"


class CheckinVehicle(db.Model):
    """Inspection au retour du véhicule"""
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
    tire_status = db.Column(db.String(50))
    brake_status = db.Column(db.String(50))
    exterior_lighting_status = db.Column(db.String(50))
    horn_status = db.Column(db.String(50))
    # New checkpoints
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

    # Relation vers user (responsable du contrôle)
    controller = db.relationship(
        "User", backref="controller_checkins", lazy=True)

    def __repr__(self):
        return f"<CheckinVehicle {self.inspection_number}>"


class NewsletterSubscriber(db.Model):
    __tablename__ = "newsletter_subscribers"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    subscribed_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<NewsletterSubscriber {self.email}>"


# ── Shared Mixins ──────────────────────────────────────────────

class TokenMixin:
    """Base for all time-limited signature tokens."""
    token = db.Column(db.String(36), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False,
                           default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False,
                           server_default=db.FetchedValue())


class SignedDocumentMixin:
    """Base for all archived signed documents."""
    hash = db.Column(db.String(255), nullable=False)
    pdf_file_hash = db.Column(db.String(64))
    data_snapshot = db.Column(db.JSON, nullable=False)
    signature = db.Column(db.Text(length=16777215))  # MEDIUMTEXT
    pdf_url = db.Column(db.Text)
    signed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PilotWaiverSignedDocument(db.Model, SignedDocumentMixin):
    __tablename__ = "pilot_waiver_signed_documents"
    waiver_id = db.Column(db.String(50), primary_key=True)


class ProductionWaiverSignedDocument(db.Model, SignedDocumentMixin):
    __tablename__ = "production_waiver_signed_documents"
    waiver_id = db.Column(db.String(50), primary_key=True)


class CheckoutSignedDocument(db.Model, SignedDocumentMixin):
    __tablename__ = "checkout_signed_documents"
    inspection_id = db.Column(db.String(255), primary_key=True)


class CheckoutToken(db.Model, TokenMixin):
    __tablename__ = "checkout_tokens"
    record_id = db.Column(db.String(255), nullable=False)
    inspection_id = db.Column(db.String(255), nullable=False)
    signature = db.Column(db.Text(length=16777215))


class CheckinSignedDocument(db.Model, SignedDocumentMixin):
    __tablename__ = "checkin_signed_documents"
    inspection_id = db.Column(db.String(255), primary_key=True)


class CheckinToken(db.Model, TokenMixin):
    __tablename__ = "checkin_tokens"
    record_id = db.Column(db.String(255), nullable=False)
    inspection_id = db.Column(db.String(255), nullable=False)
    signature = db.Column(db.Text(length=16777215))


class PilotWaiverToken(db.Model, TokenMixin):
    __tablename__ = "pilot_waiver_tokens"
    waiver_id = db.Column(db.String(255), nullable=False)


class ProductionWaiverToken(db.Model, TokenMixin):
    __tablename__ = "production_waiver_tokens"
    waiver_id = db.Column(db.String(255), nullable=False)


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
