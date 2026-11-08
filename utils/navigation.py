"""
Navigation contextuelle de l'ERP (paramètre `return_to`).

Permet de revenir à la page d'origine (fiche projet, tableau de bord, historique véhicule…)
plutôt qu'à la liste globale, après une consultation, une création ou une modification.

Sécurité : seules les URL relatives internes à l'admin (`/admin...`) sont acceptées,
ce qui empêche toute redirection ouverte vers un domaine externe.
"""

import re
from typing import Optional
from urllib.parse import urlsplit

from flask import has_request_context, redirect, request, url_for

RETURN_TO_PARAM = "return_to"
_MAX_LENGTH = 512


def safe_return_to(value) -> Optional[str]:
    """Valide une URL de retour : chemin relatif commençant par /admin, sans schéma ni hôte."""
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    if len(value) > _MAX_LENGTH or "\\" in value or any(c in value for c in "\r\n\t"):
        return None
    parts = urlsplit(value)
    if parts.scheme or parts.netloc or value.startswith("//"):
        return None
    if not (parts.path == "/admin" or parts.path.startswith("/admin/")):
        return None
    return value.rstrip("?")


def get_return_to() -> Optional[str]:
    """URL de retour transmise à la requête courante (GET ou POST), validée."""
    if not has_request_context():
        return None
    return safe_return_to(
        request.args.get(RETURN_TO_PARAM) or request.form.get(RETURN_TO_PARAM)
    )


def current_location() -> str:
    """Chemin courant (avec query string) utilisable comme URL de retour."""
    return request.full_path.rstrip("?")


def url_from_here(endpoint: str, **values) -> str:
    """URL vers `endpoint` qui mémorise la page courante comme destination de retour."""
    values[RETURN_TO_PARAM] = current_location()
    return url_for(endpoint, **values)


def url_keep_return(endpoint: str, **values) -> str:
    """URL vers `endpoint` qui propage l'URL de retour courante (si présente)."""
    return_to = get_return_to()
    if return_to:
        values[RETURN_TO_PARAM] = return_to
    return url_for(endpoint, **values)


def redirect_keep_return(endpoint: str, **values):
    """Redirection (après POST) qui conserve le contexte de retour."""
    return redirect(url_keep_return(endpoint, **values))


def redirect_back_or(endpoint: str, **values):
    """Redirige vers l'URL de retour si elle existe, sinon vers `endpoint`."""
    return redirect(get_return_to() or url_for(endpoint, **values))


_BACK_LABELS = (
    (re.compile(r"^/admin/projects/\d+"), "← Retour au projet"),
    (re.compile(r"^/admin/projects(/archives)?/?(\?|$)"), "← Retour aux projets"),
    (re.compile(r"^/admin/dashboard"), "← Retour au tableau de bord"),
    (re.compile(r"^/admin/fleet/(?!safety-rules|risk-assessment)[^/?]+"), "← Retour à l'historique du véhicule"),
    (re.compile(r"^/admin/fleet"), "← Retour à la flotte"),
    (re.compile(r"^/admin/incidents/\d+"), "← Retour à l'incident"),
    (re.compile(r"^/admin/checkouts/\d+"), "← Revenir au contrôle de départ"),
    (re.compile(r"^/admin/checkins/\d+"), "← Revenir au contrôle de retour"),
)


def back_label(return_to: Optional[str], default: str = "← Retour à la liste") -> str:
    """Libellé du bouton retour selon la page d'origine."""
    if not return_to:
        return default
    for pattern, label in _BACK_LABELS:
        if pattern.search(return_to):
            return label
    return "← Retour"


def register_navigation_helpers(app) -> None:
    """Expose les helpers de navigation contextuelle dans Jinja."""
    app.jinja_env.globals.update(
        get_return_to=get_return_to,
        url_from_here=url_from_here,
        url_keep_return=url_keep_return,
        back_label=back_label,
    )
