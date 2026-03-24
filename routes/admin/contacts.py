from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from services.admin.contacts import (
    create_contact,
    delete_contact,
    get_contact_for_edit,
    get_productions_for_select,
    list_contacts,
    update_contact,
)
from utils.decorators import require_roles


def init_contacts_routes(app):
    # ── CRUD Contacts ──────────────────────────────────────────

    def _build_vcf(c):
        """Génère une chaîne vCard 3.0 pour le téléchargement de fichier .vcf."""
        lines = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"N:{c.get('last_name', '')};{c.get('first_name', '')};;;",
            f"FN:{c.get('first_name', '')} {c.get('last_name', '')}",
        ]
        if c.get("phone") and c["phone"] != "—":
            lines.append(f"TEL;TYPE=CELL:{c['phone']}")
        if c.get("mail") and c["mail"] != "—":
            lines.append(f"EMAIL:{c['mail']}")
        if c.get("production_name") and c["production_name"] != "Freelance":
            lines.append(f"ORG:{c['production_name']}")
        if c.get("job_title") and c["job_title"] != "—":
            lines.append(f"TITLE:{c['job_title']}")
        lines.append("END:VCARD")
        return "\r\n".join(lines)

    @app.route("/admin/contacts")
    @require_roles('administrator', 'manager')
    def admin_contacts_list():
        try:
            import base64
            contacts = list_contacts()
            contacts.sort(key=lambda c: (
                c.get("last_name", "").lower(), c.get("first_name", "").lower()))
            for c in contacts:
                vcf = _build_vcf(c)
                c["vcf_b64"] = base64.b64encode(
                    vcf.encode("utf-8")).decode("ascii")
                c["vcf_filename"] = f"{c.get('first_name', '')}_{c.get('last_name', '')}.vcf".replace(
                    " ", "_")
            return render_template("admin/contacts_list.html", contacts=contacts)
        except Exception as e:
            current_app.logger.error(f"❌ Erreur lors de la récupération des contacts : {e}")
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
                current_app.logger.error(f"❌ Erreur lors de la création du contact : {e}")
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
            current_app.logger.error(f"❌ Erreur lors de la modification du contact : {e}")
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
            current_app.logger.error(f"❌ Erreur lors de la suppression du contact : {e}")
            flash(f"Erreur lors de la suppression : {str(e)}", "error")
            return redirect(url_for("admin_contacts_list"))
