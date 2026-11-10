from models.db import db, generate_inspection_number
from models.inspection import (
    CheckinSignedDocument as CheckinSignedDocument,
    CheckinToken as CheckinToken,
    CheckoutSignedDocument as CheckoutSignedDocument,
    CheckoutToken as CheckoutToken,
)
from models.mixins import SignedDocumentMixin, TokenMixin


# ── Modèle Unifié des Décharges ──────────────────────────────────

def _generate_default_waiver_id(context):
    params = context.get_current_parameters()
    w_type = params.get("waiver_type", "safety_rules")
    if w_type == "cgl":
        prefix = "BVTC"
    elif w_type == "pilot_waiver":
        prefix = "BVPA"
    elif w_type == "risk_assessment":
        prefix = "BVRA"
    else:
        prefix = "BVSR"
    return generate_inspection_number(prefix)


def _extract_vehicle_thumbnail(fields):
    """Extrait l'URL de la miniature du véhicule depuis ses champs Airtable / BDD."""
    if not fields or not isinstance(fields, dict):
        return None

    # 1. Champ 'thumbnail'
    thumb = fields.get("thumbnail")
    if isinstance(thumb, str) and thumb.strip():
        return thumb.strip()
    if isinstance(thumb, list) and len(thumb) > 0:
        item = thumb[0]
        if isinstance(item, dict):
            thumbnails = item.get("thumbnails", {})
            if isinstance(thumbnails, dict):
                large = thumbnails.get("large", {}).get("url")
                if large:
                    return large
                full = thumbnails.get("full", {}).get("url")
                if full:
                    return full
                small = thumbnails.get("small", {}).get("url")
                if small:
                    return small
            if item.get("url"):
                return item["url"]
        elif isinstance(item, str) and item.strip():
            return item.strip()

    # 2. Fallback champ 'gallery'
    gallery = fields.get("gallery")
    if isinstance(gallery, list) and len(gallery) > 0:
        item = gallery[0]
        if isinstance(item, dict):
            thumbnails = item.get("thumbnails", {})
            if isinstance(thumbnails, dict):
                large = thumbnails.get("large", {}).get("url")
                if large:
                    return large
            if item.get("url"):
                return item["url"]

    # 3. Fallback champ 'banner'
    banner = fields.get("banner")
    if isinstance(banner, list) and len(banner) > 0:
        item = banner[0]
        if isinstance(item, dict):
            thumbnails = item.get("thumbnails", {})
            if isinstance(thumbnails, dict):
                large = thumbnails.get("large", {}).get("url")
                if large:
                    return large
            if item.get("url"):
                return item["url"]
        elif isinstance(item, str) and item.strip():
            return item.strip()

    return None


