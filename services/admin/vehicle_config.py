import logging
from extensions import cache
from models import VehicleCheckpointConfig, CheckpointDefinition, db
from sqlalchemy import case
from sqlalchemy.orm.attributes import flag_modified
from utils.database import get_vehicles
from services.admin.utils import handle_admin_service_error

logger = logging.getLogger(__name__)

# Graines initiales par défaut lors de la toute première création d'une base de données vierge
DEFAULT_CHECKPOINT_SEEDS = [
    # SÉCURITÉ
    {'key': 'tires', 'label': 'Pression des pneus', 'category': 'Sécurité', 'type': 'status',
     'detail': 'eTrike/eTrike 360 : 3 bar · eBike : voir flanc pneu · eCar : 2 bar', 'has_protocol': True, 'protocol_url': '/admin/check-vehicles'},
    {'key': 'brakes', 'label': 'Contrôle des freins', 'category': 'Sécurité', 'type': 'status',
     'detail': 'Voir protocole freins complet', 'has_protocol': True, 'protocol_url': '/admin/check-vehicles'},
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
     'detail': 'eBike : 45 Nm · eCar : 45 Nm'},
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
     'detail': 'eTrike : casques passagers homologués (tailles S à XL)'},
    {'key': 'protections_pilote', 'label': 'Protections pilote', 'category': 'Équipements', 'type': 'status',
     'detail': 'Casque, combi, gants, bottes, jeans, veste, masque'},
    {'key': 'systeme_communication', 'label': 'Système de communication', 'category': 'Équipements', 'type': 'status',
     'detail': 'Intercom pilote / cadreur opérationnel (casques & boîtiers chargés)'},
    {'key': 'mallette_accessoires', 'label': 'Mallette / Roulante accessoires', 'category': 'Équipements', 'type': 'status',
     'detail': 'eTrike/eTrike 360 : chambre à air ×2, chargeur, pompe, outils · eBike & eCar : pièces de rechange, outils, bijouterie, chargeur'},
]

DEFAULT_SPECIFIC_DETAILS = {
    "eCar": [
        ("tires", "eCar : 2 bar"),
        ("serrage_roues", "eCar : 110 Nm"),
        ("serrage_arceau", "eCar : 45 Nm"),
        ("mallette_accessoires", "eCar : pièces de rechange, outils, bijouterie, chargeur"),
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
        ("mallette_accessoires", "eBike : pièces de rechange, outils, bijouterie, chargeur"),
    ],
}


def ensure_default_checkpoints():
    """Initialise automatiquement les définitions de checkpoints en base de données si la table est vide."""
    try:
        if CheckpointDefinition.query.count() > 0:
            return

        logger.info("🔧 Initialisation par défaut des CheckpointDefinition en base de données...")
        vehicles = get_vehicles()
        existing_configs = {c.vehicle_id: c.config for c in VehicleCheckpointConfig.query.all()}

        for idx, cp in enumerate(DEFAULT_CHECKPOINT_SEEDS):
            key = cp["key"]
            label = cp["label"]
            category = cp.get("category", "Sécurité")
            cp_type = cp.get("type", "status")
            unit = cp.get("unit")
            default_detail = cp.get("detail", "")

            # Construire les indications et activations initiales par véhicule
            vehicle_overrides = {}
            for v in vehicles:
                v_id = v["id"]
                v_name = v["fields"].get("name", "")

                # Vérifier si ce checkpoint était activé dans VehicleCheckpointConfig
                v_cfg = existing_configs.get(v_id) or existing_configs.get(v_name) or {}
                # Si non configuré, activer par défaut pour Sécurité ou selon historique
                enabled = v_cfg.get(key, True if category == "Sécurité" else False)

                # Vérifier si une indication spécifique existait dans DEFAULT_SPECIFIC_DETAILS
                specific_ind = ""
                for v_type, s_list in DEFAULT_SPECIFIC_DETAILS.items():
                    if v_type.lower() in v_name.lower():
                        for item in s_list:
                            if item[0] == key:
                                specific_ind = item[1]
                                break
                        if specific_ind:
                            break

                vehicle_overrides[v_id] = {
                    "enabled": bool(enabled),
                    "indication": specific_ind if specific_ind else ""
                }

            new_def = CheckpointDefinition(
                key=key,
                label=label,
                category=category,
                type=cp_type,
                unit=unit,
                has_protocol=bool(cp.get("has_protocol", False)),
                protocol_url=cp.get("protocol_url", None),
                default_detail=default_detail,
                order=idx,
                vehicle_overrides=vehicle_overrides
            )
            db.session.add(new_def)

        db.session.commit()
        cache.delete("checkpoint_definitions_all")
        logger.info("✅ CheckpointDefinition initialisés avec succès.")
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erreur lors de l'initialisation des CheckpointDefinition : {e}")


