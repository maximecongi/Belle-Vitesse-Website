# ── Date Formatting ───────────────────────────────────────────────

from datetime import datetime, timedelta
MOIS_FR = [
    "", "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
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


def format_date_slash(date_str: str) -> str:
    if not date_str or date_str == "—":
        return "—"
    try:
        parts = date_str.strip().split()
        day = int(parts[0])
        month_name = parts[1].lower()
        year = parts[2]

        month = MOIS_FR.index(month_name)
        return f"{day:02d}/{month:02d}/{year}"
    except (ValueError, IndexError):
        return date_str


def next_day(date_str_slash: str) -> str:
    """
    Prend une date au format DD/MM/YYYY et retourne la date du jour suivant
    au même format.
    """
    dt = datetime.strptime(date_str_slash, "%d/%m/%Y")
    dt += timedelta(days=1)
    return dt.strftime("%d/%m/%Y")
