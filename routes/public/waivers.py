import hashlib
import os
import re
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone

from flask import Blueprint, abort, current_app, jsonify, render_template, request
from werkzeug.utils import secure_filename

from extensions import csrf, limiter
from models import (
    CglWaiver,
    SafetyRulesWaiver,
    PilotWaiver,
    RiskAssessmentWaiver,
    WaiverToken,
    WaiverSignedDocument,
    db,
)
from routes.public.shared_docs import handle_document_download, handle_document_verify
from services.admin.safety_rules_config import (
    get_safety_rules_for_vehicles,
    get_merged_general_safety_rules,
    DEFAULT_HELMETS_INVENTORY,
)
from utils.document_utils import compute_file_sha256, CGL_VERSION
from utils.request_utils import get_client_ip
from utils.storage import ensure_dir, get_cgl_attachments_path
from utils.image_utils import optimize_and_save_image, IMAGE_EXTENSIONS


def _is_valid_magic_bytes(file_bytes: bytes, ext: str) -> bool:
    """Valide les premiers octets (magic bytes) des pièces jointes téléversées."""
    if len(file_bytes) < 4:
        return False
    if ext == ".pdf":
        return file_bytes.startswith(b"%PDF")
    if ext == ".png":
        return file_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in (".jpg", ".jpeg"):
        return file_bytes.startswith(b"\xff\xd8\xff")
    if ext in (".heic", ".heif"):
        return b"ftyp" in file_bytes[:12]
    return False


def _get_waiver_route_config(mode):
    if mode == "safety_rules":
        return {
            "mode": "safety_rules",
            "model": SafetyRulesWaiver,
            "signed_model": WaiverSignedDocument,
            "token_model": WaiverToken,
            "template_sign": "public/waivers/sign_safety_rules.html",
            "template_verify": "public/waivers/safety_rules_verify.html",
            "route_base": "safety-rules",
            "seal_prefix": "BVSR",
        }
    elif mode == "pilot_waiver":
        return {
            "mode": "pilot_waiver",
            "model": PilotWaiver,
            "signed_model": WaiverSignedDocument,
            "token_model": WaiverToken,
            "template_sign": "public/waivers/sign_pilot_waiver.html",
            "template_verify": "public/waivers/pilot_waiver_verify.html",
            "route_base": "pilot-attestation",
            "seal_prefix": "BVPA",
        }
    elif mode == "risk_assessment":
        return {
            "mode": "risk_assessment",
            "model": RiskAssessmentWaiver,
            "signed_model": WaiverSignedDocument,
            "token_model": WaiverToken,
            "template_sign": "public/waivers/sign_risk_assessment.html",
            "template_verify": "public/waivers/risk_assessment_verify.html",
            "route_base": "risk-assessment",
            "seal_prefix": "BVRA",
        }
    return {
        "mode": "cgl",
        "model": CglWaiver,
        "signed_model": WaiverSignedDocument,
        "token_model": WaiverToken,
        "template_sign": "public/cgl/sign_cgl.html",
        "template_verify": "public/cgl/cgl_verify.html",
        "route_base": "cgl",
        "seal_prefix": "BVTC",
    }


