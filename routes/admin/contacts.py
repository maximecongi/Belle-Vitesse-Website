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
    @require_roles('administrator', 'manager', 'commercial')
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
    @require_roles('administrator', 'manager', 'commercial')
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
    @require_roles('administrator', 'manager', 'commercial')
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
    @require_roles('administrator', 'manager', 'commercial')
    def admin_contact_delete(record_id):
        try:
            delete_contact(record_id)
            flash("Contact supprimé avec succès.", "success")
            return redirect(url_for("admin_contacts_list"))
        except Exception as e:
            current_app.logger.error(f"❌ Erreur lors de la suppression du contact : {e}")
            flash(f"Erreur lors de la suppression : {str(e)}", "error")
            return redirect(url_for("admin_contacts_list"))

    @app.route("/admin/api/contacts/quick", methods=["POST"])
    @require_roles('administrator', 'manager', 'commercial')
    def admin_api_contact_quick_create():
        try:
            from models import Contact, db

            data = request.get_json() or {}
            first_name = data.get("first_name", "").strip()
            last_name = data.get("last_name", "").strip()
            job_title = data.get("job_title", "").strip()
            mail = data.get("mail", "").strip()
            phone = data.get("phone", "").strip()
            production_id = data.get("production_id")

            if not first_name or not last_name:
                return jsonify({"error": "Le prénom et le nom sont requis."}), 400

            prod_id_int = int(production_id) if production_id and str(production_id).isdigit() else None

            contact = Contact(
                first_name=first_name,
                last_name=last_name,
                job_title=job_title if job_title else None,
                mail=mail if mail else None,
                phone=phone if phone else None,
                production_id=prod_id_int
            )
            db.session.add(contact)
            db.session.commit()

            display_name = f"{contact.first_name} {contact.last_name} ({contact.job_title})" if contact.job_title else f"{contact.first_name} {contact.last_name}"

            return jsonify({
                "id": str(contact.id),
                "name": display_name,
                "first_name": contact.first_name,
                "last_name": contact.last_name,
                "job_title": contact.job_title or "",
                "mail": contact.mail or "",
                "phone": contact.phone or "",
                "production_id": str(contact.production_id) if contact.production_id else ""
            }), 201
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"❌ Erreur lors de la création rapide de contact : {e}")
            return jsonify({"error": str(e)}), 500
