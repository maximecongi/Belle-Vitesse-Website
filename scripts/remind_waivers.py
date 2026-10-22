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
                # En mode dry-run, on affiche les documents éligibles sans générer de tokens ni envoyer d'emails
                from datetime import date, timedelta
                from models import CglWaiver, SafetyRulesWaiver, Project
                from sqlalchemy.orm import joinedload

                today = date.today()
                target_limit = today + timedelta(days=days_before)
                print(f"   Fenêtre d'échéance : du {today.strftime('%d/%m/%Y')} au {target_limit.strftime('%d/%m/%Y')}")

                # 1. Contrats de Location (BVRA / CGL)
                cgls = (
                    CglWaiver.query.filter(
                        CglWaiver.deleted_at.is_(None),
                        CglWaiver.status.in_(["to_send", "to_sign"]),
                    )
                    .options(joinedload(CglWaiver.project).joinedload(Project.production_contact))
                    .all()
                )
                cgl_count = 0
                for cw in cgls:
                    p = cw.project
                    if not p or p.deleted_at is not None:
                        continue
                    start_dates = [d for d in (p.departure_date, p.shoot_start_date) if d]
                    if not start_dates:
                        continue
                    p_start = min(start_dates)
                    end_dates = [d for d in (p.return_date, p.shoot_end_date) if d]
                    p_end = max(end_dates) if end_dates else p_start

                    if p_start <= target_limit and today <= p_end:
                        contact = p.production_contact
                        mail = contact.mail if contact else "AUCUN EMAIL"
                        already = " (déjà relancée aujourd'hui)" if (cw.last_reminded_at and cw.last_reminded_at.date() == today) else ""
                        print(f"   [BVRA] Projet: {p.name} | Contrat: {cw.waiver_id} | Production: {mail} | Départ: {p_start} (Fin: {p_end}){already}")
                        cgl_count += 1

                # 2. Règles de Sécurité Universelles (BVSR)
                safety_rules = (
                    SafetyRulesWaiver.query.filter(
                        SafetyRulesWaiver.deleted_at.is_(None),
                        SafetyRulesWaiver.status.in_(["to_send", "to_sign"]),
                    )
                    .options(joinedload(SafetyRulesWaiver.project))
                    .all()
                )
                safety_count = 0
                for sr in safety_rules:
                    p = sr.project
                    if not p or p.deleted_at is not None:
                        continue
                    start_dates = [d for d in (p.departure_date, p.shoot_start_date) if d]
                    if not start_dates:
                        continue
                    p_start = min(start_dates)
                    end_dates = [d for d in (p.return_date, p.shoot_end_date) if d]
                    p_end = max(end_dates) if end_dates else p_start

                    if p_start <= target_limit and today <= p_end:
                        mail = sr.signer_email or (p.pilot_contact.mail if sr.signer_role == "pilot" and p.pilot_contact else "AUCUN EMAIL")
                        already = " (déjà relancé aujourd'hui)" if (sr.last_reminded_at and sr.last_reminded_at.date() == today) else ""
                        print(f"   [BVSR] Projet: {p.name} | Doc: {sr.waiver_id} | Signataire: {sr.signer_name} ({sr.signer_role}) -> {mail} | Départ: {p_start} (Fin: {p_end}){already}")
                        safety_count += 1

                print(f"[{datetime.now()}] ℹ️ Total éligible : {cgl_count} contrat(s) BVRA, {safety_count} engagement(s) BVSR.")
                return {
                    "cgl_reminders_sent": cgl_count,
                    "safety_rules_reminders_sent": safety_count,
                    "total_reminders_sent": cgl_count + safety_count,
                }

            # Mode envoi normal
            results = auto_remind_pending_waivers(days_before=days_before, base_url=base_url)
            cgl_sent = results.get("cgl_reminders_sent", 0)
            safety_sent = results.get("safety_rules_reminders_sent", 0)
            print(
                f"[{datetime.now()}] ✅ Relances terminées avec succès : "
                f"{cgl_sent} contrat(s) BVRA, {safety_sent} engagement(s) BVSR."
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
