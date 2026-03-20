from flask import Blueprint, request, jsonify, current_app
from utils.jwt_auth import require_api_auth
from services.admin.projects import (
    list_projects,
    create_project,
    update_project,
    get_project_for_edit,
    delete_project,
)

api_projects_bp = Blueprint("api_projects", __name__)


@api_projects_bp.route("/projects", methods=["GET"])
@require_api_auth("administrator", "manager", "user")
def api_list_projects():
    try:
        result = list_projects()
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"❌ API list_projects error: {e}")
        return jsonify({"error": str(e)}), 500


@api_projects_bp.route("/projects/<int:record_id>", methods=["GET"])
@require_api_auth("administrator", "manager", "user")
def api_get_project(record_id):
    try:
        data = get_project_for_edit(record_id)
        if not data:
            return jsonify({"error": "Not found"}), 404
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"❌ API get_project error: {e}")
        return jsonify({"error": str(e)}), 500


@api_projects_bp.route("/projects", methods=["POST"])
@require_api_auth("administrator", "manager")
def api_create_project():
    try:
        data = request.get_json(silent=True) or {}
        create_project(data)
        return jsonify({"message": "Projet créé avec succès"}), 201
    except Exception as e:
        current_app.logger.error(f"❌ API create_project error: {e}")
        return jsonify({"error": str(e)}), 500


@api_projects_bp.route("/projects/<int:record_id>", methods=["PUT"])
@require_api_auth("administrator", "manager")
def api_update_project(record_id):
    try:
        data = request.get_json(silent=True) or {}
        update_project(record_id, data)
        return jsonify({"message": "Projet mis à jour"})
    except Exception as e:
        current_app.logger.error(f"❌ API update_project error: {e}")
        return jsonify({"error": str(e)}), 500


@api_projects_bp.route("/projects/<int:record_id>", methods=["DELETE"])
@require_api_auth("administrator", "manager")
def api_delete_project(record_id):
    try:
        delete_project(record_id)
        return jsonify({"message": "Projet supprimé"})
    except Exception as e:
        current_app.logger.error(f"❌ API delete_project error: {e}")
        return jsonify({"error": str(e)}), 500
