import os
from sshtunnel import SSHTunnelForwarder

def start_ssh_tunnel(app_config, logger, existing_tunnel=None):
    """
    Starts an SSH tunnel for database access in development.
    Returns (tunnel, local_port) or (None, None) if not needed or failed.
    """
    env = os.getenv("FLASK_ENV", "development")
    
    if env == "production":
        return None, None

    if existing_tunnel and existing_tunnel.is_active:
        return existing_tunnel, existing_tunnel.local_bind_port

    ssh_host = os.getenv("SSH_HOST")
    ssh_user = os.getenv("SSH_USER")
    ssh_pass = os.getenv("SSH_PASSWORD")
    mysql_host = app_config.get("MYSQL_HOST", "localhost")

    if not all([ssh_host, ssh_user, ssh_pass]):
        logger.warning("⚠️ SSH Tunnel requested but missing host/user/password.")
        return None, None

    try:
        tunnel = SSHTunnelForwarder(
            (ssh_host, 22),
            ssh_username=ssh_user,
            ssh_password=ssh_pass,
            remote_bind_address=(mysql_host, 3306)
        )
        tunnel.start()
        logger.info(f"✅ SSH Tunnel started on port {tunnel.local_bind_port}")
        return tunnel, tunnel.local_bind_port
    except Exception as e:
        logger.error(f"❌ Failed to start SSH Tunnel: {e}")
        return None, None
