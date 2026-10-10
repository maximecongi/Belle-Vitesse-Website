# utils/checkpoints.py
"""
Module de résolution des points de contrôle pour un véhicule donné.
S'appuie exclusivement sur la base de données (CheckpointDefinition via get_all_checkpoints).
"""

from typing import List, Dict, Any, Optional


def get_checkpoints_for_vehicle(vehicle_id: str, batch_configs=None, vehicle_name=None) -> list:
    """
    Retourne la liste des points de contrôle à afficher pour un véhicule donné.
    'vehicle_id' peut être un ID d'enregistrement Airtable ou un Nom de Véhicule.
    'batch_configs' : dict optionnel {vehicle_id: config_dict} pour éviter les requêtes N+1.
    """
    if not vehicle_id:
        return []

    from flask import current_app, has_app_context

    # Résoudre le nom de véhicule si non fourni
    if not vehicle_name:
        vehicle_name = vehicle_id

    if has_app_context():
        try:
            from services.admin.vehicle_config import get_all_checkpoints
            from utils.database import get_vehicles

            # Résoudre ID <-> Nom du véhicule pour la recherche des surcharges
            vehicles = get_vehicles()
            v_id_to_name = {v['id']: v.get('fields', {}).get('name', '') for v in vehicles}
            v_name_to_id = {v.get('fields', {}).get('name', ''): v['id'] for v in vehicles}

            v_id = vehicle_id
            v_name = vehicle_name
            if vehicle_id in v_id_to_name and vehicle_name == vehicle_id:
                v_name = v_id_to_name[vehicle_id]
            elif vehicle_id in v_name_to_id:
                v_id = v_name_to_id[vehicle_id]
                v_name = vehicle_id

            all_cps = get_all_checkpoints()
            if all_cps:
                resolved = []
                for cp in all_cps:
                    overrides = cp.get('vehicle_overrides') or {}

                    # Déterminer si le point de contrôle est actif pour ce véhicule
                    is_enabled = False
                    if batch_configs and (v_id in batch_configs or v_name in batch_configs):
                        cfg = batch_configs.get(v_id) or batch_configs.get(v_name) or {}
                        if isinstance(cfg, dict):
                            is_enabled = bool(cfg.get(cp['key']))
                        elif isinstance(cfg, (list, set)):
                            is_enabled = cp['key'] in cfg
                    else:
                        if (v_id and v_id in overrides) or (v_name and v_name in overrides):
                            v_ov = overrides.get(v_id) or overrides.get(v_name) or {}
                            is_enabled = bool(v_ov.get('enabled', False))
                        else:
                            is_enabled = (cp.get('category') == 'Sécurité')

                    if is_enabled:
                        # Déterminer l'indication spécifique au véhicule ou le détail par défaut
                        indication = ""
                        v_ov = overrides.get(v_id) or overrides.get(v_name) or {}
                        if v_ov.get('indication'):
                            indication = v_ov['indication'].strip()
                        elif cp.get('default_detail'):
                            indication = cp['default_detail'].strip()

                        item = {
                            'key': cp['key'],
                            'label': cp['label'],
                            'category': cp.get('category', 'Sécurité'),
                            'type': cp.get('type', 'status'),
                            'detail': indication,
                            'has_protocol': bool(cp.get('has_protocol') or cp['key'] in ('tires', 'brakes')),
                            'protocol_url': cp.get('protocol_url') or ('/admin/check-vehicles' if (cp.get('has_protocol') or cp['key'] in ('tires', 'brakes')) else ''),
                        }
                        if cp.get('unit'):
                            item['unit'] = cp['unit']
                        resolved.append(item)

                return resolved
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error fetching vehicle checkpoints from DB: {e}")

    return []
