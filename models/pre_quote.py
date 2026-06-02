from models.db import db, _utcnow


class PreQuote(db.Model):
    """Modèle représentant un pré-devis (devis rapide) pour une production."""
    __tablename__ = "pre_quotes"

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), unique=True,
                          nullable=False)  # ex: DP-2026-001
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, onupdate=_utcnow)

    # Relation avec Production
    production_id = db.Column(db.Integer, db.ForeignKey(
        'productions.id'), nullable=False)

    # Informations projet
    project_name = db.Column(db.String(200))

    # Lignes de prestation (JSON)
    # [
    #   {"category": "equipment", "description": "...", "quantity": 1, "unit": "jour", "unit_price": 850.00, "total": 850.00},
    #   ...
    # ]
    prestations = db.Column(db.JSON, nullable=False)

    # Totaux calculés
    insurance_rate = db.Column(db.Numeric(5, 2), default=10.00)
    insurance_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_ht = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    tva_rate = db.Column(db.Numeric(5, 2), default=20.00)
    tva_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_ttc = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    # Statut et Tracking
    status = db.Column(db.String(20), default='draft')  # draft, sent, accepted
    show_discounts = db.Column(db.Boolean, default=True)
    pdf_path = db.Column(db.String(500))

    # Relations
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # Créé par
    production = db.relationship(
        'Production', backref=db.backref('pre_quotes', lazy=True))
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True)
    project = db.relationship('Project', backref=db.backref('pre_quotes', lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "reference": self.reference,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "production_name": self.production.name if self.production else "Inconnue",
            "project_name": self.project_name,
            "total_ht": float(self.total_ht),
            "total_ttc": float(self.total_ttc),
            "status": self.status,
            "pdf_path": self.pdf_path,
            "insurance_rate": float(self.insurance_rate) if self.insurance_rate is not None else 10.0,
            "insurance_amount": float(self.insurance_amount) if self.insurance_amount is not None else 0.0,
            "tva_rate": float(self.tva_rate) if self.tva_rate is not None else 20.0,
            "tva_amount": float(self.tva_amount) if self.tva_amount is not None else 0.0,
            "project_id": self.project_id
        }

    def __repr__(self):
        return f"<PreQuote {self.reference} - {self.status}>"


class PreQuoteVersion(db.Model):
    """Modèle représentant une version archivée d'un pré-devis."""
    __tablename__ = "pre_quote_versions"

    id = db.Column(db.Integer, primary_key=True)
    pre_quote_id = db.Column(db.Integer, db.ForeignKey('pre_quotes.id', ondelete='CASCADE'), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)

    # Données figées (Snapshot)
    prestations = db.Column(db.JSON, nullable=False)
    total_ht = db.Column(db.Numeric(10, 2), nullable=False)
    total_ttc = db.Column(db.Numeric(10, 2), nullable=False)
    insurance_rate = db.Column(db.Numeric(5, 2))
    insurance_amount = db.Column(db.Numeric(10, 2))
    tva_rate = db.Column(db.Numeric(5, 2))
    tva_amount = db.Column(db.Numeric(10, 2))

    pdf_path = db.Column(db.String(500))
    version_note = db.Column(db.Text)  # Note explicative de la version

    # Relation avec le pré-devis d'origine
    pre_quote = db.relationship('PreQuote', backref=db.backref('versions', lazy=True, cascade='all, delete-orphan', order_by='PreQuoteVersion.version_number'))

    def to_dict(self):
        return {
            "id": self.id,
            "pre_quote_id": self.pre_quote_id,
            "version_number": self.version_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "total_ht": float(self.total_ht),
            "total_ttc": float(self.total_ttc),
            "pdf_path": self.pdf_path,
            "version_note": self.version_note or ""
        }

    def __repr__(self):
        return f"<PreQuoteVersion {self.pre_quote_id} - v{self.version_number}>"
