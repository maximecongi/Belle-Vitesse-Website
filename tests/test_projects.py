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
from services.admin.projects import (
    create_project,
    update_project,
    delete_project,
    get_project_for_edit,
    list_projects,
    update_project_notes,
)

class ProjectsTest(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        os.environ["WTF_CSRF_ENABLED"] = "False"
        os.environ["USE_SSH_TUNNEL"] = "false"

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
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

    def test_project_notes_edit(self):
        with self.app.app_context():
            user = User(firstname="Charlie", lastname="Technician", mail="charlie@example.com", role="technicien")
            prod = Production(name="Production Alpha")
            db.session.add_all([user, prod])
            db.session.flush()

            proj = Project(name="Project Notes Test", production_id=prod.id, notes="Ancienne consigne")
            db.session.add(proj)
            db.session.commit()
            proj_id = proj.id

            # 1. Test update_project_notes service function
            updated = update_project_notes(proj_id, "Nouvelle consigne technique", user_id=user.id)
            self.assertIsNotNone(updated)
            self.assertEqual(updated.notes, "Nouvelle consigne technique")
            self.assertEqual(updated.last_action_by_id, user.id)

        # 2. Test HTTP AJAX route
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = user.id
            sess["admin_user_role"] = "technicien"

        resp = self.client.post(
            f"/admin/projects/{proj_id}/notes",
            json={"notes": "Consigne mise à jour via AJAX"},
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["notes"], "Consigne mise à jour via AJAX")

        # 3. Test HTTP standard form submit route
        resp_form = self.client.post(
            f"/admin/projects/{proj_id}/notes",
            data={"notes": "Consigne finale via POST form"},
            follow_redirects=True
        )
        self.assertEqual(resp_form.status_code, 200)
        self.assertIn("Consigne finale via POST form".encode("utf-8"), resp_form.data)

    def test_soft_deleted_checks_and_waivers_on_projects(self):
        from models import CheckoutVehicle, CheckinVehicle, PilotWaiver, ProductionWaiver
        from services.admin.inspections import delete_inspection_unified
        from services.admin.waivers import delete_pilot_waiver, delete_production_waiver
        from services.admin.project_reports import get_project_detail_context
        from services.admin.checkins import create_checkin

        with self.app.app_context():
            user = User(firstname="Bob", lastname="Inspector", mail="bob@example.com", role="administrator")
            prod = Production(name="Soft Delete Prod")
            db.session.add_all([user, prod])
            db.session.flush()

            proj = Project(
                name="Project SoftDelete Test",
                production_id=prod.id,
                vehicles_to_check="1, 2"
            )
            db.session.add(proj)
            db.session.commit()

            # 1. Initially, checks are "to_check"
            projects_list = list_projects()
            p_data = next(p for p in projects_list if p["id"] == proj.id)
            v1_state = next(v for v in p_data["vehicles"] if v["id"] == "1")
            self.assertEqual(v1_state["checkout_id"], "")
            self.assertEqual(v1_state["checkout_status_id"], "to_check")
            self.assertEqual(v1_state["checkout_status"], "À réaliser")
            self.assertEqual(v1_state["checkin_id"], "")
            self.assertEqual(v1_state["checkin_status_id"], "to_check")

            # 2. Add signed checkout and checkin
            checkout = CheckoutVehicle(
                project_id=proj.id,
                vehicle_id="1",
                status="signed",
                controller_id=user.id,
                inspection_date=date.today(),
            )
            db.session.add(checkout)
            db.session.commit()

            checkin = CheckinVehicle(
                project_id=proj.id,
                vehicle_id="1",
                status="completed",
                controller_id=user.id,
                inspection_date=date.today(),
            )
            db.session.add(checkin)
            db.session.commit()

            # Verify active checks are formatted
            projects_list = list_projects()
            p_data = next(p for p in projects_list if p["id"] == proj.id)
            v1_state = next(v for v in p_data["vehicles"] if v["id"] == "1")
            self.assertEqual(v1_state["checkout_id"], checkout.id)
            self.assertEqual(v1_state["checkout_status_id"], "signed")
            self.assertEqual(v1_state["checkin_id"], checkin.id)
            self.assertEqual(v1_state["checkin_status_id"], "completed")

            # 3. Soft-delete checkout
            success = delete_inspection_unified("checkout", checkout.id)
            self.assertTrue(success)

            # Re-fetch projects and check that checkout reverted to "to_check"
            projects_list = list_projects()
            p_data = next(p for p in projects_list if p["id"] == proj.id)
            v1_state = next(v for v in p_data["vehicles"] if v["id"] == "1")
            self.assertEqual(v1_state["checkout_id"], "")
            self.assertEqual(v1_state["checkout_status_id"], "to_check")
            self.assertEqual(v1_state["checkout_status"], "À réaliser")
            # Checkin is still active
            self.assertEqual(v1_state["checkin_id"], checkin.id)

            # Verify in project detail context as well
            detail_ctx = get_project_detail_context(proj.id)
            v1_detail = next(v for v in detail_ctx["vehicles"] if v["id"] == "1")
            self.assertEqual(v1_detail["checkout_id"], "")
            self.assertEqual(v1_detail["checkout_status_id"], "to_check")

            # 4. Attempting to create a new checkin when checkout is deleted must be rejected
            with self.assertRaises(ValueError) as cm:
                create_checkin({
                    "project_id": str(proj.id),
                    "vehicle_id": "1",
                    "controller_id": str(user.id)
                })
            self.assertIn("Le départ de ce véhicule n'a pas été validé", str(cm.exception))

            # 5. Soft-delete checkin
            success_in = delete_inspection_unified("checkin", checkin.id)
            self.assertTrue(success_in)

            projects_list = list_projects()
            p_data = next(p for p in projects_list if p["id"] == proj.id)
            v1_state = next(v for v in p_data["vehicles"] if v["id"] == "1")
            self.assertEqual(v1_state["checkin_id"], "")
            self.assertEqual(v1_state["checkin_status_id"], "to_check")
            self.assertEqual(v1_state["checkin_status"], "À réaliser")

            # 6. Test Pilot & Production Waivers soft delete
            pw = PilotWaiver(project_id=proj.id, status="to_sign", pilot_first_name="Jean", pilot_last_name="Pilote")
            prw = ProductionWaiver(project_id=proj.id, status="to_sign", production_name="Prod Alpha")
            db.session.add_all([pw, prw])
            db.session.commit()

            projects_list = list_projects()
            p_data = next(p for p in projects_list if p["id"] == proj.id)
            self.assertEqual(p_data["pilot_waiver"]["id"], pw.id)
            self.assertEqual(p_data["production_waiver"]["id"], prw.id)

            # Soft-delete waivers
            del_pw_ok, _ = delete_pilot_waiver(pw.waiver_id)
            del_prw_ok, _ = delete_production_waiver(prw.waiver_id)
            self.assertTrue(del_pw_ok)
            self.assertTrue(del_prw_ok)

            projects_list = list_projects()
            p_data = next(p for p in projects_list if p["id"] == proj.id)
            self.assertIsNone(p_data["pilot_waiver"]["id"])
            self.assertEqual(p_data["pilot_waiver"]["waiver_num"], "")
            self.assertIsNone(p_data["production_waiver"]["id"])
            self.assertEqual(p_data["production_waiver"]["waiver_num"], "")

            # Check project model properties
            db.session.refresh(proj)
            self.assertEqual(len(proj.active_checkout_vehicles), 0)
            self.assertEqual(len(proj.active_checkin_vehicles), 0)
            self.assertIsNone(proj.active_pilot_waiver)
            self.assertIsNone(proj.active_production_waiver)

if __name__ == "__main__":
    unittest.main()
