import hashlib
import os
from datetime import datetime, timezone

from flask import abort, current_app, jsonify, render_template, request
from werkzeug.utils import secure_filename

from extensions import csrf, limiter
from models import (
    CglWaiver,
    SafetyRulesWaiver,
    WaiverToken,
    WaiverSignedDocument,
    db,
)
from routes.public.shared_docs import handle_document_download, handle_document_verify
from services.admin.safety_rules_config import (
    get_safety_rules_for_vehicles,
    get_general_safety_rules,
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
    return {
        "mode": "cgl",
        "model": CglWaiver,
        "signed_model": WaiverSignedDocument,
        "token_model": WaiverToken,
        "template_sign": "public/cgl/sign_cgl.html",
        "template_verify": "public/cgl/cgl_verify.html",
        "route_base": "cgl",
        "seal_prefix": "BVRA",
    }


def init_waiver_routes(app):

    # ── Routes de Signature ──────────────────────────────────────

    @app.route("/sign/cgl/<token>", methods=["GET", "POST"])
    @limiter.limit("20 per minute")
    def sign_cgl(token):
        return _handle_sign_waiver("cgl", token)

    @app.route("/sign/safety-rules/<token>", methods=["GET", "POST"])
    @limiter.limit("20 per minute")
    def sign_safety_rules(token):
        return _handle_sign_waiver("safety_rules", token)

    def _handle_sign_waiver(mode, token):
        config = _get_waiver_route_config(mode)

        # Limitation de la taille de requête (16 Mo) pour prévenir les attaques DoS (Point 6)
        if request.method == "POST":
            if request.content_length and request.content_length > 16 * 1024 * 1024:
                return jsonify({"success": False, "error": "Le volume des données soumises dépasse la limite autorisée (16 Mo)."}), 413

        # 1. Valider le jeton
        if request.method == "POST":
            token_rec = config["token_model"].query.filter_by(token=token).with_for_update().first()
        else:
            token_rec = config["token_model"].query.filter_by(token=token).first()

        if not token_rec:
            if request.method == "GET":
                return render_template(config["template_sign"], waiver={"status": "invalid"})
            return jsonify({"success": False, "error": "Jeton invalide."}), 404

        # 2. Récupérer le contrat ou la décharge
        if request.method == "POST":
            waiver = config["model"].query.filter_by(waiver_id=token_rec.waiver_id).with_for_update().first()
        else:
            waiver = config["model"].query.filter_by(waiver_id=token_rec.waiver_id).first()

        if not waiver:
            abort(404)

        # 3. Si le document a déjà été signé ou le jeton déjà consommé, afficher la vue confirmée en GET et bloquer en POST
        if waiver.status in ['signed', 'completed'] or token_rec.signature:
            if request.method == "GET":
                return render_template(config["template_sign"], waiver=waiver)
            return jsonify({"success": False, "error": "Ce document a déjà été signé."}), 400

        # Vérification d'un verrou concurrent en cours de traitement ('signing') (Point 5)
        if waiver.status == "signing":
            signing_started_at = (waiver.sign_data or {}).get("signing_started_at")
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
            is_expired = exp < (now_utc if exp.tzinfo is not None else now_utc.replace(tzinfo=None))
            if is_expired:
                if request.method == "GET":
                    return render_template(config["template_sign"], waiver={"status": "expired"})
                return jsonify({"success": False, "error": "Ce lien de signature a expiré."}), 400

        signer_ip = get_client_ip()
        user_agent = request.headers.get("User-Agent", "")[:255]

        if request.method == "GET":
            extra_ctx = {}
            if mode == "safety_rules":
                tech_names = getattr(waiver, "display_safety_technicians", getattr(waiver, "safety_technicians", "")) or ""
                extra_ctx["general_rules"] = get_merged_general_safety_rules(tech_names)
                extra_ctx["vehicle_rules"] = get_safety_rules_for_vehicles(waiver.vehicles_details)
                extra_ctx["helmets"] = waiver.helmets_inventory or DEFAULT_HELMETS_INVENTORY
            from services.common.signatures import log_signature_event
            log_signature_event(waiver.waiver_id, mode, "link_opened", ip=signer_ip, user_agent=user_agent)
            try:
                db.session.commit()
            except Exception as commit_err:
                current_app.logger.warning(f"⚠️ Erreur lors de l'enregistrement de link_opened pour {waiver.waiver_id}: {commit_err}")
                db.session.rollback()
            return render_template(config["template_sign"], waiver=waiver, **extra_ctx)

        # Pose du verrou pessimiste 'signing' avant finalisation
        waiver.status = "signing"
        s_data_lock = dict(waiver.sign_data or {})
        s_data_lock["signing_started_at"] = datetime.now(timezone.utc).isoformat()
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
            data = request.form
            output_base = current_app.config.get(
                "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

            signature_raw = data.get("signature_data") or data.get("signature")
            if not signature_raw or not str(signature_raw).strip():
                return _fail("Le tracé manuscrit de la signature est obligatoire.")

            if mode == "safety_rules":
                if data.get("ack_rules") not in ("1", "on", "true"):
                    return _fail("La prise de connaissance et le respect des Règles de Sécurité Universelles (BVSR) sont obligatoires.")

                if data.get("first_name"):
                    fn = data.get("first_name").strip()
                    if len(fn) > 100:
                        return _fail("Le prénom ne peut dépasser 100 caractères.")
                    waiver.signer_first_name = fn
                if data.get("last_name"):
                    ln = data.get("last_name").strip()
                    if len(ln) > 100:
                        return _fail("Le nom ne peut dépasser 100 caractères.")
                    waiver.signer_last_name = ln
                if data.get("email"):
                    em = data.get("email").strip()
                    import re
                    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", em) or len(em) > 120:
                        return _fail("L'adresse e-mail renseignée est invalide.")
                    waiver.signer_email = em
                if data.get("phone"):
                    ph = data.get("phone").strip()
                    if len(ph) > 50:
                        return _fail("Le numéro de téléphone ne peut dépasser 50 caractères.")
                    waiver.signer_phone = ph
                if data.get("company"):
                    co = data.get("company").strip()
                    if len(co) > 150:
                        return _fail("La société ne peut dépasser 150 caractères.")
                    waiver.signer_company = co
                if data.get("signer_role"):
                    ro = data.get("signer_role").strip()
                    if len(ro) > 100:
                        return _fail("La fonction ne peut dépasser 100 caractères.")
                    waiver.signer_role = ro
                if data.get("role_custom"):
                    rc = data.get("role_custom").strip()
                    if len(rc) > 100:
                        return _fail("Le rôle personnalisé ne peut dépasser 100 caractères.")
                    waiver.signer_role_custom = rc
                rep_name = f"{waiver.signer_first_name or ''} {waiver.signer_last_name or ''}".strip()

                bvsr_sign_data = dict(waiver.sign_data or {})
                bvsr_sign_data["ack_rules"] = True
                bvsr_sign_data["accepted_at"] = datetime.now(timezone.utc).isoformat()
                waiver.sign_data = bvsr_sign_data
            else:
                # Validation stricte du consentement et de la déclaration de pouvoir pour les CGL
                if data.get("accepted_terms") != "1":
                    return _fail("L'acceptation expresse des Conditions Générales de Location est obligatoire.")

                if data.get("has_signing_authority") != "1":
                    return _fail("La déclaration sur l'honneur de pouvoir d'engager la société est obligatoire.")

                prod_name = (data.get("production_name") or waiver.production_name or "").strip()
                if not prod_name or len(prod_name) > 150:
                    return _fail("La raison sociale de la production est obligatoire (max 150 caractères).")

                rep_name = (data.get("representative") or waiver.production_representative or "").strip()
                rep_role = (data.get("representative_role") or waiver.signer_role_custom or "").strip()
                if not rep_name or not rep_role:
                    return _fail("Le nom du signataire et sa fonction au sein de la société sont obligatoires.")
                if len(rep_name) > 150:
                    return _fail("Le nom du signataire ne peut dépasser 150 caractères.")
                if len(rep_role) > 100:
                    return _fail("La fonction du signataire ne peut dépasser 100 caractères.")

                address = (data.get("address") or waiver.production_address or "").strip()
                if address and len(address) > 255:
                    return _fail("L'adresse du siège social ne peut dépasser 255 caractères.")

                email = (data.get("email") or waiver.signer_email or "").strip()
                if email:
                    import re
                    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) or len(email) > 120:
                        return _fail("L'adresse e-mail renseignée est invalide.")

                siret_value = data.get("siret") if "siret" in data else waiver.production_siret
                siret = (siret_value or "").strip()
                legal_country = (data.get("legal_country") or (waiver.sign_data or {}).get("legal_country") or "FR").strip().upper()
                if legal_country in ("FR", "FRANCE"):
                    if not siret:
                        return _fail("Le numéro SIRET est obligatoire pour une société dont le siège est en France.")
                    import re
                    siret_clean = re.sub(r"\s+", "", siret)
                    if not siret_clean.isdigit() or len(siret_clean) != 14:
                        return _fail("Le numéro SIRET doit comporter exactement 14 chiffres pour une société française.")
                    siret = siret_clean
                elif len(siret) > 100:
                    return _fail("Le numéro d’immatriculation ne peut dépasser 100 caractères.")

                waiver.production_name = prod_name
                waiver.production_representative = rep_name
                if address:
                    waiver.production_address = address
                waiver.production_siret = siret
                if data.get("vat_number"):
                    vat = data.get("vat_number").strip()
                    if len(vat) > 100:
                        return _fail("Le numéro de TVA intracommunautaire ne peut dépasser 100 caractères.")
                    waiver.production_vat = vat
                if data.get("phone"):
                    ph = data.get("phone").strip()
                    if len(ph) > 50:
                        return _fail("Le numéro de téléphone ne peut dépasser 50 caractères.")
                    waiver.signer_phone = ph
                if email:
                    waiver.signer_email = email
                waiver.signer_role_custom = rep_role
                if data.get("insurance_company"):
                    ic = data.get("insurance_company").strip()
                    if len(ic) > 255:
                        return _fail("Le nom de la compagnie d'assurance ne peut dépasser 255 caractères.")
                    waiver.production_insurance_company = ic
                if data.get("insurance_policy"):
                    ip = data.get("insurance_policy").strip()
                    if len(ip) > 255:
                        return _fail("Le numéro de police d'assurance ne peut dépasser 255 caractères.")
                    waiver.production_insurance_policy = ip
                if data.get("location_of_use"):
                    loc = data.get("location_of_use").strip()
                    if len(loc) > 255:
                        return _fail("Le lieu d'utilisation ne peut dépasser 255 caractères.")
                    waiver.location_of_use = loc
                elif data.get("city") and not waiver.location_of_use:
                    city = data.get("city").strip()
                    if len(city) > 255:
                        return _fail("La ville ne peut dépasser 255 caractères.")
                    waiver.location_of_use = city

                # Calcul de l'empreinte du partial des articles CGL (termes acceptés immuables)
                terms_fingerprint = ""
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
                s_data["accepted_at"] = datetime.now(timezone.utc).isoformat()
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
                if data.get("insurance_company"):
                    s_data["insurance_company"] = data.get("insurance_company").strip()
                if data.get("insurance_policy"):
                    s_data["insurance_policy"] = data.get("insurance_policy").strip()

                # Pièce jointe assurance production (CGL) avec validation stricte
                insurance_file_sha256 = ""
                insurance_upload_sha256 = ""
                file = request.files.get('production_insurance')
                if file and file.filename:
                    ext = os.path.splitext(file.filename)[1].lower()
                    allowed_exts = {'.pdf', '.png', '.jpg', '.jpeg', '.heic', '.heif'}
                    if ext not in allowed_exts:
                        return _fail("Format d'attestation d'assurance non autorisé (PDF ou image requis).")

                    file_bytes = file.read()
                    if len(file_bytes) > 10 * 1024 * 1024:
                        return _fail("L'attestation d'assurance dépasse la taille maximale autorisée (10 Mo).")

                    if not _is_valid_magic_bytes(file_bytes, ext):
                        return _fail("Le contenu du fichier téléversé ne correspond pas à une attestation valide (signature de fichier non reconnue).")

                    insurance_upload_sha256 = hashlib.sha256(file_bytes).hexdigest()
                    file.seek(0)

                    upload_dir = ensure_dir(
                        get_cgl_attachments_path(waiver.project, 'insurance'))
                    stem = os.path.splitext(secure_filename(file.filename))[0]
                    if ext in ('.heic', '.heif'):
                        ext = '.jpg'
                    fname = f"prod_insurance_{int(datetime.now().timestamp())}_{stem}{ext}"
                    file_path = os.path.join(upload_dir, fname)
                    if ext in IMAGE_EXTENSIONS or ext == '.jpg':
                        optimize_and_save_image(file, file_path)
                    else:
                        file.save(file_path)
                    waiver.production_insurance_path = os.path.relpath(
                        file_path, output_base)

                    # Point 10: Calcul du SHA-256 physique du fichier stocké post-optimisation
                    insurance_file_sha256 = compute_file_sha256(file_path)

                s_data["insurance_file_sha256"] = insurance_file_sha256
                s_data["insurance_upload_sha256"] = insurance_upload_sha256
                waiver.sign_data = s_data

            waiver.signer_ip = signer_ip
            db.session.commit()

            from services.common.signatures import finalize_signed_document, log_signature_event
            if mode == "safety_rules":
                consent_payload = {
                    "ack_rules": True,
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

            result = finalize_signed_document(
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
                waiver_to_reset = config["model"].query.filter_by(waiver_id=token_rec.waiver_id).first()
                if waiver_to_reset and waiver_to_reset.status == "signing":
                    waiver_to_reset.status = "to_sign"
                    db.session.commit()
            except Exception:
                db.session.rollback()
            return jsonify({"success": False, "error": str(val_err)}), 400
        except Exception as e:
            db.session.rollback()
            try:
                waiver_to_reset = config["model"].query.filter_by(waiver_id=token_rec.waiver_id).first()
                if waiver_to_reset and waiver_to_reset.status == "signing":
                    waiver_to_reset.status = "to_sign"
                    db.session.commit()
            except Exception:
                db.session.rollback()
            current_app.logger.error(f"Error processing {mode} waiver sign: {e}")
            return jsonify({"success": False, "error": "Une erreur serveur est survenue."}), 500

    # ── Routes de Vérification ───────────────────────────────────

    @app.route("/safety-rules/verify/<string:waiver_id>", methods=["GET", "POST"])
    @app.route("/verify/safety-rules/<string:waiver_id>", methods=["GET", "POST"])
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

    @app.route("/cgl/verify/<string:waiver_id>", methods=["GET", "POST"])
    @app.route("/verify/cgl/<string:waiver_id>", methods=["GET", "POST"])
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

    # ── Routes de Téléchargement ─────────────────────────────────

    @app.route("/cgl/document/<path:filepath>")
    @app.route("/safety-rules/document/<path:filepath>")
    @app.route("/cgl/attachment/<path:filepath>")
    @csrf.exempt
    def download_waiver_secured_file(filepath):
        is_attachment = request.path.startswith("/cgl/attachment/")
        return handle_document_download(filepath, as_attachment=True if is_attachment else None)

