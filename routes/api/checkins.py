from flask import Blueprint, request, jsonify, current_app
from utils.jwt_auth import require_api_auth
from services.admin.checkins import (
    list_checkins,
    get_checkin_detail,
    create_checkin,
    update_checkin,
    delete_checkin,
)

api_checkins_bp = Blueprint("api_checkins", __name__)


@api_checkins_bp.route("/checkins", methods=["GET"])
@require_api_auth("administrator", "manager", "user")
def api_list_checkins():
    try:
        result = list_checkins()
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"❌ API list_checkins error: {e}")
        return jsonify({"error": str(e)}), 500


@api_checkins_bp.route("/checkins/<int:record_id>", methods=["GET"])
@require_api_auth("administrator", "manager", "user")
def api_get_checkin(record_id):
    try:
        data = get_checkin_detail(record_id)
        if not data:
            return jsonify({"error": "Not found"}), 404
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"❌ API get_checkin error: {e}")
        return jsonify({"error": str(e)}), 500


@api_checkins_bp.route("/checkins", methods=["POST"])
@require_api_auth("administrator", "manager", "user")
def api_create_checkin():
    try:
        data = request.get_json(silent=True) or {}
        create_checkin(data, request.files)
        return jsonify({"message": "Check-in créé avec succès"}), 201
    except Exception as e:
        current_app.logger.error(f"❌ API create_checkin error: {e}")
        return jsonify({"error": str(e)}), 500


@api_checkins_bp.route("/checkins/<int:record_id>", methods=["PUT"])
@require_api_auth("administrator", "manager", "user")
def api_update_checkin(record_id):
    try:
        data = request.get_json(silent=True) or {}
        update_checkin(record_id, data, request.files)
        return jsonify({"message": "Check-in mis à jour"})
    except Exception as e:
        current_app.logger.error(f"❌ API update_checkin error: {e}")
        return jsonify({"error": str(e)}), 500


@api_checkins_bp.route("/checkins/<int:record_id>", methods=["DELETE"])
@require_api_auth("administrator", "manager")
def api_delete_checkin(record_id):
    try:
        delete_checkin(record_id)
        return jsonify({"message": "Check-in supprimé"})
    except Exception as e:
        current_app.logger.error(f"❌ API delete_checkin error: {e}")
        return jsonify({"error": str(e)}), 500


@api_checkins_bp.route("/checkins/<int:record_id>/status", methods=["PATCH"])
@require_api_auth("administrator", "manager", "user")
def api_update_checkin_status(record_id):
    from models import db, CheckinVehicle
    from services.admin.status_mapping import get_inspection_key, INSPECTION_STATUS_MAP
    try:
        record = db.session.get(CheckinVehicle, record_id)
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
        current_app.logger.error(f"❌ API checkin status error: {e}")
        return jsonify({"error": str(e)}), 500
