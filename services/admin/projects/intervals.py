import json
from datetime import date
from typing import Optional

from utils.formatting import format_date_fr, get_today_paris, parse_date


def _parse_shoot_dates(form):
    """Parse et trie la liste des dates de tournage transmises par le formulaire."""
    val = form.get("shoot_dates") if hasattr(form, "get") else None
    if isinstance(val, str) and val.strip():
        try:
            dates = json.loads(val)
            if not isinstance(dates, list):
                dates = [s.strip() for s in val.split(",") if s.strip()]
        except Exception:
            dates = [s.strip() for s in val.split(",") if s.strip()]
    elif isinstance(val, list):
        dates = val
    else:
        dates = []

    valid_dates = []
    for d in dates:
        if isinstance(d, str) and d.strip():
            valid_dates.append(d.strip())
    return sorted(list(set(valid_dates)))


def _parse_int(val):
    """Convertit en entier ou None si non numérique ou vide."""
    if val is None:
        return None
    try:
        s = str(val).strip()
        return int(s) if s.isdigit() else None
    except (ValueError, TypeError):
        return None


def _parse_inter_shoot_statuses(form):
    """Parse la liste des statuts d'immobilisation personnalisés par intervalle."""
    val = form.get("inter_shoot_statuses") if hasattr(form, "get") else None
    if isinstance(val, str) and val.strip():
        try:
            parsed = json.loads(val)
        except Exception:
            parsed = []
    elif isinstance(val, (list, dict)):
        parsed = val
    else:
        parsed = []

    valid = []
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict) and "start" in item and "end" in item:
                valid.append({
                    "start": str(item["start"]).strip(),
                    "end": str(item["end"]).strip(),
                    "is_immobilized": bool(item.get("is_immobilized", True)),
                })
    elif isinstance(parsed, dict):
        for k, v in parsed.items():
            if "_" in k:
                parts = k.split("_")
                is_immob = bool(v.get("is_immobilized", True)) if isinstance(v, dict) else bool(v)
                valid.append({
                    "start": parts[0].strip(),
                    "end": parts[1].strip(),
                    "is_immobilized": is_immob,
                })
    return valid


def get_project_shoot_status(p, today_date: Optional[date] = None) -> dict:
    """
    Détermine le statut opérationnel d'un projet (in_progress, completed, upcoming, standby),
    son libellé, son identifiant, sa couleur sémantique et le libellé de ses dates de tournage.
    """
    if today_date is None:
        today_date = get_today_paris()

    is_punctual = (getattr(p, "date_mode", None) == "punctual")
    shoot_dates = getattr(p, "shoot_dates", None) or []
    is_immob = getattr(p, "is_immobilized_between", True)

    if is_punctual and shoot_dates:
        today_iso = today_date.isoformat()
        first_shoot = parse_date(shoot_dates[0])
        last_shoot = parse_date(shoot_dates[-1])
        ret_d = p.return_date or last_shoot

        if today_iso in shoot_dates:
            shoot_status = "in_progress"
            shoot_status_label = "En tournage"
            shoot_status_id = "in_progress"
            shoot_status_color = "var(--entity-project, #F59E0B)"
        elif first_shoot and last_shoot and (first_shoot <= today_date <= last_shoot):
            # Vérifier l'état d'immobilisation spécifique à l'intervalle du jour
            inter_intervals = p.get_inter_shoot_intervals() if hasattr(p, "get_inter_shoot_intervals") else []
            current_inter = None
            for inter in inter_intervals:
                if today_iso in inter.get("days", []):
                    current_inter = inter
                    break
            day_immob = current_inter.get("is_immobilized") if current_inter else is_immob

            if day_immob:
                shoot_status = "standby"
                shoot_status_label = "Immobilisé"
                shoot_status_id = "standby"
                shoot_status_color = "var(--status-warning, #F59E0B)"
            else:
                shoot_status = "upcoming"
                shoot_status_label = "À venir"
                shoot_status_id = "upcoming"
                shoot_status_color = "var(--status-info, #3B82F6)"
        elif ret_d and today_date > ret_d:
            shoot_status = "completed"
            shoot_status_label = "Clôturé"
            shoot_status_id = "completed"
            shoot_status_color = "var(--status-neutral, #6B7280)"
        else:
            shoot_status = "upcoming"
            shoot_status_label = "À venir"
            shoot_status_id = "upcoming"
            shoot_status_color = "var(--status-info, #3B82F6)"

        if len(shoot_dates) == 1:
            shoot_dates_label = f"Le {format_date_fr(shoot_dates[0])}"
        elif len(shoot_dates) <= 3:
            shoot_dates_label = f"Les {', '.join(format_date_fr(d) for d in shoot_dates)}"
        else:
            shoot_dates_label = f"{len(shoot_dates)} dates ({format_date_fr(shoot_dates[0])} → {format_date_fr(shoot_dates[-1])})"
    elif p.shoot_start_date and p.shoot_end_date:
        if p.shoot_start_date <= today_date <= p.shoot_end_date:
            shoot_status = "in_progress"
            shoot_status_label = "En tournage"
            shoot_status_id = "in_progress"
            shoot_status_color = "var(--entity-project, #F59E0B)"
        elif today_date > p.shoot_end_date:
            shoot_status = "completed"
            shoot_status_label = "Clôturé"
            shoot_status_id = "completed"
            shoot_status_color = "var(--status-neutral, #6B7280)"
        else:
            shoot_status = "upcoming"
            shoot_status_label = "À venir"
            shoot_status_id = "upcoming"
            shoot_status_color = "var(--status-info, #3B82F6)"
        shoot_dates_label = f"Du {format_date_fr(str(p.shoot_start_date))} au {format_date_fr(str(p.shoot_end_date))}"
    elif p.departure_date and p.return_date:
        if p.departure_date <= today_date <= p.return_date:
            shoot_status = "in_progress"
            shoot_status_label = "En tournage"
            shoot_status_id = "in_progress"
            shoot_status_color = "var(--entity-project, #F59E0B)"
        elif today_date > p.return_date:
            shoot_status = "completed"
            shoot_status_label = "Clôturé"
            shoot_status_id = "completed"
            shoot_status_color = "var(--status-neutral, #6B7280)"
        else:
            shoot_status = "upcoming"
            shoot_status_label = "À venir"
            shoot_status_id = "upcoming"
            shoot_status_color = "var(--status-info, #3B82F6)"
        shoot_dates_label = f"Du {format_date_fr(str(p.departure_date))} au {format_date_fr(str(p.return_date))}"
    else:
        shoot_status = "upcoming"
        shoot_status_label = "À venir"
        shoot_status_id = "upcoming"
        shoot_status_color = "var(--status-info, #3B82F6)"
        shoot_dates_label = "Dates à confirmer"

    return {
        "status": shoot_status,
        "label": shoot_status_label,
        "id": shoot_status_id,
        "color": shoot_status_color,
        "dates_label": shoot_dates_label,
    }

