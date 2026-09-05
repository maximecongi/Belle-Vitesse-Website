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
            current_app.logger.error(
                f"❌ Erreur lors de la mise à jour du statut : {e}")
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
            current_app.logger.error(
                f"❌ Erreur dans admin_vehicle_configs : {e}")
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

        q = request.args.get('q', '').strip()
        if not q:
            # Suggestions logiques et prioritaires au chargement initial du modal
            default_suggestions = []

            if is_manager_or_higher or role_norm == 'commercial':
                default_suggestions.append({
                    "title": "Nouveau Projet",
                    "subtitle": "Créer un nouveau tournage",
                    "url": url_for("admin_project_new"),
                    "category": "Action",
                    "icon": "plus"
                })

            default_suggestions.append({
                "title": "Nouveau Check-out",
                "subtitle": "Effectuer un contrôle de départ véhicule",
                "url": url_for("admin_checkout_new"),
                "category": "Action",
                "icon": "truck"
            })

            default_suggestions.append({
                "title": "Nouveau Check-in",
                "subtitle": "Effectuer un contrôle de retour véhicule",
                "url": url_for("admin_checkin_new"),
                "category": "Action",
                "icon": "clipboard"
            })

            default_suggestions.append({
                "title": "Déclarer un Incident",
                "subtitle": "Signaler une panne ou dommage en tournage",
                "url": url_for("admin_incident_new"),
                "category": "Action",
                "icon": "alert"
            })

            if is_manager_or_higher or role_norm == 'commercial':
                default_suggestions.append({
                    "title": "Projets (En cours)",
                    "subtitle": "Tournages en préparation ou en cours",
                    "url": url_for("admin_projects_list"),
                    "category": "Page",
                    "icon": "folder"
                })

                # Projets en cours uniquement (s'il n'y en a pas, ne rien mettre)
                try:
                    from datetime import date
                    from models import Project
                    from sqlalchemy.orm import joinedload

                    today = date.today()
                    all_active_projects = Project.query.filter(
                        Project.deleted_at.is_(None)
                    ).options(
                        joinedload(Project.production)
                    ).all()

                    for p in all_active_projects:
                        start_d = p.departure_date or p.shoot_start_date
                        end_d = p.return_date or p.shoot_end_date or start_d

                        # Un projet est en cours si le tournage/départ a commencé et que le retour n'est pas passé
                        if start_d and start_d <= today and (not end_d or end_d >= today):
                            p_name = p.name or "Projet sans nom"
                            p_code = p.project_id or ""
                            prod_name = p.production.name if p.production else ""
                            sub_parts = ["En cours"]
                            if p_code:
                                sub_parts.append(p_code)
                            if prod_name:
                                sub_parts.append(prod_name)

                            default_suggestions.append({
                                "title": p_name,
                                "subtitle": " • ".join(sub_parts),
                                "url": url_for("admin_projects_list", q=p_code or p_name),
                                "category": "Projet",
                                "icon": "folder"
                            })
                except Exception as e:
                    current_app.logger.warning(
                        f"⚠️ Erreur suggestions projets en cours : {e}")

                default_suggestions.append({
                    "title": "Nouvelle Production",
                    "subtitle": "Créer une société de production",
                    "url": url_for("admin_production_new"),
                    "category": "Action",
                    "icon": "plus"
                })
                default_suggestions.append({
                    "title": "Nouveau Contact",
                    "subtitle": "Ajouter un contact professionnel",
                    "url": url_for("admin_contact_new"),
                    "category": "Action",
                    "icon": "user"
                })
                default_suggestions.append({
                    "title": "Productions",
                    "subtitle": "Annuaire des sociétés de production",
                    "url": url_for("admin_productions_list"),
                    "category": "Page",
                    "icon": "building"
                })

            return jsonify({"results": default_suggestions})

        # Détection d'un préfixe de ciblage optionnel (ex: prod:..., contact:..., p:..., etc.)
        scope = 'all'
        if ':' in q:
            prefix, remainder = q.split(':', 1)
            prefix = prefix.strip().lower()
            if prefix in ('prod', 'production', 'productions'):
                scope = 'production'
                q = remainder.strip()
            elif prefix in ('contact', 'contacts', 'c'):
                scope = 'contact'
                q = remainder.strip()
            elif prefix in ('projet', 'projets', 'project', 'projects', 'p'):
                scope = 'project'
                q = remainder.strip()
            elif prefix in ('vehicule', 'véhicule', 'vehicules', 'véhicules', 'v'):
                scope = 'vehicle'
                q = remainder.strip()

        query_lower = q.lower()
        import unicodedata

        def normalize_str(s):
            if not s:
                return ""
            return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()

        query_norm = normalize_str(q)
        results = []

        # 1. Navigation & Actions rapides (uniquement si scope 'all')
        if scope == 'all':
            pages_and_actions = [
                {"title": "Tableau de bord", "subtitle": "Vue d'ensemble", "url": url_for(
                    "admin_dashboard"), "category": "Page", "icon": "layout", "roles": ['all']},
                {"title": "Nouveau Projet", "subtitle": "Créer un nouveau tournage", "url": url_for(
                    "admin_project_new"), "category": "Action", "icon": "plus", "roles": ['manager', 'commercial', 'admin']},
                {"title": "Projets (En cours)", "subtitle": "Tournages en préparation ou en cours", "url": url_for(
                    "admin_projects_list"), "category": "Page", "icon": "folder", "roles": ['manager', 'commercial', 'admin']},
                {"title": "Archives des Projets", "subtitle": "Projets terminés et archivés", "url": url_for(
                    "admin_projects_archives"), "category": "Page", "icon": "archive", "roles": ['manager', 'commercial', 'admin']},
                {"title": "Productions", "subtitle": "Liste des sociétés clientes", "url": url_for(
                    "admin_productions_list"), "category": "Page", "icon": "building", "roles": ['manager', 'commercial', 'admin']},
                {"title": "Nouvelle Production", "subtitle": "Créer une société de production", "url": url_for(
                    "admin_production_new"), "category": "Action", "icon": "plus", "roles": ['manager', 'commercial', 'admin']},
                {"title": "Contacts", "subtitle": "Annuaire des contacts professionnels", "url": url_for(
                    "admin_contacts_list"), "category": "Page", "icon": "user", "roles": ['manager', 'commercial', 'admin']},
                {"title": "Nouveau Contact", "subtitle": "Ajouter un contact professionnel", "url": url_for(
                    "admin_contact_new"), "category": "Action", "icon": "plus", "roles": ['manager', 'commercial', 'admin']},
                {"title": "Nouveau Check-out", "subtitle": "Effectuer un contrôle de départ",
                    "url": url_for("admin_checkout_new"), "category": "Action", "icon": "truck", "roles": ['all']},
                {"title": "Check-outs", "subtitle": "Historique des contrôles de départ", "url": url_for(
                    "admin_checkouts_list"), "category": "Page", "icon": "clipboard", "roles": ['all']},
                {"title": "Nouveau Check-in", "subtitle": "Effectuer un contrôle de retour", "url": url_for(
                    "admin_checkin_new"), "category": "Action", "icon": "check-circle", "roles": ['all']},
                {"title": "Check-ins", "subtitle": "Historique des contrôles de retour", "url": url_for(
                    "admin_checkins_list"), "category": "Page", "icon": "clipboard", "roles": ['all']},
                {"title": "Gestion des Incidents", "subtitle": "Suivi des pannes, dommages et sinistres", "url": url_for(
                    "admin_incidents_list"), "category": "Page", "icon": "alert", "roles": ['all']},
                {"title": "Déclarer un Incident", "subtitle": "Signaler une anomalie en tournage", "url": url_for(
                    "admin_incident_new"), "category": "Action", "icon": "alert", "roles": ['all']},
                {"title": "Calendrier Matériel", "subtitle": "Disponibilités et planning des équipements", "url": url_for(
                    "admin_booking"), "category": "Page", "icon": "calendar", "roles": ['manager', 'commercial', 'admin']},
                {"title": "Abonnements Calendrier (ICS)", "subtitle": "Flux iCal et synchronisation des agendas", "url": url_for(
                    "admin_calendar"), "category": "Page", "icon": "calendar", "roles": ['manager', 'commercial', 'admin']},
                {"title": "Flotte & Parc", "subtitle": "Parc de véhicules, départs, retours et incidents",
                    "url": url_for("admin_fleet_list"), "category": "Page", "icon": "truck", "roles": ['all']},
                {"title": "Tarification & Pre-quotes", "subtitle": "Grille tarifaire et devis", "url": url_for(
                    "admin_pricing"), "category": "Page", "icon": "tag", "roles": ['manager', 'commercial', 'admin']},
                {"title": "Configurations Véhicules", "subtitle": "Checkpoints et équipements", "url": url_for(
                    "admin_vehicle_configs"), "category": "Page", "icon": "settings", "roles": ['admin']},
                {"title": "Équipe & Utilisateurs", "subtitle": "Gestion des accès et collaborateurs", "url": url_for(
                    "admin_users_list"), "category": "Page", "icon": "users", "roles": ['manager', 'admin']},
                {"title": "Newsletter", "subtitle": "Abonnés et composition de campagnes", "url": url_for(
                    "admin_newsletter_dashboard"), "category": "Page", "icon": "mail", "roles": ['manager', 'admin']},
                {"title": "Générateur de Signature", "subtitle": "Générer la signature email officielle", "url": url_for(
                    "admin_signature_generator"), "category": "Outil", "icon": "pen", "roles": ['all']},
                {"title": "Documentation Technique", "subtitle": "Guides et documentations internes", "url": url_for(
                    "admin_docs_index"), "category": "Outil", "icon": "book", "roles": ['admin']},
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

                searchable = f"{item['title']} {item['subtitle']}"
                if query_lower in searchable.lower() or query_norm in normalize_str(searchable):
                    results.append({
                        "title": item["title"],
                        "subtitle": item["subtitle"],
                        "url": item["url"],
                        "category": item["category"],
                        "icon": item["icon"]
                    })

        # 2. Productions (ciblage avec ?q=)
        if (is_manager_or_higher or role_norm == 'commercial') and scope in ('all', 'production'):
            try:
                from models import Production
                productions = Production.query.order_by(
                    Production.name.asc()).limit(150).all()
                for prod in productions:
                    prod_name = prod.name or ""
                    prod_addr = prod.address or ""
                    prod_mail = prod.mail or ""
                    prod_phone = prod.phone or ""
                    searchable = f"{prod_name} {prod_addr} {prod_mail} {prod_phone}".lower(
                    )

                    if not query_lower or query_lower in searchable:
                        sub_parts = []
                        if prod_addr:
                            sub_parts.append(prod_addr)
                        if prod_mail:
                            sub_parts.append(prod_mail)
                        elif prod_phone:
                            sub_parts.append(prod_phone)

                        results.append({
                            "title": prod_name,
                            "subtitle": " • ".join(sub_parts) if sub_parts else "Société de production",
                            "url": url_for("admin_productions_list", q=prod_name),
                            "category": "Production",
                            "icon": "building"
                        })
                        if len(results) >= 25:
                            break
            except Exception as e:
                current_app.logger.warning(
                    f"⚠️ Erreur recherche productions : {e}")

        # 3. Contacts (ciblage avec ?q=)
        if (is_manager_or_higher or role_norm == 'commercial') and scope in ('all', 'contact'):
            try:
                from models import Contact
                from sqlalchemy.orm import joinedload
                contacts = Contact.query.options(joinedload(Contact.production_rel)).order_by(
                    Contact.last_name.asc(), Contact.first_name.asc()).limit(150).all()
                for c in contacts:
                    full_name = f"{c.first_name} {c.last_name}".strip()
                    prod_name = c.production_rel.name if c.production_rel else "Freelance"
                    c_job = c.job_title or ""
                    c_mail = c.mail or ""
                    c_phone = c.phone or ""
                    searchable = f"{full_name} {prod_name} {c_job} {c_mail} {c_phone}".lower(
                    )

                    if not query_lower or query_lower in searchable:
                        sub_parts = []
                        if c_job and c_job != "—":
                            sub_parts.append(c_job)
                        if prod_name and prod_name != "Freelance":
                            sub_parts.append(prod_name)
                        elif c_mail and c_mail != "—":
                            sub_parts.append(c_mail)

                        results.append({
                            "title": full_name,
                            "subtitle": " • ".join(sub_parts) if sub_parts else "Contact professionnel",
                            "url": url_for("admin_contacts_list", q=full_name),
                            "category": "Contact",
                            "icon": "user"
                        })
                        if len(results) >= 30:
                            break
            except Exception as e:
                current_app.logger.warning(
                    f"⚠️ Erreur recherche contacts : {e}")

        # 4. Projets (ciblage avec ?q=)
        if (is_manager_or_higher or role_norm == 'commercial') and scope in ('all', 'project'):
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

                    if not query_lower or query_lower in searchable:
                        sub = f"{p_code}"
                        if prod_name:
                            sub += f" • {prod_name}"
                        results.append({
                            "title": p_name,
                            "subtitle": sub,
                            "url": url_for("admin_projects_list", q=p_code or p_name),
                            "category": "Projet",
                            "icon": "folder"
                        })
                        if len(results) >= 35:
                            break
            except Exception as e:
                current_app.logger.warning(
                    f"⚠️ Erreur recherche projets : {e}")

        # 5. Véhicules
        if scope in ('all', 'vehicle'):
            try:
                from utils.database import get_vehicles
                vehicles = get_vehicles() or []
                for v in vehicles:
                    fields = v.get("fields", {})
                    v_name = fields.get("Nom") or fields.get("name") or ""
                    v_model = fields.get("Modèle") or fields.get("model") or ""
                    searchable = f"{v_name} {v_model}".lower()
                    if (not query_lower or query_lower in searchable) and v_name:
                        results.append({
                            "title": v_name,
                            "subtitle": v_model or "Véhicule Belle Vitesse",
                            "url": url_for("admin_vehicle_timeline", vehicle_id=v.get("id")),
                            "category": "Véhicule",
                            "icon": "truck"
                        })
                        if len(results) >= 40:
                            break
            except Exception as e:
                current_app.logger.warning(
                    f"⚠️ Erreur recherche véhicules : {e}")

        # 6. Incidents de tournage
        if scope in ('all', 'incident'):
            try:
                from models.incident import Incident
                incidents = Incident.query.filter(Incident.deleted_at.is_(None)).order_by(
                    Incident.incident_date.desc()).limit(30).all()
                for inc in incidents:
                    inc_num = inc.incident_number or ""
                    inc_title = inc.title or ""
                    searchable = f"{inc_num} {inc_title} {inc.severity} {inc.status}".lower(
                    )
                    if not query_lower or query_lower in searchable:
                        results.append({
                            "title": f"{inc_num} — {inc_title}",
                            "subtitle": f"{inc.severity.capitalize()} • {inc.status} • {inc.incident_date.strftime('%d/%m/%Y') if inc.incident_date else ''}",
                            "url": url_for("admin_incident_detail", record_id=inc.id),
                            "category": "Incident",
                            "icon": "alert"
                        })
                        if len(results) >= 45:
                            break
            except Exception as e:
                current_app.logger.warning(
                    f"⚠️ Erreur recherche incidents : {e}")

        return jsonify({"results": results[:20]})
