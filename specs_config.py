def with_unit(value, unit):
    if value is None:
        return None
    return f"{value} {unit}"


def dimensions(values, labels, unit):
    if not all(values):
        return None
    return " × ".join(
        f"{label} {value}" for label, value in zip(labels, values)
    ) + f" {unit}"


SPECS_CONFIG = {
    "Brand": {
        "label": {"en": "Brand", "fr": "Marque"},
        "value": lambda f: f.get("brand"),
    },
    "Model": {
        "label": {"en": "Model", "fr": "Modèle"},
        "value": lambda f: f.get("model"),
    },
    "Type": {
        "label": {"en": "Type", "fr": "Type"},
        "value": lambda f: f.get("type"),
    },
    "Max speed": {
        "label": {"en": "Max speed", "fr": "Vitesse max"},
        "value": lambda f: with_unit(f.get("max_speed"), "km/h"),
    },
    "Pan range": {
        "label": {"en": "Pan range", "fr": "Plage de pan"},
        "value": lambda f: with_unit(f.get("pan_range"), "°"),
    },
    "Tilt range": {
        "label": {"en": "Tilt range", "fr": "Plage de tilt"},
        "value": lambda f: with_unit(f.get("tilt_range"), "°"),
    },
    "Roll range": {
        "label": {"en": "Roll range", "fr": "Plage de roll"},
        "value": lambda f: with_unit(f.get("roll_range"), "°"),
    },
    "Passengers": {
        "label": {"en": "Passengers", "fr": "Passagers"},
        "value": lambda f: f.get("passengers"),
    },
    "Power": {
        "label": {"en": "Power", "fr": "Puissance"},
        "value": lambda f: f.get("power"),
    },
    "Torque": {
        "label": {"en": "Torque", "fr": "Couple"},
        "value": lambda f: f.get("torque"),
    },
    "Battery": {
        "label": {"en": "Battery", "fr": "Batterie"},
        "value": lambda f: f.get("battery_type"),
    },
    "Battery life": {
        "label": {"en": "Battery life", "fr": "Autonomie"},
        "value": lambda f: with_unit(f.get("battery_life"), "h"),
    },
    "Charging time": {
        "label": {"en": "Charging time", "fr": "Temps de charge"},
        "value": lambda f: with_unit(f.get("charging_time"), "h"),
    },
    "Remote Compatibility": {
        "label": {"en": "Remote Compatibility", "fr": "Compatibilité télécommande"},
        "value": lambda f: f.get("remote_compatibility"),
    },
    "Mount": {
        "label": {"en": "Mount", "fr": "Monture"},
        "value": lambda f: f.get("mount"),
    },
    "Power supply": {
        "label": {"en": "Power supply", "fr": "Alimentation"},
        "value": lambda f: f.get("power_supply"),
    },
    "Operating temperatures": {
        "label": {"en": "Operating temperatures", "fr": "Températures d'utilisation"},
        "value": lambda f: f.get("operating_temperatures"),
    },
    "Maximum operating speed": {
        "label": {"en": "Max operating speed", "fr": "Vitesse max d'opération"},
        "value": lambda f: with_unit(f.get("max_operating_speed"), "km/h"),
    },
    "Weather rating": {
        "label": {"en": "Weather rating", "fr": "Indice de protection"},
        "value": lambda f: f.get("weather_rating"),
    },
    "Camera tray size": {
        "label": {"en": "Camera tray size", "fr": "Taille du plateau caméra"},
        "value": lambda f: dimensions(
            [
                f.get("camera_tray_depth"),
                f.get("camera_tray_width"),
                f.get("camera_tray_height"),
            ],
            ["D", "W", "H"],
            "mm",
        ),
    },
    "Size": {
        "label": {"en": "Size", "fr": "Dimensions"},
        "value": lambda f: dimensions(
            [
                f.get("length"),
                f.get("width"),
                f.get("height"),
            ],
            ["L", "W", "H"],
            "mm",
        ),
    },
    "Weight": {
        "label": {"en": "Weight", "fr": "Poids"},
        "value": lambda f: with_unit(f.get("weight"), "kg"),
    },
}
