"""
Centralized status mapping and formatting for the admin section.
Handles labels for Waivers and Inspections (Check-ins/Check-outs).
"""

# ── Waivers Mapping ──────────────────────────────────────────────

WAIVER_STATUS_MAP = {
    "to_generate": "À générer",
    "to_send": "À envoyer",
    "to_sign": "À signer",
    "signed": "Signé",
}


def format_waiver_status(status_id):
    """
    Map an internal waiver status identifier to its French label.
    """
    return WAIVER_STATUS_MAP.get(status_id, status_id)


# ── Inspections Mapping ──────────────────────────────────────────

# DB values for inspections (legacy French strings)
INSPECTION_DB_SIGNED = "Signé"
INSPECTION_DB_TERMINÉ = "Terminé"
INSPECTION_DB_PENDING = "À signer"
INSPECTION_DB_TO_CHECK = "À contrôler"

# Mapping from internal logic keys to French labels
INSPECTION_STATUS_MAP = {
    "signed": "Signé",
    "completed": "Terminé",
    "pending": "À signer",
    "to_check": "À contrôler",
}

# Mapping from DB values (French) to internal logic keys
# This allows logic like `if get_inspection_key(record.etat_controle) == "signed"`
INSPECTION_DB_TO_KEY = {
    INSPECTION_DB_SIGNED: "signed",
    INSPECTION_DB_TERMINÉ: "completed",
    INSPECTION_DB_PENDING: "pending",
    INSPECTION_DB_TO_CHECK: "to_check",
}


def format_inspection_status(db_status):
    """
    Map a DB status string to its display label via the internal key.
    """
    key = INSPECTION_DB_TO_KEY.get(db_status, db_status)
    return INSPECTION_STATUS_MAP.get(key, db_status)


# ── CSS & UI Helpers ─────────────────────────────────────────────

def get_status_css_class(status_or_id):
    """
    Returns a CSS-friendly class name based on the status label, ID, or DB value.
    Used for badge styling in the frontend.
    """
    if not status_or_id:
        return "status-null"

    # 1. Try to find if it's an internal key
    if status_or_id in ["signed", "completed", "pending", "to_check", "to_generate", "to_send", "to_sign"]:
        mapping = {
            "signed": "status-signed",
            "completed": "status-completed",
            "pending": "status-pending-signature",
            "to_sign": "status-pending-signature",
            "to_check": "status-to-check",
            "to_generate": "status-to-generate",
            "to_send": "status-to-send",
        }
        return mapping.get(status_or_id)

    # 2. Fallback for legacy DB values or display labels
    mapping = {
        "Signé": "status-signed",
        "Terminé": "status-completed",
        "À signer": "status-pending-signature",
        "À générer": "status-to-generate",
        "À envoyer": "status-to-send",
        "À contrôler": "status-to-check",
    }

    return mapping.get(status_or_id, f"status-{status_or_id.lower().replace(' ', '-')}")
