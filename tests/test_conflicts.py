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
            self.prod_id = self.prod.id

            # Projet existant du 10 au 15 du mois prochain
            self.base_start = date(2027, 5, 10)
            self.base_end = date(2027, 5, 15)

            self.project1 = Project(
                name="Projet Alpha",
                production_id=self.prod_id,
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

    def test_punctual_mode_conflict_when_not_immobilized(self):
        """Vérifie qu'un projet ponctuel NON immobilisé libère le véhicule entre les dates."""
        with self.app.app_context():
            p_punctual = Project(
                name="Projet Ponctuel Libéré",
                production_id=self.prod_id,
                date_mode="punctual",
                is_immobilized_between=False,
                shoot_dates=["2027-06-14", "2027-06-16", "2027-06-19"],
                shoot_start_date=date(2027, 6, 14),
                shoot_end_date=date(2027, 6, 19),
                vehicles_to_check="recVeh99",
            )
            db.session.add(p_punctual)
            db.session.commit()

            # 1. Le 15 juin (jour intermédiaire libre) -> AUCUN conflit
            res_free_day = check_booking_conflicts(
                start_date_val="2027-06-15",
                end_date_val="2027-06-15",
                vehicle_ids=["recVeh99"],
            )
            self.assertFalse(res_free_day["has_conflicts"])

            # 2. Le 16 juin (jour actif de tournage) -> CONFLIT détecté
            res_shoot_day = check_booking_conflicts(
                start_date_val="2027-06-16",
                end_date_val="2027-06-16",
                vehicle_ids=["recVeh99"],
            )
            self.assertTrue(res_shoot_day["has_conflicts"])
            self.assertIn("recVeh99", res_shoot_day["conflicting_vehicle_ids"])

    def test_punctual_mode_conflict_when_immobilized(self):
        """Vérifie qu'un projet ponctuel IMMOBILISÉ bloque le véhicule même les jours intermédiaires."""
        with self.app.app_context():
            p_punctual_immob = Project(
                name="Projet Ponctuel Bloqué",
                production_id=self.prod_id,
                date_mode="punctual",
                is_immobilized_between=True,
                shoot_dates=["2027-07-10", "2027-07-15"],
                shoot_start_date=date(2027, 7, 10),
                shoot_end_date=date(2027, 7, 15),
                vehicles_to_check="recVeh88",
            )
            db.session.add(p_punctual_immob)
            db.session.commit()

            # Le 12 juillet (jour intermédiaire, mais immobilisé) -> CONFLIT détecté
            res_immob_day = check_booking_conflicts(
                start_date_val="2027-07-12",
                end_date_val="2027-07-12",
                vehicle_ids=["recVeh88"],
            )
            self.assertTrue(res_immob_day["has_conflicts"])
            self.assertIn("recVeh88", res_immob_day["conflicting_vehicle_ids"])

    def test_punctual_mode_incoming_request_not_immobilized(self):
        """Vérifie qu'une requête ponctuelle entrante non immobilisée ne conflit pas sur un jour libre."""
        with self.app.app_context():
            p_continuous = Project(
                name="Projet Continu Jour Unique",
                production_id=self.prod_id,
                departure_date=date(2027, 8, 14),
                return_date=date(2027, 8, 14),
                vehicles_to_check="recVeh77",
            )
            db.session.add(p_continuous)
            db.session.commit()

            # Requête entrante ponctuelle non immobilisée demandant le 13 et le 15 -> Aucun conflit
            res_no_conflict = check_booking_conflicts(
                start_date_val="2027-08-13",
                end_date_val="2027-08-15",
                vehicle_ids=["recVeh77"],
                date_mode="punctual",
                is_immobilized_between=False,
                shoot_dates=["2027-08-13", "2027-08-15"],
            )
            self.assertFalse(res_no_conflict["has_conflicts"])

            # Requête entrante ponctuelle non immobilisée incluant le 14 -> Conflit
            res_conflict = check_booking_conflicts(
                start_date_val="2027-08-13",
                end_date_val="2027-08-15",
                vehicle_ids=["recVeh77"],
                date_mode="punctual",
                is_immobilized_between=False,
                shoot_dates=["2027-08-13", "2027-08-14", "2027-08-15"],
            )
            self.assertTrue(res_conflict["has_conflicts"])

    def test_punctual_mode_mixed_intervals_existing_project(self):
        """Vérifie qu'un projet existant avec des intervalles mixtes bloque ou libère correctement selon chaque intervalle."""
        with self.app.app_context():
            p_mixed = Project(
                name="Projet Mixte Intervalles",
                production_id=self.prod_id,
                date_mode="punctual",
                is_immobilized_between=False,  # Fallback global False
                shoot_dates=["2027-10-12", "2027-10-14", "2027-10-18"],
                inter_shoot_statuses={
                    "2027-10-12_2027-10-14": {"is_immobilized": True},
                    "2027-10-14_2027-10-18": {"is_immobilized": False},
                },
                shoot_start_date=date(2027, 10, 12),
                shoot_end_date=date(2027, 10, 18),
                vehicles_to_check="recVeh66",
            )
            db.session.add(p_mixed)
            db.session.commit()

            # 1. Le 13 octobre : entre le 12 et le 14 (intervalle immobilisé) -> CONFLIT
            res_immob_interval = check_booking_conflicts(
                start_date_val="2027-10-13",
                end_date_val="2027-10-13",
                vehicle_ids=["recVeh66"],
            )
            self.assertTrue(res_immob_interval["has_conflicts"])
            self.assertIn("recVeh66", res_immob_interval["conflicting_vehicle_ids"])

            # 2. Le 16 octobre : entre le 14 et le 18 (intervalle non immobilisé/libre) -> AUCUN CONFLIT
            res_free_interval = check_booking_conflicts(
                start_date_val="2027-10-16",
                end_date_val="2027-10-16",
                vehicle_ids=["recVeh66"],
            )
            self.assertFalse(res_free_interval["has_conflicts"])

            # 3. Le 14 octobre : date de tournage active -> CONFLIT
            res_shoot_day = check_booking_conflicts(
                start_date_val="2027-10-14",
                end_date_val="2027-10-14",
                vehicle_ids=["recVeh66"],
            )
            self.assertTrue(res_shoot_day["has_conflicts"])

    def test_punctual_mode_mixed_intervals_incoming_request(self):
        """Vérifie qu'une requête entrante avec intervalles mixtes ne bloque que ses intervalles immobilisés."""
        with self.app.app_context():
            # Projet continu sur le 11 novembre
            p_day11 = Project(
                name="Projet Le 11 Nov",
                production_id=self.prod_id,
                departure_date=date(2027, 11, 11),
                return_date=date(2027, 11, 11),
                vehicles_to_check="recVeh55",
            )
            # Projet continu sur le 15 novembre
            p_day15 = Project(
                name="Projet Le 15 Nov",
                production_id=self.prod_id,
                departure_date=date(2027, 11, 15),
                return_date=date(2027, 11, 15),
                vehicles_to_check="recVeh55",
            )
            db.session.add_all([p_day11, p_day15])
            db.session.commit()

            # Requête entrante ponctuelle : 10 nov, 13 nov, 17 nov
            # Intervalles : 10->13 non immobilisé (le 11 est libre), 13->17 immobilisé (le 15 est bloqué)
            incoming_inter_statuses = {
                "2027-11-10_2027-11-13": {"is_immobilized": False},
                "2027-11-13_2027-11-17": {"is_immobilized": True},
            }

            # 1. Vérification contre p_day11 (11 nov) : doit être libre (pas de conflit)
            # La requête ponctuelle couvre du 10 au 13 nov
            res_check_11 = check_booking_conflicts(
                start_date_val="2027-11-10",
                end_date_val="2027-11-13",
                vehicle_ids=["recVeh55"],
                date_mode="punctual",
                shoot_dates=["2027-11-10", "2027-11-13"],
                inter_shoot_statuses=incoming_inter_statuses,
            )
            self.assertFalse(res_check_11["has_conflicts"])

            # 2. Vérification contre p_day15 (15 nov) : doit être en conflit car 13->17 est immobilisé
            res_check_15 = check_booking_conflicts(
                start_date_val="2027-11-13",
                end_date_val="2027-11-17",
                vehicle_ids=["recVeh55"],
                date_mode="punctual",
                shoot_dates=["2027-11-13", "2027-11-17"],
                inter_shoot_statuses=incoming_inter_statuses,
            )
            self.assertTrue(res_check_15["has_conflicts"])


if __name__ == '__main__':
    unittest.main()
