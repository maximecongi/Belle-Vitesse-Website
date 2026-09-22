import base64
from datetime import datetime, timezone
import io
import os
from pathlib import Path
import sys
import time

from dotenv import load_dotenv
from flask import Flask
import qrcode

# Set up paths
_root = Path(__file__).resolve().parent.parent
sys.path.append(str(_root))

# Load environment
load_dotenv(_root / ".env")

# Ensure testing interception is disabled so real SMTP sends happen
os.environ.pop("FLASK_ENV", None)
os.environ.pop("TESTING", None)

from utils.mailer import EmailService

DEST_EMAIL = "maxime@bellevitesse.com"


def generate_qr_code(data_str: str) -> str:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data_str)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()


def get_all_test_emails():
    now_year = datetime.now(timezone.utc).year
    feed_url = "https://bellevitesse.com/calendar/feed.ics?token=demo_test_token"
    webcal_url = "webcal://bellevitesse.com/calendar/feed.ics?token=demo_test_token"
    qr_b64 = generate_qr_code(webcal_url)

    emails = [
        # 1. Connexion Admin (Magic link)
        {
            "name": "1. Connexion Admin (Magic Link)",
            "subject": "[TEST 1/13] Connexion à Belle Vitesse",
            "template": "emails/magic_link.html",
            "context": {
                "firstname": "Maxime",
                "magic_link": "https://bellevitesse.com/admin/login?token=demo_magic_token",
                "now_year": now_year,
            },
            "sender_type": "admin",
        },
        # 2. Invitation Décharge Pilote
        {
            "name": "2. Invitation Décharge Pilote (Standard)",
            "subject": "[TEST 2/13] Signature décharge pilote - Tournage Porsche 911 GT3 RS",
            "template": "emails/waiver_invitation.html",
            "context": {
                "waiver_type": "pilot",
                "recipient_name": "Maxime Congi",
                "project_name": "Tournage Porsche 911 GT3 RS",
                "signature_link": "https://bellevitesse.com/waivers/pilot/demo_token",
                "is_reminder": False,
                "now_year": now_year,
            },
            "sender_type": "admin",
        },
        # 3. Rappel Décharge Pilote (Relance J-1)
        {
            "name": "3. Relance Décharge Pilote (Rappel J-1)",
            "subject": "[TEST 3/13] Rappel : Signature décharge pilote - Tournage Porsche 911 GT3 RS",
            "template": "emails/waiver_invitation.html",
            "context": {
                "waiver_type": "pilot",
                "recipient_name": "Maxime Congi",
                "project_name": "Tournage Porsche 911 GT3 RS",
                "signature_link": "https://bellevitesse.com/waivers/pilot/demo_token",
                "is_reminder": True,
                "now_year": now_year,
            },
            "sender_type": "admin",
        },
        # 4. Invitation Décharge Production
        {
            "name": "4. Invitation Décharge Production (Standard)",
            "subject": '[TEST 4/13] Signature décharge production - Spot TV Chanel No 5',
            "template": "emails/waiver_invitation.html",
            "context": {
                "waiver_type": "production",
                "recipient_name": "Maxime Congi (Prod)",
                "project_name": "Spot TV Chanel No 5",
                "signature_link": "https://bellevitesse.com/waivers/production/demo_token",
                "is_reminder": False,
                "now_year": now_year,
            },
            "sender_type": "admin",
        },
        # 5. Rappel Décharge Production (Relance J-1)
        {
            "name": "5. Relance Décharge Production (Rappel J-1)",
            "subject": '[TEST 5/13] Rappel : Signature décharge production - Spot TV Chanel No 5',
            "template": "emails/waiver_invitation.html",
            "context": {
                "waiver_type": "production",
                "recipient_name": "Maxime Congi (Prod)",
                "project_name": "Spot TV Chanel No 5",
                "signature_link": "https://bellevitesse.com/waivers/production/demo_token",
                "is_reminder": True,
                "now_year": now_year,
            },
            "sender_type": "admin",
        },
        # 6. Confirmation Décharge Signée
        {
            "name": "6. Confirmation Décharge Signée (PDF)",
            "subject": "[TEST 6/13] Décharge signée - Tournage Porsche 911 GT3 RS",
            "template": "emails/waiver_signed_confirmation.html",
            "context": {
                "recipient_name": "Maxime Congi",
                "project_name": "Tournage Porsche 911 GT3 RS",
                "now_year": now_year,
            },
            "sender_type": "contact",
        },
        # 7. Invitation Signature Constat d'Incident
        {
            "name": "7. Invitation Constat d'Incident",
            "subject": "[TEST 7/13] Action requise : Visa du constat d'incident INC-2026-0008 (Tournage Nocturne Paris)",
            "template": "emails/incident_invitation.html",
            "context": {
                "project_name": "Tournage Nocturne Paris",
                "incident_number": "INC-2026-0008",
                "incident_title": "Frottement splitter carbone et fixation camera-car",
                "incident_date": "22/09/2026",
                "location": "Pont de Bir-Hakeim, Paris",
                "signature_link": "https://bellevitesse.com/incidents/sign/demo_token",
                "now_year": now_year,
            },
            "sender_type": "admin",
        },
        # 8. Confirmation Constat d'Incident Scellé
        {
            "name": "8. Confirmation Constat Scellé",
            "subject": "[TEST 8/13] Constat scellé et signé - INC-2026-0008 (Tournage Nocturne Paris)",
            "template": "emails/incident_signed_confirmation.html",
            "context": {
                "project_name": "Tournage Nocturne Paris",
                "incident_number": "INC-2026-0008",
                "incident_title": "Frottement splitter carbone et fixation camera-car",
                "now_year": now_year,
            },
            "sender_type": "contact",
        },
        # 9. Invitation Calendrier (avec QR code)
        {
            "name": "9. Invitation Synchronisation Calendrier",
            "subject": "[TEST 9/13] Votre calendrier Belle Vitesse",
            "template": "emails/calendar_invitation.html",
            "context": {
                "user_name": "Maxime Congi",
                "feed_url": feed_url,
                "webcal_url": webcal_url,
                "qrcode_base64": qr_b64,
                "now_year": now_year,
            },
            "sender_type": "admin",
        },
        # 10. Bienvenue Newsletter
        {
            "name": "10. Bienvenue Newsletter",
            "subject": "[TEST 10/13] Bienvenue chez Belle Vitesse",
            "template": "emails/newsletter_welcome.html",
            "context": {
                "unsubscribe_url": "https://bellevitesse.com/unsubscribe/demo_token",
                "now_year": now_year,
            },
            "sender_type": "contact",
        },
        # 11. Campagne Newsletter Marketing
        {
            "name": "11. Campagne Newsletter Marketing",
            "subject": "[TEST 11/13] Nouveauté Flotte : Caméra Car Haute Vitesse & Tête Gyrostabilisée",
            "template": "emails/newsletter_campaign.html",
            "context": {
                "subject": "Nouveauté Flotte : Caméra Car Haute Vitesse & Tête Gyrostabilisée",
                "body": (
                    "Toute l'équipe Belle Vitesse est fière de vous présenter l'arrivée de notre nouvelle configuration ultra-légère "
                    "pour les prises de vues dynamiques en milieu urbain et sur piste.\n\n"
                    "Doté des dernières technologies d'amortissement actif et d'une motorisation électrique silencieuse, "
                    "ce véhicule permet des mouvements de caméra d'une fluidité exceptionnelle jusqu'à 160 km/h.\n\n"
                    "Contactez notre équipe de coordination pour réserver vos dates de tournage."
                ),
                "unsubscribe_url": "https://bellevitesse.com/unsubscribe/demo_token",
                "now_year": now_year,
            },
            "sender_type": "contact",
        },
        # 12. Alerte de Sécurité SQL
        {
            "name": "12. Alerte de Sécurité SQL",
            "subject": "[TEST 12/13] [ALERTE SQL] 2 anomalie(s) détectée(s)",
            "template": "emails/sql_alert.html",
            "context": {
                "total_alerts": 2,
                "date_str": "22/09/2026",
                "time_str": "17:35:00",
                "alerts": [
                    {
                        "subject": "Modification directe de table sensible 'users'",
                        "body": "L'utilisateur dev_user (IP: 82.64.12.34, Paris FR) a modifié la table 'users'.\nRequête : UPDATE users SET role = 'administrator' WHERE id = 4;",
                    },
                    {
                        "subject": "Activité SQL anormale hors bureau",
                        "body": "L'utilisateur system_batch (IP: 195.154.80.12) a exécuté 142 requêtes SQL suspectes.",
                    },
                ],
                "now_year": now_year,
            },
            "sender_type": "admin",
        },
        # 13. Rapport Quotidien des Tâches Planifiées (Cron)
        {
            "name": "13. Rapport Quotidien des Crons",
            "subject": "[TEST 13/13] [CRON SUCCESS] Rapport quotidien des tâches planifiées — 22/09/2026",
            "template": "emails/cron_report.html",
            "context": {
                "global_status": "OK",
                "date_str": "22/09/2026",
                "time_str": "08:00:00",
                "jobs": [
                    {
                        "display_name": "Sauvegarde Base de Données SQL",
                        "expected_freq": "Tous les jours à 4h00",
                        "last_run_display": "22/09/2026 à 04:00:01",
                        "status": "success",
                    },
                    {
                        "display_name": "Purge des logs SQL (60 jours)",
                        "expected_freq": "Tous les jours à 5h00",
                        "last_run_display": "22/09/2026 à 05:00:02",
                        "status": "success",
                    },
                    {
                        "display_name": "Alerte Anomalies SQL",
                        "expected_freq": "Toutes les 5 minutes",
                        "last_run_display": "22/09/2026 à 07:55:02",
                        "status": "success",
                    },
                    {
                        "display_name": "Vérification et réconciliation kDrive",
                        "expected_freq": "Tous les jours à 4h30",
                        "last_run_display": "22/09/2026 à 04:30:00",
                        "status": "success",
                    },
                    {
                        "display_name": "Nettoyage dossiers vides Serveur",
                        "expected_freq": "Tous les lundis à 3h45",
                        "last_run_display": "22/09/2026 à 03:45:01",
                        "status": "success",
                    },
                    {
                        "display_name": "Relance automatique des décharges (48h avant)",
                        "expected_freq": "Tous les jours à 8h00",
                        "last_run_display": "22/09/2026 à 08:00:02",
                        "status": "success",
                    },
                ],
                "failures": [],
                "now_year": now_year,
            },
            "sender_type": "admin",
        },
    ]
    return emails


def main():
    print(f"\n🚀 Démarrage de l'envoi des 13 templates d'e-mails vers {DEST_EMAIL}...\n")
    from app import create_app
    app = create_app()

    emails = get_all_test_emails()
    success_count = 0
    failure_count = 0

    with app.app_context():
        for i, item in enumerate(emails, 1):
            print(f"[{i}/{len(emails)}] Envoi de : {item['name']}...")
            try:
                ok = EmailService.send_templated_email(
                    to_email=DEST_EMAIL,
                    subject=item["subject"],
                    template_name=item["template"],
                    context=item["context"],
                    sender_type=item["sender_type"],
                    timeout=15,
                )
                if ok:
                    print(f"   ✅ Succès : '{item['subject']}'")
                    success_count += 1
                else:
                    print(f"   ❌ Échec pour : '{item['name']}'")
                    failure_count += 1
            except Exception as e:
                print(f"   ❌ Erreur d'envoi : {e}")
                failure_count += 1

            # Pause d'une seconde pour respecter le serveur SMTP
            time.sleep(1)

    print(f"\n🏁 Terminé : {success_count} envoyés avec succès, {failure_count} échec(s).\n")


if __name__ == "__main__":
    main()
