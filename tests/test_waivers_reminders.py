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


if __name__ == "__main__":
    unittest.main()
