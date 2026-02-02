import os
import mysql.connector
from sshtunnel import SSHTunnelForwarder

def get_db_connection():
    """Create and return a MySQL connection."""
    mysql_host = os.getenv("MYSQL_HOST")
    mysql_user = os.getenv("MYSQL_USER")
    mysql_password = os.getenv("MYSQL_PASSWORD")
    mysql_database = os.getenv("MYSQL_DATABASE")

    use_ssh = os.getenv("USE_SSH_TUNNEL", "false").lower() == "true"

    if use_ssh:
        ssh_host = os.getenv("SSH_HOST")
        ssh_user = os.getenv("SSH_USER")
        ssh_password = os.getenv("SSH_PASSWORD")

        tunnel = SSHTunnelForwarder(
            (ssh_host, 22),
            ssh_username=ssh_user,
            ssh_password=ssh_password,
            remote_bind_address=(mysql_host, 3306)
        )
        tunnel.start()

        connection = mysql.connector.connect(
            host="127.0.0.1",
            port=tunnel.local_bind_port,
            user=mysql_user,
            password=mysql_password,
            database=mysql_database
        )
        return connection, tunnel
    else:
        connection = mysql.connector.connect(
            host=mysql_host,
            user=mysql_user,
            password=mysql_password,
            database=mysql_database
        )
        return connection, None
