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
from models import db, Project, Production, User, CheckoutVehicle, CheckinVehicle
from services.admin.inspections import (
    list_inspections_unified,
    get_inspection_detail_unified,
    delete_inspection_unified,
    get_unified_form_context
)

class InspectionsTest(unittest.TestCase):
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

    def _create_mock_data(self):
        # Create user
        user = User(firstname="John", lastname="Doe", mail="john.doe@example.com", role="administrator")
        db.session.add(user)
        
        # Create production
        prod = Production(name="Test Prod")
        db.session.add(prod)
        db.session.flush()

        # Create project
        proj = Project(
            name="Test Project",
            production_id=prod.id,
            departure_date=date(2026, 6, 2),
            return_date=date(2026, 6, 5),
            vehicles_to_check="1"
        )
        db.session.add(proj)
        db.session.commit()

        return user, proj

    def test_list_and_details(self):
        with self.app.app_context():
            user, proj = self._create_mock_data()

            # Create checkout vehicle
            checkout = CheckoutVehicle(
                project_id=proj.id,
                controller_id=user.id,
                inspection_date=date(2026, 6, 2),
                vehicle_id="1",
                status="completed",
                tire_status="ok",
                brake_status="ok"
            )
            db.session.add(checkout)
            db.session.commit()

            # Test list unified
            res = list_inspections_unified("checkout")
            self.assertEqual(res["stats"]["total_checkouts"], 1)
            self.assertEqual(res["checkouts"][0]["project"], "Test Project")

            # Test details unified
            detail = get_inspection_detail_unified("checkout", checkout.id)
            self.assertIsNotNone(detail)
            self.assertEqual(detail["tires"], "ok")

    def test_soft_delete(self):
        with self.app.app_context():
            user, proj = self._create_mock_data()

            checkout = CheckoutVehicle(
                project_id=proj.id,
                controller_id=user.id,
                inspection_date=date(2026, 6, 2),
                vehicle_id="1",
                status="completed"
            )
            db.session.add(checkout)
            db.session.commit()

            # Delete
            success = delete_inspection_unified("checkout", checkout.id)
            self.assertTrue(success)

            # Retrieve again - unified list should be empty
            res = list_inspections_unified("checkout")
            self.assertEqual(res["stats"]["total_checkouts"], 0)

            # Unified detail should be None
            detail = get_inspection_detail_unified("checkout", checkout.id)
            self.assertIsNone(detail)

            # Check DB directly to verify deleted_at is filled
            db_checkout = db.session.get(CheckoutVehicle, checkout.id)
            self.assertIsNotNone(db_checkout)
            self.assertIsNotNone(db_checkout.deleted_at)

    def test_unified_form_context(self):
        with self.app.app_context():
            user, proj = self._create_mock_data()
            context = get_unified_form_context("checkout")
            self.assertIn("projects", context)
            self.assertIn("users", context)
            self.assertIn("vehicles", context)

if __name__ == "__main__":
    unittest.main()
