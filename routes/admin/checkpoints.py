"""
Routes d'administration pour la gestion des points de contrôle des véhicules.
Permet de lister, créer et éditer les checkpoints : libellés, catégories,
indications par défaut, véhicules concernés et indications techniques par véhicule.
"""

import logging
from flask import current_app, flash, jsonify, redirect, render_template, request, url_for
from services.admin.vehicle_config import (
    create_checkpoint,
    delete_checkpoint,
    get_all_checkpoints,
    get_checkpoint_by_id,
    get_empty_checkpoint_for_create,
    reorder_checkpoints,
    update_checkpoint,
)
from utils.decorators import require_roles

logger = logging.getLogger(__name__)


def init_checkpoints_routes(app):
    """Initialise les routes d'administration pour les points de contrôle."""

    @app.route("/admin/checkpoints", methods=["GET"])
    @require_roles("administrator")
    def admin_checkpoints_list():
        """Liste tous les points de contrôle avec filtres et indicateurs."""
        try:
            checkpoints = get_all_checkpoints()

            total_count = len(checkpoints)
            security_count = sum(1 for c in checkpoints if c.get("category") == "Sécurité")
            equipment_count = sum(1 for c in checkpoints if c.get("category") == "Équipements")

            stats = {
                "total": total_count,
                "security": security_count,
                "equipment": equipment_count,
            }

            return render_template(
                "admin/checkpoints_list.html",
                checkpoints=checkpoints,
                stats=stats,
            )
        except Exception as e:
            logger.error(f"❌ Erreur lors du chargement des points de contrôle : {e}", exc_info=True)
            flash(f"Erreur lors du chargement des points de contrôle : {e}", "error")
            return redirect(url_for("admin_dashboard"))

    @app.route("/admin/checkpoints/new", methods=["GET", "POST"])
    @require_roles("administrator")
    def admin_checkpoint_new():
        """Formulaire de création d'un nouveau point de contrôle."""
        try:
            if request.method == "POST":
                new_cp = create_checkpoint(request.form)
                if new_cp:
                    flash(f"Point de contrôle « {new_cp.label} » créé avec succès.", "success")
                    return redirect(url_for("admin_checkpoints_list"))
                else:
                    flash("Impossible de créer le point de contrôle (nom obligatoire).", "error")

            checkpoint = get_empty_checkpoint_for_create()
            return render_template(
                "admin/checkpoint_form.html",
                checkpoint=checkpoint,
                is_new=True,
            )
        except Exception as e:
            logger.error(f"❌ Erreur lors de la création d'un point de contrôle : {e}", exc_info=True)
            flash(f"Erreur lors de la création : {e}", "error")
            return redirect(url_for("admin_checkpoints_list"))

    @app.route("/admin/checkpoints/<int:checkpoint_id>/edit", methods=["GET", "POST"])
    @require_roles("administrator")
    def admin_checkpoint_edit(checkpoint_id: int):
        """Formulaire d'édition d'un point de contrôle."""
        try:
            if request.method == "POST":
                success = update_checkpoint(checkpoint_id, request.form)
                if success:
                    flash("Point de contrôle mis à jour avec succès.", "success")
                    return redirect(url_for("admin_checkpoints_list"))
                else:
                    flash("Impossible de mettre à jour le point de contrôle (introuvable).", "error")
                    return redirect(url_for("admin_checkpoints_list"))

            checkpoint = get_checkpoint_by_id(checkpoint_id)
            if not checkpoint:
                flash("Point de contrôle introuvable.", "error")
                return redirect(url_for("admin_checkpoints_list"))

            return render_template(
                "admin/checkpoint_form.html",
                checkpoint=checkpoint,
                is_new=False,
            )
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'édition du point de contrôle {checkpoint_id} : {e}", exc_info=True)
            flash(f"Erreur lors de l'édition : {e}", "error")
            return redirect(url_for("admin_checkpoints_list"))

    @app.route("/admin/checkpoints/<int:checkpoint_id>/delete", methods=["POST"])
    @require_roles("administrator")
    def admin_checkpoint_delete(checkpoint_id: int):
        """Supprime un point de contrôle."""
        try:
            success, message = delete_checkpoint(checkpoint_id)
            if success:
                flash(message, "success")
            else:
                flash(message, "error")
            return redirect(url_for("admin_checkpoints_list"))
        except Exception as e:
            logger.error(f"❌ Erreur lors de la suppression du point de contrôle {checkpoint_id} : {e}", exc_info=True)
            flash(f"Erreur lors de la suppression : {e}", "error")
            return redirect(url_for("admin_checkpoints_list"))

    @app.route("/admin/api/checkpoints/reorder", methods=["PATCH", "POST"])
    @require_roles("administrator")
    def admin_api_checkpoints_reorder():
        """Met à jour l'ordre d'affichage des points de contrôle."""
        try:
            data = request.get_json(silent=True) or {}
            ids = data.get("ids", [])
            if not ids:
                return jsonify({"success": False, "error": "Aucun identifiant fourni"}), 400

            success = reorder_checkpoints(ids)
            if success:
                return jsonify({"success": True, "message": "Ordre mis à jour avec succès"})
            return jsonify({"success": False, "error": "Erreur lors de la réorganisation"}), 500
        except Exception as e:
            logger.error(f"❌ Erreur lors de la réorganisation des checkpoints : {e}", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 400
