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
    def test_api_auto_remind_endpoint(self, mock_pilot_mail, mock_prod_mail):
        """Vérifie l'endpoint /admin/api/waivers/auto-remind avec authentification admin."""
        # 1. Non authentifié -> 403
        resp = self.client.post("/admin/api/waivers/auto-remind")
        self.assertEqual(resp.status_code, 403)

        # 2. Authentifié admin -> 200 et succès
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_role"] = "administrator"

        resp2 = self.client.post("/admin/api/waivers/auto-remind")
        self.assertEqual(resp2.status_code, 200)
        data = json.loads(resp2.data)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["results"]["production_reminders_sent"], 1)
        self.assertEqual(data["results"]["pilot_reminders_sent"], 1)


if __name__ == "__main__":
    unittest.main()
