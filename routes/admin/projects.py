from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from services.admin import (
    ReportNotFoundError,
    add_project_report,
    check_booking_conflicts,
    create_project,
    delete_project,
    delete_project_report,
    get_project_detail_context,
    get_project_for_duplicate,
    get_project_for_edit,
    get_project_form_context,
    list_projects,
    update_project,
    update_project_notes,
    update_project_report,
)
from models import ProjectReport
from models.db import db
from models.project_report import REPORT_CATEGORIES
from services.admin.project_reports import (
    generate_project_reports_pdf,
    report_item_context,
    restore_project_report,
    search_reports,
)
from utils.decorators import require_roles, session_is_admin, session_is_super_admin
from utils.entity_resolvers import resolve_project


projects_bp = Blueprint("admin_projects", __name__, url_prefix="/admin")
# ── CRUD Projets ──────────────────────────────────────────────


@projects_bp.route("/projects")
@require_roles("administrator", "manager", "commercial")
def admin_projects_list():
    try:
        q = request.args.get("q", "").strip()
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)

        pagination = list_projects(
            is_archive=False, q=q if q else None, page=page, per_page=per_page
        )
        return render_template(
            "admin/projects_list.html",
            projects=pagination.items,
            pagination=pagination,
            is_archive=False,
        )
    except Exception as e:
        current_app.logger.error(f"❌ Erreur dans admin_projects_list : {e}")
        flash("Erreur lors de la récupération des projets.", "error")
        return render_template(
            "admin/projects_list.html", projects=[], pagination=None, is_archive=False
        )


@projects_bp.route("/projects/archives")
@require_roles("administrator", "manager", "commercial")
def admin_projects_archives():
    try:
        q = request.args.get("q", "").strip()
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)

        pagination = list_projects(
            is_archive=True, q=q if q else None, page=page, per_page=per_page
        )
        return render_template(
            "admin/projects_list.html",
            projects=pagination.items,
            pagination=pagination,
            is_archive=True,
        )
    except Exception as e:
        current_app.logger.error(f"❌ Erreur dans admin_projects_archives : {e}")
        flash("Erreur lors de la récupération des archives.", "error")
        return render_template(
            "admin/projects_list.html", projects=[], pagination=None, is_archive=True
        )


@projects_bp.route("/projects/new", methods=["GET", "POST"])
@require_roles("administrator", "manager", "commercial")
def admin_project_new():
    duplicate_from = request.args.get("duplicate_from", type=int)
    if request.method == "GET" and duplicate_from:
        return redirect(
            url_for("admin_projects.admin_project_duplicate", record_id=duplicate_from)
        )

    context = get_project_form_context()

    if request.method == "POST":
        try:
            if not request.form.get("name"):
                flash("Le nom du projet est requis.", "error")
                return render_template(
                    "admin/project_form.html",
                    data=request.form,
                    is_edit=False,
                    **context,
                )
            created = create_project(request.form, user_id=session.get("admin_user_id"))
            flash("Projet créé avec succès !", "success")
            new_id = created.id if hasattr(created, "id") else created
            return redirect(
                url_for("admin_projects.admin_project_detail", record_id=new_id)
            )
        except Exception as e:
            from services.admin.utils import format_user_friendly_error

            current_app.logger.error(f"❌ Erreur lors de la création du projet : {e}")
            flash(
                format_user_friendly_error(e, "Erreur lors de la création du projet."),
                "error",
            )
            return render_template(
                "admin/project_form.html", data=request.form, is_edit=False, **context
            )

    return render_template("admin/project_form.html", is_edit=False, **context)


@projects_bp.route("/projects/<int:record_id>/duplicate", methods=["GET"])
@require_roles("administrator", "manager", "commercial")
def admin_project_duplicate(record_id):
    try:
        data = get_project_for_duplicate(record_id)
        if not data:
            abort(404)

        context = get_project_form_context()
        source_name = data.get("source_project_name", "")

        return render_template(
            "admin/project_form.html",
            data=data,
            is_edit=False,
            is_duplicate=True,
            source_project_id=record_id,
            source_project_name=source_name,
            **context,
        )
    except Exception as e:
        from services.admin.utils import format_user_friendly_error

        current_app.logger.error(
            f"❌ Erreur lors de la duplication du projet {record_id} : {e}"
        )
        flash(
            format_user_friendly_error(
                e, "Erreur lors de la préparation de la duplication du tournage."
            ),
            "error",
        )
        return redirect(
            url_for("admin_projects.admin_project_detail", record_id=record_id)
        )


