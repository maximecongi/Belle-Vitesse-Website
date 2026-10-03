from datetime import timedelta
from models.db import db, generate_inspection_number, _utcnow


# ── Mixins Partagés ──────────────────────────────────────────────

class TokenMixin:
    """Base pour tous les jetons (tokens) de signature à durée limitée."""
    token = db.Column(db.String(36), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    expires_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: _utcnow() + timedelta(hours=24),
                           server_default=db.FetchedValue())


class SignedDocumentMixin:
    """Base pour tous les documents signés archivés."""
    hash = db.Column(db.String(255), nullable=False)  # Empreinte de l'intégrité des données
    pdf_file_hash = db.Column(db.String(64))  # Hash SHA-256 du fichier PDF binaire
    data_snapshot = db.Column(db.JSON, nullable=False)  # Copie conforme des données au moment de la signature
    signature = db.Column(db.String(255), nullable=True)  # Chemin relatif du fichier signature PNG
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
    w_type = params.get("waiver_type", "pilot")
    prefix = "BVPW" if w_type == "production" else "BVDW"
    return generate_inspection_number(prefix)


class Waiver(db.Model):
    """
    Modèle unifié représentant une décharge de responsabilité (pilote, production, etc.).
    Remplace les anciennes tables jumelles pilot_waivers et production_waivers.
    Supporte le polymorphisme Single Table Inheritance pour PilotWaiver et ProductionWaiver.
    """
    __tablename__ = "waivers"
    __table_args__ = (
        db.UniqueConstraint("project_id", "waiver_type", name="uq_project_waiver_type"),
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    waiver_type = db.Column(db.String(20), nullable=False, default="pilot", index=True)
    waiver_id = db.Column(db.String(50), unique=True, default=_generate_default_waiver_id, nullable=False, index=True)

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

    # Données signataire Pilote
    pilot_first_name = db.Column(db.String(100), nullable=True)
    pilot_last_name = db.Column(db.String(100), nullable=True)
    pilot_dob = db.Column(db.Date, nullable=True)
    pilot_license_number = db.Column(db.String(100), nullable=True)
    pilot_address = db.Column(db.Text, nullable=True)
    pilot_insurance_company = db.Column(db.String(255), nullable=True)
    pilot_insurance_policy = db.Column(db.String(255), nullable=True)
    pilot_license_path = db.Column(db.String(500), nullable=True)
    pilot_insurance_path = db.Column(db.String(500), nullable=True)
    pilot_identity_path = db.Column(db.String(500), nullable=True)

    # Données signataire Production
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

    # Signature (Chemin relatif PNG ex: signatures/waivers/BVDW-xxx.png)
    signature_data = db.Column(db.String(255), nullable=True)
    # Chemin relatif du PDF signé
    signed_pdf_path = db.Column(db.String(500), nullable=True)

    @property
    def signature_data_uri(self):
        """Retourne la Data URI de la signature pour injection directe dans les templates ou PDF."""
        from utils.signature_storage import load_signature_data_uri
        return load_signature_data_uri(self.signature_data)

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
    def type(self):
        return self.waiver_type

    @type.setter
    def type(self, val):
        self.waiver_type = val

    def __init__(self, **kwargs):
        if "waiver_type" not in kwargs:
            poly_id = getattr(self, "__mapper_args__", {}).get("polymorphic_identity")
            if poly_id and poly_id != "waiver":
                kwargs["waiver_type"] = poly_id
            else:
                kwargs["waiver_type"] = kwargs.get("type", "pilot")
        if "waiver_id" not in kwargs:
            prefix = "BVPW" if kwargs.get("waiver_type") == "production" else "BVDW"
            kwargs["waiver_id"] = generate_inspection_number(prefix)
        super().__init__(**kwargs)

    def to_dict(self):
        """Convertit l'objet en dictionnaire pour les réponses API."""
        return {
            "id": self.id,
            "waiver_id": self.waiver_id,
            "waiver_type": self.waiver_type,
            "type": self.waiver_type,
            "project_id": self.project_id,
            "status": self.status,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "signed_at": self.signed_at.isoformat() if self.signed_at else None,
            "pilot_first_name": self.pilot_first_name,
            "pilot_last_name": self.pilot_last_name,
            "production_name": self.production_name,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }

    @property
    def vehicles_details(self):
        """
        Retourne la liste détaillée des véhicules concernés par la décharge :
        nom, identifiant unique (unique_id) et numéro de contrôle au départ (checkout_doc_id).
        """
        results = []
        p = self.project

        # 1. Récupération des IDs véhicules du projet
        veh_ids = []
        if p and p.vehicles_to_check:
            veh_ids = [v.strip() for v in p.vehicles_to_check.split(",") if v.strip()]
        elif p and p.active_checkout_vehicles:
            for cv in p.active_checkout_vehicles:
                if cv.vehicle_id and str(cv.vehicle_id) not in veh_ids:
                    veh_ids.append(str(cv.vehicle_id))

        if veh_ids:
            try:
                from utils.database import get_vehicles
                all_vehicles = get_vehicles() or []
                vehicle_map = {str(v["id"]): v.get("fields", {}) for v in all_vehicles}
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
                results.append({
                    "name": v_name,
                    "unique_id": u_id,
                    "checkout_doc_id": co_num,
                })
        elif self.vehicles:
            # Fallback pour les décharges historiques sans veh_ids sur le projet : résolution par nom
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
                match_id, match_fields = name_to_fields.get(clean.lower(), (None, {}))
                u_id = match_fields.get("unique_id", "")
                co_num = checkout_map.get(str(match_id), "") if match_id else ""
                results.append({
                    "name": clean,
                    "unique_id": u_id,
                    "checkout_doc_id": co_num,
                })

        return results

    def __repr__(self):
        return f"<Waiver {self.waiver_id} ({self.waiver_type}) - {self.status}>"


class PilotWaiver(Waiver):
    """Sous-classe polymorphique pour les décharges pilotes."""
    __mapper_args__ = {
        "polymorphic_identity": "pilot",
    }

    def __repr__(self):
        return f"<PilotWaiver {self.waiver_id} - {self.status}>"


class ProductionWaiver(Waiver):
    """Sous-classe polymorphique pour les décharges productions."""
    __mapper_args__ = {
        "polymorphic_identity": "production",
    }

    def __repr__(self):
        return f"<ProductionWaiver {self.waiver_id} - {self.status}>"


# ── Tokens et Documents Signés Unifiés ───────────────────────────

class WaiverToken(db.Model, TokenMixin):
    """Jeton de session pour la signature d'une décharge unifiée."""
    __tablename__ = "waiver_tokens"
    waiver_id = db.Column(db.String(255), nullable=False, index=True)
    signature = db.Column(db.String(255), nullable=True)


class WaiverSignedDocument(db.Model, SignedDocumentMixin):
    """Archive d'une décharge unifiée signée."""
    __tablename__ = "waiver_signed_documents"
    waiver_id = db.Column(db.String(50), primary_key=True)


# Aliases pour rétrocompatibilité
PilotWaiverToken = WaiverToken
ProductionWaiverToken = WaiverToken
PilotWaiverSignedDocument = WaiverSignedDocument
ProductionWaiverSignedDocument = WaiverSignedDocument


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