class Waiver(db.Model):
    """
    Modèle unifié représentant un document juridique / décharge (CGL ou Règles de Sécurité BVSR).
    Supporte le polymorphisme Single Table Inheritance pour CglWaiver et SafetyRulesWaiver.
    """
    __tablename__ = "waivers"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey(
        "projects.id", ondelete="CASCADE"), nullable=False, index=True)
    waiver_type = db.Column(db.String(20), nullable=False,
                            default="safety_rules", index=True)
    waiver_id = db.Column(db.String(
        50), unique=True, default=_generate_default_waiver_id, nullable=False, index=True)

    __mapper_args__ = {
        "polymorphic_on": waiver_type,
        "polymorphic_identity": "waiver",
    }

    # Copie du nom du projet au moment de la génération
    project_name = db.Column(db.String(255), nullable=True)
    # Statut (to_generate, to_send, to_sign, signed)
    status = db.Column(db.String(20), default="to_generate", nullable=False)
    generated_at = db.Column(db.DateTime, nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    signed_at = db.Column(db.DateTime, nullable=True)

    # Données signataire universel (BVSR)
    # 'pilot', 'first_ad', 'production', 'camera_operator', 'stunt', 'other'
    signer_role = db.Column(db.String(50), nullable=True)
    signer_role_custom = db.Column(db.String(100), nullable=True)
    signer_first_name = db.Column(db.String(100), nullable=True)
    signer_last_name = db.Column(db.String(100), nullable=True)
    signer_email = db.Column(db.String(120), nullable=True)
    signer_phone = db.Column(db.String(50), nullable=True)
    signer_company = db.Column(db.String(255), nullable=True)
    # Contact ERP choisi comme signataire (les coordonnées ci-dessus restent la copie figée à valeur légale)
    signer_contact_id = db.Column(db.Integer, db.ForeignKey(
        "contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    signer_contact = db.relationship("Contact", foreign_keys=[signer_contact_id], lazy=True)
    # Noms des référents BV pour ce tournage (personnalisables)
    safety_technicians = db.Column(db.Text, nullable=True)
    helmets_inventory = db.Column(db.JSON, default=dict, nullable=True)
    custom_rules_snapshot = db.Column(db.JSON, default=dict, nullable=True)
    bv_signature_data = db.Column(db.String(255), nullable=True)
    bv_signed_at = db.Column(db.DateTime, nullable=True)
    bv_signer_name = db.Column(db.String(100), nullable=True)

    # Données signataire Production (BVTC / CGL)
    production_name = db.Column(db.String(255), nullable=True)
    production_representative = db.Column(db.String(255), nullable=True)
    production_address = db.Column(db.Text, nullable=True)
    production_siret = db.Column(db.String(100), nullable=True)
    production_vat = db.Column(db.String(100), nullable=True)
    production_insurance_company = db.Column(db.String(255), nullable=True)
    production_insurance_policy = db.Column(db.String(255), nullable=True)
    production_insurance_validity = db.Column(db.String(100), nullable=True)
    location_of_use = db.Column(db.Text, nullable=True)
    production_insurance_path = db.Column(db.String(500), nullable=True)

    # Contexte commun du tournage
    vehicles = db.Column(db.Text, nullable=True)
    shooting_dates = db.Column(db.String(255), nullable=True)

    # Snapshot JSON flexible pour toute extension future
    sign_data = db.Column(db.JSON, default=dict, nullable=True)

    # Signature (Chemin relatif PNG ex: signatures/waivers/BVSR-xxx.png)
    signature_data = db.Column(db.String(255), nullable=True)
    # Chemin relatif du PDF signé
    signed_pdf_path = db.Column(db.String(500), nullable=True)

    @property
    def signer_name(self):
        """Retourne le nom complet du signataire individuel ou du représentant."""
        if self.signer_first_name or self.signer_last_name:
            return f"{self.signer_first_name or ''} {self.signer_last_name or ''}".strip()
        if self.production_representative:
            return self.production_representative.strip()
        return "—"

    @property
    def signer_role_label(self):
        """Libellé en français du rôle du signataire."""
        roles = {
            "pilot": "Pilote",
            "operator": "Cadreur",
            "camera_operator": "Cadreur",
            "stunt_coordinator": "Coordinateur Cascades",
            "stunt_performer": "Cascadeur",
            "stunt": "Coordinateur Cascades",
            "production": "Directeur de production",
            "director": "Réalisateur",
            "first_ad": "1er Assistant Réalisateur",
            "key_grip": "Chef Machiniste",
            "location_manager": "Régisseur Général",
            "technician": "Technicien Plateau",
            "other": self.signer_role_custom or "Intervenant Plateau",
        }
        return roles.get(self.signer_role, self.signer_role_custom or self.signer_role or "Intervenant")

    @property
    def display_representative_role(self):
        """Retourne la fonction ou qualité du représentant légal."""
        if self.sign_data and self.sign_data.get("representative_role"):
            return self.sign_data.get("representative_role")
        return self.signer_role_custom or "Représentant légal"

    @property
    def display_legal_form_only(self):
        """Retourne uniquement la forme juridique du locataire (ex: SAS)."""
        if self.sign_data and self.sign_data.get("legal_form"):
            return self.sign_data.get("legal_form")
        return ""

    @property
    def display_legal_country(self):
        """Retourne le pays d'immatriculation / siège social (ex: France)."""
        if self.sign_data and self.sign_data.get("legal_country"):
            from utils.countries import get_country_name
            return get_country_name(self.sign_data.get("legal_country"))
        return "France"

    @property
    def display_legal_identifier_label(self):
        """Libellé adapté à l'identifiant renseigné pour le pays du siège."""
        return "SIRET" if self.display_legal_country.strip().lower() == "france" else "N° d’immatriculation"

    @property
    def display_legal_form(self):
        """Retourne la combinaison forme juridique et pays du locataire."""
        form = self.display_legal_form_only
        country = self.display_legal_country
        if form and country:
            if country.lower() not in form.lower():
                return f"{form} ({country})"
            return form
        return form or country or ""

    @property
    def display_signature_city(self):
        """Retourne la ville de signature (« Fait à »)."""
        if self.sign_data and self.sign_data.get("signature_city"):
            return self.sign_data.get("signature_city")
        return self.location_of_use or ""

    @property
    def display_order_ref(self):
        """Retourne la référence du bon de commande (uniquement si renseignée dans sign_data)."""
        if self.sign_data and self.sign_data.get("order_ref"):
            return self.sign_data.get("order_ref")
        return ""

    @property
    def bv_signature_data_uri(self):
        """Retourne la Data URI du contreseing Belle Vitesse pour injection directe dans les PDF."""
        from utils.signature_storage import load_signature_data_uri
        return load_signature_data_uri(self.bv_signature_data)

    @property
    def signature_data_uri(self):
        """Retourne la Data URI de la signature pour injection directe dans les templates ou PDF."""
        from utils.signature_storage import load_signature_data_uri
        return load_signature_data_uri(self.signature_data)

    @property
    def display_shooting_dates(self):
        """Retourne les dates de tournage simplifiées (date de début et date de fin)."""
        from services.admin.waivers import format_waiver_shooting_dates
        return format_waiver_shooting_dates(self.shooting_dates, default_sep=" au ")

    @property
    def display_project_name(self):
        """Retourne le nom du projet associé ou enregistré."""
        if self.project and self.project.name:
            return self.project.name
        return self.project_name or "—"

    @property
    def display_production_name(self):
        """Retourne le nom de la production associée ou enregistrée."""
        if self.project and self.project.production and self.project.production.name:
            return self.project.production.name
        return self.production_name or "—"

    @property
    def display_shooting_locations_list(self):
        """
        Retourne la liste ordonnée des lieux de tournage [{"name": ..., "address": ...}].
        Source prioritaire :
        1. Snapshot signé (sign_data["shooting_locations"] ou latest_signed_document.snapshot_data)
        2. Projet associé (locations_list)
        3. Repli sur location_of_use
        """
        if self.sign_data and isinstance(self.sign_data.get("shooting_locations"), list):
            return self.sign_data["shooting_locations"]

        doc = self.latest_signed_document
        if doc and doc.snapshot_data and isinstance(doc.snapshot_data.get("shooting_locations"), list):
            return doc.snapshot_data["shooting_locations"]

        if self.project and getattr(self.project, "locations_list", None):
            return self.project.locations_list

        if self.location_of_use and self.location_of_use.strip():
            return [{"name": self.location_of_use.strip(), "address": ""}]

        return []

    @property
    def has_shooting_locations(self):
        """Indique si la décharge dispose d'au moins un lieu de tournage."""
        return len(self.display_shooting_locations_list) > 0

    @property
    def display_shooting_locations(self):
        """Retourne une chaîne formatée et lisible des lieux de tournage."""
        locs = self.display_shooting_locations_list
        if not locs:
            return self.location_of_use or ""
        parts = []
        for loc in locs:
            if isinstance(loc, dict):
                name = loc.get("name", "").strip()
                addr = loc.get("address", "").strip()
                if addr:
                    parts.append(f"{name} ({addr})")
                elif name:
                    parts.append(name)
            elif isinstance(loc, str) and loc.strip():
                parts.append(loc.strip())
        return " ; ".join(parts) if parts else (self.location_of_use or "")

    # Traçabilité de la signature
    signer_ip = db.Column(db.String(45), nullable=True)

    # Historique d'archivage / synchronisation (legacy)
    webhook_triggered_at = db.Column(db.DateTime, nullable=True)

    # Suivi des relances automatiques
    last_reminded_at = db.Column(db.DateTime, nullable=True)
    reminder_count = db.Column(db.Integer, default=0, nullable=False)

    # Soft-delete support
    deleted_at = db.Column(db.DateTime, nullable=True)

    @property
    def created_at(self):
        """Alias pour generated_at pour cohérence avec les autres modèles et templates."""
        return self.generated_at

    @property
    def type(self):
        return self.waiver_type

    @type.setter
    def type(self, val):
        self.waiver_type = val

    def __init__(self, **kwargs):
        if "waiver_type" not in kwargs:
            poly_id = getattr(self, "__mapper_args__", {}
                              ).get("polymorphic_identity")
            kwargs["waiver_type"] = poly_id if poly_id != "waiver" else kwargs.get(
                "type", "safety_rules")
        if "waiver_id" not in kwargs:
            wt = kwargs.get("waiver_type")
            if wt == "cgl":
                prefix = "BVTC"
            elif wt == "pilot_waiver":
                prefix = "BVPA"
            elif wt == "risk_assessment":
                prefix = "BVRA"
            else:
                prefix = "BVSR"
            kwargs["waiver_id"] = generate_inspection_number(prefix)
        super().__init__(**kwargs)

    @property
    def hash(self):
        """Retourne l'empreinte cryptographique du document scellé s'il existe."""
        if self.sign_data and self.sign_data.get("hash"):
            return self.sign_data.get("hash")
        from models.waiver import WaiverSignedDocument
        signed_doc = WaiverSignedDocument.query.filter_by(
            waiver_id=self.waiver_id).order_by(WaiverSignedDocument.version.desc()).first()
        return signed_doc.hash if signed_doc else None

    @hash.setter
    def hash(self, value):
        data = dict(self.sign_data or {})
        data["hash"] = value
        self.sign_data = data

    def to_dict(self):
        """Convertit l'objet en dictionnaire pour les réponses API."""
        return {
            "id": self.id,
            "waiver_id": self.waiver_id,
            "waiver_type": self.waiver_type,
            "project_id": self.project_id,
            "status": self.status,
            "signer_name": self.signer_name,
            "signer_role": self.signer_role,
            "signer_email": self.signer_email,
            "production_name": self.production_name,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "signed_at": self.signed_at.isoformat() if self.signed_at else None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }

    @property
    def vehicles_details(self):
        """
        Retourne la liste détaillée des véhicules concernés par la décharge :
        nom, identifiant unique (unique_id), numéro de contrôle au départ (checkout_doc_id)
        et URL de la miniature (thumbnail).
        """
        results = []
        p = self.project

        # 1. Récupération des IDs véhicules du projet
        veh_ids = []
        if p and p.vehicles_to_check:
            veh_ids = [v.strip()
                       for v in p.vehicles_to_check.split(",") if v.strip()]
        elif p and p.active_checkout_vehicles:
            for cv in p.active_checkout_vehicles:
                if cv.vehicle_id and str(cv.vehicle_id) not in veh_ids:
                    veh_ids.append(str(cv.vehicle_id))

        if veh_ids:
            try:
                from utils.database import get_vehicles
                all_vehicles = get_vehicles() or []
                vehicle_map = {str(v["id"]): v.get("fields", {})
                               for v in all_vehicles}
            except Exception:
                vehicle_map = {}

            missing_ids = [vid for vid in veh_ids if str(vid) not in vehicle_map]
            if missing_ids:
                try:
                    from models.catalog import Vehicle
                    db_vehicles = Vehicle.query.filter(Vehicle.id.in_(missing_ids)).all()
                    for db_v in db_vehicles:
                        vehicle_map[str(db_v.id)] = db_v.fields or {}
                except Exception:
                    pass

            # Map des checkouts actifs par vehicle_id pour ce projet
            checkout_map = {}
            if p and p.active_checkout_vehicles:
                for cv in p.active_checkout_vehicles:
                    if cv.vehicle_id:
                        checkout_map[str(cv.vehicle_id)] = cv.inspection_number

            for vid in veh_ids:
                v_fields = vehicle_map.get(str(vid), {})
                v_name = v_fields.get("Nom") or v_fields.get("name") or f"ID {vid}"
                u_id = v_fields.get("unique_id") or v_fields.get("ID Unique") or ""
                co_num = checkout_map.get(str(vid)) or ""
                thumb = _extract_vehicle_thumbnail(v_fields)
                v_slug = v_fields.get("slug") or ""
                results.append({
                    "id": str(vid),
                    "name": v_name,
                    "unique_id": u_id,
                    "checkout_doc_id": co_num,
                    "thumbnail": thumb,
                    "slug": v_slug,
                })
        elif self.vehicles:
            try:
                from flask import g, has_request_context
                if has_request_context():
                    if not hasattr(g, "_waiver_name_to_fields"):
                        from utils.database import get_vehicles
                        all_vehicles = get_vehicles() or []
                        ntf = {}
                        for v in all_vehicles:
                            f = v.get("fields", {})
                            v_name = f.get("name")
                            if v_name:
                                ntf[v_name.strip().lower()] = (v["id"], f)
                        g._waiver_name_to_fields = ntf
                    name_to_fields = g._waiver_name_to_fields
                else:
                    from utils.database import get_vehicles
                    all_vehicles = get_vehicles() or []
                    name_to_fields = {}
                    for v in all_vehicles:
                        f = v.get("fields", {})
                        v_name = f.get("name")
                        if v_name:
                            name_to_fields[v_name.strip().lower()] = (v["id"], f)
            except Exception:
                name_to_fields = {}

            # Map checkout par vehicle_id
            checkout_map = {}
            if p and p.active_checkout_vehicles:
                for cv in p.active_checkout_vehicles:
                    if cv.vehicle_id:
                        checkout_map[str(cv.vehicle_id)] = cv.inspection_number

            for v_str in self.vehicles.split(","):
                clean = v_str.strip()
                if not clean:
                    continue
                match_id, match_fields = name_to_fields.get(
                    clean.lower(), (None, {}))
                u_id = match_fields.get("unique_id", "")
                co_num = checkout_map.get(
                    str(match_id), "") if match_id else ""
                thumb = _extract_vehicle_thumbnail(match_fields)
                v_slug = match_fields.get("slug") or ""
                results.append({
                    "id": str(match_id) if match_id else "",
                    "name": clean,
                    "unique_id": u_id,
                    "checkout_doc_id": co_num,
                    "thumbnail": thumb,
                    "slug": v_slug,
                })

        return results

    @property
    def non_road_legal_vehicles(self):
        """
        Retourne la liste des véhicules non-homologués route (route fermée uniquement) pour ce document.
        Prend en compte la configuration spécifique du projet si disponible, avec repli sur les détections par défaut.
        """
        details = self.vehicles_details or []
        p = self.project
        if not p:
            non_road_keywords = ["erover", "erider", "stark", "polar"]
            return [
                v for v in details
                if any(k in (v.get("slug") or "").lower() or k in (v.get("name") or "").lower() for k in non_road_keywords)
            ]
        return [
            v for v in details
            if not p.is_vehicle_road_legal(v.get("id"), v.get("slug", ""), v.get("name", ""))
        ]

    @property
    def signed_documents(self):
        """Retourne toutes les versions scellées de cette décharge, ordonnées par version croissante."""
        return WaiverSignedDocument.query.filter_by(waiver_id=self.waiver_id).order_by(WaiverSignedDocument.version.asc()).all()

    @property
    def latest_signed_document(self):
        """Retourne la version scellée la plus récente."""
        return WaiverSignedDocument.query.filter_by(waiver_id=self.waiver_id).order_by(WaiverSignedDocument.version.desc()).first()

    def __repr__(self):
        return f"<Waiver {self.waiver_id} ({self.waiver_type}) - {self.status}>"


class CglWaiver(Waiver):
    """Conditions Générales de Location (CGL - BVTC)."""
    __mapper_args__ = {
        "polymorphic_identity": "cgl",
    }

    @property
    def display_contract_production_name(self):
        """Raison sociale du Locataire telle que saisie au formulaire CGL (à défaut, celle du projet)."""
        if self.production_name and self.production_name.strip():
            return self.production_name.strip()
        return self.display_production_name

    def __repr__(self):
        return f"<CglWaiver {self.waiver_id} - {self.status}>"


class SafetyRulesWaiver(Waiver):
    """Règles de Sécurité."""
    __mapper_args__ = {
        "polymorphic_identity": "safety_rules",
    }

    @property
    def display_safety_technicians(self):
        """Retourne les référents techniques BV enregistrés ou à défaut ceux du projet."""
        if self.safety_technicians and self.safety_technicians.strip():
            return self.safety_technicians.strip()
        if self.project and getattr(self.project, "bv_referents_names", None):
            val = self.project.bv_referents_names
            return val.strip() if val and val.strip() else None
        return None

    @property
    def display_safety_technicians_count(self):
        """Retourne le nombre de référents BV associés (int)."""
        if self.project and getattr(self.project, "bv_referents", None):
            return len(self.project.bv_referents)
        techs_str = self.display_safety_technicians
        if not techs_str:
            return 0
        return len([name for name in techs_str.split(",") if name.strip()])

    @property
    def display_safety_technicians_list(self):
        """Retourne la liste des référents BV (objets User du projet si disponibles, ou liste d'objets avec name)."""
        if self.project and getattr(self.project, "bv_referents", None):
            referents = []
            for u in self.project.bv_referents:
                full_name = f"{u.firstname or ''} {u.lastname or ''}".strip()
                referents.append({
                    "name": full_name or u.mail or "Référent BV",
                    "role": getattr(u, "role_display", u.role or "Technicien"),
                })
            if referents:
                return referents

        techs_str = self.display_safety_technicians
        if not techs_str:
            return []
        return [{"name": name.strip(), "role": "Technicien"} for name in techs_str.split(",") if name.strip()]

    def __repr__(self):
        return f"<SafetyRulesWaiver {self.waiver_id} - {self.signer_role} - {self.status}>"


class PilotWaiver(Waiver):
    """Attestation d'information et d'engagement du pilote (Annexe 3 aux CGL - BVPA)."""
    __mapper_args__ = {
        "polymorphic_identity": "pilot_waiver",
    }

    @property
    def pilot_function_label(self):
        """Retourne la fonction du signataire adaptée à l'Annexe 3."""
        roles = {
            "pilot": "Pilote",
            "operator": "Opérateur gyropode",
            "stunt_performer": "Cascadeur",
            "other": self.signer_role_custom or "Autre",
        }
        return roles.get(self.signer_role, self.signer_role_custom or self.signer_role or "Pilote")

    @property
    def vehicles_details(self):
        """
        Retourne la liste détaillée des véhicules confiés spécifiquement à ce pilote.
        Si self.vehicles est défini, ne filtre que les véhicules assignés.
        """
        if not self.vehicles:
            return super().vehicles_details

        selected_tokens = {v.strip().lower()
                           for v in self.vehicles.split(",") if v.strip()}
        all_details = super().vehicles_details
        filtered = [
            v for v in all_details
            if v.get("name", "").strip().lower() in selected_tokens
            or v.get("unique_id", "").strip().lower() in selected_tokens
            or v.get("slug", "").strip().lower() in selected_tokens
        ]
        return filtered if filtered else all_details

    def __repr__(self):
        return f"<PilotWaiver {self.waiver_id} - {self.signer_name} - {self.status}>"


class ProductionWaiver(Waiver):
    """Décharge de production (Legacy BVPW)."""
    __mapper_args__ = {
        "polymorphic_identity": "production",
    }

    def __repr__(self):
        return f"<ProductionWaiver {self.waiver_id} - {self.status}>"


class LegacyPilotWaiver(PilotWaiver):
    """Décharge pilote historique avec identifiant polymorphe 'pilot' (Legacy BVPA/BVDW)."""
    __mapper_args__ = {
        "polymorphic_identity": "pilot",
    }

    def __repr__(self):
        return f"<LegacyPilotWaiver {self.waiver_id} - {self.status}>"


class RiskAssessmentWaiver(Waiver):
    """Analyse des Risques (Risk Assessment - BVRA)."""
    __mapper_args__ = {
        "polymorphic_identity": "risk_assessment",
    }

    @property
    def vehicles_details(self):
        """
        Retourne la liste détaillée des véhicules concernés par l'analyse des risques.
        Récupère automatiquement tous les véhicules du projet (ou self.vehicles en repli).
        """
        details = super().vehicles_details
        if details:
            return details

        # Repli si le projet n'avait pas encore vehicles_to_check mais waiver.vehicles est renseigné
        if self.vehicles:
            try:
                from utils.database import get_vehicles
                all_vehicles = get_vehicles() or []
                vehicle_by_name = {}
                for v in all_vehicles:
                    f = v.get("fields", {})
                    v_name = f.get("Nom") or f.get("name")
                    if v_name:
                        vehicle_by_name[v_name.strip().lower()] = (v["id"], f)
            except Exception:
                vehicle_by_name = {}

            try:
                from models.catalog import Vehicle
                db_vehicles = Vehicle.query.all()
                for db_v in db_vehicles:
                    f = db_v.fields or {}
                    v_name = f.get("Nom") or f.get("name")
                    if v_name and v_name.strip().lower() not in vehicle_by_name:
                        vehicle_by_name[v_name.strip().lower()] = (db_v.id, f)
            except Exception:
                pass

            results = []
            for v_str in self.vehicles.split(","):
                clean = v_str.strip()
                if not clean:
                    continue
                match_id, match_fields = vehicle_by_name.get(clean.lower(), (None, {}))
                results.append({
                    "id": str(match_id) if match_id else "",
                    "name": clean,
                    "unique_id": match_fields.get("unique_id") or match_fields.get("ID Unique") or "",
                    "checkout_doc_id": "",
                    "thumbnail": _extract_vehicle_thumbnail(match_fields),
                    "slug": match_fields.get("slug") or "",
                })
            return results

        return []

    def __repr__(self):
        return f"<RiskAssessmentWaiver {self.waiver_id} - {self.signer_role} - {self.status}>"


# ── Tokens et Documents Signés Unifiés ───────────────────────────

class WaiverToken(db.Model, TokenMixin):
    """Jeton de session pour la signature d'une décharge unifiée."""
    __tablename__ = "waiver_tokens"
    waiver_id = db.Column(db.String(255), nullable=False, index=True)
    signature = db.Column(db.String(255), nullable=True)


class WaiverSignedDocument(db.Model, SignedDocumentMixin):
    """Archive d'une décharge unifiée signée (avec support du versionnement et traçabilité parent_hash)."""
    __tablename__ = "waiver_signed_documents"
    waiver_id = db.Column(db.String(50), primary_key=True)
    version = db.Column(db.Integer, primary_key=True, default=1)
    parent_hash = db.Column(db.String(255), nullable=True)



