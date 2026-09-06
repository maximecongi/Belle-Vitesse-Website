import os
import sys
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock weasyprint if not present
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from app import create_app
from models import CheckinVehicle, CheckoutVehicle, Incident, Production, Project, User, db
from services.admin.fleet import get_fleet_overview, get_vehicle_timeline


class FleetTest(unittest.TestCase):
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
        user = User(
            firstname="Alex",
            lastname="Tech",
            mail="alex.tech@example.com",
            role="administrator"
        )
        db.session.add(user)

        prod = Production(name="Studio Cinema")
        db.session.add(prod)
        db.session.flush()

        proj = Project(
            name="Tournage Pub Sport",
            production_id=prod.id,
            departure_date=date(2026, 9, 1),
            shoot_start_date=date(2026, 9, 2),
            shoot_end_date=date(2026, 9, 3),
            return_date=date(2026, 9, 4),
            vehicles_to_check="recTest123"
        )
        db.session.add(proj)
        db.session.commit()

        return user, proj

    @patch("services.admin.fleet.get_vehicles")
    def test_fleet_overview(self, mock_get_vehicles):
        mock_get_vehicles.return_value = [
            {
                "id": "recTest123",
                "fields": {
                    "name": "eCar Proto",
                    "unique_id": "ECAR-PROTO",
                    "brand": "Belle Vitesse",
                    "model": "Mk1",
                    "daily_rate": 1200,
                    "order": 1,
                }
            }
        ]

        with self.app.app_context():
            user, proj = self._create_mock_data()

            # Checkout
            co = CheckoutVehicle(
                project_id=proj.id,
                controller_id=user.id,
                inspection_date=date(2026, 9, 1),
                vehicle_id="recTest123",
                status="signed",
                battery_level=100,
                tire_status="ok",
                brake_status="ok"
            )
            db.session.add(co)

            # Checkin
            ci = CheckinVehicle(
                project_id=proj.id,
                controller_id=user.id,
                inspection_date=date(2026, 9, 4),
                vehicle_id="recTest123",
                status="signed",
                battery_level=88,
                tire_status="ok",
                brake_status="ok"
            )
            db.session.add(ci)

            # Incident
            inc = Incident(
                title="Rayure aile arrière",
                project_id=proj.id,
                vehicle_id="recTest123",
                reported_by_id=user.id,
                incident_date=date(2026, 9, 3),
                severity="mineur",
                status="signale"
            )
            db.session.add(inc)
            db.session.commit()

            res = get_fleet_overview()
            self.assertEqual(res["stats"]["total"], 1)
            self.assertEqual(res["stats"]["available"], 1)

            veh = res["vehicles"][0]
            self.assertEqual(veh["id"], "recTest123")
            self.assertEqual(veh["name"], "eCar Proto")
            self.assertEqual(veh["checkouts_count"], 1)
            self.assertEqual(veh["checkins_count"], 1)
            self.assertEqual(veh["incidents_count"], 1)
            self.assertEqual(veh["projects_count"], 1)
            self.assertEqual(veh["latest_battery"], 88)

    @patch("services.admin.fleet.get_vehicles")
    def test_vehicle_timeline(self, mock_get_vehicles):
        mock_get_vehicles.return_value = [
            {
                "id": "recTest123",
                "fields": {
                    "name": "eCar Proto",
                    "unique_id": "ECAR-PROTO",
                    "brand": "Belle Vitesse",
                    "model": "Mk1",
                    "daily_rate": 1200,
                    "max_speed": "80 km/h",
                    "battery_life": "6 heures",
                }
            }
        ]

        with self.app.app_context():
            user, proj = self._create_mock_data()

            co = CheckoutVehicle(
                project_id=proj.id,
                controller_id=user.id,
                inspection_date=date(2026, 9, 1),
                vehicle_id="recTest123",
                status="signed",
                battery_level=100,
                tire_status="ok",
                brake_status="ok"
            )
            db.session.add(co)

            ci = CheckinVehicle(
                project_id=proj.id,
                controller_id=user.id,
                inspection_date=date(2026, 9, 4),
                vehicle_id="recTest123",
                status="signed",
                battery_level=90,
                tire_status="ok",
                brake_status="ok"
            )
            db.session.add(ci)

            inc = Incident(
                title="Pneu sous-gonflé",
                project_id=proj.id,
                vehicle_id="recTest123",
                reported_by_id=user.id,
                incident_date=date(2026, 9, 2),
                severity="mineur",
                status="signale"
            )
            db.session.add(inc)
            db.session.commit()

            timeline = get_vehicle_timeline("recTest123")
            self.assertIsNotNone(timeline)
            self.assertEqual(timeline["vehicle"]["name"], "eCar Proto")
            self.assertEqual(timeline["vehicle"]["unique_id"], "ECAR-PROTO")
            self.assertEqual(timeline["stats"]["total_checkouts"], 1)
            self.assertEqual(timeline["stats"]["total_checkins"], 1)
            self.assertEqual(timeline["stats"]["total_incidents"], 1)
            self.assertEqual(timeline["stats"]["total_projects"], 1)
            self.assertEqual(timeline["stats"]["total_events"], 4)
            self.assertEqual(timeline["stats"]["conformance_rate"], 100)

            # Vérifier l'ordre chronologique décroissant des événements
            dates = [e["date"] for e in timeline["events"]]
            self.assertEqual(dates, sorted(dates, reverse=True))

            # Vérifier la structure de la timeline hiérarchique (missions)
            self.assertIn("missions", timeline)
            self.assertEqual(len(timeline["missions"]), 1)
            mission = timeline["missions"][0]
            self.assertEqual(mission["type"], "project_mission")
            self.assertEqual(mission["project_name"], proj.name)
            self.assertEqual(len(mission["sub_events"]), 3)
            self.assertTrue(mission["has_checkout"])
            self.assertTrue(mission["has_checkin"])
            self.assertTrue(mission["has_incidents"])

    @patch("services.admin.fleet.get_vehicles")
    def test_vehicle_timeline_with_critical_incident(self, mock_get_vehicles):
        mock_get_vehicles.return_value = [
            {
                "id": "recCritical",
                "fields": {
                    "name": "eTrike Alerte",
                    "unique_id": "ETRIKE-01",
                }
            }
        ]

        with self.app.app_context():
            user, proj = self._create_mock_data()

            # Checkout avec anomalie freins
            co = CheckoutVehicle(
                project_id=proj.id,
                controller_id=user.id,
                inspection_date=date(2026, 9, 1),
                vehicle_id="recCritical",
                status="signed",
                battery_level=90,  # Défaillance batterie au départ (<100%)
                tire_status="ok",
                brake_status="damage"  # Défaillance frein
            )
            db.session.add(co)

            # Incident critique non résolu
            inc = Incident(
                title="Défaillance hydraulique frein avant",
                project_id=proj.id,
                vehicle_id="recCritical",
                reported_by_id=user.id,
                incident_date=date(2026, 9, 2),
                severity="critique",
                status="en_cours"
            )
            db.session.add(inc)
            db.session.commit()

            timeline = get_vehicle_timeline("recCritical")
            self.assertIsNotNone(timeline)
            self.assertEqual(timeline["stats"]["open_critical_incidents"], 1)
            self.assertEqual(timeline["stats"]["current_status"], "incident")
            self.assertEqual(timeline["stats"]["conformance_rate"], 0)

            # Vérifier les anomalies détectées dans le checkout
            checkout_event = next(e for e in timeline["events"] if e["type"] == "checkout")
            self.assertGreater(checkout_event["failure_count"], 0)

    @patch("services.admin.fleet.get_vehicles")
    def test_fleet_routes(self, mock_get_vehicles):
        mock_get_vehicles.return_value = [
            {
                "id": "recTest123",
                "fields": {
                    "name": "eCar Proto",
                    "unique_id": "ECAR-PROTO",
                }
            }
        ]

        # 1. Non authentifié -> redirection login
        res = self.client.get("/admin/fleet")
        self.assertEqual(res.status_code, 302)

        # 2. Authentifié
        with self.app.app_context():
            user, proj = self._create_mock_data()

            with self.client.session_transaction() as sess:
                sess["admin_authenticated"] = True
                sess["admin_user_id"] = user.id
                sess["admin_user_firstname"] = user.firstname
                sess["admin_user_lastname"] = user.lastname
                sess["admin_user_role"] = "administrator"

            # GET /admin/fleet -> 200 OK
            res_fleet = self.client.get("/admin/fleet")
            self.assertEqual(res_fleet.status_code, 200)
            self.assertIn(b"eCar Proto", res_fleet.data)
            self.assertNotIn("Dernière charge connue".encode("utf-8"), res_fleet.data)

            # GET /admin/fleet/recTest123 -> 200 OK
            res_timeline = self.client.get("/admin/fleet/recTest123")
            self.assertEqual(res_timeline.status_code, 200)
            self.assertIn(b"ECAR-PROTO", res_timeline.data)
            self.assertNotIn("Autonomie :".encode("utf-8"), res_timeline.data)
            self.assertIn(f"/admin/projects?q={proj.project_id}".encode("utf-8"), res_timeline.data)
            self.assertIn("Vue par Tournage (1)".encode("utf-8"), res_timeline.data)
            self.assertIn(f"mission-card-{proj.id}".encode("utf-8"), res_timeline.data)
            self.assertNotIn("Aucun tournage ou événement répertorié pour ce véhicule".encode("utf-8"), res_timeline.data)

            # GET /admin/fleet/inconnu -> redirect vers la liste avec flash
            res_unknown = self.client.get("/admin/fleet/inconnu")
            self.assertEqual(res_unknown.status_code, 302)
            self.assertIn("/admin/fleet", res_unknown.headers.get("Location", ""))


if __name__ == "__main__":
    unittest.main()
