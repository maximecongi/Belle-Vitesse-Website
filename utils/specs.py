from flask import g

from utils.specs_config import SPECS_CONFIG


def keep(v):
    return v is not None and v != ""


def build_specs(fields):
    """
    Retourne un dict de specs avec labels traduits selon g.lang.
    """
    lang = getattr(g, 'lang', 'en')
    specs = {}

    for key, cfg in SPECS_CONFIG.items():
        value = cfg["value"](fields)
        if keep(value):
            label = cfg["label"].get(lang, cfg["label"]["en"])
            specs[label] = value

    return specs


def build_specs_bilingual(fields):
    """
    Retourne la liste ordonnée des specs disponibles avec leurs libellés FR et EN.
    Utilisé par les fiches publiques bilingues (bascule FR/EN côté client et PDF).
    """
    fields = fields or {}
    specs = []
    for key, cfg in SPECS_CONFIG.items():
        try:
            value = cfg["value"](fields)
        except Exception:
            value = None
        if keep(value):
            specs.append({
                "key": key,
                "label_fr": cfg["label"].get("fr", cfg["label"]["en"]),
                "label_en": cfg["label"]["en"],
                "value": value,
            })
    return specs
