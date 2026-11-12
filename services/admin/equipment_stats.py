"""
Statistiques d'utilisation du matériel, calculées à partir du pointage journalier
(ProjectEquipmentUsage) : fiche véhicule, tableau de bord, rappel quotidien, outils MCP.

Définitions :
- jour utilisé      : couple matériel × jour de tournage pointé « utilisé » ;
- taux d'utilisation : jours utilisés / jours pointés (utilisé + non utilisé) ;
- taux de pointage   : couples matériel × jour de tournage passés pointés / couples attendus.
"""
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import selectinload

from models import Head, Project, Vehicle
from models.equipment_usage import ProjectEquipmentUsage
from services.admin.equipment_colors import DEFAULT_COLOR, get_color_map
from utils.formatting import get_today_paris

_MONTHS_SHORT_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
                    "juil.", "août", "sept.", "oct.", "nov.", "déc."]
_MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin",
              "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

USAGE_PERIODS = {"30d": "30 derniers jours", "year": "Année en cours"}
POINTING_RATE_WINDOW_DAYS = 90


def _rate(num, den):
    return round(100 * num / den) if den else None


def _active_usage_query():
    """Pointages des projets non supprimés."""
    return (ProjectEquipmentUsage.query
            .join(Project, Project.id == ProjectEquipmentUsage.project_id)
            .filter(Project.deleted_at.is_(None)))


# ── Fiche matériel ─────────────────────────────────────────────


def equipment_usage_stats(equipment_type, equipment_id, year=None, today=None):
    """
    Statistiques d'un véhicule / d'une tête :
    jours utilisés sur l'année (par mois), sur 12 mois glissants, au total, taux d'utilisation
    et jours utilisés par projet.
    """
    today = today or get_today_paris()
    year = int(year or today.year)
    entries = (_active_usage_query()
               .filter(ProjectEquipmentUsage.equipment_type == equipment_type,
                       ProjectEquipmentUsage.equipment_id == str(equipment_id))
               .all())

    months = [0] * 12
    used_total = unused_total = used_12m = 0
    per_project = {}
    window_start = today - timedelta(days=365)
    years = {today.year}
    for e in entries:
        years.add(e.usage_date.year)
        if e.used:
            used_total += 1
            per_project[e.project_id] = per_project.get(e.project_id, 0) + 1
            if e.usage_date.year == year:
                months[e.usage_date.month - 1] += 1
            if window_start < e.usage_date <= today:
                used_12m += 1
        else:
            unused_total += 1

    peak = max(months) or 1
    return {
        "year": year,
        "prev_year": year - 1 if (year - 1) >= min(years) else None,
        "next_year": year + 1 if (year + 1) <= today.year else None,
        "used_year": sum(months),
        "used_12m": used_12m,
        "used_total": used_total,
        "unused_total": unused_total,
        "usage_rate": _rate(used_total, used_total + unused_total),
        "months": [
            {"label": _MONTHS_SHORT_FR[i], "label_full": f"{_MONTHS_FR[i]} {year}", "count": c,
             "pct": round(100 * c / peak), "is_current": (year == today.year and i == today.month - 1)}
            for i, c in enumerate(months)
        ],
        "per_project": per_project,
    }


# ── Tableau de bord ────────────────────────────────────────────


def _period_start(period, today):
    if period == "year":
        return date(today.year, 1, 1)
    return today - timedelta(days=29)


def fleet_usage_ranking(period="30d", today=None):
    """
    Classement de tout le matériel du catalogue (véhicules puis têtes) par jours utilisés
    sur la période (« 30d » : 30 derniers jours, « year » : année en cours).
    """
    today = today or get_today_paris()
    period = period if period in USAGE_PERIODS else "30d"
    start = _period_start(period, today)
    rows = (_active_usage_query()
            .with_entities(ProjectEquipmentUsage.equipment_type, ProjectEquipmentUsage.equipment_id,
                           func.count(ProjectEquipmentUsage.id))
            .filter(ProjectEquipmentUsage.used.is_(True),
                    ProjectEquipmentUsage.usage_date >= start,
                    ProjectEquipmentUsage.usage_date <= today)
            .group_by(ProjectEquipmentUsage.equipment_type, ProjectEquipmentUsage.equipment_id)
            .all())
    counts = {(t, str(i)): n for t, i, n in rows}
    colors = get_color_map()

    items = []
    for eq_type, model in (("vehicle", Vehicle), ("head", Head)):
        for rec in model.query.order_by(model.display_order, model.id).all():
            f = rec.fields if isinstance(rec.fields, dict) else {}
            items.append({
                "type": eq_type,
                "id": str(rec.id),
                "name": f.get("name") or f.get("Nom") or str(rec.id),
                "type_label": "Véhicule" if eq_type == "vehicle" else "Tête",
                "color": colors.get((eq_type, str(rec.id)), DEFAULT_COLOR),
                "used_days": counts.get((eq_type, str(rec.id)), 0),
            })
    items.sort(key=lambda x: -x["used_days"])  # tri stable : l'ordre du catalogue départage les égalités
    peak = max([i["used_days"] for i in items] or [0]) or 1
    for i in items:
        i["pct"] = round(100 * i["used_days"] / peak)
    return {
        "period": period,
        "period_label": USAGE_PERIODS[period],
        "periods": USAGE_PERIODS,
        "start": start,
        "rows": items,
        "total_used": sum(i["used_days"] for i in items),
    }


