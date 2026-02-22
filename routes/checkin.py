"""
Checkin routes — thin HTTP layer.
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

from utils.checkin import (
    get_checkin_record,
    get_checkin_by_inspection_id,
    format_checkin_data,
)
from services.checkin import (
    validate_signing_token,
    generate_signing_token,
    process_signature,
    verify_checkin_document,
    validate_pdf_access_token,
)


def init_checkin_routes(app):
    """Public checkin flow: view, generate, sign, verify, download."""

    # ── Auth Guards ───────────────────────────────────────────────

    def require_checkin_token():
        token = request.headers.get("X-Check-Token")
        expected = os.getenv("CHECK_API_TOKEN")
        if not expected:
            current_app.logger.error("❌ CHECK_API_TOKEN is not set.")
            abort(500)
        if not token or not secrets.compare_digest(token, expected):
            abort(403)

    # ── Routes ────────────────────────────────────────────────────

    @app.route("/checkin/<inspection_id>")
    def checkin_view(inspection_id):
        require_checkin_token()
        record = get_checkin_by_inspection_id(inspection_id)
        if not record:
            abort(404)
        data = format_checkin_data(record)
        return render_template(
            "checkin.html", data=data, signature=None, qr=None, hash=None
        )

    @app.route("/checkin/generate", methods=["POST"])
    def checkin_generate():
        require_checkin_token()
        payload = request.get_json(silent=True)
        if not payload or "record_id" not in payload:
            return jsonify({"error": "record_id is required"}), 400

        result = generate_signing_token(payload["record_id"])
        if not result:
            return jsonify({"error": "Record not found in Airtable"}), 404

        return jsonify({"status": "draft_ready", **result}), 201

    @app.route("/checkin/sign/<token>", methods=["GET"])
    def checkin_sign_page(token):
        entry, error_code = validate_signing_token(token)
        if not entry:
            abort(error_code)

        record = get_checkin_record(entry["record_id"])
        if not record:
            abort(404)
        data = format_checkin_data(record)
        return render_template("checkin_sign.html", data=data, token=token)

    @app.route("/checkin/sign/<token>", methods=["POST"])
    @csrf.exempt
    def checkin_submit_signature(token):
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
        except Exception as e:
            current_app.logger.error(
                f"❌ Critical error during checkin signature submission: {e}", exc_info=True)
            return jsonify({"error": "Internal server error during signature processing"}), 500

    @app.route("/checkin/verify/<inspection_id>", methods=["GET", "POST"])
    def checkin_verify(inspection_id):
        uploaded_file = request.files.get(
            "pdf") if request.method == "POST" else None
        context = verify_checkin_document(inspection_id, uploaded_file)

        if context is None:
            abort(404)

        return render_template("checkin_verify.html", **context)

    @app.route("/checkin/document/<filename>")
    @csrf.exempt
    def download_checkin_document(filename):
        access_token = request.args.get("t", "")
        if not access_token or not validate_pdf_access_token(filename, access_token):
            abort(403)

        private_folder = current_app.config.get("PRIVATE_FOLDER")
        directory = os.path.join(private_folder, "checkin_pdfs")

        try:
            return send_from_directory(directory, filename)
        except Exception:
            abort(404)
