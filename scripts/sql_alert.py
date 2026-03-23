import ast
import os
import re
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from functools import lru_cache
from pathlib import Path

import requests
from dotenv import load_dotenv
from utils.scripts_helper import build_minimal_app

# Setup path for local imports
_root = Path(__file__).parent.parent.parent
sys.path.append(str(_root))

# Load environment variables
load_dotenv(_root / '.env')


@lru_cache(maxsize=128)
def get_geolocation(ip_address):
    if not ip_address or ip_address in ("127.0.0.1", "::1", "localhost", "None"):
        return "Local"
    try:
        response = requests.get(
            f"http://ip-api.com/json/{ip_address}?fields=status,country,city", timeout=2.0)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return f"{data.get('city', '')}, {data.get('country', '')}".strip(', ')
    except Exception:
        pass
    return "Unknown"


def render_query(query: str, parameters: str | None) -> str:
    """Reconstitue la requête SQL avec ses paramètres injectés."""
    if not parameters:
        return query
    try:
        params = ast.literal_eval(parameters)
    except Exception:
        return query

    if isinstance(params, dict):
        def replace(match):
            key = match.group(1)
            val = params.get(key)
            if val is None:
                return "NULL"
            if isinstance(val, str):
                return f"'{val}'"
            return str(val)
        return re.sub(r'%\((\w+)\)s', replace, query)

    if isinstance(params, (list, tuple)):
        it = iter(params)

        def replace(_):
            val = next(it, None)
            if val is None:
                return "NULL"
            if isinstance(val, str):
                return f"'{val}'"
            return str(val)
        return re.sub(r'%s', replace, query)

    return query


def send_alerts_batch(alerts: list[dict], app):
    """Envoie toutes les alertes en un seul mail récapitulatif."""
    if not alerts:
        return

    for alert in alerts:
        print(f"[{datetime.now()}] 🚨 ALERTE : {alert['subject']}\n{alert['body']}\n")

    smtp_host = os.getenv("MAIL_SERVER")
    smtp_port = int(os.getenv("MAIL_PORT", 587))
    smtp_user = os.getenv("MAIL_ADMIN_USERNAME")
    smtp_password = os.getenv("MAIL_ADMIN_PASSWORD")
    alert_to = os.getenv("SUPER_ADMIN_MAIL")

    if not all([smtp_host, smtp_user, smtp_password, alert_to]):
        print(
            f"[{datetime.now()}] ⚠️  Config mail manquante. {len(alerts)} alerte(s) non envoyée(s).")
        return

    from flask import render_template

    now_utc = datetime.now(timezone.utc)
    date_str = now_utc.strftime("%d/%m/%Y")
    time_str = now_utc.strftime("%H:%M:%S")
    now_year = now_utc.year
    subject = f"[ALERTE SQL] {len(alerts)} alerte(s) détectée(s) — {date_str} {time_str}"

    with app.app_context():
        html_content = render_template(
            "emails/sql_alert.html",
            alerts=alerts,
            total_alerts=len(alerts),
            date_str=date_str,
            time_str=time_str,
            now_year=now_year,
        )

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = smtp_user
    msg['To'] = alert_to
    msg.add_alternative(html_content, subtype='html')

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if os.getenv("MAIL_USE_TLS", "true").lower() == "true":
                server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        print(
            f"[{datetime.now()}] 📧 Mail récapitulatif envoyé ({len(alerts)} alerte(s)).")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Erreur envoi mail : {e}")


# No more build_minimal_app here, it's imported at the top.


