import json


def _parse_shooting_locations(form) -> list:
    """
    Parse et valide la liste des lieux de tournage transmise par le formulaire.
    Format attendu : [{"name": ..., "address": ...}].
    """
    val = form.get("shooting_locations") if hasattr(form, "get") else None
    if isinstance(val, str) and val.strip():
        try:
            parsed = json.loads(val)
        except Exception:
            parsed = []
    elif isinstance(val, list):
        parsed = val
    else:
        parsed = []

    cleaned = []
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
                address = str(item.get("address") or "").strip()
                if name:  # Nom obligatoire, adresse facultative
                    cleaned.append({"name": name, "address": address})
    return cleaned

