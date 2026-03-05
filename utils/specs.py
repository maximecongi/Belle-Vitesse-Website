from specs_config import SPECS_CONFIG
from flask import g


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
