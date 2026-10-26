from flask import Blueprint, current_app, jsonify, request

from services.admin.checkouts import (
    create_checkout,
    delete_checkout,
    get_checkout_detail,
    list_checkouts,
    update_checkout,
)
from utils.jwt_auth import require_api_auth

api_checkouts_bp = Blueprint("api_checkouts", __name__)


@api_checkouts_bp.route("/checkouts", methods=["GET"])
@require_api_auth("administrator", "manager", "user")
def api_list_checkouts():
    try:
        result = list_checkouts()
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"❌ API list_checkouts error: {e}")
        return jsonify({"error": str(e)}), 500


@api_checkouts_bp.route("/checkouts/<int:record_id>", methods=["GET"])
@require_api_auth("administrator", "manager", "user")
def api_get_checkout(record_id):
    try:
        data = get_checkout_detail(record_id)
        if not data:
            return jsonify({"error": "Not found"}), 404
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"❌ API get_checkout error: {e}")
        return jsonify({"error": str(e)}), 500


@api_checkouts_bp.route("/checkouts", methods=["POST"])
@require_api_auth("administrator", "manager", "user")
def api_create_checkout():
    try:
        data = request.get_json(silent=True) or {}
        create_checkout(data, request.files)
        return jsonify({"message": "Checkout créé avec succès"}), 201
    except Exception as e:
        current_app.logger.error(f"❌ API create_checkout error: {e}")
        return jsonify({"error": str(e)}), 500


@api_checkouts_bp.route("/checkouts/<int:record_id>", methods=["PUT"])
@require_api_auth("administrator", "manager", "user")
def api_update_checkout(record_id):
    try:
        data = request.get_json(silent=True) or {}
        update_checkout(record_id, data, request.files)
        return jsonify({"message": "Checkout mis à jour"})
    except Exception as e:
        current_app.logger.error(f"❌ API update_checkout error: {e}")
        return jsonify({"error": str(e)}), 500


@api_checkouts_bp.route("/checkouts/<int:record_id>", methods=["DELETE"])
@require_api_auth("administrator", "manager")
def api_delete_checkout(record_id):
    try:
        delete_checkout(record_id)
        return jsonify({"message": "Checkout supprimé"})
    except Exception as e:
        current_app.logger.error(f"❌ API delete_checkout error: {e}")
        return jsonify({"error": str(e)}), 500


@api_checkouts_bp.route("/checkouts/<int:record_id>/status", methods=["PATCH"])
@require_api_auth("administrator", "manager", "user")
def api_update_checkout_status(record_id):
    from models import CheckoutVehicle, db
    from services.admin.status_mapping import INSPECTION_STATUS_MAP, get_inspection_key
    try:
        record = db.session.get(CheckoutVehicle, record_id)
        if not record:
            return jsonify({"error": "Not found"}), 404

        data = request.get_json(silent=True) or {}
        new_status = data.get("status")
        if not new_status:
            return jsonify({"error": "Missing status"}), 400

        # Sécurité : interdire le passage manuel aux statuts scellés/signés sans signature cryptographique
        forbidden_manual_statuses = {"signed", "completed", "signé", "validé", "approved"}
        if str(new_status).strip().lower() in forbidden_manual_statuses:
            return jsonify({
                "error": "Le statut 'signed' ne peut être obtenu que par scellement cryptographique avec un jeton valide."
            }), 400

        record.status = new_status
        db.session.commit()

        status_id = get_inspection_key(record.status)
        return jsonify({
            "status": INSPECTION_STATUS_MAP.get(status_id, status_id),
            "status_id": status_id,
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ API checkout status error: {e}")
        return jsonify({"error": str(e)}), 500


@api_checkouts_bp.route("/checkouts/<int:record_id>/finalize", methods=["POST"])
@require_api_auth("administrator", "manager", "user")
def api_finalize_checkout(record_id):
    """
    Finalize a checkout by submitting signature data with a valid token.
    Triggers PDF generation, emails, and webhooks.
    """
    from services.common.signatures import process_inspection_signature
    try:
        data = request.get_json(silent=True) or {}
        signature_data = data.get("signature_data")
        token = data.get("token")

        if not signature_data:
            return jsonify({"error": "signature_data requis"}), 400

        if not token:
            return jsonify({"error": "Le jeton de validation (token) est obligatoire pour sceller ce document."}), 400

        from utils.request_utils import get_client_ip
        signer_ip = get_client_ip()

        try:
            result = process_inspection_signature(
                token, "checkout", signature_data, signer_ip, expected_record_id=record_id
            )
        except ValueError as val_err:
            return jsonify({"error": str(val_err)}), 400

        return jsonify({
            "message": "Checkout finalisé avec succès",
            "document_id": result.get("document_id"),
            "pdf_url": result.get("pdf_url")
        })
    except Exception as e:
        current_app.logger.error(f"❌ API finalize_checkout error: {e}")
        return jsonify({"error": str(e)}), 500
