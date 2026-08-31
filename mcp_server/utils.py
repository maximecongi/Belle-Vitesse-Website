"""Utilitaires partagés pour le serveur MCP (parsing de dates, recherche, pagination)."""
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Union


def parse_flexible_date(val: Union[str, date, datetime, None]) -> Optional[str]:
    """
    Parse et normalise une date vers le format ISO standard 'YYYY-MM-DD'.
    Supporte de multiples formats :
    - 'YYYY-MM-DD'
    - 'DD/MM/YYYY', 'DD-MM-YYYY', 'DD.MM.YYYY'
    - 'YYYY/MM/DD'
    - Objets date ou datetime
    """
    if not val:
        return None
    if isinstance(val, (date, datetime)):
        return val.strftime("%Y-%m-%d")

    val_str = str(val).strip()
    if not val_str:
        return None

    # Extraction si ISO timestamp (ex: "2026-09-15T14:30:00")
    if "T" in val_str:
        val_str = val_str.split("T")[0].strip()

    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%Y/%m/%d",
        "%Y.%m.%d",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(val_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Repli regex basique si format YYYY-MM-DD partiel
    match = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$", val_str)
    if match:
        y, m, d = match.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    match_fr = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$", val_str)
    if match_fr:
        d, m, y = match_fr.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    return None


def _normalize_text(txt: Any) -> str:
    """Normalise un texte en minuscules et sans accents pour une recherche tolérante."""
    if txt is None:
        return ""
    import unicodedata
    nfkd = unicodedata.normalize("NFD", str(txt).lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def matches_search_query(item: Union[Dict[str, Any], Any], query: Optional[str], fields: Sequence[str]) -> bool:
    """Vérifie si au moins un des champs spécifiés contient la requête de recherche (insensible à la casse et aux accents)."""
    if not query:
        return True
    q_norm = _normalize_text(query).strip()
    if not q_norm:
        return True

    for field in fields:
        val = None
        if isinstance(item, dict):
            val = item.get(field)
        elif hasattr(item, field):
            val = getattr(item, field)

        if val is not None:
            val_norm = _normalize_text(val)
            if q_norm in val_norm:
                return True
    return False


def apply_pagination(items: List[Any], limit: Optional[int] = 50, offset: Optional[int] = 0) -> List[Any]:
    """Applique une pagination simple (offset / limit) sur une liste."""
    safe_offset = max(0, int(offset or 0))
    safe_limit = max(1, min(500, int(limit or 50)))
    return items[safe_offset : safe_offset + safe_limit]
