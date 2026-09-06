#!/usr/bin/env python3
"""
Relance automatique des décharges (pilotes et productions) 48h avant le tournage.

Usage :
    python scripts/remind_waivers.py              # Relance les décharges à J-2 (48h)
    python scripts/remind_waivers.py --days 3     # Relance à J-3
    python scripts/remind_waivers.py --dry-run    # Simule sans envoyer d'e-mails
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Configuration du chemin pour les imports du projet
_root = Path(__file__).parent.parent
sys.path.append(str(_root))

from dotenv import load_dotenv
from utils.cron_helper import monitor_cron_job
from utils.scripts_helper import build_minimal_app

load_dotenv(_root / ".env")


def run_reminders(days_before: int = 2, dry_run: bool = False):
    """Exécute la vérification et la relance des décharges."""
    from services.admin.waivers import auto_remind_pending_waivers

    app, tunnel = build_minimal_app()
    try:
        with app.app_context():
            base_url = (
                os.getenv("APP_BASE_URL")
                or os.getenv("BASE_URL")
                or "https://bellevitesse.com"
            )
            print(
                f"[{datetime.now()}] 🔔 Vérification des décharges non signées à J-{days_before} "
                f"({'SIMULATION / DRY-RUN' if dry_run else 'ENVOI RÉEL'})..."
            )

            if dry_run:
                # En mode dry-run, on affiche les décharges éligibles sans générer de tokens ni envoyer d'emails
                from datetime import date, timedelta
                from models import PilotWaiver, ProductionWaiver, Project
                from sqlalchemy.orm import joinedload

                today = date.today()
                target_limit = today + timedelta(days=days_before)
                print(f"   Fenêtre d'échéance : du {today.strftime('%d/%m/%Y')} au {target_limit.strftime('%d/%m/%Y')}")

                # Productions
                prods = (
                    ProductionWaiver.query.filter(
                        ProductionWaiver.deleted_at.is_(None),
                        ProductionWaiver.status.in_(["to_send", "to_sign"]),
                    )
                    .options(joinedload(ProductionWaiver.project).joinedload(Project.production_contact))
                    .all()
                )
                prod_count = 0
                for pw in prods:
                    p = pw.project
                    if not p or p.deleted_at is not None:
                        continue
                    p_date = p.departure_date or p.shoot_start_date
                    if p_date and today <= p_date <= target_limit:
                        contact = p.production_contact
                        mail = contact.mail if contact else "AUCUN EMAIL"
                        already = " (déjà relancée aujourd'hui)" if (pw.last_reminded_at and pw.last_reminded_at.date() == today) else ""
                        print(f"   [PROD] Projet: {p.name} | Décharge: {pw.waiver_id} | Contact: {mail} | Date: {p_date}{already}")
                        prod_count += 1

                # Pilotes
                pilots = (
                    PilotWaiver.query.filter(
                        PilotWaiver.deleted_at.is_(None),
                        PilotWaiver.status.in_(["to_send", "to_sign"]),
                    )
                    .options(joinedload(PilotWaiver.project).joinedload(Project.pilot_contact))
                    .all()
                )
                pilot_count = 0
                for dw in pilots:
                    p = dw.project
                    if not p or p.deleted_at is not None:
                        continue
                    p_date = p.departure_date or p.shoot_start_date
                    if p_date and today <= p_date <= target_limit:
                        pilot = p.pilot_contact
                        mail = pilot.mail if pilot else "AUCUN EMAIL"
                        already = " (déjà relancée aujourd'hui)" if (dw.last_reminded_at and dw.last_reminded_at.date() == today) else ""
                        print(f"   [PILOTE] Projet: {p.name} | Décharge: {dw.waiver_id} | Pilote: {mail} | Date: {p_date}{already}")
                        pilot_count += 1

                print(f"[{datetime.now()}] ℹ️ Total éligible : {prod_count} production(s), {pilot_count} pilote(s).")
                return {"production_reminders_sent": prod_count, "pilot_reminders_sent": pilot_count}

            # Mode envoi normal
            results = auto_remind_pending_waivers(days_before=days_before, base_url=base_url)
            prod_sent = results.get("production_reminders_sent", 0)
            pilot_sent = results.get("pilot_reminders_sent", 0)
            print(
                f"[{datetime.now()}] ✅ Relances terminées avec succès : "
                f"{prod_sent} production(s), {pilot_sent} pilote(s)."
            )
            for d in results.get("details", []):
                print(
                    f"   - [{d['type'].upper()}] Projet: '{d['project_name']}' -> {d['recipient']} "
                    f"(Départ: {d['departure_date']}, Relance n°{d['reminder_count']})"
                )
            return results
    finally:
        if tunnel and tunnel.is_active:
            tunnel.stop()
            print(f"[{datetime.now()}] 🔌 SSH Tunnel fermé.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Relance automatique des décharges J-2 (48h avant)")
    parser.add_argument("--days", type=int, default=2, help="Nombre de jours avant le tournage (défaut : 2)")
    parser.add_argument("--dry-run", action="store_true", help="Simuler sans envoyer d'e-mails réels")
    args = parser.parse_args()

    if args.dry_run:
        run_reminders(days_before=args.days, dry_run=True)
    else:
        with monitor_cron_job("remind_waivers"):
            run_reminders(days_before=args.days, dry_run=False)
