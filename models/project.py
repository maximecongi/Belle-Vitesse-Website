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
    projects = db.relationship("Project", back_populates="production", lazy=True)
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


project_bv_referents = db.Table(
    "project_bv_referents",
    db.Column("project_id", db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
    db.Column("user_id", db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)

project_vehicles = db.Table(
    "project_vehicles",
    db.Column("project_id", db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
    db.Column("vehicle_id", db.String(100), primary_key=True),
)



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
    shooting_locations = db.Column(db.JSON, nullable=True)  # Liste ordonnée des lieux ex: [{"name": "Circuit Paul Ricard", "address": "Le Castellet"}]
    # Liste des identifiants de véhicules séparés par virgules ex: "3,5"
    vehicles_to_check = db.Column(db.String(500))
    # Liste des identifiants de têtes séparés par virgules ex: "recXX,recYY"
    heads_to_check = db.Column(db.String(500))
    # Statuts d'homologation route des véhicules pour ce projet ex: {"rec_erover": false, "rec_ecar": true}
    vehicle_road_legal_statuses = db.Column(db.JSON, nullable=True)
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
    # Société de production associée
    production = db.relationship(
        "Production", back_populates="projects", foreign_keys=[production_id], lazy=True)
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
    # Décharges associées au projet
    waivers = db.relationship(
        "Waiver", backref="project", cascade="all, delete-orphan", lazy=True)
    # Contrat Cadre / CGL (Terms & Conditions - BVTC) associé (unique actif pour le projet)
    cgl = db.relationship(
        "CglWaiver",
        primaryjoin="and_(Project.id == foreign(CglWaiver.project_id), CglWaiver.deleted_at.is_(None))",
        order_by="desc(CglWaiver.id)",
        uselist=False,
        lazy=True,
        overlaps="project,waivers",
    )
    # Règles de sécurité universelles associées (BVSR, multiples possibles pour le projet)
    safety_rules = db.relationship(
        "SafetyRulesWaiver", lazy=True, order_by="SafetyRulesWaiver.id", overlaps="project,waivers")
    # Attestations d'information et d'engagement du pilote (Annexe 3 aux CGL - BVPA)
    pilot_waivers = db.relationship(
        "PilotWaiver", lazy=True, order_by="PilotWaiver.id", overlaps="project,waivers")
    # Analyses des risques associées (Risk Assessment - BVRA)
    risk_assessments = db.relationship(
        "RiskAssessmentWaiver", lazy=True, order_by="RiskAssessmentWaiver.id", overlaps="project,waivers")
    # Utilisateur ayant effectué la dernière action
    last_action_by = db.relationship(
        "User", foreign_keys=[last_action_by_id], lazy=True)
    # Objets kDrive synchronisés pour ce projet
    kdrive_objects = db.relationship(
        "KDriveObject", backref="project", cascade="all, delete-orphan", lazy=True)
    # Référents Belle Vitesse rattachés au projet
    bv_referents = db.relationship(
        "User",
        secondary=project_bv_referents,
        backref=db.backref("referred_projects", lazy="dynamic"),
        lazy="joined",
    )

    @property
    def bv_referents_names(self):
        """Retourne la liste des noms complets des référents BV séparés par une virgule."""
        if not self.bv_referents:
            return ""
        return ", ".join(f"{u.firstname} {u.lastname}".strip() for u in self.bv_referents if (u.firstname or u.lastname))

    @property
    def vehicle_ids_list(self) -> list:
        """Retourne la liste ordonnée et nettoyée des IDs de véhicules assignés."""
        if not self.vehicles_to_check:
            return []
        return [v.strip() for v in self.vehicles_to_check.split(",") if v.strip()]

    @property
    def head_ids_list(self) -> list:
        """Retourne la liste ordonnée et nettoyée des IDs de têtes assignées."""
        if not self.heads_to_check:
            return []
        return [h.strip() for h in self.heads_to_check.split(",") if h.strip()]

    def is_vehicle_road_legal(self, vehicle_id: str = "", vehicle_slug: str = "", vehicle_name: str = "") -> bool:
        """
        Détermine si un véhicule est homologué route pour ce tournage.
        1. Statut explicite dans vehicle_road_legal_statuses s'il existe (par ID, par slug ou par nom).
        2. Sinon détection automatique par défaut : eRover, eRider, Stark Varg sont non-homologués route (route fermée).
        """
        statuses = self.vehicle_road_legal_statuses or {}
        vid_str = str(vehicle_id).strip() if vehicle_id else ""
        slug_lower = (vehicle_slug or "").lower().strip()
        name_lower = (vehicle_name or "").lower().strip()

        # 1. Vérification directe dans statuses (par ID, par slug ou par nom)
        for key in [vid_str, slug_lower, name_lower]:
            if key and key in statuses:
                return bool(statuses[key])

        # 2. Si non trouvé par clé directe mais qu'on a un vid_str, chercher dans la BDD catalog pour résoudre le slug/nom
        if vid_str and not slug_lower and not name_lower:
            try:
                from models.catalog import Vehicle
                db_v = db.session.get(Vehicle, vid_str) if hasattr(db.session, "get") else Vehicle.query.get(vid_str)
                if db_v and db_v.fields:
                    f = db_v.fields
                    slug_lower = (f.get("slug") or "").lower().strip()
                    name_lower = (f.get("name") or f.get("Nom") or "").lower().strip()
                    for key in [slug_lower, name_lower]:
                        if key and key in statuses:
                            return bool(statuses[key])
            except Exception:
                pass

        # 3. Valeur par défaut
        non_road_keywords = ["erover", "erider", "stark", "polar"]
        if any(k in vid_str.lower() or k in slug_lower or k in name_lower for k in non_road_keywords):
            return False

        return True

    def set_vehicle_road_legal(self, vehicle_id: str, is_road_legal: bool):
        """Met à jour le statut d'homologation route d'un véhicule pour ce projet."""
        from sqlalchemy.orm.attributes import flag_modified

        statuses = dict(self.vehicle_road_legal_statuses or {})
        vid_str = str(vehicle_id).strip()
        statuses[vid_str] = bool(is_road_legal)

        # Récupération du slug et du nom pour synchroniser toutes les clés (Airtable ID, slug, nom)
        try:
            from models.catalog import Vehicle
            db_v = db.session.get(Vehicle, vid_str) if hasattr(db.session, "get") else Vehicle.query.get(vid_str)
            if not db_v:
                db_v = Vehicle.query.filter(
                    (Vehicle.fields["slug"].astext == vid_str)
                    | (Vehicle.fields["name"].astext == vid_str)
                ).first()
            if db_v and db_v.fields:
                f = db_v.fields
                v_s = (f.get("slug") or "").lower().strip()
                v_n = (f.get("name") or f.get("Nom") or "").lower().strip()
                if v_s:
                    statuses[v_s] = bool(is_road_legal)
                if v_n:
                    statuses[v_n] = bool(is_road_legal)
                if db_v.id:
                    statuses[str(db_v.id)] = bool(is_road_legal)
        except Exception:
            pass

        try:
            from utils.database import get_vehicles
            for v in (get_vehicles() or []):
                v_id = str(v.get("id") or "")
                f = v.get("fields") or {}
                v_s = (f.get("slug") or "").lower().strip()
                v_n = (f.get("name") or f.get("Nom") or "").lower().strip()
                if vid_str.lower() in [v_id.lower(), v_s, v_n]:
                    if v_id:
                        statuses[v_id] = bool(is_road_legal)
                    if v_s:
                        statuses[v_s] = bool(is_road_legal)
                    if v_n:
                        statuses[v_n] = bool(is_road_legal)
                    break
        except Exception:
            pass

        self.vehicle_road_legal_statuses = statuses
        flag_modified(self, "vehicle_road_legal_statuses")


    @property
    def active_checkout_vehicles(self):
        """Retourne la liste des départs non supprimés associés à ce projet."""
        return [c for c in (self.checkout_vehicles or []) if getattr(c, "deleted_at", None) is None]

    @property
    def active_checkin_vehicles(self):
        """Retourne la liste des retours non supprimés associés à ce projet."""
        return [c for c in (self.checkin_vehicles or []) if getattr(c, "deleted_at", None) is None]

    def clear_waiver_cache(self):
        """Réinitialise les caches mémoïsés des décharges actives."""
        for attr in ("_memo_active_cgl", "_memo_active_safety_rules", "_memo_active_pilot_waivers", "_memo_active_risk_assessments"):
            if attr in self.__dict__:
                del self.__dict__[attr]

    @property
    def active_cgl(self):
        """Retourne le contrat CGL / Terms & Conditions (BVTC) si il existe et n'a pas été supprimé."""
        if hasattr(self, "_memo_active_cgl"):
            memo = self._memo_active_cgl
            if memo is None or getattr(memo, "deleted_at", None) is None:
                return memo
            self.clear_waiver_cache()

        res = None
        if "cgl" in self.__dict__ and self.cgl and getattr(self.cgl, "deleted_at", None) is None:
            res = self.cgl
        elif "waivers" in self.__dict__:
            active = [
                w for w in (self.waivers or [])
                if getattr(w, "waiver_type", None) == "cgl" and getattr(w, "deleted_at", None) is None
            ]
            if active:
                res = active[-1]
        elif self.cgl and getattr(self.cgl, "deleted_at", None) is None:
            res = self.cgl
        else:
            from models.waiver import CglWaiver
            res = CglWaiver.query.filter_by(project_id=self.id, deleted_at=None).order_by(CglWaiver.id.desc()).first()
        self._memo_active_cgl = res
        return res

    @property
    def active_safety_rules(self):
        """Retourne la liste des règles de sécurité universelles (BVSR) actives pour ce projet."""
        if hasattr(self, "_memo_active_safety_rules"):
            return self._memo_active_safety_rules
        if "waivers" in self.__dict__:
            res = [
                w for w in (self.waivers or [])
                if getattr(w, "waiver_type", None) == "safety_rules" and getattr(w, "deleted_at", None) is None
            ]
        else:
            res = [sr for sr in (self.safety_rules or []) if getattr(sr, "deleted_at", None) is None]
        self._memo_active_safety_rules = res
        return res

    @property
    def active_pilot_waivers(self):
        """Retourne la liste des attestations pilotes (BVPA) actives pour ce projet."""
        if hasattr(self, "_memo_active_pilot_waivers"):
            return self._memo_active_pilot_waivers
        if "waivers" in self.__dict__:
            res = [
                w for w in (self.waivers or [])
                if getattr(w, "waiver_type", None) in ("pilot_waiver", "pilot") and getattr(w, "deleted_at", None) is None
            ]
        else:
            res = [pw for pw in (self.pilot_waivers or []) if getattr(pw, "deleted_at", None) is None]
        self._memo_active_pilot_waivers = res
        return res

    @property
    def active_risk_assessments(self):
        """Retourne la liste des analyses de risques (BVRA) actives pour ce projet."""
        if hasattr(self, "_memo_active_risk_assessments"):
            return self._memo_active_risk_assessments
        if "waivers" in self.__dict__:
            res = [
                w for w in (self.waivers or [])
                if getattr(w, "waiver_type", None) == "risk_assessment" and getattr(w, "deleted_at", None) is None
            ]
        else:
            res = [ra for ra in (self.risk_assessments or []) if getattr(ra, "deleted_at", None) is None]
        self._memo_active_risk_assessments = res
        return res


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

    @property
    def locations_list(self):
        """Retourne la liste ordonnée et nettoyée des lieux de tournage [{"name": ..., "address": ...}]."""
        raw = self.shooting_locations
        if not raw or not isinstance(raw, list):
            return []
        cleaned = []
        for item in raw:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
                address = str(item.get("address") or "").strip()
                if name:  # Le nom est obligatoire, l'adresse est facultative
                    cleaned.append({"name": name, "address": address})
        return cleaned

    @property
    def has_shooting_locations(self):
        """Indique si le projet dispose d'au moins un lieu de tournage valide."""
        return len(self.locations_list) > 0

    @property
    def display_shooting_locations(self):
        """Retourne une chaîne formatée et lisible des lieux de tournage."""
        locs = self.locations_list
        if not locs:
            return ""
        parts = []
        for loc in locs:
            if loc["address"]:
                parts.append(f"{loc['name']} ({loc['address']})")
            else:
                parts.append(loc["name"])
        return " ; ".join(parts)

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
            "shooting_locations": self.locations_list,
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


@db.event.listens_for(Project, "expire")
def _on_project_expire(target, attrs):
    if target is not None and hasattr(target, "clear_waiver_cache"):
        target.clear_waiver_cache()


@db.event.listens_for(Project, "refresh")
def _on_project_refresh(target, context, attrs):
    if target is not None and hasattr(target, "clear_waiver_cache"):
        target.clear_waiver_cache()

