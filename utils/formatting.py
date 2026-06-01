# ── Date Formatting ───────────────────────────────────────────────

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
