"""
Utilitaires de requêtes HTTP partagés (extraction IP sécurisée, etc.).
"""

from flask import request


def get_client_ip() -> str:
    """
    Extrait l'adresse IP cliente de confiance.
    Comme ProxyFix(x_for=1) est configuré au niveau WSGI (app.py),
    request.remote_addr contient déjà l'IP cliente résolue de manière sécurisée
    par le reverse-proxy (Traefik).
    """
    ip = request.remote_addr or ""
    return ip.strip()[:45]
