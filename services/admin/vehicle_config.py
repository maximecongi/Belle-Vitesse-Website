from extensions import cache
from models import VehicleCheckpointConfig, db
from utils.checkpoints import ALL_POSSIBLE_CHECKPOINTS
from utils.database import get_vehicles


def get_checkpoint_configs():
    """Fetch all vehicle checkpoint configurations with caching."""
    configs = cache.get('checkpoint_configs')
    if configs is not None:
        return configs

    # Fetch from DB
    records = VehicleCheckpointConfig.query.all()
    configs = {c.vehicle_id: c.config for c in records}

    cache.set('checkpoint_configs', configs, timeout=3600)

    return configs


def get_vehicles_with_config():
    """Fetch all vehicles and their current checkpoint configuration."""
    vehicles = get_vehicles()
    # Get all local configs via the cached helper
    local_configs = get_checkpoint_configs()

    results = []
    for v in vehicles:
        record_id = v['id']
        name = v['fields'].get('name', 'Unknown')

        # If no config in DB, use legacy fallback as initial state for UI
        # Try Record ID first, then Name for existing configs
        current_config = local_configs.get(
            record_id) or local_configs.get(name)

        if not current_config:
            # Default to no checkpoints enabled if not configured
            current_config = {
                cp['key']: False for cp in ALL_POSSIBLE_CHECKPOINTS}

        results.append({
            'id': record_id,
            'name': name,
            'config': current_config
        })

    return results


def save_vehicle_checkpoint_config(vehicle_id, enabled_keys):
    """Save the enabled checkpoints for a specific vehicle."""
    # Build the full config dict
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
