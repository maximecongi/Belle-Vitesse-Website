"""
Tests unitaires pour la route publique du flux calendrier iCal (/cal/<token>.ics).
Couvre la validation des tokens, la génération granulaire des événements
(départ, tournage continu, tournage ponctuel par blocs, immobilisations, retour),
et la conformité du format iCalendar.
"""
from models import CalendarSubscription, Contact, Production, Project, User, db
from icalendar import Calendar
from app import create_app
from datetime import date, timedelta
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")))

# Mock WeasyPrint
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint


class CalendarFeedTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        os.environ["WTF_CSRF_ENABLED"] = "False"
        os.environ["LAUNCH_MODE"] = "false"
        os.environ["USE_SSH_TUNNEL"] = "false"

        self.app = create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

            # Utilisateur et token d'abonnement
            self.user = User(
                firstname="Jean",
                lastname="Dupont",
                mail="jean.dupont@bellevitesse.com",
                role="administrator",
            )
            db.session.add(self.user)
            db.session.commit()
            self.user_id = self.user.id

            self.sub = CalendarSubscription(
                user_id=self.user_id,
                token="valid_test_token_12345",
                is_active=True,
            )
            db.session.add(self.sub)

            self.sub_inactive = CalendarSubscription(
                user_id=self.user.id,
                token="revoked_token_67890",
                is_active=False,
            )
            db.session.add(self.sub_inactive)

            # Production & contacts de test
            self.prod = Production(name="SuperProd Films")
            db.session.add(self.prod)
            db.session.commit()
            self.prod_id = self.prod.id

            self.contact_pilot = Contact(
                first_name="Alain",
                last_name="Prost",
                phone="+33 6 11 22 33 44",
                mail="pilot@bv.fr",
                production_id=self.prod_id,
            )
            self.contact_dop = Contact(
                first_name="Roger",
                last_name="Deakins",
                phone="+33 6 99 88 77 66",
                mail="dop@bv.fr",
                production_id=self.prod_id,
            )
            db.session.add_all([self.contact_pilot, self.contact_dop])
            db.session.commit()
            self.contact_pilot_id = self.contact_pilot.id
            self.contact_dop_id = self.contact_dop.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_calendar_feed_invalid_token(self):
        """Vérifie qu'un token inexistant retourne 404."""
        resp = self.client.get("/cal/unknown_token.ics")
        self.assertEqual(resp.status_code, 404)

        # Un token révoqué pour un utilisateur ayant un token actif est redirigé (302)
        resp_revoked = self.client.get("/cal/revoked_token_67890.ics")
        self.assertEqual(resp_revoked.status_code, 302)
        self.assertIn("valid_test_token_12345",
                      resp_revoked.headers.get("Location", ""))

        # Suivre la redirection renvoie 200
        resp_followed = self.client.get(
            "/cal/revoked_token_67890.ics", follow_redirects=True)
        self.assertEqual(resp_followed.status_code, 200)

        # Si l'utilisateur n'a aucun token actif, renvoie 404
        with self.app.app_context():
            CalendarSubscription.query.filter_by(
                user_id=self.user_id).update({"is_active": False})
            db.session.commit()

        resp_no_active = self.client.get("/cal/revoked_token_67890.ics")
        self.assertEqual(resp_no_active.status_code, 404)

    def test_calendar_feed_alias_route(self):
        """Vérifie que la route alias /calendar/feed.ics?token=... fonctionne."""
        resp = self.client.get(
            "/calendar/feed.ics?token=valid_test_token_12345")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "text/calendar")

    def test_calendar_feed_continuous_project(self):
        """Vérifie la génération d'un projet continu (un seul événement continu du début à la fin du tournage, sans départs ni retours)."""
        with self.app.app_context():
            p = Project(
                name="Tournage Continu Pub",
                project_id="PROJ-CONT-01",
                production_id=self.prod_id,
                pilot_contact_id=self.contact_pilot_id,
                dop_contact_id=self.contact_dop_id,
                departure_date=date(2026, 10, 10),
                shoot_start_date=date(2026, 10, 12),
                shoot_end_date=date(2026, 10, 14),
                return_date=date(2026, 10, 15),
                date_mode="continuous",
                notes="Prévoir pneus pluie",
            )
            db.session.add(p)
            db.session.commit()
            proj_id = p.id

        resp = self.client.get("/cal/valid_test_token_12345.ics")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "text/calendar")
        self.assertIn("Content-Disposition", resp.headers)

        cal = Calendar.from_ical(resp.data)
        events = [c for c in cal.walk() if c.name == "VEVENT"]

        # Doit contenir exactement 1 événement continu (Départ et Retour exclus)
        self.assertEqual(len(events), 1)

        shoot_evt = events[0]
        self.assertEqual(str(shoot_evt.get("summary")), "🎬 Tournage : Tournage Continu Pub")

        # Vérification des dates (du début à la fin du tournage + 1j pour dtend exclusif iCal)
        self.assertEqual(shoot_evt.get("dtstart").dt, date(2026, 10, 12))
        self.assertEqual(shoot_evt.get("dtend").dt, date(2026, 10, 15))  # 14 + 1 jour
        self.assertEqual(str(shoot_evt.get("uid")), f"bv-project-{proj_id}-shoot@bellevitesse.com")

        # Vérification de la description riche conservée
        desc = str(shoot_evt.get("description"))
        self.assertIn("Alain Prost", desc)
        self.assertIn("+33 6 11 22 33 44", desc)
        self.assertIn("Roger Deakins", desc)
        self.assertIn("Prévoir pneus pluie", desc)
        self.assertIn("SuperProd Films", desc)
        self.assertIn("PROJ-CONT-01", desc)
        self.assertIn("Départ : 10/10/2026", desc)
        self.assertIn("Retour : 15/10/2026", desc)

    def test_calendar_feed_punctual_project_with_immobilization(self):
        """
        Vérifie la génération d'un projet ponctuel simplifié :
        - Un seul événement continu couvrant de la 1re date de tournage à la dernière date de tournage
        - Départs et retours exclus du calendrier
        - Conservation de la description riche détaillant les dates ponctuelles et les immobilisations
        """
        with self.app.app_context():
            p = Project(
                name="Clip Ponctuel Cascade",
                project_id="PROJ-PUNCT-02",
                production_id=self.prod_id,
                departure_date=date(2026, 10, 1),
                date_mode="punctual",
                # Tournages : 3-4 Oct, 8 Oct, 12 Oct
                shoot_dates=["2026-10-03", "2026-10-04",
                             "2026-10-08", "2026-10-12"],
                # Intervalle 1 (5 au 7 Oct) : Immobilisé sur place
                inter_shoot_statuses=[
                    {"start": "2026-10-04", "end": "2026-10-08",
                        "is_immobilized": True},
                    {"start": "2026-10-08", "end": "2026-10-12",
                        "is_immobilized": False},
                ],
                return_date=date(2026, 10, 13),
            )
            db.session.add(p)
            db.session.commit()
            proj_id = p.id

        resp = self.client.get("/cal/valid_test_token_12345.ics")
        self.assertEqual(resp.status_code, 200)

        cal = Calendar.from_ical(resp.data)
        events = [c for c in cal.walk() if c.name == "VEVENT"]

        # Devrait générer exactement 1 événement continu couvrant du 3 au 12 Octobre
        self.assertEqual(len(events), 1)

        shoot_evt = events[0]
        self.assertEqual(str(shoot_evt.get("summary")), "🎬 Tournage : Clip Ponctuel Cascade")
        self.assertEqual(shoot_evt.get("dtstart").dt, date(2026, 10, 3))
        self.assertEqual(shoot_evt.get("dtend").dt, date(2026, 10, 13))  # 12 Oct + 1 jour
        self.assertEqual(str(shoot_evt.get("uid")), f"bv-project-{proj_id}-shoot@bellevitesse.com")

        # Vérification que la description détaillée conserve le détail des jours et de l'immobilisation
        desc = str(shoot_evt.get("description"))
        self.assertIn("Tournage (4j) : 03/10/2026, 04/10/2026, 08/10/2026, 12/10/2026", desc)
        self.assertIn("Immobilisé sur place (3j)", desc)
        self.assertIn("Départ : 01/10/2026", desc)
        self.assertIn("Retour : 13/10/2026", desc)

    def test_calendar_feed_excludes_projects_without_shoot_dates(self):
        """Vérifie qu'un projet ayant seulement une date de départ ou retour (sans tournage) ne crée pas d'événement."""
        with self.app.app_context():
            p = Project(
                name="Transport Pur",
                project_id="PROJ-TRANS-01",
                production_id=self.prod_id,
                departure_date=date(2026, 10, 1),
                return_date=date(2026, 10, 2),
                date_mode="continuous",
            )
            db.session.add(p)
            db.session.commit()

        resp = self.client.get("/cal/valid_test_token_12345.ics")
        self.assertEqual(resp.status_code, 200)
        cal = Calendar.from_ical(resp.data)
        events = [c for c in cal.walk() if c.name == "VEVENT"]
        self.assertEqual(len(events), 0)

    @patch("routes.public.calendar_feed.get_vehicles")
    @patch("routes.public.calendar_feed.get_heads")
    def test_calendar_feed_vehicles_and_heads_resolution(self, mock_heads, mock_vehicles):
        """Vérifie que les noms de véhicules et têtes sont correctement injectés dans les descriptions."""
        mock_vehicles.return_value = [
            {"id": "recVeh1", "fields": {"name": "AUDI RS4 Tracking Car"}},
            {"id": "recVeh2", "fields": {"name": "PORSCHE CAYENNE Turbo"}},
        ]
        mock_heads.return_value = [
            {"id": "recHead1", "fields": {"name": "FLIGHT HEAD V"}},
        ]

        with self.app.app_context():
            p = Project(
                name="Long-Métrage Course",
                project_id="PROJ-MAT-03",
                production_id=self.prod_id,
                departure_date=date(2026, 11, 1),
                shoot_start_date=date(2026, 11, 2),
                return_date=date(2026, 11, 3),
                vehicles_to_check="recVeh1, recVeh2",
                heads_to_check="recHead1",
            )
            db.session.add(p)
            db.session.commit()

        resp = self.client.get("/cal/valid_test_token_12345.ics")
        self.assertEqual(resp.status_code, 200)

        cal = Calendar.from_ical(resp.data)
        events = [c for c in cal.walk() if c.name == "VEVENT"]
        self.assertTrue(len(events) >= 1)

        desc = str(events[0].get("description"))
        self.assertIn("AUDI RS4 Tracking Car", desc)
        self.assertIn("PORSCHE CAYENNE Turbo", desc)
        self.assertIn("FLIGHT HEAD V", desc)


if __name__ == "__main__":
    unittest.main()
