from flask import render_template
from app import create_app
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

# Isolation stricte de l'environnement de test
os.environ["FLASK_ENV"] = "testing"
os.environ["TESTING"] = "True"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["WTF_CSRF_ENABLED"] = "False"
os.environ["USE_SSH_TUNNEL"] = "false"


class EmailTemplatesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def test_magic_link_rendering(self):
        with self.app.app_context():
            html = render_template(
                "emails/magic_link.html",
                firstname="Maxime",
                magic_link="https://bellevitesse.com/admin/login?token=xyz123",
                now_year=2026,
            )
            self.assertIn("Connexion Admin.", html)
            self.assertIn("Bonjour Maxime,", html)
            self.assertIn(
                "https://bellevitesse.com/admin/login?token=xyz123", html)
            self.assertIn("© Belle Vitesse", html)
            self.assertIn("2026", html)

    def test_waiver_invitation_rendering_standard(self):
        with self.app.app_context():
            html = render_template(
                "emails/waiver_invitation.html",
                waiver_type="pilot",
                recipient_name="Luc Pilote",
                project_name="Tournage Pub Vitesse",
                production_name="Studio Test Prod",
                signature_link="https://bellevitesse.com/waivers/pilot/token123",
                is_reminder=False,
                now_year=2026,
            )
            self.assertIn("Signature Décharge Pilote", html)
            self.assertIn("Tournage Pub Vitesse", html)
            self.assertIn("Studio Test Prod", html)
            self.assertIn("info-card info-card-waiver", html)
            self.assertNotIn("project-pill", html)
            self.assertIn(
                "https://bellevitesse.com/waivers/pilot/token123", html)
            self.assertNotIn("Signature en attente", html)

    def test_waiver_invitation_rendering_reminder(self):
        with self.app.app_context():
            html = render_template(
                "emails/waiver_invitation.html",
                waiver_type="production",
                recipient_name="Jean Prod",
                project_name="Film Long Métrage",
                production_name="Studio Grand Angle",
                signature_link="https://bellevitesse.com/waivers/prod/token456",
                is_reminder=True,
                now_year=2026,
            )
            self.assertIn("Rappel : Signature Décharge Production", html)
            self.assertIn("alert-box alert-box-warning", html)
            self.assertIn("Signature en attente", html)
            self.assertIn("Film Long Métrage", html)
            self.assertIn("Studio Grand Angle", html)
            self.assertNotIn("project-pill", html)

    def test_waiver_signed_confirmation_rendering(self):
        with self.app.app_context():
            # Test 1 : Sans waiver_type explicite
            html = render_template(
                "emails/waiver_signed_confirmation.html",
                recipient_name="Jean Dupont",
                project_name="Spot Commercial",
                production_name="Studio Test Prod",
                now_year=2026,
            )
            self.assertIn("Décharge Signée.", html)
            self.assertIn("info-card info-card-waiver", html)
            self.assertIn("Spot Commercial", html)
            self.assertIn("Studio Test Prod", html)
            self.assertIn("Jean Dupont", html)
            self.assertIn("badge-success", html)
            self.assertNotIn("project-pill", html)
            self.assertNotIn("<strong>Type de décharge :</strong> </div>", html)

            # Test 2 : Avec waiver_type='production'
            html_prod = render_template(
                "emails/waiver_signed_confirmation.html",
                recipient_name="Claire Martin",
                project_name="Spot Commercial",
                production_name="Studio Test Prod",
                waiver_type="production",
                now_year=2026,
            )
            self.assertIn("Claire Martin", html_prod)
            self.assertIn("Type de décharge :", html_prod)
            self.assertIn("Production", html_prod)

    def test_incident_invitation_rendering(self):
        with self.app.app_context():
            html = render_template(
                "emails/incident_invitation.html",
                project_name="Clip Rap Paris",
                production_name="Studio Test Prod",
                recipient_name="Maxime Test",
                incident_number="INC-2026-0042",
                incident_title="Impact carrosserie aile arrière",
                incident_date="22/09/2026",
                location="Circuit Jean Behra",
                signature_link="https://bellevitesse.com/incidents/sign/token789",
                now_year=2026,
            )
            self.assertIn("Signature Constat d'Incident.", html)
            self.assertIn("info-card info-card-incident", html)
            self.assertIn("Clip Rap Paris", html)
            self.assertIn("Studio Test Prod", html)
            self.assertIn("INC-2026-0042", html)
            self.assertIn("Impact carrosserie aile arrière", html)
            self.assertIn("22/09/2026", html)
            self.assertIn("Circuit Jean Behra", html)
            self.assertIn("badge-warning", html)
            self.assertNotIn("project-pill", html)

    def test_incident_signed_confirmation_rendering(self):
        with self.app.app_context():
            html = render_template(
                "emails/incident_signed_confirmation.html",
                project_name="Clip Rap Paris",
                production_name="Studio Test Prod",
                recipient_name="Maxime Test",
                incident_number="INC-2026-0042",
                incident_title="Impact carrosserie aile arrière",
                incident_date="22/09/2026",
                location="Circuit Jean Behra",
                now_year=2026,
            )
            self.assertIn("Constat d'Incident Scellé.", html)
            self.assertIn("info-card info-card-incident", html)
            self.assertIn("Clip Rap Paris", html)
            self.assertIn("Studio Test Prod", html)
            self.assertIn("INC-2026-0042", html)
            self.assertIn("22/09/2026", html)
            self.assertIn("Circuit Jean Behra", html)
            self.assertIn("badge-success", html)
            self.assertNotIn("project-pill", html)

    def test_calendar_invitation_rendering(self):
        with self.app.app_context():
            html = render_template(
                "emails/calendar_invitation.html",
                user_name="Maxime",
                feed_url="https://bellevitesse.com/calendar/feed.ics?token=cal123",
                webcal_url="webcal://bellevitesse.com/calendar/feed.ics?token=cal123",
                qrcode_base64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
                now_year=2026,
            )
            self.assertIn("Calendrier Projets.", html)
            self.assertIn("qr-code-box", html)
            self.assertIn("instructions-card", html)
            self.assertIn(
                "webcal://bellevitesse.com/calendar/feed.ics?token=cal123", html)
            self.assertIn("blanc-fond-transparent.png", html)

    def test_newsletter_welcome_rendering(self):
        with self.app.app_context():
            html = render_template(
                "emails/newsletter_welcome.html",
                unsubscribe_url="https://bellevitesse.com/unsubscribe/token_abc",
                now_year=2026,
            )
            self.assertIn("Bienvenue chez Belle Vitesse.", html)
            self.assertIn(
                "https://bellevitesse.com/unsubscribe/token_abc", html)
            self.assertIn("© Belle Vitesse", html)
            self.assertIn("2026", html)

    def test_company_settings_dynamic_in_email(self):
        """Vérifie que les coordonnées société définies dans app_settings sont bien injectées dans le footer des emails."""
        with self.app.app_context():
            html = render_template(
                "emails/magic_link.html",
                firstname="Maxime",
                magic_link="https://bellevitesse.com/admin/login?token=xyz123",
                now_year=2026,
            )
            self.assertIn("39 rue Maurice Gunsbourg", html)
            self.assertIn("94200 Ivry-sur-Seine", html)
            self.assertIn("contact@bellevitesse.com", html)

    def test_newsletter_campaign_rendering(self):
        with self.app.app_context():
            html = render_template(
                "emails/newsletter_campaign.html",
                subject="Nouvelle Grue Télescopique en Flotte",
                body="Nous avons le plaisir d'accueillir un nouveau matériel.\n\nVenez découvrir ses spécifications techniques.",
                unsubscribe_url="https://bellevitesse.com/unsubscribe/token_xyz",
                now_year=2026,
            )
            self.assertIn("Nouvelle Grue Télescopique en Flotte", html)
            self.assertIn("Nous avons le plaisir d'accueillir", html)
            self.assertIn(
                "https://bellevitesse.com/unsubscribe/token_xyz", html)
            self.assertIn("content-left", html)

    def test_sql_alert_rendering(self):
        with self.app.app_context():
            html = render_template(
                "emails/sql_alert.html",
                total_alerts=1,
                date_str="22/09/2026",
                time_str="17:00:00",
                alerts=[
                    {
                        "subject": "Tentative de suppression sur table critique",
                        "body": "Utilisateur suspect sur IP 1.2.3.4 : DROP TABLE test;",
                    }
                ],
                now_year=2026,
            )
            self.assertIn("Alerte de Sécurité SQL", html)
            self.assertIn("1 anomalie(s)", html)
            self.assertIn("Tentative de suppression sur table critique", html)
            self.assertIn("alert-box alert-box-warning", html)

    def test_cron_report_rendering(self):
        with self.app.app_context():
            html = render_template(
                "emails/cron_report.html",
                jobs=[
                    {
                        "display_name": "Sauvegarde SQL",
                        "expected_freq": "Tous les jours à 4h00",
                        "last_run_display": "22/09/2026 à 04:00:00",
                        "status": "success",
                    }
                ],
                failures=[],
                global_status="OK",
                date_str="22/09/2026",
                time_str="08:00:00",
                now_year=2026,
            )
            self.assertIn("Statut Quotidien des Tâches Planifiées", html)
            self.assertIn("email-table", html)
            self.assertIn("Dernière exécution", html)
            self.assertNotIn("Dernière exécution (UTC)", html)
            self.assertIn("status-ok", html)


if __name__ == "__main__":
    unittest.main()
