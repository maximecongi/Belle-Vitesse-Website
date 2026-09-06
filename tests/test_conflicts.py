import json
import os
import unittest
from datetime import date

# Isolation stricte de l'environnement de test avant tout import d'app
os.environ["FLASK_ENV"] = "testing"
os.environ["TESTING"] = "True"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["WTF_CSRF_ENABLED"] = "False"
os.environ["USE_SSH_TUNNEL"] = "false"

from app import create_app
from models import Production, Project, User, db
from services.admin.conflicts import check_booking_conflicts


class ConflictsTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

            # Données de test
            self.prod = Production(name="Production Conflit Test")
            db.session.add(self.prod)
            db.session.commit()

            # Projet existant du 10 au 15 du mois prochain
            self.base_start = date(2027, 5, 10)
            self.base_end = date(2027, 5, 15)

            self.project1 = Project(
                name="Projet Alpha",
                production_id=self.prod.id,
                departure_date=self.base_start,
                return_date=self.base_end,
                vehicles_to_check="recVeh1,recVeh2",
                heads_to_check="recHead1",
            )
            db.session.add(self.project1)
            db.session.commit()
            self.project1_id = self.project1.id
            self.project1_code = self.project1.project_id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_overlap_conflict_detected_on_vehicle(self):
        """Vérifie qu'un chevauchement de dates sur un véhicule est bien détecté."""
        with self.app.app_context():
            res = check_booking_conflicts(
                start_date_val="2027-05-12",
                end_date_val="2027-05-18",
                vehicle_ids=["recVeh1"],
            )
            self.assertTrue(res["has_conflicts"])
            self.assertIn("recVeh1", res["conflicting_vehicle_ids"])
            self.assertEqual(res["total_conflicts"], 1)
            self.assertEqual(res["conflicts_list"][0]["project_code"], self.project1_code)

    def test_no_overlap_no_conflict(self):
        """Vérifie qu'aucune alerte n'est levée si les dates sont disjointes."""
        with self.app.app_context():
            res = check_booking_conflicts(
                start_date_val="2027-05-16",
                end_date_val="2027-05-20",
                vehicle_ids=["recVeh1"],
            )
            self.assertFalse(res["has_conflicts"])
            self.assertEqual(res["total_conflicts"], 0)

    def test_head_conflict_detected(self):
        """Vérifie la détection d'un conflit sur une tête gyrostabilisée."""
        with self.app.app_context():
            res = check_booking_conflicts(
                start_date_val="2027-05-08",
                end_date_val="2027-05-11",
                head_ids=["recHead1"],
            )
            self.assertTrue(res["has_conflicts"])
            self.assertIn("recHead1", res["conflicting_head_ids"])

    def test_exclude_project_id_for_self_edit(self):
        """Vérifie que l'édition d'un projet n'entre pas en conflit avec lui-même (par ID entier et par code)."""
        with self.app.app_context():
            # Test par ID entier
            res_id = check_booking_conflicts(
                start_date_val="2027-05-10",
                end_date_val="2027-05-15",
                vehicle_ids=["recVeh1"],
                exclude_project_id=self.project1_id,
            )
            self.assertFalse(res_id["has_conflicts"])

            # Test par code project_id (BVPR-...)
            res_code = check_booking_conflicts(
                start_date_val="2027-05-10",
                end_date_val="2027-05-15",
                vehicle_ids=["recVeh1"],
                exclude_project_id=self.project1_code,
            )
            self.assertFalse(res_code["has_conflicts"])

    def test_get_project_for_edit_contains_ids(self):
        """Vérifie que get_project_for_edit renvoie bien les clés id, record_id et project_id."""
        from services.admin.projects import get_project_for_edit
        with self.app.app_context():
            edit_data = get_project_for_edit(self.project1_id)
            self.assertIsNotNone(edit_data)
            self.assertEqual(edit_data["id"], self.project1_id)
            self.assertEqual(edit_data["record_id"], self.project1_id)
            self.assertEqual(edit_data["project_id"], self.project1_code)

    def test_api_check_conflicts_endpoint_with_exclusion(self):
        """Vérifie que l'API HTTP exclut bien le projet en cours d'édition pour éviter l'auto-conflit."""
        with self.client.session_transaction() as sess:
            sess['admin_authenticated'] = True
            sess['admin_user_id'] = 1
            sess['admin_user_role'] = 'administrator'

        # Sans exclusion -> conflit détecté
        payload_conflict = {
            "start_date": "2027-05-11",
            "end_date": "2027-05-13",
            "vehicle_ids": ["recVeh2"],
        }
        resp = self.client.post(
            "/admin/api/projects/check-conflicts",
            data=json.dumps(payload_conflict),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["data"]["has_conflicts"])

        # Avec exclusion (par id) -> aucun conflit
        payload_no_conflict = {
            "start_date": "2027-05-11",
            "end_date": "2027-05-13",
            "vehicle_ids": ["recVeh2"],
            "project_id": self.project1_id,
        }
        resp = self.client.post(
            "/admin/api/projects/check-conflicts",
            data=json.dumps(payload_no_conflict),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.get_json()["data"]["has_conflicts"])


if __name__ == '__main__':
    unittest.main()
