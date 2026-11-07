import json
import logging
import re

from models import AppSetting
from utils.image_utils import extract_vehicle_image

logger = logging.getLogger(__name__)


def _to_lines(value):
    """Convertit une liste ou une chaîne multiligne en liste de chaînes (non filtrée)."""
    if isinstance(value, list):
        return [str(r) if r is not None else "" for r in value]
    if isinstance(value, str):
        return value.split("\n")
    return []


def normalize_rule_pairs(rules_fr, rules_en):
    """Aligne les consignes FR/EN ligne à ligne.

    Les deux listes retournées ont toujours la même longueur : seules les lignes
    vides en FR *et* en EN sont retirées, une traduction manquante est conservée
    sous forme de chaîne vide pour ne pas décaler les paires suivantes.
    """
    fr_list = _to_lines(rules_fr)
    en_list = _to_lines(rules_en)
    clean_fr, clean_en = [], []
    for i in range(max(len(fr_list), len(en_list))):
        fr = fr_list[i].strip() if i < len(fr_list) else ""
        en = en_list[i].strip() if i < len(en_list) else ""
        if fr or en:
            clean_fr.append(fr)
            clean_en.append(en)
    return clean_fr, clean_en

# ── Règles Générales de Sécurité Universelles par défaut (FR / EN) ──
# Applicables à tous les tournages (y compris en location sèche sans pilote BV)
DEFAULT_GENERAL_SAFETY_RULES = {
    "rules_fr": [
        "Seul le pilote désigné d'un commun accord avec le coordonnateur cascade conduit le véhicule.",
        "Interdiction de monter ou descendre du véhicule en mouvement.",
        "Zone de roulage définie et sécurisée par la production avant chaque séquence (périmètre, circulation, public).",
        "Les véhicules sont seulement autorisés à rouler sur routes fermées.",
        "Tout élément technique doit être élingué et sécurisé.",
    ],
    "rules_en": [
        "Only the driver designated by mutual agreement with the stunt coordinator may drive the vehicle.",
        "No getting on or off the vehicle while it is moving.",
        "The driving area must be defined and secured by the production before each sequence (perimeter, traffic, public).",
        "Vehicles may only be driven on closed roads.",
        "Every technical element must be rigged and secured.",
    ],
}

# ── Règles Spécifiques en Présence de Référents Plateau BV (FR / EN) ──
# Prolonge automatiquement la Section 1 si des référents BV sont affectés au projet.
# Supporte les placeholders {technicians_and} (conjonction 'et'/'and') et {technicians_or} (disjonction 'ou'/'or').
# L'ancien nom {technicians} reste accepté comme alias de {technicians_and}.
TECHNICIANS_AND_PLACEHOLDER = "{technicians_and}"
TECHNICIANS_OR_PLACEHOLDER = "{technicians_or}"
LEGACY_TECHNICIANS_PLACEHOLDER = "{technicians}"


def _migrate_legacy_placeholders(rules):
    """Renomme l'ancien placeholder {technicians} en {technicians_and} dans une liste de consignes."""
    return [str(r).replace(LEGACY_TECHNICIANS_PLACEHOLDER, TECHNICIANS_AND_PLACEHOLDER) for r in (rules or [])]


DEFAULT_BV_REFERENTS_SAFETY_RULES = {
    "rules_fr": [
        "Le pilote ainsi que {technicians_and}, technicien(s) véhicule, peuvent refuser ou interrompre un mouvement s'ils estiment que la sécurité n'est pas assurée.",
        "Chaque nouvelle installation doit être validée au niveau sécurité par {technicians_or}.",
        "Au moins un des techniciens référents ({technicians_or}) doit avoir accès au véhicule en permanence, depuis un véhicule suiveur.",
    ],
    "rules_en": [
        "The driver, as well as {technicians_and}, vehicle technician(s), may refuse or stop any move if they consider that safety is not ensured.",
        "Every new setup must be safety-approved by {technicians_or}.",
        "At least one of the vehicle technicians ({technicians_or}) must have constant access to the vehicle, from a follow vehicle.",
    ],
}

