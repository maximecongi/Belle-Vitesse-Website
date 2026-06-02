from models.db import db, _utcnow


class SalaryPosition(db.Model):
    """Définition d'un poste et de son groupe pour la grille de salaires."""
    __tablename__ = "salary_positions"

    id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.String(100), nullable=True, default='', index=True)
    position = db.Column(db.String(150), nullable=True, default='')
    notes = db.Column(db.Text)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(
        db.DateTime, default=_utcnow, onupdate=_utcnow)

    rates = db.relationship('SalaryRate', backref='position_ref', cascade='all, delete-orphan', lazy='joined')

    def __repr__(self):
        return f"<SalaryPosition {self.position} ({self.group_name})>"


class SalaryRate(db.Model):
    """Grille de salaire par position et type de contrat."""
    __tablename__ = "salary_rates"

    id = db.Column(db.Integer, primary_key=True)
    position_id = db.Column(db.Integer, db.ForeignKey('salary_positions.id', ondelete='CASCADE'), nullable=False)
    annexe = db.Column(db.String(255))
    base_hourly = db.Column(db.Numeric(10, 2))
    invoice_10h = db.Column(db.Numeric(10, 2))
    invoice_8h = db.Column(db.Numeric(10, 2))
    inter_10h = db.Column(db.Numeric(10, 2))
    inter_8h = db.Column(db.Numeric(10, 2))
    inter_hs = db.Column(db.Numeric(10, 2))
    invoice_hs = db.Column(db.Numeric(10, 2))
    updated_at = db.Column(
        db.DateTime, default=_utcnow, onupdate=_utcnow)

    # Propriétés de rétrocompatibilité pointant vers SalaryPosition
    @property
    def position(self):
        return self.position_ref.position if self.position_ref else ""

    @position.setter
    def position(self, value):
        if not self.position_ref:
            self.position_ref = SalaryPosition()
        self.position_ref.position = value

    @property
    def group_name(self):
        return self.position_ref.group_name if self.position_ref else ""

    @group_name.setter
    def group_name(self, value):
        if not self.position_ref:
            self.position_ref = SalaryPosition()
        self.position_ref.group_name = value

    @property
    def notes(self):
        return self.position_ref.notes if self.position_ref else ""

    @notes.setter
    def notes(self, value):
        if not self.position_ref:
            self.position_ref = SalaryPosition()
        self.position_ref.notes = value

    @property
    def display_order(self):
        return self.position_ref.display_order if self.position_ref else 0

    @display_order.setter
    def display_order(self, value):
        if not self.position_ref:
            self.position_ref = SalaryPosition()
        self.position_ref.display_order = value

    def to_dict(self):
        """Convertit l'objet en dictionnaire pour les réponses API."""
        return {
            "id": self.id,
            "position_id": self.position_id,
            "group_name": self.group_name,
            "position": self.position,
            "annexe": self.annexe or "",
            "base_hourly": float(self.base_hourly) if self.base_hourly else 0.0,
            "invoice_10h": float(self.invoice_10h) if self.invoice_10h else 0.0,
            "invoice_8h": float(self.invoice_8h) if self.invoice_8h else 0.0,
            "inter_10h": float(self.inter_10h) if self.inter_10h else 0.0,
            "inter_8h": float(self.inter_8h) if self.inter_8h else 0.0,
            "inter_hs": float(self.inter_hs) if self.inter_hs else 0.0,
            "invoice_hs": float(self.invoice_hs) if self.invoice_hs else 0.0,
            "notes": self.notes or "",
            "display_order": self.display_order,
        }

    def __repr__(self):
        return f"<SalaryRate {self.position} ({self.group_name}) - {self.annexe}>"


class LogisticsRate(db.Model):
    """Tarifs logistiques (souvent ajoutés manuellement)."""
    __tablename__ = "logistics_rates"

    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(255), nullable=True, default='')
    daily_rate = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    notes = db.Column(db.Text)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(
        db.DateTime, default=_utcnow, onupdate=_utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "item_name": self.item_name,
            "daily_rate": float(self.daily_rate) if self.daily_rate else 0,
            "notes": self.notes or "",
            "display_order": self.display_order,
        }
