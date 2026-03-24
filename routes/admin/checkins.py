from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from services.admin import (
    create_checkin,
    delete_checkin,
    get_checkin_detail,
    get_checkin_form_context,
    list_checkins,
    update_checkin,
)
from utils.decorators import require_roles


def init_checkins_routes(app):
    # ── CRUD Retours (Check-ins) ──────────────────────────────────

    @app.route("/admin/checkins")
    @require_roles('administrator', 'manager', 'user')
    def admin_checkins_list():
        try:
            result = list_checkins()
            return render_template(
                "admin/checkins_list.html",
                checkins=result["checkins"],
            )
        except Exception as e:
            current_app.logger.error(f"❌ Erreur dans admin_checkins_list : {e}")
            flash("Erreur lors de la récupération de la liste.", "error")
            return render_template(
                "admin/checkins_list.html",
                checkins=[],
            )

    @app.route("/admin/checkins/<record_id>")
    @require_roles('administrator', 'manager', 'user')
    def admin_checkin_detail(record_id):
        try:
            data = get_checkin_detail(record_id)
            if not data:
                abort(404)
            return render_template("admin/checkin_detail.html", data=data, record_id=record_id)
        except Exception as e:
            current_app.logger.error(f"❌ Erreur dans admin_checkin_detail : {e}")
            flash("Erreur lors de la récupération du détail.", "error")
            return redirect(url_for("admin_checkins_list"))

    @app.route("/admin/checkins/new", methods=["GET", "POST"])
    @require_roles('administrator', 'manager', 'user')
    def admin_checkin_new():
        context = get_checkin_form_context()

        initial_data = {}
        if request.method == "GET":
            # Pré-remplissage depuis les paramètres URL si fournis
            if request.args.get("project_id"):
                initial_data["project_id"] = request.args.get("project_id")
            if request.args.get("vehicle_id"):
                initial_data["vehicle_id"] = request.args.get("vehicle_id")

        if request.method == "POST":
            try:
                create_checkin(request.form, request.files)
                flash("Checkin créé avec succès !", "success")
                return redirect(url_for("admin_checkins_list"))
            except Exception as e:
                current_app.logger.error(f"❌ Erreur lors de la création du retour : {e}")
                flash(f"Erreur lors de la création : {str(e)}", "warning")
                return render_template(
                    "admin/checkin_form.html",
                    data=request.form.to_dict(),
                    is_edit=False,
                    **context,
                )

        return render_template("admin/checkin_form.html", data=initial_data, is_edit=False, **context)

    @app.route("/admin/checkins/<record_id>/edit", methods=["GET", "POST"])
    @require_roles('administrator', 'manager', 'user')
    def admin_checkin_edit(record_id):
        context = get_checkin_form_context()

        try:
            data = get_checkin_detail(record_id)
            if not data:
                abort(404)

            if request.method == "POST":
                update_checkin(record_id, request.form, request.files)
                flash("Checkin modifié avec succès !", "success")
                return redirect(url_for("admin_checkin_detail", record_id=record_id))

            return render_template(
                "admin/checkin_form.html", data=data, is_edit=True, **context
            )
        except Exception as e:
            current_app.logger.error(f"❌ Erreur lors de la modification du retour : {e}")
            flash(f"Erreur lors de la modification : {str(e)}", "error")
            return redirect(url_for("admin_checkin_detail", record_id=record_id))

    @app.route("/admin/checkins/<record_id>/delete", methods=["POST"])
    @require_roles('administrator', 'manager', 'user')
    def admin_checkin_delete(record_id):
        try:
            delete_checkin(record_id)
            flash("Checkin supprimé définitivement.", "success")
            return redirect(url_for("admin_checkins_list"))
        except Exception as e:
            current_app.logger.error(f"❌ Erreur lors de la suppression du retour : {e}")
            flash(f"Erreur lors de la suppression : {str(e)}", "error")
            return redirect(url_for("admin_checkin_detail", record_id=record_id))

    @app.route("/admin/checkins/<record_id>/seal", methods=["POST"])
    @require_roles('administrator', 'manager', 'user')
    def admin_checkin_seal(record_id):
        try:
            from services.common.signatures import generate_inspection_token
            token = generate_inspection_token(record_id, "checkin")
            if not token:
                flash(
                    "Checkin introuvable ou erreur lors de la création du lien de signature.", "error")
                return redirect(url_for("admin_checkin_detail", record_id=record_id))


            # The generate_signing_token already sets status to "À signer"
            flash("La demande de scellement a été initiée et vous avez été redirigé vers la page de signature.", "success")
            return redirect(url_for("checkin_sign_page", token=token["token"]))

        except Exception as e:
            current_app.logger.error(f"❌ Erreur lors du scellement du retour : {e}")
            flash(
                f"Erreur technique lors de la création du lien de signature : {str(e)}", "error")
            return redirect(url_for("admin_checkin_detail", record_id=record_id))
