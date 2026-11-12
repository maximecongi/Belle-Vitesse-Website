"""Outils MCP : pointage journalier du matériel (véhicules / têtes) par jour de tournage."""
from typing import Any, Dict, List, Optional

from mcp_server.context import CURRENT_MCP_USER
from mcp_server.core import mcp
from mcp_server.decorators import require_mcp_scope, run_in_flask_context
from mcp_server.tools.projects import _resolve_project


def _mcp_user_id() -> Optional[int]:
    user = CURRENT_MCP_USER.get()
    return getattr(user, "id", None) if user else None


def _compact_state(project, state: Dict[str, Any]) -> Dict[str, Any]:
    """État du pointage, lisible par un assistant : un tableau par matériel."""
    return {
        "project": {"id": project.id, "project_id": project.project_id, "name": project.name},
        "days": [{"date": d["iso"], "label": d["label"]} for d in state["days"]],
        "equipment": [
            {
                "type": e["type"],
                "id": e["id"],
                "name": e["name"],
                "color": e["color"],
                "used_days": e["used_days"],
                "unused_days": e["unused_days"],
                "pending_days": e["pending_days"],
                "marks": state["marks"].get(e["key"], {}),
            }
            for e in state["equipment"]
        ],
        "pending_past_days": state["pending_count"],
        "orphan_marks": state["orphans_count"],
        "states": {"used": "utilisé", "unused": "non utilisé", "none": "non pointé"},
    }


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_equipment_usage(project_id: Any) -> Dict[str, Any]:
    """
    Pointage du matériel d'un projet : pour chaque véhicule / tête engagé, l'état de chaque jour de
    tournage (« used » utilisé, « unused » non utilisé, absent = non pointé) et les totaux.
    - project_id: identifiant numérique ou code BVPR du projet
    """
    p = _resolve_project(project_id)
    if not p:
        return {"status": "error", "message": f"Projet '{project_id}' introuvable."}
    from services.admin.equipment_usage import get_usage_state
    return {"status": "success", **_compact_state(p, get_usage_state(p))}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def set_equipment_usage(project_id: Any, changes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Pointe le matériel d'un projet par jour de tournage (lot tout-ou-rien, tracé dans l'historique).
    - project_id: identifiant numérique ou code BVPR du projet
    - changes: liste de {"equipment": nom ou identifiant du véhicule / de la tête (ex: "eCar"),
      "date": "AAAA-MM-JJ", "state": "used" | "unused" | "none"}.
      Exemple : « l'eCar n'a pas roulé jeudi » → [{"equipment": "eCar", "date": "2026-10-15", "state": "unused"}]
    Seuls le matériel engagé sur le projet et ses jours de tournage sont acceptés.
    """
    p = _resolve_project(project_id)
    if not p:
        return {"status": "error", "message": f"Projet '{project_id}' introuvable."}
    from services.admin.equipment_usage import (
        EquipmentUsageError,
        get_usage_state,
        project_equipment,
        set_equipment_usage as _set_usage,
    )

    equipment = project_equipment(p)
    by_id = {e["id"].lower(): e for e in equipment}
    by_name = {e["name"].strip().lower(): e for e in equipment}
    resolved = []
    for raw in changes or []:
        if not isinstance(raw, dict):
            return {"status": "error", "message": "Chaque pointage doit être un objet {equipment, date, state}."}
        ref = str(raw.get("equipment") or raw.get("equipment_id") or "").strip().lower()
        eq = by_id.get(ref) or by_name.get(ref)
        if eq is None:
            names = ", ".join(e["name"] for e in equipment) or "aucun"
            return {"status": "error",
                    "message": f"Matériel « {raw.get('equipment') or raw.get('equipment_id')} » non engagé sur ce projet "
                               f"(matériel du projet : {names})."}
        resolved.append({"equipment_type": eq["type"], "equipment_id": eq["id"],
                         "date": raw.get("date"), "state": raw.get("state")})
    try:
        state = _set_usage(p.id, resolved, user_id=_mcp_user_id(), source="mcp")
    except EquipmentUsageError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": f"Erreur lors de l'enregistrement du pointage : {e}"}
    return {"status": "success", **_compact_state(p, state or get_usage_state(p))}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_equipment_usage_history(project_id: Any, limit: int = 100) -> Dict[str, Any]:
    """
    Historique des pointages d'un projet (du plus récent au plus ancien) : qui a changé quel
    matériel, pour quel jour, ancien → nouvel état, depuis l'interface (web) ou l'IA (mcp).
    - project_id: identifiant numérique ou code BVPR du projet
    - limit: nombre maximal d'entrées (défaut 100, max 500)
    """
    p = _resolve_project(project_id)
    if not p:
        return {"status": "error", "message": f"Projet '{project_id}' introuvable."}
    from models import ProjectEquipmentUsageLog
    from services.admin.equipment_usage import project_equipment

    names = {(e["type"], e["id"]): e["name"] for e in project_equipment(p)}
    limit = max(1, min(int(limit or 100), 500))
    logs = (ProjectEquipmentUsageLog.query.filter_by(project_id=p.id)
            .order_by(ProjectEquipmentUsageLog.created_at.desc(), ProjectEquipmentUsageLog.id.desc())
            .limit(limit).all())
    entries = []
    for log in logs:
        item = log.to_dict()
        item["equipment_name"] = names.get((log.equipment_type, log.equipment_id), log.equipment_id)
        entries.append(item)
    return {"status": "success", "project_id": p.project_id, "count": len(entries), "history": entries}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_fleet_usage_stats(period: str = "30d") -> Dict[str, Any]:
    """
    Vue d'ensemble de l'utilisation du matériel (tableau de bord) :
    jours utilisés par véhicule / tête sur la période, taux de pointage (90 derniers jours)
    et projets ayant des jours de tournage passés non pointés.
    - period: "30d" (30 derniers jours, défaut) ou "year" (année en cours)
    """
    from services.admin.equipment_stats import dashboard_usage_context

    ctx = dashboard_usage_context(period=period)
    ranking = ctx["ranking"]
    return {
        "status": "success",
        "period": ranking["period"],
        "period_label": ranking["period_label"],
        "since": ranking["start"].isoformat(),
        "usage_by_equipment": [
            {k: i[k] for k in ("type", "id", "name", "color", "used_days")} for i in ranking["rows"]
        ],
        "pointing_rate": ctx["pointing"],
        "projects_to_point": [
            {**p, "last_day": p["last_day"].isoformat() if p["last_day"] else None}
            for p in ctx["pending_projects"]
        ],
    }


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_equipment_usage_stats(equipment: str, year: Optional[int] = None) -> Dict[str, Any]:
    """
    Statistiques d'utilisation d'un véhicule ou d'une tête : jours utilisés par mois sur l'année,
    sur 12 mois glissants, au total, taux d'utilisation et jours utilisés par projet.
    - equipment: nom ou identifiant du véhicule / de la tête (ex: "eRider")
    - year: année (défaut : année en cours)
    """
    from models import Head, Project, Vehicle
    from services.admin.equipment_stats import equipment_usage_stats

    ref = str(equipment or "").strip().lower()
    found = None
    for eq_type, model in (("vehicle", Vehicle), ("head", Head)):
        for rec in model.query.all():
            f = rec.fields if isinstance(rec.fields, dict) else {}
            candidates = {str(rec.id).lower(), str(f.get("name") or "").strip().lower(),
                          str(f.get("slug") or "").strip().lower(), str(f.get("unique_id") or "").strip().lower()}
            if ref and ref in candidates:
                found = (eq_type, str(rec.id), f.get("name") or str(rec.id))
                break
        if found:
            break
    if not found:
        return {"status": "error", "message": f"Matériel « {equipment} » introuvable."}

    stats = equipment_usage_stats(found[0], found[1], year=year)
    projects = {p.id: p for p in Project.query.filter(Project.id.in_(list(stats["per_project"]) or [0])).all()}
    return {
        "status": "success",
        "equipment": {"type": found[0], "id": found[1], "name": found[2]},
        "year": stats["year"],
        "used_days_year": stats["used_year"],
        "used_days_12_months": stats["used_12m"],
        "used_days_total": stats["used_total"],
        "unused_days_total": stats["unused_total"],
        "usage_rate_percent": stats["usage_rate"],
        "by_month": [{"month": m["label_full"], "used_days": m["count"]} for m in stats["months"]],
        "by_project": [
            {"project_id": projects[pid].project_id if pid in projects else pid,
             "name": projects[pid].name if pid in projects else None, "used_days": n}
            for pid, n in sorted(stats["per_project"].items(), key=lambda kv: -kv[1])
        ],
    }
