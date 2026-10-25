import hashlib
import os
from datetime import datetime, timezone

from flask import abort, current_app, jsonify, render_template, request
from werkzeug.utils import secure_filename

from extensions import csrf
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
    DEFAULT_HELMETS_INVENTORY,
)
from utils.request_utils import get_client_ip
from utils.storage import ensure_dir, get_cgl_attachments_path
from utils.image_utils import optimize_and_save_image, IMAGE_EXTENSIONS


def _get_waiver_route_config(mode):
    if mode == "safety_rules":
        return {
            "model": SafetyRulesWaiver,
            "signed_model": WaiverSignedDocument,
            "token_model": WaiverToken,
            "template_sign": "public/waivers/sign_safety_rules.html",
            "template_verify": "public/waivers/safety_rules_verify.html",
            "route_base": "safety-rules",
            "seal_prefix": "BVSR",
        }
    return {
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
    def sign_cgl(token):
        return _handle_sign_waiver("cgl", token)

    @app.route("/sign/safety-rules/<token>", methods=["GET", "POST"])
    def sign_safety_rules(token):
        return _handle_sign_waiver("safety_rules", token)

    def _handle_sign_waiver(mode, token):
        config = _get_waiver_route_config(mode)

        # 1. Valider le jeton
        token_rec = config["token_model"].query.filter_by(token=token).first()
        if not token_rec:
            if request.method == "GET":
                return render_template(config["template_sign"], waiver={"status": "invalid"})
            return jsonify({"success": False, "error": "Jeton invalide."}), 404

        # 2. Récupérer le contrat ou la décharge
        waiver = config["model"].query.filter_by(waiver_id=token_rec.waiver_id).first()
        if not waiver:
            abort(404)

        # 3. Si le document a déjà été signé ou le jeton déjà consommé, afficher la vue confirmée en GET et bloquer en POST
        if waiver.status in ['signed', 'completed'] or token_rec.signature:
            if request.method == "GET":
                return render_template(config["template_sign"], waiver=waiver)
            return jsonify({"success": False, "error": "Ce document a déjà été signé."}), 400

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
                extra_ctx["vehicle_rules"] = get_safety_rules_for_vehicles(waiver.vehicles_details)
                extra_ctx["helmets"] = waiver.helmets_inventory or DEFAULT_HELMETS_INVENTORY
            from services.common.signatures import log_signature_event
            log_signature_event(waiver.waiver_id, mode, "link_opened", ip=signer_ip, user_agent=user_agent)
            return render_template(config["template_sign"], waiver=waiver, **extra_ctx)

        if waiver.status in ['signed', 'completed']:
            return jsonify({"success": False, "error": "Ce document a déjà été signé."}), 400

        try:
            data = request.form
            output_base = current_app.config.get(
                "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

            signature_raw = data.get("signature_data") or data.get("signature")
            if not signature_raw or not str(signature_raw).strip():
                return jsonify({"success": False, "error": "Le tracé manuscrit de la signature est obligatoire."}), 400

            if mode == "safety_rules":
                if data.get("first_name"):
                    waiver.signer_first_name = data.get("first_name").strip()
                if data.get("last_name"):
                    waiver.signer_last_name = data.get("last_name").strip()
                if data.get("email"):
                    waiver.signer_email = data.get("email").strip()
                if data.get("phone"):
                    waiver.signer_phone = data.get("phone").strip()
                if data.get("company"):
                    waiver.signer_company = data.get("company").strip()
                if data.get("signer_role"):
                    waiver.signer_role = data.get("signer_role").strip()
                if data.get("role_custom"):
                    waiver.signer_role_custom = data.get("role_custom").strip()
                rep_name = f"{waiver.signer_first_name} {waiver.signer_last_name}".strip()
            else:
                # Validation stricte du consentement et de la déclaration de pouvoir pour les CGL
                if data.get("accepted_terms") != "1":
                    return jsonify({
                        "success": False,
                        "error": "L'acceptation expresse des Conditions Générales de Location est obligatoire."
                    }), 400

                if data.get("has_signing_authority") != "1":
                    return jsonify({
                        "success": False,
                        "error": "La déclaration sur l'honneur de pouvoir d'engager la société est obligatoire."
                    }), 400

                rep_name = (data.get("representative") or "").strip()
                rep_role = (data.get("representative_role") or "").strip()
                if not rep_name or not rep_role:
                    return jsonify({
                        "success": False,
                        "error": "Le nom du signataire et sa fonction au sein de la société sont obligatoires."
                    }), 400

                waiver.production_name = data.get("production_name")
                waiver.production_representative = rep_name
                waiver.production_address = data.get("address")
                waiver.production_siret = data.get("siret")
                waiver.production_vat = data.get("vat_number")
                if data.get("phone"):
                    waiver.signer_phone = data.get("phone").strip()
                if data.get("email"):
                    waiver.signer_email = data.get("email").strip()
                waiver.signer_role_custom = rep_role
                if data.get("insurance_company"):
                    waiver.production_insurance_company = data.get("insurance_company").strip()
                if data.get("insurance_policy"):
                    waiver.production_insurance_policy = data.get("insurance_policy").strip()
                if data.get("location_of_use"):
                    waiver.location_of_use = data.get("location_of_use").strip()
                elif data.get("city") and not waiver.location_of_use:
                    waiver.location_of_use = data.get("city").strip()

                # Calcul de l'empreinte du template des CGL (termes acceptés)
                terms_fingerprint = ""
                try:
                    template_source, _, _ = current_app.jinja_env.loader.get_source(
                        current_app.jinja_env, config["template_sign"])
                    terms_fingerprint = hashlib.sha256(template_source.encode("utf-8")).hexdigest()
                except Exception:
                    pass

                # Snapshot structuré JSON
                s_data = dict(waiver.sign_data or {})
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
                file = request.files.get('production_insurance')
                if file and file.filename:
                    ext = os.path.splitext(file.filename)[1].lower()
                    allowed_exts = {'.pdf', '.png', '.jpg', '.jpeg', '.heic', '.heif'}
                    if ext not in allowed_exts:
                        return jsonify({
                            "success": False,
                            "error": "Format d'attestation d'assurance non autorisé (PDF ou image requis)."
                        }), 400

                    file_bytes = file.read()
                    if len(file_bytes) > 10 * 1024 * 1024:
                        return jsonify({
                            "success": False,
                            "error": "L'attestation d'assurance dépasse la taille maximale autorisée (10 Mo)."
                        }), 400

                    insurance_file_sha256 = hashlib.sha256(file_bytes).hexdigest()
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

                s_data["insurance_file_sha256"] = insurance_file_sha256
                waiver.sign_data = s_data

            waiver.signer_ip = signer_ip
            db.session.commit()

            from services.common.signatures import finalize_signed_document, log_signature_event
            log_signature_event(
                waiver.waiver_id,
                mode,
                "consent_recorded",
                {
                    "accepted_terms": True,
                    "has_signing_authority": True if mode == "cgl" else None,
                    "signer_name": rep_name,
                },
                ip=signer_ip,
                user_agent=user_agent
            )

            result = finalize_signed_document(mode, waiver.id, signature_raw, signer_ip)

            # Consommation du jeton à usage unique (marqué comme signé, conservé pour l'affichage de confirmation)
            try:
                token_rec.signature = result.get("hash") or "signed"
                db.session.commit()
            except Exception as token_err:
                current_app.logger.warning(f"⚠️ Erreur lors de la mise à jour du jeton {token}: {token_err}")

            return jsonify({
                "success": True,
                "document_id": waiver.waiver_id,
            })

        except ValueError as val_err:
            db.session.rollback()
            return jsonify({"success": False, "error": str(val_err)}), 400
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error processing {mode} waiver sign: {e}")
            return jsonify({"success": False, "error": "Une erreur serveur est survenue."}), 500

    # ── Routes de Vérification ───────────────────────────────────

    @app.route("/safety-rules/verify/<string:waiver_id>", methods=["GET", "POST"])
    @app.route("/verify/safety-rules/<string:waiver_id>", methods=["GET", "POST"])
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
        return handle_document_download(filepath)
