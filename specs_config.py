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
        "side": "left",
        "value": lambda f: f.get("brand"),
    },
    "Model": {
        "side": "left",
        "value": lambda f: f.get("model"),
    },
    "Type": {
        "side": "left",
        "value": lambda f: f.get("type"),
    },
    "Max speed": {
        "side": "left",
        "value": lambda f: with_unit(f.get("max_speed"), "km/h"),
    },
    "Pan range": {
        "side": "left",
        "value": lambda f: with_unit(f.get("pan_range"), "°"),
    },
    "Tilt range": {
        "side": "left",
        "value": lambda f: with_unit(f.get("tilt_range"), "°"),
    },
    "Roll range": {
        "side": "left",
        "value": lambda f: with_unit(f.get("roll_range"), "°"),
    },
    "Passengers": {
        "side": "left",
        "value": lambda f: f.get("passengers"),
    },
    "Power": {
        "side": "left",
        "value": lambda f: f.get("power"),
    },
    "Torque": {
        "side": "right",
        "value": lambda f: f.get("torque"),
    },
    "Battery": {
        "side": "right",
        "value": lambda f: f.get("battery_type"),
    },
    "Battery life": {
        "side": "right",
        "value": lambda f: f.get("battery_life"),
    },
    "Charging time": {
        "side": "right",
        "value": lambda f: f.get("charging_time"),
    },
    "Remote Compatibility": {
        "side": "right",
        "value": lambda f: f.get("remote_compatibility"),
    },
    "Mount": {
        "side": "right",
        "value": lambda f: f.get("mount"),
    },
    "Power supply": {
        "side": "right",
        "value": lambda f: f.get("power_supply"),
    },
    "Operating temperatures": {
        "side": "right",
        "value": lambda f: f.get("operating_temperatures"),
    },
    "Maximum operating speed": {
        "side": "left",
        "value": lambda f: with_unit(f.get("max_operating_speed"), "km/h"),
    },
    "Weather rating": {
        "side": "right",
        "value": lambda f: f.get("weather_rating"),
    },
    "Camera tray size": {
        "side": "right",
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
        "side": "right",
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
        "side": "right",
        "value": lambda f: with_unit(f.get("weight"), "kg"),
    },
}
