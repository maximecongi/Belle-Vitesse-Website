"""
Routes publiques d'inspection (Check-out & Check-in) — couche HTTP légère unifiée.

Chaque gestionnaire : analyse la requête → appelle le service → affiche/redirige.
Toute la logique métier réside dans services.admin.inspections ou services.common.signatures.
"""

import os
import secrets

from flask import (
    abort,
    current_app,
    jsonify,
    render_template,
    request,
)

from extensions import csrf
from models import (
    CheckinSignedDocument,
    CheckinVehicle,
    CheckoutSignedDocument,
    CheckoutVehicle,
    db,
)
from routes.public.shared_docs import handle_document_download, handle_document_verify
from services.common.signatures import (
    abandon_inspection_signature,
    generate_inspection_token,
    process_inspection_signature,
    resume_inspection_signature,
    validate_inspection_token,
)


def _get_inspection_config(mode):
    if mode == "checkout":
        return {
            "mode": "checkout",
            "model": CheckoutVehicle,
            "signed_model": CheckoutSignedDocument,
            "seal_prefix": "BVCO",
            "template_pdf": "pdf/checkout.html",
            "route_base": "checkout",
        }
    elif mode == "checkin":
        return {
            "mode": "checkin",
            "model": CheckinVehicle,
            "signed_model": CheckinSignedDocument,
            "seal_prefix": "BVCI",
            "template_pdf": "pdf/checkin.html",
            "route_base": "checkin",
        }
    raise ValueError(f"Unknown inspection mode: {mode}")


def register_inspection_routes(app, mode):
    """Enregistre l'ensemble des routes publiques pour une inspection (checkout ou checkin)."""
    cfg = _get_inspection_config(mode)
    route_base = cfg["route_base"]
    model = cfg["model"]
    signed_model = cfg["signed_model"]
    seal_prefix = cfg["seal_prefix"]
    template_pdf = cfg["template_pdf"]

    def require_check_token():
        token = request.headers.get("X-Check-Token")
        expected = os.getenv("CHECK_API_TOKEN")
        if not expected:
            current_app.logger.error("❌ CHECK_API_TOKEN is not set.")
            abort(500)
        if not token or not secrets.compare_digest(token, expected):
            abort(403)

    # 1. Vue PDF brute protégée par token
    @app.route(f"/{route_base}/<inspection_id>", endpoint=f"{mode}_view")
    def inspection_view(inspection_id):
        require_check_token()
        record = model.query.filter_by(inspection_number=inspection_id).first()
        if not record:
            abort(404)

        from services.admin.inspections import _format_base_inspection_admin
        from utils.database import get_vehicles
        vehicle_map = {v["id"]: v.get("fields", {}) for v in get_vehicles()}
        data = _format_base_inspection_admin(record, vehicle_map)

        return render_template(
            template_pdf, data=data, signature=None, qr=None, hash=None
        )

    # 2. Génération du draft token
    @app.route(f"/{route_base}/generate", methods=["POST"], endpoint=f"{mode}_generate")
    @csrf.exempt
    def inspection_generate():
        require_check_token()
        payload = request.get_json(silent=True)
        if not payload or "record_id" not in payload:
            return jsonify({"error": "record_id is required"}), 400

        result = generate_inspection_token(payload["record_id"], mode)
        if not result:
            return jsonify({"error": "Record not found in database"}), 404

        return jsonify({"status": "draft_ready", **result}), 201

    # 3. Page publique de signature (GET)
    @app.route(f"/{route_base}/sign/<token>", methods=["GET"], endpoint=f"{mode}_sign_page")
    def inspection_sign_page(token):
        entry, error_code = validate_inspection_token(token, mode)
        if not entry:
            abort(error_code)

        record = db.session.get(model, int(entry.record_id))
        if not record:
            abort(404)

        if record.status == "in_progress":
            try:
                record.status = "pending"
                db.session.commit()
            except Exception:
                pass

        from services.admin.inspections import _format_base_inspection_admin
        from utils.database import get_vehicles
        vehicle_map = {v["id"]: v.get("fields", {}) for v in get_vehicles()}
        data = _format_base_inspection_admin(record, vehicle_map)

        return render_template("public/inspection_sign.html", data=data, token=token, type=mode)

    # 4. Abandon de signature (POST)
    @app.route(f"/{route_base}/sign/<token>/abandon", methods=["POST"], endpoint=f"{mode}_abandon")
    @csrf.exempt
    def inspection_abandon(token):
        abandon_inspection_signature(token, mode)
        return jsonify({"status": "abandoned"}), 200

    # 5. Reprise de signature (POST)
    @app.route(f"/{route_base}/sign/<token>/resume", methods=["POST"], endpoint=f"{mode}_resume")
    @csrf.exempt
    def inspection_resume(token):
        resume_inspection_signature(token, mode)
        return jsonify({"status": "resumed"}), 200

    # 6. Soumission de signature (POST)
    @app.route(f"/{route_base}/sign/<token>", methods=["POST"], endpoint=f"{mode}_submit_signature")
    @csrf.exempt
    def inspection_submit_signature(token):
        entry, error_code = validate_inspection_token(token, mode)
        if not entry:
            error_messages = {
                404: "Jeton invalide ou expiré",
                410: "Jeton expiré",
                400: "Déjà signé",
            }
            return jsonify({"error": error_messages.get(error_code, "Error")}), error_code

        payload = request.get_json(silent=True)
        if not payload or "signature" not in payload:
            return jsonify({"error": "signature data is required"}), 400

        signed_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        try:
            record = process_inspection_signature(token, mode, payload["signature"], signed_ip)
            return jsonify({"status": "signed", **record}), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        except Exception as e:
            current_app.logger.error(
                f"❌ Critical error during {mode} signature submission: {e}", exc_info=True)
            return jsonify({"error": "Internal server error during signature processing"}), 500

    # 7. Vérification de document scellé (GET/POST)
    @app.route(f"/{route_base}/verify/<inspection_id>", methods=["GET", "POST"], endpoint=f"{mode}_verify")
    @csrf.exempt
    def inspection_verify(inspection_id):
        config = {
            "signed_model": signed_model,
            "seal_prefix": seal_prefix,
            "template_verify": "public/inspection_verify.html",
            "route_base": route_base,
            "get_seal_args": lambda data, signed_doc: [
                data.get("inspection_id", ""),
                data.get("vehicle_id", ""),
                signed_doc.signature,
                data.get("_seal_signed_at", "")
            ]
        }
        return handle_document_verify(config, inspection_id)

    # 8. Téléchargement sécurisé de document
    @app.route(f"/{route_base}/document/<path:filepath>", endpoint=f"download_{mode}_document")
    @csrf.exempt
    def download_inspection_document(filepath):
        return handle_document_download(filepath)
