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
