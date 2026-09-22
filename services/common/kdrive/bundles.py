"""
Module d'extraction et de résolution unifiée des lots de fichiers (bundles) pour kDrive.
Centralise la détection des pièces jointes pour les Décharges, Inspections et Incidents.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _parse_json_list(raw_value: Any) -> List[str]:
    """Parse de manière sécurisée une chaîne JSON ou une liste existante."""
    if not raw_value:
        return []
    if isinstance(raw_value, (list, tuple, set)):
        return [str(item).strip() for item in raw_value if item]
    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if item]
        except Exception:
            pass
    return []


def resolve_entity_info(
    record: Any, mode_or_type: Optional[str] = None
) -> Tuple[str, Optional[str], Optional[int]]:
    """
    Résout de manière polymorphique les informations essentielles d'une entité signée :
    (entity_type, entity_id, project_id)
    """
    # 1. Résolution de l'entity_type
    entity_type = mode_or_type
    class_name = record.__class__.__name__

    if entity_type in ("checkout", "checkin", "incident"):
        pass
    elif entity_type in ("pilot", "pilot_waiver") or class_name == "PilotWaiver":
        entity_type = "pilot_waiver"
    elif entity_type in ("production", "production_waiver") or class_name == "ProductionWaiver":
        entity_type = "production_waiver"
    elif class_name == "CheckoutVehicle":
        entity_type = "checkout"
    elif class_name == "CheckinVehicle":
        entity_type = "checkin"
    elif class_name == "Incident":
        entity_type = "incident"
    else:
        entity_type = str(mode_or_type or "").lower()

    # 2. Résolution de l'entity_id
    entity_id = (
        getattr(record, "inspection_number", None)
        or getattr(record, "waiver_id", None)
        or getattr(record, "incident_number", None)
    )

    # 3. Résolution du project_id
    project_id = getattr(record, "project_id", None)
    if not project_id and getattr(record, "project", None):
        project_id = getattr(record.project, "id", None)

    return entity_type, entity_id, project_id


def extract_bundle_file_specs(
    record: Any,
    entity_type: Optional[str] = None,
    rel_pdf_path: Optional[str] = None,
    custom_pdf_filename: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Construit la liste unifiée des spécifications de fichiers (file_specs) pour kDrive.
    Supporte les inspections (départ/retour), les décharges (pilote/production) et les incidents.
    """
    resolved_type, _, _ = resolve_entity_info(record, entity_type)
    file_specs: List[Dict[str, Any]] = []

    # 1. PDF Principal signé
    pdf_path = rel_pdf_path or getattr(record, "signed_pdf_path", None)
    if pdf_path:
        filename = custom_pdf_filename or os.path.basename(pdf_path)
        file_specs.append({"role": "pdf", "path": pdf_path, "filename": filename})

    # 2. Pièces jointes selon le type d'entité
    if resolved_type in ("checkout", "checkin"):
        for p in _parse_json_list(getattr(record, "interior_photos", None)):
            file_specs.append({"role": "photo", "path": p})
        for p in _parse_json_list(getattr(record, "exterior_photos", None)):
            file_specs.append({"role": "photo", "path": p})

    elif resolved_type == "pilot_waiver":
        license_path = getattr(record, "pilot_license_path", None)
        if license_path:
            file_specs.append({"role": "license", "path": license_path})

        insurance_path = getattr(record, "pilot_insurance_path", None)
        if insurance_path:
            file_specs.append({"role": "insurance", "path": insurance_path})

        identity_path = getattr(record, "pilot_identity_path", None)
        if identity_path:
            file_specs.append({"role": "identity", "path": identity_path})

    elif resolved_type == "production_waiver":
        insurance_path = getattr(record, "production_insurance_path", None)
        if insurance_path:
            file_specs.append({"role": "insurance", "path": insurance_path})

    elif resolved_type == "incident":
        # Photos
        photos = getattr(record, "photos_list", None)
        if photos is None:
            photos = _parse_json_list(getattr(record, "photos", None))
        for p in photos:
            if p:
                file_specs.append({"role": "photo", "path": p})

        # Documents annexes
        docs = getattr(record, "documents_list", None)
        if docs is None:
            docs = _parse_json_list(getattr(record, "documents", None))
        for d in docs:
            if d:
                file_specs.append({"role": "document", "path": d})

    return file_specs
