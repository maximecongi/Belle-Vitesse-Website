from flask import (
    Blueprint,
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
    get_all_checkpoints,
    get_vehicles_with_config,
    save_vehicle_checkpoint_config,
)
from utils.decorators import require_roles


api_bp = Blueprint('admin_api', __name__, url_prefix='/admin')
# ── API Administrative ────────────────────────────────────────


@api_bp.route("/api/events")
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


@api_bp.route("/api/checkouts/<int:record_id>/status", methods=["GET", "POST"])
@require_roles('administrator', 'manager', 'user')
def admin_api_checkout_status(record_id):
    from models import CheckoutVehicle
    return _handle_status_update(CheckoutVehicle, record_id)


@api_bp.route("/api/checkins/<int:record_id>/status", methods=["GET", "POST"])
@require_roles('administrator', 'manager', 'user')
def admin_api_checkin_status(record_id):
    from models import CheckinVehicle
    return _handle_status_update(CheckinVehicle, record_id)


@api_bp.route("/vehicle-configs")
@require_roles('administrator')
def admin_vehicle_configs():
    try:
        vehicles = get_vehicles_with_config()
        return render_template(
            "admin/vehicle_configs.html",
            vehicles=vehicles,
            possible_checkpoints=get_all_checkpoints()
        )
    except Exception as e:
        current_app.logger.error(
            f"❌ Erreur dans admin_vehicle_configs : {e}")
        flash(
            f"Erreur lors du chargement des configurations: {e}", "error")
        return redirect(url_for('admin_dashboard.admin_dashboard'))


@api_bp.route("/api/vehicle-configs", methods=["POST"])
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


