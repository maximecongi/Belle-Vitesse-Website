"""
Routes d'administration pour les inspections (Check-outs et Check-ins) — couche HTTP factorisée.

Définit un gestionnaire générique d'enregistrement des routes CRUD d'administration.
"""

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
    create_checkout,
    delete_checkin,
    delete_checkout,
    get_checkin_detail,
    get_checkin_form_context,
    get_checkout_detail,
    get_checkout_form_context,
    list_checkins,
    list_checkouts,
    update_checkin,
    update_checkout,
)
from utils.decorators import require_roles


def _get_admin_inspection_config(mode):
    if mode == "checkout":
        return {
            "mode": "checkout",
            "plural": "checkouts",
            "label_fr": "départ",
            "label_title": "Checkout",
            "list_func": list_checkouts,
            "get_detail_func": get_checkout_detail,
            "get_context_func": get_checkout_form_context,
            "create_func": create_checkout,
            "update_func": update_checkout,
            "delete_func": delete_checkout,
            "template_list": "admin/checkouts_list.html",
            "template_detail": "admin/checkout_detail.html",
            "template_form": "admin/checkout_form.html",
        }
    elif mode == "checkin":
        return {
            "mode": "checkin",
            "plural": "checkins",
            "label_fr": "retour",
            "label_title": "Checkin",
            "list_func": list_checkins,
            "get_detail_func": get_checkin_detail,
            "get_context_func": get_checkin_form_context,
            "create_func": create_checkin,
            "update_func": update_checkin,
            "delete_func": delete_checkin,
            "template_list": "admin/checkins_list.html",
            "template_detail": "admin/checkin_detail.html",
            "template_form": "admin/checkin_form.html",
        }
    raise ValueError(f"Unknown admin inspection mode: {mode}")


def register_admin_inspection_routes(app, mode):
    """
    Enregistre l'ensemble des routes d'administration pour les inspections (checkout ou checkin).
    Préserve strictement tous les noms d'endpoints Flask originaux.
    """
    cfg = _get_admin_inspection_config(mode)
    plural = cfg["plural"]
    label_fr = cfg["label_fr"]
    label_title = cfg["label_title"]
    list_func = cfg["list_func"]
    get_detail_func = cfg["get_detail_func"]
    get_context_func = cfg["get_context_func"]
    create_func = cfg["create_func"]
    update_func = cfg["update_func"]
    delete_func = cfg["delete_func"]
    template_list = cfg["template_list"]
    template_detail = cfg["template_detail"]
    template_form = cfg["template_form"]

    endpoint_list = f"admin_{plural}_list"
    endpoint_detail = f"admin_{mode}_detail"
    endpoint_new = f"admin_{mode}_new"
    endpoint_edit = f"admin_{mode}_edit"
    endpoint_delete = f"admin_{mode}_delete"
    endpoint_seal = f"admin_{mode}_seal"
    sign_page_endpoint = f"{mode}_sign_page"

    # 1. Liste des inspections
    @app.route(f"/admin/{plural}", endpoint=endpoint_list)
    @require_roles('administrator', 'manager', 'user')
    def admin_inspection_list():
        try:
            result = list_func()
            return render_template(
                template_list,
                **{plural: result[plural]},
            )
        except Exception as e:
            current_app.logger.error(f"❌ Erreur dans {endpoint_list} : {e}")
            flash("Erreur lors de la récupération de la liste.", "error")
            return render_template(
                template_list,
                **{plural: []},
            )

    # 2. Détail d'une inspection
    @app.route(f"/admin/{plural}/<record_id>", endpoint=endpoint_detail)
    @require_roles('administrator', 'manager', 'user')
    def admin_inspection_detail(record_id):
        try:
            data = get_detail_func(record_id)
            if not data:
                abort(404)
            return render_template(template_detail, data=data, record_id=record_id)
        except Exception as e:
            current_app.logger.error(f"❌ Erreur dans {endpoint_detail} : {e}")
            flash("Erreur lors de la récupération du détail.", "error")
            return redirect(url_for(endpoint_list))

    # 3. Création d'une inspection
    @app.route(f"/admin/{plural}/new", methods=["GET", "POST"], endpoint=endpoint_new)
    @require_roles('administrator', 'manager', 'user')
    def admin_inspection_new():
        context = get_context_func()
        initial_data = {}

        if request.method == "GET":
            if request.args.get("project_id"):
                initial_data["project_id"] = request.args.get("project_id")
            if request.args.get("vehicle_id"):
                initial_data["vehicle_id"] = request.args.get("vehicle_id")

        if request.method == "POST":
            try:
                create_func(request.form, request.files)
                flash(f"{label_title} créé avec succès !", "success")
                return redirect(url_for(endpoint_list))
            except Exception as e:
                current_app.logger.error(f"❌ Erreur lors de la création du {label_fr} : {e}")
                flash(f"Erreur lors de la création : {str(e)}", "warning")
                return render_template(
                    template_form,
                    data=request.form.to_dict(),
                    is_edit=False,
                    **context,
                )

        return render_template(template_form, data=initial_data, is_edit=False, **context)

    # 4. Modification d'une inspection
    @app.route(f"/admin/{plural}/<record_id>/edit", methods=["GET", "POST"], endpoint=endpoint_edit)
    @require_roles('administrator', 'manager', 'user')
    def admin_inspection_edit(record_id):
        context = get_context_func()

        try:
            data = get_detail_func(record_id)
            if not data:
                abort(404)

            if request.method == "POST":
                update_func(record_id, request.form, request.files)
                flash(f"{label_title} modifié avec succès !", "success")
                return redirect(url_for(endpoint_detail, record_id=record_id))

            return render_template(
                template_form, data=data, is_edit=True, **context
            )
        except Exception as e:
            current_app.logger.error(f"❌ Erreur lors de la modification du {label_fr} : {e}")
            flash(f"Erreur lors de la modification : {str(e)}", "error")
            return redirect(url_for(endpoint_detail, record_id=record_id))

    # 5. Suppression d'une inspection
    @app.route(f"/admin/{plural}/<record_id>/delete", methods=["POST"], endpoint=endpoint_delete)
    @require_roles('administrator', 'manager', 'user')
    def admin_inspection_delete(record_id):
        try:
            delete_func(record_id)
            flash(f"{label_title} supprimé définitivement.", "success")
            return redirect(url_for(endpoint_list))
        except Exception as e:
            current_app.logger.error(f"❌ Erreur lors de la suppression du {label_fr} : {e}")
            flash(f"Erreur lors de la suppression : {str(e)}", "error")
            return redirect(url_for(endpoint_detail, record_id=record_id))

    # 6. Scellement d'une inspection
    @app.route(f"/admin/{plural}/<record_id>/seal", methods=["POST"], endpoint=endpoint_seal)
    @require_roles('administrator', 'manager', 'user')
    def admin_inspection_seal(record_id):
        try:
            from services.common.signatures import generate_inspection_token

            token = generate_inspection_token(record_id, mode)
            if not token:
                flash(
                    f"{label_title} introuvable ou erreur lors de la création du lien de signature.", "error")
                return redirect(url_for(endpoint_detail, record_id=record_id))

            flash("La demande de scellement a été initiée et vous avez été redirigé vers la page de signature.", "success")
            return redirect(url_for(sign_page_endpoint, token=token["token"]))

        except Exception as e:
            current_app.logger.error(f"❌ Erreur lors du scellement du {label_fr} : {e}")
            flash(
                f"Erreur technique lors de la création du lien de signature : {str(e)}", "error")
            return redirect(url_for(endpoint_detail, record_id=record_id))
