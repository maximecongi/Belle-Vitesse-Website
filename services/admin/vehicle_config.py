from models import db, VehicleCheckpointConfig
from utils.airtable import get_vehicles
from utils.checkpoints import LEGACY_CHECKPOINTS_CONFIG, ALL_POSSIBLE_CHECKPOINTS


def get_vehicles_with_config():
    """Fetch all vehicles and their current checkpoint configuration."""
    vehicles = get_vehicles()
    # Get all local configs
    local_configs = {
        c.vehicle_id: c.config for c in VehicleCheckpointConfig.query.all()}

    results = []
    for v in vehicles:
        record_id = v['id']
        name = v['fields'].get('name', 'Unknown')

        # If no config in DB, use legacy fallback as initial state for UI
        # Try Record ID first, then Name for existing configs
        current_config = local_configs.get(
            record_id) or local_configs.get(name)

        if not current_config:
            # Fallback logic to show what's currently active via legacy rules
            enabled_keys = []
            for key, keys in LEGACY_CHECKPOINTS_CONFIG.items():
                if key.lower() in name.lower():
                    enabled_keys = keys
                    break

            current_config = {cp['key']: (cp['key'] in enabled_keys)
                              for cp in ALL_POSSIBLE_CHECKPOINTS}

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
    return True