def _projects_with_usage():
    return (Project.query.filter(Project.deleted_at.is_(None))
            .options(selectinload(Project.equipment_usage), selectinload(Project.production))
            .all())


def pointing_rate(today=None, window_days=POINTING_RATE_WINDOW_DAYS, projects=None):
    """
    Taux de pointage sur la fenêtre (jours de tournage passés des `window_days` derniers jours) :
    part des couples matériel × jour qui sont pointés (utilisé ou non utilisé).
    """
    from services.admin.equipment_usage import _equipment_keys, usage_days

    today = today or get_today_paris()
    start = today - timedelta(days=window_days - 1)
    expected = marked = 0
    for p in (projects if projects is not None else _projects_with_usage()):
        keys = _equipment_keys(p)
        if not keys:
            continue
        days = [d for d in usage_days(p) if start <= d <= today]
        if not days:
            continue
        done = {(e.key, e.usage_date) for e in (p.equipment_usage or [])}
        for d in days:
            for k in keys:
                expected += 1
                if (k, d) in done:
                    marked += 1
    return {"rate": _rate(marked, expected), "marked": marked, "expected": expected,
            "missing": expected - marked, "window_days": window_days}


def projects_pending_usage(today=None, ended_within_days=None, projects=None):
    """
    Projets ayant des jours de tournage passés non entièrement pointés, du plus récent au plus ancien.
    `ended_within_days` : ne garde que les projets dont le dernier jour de tournage passé date de moins de N jours.
    """
    from services.admin.equipment_usage import pending_usage_count, usage_days

    today = today or get_today_paris()
    result = []
    for p in (projects if projects is not None else _projects_with_usage()):
        pending = pending_usage_count(p, today)
        if not pending:
            continue
        past = [d for d in usage_days(p) if d <= today]
        last_day = past[-1] if past else None
        if ended_within_days is not None and last_day and (today - last_day).days > ended_within_days:
            continue
        result.append({
            "id": p.id,
            "project_id": p.project_id,
            "name": p.name,
            "production": p.production.name if p.production else "",
            "pending_days": pending,
            "last_day": last_day,
        })
    result.sort(key=lambda x: x["last_day"] or date.min, reverse=True)
    return result


def dashboard_usage_context(period="30d", today=None):
    """Contexte du bloc « Utilisation du matériel » du tableau de bord."""
    today = today or get_today_paris()
    projects = _projects_with_usage()
    pending = projects_pending_usage(today, projects=projects)
    return {
        "ranking": fleet_usage_ranking(period, today),
        "pointing": pointing_rate(today, projects=projects),
        "pending_projects": pending,
        "pending_days_total": sum(p["pending_days"] for p in pending),
    }


# ── Rappel quotidien (administrateurs & managers) ──────────────

DIGEST_WINDOW_DAYS = 60  # projets dont le dernier jour de tournage passé date de moins de 60 jours
_DIGEST_ROLES = ("administrateur", "super administrateur", "manager")


def usage_digest_recipients():
    """Adresses e-mail des administrateurs et managers."""
    from models import User
    from utils.decorators import normalize_role

    return sorted({
        u.mail.strip() for u in User.query.all()
        if u.mail and normalize_role(u.role) in _DIGEST_ROLES
    })


def send_usage_reminder_digest(today=None, base_url=None, dry_run=False):
    """
    Envoie aux administrateurs et managers un résumé unique des projets ayant des jours de tournage
    passés non pointés (dernier jour passé de moins de DIGEST_WINDOW_DAYS jours).
    Aucun e-mail s'il n'y a rien à signaler. Retourne {"projects", "recipients", "sent"}.
    """
    from flask import url_for
    from utils.mailer import EmailService
    from utils.request_utils import resolve_base_url

    today = today or get_today_paris()
    projects = projects_pending_usage(today, ended_within_days=DIGEST_WINDOW_DAYS)
    recipients = usage_digest_recipients()
    result = {"projects": projects, "recipients": recipients, "sent": 0}
    if not projects or not recipients or dry_run:
        return result

    root = resolve_base_url(base_url).rstrip("/")
    for p in projects:
        p["url"] = root + url_for("admin_projects.admin_project_detail", record_id=p["id"]) + "#pointage"
        p["last_day_fr"] = p["last_day"].strftime("%d/%m/%Y") if p["last_day"] else "—"
    total = sum(p["pending_days"] for p in projects)
    subject = (f"Pointage du matériel : {len(projects)} projet{'s' if len(projects) > 1 else ''} "
               f"à compléter ({total} jour{'s' if total > 1 else ''})")
    text = "\n".join([subject, ""] + [
        f"- {p['name']} ({p['production']}) : {p['pending_days']} jour(s) à pointer — {p['url']}" for p in projects
    ])
    context = {"projects": projects, "total_days": total, "window_days": DIGEST_WINDOW_DAYS,
               "dashboard_url": root + url_for("admin_dashboard.admin_dashboard") + "#utilisation-materiel"}
    for to in recipients:
        if EmailService.send_templated_email(
            to_email=to, subject=subject, template_name="emails/equipment_usage_digest.html",
            context=context, text_content=text, sender_type="contact",
        ):
            result["sent"] += 1
    return result
