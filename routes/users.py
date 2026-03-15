from flask import render_template, request, redirect, url_for, flash

from services.users import list_users, get_user, create_user, update_user, delete_user
from utils.decorators import require_roles


def init_users_routes(app):

    @app.route("/admin/users")
    @require_roles('administrator')
    def admin_users_list():
        users = list_users()
        return render_template("admin/users_list.html", users=users)

    @app.route("/admin/users/new", methods=["GET", "POST"])
    @require_roles('administrator')
    def admin_user_create():
        if request.method == "POST":
            data = {
                "firstname": request.form.get("firstname"),
                "lastname": request.form.get("lastname"),
                "mail": request.form.get("mail"),
                "role": request.form.get("role"),
                "phone": request.form.get("phone"),
                "job": request.form.get("job")
            }
            if create_user(data):
                flash("Utilisateur créé avec succès.", "success")
                return redirect(url_for("admin_users_list"))
            flash("Erreur lors de la création de l'utilisateur.", "error")
        return render_template("admin/user_form.html", is_edit=False, data=None)

    @app.route("/admin/users/<record_id>/edit", methods=["GET", "POST"])
    @require_roles('administrator')
    def admin_user_edit(record_id):
        user = get_user(record_id)
        if not user:
            flash("Utilisateur introuvable.", "error")
            return redirect(url_for("admin_users_list"))

        if request.method == "POST":
            data = {
                "firstname": request.form.get("firstname"),
                "lastname": request.form.get("lastname"),
                "mail": request.form.get("mail"),
                "role": request.form.get("role"),
                "phone": request.form.get("phone"),
                "job": request.form.get("job")
            }
            if update_user(record_id, data):
                flash("Utilisateur mis à jour avec succès.", "success")
                return redirect(url_for("admin_users_list"))
            flash("Erreur lors de la mise à jour de l'utilisateur.", "error")

        return render_template("admin/user_form.html", is_edit=True, data=user, record_id=record_id)

    @app.route("/admin/users/<record_id>/delete", methods=["POST"])
    @require_roles('administrator')
    def admin_user_delete(record_id):
        if delete_user(record_id):
            flash("Utilisateur supprimé avec succès.", "success")
        else:
            flash("Erreur lors de la suppression de l'utilisateur.", "error")
        return redirect(url_for("admin_users_list"))