@projects_bp.route("/projects/<int:record_id>/edit", methods=["GET", "POST"])
@require_roles("administrator", "manager", "commercial")
def admin_project_edit(record_id):
    context = get_project_form_context()

    try:
        if request.method == "POST":
            update_project(
                record_id, request.form, user_id=session.get("admin_user_id")
            )
            flash("Projet modifié avec succès !", "success")
            return redirect(
                url_for("admin_projects.admin_project_detail", record_id=record_id)
            )

        data = get_project_for_edit(record_id)
        if not data:
            abort(404)
        return render_template(
            "admin/project_form.html",
            data=data,
            is_edit=True,
            record_id=record_id,
            **context,
        )
    except Exception as e:
        from services.admin.utils import format_user_friendly_error

        current_app.logger.error(f"❌ Erreur lors de la modification du projet : {e}")
        flash(
            format_user_friendly_error(e, "Erreur lors de la modification du projet."),
            "error",
        )
        return redirect(url_for("admin_projects.admin_projects_list"))


@projects_bp.route("/projects/<int:record_id>/delete", methods=["POST"])
@require_roles("administrator", "manager", "commercial")
def admin_project_delete(record_id):
    try:
        delete_project(record_id, user_id=session.get("admin_user_id"))
        flash("Projet supprimé avec succès.", "success")
        return redirect(url_for("admin_projects.admin_projects_list"))
    except Exception as e:
        from services.admin.utils import format_user_friendly_error

        current_app.logger.error(f"❌ Erreur lors de la suppression du projet : {e}")
        flash(
            format_user_friendly_error(e, "Erreur lors de la suppression du projet."),
            "error",
        )
        return redirect(
            url_for("admin_projects.admin_project_edit", record_id=record_id)
        )


# ── Hub / Fiche Projet & Rapports Collectifs ──────────────────
@projects_bp.route("/projects/<int:record_id>", methods=["GET"])
@require_roles("administrator", "manager", "commercial", "user", "technicien")
def admin_project_detail(record_id):
    try:
        current_user_id = session.get("admin_user_id")
        is_admin = session_is_admin()

        context = get_project_detail_context(
            record_id, current_user_id=current_user_id, is_admin=is_admin,
            is_super_admin=session_is_super_admin(),
        )
        if not context:
            abort(404)

        return render_template("admin/project_detail.html", **context)
    except Exception as e:
        current_app.logger.error(f"❌ Erreur dans admin_project_detail : {e}")
        flash("Erreur lors de l'accès à la fiche projet.", "error")
        return redirect(url_for("admin_projects.admin_projects_list"))


@projects_bp.route("/projects/<string:project_code>", methods=["GET"])
@require_roles("administrator", "manager", "commercial", "user", "technicien")
def admin_project_detail_by_code(project_code):
    """Redirige les requêtes utilisant le code métier BVPR-* vers la route canonique avec ID."""
    p = resolve_project(project_code)
    if not p or p.deleted_at is not None:
        abort(404)
    return redirect(url_for("admin_projects.admin_project_detail", record_id=p.id))


@projects_bp.route("/projects/<int:record_id>/kdrive/resync", methods=["POST"])
@require_roles("administrator", "manager")
def admin_project_kdrive_resync(record_id):
    try:
        project = resolve_project(record_id)
        if not project or project.deleted_at is not None:
            abort(404)

        from services.common.kdrive import dispatch_create_project_tree

        dispatch_create_project_tree(project.id)
        flash("Synchronisation kDrive relancée.", "success")
        return redirect(
            url_for("admin_projects.admin_project_detail", record_id=record_id)
        )
    except Exception as e:
        current_app.logger.error(f"❌ Erreur resync kDrive : {e}")
        flash(f"Erreur lors de la synchronisation : {e}", "error")
        return redirect(
            url_for("admin_projects.admin_project_detail", record_id=record_id)
        )


