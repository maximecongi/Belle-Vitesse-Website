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
    "signed": "Signé",
    "validated": "Validé",
    "completed": "Terminé"
}


def get_inspection_key(status):
    """
    Returns the English internal key for a given status.
    Ensures that we always have a valid key (defaults to 'to_check').
    """
    if not status or status not in INSPECTION_STATUS_MAP:
        return "warning"
    return status


# ── Checkpoints Mapping ──────────────────────────────────────────

CHECKPOINT_STATUS_MAP = {
    "ok": "OK",
    "critical": "Défaut",
    "warning": "À vérifier"
}


def get_checkpoint_key(status):
    """
    Returns the English internal key for a checkpoint status.
    Mappings:
      - OK/ok -> ok
      - À vérifier/warning/pending -> warning
      - Défaut/critical/Non/no -> critical
    """
    if not status:
        return "pending"
    s = str(status).lower().strip()
    if s in ["ok", "success", "oui", "yes"]:
        return "ok"
    if s in ["à vérifier", "warning", "pending", "to_check"]:
        return "warning"
    if s in ["défaut", "critical", "non", "no", "danger"]:
        return "critical"
    if s in ["non pertinent", "not_applicable", "n/a", "none"]:
        return "not_applicable"
    return s


def get_checkpoint_status(status):
    """
    Returns the French label for a checkpoint status.
    """
    return CHECKPOINT_STATUS_MAP.get(status, status)

# ── CSS & UI Helpers ─────────────────────────────────────────────


def get_status_css_class(status_id):
    """
    Returns a CSS-friendly class name based on the internal English key.
    Handles both Inspection and Checkpoint statuses.
    """
    if not status_id:
        return "status-null"

    # Map internal English keys to CSS classes
    mapping = {
        # Inspections
        "to_check": "status-to-check",
        "in_progress": "status-in-progress",
        "pending": "status-pending-signature",
        "signed": "status-signed",
        "validated": "status-completed",
        "completed": "status-completed",
        # Waivers
        "to_generate": "status-to-generate",
        "to_send": "status-to-send",
        "to_sign": "status-pending-signature",
        # Checkpoints
        "ok": "status-ok",
        "warning": "status-warning",
        "critical": "status-critical",
        "not_applicable": "status-neutral",
    }

    # Try checkpoint key first, then inspection key
    key = get_checkpoint_key(status_id)
    if key in mapping:
        return mapping[key]

    key = get_inspection_key(status_id)
    return mapping.get(key, f"status-{str(key).lower().replace(' ', '-')}")
