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
        self.app.config["WTF_CSRF_ENABLED"] = False
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
            self.assertEqual(detail["failures"], [])
            self.assertFalse(detail["has_failures"])

            # Test details with failure and low battery
            checkout.tire_status = "critical"
            checkout.battery_level = 85
            db.session.commit()

            detail_failed = get_inspection_detail_unified("checkout", checkout.id)
            self.assertTrue(detail_failed["has_failures"])
            self.assertIn("Charge batterie (< 100%)", detail_failed["failures"])
            self.assertEqual(detail_failed["failure_count"], 2)

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

    def test_create_checkout_and_checkin_routes(self):
        with self.app.app_context():
            user, proj = self._create_mock_data()

            with self.client.session_transaction() as sess:
                sess['admin_authenticated'] = True
                sess['admin_user_id'] = user.id
                sess['admin_user_firstname'] = user.firstname
                sess['admin_user_lastname'] = user.lastname
                sess['admin_user_role'] = 'administrator'
                sess['admin_logged_in'] = True

            # POST /admin/checkouts/new without photos
            res = self.client.post("/admin/checkouts/new", data={
                "project_id": str(proj.id),
                "vehicle_id": "1",
                "controller_id": user.id,
                "battery_level": "100",
                "notes": "Test creation checkout",
                "tires": "ok",
                "brakes": "ok"
            }, follow_redirects=False)

            self.assertEqual(res.status_code, 302)
            self.assertIn("/admin/checkouts", res.headers.get("Location", ""))

            checkout = CheckoutVehicle.query.filter_by(project_id=proj.id).first()
            self.assertIsNotNone(checkout)
            self.assertEqual(checkout.battery_level, 100)

            # Mark checkout as signed so checkin is permitted by business rule
            checkout.status = 'signed'
            db.session.commit()

            # POST /admin/checkins/new without photos
            res_in = self.client.post("/admin/checkins/new", data={
                "project_id": str(proj.id),
                "vehicle_id": "1",
                "controller_id": user.id,
                "battery_level": "90",
                "notes": "Test creation checkin",
                "tires": "ok",
                "brakes": "ok"
            }, follow_redirects=False)

            self.assertEqual(res_in.status_code, 302)
            self.assertIn("/admin/checkins", res_in.headers.get("Location", ""))

            checkin = CheckinVehicle.query.filter_by(project_id=proj.id).first()
            self.assertIsNotNone(checkin)
            self.assertEqual(checkin.battery_level, 90)

    def test_verify_public_routes(self):
        from models import CheckoutSignedDocument, CheckinSignedDocument
        with self.app.app_context():
            user, proj = self._create_mock_data()

            doc_co = CheckoutSignedDocument(
                inspection_id="BVCO-TEST1234",
                hash="mock_hash_123",
                data_snapshot={
                    "inspection_id": "BVCO-TEST1234",
                    "project": "Test Project",
                    "production": "Test Prod",
                    "control_date": "05/09/2026",
                    "controller": {"name": "John Doe"},
                    "vehicle": {"fields": {"name": "Test Car", "unique_id": "CAR-01"}},
                    "vehicle_id": "1",
                    "signed_at": "2026-09-05T12:00:00"
                },
                signature="data:image/png;base64,mock",
                pdf_url="/checkout/document/test.pdf"
            )
            db.session.add(doc_co)

            doc_ci = CheckinSignedDocument(
                inspection_id="BVCI-TEST5678",
                hash="mock_hash_456",
                data_snapshot={
                    "inspection_id": "BVCI-TEST5678",
                    "project": "Test Project",
                    "production": "Test Prod",
                    "control_date": "05/09/2026",
                    "controller": {"name": "John Doe"},
                    "vehicle": {"fields": {"name": "Test Car", "unique_id": "CAR-01"}},
                    "vehicle_id": "1",
                    "signed_at": "2026-09-05T12:00:00"
                },
                signature="data:image/png;base64,mock",
                pdf_url="/checkin/document/test.pdf"
            )
            db.session.add(doc_ci)
            db.session.commit()

        # Test GET /checkout/verify/BVCO-TEST1234
        res_co = self.client.get("/checkout/verify/BVCO-TEST1234")
        self.assertEqual(res_co.status_code, 200)
        self.assertIn(b"BVCO-TEST1234", res_co.data)
        self.assertIn("Données Scellées".encode("utf-8"), res_co.data)

        # Test GET /checkin/verify/BVCI-TEST5678
        res_ci = self.client.get("/checkin/verify/BVCI-TEST5678")
        self.assertEqual(res_ci.status_code, 200)
        self.assertIn(b"BVCI-TEST5678", res_ci.data)
        self.assertIn("Données Scellées".encode("utf-8"), res_ci.data)


if __name__ == "__main__":
    unittest.main()
