"""
Package d'administration des décharges et documents légaux Belle Vitesse.
Architecture modulaire :
- common.py : Utilitaires partagés (dates, URLs de signature, tokens, suppression d'actifs)
- core.py : Gestion du cycle de vie unifié (création, génération, envoi, reset, suppression)
- cgl.py : Spécificités des Conditions Générales de Location (CGL - BVRA)
- safety_rules.py : Spécificités des Règles de Sécurité Universelles (BVSR) et contreseing
- reminders.py : Relances automatiques par e-mail
"""
from .cgl import (
    create_cgl,
    delete_cgl,
    delete_cgl_internal,
    generate_cgl,
    list_cgl,
    reset_cgl,
    send_cgl,
)
from .common import (
    _format_project_shooting_dates,
    format_waiver_shooting_dates,
    get_or_create_waiver_signing_url,
)
from .core import (
    create_waiver,
    delete_waiver,
    delete_waiver_internal,
    generate_waiver,
    reset_waiver,
    send_waiver,
)
from .reminders import (
    auto_remind_pending_waivers,
)
from .safety_rules import (
    countersign_safety_rules,
    create_safety_rules_waiver,
    delete_safety_rules_internal,
    delete_safety_rules_waiver,
    delete_safety_rules_waiver_internal,
    generate_safety_rules_waiver,
    list_safety_rules_waivers,
    reset_safety_rules_waiver,
    send_safety_rules_waiver,
)

__all__ = [
    # Common
    "format_waiver_shooting_dates",
    "get_or_create_waiver_signing_url",
    # Core
    "create_waiver",
    "generate_waiver",
    "send_waiver",
    "delete_waiver",
    "reset_waiver",
    "delete_waiver_internal",
    # CGL
    "create_cgl",
    "delete_cgl",
    "generate_cgl",
    "send_cgl",
    "reset_cgl",
    "delete_cgl_internal",
    "list_cgl",
    # Safety Rules
    "create_safety_rules_waiver",
    "delete_safety_rules_waiver",
    "generate_safety_rules_waiver",
    "send_safety_rules_waiver",
    "reset_safety_rules_waiver",
    "delete_safety_rules_waiver_internal",
    "delete_safety_rules_internal",
    "countersign_safety_rules",
    "list_safety_rules_waivers",
    # Reminders
    "auto_remind_pending_waivers",
]
