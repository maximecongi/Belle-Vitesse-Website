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
)

from extensions import csrf

from models import db, CheckinVehicle
from services.checkin import (
    validate_signing_token,
    generate_signing_token,
    process_signature,
)
from routes.shared_docs import handle_document_download, handle_document_verify


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
        record = CheckinVehicle.query.filter_by(
            numero_inspection=inspection_id).first()
        if not record:
            abort(404)

        from services.admin.inspections import _format_base_inspection_admin
        from utils.database import get_vehicles
        vehicle_map = {v["id"]: v.get("fields", {}) for v in get_vehicles()}
        data = _format_base_inspection_admin(record, vehicle_map)
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
            return jsonify({"error": "Record not found in database"}), 404

        return jsonify({"status": "draft_ready", **result}), 201

    @app.route("/checkin/sign/<token>", methods=["GET"])
    def checkin_sign_page(token):
        entry, error_code = validate_signing_token(token)
        if not entry:
            abort(error_code)

        record = db.session.get(CheckinVehicle, int(entry.record_id))
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

        from services.admin.inspections import _format_base_inspection_admin
        from utils.database import get_vehicles
        vehicle_map = {v["id"]: v.get("fields", {}) for v in get_vehicles()}
        data = _format_base_inspection_admin(record, vehicle_map)

        return render_template("checkin_sign.html", data=data, token=token)

    @app.route("/checkin/sign/<token>/abandon", methods=["POST"])
    @csrf.exempt
    def checkin_abandon(token):
        from services.checkin import abandon_signature
        abandon_signature(token)
        return jsonify({"status": "abandoned"}), 200

    @app.route("/checkin/sign/<token>/resume", methods=["POST"])
    @csrf.exempt
    def checkin_resume(token):
        from services.checkin import resume_signature
        resume_signature(token)
        return jsonify({"status": "resumed"}), 200

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
    @csrf.exempt
    def checkin_verify(inspection_id):
        from models import CheckinSignedDocument
        config = {
            "signed_model": CheckinSignedDocument,
            "seal_prefix": "INSPECTION",
            "template_verify": "checkin_verify.html",
            "route_base": "checkin",
            "get_seal_args": lambda data, signed_doc: [
                data.get("inspection_id", ""),
                data.get("vehicle_id", ""),
                signed_doc.signature,
                data.get("_seal_signed_at", "")
            ]
        }
        return handle_document_verify(config, inspection_id)

    @app.route("/checkin/document/<path:filepath>")
    @csrf.exempt
    def download_checkin_document(filepath):
        return handle_document_download(filepath)
