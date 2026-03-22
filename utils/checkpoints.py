# utils/checkpoints.py

# Les éléments ont les clés suivantes :
# - key : la clé dans le dictionnaire data
# - label : le libellé affiché
# - unit : l'unité à afficher (ex: 'km', '%') si type='value'
# - type : 'value' (affiche la valeur + unit) ou 'status' (affiche un badge OK/Défaut/...)
# - category : 'Sécurité' ou 'Équipements'
# - detail : Texte d'aide ou précision

# Common building blocks to ensure consistency
BASE_CHECKPOINTS = []

ALL_POSSIBLE_CHECKPOINTS = [
    # SÉCURITÉ
    {'key': 'tires', 'label': 'Pression des pneus', 'category': 'Sécurité', 'type': 'status',
     'detail': 'eTrike/eTrike 360 : 3 bar · eBike : voir flanc pneu · eCar : 2 bar'},
    {'key': 'brakes', 'label': 'Contrôle des freins', 'category': 'Sécurité', 'type': 'status',
     'detail': 'Voir protocole freins complet'},
    {'key': 'fonctionnement_vitesses', 'label': 'Fonctionnement des vitesses', 'category': 'Sécurité', 'type': 'status',
     'detail': 'Rouler et passer toutes les vitesses'},
    {'key': 'moteur_assistance', 'label': 'Moteur / Assistance électrique', 'category': 'Sécurité', 'type': 'status',
     'detail': 'Vérifier tous les modes d\'assistance'},
    {'key': 'test_roulage', 'label': 'Test roulage (D / R / N)', 'category': 'Sécurité', 'type': 'status',
     'detail': 'Pas de bruit anormal en roulage'},
    {'key': 'serrage_roues', 'label': 'Serrage des roues', 'category': 'Sécurité', 'type': 'status',
     'detail': 'eTrike/eTrike 360 : 12 Nm · eCar : 110 Nm'},
    {'key': 'tension_chaine', 'label': 'Tension chaîne', 'category': 'Sécurité', 'type': 'status',
     'detail': 'Vérification du jeu'},
    {'key': 'serrage_arceau', 'label': 'Serrage barres / arceau', 'category': 'Sécurité', 'type': 'status',
     'detail': 'eBike : x Nm à définir · eCar : 45 Nm'},
    {'key': 'serrage_plaques_sieges', 'label': 'Serrage plaques & sièges', 'category': 'Sécurité', 'type': 'status',
     'detail': 'Vérification du serrage'},
    {'key': 'ceinture_securite', 'label': 'Ceinture de sécurité', 'category': 'Sécurité', 'type': 'status',
     'detail': 'Fonctionnement & état'},
    {'key': 'lights', 'label': 'Phares & clignotants', 'category': 'Sécurité', 'type': 'status',
     'detail': 'Fonctionnement complet'},
    {'key': 'horn', 'label': 'Klaxon', 'category': 'Sécurité', 'type': 'status',
     'detail': 'Fonctionnement'},

    # ÉQUIPEMENTS
    {'key': 'battery', 'label': 'Charge', 'unit': '%',
     'type': 'value', 'category': 'Équipements'},
    {'key': 'casques_passagers', 'label': 'Casques passagers', 'category': 'Équipements', 'type': 'status',
     'detail': 'Trike : x casques à définir'},
    {'key': 'protections_pilote', 'label': 'Protections pilote', 'category': 'Équipements', 'type': 'status',
     'detail': 'Casque, combi, gants, bottes, jeans, veste, masque'},
    {'key': 'systeme_communication', 'label': 'Système de communication', 'category': 'Équipements', 'type': 'status',
     'detail': 'À définir'},
    {'key': 'mallette_accessoires', 'label': 'Mallette / Roulante accessoires', 'category': 'Équipements', 'type': 'status',
     'detail': 'eTrike/eTrike 360 : chambre à air ×2, chargeur, pompe, outils · eBike & eCar : pièces de rechange, outils, bijouterie, chargeur'},
]

# Mapping from English 'key' to standardized English database columns in models.py
CHECKPOINT_TO_MODEL_MAP = {
    'tires': 'tire_status',
    'brakes': 'brake_status',
    'lights': 'exterior_lighting_status',
    'horn': 'horn_status',
    'fonctionnement_vitesses': 'gearbox_status',
    'moteur_assistance': 'engine_assistance_status',
    'test_roulage': 'driving_test_status',
    'serrage_roues': 'wheel_tightness_status',
    'tension_chaine': 'chain_tension_status',
    'serrage_arceau': 'roll_bar_tightness_status',
    'serrage_plaques_sieges': 'seat_plate_tightness_status',
    'ceinture_securite': 'seat_belt_status',
    'casques_passagers': 'passenger_helmets_status',
    'protections_pilote': 'pilot_protections_status',
    'systeme_communication': 'communication_system_status',
    'mallette_accessoires': 'accessories_case_status',
}

