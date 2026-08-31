"""Outils MCP : Domaine Pré-Devis & Devis."""
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


def _format_pre_quote(pq) -> Dict[str, Any]:
    if not pq:
        return {}
    data = pq.to_dict() if hasattr(pq, "to_dict") else dict(pq)
    data["prestations"] = pq.prestations or []
    data["versions"] = [
        v.to_dict() if hasattr(v, "to_dict") else dict(v)
        for v in getattr(pq, "versions", [])
    ]
    return data


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def list_pre_quotes(
    project_id: Optional[int] = None,
    production_id: Optional[int] = None,
    status: Optional[str] = None,
    query: Optional[str] = None,
    limit: Optional[int] = 50,
    offset: Optional[int] = 0,
) -> List[Dict[str, Any]]:
    """
    Liste les pré-devis avec filtres et pagination.
    - project_id: Filtrer par ID de projet associé
    - production_id: Filtrer par ID de société de production
    - status: 'draft', 'sent', 'accepted', etc.
    - query: Recherche par référence (DP-...), nom de projet ou nom de production
    - limit: Nombre max d'éléments (défaut 50, max 500)
    - offset: Décalage de pagination
    """
    from services.admin.pre_quote import list_pre_quotes as _list
    from mcp_server.utils import matches_search_query, apply_pagination

    quotes = _list()
    filtered = []
    for q in quotes:
        if project_id is not None and getattr(q, "project_id", None) != project_id:
            continue
        if production_id is not None and getattr(q, "production_id", None) != production_id:
            continue
        if status and status.lower() != "all" and getattr(q, "status", "").lower() != status.lower():
            continue

        formatted = _format_pre_quote(q)
        if query and not matches_search_query(formatted, query, ["reference", "project_name", "production_name", "status"]):
            continue

        filtered.append(formatted)

    return apply_pagination(filtered, limit=limit, offset=offset)


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_pre_quote(pre_quote_id: int) -> Optional[Dict[str, Any]]:
    """Récupère le détail d'un pré-devis par son ID."""
    from models import PreQuote, db
    pq = db.session.get(PreQuote, pre_quote_id)
    return _format_pre_quote(pq) if pq else None


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def create_pre_quote(
    project_id: Optional[int] = None,
    production_id: Optional[int] = None,
    version_label: Optional[str] = "V1",
    items: Optional[List[Dict[str, Any]]] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Crée un nouveau pré-devis pour un projet ou une société de production avec ses lignes d'équipements / prestations."""
    from services.admin.pre_quote import create_pre_quote as _create
    if project_id and not production_id:
        from models import Project, db
        proj = db.session.get(Project, project_id)
        if proj:
            production_id = proj.production_id

    if not production_id:
        from models import Production
        first_prod = Production.query.first()
        if first_prod:
            production_id = first_prod.id

    form_data = {
        "project_id": project_id,
        "production_id": production_id,
        "version_label": version_label or "V1",
        "prestations": items or [],
        "notes": notes or "",
    }
    pq = _create(form_data)
    return {"success": pq is not None, "pre_quote_id": pq.id if pq else None, "reference": pq.reference if pq else None, "message": "Pré-devis créé avec succès." if pq else "Échec de création."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def duplicate_pre_quote(
    pre_quote_id: int,
    new_project_name: Optional[str] = None,
    production_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Duplique un pré-devis existant avec l'ensemble de ses lignes de prestations pour créer un nouveau devis distinct.
    """
    from models import PreQuote, db
    from services.admin.pre_quote import create_pre_quote as _create

    orig = db.session.get(PreQuote, pre_quote_id)
    if not orig:
        return {"success": False, "message": f"Pré-devis source #{pre_quote_id} introuvable."}

    target_prod_id = production_id if production_id is not None else orig.production_id
    target_project_name = new_project_name if new_project_name is not None else f"{orig.project_name or 'Projet'} (Copie)"

    form_data = {
        "production_id": target_prod_id,
        "project_name": target_project_name,
        "version_label": "V1",
        "prestations": list(orig.prestations or []),
        "tva_rate": float(orig.tva_rate) if orig.tva_rate is not None else 20.0,
        "insurance_rate": float(orig.insurance_rate) if orig.insurance_rate is not None else 10.0,
        "insurance_based_on_undiscounted": bool(orig.insurance_based_on_undiscounted),
        "notes": f"Dupliqué depuis {orig.reference}",
    }

    new_pq = _create(form_data)
    return {
        "success": new_pq is not None,
        "new_pre_quote_id": new_pq.id if new_pq else None,
        "reference": new_pq.reference if new_pq else None,
        "message": f"Pré-devis dupliqué avec succès : {new_pq.reference}" if new_pq else "Échec de la duplication.",
    }


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_pre_quote(
    pre_quote_id: int,
    items: Optional[List[Dict[str, Any]]] = None,
    notes: Optional[str] = None,
    production_id: Optional[int] = None,
    project_name: Optional[str] = None,
    status: Optional[str] = None,
    show_discounts: Optional[bool] = None,
) -> Dict[str, Any]:
    """Met à jour un pré-devis existant (mode patch : conserve les champs non spécifiés)."""
    from models import PreQuote, db
    from services.admin.pre_quote import update_pre_quote as _update

    pq = db.session.get(PreQuote, pre_quote_id)
    if not pq:
        return {"success": False, "message": f"Pré-devis #{pre_quote_id} introuvable."}

    form_data = {}
    if items is not None:
        form_data["prestations"] = items
    if notes is not None:
        form_data["notes"] = notes
    if production_id is not None:
        form_data["production_id"] = production_id
    if project_name is not None:
        form_data["project_name"] = project_name
    if status is not None:
        form_data["status"] = status
    if show_discounts is not None:
        form_data["show_discounts"] = show_discounts

    updated_pq = _update(pre_quote_id, form_data)
    return {"success": updated_pq is not None, "message": "Pré-devis mis à jour." if updated_pq else "Échec de mise à jour."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def delete_pre_quote(pre_quote_id: int, confirm: bool = False) -> Dict[str, Any]:
    """
    Supprime un pré-devis par son ID.
    ATTENTION: Action destructrice (Scope 'admin' requis).
    """
    from models import PreQuote, db
    from services.admin.pre_quote import delete_pre_quote as _delete
    pq = db.session.get(PreQuote, pre_quote_id)
    if not pq:
        return {"success": False, "message": f"Pré-devis #{pre_quote_id} introuvable."}

    if not confirm:
        return {
            "success": False,
            "status": "requires_confirmation",
            "pre_quote_id": pre_quote_id,
            "reference": pq.reference,
            "message": f"⚠️ ATTENTION : Vous êtes sur le point de supprimer le pré-devis #{pre_quote_id} ({pq.reference}). Confirmez avec confirm=True."
        }

    success = _delete(pre_quote_id)
    return {"success": success, "message": f"Pré-devis #{pre_quote_id} supprimé avec succès." if success else "Échec de suppression."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def create_pre_quote_version(pre_quote_id: int, version_label: str) -> Dict[str, Any]:
    """Duplique un pré-devis sous une nouvelle version (ex: V2, V3)."""
    from services.admin.pre_quote import create_pre_quote_version as _version
    ver = _version(pre_quote_id, version_label)
    return {"success": ver is not None, "new_version_id": ver.id if ver else None, "version_number": ver.version_number if ver else None, "message": f"Version {version_label} créée." if ver else "Échec."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_pre_quote_form_context(
    project_id: Optional[int] = None,
    category: Optional[str] = None,
    compact: Optional[bool] = True,
) -> Dict[str, Any]:
    """
    Récupère le contexte du formulaire pré-devis (paramètres livraison, projets, tarifs).
    - project_id: ID du projet spécifique (évite de charger tous les projets de la base)
    - category: Filtrer sur un domaine précis ('delivery', 'projects', 'equipment', 'salaries', 'logistics') ou None pour tout
    - compact: Si True (par défaut), optimise et allège le volume de données retourné pour économiser les tokens
    """
    from services.admin.pre_quote import get_delivery_config
    from services.admin.projects import list_projects
    from services.admin.pricing import list_equipment_rates, list_salary_rates, list_logistics_rates

    # Projets
    raw_projects = list_projects()
    if project_id:
        selected_projects = [p for p in raw_projects if p.get("id") == project_id]
    else:
        selected_projects = raw_projects

    if compact:
        proj_data = [
            {
                "id": p.get("id"),
                "project_id": p.get("project_id"),
                "name": p.get("name"),
                "production_name": p.get("production_name"),
                "departure_date": p.get("departure_date"),
                "shoot_start": p.get("shoot_start"),
                "shoot_end": p.get("shoot_end"),
                "return_date": p.get("return_date"),
                "vehicles": p.get("vehicles", []),
                "heads": p.get("heads", []),
            }
            for p in selected_projects
        ]
    else:
        proj_data = selected_projects

    # Équipements
    raw_eq = list_equipment_rates()
    if compact:
        eq_data = {}
        for cat_key, cat_val in raw_eq.items():
            eq_data[cat_key] = [
                {"id": it.get("id"), "name": it.get("name"), "daily_rate": it.get("daily_rate")}
                for it in cat_val.get("items", [])
            ]
    else:
        eq_data = raw_eq

    # Salaires
    raw_sal = list_salary_rates()
    if compact:
        sal_data = [
            {
                "id": r.get("id"),
                "position": r.get("position"),
                "group_name": r.get("group_name"),
                "annexe": r.get("annexe"),
                "invoice_8h": r.get("invoice_8h"),
                "invoice_10h": r.get("invoice_10h"),
            }
            for r in raw_sal
        ]
    else:
        sal_data = raw_sal

    # Logistique
    raw_log = list_logistics_rates()
    if compact:
        log_data = [
            {"id": l.get("id"), "name": l.get("name") or l.get("label"), "amount": l.get("amount") or l.get("rate")}
            for l in raw_log
        ]
    else:
        log_data = raw_log

    delivery_data = get_delivery_config()

    full_response = {
        "delivery_config": delivery_data,
        "projects": proj_data,
        "equipment_rates": eq_data,
        "salary_rates": sal_data,
        "logistics_rates": log_data,
    }

    # Mapping category
    cat_map = {
        "delivery": "delivery_config",
        "delivery_config": "delivery_config",
        "projects": "projects",
        "project": "projects",
        "equipment": "equipment_rates",
        "equipment_rates": "equipment_rates",
        "salaries": "salary_rates",
        "salary_rates": "salary_rates",
        "logistics": "logistics_rates",
        "logistics_rates": "logistics_rates",
    }

    if category:
        key = cat_map.get(category.lower())
        if key and key in full_response:
            return {key: full_response[key]}

    return full_response

