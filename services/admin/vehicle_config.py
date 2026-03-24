from extensions import cache
from models import VehicleCheckpointConfig, db
from utils.checkpoints import ALL_POSSIBLE_CHECKPOINTS
from utils.database import get_vehicles


def get_checkpoint_configs():
    """Récupère toutes les configurations de points de contrôle des véhicules avec mise en cache."""
    configs = cache.get('checkpoint_configs')
    if configs is not None:
        return configs

    # Récupération en base de données
    records = VehicleCheckpointConfig.query.all()
    configs = {c.vehicle_id: c.config for c in records}

    cache.set('checkpoint_configs', configs, timeout=3600)

    return configs


def get_vehicles_with_config():
    """Récupère tous les véhicules et leur configuration actuelle de points de contrôle."""
    vehicles = get_vehicles()
    # Récupère toutes les configurations via l'aide avec cache
    local_configs = get_checkpoint_configs()

    results = []
    for v in vehicles:
        record_id = v['id']
        name = v['fields'].get('name', 'Unknown')

        # Si aucune config en base, utilise le fallback hérité comme état initial
        # Tente d'abord l'ID, puis le nom pour les configs existantes
        current_config = local_configs.get(
            record_id) or local_configs.get(name)

        if not current_config:
            # Par défaut, aucun point de contrôle n'est activé si non configuré
            current_config = {
                cp['key']: False for cp in ALL_POSSIBLE_CHECKPOINTS}

        results.append({
            'id': record_id,
            'name': name,
            'config': current_config
        })

    return results


def save_vehicle_checkpoint_config(vehicle_id, enabled_keys):
    """Enregistre les points de contrôle activés pour un véhicule spécifique."""
    # Construit le dictionnaire de configuration complet
    full_config = {cp['key']: (cp['key'] in enabled_keys)
                   for cp in ALL_POSSIBLE_CHECKPOINTS}

    config_record = VehicleCheckpointConfig.query.filter_by(
        vehicle_id=vehicle_id).first()
    if config_record:
        config_record.config = full_config
    else:
        config_record = VehicleCheckpointConfig(
            vehicle_id=vehicle_id,
            config=full_config
        )
        db.session.add(config_record)

    db.session.commit()
    cache.delete('checkpoint_configs')
    return True
