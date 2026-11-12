#!/usr/bin/env python3
"""
Mail du matin du suivi commercial : échanges prévus aujourd'hui ou en retard (timeline commerciale)
et devis sans réponse du client depuis au moins QUOTE_FOLLOWUP_DAYS jours (variable du .env, 10 par défaut ; aucun e-mail s'il n'y a
rien à relancer).
Administrateurs / managers : tous les projets. Commerciaux : les projets dont ils sont le commercial.

Usage :
    python scripts/remind_quote_followups.py            # Envoi réel
    python scripts/remind_quote_followups.py --dry-run  # Affiche les projets et destinataires sans envoyer
    python scripts/remind_quote_followups.py --days 7   # Seuil ponctuel (prioritaire sur le .env)

Crontab (hôte) : tous les jours ouvrés à 8h30
    30 8 * * 1-5 cd /app && python scripts/remind_quote_followups.py >> logs/cron.log 2>&1
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


def run(dry_run: bool = False, days: int = None):
    from services.admin.commercial_timeline import QUOTE_FOLLOWUP_DAYS, send_quote_followup_digest

    days = days or QUOTE_FOLLOWUP_DAYS
    app, tunnel = build_minimal_app()
    try:
        with app.app_context(), app.test_request_context():
            base_url = os.getenv("APP_BASE_URL") or os.getenv("BASE_URL") or "https://bellevitesse.com"
            result = send_quote_followup_digest(base_url=base_url, dry_run=dry_run, days=days)
            mode = "SIMULATION" if dry_run else "ENVOI RÉEL"
            print(f"[{datetime.now()}] 📨 Suivi commercial ({mode}, seuil {days} j) : "
                  f"{len(result['followups'])} devis à relancer, {len(result['planned'])} échange(s) prévu(s) "
                  f"aujourd'hui ou en retard, {len(result['recipients'])} destinataire(s), "
                  f"{result['sent']} e-mail(s) envoyé(s).")
            for item in result["planned"]:
                ev = item["event"]
                print(f"   - [agenda] {ev.headline} — {item['project'].name} : {ev.occurred_at:%d/%m/%Y}"
                      f"{' (en retard)' if item['days'] < 0 else ''}")
            for f in result["followups"]:
                p = f["project"]
                print(f"   - {p.name} ({p.production.name if p.production else '—'}) : "
                      f"{f['days_waiting']} j sans réponse")
            return result
    finally:
        if tunnel and tunnel.is_active:
            tunnel.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Récapitulatif des devis à relancer")
    parser.add_argument("--dry-run", action="store_true", help="Simuler sans envoyer d'e-mails")
    parser.add_argument("--days", type=int, default=None, help="Jours sans réponse avant relance")
    args = parser.parse_args()
    if args.dry_run:
        run(dry_run=True, days=args.days)
    else:
        with monitor_cron_job("remind_quote_followups"):
            run(dry_run=False, days=args.days)
