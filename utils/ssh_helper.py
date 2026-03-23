import os
import logging
from sshtunnel import SSHTunnelForwarder

# Global tunnel state
_tunnel = None


def get_ssh_tunnel():
    """
    Ensure the SSH tunnel is started (if in dev) and return (tunnel, local_port).
    Returns (None, None) in production.
    """
    global _tunnel
    env = os.getenv("FLASK_ENV", "development")
    
    if env == "production":
        return None, None

    if _tunnel and _tunnel.is_active:
        return _tunnel, _tunnel.local_bind_port

    # Attempt to start a new tunnel
    logger = logging.getLogger("ssh_helper")
    ssh_host = os.getenv("SSH_HOST")
    ssh_user = os.getenv("SSH_USER")
    ssh_pass = os.getenv("SSH_PASSWORD")
    mysql_host = os.getenv("MYSQL_HOST", "localhost")

    if not all([ssh_host, ssh_user, ssh_pass]):
        logger.warning("⚠️ SSH Tunnel requested but missing host/user/password.")
        return None, None

    try:
        _tunnel = SSHTunnelForwarder(
            (ssh_host, 22),
            ssh_username=ssh_user,
            ssh_password=ssh_pass,
            remote_bind_address=(mysql_host, 3306)
        )
        _tunnel.start()
        logger.info(f"✅ SSH Tunnel started on port {_tunnel.local_bind_port}")
        return _tunnel, _tunnel.local_bind_port
    except Exception as e:
        logger.error(f"❌ Failed to start SSH Tunnel: {e}")
        return None, None


def start_ssh_tunnel(app_config, logger, existing_tunnel=None):
    """ Legacy wrapper for start_ssh_tunnel to maintain compatibility during refactor. """
    return get_ssh_tunnel()
