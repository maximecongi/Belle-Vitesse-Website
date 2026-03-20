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