# ── Règles de sécurité par défaut par famille de véhicule (FR / EN) ──
DEFAULT_VEHICLE_SAFETY_RULES = {
    "erover": {
        "label": "eRover (Polaris Kinetic)",
        "keywords": ["erover", "polaris", "kinetic", "rover", "buggy"],
        "rules_fr": [
            "Casque obligatoire pour toute personne à l'extérieur de l'habitacle.",
            "Ceinture obligatoire pour toute personne présente sur le véhicule en roulage.",
            "Double ceinture pour tout opérateur caméra exposé à l'extérieur de l'habitacle.",
            "Nombre de personnes autorisées en roulage : 1 pilote + 4 passagers maximum, dont 2 au plus à l'extérieur de l'habitacle.",
            "Répartition du poids cohérente sur le véhicule.",
            "Double klaxon avant chaque mouvement pour prévenir l'équipe du déplacement.",
            "Aucune modification interne du véhicule n'est autorisée.",
            "Safety meeting obligatoire le premier jour de tournage pour les personnes présentes sur le véhicule et avant la première montée de toute nouvelle personne.",
            "Le pilote s'engage à faire respecter le port de la ceinture et du casque.",
        ],
        "rules_en": [
            "Helmet mandatory for anyone outside the cabin.",
            "Seatbelt mandatory for anyone on board while the vehicle is moving.",
            "Double harness for any camera operator exposed outside the cabin.",
            "Maximum number of people on board while moving : 1 driver + 4 people, of which no more than 2 outside the cabin.",
            "Weight must be evenly distributed on the vehicle.",
            "Two horn blasts before every move to warn the crew.",
            "No internal modification of the vehicle is allowed.",
            "Mandatory safety meeting on the first day of shooting for everyone riding on the vehicle, and before any new person gets on board for the first time.",
            "The driver is responsible for enforcing seatbelt and helmet rules.",
        ],
        "equipment_ids": ["helmets_jet", "operator_harness"],
    },
    "erider": {
        "label": "eRider (Stark Varg)",
        "keywords": ["erider", "stark", "varg", "rider", "moto", "ebike"],
        "rules_fr": [
            "Casque obligatoire.",
            "Protection intégrale recommandée pour le pilote.",
            "Roulage réservé au pilote agréé habilité à la conduite de motos tout-terrain haute performance.",
            "Vérification préalable de la trajectoire et de l'adhérence du sol avant toute prise.",
        ],
        "rules_en": [
            "Helmet mandatory.",
            "Full body protection recommended for the rider.",
            "Riding restricted to approved rider qualified for high-performance off-road electric motorcycles.",
            "Prior inspection of surface traction and driving path before any take.",
        ],
        "equipment_ids": ["moto_helmet", "joint_protections"],
    },
    "ecar": {
        "label": "eCar (Twizy)",
        "keywords": ["ecar", "twizy", "car"],
        "rules_fr": [
            "Casque obligatoire pour tout opérateur sur plateforme extérieure ou arrière.",
            "Respect strict de la charge maximale utile (110 kg sur arceau / plateformes).",
            "Élingage obligatoire de la tête caméra et de tout accessoire technique.",
            "Ceinture de sécurité obligatoire pour le pilote et le passager avant.",
        ],
        "rules_en": [
            "Helmet mandatory for any operator on external or rear platform.",
            "Strict compliance with maximum payload (110 kg on rig / platforms).",
            "Mandatory safety tethering for camera head and all technical accessories.",
            "Seatbelt mandatory for driver and front passenger.",
        ],
        "equipment_ids": ["helmets_jet", "camera_tethers"],
    },
    "etrike": {
        "label": "eTrike / Trike 360",
        "keywords": ["etrike", "trike", "360", "back trike"],
        "rules_fr": [
            "Casque obligatoire pour toute personne sur le trike en roulage.",
            "Vitesse maximale adaptée au rayon de braquage et à la stabilité de la charge.",
            "Élingage de sécurité obligatoire pour tout matériel de prise de vues embarqué.",
            "Interdiction de se pencher en dehors de la plateforme en mouvement.",
        ],
        "rules_en": [
            "Helmet mandatory for anyone on the trike while moving.",
            "Speed adapted to turning radius and payload stability.",
            "Mandatory safety tethering for all onboard camera equipment.",
            "Do not lean outside the platform while moving.",
        ],
        "equipment_ids": ["helmets_jet", "camera_tethers"],
    },
    "segway": {
        "label": "Segway i2 / x2",
        "keywords": ["segway", "i2", "x2", "gyropode"],
        "rules_fr": [
            "Casque et protections articulaires obligatoires pour l'opérateur.",
            "Utilisation réservée à un opérateur formé et agréé.",
            "Sol sec, propre et sans dénivelé imprévu.",
            "Vérification du hardmount Steadicam avant chaque prise.",
        ],
        "rules_en": [
            "Helmet and joint protective gear mandatory for operator.",
            "Use restricted to trained and approved operator.",
            "Dry, clean ground free of unexpected drop-offs.",
            "Check Steadicam hardmount before every take.",
        ],
        "equipment_ids": ["joint_protections"],
    },
    "rickshaw": {
        "label": "Jackal Rickshaw",
        "keywords": ["rickshaw", "jackal"],
        "rules_fr": [
            "Casque recommandé pour l'opérateur sur le siège.",
            "Harnais de maintien recommandé selon la configuration.",
            "Opérateur et pousseurs synchronisés avant tout mouvement.",
        ],
        "rules_en": [
            "Helmet recommended for seated operator.",
            "Safety harness recommended depending on setup.",
            "Operator and grips synchronized before any movement.",
        ],
        "equipment_ids": ["operator_harness", "helmets_jet"],
    },
}