# Specific detail overrides by vehicle type/name
SPECIFIC_DETAILS = {
    "eCar": [
        ("tires", "eCar : 2 bar"),
        ("serrage_roues", "eCar : 110 Nm"),
        ("serrage_arceau", "eCar : 45 Nm"),
        ("mallette_accessoires",
         "eCar : pièces de rechange, outils, bijouterie, chargeur"),
    ],
    "eTrike": [
        ("tires", "eTrike/eTrike 360 : 3 bar"),
        ("serrage_roues", "eTrike/eTrike 360 : 12 Nm"),
        ("mallette_accessoires", "Trike : chambre à air ×2, chargeur, pompe, outils"),
    ],
    "eBike": [
        ("tires", "eBike : voir flanc pneu"),
        ("serrage_roues", "eBike : 110 Nm"),
        ("serrage_arceau", "eBike : 45 Nm"),
        ("mallette_accessoires",
         "eBike : pièces de rechange, outils, bijouterie, chargeur"),
    ],
}


def get_checkpoints_for_vehicle(vehicle_id: str, batch_configs=None, vehicle_name=None) -> list:
    """
    Returns the list of checkpoints to display for a given vehicle.
    vehicle_id can be an Airtable Record ID or a Vehicle Name.
    batch_configs: optional dict {vehicle_id: config_dict} to avoid N+1 queries.
    """
    if not vehicle_id:
        return BASE_CHECKPOINTS

    from flask import current_app, has_app_context

    # 1. Try batch_configs first (passed from service layer)
    if batch_configs and vehicle_id in batch_configs:
        config = batch_configs[vehicle_id]
        if isinstance(config, dict):
            # DB config is a dict {key: bool}
            enabled_keys = {k for k, v in config.items() if v}
        else:
            # Legacy or other format might be a list
            enabled_keys = config

        return BASE_CHECKPOINTS + _resolve_checkpoints(enabled_keys)

    # Resolve the vehicle name if it's an Airtable ID (starts with rec)
    if not vehicle_name:
        vehicle_name = vehicle_id

    # Try to resolve actual name from DB/Airtable if we only have an ID so we can match SPECIFIC_DETAILS later
    if has_app_context() and vehicle_id.startswith('rec') and vehicle_name == vehicle_id:
        try:
            from utils.database import get_vehicles
            vehicles = get_vehicles()
            for v in vehicles:
                if v['id'] == vehicle_id:
                    vehicle_name = v['fields'].get('name', vehicle_id)
                    break
        except Exception:
            pass

    # 1. Try batch_configs first (passed from service layer)
    if batch_configs and vehicle_id in batch_configs:
        config = batch_configs[vehicle_id]
        if isinstance(config, dict):
            # DB config is a dict {key: bool}
            enabled_keys = {k for k, v in config.items() if v}
        else:
            # Legacy or other format might be a list
            enabled_keys = config

        return BASE_CHECKPOINTS + _resolve_checkpoints(enabled_keys, vehicle_name)

    # 2. Try to get from DB (cached) if in app context
    if has_app_context():
        try:
            from services.admin.vehicle_config import get_checkpoint_configs
            all_configs = get_checkpoint_configs()

            config = all_configs.get(vehicle_id)
            if not config and vehicle_id.startswith('rec') and vehicle_name != vehicle_id:
                config = all_configs.get(vehicle_name)

            if config:
                # DB config is usually {key: bool}
                enabled_keys = {k for k, v in config.items() if v}
                return BASE_CHECKPOINTS + _resolve_checkpoints(enabled_keys, vehicle_name)
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error fetching vehicle config: {e}")

    # Final fallback: return ALL possible checkpoints
    return BASE_CHECKPOINTS + ALL_POSSIBLE_CHECKPOINTS


def _resolve_checkpoints(enabled_keys, vehicle_name=None) -> list:
    """Helper to build list of checkpoint dicts, supporting optional detail overrides from SPECIFIC_DETAILS."""
    # Base enabled keys (usually just a set/list of strings from DB)
    enabled_keys_set = set()
    for item in enabled_keys:
        if isinstance(item, (tuple, list)) and len(item) >= 1:
            enabled_keys_set.add(item[0])
        else:
            enabled_keys_set.add(item)

    # Find specific details for the given vehicle
    detail_overrides = {}
    if vehicle_name:
        for v_type, specific_list in SPECIFIC_DETAILS.items():
            if v_type.lower() in vehicle_name.lower():
                for item in specific_list:
                    if isinstance(item, (tuple, list)) and len(item) >= 2:
                        detail_overrides[item[0]] = item[1]
                break

    result = []
    for cp in ALL_POSSIBLE_CHECKPOINTS:
        if cp['key'] in enabled_keys_set:
            new_cp = cp.copy()
            if cp['key'] in detail_overrides:
                new_cp['detail'] = detail_overrides[cp['key']]
            result.append(new_cp)

    return result
