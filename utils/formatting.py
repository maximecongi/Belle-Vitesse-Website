from datetime import date, datetime


def get_today_paris() -> date:
    """Retourne la date courante dans le fuseau horaire Europe/Paris (pour éviter les décalages UTC sur serveur)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Paris")).date()
    except Exception:
        return datetime.now().date()


def get_today_paris_iso() -> str:
    """Retourne la date du jour au format ISO YYYY-MM-DD selon le fuseau Europe/Paris."""
    return get_today_paris().strftime("%Y-%m-%d")


MOIS_FR = [
    "", "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


MOIS_COURTS_FR = [
    "", "janv.", "févr.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc."
]


def format_date_fr(date_str: str) -> str:
    """Convert a date string to French format (ex: 16 février 2026)."""
    if not date_str or date_str == "—":
        return "—"
    try:
        if "/" in date_str:
            parts = date_str.split("/")
            day, month, year = int(parts[0]), int(parts[1]), parts[2]
        elif "-" in date_str:
            parts = date_str.split("-")
            year, month, day = parts[0], int(parts[1]), int(parts[2])
        else:
            return date_str
        return f"{day} {MOIS_FR[month]} {year}"
    except (ValueError, IndexError):
        return date_str


def _parse_single_date(val):
    """Parse une valeur en objet date, supportant les formats ISO et FR."""
    if not val:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    val_str = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(val_str, fmt).date()
        except ValueError:
            pass
    return None


def _format_day_month(d: date, include_year: bool = False, short_month: bool = True) -> str:
    """Formate un jour avec le nom du mois en français (court ou long)."""
    month_name = MOIS_COURTS_FR[d.month] if short_month else MOIS_FR[d.month]
    day_str = f"{d.day:02d}"
    if include_year:
        return f"{day_str} {month_name} {d.year}"
    return f"{day_str} {month_name}"


def _format_period(start: date, end: date, short_month: bool = True) -> dict:
    """Formate une période (un jour ou plusieurs jours consécutifs)."""
    is_same_day = (start == end)
    days_count = (end - start).days + 1

    if is_same_day:
        label = _format_day_month(start, include_year=True, short_month=short_month)
        compact = _format_day_month(start, include_year=False, short_month=short_month)
    elif start.year == end.year and start.month == end.month:
        month_name = MOIS_COURTS_FR[start.month] if short_month else MOIS_FR[start.month]
        label = f"{start.day:02d} au {end.day:02d} {month_name} {start.year}"
        compact = f"{start.day:02d}–{end.day:02d} {month_name}"
    elif start.year == end.year:
        start_m = MOIS_COURTS_FR[start.month] if short_month else MOIS_FR[start.month]
        end_m = MOIS_COURTS_FR[end.month] if short_month else MOIS_FR[end.month]
        label = f"{start.day:02d} {start_m} au {end.day:02d} {end_m} {start.year}"
        compact = f"{start.day:02d} {start_m} – {end.day:02d} {end_m}"
    else:
        label = f"{_format_day_month(start, include_year=True, short_month=short_month)} au {_format_day_month(end, include_year=True, short_month=short_month)}"
        compact = f"{start.day:02d}/{start.month:02d}/{start.year} – {end.day:02d}/{end.month:02d}/{end.year}"

    return {
        "start": start,
        "end": end,
        "days_count": days_count,
        "is_range": not is_same_day,
        "label": label,
        "compact": compact,
        "badge_label": f"{label} ({days_count}j)" if not is_same_day else label,
    }


def parse_and_format_shooting_dates(raw_input) -> dict:
    """
    Analyse intelligente des dates de tournage (string avec virgules, liste de dates, ou période continue).
    Retourne une structure riche exploitée par les listes et pages publiques de signature.
    """
    import re

    if not raw_input or raw_input == "—":
        return {
            "is_punctual": False,
            "has_dates": False,
            "total_days": 0,
            "periods_count": 0,
            "periods": [],
            "display_text": "—",
            "global_label": "—",
            "summary_text": "—",
            "legal_summary_text": "—",
            "raw": ""
        }

    parsed_dates = []

    if isinstance(raw_input, (list, set, tuple)):
        for item in raw_input:
            d = _parse_single_date(item)
            if d:
                parsed_dates.append(d)
    elif isinstance(raw_input, str):
        chunks = [c.strip() for c in re.split(r'[,;]+', raw_input) if c.strip()]
        if len(chunks) > 1:
            for c in chunks:
                d = _parse_single_date(c)
                if d:
                    parsed_dates.append(d)
        elif len(chunks) == 1:
            single_d = _parse_single_date(chunks[0])
            if single_d:
                parsed_dates.append(single_d)
            else:
                return {
                    "is_punctual": False,
                    "has_dates": True,
                    "total_days": 1,
                    "periods_count": 1,
                    "periods": [],
                    "display_text": raw_input,
                    "global_label": raw_input,
                    "summary_text": raw_input,
                    "legal_summary_text": raw_input,
                    "raw": raw_input
                }

    if not parsed_dates:
        return {
            "is_punctual": False,
            "has_dates": bool(raw_input),
            "total_days": 1,
            "periods_count": 1,
            "periods": [],
            "display_text": str(raw_input),
            "global_label": str(raw_input),
            "summary_text": str(raw_input),
            "legal_summary_text": str(raw_input),
            "raw": str(raw_input)
        }

    sorted_dates = sorted(list(set(parsed_dates)))
    total_days = len(sorted_dates)

    periods_raw = []
    curr_start = sorted_dates[0]
    curr_end = sorted_dates[0]

    for d in sorted_dates[1:]:
        if (d - curr_end).days == 1:
            curr_end = d
        else:
            periods_raw.append((curr_start, curr_end))
            curr_start = d
            curr_end = d
    periods_raw.append((curr_start, curr_end))

    periods = [_format_period(s, e) for s, e in periods_raw]
    periods_count = len(periods)

    first_d = sorted_dates[0]
    last_d = sorted_dates[-1]

    if first_d == last_d:
        global_label = _format_day_month(first_d, include_year=True)
    elif first_d.year == last_d.year and first_d.month == last_d.month:
        m = MOIS_COURTS_FR[first_d.month]
        global_label = f"Du {first_d.day:02d} au {last_d.day:02d} {m} {first_d.year}"
    elif first_d.year == last_d.year:
        m1 = MOIS_COURTS_FR[first_d.month]
        m2 = MOIS_COURTS_FR[last_d.month]
        global_label = f"Du {first_d.day:02d} {m1} au {last_d.day:02d} {m2} {first_d.year}"
    else:
        global_label = f"Du {_format_day_month(first_d, True)} au {_format_day_month(last_d, True)}"

    slots_str = ", ".join(p["compact"] for p in periods)
    if not slots_str.endswith(str(last_d.year)):
        slots_str += f" {last_d.year}"

    days_txt = f"{total_days} jour{'s' if total_days > 1 else ''}"
    slots_txt = f"{periods_count} créneau{'x' if periods_count > 1 else ''}"

    summary_text = f"{days_txt} ({slots_str})" if total_days > 1 else periods[0]["label"]
    legal_summary = f"{days_txt} de tournage ({global_label} : {slots_str})" if total_days > 1 else periods[0]["label"]
    display_text = summary_text if periods_count > 1 else periods[0]["label"]

    return {
        "is_punctual": periods_count > 1 or total_days > 1,
        "has_dates": True,
        "total_days": total_days,
        "periods_count": periods_count,
        "periods": periods,
        "display_text": display_text,
        "global_label": global_label,
        "summary_text": summary_text,
        "legal_summary_text": legal_summary,
        "raw": str(raw_input)
    }


# ── Markdown Rendering (Notion-style & Secure) ───────────────────────

import re
import bleach
import markdown
from markupsafe import Markup

ALLOWED_MARKDOWN_TAGS = [
    'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'del',
    'h1', 'h2', 'h3', 'h4', 'ul', 'ol', 'li', 'blockquote',
    'code', 'pre', 'hr', 'a', 'span', 'table', 'thead', 'tbody', 'tr', 'th', 'td'
]

ALLOWED_MARKDOWN_ATTRS = {
    'a': ['href', 'title', 'target', 'rel'],
    'span': ['class'],
    'code': ['class'],
    'th': ['align'],
    'td': ['align']
}


def render_markdown(text: str) -> Markup:
    """
    Convertit du texte Markdown enrichi (façon Notion) en HTML sécurisé.
    Gère les listes de tâches (- [ ] et - [x]), les citations, le code et les liens.
    """
    if not text:
        return Markup("")

    # Élimination préventive complète des balises script et style et de leur contenu
    text = re.sub(r'<script.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Conversion Markdown vers HTML
    raw_html = markdown.markdown(
        text,
        extensions=['extra', 'nl2br', 'sane_lists']
    )

    # Assainissement anti-XSS strict
    cleaned_html = bleach.clean(
        raw_html,
        tags=ALLOWED_MARKDOWN_TAGS,
        attributes=ALLOWED_MARKDOWN_ATTRS,
        strip=True
    )

    # Rendre les liens externes sécurisés (target=_blank et rel=noopener)
    cleaned_html = re.sub(
        r'<a (?!.*?target=)',
        r'<a target="_blank" rel="noopener noreferrer" ',
        cleaned_html
    )

    return Markup(cleaned_html)


def truncate_report(text: str, limit: int = 200) -> str:
    """
    Tronque proprement un texte Markdown à environ `limit` caractères (par défaut 200)
    en respectant les frontières de mots, et ajoute des points de suspension (...).
    """
    if not text or len(text) <= limit:
        return text or ""

    # Découpe préliminaire à la limite
    truncated = text[:limit]

    # Trouver le dernier séparateur (espace, tabulation ou saut de ligne)
    last_space = max(truncated.rfind(" "), truncated.rfind("\n"), truncated.rfind("\t"))

    # Si on trouve un espace dans une marge raisonnable (au-delà de 60% de la limite)
    if last_space > int(limit * 0.6):
        truncated = truncated[:last_space].rstrip()
    else:
        truncated = truncated.rstrip()

    # Nettoyer les marqueurs markdown orphelins en fin de chaîne (*, #, `, >, -, _, ~)
    truncated = re.sub(r'(\*{1,2}|#{1,6}|`{1,3}|>|-|\_|\~)+$', '', truncated).rstrip()

    return f"{truncated}..."