DEFAULT_SAFETY_EQUIPMENT_CATALOG = [
    {
        "id": "helmets_jet",
        "label_fr": "Casques mis à disposition : 6 casques jet ouverts (1 Small, 2 Medium, 2 Large, 1 XLarge).",
        "label_en": "Helmets provided : 6 open face jet helmets (1 Small, 2 Medium, 2 Large, 1 XLarge).",
    },
    {
        "id": "operator_harness",
        "label_fr": "Harnais de maintien et double ceinture de sécurité opérateur.",
        "label_en": "Operator safety harness and double safety seatbelt.",
    },
    {
        "id": "camera_tethers",
        "label_fr": "Élingues de sécurité acier certifiées pour matériel caméra.",
        "label_en": "Certified steel safety tethers for camera equipment.",
    },
    {
        "id": "joint_protections",
        "label_fr": "Kit complet de protections articulaires opérateur (genouillères, coudières).",
        "label_en": "Complete operator joint protective gear kit (knee pads, elbow pads).",
    },
    {
        "id": "moto_helmet",
        "label_fr": "Casque moto homologué mis à disposition.",
        "label_en": "Certified motorcycle helmet provided.",
    },
]

DEFAULT_HELMETS_INVENTORY = {
    "total": 6,
    "description_fr": "6 casques jet ouverts : 1 Small, 2 Medium, 2 Large, 1 XLarge",
    "description_en": "6 open face jet helmets : 1 Small, 2 Medium, 2 Large, 1 XLarge",
    "sizes": {"Small": 1, "Medium": 2, "Large": 2, "XLarge": 1},
}


def get_safety_equipment_catalog():
    """
    Retourne le catalogue global des équipements de sécurité (FR / EN).
    Chaque équipement possède un identifiant unique stable (id), label_fr et label_en.
    """
    try:
        custom_raw = AppSetting.get("safety_equipment_catalog", None)
        if custom_raw is not None and str(custom_raw).strip() != "":
            if isinstance(custom_raw, str):
                custom_list = json.loads(custom_raw)
            elif isinstance(custom_raw, list):
                custom_list = custom_raw
            else:
                custom_list = None

            # Une liste enregistrée (même vide) fait foi : pas de retour aux valeurs par défaut
            if isinstance(custom_list, list):
                res = []
                for item in custom_list:
                    if isinstance(item, dict) and item.get("id"):
                        res.append({
                            "id": str(item["id"]).strip(),
                            "label_fr": str(item.get("label_fr") or "").strip(),
                            "label_en": str(item.get("label_en") or "").strip(),
                        })
                return res
    except Exception as e:
        logger.warning(f"Erreur lors de la lecture du catalogue d'équipements de sécurité : {e}")

    return [dict(item) for item in DEFAULT_SAFETY_EQUIPMENT_CATALOG]


def save_safety_equipment_catalog(equipment_items):
    """
    Enregistre le catalogue global des équipements de sécurité dans AppSetting.
    equipment_items peut être une liste de dicts (id, label_fr, label_en) ou de tuples.
    """
    try:
        clean_items = []
        for idx, item in enumerate(equipment_items or []):
            if isinstance(item, dict):
                item_id = str(item.get("id") or "").strip()
                label_fr = str(item.get("label_fr") or "").strip()
                label_en = str(item.get("label_en") or "").strip()
            elif isinstance(item, (list, tuple)):
                item_id = str(item[0]).strip() if len(item) > 0 else ""
                label_fr = str(item[1]).strip() if len(item) > 1 else ""
                label_en = str(item[2]).strip() if len(item) > 2 else ""
            else:
                continue

            if not label_fr and not label_en:
                continue
            if not item_id:
                # Génère un identifiant slugifié à partir du libellé français ou d'un index
                import re
                slug = re.sub(r'[^a-z0-9]+', '_', label_fr.lower())[:30].strip('_')
                item_id = slug or f"eq_{idx + 1}"

            clean_items.append({
                "id": item_id,
                "label_fr": label_fr,
                "label_en": label_en,
            })

        AppSetting.set("safety_equipment_catalog", json.dumps(clean_items, ensure_ascii=False))
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde du catalogue d'équipements : {e}")
        return False


