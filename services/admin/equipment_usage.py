"""
Pointage journalier du matériel (véhicules et têtes) par jour de tournage.

Pour chaque jour de tournage d'un projet, l'équipe indique si chaque matériel engagé a été
utilisé ou non. Trois états : non pointé (aucune ligne), utilisé, non utilisé.
Les données servent à la facturation au réel, aux statistiques flotte et à la maintenance.
"""
import logging
from datetime import date, datetime, timezone

from flask import current_app, render_template

from models import db
from models.equipment_usage import EQUIPMENT_TYPES, ProjectEquipmentUsage, ProjectEquipmentUsageLog
from services.admin.equipment_colors import DEFAULT_COLOR, get_color_map
from utils.database import get_heads, get_vehicles
from utils.document_utils import render_pdf_from_template
from utils.entity_resolvers import resolve_project
from utils.formatting import get_today_paris

logger = logging.getLogger(__name__)

# États acceptés côté API
STATE_USED = "used"
STATE_UNUSED = "unused"
STATE_NONE = "none"
_STATES = (STATE_USED, STATE_UNUSED, STATE_NONE)


_EQUIPMENT_TYPE_LABELS = {"vehicle": "Véhicule", "head": "Tête"}


class EquipmentUsageError(ValueError):
    """Requête de pointage invalide (matériel non engagé, jour hors tournage, état inconnu…)."""


# ── Jours et matériel pointables ───────────────────────────────


def usage_days(project) -> list:
    """Jours pointables : les jours de tournage du projet (mêmes jours que les rapports d'équipe)."""
    from services.admin.project_reports import project_shoot_days
    return project_shoot_days(project)


def _day_label(project, d, days=None):
    from services.admin.project_reports import _format_day_fr
    days = days if days is not None else usage_days(project)
    prefix = f"J{days.index(d) + 1} · " if d in days else ""
    return f"{prefix}{_format_day_fr(d)}"


def project_equipment(project, vehicle_map=None, heads_map=None) -> list:
    """Matériel engagé sur le projet, dans l'ordre d'affichage (véhicules puis têtes)."""
    if vehicle_map is None:
        vehicle_map = {v["id"]: v.get("fields", {}) for v in (get_vehicles() or [])}
    if heads_map is None:
        heads_map = {h["id"]: h.get("fields", {}) for h in (get_heads() or [])}

    items = []
    for vid in project.vehicle_ids_list:
        f = vehicle_map.get(vid, {}) or {}
        items.append({
            "type": "vehicle",
            "id": vid,
            "name": f.get("name") or f.get("Nom") or "Véhicule",
            "code": f.get("unique_id") or "",
        })
    for hid in project.head_ids_list:
        f = heads_map.get(hid, {}) or {}
        items.append({
            "type": "head",
            "id": hid,
            "name": f.get("name") or "Tête",
            "code": f.get("brand") or "",
        })
    # Couleur fixe du matériel (identique sur tous les projets, modifiable depuis la page Flotte)
    color_map = get_color_map() if items else {}
    for item in items:
        item["key"] = f"{item['type']}:{item['id']}"
        item["color"] = color_map.get((item["type"], str(item["id"])), DEFAULT_COLOR)
        item["type_label"] = _EQUIPMENT_TYPE_LABELS[item["type"]]
    return items


def _equipment_keys(project) -> set:
    return {f"vehicle:{v}" for v in project.vehicle_ids_list} | {f"head:{h}" for h in project.head_ids_list}


# ── Lecture de l'état ──────────────────────────────────────────


def pending_usage_count(project, today=None, entries=None) -> int:
    """
    Nombre de jours de tournage passés (aujourd'hui inclus) où au moins un matériel engagé
    n'est pas encore pointé. Sert de rappel « X jours à pointer ».
    """
    keys = _equipment_keys(project)
    if not keys:
        return 0
    today = today or get_today_paris()
    past_days = [d for d in usage_days(project) if d <= today]
    if not past_days:
        return 0
    entries = entries if entries is not None else (project.equipment_usage or [])
    marked = {(e.key, e.usage_date) for e in entries}
    return sum(1 for d in past_days if any((k, d) not in marked for k in keys))


def get_usage_state(project, vehicle_map=None, heads_map=None, today=None) -> dict:
    """
    État complet du pointage pour le hub projet et l'API :
    jours, matériel, marques par matériel, totaux et pointages orphelins.
    """
    today = today or get_today_paris()
    days = usage_days(project)
    day_set = set(days)
    equipment = project_equipment(project, vehicle_map, heads_map)
    keys = {e["key"] for e in equipment}
    entries = list(project.equipment_usage or [])

    marks = {e["key"]: {} for e in equipment}
    orphans = 0
    for entry in entries:
        if entry.key in keys and entry.usage_date in day_set:
            marks[entry.key][entry.usage_date.isoformat()] = STATE_USED if entry.used else STATE_UNUSED
        else:
            orphans += 1

    for e in equipment:
        m = marks[e["key"]]
        e["used_days"] = sum(1 for s in m.values() if s == STATE_USED)
        e["unused_days"] = sum(1 for s in m.values() if s == STATE_UNUSED)
        e["pending_days"] = len(days) - len(m)

    return {
        "days": [{"iso": d.isoformat(), "label": _day_label(project, d, days), "is_past": d <= today} for d in days],
        "equipment": equipment,
        "marks": marks,
        "pending_count": pending_usage_count(project, today, entries),
        "orphans_count": orphans,
    }


# ── Écriture ───────────────────────────────────────────────────


