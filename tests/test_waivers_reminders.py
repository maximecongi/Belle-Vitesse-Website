import json
import os
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

# Isolation stricte de l'environnement de test avant tout import d'app
os.environ["FLASK_ENV"] = "testing"
os.environ["TESTING"] = "True"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["WTF_CSRF_ENABLED"] = "False"
os.environ["USE_SSH_TUNNEL"] = "false"

from app import create_app
from models import Contact, CglWaiver, SafetyRulesWaiver, Production, Project, db
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
            tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
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

            # CGL et Règles de sécurité non signées
            self.cgl = CglWaiver(
                project_id=self.project.id,
                status="to_sign",
            )
            self.bvsr = SafetyRulesWaiver(
                project_id=self.project.id,
                signer_role="pilot",
                signer_first_name="Luc",
                signer_last_name="Pilote",
                signer_email="luc.pilote@example.com",
                status="to_send",
            )
            db.session.add_all([self.cgl, self.bvsr])
            db.session.commit()

            self.prod_id = self.prod.id
            self.contact_prod_id = self.contact_prod.id
            self.contact_pilot_id = self.contact_pilot.id
            self.project_id = self.project.id
            self.cgl_id = self.cgl.id
            self.bvsr_id = self.bvsr.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    @patch("utils.mailer.send_cgl_invitation_email", return_value=True)
    @patch("utils.mailer.send_safety_rules_invitation_email", return_value=True)
    def test_auto_remind_pending_waivers_service(self, mock_bvsr_mail, mock_cgl_mail):
        """Vérifie que le service de relance détecte les CGL et BVSR J-1 et incrémente le compteur."""
        with self.app.app_context():
            res = auto_remind_pending_waivers(days_before=2, base_url="http://testserver")
            self.assertEqual(res["cgl_reminders_sent"], 1)
            self.assertEqual(res["safety_rules_reminders_sent"], 1)

            # Vérification des arguments d'appel mail avec is_reminder=True
            mock_cgl_mail.assert_called_once()
            _, cgl_kwargs = mock_cgl_mail.call_args
            self.assertTrue(cgl_kwargs.get("is_reminder"))

            mock_bvsr_mail.assert_called_once()
            _, bvsr_kwargs = mock_bvsr_mail.call_args
            self.assertTrue(bvsr_kwargs.get("is_reminder"))

            # Vérification de l'état en base
            cw = db.session.get(CglWaiver, self.cgl_id)
            sr = db.session.get(SafetyRulesWaiver, self.bvsr_id)
            self.assertEqual(cw.reminder_count, 1)
            self.assertIsNotNone(cw.last_reminded_at)
            self.assertEqual(sr.reminder_count, 1)
            self.assertEqual(sr.status, "to_sign")

            # Une seconde exécution immédiate le même jour ne doit pas renvoyer
            res2 = auto_remind_pending_waivers(days_before=2, base_url="http://testserver")
            self.assertEqual(res2["cgl_reminders_sent"], 0)
            self.assertEqual(res2["safety_rules_reminders_sent"], 0)

    @patch("utils.mailer.send_cgl_invitation_email", return_value=True)
    @patch("utils.mailer.send_safety_rules_invitation_email", return_value=True)
    def test_auto_remind_ongoing_shoot_after_departure(self, mock_bvsr_mail, mock_cgl_mail):
        """Vérifie que les CGL et BVSR non signés sont relancés si départ passé mais tournage en cours."""
        with self.app.app_context():
            yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
            future_return = datetime.now(timezone.utc).date() + timedelta(days=2)

            # Projet en cours : départ hier, retour dans 2 jours
            p_ongoing = Project(
                name="Tournage En Cours",
                production_id=self.prod_id,
                production_contact_id=self.contact_prod_id,
                pilot_contact_id=self.contact_pilot_id,
                departure_date=yesterday,
                return_date=future_return,
            )
            db.session.add(p_ongoing)
            db.session.commit()

            cgl_ongoing = CglWaiver(project_id=p_ongoing.id, status="to_sign")
            bvsr_ongoing = SafetyRulesWaiver(
                project_id=p_ongoing.id,
                signer_role="pilot",
                signer_first_name="Luc",
                signer_last_name="Pilote",
                signer_email="luc.pilote@example.com",
                status="to_sign",
            )
            db.session.add_all([cgl_ongoing, bvsr_ongoing])
            db.session.commit()

            # Projet passé et achevé : retour hier
            p_past = Project(
                name="Tournage Passé Terminé",
                production_id=self.prod_id,
                production_contact_id=self.contact_prod_id,
                pilot_contact_id=self.contact_pilot_id,
                departure_date=yesterday - timedelta(days=3),
                return_date=yesterday,
            )
            db.session.add(p_past)
            db.session.commit()

            cgl_past = CglWaiver(project_id=p_past.id, status="to_sign")
            bvsr_past = SafetyRulesWaiver(
                project_id=p_past.id,
                signer_role="pilot",
                signer_first_name="Luc",
                signer_last_name="Pilote",
                signer_email="luc.pilote@example.com",
                status="to_sign",
            )
            db.session.add_all([cgl_past, bvsr_past])
            db.session.commit()

            res = auto_remind_pending_waivers(days_before=2, base_url="http://testserver")

            # self.project (J-1) + p_ongoing (départ hier, retour J+2) doivent être relancés = 2
            # p_past (retour hier) ne doit PAS être relancé
            self.assertEqual(res["cgl_reminders_sent"], 2)
            self.assertEqual(res["safety_rules_reminders_sent"], 2)

            relanced_projects = [d["project_name"] for d in res["details"]]
            self.assertIn("Tournage Urgent J-1", relanced_projects)
            self.assertIn("Tournage En Cours", relanced_projects)
            self.assertNotIn("Tournage Passé Terminé", relanced_projects)

    @patch("utils.mailer.send_cgl_invitation_email", return_value=True)
    @patch("utils.mailer.send_safety_rules_invitation_email", return_value=True)
    def test_manual_send_waiver_reminder(self, mock_bvsr_mail, mock_cgl_mail):
        """Vérifie que l'envoi manuel depuis l'admin détecte la relance si déjà envoyé/to_sign."""
        from services.admin.waivers import send_cgl, send_safety_rules_waiver

        with self.app.app_context():
            # cgl est déjà à to_sign -> doit être comptabilisé comme relance
            success, flash_msg = send_cgl(self.cgl_id, base_url="http://testserver")
            self.assertTrue(success)
            self.assertIn("Relance envoyée", flash_msg)
            cw = db.session.get(CglWaiver, self.cgl_id)
            self.assertEqual(cw.reminder_count, 1)
            self.assertIsNotNone(cw.last_reminded_at)
            _, cgl_kwargs = mock_cgl_mail.call_args
            self.assertTrue(cgl_kwargs.get("is_reminder"))

            # bvsr est à to_send -> premier envoi
            success_p, flash_msg_p = send_safety_rules_waiver(self.bvsr_id, base_url="http://testserver")
            self.assertTrue(success_p)
            self.assertIn("envoyées", flash_msg_p)
            sr = db.session.get(SafetyRulesWaiver, self.bvsr_id)
            self.assertEqual(sr.reminder_count, 0)
            _, bvsr_kwargs = mock_bvsr_mail.call_args
            self.assertFalse(bvsr_kwargs.get("is_reminder"))

            # Deuxième envoi manuel sur bvsr (maintenant to_sign) -> doit être une relance
            success_p2, flash_msg_p2 = send_safety_rules_waiver(self.bvsr_id, base_url="http://testserver")
            self.assertTrue(success_p2)
            self.assertIn("Relance envoyée", flash_msg_p2)
            sr2 = db.session.get(SafetyRulesWaiver, self.bvsr_id)
            self.assertEqual(sr2.reminder_count, 1)
            self.assertIsNotNone(sr2.last_reminded_at)

    @patch("utils.mailer.send_cgl_invitation_email", return_value=True)
    @patch("utils.mailer.send_safety_rules_invitation_email", return_value=True)
    def test_script_remind_waivers_dry_run(self, mock_bvsr_mail, mock_cgl_mail):
        """Vérifie le fonctionnement du script scripts/remind_waivers.py en mode dry-run."""
        from scripts.remind_waivers import run_reminders

        with patch("scripts.remind_waivers.build_minimal_app", return_value=(self.app, None)):
            res = run_reminders(days_before=2, dry_run=True)
            self.assertEqual(res["cgl_reminders_sent"], 1)
            self.assertEqual(res["safety_rules_reminders_sent"], 1)
            mock_bvsr_mail.assert_not_called()
            mock_cgl_mail.assert_not_called()

    @patch("utils.mailer.EmailService._send_smtp_message", return_value=True)
    def test_mailer_invitation_reminder_content(self, mock_send_smtp):
        """Vérifie que les emails d'invitation avec is_reminder=True portent l'objet et le bandeau de relance adaptés."""
        from utils.mailer import send_safety_rules_invitation_email, send_cgl_invitation_email

        with self.app.app_context():
            # Email BVSR
            ok_bvsr = send_safety_rules_invitation_email(
                to_email="test.intervenant@example.com",
                recipient_name="Luc Intervenant",
                project_name="Projet Alpha",
                signature_link="http://localhost:5000/sign/safety-rules/abc",
                is_reminder=True,
            )
            self.assertTrue(ok_bvsr)
            msg_bvsr = mock_send_smtp.call_args[0][0]
            self.assertIn("Rappel :", msg_bvsr["Subject"])
            self.assertIn("Règles de Sécurité", msg_bvsr["Subject"])
            bvsr_payloads = [part.get_payload(decode=True).decode('utf-8') for part in msg_bvsr.get_payload()]
            bvsr_full_text = "\n".join(bvsr_payloads)
            self.assertIn("RAPPEL : Le tournage approche", bvsr_full_text)
            self.assertIn("Signature en attente", bvsr_full_text)
            self.assertNotIn("décharge de responsabilité pilote", bvsr_full_text)
            self.assertNotIn("décharge de responsabilité production", bvsr_full_text)

            mock_send_smtp.reset_mock()

            # Email CGL
            ok_cgl = send_cgl_invitation_email(
                to_email="test.prod@example.com",
                prod_contact_name="Prod Contact",
                project_name="Projet Beta",
                signature_link="http://localhost:5000/sign/cgl/xyz",
                is_reminder=True,
            )
            self.assertTrue(ok_cgl)
            msg_cgl = mock_send_smtp.call_args[0][0]
            self.assertIn("Rappel :", msg_cgl["Subject"])
            self.assertIn("Conditions Générales de Location (CGL)", msg_cgl["Subject"])
            cgl_payloads = [part.get_payload(decode=True).decode('utf-8') for part in msg_cgl.get_payload()]
            cgl_full_text = "\n".join(cgl_payloads)
            self.assertIn("RAPPEL : Le tournage approche", cgl_full_text)
            self.assertIn("Signature en attente", cgl_full_text)
            self.assertNotIn("décharge de responsabilité pilote", cgl_full_text)
            self.assertNotIn("décharge de responsabilité production", cgl_full_text)


if __name__ == "__main__":
    unittest.main()