# Alias rétro-compatible
_extract_vehicle_image = extract_vehicle_image


def _find_default_rules(name):
    """Associe des règles et identifiants d'équipements par défaut en fonction du nom du véhicule."""
    query = (name or "").lower().strip()
    for key, data in DEFAULT_VEHICLE_SAFETY_RULES.items():
        if key in query:
            return (
                list(data.get("rules_fr") or []),
                list(data.get("rules_en") or []),
                data.get("label") or name,
                list(data.get("equipment_ids") or []),
            )
        for kw in data.get("keywords") or []:
            if kw in query:
                return (
                    list(data.get("rules_fr") or []),
                    list(data.get("rules_en") or []),
                    data.get("label") or name,
                    list(data.get("equipment_ids") or []),
                )
    return (
        [
            "Casque obligatoire pour toute personne sur le véhicule en roulage.",
            "Respect strict des consignes du pilote et du superviseur Belle Vitesse.",
        ],
        [
            "Helmet mandatory for anyone on the vehicle while moving.",
            "Strict compliance with instructions from the pilot and Belle Vitesse crew.",
        ],
        name or "Véhicule",
        ["helmets_jet"],
    )


def _equipment_pairs(equipment_ids, eq_catalog):
    """Retourne les libellés FR/EN alignés des équipements rattachés (EN vide si non traduit)."""
    eq_fr, eq_en = [], []
    for x in equipment_ids:
        item = eq_catalog.get(x)
        if item and (item.get("label_fr") or item.get("label_en")):
            eq_fr.append(item.get("label_fr") or item.get("label_en"))
            eq_en.append(item.get("label_en") or "")
    return eq_fr, eq_en


def _match_legacy_custom_key(vname, custom_dict, fleet_ids):
    """Retrouve une personnalisation enregistrée sous une ancienne clé nominative (ex: "erover").

    Les clés correspondant à l'id d'un véhicule de la flotte sont ignorées : elles
    appartiennent à ce véhicule (évite qu'un id "3" corresponde à « eTrike 360 »).
    Correspondance exacte d'abord, puis par mot entier en privilégiant la clé la plus longue.
    """
    vname_lower = (vname or "").lower().strip()
    if not vname_lower:
        return None
    candidates = [
        k for k, v in custom_dict.items()
        if isinstance(v, dict) and str(k).strip() and str(k) not in fleet_ids
    ]
    for k in candidates:
        if k.lower().strip() == vname_lower:
            return k
    for k in sorted(candidates, key=len, reverse=True):
        k_lower = k.lower().strip()
        if len(k_lower) >= 3 and not k_lower.isdigit() and re.search(
            r"(?<![a-z0-9])" + re.escape(k_lower) + r"(?![a-z0-9])", vname_lower
        ):
            return k
    return None


