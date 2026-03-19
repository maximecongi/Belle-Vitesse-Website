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
    list_checkouts,
    get_checkout_detail,
    get_checkout_form_context,
    create_checkout,
    update_checkout,
    delete_checkout,
)


def init_checkouts_routes(app):
    # ── Checkouts CRUD ────────────────────────────────────────────

    @app.route("/admin/checkouts")
    @require_roles('administrator', 'manager', 'user')
    def admin_checkouts_list():
        try:
            result = list_checkouts()
            return render_template(
                "admin/checkouts_list.html",
                checkouts=result["checkouts"],
            )
        except Exception as e:
            current_app.logger.error(f"❌ Error in admin_checkouts_list: {e}")
            flash("Erreur lors de la récupération de la liste.", "error")
            return render_template(
                "admin/checkouts_list.html",
                checkouts=[],
            )

    @app.route("/admin/checkouts/<record_id>")
    @require_roles('administrator', 'manager', 'user')
    def admin_checkout_detail(record_id):
        try:
            data = get_checkout_detail(record_id)
            if not data:
                abort(404)
            return render_template("admin/checkout_detail.html", data=data, record_id=record_id)
        except Exception as e:
            current_app.logger.error(f"❌ Error in admin_checkout_detail: {e}")
            flash("Erreur lors de la récupération du détail.", "error")
            return redirect(url_for("admin_checkouts_list"))

    @app.route("/admin/checkouts/new", methods=["GET", "POST"])
    @require_roles('administrator', 'manager', 'user')
    def admin_checkout_new():
        context = get_checkout_form_context()

        initial_data = {}
        if request.method == "GET":
            # Prefill from URL params if provided
            if request.args.get("project_id"):
                initial_data["project_id"] = request.args.get("project_id")
            if request.args.get("vehicle_id"):
                initial_data["vehicle_id"] = request.args.get("vehicle_id")

        if request.method == "POST":
            try:
                create_checkout(request.form, request.files)
                flash("Checkout créé avec succès !", "success")
                return redirect(url_for("admin_checkouts_list"))
            except Exception as e:
                current_app.logger.error(f"❌ Error creating checkout: {e}")
                flash(f"Erreur lors de la création : {str(e)}", "warning")
                return render_template(
                    "admin/checkout_form.html",
                    data=request.form.to_dict(),
                    is_edit=False,
                    **context,
                )

        return render_template("admin/checkout_form.html", data=initial_data, is_edit=False, **context)

    @app.route("/admin/checkouts/<record_id>/edit", methods=["GET", "POST"])
    @require_roles('administrator', 'manager', 'user')
    def admin_checkout_edit(record_id):
        context = get_checkout_form_context()

        try:
            data = get_checkout_detail(record_id)
            if not data:
                abort(404)

            if request.method == "POST":
                update_checkout(record_id, request.form, request.files)
                flash("Checkout modifié avec succès !", "success")
                return redirect(url_for("admin_checkout_detail", record_id=record_id))

            return render_template(
                "admin/checkout_form.html", data=data, is_edit=True, **context
            )
        except Exception as e:
            current_app.logger.error(f"❌ Error editing checkout: {e}")
            flash(f"Erreur lors de la modification : {str(e)}", "error")
            return redirect(url_for("admin_checkout_detail", record_id=record_id))

    @app.route("/admin/checkouts/<record_id>/delete", methods=["POST"])
    @require_roles('administrator', 'manager', 'user')
    def admin_checkout_delete(record_id):
        try:
            delete_checkout(record_id)
            flash("Checkout supprimé définitivement.", "success")
            return redirect(url_for("admin_checkouts_list"))
        except Exception as e:
            current_app.logger.error(f"❌ Error deleting checkout: {e}")
            flash(f"Erreur lors de la suppression : {str(e)}", "error")
            return redirect(url_for("admin_checkout_detail", record_id=record_id))

    @app.route("/admin/checkouts/<record_id>/seal", methods=["POST"])
    @require_roles('administrator', 'manager', 'user')
    def admin_checkout_seal(record_id):
        try:
            from services.public.checkout import generate_signing_token

            result = generate_signing_token(record_id)
            if not result:
                flash(
                    "Checkout introuvable ou erreur lors de la création du lien de signature.", "error")
                return redirect(url_for("admin_checkout_detail", record_id=record_id))

            token = result["token"]

            flash("La demande de scellement a été initiée et vous avez été redirigé vers la page de signature.", "success")
            return redirect(url_for("checkout_sign_page", token=token))

        except Exception as e:
            current_app.logger.error(f"❌ Error sealing checkout: {e}")
            flash(
                f"Erreur technique lors de la création du lien de signature : {str(e)}", "error")
            return redirect(url_for("admin_checkout_detail", record_id=record_id))
