from models.db import db, _utcnow


# Types de matériel pointables sur un jour de tournage
EQUIPMENT_TYPES = ("vehicle", "head")


class ProjectEquipmentUsage(db.Model):
    """
    Pointage journalier du matériel d'un projet : pour un jour de tournage donné,
    indique si un véhicule (ou une tête) a réellement été utilisé.

    Trois états par couple matériel × jour :
    - aucune ligne      → non pointé
    - used = True       → utilisé
    - used = False      → non utilisé (resté au camion, en panne, etc.)

    Sert de base à la facturation au réel, aux statistiques de flotte et au suivi maintenance.
    """
    __tablename__ = "project_equipment_usage"
    __table_args__ = (
        db.UniqueConstraint(
            "project_id", "equipment_type", "equipment_id", "usage_date",
            name="uq_project_equipment_usage_day",
        ),
        db.Index("ix_project_equipment_usage_equipment", "equipment_type", "equipment_id", "usage_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    equipment_type = db.Column(db.String(20), nullable=False)  # 'vehicle' ou 'head'
    equipment_id = db.Column(db.String(100), nullable=False)  # même identifiant que vehicles_to_check / heads_to_check
    usage_date = db.Column(db.Date, nullable=False)
    used = db.Column(db.Boolean, nullable=False)
    updated_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    project = db.relationship(
        "Project",
        backref=db.backref("equipment_usage", cascade="all, delete-orphan", lazy=True),
    )
    updated_by = db.relationship("User", lazy=True)

    @property
    def key(self) -> str:
        """Clé « type:id » utilisée côté interface."""
        return f"{self.equipment_type}:{self.equipment_id}"

    def __repr__(self):
        return f"<ProjectEquipmentUsage {self.project_id} {self.key} {self.usage_date} used={self.used}>"


class ProjectEquipmentUsageLog(db.Model):
    """
    Historique des pointages (stockage seul) : une ligne par changement réel d'état
    d'un couple matériel × jour. Conservé pour la traçabilité (litiges de facturation, audit),
    consultable via l'outil MCP get_equipment_usage_history.
    """
    __tablename__ = "project_equipment_usage_logs"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    equipment_type = db.Column(db.String(20), nullable=False)
    equipment_id = db.Column(db.String(100), nullable=False)
    usage_date = db.Column(db.Date, nullable=False)
    old_state = db.Column(db.String(10), nullable=False)  # 'used' | 'unused' | 'none'
    new_state = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    source = db.Column(db.String(20), nullable=False, default="web")  # 'web' | 'mcp'
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    project = db.relationship(
        "Project",
        backref=db.backref("equipment_usage_logs", cascade="all, delete-orphan", lazy="dynamic"),
    )
    user = db.relationship("User", lazy=True)

    def to_dict(self):
        return {
            "equipment_type": self.equipment_type,
            "equipment_id": self.equipment_id,
            "date": self.usage_date.isoformat(),
            "old_state": self.old_state,
            "new_state": self.new_state,
            "user": (f"{self.user.firstname} {self.user.lastname}".strip() if self.user else None),
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