def get_all_vehicle_safety_rules_catalog():
    """
    Retourne le catalogue des règles de sécurité pour chaque véhicule réel de la flotte,
    en combinant les règles par défaut, les équipements rattachés et les personnalisations enregistrées.
    """
    catalog = {}
    custom_dict = {}
    consumed_legacy_keys = set()
    eq_catalog = {eq["id"]: eq for eq in get_safety_equipment_catalog()}

    try:
        custom_raw = AppSetting.get("fleet_safety_rules", None)
        if custom_raw:
            if isinstance(custom_raw, str):
                custom_dict = json.loads(custom_raw)
            elif isinstance(custom_raw, dict):
                custom_dict = custom_raw
    except Exception as e:
        logger.warning(f"Erreur lors de la lecture des règles de sécurité de flotte : {e}")

    # Récupération des véhicules réels de la flotte avec fusion systématique des données SQL locales
    fleet_vehicles = []
    seen_ids = set()
    try:
        from utils.database import get_vehicles
        for v in (get_vehicles() or []):
            fleet_vehicles.append(v)
            if v.get("id"):
                seen_ids.add(str(v["id"]))
    except Exception as e:
        logger.warning(f"Impossible de charger les véhicules via get_vehicles : {e}")

    try:
        from models.catalog import Vehicle
        db_vehs = Vehicle.query.all()
        for v in db_vehs:
            if str(v.id) not in seen_ids:
                fleet_vehicles.append({
                    "id": v.id,
                    "fields": v.fields or {}
                })
                seen_ids.add(str(v.id))
    except Exception as e:
        logger.warning(f"Erreur réconciliation véhicules règles de sécurité : {e}")

    # Si des véhicules existent dans la flotte
    if fleet_vehicles:
        for veh in fleet_vehicles:
            vid = str(veh.get("id") or "").strip()
            fields = veh.get("fields") or {}
            vname = fields.get("Nom") or fields.get("name") or f"Véhicule {vid}"
            vimg = _extract_vehicle_image(fields)

            def_fr, def_en, def_lbl, def_eq_ids = _find_default_rules(vname)

            # Recherche d'une personnalisation (par id, ou fallback par ancienne clé nominative)
            custom_entry = custom_dict.get(vid)
            if not custom_entry:
                legacy_key = _match_legacy_custom_key(vname, custom_dict, seen_ids)
                if legacy_key:
                    custom_entry = custom_dict[legacy_key]
                    consumed_legacy_keys.add(legacy_key)

            if custom_entry and isinstance(custom_entry, dict):
                label = custom_entry.get("label") or def_lbl
                rules_fr = custom_entry.get("rules_fr", def_fr)
                rules_en = custom_entry.get("rules_en", def_en)
                equipment_ids = custom_entry.get("equipment_ids")
                if equipment_ids is None:
                    equipment_ids = def_eq_ids
            else:
                label = def_lbl
                rules_fr = def_fr
                rules_en = def_en
                equipment_ids = def_eq_ids

            clean_eq_ids = [str(x).strip() for x in equipment_ids if str(x).strip()] if isinstance(equipment_ids, list) else []
            eq_fr, eq_en = _equipment_pairs(clean_eq_ids, eq_catalog)

            catalog[vid] = {
                "id": vid,
                "name": vname,
                "image": vimg,
                "label": label,
                "rules_fr": normalize_rule_pairs(rules_fr, rules_en)[0],
                "rules_en": normalize_rule_pairs(rules_fr, rules_en)[1],
                "equipment_ids": clean_eq_ids,
                "equipment_fr": eq_fr,
                "equipment_en": eq_en,
            }
    else:
        # Fallback de secours (tests unitaires sans BDD de flotte)
        for key, data in DEFAULT_VEHICLE_SAFETY_RULES.items():
            custom_entry = custom_dict.get(key, {})
            label = custom_entry.get("label") or data.get("label") or key.capitalize()
            rules_fr = custom_entry.get("rules_fr", data.get("rules_fr", []))
            rules_en = custom_entry.get("rules_en", data.get("rules_en", []))
            equipment_ids = custom_entry.get("equipment_ids")
            if equipment_ids is None:
                equipment_ids = data.get("equipment_ids", [])

            clean_eq_ids = [str(x).strip() for x in equipment_ids if str(x).strip()] if isinstance(equipment_ids, list) else []
            eq_fr, eq_en = _equipment_pairs(clean_eq_ids, eq_catalog)

            catalog[key] = {
                "id": key,
                "name": label,
                "image": "/static/imgs/placeholders/vehicle.svg",
                "label": label,
                "rules_fr": normalize_rule_pairs(rules_fr, rules_en)[0],
                "rules_en": normalize_rule_pairs(rules_fr, rules_en)[1],
                "equipment_ids": clean_eq_ids,
                "equipment_fr": eq_fr,
                "equipment_en": eq_en,
            }

    # Inclure également les entrées personnalisées enregistrées dans AppSetting non encore dans catalog
    # (hors anciennes clés nominatives déjà rattachées à un véhicule réel, pour éviter les doublons)
    for c_id, c_data in custom_dict.items():
        if c_id not in catalog and c_id not in consumed_legacy_keys and isinstance(c_data, dict):
            c_label = c_data.get("label") or c_id
            equipment_ids = c_data.get("equipment_ids") or []
            clean_eq_ids = [str(x).strip() for x in equipment_ids if str(x).strip()] if isinstance(equipment_ids, list) else []
            eq_fr, eq_en = _equipment_pairs(clean_eq_ids, eq_catalog)

            catalog[c_id] = {
                "id": c_id,
                "name": c_label,
                "image": "/static/imgs/placeholders/vehicle.svg",
                "label": c_label,
                "rules_fr": normalize_rule_pairs(c_data.get("rules_fr"), c_data.get("rules_en"))[0],
                "rules_en": normalize_rule_pairs(c_data.get("rules_fr"), c_data.get("rules_en"))[1],
                "equipment_ids": clean_eq_ids,
                "equipment_fr": eq_fr,
                "equipment_en": eq_en,
            }

    return catalog


