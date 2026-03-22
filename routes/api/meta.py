from flask import Blueprint, current_app, jsonify

from services.admin.inspections import get_unified_form_context
from services.admin.status_mapping import CHECKPOINT_STATUS_MAP, INSPECTION_STATUS_MAP
from utils.database import get_all_static, get_grips_categories, get_heads, get_vehicles
from utils.jwt_auth import require_api_auth

api_meta_bp = Blueprint("api_meta", __name__)

@api_meta_bp.route("/meta/vehicles", methods=["GET"])
@require_api_auth("administrator", "manager", "user")
def api_list_vehicles_meta():
    """List all vehicles with basic info and slug."""
    try:
        vehicles = get_vehicles()
        # Format for API: simplify fields
        formatted = []
        for v in vehicles:
            f = v.get("fields", {})
            formatted.append({
                "id": v["id"],
                "name": f.get("name"),
                "slug": f.get("slug"),
                "unique_id": f.get("unique_id"),
                "plate": f.get("plate"),
                "brand": f.get("brand"),
                "model": f.get("model"),
                "type": f.get("type"),
                "image_url": f.get("image_url")
            })
        return jsonify(formatted)
    except Exception as e:
        current_app.logger.error(f"❌ API list_vehicles_meta error: {e}")
        return jsonify({"error": str(e)}), 500

@api_meta_bp.route("/meta/inspection-context", methods=["GET"])
@require_api_auth("administrator", "manager", "user")
def api_inspection_context():
    """Get all context data needed to start a new inspection (projects, users, vehicles, checkpoints)."""
    try:
        # We can detect mode via query param if needed, but get_unified_form_context returns both
        context = get_unified_form_context(mode="checkout")
        return jsonify(context)
    except Exception as e:
        current_app.logger.error(f"❌ API inspection_context error: {e}")
        return jsonify({"error": str(e)}), 500

@api_meta_bp.route("/meta/static-data", methods=["GET"])
@require_api_auth("administrator", "manager", "user")
def api_static_data():
    """Get categories, heads, status maps, and static translations."""
    try:
        return jsonify({
            "heads": get_heads(),
            "grips_categories": get_grips_categories(),
            "static_content": get_all_static(),
            "inspection_statuses": INSPECTION_STATUS_MAP,
            "checkpoint_statuses": CHECKPOINT_STATUS_MAP
        })
    except Exception as e:
        current_app.logger.error(f"❌ API static_data error: {e}")
        return jsonify({"error": str(e)}), 500
