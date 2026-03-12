import os
from werkzeug.utils import secure_filename
from flask import render_template, request, jsonify, current_app, abort
from models import PilotWaiver, PilotWaiverSignedDocument, db
from utils.waivers import process_pilot_waiver_signature
from utils.waiver_verification import verify_waiver_seal, verify_pdf_hash
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

                # Handle file uploads
                upload_dir = os.path.join(
                    current_app.static_folder, 'uploads', 'waivers', 'attachments', str(waiver.id))
                os.makedirs(upload_dir, exist_ok=True)

                file_fields = {
                    'pilot_license': 'pilot_license_path',
                    'pilot_insurance': 'pilot_insurance_path',
                    'pilot_identity': 'pilot_identity_path'
                }

                for field_name, attr_name in file_fields.items():
                    file = request.files.get(field_name)
                    if file and file.filename:
                        filename = secure_filename(file.filename)
                        # Prepend timestamp to avoid collisions if re-signed (though not expected here)
                        filename = f"{field_name}_{filename}"
                        file_path = os.path.join(upload_dir, filename)
                        file.save(file_path)
                        # Store relative path for URL generation (starts with /static/)
                        relative_path = f"/static/uploads/waivers/attachments/{waiver.id}/{filename}"
                        setattr(waiver, attr_name, relative_path)

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

        # Ensure hash is in data if template expects data.hash (fallback)
        if not data.get('hash'):
            data['hash'] = stored_hash

        return render_template(
            "waivers/pilot_waiver_verify.html",
            data=data,
            seal_valid=seal_valid,
            pdf_valid=pdf_valid,
            pdf_error=pdf_error,
            inspection_id=signed_doc.waiver_id,
            document_hash=stored_hash,
            project_name=data.get('project_name'),
            has_pdf_hash=bool(stored_pdf_file_hash)
        )
