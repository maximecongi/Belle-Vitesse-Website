import logging
import json
from models import AppSetting

logger = logging.getLogger(__name__)

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
    },
}

DEFAULT_HELMETS_INVENTORY = {
    "total": 6,
    "description_fr": "6 casques jet ouverts : 1 Small, 2 Medium, 2 Large, 1 XLarge",
    "description_en": "6 open face jet helmets : 1 Small, 2 Medium, 2 Large, 1 XLarge",
    "sizes": {"Small": 1, "Medium": 2, "Large": 2, "XLarge": 1},
}


def _extract_vehicle_image(fields):
    """Extrait l'image principale ou retourne le placeholder par défaut."""
    if not fields or not isinstance(fields, dict):
        return "/static/imgs/placeholders/vehicle.svg"
    thumb = fields.get("thumbnail")
    if isinstance(thumb, list) and len(thumb) > 0 and isinstance(thumb[0], dict):
        thumbnails = thumb[0].get("thumbnails", {})
        if isinstance(thumbnails, dict):
            large = thumbnails.get("large", {}).get("url")
            if large:
                return large
            full = thumbnails.get("full", {}).get("url")
            if full:
                return full
        url = thumb[0].get("url")
        if url:
            return url
    banner = fields.get("banner")
    if isinstance(banner, list) and len(banner) > 0 and isinstance(banner[0], dict):
        url = banner[0].get("url")
        if url:
            return url
    return "/static/imgs/placeholders/vehicle.svg"


def _find_default_rules(name):
    """Associe des règles par défaut cohérentes en fonction du nom du véhicule."""
    query = (name or "").lower().strip()
    for key, data in DEFAULT_VEHICLE_SAFETY_RULES.items():
        if key in query:
            return list(data.get("rules_fr") or []), list(data.get("rules_en") or []), data.get("label") or name
        for kw in data.get("keywords") or []:
            if kw in query:
                return list(data.get("rules_fr") or []), list(data.get("rules_en") or []), data.get("label") or name
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
    )


def get_all_vehicle_safety_rules_catalog():
    """
    Retourne le catalogue des règles de sécurité pour chaque véhicule réel de la flotte,
    en combinant les règles par défaut et les personnalisations enregistrées.
    """
    catalog = {}
    custom_dict = {}
    try:
        custom_raw = AppSetting.get("fleet_safety_rules", None)
        if custom_raw:
            if isinstance(custom_raw, str):
                custom_dict = json.loads(custom_raw)
            elif isinstance(custom_raw, dict):
                custom_dict = custom_raw
    except Exception as e:
        logger.warning(f"Erreur lors de la lecture des règles de sécurité de flotte : {e}")

    # Récupération des véhicules réels de la flotte
    fleet_vehicles = []
    try:
        from utils.database import get_vehicles
        fleet_vehicles = get_vehicles() or []
    except Exception as e:
        logger.warning(f"Impossible de charger les véhicules via get_vehicles : {e}")

    # Si aucun véhicule retourné (ex: test unitaire isolé sans sync), tente via Vehicle.query
    if not fleet_vehicles:
        try:
            from models.catalog import Vehicle
            db_vehs = Vehicle.query.all()
            for v in db_vehs:
                fleet_vehicles.append({
                    "id": v.id,
                    "fields": v.fields or {}
                })
        except Exception:
            pass

    # Si des véhicules existent dans la flotte
    if fleet_vehicles:
        for veh in fleet_vehicles:
            vid = str(veh.get("id") or "").strip()
            fields = veh.get("fields") or {}
            vname = fields.get("Nom") or fields.get("name") or f"Véhicule {vid}"
            vimg = _extract_vehicle_image(fields)

            def_fr, def_en, def_lbl = _find_default_rules(vname)

            # Recherche d'une personnalisation (par id, ou fallback par nom)
            custom_entry = custom_dict.get(vid)
            if not custom_entry:
                for ckey, cval in custom_dict.items():
                    if ckey.lower() == vname.lower() or ckey.lower() in vname.lower():
                        custom_entry = cval
                        break

            if custom_entry and isinstance(custom_entry, dict):
                label = custom_entry.get("label") or def_lbl
                rules_fr = custom_entry.get("rules_fr", def_fr)
                rules_en = custom_entry.get("rules_en", def_en)
            else:
                label = def_lbl
                rules_fr = def_fr
                rules_en = def_en

            catalog[vid] = {
                "id": vid,
                "name": vname,
                "image": vimg,
                "label": label,
                "rules_fr": rules_fr if isinstance(rules_fr, list) else [r.strip() for r in str(rules_fr).split("\n") if r.strip()],
                "rules_en": rules_en if isinstance(rules_en, list) else [r.strip() for r in str(rules_en).split("\n") if r.strip()],
            }
    else:
        # Fallback de secours (tests unitaires sans BDD de flotte)
        for key, data in DEFAULT_VEHICLE_SAFETY_RULES.items():
            custom_entry = custom_dict.get(key, {})
            label = custom_entry.get("label") or data.get("label") or key.capitalize()
            rules_fr = custom_entry.get("rules_fr", data.get("rules_fr", []))
            rules_en = custom_entry.get("rules_en", data.get("rules_en", []))
            catalog[key] = {
                "id": key,
                "name": label,
                "image": "/static/imgs/placeholders/vehicle.svg",
                "label": label,
                "rules_fr": rules_fr if isinstance(rules_fr, list) else [r.strip() for r in str(rules_fr).split("\n") if r.strip()],
                "rules_en": rules_en if isinstance(rules_en, list) else [r.strip() for r in str(rules_en).split("\n") if r.strip()],
            }

    # Inclure également les entrées personnalisées enregistrées dans AppSetting non encore dans catalog
    for c_id, c_data in custom_dict.items():
        if c_id not in catalog and isinstance(c_data, dict):
            c_label = c_data.get("label") or c_id
            catalog[c_id] = {
                "id": c_id,
                "name": c_label,
                "image": "/static/imgs/placeholders/vehicle.svg",
                "label": c_label,
                "rules_fr": c_data.get("rules_fr") or [],
                "rules_en": c_data.get("rules_en") or [],
            }

    return catalog


def save_vehicle_safety_rules(vehicle_id=None, rules_fr=None, rules_en=None, label=None, vehicle_key=None, **kwargs):
    """
    Enregistre ou met à jour les règles spécifiques pour un véhicule réel dans la configuration de flotte.
    Accepte vehicle_id ou vehicle_key pour une compatibilité totale.
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
        entry["rules_fr"] = rules_fr if isinstance(rules_fr, list) else [r.strip() for r in str(rules_fr or '').split("\n") if r.strip()]
        entry["rules_en"] = rules_en if isinstance(rules_en, list) else [r.strip() for r in str(rules_en or '').split("\n") if r.strip()]

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
                if (c_id_lower and c_id_lower in vname_lower) or (vslug and vslug in c_id_lower) or (c_name_lower and c_name_lower in vname_lower) or (vname_lower and vname_lower in c_name_lower):
                    entry = c_data
                    break

        if entry:
            label = entry.get("label") or entry.get("name") or vname
            if label not in matched_categories:
                matched_categories[label] = {
                    "label": label,
                    "rules_fr": entry.get("rules_fr") or [],
                    "rules_en": entry.get("rules_en") or [],
                }

    return list(matched_categories.values())
