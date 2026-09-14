from models.db import db, _utcnow


class CheckpointDefinition(db.Model):
    """Définition personnalisable d'un point de contrôle de véhicule.

    Permet d'éditer le libellé, la catégorie, l'indication par défaut,
    les véhicules concernés ainsi que l'indication technique spécifique à chaque véhicule.
    """
    __tablename__ = "checkpoint_definitions"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    label = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100), default="Sécurité", nullable=False)
    type = db.Column(db.String(50), default="status", nullable=False)  # 'status' ou 'value'
    unit = db.Column(db.String(20), nullable=True)                     # ex: '%'
    default_detail = db.Column(db.Text, nullable=True)                 # Indication globale de fallback
    order = db.Column(db.Integer, default=0, nullable=False)

    # Dictionnaire JSON :
    # {
    #     "<vehicle_id>": {
    #         "enabled": true|false,
    #         "indication": "2 bar"
    #     }
    # }
    vehicle_overrides = db.Column(db.JSON, default=dict, nullable=False)

    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    def is_vehicle_enabled(self, vehicle_id: str, vehicle_name: str = None) -> bool:
        """Indique si ce point de contrôle est actif pour le véhicule donné."""
        overrides = self.vehicle_overrides or {}
        if vehicle_id in overrides:
            return bool(overrides[vehicle_id].get("enabled", False))
        if vehicle_name and vehicle_name in overrides:
            return bool(overrides[vehicle_name].get("enabled", False))
        return self.category == "Sécurité"

    def get_indication_for_vehicle(self, vehicle_id: str, vehicle_name: str = None) -> str:
        """Retourne l'indication spécifique pour le véhicule ou l'indication par défaut."""
        overrides = self.vehicle_overrides or {}
        if vehicle_id in overrides and overrides[vehicle_id].get("indication"):
            return overrides[vehicle_id]["indication"].strip()
        if vehicle_name and vehicle_name in overrides and overrides[vehicle_name].get("indication"):
            return overrides[vehicle_name]["indication"].strip()
        return (self.default_detail or "").strip()

    def to_dict(self) -> dict:
        """Sérialise le point de contrôle."""
        return {
            "id": self.id,
            "key": self.key,
            "label": self.label,
            "category": self.category,
            "type": self.type,
            "unit": self.unit,
            "default_detail": self.default_detail,
            "order": self.order,
            "vehicle_overrides": self.vehicle_overrides or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<CheckpointDefinition {self.key} : {self.label}>"
