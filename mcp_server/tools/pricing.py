"""Outils MCP : Domaine Tarification & Grilles Tarifaires."""
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_equipment_rates(
    category: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Récupère la grille tarifaire des équipements et véhicules (véhicules, têtes, accessoires).
    - category: 'vehicles', 'heads', 'grip_products' ou None pour tous
    - query: Recherche par nom d'équipement
    """
    from services.admin.pricing import list_equipment_rates as _list
    from mcp_server.utils import matches_search_query

    raw = _list()
    if category and category.lower() in raw:
        raw = {category.lower(): raw[category.lower()]}

    if query:
        filtered_res = {}
        for cat_key, cat_data in raw.items():
            matching_items = [
                item for item in cat_data.get("items", [])
                if matches_search_query(item, query, ["name", "id"])
            ]
            filtered_res[cat_key] = {
                **cat_data,
                "items": matching_items,
            }
        return filtered_res

    return raw


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_equipment_daily_rate(table_name: str, record_id: str, value: float) -> Dict[str, Any]:
    """Met à jour le tarif journalier d'un équipement ou d'un véhicule."""
    from services.admin.pricing import update_equipment_daily_rate as _update
    res = _update(table_name, str(record_id), value)
    return {"success": res is not None, "item": res, "message": f"Tarif mis à jour à {value} €." if res else "Échec."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_salary_rates(
    query: Optional[str] = None,
    annexe: Optional[str] = None,
    group_name: Optional[str] = None,
    limit: Optional[int] = 50,
    offset: Optional[int] = 0,
) -> List[Dict[str, Any]]:
    """
    Récupère les tarifs salariaux des techniciens / pilotes avec recherche, filtres et pagination.
    - query: Recherche par nom de poste/rôle (ex: 'pilote', 'cadreur', 'assistant')
    - annexe: Filtrer par convention ('Annexe 1', 'Annexe 2', 'Annexe 3', 'Annexe 1 renfort')
    - group_name: Filtrer par groupe de métier (ex: 'PILOTES', 'CADRAGE', 'RÉGIE')
    - limit: Nombre max de résultats retournés (défaut 50, max 500)
    - offset: Décalage de pagination
    """
    from services.admin.pricing import list_salary_rates as _list
    from mcp_server.utils import matches_search_query, apply_pagination

    all_rates = _list()
    filtered = []
    for r in all_rates:
        if annexe and r.get("annexe", "").lower() != annexe.strip().lower():
            continue
        if group_name and r.get("group_name", "").lower() != group_name.strip().lower():
            continue
        if query and not matches_search_query(r, query, ["position", "position_name", "name", "group_name", "annexe", "notes", "role"]):
            continue
        filtered.append(r)

    return apply_pagination(filtered, limit=limit, offset=offset)


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_salary_rate(rate_id: int, field: str, value: Any) -> Dict[str, Any]:
    """Met à jour un champ spécifique d'un tarif salarial de rôle/technicien."""
    from services.admin.pricing import update_salary_rate as _update
    success = _update(rate_id, field, value)
    return {"success": success is not None, "message": f"Tarif salarial #{rate_id} mis à jour." if success else "Échec."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def delete_salary_rate(rate_id: int, confirm: bool = False) -> Dict[str, Any]:
    """
    Supprime un tarif salarial de rôle par son ID.
    ATTENTION: Action destructrice (Scope 'admin' requis).
    """
    from services.admin.pricing import delete_salary_rate as _delete
    if not confirm:
        return {
            "success": False,
            "status": "requires_confirmation",
            "rate_id": rate_id,
            "message": f"⚠️ ATTENTION : Vous êtes sur le point de supprimer le tarif salarial #{rate_id}. Confirmez avec confirm=True."
        }
    success = _delete(rate_id)
    return {"success": success, "message": f"Tarif salarial #{rate_id} supprimé." if success else "Échec."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_logistics_rates(
    query: Optional[str] = None,
    limit: Optional[int] = 50,
    offset: Optional[int] = 0,
) -> List[Dict[str, Any]]:
    """
    Récupère les tarifs logistiques (kilométrage, carburant, convoyage) avec recherche et pagination.
    - query: Recherche par libellé ou description
    - limit: Nombre max d'éléments (défaut 50, max 500)
    - offset: Décalage de pagination
    """
    from services.admin.pricing import list_logistics_rates as _list
    from mcp_server.utils import matches_search_query, apply_pagination

    all_rates = _list()
    filtered = []
    for r in all_rates:
        if query and not matches_search_query(r, query, ["name", "label", "description", "category"]):
            continue
        filtered.append(r)

    return apply_pagination(filtered, limit=limit, offset=offset)


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_logistics_rate(rate_id: int, field: str, value: Any) -> Dict[str, Any]:
    """Met à jour un tarif logistique par son ID."""
    from services.admin.pricing import update_logistics_rate as _update
    success = _update(rate_id, field, value)
    return {"success": success is not None, "message": f"Tarif logistique #{rate_id} mis à jour." if success else "Échec."}

