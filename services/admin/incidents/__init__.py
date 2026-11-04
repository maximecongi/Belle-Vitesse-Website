"""
Package modulaire de gestion des incidents de tournage Belle Vitesse.
Re-exporte l'ensemble des constantes, fonctions CRUD, médias, signatures et génération PDF
pour assurer une compatibilité ascendante totale (100% transparent).
"""

from services.admin.incidents.constants import (
    INCIDENT_CATEGORY_MAP,
    INCIDENT_IMPACT_LUCIDE_ICONS,
    INCIDENT_IMPACT_MAP,
    INCIDENT_SEVERITY_LUCIDE_ICONS,
    INCIDENT_SEVERITY_MAP,
    INCIDENT_STATUS_BADGE_VALS,
    INCIDENT_STATUS_ICONS,
    INCIDENT_STATUS_LUCIDE_ICONS,
    INCIDENT_STATUS_MAP,
)
from services.admin.incidents.crud import (
    _clean_str,
    _format_date,
    _parse_date,
    _parse_time,
    create_incident,
    delete_incident,
    get_incident_detail,
    get_incident_filter_options,
    get_incident_form_context,
    list_incidents,
    resolve_incident_equipments,
    update_incident,
    update_incident_status,
)
from services.admin.incidents.media import (
    _save_uploaded_files,
)
from services.admin.incidents.pdf import (
    generate_incident_pdf,
)
from services.admin.incidents.signatures import (
    finalize_incident_document,
    generate_incident_token,
    sign_incident_bv,
    sign_incident_prod,
    validate_incident_token,
)

__all__ = [
    # Constantes & Mappings
    "INCIDENT_CATEGORY_MAP",
    "INCIDENT_SEVERITY_MAP",
    "INCIDENT_STATUS_MAP",
    "INCIDENT_STATUS_ICONS",
    "INCIDENT_STATUS_LUCIDE_ICONS",
    "INCIDENT_SEVERITY_LUCIDE_ICONS",
    "INCIDENT_IMPACT_LUCIDE_ICONS",
    "INCIDENT_STATUS_BADGE_VALS",
    "INCIDENT_IMPACT_MAP",
    # Helpers
    "_clean_str",
    "_parse_date",
    "_parse_time",
    "_format_date",
    # CRUD & Requetage
    "list_incidents",
    "get_incident_filter_options",
    "resolve_incident_equipments",
    "get_incident_detail",
    "create_incident",
    "update_incident",
    "update_incident_status",
    "delete_incident",
    "get_incident_form_context",
    # Médias
    "_save_uploaded_files",
    # Signatures
    "sign_incident_bv",
    "sign_incident_prod",
    "generate_incident_token",
    "validate_incident_token",
    "finalize_incident_document",
    # PDF
    "generate_incident_pdf",
]

