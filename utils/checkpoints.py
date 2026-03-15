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
     'detail': 'Trike : 3 bar · Stark : voir flanc pneu · Twizy : 2 bar'},
    {'key': 'brakes', 'label': 'Contrôle des freins', 'category': 'Sécurité', 'type': 'status',
     'detail': 'Voir protocole freins complet'},
    {'key': 'fonctionnement_vitesses', 'label': 'Fonctionnement des vitesses', 'category': 'Sécurité', 'type': 'status',
     'detail': 'Rouler et passer toutes les vitesses'},
    {'key': 'moteur_assistance', 'label': 'Moteur / Assistance électrique', 'category': 'Sécurité', 'type': 'status',
     'detail': 'Vérifier tous les modes d\'assistance'},
    {'key': 'test_roulage', 'label': 'Test roulage (D / R / N)', 'category': 'Sécurité', 'type': 'status',
     'detail': 'Pas de bruit anormal en roulage'},
    {'key': 'serrage_roues', 'label': 'Serrage des roues', 'category': 'Sécurité', 'type': 'status',
     'detail': 'Trike : 12 Nm · Twizy : 110 Nm'},
    {'key': 'tension_chaine', 'label': 'Tension chaîne', 'category': 'Sécurité', 'type': 'status',
     'detail': 'Vérification du jeu'},
    {'key': 'serrage_arceau', 'label': 'Serrage barres / arceau', 'category': 'Sécurité', 'type': 'status',
     'detail': 'Stark : x Nm à définir · Twizy : 45 Nm'},
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
     'detail': 'Trike : chambre à air ×2, chargeur, pompe, outils · Stark & Twizy : pièces de rechange, outils, bijouterie, chargeur'},
]

# Legacy hardcoded configs (will be used as first-time defaults if DB is empty)
LEGACY_CHECKPOINTS_CONFIG = {
    "eCar": [
        "tires", "brakes", "test_roulage", "serrage_roues", "serrage_arceau",
        "serrage_plaques_sieges", "battery", "lights", "horn", "mallette_accessoires"
    ],
    "eTrike": [
        "tires", "brakes", "fonctionnement_vitesses", "moteur_assistance", "serrage_roues",
        "serrage_plaques_sieges", "battery", "ceinture_securite", "casques_passagers", "mallette_accessoires"
    ],
    "eBike": [
        "tires", "brakes", "fonctionnement_vitesses", "moteur_assistance", "serrage_roues",
        "tension_chaine", "serrage_arceau", "battery", "protections_pilote", "systeme_communication", "mallette_accessoires"
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
    if not vehicle_name:
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
                        from utils.database import get_vehicles
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
    if current_app:
        current_app.logger.info(
            f"🔍 FALLBACK matching for vehicle: '{vehicle_search_name}'")

    for key, enabled_keys in LEGACY_CHECKPOINTS_CONFIG.items():
        if key.lower() in vehicle_search_name.lower():
            if current_app:
                current_app.logger.info(f"✅ Matched legacy config: {key}")
            return BASE_CHECKPOINTS + [
                cp for cp in ALL_POSSIBLE_CHECKPOINTS
                if cp['key'] in enabled_keys
            ]

    # Final fallback: return ALL possible checkpoints if unknown vehicle
    if current_app:
        current_app.logger.warning(
            f"⚠️ No match found for '{vehicle_search_name}', returning ALL checkpoints.")
    return BASE_CHECKPOINTS + ALL_POSSIBLE_CHECKPOINTS
