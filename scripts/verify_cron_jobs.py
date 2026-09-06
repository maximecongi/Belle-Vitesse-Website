import ast
import json
import os
import smtplib
import sys
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from pathlib import Path
from dotenv import load_dotenv

# Setup path for local imports (parent of scripts/)
_root = Path(__file__).parent.parent
sys.path.append(str(_root))

from utils.scripts_helper import build_minimal_app

# Load environment variables
load_dotenv(_root / ".env")

# Define expected cron jobs and their execution schedule tolerances
EXPECTED_JOBS = [
    {
        "job_name": "backup_sql",
        "display_name": "Sauvegarde Base de Données SQL",
        "expected_freq": "Tous les jours à 4h00",
        "tolerance_hours": 26,  # 24h + 2h margin
    },
    {
        "job_name": "purge_sql_logs",
        "display_name": "Purge des logs SQL (60 jours)",
        "expected_freq": "Tous les jours à 5h00",
        "tolerance_hours": 26,  # 24h + 2h margin
    },
    {
        "job_name": "sql_alert",
        "display_name": "Alerte Anomalies SQL",
        "expected_freq": "Toutes les 5 minutes",
        "tolerance_hours": 1,  # 1h tolerance (runs frequently)
    },
    {
        "job_name": "cleanup_empty_folders_kdrive",
        "display_name": "Nettoyage dossiers vides kDrive",
        "expected_freq": "Tous les lundis à 3h30",
        "tolerance_hours": 170,  # 168h (7 days) + 2h margin
    },
    {
        "job_name": "cleanup_empty_folders_server",
        "display_name": "Nettoyage dossiers vides Serveur",
        "expected_freq": "Tous les lundis à 3h45",
        "tolerance_hours": 170,  # 168h (7 days) + 2h margin
    },
    {
        "job_name": "remind_waivers",
        "display_name": "Relance automatique des décharges (48h avant)",
        "expected_freq": "Tous les jours à 8h00",
        "tolerance_hours": 26,  # 24h + 2h margin
    },
]


def load_cron_status():
    """Load cron execution statuses from the shared JSON file."""
    possible_paths = [
        Path("/app/logs"),
        Path(__file__).parent.parent.parent / "logs",
        Path(__file__).parent.parent / "logs",
    ]
    logs_dir = None
    for p in possible_paths:
        if p.exists() and p.is_dir():
            logs_dir = p
            break

    if not logs_dir:
        logs_dir = Path(__file__).parent.parent / "logs"

    status_file = logs_dir / "cron_status.json"

    if status_file.exists():
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error reading {status_file}: {e}")
    return {}


def format_timestamp(iso_str):
    """Convert ISO UTC timestamp into a readable format in French timezone."""
    if not iso_str:
        return "Jamais"
    try:
        dt = datetime.fromisoformat(iso_str)
        # Shift to local display if needed, but keeping UTC clear for logs
        return dt.strftime("%d/%m/%Y à %H:%M:%S")
    except Exception:
        return iso_str


def verify_jobs():
    statuses = load_cron_status()
    now = datetime.now(timezone.utc)

    jobs_report = []
    failures = []
    global_status = "OK"

    for expected in EXPECTED_JOBS:
        name = expected["job_name"]
        disp_name = expected["display_name"]
        freq = expected["expected_freq"]
        tolerance = expected["tolerance_hours"]

        job_info = {
            "job_name": name,
            "display_name": disp_name,
            "expected_freq": freq,
            "last_run_display": "Jamais",
            "status": "missing",
        }

        if name in statuses:
            info = statuses[name]
            last_run_str = info.get("last_run")
            status = info.get("status")
            error = info.get("error")

            job_info["last_run_display"] = format_timestamp(last_run_str)

            if last_run_str:
                try:
                    last_run_dt = datetime.fromisoformat(last_run_str)
                    age_hours = (now - last_run_dt).total_seconds() / 3600.0
                except Exception:
                    age_hours = 9999.0
            else:
                age_hours = 9999.0

            # Determine actual status
            if status == "failed":
                job_info["status"] = "failed"
                global_status = "DANGER"
                failures.append(
                    {
                        "job_name": name,
                        "display_name": disp_name,
                        "status_label": "ÉCHEC D'EXÉCUTION",
                        "last_run_display": job_info["last_run_display"],
                        "error_message": error or "Aucune traceback fournie.",
                    }
                )
            elif age_hours > tolerance:
                job_info["status"] = "stale"
                if global_status != "DANGER":
                    global_status = "WARNING"
                failures.append(
                    {
                        "job_name": name,
                        "display_name": disp_name,
                        "status_label": f"EN RETARD (Dernière exécution il y a {int(age_hours)}h, tolérance: {tolerance}h)",
                        "last_run_display": job_info["last_run_display"],
                        "error_message": f"La tâche planifiée ne s'est pas exécutée dans le délai de tolérance imparti ({tolerance} heures).",
                    }
                )
            else:
                job_info["status"] = "success"
        else:
            # Job missing entirely
            if global_status != "DANGER":
                global_status = "WARNING"
            failures.append(
                {
                    "job_name": name,
                    "display_name": disp_name,
                    "status_label": "MANQUANT",
                    "last_run_display": "Jamais",
                    "error_message": "Aucun enregistrement d'exécution n'a été trouvé pour cette tâche planifiée.",
                }
            )

        jobs_report.append(job_info)

    return jobs_report, failures, global_status


def send_report_email(jobs, failures, global_status, app):
    """Render HTML report and send email to the administrator."""
    smtp_host = os.getenv("MAIL_SERVER")
    smtp_port = int(os.getenv("MAIL_PORT", 587))
    smtp_user = os.getenv("MAIL_ADMIN_USERNAME")
    smtp_password = os.getenv("MAIL_ADMIN_PASSWORD")
    alert_to = os.getenv("SUPER_ADMIN_MAIL")

    if not all([smtp_host, smtp_user, smtp_password, alert_to]):
        print(f"[{datetime.now()}] ⚠️ Mail config missing. Report not sent.")
        return

    from flask import render_template

    now_utc = datetime.now(timezone.utc)
    date_str = now_utc.strftime("%d/%m/%Y")
    time_str = now_utc.strftime("%H:%M:%S")

    subject_prefix = "[CRON SUCCESS]" if global_status == "OK" else "[CRON WARNING]" if global_status == "WARNING" else "[CRON ALERTE ÉCHEC]"
    subject = f"{subject_prefix} Rapport quotidien des tâches planifiées — {date_str}"

    with app.app_context():
        html_content = render_template(
            "emails/cron_report.html",
            jobs=jobs,
            failures=failures,
            global_status=global_status,
            date_str=date_str,
            time_str=time_str,
            now_year=now_utc.year,
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"Belle Vitesse Admin <{smtp_user}>"
    msg["To"] = alert_to
    msg.add_alternative(html_content, subtype="html")

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if os.getenv("MAIL_USE_TLS", "true").lower() == "true":
                server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        print(f"[{datetime.now()}] 📧 Daily cron report email sent to {alert_to}.")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Failed to send daily cron report email: {e}")


def main():
    app, tunnel = build_minimal_app()
    try:
        jobs, failures, global_status = verify_jobs()
        send_report_email(jobs, failures, global_status, app)
    finally:
        if tunnel and tunnel.is_active:
            tunnel.stop()


if __name__ == "__main__":
    main()
