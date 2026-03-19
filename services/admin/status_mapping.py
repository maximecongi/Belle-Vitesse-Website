"""
Centralized status mapping and formatting for the admin section.
Handles labels for Waivers and Inspections (Check-ins/Check-outs).
Using standardized English keys as Source of Truth.
"""

# ── Waivers Mapping ──────────────────────────────────────────────

WAIVER_STATUS_MAP = {
    "to_generate": "À générer",
    "to_send": "À envoyer",
    "to_sign": "À signer",
    "signed": "Signé",
    "approved": "Approuvé",
    "rejected": "Rejeté",
}


def format_waiver_status(status_id):
    """
    Map an internal waiver status identifier to its French label.
    """
    return WAIVER_STATUS_MAP.get(status_id, status_id)


# Unified internal keys for inspections
INSPECTION_STATUS_MAP = {
    "to_check": "À contrôler",
    "in_progress": "En cours",
    "pending": "À signer",
    "signed": "Signé"
}


def get_inspection_key(status):
    """
    Returns the English internal key for a given status.
    Ensures that we always have a valid key (defaults to 'to_check').
    """
    if not status or status not in INSPECTION_STATUS_MAP:
        return "warning"
    return status


def format_inspection_status(status_id):
    """
    Map an internal inspection status identifier to its French label.
    """
    return INSPECTION_STATUS_MAP.get(status_id, status_id)


# ── Checkpoints Mapping ──────────────────────────────────────────

CHECKPOINT_STATUS_MAP = {
    "ok": "OK",
    "critical": "Défaut",
    "warning": "À vérifier"
}


def get_checkpoint_key(status):
    """
    Standardize the internal key for a checkpoint status.
    Handles None/Empty and maps common synonyms and legacy labels.
    """
    if not status:
        return "pending"

    s = str(status).lower().strip()

    # Mapping synonyms to standardized internal keys
    mappings = {
        "ok": ["ok", "success", "oui", "yes"],
        "critical": ["critical", "défaut", "non", "no", "danger"],
        "warning": ["warning", "à vérifier", "pending", "to_check"],
        "not_applicable": ["not_applicable", "non pertinent", "n/a", "none"]
    }

    for key, synonyms in mappings.items():
        if s in synonyms:
            return key

    return s


def format_checkpoint_status(status):
    """
    Returns the French label for a checkpoint status.
    """
    return CHECKPOINT_STATUS_MAP.get(status, status)

# ── CSS & UI Helpers ─────────────────────────────────────────────
