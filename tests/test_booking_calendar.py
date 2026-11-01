import json
import os
import unittest
from datetime import date
from unittest.mock import patch

# Isolation stricte de l'environnement de test
os.environ["FLASK_ENV"] = "testing"
os.environ["TESTING"] = "True"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["WTF_CSRF_ENABLED"] = "False"
os.environ["USE_SSH_TUNNEL"] = "false"

from app import create_app
from models import Production, Project, User, db


class BookingCalendarTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

            # Créer l'utilisateur admin pour les droits de session
            self.user = User(
                firstname="Admin",
                lastname="Test",
                mail="admin@test.com",
                role="Super Administrateur",
            )
            db.session.add(self.user)
            self.prod = Production(name="Production Booking Test")
            db.session.add(self.prod)
            db.session.commit()
            self.user_id = self.user.id
            self.prod_id = self.prod.id

        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = self.user_id
            sess["admin_user_role"] = "super administrateur"

    def tearDown(self):
        with self.app.app_context():
            db.session.rollback()
            db.session.remove()
            db.drop_all()

    @patch("routes.admin.booking.get_vehicles")
    def test_booking_data_continuous_project(self, mock_get_vehicles):
        mock_get_vehicles.return_value = [
            {"id": "veh1", "fields": {"name": "Véhicule Travelling 1"}}
        ]

        with self.app.app_context():
            p_continuous = Project(
                name="Projet Continu",
                production_id=self.prod_id,
                date_mode="continuous",
                departure_date=date(2027, 5, 10),
                shoot_start_date=date(2027, 5, 10),
                shoot_end_date=date(2027, 5, 15),
                return_date=date(2027, 5, 15),
                vehicles_to_check="veh1",
            )
            db.session.add(p_continuous)
            db.session.commit()

        resp = self.client.get("/admin/api/booking-data?category=vehicle")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertIn("bookings", data)
        self.assertEqual(len(data["bookings"]), 1)
        b = data["bookings"][0]
        self.assertEqual(b["item_id"], "veh1")
        self.assertEqual(b["date_mode"], "continuous")
        self.assertEqual(b["active_spans"], [{"start": "2027-05-10", "end": "2027-05-15"}])

    @patch("routes.admin.booking.get_vehicles")
    def test_booking_data_punctual_not_immobilized_frees_intermediate_days(self, mock_get_vehicles):
        """
        Vérifie qu'un projet ponctuel avec un intervalle non-immobilisé retourne des active_spans
        séparés et ne bloque pas les jours intermédiaires.
        """
        mock_get_vehicles.return_value = [
            {"id": "veh2", "fields": {"name": "Véhicule Grue 2"}}
        ]

        with self.app.app_context():
            p_punctual = Project(
                name="Projet Ponctuel Non Immobilisé",
                production_id=self.prod_id,
                date_mode="punctual",
                is_immobilized_between=False,
                shoot_dates=["2027-06-10", "2027-06-15"],
                shoot_start_date=date(2027, 6, 10),
                shoot_end_date=date(2027, 6, 15),
                vehicles_to_check="veh2",
            )
            db.session.add(p_punctual)
            db.session.commit()

        resp = self.client.get("/admin/api/booking-data?category=vehicle")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertEqual(len(data["bookings"]), 1)
        b = data["bookings"][0]
        self.assertEqual(b["item_id"], "veh2")
        self.assertEqual(b["date_mode"], "punctual")
        self.assertEqual(b["shoot_dates"], ["2027-06-10", "2027-06-15"])

        # Doit contenir 2 spans distincts pour le 10 et le 15, les 11, 12, 13, 14 étant libérés
        self.assertEqual(len(b["active_spans"]), 2)
        self.assertEqual(b["active_spans"][0], {"start": "2027-06-10", "end": "2027-06-10"})
        self.assertEqual(b["active_spans"][1], {"start": "2027-06-15", "end": "2027-06-15"})

        # Vérifier que l'intervalle est bien marqué comme non-immobilisé
        self.assertEqual(len(b["intervals"]), 1)
        self.assertFalse(b["intervals"][0]["is_immobilized"])
        self.assertIn("2027-06-11", b["intervals"][0]["days"])
        self.assertIn("2027-06-14", b["intervals"][0]["days"])

    @patch("routes.admin.booking.get_vehicles")
    def test_booking_data_punctual_immobilized_blocks_intermediate_days(self, mock_get_vehicles):
        """
        Vérifie qu'un projet ponctuel avec intervalle immobilisé bloque tout le span en continu.
        """
        mock_get_vehicles.return_value = [
            {"id": "veh3", "fields": {"name": "Véhicule Travelling 3"}}
        ]

        with self.app.app_context():
            p_immob = Project(
                name="Projet Ponctuel Immobilisé",
                production_id=self.prod_id,
                date_mode="punctual",
                is_immobilized_between=True,
                shoot_dates=["2027-07-10", "2027-07-12"],
                shoot_start_date=date(2027, 7, 10),
                shoot_end_date=date(2027, 7, 12),
                vehicles_to_check="veh3",
            )
            db.session.add(p_immob)
            db.session.commit()

        resp = self.client.get("/admin/api/booking-data?category=vehicle")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertEqual(len(data["bookings"]), 1)
        b = data["bookings"][0]
        self.assertEqual(b["item_id"], "veh3")
        self.assertEqual(b["date_mode"], "punctual")
        # Le span doit être continu car le 11 juillet est immobilisé
        self.assertEqual(b["active_spans"], [{"start": "2027-07-10", "end": "2027-07-12"}])
        self.assertTrue(b["intervals"][0]["is_immobilized"])

