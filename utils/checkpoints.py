# utils/checkpoints.py

# Les éléments ont les clés suivantes :
# - key : la clé dans le dictionnaire data
# - label : le libellé affiché
# - unit : l'unité à afficher (ex: 'km', '%') si type='value'
# - type : 'value' (affiche la valeur + unit) ou 'status' (affiche un badge OK/Défaut/...)

# Common building blocks to ensure consistency
BASE_CHECKPOINTS = [
    {'key': 'km', 'label': 'Kilométrage', 'unit': 'km', 'type': 'value'},
    {'key': 'battery', 'label': 'Charge', 'unit': '%', 'type': 'value'},
]

ALL_POSSIBLE_CHECKPOINTS = [
    {'key': 'tires', 'label': 'Pneus', 'unit': '', 'type': 'status'},
    {'key': 'spare_tire', 'label': 'Roue de secours', 'unit': '', 'type': 'status'},
    {'key': 'brakes', 'label': 'Freins', 'unit': '', 'type': 'status'},
    {'key': 'oil', 'label': 'Niveau Huile', 'unit': '', 'type': 'status'},
    {'key': 'coolant', 'label': 'Liquide de refroidissement',
        'unit': '', 'type': 'status'},
    {'key': 'lights', 'label': 'Éclairage', 'unit': '', 'type': 'status'},
    {'key': 'engine_start', 'label': 'Démarrage Moteur', 'unit': '', 'type': 'status'},
    {'key': 'wipers', 'label': 'Essuie-glaces', 'unit': '', 'type': 'status'},
    {'key': 'horn', 'label': 'Klaxon', 'unit': '', 'type': 'status'},
    {'key': 'safety_triangle', 'label': 'Triangle / Gilet',
        'unit': '', 'type': 'status'},
    {'key': 'fire_extinguisher', 'label': 'Extincteur', 'unit': '', 'type': 'status'},
]

# Legacy hardcoded configs (will be used as first-time defaults if DB is empty)
LEGACY_CHECKPOINTS_CONFIG = {
    "eCar": [cp['key'] for cp in ALL_POSSIBLE_CHECKPOINTS],
    "eTrike": ["tires", "brakes", "lights", "horn"],
    "eBike": ["tires", "brakes", "lights", "horn"],
    "Segway": ["tires", "brakes", "lights", "horn"],
    "Jackal": ["tires", "brakes", "lights", "horn"],
}


def get_checkpoints_for_vehicle(vehicle_id: str, batch_configs=None) -> list:
    """
    Returns the list of checkpoints to display for a given vehicle.
    vehicle_id can be an Airtable Record ID or a Vehicle Name.
    batch_configs: optional dict {vehicle_id: config_dict} to avoid N+1 queries.
    """
    if not vehicle_id:
        return BASE_CHECKPOINTS

    from models import VehicleCheckpointConfig
    from flask import has_app_context, current_app

    # 1. Try batch_configs first (passed from service layer)
    if batch_configs and vehicle_id in batch_configs:
        enabled_keys = {
            k for k, v in batch_configs[vehicle_id].items() if v}
        return BASE_CHECKPOINTS + [
            cp for cp in ALL_POSSIBLE_CHECKPOINTS
            if cp['key'] in enabled_keys
        ]

    # Resolve the vehicle name if it's an Airtable ID (starts with rec)
    # We delay this to use it only as fallback for lookup or for title display
    vehicle_name = vehicle_id

    # 2. Try to get from DB if in app context
    if has_app_context():
        try:
            # Try lookup by exact ID first (Technical ID from Airtable)
            config_record = VehicleCheckpointConfig.query.filter_by(
                vehicle_id=vehicle_id).first()

            # If not found, maybe it's stored under the name?
            # (Legacy or manually entered configs)
            if not config_record:
                # Resolve name only if needed
                if vehicle_id.startswith('rec'):
                    try:
                        from utils.airtable import get_vehicles
                        vehicles = get_vehicles()
                        for v in vehicles:
                            if v['id'] == vehicle_id:
                                vehicle_name = v['fields'].get(
                                    'name', vehicle_id)
                                break
                    except Exception:
                        pass

                if vehicle_name != vehicle_id:
                    config_record = VehicleCheckpointConfig.query.filter_by(
                        vehicle_id=vehicle_name).first()

            if config_record and config_record.config:
                enabled_keys = {
                    k for k, v in config_record.config.items() if v}
                return BASE_CHECKPOINTS + [
                    cp for cp in ALL_POSSIBLE_CHECKPOINTS
                    if cp['key'] in enabled_keys
                ]
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error fetching vehicle config: {e}")

    # 3. Fallback to hardcoded legacy rules (using resolved name)
    # Last resort if no DB entry exists
    vehicle_search_name = vehicle_name or vehicle_id
    for key, enabled_keys in LEGACY_CHECKPOINTS_CONFIG.items():
        if key.lower() in vehicle_search_name.lower():
            return BASE_CHECKPOINTS + [
                cp for cp in ALL_POSSIBLE_CHECKPOINTS
                if cp['key'] in enabled_keys
            ]

    # Final fallback
    return BASE_CHECKPOINTS
