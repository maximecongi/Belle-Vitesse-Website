# utils/checkpoints.py

# Les éléments ont les clés suivantes :
# - key : la clé dans le dictionnaire data
# - label : le libellé affiché
# - unit : l'unité à afficher (ex: 'km', '%') si type='value'
# - type : 'value' (affiche la valeur + unit) ou 'status' (affiche un badge OK/Défaut/...)

DEFAULT_CHECKPOINTS = [
    {'key': 'km', 'label': 'Kilométrage', 'unit': 'km', 'type': 'value'},
    {'key': 'battery', 'label': 'Charge', 'unit': '%', 'type': 'value'},
    {'key': 'tires', 'label': 'Pneus', 'unit': '', 'type': 'status'},
    {'key': 'brakes', 'label': 'Freins', 'unit': '', 'type': 'status'},
    {'key': 'oil', 'label': 'Niveau Huile', 'unit': '', 'type': 'status'},
    {'key': 'lights', 'label': 'Éclairage', 'unit': '', 'type': 'status'},
    {'key': 'engine_start', 'label': 'Moteur', 'unit': '', 'type': 'status'}
]

# Modèles spécifiques.
# Les clés de ce dictionnaire doivent correspondre aux noms ou débuts de noms des véhicules
# tels qu'ils sont récupérés depuis Airtable (ex: "eTrike", "eCar").
CHECKPOINTS_CONFIG = {
    # eTrike n'a pas d'essuie-glaces, ni de liquide de refroidissement, ni de roue de secours.
    "eTrike": [
        {'key': 'km', 'label': 'Kilométrage', 'unit': 'km', 'type': 'value'},
        {'key': 'battery', 'label': 'Charge', 'unit': '%', 'type': 'value'},
        {'key': 'tires', 'label': 'Pneus', 'unit': '', 'type': 'status'},
        {'key': 'brakes', 'label': 'Freins', 'unit': '', 'type': 'status'},
        {'key': 'lights', 'label': 'Éclairage', 'unit': '', 'type': 'status'},
        {'key': 'horn', 'label': 'Klaxon', 'unit': '', 'type': 'status'},
    ],
    "eCar": [
        {'key': 'km', 'label': 'Kilométrage', 'unit': 'km', 'type': 'value'},
        {'key': 'battery', 'label': 'Charge', 'unit': '%', 'type': 'value'},
        {'key': 'tires', 'label': 'Pneus', 'unit': '', 'type': 'status'},
        {'key': 'spare_tire', 'label': 'Roue de secours',
            'unit': '', 'type': 'status'},
        {'key': 'brakes', 'label': 'Freins', 'unit': '', 'type': 'status'},
        {'key': 'oil', 'label': 'Niveau Huile', 'unit': '', 'type': 'status'},
        {'key': 'coolant', 'label': 'Liquide de refroidissement',
            'unit': '', 'type': 'status'},
        {'key': 'lights', 'label': 'Éclairage', 'unit': '', 'type': 'status'},
        {'key': 'engine_start', 'label': 'Démarrage Moteur',
            'unit': '', 'type': 'status'},
        {'key': 'wipers', 'label': 'Essuie-glaces', 'unit': '', 'type': 'status'},
        {'key': 'horn', 'label': 'Klaxon', 'unit': '', 'type': 'status'},
        {'key': 'safety_triangle', 'label': 'Triangle / Gilet',
            'unit': '', 'type': 'status'},
        {'key': 'fire_extinguisher', 'label': 'Extincteur',
            'unit': '', 'type': 'status'},
    ]
}


def get_checkpoints_for_vehicle(vehicle_name: str) -> list:
    """
    Retourne la liste des points de contrôle spécifique au véhicule.
    Si aucune correspondance n'est trouvée, retourne la liste par défaut.
    """
    if not vehicle_name:
        return DEFAULT_CHECKPOINTS

    for key, config in CHECKPOINTS_CONFIG.items():
        if key.lower() in vehicle_name.lower():
            return config

    return DEFAULT_CHECKPOINTS
