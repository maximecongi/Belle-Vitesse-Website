"""
Checkout routes — thin HTTP layer.

Each handler: parse request → call service → render/redirect.
All business logic lives in services.checkout.
"""

import os
import secrets

from flask import (
    render_template,
    abort,
    jsonify,
    request,
    current_app,
    send_from_directory,
)

from extensions import csrf

from models import db, CheckoutVehicle
from services.checkout import (
    validate_signing_token,
    generate_signing_token,
    process_signature,
    verify_checkout_document,
    validate_pdf_access_token,
)


def init_checkout_routes(app):
    """Public checkout flow: view, generate, sign, verify, download."""

    # ── Auth Guards ───────────────────────────────────────────────

    def require_checkout_token():
        token = request.headers.get("X-Check-Token")
        expected = os.getenv("CHECK_API_TOKEN")
        if not expected:
            current_app.logger.error("❌ CHECK_API_TOKEN is not set.")
            abort(500)
        if not token or not secrets.compare_digest(token, expected):
            abort(403)

    # ── Routes ────────────────────────────────────────────────────

    @app.route("/checkout/<inspection_id>")
    def checkout_view(inspection_id):
        require_checkout_token()
        record = CheckoutVehicle.query.filter_by(
            numero_inspection=inspection_id).first()
        if not record:
            abort(404)

        from services.admin import _format_checkout_admin
        from utils.database import get_vehicles
        vehicle_map = {v["id"]: v.get("fields", {}) for v in get_vehicles()}
        data = _format_checkout_admin(record, vehicle_map)

        return render_template(
            "checkout.html", data=data, signature=None, qr=None, hash=None
        )

    @app.route("/checkout/generate", methods=["POST"])
    @csrf.exempt
    def checkout_generate():
        require_checkout_token()
        payload = request.get_json(silent=True)
        if not payload or "record_id" not in payload:
            return jsonify({"error": "record_id is required"}), 400

        result = generate_signing_token(payload["record_id"])
        if not result:
            return jsonify({"error": "Record not found in database"}), 404

        return jsonify({"status": "draft_ready", **result}), 201

    @app.route("/checkout/sign/<token>", methods=["GET"])
    def checkout_sign_page(token):
        entry, error_code = validate_signing_token(token)
        if not entry:
            abort(error_code)

        record = db.session.get(CheckoutVehicle, int(entry.record_id))
        if not record:
            abort(404)

        # If user reloaded the page, the abandon beacon might have set this to 'En cours'.
        # We catch it here and revert it to 'À signer' since the user is still on the page.
        if record.etat_controle == "En cours":
            try:
                record.etat_controle = "À signer"
                db.session.commit()
            except Exception:
                pass

        from services.admin import _format_checkout_admin
        from utils.database import get_vehicles
        vehicle_map = {v["id"]: v.get("fields", {}) for v in get_vehicles()}
        data = _format_checkout_admin(record, vehicle_map)

        return render_template("checkout_sign.html", data=data, token=token)

    @app.route("/checkout/sign/<token>/abandon", methods=["POST"])
    @csrf.exempt
    def checkout_abandon(token):
        from services.checkout import abandon_signature
        abandon_signature(token)
        return jsonify({"status": "abandoned"}), 200

    @app.route("/checkout/sign/<token>/resume", methods=["POST"])
    @csrf.exempt
    def checkout_resume(token):
        from services.checkout import resume_signature
        resume_signature(token)
        return jsonify({"status": "resumed"}), 200

    @app.route("/checkout/sign/<token>", methods=["POST"])
    @csrf.exempt
    def checkout_submit_signature(token):
        entry, error_code = validate_signing_token(token)
        if not entry:
            error_messages = {
                404: "Invalid or expired token",
                410: "Token expired",
                400: "Already signed",
            }
            return jsonify({"error": error_messages.get(error_code, "Error")}), error_code

        payload = request.get_json(silent=True)
        if not payload or "signature" not in payload:
            return jsonify({"error": "signature data is required"}), 400

        signed_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        try:
            result = process_signature(token, payload["signature"], signed_ip)
            return jsonify({"status": "signed", **result}), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 404

    @app.route("/checkout/verify/<inspection_id>", methods=["GET", "POST"])
    @csrf.exempt
    def checkout_verify(inspection_id):
        uploaded_file = request.files.get(
            "pdf") if request.method == "POST" else None
        context = verify_checkout_document(inspection_id, uploaded_file)

        if context is None:
            abort(404)

        return render_template("checkout_verify.html", **context)

    @app.route("/checkout/document/<path:filepath>")
    @csrf.exempt
    def download_checkout_document(filepath):
        access_token = request.args.get("t", "")
        if not access_token or not validate_pdf_access_token(filepath, access_token):
            abort(403)

        output_base = current_app.config.get(
            "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))
        private_folder = current_app.config.get("PRIVATE_FOLDER")

        try:
            if "/" in filepath and not filepath.startswith(".."):
                # New hierarchical structure
                return send_from_directory(output_base, filepath)
            else:
                # Legacy flat structure
                directory = os.path.join(private_folder, "checkout_pdfs")
                return send_from_directory(directory, filepath)
        except Exception:
            abort(404)
