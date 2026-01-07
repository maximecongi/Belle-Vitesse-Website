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
    "Pan range": {
        "side": "left",
        "value": lambda f: (
            f'{f.get("pan_range")}°'
            if f.get("pan_range") is not None else None
        )
    },
     "Tilt range": {
        "side": "left",
        "value": lambda f: (
            f'{f.get("tilt_range")}°'
            if f.get("tilt_range") is not None else None
        )
    },
      "Roll range": {
        "side": "left",
        "value": lambda f: (
            f'{f.get("roll_range")}°'
            if f.get("roll_range") is not None else None
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
    "Camera tray size": {
        "side": "right",
        "value": lambda f: (
            f'D {f.get("camera_tray_depth")} × W {f.get("camera_tray_width")} × H {f.get("camera_tray_height")} mm'
            if all([f.get("camera_tray_depth"), f.get("camera_tray_width"), f.get("camera_tray_height")])
            else None
        )
    },
    "Size": {
        "side": "right",
        "value": lambda f: (
            f'L {f.get("length")} × W {f.get("width")} × H {f.get("height")} mm'
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
