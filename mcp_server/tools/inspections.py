"""Outils MCP : Domaine Inspections (Checkouts / Checkins)."""
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def list_checkouts() -> Dict[str, Any]:
    """Liste tous les formulaires d'inspection Checkout (départ véhicule) et statistiques."""
    from services.admin.checkouts import list_checkouts as _list
    return _list()


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def list_checkins() -> Dict[str, Any]:
    """Liste tous les formulaires d'inspection Checkin (retour véhicule) et statistiques."""
    from services.admin.checkins import list_checkins as _list
    return _list()


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_inspection_detail(mode: str, record_id: int) -> Optional[Dict[str, Any]]:
    """
    Récupère le détail complet d'une inspection.
    - mode: 'checkout' ou 'checkin'
    - record_id: ID de la fiche d'inspection
    """
    if mode.lower() == "checkout":
        from services.admin.checkouts import get_checkout_detail
        return get_checkout_detail(record_id)
    elif mode.lower() == "checkin":
        from services.admin.checkins import get_checkin_detail
        return get_checkin_detail(record_id)
    return None


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def delete_inspection(mode: str, record_id: int, confirm: bool = False) -> Dict[str, Any]:
    """
    Supprime définitivement un enregistrement d'inspection (checkout ou checkin).
    ATTENTION: Action destructrice (Scope 'admin' requis).
    L'IA doit obligatoirement l'exécuter d'abord avec confirm=False pour simuler l'impact et demander la confirmation à l'utilisateur humain.
    """
    from services.admin.inspections import delete_inspection_unified as _delete
    if mode.lower() not in ("checkout", "checkin"):
        return {"success": False, "message": "Mode invalide. Utilisez 'checkout' ou 'checkin'."}

    if not confirm:
        return {
            "success": False,
            "status": "requires_confirmation",
            "mode": mode,
            "record_id": record_id,
            "message": (
                f"⚠️ ATTENTION : Vous êtes sur le point de supprimer la fiche d'inspection {mode.upper()} #{record_id}. "
                "Veuillez demander la confirmation explicite à l'utilisateur humain devant son écran, "
                "puis ré-exécutez cet outil avec confirm=True."
            )
        }

    success = _delete(mode.lower(), record_id)
    return {"success": success, "message": f"Inspection {mode} #{record_id} supprimée avec succès." if success else "Échec de la suppression."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_inspection_form_context(
    mode: str = "checkout",
    project_id: Optional[int] = None,
    category: Optional[str] = None,
    compact: Optional[bool] = True,
) -> Dict[str, Any]:
    """
    Récupère le contexte nécessaire à la création/édition d'un départ (checkout) ou retour (checkin).
    - mode: 'checkout' (départ) ou 'checkin' (retour)
    - project_id: Filtrer sur un projet spécifique
    - category: Filtrer un seul sous-ensemble ('projects', 'vehicles', 'users')
    - compact: True par défaut pour optimiser l'usage des tokens
    """
    from services.admin.checkouts import get_checkout_form_context

    raw = get_checkout_form_context()
    if not compact:
        if category and category.lower() in raw:
            return {category.lower(): raw[category.lower()]}
        return raw

    # Version compacte épurée
    raw_projects = raw.get("projects", [])
    if project_id:
        selected_projects = [p for p in raw_projects if str(p.get("id")) == str(project_id)]
    else:
        selected_projects = raw_projects

    compact_projects = [
        {
            "id": int(p["id"]) if str(p.get("id", "")).isdigit() else p.get("id"),
            "name": p.get("fields", {}).get("Nom") or p.get("name"),
            "production": p.get("fields", {}).get("_production_name"),
            "departure_date": p.get("fields", {}).get("Date de départ"),
            "shoot_start": p.get("fields", {}).get("Date de début de tournage"),
            "shoot_end": p.get("fields", {}).get("Date de fin de tournage"),
            "vehicles_to_check": p.get("fields", {}).get("Véhicules à contrôler", []),
            "main_vehicle_name": p.get("fields", {}).get("_vehicle_name"),
        }
        for p in selected_projects
    ]

    compact_vehicles = [
        {
            "id": v.get("id"),
            "name": v.get("fields", {}).get("name") or v.get("id"),
            "is_blocked": bool(v.get("fields", {}).get("_blocked_by")),
            "blocked_by": v.get("fields", {}).get("_blocked_by"),
        }
        for v in raw.get("vehicles", [])
    ]

    compact_users = [
        {
            "id": int(u["id"]) if str(u.get("id", "")).isdigit() else u.get("id"),
            "name": f"{u.get('fields', {}).get('firstname', '')} {u.get('fields', {}).get('lastname', '')}".strip(),
        }
        for u in raw.get("users", [])
    ]

    res = {
        "mode": mode.lower(),
        "projects": compact_projects,
        "vehicles": compact_vehicles,
        "users": compact_users,
        "checkpoints_note": "Utilisez l'outil 'get_checkpoints_for_vehicle(vehicle_id)' pour obtenir les points de contrôle d'un véhicule spécifique.",
    }

    cat_map = {
        "projects": "projects",
        "project": "projects",
        "vehicles": "vehicles",
        "vehicle": "vehicles",
        "users": "users",
        "user": "users",
    }

    if category:
        key = cat_map.get(category.lower())
        if key and key in res:
            return {key: res[key]}

    return res

