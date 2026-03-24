"""
Mapping centralisé des statuts et formatage pour la section administration.
Gère les labels pour les décharges et les inspections (Départs/Retours).
Utilise des clés anglaises standardisées comme source de vérité.
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
    Mappe un identifiant de statut de décharge interne vers son label français.
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
    Retourne la clé interne (anglaise) pour un statut donné.
    Garantit toujours le retour d'une clé valide (par défaut 'warning' si inconnu).
    """
    if not status or status not in INSPECTION_STATUS_MAP:
        return "warning"
    return status


def format_inspection_status(status_id):
    """
    Mappe un identifiant de statut d'inspection interne vers son label français.
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
    Standardise la clé interne pour le statut d'un point de contrôle.
    Gère les valeurs vides et mappe les synonymes ou anciens labels.
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
    Retourne le label français pour le statut d'un point de contrôle.
    """
    return CHECKPOINT_STATUS_MAP.get(status, status)

# ── CSS & UI Helpers ─────────────────────────────────────────────
