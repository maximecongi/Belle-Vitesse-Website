import json
import os
import unittest
from datetime import date, timedelta
from unittest.mock import patch

# Isolation stricte de l'environnement de test avant tout import d'app
os.environ["FLASK_ENV"] = "testing"
os.environ["TESTING"] = "True"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["WTF_CSRF_ENABLED"] = "False"
os.environ["USE_SSH_TUNNEL"] = "false"

from app import create_app
from models import Contact, PilotWaiver, Production, ProductionWaiver, Project, db
from services.admin.waivers import auto_remind_pending_waivers


class WaiversRemindersTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

            # Création de contacts et production
            self.prod = Production(name="Prod Relance Test")
            db.session.add(self.prod)
            db.session.commit()

            self.contact_prod = Contact(
                first_name="Jean",
                last_name="Dupont",
                mail="jean.dupont@example.com",
                job_title="production",
            )
            self.contact_pilot = Contact(
                first_name="Luc",
                last_name="Pilote",
                mail="luc.pilote@example.com",
                job_title="pilote",
            )
            db.session.add_all([self.contact_prod, self.contact_pilot])
            db.session.commit()

            # Projet partant demain (J+1)
            tomorrow = date.today() + timedelta(days=1)
            end_date = tomorrow + timedelta(days=3)

            self.project = Project(
                name="Tournage Urgent J-1",
                production_id=self.prod.id,
                production_contact_id=self.contact_prod.id,
                pilot_contact_id=self.contact_pilot.id,
                departure_date=tomorrow,
                return_date=end_date,
            )
            db.session.add(self.project)
            db.session.commit()

            # Décharges non signées
            self.pw = ProductionWaiver(
                project_id=self.project.id,
                status="to_sign",
            )
            self.dw = PilotWaiver(
                project_id=self.project.id,
                status="to_send",
            )
            db.session.add_all([self.pw, self.dw])
            db.session.commit()

            self.project_id = self.project.id
            self.pw_id = self.pw.id
            self.dw_id = self.dw.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    @patch("utils.mailer.send_production_waiver_invitation_email", return_value=True)
    @patch("utils.mailer.send_waiver_invitation_email", return_value=True)
    def test_auto_remind_pending_waivers_service(self, mock_pilot_mail, mock_prod_mail):
        """Vérifie que le service de relance détecte les décharges J-1 et incrémente le compteur."""
        with self.app.app_context():
            res = auto_remind_pending_waivers(days_before=2, base_url="http://testserver")
            self.assertEqual(res["production_reminders_sent"], 1)
            self.assertEqual(res["pilot_reminders_sent"], 1)

            # Vérification des arguments d'appel mail avec is_reminder=True
            mock_prod_mail.assert_called_once()
            _, prod_kwargs = mock_prod_mail.call_args
            self.assertTrue(prod_kwargs.get("is_reminder"))

            mock_pilot_mail.assert_called_once()
            _, pilot_kwargs = mock_pilot_mail.call_args
            self.assertTrue(pilot_kwargs.get("is_reminder"))

            # Vérification de l'état en base
            pw = db.session.get(ProductionWaiver, self.pw_id)
            dw = db.session.get(PilotWaiver, self.dw_id)
            self.assertEqual(pw.reminder_count, 1)
            self.assertIsNotNone(pw.last_reminded_at)
            self.assertEqual(dw.reminder_count, 1)
            self.assertEqual(dw.status, "to_sign")

            # Une seconde exécution immédiate le même jour ne doit pas renvoyer
            res2 = auto_remind_pending_waivers(days_before=2, base_url="http://testserver")
            self.assertEqual(res2["production_reminders_sent"], 0)
            self.assertEqual(res2["pilot_reminders_sent"], 0)

    @patch("utils.mailer.send_production_waiver_invitation_email", return_value=True)
    @patch("utils.mailer.send_waiver_invitation_email", return_value=True)
    def test_manual_send_waiver_reminder(self, mock_pilot_mail, mock_prod_mail):
        """Vérifie que l'envoi manuel depuis l'admin détecte la relance si déjà envoyé/to_sign."""
        from services.admin.waivers import send_production_waiver, send_pilot_waiver

        with self.app.app_context():
            # pw est déjà à to_sign -> doit être comptabilisé comme relance
            success, flash_msg = send_production_waiver(self.pw_id, base_url="http://testserver")
            self.assertTrue(success)
            self.assertIn("Relance envoyée", flash_msg)
            pw = db.session.get(ProductionWaiver, self.pw_id)
            self.assertEqual(pw.reminder_count, 1)
            self.assertIsNotNone(pw.last_reminded_at)
            _, prod_kwargs = mock_prod_mail.call_args
            self.assertTrue(prod_kwargs.get("is_reminder"))

            # dw est à to_send -> premier envoi
            success_p, flash_msg_p = send_pilot_waiver(self.dw_id, base_url="http://testserver")
            self.assertTrue(success_p)
            self.assertIn("Décharge envoyée", flash_msg_p)
            dw = db.session.get(PilotWaiver, self.dw_id)
            self.assertEqual(dw.reminder_count, 0)
            _, pilot_kwargs = mock_pilot_mail.call_args
            self.assertFalse(pilot_kwargs.get("is_reminder"))

            # Deuxième envoi manuel sur dw (maintenant to_sign) -> doit être une relance
            success_p2, flash_msg_p2 = send_pilot_waiver(self.dw_id, base_url="http://testserver")
            self.assertTrue(success_p2)
            self.assertIn("Relance envoyée", flash_msg_p2)
            dw2 = db.session.get(PilotWaiver, self.dw_id)
            self.assertEqual(dw2.reminder_count, 1)
            self.assertIsNotNone(dw2.last_reminded_at)

    @patch("utils.mailer.send_production_waiver_invitation_email", return_value=True)
    @patch("utils.mailer.send_waiver_invitation_email", return_value=True)
    def test_script_remind_waivers_dry_run(self, mock_pilot_mail, mock_prod_mail):
        """Vérifie le fonctionnement du script scripts/remind_waivers.py en mode dry-run."""
        from scripts.remind_waivers import run_reminders

        # En mockant build_minimal_app pour retourner self.app et None
        with patch("scripts.remind_waivers.build_minimal_app", return_value=(self.app, None)):
            res = run_reminders(days_before=2, dry_run=True)
            self.assertEqual(res["production_reminders_sent"], 1)
            self.assertEqual(res["pilot_reminders_sent"], 1)
            # En mode dry-run, aucun mail n'est envoyé
            mock_pilot_mail.assert_not_called()
            mock_prod_mail.assert_not_called()

    @patch("utils.mailer.EmailService._send_smtp_message", return_value=True)
    def test_mailer_invitation_reminder_content(self, mock_send_smtp):
        """Vérifie que les emails d'invitation avec is_reminder=True portent l'objet et le bandeau de relance."""
        from utils.mailer import send_waiver_invitation_email, send_production_waiver_invitation_email

        with self.app.app_context():
            # Email pilote
            ok_pilot = send_waiver_invitation_email(
                to_email="test.pilot@example.com",
                pilot_name="Pilote Test",
                project_name="Projet Alpha",
                signature_link="http://localhost:5000/sign/waiver/abc",
                is_reminder=True,
            )
            self.assertTrue(ok_pilot)
            msg_pilot = mock_send_smtp.call_args[0][0]
            self.assertIn("Rappel : Signature décharge pilote - Projet Alpha", msg_pilot["Subject"])
            pilot_payloads = [part.get_payload(decode=True).decode('utf-8') for part in msg_pilot.get_payload()]
            pilot_full_text = "\n".join(pilot_payloads)
            self.assertIn("RAPPEL : Le tournage approche", pilot_full_text)
            self.assertIn("Signature en attente", pilot_full_text)

            mock_send_smtp.reset_mock()

            # Email production
            ok_prod = send_production_waiver_invitation_email(
                to_email="test.prod@example.com",
                prod_contact_name="Prod Contact",
                project_name="Projet Beta",
                signature_link="http://localhost:5000/sign/production-waiver/xyz",
                is_reminder=True,
            )
            self.assertTrue(ok_prod)
            msg_prod = mock_send_smtp.call_args[0][0]
            self.assertIn("Rappel : Signature décharge production - Projet Beta", msg_prod["Subject"])
            prod_payloads = [part.get_payload(decode=True).decode('utf-8') for part in msg_prod.get_payload()]
            prod_full_text = "\n".join(prod_payloads)
            self.assertIn("RAPPEL : Le tournage approche", prod_full_text)
            self.assertIn("Signature en attente", prod_full_text)

    @patch("utils.mailer.EmailService._send_smtp_message", return_value=True)
    def test_send_templated_email_with_attachments_and_headers(self, mock_send_smtp):
        """Vérifie le bon fonctionnement du helper générique EmailService.send_templated_email."""
        import tempfile
        from utils.mailer import EmailService

        with self.app.app_context():
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
                tmp_pdf.write(b"%PDF-1.4 mock content")
                tmp_pdf_path = tmp_pdf.name

            try:
                ok = EmailService.send_templated_email(
                    to_email="client@example.com",
                    subject="Test Templated",
                    template_name="emails/waiver_signed_confirmation.html",
                    context={"recipient_name": "Client Test", "project_name": "Projet PDF"},
                    text_content="Texte de secours brut",
                    sender_type="admin",
                    cc=["admin1@example.com", "admin2@example.com"],
                    attachments=[tmp_pdf_path],
                    extra_headers={"X-Custom-Header": "TestValue"},
                )
                self.assertTrue(ok)
                mock_send_smtp.assert_called_once()
                msg, recipients, kwargs = mock_send_smtp.call_args[0][0], mock_send_smtp.call_args[0][1], mock_send_smtp.call_args[1]

                self.assertEqual(msg["Subject"], "Test Templated")
                self.assertEqual(msg["To"], "client@example.com")
                self.assertIn("admin1@example.com", msg["Cc"])
                self.assertEqual(msg["X-Custom-Header"], "TestValue")
                self.assertEqual(recipients, ["client@example.com", "admin1@example.com", "admin2@example.com"])
                self.assertEqual(kwargs.get("sender_type"), "admin")
                self.assertEqual(msg.get_content_type(), "multipart/mixed")
            finally:
                if os.path.exists(tmp_pdf_path):
                    os.remove(tmp_pdf_path)


if __name__ == "__main__":
    unittest.main()