def check_alerts():
    from sqlalchemy import func

    from models import SqlQueryLog, db

    app, tunnel = build_minimal_app()
    alerts = []

    try:
        with app.app_context():
            now = datetime.now(timezone.utc)

            seuil_delete_count = int(os.getenv("SEUIL_DELETE_COUNT", 3))
            seuil_delete_window = int(os.getenv("SEUIL_DELETE_WINDOW", 10))
            seuil_flood_count = int(os.getenv("SEUIL_FLOOD_COUNT", 200))
            seuil_flood_window = int(os.getenv("SEUIL_FLOOD_WINDOW", 5))
            heure_debut = int(os.getenv("HEURE_DEBUT_BUREAU", 8))
            heure_fin = int(os.getenv("HEURE_FIN_BUREAU", 20))
            tables_sensibles = [
                t.strip()
                for t in os.getenv("TABLES_SENSIBLES", "users,passwords,tokens,sessions,payments").split(",")
                if t.strip()
            ]

            # ── 1. DELETE flood ───────────────────────────────────────────────
            delete_window = now - timedelta(minutes=seuil_delete_window)
            delete_users = (
                db.session.query(
                    SqlQueryLog.user,
                    SqlQueryLog.ip_address,
                    func.count(SqlQueryLog.id).label("cnt")
                )
                .filter(
                    SqlQueryLog.query.like("DELETE%"),
                    SqlQueryLog.timestamp >= delete_window,
                    SqlQueryLog.user != "system",
                )
                .group_by(SqlQueryLog.user, SqlQueryLog.ip_address)
                .having(func.count(SqlQueryLog.id) >= seuil_delete_count)
                .all()
            )

            for row in delete_users:
                loc = get_geolocation(row.ip_address)
                alerts.append({
                    "subject": f"DELETE Flood par {row.user}",
                    "body": (
                        f"L'utilisateur {row.user} (IP: {row.ip_address}, {loc}) "
                        f"a exécuté {row.cnt} requêtes DELETE "
                        f"dans les {seuil_delete_window} dernières minutes."
                    ),
                })

            # ── 2. Flood général ──────────────────────────────────────────────
            flood_window = now - timedelta(minutes=seuil_flood_window)
            flood_users = (
                db.session.query(
                    SqlQueryLog.user,
                    SqlQueryLog.ip_address,
                    func.count(SqlQueryLog.id).label("cnt")
                )
                .filter(
                    SqlQueryLog.timestamp >= flood_window,
                    SqlQueryLog.user != "system",
                )
                .group_by(SqlQueryLog.user, SqlQueryLog.ip_address)
                .having(func.count(SqlQueryLog.id) >= seuil_flood_count)
                .all()
            )

            for row in flood_users:
                loc = get_geolocation(row.ip_address)
                alerts.append({
                    "subject": f"Flood total par {row.user}",
                    "body": (
                        f"L'utilisateur {row.user} (IP: {row.ip_address}, {loc}) "
                        f"a exécuté {row.cnt} requêtes SQL "
                        f"dans les {seuil_flood_window} dernières minutes."
                    ),
                })

            # ── 3. Tables sensibles (5 dernières minutes) ─────────────────────
            recent_window = now - timedelta(minutes=5)

            for tbl in tables_sensibles:
                sensitive_logs = (
                    db.session.query(SqlQueryLog)
                    .filter(
                        SqlQueryLog.timestamp >= recent_window,
                        (
                            SqlQueryLog.query.like(f"DELETE FROM {tbl}%")
                            | SqlQueryLog.query.like(f"UPDATE {tbl}%")
                            | SqlQueryLog.query.like(f"DROP TABLE {tbl}%")
                        ),
                    )
                    .all()
                )

                for log in sensitive_logs:
                    loc = get_geolocation(log.ip_address)
                    alerts.append({
                        "subject": f"Modification de table sensible '{tbl}' par {log.user}",
                        "body": (
                            f"L'utilisateur {log.user} (IP: {log.ip_address}, {loc}) "
                            f"a modifié la table '{tbl}' à {log.timestamp} UTC.\n"
                            f"Requête : {render_query(log.query, log.parameters)}"
                        ),
                    })

            # ── 4. Activité hors heures de bureau ─────────────────────────────
            current_hour = now.hour
            if current_hour < heure_debut or current_hour >= heure_fin:
                out_of_hours = (
                    db.session.query(
                        SqlQueryLog.user,
                        SqlQueryLog.ip_address,
                        func.count(SqlQueryLog.id).label("cnt")
                    )
                    .filter(
                        SqlQueryLog.timestamp >= recent_window,
                        SqlQueryLog.user != "system",
                    )
                    .group_by(SqlQueryLog.user, SqlQueryLog.ip_address)
                    .all()
                )

                for row in out_of_hours:
                    loc = get_geolocation(row.ip_address)
                    alerts.append({
                        "subject": f"Activité SQL hors bureau par {row.user}",
                        "body": (
                            f"L'utilisateur {row.user} (IP: {row.ip_address}, {loc}) "
                            f"a exécuté {row.cnt} requêtes SQL "
                            f"hors des heures normales ({heure_debut}h-{heure_fin}h UTC)."
                        ),
                    })

        send_alerts_batch(alerts, app)

    finally:
        if tunnel and tunnel.is_active:
            tunnel.stop()
            print(f"[{datetime.now()}] 🔌 SSH Tunnel fermé.")


if __name__ == "__main__":
    check_alerts()