@api_bp.route("/api/search")
@require_roles('administrator', 'manager', 'commercial', 'user', 'technicien')
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
    raw_scope = request.args.get('scope', 'all').strip().lower()
    active_scopes = set(s.strip() for s in raw_scope.split(',') if s.strip())
    if not active_scopes:
        active_scopes = {'all'}

    # Détection d'un préfixe de ciblage optionnel dans la barre de recherche (ex: prod:..., p:..., co:..., etc.)
    if ':' in q:
        prefix, remainder = q.split(':', 1)
        prefix = prefix.strip().lower()
        remainder_clean = remainder.strip()
        pfx_scope = None
        if prefix in ('p', 'projet', 'projets', 'project', 'projects'):
            pfx_scope = 'project'
        elif prefix in ('c', 'controle', 'controles', 'contrôle', 'contrôles', 'inspection', 'inspections'):
            pfx_scope = 'inspection'
        elif prefix in ('co', 'checkout', 'checkouts', 'depart', 'départ', 'departs', 'départs'):
            pfx_scope = 'checkout'
        elif prefix in ('ci', 'checkin', 'checkins', 'retour', 'retours'):
            pfx_scope = 'checkin'
        elif prefix in ('w', 'waiver', 'waivers', 'decharge', 'décharge', 'decharges', 'décharges', 'cgl'):
            pfx_scope = 'waiver'
        elif prefix in ('v', 'vehicule', 'véhicule', 'vehicules', 'véhicules', 'vehicle', 'vehicles'):
            pfx_scope = 'vehicle'
        elif prefix in ('ct', 'contact', 'contacts'):
            pfx_scope = 'contact'
        elif prefix in ('prod', 'production', 'productions'):
            pfx_scope = 'production'
        elif prefix in ('i', 'inc', 'incident', 'incidents'):
            pfx_scope = 'incident'

        if pfx_scope:
            q = remainder_clean
            if 'all' in active_scopes:
                active_scopes = {pfx_scope}
            else:
                active_scopes.add(pfx_scope)

    import unicodedata
    def normalize_str(s):
        if not s:
            return ""
        return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()

    query_lower = q.lower()
    query_norm = normalize_str(q)

    if not q:
        # Suggestions logiques et prioritaires au chargement initial du modal (vide)
        default_suggestions = []

        # 1. Projets en cours (Hub direct)
        if is_manager_or_higher or role_norm in ('commercial', 'technicien', 'user'):
            try:
                from datetime import date
                from models.project import Project
                from sqlalchemy.orm import joinedload

                today = date.today()
                all_active_projects = Project.query.filter(
                    Project.deleted_at.is_(None)
                ).options(
                    joinedload(Project.production)
                ).order_by(Project.departure_date.asc()).all()

                for p in all_active_projects:
                    start_d = p.departure_date or p.shoot_start_date
                    end_d = p.return_date or p.shoot_end_date or start_d

                    if start_d and start_d <= today and (not end_d or end_d >= today):
                        p_name = p.name or "Projet sans nom"
                        p_code = p.project_id or ""
                        prod_name = p.production.name if p.production else ""
                        dates_str = ""
                        if start_d:
                            dates_str = start_d.strftime("%d/%m")
                            if end_d and end_d != start_d:
                                dates_str += f" → {end_d.strftime('%d/%m')}"

                        sub_parts = ["En cours"]
                        if p_code:
                            sub_parts.append(p_code)
                        if prod_name:
                            sub_parts.append(prod_name)
                        if dates_str:
                            sub_parts.append(dates_str)

                        default_suggestions.append({
                            "id": f"proj-{p.id}",
                            "title": p_name,
                            "subtitle": " • ".join(sub_parts),
                            "url": url_for("admin_projects.admin_project_detail", record_id=p.id),
                            "category": "Projets en cours",
                            "entity_type": "project",
                            "icon": "clapperboard"
                        })
                        if len(default_suggestions) >= 4:
                            break
            except Exception as e:
                current_app.logger.warning(f"⚠️ Erreur suggestions projets en cours : {e}")

        # 2. Actions rapides prioritaires
        if is_manager_or_higher or role_norm == 'commercial':
            default_suggestions.append({
                "id": "act-new-project",
                "title": "Nouveau Projet",
                "subtitle": "Créer un nouveau tournage",
                "url": url_for("admin_projects.admin_project_new"),
                "category": "Actions rapides",
                "entity_type": "action",
                "icon": "plus"
            })

        default_suggestions.append({
            "id": "act-new-checkout",
            "title": "Nouveau Check-out",
            "subtitle": "Effectuer un contrôle de départ véhicule",
            "url": url_for("admin_checkouts.admin_checkout_new"),
            "category": "Actions rapides",
            "entity_type": "checkout",
            "icon": "truck"
        })

        default_suggestions.append({
            "id": "act-new-checkin",
            "title": "Nouveau Check-in",
            "subtitle": "Effectuer un contrôle de retour véhicule",
            "url": url_for("admin_checkins.admin_checkin_new"),
            "category": "Actions rapides",
            "entity_type": "checkin",
            "icon": "package-check"
        })

        default_suggestions.append({
            "id": "act-new-incident",
            "title": "Déclarer un Incident",
            "subtitle": "Signaler une panne ou dommage en tournage",
            "url": url_for("admin_incidents.admin_incident_new"),
            "category": "Actions rapides",
            "entity_type": "incident",
            "icon": "alert-triangle"
        })

        if is_manager_or_higher or role_norm == 'commercial':
            default_suggestions.append({
                "id": "act-new-contact",
                "title": "Nouveau Contact",
                "subtitle": "Ajouter un contact professionnel",
                "url": url_for("admin_contacts.admin_contact_new"),
                "category": "Actions rapides",
                "entity_type": "contact",
                "icon": "user-plus"
            })
            default_suggestions.append({
                "id": "act-new-prod",
                "title": "Nouvelle Production",
                "subtitle": "Créer une société de production",
                "url": url_for("admin_productions.admin_production_new"),
                "category": "Actions rapides",
                "entity_type": "production",
                "icon": "building"
            })

        return jsonify({
            "results": default_suggestions,
            "scope": ",".join(sorted(active_scopes)),
            "query": q
        })

    results = []

    # 1. Navigation & Actions rapides (uniquement si scope 'all')
    if 'all' in active_scopes:
        pages_and_actions = [
            {"title": "Tableau de bord", "subtitle": "Vue d'ensemble", "url": url_for(
                "admin_dashboard.admin_dashboard"), "category": "Navigation", "entity_type": "page", "icon": "layout-dashboard", "roles": ['all']},
            {"title": "Nouveau Projet", "subtitle": "Créer un nouveau tournage", "url": url_for(
                "admin_projects.admin_project_new"), "category": "Actions", "entity_type": "action", "icon": "plus", "roles": ['manager', 'commercial', 'admin']},
            {"title": "Projets (Tous)", "subtitle": "Tournages en préparation ou en cours", "url": url_for(
                "admin_projects.admin_projects_list"), "category": "Navigation", "entity_type": "page", "icon": "clapperboard", "roles": ['all']},
            {"title": "Archives des Projets", "subtitle": "Projets terminés et archivés", "url": url_for(
                "admin_projects.admin_projects_archives"), "category": "Navigation", "entity_type": "page", "icon": "archive", "roles": ['manager', 'commercial', 'admin']},
            {"title": "Nouveau Check-out", "subtitle": "Effectuer un contrôle de départ", "url": url_for(
                "admin_checkouts.admin_checkout_new"), "category": "Actions", "entity_type": "checkout", "icon": "truck", "roles": ['all']},
            {"title": "Check-outs (Départs)", "subtitle": "Historique des contrôles de départ", "url": url_for(
                "admin_checkouts.admin_checkouts_list"), "category": "Navigation", "entity_type": "checkout", "icon": "truck", "roles": ['all']},
            {"title": "Nouveau Check-in", "subtitle": "Effectuer un contrôle de retour", "url": url_for(
                "admin_checkins.admin_checkin_new"), "category": "Actions", "entity_type": "checkin", "icon": "package-check", "roles": ['all']},
            {"title": "Check-ins (Retours)", "subtitle": "Historique des contrôles de retour", "url": url_for(
                "admin_checkins.admin_checkins_list"), "category": "Navigation", "entity_type": "checkin", "icon": "package-check", "roles": ['all']},
            {"title": "Conditions Générales (CGL)", "subtitle": "Conditions Générales de Location", "url": url_for(
                "admin_waivers.admin_cgl_list"), "category": "Navigation", "entity_type": "waiver", "icon": "file-signature", "roles": ['manager', 'commercial', 'admin']},
            {"title": "Nouvelles CGL", "subtitle": "Créer les CGL pour un tournage", "url": url_for(
                "admin_waivers.admin_cgl_new"), "category": "Actions", "entity_type": "waiver", "icon": "plus", "roles": ['manager', 'commercial', 'admin']},
            {"title": "Règles de Sécurité", "subtitle": "Engagements et décharges de sécurité universelles", "url": url_for(
                "admin_waivers.admin_safety_rules_list"), "category": "Navigation", "entity_type": "waiver", "icon": "shield", "roles": ['manager', 'commercial', 'admin']},
            {"title": "Attestations Pilotes (Annexe 3)", "subtitle": "Décharges et attestations des pilotes", "url": url_for(
                "admin_waivers.admin_pilot_waivers_list"), "category": "Navigation", "entity_type": "waiver", "icon": "file-check", "roles": ['manager', 'commercial', 'admin']},
            {"title": "Gestion des Incidents", "subtitle": "Suivi des pannes, dommages et sinistres", "url": url_for(
                "admin_incidents.admin_incidents_list"), "category": "Navigation", "entity_type": "incident", "icon": "alert-triangle", "roles": ['all']},
            {"title": "Déclarer un Incident", "subtitle": "Signaler une anomalie en tournage", "url": url_for(
                "admin_incidents.admin_incident_new"), "category": "Actions", "entity_type": "incident", "icon": "alert-triangle", "roles": ['all']},
            {"title": "Flotte & Parc", "subtitle": "Parc de véhicules, statuts et contrôles", "url": url_for(
                "admin_fleet.admin_fleet_list"), "category": "Navigation", "entity_type": "vehicle", "icon": "truck", "roles": ['all']},
            {"title": "Calendrier Matériel", "subtitle": "Disponibilités et planning des équipements", "url": url_for(
                "admin_booking.admin_booking"), "category": "Navigation", "entity_type": "page", "icon": "calendar", "roles": ['manager', 'commercial', 'admin']},
            {"title": "Abonnements Calendrier (ICS)", "subtitle": "Flux iCal et synchronisation des agendas", "url": url_for(
                "admin_calendar.admin_calendar"), "category": "Navigation", "entity_type": "page", "icon": "calendar-range", "roles": ['manager', 'commercial', 'admin']},
            {"title": "Productions", "subtitle": "Annuaire des sociétés clientes", "url": url_for(
                "admin_productions.admin_productions_list"), "category": "Navigation", "entity_type": "production", "icon": "building", "roles": ['manager', 'commercial', 'admin']},
            {"title": "Nouvelle Production", "subtitle": "Créer une société de production", "url": url_for(
                "admin_productions.admin_production_new"), "category": "Actions", "entity_type": "production", "icon": "plus", "roles": ['manager', 'commercial', 'admin']},
            {"title": "Contacts", "subtitle": "Annuaire des contacts professionnels", "url": url_for(
                "admin_contacts.admin_contacts_list"), "category": "Navigation", "entity_type": "contact", "icon": "users", "roles": ['manager', 'commercial', 'admin']},
            {"title": "Nouveau Contact", "subtitle": "Ajouter un contact professionnel", "url": url_for(
                "admin_contacts.admin_contact_new"), "category": "Actions", "entity_type": "contact", "icon": "plus", "roles": ['manager', 'commercial', 'admin']},
            {"title": "Tarification", "subtitle": "Grille tarifaire et options matériels", "url": url_for(
                "admin_pricing.admin_pricing"), "category": "Navigation", "entity_type": "page", "icon": "tag", "roles": ['manager', 'commercial', 'admin']},
            {"title": "Configurations Véhicules", "subtitle": "Checkpoints et équipements", "url": url_for(
                "admin_api.admin_vehicle_configs"), "category": "Navigation", "entity_type": "page", "icon": "settings", "roles": ['admin']},
            {"title": "Équipe & Utilisateurs", "subtitle": "Gestion des accès et collaborateurs", "url": url_for(
                "admin_users.admin_users_list"), "category": "Navigation", "entity_type": "page", "icon": "users", "roles": ['manager', 'admin']},
            {"title": "Générateur de Signature", "subtitle": "Générer la signature email officielle", "url": url_for(
                "admin_tools.admin_signature_generator"), "category": "Navigation", "entity_type": "page", "icon": "pen-tool", "roles": ['all']},
            {"title": "Documentation Technique", "subtitle": "Guides et documentations internes", "url": url_for(
                "admin_tools.admin_docs_index"), "category": "Navigation", "entity_type": "page", "icon": "book-open", "roles": ['admin']},
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
                    "id": f"nav-{item['title']}",
                    "title": item["title"],
                    "subtitle": item["subtitle"],
                    "url": item["url"],
                    "category": item["category"],
                    "entity_type": item["entity_type"],
                    "icon": item["icon"]
                })

    # 2. Projets (vers Project Hub !)
    if 'all' in active_scopes or 'project' in active_scopes:
        try:
            from models.project import Project, Production
            from sqlalchemy.orm import joinedload
            from sqlalchemy import or_

            projects_query = Project.query.filter(
                Project.deleted_at.is_(None)
            ).options(
                joinedload(Project.production)
            ).outerjoin(Production, Project.production_id == Production.id)

            # Recherche ciblée SQL si possible
            tokens = query_lower.split()
            for t in tokens:
                pattern = f"%{t}%"
                projects_query = projects_query.filter(
                    or_(
                        Project.name.ilike(pattern),
                        Project.project_id.ilike(pattern),
                        Project.notes.ilike(pattern),
                        Production.name.ilike(pattern)
                    )
                )

            found_projects = projects_query.order_by(Project.departure_date.desc()).limit(15).all()

            for p in found_projects:
                p_name = p.name or "Projet sans nom"
                p_code = p.project_id or ""
                prod_name = p.production.name if p.production else ""

                start_d = p.departure_date or p.shoot_start_date
                end_d = p.return_date or p.shoot_end_date or start_d
                dates_str = ""
                if start_d:
                    dates_str = start_d.strftime("%d/%m/%Y")
                    if end_d and end_d != start_d:
                        dates_str += f" → {end_d.strftime('%d/%m/%Y')}"

                sub_parts = []
                if p_code:
                    sub_parts.append(p_code)
                if prod_name:
                    sub_parts.append(prod_name)
                if dates_str:
                    sub_parts.append(dates_str)

                results.append({
                    "id": f"proj-{p.id}",
                    "title": p_name,
                    "subtitle": " • ".join(sub_parts) if sub_parts else "Fiche Projet",
                    "url": url_for("admin_projects.admin_project_detail", record_id=p.id),
                    "category": "Projets",
                    "entity_type": "project",
                    "icon": "clapperboard"
                })
        except Exception as e:
            current_app.logger.warning(f"⚠️ Erreur recherche projets : {e}")

    # 3. Contrôles Check-out (Départs)
    if 'all' in active_scopes or bool(active_scopes & {'inspection', 'checkout'}):
        try:
            from models.inspection import CheckoutVehicle
            from models.project import Project
            from sqlalchemy.orm import joinedload
            from sqlalchemy import or_

            co_query = CheckoutVehicle.query.filter(
                CheckoutVehicle.deleted_at.is_(None)
            ).options(
                joinedload(CheckoutVehicle.project)
            ).outerjoin(Project, CheckoutVehicle.project_id == Project.id)

            tokens = query_lower.split()
            for t in tokens:
                pattern = f"%{t}%"
                co_query = co_query.filter(
                    or_(
                        CheckoutVehicle.inspection_number.ilike(pattern),
                        CheckoutVehicle.notes.ilike(pattern),
                        Project.name.ilike(pattern),
                        Project.project_id.ilike(pattern)
                    )
                )

            found_cos = co_query.order_by(CheckoutVehicle.inspection_date.desc()).limit(10).all()

            for co in found_cos:
                num = co.inspection_number or f"Check-out #{co.id}"
                proj_name = co.project.name if co.project else "Sans projet"
                d_str = co.inspection_date.strftime("%d/%m/%Y") if co.inspection_date else ""

                sub_parts = [f"Projet : {proj_name}"]
                if d_str:
                    sub_parts.append(d_str)
                if co.status:
                    status_lbl = "Validé" if co.status == "signed" else ("En cours" if co.status == "in_progress" else co.status)
                    sub_parts.append(status_lbl)

                results.append({
                    "id": f"checkout-{co.id}",
                    "title": f"{num} — Départ",
                    "subtitle": " • ".join(sub_parts),
                    "url": url_for("admin_checkouts.admin_checkout_detail", record_id=co.id),
                    "category": "Contrôles Départs",
                    "entity_type": "checkout",
                    "icon": "truck"
                })
        except Exception as e:
            current_app.logger.warning(f"⚠️ Erreur recherche checkouts : {e}")

    # 4. Contrôles Check-in (Retours)
    if 'all' in active_scopes or bool(active_scopes & {'inspection', 'checkin'}):
        try:
            from models.inspection import CheckinVehicle
            from models.project import Project
            from sqlalchemy.orm import joinedload
            from sqlalchemy import or_

            ci_query = CheckinVehicle.query.filter(
                CheckinVehicle.deleted_at.is_(None)
            ).options(
                joinedload(CheckinVehicle.project)
            ).outerjoin(Project, CheckinVehicle.project_id == Project.id)

            tokens = query_lower.split()
            for t in tokens:
                pattern = f"%{t}%"
                ci_query = ci_query.filter(
                    or_(
                        CheckinVehicle.inspection_number.ilike(pattern),
                        CheckinVehicle.notes.ilike(pattern),
                        Project.name.ilike(pattern),
                        Project.project_id.ilike(pattern)
                    )
                )

            found_cis = ci_query.order_by(CheckinVehicle.inspection_date.desc()).limit(10).all()

            for ci in found_cis:
                num = ci.inspection_number or f"Check-in #{ci.id}"
                proj_name = ci.project.name if ci.project else "Sans projet"
                d_str = ci.inspection_date.strftime("%d/%m/%Y") if ci.inspection_date else ""

                sub_parts = [f"Projet : {proj_name}"]
                if d_str:
                    sub_parts.append(d_str)
                if ci.status:
                    status_lbl = "Validé" if ci.status == "signed" else ("En cours" if ci.status == "in_progress" else ci.status)
                    sub_parts.append(status_lbl)

                results.append({
                    "id": f"checkin-{ci.id}",
                    "title": f"{num} — Retour",
                    "subtitle": " • ".join(sub_parts),
                    "url": url_for("admin_checkins.admin_checkin_detail", record_id=ci.id),
                    "category": "Contrôles Retours",
                    "entity_type": "checkin",
                    "icon": "package-check"
                })
        except Exception as e:
            current_app.logger.warning(f"⚠️ Erreur recherche checkins : {e}")

    # 5. Décharges (Waivers : CGL BVRA, Règles BVSR, Pilotes BVPA)
    if 'all' in active_scopes or 'waiver' in active_scopes:
        try:
            from models.waiver import Waiver
            from models.project import Project
            from sqlalchemy.orm import joinedload
            from sqlalchemy import or_

            w_query = Waiver.query.options(
                joinedload(Waiver.project)
            ).outerjoin(Project, Waiver.project_id == Project.id)

            tokens = query_lower.split()
            for t in tokens:
                pattern = f"%{t}%"
                w_query = w_query.filter(
                    or_(
                        Waiver.waiver_id.ilike(pattern),
                        Waiver.signer_first_name.ilike(pattern),
                        Waiver.signer_last_name.ilike(pattern),
                        Waiver.production_name.ilike(pattern),
                        Waiver.signer_company.ilike(pattern),
                        Project.name.ilike(pattern)
                    )
                )

            found_waivers = w_query.order_by(Waiver.id.desc()).limit(12).all()

            for w in found_waivers:
                w_num = w.waiver_id or f"Waiver #{w.id}"
                w_type = getattr(w, "waiver_type", "")
                if w_type == "cgl":
                    type_label = "CGL (Location)"
                elif w_type == "pilot_waiver":
                    type_label = "Attestation Pilote"
                else:
                    type_label = "Règles de Sécurité"

                proj_name = w.project.name if w.project else (w.project_name or "Projet")
                signer_name = ""
                if getattr(w, "signer_first_name", None) or getattr(w, "signer_last_name", None):
                    signer_name = f"{w.signer_first_name or ''} {w.signer_last_name or ''}".strip()
                elif getattr(w, "production_name", None):
                    signer_name = w.production_name

                sub_parts = [f"Projet : {proj_name}"]
                if signer_name:
                    sub_parts.append(signer_name)
                if w.status:
                    status_lbl = "Signé" if w.status == "signed" else ("Envoyé" if w.status == "to_sign" else "À générer")
                    sub_parts.append(status_lbl)

                results.append({
                    "id": f"waiver-{w.id}",
                    "title": f"{w_num} — {type_label}",
                    "subtitle": " • ".join(sub_parts),
                    "url": url_for("admin_projects.admin_project_detail", record_id=w.project_id) + "#waivers",
                    "category": "Décharges",
                    "entity_type": "waiver",
                    "icon": "file-signature"
                })
        except Exception as e:
            current_app.logger.warning(f"⚠️ Erreur recherche décharges : {e}")

    # 6. Véhicules
    if 'all' in active_scopes or 'vehicle' in active_scopes:
        try:
            from utils.database import get_vehicles
            vehicles = get_vehicles() or []
            for v in vehicles:
                fields = v.get("fields", {})
                v_name = fields.get("Nom") or fields.get("name") or ""
                v_model = fields.get("Modèle") or fields.get("model") or ""
                searchable = f"{v_name} {v_model}".lower()
                if (not query_lower or query_lower in searchable or query_norm in normalize_str(searchable)) and v_name:
                    results.append({
                        "id": f"veh-{v.get('id')}",
                        "title": v_name,
                        "subtitle": v_model or "Véhicule Belle Vitesse",
                        "url": url_for("admin_fleet.admin_vehicle_timeline", vehicle_id=v.get("id")),
                        "category": "Véhicules",
                        "entity_type": "vehicle",
                        "icon": "truck"
                    })
                    if len(results) >= 20:
                        break
        except Exception as e:
            current_app.logger.warning(f"⚠️ Erreur recherche véhicules : {e}")

    # 7. Incidents de tournage
    if 'all' in active_scopes or 'incident' in active_scopes:
        try:
            from models.incident import Incident
            from models.project import Project
            from sqlalchemy.orm import joinedload
            from sqlalchemy import or_

            inc_query = Incident.query.filter(
                Incident.deleted_at.is_(None)
            ).options(
                joinedload(Incident.project)
            ).outerjoin(Project, Incident.project_id == Project.id)

            tokens = query_lower.split()
            for t in tokens:
                pattern = f"%{t}%"
                inc_query = inc_query.filter(
                    or_(
                        Incident.incident_number.ilike(pattern),
                        Incident.title.ilike(pattern),
                        Incident.description.ilike(pattern),
                        Project.name.ilike(pattern)
                    )
                )

            found_incidents = inc_query.order_by(Incident.incident_date.desc()).limit(10).all()

            for inc in found_incidents:
                inc_num = inc.incident_number or f"INC-{inc.id}"
                inc_title = inc.title or "Incident"
                proj_name = inc.project.name if inc.project else ""

                sub_parts = []
                if inc.severity_label:
                    sub_parts.append(inc.severity_label)
                if inc.status_label:
                    sub_parts.append(inc.status_label)
                if proj_name:
                    sub_parts.append(f"Projet : {proj_name}")
                if inc.incident_date:
                    sub_parts.append(inc.incident_date.strftime("%d/%m/%Y"))

                results.append({
                    "id": f"inc-{inc.id}",
                    "title": f"{inc_num} — {inc_title}",
                    "subtitle": " • ".join(sub_parts) if sub_parts else "Fiche Incident",
                    "url": url_for("admin_incidents.admin_incident_detail", record_id=inc.id),
                    "category": "Incidents",
                    "entity_type": "incident",
                    "icon": "alert-triangle"
                })
        except Exception as e:
            current_app.logger.warning(f"⚠️ Erreur recherche incidents : {e}")

    # 8. Contacts (vers fiche édition directe)
    if (is_manager_or_higher or role_norm == 'commercial') and ('all' in active_scopes or 'contact' in active_scopes):
        try:
            from models.project import Contact
            from sqlalchemy.orm import joinedload
            from sqlalchemy import or_

            c_query = Contact.query.options(joinedload(Contact.production_rel))
            tokens = query_lower.split()
            for t in tokens:
                pattern = f"%{t}%"
                c_query = c_query.filter(
                    or_(
                        Contact.first_name.ilike(pattern),
                        Contact.last_name.ilike(pattern),
                        Contact.mail.ilike(pattern),
                        Contact.phone.ilike(pattern),
                        Contact.job_title.ilike(pattern)
                    )
                )

            contacts = c_query.order_by(Contact.last_name.asc(), Contact.first_name.asc()).limit(15).all()

            for c in contacts:
                full_name = f"{c.first_name} {c.last_name}".strip()
                prod_name = c.production_rel.name if c.production_rel else "Freelance"
                c_job = c.job_title or ""
                c_mail = c.mail or ""
                c_phone = c.phone or ""

                sub_parts = []
                if c_job and c_job != "—":
                    sub_parts.append(c_job)
                if prod_name and prod_name != "Freelance":
                    sub_parts.append(prod_name)
                elif c_mail and c_mail != "—":
                    sub_parts.append(c_mail)
                elif c_phone:
                    sub_parts.append(c_phone)

                results.append({
                    "id": f"contact-{c.id}",
                    "title": full_name,
                    "subtitle": " • ".join(sub_parts) if sub_parts else "Contact professionnel",
                    "url": url_for("admin_contacts.admin_contact_edit", record_id=c.id),
                    "category": "Contacts",
                    "entity_type": "contact",
                    "icon": "user"
                })
        except Exception as e:
            current_app.logger.warning(f"⚠️ Erreur recherche contacts : {e}")

    # 9. Productions (vers fiche édition directe)
    if (is_manager_or_higher or role_norm == 'commercial') and ('all' in active_scopes or 'production' in active_scopes):
        try:
            from models.project import Production
            from sqlalchemy import or_

            p_query = Production.query
            tokens = query_lower.split()
            for t in tokens:
                pattern = f"%{t}%"
                p_query = p_query.filter(
                    or_(
                        Production.name.ilike(pattern),
                        Production.address.ilike(pattern),
                        Production.mail.ilike(pattern),
                        Production.phone.ilike(pattern)
                    )
                )

            productions = p_query.order_by(Production.name.asc()).limit(15).all()

            for prod in productions:
                prod_name = prod.name or ""
                prod_addr = prod.address or ""
                prod_mail = prod.mail or ""
                prod_phone = prod.phone or ""

                sub_parts = []
                if prod_addr:
                    sub_parts.append(prod_addr)
                if prod_mail:
                    sub_parts.append(prod_mail)
                elif prod_phone:
                    sub_parts.append(prod_phone)

                results.append({
                    "id": f"prod-{prod.id}",
                    "title": prod_name,
                    "subtitle": " • ".join(sub_parts) if sub_parts else "Société de production",
                    "url": url_for("admin_productions.admin_production_edit", record_id=prod.id),
                    "category": "Productions",
                    "entity_type": "production",
                    "icon": "building"
                })
        except Exception as e:
            current_app.logger.warning(f"⚠️ Erreur recherche productions : {e}")

    return jsonify({
        "results": results[:40],
        "scope": ",".join(sorted(active_scopes)),
        "query": q
    })


def init_api_routes(app):
    """Enregistre le blueprint admin_api (compatibilité ascendante)."""
    if "admin_api" not in app.blueprints:
        app.register_blueprint(api_bp)