@projects_bp.route("/projects/<int:record_id>/notes", methods=["POST"])
@require_roles("administrator", "manager", "commercial", "user", "technicien")
def admin_project_notes_edit(record_id):
    try:
        payload = request.get_json(silent=True) or request.form or {}
        notes = payload.get("notes", "")
        current_user_id = session.get("admin_user_id")

        project = update_project_notes(record_id, notes=notes, user_id=current_user_id)
        if not project:
            abort(404)

        if (
            request.is_json
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        ):
            return jsonify({"status": "success", "notes": project.notes or ""}), 200

        flash("Notes du projet enregistrées avec succès.", "success")
        return redirect(
            url_for("admin_projects.admin_project_detail", record_id=record_id)
        )
    except Exception as e:
        current_app.logger.error(f"❌ Erreur enregistrement note projet : {e}")
        if (
            request.is_json
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        ):
            return jsonify({"status": "error", "message": "Erreur serveur"}), 500
        flash(f"Erreur lors de l'enregistrement de la note : {str(e)}", "error")
        return redirect(
            url_for("admin_projects.admin_project_detail", record_id=record_id)
        )


@projects_bp.route(
    "/projects/<int:record_id>/vehicle/<string:vehicle_id>/toggle-road-legal",
    methods=["POST"],
)
@require_roles("administrator", "manager", "commercial", "user", "technicien")
def admin_project_vehicle_toggle_road_legal(record_id, vehicle_id):
    """Bascule le statut Road Legal (homologué route vs route fermée uniquement) d'un véhicule pour ce projet."""
    try:
        project = resolve_project(record_id)
        if not project or project.deleted_at is not None:
            return jsonify({"status": "error", "message": "Projet introuvable."}), 404

        payload = request.get_json(silent=True) or request.form or {}
        current_legal = project.is_vehicle_road_legal(vehicle_id)
        if "is_road_legal" in payload:
            target_legal = bool(payload.get("is_road_legal"))
        else:
            target_legal = not current_legal

        project.set_vehicle_road_legal(vehicle_id, target_legal)
        db.session.commit()

        return jsonify(
            {
                "status": "success",
                "vehicle_id": vehicle_id,
                "is_road_legal": target_legal,
                "label_fr": "Homologué route" if target_legal else "Route fermée",
            }
        ), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Erreur toggle road legal : {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ── Rapports d'équipe ──────────────────────────────────────────

_REPORT_ROLES = ("administrator", "manager", "commercial", "user", "technicien")


def _wants_json():
    return request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _report_payload():
    """Champs du formulaire de rapport (JSON, formulaire classique ou multipart)."""
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form


def _render_report_item(report):
    """HTML d'une carte de rapport, identique au rendu de la fiche projet (réponses AJAX)."""
    ctx = report_item_context(
        report, current_user_id=session.get("admin_user_id"), is_admin=session_is_admin()
    )
    return render_template("admin/_report_item.html", **ctx)


def _active_reports_count(record_id):
    return ProjectReport.active().filter_by(project_id=record_id).count()


def _report_response(record_id, anchor, *, message, category="success", status=200, payload=None):
    """Réponse unifiée des routes de rapports : JSON (XHR) ou flash + redirection."""
    if _wants_json():
        body = {"status": "success" if category == "success" else "error", "message": message}
        if category == "success":
            body.update(payload or {})
        return jsonify(body), status
    flash(message, category)
    return redirect(
        url_for("admin_projects.admin_project_detail", record_id=record_id) + f"#{anchor}"
    )


@projects_bp.route("/projects/<int:record_id>/reports", methods=["POST"])
@require_roles(*_REPORT_ROLES)
def admin_project_reports_add(record_id):
    payload = _report_payload()
    try:
        report = add_project_report(
            record_id,
            user_id=session.get("admin_user_id"),
            content=payload.get("content", ""),
            title=payload.get("title", ""),
            category=payload.get("category"),
            shoot_day=payload.get("shoot_day") or None,
            photos=request.files.getlist("photos"),
        )
        return _report_response(
            record_id, f"report-{report.id}", status=201, message="Rapport publié.",
            payload={
                "report": report.to_dict(),
                "html": _render_report_item(report),
                "count": _active_reports_count(record_id),
            },
        )
    except ValueError as ve:
        return _report_response(record_id, "reports", message=str(ve), category="error", status=400)
    except Exception as e:
        current_app.logger.error(f"❌ Erreur ajout rapport projet : {e}")
        return _report_response(
            record_id, "reports", message="Erreur lors de l'enregistrement du rapport.",
            category="error", status=500,
        )


@projects_bp.route(
    "/projects/<int:record_id>/reports/<int:report_id>/delete", methods=["POST"]
)
@require_roles(*_REPORT_ROLES)
def admin_project_report_delete(record_id, report_id):
    try:
        current_user_id = session.get("admin_user_id")
        delete_project_report(
            report_id,
            current_user_id=current_user_id,
            is_admin=session_is_admin(),
            project_id=record_id,
        )
        # « Annuler » n'est proposé qu'à qui pourra effectivement restaurer le rapport
        report = db.session.get(ProjectReport, report_id)
        can_restore = report is not None and report.can_be_restored_by(current_user_id, session_is_super_admin())
        return _report_response(
            record_id, "reports", message="Rapport supprimé.",
            payload={
                "count": _active_reports_count(record_id),
                "restore_url": url_for(
                    "admin_projects.admin_project_report_restore", record_id=record_id, report_id=report_id
                ) if can_restore else None,
            },
        )
    except ReportNotFoundError as nf:
        return _report_response(record_id, "reports", message=str(nf), category="error", status=404)
    except PermissionError as pe:
        return _report_response(record_id, "reports", message=str(pe), category="error", status=403)
    except Exception as e:
        current_app.logger.error(f"❌ Erreur suppression rapport projet : {e}")
        return _report_response(
            record_id, "reports", message="Erreur lors de la suppression.",
            category="error", status=500,
        )


@projects_bp.route(
    "/projects/<int:record_id>/reports/<int:report_id>/restore", methods=["POST"]
)
@require_roles(*_REPORT_ROLES)
def admin_project_report_restore(record_id, report_id):
    try:
        report = restore_project_report(
            report_id,
            current_user_id=session.get("admin_user_id"),
            is_super_admin=session_is_super_admin(),
            project_id=record_id,
        )
        return _report_response(
            record_id, f"report-{report.id}", message="Rapport restauré.",
            payload={
                "report": report.to_dict(),
                "html": _render_report_item(report),
                "count": _active_reports_count(record_id),
            },
        )
    except ReportNotFoundError as nf:
        return _report_response(record_id, "reports", message=str(nf), category="error", status=404)
    except PermissionError as pe:
        return _report_response(record_id, "reports", message=str(pe), category="error", status=403)
    except Exception as e:
        current_app.logger.error(f"❌ Erreur restauration rapport projet : {e}")
        return _report_response(
            record_id, "reports", message="Erreur lors de la restauration.",
            category="error", status=500,
        )


@projects_bp.route(
    "/projects/<int:record_id>/reports/<int:report_id>/edit", methods=["POST"]
)
@require_roles(*_REPORT_ROLES)
def admin_project_report_edit(record_id, report_id):
    payload = _report_payload()
    anchor = f"report-{report_id}"
    remove = payload.getlist("remove_photos") if hasattr(payload, "getlist") else payload.get("remove_photos", [])
    fields = {}
    if "category" in payload:
        fields["category"] = payload.get("category")
    if "shoot_day" in payload:
        fields["shoot_day"] = payload.get("shoot_day") or None
    try:
        report = update_project_report(
            report_id,
            current_user_id=session.get("admin_user_id"),
            content=payload.get("content", ""),
            title=payload.get("title", ""),
            is_admin=session_is_admin(),
            project_id=record_id,
            new_photos=request.files.getlist("photos"),
            remove_photos=remove,
            **fields,
        )
        return _report_response(
            record_id, anchor, message="Rapport modifié avec succès.",
            payload={"report": report.to_dict(), "html": _render_report_item(report)},
        )
    except ReportNotFoundError as nf:
        return _report_response(record_id, "reports", message=str(nf), category="error", status=404)
    except PermissionError as pe:
        return _report_response(record_id, anchor, message=str(pe), category="error", status=403)
    except ValueError as ve:
        return _report_response(record_id, anchor, message=str(ve), category="error", status=400)
    except Exception as e:
        current_app.logger.error(f"❌ Erreur modification rapport projet : {e}")
        return _report_response(
            record_id, anchor, message="Erreur lors de la modification.",
            category="error", status=500,
        )


@projects_bp.route("/projects/<int:record_id>/reports/export", methods=["GET"])
@require_roles(*_REPORT_ROLES)
def admin_project_reports_export(record_id):
    """Journal de bord du projet en PDF (filtres optionnels : ?category=…&day=AAAA-MM-JJ)."""
    try:
        pdf, filename = generate_project_reports_pdf(
            record_id,
            category=request.args.get("category"),
            shoot_day=request.args.get("day") or None,
            base_url=request.url_root,
        )
    except ValueError as ve:
        flash(str(ve), "error")
        return redirect(url_for("admin_projects.admin_project_detail", record_id=record_id) + "#reports")
    if pdf is None:
        abort(404)
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@projects_bp.route("/reports", methods=["GET"])
@require_roles(*_REPORT_ROLES)
def admin_reports_search():
    """Recherche transversale dans les rapports d'équipe de tous les projets."""
    filters = {
        "q": (request.args.get("q") or "").strip(),
        "category": (request.args.get("category") or "").strip(),
    }
    pagination = search_reports(
        query=filters["q"],
        category=filters["category"],
        page=request.args.get("page", 1, type=int),
        per_page=20,
    )
    return render_template(
        "admin/reports_search.html",
        pagination=pagination,
        reports=pagination.items,
        filters=filters,
        report_categories=[(k, label) for k, label, _ in REPORT_CATEGORIES],
    )


@projects_bp.route("/projects/<int:record_id>/print", methods=["GET"])
@require_roles("administrator", "manager", "commercial", "user", "technicien")
def admin_project_print(record_id):
    try:
        current_user_id = session.get("admin_user_id")
        is_admin = session_is_admin()

        context = get_project_detail_context(
            record_id, current_user_id=current_user_id, is_admin=is_admin,
            is_super_admin=session_is_super_admin(),
        )
        if not context:
            abort(404)

        return render_template("admin/project_detail.html", is_print=True, **context)
    except Exception as e:
        current_app.logger.error(f"❌ Erreur dans admin_project_print : {e}")
        flash("Erreur lors de la génération de la vue d'impression.", "error")
        return redirect(
            url_for("admin_projects.admin_project_detail", record_id=record_id)
        )


# ── API Détection Conflits de Réservation ──────────────────────
@projects_bp.route("/api/projects/check-conflicts", methods=["POST"])
@require_roles("administrator", "manager", "commercial")
def admin_api_check_conflicts():
    try:
        payload = request.get_json(silent=True) or request.form or {}
        start_date = (
            payload.get("start_date")
            or payload.get("departure_date")
            or payload.get("shoot_start")
        )
        end_date = (
            payload.get("end_date")
            or payload.get("return_date")
            or payload.get("shoot_end")
        )

        vehicle_ids = payload.get("vehicle_ids")
        if isinstance(vehicle_ids, str):
            vehicle_ids = [v.strip() for v in vehicle_ids.split(",") if v.strip()]
        elif vehicle_ids is None:
            vehicle_ids = []

        head_ids = payload.get("head_ids")
        if isinstance(head_ids, str):
            head_ids = [h.strip() for h in head_ids.split(",") if h.strip()]
        elif head_ids is None:
            head_ids = []

        exclude_id = (
            payload.get("project_id") or payload.get("record_id") or payload.get("id")
        )
        if str(exclude_id).strip() in ("", "null", "None", "undefined"):
            exclude_id = None

        date_mode = payload.get("date_mode", "continuous")
        is_immob = payload.get("is_immobilized_between")
        if is_immob is None:
            is_immob = True
        else:
            is_immob = (
                True if str(is_immob).lower() in ("true", "1", "yes", "on") else False
            )

        shoot_dates = payload.get("shoot_dates")
        if isinstance(shoot_dates, str):
            import json

            try:
                shoot_dates = json.loads(shoot_dates)
            except Exception:
                shoot_dates = [s.strip() for s in shoot_dates.split(",") if s.strip()]

        inter_shoot_statuses = payload.get("inter_shoot_statuses")
        if isinstance(inter_shoot_statuses, str):
            import json

            try:
                inter_shoot_statuses = json.loads(inter_shoot_statuses)
            except Exception:
                inter_shoot_statuses = []

        result = check_booking_conflicts(
            start_date_val=start_date,
            end_date_val=end_date,
            vehicle_ids=vehicle_ids,
            head_ids=head_ids,
            exclude_project_id=exclude_id,
            date_mode=date_mode,
            is_immobilized_between=is_immob,
            shoot_dates=shoot_dates,
            inter_shoot_statuses=inter_shoot_statuses,
        )
        return jsonify({"status": "success", "data": result}), 200
    except Exception as e:
        current_app.logger.error(f"❌ Erreur API check-conflicts : {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


def init_projects_routes(app):
    """Enregistre le blueprint admin_projects (compatibilité ascendante)."""
    if "admin_projects" not in app.blueprints:
        app.register_blueprint(projects_bp)
