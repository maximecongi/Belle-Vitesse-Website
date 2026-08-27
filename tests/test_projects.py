import os
import sys
import unittest
from datetime import date
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock weasyprint
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from app import create_app
from models import db, Project, Production, User, Contact
from services.admin.projects import create_project, update_project, delete_project, get_project_for_edit, list_projects

class ProjectsTest(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        os.environ["WTF_CSRF_ENABLED"] = "False"
        os.environ["USE_SSH_TUNNEL"] = "false"

        self.app = create_app()
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_project_crud_tracking(self):
        with self.app.app_context():
            # Create user
            user = User(firstname="Alice", lastname="Smith", mail="alice.smith@example.com", role="manager")
            db.session.add(user)
            db.session.flush()

            # Create production
            prod = Production(name="Test Production")
            db.session.add(prod)
            db.session.flush()

            # Create contacts
            contact_pilot = Contact(first_name="Jean", last_name="Pilote", mail="pilot@example.com")
            contact_dop = Contact(first_name="Claire", last_name="DOP", mail="dop@example.com")
            contact_first_ac = Contact(first_name="Marc", last_name="Assistant", mail="ac@example.com")
            contact_key_grip = Contact(first_name="Paul", last_name="Machino", mail="grip@example.com")
            db.session.add_all([contact_pilot, contact_dop, contact_first_ac, contact_key_grip])
            db.session.flush()

            # 1. Test create_project records user_id and technical contacts
            form_data = {
                "name": "Project X",
                "production_id": str(prod.id),
                "pilot_contact_id": str(contact_pilot.id),
                "dop_contact_id": str(contact_dop.id),
                "first_ac_contact_id": str(contact_first_ac.id),
                "key_grip_contact_id": str(contact_key_grip.id),
                "departure_date": date(2026, 6, 15),
                "shoot_start": date(2026, 6, 16),
                "shoot_end": date(2026, 6, 20),
                "return_date": date(2026, 6, 21)
            }
            # Mock getlist for vehicles/heads
            class MockForm(dict):
                def getlist(self, name):
                    return []
            
            form = MockForm(form_data)
            success = create_project(form, user_id=user.id)
            self.assertTrue(success)

            proj = Project.query.filter_by(name="Project X").first()
            self.assertIsNotNone(proj)
            self.assertEqual(proj.last_action_by_id, user.id)
            self.assertEqual(proj.first_ac_contact_id, contact_first_ac.id)
            self.assertEqual(proj.key_grip_contact_id, contact_key_grip.id)
            self.assertEqual(proj.first_ac_contact.first_name, "Marc")
            self.assertEqual(proj.key_grip_contact.first_name, "Paul")

            # Check to_dict & get_project_for_edit & list_projects
            proj_dict = proj.to_dict()
            self.assertEqual(proj_dict["first_ac_contact_id"], contact_first_ac.id)
            self.assertEqual(proj_dict["key_grip_contact_id"], contact_key_grip.id)

            edit_data = get_project_for_edit(proj.id)
            self.assertEqual(edit_data["first_ac_contact_id"], str(contact_first_ac.id))
            self.assertEqual(edit_data["key_grip_contact_id"], str(contact_key_grip.id))

            all_p = list_projects()
            p_admin = next((p for p in all_p if p["id"] == proj.id), None)
            self.assertIsNotNone(p_admin)
            self.assertEqual(p_admin["first_ac_contact_name"], "Marc Assistant")
            self.assertEqual(p_admin["key_grip_contact_name"], "Paul Machino")

            # 2. Test update_project records updated user_id and modified contacts
            user2 = User(firstname="Bob", lastname="Jones", mail="bob.jones@example.com", role="administrator")
            db.session.add(user2)
            db.session.flush()

            form_data["name"] = "Project X Updated"
            form_data["first_ac_contact_id"] = ""
            form = MockForm(form_data)
            success = update_project(proj.id, form, user_id=user2.id)
            self.assertTrue(success)

            proj = db.session.get(Project, proj.id)
            self.assertEqual(proj.name, "Project X Updated")
            self.assertEqual(proj.last_action_by_id, user2.id)
            self.assertIsNone(proj.first_ac_contact_id)
            self.assertEqual(proj.key_grip_contact_id, contact_key_grip.id)

            # 3. Test delete_project records user_id who deleted
            success = delete_project(proj.id, user_id=user.id)
            self.assertTrue(success)

            proj = db.session.get(Project, proj.id)
            self.assertIsNotNone(proj.deleted_at)
            self.assertEqual(proj.last_action_by_id, user.id)

if __name__ == "__main__":
    unittest.main()
