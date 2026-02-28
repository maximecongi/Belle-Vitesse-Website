from utils.decorators import require_roles
from flask import (
    render_template,
    abort,
    request,
    current_app,
    redirect,
    url_for,
    flash,
)


from services.admin import (
    list_productions,
    create_production,
    update_production,
    get_production_for_edit,
    delete_production,
)


def init_productions_routes(app):
    # ── Productions CRUD ──────────────────────────────────────────

    @app.route("/admin/productions")
    @require_roles('administrator', 'manager')
    def admin_productions_list():
        try:
            productions = list_productions()
            return render_template("admin/productions_list.html", productions=productions)
        except Exception as e:
            current_app.logger.error(f"❌ Error fetching productions: {e}")
            flash(
                f"Erreur lors de la récupération des productions : {str(e)}", "error")
            return render_template("admin/productions_list.html", productions=[])

    @app.route("/admin/productions/new", methods=["GET", "POST"])
    @require_roles('administrator', 'manager')
    def admin_production_new():
        if request.method == "POST":
            try:
                create_production(request.form)
                flash("Production créée avec succès !", "success")
                return redirect(url_for("admin_productions_list"))
            except Exception as e:
                current_app.logger.error(f"❌ Error creating production: {e}")
                flash(f"Erreur lors de la création : {str(e)}", "error")
                return render_template(
                    "admin/production_form.html", data=request.form, is_edit=False
                )
        return render_template("admin/production_form.html", is_edit=False)

    @app.route("/admin/productions/<record_id>/edit", methods=["GET", "POST"])
    @require_roles('administrator', 'manager')
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
            current_app.logger.error(f"❌ Error editing production: {e}")
            flash(f"Erreur lors de la modification : {str(e)}", "error")
            return redirect(url_for("admin_productions_list"))

    @app.route("/admin/productions/<record_id>/delete", methods=["POST"])
    @require_roles('administrator', 'manager')
    def admin_production_delete(record_id):
        try:
            delete_production(record_id)
            flash("Production supprimée avec succès.", "success")
            return redirect(url_for("admin_productions_list"))
        except Exception as e:
            current_app.logger.error(f"❌ Error deleting production: {e}")
            flash(f"Erreur lors de la suppression : {str(e)}", "error")
            return redirect(url_for("admin_productions_list"))