def _parse_day(value) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value or "").strip()[:10])
    except ValueError:
        raise EquipmentUsageError("Jour invalide (format attendu : AAAA-MM-JJ).")


def set_equipment_usage(project_id, changes, user_id=None, source="web") -> dict:
    """
    Applique un lot de pointages. `changes` : liste de dicts
    {"equipment_type": "vehicle"|"head", "equipment_id": str, "date": "AAAA-MM-JJ", "state": "used"|"unused"|"none"}.
    Le lot est validé intégralement avant écriture (tout ou rien). Chaque changement réel est
    tracé dans l'historique (ProjectEquipmentUsageLog, `source` = 'web' ou 'mcp'). Retourne l'état à jour.
    """
    project = resolve_project(project_id)
    if not project or project.deleted_at is not None:
        raise LookupError("Projet introuvable.")
    if not isinstance(changes, list) or not changes:
        raise EquipmentUsageError("Aucun pointage à enregistrer.")
    if len(changes) > 2000:
        raise EquipmentUsageError("Trop de pointages dans une seule requête.")

    keys = _equipment_keys(project)
    day_set = set(usage_days(project))

    # 1. Validation complète du lot (la dernière valeur l'emporte pour un même couple matériel × jour)
    normalized = {}
    for raw in changes:
        if not isinstance(raw, dict):
            raise EquipmentUsageError("Format de pointage invalide.")
        eq_type = str(raw.get("equipment_type") or "").strip()
        eq_id = str(raw.get("equipment_id") or "").strip()
        state = str(raw.get("state") or "").strip().lower()
        if eq_type not in EQUIPMENT_TYPES:
            raise EquipmentUsageError("Type de matériel inconnu.")
        if f"{eq_type}:{eq_id}" not in keys:
            raise EquipmentUsageError("Ce matériel n'est pas engagé sur le projet.")
        if state not in _STATES:
            raise EquipmentUsageError("État de pointage inconnu.")
        day = _parse_day(raw.get("date"))
        if day not in day_set:
            raise EquipmentUsageError("Ce jour n'est pas un jour de tournage du projet.")
        normalized[(eq_type, eq_id, day)] = state

    # 2. Écriture
    existing = {
        (e.equipment_type, e.equipment_id, e.usage_date): e
        for e in ProjectEquipmentUsage.query.filter_by(project_id=project.id).all()
    }
    try:
        for (eq_type, eq_id, day), state in normalized.items():
            entry = existing.get((eq_type, eq_id, day))
            old_state = STATE_NONE if entry is None else (STATE_USED if entry.used else STATE_UNUSED)
            if old_state != state:
                # Historique : uniquement les changements réels
                db.session.add(ProjectEquipmentUsageLog(
                    project_id=project.id, equipment_type=eq_type, equipment_id=eq_id, usage_date=day,
                    old_state=old_state, new_state=state, user_id=user_id, source=source,
                ))
            if state == STATE_NONE:
                if entry is not None:
                    db.session.delete(entry)
                continue
            used = state == STATE_USED
            if entry is None:
                db.session.add(ProjectEquipmentUsage(
                    project_id=project.id, equipment_type=eq_type, equipment_id=eq_id,
                    usage_date=day, used=used, updated_by_id=user_id,
                ))
            elif entry.used != used:
                entry.used = used
                entry.updated_by_id = user_id
        if user_id:
            project.last_action_by_id = user_id
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    db.session.expire(project, ["equipment_usage"])
    return get_usage_state(project)


# ── Relevé d'utilisation (PDF) ─────────────────────────────────


def build_usage_export_context(project_id):
    """Données du relevé d'utilisation du matériel (tableau jours × matériel + totaux)."""
    project = resolve_project(project_id)
    if not project or project.deleted_at is not None:
        return None
    from services.admin.project_reports import _format_datetime_fr

    state = get_usage_state(project)
    rows = []
    for day in state["days"]:
        rows.append({
            "label": day["label"],
            "cells": [state["marks"][e["key"]].get(day["iso"], STATE_NONE) for e in state["equipment"]],
        })
    days = usage_days(project)
    if days:
        from services.admin.project_reports import _format_day_fr
        period = _format_day_fr(days[0]) if len(days) == 1 else f"{_format_day_fr(days[0])} → {_format_day_fr(days[-1])}"
    else:
        period = "Dates à confirmer"
    return {
        "project": project,
        "equipment": state["equipment"],
        "rows": rows,
        "days_count": len(days),
        "period_label": period,
        "pending_count": sum(e["pending_days"] for e in state["equipment"]),
        "orphans_count": state["orphans_count"],
        "generated_at_fr": _format_datetime_fr(datetime.now(timezone.utc)),
    }


def generate_equipment_usage_pdf(project_id, base_url=None):
    """Compile le relevé d'utilisation du matériel en PDF. Retourne (bytes, nom de fichier)."""
    ctx = build_usage_export_context(project_id)
    if ctx is None:
        return None, None
    project = ctx["project"]
    company_name = current_app.config.get("COMPANY_NAME", "Belle Vitesse")
    html = render_template(
        "pdf/equipment_usage.html",
        company_name=company_name,
        doc_id=project.project_id,
        is_preview=False,
        **ctx,
    )
    filename = f"Releve-utilisation-{project.project_id or project.id}.pdf"
    pdf = render_pdf_from_template(
        html_content=html,
        base_url=base_url or "http://localhost",
        stylesheets=["css/pdf/equipment-usage-pdf.css"],
        filename=filename,
        compress=True,
    )
    return pdf, filename
