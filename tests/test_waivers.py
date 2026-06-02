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
from models import db, Project, Production, User, PilotWaiver, ProductionWaiver
from services.admin.waivers import (
    create_pilot_waiver,
    create_production_waiver,
    list_pilot_waivers,
    list_production_waivers,
    generate_pilot_waiver,
    generate_production_waiver,
    reset_pilot_waiver,
    reset_production_waiver,
    delete_pilot_waiver_internal,
    delete_production_waiver_internal
)

class WaiversTest(unittest.TestCase):
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

    def test_create_and_list_waivers(self):
        with self.app.app_context():
            user, proj = self._create_mock_data()

            # Create waivers
            success, msg = create_pilot_waiver(proj.id)
            self.assertTrue(success)
            
            success, msg = create_production_waiver(proj.id)
            self.assertTrue(success)

            # List
            pilots = list_pilot_waivers()
            self.assertEqual(len(pilots), 1)
            self.assertEqual(pilots[0]["project_name"], "Test Project")

            productions = list_production_waivers()
            self.assertEqual(len(productions), 1)
            self.assertEqual(productions[0]["project_name"], "Test Project")

    def test_soft_delete_waivers(self):
        with self.app.app_context():
            user, proj = self._create_mock_data()

            # Create
            create_pilot_waiver(proj.id)
            create_production_waiver(proj.id)

            # Soft delete
            delete_pilot_waiver_internal(proj.id)
            delete_production_waiver_internal(proj.id)

            # List again - should be empty
            pilots = list_pilot_waivers()
            self.assertEqual(len(pilots), 0)

            productions = list_production_waivers()
            self.assertEqual(len(productions), 0)

            # Check DB directly
            pw = db.session.query(PilotWaiver).filter_by(project_id=proj.id).first()
            self.assertIsNotNone(pw)
            self.assertIsNotNone(pw.deleted_at)

            prw = db.session.query(ProductionWaiver).filter_by(project_id=proj.id).first()
            self.assertIsNotNone(prw)
            self.assertIsNotNone(prw.deleted_at)

if __name__ == "__main__":
    unittest.main()