def get_all_checkpoints():
    """Récupère toutes les définitions de points de contrôle triées avec informations enrichies."""
    ensure_default_checkpoints()

    cached_list = cache.get("checkpoint_definitions_all")
    if cached_list is not None:
        return cached_list

    category_priority = case(
        (CheckpointDefinition.category == "Sécurité", 0),
        (CheckpointDefinition.category == "Équipements", 1),
        else_=2
    )
    checkpoints = CheckpointDefinition.query.order_by(
        category_priority, CheckpointDefinition.order, CheckpointDefinition.id
    ).all()
    vehicles = get_vehicles()
    v_map = {v["id"]: v["fields"].get("name", "Véhicule") for v in vehicles}

    results = []
    for cp in checkpoints:
        overrides = cp.vehicle_overrides or {}
        enabled_vehicles = []
        for v_id, v_name in v_map.items():
            ov = overrides.get(v_id) or {}
            if ov.get("enabled"):
                enabled_vehicles.append({
                    "id": v_id,
                    "name": v_name,
                    "indication": ov.get("indication", "")
                })

        has_protocol_val = cp.has_protocol_available() if hasattr(cp, "has_protocol_available") else bool(getattr(cp, "has_protocol", False) or cp.key in ("tires", "brakes"))
        protocol_url_val = getattr(cp, "protocol_url", "") or ""

        results.append({
            "id": cp.id,
            "key": cp.key,
            "label": cp.label,
            "category": cp.category,
            "type": cp.type,
            "unit": cp.unit,
            "has_protocol": has_protocol_val,
            "protocol_url": protocol_url_val,
            "default_detail": cp.default_detail,
            "detail": cp.default_detail,
            "order": cp.order,
            "vehicle_overrides": overrides,
            "enabled_vehicles": enabled_vehicles,
            "enabled_count": len(enabled_vehicles),
            "total_vehicles": len(vehicles)
        })

    cache.set("checkpoint_definitions_all", results, timeout=3600)
    return results


def get_checkpoint_by_id(checkpoint_id: int):
    """Récupère un point de contrôle par son ID avec les détails de tous les véhicules."""
    ensure_default_checkpoints()
    cp = CheckpointDefinition.query.get(checkpoint_id)
    if not cp:
        return None

    vehicles = get_vehicles()
    overrides = cp.vehicle_overrides or {}

    vehicles_config = []
    for v in vehicles:
        v_id = v["id"]
        v_name = v["fields"].get("name", "Véhicule")
        ov = overrides.get(v_id) or {}
        vehicles_config.append({
            "id": v_id,
            "name": v_name,
            "enabled": bool(ov.get("enabled", False)),
            "indication": ov.get("indication", "")
        })

    return {
        "id": cp.id,
        "key": cp.key,
        "label": cp.label,
        "category": cp.category,
        "type": cp.type,
        "unit": cp.unit,
        "has_protocol": cp.has_protocol_available() if hasattr(cp, "has_protocol_available") else bool(getattr(cp, "has_protocol", False) or cp.key in ("tires", "brakes")),
        "protocol_url": getattr(cp, "protocol_url", "") or "",
        "default_detail": cp.default_detail,
        "order": cp.order,
        "vehicles": vehicles_config
    }


import re
import unicodedata