def save_vehicle_safety_rules(vehicle_id=None, rules_fr=None, rules_en=None, label=None, vehicle_key=None, equipment_ids=None, **kwargs):
    """
    Enregistre ou met à jour les règles et les identifiants d'équipements sélectionnés pour un véhicule.
    """
    try:
        target_id = vehicle_id or vehicle_key
        if not target_id:
            logger.error("Identifiant de véhicule manquant pour save_vehicle_safety_rules")
            return False

        clean_id = str(target_id).strip()
        custom_raw = AppSetting.get("fleet_safety_rules", None)
        if custom_raw:
            if isinstance(custom_raw, str):
                custom_dict = json.loads(custom_raw)
            elif isinstance(custom_raw, dict):
                custom_dict = custom_raw
            else:
                custom_dict = {}
        else:
            custom_dict = {}

        entry = custom_dict.get(clean_id, {})
        if label:
            entry["label"] = label.strip()
        entry["rules_fr"], entry["rules_en"] = normalize_rule_pairs(rules_fr, rules_en)
        if equipment_ids is not None:
            if isinstance(equipment_ids, list):
                entry["equipment_ids"] = [str(x).strip() for x in equipment_ids if str(x).strip()]
            elif isinstance(equipment_ids, str):
                entry["equipment_ids"] = [x.strip() for x in equipment_ids.split(",") if x.strip()]

        custom_dict[clean_id] = entry
        AppSetting.set("fleet_safety_rules", json.dumps(custom_dict, ensure_ascii=False))
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde des règles de sécurité pour le véhicule {vehicle_id or vehicle_key} : {e}")
        return False


def get_safety_rules_for_vehicles(vehicles_details, catalog=None):
    """
    Extrait les règles de sécurité dédupliquées pour une liste de véhicules d'un tournage.
    vehicles_details peut être une liste de dicts (avec 'id', 'name', 'slug') ou une chaîne / liste d'identifiants/noms.
    """
    if catalog is None:
        catalog = get_all_vehicle_safety_rules_catalog()

    matched_categories = {}

    if isinstance(vehicles_details, str):
        vehicle_items = [v.strip() for v in vehicles_details.split(",") if v.strip()]
    elif isinstance(vehicles_details, list):
        vehicle_items = vehicles_details
    else:
        vehicle_items = []

    for item in vehicle_items:
        vid = ""
        vname = ""
        vslug = ""
        if isinstance(item, dict):
            vid = str(item.get("id") or "").strip()
            vname = str(item.get("name") or "").strip()
            vslug = str(item.get("slug") or "").strip().lower()
        elif isinstance(item, str):
            vid = item.strip()
            vname = item.strip()
            vslug = item.strip().lower()

        # 1. Correspondance directe par ID ou slug exact
        entry = catalog.get(vid) or (catalog.get(vslug) if vslug else None)

        # 2. Correspondance par nom ou label exact
        if not entry:
            vname_lower = vname.lower()
            for c_id, c_data in catalog.items():
                if c_id.lower() == vname_lower or (vslug and c_id.lower() == vslug):
                    entry = c_data
                    break
                if c_data.get("name", "").lower() == vname_lower or c_data.get("label", "").lower() == vname_lower:
                    entry = c_data
                    break

        # 3. Correspondance partielle (ex: "erover" dans "eRover 01" ou c_id dans vname_lower)
        if not entry:
            vname_lower = vname.lower()
            for c_id, c_data in catalog.items():
                c_id_lower = c_id.lower()
                c_name_lower = c_data.get("name", "").lower()
                c_lbl_lower = c_data.get("label", "").lower()
                # Un id numérique ne doit jamais matcher par sous-chaîne (ex: "3" dans "etrike 360")
                if (
                    (c_id_lower and not c_id_lower.isdigit() and c_id_lower in vname_lower)
                    or (vslug and vslug in c_id_lower)
                    or (c_name_lower and c_name_lower in vname_lower)
                    or (c_lbl_lower and c_lbl_lower in vname_lower)
                    or (vname_lower and vname_lower in c_name_lower)
                ):
                    entry = c_data
                    break

        if entry:
            label = entry.get("label") or entry.get("name") or vname
            if label not in matched_categories:
                matched_categories[label] = {
                    "label": label,
                    "rules_fr": entry.get("rules_fr") or [],
                    "rules_en": entry.get("rules_en") or [],
                    "equipment_ids": entry.get("equipment_ids") or [],
                    "equipment_fr": entry.get("equipment_fr") or [],
                    "equipment_en": entry.get("equipment_en") or [],
                }

    return list(matched_categories.values())


