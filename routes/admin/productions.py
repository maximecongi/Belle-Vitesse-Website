from flask import (
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from models import Production, db
from services.admin import (
    create_production,
    delete_production,
    get_production_for_edit,
    list_productions,
    update_production,
)
from utils.decorators import require_roles


def init_productions_routes(app):
    # ── CRUD Productions ──────────────────────────────────────────

    @app.route("/admin/productions")
    @require_roles('administrator', 'manager', 'commercial')
    def admin_productions_list():
        try:
            productions = list_productions()
            productions.sort(key=lambda p: p.get("name", "").lower())
            return render_template("admin/productions_list.html", productions=productions)
        except Exception as e:
            current_app.logger.error(f"❌ Erreur lors de la récupération des productions : {e}")
            flash(
                f"Erreur lors de la récupération des productions : {str(e)}", "error")
            return render_template("admin/productions_list.html", productions=[])

    @app.route("/admin/productions/new", methods=["GET", "POST"])
    @require_roles('administrator', 'manager', 'commercial')
    def admin_production_new():
        if request.method == "POST":
            try:
                create_production(request.form)
                flash("Production créée avec succès !", "success")
                return redirect(url_for("admin_productions_list"))
            except Exception as e:
                current_app.logger.error(f"❌ Erreur lors de la création de la production : {e}")
                flash(f"Erreur lors de la création : {str(e)}", "error")
                return render_template(
                    "admin/production_form.html", data=request.form, is_edit=False
                )
        return render_template("admin/production_form.html", is_edit=False)

    @app.route("/admin/productions/<record_id>/edit", methods=["GET", "POST"])
    @require_roles('administrator', 'manager', 'commercial')
    def admin_production_edit(record_id):
        try:
            if request.method == "POST":
                update_production(record_id, request.form)
                flash("Production modifiée avec succès !", "success")
                return redirect(url_for("admin_productions_list"))

            data = get_production_for_edit(record_id)
            if not data:
                abort(404)
            return render_template("admin/production_form.html", data=data, is_edit=True)
        except Exception as e:
            current_app.logger.error(f"❌ Erreur lors de la modification de la production : {e}")
            flash(f"Erreur lors de la modification : {str(e)}", "error")
            return redirect(url_for("admin_productions_list"))

    @app.route("/admin/productions/<record_id>/delete", methods=["POST"])
    @require_roles('administrator', 'manager', 'commercial')
    def admin_production_delete(record_id):
        try:
            delete_production(record_id)
            flash("Production supprimée avec succès.", "success")
            return redirect(url_for("admin_productions_list"))
        except Exception as e:
            current_app.logger.error(f"❌ Erreur lors de la suppression de la production : {e}")
            flash(f"Erreur lors de la suppression : {str(e)}", "error")
            return redirect(url_for("admin_productions_list"))

    @app.route("/admin/api/productions/quick", methods=["POST"])
    @require_roles('administrator', 'manager', 'commercial')
    def admin_api_production_quick_create():
        try:
            data = request.get_json() or {}
            name = data.get("name", "").strip()
            if not name:
                return jsonify({"error": "Le nom de la production est requis."}), 400

            existing = Production.query.filter(Production.name.ilike(name)).first()
            if existing:
                return jsonify({"id": str(existing.id), "name": existing.name})

            prod = Production(name=name)
            db.session.add(prod)
            db.session.commit()

            return jsonify({"id": str(prod.id), "name": prod.name})
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"❌ Erreur lors de la création rapide de production : {e}")
            return jsonify({"error": str(e)}), 500
