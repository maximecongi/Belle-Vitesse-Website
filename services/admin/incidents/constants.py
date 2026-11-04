"""
Constantes, nomenclatures et dictionnaires d'icônes et libellés du module Incidents.
"""

# ── Dictionnaires de Correspondance ──────────────────────────────

INCIDENT_CATEGORY_MAP = {
    "vehicule": "Véhicule",
    "materiel_camera": "Matériel Caméra / Tête",
    "mecanique": "Mécanique",
    "electrique": "Électrique / Batterie",
    "carrosserie": "Carrosserie",
    "accident_tiers": "Accident avec tiers",
    "meteo": "Intempéries / Météo",
    "securite": "Sécurité / Humain",
    "autre": "Autre incident",
}

INCIDENT_SEVERITY_MAP = {
    "mineur": "Mineur",
    "modere": "Modéré",
    "critique": "Critique",
}

INCIDENT_STATUS_MAP = {
    "signale": "Signalé",
    "en_expertise": "En expertise / Devis",
    "en_reparation": "En réparation atelier",
    "assurance": "Assurance",
    "resolu": "Résolu / Réparé",
    "cloture": "Clôturé",
}

INCIDENT_STATUS_ICONS = {
    "signale": "📣",
    "en_expertise": "🔍",
    "en_reparation": "🔧",
    "assurance": "📋",
    "resolu": "✅",
    "cloture": "🔒",
}

INCIDENT_STATUS_LUCIDE_ICONS = {
    "signale": "megaphone",
    "en_expertise": "search",
    "en_reparation": "wrench",
    "assurance": "clipboard-list",
    "resolu": "check-circle",
    "cloture": "lock",
}

INCIDENT_SEVERITY_LUCIDE_ICONS = {
    "mineur": "info",
    "modere": "alert-triangle",
    "critique": "alert-octagon",
}

INCIDENT_IMPACT_LUCIDE_ICONS = {
    "aucun": "check-circle",
    "retard": "clock",
    "interruption": "pause-circle",
    "annulation": "ban",
}

INCIDENT_STATUS_BADGE_VALS = {
    "signale": "neutral",
    "en_expertise": "warning",
    "en_reparation": "in_progress",
    "assurance": "assurance",
    "resolu": "ok",
    "cloture": "cloture",
}

INCIDENT_IMPACT_MAP = {
    "aucun": "Aucun impact",
    "retard": "Retard sur planning",
    "interruption": "Interruption temporaire",
    "annulation": "Annulation de session",
}

