from utils.decorators import require_roles
from datetime import datetime
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
    list_projects,
    get_project_form_context,
    create_project,
    update_project,
    get_project_for_edit,
    delete_project,
)


def init_projects_routes(app):
    # ── Projects CRUD ─────────────────────────────────────────────

    @app.route("/admin/projects")
    @require_roles('administrator', 'manager')
    def admin_projects_list():
        try:
            projects = list_projects()
            today_iso = datetime.now().strftime('%Y-%m-%d')
            upcoming_projects = [p for p in projects
                                 if not p.get("raw_return_date") or p.get("raw_return_date") >= today_iso]
            return render_template("admin/projects_list.html", projects=upcoming_projects, is_archive=False)
        except Exception as e:
            current_app.logger.error(f"❌ Error in admin_projects_list: {e}")
            flash("Erreur lors de la récupération des projets.", "error")
            return render_template("admin/projects_list.html", projects=[], is_archive=False)

    @app.route("/admin/projects/archives")
    @require_roles('administrator', 'manager')
    def admin_projects_archives():
        try:
            projects = list_projects()
            today_iso = datetime.now().strftime('%Y-%m-%d')
            past_projects = [p for p in projects
                             if p.get("raw_return_date") and p.get("raw_return_date") < today_iso]
            return render_template("admin/projects_list.html", projects=past_projects, is_archive=True)
        except Exception as e:
            current_app.logger.error(
                f"❌ Error in admin_projects_archives: {e}")
            flash("Erreur lors de la récupération des archives.", "error")
            return render_template("admin/projects_list.html", projects=[], is_archive=True)

    @app.route("/admin/projects/new", methods=["GET", "POST"])
    @require_roles('administrator', 'manager')
    def admin_project_new():
        context = get_project_form_context()

        if request.method == "POST":
            try:
                if not request.form.get("name"):
                    flash("Le nom du projet est requis.", "error")
                    return render_template(
                        "admin/project_form.html", data=request.form, is_edit=False, **context
                    )
                create_project(request.form)
                flash("Projet créé avec succès !", "success")
                return redirect(url_for("admin_projects_list"))
            except Exception as e:
                current_app.logger.error(f"❌ Error creating project: {e}")
                flash(f"Erreur lors de la création : {str(e)}", "error")
                return render_template(
                    "admin/project_form.html", data=request.form, is_edit=False, **context
                )

        return render_template("admin/project_form.html", is_edit=False, **context)

    @app.route("/admin/projects/<record_id>/edit", methods=["GET", "POST"])
    @require_roles('administrator', 'manager')
    def admin_project_edit(record_id):
        context = get_project_form_context()

        try:
            if request.method == "POST":
                update_project(record_id, request.form)
                flash("Projet modifié avec succès !", "success")
                return redirect(url_for("admin_projects_list"))

            data = get_project_for_edit(record_id)
            if not data:
                abort(404)
            return render_template("admin/project_form.html", data=data, is_edit=True, **context)
        except Exception as e:
            current_app.logger.error(f"❌ Error editing project: {e}")
            flash(f"Erreur lors de la modification : {str(e)}", "error")
            return redirect(url_for("admin_projects_list"))

    @app.route("/admin/projects/<record_id>/delete", methods=["POST"])
    @require_roles('administrator', 'manager')
    def admin_project_delete(record_id):
        try:
            delete_project(record_id)
            flash("Projet supprimé avec succès.", "success")
            return redirect(url_for("admin_projects_list"))
        except Exception as e:
            current_app.logger.error(f"❌ Error deleting project: {e}")
            flash(f"Erreur lors de la suppression : {str(e)}", "error")
            return redirect(url_for("admin_project_edit", record_id=record_id))
