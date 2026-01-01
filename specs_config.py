SPECS_CONFIG = {
    "Brand": {
        "side": "left",
        "value": lambda f: f.get("brand")
    },
    "Model": {
        "side": "left",
        "value": lambda f: f.get("model")
    },
    "Type": {
        "side": "left",
        "value": lambda f: f.get("type")
    },
    "Max speed": {
        "side": "left",
        "value": lambda f: (
            f'{f.get("max_speed")} km/h'
            if f.get("max_speed") is not None else None
        )
    },
    "Passengers": {
        "side": "left",
        "value": lambda f: f.get("passengers")
    },
    "Power": {
        "side": "left",
        "value": lambda f: f.get("power")
    },
    "Torque": {
        "side": "right",
        "value": lambda f: f.get("torque")
    },
    "Battery": {
        "side": "right",
        "value": lambda f: f.get("battery_type")
    },
    "Battery life": {
        "side": "right",
        "value": lambda f: f.get("battery_life")
    },
    "Charging time": {
        "side": "right",
        "value": lambda f: f.get("charging_time")
    },
    "Size": {
        "side": "right",
        "value": lambda f: (
            f'L {f.get("length")} × W {f.get("width")} × H {f.get("height")} cm'
            if all([f.get("length"), f.get("width"), f.get("height")])
            else None
        )
    },
    "Weight": {
        "side": "right",
        "value": lambda f: (
            f'{f.get("weight")} kg'
            if f.get("weight") is not None else None
        )
    },
}
