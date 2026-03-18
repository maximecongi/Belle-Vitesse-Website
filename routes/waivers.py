import os
import secrets
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import render_template, request, jsonify, current_app, abort, send_from_directory

from models import (
    db,
    PilotWaiver,
    PilotWaiverSignedDocument,
    ProductionWaiver,
    ProductionWaiverSignedDocument,
    PilotWaiverToken,
    ProductionWaiverToken
)
from services.shared.waiver_signatures import process_waiver_signature
from utils.document_utils import (
    validate_pdf_access_token,
    generate_pdf_access_token,
    verify_hmac_seal,
    verify_pdf_hash
)
from utils.storage import (
    get_pilot_attachments_path,
    get_production_attachments_path,
    ensure_dir
)
from extensions import csrf

# ── Shared Helpers ──────────────────────────────────────────────


def _get_waiver_route_config(mode):
    if mode == "pilot":
        return {
            "model": PilotWaiver,
            "signed_model": PilotWaiverSignedDocument,
            "token_model": PilotWaiverToken,
            "template_sign": "waivers/sign_pilot_waiver.html",
            "template_verify": "waivers/pilot_waiver_verify.html",
            "route_base": "pilot-waiver",
            "seal_prefix": "WAIVER"
        }
    return {
        "model": ProductionWaiver,
        "signed_model": ProductionWaiverSignedDocument,
        "token_model": ProductionWaiverToken,
        "template_sign": "waivers/sign_production_waiver.html",
        "template_verify": "waivers/production_waiver_verify.html",
        "route_base": "production-waiver",
        "seal_prefix": "WAIVER_PROD"
    }


def _is_authorized(filepath):
    """Internal helper for document/attachment authorization."""
    token_header = request.headers.get("X-Check-Token")
    expected_header = os.getenv("CHECK_API_TOKEN")
    access_token = request.args.get("t", "")

    if expected_header and token_header and secrets.compare_digest(token_header, expected_header):
        return True
    return validate_pdf_access_token(filepath, access_token)


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
            process_waiver_signature(mode, waiver.id)
            return jsonify({"success": True})

        except Exception as e:
            current_app.logger.error(
                f"Error processing {mode} waiver sign: {e}")
            return jsonify({"success": False, "error": "Une erreur serveur est survenue."}), 500

    # ── Verification Routes ──────────────────────────────────────

    @app.route("/verify/waiver/<string:waiver_id>", methods=["GET", "POST"])
    @csrf.exempt
    def verify_pilot_waiver(waiver_id):
        return _handle_verify_waiver("pilot", waiver_id)

    @app.route("/verify/production-waiver/<string:waiver_id>", methods=["GET", "POST"])
    @csrf.exempt
    def verify_production_waiver(waiver_id):
        return _handle_verify_waiver("production", waiver_id)

    def _handle_verify_waiver(mode, waiver_id):
        config = _get_waiver_route_config(mode)
        signed_doc = config["signed_model"].query.filter_by(
            waiver_id=waiver_id).first()
        if not signed_doc:
            abort(404)

        data = signed_doc.data_snapshot
        if 'signed_at' in data and isinstance(data['signed_at'], str):
            try:
                data['signed_at'] = datetime.fromisoformat(data['signed_at'])
            except:
                pass

        # 1. Verify Seal
        seal_args = []
        if mode == "pilot":
            seal_args = [data.get("_seal_pilot_name", ""),
                         data.get("_seal_license", "")]
        else:
            seal_args = [data.get("_seal_production_name", ""), data.get(
                "_seal_representative", "")]
        seal_args += [signed_doc.signature, data.get("_seal_signed_at", "")]

        seal_valid = verify_hmac_seal(
            signed_doc.hash, config["seal_prefix"], waiver_id, *seal_args)

        pdf_valid = None
        pdf_error = None
        if request.method == "POST":
            uploaded_file = request.files.get("pdf")
            if uploaded_file:
                if not uploaded_file.filename.lower().endswith(".pdf"):
                    pdf_error = "Le fichier doit être un PDF."
                elif not signed_doc.pdf_file_hash:
                    pdf_error = "Pas d'empreinte enregistrée."
                else:
                    pdf_valid = verify_pdf_hash(
                        uploaded_file.read(), signed_doc.pdf_file_hash)

        # 2. PDF URL with token
        pdf_download_url = None
        if signed_doc.pdf_url:
            path_part = signed_doc.pdf_url.split(
                "/document/")[-1].split("?")[0]
            token = generate_pdf_access_token(path_part)
            pdf_download_url = f"/{config['route_base']}/document/{path_part}?t={token}"

        return render_template(
            config["template_verify"],
            data=data,
            seal_valid=seal_valid,
            pdf_valid=pdf_valid,
            pdf_error=pdf_error,
            inspection_id=signed_doc.waiver_id,
            document_hash=signed_doc.hash,
            project_name=data.get('project_name'),
            has_pdf_hash=bool(signed_doc.pdf_file_hash),
            pdf_download_url=pdf_download_url
        )

    # ── Download Routes ──────────────────────────────────────────

    @app.route("/pilot-waiver/document/<path:filepath>")
    @app.route("/production-waiver/document/<path:filepath>")
    @csrf.exempt
    def download_waiver_document(filepath):
        if not _is_authorized(filepath):
            abort(403)
        output_base = current_app.config.get(
            "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))
        return send_from_directory(output_base, filepath)

    @app.route("/pilot-waiver/attachment/<path:filepath>")
    @app.route("/production-waiver/attachment/<path:filepath>")
    @csrf.exempt
    def download_waiver_attachment(filepath):
        if not _is_authorized(filepath):
            abort(403)
        output_base = current_app.config.get(
            "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))
        return send_from_directory(output_base, filepath)
