from flask import current_app, flash, jsonify, render_template, request

from services.admin.pricing import (
    add_logistics_rate,
    add_salary_rate,
    delete_logistics_rate,
    delete_salary_rate,
    delete_salary_group,
    get_invoice_factor,
    list_equipment_rates,
    list_logistics_rates,
    list_salary_rates,
    list_salary_rates_grouped,
    list_salary_groups,
    rename_salary_group,
    reorder_equipment,
    reorder_logistics_rates,
    reorder_salary_rates,
    update_equipment_daily_rate,
    update_invoice_factor,
    update_logistics_rate,
    update_salary_rate,
)
from utils.decorators import require_roles


def init_pricing_routes(app):

    # ── Page principale ──────────────────────────────────────────

    @app.route("/admin/pricing")
    @require_roles('administrator', 'manager', 'commercial')
    def admin_pricing():
        """Page tarification avec 3 onglets indépendants."""

        # Chaque section est chargée indépendamment
        try:
            equipment = list_equipment_rates()
        except Exception as e:
            current_app.logger.error(f"❌ Équipement: {e}")
            equipment = {}
            flash(f"Erreur chargement Équipement : {e}", "error")

        try:
            salary_grouped = list_salary_rates_grouped()
        except Exception as e:
            current_app.logger.error(f"❌ Salaires: {e}")
            salary_grouped = {}
            flash(f"Erreur chargement Salaires : {e}", "error")

        try:
            logistics = list_logistics_rates()
        except Exception as e:
            current_app.logger.error(f"❌ Logistique: {e}")
            logistics = []
            flash(f"Erreur chargement Logistique : {e}", "error")

        return render_template(
            "admin/pricing.html",
            equipment=equipment,
            salary_grouped=salary_grouped,
            logistics=logistics,
            invoice_factor=get_invoice_factor(),
        )

    # ── API Équipement ───────────────────────────────────────────

    @app.route("/admin/api/pricing/equipment", methods=["PATCH"])
    @require_roles('administrator')
    def admin_api_pricing_equipment():
        try:
            data = request.get_json(force=True)
            updated = update_equipment_daily_rate(
                data.get("table"), data.get("id"), data.get("value"))
            return jsonify({"success": True, "data": updated})
        except Exception as e:
            current_app.logger.error(f"❌ PATCH equipment: {e}")
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/admin/api/pricing/equipment/reorder", methods=["PATCH"])
    @require_roles('administrator')
    def admin_api_pricing_equipment_reorder():
        try:
            data = request.get_json(force=True)
            reorder_equipment(data.get("table"), data.get("ids", []))
            return jsonify({"success": True})
        except Exception as e:
            current_app.logger.error(f"❌ PATCH equipment reorder: {e}")
            return jsonify({"success": False, "error": str(e)}), 400

    # ── API Salaires ─────────────────────────────────────────────

    @app.route("/admin/api/pricing/salary", methods=["POST"])
    @require_roles('administrator')
    def admin_api_pricing_salary_add():
        try:
            data = request.get_json(force=True) if request.data else {}
            group_name = data.get('group_name', '') if data else ''
            annexe = data.get('annexe', 'Annexe 1') if data else 'Annexe 1'
            new_item = add_salary_rate(group_name, annexe)
            return jsonify({"success": True, "data": new_item})
        except Exception as e:
            current_app.logger.error(f"❌ POST salary: {e}")
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/admin/api/pricing/salary", methods=["PATCH"])
    @require_roles('administrator')
    def admin_api_pricing_salary_update():
        try:
            data = request.get_json(force=True)
            result = update_salary_rate(
                data.get("id"), data.get("field"), data.get("value"))
            return jsonify({
                "success": True,
                "data": result["rate"],
                "updated_rates": result["updated_rates"]
            })
        except Exception as e:
            current_app.logger.error(f"❌ PATCH salary: {e}")
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/admin/api/pricing/salary/<int:rate_id>", methods=["DELETE"])
    @require_roles('administrator')
    def admin_api_pricing_salary_delete(rate_id):
        try:
            delete_salary_rate(rate_id)
            return jsonify({"success": True})
        except Exception as e:
            current_app.logger.error(f"❌ DELETE salary: {e}")
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/admin/api/pricing/salary/reorder", methods=["PATCH"])
    @require_roles('administrator')
    def admin_api_pricing_salary_reorder():
        try:
            data = request.get_json(force=True)
            reorder_salary_rates(data.get("groups", {}))
            return jsonify({"success": True})
        except Exception as e:
            current_app.logger.error(f"❌ PATCH salary reorder: {e}")
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/admin/api/pricing/salary/rename-group", methods=["PATCH"])
    @require_roles('administrator')
    def admin_api_pricing_salary_rename_group():
        try:
            data = request.get_json(force=True)
            new_name = rename_salary_group(data.get("old_name"), data.get("new_name"))
            return jsonify({"success": True, "new_name": new_name})
        except Exception as e:
            current_app.logger.error(f"❌ PATCH salary rename-group: {e}")
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/admin/api/pricing/salary/delete-group", methods=["DELETE"])
    @require_roles('administrator')
    def admin_api_pricing_salary_delete_group():
        try:
            data = request.get_json(force=True)
            count = delete_salary_group(data.get("group_name"))
            return jsonify({"success": True, "deleted_count": count})
        except Exception as e:
            current_app.logger.error(f"❌ DELETE salary group: {e}")
            return jsonify({"success": False, "error": str(e)}), 400

    # ── API Logistique ───────────────────────────────────────────

    @app.route("/admin/api/pricing/logistics", methods=["POST"])
    @require_roles('administrator')
    def admin_api_pricing_logistics_add():
        try:
            new_item = add_logistics_rate()
            return jsonify({"success": True, "data": new_item})
        except Exception as e:
            current_app.logger.error(f"❌ POST logistics: {e}")
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/admin/api/pricing/logistics", methods=["PATCH"])
    @require_roles('administrator')
    def admin_api_pricing_logistics_update():
        try:
            data = request.get_json(force=True)
            updated = update_logistics_rate(
                data.get("id"), data.get("field"), data.get("value"))
            return jsonify({"success": True, "data": updated})
        except Exception as e:
            current_app.logger.error(f"❌ PATCH logistics: {e}")
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/admin/api/pricing/logistics/<int:rate_id>", methods=["DELETE"])
    @require_roles('administrator')
    def admin_api_pricing_logistics_delete(rate_id):
        try:
            delete_logistics_rate(rate_id)
            return jsonify({"success": True})
        except Exception as e:
            current_app.logger.error(f"❌ DELETE logistics: {e}")
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/admin/api/pricing/logistics/reorder", methods=["PATCH"])
    @require_roles('administrator')
    def admin_api_pricing_logistics_reorder():
        try:
            data = request.get_json(force=True)
            reorder_logistics_rates(data.get("ids", []))
            return jsonify({"success": True})
        except Exception as e:
            current_app.logger.error(f"❌ PATCH logistics reorder: {e}")
            return jsonify({"success": False, "error": str(e)}), 400

    # ── API Facteur Invoice ────────────────────────────────────────

    @app.route("/admin/api/pricing/invoice-factor", methods=["PATCH"])
    @require_roles('administrator')
    def admin_api_pricing_invoice_factor():
        try:
            data = request.get_json()
            new_factor = update_invoice_factor(data.get("value"))
            # Renvoyer toutes les lignes recalculées pour mise à jour UI
            salaries = list_salary_rates()
            return jsonify({
                "success": True,
                "factor": new_factor,
                "salaries": salaries,
            })
        except Exception as e:
            current_app.logger.error(f"❌ PATCH invoice-factor: {e}")
            return jsonify({"success": False, "error": str(e)}), 400
