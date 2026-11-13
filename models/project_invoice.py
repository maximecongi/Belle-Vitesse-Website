"""Factures d'un projet : un projet peut être facturé en plusieurs fois (acompte, par semaine, solde…)."""
from models.db import _utcnow, db


class ProjectInvoice(db.Model):
    """
    Facture émise sur un projet : montant global HT, ventilation par véhicule / tête
    (equipment_billing = {"vehicle:<id>" | "head:<id>": montant}), le reste étant « Autres prestations ».
    Le chiffre d'affaires est compté à la date d'émission (issued_on).
    """
    __tablename__ = "project_invoices"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number = db.Column(db.String(60), nullable=True)
    label = db.Column(db.String(150), nullable=True)
    issued_on = db.Column(db.Date, nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    equipment_billing = db.Column(db.JSON, nullable=True)
    is_paid = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    paid_on = db.Column(db.Date, nullable=True)
    # Fichier de la facture : copie locale (chemin relatif à OUTPUT_FOLDER), envoyée dans 2_FACTURES sur kDrive
    file_path = db.Column(db.String(500), nullable=True)
    file_name = db.Column(db.String(255), nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    project = db.relationship(
        "Project",
        backref=db.backref(
            "invoices", cascade="all, delete-orphan", lazy=True,
            order_by="(ProjectInvoice.issued_on.asc(), ProjectInvoice.position.asc(), ProjectInvoice.id.asc())",
        ),
    )

    @property
    def equipment_map(self) -> dict:
        """Montants par matériel encore engagé sur le projet : {"vehicle:<id>" | "head:<id>": float}."""
        project = self.project
        engaged = None
        if project is not None:
            engaged = {f"vehicle:{v}" for v in project.vehicle_ids_list} | {f"head:{h}" for h in project.head_ids_list}
        result = {}
        for key, value in (self.equipment_billing or {}).items():
            try:
                amount = float(value)
            except (TypeError, ValueError):
                continue
            if amount and (engaged is None or key in engaged):
                result[key] = amount
        return result

    @property
    def kdrive_entity_id(self) -> str:
        """Identifiant de suivi kDrive (table kdrive_objects) du fichier de cette facture."""
        return f"FACT-{self.id}"

    @property
    def equipment_total(self) -> float:
        return round(sum(self.equipment_map.values()), 2)

    @property
    def total(self) -> float:
        return float(self.amount or 0)

    @property
    def other(self) -> float:
        """Part « Autres prestations » (montant − matériel), jamais négative."""
        return max(self.total - sum(self.equipment_map.values()), 0.0)
