from flask import Blueprint, current_app, jsonify, request

from services.admin.waivers import (
    create_cgl,
    create_safety_rules_waiver,
    delete_cgl,
    delete_safety_rules_waiver,
    generate_cgl,
    generate_safety_rules_waiver,
    list_cgl,
    list_safety_rules_waivers,
    reset_cgl,
    reset_safety_rules_waiver,
    send_cgl,
    send_safety_rules_waiver,
)
from utils.jwt_auth import require_api_auth

api_waivers_bp = Blueprint("api_waivers", __name__)


# ── Conditions Générales de Location (CGL - BVRA) ────────────────────

@api_waivers_bp.route("/cgl", methods=["GET"])
@require_api_auth("administrator", "manager", "commercial", "user")
def api_list_cgl():
    try:
        result = list_cgl()
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"❌ API list_cgl error: {e}")
        return jsonify({"error": str(e)}), 500


@api_waivers_bp.route("/cgl", methods=["POST"])
@require_api_auth("administrator", "manager", "commercial")
def api_create_cgl():
    """Crée des CGL pour un project_id donné."""
    try:
        data = request.get_json(silent=True) or {}
        project_id = data.get("project_id")
        if not project_id:
            return jsonify({"error": "project_id requis"}), 400
        success, msg = create_cgl(project_id)
        if success:
            return jsonify({"message": msg}), 201
        return jsonify({"error": msg}), 400
    except Exception as e:
        current_app.logger.error(f"❌ API create_cgl error: {e}")
        return jsonify({"error": str(e)}), 500


@api_waivers_bp.route("/cgl/<waiver_id>/generate", methods=["POST"])
@require_api_auth("administrator", "manager", "commercial")
def api_generate_cgl(waiver_id):
    try:
        success, msg = generate_cgl(waiver_id)
        if success:
            return jsonify({"message": msg})
        return jsonify({"error": msg}), 400
    except Exception as e:
        current_app.logger.error(f"❌ API generate_cgl error: {e}")
        return jsonify({"error": str(e)}), 500


@api_waivers_bp.route("/cgl/<waiver_id>/send", methods=["POST"])
@require_api_auth("administrator", "manager", "commercial")
def api_send_cgl(waiver_id):
    try:
        success, msg = send_cgl(waiver_id)
        if success:
            return jsonify({"message": msg})
        return jsonify({"error": msg}), 400
    except Exception as e:
        current_app.logger.error(f"❌ API send_cgl error: {e}")
        return jsonify({"error": str(e)}), 500


@api_waivers_bp.route("/cgl/<waiver_id>", methods=["DELETE"])
@api_waivers_bp.route("/cgl/<waiver_id>/delete", methods=["POST"])
@require_api_auth("administrator", "manager", "commercial")
def api_delete_cgl(waiver_id):
    try:
        success, msg = delete_cgl(waiver_id)
        if success:
            return jsonify({"message": msg})
        return jsonify({"error": msg}), 404
    except Exception as e:
        current_app.logger.error(f"❌ API delete_cgl error: {e}")
        return jsonify({"error": str(e)}), 500


@api_waivers_bp.route("/cgl/<waiver_id>/reset", methods=["POST"])
@require_api_auth("administrator", "manager", "commercial")
def api_reset_cgl(waiver_id):
    try:
        success, msg = reset_cgl(waiver_id)
        if success:
            return jsonify({"message": msg})
        return jsonify({"error": msg}), 400
    except Exception as e:
        current_app.logger.error(f"❌ API reset_cgl error: {e}")
        return jsonify({"error": str(e)}), 500


# ── Règles de Sécurité Universelles (BVSR) ───────────────────────────

@api_waivers_bp.route("/safety-rules", methods=["GET"])
@require_api_auth("administrator", "manager", "commercial", "user")
def api_list_safety_rules():
    try:
        result = list_safety_rules_waivers()
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"❌ API list_safety_rules error: {e}")
        return jsonify({"error": str(e)}), 500


@api_waivers_bp.route("/safety-rules", methods=["POST"])
@require_api_auth("administrator", "manager", "commercial")
def api_create_safety_rules():
    """Crée un engagement BVSR pour un intervenant d'un projet."""
    try:
        data = request.get_json(silent=True) or {}
        project_id = data.get("project_id")
        if not project_id:
            return jsonify({"error": "project_id requis"}), 400
        success, msg = create_safety_rules_waiver(
            project_id=project_id,
            signer_role=data.get("signer_role", "pilot"),
            signer_role_custom=data.get("signer_role_custom"),
            signer_first_name=data.get("signer_first_name"),
            signer_last_name=data.get("signer_last_name"),
            signer_email=data.get("signer_email"),
            signer_phone=data.get("signer_phone"),
            signer_company=data.get("signer_company"),
            safety_technicians=data.get("safety_technicians"),
        )
        if success:
            return jsonify({"message": msg}), 201
        return jsonify({"error": msg}), 400
    except Exception as e:
        current_app.logger.error(f"❌ API create_safety_rules error: {e}")
        return jsonify({"error": str(e)}), 500


@api_waivers_bp.route("/safety-rules/<waiver_id>/generate", methods=["POST"])
@require_api_auth("administrator", "manager", "commercial")
def api_generate_safety_rules(waiver_id):
    try:
        success, msg = generate_safety_rules_waiver(waiver_id)
        if success:
            return jsonify({"message": msg})
        return jsonify({"error": msg}), 400
    except Exception as e:
        current_app.logger.error(f"❌ API generate_safety_rules error: {e}")
        return jsonify({"error": str(e)}), 500


@api_waivers_bp.route("/safety-rules/<waiver_id>/send", methods=["POST"])
@require_api_auth("administrator", "manager", "commercial")
def api_send_safety_rules(waiver_id):
    try:
        success, msg = send_safety_rules_waiver(waiver_id)
        if success:
            return jsonify({"message": msg})
        return jsonify({"error": msg}), 400
    except Exception as e:
        current_app.logger.error(f"❌ API send_safety_rules error: {e}")
        return jsonify({"error": str(e)}), 500


@api_waivers_bp.route("/safety-rules/<waiver_id>", methods=["DELETE"])
@api_waivers_bp.route("/safety-rules/<waiver_id>/delete", methods=["POST"])
@require_api_auth("administrator", "manager", "commercial")
def api_delete_safety_rules(waiver_id):
    try:
        success, msg = delete_safety_rules_waiver(waiver_id)
        if success:
            return jsonify({"message": msg})
        return jsonify({"error": msg}), 404
    except Exception as e:
        current_app.logger.error(f"❌ API delete_safety_rules error: {e}")
        return jsonify({"error": str(e)}), 500


@api_waivers_bp.route("/safety-rules/<waiver_id>/reset", methods=["POST"])
@require_api_auth("administrator", "manager", "commercial")
def api_reset_safety_rules(waiver_id):
    try:
        success, msg = reset_safety_rules_waiver(waiver_id)
        if success:
            return jsonify({"message": msg})
        return jsonify({"error": msg}), 400
    except Exception as e:
        current_app.logger.error(f"❌ API reset_safety_rules error: {e}")
        return jsonify({"error": str(e)}), 500
