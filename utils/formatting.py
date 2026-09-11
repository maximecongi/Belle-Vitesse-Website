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
