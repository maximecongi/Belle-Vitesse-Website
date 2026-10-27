from datetime import datetime, timedelta, timezone
from models.db import db, generate_inspection_number, _utcnow


# ── Mixins Partagés ──────────────────────────────────────────────

class TokenMixin:
    """Base pour tous les jetons (tokens) de signature à durée limitée."""
    token = db.Column(db.String(36), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    expires_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: _utcnow() + timedelta(hours=24),
                           server_default=db.FetchedValue())

    def is_expired(self) -> bool:
        """Indique si le jeton a dépassé sa durée de validité (24h)."""
        now = datetime.now(timezone.utc)
        if self.expires_at:
            exp = self.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            return now > exp
        if self.created_at:
            created = self.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            return (now - created) > timedelta(hours=24)
        return False


class SignedDocumentMixin:
    """Base pour tous les documents signés archivés."""
    hash = db.Column(
        db.String(255), nullable=False)  # Empreinte de l'intégrité des données
    # Hash SHA-256 du fichier PDF binaire
    pdf_file_hash = db.Column(db.String(64))
    # Copie conforme des données au moment de la signature
    data_snapshot = db.Column(db.JSON, nullable=False)
    # Chemin relatif du fichier signature PNG
    signature = db.Column(db.String(255), nullable=True)
    pdf_url = db.Column(db.Text)  # URL (ou chemin) vers le fichier PDF
    signed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=_utcnow)

    @property
    def signature_data_uri(self):
        """Retourne la Data URI de la signature pour injection directe dans les templates ou PDF."""
        from utils.signature_storage import load_signature_data_uri
        return load_signature_data_uri(self.signature)


# ── Modèle Unifié des Décharges ──────────────────────────────────

def _generate_default_waiver_id(context):
    params = context.get_current_parameters()
    w_type = params.get("waiver_type", "safety_rules")
    prefix = "BVRA" if w_type == "cgl" else "BVSR"
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
    # Noms des référents BV pour ce tournage (personnalisables)
    safety_technicians = db.Column(db.Text, nullable=True)
    helmets_inventory = db.Column(db.JSON, default=dict, nullable=True)
    custom_rules_snapshot = db.Column(db.JSON, default=dict, nullable=True)
    bv_signature_data = db.Column(db.String(255), nullable=True)
    bv_signed_at = db.Column(db.DateTime, nullable=True)
    bv_signer_name = db.Column(db.String(100), nullable=True)

    # Données signataire Production (BVRA / CGL)
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
            prefix = "BVRA" if kwargs.get("waiver_type") == "cgl" else "BVSR"
            kwargs["waiver_id"] = generate_inspection_number(prefix)
        super().__init__(**kwargs)

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

            # Map des checkouts actifs par vehicle_id pour ce projet
            checkout_map = {}
            if p and p.active_checkout_vehicles:
                for cv in p.active_checkout_vehicles:
                    if cv.vehicle_id:
                        checkout_map[str(cv.vehicle_id)] = cv.inspection_number

            for vid in veh_ids:
                v_fields = vehicle_map.get(str(vid), {})
                v_name = v_fields.get("name") or f"ID {vid}"
                u_id = v_fields.get("unique_id") or ""
                co_num = checkout_map.get(str(vid)) or ""
                thumb = _extract_vehicle_thumbnail(v_fields)
                v_slug = v_fields.get("slug") or ""
                results.append({
                    "name": v_name,
                    "unique_id": u_id,
                    "checkout_doc_id": co_num,
                    "thumbnail": thumb,
                    "slug": v_slug,
                })
        elif self.vehicles:
            try:
                from utils.database import get_vehicles
                all_vehicles = get_vehicles() or []
            except Exception:
                all_vehicles = []

            # Dictionnaire nom -> fields
            name_to_fields = {}
            for v in all_vehicles:
                f = v.get("fields", {})
                v_name = f.get("name")
                if v_name:
                    name_to_fields[v_name.strip().lower()] = (v["id"], f)

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
                    "name": clean,
                    "unique_id": u_id,
                    "checkout_doc_id": co_num,
                    "thumbnail": thumb,
                    "slug": v_slug,
                })

        return results

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
    """Conditions Générales de Location (CGL - BVRA)."""
    __mapper_args__ = {
        "polymorphic_identity": "cgl",
    }

    def __repr__(self):
        return f"<CglWaiver {self.waiver_id} - {self.status}>"


class SafetyRulesWaiver(Waiver):
    """Règles de Sécurité Universelles (BVSR)."""
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

    def __repr__(self):
        return f"<SafetyRulesWaiver {self.waiver_id} - {self.signer_role} - {self.status}>"


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


# ── Modèles des Inspections (Préservés) ──────────────────────────

class CheckoutSignedDocument(db.Model, SignedDocumentMixin):
    """Archive d'une inspection au départ signée."""
    __tablename__ = "checkout_signed_documents"
    inspection_id = db.Column(db.String(255), primary_key=True)


class CheckoutToken(db.Model, TokenMixin):
    """Jeton de session pour la signature d'un check-out."""
    __tablename__ = "checkout_tokens"
    record_id = db.Column(db.String(255), nullable=False)
    inspection_id = db.Column(db.String(255), nullable=False)
    signature = db.Column(db.String(255), nullable=True)


class CheckinSignedDocument(db.Model, SignedDocumentMixin):
    """Archive d'une inspection au retour signée."""
    __tablename__ = "checkin_signed_documents"
    inspection_id = db.Column(db.String(255), primary_key=True)


class CheckinToken(db.Model, TokenMixin):
    """Jeton de session pour la signature d'un check-in."""
    __tablename__ = "checkin_tokens"
    record_id = db.Column(db.String(255), nullable=False)
    inspection_id = db.Column(db.String(255), nullable=False)
    signature = db.Column(db.String(255), nullable=True)
