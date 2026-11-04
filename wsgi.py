"""
Point d'entrée WSGI de production et serveur applicatif (Gunicorn / Docker).
Fournit l'instance de l'application Flask et les utilitaires de préchauffage du cache.
"""

from app import create_app, warm_cache

application = create_app()
app = application

__all__ = ["application", "app", "warm_cache"]
