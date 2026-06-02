import ast
import json


def _from_json(s):
    """Désérialise une chaîne JSON ou une syntaxe littérale Python en objet."""
    if not isinstance(s, str):
        return s
    # Tente le JSON d'abord, puis la syntaxe littérale Python (tuples, etc.)
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        result = ast.literal_eval(s)
        # Convertit les tuples en listes pour la cohérence
        if isinstance(result, list):
            return [list(item) if isinstance(item, tuple) else item for item in result]
        return result
    except (ValueError, SyntaxError):
        return []


def init_jinja_filters(app):
    """Enregistre les filtres Jinja2 personnalisés dans l'application Flask."""
    app.jinja_env.filters["slugify"] = lambda s: s.lower().replace(" ", "_")
    app.jinja_env.filters["from_json"] = _from_json
