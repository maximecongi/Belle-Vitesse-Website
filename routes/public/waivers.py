import os
from datetime import datetime

from flask import abort, current_app, jsonify, render_template, request
from werkzeug.utils import secure_filename

from extensions import csrf
from models import (
    PilotWaiver,
    PilotWaiverSignedDocument,
    PilotWaiverToken,
    ProductionWaiver,
    ProductionWaiverSignedDocument,
    ProductionWaiverToken,
    db,
)
from routes.public.shared_docs import handle_document_download, handle_document_verify
from utils.storage import (
    ensure_dir,
    get_pilot_attachments_path,
    get_production_attachments_path,
)

# ── Shared Helpers ──────────────────────────────────────────────


def _get_waiver_route_config(mode):
    if mode == "pilot":
        return {
            "model": PilotWaiver,
            "signed_model": PilotWaiverSignedDocument,
            "token_model": PilotWaiverToken,
            "template_sign": "public/waivers/sign_pilot_waiver.html",
            "template_verify": "public/waivers/pilot_waiver_verify.html",
            "route_base": "pilot-waiver",
            "seal_prefix": "WAIVER"
        }
    return {
        "model": ProductionWaiver,
        "signed_model": ProductionWaiverSignedDocument,
        "token_model": ProductionWaiverToken,
        "template_sign": "public/waivers/sign_production_waiver.html",
        "template_verify": "public/waivers/production_waiver_verify.html",
        "route_base": "production-waiver",
        "seal_prefix": "WAIVER_PROD"
    }


def init_waiver_routes(app):

    # ── Signing Routes ──────────────────────────────────────────

    @app.route("/sign/waiver/<token>", methods=["GET", "POST"])
    def sign_pilot_waiver(token):
        return _handle_sign_waiver("pilot", token)

    @app.route("/sign/production-waiver/<token>", methods=["GET", "POST"])
    def sign_production_waiver(token):
        return _handle_sign_waiver("production", token)

    def _handle_sign_waiver(mode, token):
        config = _get_waiver_route_config(mode)

        # 1. Validate Token
        token_rec = config["token_model"].query.filter_by(token=token).first()
        if not token_rec:
            if request.method == "GET":
                return render_template(config["template_sign"], waiver={"status": "invalid"})
            return jsonify({"success": False, "error": "Token invalide."})

        # 2. Check Expiration (24h)
        if token_rec.expires_at and token_rec.expires_at < datetime.utcnow():
            if request.method == "GET":
                return render_template(config["template_sign"], waiver={"status": "expired"})
            return jsonify({"success": False, "error": "Ce lien de signature a expiré."})

        # 3. Get Waiver
        waiver = config["model"].query.filter_by(
            waiver_id=token_rec.waiver_id).first()
        if not waiver:
            abort(404)

        if request.method == "GET":
            return render_template(config["template_sign"], waiver=waiver)

        if waiver.status == 'signed':
            return jsonify({"success": False, "error": "Cette décharge a déjà été signée."})

        try:
            data = request.form
            output_base = current_app.config.get(
                "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

            if mode == "pilot":
                waiver.pilot_first_name = data.get("first_name")
                waiver.pilot_last_name = data.get("last_name")
                waiver.pilot_dob = data.get("dob")
                waiver.pilot_license_number = data.get("license_number")
                waiver.pilot_address = data.get("address")
                waiver.pilot_insurance_company = data.get("insurance_company")
                waiver.pilot_insurance_policy = data.get("insurance_policy")

                # Attachments Pilot
                for field, doc_type, attr in [('pilot_license', 'license', 'pilot_license_path'),
                                              ('pilot_insurance', 'insurance',
                                               'pilot_insurance_path'),
                                              ('pilot_identity', 'identity', 'pilot_identity_path')]:
                    file = request.files.get(field)
                    if file and file.filename:
                        upload_dir = ensure_dir(
                            get_pilot_attachments_path(waiver.project, doc_type))
                        fname = f"{field}_{int(datetime.now().timestamp())}_{secure_filename(file.filename)}"
                        file_path = os.path.join(upload_dir, fname)
                        file.save(file_path)
                        setattr(waiver, attr, os.path.relpath(
                            file_path, output_base))
            else:
                waiver.production_name = data.get("production_name")
                waiver.production_representative = data.get("representative")
                waiver.production_address = data.get("address")
                waiver.production_siret = data.get("siret")
                waiver.production_vat = data.get("vat_number")
                waiver.production_insurance_company = data.get(
                    "insurance_company")
                waiver.production_insurance_policy = data.get(
                    "insurance_policy")
                waiver.production_insurance_validity = data.get(
                    "insurance_validity")
                waiver.location_of_use = data.get("location_of_use")

                # Attachment Production
                file = request.files.get('production_insurance')
                if file and file.filename:
                    upload_dir = ensure_dir(
                        get_production_attachments_path(waiver.project, 'insurance'))
                    fname = f"prod_insurance_{int(datetime.now().timestamp())}_{secure_filename(file.filename)}"
                    file_path = os.path.join(upload_dir, fname)
                    file.save(file_path)
                    waiver.production_insurance_path = os.path.relpath(
                        file_path, output_base)

            waiver.signature_data = data.get("signature_data")
            signer_ip = request.headers.get(
                'X-Forwarded-For', request.remote_addr)
            if signer_ip and ',' in signer_ip:
                signer_ip = signer_ip.split(',')[0].strip()
            waiver.signer_ip = signer_ip

            db.session.commit()

            from services.common.signatures import finalize_signed_document
            finalize_signed_document(mode, waiver.id, waiver.signature_data, signer_ip)

            # We don't delete the token immediately to allow the user
            # to see the "signed" state if they reload the page.
            # Token will expire naturally after 24h.
            # db.session.delete(token_rec)
            # db.session.commit()

            return jsonify({"success": True})

        except Exception as e:
            current_app.logger.error(
                f"Error processing {mode} waiver sign: {e}")
            return jsonify({"success": False, "error": "Une erreur serveur est survenue."}), 500

    # ── Verification Routes ──────────────────────────────────────

    @app.route("/verify/waiver/<string:waiver_id>", methods=["GET", "POST"])
    @csrf.exempt
    def verify_pilot_waiver(waiver_id):
        config = _get_waiver_route_config("pilot")

        def get_seal_args(data, signed_doc):
            return [waiver_id,
                    data.get("_seal_pilot_name", ""),
                    data.get("_seal_license", ""),
                    signed_doc.signature,
                    data.get("_seal_signed_at", "")]

        config["get_seal_args"] = get_seal_args
        return handle_document_verify(config, waiver_id)

    @app.route("/verify/production-waiver/<string:waiver_id>", methods=["GET", "POST"])
    @csrf.exempt
    def verify_production_waiver(waiver_id):
        config = _get_waiver_route_config("production")

        def get_seal_args(data, signed_doc):
            return [waiver_id,
                    data.get("_seal_production_name", ""),
                    data.get("_seal_representative", ""),
                    signed_doc.signature,
                    data.get("_seal_signed_at", "")]

        config["get_seal_args"] = get_seal_args
        return handle_document_verify(config, waiver_id)

    # ── Download Routes ──────────────────────────────────────────

    @app.route("/pilot-waiver/document/<path:filepath>")
    @app.route("/production-waiver/document/<path:filepath>")
    @app.route("/pilot-waiver/attachment/<path:filepath>")
    @app.route("/production-waiver/attachment/<path:filepath>")
    @csrf.exempt
    def download_waiver_secured_file(filepath):
        return handle_document_download(filepath)
