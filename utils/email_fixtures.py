"""
utils/email_fixtures.py
Centralisation canonique des données de démo et de test pour les e-mails transactionnels.
Partagé entre les routes de prévisualisation web (/temp-email-preview) et le script CLI (send_test_emails.py).
"""
from datetime import datetime, timezone


def get_demo_email_data(mail_type: str) -> dict:
    """
    Retourne la configuration canonique (template, context, subject) pour un type d'e-mail donné.
    Retourne None si le type est inconnu.
    """
    now_year = datetime.now(timezone.utc).year
    m = (mail_type or "").lower().strip()

    if m in ("all-badges", "all_badges", "badges", "showcase"):
        return {
            "template": "emails/showcase_badges.html",
            "subject": "Nuancier Complet des Badges — Belle Vitesse",
            "context": {"now_year": now_year},
        }

    if m in ("waiver", "decharge", "waiver_signed"):
        return {
            "template": "emails/waiver_signed_confirmation.html",
            "subject": "Décharge signée - Tournage Porsche 911 GT3 RS",
            "context": {
                "recipient_name": "Maxime Congi",
                "display_name": "Maxime Congi",
                "project_name": "Tournage Porsche 911 GT3 RS",
                "production_name": "Studio Transatlantique",
                "waiver_type": "pilot",
                "type_title": "Pilote",
                "now_year": now_year,
            },
        }

    if m in ("waiver_invitation", "waiver_pilot"):
        return {
            "template": "emails/waiver_invitation.html",
            "subject": "Signature décharge pilote - Tournage Porsche 911 GT3 RS",
            "context": {
                "waiver_type": "pilot",
                "recipient_name": "Maxime Congi",
                "display_name": "Maxime Congi",
                "project_name": "Tournage Porsche 911 GT3 RS",
                "production_name": "Studio Transatlantique",
                "signature_link": "https://bellevitesse.com/waivers/pilot/demo_token",
                "is_reminder": False,
                "now_year": now_year,
            },
        }

    if m in ("waiver_reminder", "waiver_pilot_reminder"):
        return {
            "template": "emails/waiver_invitation.html",
            "subject": "Rappel : Signature décharge pilote - Tournage Porsche 911 GT3 RS",
            "context": {
                "waiver_type": "pilot",
                "recipient_name": "Maxime Congi",
                "display_name": "Maxime Congi",
                "project_name": "Tournage Porsche 911 GT3 RS",
                "production_name": "Studio Transatlantique",
                "signature_link": "https://bellevitesse.com/waivers/pilot/demo_token",
                "is_reminder": True,
                "now_year": now_year,
            },
        }

    if m in ("incident", "incident_signed"):
        return {
            "template": "emails/incident_signed_confirmation.html",
            "subject": "Constat scellé et signé - INC-2026-0008 (Tournage Nocturne Paris)",
            "context": {
                "recipient_name": "Maxime Congi",
                "project_name": "Tournage Nocturne Paris",
                "production_name": "Iconoclast Films",
                "incident_number": "INC-2026-0008",
                "incident_date": "22/09/2026",
                "location": "Pont de Bir-Hakeim, Paris",
                "incident_title": "Frottement splitter carbone et fixation camera-car",
                "now_year": now_year,
            },
        }

    if m in ("incident_invitation", "incident_visa"):
        return {
            "template": "emails/incident_invitation.html",
            "subject": "Action requise : Visa du constat d'incident INC-2026-0008 (Tournage Nocturne Paris)",
            "context": {
                "recipient_name": "Maxime Congi",
                "project_name": "Tournage Nocturne Paris",
                "production_name": "Iconoclast Films",
                "incident_number": "INC-2026-0008",
                "incident_title": "Frottement splitter carbone et fixation camera-car",
                "incident_date": "22/09/2026",
                "location": "Pont de Bir-Hakeim, Paris",
                "signature_link": "https://bellevitesse.com/incidents/sign/demo_token",
                "now_year": now_year,
            },
        }

    if m in ("cron", "cron_report"):
        return {
            "template": "emails/cron_report.html",
            "subject": "Statut Quotidien des Tâches Planifiées — Belle Vitesse",
            "context": {
                "global_status": "OK",
                "date_str": "22/09/2026",
                "time_str": "18:30:00",
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
                        "status": "failed",
                    },
                    {
                        "display_name": "Relance automatique des décharges",
                        "expected_freq": "Tous les jours à 8h00",
                        "last_run_display": "22/09/2026 à 08:00:02",
                        "status": "stale",
                    },
                    {
                        "display_name": "Nettoyage dossiers vides Serveur",
                        "expected_freq": "Tous les lundis à 3h45",
                        "last_run_display": "22/09/2026 à 03:45:01",
                        "status": "missing",
                    },
                ],
                "failures": [],
                "now_year": now_year,
            },
        }

    if m in ("calendar", "calendar_invitation"):
        return {
            "template": "emails/calendar_invitation.html",
            "subject": "Votre calendrier des projets Belle Vitesse",
            "context": {
                "user_name": "Maxime Congi",
                "feed_url": "https://bellevitesse.com/calendar/feed.ics?token=demo_token",
                "webcal_url": "webcal://bellevitesse.com/calendar/feed.ics?token=demo_token",
                "qrcode_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
                "now_year": now_year,
            },
        }

    return None
