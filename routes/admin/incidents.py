from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    Response,
    session,
    url_for,
)

from services.admin.incidents import (
    list_incidents,
    get_incident_detail,
    create_incident,
    update_incident,
    delete_incident,
    get_incident_form_context,
    generate_incident_pdf,
)
from utils.decorators import require_roles


def init_incidents_routes(app):
    # ── Gestion des Incidents de Tournage ─────────────────────────

    @app.route("/admin/incidents")
    @require_roles("administrator", "manager", "user", "commercial")
    def admin_incidents_list():
        try:
            status_filter = request.args.get("status")
            severity_filter = request.args.get("severity")
            category_filter = request.args.get("category")
            project_filter = request.args.get("project_id")
            query_filter = request.args.get("q")

            data = list_incidents(
                status=status_filter,
                severity=severity_filter,
                category=category_filter,
                project_id=project_filter,
                query=query_filter,
            )
            form_context = get_incident_form_context()

            return render_template(
                "admin/incidents_list.html",
                incidents=data["incidents"],
                stats=data["stats"],
                filters={
                    "status": status_filter,
                    "severity": severity_filter,
                    "category": category_filter,
                    "project_id": project_filter,
                    "q": query_filter,
                },
                context=form_context,
            )
        except Exception as e:
            current_app.logger.error(f"❌ Erreur dans admin_incidents_list : {e}")
            flash("Erreur lors de la récupération de la liste des incidents.", "error")
            return render_template(
                "admin/incidents_list.html",
                incidents=[],
                stats={
                    "total": 0,
                    "in_progress": 0,
                    "critical": 0,
                    "reparation": 0,
                    "total_estimated_cost": 0,
                    "total_actual_cost": 0,
                },
                filters={},
                context=get_incident_form_context(),
            )

    @app.route("/admin/incidents/<record_id>")
    @require_roles("administrator", "manager", "user", "commercial")
    def admin_incident_detail(record_id):
        try:
            data = get_incident_detail(record_id)
            if not data:
                abort(404)
            return render_template("admin/incident_detail.html", incident=data)
        except Exception as e:
            current_app.logger.error(f"❌ Erreur dans admin_incident_detail : {e}")
            flash("Erreur lors de la récupération du détail de l'incident.", "error")
            return redirect(url_for("admin_incidents_list"))

    @app.route("/admin/incidents/new", methods=["GET", "POST"])
    @require_roles("administrator", "manager", "user")
    def admin_incident_new():
        context = get_incident_form_context()

        if request.method == "POST":
            try:
                photos = request.files.getlist("photos")
                documents = request.files.getlist("documents")
                form_data = request.form.to_dict(flat=True)
                if not form_data.get("reported_by_id"):
                    form_data["reported_by_id"] = session.get("admin_user_id")
                incident = create_incident(
                    form_data=form_data,
                    uploaded_photos=photos,
                    uploaded_documents=documents,
                )
                flash(f"✅ Incident {incident.incident_number} déclaré avec succès.", "success")
                return redirect(url_for("admin_incident_detail", record_id=incident.id))
            except Exception as e:
                current_app.logger.error(f"❌ Erreur lors de la création d'incident : {e}")
                flash(f"Erreur lors de la déclaration de l'incident : {e}", "error")
                return render_template(
                    "admin/incident_form.html",
                    context=context,
                    incident=request.form,
                    is_edit=False,
                )

        # Pré-remplissage éventuel depuis un projet ou un contrôle
        initial_data = {
            "project_id": request.args.get("project_id", ""),
            "vehicle_id": request.args.get("vehicle_id", ""),
            "checkout_id": request.args.get("checkout_id", ""),
            "checkin_id": request.args.get("checkin_id", ""),
            "severity": "modere",
            "status": "signale",
            "category": "vehicule",
            "shooting_impact": "aucun",
        }

        return render_template(
            "admin/incident_form.html",
            context=context,
            incident=initial_data,
            is_edit=False,
        )

    @app.route("/admin/incidents/<record_id>/edit", methods=["GET", "POST"])
    @require_roles("administrator", "manager", "user")
    def admin_incident_edit(record_id):
        data = get_incident_detail(record_id)
        if not data:
            abort(404)

        context = get_incident_form_context()

        if request.method == "POST":
            try:
                photos = request.files.getlist("photos")
                documents = request.files.getlist("documents")
                removed_photos = request.form.getlist("remove_photos")
                incident = update_incident(
                    record_id=record_id,
                    form_data=request.form,
                    uploaded_photos=photos,
                    uploaded_documents=documents,
                    removed_photos=removed_photos,
                )
                flash(f"✅ Incident {incident.incident_number} mis à jour.", "success")
                return redirect(url_for("admin_incident_detail", record_id=incident.id))
            except Exception as e:
                current_app.logger.error(f"❌ Erreur lors de la mise à jour d'incident : {e}")
                flash(f"Erreur lors de la mise à jour : {e}", "error")

        return render_template(
            "admin/incident_form.html",
            context=context,
            incident=data,
            is_edit=True,
        )

    @app.route("/admin/incidents/<record_id>/delete", methods=["POST"])
    @require_roles("administrator", "manager")
    def admin_incident_delete(record_id):
        try:
            res = delete_incident(record_id, confirm=True)
            if res.get("success"):
                flash(res.get("message", "Incident supprimé."), "success")
            else:
                flash(res.get("message", "Échec de la suppression."), "error")
        except Exception as e:
            current_app.logger.error(f"❌ Erreur suppression incident : {e}")
            flash("Erreur lors de la suppression.", "error")

        return redirect(url_for("admin_incidents_list"))

    @app.route("/admin/incidents/<record_id>/pdf")
    @require_roles("administrator", "manager", "user", "commercial")
    def admin_incident_pdf(record_id):
        try:
            pdf_bytes, filename = generate_incident_pdf(record_id)
            return Response(
                pdf_bytes,
                mimetype="application/pdf",
                headers={
                    "Content-Disposition": f"inline; filename={filename}",
                    "Content-Type": "application/pdf",
                },
            )
        except Exception as e:
            current_app.logger.error(f"❌ Erreur génération PDF incident : {e}")
            flash(f"Erreur lors de la génération du PDF : {e}", "error")
            return redirect(url_for("admin_incident_detail", record_id=record_id))
