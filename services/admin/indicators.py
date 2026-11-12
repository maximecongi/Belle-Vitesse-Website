"""
Indicateurs de pilotage (page Indicateurs, administrateurs).

Toute la page partage une période (30 jours, trimestre, 12 mois, année en cours) comparée à la
période précédente de même durée (pour « Année » : même portion de l'année précédente).
Les indicateurs « instantanés » (devis à relancer, projets à pointer, incidents ouverts) ignorent
la période. L'évolution mensuelle couvre toujours les 12 derniers mois ; les mois qui recoupent la
période sélectionnée sont signalés (`in_period`).

Chaque domaine expose le même gabarit : 4 KPI, 2 graphiques en barres, 1 évolution mensuelle.
"""
from datetime import date, timedelta

from sqlalchemy.orm import selectinload

from models import Head, Project, Vehicle
from models.commercial_event import LOST_REASON_LABELS
from services.admin.equipment_colors import DEFAULT_COLOR, get_color_map
from utils.formatting import get_today_paris

PERIODS = {"30d": "30 jours", "quarter": "Trimestre", "12m": "12 mois", "year": "Année"}
DEFAULT_PERIOD = "12m"
TABS = {"commercial": "Commercial", "equipment": "Matériel", "incidents": "Incidents"}
DEFAULT_TAB = "commercial"

_MONTHS_SHORT = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
                 "juil.", "août", "sept.", "oct.", "nov.", "déc."]