def get_safety_equipment_for_vehicles(vehicles_details, catalog=None):
    """
    Rassemble et déduplique la liste des équipements de sécurité fournis
    pour l'ensemble des véhicules réservés d'un tournage à partir du catalogue d'équipements.
    Résolution garantie sans doublon via l'ID de chaque équipement.
    Retourne un dict: {"rules_fr": [...], "rules_en": [...]}
    """
    v_rules = get_safety_rules_for_vehicles(vehicles_details, catalog=catalog)
    eq_catalog = {eq["id"]: eq for eq in get_safety_equipment_catalog()}

    compiled_fr = []
    compiled_en = []
    seen_ids = set()
    seen_labels = set()

    for vr in v_rules:
        # 1. Utilisation prioritaire des equipment_ids rattachés
        for eq_id in (vr.get("equipment_ids") or []):
            clean_id = str(eq_id).strip()
            if clean_id and clean_id not in seen_ids:
                seen_ids.add(clean_id)
                eq_item = eq_catalog.get(clean_id)
                if eq_item:
                    l_fr = eq_item.get("label_fr") or ""
                    l_en = eq_item.get("label_en") or ""
                    if l_fr and l_fr.lower() not in seen_labels:
                        seen_labels.add(l_fr.lower())
                        compiled_fr.append(l_fr)
                        compiled_en.append(l_en)

        # 2. Rétro-compatibilité si un véhicule a directement equipment_fr
        for idx, item_fr in enumerate(vr.get("equipment_fr") or []):
            clean_fr = str(item_fr).strip()
            if not clean_fr:
                continue
            norm_key = clean_fr.lower()
            if norm_key not in seen_labels:
                seen_labels.add(norm_key)
                compiled_fr.append(clean_fr)
                eq_en_list = vr.get("equipment_en") or []
                item_en = eq_en_list[idx].strip() if (idx < len(eq_en_list) and str(eq_en_list[idx]).strip()) else ""
                compiled_en.append(item_en)

    return {
        "rules_fr": compiled_fr,
        "rules_en": compiled_en,
    }


def get_general_safety_rules():
    """
    Retourne les règles générales de sécurité (FR / EN).
    Lit la configuration personnalisée dans AppSetting ("general_safety_rules") ou la dotation initiale.
    Aucun fallback forcé si la configuration enregistrée contient des listes vides ou modifiées.
    """
    try:
        custom_raw = AppSetting.get("general_safety_rules", None)
        if custom_raw is not None and str(custom_raw).strip() != "":
            if isinstance(custom_raw, str):
                custom_dict = json.loads(custom_raw)
            elif isinstance(custom_raw, dict):
                custom_dict = custom_raw
            else:
                custom_dict = {}

            if isinstance(custom_dict, dict) and ("rules_fr" in custom_dict or "rules_en" in custom_dict):
                rules_fr, rules_en = normalize_rule_pairs(
                    custom_dict.get("rules_fr"), custom_dict.get("rules_en"))
                return {"rules_fr": rules_fr, "rules_en": rules_en}
    except Exception as e:
        logger.warning(f"Erreur lors de la lecture des règles générales de sécurité : {e}")

    return {
        "rules_fr": list(DEFAULT_GENERAL_SAFETY_RULES["rules_fr"]),
        "rules_en": list(DEFAULT_GENERAL_SAFETY_RULES["rules_en"]),
    }


def save_general_safety_rules(rules_fr=None, rules_en=None):
    """
    Enregistre les règles générales de sécurité (FR / EN) dans AppSetting.
    Accepte des listes ou des chaînes multilignes.
    """
    try:
        clean_fr, clean_en = normalize_rule_pairs(rules_fr, rules_en)

        payload = {
            "rules_fr": clean_fr,
            "rules_en": clean_en,
        }
        AppSetting.set("general_safety_rules", json.dumps(payload, ensure_ascii=False))
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde des règles générales de sécurité : {e}")
        return False


def get_bv_referents_safety_rules():
    """
    Retourne les règles de sécurité spécifiques liées à la présence de référents BV (FR / EN).
    Lit la configuration personnalisée dans AppSetting ("bv_referents_safety_rules") ou la dotation initiale.
    """
    try:
        custom_raw = AppSetting.get("bv_referents_safety_rules", None)
        if custom_raw is not None and str(custom_raw).strip() != "":
            if isinstance(custom_raw, str):
                custom_dict = json.loads(custom_raw)
            elif isinstance(custom_raw, dict):
                custom_dict = custom_raw
            else:
                custom_dict = {}

            if isinstance(custom_dict, dict) and ("rules_fr" in custom_dict or "rules_en" in custom_dict):
                rules_fr, rules_en = normalize_rule_pairs(
                    custom_dict.get("rules_fr"), custom_dict.get("rules_en"))
                # Les consignes enregistrées avec l'ancien nom sont présentées (et réenregistrées) avec le nouveau
                return {
                    "rules_fr": _migrate_legacy_placeholders(rules_fr),
                    "rules_en": _migrate_legacy_placeholders(rules_en),
                }
    except Exception as e:
        logger.warning(f"Erreur lors de la lecture des règles de sécurité référents BV : {e}")

    return {
        "rules_fr": list(DEFAULT_BV_REFERENTS_SAFETY_RULES["rules_fr"]),
        "rules_en": list(DEFAULT_BV_REFERENTS_SAFETY_RULES["rules_en"]),
    }


