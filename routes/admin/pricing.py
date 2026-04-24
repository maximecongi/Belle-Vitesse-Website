from flask import current_app, jsonify, render_template, request

from services.admin.pricing import (
    list_equipment_rates,
    list_logistics_rates,
    list_salary_rates,
    update_equipment_rate,
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
                logistics={},
            )

    # ── API PATCH : tarif équipement ──────────────────────────

    @app.route("/admin/api/pricing/equipment", methods=["PATCH"])
    @require_roles('administrator')
    def admin_api_pricing_equipment():
        try:
            data = request.get_json(force=True)
            rate_id = data.get("id")
            field = data.get("field")
            value = data.get("value")

            if not rate_id or not field:
                return jsonify({"success": False, "error": "Paramètres manquants"}), 400

            updated = update_equipment_rate(rate_id, field, value)
            return jsonify({"success": True, "data": updated})
        except ValueError as e:
            return jsonify({"success": False, "error": str(e)}), 400
        except Exception as e:
            current_app.logger.error(f"❌ Erreur mise à jour tarif équipement : {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    # ── API PATCH : tarif salaire ─────────────────────────────

    @app.route("/admin/api/pricing/salary", methods=["PATCH"])
    @require_roles('administrator')
    def admin_api_pricing_salary():
        try:
            data = request.get_json(force=True)
            rate_id = data.get("id")
            field = data.get("field")
            value = data.get("value")

            if not rate_id or not field:
                return jsonify({"success": False, "error": "Paramètres manquants"}), 400

            updated = update_salary_rate(rate_id, field, value)
            return jsonify({"success": True, "data": updated})
        except ValueError as e:
            return jsonify({"success": False, "error": str(e)}), 400
        except Exception as e:
            current_app.logger.error(f"❌ Erreur mise à jour tarif salaire : {e}")
            return jsonify({"success": False, "error": str(e)}), 500
