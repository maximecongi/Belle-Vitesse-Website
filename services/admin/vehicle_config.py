import logging
from extensions import cache
from models import VehicleCheckpointConfig, CheckpointDefinition, db
from sqlalchemy import case
from sqlalchemy.orm.attributes import flag_modified
from utils.checkpoints import ALL_POSSIBLE_CHECKPOINTS, SPECIFIC_DETAILS
from utils.database import get_vehicles

logger = logging.getLogger(__name__)


def ensure_default_checkpoints():
    """Initialise automatiquement les définitions de checkpoints en base de données si la table est vide."""
    try:
        if CheckpointDefinition.query.count() > 0:
            return

        logger.info("🔧 Initialisation par défaut des CheckpointDefinition en base de données...")
        vehicles = get_vehicles()
        existing_configs = {c.vehicle_id: c.config for c in VehicleCheckpointConfig.query.all()}

        for idx, cp in enumerate(ALL_POSSIBLE_CHECKPOINTS):
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

                # Vérifier si une indication spécifique existait dans SPECIFIC_DETAILS
                specific_ind = ""
                for v_type, s_list in SPECIFIC_DETAILS.items():
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

        results.append({
            "id": cp.id,
            "key": cp.key,
            "label": cp.label,
            "category": cp.category,
            "type": cp.type,
            "unit": cp.unit,
            "default_detail": cp.default_detail,
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
        "default_detail": "",
        "order": 0,
        "vehicles": vehicles_config
    }


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

    new_cp = CheckpointDefinition(
        key=key,
        label=label,
        category=category,
        type="status",
        default_detail=default_detail,
        order=order,
        vehicle_overrides=vehicle_overrides
    )
    db.session.add(new_cp)
    db.session.commit()

    cache.delete("checkpoint_definitions_all")
    cache.delete("checkpoint_configs")
    return new_cp


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

        db.session.delete(cp)
        db.session.commit()

        # Invalidation des caches
        cache.delete("checkpoint_definitions_all")
        cache.delete("checkpoint_configs")
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
