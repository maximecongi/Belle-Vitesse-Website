from flask import current_app, jsonify, render_template, request

from services.admin.pricing import (
    add_logistics_rate,
    add_salary_rate,
    delete_logistics_rate,
    delete_salary_rate,
    list_equipment_rates,
    list_logistics_rates,
    list_salary_rates,
    update_equipment_daily_rate,
    update_logistics_rate,
    update_salary_rate,
)
from utils.decorators import require_roles


def init_pricing_routes(app):

    @app.route("/admin/pricing")
    @require_roles('administrator')
    def admin_pricing():
        try:
            equipment = list_equipment_rates()
            salaries = list_salary_rates()
            logistics = list_logistics_rates()
            return render_template(
                "admin/pricing.html",
                equipment=equipment,
                salaries=salaries,
                logistics=logistics,
            )
        except Exception as e:
            current_app.logger.error(f"❌ Erreur tarification : {e}")
            return render_template(
                "admin/pricing.html",
                equipment={},
                salaries={},
                logistics=[],
            )

    # ── Équipement ───────────────────────────────────────────────

    @app.route("/admin/api/pricing/equipment", methods=["PATCH"])
    @require_roles('administrator')
    def admin_api_pricing_equipment():
        try:
            data = request.get_json(force=True)
            updated = update_equipment_daily_rate(data.get("table"), data.get("id"), data.get("value"))
            return jsonify({"success": True, "data": updated})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    # ── Salaires ─────────────────────────────────────────────────

    @app.route("/admin/api/pricing/salary", methods=["POST"])
    @require_roles('administrator')
    def admin_api_pricing_salary_add():
        try:
            data = request.get_json(force=True)
            new_item = add_salary_rate(data.get("group_name"))
            return jsonify({"success": True, "data": new_item})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/admin/api/pricing/salary", methods=["PATCH"])
    @require_roles('administrator')
    def admin_api_pricing_salary_update():
        try:
            data = request.get_json(force=True)
            updated = update_salary_rate(data.get("id"), data.get("field"), data.get("value"))
            return jsonify({"success": True, "data": updated})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/admin/api/pricing/salary/<int:rate_id>", methods=["DELETE"])
    @require_roles('administrator')
    def admin_api_pricing_salary_delete(rate_id):
        try:
            success = delete_salary_rate(rate_id)
            return jsonify({"success": success})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    # ── Logistique ───────────────────────────────────────────────

    @app.route("/admin/api/pricing/logistics", methods=["POST"])
    @require_roles('administrator')
    def admin_api_pricing_logistics_add():
        try:
            new_item = add_logistics_rate()
            return jsonify({"success": True, "data": new_item})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/admin/api/pricing/logistics", methods=["PATCH"])
    @require_roles('administrator')
    def admin_api_pricing_logistics_update():
        try:
            data = request.get_json(force=True)
            updated = update_logistics_rate(data.get("id"), data.get("field"), data.get("value"))
            return jsonify({"success": True, "data": updated})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/admin/api/pricing/logistics/<int:rate_id>", methods=["DELETE"])
    @require_roles('administrator')
    def admin_api_pricing_logistics_delete(rate_id):
        try:
            success = delete_logistics_rate(rate_id)
            return jsonify({"success": success})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400
