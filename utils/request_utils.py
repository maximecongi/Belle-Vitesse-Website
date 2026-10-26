"""
Utilitaires de requêtes HTTP partagés (extraction IP sécurisée, résolution d'URL de base, etc.).
"""

import os
from typing import Optional
from flask import current_app, has_app_context, has_request_context, request


def get_client_ip() -> str:
    """
    Extrait l'adresse IP cliente de confiance.
    Comme ProxyFix(x_for=1) est configuré au niveau WSGI (app.py),
    request.remote_addr contient déjà l'IP cliente résolue de manière sécurisée
    par le reverse-proxy (Traefik).
    """
    ip = request.remote_addr or ""
    return ip.strip()[:45]


def resolve_base_url(custom_url: Optional[str] = None) -> str:
    """
    Résout de manière robuste l'URL de base absolue de l'application (pour QR codes, emails, liens de signature).
    Garantit qu'en environnement de développement (ou sur 127.0.0.1 / localhost),
    le schéma est strictement 'http://' et JAMAIS 'https://'.
    """
    candidate = custom_url
    if not candidate:
        if current_app:
            candidate = (
                current_app.config.get("APP_BASE_URL")
                or current_app.config.get("BASE_URL")
            )
        if not candidate:
            candidate = os.getenv("APP_BASE_URL") or os.getenv("BASE_URL")

    if not candidate and has_request_context():
        candidate = request.host_url

    if not candidate:
        server_name = current_app.config.get("SERVER_NAME") if current_app else os.getenv("SERVER_NAME")
        if server_name:
            candidate = server_name
        else:
            is_dev = False
            if current_app:
                is_dev = bool(
                    current_app.config.get("FLASK_ENV") in ("development", "testing")
                    or current_app.config.get("DEBUG")
                    or current_app.config.get("TESTING")
                )
            if not is_dev:
                is_dev = os.getenv("FLASK_ENV") in ("development", "testing")
            candidate = "http://127.0.0.1:5001" if is_dev else "https://bellevitesse.com"

    candidate = candidate.strip().rstrip("/")

    # Retirer d'éventuels préfixes doubles ou mal formés comme "https://http://" ou "http://https://"
    if candidate.startswith("https://http://"):
        candidate = "http://" + candidate[len("https://http://"):]
    elif candidate.startswith("http://https://"):
        candidate = "https://" + candidate[len("http://https://"):]

    # Détecter si l'hôte est local (127.0.0.1, localhost, 0.0.0.0, *.local)
    is_local_host = any(
        h in candidate.lower() for h in ("127.0.0.1", "localhost", "0.0.0.0", ".local")
    )

    if not candidate.startswith(("http://", "https://")):
        if is_local_host:
            candidate = f"http://{candidate}"
        else:
            candidate = f"https://{candidate}"

    # Règle absolue pour le développement local :
    # Si l'URL pointe vers un hôte local (127.0.0.1, localhost, etc.), convertir STRICTEMENT https:// en http://
    if is_local_host and candidate.startswith("https://"):
        candidate = "http://" + candidate[len("https://"):]

    return candidate.rstrip("/")
