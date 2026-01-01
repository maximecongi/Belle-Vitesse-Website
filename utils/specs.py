from specs_config import SPECS_CONFIG

def keep(v):
    return v is not None and v != ""

def build_specs(fields):
    """
    Retourne deux dicts : specs_left et specs_right
    en filtrant les valeurs vides et en respectant la config
    """
    specs_left = {}
    specs_right = {}

    for label, cfg in SPECS_CONFIG.items():
        value = cfg["value"](fields)
        if keep(value):
            if cfg["side"] == "left":
                specs_left[label] = value
            else:
                specs_right[label] = value

    return specs_left, specs_right
