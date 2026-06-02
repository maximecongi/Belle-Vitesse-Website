from models.db import db, _utcnow


class SyncRecordMixin:
    """Base pour les tables synchronisées depuis Airtable."""
    id = db.Column(
        db.String(255), primary_key=True)  # ID d'enregistrement Airtable
    createdTime = db.Column(db.DateTime)
    fields = db.Column(db.JSON)  # Contenu brut des champs Airtable
    updated_at = db.Column(
        db.DateTime, default=_utcnow, onupdate=_utcnow)


class Vehicle(db.Model, SyncRecordMixin):
    """Véhicules synchronisés depuis Airtable."""
    __tablename__ = "vehicles"
    daily_rate = db.Column(db.Numeric(10, 2), nullable=True)
    display_order = db.Column(db.Integer, nullable=False, default=0)


class Head(db.Model, SyncRecordMixin):
    """Têtes de caméra synchronisées depuis Airtable."""
    __tablename__ = "heads"
    daily_rate = db.Column(db.Numeric(10, 2), nullable=True)
    display_order = db.Column(db.Integer, nullable=False, default=0)


class GripCategory(db.Model, SyncRecordMixin):
    """Catégories de matériel Grip (Airtable)."""
    __tablename__ = "grips_categories"


class GripProduct(db.Model, SyncRecordMixin):
    """Produits Grip individuels (Airtable)."""
    __tablename__ = "grip_products"
    daily_rate = db.Column(db.Numeric(10, 2), nullable=True)
    display_order = db.Column(db.Integer, nullable=False, default=0)


class Config(db.Model, SyncRecordMixin):
    """Configurations spécifiques (Airtable)."""
    __tablename__ = "configs"


class Static(db.Model, SyncRecordMixin):
    """Données statiques de contenu (Airtable)."""
    __tablename__ = "static"
