#!/usr/bin/env python3
"""
Résumé quotidien du pointage du matériel : envoie aux administrateurs et managers la liste des
projets ayant des jours de tournage passés non pointés (aucun e-mail s'il n'y a rien à signaler).

Usage :
    python scripts/remind_equipment_usage.py            # Envoi réel
    python scripts/remind_equipment_usage.py --dry-run  # Affiche les projets et destinataires sans envoyer

Crontab (hôte) : tous les jours à 8h15
    15 8 * * * cd /app && python scripts/remind_equipment_usage.py >> logs/cron.log 2>&1
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dotenv import load_dotenv  # isort: skip # noqa: E402
from utils.cron_helper import monitor_cron_job  # isort: skip # noqa: E402
from utils.scripts_helper import build_minimal_app  # isort: skip # noqa: E402

load_dotenv(_root / ".env")


def run(dry_run: bool = False):
    from services.admin.equipment_stats import send_usage_reminder_digest

    app, tunnel = build_minimal_app()
    try:
        with app.app_context(), app.test_request_context():
            base_url = os.getenv("APP_BASE_URL") or os.getenv("BASE_URL") or "https://bellevitesse.com"
            result = send_usage_reminder_digest(base_url=base_url, dry_run=dry_run)
            mode = "SIMULATION" if dry_run else "ENVOI RÉEL"
            print(f"[{datetime.now()}] 📋 Pointage du matériel ({mode}) : "
                  f"{len(result['projects'])} projet(s) à pointer, {len(result['recipients'])} destinataire(s), "
                  f"{result['sent']} e-mail(s) envoyé(s).")
            for p in result["projects"]:
                print(f"   - {p['name']} ({p['production']}) : {p['pending_days']} jour(s) à pointer")
            return result
    finally:
        if tunnel and tunnel.is_active:
            tunnel.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Résumé quotidien du pointage du matériel")
    parser.add_argument("--dry-run", action="store_true", help="Simuler sans envoyer d'e-mails")
    args = parser.parse_args()
    if args.dry_run:
        run(dry_run=True)
    else:
        with monitor_cron_job("remind_equipment_usage"):
            run(dry_run=False)
