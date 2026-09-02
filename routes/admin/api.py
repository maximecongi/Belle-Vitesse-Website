from flask import (
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from services.admin.calendar import get_calendar_events
from services.admin.vehicle_config import (
    get_vehicles_with_config,
    save_vehicle_checkpoint_config,
)
from utils.checkpoints import ALL_POSSIBLE_CHECKPOINTS
from utils.decorators import require_roles


def init_api_routes(app):
    # ── API Administrative ────────────────────────────────────────

    @app.route("/admin/api/events")
    @require_roles('administrator', 'manager', 'commercial', 'user')
    def admin_api_events():
        try:
            events = get_calendar_events()
            return jsonify(events)
        except Exception as e:
            current_app.logger.error(f"❌ Erreur dans admin_api_events : {e}")
            return jsonify([]), 500

    def _handle_status_update(model, record_id):
        from models import db
        from services.admin.status_mapping import get_inspection_key
        try:
            record = db.session.get(model, record_id)
            if not record:
                return jsonify({"error": "Not found"}), 404

            if request.method == "POST":
                data = request.get_json()
                new_status = data.get("status") if data else None
                if not new_status:
                    return jsonify({"error": "Missing status"}), 400

                record.status = new_status
                db.session.commit()
                from services.admin.status_mapping import INSPECTION_STATUS_MAP
                status_id = get_inspection_key(record.status)
                status_label = INSPECTION_STATUS_MAP.get(status_id, status_id)
                return jsonify({
                    "status": status_label, 
                    "status_id": status_id,
                    "message": "Statut mis à jour avec succès"
                })

            status_id = get_inspection_key(record.status)
            from services.admin.status_mapping import INSPECTION_STATUS_MAP
            status_label = INSPECTION_STATUS_MAP.get(status_id, status_id)
            return jsonify({
                "status": status_label,
                "status_id": status_id
            })
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"❌ Erreur lors de la mise à jour du statut : {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/admin/api/checkouts/<int:record_id>/status", methods=["GET", "POST"])
    @require_roles('administrator', 'manager', 'user')
    def admin_api_checkout_status(record_id):
        from models import CheckoutVehicle
        return _handle_status_update(CheckoutVehicle, record_id)

    @app.route("/admin/api/checkins/<int:record_id>/status", methods=["GET", "POST"])
    @require_roles('administrator', 'manager', 'user')
    def admin_api_checkin_status(record_id):
        from models import CheckinVehicle
        return _handle_status_update(CheckinVehicle, record_id)

    @app.route("/admin/vehicle-configs")
    @require_roles('administrator')
    def admin_vehicle_configs():
        try:
            vehicles = get_vehicles_with_config()
            return render_template(
                "admin/vehicle_configs.html",
                vehicles=vehicles,
                possible_checkpoints=ALL_POSSIBLE_CHECKPOINTS
            )
        except Exception as e:
            current_app.logger.error(f"❌ Erreur dans admin_vehicle_configs : {e}")
            flash(
                f"Erreur lors du chargement des configurations: {e}", "error")
            return redirect(url_for('admin_dashboard'))

    @app.route("/admin/api/vehicle-configs", methods=["POST"])
    @require_roles('administrator')
    def admin_api_save_vehicle_config():
        try:
            data = request.get_json()
            vehicle_id = data.get("vehicle_id")
            enabled_keys = data.get("enabled_keys", [])

            if not vehicle_id:
                return jsonify({"error": "Missing vehicle_id"}), 400

            save_vehicle_checkpoint_config(vehicle_id, enabled_keys)
            return jsonify({"success": True})
        except Exception as e:
            current_app.logger.error(
                f"❌ Erreur dans admin_api_save_vehicle_config : {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/admin/api/search")
    @require_roles('administrator', 'manager', 'commercial', 'user')
    def admin_api_search():
        """Recherche globale multi-entités pour la Command Palette (Cmd+K)."""
        q = request.args.get('q', '').strip()
        if not q:
            return jsonify({"results": []})

        query_lower = q.lower()
        results = []

        # Rôle de l'utilisateur connecté
        user_role = session.get('admin_user_role', 'user')
        from utils.decorators import normalize_role
        role_norm = normalize_role(user_role)
        is_manager_or_higher = role_norm in (
            'manager', 'administrator', 'administrateur',
            'super administrator', 'super administrateur'
        )
        is_admin_or_higher = role_norm in (
            'administrator', 'administrateur',
            'super administrator', 'super administrateur'
        )

        # 1. Navigation & Actions rapides
        pages_and_actions = [
            {"title": "Tableau de bord", "subtitle": "Vue d'ensemble", "url": url_for("admin_dashboard"), "category": "Page", "icon": "layout", "roles": ['all']},
            {"title": "Nouveau Projet", "subtitle": "Créer un nouveau tournage", "url": url_for("admin_project_new"), "category": "Action", "icon": "plus", "roles": ['manager', 'commercial', 'admin']},
            {"title": "Projets (En cours)", "subtitle": "Tournages en préparation ou en cours", "url": url_for("admin_projects_list"), "category": "Page", "icon": "folder", "roles": ['manager', 'commercial', 'admin']},
            {"title": "Archives des Projets", "subtitle": "Projets terminés et archivés", "url": url_for("admin_projects_archives"), "category": "Page", "icon": "archive", "roles": ['manager', 'commercial', 'admin']},
            {"title": "Nouveau Check-out", "subtitle": "Effectuer un contrôle de départ", "url": url_for("admin_checkout_new"), "category": "Action", "icon": "truck", "roles": ['all']},
            {"title": "Check-outs", "subtitle": "Historique des contrôles de départ", "url": url_for("admin_checkouts_list"), "category": "Page", "icon": "clipboard", "roles": ['all']},
            {"title": "Nouveau Check-in", "subtitle": "Effectuer un contrôle de retour", "url": url_for("admin_checkin_new"), "category": "Action", "icon": "check-circle", "roles": ['all']},
            {"title": "Check-ins", "subtitle": "Historique des contrôles de retour", "url": url_for("admin_checkins_list"), "category": "Page", "icon": "clipboard", "roles": ['all']},
            {"title": "Calendrier", "subtitle": "Planning et réservations", "url": url_for("admin_calendar"), "category": "Page", "icon": "calendar", "roles": ['manager', 'commercial', 'admin']},
            {"title": "Tarification & Pre-quotes", "subtitle": "Grille tarifaire et devis", "url": url_for("admin_pricing"), "category": "Page", "icon": "tag", "roles": ['manager', 'commercial', 'admin']},
            {"title": "Configurations Véhicules", "subtitle": "Checkpoints et équipements", "url": url_for("admin_vehicle_configs"), "category": "Page", "icon": "settings", "roles": ['admin']},
            {"title": "Équipe & Utilisateurs", "subtitle": "Gestion des accès et collaborateurs", "url": url_for("admin_users_list"), "category": "Page", "icon": "users", "roles": ['manager', 'admin']},
            {"title": "Newsletter", "subtitle": "Abonnés et composition de campagnes", "url": url_for("admin_newsletter_dashboard"), "category": "Page", "icon": "mail", "roles": ['manager', 'admin']},
            {"title": "Générateur de Signature", "subtitle": "Générer la signature email officielle", "url": url_for("admin_signature_generator"), "category": "Outil", "icon": "pen", "roles": ['all']},
            {"title": "Documentation Technique", "subtitle": "Guides et documentations internes", "url": url_for("admin_docs_index"), "category": "Outil", "icon": "book", "roles": ['admin']},
        ]

        for item in pages_and_actions:
            allowed = 'all' in item['roles']
            if not allowed:
                if 'admin' in item['roles'] and is_admin_or_higher:
                    allowed = True
                elif 'manager' in item['roles'] and is_manager_or_higher:
                    allowed = True
                elif 'commercial' in item['roles'] and role_norm == 'commercial':
                    allowed = True
            if not allowed:
                continue

            searchable = f"{item['title']} {item['subtitle']}".lower()
            if query_lower in searchable:
                results.append({
                    "title": item["title"],
                    "subtitle": item["subtitle"],
                    "url": item["url"],
                    "category": item["category"],
                    "icon": item["icon"]
                })

        # 2. Projets
        if is_manager_or_higher or role_norm == 'commercial':
            try:
                from models import Project
                from sqlalchemy.orm import joinedload
                projects = Project.query.filter(Project.deleted_at.is_(None)).options(
                    joinedload(Project.production)
                ).order_by(Project.departure_date.desc()).limit(100).all()

                for p in projects:
                    p_name = p.name or ""
                    p_code = p.project_id or ""
                    prod_name = p.production.name if p.production else ""
                    searchable = f"{p_code} {p_name} {prod_name}".lower()

                    if query_lower in searchable:
                        sub = f"{p_code}"
                        if prod_name:
                            sub += f" • {prod_name}"
                        results.append({
                            "title": p_name,
                            "subtitle": sub,
                            "url": url_for("admin_project_edit", record_id=p.id),
                            "category": "Projet",
                            "icon": "folder"
                        })
                        if len(results) >= 20:
                            break
            except Exception as e:
                current_app.logger.warning(f"⚠️ Erreur recherche projets : {e}")

        # 3. Véhicules
        try:
            from utils.database import get_vehicles
            vehicles = get_vehicles() or []
            for v in vehicles:
                fields = v.get("fields", {})
                v_name = fields.get("Nom") or fields.get("name") or ""
                v_model = fields.get("Modèle") or fields.get("model") or ""
                searchable = f"{v_name} {v_model}".lower()
                if query_lower in searchable and v_name:
                    results.append({
                        "title": v_name,
                        "subtitle": v_model or "Véhicule Belle Vitesse",
                        "url": url_for("admin_vehicle_configs") if is_admin_or_higher else url_for("admin_checkouts_list"),
                        "category": "Véhicule",
                        "icon": "truck"
                    })
                    if len(results) >= 25:
                        break
        except Exception as e:
            current_app.logger.warning(f"⚠️ Erreur recherche véhicules : {e}")

        # 4. Contacts
        if is_manager_or_higher or role_norm == 'commercial':
            try:
                from models import Contact
                contacts = Contact.query.limit(100).all()
                for c in contacts:
                    c_name = f"{c.first_name} {c.last_name}"
                    c_job = c.job_title or ""
                    searchable = f"{c_name} {c_job}".lower()
                    if query_lower in searchable:
                        results.append({
                            "title": c_name,
                            "subtitle": c_job or "Contact professionnel",
                            "url": url_for("admin_contacts_list"),
                            "category": "Contact",
                            "icon": "user"
                        })
                        if len(results) >= 30:
                            break
            except Exception as e:
                current_app.logger.warning(f"⚠️ Erreur recherche contacts : {e}")

        return jsonify({"results": results[:20]})
