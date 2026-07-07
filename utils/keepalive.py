import socket as _socket
from sqlalchemy import event, engine as _sa_engine


def init_tcp_keepalive(app):
    """Active le TCP keepalive sur chaque nouvelle connexion MySQL pour éviter les coupures."""
    @event.listens_for(_sa_engine.Engine, "connect")
    def _set_tcp_keepalive(dbapi_connection, connection_record):
        """Active le TCP keepalive sur chaque nouvelle connexion MySQL.

        Détecte automatiquement s'il faut utiliser l'objet socket natif (PyMySQL)
        ou recréer un wrapper à partir du file descriptor (mysqlclient).
        """
        sock = None
        should_detach = False
        try:
            # 1. Utilise l'objet socket s'il est déjà disponible (PyMySQL)
            if hasattr(dbapi_connection, '_sock') and dbapi_connection._sock is not None:
                sock = dbapi_connection._sock
            elif hasattr(dbapi_connection, 'sock') and dbapi_connection.sock is not None:
                sock = dbapi_connection.sock
            # 2. Sinon, récupère le FD natif (mysqlclient)
            elif hasattr(dbapi_connection, 'fileno'):
                try:
                    fd = dbapi_connection.fileno()
                    if fd is not None and fd >= 0:
                        sock = _socket.socket(fileno=fd)
                        should_detach = True
                except AttributeError:
                    pass

            if sock is not None:
                sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_KEEPALIVE, 1)
                
                # Configurer les options TCP Keepalive de manière robuste selon l'OS
                # Sur macOS, TCP_KEEPIDLE n'existe pas et est remplacé par TCP_KEEPALIVE.
                # On configure chaque option individuellement pour éviter qu'une erreur n'annule les autres.
                for opt_name, val in [
                    ('TCP_KEEPIDLE', 10),
                    ('TCP_KEEPALIVE', 10),
                    ('TCP_KEEPINTVL', 10),
                    ('TCP_KEEPCNT', 3)
                ]:
                    if hasattr(_socket, opt_name):
                        try:
                            sock.setsockopt(_socket.IPPROTO_TCP, getattr(_socket, opt_name), val)
                        except (AttributeError, OSError):
                            pass

                # N'appeler detach() que si on a créé un nouveau wrapper socket temporaire
                if should_detach:
                    sock.detach()
        except Exception as e:
            app.logger.debug(f"ℹ️ TCP keepalive non configuré pour cette connexion : {e}")