def _slugify(text: str) -> str:
    """Génère un identifiant slug propre à partir d'une chaîne."""
    if not text:
        return "checkpoint"
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    slug = re.sub(r"[-\s]+", "_", text)
    return slug or "checkpoint"


def get_empty_checkpoint_for_create():
    """Prépare un objet checkpoint vierge avec tous les véhicules de la flotte pour le formulaire de création."""
    ensure_default_checkpoints()
    vehicles = get_vehicles()
    vehicles_config = []
    for v in vehicles:
        v_id = v["id"]
        v_name = v["fields"].get("name", "Véhicule")
        vehicles_config.append({
            "id": v_id,
            "name": v_name,
            "enabled": True,
            "indication": ""
        })

    return {
        "id": None,
        "key": "",
        "label": "",
        "category": "Sécurité",
        "type": "status",
        "unit": "",
        "has_protocol": False,
        "protocol_url": "",
        "default_detail": "",
        "order": 0,
        "vehicles": vehicles_config
    }


@handle_admin_service_error
def create_checkpoint(form_data: dict):
    """Crée un nouveau point de contrôle avec ses configurations par véhicule."""
    ensure_default_checkpoints()
    label = form_data.get("label", "").strip()
    if not label:
        return None

    key = _slugify(label)

    # Assurer l'unicité de la clé
    base_key = key
    counter = 1
    while CheckpointDefinition.query.filter_by(key=key).first() is not None:
        key = f"{base_key}_{counter}"
        counter += 1

    category = form_data.get("category", "Sécurité").strip()
    if category not in ("Sécurité", "Équipements"):
        category = "Sécurité"

    default_detail = form_data.get("default_detail", "").strip()

    # Ordre d'affichage : manuel si renseigné, sinon fin de liste
    order_val = form_data.get("order")
    if order_val is not None and str(order_val).strip().isdigit():
        order = int(order_val)
    else:
        max_order = db.session.query(db.func.max(CheckpointDefinition.order)).scalar()
        order = (max_order + 1) if max_order is not None else 0

    # Véhicules
    vehicles = get_vehicles()
    vehicle_overrides = {}
    for v in vehicles:
        v_id = v["id"]
        is_enabled = bool(form_data.get(f"vehicle_enabled_{v_id}"))
        indication = form_data.get(f"vehicle_indication_{v_id}", "").strip()
        vehicle_overrides[v_id] = {
            "enabled": is_enabled,
            "indication": indication
        }

        # Synchroniser la table matrice VehicleCheckpointConfig
        v_rec = VehicleCheckpointConfig.query.filter_by(vehicle_id=v_id).first()
        if v_rec:
            cfg = dict(v_rec.config or {})
            cfg[key] = is_enabled
            v_rec.config = cfg
            flag_modified(v_rec, "config")
        else:
            v_rec = VehicleCheckpointConfig(vehicle_id=v_id, config={key: is_enabled})
            db.session.add(v_rec)

    cp_type = form_data.get("type", "status").strip()
    if cp_type not in ("status", "value"):
        cp_type = "status"
    unit = form_data.get("unit", "").strip() or None
    if cp_type != "value":
        unit = None
    has_protocol = bool(form_data.get("has_protocol"))
    protocol_url = form_data.get("protocol_url", "").strip() or None

    new_cp = CheckpointDefinition(
        key=key,
        label=label,
        category=category,
        type=cp_type,
        unit=unit,
        has_protocol=has_protocol,
        protocol_url=protocol_url,
        default_detail=default_detail,
        order=order,
        vehicle_overrides=vehicle_overrides
    )
    db.session.add(new_cp)
    db.session.commit()

    cache.delete("checkpoint_definitions_all")
    cache.delete("checkpoint_configs")
    return new_cp