def save_bv_referents_safety_rules(rules_fr=None, rules_en=None):
    """
    Enregistre les règles de sécurité spécifiques aux référents BV (FR / EN) dans AppSetting.
    """
    try:
        clean_fr, clean_en = normalize_rule_pairs(rules_fr, rules_en)

        payload = {
            "rules_fr": clean_fr,
            "rules_en": clean_en,
        }
        AppSetting.set("bv_referents_safety_rules", json.dumps(payload, ensure_ascii=False))
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde des règles de sécurité référents BV : {e}")
        return False


def format_technicians_list(tech_input, conjunction="et", lang="fr"):
    """
    Formate élégamment une liste de techniciens avec virgules et conjonction finale.
    Exemples :
      - 1 nom  -> "Maxime Perrard"
      - 2 noms -> "Maxime Perrard et Ewen Gicquel"
      - 3 noms -> "Maxime Perrard, Ewen Gicquel et Simon Maignan"
    """
    if not tech_input:
        return ""
    if isinstance(tech_input, str):
        items = [name.strip() for name in tech_input.split(",") if name.strip()]
    elif isinstance(tech_input, (list, tuple)):
        items = [str(name).strip() for name in tech_input if str(name).strip()]
    else:
        items = [str(tech_input).strip()]

    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        conj = f" {conjunction} "
        return conj.join(items)

    head = ", ".join(items[:-1])
    return f"{head} {conjunction} {items[-1]}"


def format_bv_referents_rules(safety_technicians, rules_dict=None):
    """
    Injecte dynamiquement les noms des techniciens référents dans les règles spécifiques BV.
    Gère les remplacements :
      - {technicians_and} : conjonction "et" (FR) / "and" (EN) avec gestion des virgules > 2
      - {technicians_or}  : disjonction "ou" (FR) / "or" (EN) avec gestion des virgules > 2
      - {technicians}     : ancien nom de {technicians_and}, toujours accepté
    """
    if not safety_technicians:
        return {"rules_fr": [], "rules_en": []}

    rules = rules_dict or get_bv_referents_safety_rules()
    names_fr_and = format_technicians_list(safety_technicians, conjunction="et", lang="fr")
    names_fr_or = format_technicians_list(safety_technicians, conjunction="ou", lang="fr")
    names_en_and = format_technicians_list(safety_technicians, conjunction="and", lang="en")
    names_en_or = format_technicians_list(safety_technicians, conjunction="or", lang="en")

    def _fill(rule, names_and, names_or):
        return (
            str(rule)
            .replace(TECHNICIANS_AND_PLACEHOLDER, names_and)
            .replace(TECHNICIANS_OR_PLACEHOLDER, names_or)
            .replace(LEGACY_TECHNICIANS_PLACEHOLDER, names_and)
        )

    formatted_fr = [_fill(r, names_fr_and, names_fr_or) for r in (rules.get("rules_fr") or [])]
    formatted_en = [_fill(r, names_en_and, names_en_or) for r in (rules.get("rules_en") or [])]

    return {
        "rules_fr": formatted_fr,
        "rules_en": formatted_en,
    }


def get_merged_general_safety_rules(safety_technicians=None):
    """
    Retourne l'ensemble des règles de la Section 1 (Règles Générales).
    Si safety_technicians est non vide, concatène automatiquement les règles référents BV
    formatées à la suite des règles générales universelles.
    """
    general = get_general_safety_rules()
    rules_fr = list(general.get("rules_fr") or [])
    rules_en = list(general.get("rules_en") or [])

    tech_names = safety_technicians.strip() if safety_technicians and str(safety_technicians).strip() else None
    if tech_names:
        bv_rules = format_bv_referents_rules(tech_names)
        rules_fr.extend(bv_rules.get("rules_fr") or [])
        rules_en.extend(bv_rules.get("rules_en") or [])

    return {
        "rules_fr": rules_fr,
        "rules_en": rules_en,
    }


