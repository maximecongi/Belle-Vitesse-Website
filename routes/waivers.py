import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import render_template, request, jsonify, current_app, abort, send_from_directory
import secrets
from models import PilotWaiver, PilotWaiverSignedDocument, ProductionWaiver, ProductionWaiverSignedDocument, db
from utils.waivers import (
    process_pilot_waiver_signature,
    process_production_waiver_signature,
    validate_waiver_pdf_access_token,
    generate_waiver_pdf_access_token
)
from utils.storage import (
    get_pilot_attachments_path,
    get_production_attachments_path,
    ensure_dir
)
from utils.waiver_verification import (
    verify_waiver_seal,
    verify_production_waiver_seal,
    verify_pdf_hash
)
from extensions import csrf


def init_waiver_routes(app):
    @app.route("/sign/waiver/<token>", methods=["GET", "POST"])
    def sign_pilot_waiver(token):
        waiver = PilotWaiver.query.filter_by(signature_token=token).first()

        if request.method == "GET":
            if not waiver:
                return render_template("waivers/sign_pilot_waiver.html", waiver={"status": "invalid"})
            return render_template("waivers/sign_pilot_waiver.html", waiver=waiver)

        if request.method == "POST":
            if not waiver or waiver.status == 'signed':
                return jsonify({"success": False, "error": "Token invalide ou décharge déjà signée."})

            try:
                # Get form data (using request.form for multipart/form-data)
                data = request.form

                # Update waiver data
                waiver.pilot_first_name = data.get("first_name")
                waiver.pilot_last_name = data.get("last_name")
                waiver.pilot_dob = data.get("dob")
                waiver.pilot_license_number = data.get("license_number")
                waiver.pilot_address = data.get("address")
                waiver.pilot_insurance_company = data.get("insurance_company")
                waiver.pilot_insurance_policy = data.get("insurance_policy")
                waiver.signature_data = data.get("signature_data")

                # Handle file uploads using new storage hierarchy
                output_base = current_app.config.get(
                    "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

                file_fields = {
                    'pilot_license': ('pilot_license_path', 'license'),
                    'pilot_insurance': ('pilot_insurance_path', 'insurance'),
                    'pilot_identity': ('pilot_identity_path', 'identity')
                }

                for field_name, (attr_name, doc_type) in file_fields.items():
                    file = request.files.get(field_name)
                    if file and file.filename:
                        upload_dir = ensure_dir(
                            get_pilot_attachments_path(waiver.project, doc_type))
                        filename = secure_filename(file.filename)
                        # Prepend timestamp to avoid collisions
                        filename = f"{field_name}_{int(datetime.now().timestamp())}_{filename}"
                        file_path = os.path.join(upload_dir, filename)
                        file.save(file_path)

                        # Store relative path from output base
                        rel_path = os.path.relpath(file_path, output_base)
                        setattr(waiver, attr_name, rel_path)

                signer_ip = request.headers.get(
                    'X-Forwarded-For', request.remote_addr)
                if signer_ip and ',' in signer_ip:
                    signer_ip = signer_ip.split(',')[0].strip()
                waiver.signer_ip = signer_ip

                db.session.commit()

                # Trigger background process or process synchronously
                process_pilot_waiver_signature(waiver.id)

                return jsonify({"success": True})

            except Exception as e:
                current_app.logger.error(
                    f"Error processing waiver signature: {e}")
                return jsonify({"success": False, "error": "Une erreur serveur est survenue."}), 500

    @app.route("/verify/waiver/<string:waiver_id>", methods=["GET", "POST"])
    @csrf.exempt
    def verify_pilot_waiver(waiver_id):
        signed_doc = PilotWaiverSignedDocument.query.filter_by(
            waiver_id=waiver_id).first()
        if not signed_doc:
            abort(404)

        data = signed_doc.data_snapshot
        # Convert signed_at string from JSON back to datetime for strftime in template
        if 'signed_at' in data and isinstance(data['signed_at'], str):
            try:
                from datetime import datetime
                data['signed_at'] = datetime.fromisoformat(data['signed_at'])
            except (ValueError, TypeError):
                pass

        stored_hash = signed_doc.hash
        stored_signature = signed_doc.signature
        stored_pdf_file_hash = signed_doc.pdf_file_hash

        # 1. Verify HMAC seal
        seal_valid = verify_waiver_seal(
            waiver_id=str(waiver_id),
            pilot_name=data.get("_seal_pilot_name", ""),
            license_number=data.get("_seal_license", ""),
            signature_data=stored_signature,
            signed_at=data.get("_seal_signed_at", ""),
            expected_hash=stored_hash
        )

        pdf_valid = None
        pdf_error = None

        # 2. Verify uploaded PDF (if POST)
        if request.method == "POST":
            uploaded_file = request.files.get("pdf")
            if uploaded_file:
                if not uploaded_file.filename.lower().endswith(".pdf"):
                    pdf_error = "Le fichier doit être un PDF."
                elif not stored_pdf_file_hash:
                    pdf_error = "Ce document n'a pas d'empreinte PDF enregistrée."
                else:
                    uploaded_bytes = uploaded_file.read()
                    pdf_valid = verify_pdf_hash(
                        uploaded_bytes, stored_pdf_file_hash)

        # Fallback for project_name if missing from snapshot (old documents)
        if not data.get('project_name'):
            waiver = PilotWaiver.query.filter_by(waiver_id=waiver_id).first()
            if waiver:
                data['project_name'] = waiver.project_name or (
                    waiver.project.nom if waiver.project else None)

        if not data.get('hash'):
            data['hash'] = stored_hash

        # Generate access token for the PDF download link
        pdf_url = signed_doc.pdf_url
        if pdf_url:
            # Extract path from URL - handles both filename for legacy and full path
            # URLs are either /pilot-waiver/document/FILENAME or /pilot-waiver/document/PATH/TO/FILE
            # We want the part after /document/
            path_part = pdf_url.split("/document/")[-1].split("?")[0]
            token = generate_waiver_pdf_access_token(path_part)
            pdf_download_url = f"/pilot-waiver/document/{path_part}?t={token}"
        else:
            pdf_download_url = None

        return render_template(
            "waivers/pilot_waiver_verify.html",
            data=data,
            seal_valid=seal_valid,
            pdf_valid=pdf_valid,
            pdf_error=pdf_error,
            inspection_id=signed_doc.waiver_id,
            document_hash=stored_hash,
            project_name=data.get('project_name'),
            has_pdf_hash=bool(stored_pdf_file_hash),
            pdf_download_url=pdf_download_url
        )

    @app.route("/pilot-waiver/document/<path:filepath>")
    @csrf.exempt
    def download_pilot_waiver_document(filepath):
        # 1. Check for header-based access (admin/automation)
        token_header = request.headers.get("X-Check-Token")
        expected_header = os.getenv("CHECK_API_TOKEN")

        # 2. Check for URL-based access (pilots/preview)
        access_token = request.args.get("t", "")

        is_authorized = False

        if expected_header and token_header and secrets.compare_digest(token_header, expected_header):
            is_authorized = True
        elif access_token and validate_waiver_pdf_access_token(filepath, access_token):
            is_authorized = True

        if not is_authorized:
            abort(403)

        output_base = current_app.config.get(
            "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

        try:
            return send_from_directory(output_base, filepath)
        except Exception:
            abort(404)

    @app.route("/pilot-waiver/attachment/<path:filepath>")
    @csrf.exempt
    def download_pilot_waiver_attachment(filepath):
        # filepath is either "waiver_id/filename" (legacy) or "YEAR/MONTH/.../filename" (new)
        # 1. Check for header-based access
        token_header = request.headers.get("X-Check-Token")
        expected_header = os.getenv("CHECK_API_TOKEN")

        # 2. Check for URL-based access
        access_token = request.args.get("t", "")

        is_authorized = False
        if expected_header and token_header and secrets.compare_digest(token_header, expected_header):
            is_authorized = True
        elif access_token and validate_waiver_pdf_access_token(filepath, access_token):
            is_authorized = True

        if not is_authorized:
            abort(403)

        output_base = current_app.config.get(
            "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

        try:
            return send_from_directory(output_base, filepath)
        except Exception:
            abort(404)

    # --- PRODUCTION WAIVER ROUTES ---

    @app.route("/sign/production-waiver/<token>", methods=["GET", "POST"])
    def sign_production_waiver(token):
        waiver = ProductionWaiver.query.filter_by(
            signature_token=token).first()

        if request.method == "GET":
            if not waiver:
                return render_template("waivers/sign_production_waiver.html", waiver={"status": "invalid"})
            return render_template("waivers/sign_production_waiver.html", waiver=waiver)

        if request.method == "POST":
            if not waiver or waiver.status == 'signed':
                return jsonify({"success": False, "error": "Token invalide ou décharge déjà signée."})

            try:
                data = request.form

                # Update waiver data
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
                waiver.signature_data = data.get("signature_data")

                # Handle file uploads using new storage hierarchy
                output_base = current_app.config.get(
                    "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

                file = request.files.get('production_insurance')
                if file and file.filename:
                    upload_dir = ensure_dir(
                        get_production_attachments_path(waiver.project, 'insurance'))
                    filename = secure_filename(file.filename)
                    filename = f"prod_insurance_{int(datetime.now().timestamp())}_{filename}"
                    file_path = os.path.join(upload_dir, filename)
                    file.save(file_path)

                    # Store relative path from output base
                    rel_path = os.path.relpath(file_path, output_base)
                    waiver.production_insurance_path = rel_path

                signer_ip = request.headers.get(
                    'X-Forwarded-For', request.remote_addr)
                if signer_ip and ',' in signer_ip:
                    signer_ip = signer_ip.split(',')[0].strip()
                waiver.signer_ip = signer_ip

                db.session.commit()

                # Process signature
                process_production_waiver_signature(waiver.id)

                return jsonify({"success": True})

            except Exception as e:
                current_app.logger.error(
                    f"Error processing production waiver signature: {e}")
                return jsonify({"success": False, "error": "Une erreur serveur est survenue."}), 500

    @app.route("/verify/production-waiver/<string:waiver_id>", methods=["GET", "POST"])
    @csrf.exempt
    def verify_production_waiver(waiver_id):
        signed_doc = ProductionWaiverSignedDocument.query.filter_by(
            waiver_id=waiver_id).first()
        if not signed_doc:
            abort(404)

        data = signed_doc.data_snapshot
        if 'signed_at' in data and isinstance(data['signed_at'], str):
            try:
                from datetime import datetime
                data['signed_at'] = datetime.fromisoformat(data['signed_at'])
            except (ValueError, TypeError):
                pass

        stored_hash = signed_doc.hash
        stored_signature = signed_doc.signature
        stored_pdf_file_hash = signed_doc.pdf_file_hash

        seal_valid = verify_production_waiver_seal(
            waiver_id=str(waiver_id),
            production_name=data.get("_seal_production_name", ""),
            representative=data.get("_seal_representative", ""),
            signature_data=stored_signature,
            signed_at=data.get("_seal_signed_at", ""),
            expected_hash=stored_hash
        )

        pdf_valid = None
        pdf_error = None

        if request.method == "POST":
            uploaded_file = request.files.get("pdf")
            if uploaded_file:
                if not uploaded_file.filename.lower().endswith(".pdf"):
                    pdf_error = "Le fichier doit être un PDF."
                elif not stored_pdf_file_hash:
                    pdf_error = "Ce document n'a pas d'empreinte PDF enregistrée."
                else:
                    uploaded_bytes = uploaded_file.read()
                    pdf_valid = verify_pdf_hash(
                        uploaded_bytes, stored_pdf_file_hash)

        if not data.get('hash'):
            data['hash'] = stored_hash

        pdf_url = signed_doc.pdf_url
        if pdf_url:
            path_part = pdf_url.split("/document/")[-1].split("?")[0]
            token = generate_waiver_pdf_access_token(path_part)
            pdf_download_url = f"/production-waiver/document/{path_part}?t={token}"
        else:
            pdf_download_url = None

        return render_template(
            "waivers/production_waiver_verify.html",
            data=data,
            seal_valid=seal_valid,
            pdf_valid=pdf_valid,
            pdf_error=pdf_error,
            inspection_id=signed_doc.waiver_id,
            document_hash=stored_hash,
            project_name=data.get('project_name'),
            has_pdf_hash=bool(stored_pdf_file_hash),
            pdf_download_url=pdf_download_url
        )

    @app.route("/production-waiver/document/<path:filepath>")
    @csrf.exempt
    def download_production_waiver_document(filepath):
        token_header = request.headers.get("X-Check-Token")
        expected_header = os.getenv("CHECK_API_TOKEN")
        access_token = request.args.get("t", "")

        is_authorized = False
        if expected_header and token_header and secrets.compare_digest(token_header, expected_header):
            is_authorized = True
        elif access_token and validate_waiver_pdf_access_token(filepath, access_token):
            is_authorized = True

        if not is_authorized:
            abort(403)

        output_base = current_app.config.get(
            "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

        try:
            return send_from_directory(output_base, filepath)
        except Exception:
            abort(404)

    @app.route("/production-waiver/attachment/<path:filepath>")
    @csrf.exempt
    def download_production_waiver_attachment(filepath):
        token_header = request.headers.get("X-Check-Token")
        expected_header = os.getenv("CHECK_API_TOKEN")
        access_token = request.args.get("t", "")

        is_authorized = False
        if expected_header and token_header and secrets.compare_digest(token_header, expected_header):
            is_authorized = True
        elif access_token and validate_waiver_pdf_access_token(filepath, access_token):
            is_authorized = True

        if not is_authorized:
            abort(403)

        output_base = current_app.config.get(
            "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

        try:
            return send_from_directory(output_base, filepath)
        except Exception:
            abort(404)