@handle_admin_service_error
def update_checkpoint(checkpoint_id: int, form_data: dict) -> bool:
    """Met à jour un point de contrôle : nom, catégorie, ordre, indication par défaut et véhicules concernés avec indications."""
    cp = CheckpointDefinition.query.get(checkpoint_id)
    if not cp:
        return False

    # 1. Mise à jour des informations générales
    label = form_data.get("label", "").strip()
    if label:
        cp.label = label
    
    category = form_data.get("category", "").strip()
    if category in ("Sécurité", "Équipements"):
        cp.category = category

    cp_type = form_data.get("type", "").strip()
    if cp_type in ("status", "value"):
        cp.type = cp_type

    unit_val = form_data.get("unit")
    if unit_val is not None:
        cp.unit = unit_val.strip() or None

    if cp.type != "value":
        cp.unit = None

    cp.has_protocol = bool(form_data.get("has_protocol"))

    protocol_url_val = form_data.get("protocol_url")
    if protocol_url_val is not None:
        cp.protocol_url = protocol_url_val.strip() or None

    default_detail = form_data.get("default_detail", "").strip()
    cp.default_detail = default_detail

    order_val = form_data.get("order")
    if order_val is not None and str(order_val).strip().isdigit():
        cp.order = int(order_val)

    # 2. Mise à jour des véhicules concernés et indications spécifiques
    vehicles = get_vehicles()
    current_overrides = dict(cp.vehicle_overrides or {})

    for v in vehicles:
        v_id = v["id"]
        # Récupérer activation et indication depuis le formulaire
        is_enabled = bool(form_data.get(f"vehicle_enabled_{v_id}"))
        indication = form_data.get(f"vehicle_indication_{v_id}", "").strip()

        current_overrides[v_id] = {
            "enabled": is_enabled,
            "indication": indication
        }

        # Synchroniser la table matrice VehicleCheckpointConfig
        v_rec = VehicleCheckpointConfig.query.filter_by(vehicle_id=v_id).first()
        if v_rec:
            cfg = dict(v_rec.config or {})
            cfg[cp.key] = is_enabled
            v_rec.config = cfg
            flag_modified(v_rec, "config")
        else:
            v_rec = VehicleCheckpointConfig(
                vehicle_id=v_id,
                config={cp.key: is_enabled}
            )
            db.session.add(v_rec)

    cp.vehicle_overrides = current_overrides
    flag_modified(cp, "vehicle_overrides")
    db.session.commit()

    # Invalidation des caches
    cache.delete("checkpoint_definitions_all")
    cache.delete("checkpoint_configs")
    return True


@handle_admin_service_error
def reorder_checkpoints(ordered_ids: list) -> bool:
    """Met à jour l'ordre d'affichage des points de contrôle d'après la liste ordonnée de leurs IDs."""
    try:
        for index, cp_id in enumerate(ordered_ids, start=1):
            cp = CheckpointDefinition.query.get(int(cp_id))
            if cp:
                cp.order = index
        db.session.commit()
        cache.delete("checkpoint_definitions_all")
        cache.delete("checkpoint_configs")
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erreur lors du réordonnancement des checkpoints : {e}", exc_info=True)
        return False