class SignFormError(ValueError):
    """Erreur de validation d'un formulaire public de signature (message destiné au signataire)."""


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _apply_sign_form(mode, waiver, data, *, strict, user_agent="", output_base=None):
    """
    Applique les valeurs saisies dans le formulaire public de signature sur l'objet waiver.

    - strict=True  : signature réelle. Consentements, champs requis et formats sont contrôlés
                     (SignFormError levée), la pièce jointe d'assurance CGL est enregistrée.
    - strict=False : aperçu PDF live. Aucun contrôle bloquant, valeurs tronquées à la longueur
                     maximale, aucun fichier écrit. L'appelant doit annuler la transaction.

    Retourne (rep_name, rep_role) pour la journalisation du consentement.
    """

    def require(condition, message):
        if strict and not condition:
            raise SignFormError(message)

    def clip(value, max_len, message):
        value = str(value or "").strip()
        if len(value) > max_len:
            if strict:
                raise SignFormError(message)
            value = value[:max_len]
        return value

    def email_value(raw):
        email = clip(raw, 120, "L'adresse e-mail renseignée est invalide.")
        if email and not _EMAIL_RE.match(email):
            require(False, "L'adresse e-mail renseignée est invalide.")
        return email

    rep_role = None
    now_iso = datetime.now(timezone.utc).isoformat()

    if mode in ("safety_rules", "pilot_waiver", "risk_assessment"):
        ack_key = {
            "safety_rules": "ack_rules",
            "pilot_waiver": "ack_pilot_engagement",
            "risk_assessment": "ack_risk_assessment",
        }[mode]
        ack_message = {
            "safety_rules": "La prise de connaissance et le respect des Règles de Sécurité sont obligatoires.",
            "pilot_waiver": "La déclaration sur l'honneur et le respect des consignes de sécurité de l'Annexe 3 sont obligatoires.",
            "risk_assessment": "La prise de connaissance et le respect de l'Analyse des Risques sont obligatoires.",
        }[mode]
        require(str(data.get(ack_key, "")).lower() in ("1", "on", "true"), ack_message)

        if data.get("first_name"):
            waiver.signer_first_name = clip(data.get("first_name"), 100, "Le prénom ne peut dépasser 100 caractères.")
        if data.get("last_name"):
            waiver.signer_last_name = clip(data.get("last_name"), 100, "Le nom ne peut dépasser 100 caractères.")
        if data.get("email"):
            waiver.signer_email = email_value(data.get("email"))
        if data.get("phone"):
            waiver.signer_phone = clip(data.get("phone"), 50, "Le numéro de téléphone ne peut dépasser 50 caractères.")

        entity_type = None
        comp_name = comp_addr = ""
        if mode == "pilot_waiver":
            if data.get("company"):
                waiver.signer_company = clip(data.get("company"), 150, "La société ne peut dépasser 150 caractères.")
        else:
            entity_type = str(data.get("signer_entity_type") or data.get("entity_type") or "freelance").strip().lower()
            if entity_type == "company":
                comp_name = str(data.get("company_name") or data.get("company") or "").strip()
                comp_addr = str(data.get("company_address") or "").strip()
                waiver.signer_company = comp_name
                waiver.production_name = comp_name
                waiver.production_address = comp_addr
            else:
                entity_type = "freelance"
                if mode == "safety_rules":
                    waiver.signer_company = None
                    waiver.production_name = None
                    waiver.production_address = None
                elif data.get("company"):
                    waiver.signer_company = str(data.get("company")).strip()

        role_raw = data.get("signer_role") or (data.get("role") if mode == "risk_assessment" else None)
        if role_raw:
            waiver.signer_role = clip(role_raw, 100, "La fonction ne peut dépasser 100 caractères.")
        if data.get("role_custom"):
            waiver.signer_role_custom = clip(data.get("role_custom"), 100, "Le rôle personnalisé ne peut dépasser 100 caractères.")

        rep_name = f"{waiver.signer_first_name or ''} {waiver.signer_last_name or ''}".strip()

        sign_data = dict(waiver.sign_data or {})
        if entity_type:
            sign_data["entity_type"] = entity_type
            if entity_type == "company":
                sign_data["company_name"] = comp_name
                sign_data["company_address"] = comp_addr
        sign_data[ack_key] = True
        sign_data["accepted_at"] = now_iso
        if mode == "pilot_waiver":
            sign_data["authority_declaration_text"] = (
                "Je déclare être sous l'autorité exclusive de la production (l'Employeur), "
                "sans aucun lien de subordination juridique avec Belle Vitesse, et m'engage à appliquer "
                "rigoureusement l'ensemble des règles opérationnelles et de sécurité de l'Annexe 3."
            )
        sign_data["shooting_locations"] = waiver.display_shooting_locations_list
        waiver.sign_data = sign_data
        return rep_name, rep_role

    # ── CGL ──────────────────────────────────────────────────────
    # Validation stricte du consentement et de la déclaration de pouvoir pour les CGL
    require(data.get("accepted_terms") == "1",
            "L'acceptation expresse des Conditions Générales de Location est obligatoire.")
    require(data.get("has_signing_authority") == "1",
            "La déclaration sur l'honneur de pouvoir d'engager la société est obligatoire.")

    prod_name = (data.get("production_name") or waiver.production_name or "").strip()
    require(prod_name and len(prod_name) <= 150,
            "La raison sociale de la production est obligatoire (max 150 caractères).")
    prod_name = prod_name[:150]

    rep_name = (data.get("representative") or waiver.production_representative or "").strip()
    rep_role = (data.get("representative_role") or waiver.signer_role_custom or "").strip()
    require(rep_name and rep_role,
            "Le nom du signataire et sa fonction au sein de la société sont obligatoires.")
    rep_name = clip(rep_name, 150, "Le nom du signataire ne peut dépasser 150 caractères.")
    rep_role = clip(rep_role, 100, "La fonction du signataire ne peut dépasser 100 caractères.")

    address = clip(data.get("address") or waiver.production_address or "", 255,
                   "L'adresse du siège social ne peut dépasser 255 caractères.")

    email = (data.get("email") or waiver.signer_email or "").strip()
    if email:
        email = email_value(email)

    siret_value = data.get("siret") if "siret" in data else waiver.production_siret
    siret = (siret_value or "").strip()
    legal_country = (data.get("legal_country") or (waiver.sign_data or {}).get("legal_country") or "FR").strip().upper()
    if legal_country in ("FR", "FRANCE"):
        require(siret, "Le numéro SIRET est obligatoire pour une société dont le siège est en France.")
        siret_clean = re.sub(r"\s+", "", siret)
        if strict:
            require(siret_clean.isdigit() and len(siret_clean) == 14,
                    "Le numéro SIRET doit comporter exactement 14 chiffres pour une société française.")
            siret = siret_clean
    else:
        siret = clip(siret, 100, "Le numéro d’immatriculation ne peut dépasser 100 caractères.")

    waiver.production_name = prod_name
    waiver.production_representative = rep_name
    if address:
        waiver.production_address = address
    waiver.production_siret = siret
    if data.get("vat_number"):
        waiver.production_vat = clip(data.get("vat_number"), 100,
                                     "Le numéro de TVA intracommunautaire ne peut dépasser 100 caractères.")
    if data.get("phone"):
        waiver.signer_phone = clip(data.get("phone"), 50, "Le numéro de téléphone ne peut dépasser 50 caractères.")
    if email:
        waiver.signer_email = email
    waiver.signer_role_custom = rep_role
    if data.get("insurance_company"):
        waiver.production_insurance_company = clip(
            data.get("insurance_company"), 255, "Le nom de la compagnie d'assurance ne peut dépasser 255 caractères.")
    if data.get("insurance_policy"):
        waiver.production_insurance_policy = clip(
            data.get("insurance_policy"), 255, "Le numéro de police d'assurance ne peut dépasser 255 caractères.")
    if data.get("location_of_use"):
        waiver.location_of_use = clip(data.get("location_of_use"), 255,
                                      "Le lieu d'utilisation ne peut dépasser 255 caractères.")
    elif data.get("city") and not waiver.location_of_use:
        waiver.location_of_use = clip(data.get("city"), 255, "La ville ne peut dépasser 255 caractères.")

    # Calcul de l'empreinte du partial des articles CGL (termes acceptés immuables)
    terms_fingerprint = ""
    if strict:
        try:
            template_source, _, _ = current_app.jinja_env.loader.get_source(
                current_app.jinja_env, "public/cgl/_cgl_articles.html")
            terms_fingerprint = hashlib.sha256(template_source.encode("utf-8")).hexdigest()
        except Exception:
            pass

    # Snapshot structuré JSON
    s_data = dict(waiver.sign_data or {})
    s_data["cgl_version"] = CGL_VERSION
    s_data["accepted_terms"] = True
    s_data["accepted_at"] = now_iso
    s_data["has_signing_authority"] = True
    s_data["authority_declaration_text"] = (
        "Je certifie sur l'honneur être dûment habilité(e) et disposer de tous les pouvoirs "
        "et délégations nécessaires pour représenter, engager juridiquement et obliger financièrement "
        "la société preneuse pour le présent contrat de location et l'ensemble de ses suites."
    )
    s_data["representative_name"] = rep_name
    s_data["representative_role"] = rep_role
    s_data["terms_fingerprint"] = terms_fingerprint
    s_data["user_agent"] = user_agent

    if data.get("legal_form"):
        s_data["legal_form"] = data.get("legal_form").strip()
    if data.get("legal_country"):
        s_data["legal_country"] = data.get("legal_country").strip()
    if rep_role:
        s_data["representative_role"] = rep_role
    if data.get("city"):
        s_data["signature_city"] = data.get("city").strip()
    if data.get("order_ref"):
        s_data["order_ref"] = data.get("order_ref").strip()
    # Stocker la liste des lieux au moment de la signature
    s_data["shooting_locations"] = waiver.display_shooting_locations_list
    if data.get("insurance_company"):
        s_data["insurance_company"] = data.get("insurance_company").strip()
    if data.get("insurance_policy"):
        s_data["insurance_policy"] = data.get("insurance_policy").strip()

    # Pièce jointe assurance production (CGL) avec validation stricte — jamais en aperçu
    if strict:
        insurance_file_sha256 = ""
        insurance_upload_sha256 = ""
        file = request.files.get('production_insurance')
        if file and file.filename:
            ext = os.path.splitext(file.filename)[1].lower()
            allowed_exts = {'.pdf', '.png', '.jpg', '.jpeg', '.heic', '.heif'}
            if ext not in allowed_exts:
                raise SignFormError("Format d'attestation d'assurance non autorisé (PDF ou image requis).")

            file_bytes = file.read()
            if len(file_bytes) > 10 * 1024 * 1024:
                raise SignFormError("L'attestation d'assurance dépasse la taille maximale autorisée (10 Mo).")

            if not _is_valid_magic_bytes(file_bytes, ext):
                raise SignFormError("Le contenu du fichier téléversé ne correspond pas à une attestation valide (signature de fichier non reconnue).")

            insurance_upload_sha256 = hashlib.sha256(file_bytes).hexdigest()
            file.seek(0)

            upload_dir = ensure_dir(get_cgl_attachments_path(waiver.project, 'insurance'))
            stem = os.path.splitext(secure_filename(file.filename))[0]
            if ext in ('.heic', '.heif'):
                ext = '.jpg'
            fname = f"prod_insurance_{int(datetime.now().timestamp())}_{stem}{ext}"
            file_path = os.path.join(upload_dir, fname)
            if ext in IMAGE_EXTENSIONS or ext == '.jpg':
                optimize_and_save_image(file, file_path)
            else:
                file.save(file_path)
            waiver.production_insurance_path = os.path.relpath(file_path, output_base)

            # Point 10: Calcul du SHA-256 physique du fichier stocké post-optimisation
            insurance_file_sha256 = compute_file_sha256(file_path)

        s_data["insurance_file_sha256"] = insurance_file_sha256
        s_data["insurance_upload_sha256"] = insurance_upload_sha256
    waiver.sign_data = s_data
    return rep_name, rep_role


