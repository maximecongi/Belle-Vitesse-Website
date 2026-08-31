"""Outils MCP : Domaine Projets."""
from datetime import date, datetime
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope
from mcp_server.utils import parse_flexible_date, matches_search_query, apply_pagination


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def list_projects(
    query: Optional[str] = None,
    status: Optional[str] = None,
    production_id: Optional[int] = None,
    limit: Optional[int] = 50,
    offset: Optional[int] = 0,
) -> List[Dict[str, Any]]:
    """
    Liste les projets (tournages) avec recherche textuelle, filtre temporel et pagination.
    - query: Recherche par nom de projet, code BVPR, nom de production ou notes
    - status: 'all', 'active' (tournage en cours aujourd'hui), 'upcoming' (futur), 'past' (terminé)
    - production_id: Filtrer par identifiant de société de production
    - limit: Nombre maximum de projets retournés (défaut 50, max 500)
    - offset: Décalage pour la pagination
    """
    from services.admin.projects import list_projects as _list_projects
    all_projects = _list_projects()
    today_str = date.today().isoformat()

    filtered = []
    for p in all_projects:
        # Filtre production
        if production_id is not None:
            p_prod_id = p.get("production_id")
            if p_prod_id != production_id and str(p_prod_id) != str(production_id):
                continue

        # Filtre temporel / statut
        if status and status.lower() != "all":
            st = status.lower()
            start_d = p.get("shoot_start_raw") or p.get("departure_date_raw") or ""
            end_d = p.get("shoot_end_raw") or p.get("return_date_raw") or ""

            if st == "active":
                if not (start_d <= today_str <= (end_d or start_d)):
                    continue
            elif st == "upcoming":
                if not (start_d > today_str):
                    continue
            elif st == "past":
                if not (end_d and end_d < today_str):
                    continue

        # Recherche textuelle
        if query and not matches_search_query(p, query, ["name", "project_id", "production_name", "notes"]):
            continue

        filtered.append(p)

    return apply_pagination(filtered, limit=limit, offset=offset)


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_project(project_id: int) -> Optional[Dict[str, Any]]:
    """
    Récupère les détails enrichis d'un projet par son ID numérique ou code BVPR.
    Inclut les contacts résolus, la société de production, les véhicules résolus et le statut des décharges.
    """
    from models import Project, db
    from utils.database import get_vehicles, get_heads

    # Recherche par ID primaire ou par identifiant BVPR
    project = db.session.get(Project, project_id)
    if not project:
        project = Project.query.filter_by(project_id=str(project_id)).first()

    if not project or project.deleted_at:
        return None

    # Mapping véhicules & têtes pour enrichissement
    all_veh_map = {v.get("id"): v for v in get_vehicles()}
    all_head_map = {h.get("id"): h for h in get_heads()}

    veh_ids = [v.strip() for v in (project.vehicles_to_check or "").split(",") if v.strip()]
    head_ids = [h.strip() for h in (project.heads_to_check or "").split(",") if h.strip()]

    resolved_vehicles = []
    for vid in veh_ids:
        raw_v = all_veh_map.get(vid, {})
        fields = raw_v.get("fields", {})
        resolved_vehicles.append({
            "id": vid,
            "name": fields.get("name") or vid,
            "daily_rate": fields.get("daily_rate"),
        })

    resolved_heads = []
    for hid in head_ids:
        raw_h = all_head_map.get(hid, {})
        fields = raw_h.get("fields", {})
        resolved_heads.append({
            "id": hid,
            "name": fields.get("name") or hid,
            "daily_rate": fields.get("daily_rate"),
        })

    def _fmt_contact(c):
        if not c:
            return None
        return {
            "id": c.id,
            "first_name": c.first_name,
            "last_name": c.last_name,
            "full_name": f"{c.first_name} {c.last_name}".strip(),
            "job": c.job_title or "",
            "email": c.mail or "",
            "phone": c.phone or "",
        }

    # Statut décharges
    pilot_waiver_data = None
    if project.pilot_waiver:
        pw = project.pilot_waiver
        pilot_waiver_data = {
            "waiver_id": pw.waiver_id,
            "status": pw.status,
            "signed_at": pw.signed_at.isoformat() if pw.signed_at else None,
            "signed_pdf_url": pw.signed_pdf_path if pw.signed_pdf_path else None,
        }

    production_waiver_data = None
    if project.production_waiver:
        prw = project.production_waiver
        production_waiver_data = {
            "waiver_id": prw.waiver_id,
            "status": prw.status,
            "signed_at": prw.signed_at.isoformat() if prw.signed_at else None,
            "signed_pdf_url": prw.signed_pdf_path if prw.signed_pdf_path else None,
        }

    production_data = None
    if project.production:
        production_data = {
            "id": project.production.id,
            "name": project.production.name,
            "address": project.production.address or "",
            "email": project.production.mail or "",
            "phone": project.production.phone or "",
        }

    # Format de retour enrichi tout en conservant les clés legacy
    return {
        "id": project.id,
        "project_id": project.project_id,
        "name": project.name,
        "notes": project.notes or "",
        "departure_date": project.departure_date.strftime("%Y-%m-%d") if project.departure_date else None,
        "shoot_start_date": project.shoot_start_date.strftime("%Y-%m-%d") if project.shoot_start_date else None,
        "shoot_end_date": project.shoot_end_date.strftime("%Y-%m-%d") if project.shoot_end_date else None,
        "return_date": project.return_date.strftime("%Y-%m-%d") if project.return_date else None,
        # Compatibilité formulaires et scripts existants
        "departure_date_raw": str(project.departure_date) if project.departure_date else "",
        "shoot_start_raw": str(project.shoot_start_date) if project.shoot_start_date else "",
        "shoot_end_raw": str(project.shoot_end_date) if project.shoot_end_date else "",
        "return_date_raw": str(project.return_date) if project.return_date else "",
        "production_id": str(project.production_id) if project.production_id else "",
        "pilot_contact_id": str(project.pilot_contact_id) if project.pilot_contact_id else "",
        "production_contact_id": str(project.production_contact_id) if project.production_contact_id else "",
        "dop_contact_id": str(project.dop_contact_id) if project.dop_contact_id else "",
        "first_ac_contact_id": str(project.first_ac_contact_id) if project.first_ac_contact_id else "",
        "key_grip_contact_id": str(project.key_grip_contact_id) if project.key_grip_contact_id else "",
        "vehicle_ids": veh_ids,
        "head_ids": head_ids,
        # Données enrichies
        "production": production_data,
        "production_name": project.production.name if project.production else "Non assignée",
        "assigned_contacts": {
            "pilot": _fmt_contact(project.pilot_contact),
            "production_contact": _fmt_contact(project.production_contact),
            "dop": _fmt_contact(project.dop_contact),
            "first_ac": _fmt_contact(project.first_ac_contact),
            "key_grip": _fmt_contact(project.key_grip_contact),
        },
        "vehicles": resolved_vehicles,
        "heads": resolved_heads,
        "waivers": {
            "pilot": pilot_waiver_data,
            "production": production_waiver_data,
        },
    }


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def create_project(
    name: str,
    production_id: Optional[int] = None,
    pilot_contact_id: Optional[int] = None,
    production_contact_id: Optional[int] = None,
    dop_contact_id: Optional[int] = None,
    first_ac_contact_id: Optional[int] = None,
    key_grip_contact_id: Optional[int] = None,
    notes: Optional[str] = None,
    departure_date: Optional[str] = None,
    shoot_start: Optional[str] = None,
    shoot_end: Optional[str] = None,
    return_date: Optional[str] = None,
    vehicle_ids: Optional[List[str]] = None,
    head_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Crée un nouveau projet et génère automatiquement ses décharges pilote/production.
    Les dates peuvent être passées aux formats 'YYYY-MM-DD', 'DD/MM/YYYY', etc.
    """
    from services.admin.projects import create_project as _create_project

    class MultiDictMock(dict):
        def getlist(self, key):
            if key == "vehicle_ids":
                return vehicle_ids or []
            if key == "head_ids":
                return head_ids or []
            return []

    if not production_id:
        from models import Production
        first_prod = Production.query.first()
        if first_prod:
            production_id = first_prod.id

    form_data = MultiDictMock({
        "name": name,
        "production_id": str(production_id) if production_id else "",
        "pilot_contact_id": str(pilot_contact_id) if pilot_contact_id else "",
        "production_contact_id": str(production_contact_id) if production_contact_id else "",
        "dop_contact_id": str(dop_contact_id) if dop_contact_id else "",
        "first_ac_contact_id": str(first_ac_contact_id) if first_ac_contact_id else "",
        "key_grip_contact_id": str(key_grip_contact_id) if key_grip_contact_id else "",
        "notes": notes or "",
        "departure_date": parse_flexible_date(departure_date) or "",
        "shoot_start": parse_flexible_date(shoot_start) or "",
        "shoot_end": parse_flexible_date(shoot_end) or "",
        "return_date": parse_flexible_date(return_date) or "",
    })

    success = _create_project(form_data)
    return {"success": success, "message": "Projet créé avec succès." if success else "Échec de la création."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_project(
    project_id: int,
    name: Optional[str] = None,
    production_id: Optional[int] = None,
    pilot_contact_id: Optional[int] = None,
    production_contact_id: Optional[int] = None,
    dop_contact_id: Optional[int] = None,
    first_ac_contact_id: Optional[int] = None,
    key_grip_contact_id: Optional[int] = None,
    notes: Optional[str] = None,
    departure_date: Optional[str] = None,
    shoot_start: Optional[str] = None,
    shoot_end: Optional[str] = None,
    return_date: Optional[str] = None,
    vehicle_ids: Optional[List[str]] = None,
    head_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Met à jour un projet existant par son ID (mode patch : conserve les champs non spécifiés).
    Les dates peuvent être fournies dans tous les formats usuels ('YYYY-MM-DD', 'DD/MM/YYYY', etc.).
    """
    from models import Project, db
    from services.admin.projects import update_project as _update_project

    project = db.session.get(Project, project_id)
    if not project:
        return {"success": False, "message": f"Projet #{project_id} introuvable."}

    # Récupérer les identifiants existants pour les véhicules et têtes
    existing_veh_ids = [v.strip() for v in (project.vehicles_to_check or "").split(",") if v.strip()]
    existing_head_ids = [h.strip() for h in (project.heads_to_check or "").split(",") if h.strip()]

    final_veh_ids = vehicle_ids if vehicle_ids is not None else existing_veh_ids
    final_head_ids = head_ids if head_ids is not None else existing_head_ids

    class MultiDictMock(dict):
        def getlist(self, key):
            if key == "vehicle_ids":
                return final_veh_ids
            if key == "head_ids":
                return final_head_ids
            return []

    # Dates existantes
    existing_dep = project.departure_date.strftime("%Y-%m-%d") if project.departure_date else ""
    existing_start = project.shoot_start_date.strftime("%Y-%m-%d") if project.shoot_start_date else ""
    existing_end = project.shoot_end_date.strftime("%Y-%m-%d") if project.shoot_end_date else ""
    existing_ret = project.return_date.strftime("%Y-%m-%d") if project.return_date else ""

    parsed_dep = parse_flexible_date(departure_date) if departure_date is not None else existing_dep
    parsed_start = parse_flexible_date(shoot_start) if shoot_start is not None else existing_start
    parsed_end = parse_flexible_date(shoot_end) if shoot_end is not None else existing_end
    parsed_ret = parse_flexible_date(return_date) if return_date is not None else existing_ret

    form_data = MultiDictMock({
        "name": name if name is not None else (project.name or ""),
        "production_id": str(production_id) if production_id is not None else (str(project.production_id) if project.production_id else ""),
        "pilot_contact_id": str(pilot_contact_id) if pilot_contact_id is not None else (str(project.pilot_contact_id) if project.pilot_contact_id else ""),
        "production_contact_id": str(production_contact_id) if production_contact_id is not None else (str(project.production_contact_id) if project.production_contact_id else ""),
        "dop_contact_id": str(dop_contact_id) if dop_contact_id is not None else (str(project.dop_contact_id) if project.dop_contact_id else ""),
        "first_ac_contact_id": str(first_ac_contact_id) if first_ac_contact_id is not None else (str(project.first_ac_contact_id) if project.first_ac_contact_id else ""),
        "key_grip_contact_id": str(key_grip_contact_id) if key_grip_contact_id is not None else (str(project.key_grip_contact_id) if project.key_grip_contact_id else ""),
        "notes": notes if notes is not None else (project.notes or ""),
        "departure_date": parsed_dep or "",
        "shoot_start": parsed_start or "",
        "shoot_end": parsed_end or "",
        "return_date": parsed_ret or "",
    })

    success = _update_project(project_id, form_data)
    return {"success": success, "message": "Projet mis à jour." if success else "Projet introuvable."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def delete_project(project_id: int, confirm: bool = False) -> Dict[str, Any]:
    """
    Supprime un projet par soft-delete et nettoie ses décharges associées.
    ATTENTION: Action destructrice (Scope 'admin' requis).
    L'IA doit obligatoirement l'exécuter d'abord avec confirm=False pour simuler l'impact et demander la confirmation à l'utilisateur humain.
    """
    from services.admin.projects import get_project_for_edit, delete_project as _delete_project
    proj = get_project_for_edit(project_id)
    if not proj:
        return {"success": False, "message": f"Projet #{project_id} introuvable."}

    if not confirm:
        proj_name = proj.get("name", "Sans nom")
        return {
            "success": False,
            "status": "requires_confirmation",
            "project_id": project_id,
            "project_name": proj_name,
            "message": (
                f"⚠️ ATTENTION : Vous êtes sur le point de supprimer le projet #{project_id} '{proj_name}'. "
                "Veuillez demander la confirmation explicite à l'utilisateur humain devant son écran, "
                "puis ré-exécutez cet outil avec confirm=True."
            )
        }

    success = _delete_project(project_id)
    return {"success": success, "message": f"Projet #{project_id} supprimé avec succès." if success else "Échec de la suppression."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_project_form_context(
    category: Optional[str] = None,
    compact: Optional[bool] = True,
) -> Dict[str, Any]:
    """
    Récupère le contexte nécessaire aux formulaires de projet (listes de sélections).
    - category: Filtrer sur un domaine précis ('productions', 'contacts', 'vehicles', 'heads') ou None pour tout
    - compact: Si True (par défaut), retourne un payload ultra-léger (id, nom) pour économiser les tokens. Si False, retourne l'intégralité des attributs catalogue.
    """
    from services.admin.projects import get_project_form_context as _context
    raw = _context()
    if not compact:
        if category and category.lower() in raw:
            return {category.lower(): raw[category.lower()]}
        return raw

    compact_prods = [
        {"id": int(p["id"]) if str(p.get("id", "")).isdigit() else p.get("id"), "name": p.get("fields", {}).get("Nom") or p.get("name", "")}
        for p in raw.get("productions", [])
    ]
    compact_contacts = [
        {"id": int(c["id"]) if str(c.get("id", "")).isdigit() else c.get("id"), "name": c.get("name", "")}
        for c in raw.get("contacts", [])
    ]
    compact_vehicles = [
        {
            "id": v.get("id"),
            "name": v.get("fields", {}).get("name") or v.get("id"),
            "daily_rate": v.get("fields", {}).get("daily_rate"),
        }
        for v in raw.get("vehicles", [])
    ]
    compact_heads = [
        {
            "id": h.get("id"),
            "name": h.get("fields", {}).get("name") or h.get("id"),
            "daily_rate": h.get("fields", {}).get("daily_rate"),
        }
        for h in raw.get("heads", [])
    ]

    res = {
        "productions": compact_prods,
        "contacts": compact_contacts,
        "vehicles": compact_vehicles,
        "heads": compact_heads,
    }

    if category and category.lower() in res:
        return {category.lower(): res[category.lower()]}

    return res


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_dashboard_summary() -> Dict[str, Any]:
    """
    Fournit une vue synthétique de l'activité pour l'agent IA :
    - Tournages en cours cette semaine
    - Tournages à venir sous 15 jours
    - Décharges en attente de signature
    - Pré-devis récents en attente
    """
    from datetime import timedelta
    from models import Project, PreQuote, PilotWaiver, ProductionWaiver

    today = date.today()
    in_15_days = today + timedelta(days=15)
    today_str = today.isoformat()
    in_15_str = in_15_days.isoformat()

    all_projects = Project.query.filter(Project.deleted_at.is_(None)).all()

    active_now = []
    upcoming_15d = []

    for p in all_projects:
        start_d = p.shoot_start_date or p.departure_date
        end_d = p.shoot_end_date or p.return_date or start_d

        if start_d and end_d:
            if start_d <= today <= end_d:
                active_now.append({
                    "id": p.id,
                    "project_id": p.project_id,
                    "name": p.name,
                    "production": p.production.name if p.production else "—",
                    "shoot_start": str(p.shoot_start_date or ""),
                    "shoot_end": str(p.shoot_end_date or ""),
                })
            elif today < start_d <= in_15_days:
                upcoming_15d.append({
                    "id": p.id,
                    "project_id": p.project_id,
                    "name": p.name,
                    "production": p.production.name if p.production else "—",
                    "shoot_start": str(p.shoot_start_date or ""),
                    "shoot_end": str(p.shoot_end_date or ""),
                })

    # Décharges en attente pour projets futurs/actifs
    pending_pilot_waivers = PilotWaiver.query.filter(PilotWaiver.status != "signed").count()
    pending_prod_waivers = ProductionWaiver.query.filter(ProductionWaiver.status != "signed").count()

    # Pré-devis récents (draft)
    recent_quotes = [
        q.to_dict() for q in PreQuote.query.order_by(PreQuote.created_at.desc()).limit(5).all()
    ]

    return {
        "date": today_str,
        "active_shoots_count": len(active_now),
        "active_shoots": active_now,
        "upcoming_shoots_15d_count": len(upcoming_15d),
        "upcoming_shoots_15d": upcoming_15d,
        "pending_waivers": {
            "pilot_count": pending_pilot_waivers,
            "production_count": pending_prod_waivers,
            "total": pending_pilot_waivers + pending_prod_waivers,
        },
        "recent_pre_quotes": recent_quotes,
    }