@handle_admin_service_error
def delete_checkpoint(checkpoint_id: int) -> tuple[bool, str]:
    """Supprime un point de contrôle et nettoie les configurations associées."""
    try:
        cp = CheckpointDefinition.query.get(checkpoint_id)
        if not cp:
            return False, "Point de contrôle introuvable."
        
        cp_key = cp.key
        cp_label = cp.label

        # Nettoyer la clé dans la table matrice VehicleCheckpointConfig de chaque véhicule
        v_configs = VehicleCheckpointConfig.query.all()
        for vc in v_configs:
            if vc.config and cp_key in vc.config:
                cfg = dict(vc.config)
                del cfg[cp_key]
                vc.config = cfg
                flag_modified(vc, "config")

        # 1. Supprimer le point de contrôle et invalider les caches
        db.session.delete(cp)
        db.session.commit()

        cache.delete("checkpoint_definitions_all")
        cache.delete("checkpoint_configs")

        # 2. Nettoyer les évaluations orphelines dans les inspections non scellées (in_progress)
        try:
            from models import InspectionCheckpoint, CheckoutVehicle, CheckinVehicle
            from services.admin.utils import _is_ready

            in_progress_checkouts = CheckoutVehicle.query.filter_by(status='in_progress').all()
            for co in in_progress_checkouts:
                InspectionCheckpoint.query.filter_by(checkout_id=co.id, checkpoint_key=cp_key).delete()
                db.session.expire(co, ['checkpoints'])
                statuses = co.checkpoint_statuses
                co.vehicle_ready = _is_ready(statuses, co.vehicle_id, is_checkout=True, battery_val=co.battery_level)

            in_progress_checkins = CheckinVehicle.query.filter_by(status='in_progress').all()
            for ci in in_progress_checkins:
                InspectionCheckpoint.query.filter_by(checkin_id=ci.id, checkpoint_key=cp_key).delete()
                db.session.expire(ci, ['checkpoints'])
                statuses = ci.checkpoint_statuses
                ci.vehicle_ready = _is_ready(statuses, ci.vehicle_id, is_checkout=False, battery_val=ci.battery_level)

            db.session.commit()
        except Exception as e_clean:
            logger.warning(f"⚠️ Nettoyage partiel des inspections lors de la suppression de {cp_key}: {e_clean}")

        return True, f"Point de contrôle « {cp_label} » supprimé avec succès."
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erreur lors de la suppression du point de contrôle {checkpoint_id} : {e}", exc_info=True)
        return False, f"Erreur lors de la suppression : {e}"


def get_checkpoint_configs():
    """Récupère toutes les configurations de points de contrôle des véhicules avec mise en cache."""
    configs = cache.get("checkpoint_configs")
    if configs is not None:
        return configs

    # Récupération en base de données
    records = VehicleCheckpointConfig.query.all()
    configs = {c.vehicle_id: c.config for c in records}

    cache.set("checkpoint_configs", configs, timeout=3600)
    return configs


def get_vehicles_with_config():
    """Récupère tous les véhicules et leur configuration actuelle de points de contrôle pour la vue matrice."""
    ensure_default_checkpoints()
    vehicles = get_vehicles()
    local_configs = get_checkpoint_configs()
    category_priority = case(
        (CheckpointDefinition.category == "Sécurité", 0),
        (CheckpointDefinition.category == "Équipements", 1),
        else_=2
    )
    all_cps = CheckpointDefinition.query.order_by(
        category_priority, CheckpointDefinition.order, CheckpointDefinition.id
    ).all()

    results = []
    for v in vehicles:
        record_id = v["id"]
        name = v["fields"].get("name", "Unknown")

        current_config = local_configs.get(record_id) or local_configs.get(name)
        if not current_config:
            current_config = {cp.key: False for cp in all_cps}

        results.append({
            "id": record_id,
            "name": name,
            "config": current_config
        })

    return results


@handle_admin_service_error
def save_vehicle_checkpoint_config(vehicle_id, enabled_keys):
    """Enregistre les points de contrôle activés pour un véhicule spécifique depuis la vue matrice."""
    ensure_default_checkpoints()
    all_cps = CheckpointDefinition.query.all()
    full_config = {cp.key: (cp.key in enabled_keys) for cp in all_cps}

    config_record = VehicleCheckpointConfig.query.filter_by(vehicle_id=vehicle_id).first()
    if config_record:
        config_record.config = full_config
    else:
        config_record = VehicleCheckpointConfig(
            vehicle_id=vehicle_id,
            config=full_config
        )
        db.session.add(config_record)

    # Répercuter sur CheckpointDefinition.vehicle_overrides
    for cp in all_cps:
        ov = dict(cp.vehicle_overrides or {})
        v_data = dict(ov.get(vehicle_id, {}))
        v_data["enabled"] = bool(cp.key in enabled_keys)
        ov[vehicle_id] = v_data
        cp.vehicle_overrides = ov
        flag_modified(cp, "vehicle_overrides")

    if config_record:
        flag_modified(config_record, "config")

    db.session.commit()
    cache.delete("checkpoint_definitions_all")
    cache.delete("checkpoint_configs")
    return True