_MONTHS_FULL = ["janvier", "février", "mars", "avril", "mai", "juin",
                "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


# ── Périodes ───────────────────────────────────────────────────

def _shift_years(d, years):
    """Même jour `years` ans plus tôt/tard (29 février → 28 février)."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


def _fmt_day(d, with_year=True):
    s = f"{d.day} {_MONTHS_SHORT[d.month - 1]}"
    return f"{s} {d.year}" if with_year else s


def _fmt_range(start, end):
    return f"{_fmt_day(start, start.year != end.year)} – {_fmt_day(end)}"


def resolve_period(key, today=None):
    """Bornes (incluses) de la période et de la période de comparaison."""
    today = today or get_today_paris()
    key = key if key in PERIODS else DEFAULT_PERIOD
    if key in ("30d", "quarter"):
        length = 30 if key == "30d" else 90
        start = today - timedelta(days=length - 1)
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=length - 1)
    elif key == "12m":
        start = _shift_years(today, -1) + timedelta(days=1)
        prev_end = start - timedelta(days=1)
        prev_start = _shift_years(prev_end, -1) + timedelta(days=1)
    else:  # year : du 1er janvier à aujourd'hui, comparé à la même portion de l'an dernier
        start = date(today.year, 1, 1)
        prev_start = date(today.year - 1, 1, 1)
        prev_end = _shift_years(today, -1)
    return {
        "key": key,
        "label": PERIODS[key],
        "start": start,
        "end": today,
        "prev_start": prev_start,
        "prev_end": prev_end,
        "days": (today - start).days + 1,
        "caption": f"Du {_fmt_day(start)} au {_fmt_day(today)}",
        "prev_caption": _fmt_range(prev_start, prev_end),
    }


def last_12_months(period):
    """Les 12 derniers mois (le mois courant inclus), du plus ancien au plus récent."""
    end = period["end"]
    months = []
    y, m = end.year, end.month
    for _ in range(12):
        first = date(y, m, 1)
        nxt = date(y + (m == 12), m % 12 + 1, 1)
        months.append({
            "year": y, "month": m, "start": first, "end": nxt - timedelta(days=1),
            "label": _MONTHS_SHORT[m - 1], "label_full": f"{_MONTHS_FULL[m - 1]} {y}",
            "in_period": first <= period["end"] and nxt - timedelta(days=1) >= period["start"],
        })
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return list(reversed(months))


def _in(d, start, end):
    return d is not None and start <= d <= end


def _month_index(months, d):
    for i, m in enumerate(months):
        if m["start"] <= d <= m["end"]:
            return i
    return None


def _monthly_series(months, dates):
    counts = [0] * len(months)
    for d in dates:
        i = _month_index(months, d) if d else None
        if i is not None:
            counts[i] += 1
    return counts


def _chart(months, series):
    """
    Histogramme mensuel : `series` = [(clé, libellé, [valeurs par mois])].
    Les hauteurs sont relatives au maximum toutes séries confondues.
    """
    peak = max([v for _, _, values in series for v in values] or [0]) or 1
    cols = []
    for i, m in enumerate(months):
        cols.append({
            **m,
            "points": [
                {"key": key, "label": label, "value": values[i], "pct": round(100 * values[i] / peak)}
                for key, label, values in series
            ],
        })
    return {
        "series": [{"key": key, "label": label} for key, label, _ in series],
        "columns": cols,
        "total": sum(sum(values) for _, _, values in series),
    }


def _bars(rows):
    """Barres horizontales triées : rows = [(clé, libellé, valeur)] ; pct relatif au maximum."""
    rows = [r for r in rows if r[2]]
    rows.sort(key=lambda r: (-r[2], r[1]))
    top = max([r[2] for r in rows] or [0]) or 1
    return [{"key": k, "label": label, "count": n, "pct": round(100 * n / top)} for k, label, n in rows]


def _rate(num, den):
    return round(100 * num / den) if den else None


def _avg(values):
    return round(sum(values) / len(values)) if values else None


# ── Écarts avec la période précédente ──────────────────────────

def delta(current, previous, unit="", better="up", money=False):
    """
    Écart affichable entre deux valeurs : texte signé (« +8 pts », « −2 j »), sens et tonalité
    (good / bad / neutral selon que la hausse est souhaitable ou non). None si non comparable.
    """
    if current is None or previous is None:
        return None
    diff = current - previous
    if money:
        number = f"{abs(diff):,.0f}".replace(",", " ")
    else:
        number = f"{abs(diff):g}"
    sign = "+" if diff > 0 else ("−" if diff < 0 else "±")
    direction = "up" if diff > 0 else ("down" if diff < 0 else "flat")
    if diff == 0:
        tone = "neutral"
    else:
        tone = "good" if (diff > 0) == (better == "up") else "bad"
    return {"text": f"{sign}{number}{unit}", "direction": direction, "tone": tone}


# ── Commercial ─────────────────────────────────────────────────

def _project_milestones(project):
    """Dates clés (dates calendaires) de la timeline commerciale réalisée d'un projet."""
    from services.admin.commercial_timeline import WON_COMMERCIAL_STATUSES, _done

    events = _done(project.commercial_events)
    first_of = lambda t: next((e for e in events if e.event_type == t), None)  # noqa: E731
    confirmed = first_of("confirmed")
    quote = first_of("quote_sent")
    lost = [e for e in events if e.event_type == "lost"]
    is_lost = project.commercial_status == "lost"
    return {
        "first": events[0].occurred_at if events else None,
        "confirmed": confirmed.occurred_at if confirmed else None,
        "quoted": bool(quote) or project.commercial_status in WON_COMMERCIAL_STATUSES,
        "won": project.commercial_status in WON_COMMERCIAL_STATUSES,
        "lost": lost[-1].occurred_at if (is_lost and lost) else None,
        "lost_reason": lost[-1].lost_reason if (is_lost and lost) else None,
    }


def _commercial_window(items, start, end):
    new = [i for i in items if i["first"] and _in(i["first"].date(), start, end)]
    won = [i for i in items if i["confirmed"] and _in(i["confirmed"].date(), start, end)]
    lost = [i for i in items if i["lost"] and _in(i["lost"].date(), start, end)]
    delays = [(i["confirmed"] - i["first"]).total_seconds() / 86400 for i in won if i["first"]]
    return {
        "new": len(new),
        "won": len(won),
        "lost": len(lost),
        "conversion_rate": _rate(len(won), len(won) + len(lost)),
        "avg_days_to_confirm": _avg(delays),
        "confirmed_sample": len(delays),
        "lost_reasons": _bars([
            (key, label, sum(1 for i in lost if i["lost_reason"] == key))
            for key, label in LOST_REASON_LABELS.items()
        ]),
        "cohort": new,
    }


def commercial_indicators(period, months, now=None):
    from services.admin.commercial_timeline import find_projects_awaiting_quote_reply

    projects = (Project.query
                .filter(Project.deleted_at.is_(None), Project.commercial_status.isnot(None))
                .options(selectinload(Project.commercial_events))
                .all())
    items = [_project_milestones(p) for p in projects]
    cur = _commercial_window(items, period["start"], period["end"])
    prev = _commercial_window(items, period["prev_start"], period["prev_end"])

    # Entonnoir : jusqu'où sont allées les demandes reçues pendant la période
    cohort = cur.pop("cohort")
    prev.pop("cohort")
    total = len(cohort)
    stages = [
        ("requests", "Demandes reçues", total),
        ("quoted", "Devis envoyés", sum(1 for i in cohort if i["quoted"])),
        ("won", "Confirmées", sum(1 for i in cohort if i["won"])),
    ]
    funnel = {
        "stages": [{"key": k, "label": label, "count": n, "pct": _rate(n, total) or 0} for k, label, n in stages],
        "lost": sum(1 for i in cohort if i["lost"]),
        "open": sum(1 for i in cohort if not i["won"] and not i["lost"]),
        "total": total,
    }

    followups = find_projects_awaiting_quote_reply(now=now)
    chart = _chart(months, [
        ("requests", "Nouvelles demandes", _monthly_series(months, [i["first"].date() for i in items if i["first"]])),
        ("won", "Confirmations", _monthly_series(months, [i["confirmed"].date() for i in items if i["confirmed"]])),
    ])
    return {
        **cur,
        "deltas": {
            "conversion_rate": delta(cur["conversion_rate"], prev["conversion_rate"], " pts"),
            "avg_days_to_confirm": delta(cur["avg_days_to_confirm"], prev["avg_days_to_confirm"], " j", better="down"),
            "new": delta(cur["new"], prev["new"]),
        },
        "followups": len(followups),
        "funnel": funnel,
        "chart": chart,
    }


# ── Matériel ───────────────────────────────────────────────────

def _equipment_catalog():
    colors = get_color_map()
    items = []
    for eq_type, model in (("vehicle", Vehicle), ("head", Head)):
        for rec in model.query.order_by(model.display_order, model.id).all():
            f = rec.fields if isinstance(rec.fields, dict) else {}
            items.append({
                "type": eq_type,
                "id": str(rec.id),
                "name": f.get("name") or f.get("Nom") or str(rec.id),
                "color": colors.get((eq_type, str(rec.id)), DEFAULT_COLOR),
            })
    return items


def _usage_window(rows, start, end):
    pointed, used = {}, {}
    for eq_type, eq_id, day, is_used in rows:
        if not _in(day, start, end):
            continue
        k = (eq_type, str(eq_id))
        pointed[k] = pointed.get(k, 0) + 1
        if is_used:
            used[k] = used.get(k, 0) + 1
    total_pointed, total_used = sum(pointed.values()), sum(used.values())
    return {"pointed": pointed, "used": used, "used_days": total_used,
            "usage_rate": _rate(total_used, total_pointed), "pointed_days": total_pointed}


def equipment_indicators(period, months):
    from models.equipment_usage import ProjectEquipmentUsage
    from services.admin.equipment_stats import (
        _active_usage_query,
        _projects_with_usage,
        pointing_rate,
        projects_pending_usage,
    )

    since = min(period["prev_start"], months[0]["start"])
    rows = (_active_usage_query()
            .with_entities(ProjectEquipmentUsage.equipment_type, ProjectEquipmentUsage.equipment_id,
                           ProjectEquipmentUsage.usage_date, ProjectEquipmentUsage.used)
            .filter(ProjectEquipmentUsage.usage_date >= since,
                    ProjectEquipmentUsage.usage_date <= period["end"])
            .all())
    cur = _usage_window(rows, period["start"], period["end"])
    prev = _usage_window(rows, period["prev_start"], period["prev_end"])

    projects = _projects_with_usage()
    pointing = pointing_rate(today=period["end"], window_days=period["days"], projects=projects)
    prev_days = (period["prev_end"] - period["prev_start"]).days + 1
    prev_pointing = pointing_rate(today=period["prev_end"], window_days=prev_days, projects=projects)

    catalog = _equipment_catalog()
    by_used, by_rate = [], []
    for eq in catalog:
        k = (eq["type"], eq["id"])
        n_used, n_pointed = cur["used"].get(k, 0), cur["pointed"].get(k, 0)
        by_used.append({**eq, "count": n_used})
        if n_pointed:
            by_rate.append({**eq, "count": _rate(n_used, n_pointed), "pointed": n_pointed, "used": n_used})
    by_used.sort(key=lambda x: -x["count"])  # tri stable : l'ordre du catalogue départage les égalités
    by_rate.sort(key=lambda x: -x["count"])
    peak = max([x["count"] for x in by_used] or [0]) or 1
    for x in by_used:
        x["pct"] = round(100 * x["count"] / peak)
    for x in by_rate:
        x["pct"] = x["count"]

    chart = _chart(months, [
        ("used", "Jours utilisés", _monthly_series(months, [r[2] for r in rows if r[3]])),
    ])
    return {
        "usage_rate": cur["usage_rate"],
        "used_days": cur["used_days"],
        "pointed_days": cur["pointed_days"],
        "pointing": pointing,
        "pending_projects": len(projects_pending_usage(today=period["end"], projects=projects)),
        "deltas": {
            "usage_rate": delta(cur["usage_rate"], prev["usage_rate"], " pts"),
            "used_days": delta(cur["used_days"], prev["used_days"], " j"),
            "pointing": delta(pointing["rate"], prev_pointing["rate"], " pts"),
        },
        "by_used": by_used,
        "by_rate": by_rate,
        "chart": chart,
    }


# ── Incidents ──────────────────────────────────────────────────

def incidents_indicators(period, months):
    from models.incident import Incident
    from services.admin.incidents.stats import incident_stats

    cur = incident_stats(period["start"], period["end"])
    prev = incident_stats(period["prev_start"], period["prev_end"])
    dates = [d for (d,) in Incident.query.with_entities(Incident.incident_date)
             .filter(Incident.deleted_at.is_(None), Incident.incident_date >= months[0]["start"]).all()]
    return {
        **cur,
        "actual_cost_label": f"{cur['actual_cost']:,.0f}".replace(",", "\u202f") + " €",
        "deltas": {
            "declared": delta(cur["declared"], prev["declared"], better="down"),
            "avg_days_to_resolve": delta(cur["avg_days_to_resolve"], prev["avg_days_to_resolve"], " j", better="down"),
            "actual_cost": delta(cur["actual_cost"], prev["actual_cost"], " €", better="down", money=True),
        },
        "chart": _chart(months, [("declared", "Incidents déclarés", _monthly_series(months, dates))]),
    }
