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

from services.admin.contacts import (
    list_contacts,
    create_contact,
    update_contact,
    get_contact_for_edit,
    delete_contact,
    get_productions_for_select,
)


def init_contacts_routes(app):
    # ── Contacts CRUD ──────────────────────────────────────────

    @app.route("/admin/contacts")
    @require_roles('administrator', 'manager')
    def admin_contacts_list():
        try:
            contacts = list_contacts()
            return render_template("admin/contacts_list.html", contacts=contacts)
        except Exception as e:
            current_app.logger.error(f"❌ Error fetching contacts: {e}")
            flash(
                f"Erreur lors de la récupération des contacts : {str(e)}", "error")
            return render_template("admin/contacts_list.html", contacts=[])

    @app.route("/admin/contacts/new", methods=["GET", "POST"])
    @require_roles('administrator', 'manager')
    def admin_contact_new():
        if request.method == "POST":
            try:
                create_contact(request.form)
                flash("Contact créé avec succès !", "success")
                return redirect(url_for("admin_contacts_list"))
            except Exception as e:
                current_app.logger.error(f"❌ Error creating contact: {e}")
                flash(f"Erreur lors de la création : {str(e)}", "error")
                return render_template(
                    "admin/contact_form.html",
                    data=request.form,
                    productions=get_productions_for_select(),
                    is_edit=False,
                )
        return render_template(
            "admin/contact_form.html",
            productions=get_productions_for_select(),
            is_edit=False,
        )

    @app.route("/admin/contacts/<int:record_id>/edit", methods=["GET", "POST"])
    @require_roles('administrator', 'manager')
    def admin_contact_edit(record_id):
        try:
            if request.method == "POST":
                update_contact(record_id, request.form)
                flash("Contact modifié avec succès !", "success")
                return redirect(url_for("admin_contacts_list"))

            data = get_contact_for_edit(record_id)
            if not data:
                abort(404)
            return render_template(
                "admin/contact_form.html",
                data=data,
                productions=get_productions_for_select(),
                is_edit=True,
            )
        except Exception as e:
            current_app.logger.error(f"❌ Error editing contact: {e}")
            flash(f"Erreur lors de la modification : {str(e)}", "error")
            return redirect(url_for("admin_contacts_list"))

    @app.route("/admin/contacts/<int:record_id>/delete", methods=["POST"])
    @require_roles('administrator', 'manager')
    def admin_contact_delete(record_id):
        try:
            delete_contact(record_id)
            flash("Contact supprimé avec succès.", "success")
            return redirect(url_for("admin_contacts_list"))
        except Exception as e:
            current_app.logger.error(f"❌ Error deleting contact: {e}")
            flash(f"Erreur lors de la suppression : {str(e)}", "error")
            return redirect(url_for("admin_contacts_list"))
