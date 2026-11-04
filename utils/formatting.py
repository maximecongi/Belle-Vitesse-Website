import re
from datetime import date, datetime

import bleach
import markdown
from markupsafe import Markup


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


def parse_date(val) -> date | None:
    """
    Parse de manière tolérante une valeur en objet date.
    Gère les objets date, datetime et les formats textuels courants (YYYY-MM-DD, DD/MM/YYYY, etc.).
    """
    if not val:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    val_str = str(val).strip()
    if not val_str:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(val_str[:10], fmt).date()
        except ValueError:
            pass
    return None



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


def format_date_numeric(d) -> str:
    """
    Formate une date en format numérique standard français JJ/MM/AAAA (ex: 01/01/2026).
    Supporte les objets date, datetime et les chaînes de caractères (ISO, JJ/MM/AAAA ou texte FR).
    """
    if not d or str(d).strip() in ("", "—", "-", "None"):
        return "—"
    if hasattr(d, "strftime"):
        return d.strftime("%d/%m/%Y")
    d_str = str(d).strip()

    # Si format ISO YYYY-MM-DD ou datetime ISO
    if "-" in d_str and "/" not in d_str:
        try:
            clean_iso = d_str.split(" ")[0].split("T")[0]
            parts = clean_iso.split("-")
            if len(parts) == 3:
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                return f"{day:02d}/{month:02d}/{year:04d}"
        except Exception:
            pass

    # Si format JJ/MM/AAAA ou J/M/AAAA
    if "/" in d_str:
        try:
            parts = d_str.split(" ")[0].split("/")
            if len(parts) == 3:
                day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                return f"{day:02d}/{month:02d}/{year:04d}"
        except Exception:
            pass

    # Si format textuel français (ex: "16 février 2026" ou "1er janvier 2026")
    parts = d_str.split(" ")
    if len(parts) >= 3:
        day_str = parts[0].lower().replace("1er", "1")
        month_str = parts[1].lower()
        year_str = parts[2]
        if month_str in MOIS_FR:
            try:
                month = MOIS_FR.index(month_str)
                day = int(day_str)
                year = int(year_str)
                return f"{day:02d}/{month:02d}/{year:04d}"
            except Exception:
                pass

    return d_str


# ── Markdown Rendering (Notion-style & Secure) ───────────────────────

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