public_waivers_bp = Blueprint("public_waivers", __name__)


# ── Routes de Signature ──────────────────────────────────────

@public_waivers_bp.route("/sign/cgl/<token>", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def sign_cgl(token):
    return _handle_sign_waiver("cgl", token)

@public_waivers_bp.route("/sign/safety-rules/<token>", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def sign_safety_rules(token):
    return _handle_sign_waiver("safety_rules", token)

@public_waivers_bp.route("/sign/pilot-attestation/<token>", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def sign_pilot_waiver(token):
    return _handle_sign_waiver("pilot_waiver", token)

@public_waivers_bp.route("/sign/risk-assessment/<token>", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def sign_risk_assessment(token):
    return _handle_sign_waiver("risk_assessment", token)

# ── Aperçu PDF live des formulaires de signature ────────────
#
# Protection de la charge serveur (un rendu WeasyPrint ≈ 1 à 2,5 s de CPU, GIL compris) :
# - côté client, une seule requête d'aperçu en vol par onglet (cf. pdf-form-preview.js) ;
# - cache LRU par processus des PDF déjà rendus, indexé sur l'empreinte du HTML final
#   (toute modification du formulaire, des données admin ou des templates l'invalide) ;
# - au plus _PREVIEW_MAX_CONCURRENT rendus simultanés par worker : au-delà, réponse 429
#   et le navigateur réessaie en conservant le dernier aperçu affiché ;
# - rate limit par jeton de signature (et non par IP partagée d'une production).

_PREVIEW_RATE_LIMIT = "30 per minute"
_PREVIEW_MAX_CONCURRENT = 1
_PREVIEW_ACQUIRE_TIMEOUT_S = 0.5
_PREVIEW_RETRY_AFTER_S = 2
_PREVIEW_CACHE_MAX_ENTRIES = 32
_PREVIEW_CACHE_TTL_S = 15 * 60

_preview_render_slots = threading.BoundedSemaphore(_PREVIEW_MAX_CONCURRENT)
_preview_cache = OrderedDict()
_preview_cache_lock = threading.Lock()


def _preview_rate_key():
    token = (request.view_args or {}).get("token")
    return f"sign-preview:{token}" if token else get_client_ip()


def _preview_cache_get(key):
    with _preview_cache_lock:
        entry = _preview_cache.get(key)
        if not entry:
            return None
        created_at, pdf_bytes = entry
        if time.monotonic() - created_at > _PREVIEW_CACHE_TTL_S:
            _preview_cache.pop(key, None)
            return None
        _preview_cache.move_to_end(key)
        return pdf_bytes


def _preview_cache_set(key, pdf_bytes):
    with _preview_cache_lock:
        _preview_cache[key] = (time.monotonic(), pdf_bytes)
        _preview_cache.move_to_end(key)
        while len(_preview_cache) > _PREVIEW_CACHE_MAX_ENTRIES:
            _preview_cache.popitem(last=False)


def _preview_pdf_response(pdf_bytes, waiver_id, cache_status):
    response = current_app.response_class(pdf_bytes, mimetype="application/pdf")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Disposition"] = f'inline; filename="{waiver_id}_apercu.pdf"'
    response.headers["X-Preview-Cache"] = cache_status
    return response

@public_waivers_bp.route("/sign/cgl/<token>/preview", methods=["POST"])
@limiter.limit(_PREVIEW_RATE_LIMIT, key_func=_preview_rate_key)
def preview_cgl(token):
    return _handle_sign_preview("cgl", token)

@public_waivers_bp.route("/sign/safety-rules/<token>/preview", methods=["POST"])
@limiter.limit(_PREVIEW_RATE_LIMIT, key_func=_preview_rate_key)
def preview_safety_rules(token):
    return _handle_sign_preview("safety_rules", token)

@public_waivers_bp.route("/sign/pilot-attestation/<token>/preview", methods=["POST"])
@limiter.limit(_PREVIEW_RATE_LIMIT, key_func=_preview_rate_key)
def preview_pilot_waiver(token):
    return _handle_sign_preview("pilot_waiver", token)

@public_waivers_bp.route("/sign/risk-assessment/<token>/preview", methods=["POST"])
@limiter.limit(_PREVIEW_RATE_LIMIT, key_func=_preview_rate_key)
def preview_risk_assessment(token):
    return _handle_sign_preview("risk_assessment", token)


def _handle_sign_preview(mode, token):
    """
    Rend le PDF réel du document (même template WeasyPrint que l'archive scellée) à partir des
    valeurs en cours de saisie, avec les zones issues du formulaire surlignées et cliquables.
    Rien n'est persisté : les modifications appliquées au waiver sont annulées après rendu.
    """
    from services.common.signatures import FLOW_CONFIG, build_document_render_context
    from utils.document_utils import render_pdf_from_template
    from utils.request_utils import resolve_base_url

    config = _get_waiver_route_config(mode)
    if request.content_length and request.content_length > 1024 * 1024:
        return jsonify({"success": False, "error": "Requête trop volumineuse."}), 413

    token_rec = config["token_model"].query.filter_by(token=token).first()
    if not token_rec:
        return jsonify({"success": False, "error": "Jeton invalide."}), 404
    waiver = config["model"].query.filter_by(waiver_id=token_rec.waiver_id).first()
    if not waiver:
        return jsonify({"success": False, "error": "Document introuvable."}), 404
    if waiver.status in ("signed", "completed") or token_rec.signature:
        return jsonify({"success": False, "error": "Ce document a déjà été signé."}), 409
    if token_rec.expires_at:
        exp = token_rec.expires_at
        now_utc = datetime.now(timezone.utc)
        if exp < (now_utc if exp.tzinfo is not None else now_utc.replace(tzinfo=None)):
            return jsonify({"success": False, "error": "Ce lien de signature a expiré."}), 410

    data = request.form
    flow = FLOW_CONFIG[mode]
    base_url = resolve_base_url()
    try:
        with db.session.no_autoflush:
            _apply_sign_form(mode, waiver, data, strict=False)
            ctx = build_document_render_context(mode, waiver)
            html_content = render_template(
                flow["template"],
                **ctx,
                base_url=base_url,
                form_preview=True,
                form_values={k: (v or "").strip() for k, v in data.items() if k != "csrf_token"},
            )
    except Exception as e:
        current_app.logger.error(f"Erreur d'aperçu {mode} ({waiver.waiver_id}) : {e}")
        return jsonify({"success": False, "error": "Aperçu indisponible."}), 500
    finally:
        # Aucune donnée de l'aperçu ne doit être persistée
        db.session.rollback()

    cache_key = hashlib.sha256(f"{mode}|{token}|".encode("utf-8") + html_content.encode("utf-8")).hexdigest()
    cached_pdf = _preview_cache_get(cache_key)
    if cached_pdf is not None:
        return _preview_pdf_response(cached_pdf, waiver.waiver_id, "hit")

    # Plafond de rendus simultanés : protège le reste du site (admin, pages publiques)
    if not _preview_render_slots.acquire(timeout=_PREVIEW_ACQUIRE_TIMEOUT_S):
        busy = jsonify({"success": False, "error": "Aperçu momentanément indisponible, nouvel essai en cours."})
        busy.status_code = 429
        busy.headers["Retry-After"] = str(_PREVIEW_RETRY_AFTER_S)
        return busy
    try:
        pdf_bytes = render_pdf_from_template(
            html_content,
            base_url=base_url,
            stylesheets=flow["stylesheets"],
            compress=False,
            filename=f"{waiver.waiver_id}_apercu.pdf",
        )
    except Exception as e:
        current_app.logger.error(f"Erreur de compilation de l'aperçu {mode} : {e}")
        return jsonify({"success": False, "error": "Aperçu indisponible."}), 500
    finally:
        _preview_render_slots.release()

    _preview_cache_set(cache_key, pdf_bytes)
    return _preview_pdf_response(pdf_bytes, waiver.waiver_id, "miss")


def _handle_sign_waiver(mode, token):
    config = _get_waiver_route_config(mode)

    # Limitation de la taille de requête (16 Mo) pour prévenir les attaques DoS (Point 6)
    if request.method == "POST":
        if request.content_length and request.content_length > 16 * 1024 * 1024:
            return jsonify({"success": False, "error": "Le volume des données soumises dépasse la limite autorisée (16 Mo)."}), 413

    # 1. Valider le jeton
    if request.method == "POST":
        token_rec = config["token_model"].query.filter_by(
            token=token).with_for_update().first()
    else:
        token_rec = config["token_model"].query.filter_by(
            token=token).first()

    if not token_rec:
        if request.method == "GET":
            return render_template(config["template_sign"], waiver={"status": "invalid"})
        return jsonify({"success": False, "error": "Jeton invalide."}), 404

    # 2. Récupérer le contrat ou la décharge
    if request.method == "POST":
        waiver = config["model"].query.filter_by(
            waiver_id=token_rec.waiver_id).with_for_update().first()
    else:
        waiver = config["model"].query.filter_by(
            waiver_id=token_rec.waiver_id).first()

    if not waiver:
        abort(404)

    # 3. Si le document a déjà été signé ou le jeton déjà consommé, afficher la vue confirmée en GET et bloquer en POST
    if waiver.status in ['signed', 'completed'] or token_rec.signature:
        if request.method == "GET":
            return render_template(config["template_sign"], waiver=waiver)
        return jsonify({"success": False, "error": "Ce document a déjà été signé."}), 400

    # Vérification d'un verrou concurrent en cours de traitement ('signing') (Point 5)
    if waiver.status == "signing":
        signing_started_at = (waiver.sign_data or {}
                              ).get("signing_started_at")
        is_stale = False
        if signing_started_at:
            try:
                started_dt = datetime.fromisoformat(signing_started_at)
                if started_dt.tzinfo is None:
                    started_dt = started_dt.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - started_dt).total_seconds() > 600:
                    is_stale = True
            except Exception:
                is_stale = True
        else:
            is_stale = True

        if is_stale:
            waiver.status = "to_sign"
            if request.method == "POST":
                db.session.commit()
        else:
            if request.method == "GET":
                return render_template(config["template_sign"], waiver=waiver)
            return jsonify({
                "success": False,
                "error": "Une signature est déjà en cours de traitement. Veuillez patienter quelques instants."
            }), 409

    # 4. Vérifier l'expiration (24h) uniquement si le document n'est pas encore signé
    if token_rec.expires_at:
        exp = token_rec.expires_at
        now_utc = datetime.now(timezone.utc)
        is_expired = exp < (
            now_utc if exp.tzinfo is not None else now_utc.replace(tzinfo=None))
        if is_expired:
            if request.method == "GET":
                return render_template(config["template_sign"], waiver={"status": "expired"})
            return jsonify({"success": False, "error": "Ce lien de signature a expiré."}), 400

    signer_ip = get_client_ip()
    user_agent = request.headers.get("User-Agent", "")[:255]

    if request.method == "GET":
        extra_ctx = {}
        if mode == "safety_rules":
            tech_names = getattr(waiver, "display_safety_technicians", getattr(
                waiver, "safety_technicians", "")) or ""
            extra_ctx["general_rules"] = get_merged_general_safety_rules(
                tech_names)
            extra_ctx["vehicle_rules"] = get_safety_rules_for_vehicles(
                waiver.vehicles_details)
            from services.admin.safety_rules_config import get_safety_equipment_for_vehicles
            extra_ctx["safety_equipment"] = get_safety_equipment_for_vehicles(
                waiver.vehicles_details)
            extra_ctx["helmets"] = waiver.helmets_inventory or DEFAULT_HELMETS_INVENTORY
        elif mode == "risk_assessment":
            from services.admin.risk_assessment_config import (
                get_general_risk_assessment,
                get_risk_assessment_for_vehicles,
            )
            extra_ctx["general_risks"] = get_general_risk_assessment()
            extra_ctx["vehicle_sections"] = get_risk_assessment_for_vehicles(
                waiver.vehicles_details
            )
        from services.common.signatures import log_signature_event
        log_signature_event(
            waiver.waiver_id, mode, "link_opened", ip=signer_ip, user_agent=user_agent)
        try:
            db.session.commit()
        except Exception as commit_err:
            current_app.logger.warning(
                f"⚠️ Erreur lors de l'enregistrement de link_opened pour {waiver.waiver_id}: {commit_err}")
            db.session.rollback()
        return render_template(config["template_sign"], waiver=waiver, **extra_ctx)

    # Pose du verrou pessimiste 'signing' avant finalisation
    waiver.status = "signing"
    s_data_lock = dict(waiver.sign_data or {})
    s_data_lock["signing_started_at"] = datetime.now(
        timezone.utc).isoformat()
    waiver.sign_data = s_data_lock
    db.session.commit()

    def _fail(msg, status_code=400):
        try:
            waiver.status = "to_sign"
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({"success": False, "error": msg}), status_code

    try:
        data = request.get_json(silent=True) or request.form
        output_base = current_app.config.get(
            "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

        signature_raw = data.get("signature_data") or data.get("signature")
        if not signature_raw or not str(signature_raw).strip():
            return _fail("Le tracé manuscrit de la signature est obligatoire.")

        # Contrôle de la présence des lieux de tournage sur la fiche projet
        if not getattr(waiver, "has_shooting_locations", False):
            return _fail("Impossible de signer ce document : aucun lieu de tournage n'a été renseigné sur la fiche projet. Veuillez contacter l'administrateur afin qu'il complète les lieux sur le projet.")

        try:
            rep_name, rep_role = _apply_sign_form(
                mode, waiver, data, strict=True, user_agent=user_agent, output_base=output_base)
        except SignFormError as form_err:
            return _fail(str(form_err))

        waiver.signer_ip = signer_ip
        db.session.commit()

        from services.common.signatures import finalize_signed_document, log_signature_event
        if mode == "safety_rules":
            consent_payload = {
                "ack_rules": True,
                "signer_name": rep_name,
                "signer_role": waiver.signer_role,
            }
        elif mode == "pilot_waiver":
            consent_payload = {
                "ack_pilot_engagement": True,
                "signer_name": rep_name,
                "signer_role": waiver.signer_role,
            }
        elif mode == "risk_assessment":
            consent_payload = {
                "ack_risk_assessment": True,
                "signer_name": rep_name,
                "signer_role": waiver.signer_role,
            }
        else:
            consent_payload = {
                "accepted_terms": True,
                "has_signing_authority": True,
                "signer_name": rep_name,
                "representative_role": rep_role,
                "cgl_version": CGL_VERSION,
            }

        log_signature_event(
            waiver.waiver_id,
            mode,
            "consent_recorded",
            consent_payload,
            ip=signer_ip,
            user_agent=user_agent,
            raise_on_failure=True,
        )

        finalize_signed_document(
            mode,
            waiver.id,
            signature_raw,
            signer_ip,
            user_agent=user_agent,
            token_entry=token_rec,
        )

        return jsonify({
            "success": True,
            "document_id": waiver.waiver_id,
        })

    except ValueError as val_err:
        db.session.rollback()
        try:
            waiver_to_reset = config["model"].query.filter_by(
                waiver_id=token_rec.waiver_id).first()
            if waiver_to_reset and waiver_to_reset.status == "signing":
                waiver_to_reset.status = "to_sign"
                db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({"success": False, "error": str(val_err)}), 400
    except Exception as e:
        db.session.rollback()
        try:
            waiver_to_reset = config["model"].query.filter_by(
                waiver_id=token_rec.waiver_id).first()
            if waiver_to_reset and waiver_to_reset.status == "signing":
                waiver_to_reset.status = "to_sign"
                db.session.commit()
        except Exception:
            db.session.rollback()
        current_app.logger.error(
            f"Error processing {mode} waiver sign: {e}")
        return jsonify({"success": False, "error": "Une erreur serveur est survenue."}), 500

# ── Routes de Vérification ───────────────────────────────────

@public_waivers_bp.route("/safety-rules/verify/<string:waiver_id>", methods=["GET", "POST"])
@public_waivers_bp.route("/verify/safety-rules/<string:waiver_id>", methods=["GET", "POST"])
@limiter.limit("20 per minute")
@csrf.exempt
def verify_safety_rules(waiver_id):
    config = _get_waiver_route_config("safety_rules")

    def get_seal_args(data, signed_doc):
        return [waiver_id,
                data.get("_seal_signer_name", ""),
                data.get("_seal_signer_role", ""),
                signed_doc.signature,
                data.get("_seal_signed_at", "")]

    config["get_seal_args"] = get_seal_args
    return handle_document_verify(config, waiver_id)

@public_waivers_bp.route("/pilot-attestation/verify/<string:waiver_id>", methods=["GET", "POST"])
@public_waivers_bp.route("/verify/pilot-attestation/<string:waiver_id>", methods=["GET", "POST"])
@limiter.limit("20 per minute")
@csrf.exempt
def verify_pilot_waiver(waiver_id):
    config = _get_waiver_route_config("pilot_waiver")

    def get_seal_args(data, signed_doc):
        return [waiver_id,
                data.get("_seal_signer_name", ""),
                data.get("_seal_signer_role", ""),
                signed_doc.signature,
                data.get("_seal_signed_at", "")]

    config["get_seal_args"] = get_seal_args
    return handle_document_verify(config, waiver_id)

@public_waivers_bp.route("/cgl/verify/<string:waiver_id>", methods=["GET", "POST"])
@public_waivers_bp.route("/verify/cgl/<string:waiver_id>", methods=["GET", "POST"])
@limiter.limit("20 per minute")
@csrf.exempt
def verify_cgl(waiver_id):
    config = _get_waiver_route_config("cgl")

    def get_seal_args(data, signed_doc):
        return [waiver_id,
                data.get("_seal_production_name", ""),
                data.get("_seal_representative", ""),
                signed_doc.signature,
                data.get("_seal_signed_at", "")]

    config["get_seal_args"] = get_seal_args
    return handle_document_verify(config, waiver_id)

@public_waivers_bp.route("/risk-assessment/verify/<string:waiver_id>", methods=["GET", "POST"])
@public_waivers_bp.route("/verify/risk-assessment/<string:waiver_id>", methods=["GET", "POST"])
@limiter.limit("20 per minute")
@csrf.exempt
def verify_risk_assessment(waiver_id):
    config = _get_waiver_route_config("risk_assessment")

    def get_seal_args(data, signed_doc):
        return [waiver_id,
                data.get("_seal_signer_name", ""),
                data.get("_seal_signer_role", ""),
                signed_doc.signature,
                data.get("_seal_signed_at", "")]

    config["get_seal_args"] = get_seal_args
    return handle_document_verify(config, waiver_id)

# ── Routes de Téléchargement ─────────────────────────────────

@public_waivers_bp.route("/cgl/document/<path:filepath>")
@public_waivers_bp.route("/safety-rules/document/<path:filepath>")
@public_waivers_bp.route("/pilot-attestation/document/<path:filepath>")
@public_waivers_bp.route("/risk-assessment/document/<path:filepath>")
@public_waivers_bp.route("/cgl/attachment/<path:filepath>")
@csrf.exempt
def download_waiver_secured_file(filepath):
    is_attachment = request.path.startswith("/cgl/attachment/")
    return handle_document_download(filepath, as_attachment=True if is_attachment else None)


def init_waiver_routes(app):
    """Initialise les routes publiques pour les décharges (CGL, Règles de sécurité, Attestations pilotes)."""
    if "public_waivers" not in app.blueprints:
        app.register_blueprint(public_waivers_bp)
