import os
import sys
import unittest
from datetime import date
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Isolation stricte de l'environnement de test avant tout import d'app
os.environ["FLASK_ENV"] = "testing"
os.environ["TESTING"] = "True"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["WTF_CSRF_ENABLED"] = "False"
os.environ["USE_SSH_TUNNEL"] = "false"

# Mock weasyprint si absent
if "weasyprint" not in sys.modules:
    mock_weasyprint = MagicMock()
    mock_weasyprint.HTML = MagicMock()
    mock_weasyprint.CSS = MagicMock()
    sys.modules["weasyprint"] = mock_weasyprint

from app import create_app
from models import (
    CheckinVehicle,
    CheckoutVehicle,
    Incident,
    PilotWaiver,
    Production,
    ProductionWaiver,
    Project,
    User,
    db,
)
from utils.entity_resolvers import (
    resolve_incident,
    resolve_inspection,
    resolve_pilot_waiver,
    resolve_production_waiver,
    resolve_project,
    resolve_waiver,
)


class EntityResolversTestCase(unittest.TestCase):
    """Tests unitaires pour les résolveurs polymorphiques et le typage unifié des entités."""

    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

            # Création utilisateur admin de test
            self.user = User(
                firstname="Admin",
                lastname="BV",
                mail="admin@bellevitesse.com",
                role="administrator"
            )
            db.session.add(self.user)

            # Création production
            self.prod = Production(name="Studio Alpes", mail="alpes@example.com")
            db.session.add(self.prod)
            db.session.flush()

            # Création projet
            self.project = Project(
                name="Tournage Pub Alpes",
                project_id="BVPR-ALPTEST001",
                production_id=self.prod.id,
                departure_date=date(2026, 10, 1),
                return_date=date(2026, 10, 5)
            )
            db.session.add(self.project)
            db.session.flush()

            # Décharges
            self.pilot_waiver = PilotWaiver(
                project_id=self.project.id,
                waiver_id="BVDW-PILOT001",
                pilot_first_name="Jean",
                pilot_last_name="Pilote",
                status="to_send"
            )
            self.prod_waiver = ProductionWaiver(
                project_id=self.project.id,
                waiver_id="BVPW-PROD001",
                production_name="Studio Alpes",
                status="to_send"
            )
            db.session.add(self.pilot_waiver)
            db.session.add(self.prod_waiver)

            # Incident
            self.incident = Incident(
                incident_number="BVIC-INC001",
                project_id=self.project.id,
                title="Impact pare-brise",
                incident_date=date.today(),
                severity="modere",
                status="signale",
                reported_by_id=self.user.id
            )
            db.session.add(self.incident)

            # Inspections
            self.checkout = CheckoutVehicle(
                inspection_number="BVCO-OUT001",
                project_id=self.project.id,
                vehicle_id="recVehicle1",
                status="signed"
            )
            self.checkin = CheckinVehicle(
                inspection_number="BVCI-IN001",
                project_id=self.project.id,
                vehicle_id="recVehicle1",
                status="signed"
            )
            db.session.add(self.checkout)
            db.session.add(self.checkin)

            db.session.commit()

            self.user_id = self.user.id
            self.project_id = self.project.id
            self.pilot_waiver_id = self.pilot_waiver.id
            self.prod_waiver_id = self.prod_waiver.id
            self.incident_id = self.incident.id
            self.checkout_id = self.checkout.id
            self.checkin_id = self.checkin.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_resolve_project(self):
        """Vérifie la résolution de projet par entier, chaîne numérique ou code BVPR-*."""
        with self.app.app_context():
            # Par entier
            res_int = resolve_project(self.project_id)
            self.assertIsNotNone(res_int)
            self.assertEqual(res_int.name, "Tournage Pub Alpes")

            # Par chaîne numérique
            res_str_num = resolve_project(str(self.project_id))
            self.assertIsNotNone(res_str_num)
            self.assertEqual(res_str_num.id, self.project_id)

            # Par code métier
            res_code = resolve_project("BVPR-ALPTEST001")
            self.assertIsNotNone(res_code)
            self.assertEqual(res_code.id, self.project_id)

            # Inexistant ou None
            self.assertIsNone(resolve_project(99999))
            self.assertIsNone(resolve_project("BVPR-INCONNU"))
            self.assertIsNone(resolve_project(None))

    def test_resolve_waivers(self):
        """Vérifie la résolution des décharges pilote et production."""
        with self.app.app_context():
            # Pilote par int, str num, code
            self.assertEqual(resolve_pilot_waiver(self.pilot_waiver_id).waiver_id, "BVDW-PILOT001")
            self.assertEqual(resolve_pilot_waiver(str(self.pilot_waiver_id)).waiver_id, "BVDW-PILOT001")
            self.assertEqual(resolve_pilot_waiver("BVDW-PILOT001").id, self.pilot_waiver_id)
            self.assertIsNone(resolve_pilot_waiver(None))
            self.assertIsNone(resolve_pilot_waiver("BVDW-INCONNU"))

            # Production par int, str num, code
            self.assertEqual(resolve_production_waiver(self.prod_waiver_id).waiver_id, "BVPW-PROD001")
            self.assertEqual(resolve_production_waiver(str(self.prod_waiver_id)).waiver_id, "BVPW-PROD001")
            self.assertEqual(resolve_production_waiver("BVPW-PROD001").id, self.prod_waiver_id)
            self.assertIsNone(resolve_production_waiver(None))
            self.assertIsNone(resolve_production_waiver("BVPW-INCONNU"))

    def test_resolve_incident(self):
        """Vérifie la résolution d'incident par int, str num, ou numéro BVIC-*."""
        with self.app.app_context():
            self.assertEqual(resolve_incident(self.incident_id).incident_number, "BVIC-INC001")
            self.assertEqual(resolve_incident(str(self.incident_id)).incident_number, "BVIC-INC001")
            self.assertEqual(resolve_incident("BVIC-INC001").id, self.incident_id)
            self.assertIsNone(resolve_incident(None))
            self.assertIsNone(resolve_incident("BVIC-INCONNU"))

    def test_resolve_inspections(self):
        """Vérifie la résolution d'inspections checkout et checkin."""
        with self.app.app_context():
            # Checkout
            self.assertEqual(resolve_inspection("checkout", self.checkout_id).inspection_number, "BVCO-OUT001")
            self.assertEqual(resolve_inspection("checkout", str(self.checkout_id)).inspection_number, "BVCO-OUT001")
            self.assertEqual(resolve_inspection("checkout", "BVCO-OUT001").id, self.checkout_id)
            self.assertIsNone(resolve_inspection("checkout", None))

            # Checkin
            self.assertEqual(resolve_inspection("checkin", self.checkin_id).inspection_number, "BVCI-IN001")
            self.assertEqual(resolve_inspection("checkin", str(self.checkin_id)).inspection_number, "BVCI-IN001")
            self.assertEqual(resolve_inspection("checkin", "BVCI-IN001").id, self.checkin_id)
            self.assertIsNone(resolve_inspection("checkin", None))

    def test_routes_code_redirects(self):
        """Vérifie que les routes admin redirigent correctement les codes métier vers l'ID canonique."""
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = self.user_id
            sess["admin_user_role"] = "administrator"

        # Redirection code projet BVPR-*
        resp = self.client.get("/admin/projects/BVPR-ALPTEST001")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.location.endswith(f"/admin/projects/{self.project_id}"))

        # Redirection code incident BVIC-*
        resp = self.client.get("/admin/incidents/BVIC-INC001")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.location.endswith(f"/admin/incidents/{self.incident_id}"))

        # Redirection code départ BVCO-*
        resp = self.client.get("/admin/checkouts/BVCO-OUT001")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.location.endswith(f"/admin/checkouts/{self.checkout_id}"))

        # Redirection code retour BVCI-*
        resp = self.client.get("/admin/checkins/BVCI-IN001")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.location.endswith(f"/admin/checkins/{self.checkin_id}"))

        # Accès direct avec <int:record_id>
        resp_direct = self.client.get(f"/admin/projects/{self.project_id}")
        self.assertEqual(resp_direct.status_code, 200)

        # Code inexistant -> 404
        resp_404 = self.client.get("/admin/projects/BVPR-NONEXISTENT")
        self.assertEqual(resp_404.status_code, 404)


if __name__ == '__main__':
    unittest.main()
