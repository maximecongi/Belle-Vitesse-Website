from flask import Blueprint, current_app, jsonify, request

from services.admin.productions import (
    create_production,
    delete_production,
    get_production_for_edit,
    list_productions,
    update_production,
)
from utils.jwt_auth import require_api_auth

api_productions_bp = Blueprint("api_productions", __name__)


@api_productions_bp.route("/productions", methods=["GET"])
@require_api_auth("administrator", "manager", "user")
def api_list_productions():
    try:
        result = list_productions()
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"❌ API list_productions error: {e}")
        return jsonify({"error": str(e)}), 500


@api_productions_bp.route("/productions/<int:record_id>", methods=["GET"])
@require_api_auth("administrator", "manager", "user")
def api_get_production(record_id):
    try:
        data = get_production_for_edit(record_id)
        if not data:
            return jsonify({"error": "Not found"}), 404
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"❌ API get_production error: {e}")
        return jsonify({"error": str(e)}), 500


@api_productions_bp.route("/productions", methods=["POST"])
@require_api_auth("administrator", "manager")
def api_create_production():
    try:
        data = request.get_json(silent=True) or {}
        create_production(data)
        return jsonify({"message": "Production créée avec succès"}), 201
    except Exception as e:
        current_app.logger.error(f"❌ API create_production error: {e}")
        return jsonify({"error": str(e)}), 500


@api_productions_bp.route("/productions/<int:record_id>", methods=["PUT"])
@require_api_auth("administrator", "manager")
def api_update_production(record_id):
    try:
        data = request.get_json(silent=True) or {}
        update_production(record_id, data)
        return jsonify({"message": "Production mise à jour"})
    except Exception as e:
        current_app.logger.error(f"❌ API update_production error: {e}")
        return jsonify({"error": str(e)}), 500


@api_productions_bp.route("/productions/<int:record_id>", methods=["DELETE"])
@require_api_auth("administrator", "manager")
def api_delete_production(record_id):
    try:
        delete_production(record_id)
        return jsonify({"message": "Production supprimée"})
    except Exception as e:
        current_app.logger.error(f"❌ API delete_production error: {e}")
        return jsonify({"error": str(e)}), 500
