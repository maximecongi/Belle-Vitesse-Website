"""Validation commune des checkpoints de type mesure."""

from decimal import Decimal, InvalidOperation


RULE_FIELDS = ("minimum", "maximum", "goal", "tolerance")


def decimal_value(value):
    if value is None or str(value).strip() == "":
        raise ValueError("toutes les bornes numériques sont obligatoires")
    try:
        result = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("une valeur numérique est invalide")
    if not result.is_finite():
        raise ValueError("les nombres doivent être finis")
    try:
        rounded = result.quantize(Decimal("0.1"))
    except InvalidOperation:
        raise ValueError("la valeur numérique dépasse la précision autorisée")
    if rounded != result:
        raise ValueError(
            "les mesures et leurs règles sont limitées à une décimale")
    return rounded


def normalize_measurement_rules(data):
    if not data or not isinstance(data, dict):
        raise ValueError("règles de mesure manquantes")
    rules = {field: decimal_value(data.get(field)) for field in RULE_FIELDS}
    if rules["minimum"] > rules["maximum"]:
        raise ValueError(
            "la valeur minimale doit être inférieure ou égale à la valeur maximale")
    if not rules["minimum"] <= rules["goal"] <= rules["maximum"]:
        raise ValueError(
            "l’objectif doit être compris dans la plage autorisée")
    if rules["tolerance"] < 0:
        raise ValueError("la tolérance doit être positive ou nulle")
    return rules


def format_rule_decimal(value):
    if value is None or str(value).strip() in ("", "None"):
        return None
    try:
        d = Decimal(str(value).strip().replace(",", "."))
        return format(d.quantize(Decimal("0.1")), "f")
    except Exception:
        return str(value)


def snapshot_rules(config):
    """Retourne les paramètres numériques sérialisables d'une définition avec une seule décimale."""
    return {field: format_rule_decimal(config.get(field)) if config.get(field) is not None else None
            for field in RULE_FIELDS} | {"unit": config.get("unit") or ""}


def validate_measurement(value, config, is_checkout):
    """Valide une valeur, puis la normalise pour le stockage. Retourne (value, erreur)."""
    try:
        measured = decimal_value(value)
        rules = normalize_measurement_rules(config)
    except ValueError as exc:
        return None, str(exc)

    if not rules["minimum"] <= measured <= rules["maximum"]:
        return None, "valeur hors de la plage autorisée"
    if is_checkout:
        lower = max(rules["minimum"], rules["goal"] - rules["tolerance"])
        upper = min(rules["maximum"], rules["goal"] + rules["tolerance"])
        if not lower <= measured <= upper:
            return None, "valeur hors de l’objectif et de sa tolérance"
    normalized = format(measured.normalize(), "f")
    return normalized, None
