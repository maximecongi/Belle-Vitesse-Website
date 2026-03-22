from flask import Blueprint, request, jsonify, current_app
from utils.jwt_auth import require_api_auth
from services.admin.checkouts import (
    list_checkouts,
    get_checkout_detail,
    create_checkout,
    update_checkout,
    delete_checkout,
)

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
    from models import db, CheckoutVehicle
    from services.admin.status_mapping import get_inspection_key, INSPECTION_STATUS_MAP
    try:
        record = db.session.get(CheckoutVehicle, record_id)
        if not record:
            return jsonify({"error": "Not found"}), 404

        data = request.get_json(silent=True) or {}
        new_status = data.get("status")
        if not new_status:
            return jsonify({"error": "Missing status"}), 400

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
    Finalize a checkout by submitting signature data.
    Triggers PDF generation, emails, and webhooks.
    """
    from services.common.signatures import process_inspection_signature
    try:
        data = request.get_json(silent=True) or {}
        signature_data = data.get("signature_data")
        token = data.get("token")  # Optional if we want to bypass token check in some cases, but process_inspection_signature needs it

        if not signature_data:
            return jsonify({"error": "signature_data requis"}), 400

        # We treat the API call as a trusted source (IP de l'app ou du proxy)
        signer_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if signer_ip and ',' in signer_ip:
            signer_ip = signer_ip.split(',')[0].strip()

        # If we have a token (sent by the app), we use the standard process
        if token:
            result = process_inspection_signature(token, "checkout", signature_data, signer_ip)
        else:
            # Direct finalization using the record_id (skipping token validation)
            from services.common.signatures import finalize_signed_document
            result = finalize_signed_document("checkout", record_id, signature_data, signer_ip)

        return jsonify({
            "message": "Checkout finalisé avec succès",
            "document_id": result.get("document_id"),
            "pdf_url": result.get("pdf_url")
        })
    except Exception as e:
        current_app.logger.error(f"❌ API finalize_checkout error: {e}")
        return jsonify({"error": str(e)}), 500
