from models.db import db, generate_inspection_number


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
    first_ac_contact_id = db.Column(db.Integer, db.ForeignKey(
        "contacts.id"), nullable=True, index=True)
    key_grip_contact_id = db.Column(db.Integer, db.ForeignKey(
        "contacts.id"), nullable=True, index=True)
    departure_date = db.Column(db.Date, index=True)  # Date de départ (enlèvement)
    shoot_start_date = db.Column(db.Date, index=True)  # Date de début de tournage (ou 1re date ponctuelle)
    shoot_end_date = db.Column(db.Date)  # Date de fin de tournage (ou dernière date ponctuelle)
    return_date = db.Column(db.Date)  # Date de retour prévu
    date_mode = db.Column(db.String(20), default="continuous", nullable=False)  # 'continuous' ou 'punctual'
    is_immobilized_between = db.Column(db.Boolean, default=True, nullable=False)  # Valeur par défaut d'immobilisation
    shoot_dates = db.Column(db.JSON, nullable=True)  # Liste ordonnée des dates de tournage pour le mode ponctuel ex: ["2026-10-14", "2026-10-16"]
    inter_shoot_statuses = db.Column(db.JSON, nullable=True)  # Statuts d'immobilisation spécifiques par intervalle ex: [{"start": "2026-10-12", "end": "2026-10-14", "is_immobilized": true}]
    # Liste des identifiants de véhicules séparés par virgules ex: "3,5"
    vehicles_to_check = db.Column(db.String(500))
    # Liste des identifiants de têtes séparés par virgules ex: "recXX,recYY"
    heads_to_check = db.Column(db.String(500))
    notes = db.Column(db.Text)  # Demandes spécifiques

    # Soft-delete support
    deleted_at = db.Column(db.DateTime, nullable=True)

    # Tracking de la dernière action
    last_action_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    # Synchronisation kDrive Infomaniak
    kdrive_folder_id = db.Column(db.BigInteger, nullable=True, index=True)
    kdrive_path = db.Column(db.String(500), nullable=True)
    kdrive_sync_status = db.Column(db.String(20), default="pending", nullable=False)
    kdrive_last_error = db.Column(db.Text, nullable=True)
    kdrive_last_cancel_id = db.Column(db.String(100), nullable=True)

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
    # Contact 1er Assistant Caméra du projet
    first_ac_contact = db.relationship(
        "Contact", foreign_keys=[first_ac_contact_id], backref="first_ac_projects", lazy=True)
    # Contact Chef Machiniste du projet
    key_grip_contact = db.relationship(
        "Contact", foreign_keys=[key_grip_contact_id], backref="key_grip_projects", lazy=True)
    # Décharge pilote associée (unique pour le projet)
    pilot_waiver = db.relationship(
        "PilotWaiver", backref="project", uselist=False, lazy=True)
    # Décharge production associée (unique pour le projet)
    production_waiver = db.relationship(
        "ProductionWaiver", backref="project", uselist=False, lazy=True)
    # Utilisateur ayant effectué la dernière action
    last_action_by = db.relationship(
        "User", foreign_keys=[last_action_by_id], lazy=True)
    # Objets kDrive synchronisés pour ce projet
    kdrive_objects = db.relationship(
        "KDriveObject", backref="project", cascade="all, delete-orphan", lazy=True)

    @property
    def active_checkout_vehicles(self):
        """Retourne la liste des départs non supprimés associés à ce projet."""
        return [c for c in (self.checkout_vehicles or []) if getattr(c, "deleted_at", None) is None]

    @property
    def active_checkin_vehicles(self):
        """Retourne la liste des retours non supprimés associés à ce projet."""
        return [c for c in (self.checkin_vehicles or []) if getattr(c, "deleted_at", None) is None]

    @property
    def active_pilot_waiver(self):
        """Retourne la décharge pilote si elle existe et n'a pas été supprimée."""
        return self.pilot_waiver if (self.pilot_waiver and getattr(self.pilot_waiver, "deleted_at", None) is None) else None

    @property
    def active_production_waiver(self):
        """Retourne la décharge production si elle existe et n'a pas été supprimée."""
        return self.production_waiver if (self.production_waiver and getattr(self.production_waiver, "deleted_at", None) is None) else None

    @property
    def kdrive_web_url(self):
        """Retourne l'URL directe vers le dossier kDrive du projet sur l'interface Infomaniak."""
        if not self.kdrive_folder_id:
            return None
        from services.common.kdrive.config import KDRIVE_DRIVE_ID
        return f"https://kdrive.infomaniak.com/app/drive/{KDRIVE_DRIVE_ID}/files/{self.kdrive_folder_id}"

    @property
    def is_punctual(self):
        """Indique si le projet utilise le mode de dates ponctuelles."""
        return self.date_mode == "punctual"

    @property
    def effective_shoot_dates(self):
        """Retourne la liste des dates de tournage (ISO strings)."""
        if self.is_punctual and self.shoot_dates:
            return sorted(self.shoot_dates)
        if self.shoot_start_date and self.shoot_end_date:
            from datetime import timedelta
            cur = self.shoot_start_date
            dates = []
            while cur <= self.shoot_end_date:
                dates.append(cur.isoformat())
                cur += timedelta(days=1)
            return dates
        if self.shoot_start_date:
            return [self.shoot_start_date.isoformat()]
        return []

    def get_inter_shoot_intervals(self):
        """
        Calcule et retourne la liste détaillée des intervalles entre dates de tournage successives,
        avec leurs jours intermédiaires et leur état d'immobilisation respectif.
        """
        if not self.is_punctual or not self.shoot_dates:
            return []

        from datetime import datetime, timedelta

        # Dates de tournage uniques et triées
        sorted_dates = []
        for d_str in self.shoot_dates:
            try:
                sorted_dates.append(datetime.strptime(str(d_str).strip(), "%Y-%m-%d").date())
            except Exception:
                pass
        sorted_dates = sorted(list(set(sorted_dates)))

        if len(sorted_dates) < 2:
            return []

        # Mapping des statuts d'intervalles enregistrés
        custom_statuses = {}
        if isinstance(self.inter_shoot_statuses, list):
            for item in self.inter_shoot_statuses:
                if isinstance(item, dict) and "start" in item and "end" in item:
                    k = f"{item['start']}_{item['end']}"
                    custom_statuses[k] = bool(item.get("is_immobilized", True))
        elif isinstance(self.inter_shoot_statuses, dict):
            for k, v in self.inter_shoot_statuses.items():
                if isinstance(v, dict):
                    custom_statuses[k] = bool(v.get("is_immobilized", True))
                else:
                    custom_statuses[k] = bool(v)

        default_immob = bool(self.is_immobilized_between) if self.is_immobilized_between is not None else True
        intervals = []

        for i in range(len(sorted_dates) - 1):
            d1 = sorted_dates[i]
            d2 = sorted_dates[i + 1]
            diff = (d2 - d1).days

            # S'il y a au moins un jour intermédiaire entre d1 et d2
            if diff > 1:
                cur = d1 + timedelta(days=1)
                days_between = []
                while cur < d2:
                    days_between.append(cur.isoformat())
                    cur += timedelta(days=1)

                key = f"{d1.isoformat()}_{d2.isoformat()}"
                is_immob = custom_statuses.get(key, default_immob)

                intervals.append({
                    "start": d1.isoformat(),
                    "end": d2.isoformat(),
                    "days": days_between,
                    "days_count": len(days_between),
                    "is_immobilized": is_immob,
                })

        return intervals

    @property
    def effective_blocked_dates(self):
        """
        Retourne l'ensemble de toutes les dates (objets date) où le matériel est bloqué,
        en combinant dates de tournage, jours intermédiaires immobilisés et jalons départ/retour.
        """
        from datetime import datetime
        blocked = set()

        if self.departure_date:
            blocked.add(self.departure_date)
        if self.return_date:
            blocked.add(self.return_date)

        if not self.is_punctual or not self.shoot_dates:
            # Mode continu classique
            p_start = self.shoot_start_date or self.departure_date
            p_end = self.shoot_end_date or self.return_date or p_start
            if p_start and p_end:
                from datetime import timedelta
                cur = p_start
                while cur <= p_end:
                    blocked.add(cur)
                    cur += timedelta(days=1)
            return blocked

        # Mode ponctuel : ajouter les jours de tournage
        for d_str in self.shoot_dates:
            try:
                blocked.add(datetime.strptime(str(d_str).strip(), "%Y-%m-%d").date())
            except Exception:
                pass

        # Ajouter les jours d'intervalles qui sont immobilisés
        intervals = self.get_inter_shoot_intervals()
        for inter in intervals:
            if inter.get("is_immobilized"):
                for day_str in inter.get("days", []):
                    try:
                        blocked.add(datetime.strptime(day_str, "%Y-%m-%d").date())
                    except Exception:
                        pass

        return blocked

    def to_dict(self):
        """Convertit l'objet en dictionnaire pour les réponses API."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "production_id": self.production_id,
            "pilot_contact_id": self.pilot_contact_id,
            "production_contact_id": self.production_contact_id,
            "dop_contact_id": self.dop_contact_id,
            "first_ac_contact_id": self.first_ac_contact_id,
            "key_grip_contact_id": self.key_grip_contact_id,
            "departure_date": self.departure_date.isoformat() if self.departure_date else None,
            "shoot_start_date": self.shoot_start_date.isoformat() if self.shoot_start_date else None,
            "shoot_end_date": self.shoot_end_date.isoformat() if self.shoot_end_date else None,
            "return_date": self.return_date.isoformat() if self.return_date else None,
            "date_mode": self.date_mode or "continuous",
            "is_immobilized_between": bool(self.is_immobilized_between),
            "shoot_dates": self.shoot_dates or [],
            "inter_shoot_statuses": self.inter_shoot_statuses or [],
            "vehicles_to_check": self.vehicles_to_check,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "kdrive_folder_id": self.kdrive_folder_id,
            "kdrive_path": self.kdrive_path,
            "kdrive_sync_status": self.kdrive_sync_status,
            "kdrive_last_error": self.kdrive_last_error,
            "kdrive_web_url": self.kdrive_web_url,
        }

    def __repr__(self):
        return f"<Project {self.name}>"
