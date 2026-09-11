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
    "draft": "Brouillon",
    "pending": "À signer",
}


def format_waiver_status(status_id):
    """
    Mappe un identifiant de statut de décharge interne vers son label français.
    """
    if not status_id:
        return "À générer"
    return WAIVER_STATUS_MAP.get(str(status_id).lower(), str(status_id).capitalize())


# Unified internal keys for inspections
INSPECTION_STATUS_MAP = {
    "to_check": "À contrôler",
    "pending": "À signer",
    "in_progress": "En cours",
    "signed": "Signé",
    "approved": "Signé",
    "completed": "Signé",
    "ok": "Signé",
    "cloture": "Clôturé",
    "draft": "Brouillon",
    "to_sign": "À signer",
    "warning": "À vérifier",
    "critical": "Défaut",
}


def get_inspection_key(status):
    """
    Retourne la clé interne pour un statut donné.
    Garantit toujours le retour d'une clé valide (par défaut 'to_check' si inconnu).
    """
    if not status or status not in INSPECTION_STATUS_MAP:
        return "to_check"
    return status


def format_inspection_status(status_id):
    """
    Mappe un identifiant de statut d'inspection interne vers son label français.
    """
    if not status_id:
        return "À réaliser"
    return INSPECTION_STATUS_MAP.get(str(status_id).lower(), str(status_id).capitalize())


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
