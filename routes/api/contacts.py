from flask import Blueprint, request, jsonify, current_app
from utils.jwt_auth import require_api_auth
from services.admin.contacts import (
    list_contacts,
    create_contact,
    update_contact,
    get_contact_for_edit,
    delete_contact,
)

api_contacts_bp = Blueprint("api_contacts", __name__)


@api_contacts_bp.route("/contacts", methods=["GET"])
@require_api_auth("administrator", "manager", "user")
def api_list_contacts():
    try:
        result = list_contacts()
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"❌ API list_contacts error: {e}")
        return jsonify({"error": str(e)}), 500


@api_contacts_bp.route("/contacts/<int:record_id>", methods=["GET"])
@require_api_auth("administrator", "manager", "user")
def api_get_contact(record_id):
    try:
        data = get_contact_for_edit(record_id)
        if not data:
            return jsonify({"error": "Not found"}), 404
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"❌ API get_contact error: {e}")
        return jsonify({"error": str(e)}), 500


@api_contacts_bp.route("/contacts", methods=["POST"])
@require_api_auth("administrator", "manager")
def api_create_contact():
    try:
        data = request.get_json(silent=True) or {}
        create_contact(data)
        return jsonify({"message": "Contact créé avec succès"}), 201
    except Exception as e:
        current_app.logger.error(f"❌ API create_contact error: {e}")
        return jsonify({"error": str(e)}), 500


@api_contacts_bp.route("/contacts/<int:record_id>", methods=["PUT"])
@require_api_auth("administrator", "manager")
def api_update_contact(record_id):
    try:
        data = request.get_json(silent=True) or {}
        update_contact(record_id, data)
        return jsonify({"message": "Contact mis à jour"})
    except Exception as e:
        current_app.logger.error(f"❌ API update_contact error: {e}")
        return jsonify({"error": str(e)}), 500


@api_contacts_bp.route("/contacts/<int:record_id>", methods=["DELETE"])
@require_api_auth("administrator", "manager")
def api_delete_contact(record_id):
    try:
        delete_contact(record_id)
        return jsonify({"message": "Contact supprimé"})
    except Exception as e:
        current_app.logger.error(f"❌ API delete_contact error: {e}")
        return jsonify({"error": str(e)}), 500
