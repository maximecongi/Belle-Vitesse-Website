"""
Tests unitaires pour la route publique du flux calendrier iCal (/cal/<token>.ics).
Couvre la validation des tokens, la génération granulaire des événements
(départ, tournage continu, tournage ponctuel par blocs, immobilisations, retour),
et la conformité du format iCalendar.
"""
from datetime import date, timedelta
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock WeasyPrint
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from app import create_app
from icalendar import Calendar
from models import CalendarSubscription, Contact, Production, Project, User, db


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

            self.sub = CalendarSubscription(
                user_id=self.user.id,
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
        """Vérifie qu'un token inexistant ou inactif retourne 404."""
        resp = self.client.get("/cal/unknown_token.ics")
        self.assertEqual(resp.status_code, 404)

        resp_revoked = self.client.get("/cal/revoked_token_67890.ics")
        self.assertEqual(resp_revoked.status_code, 404)

    def test_calendar_feed_continuous_project(self):
        """Vérifie la génération d'un projet continu (départ, tournage continu, retour)."""
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

        # Doit contenir 3 événements : Départ, Tournage, Retour
        self.assertEqual(len(events), 3)

        summaries = [str(e.get("summary")) for e in events]
        self.assertIn("🚚 Départ : Tournage Continu Pub", summaries)
        self.assertIn("🎬 Tournage : Tournage Continu Pub", summaries)
        self.assertIn("📦 Retour : Tournage Continu Pub", summaries)

        # Vérification des dates
        dep_evt = next(e for e in events if "🚚" in str(e.get("summary")))
        self.assertEqual(dep_evt.get("dtstart").dt, date(2026, 10, 10))
        self.assertEqual(dep_evt.get("dtend").dt, date(2026, 10, 11))
        self.assertEqual(str(dep_evt.get("uid")), f"bv-project-{proj_id}-checkout@bellevitesse.com")

        shoot_evt = next(e for e in events if "🎬" in str(e.get("summary")))
        self.assertEqual(shoot_evt.get("dtstart").dt, date(2026, 10, 12))
        self.assertEqual(shoot_evt.get("dtend").dt, date(2026, 10, 15))  # 14 + 1 jour
        self.assertEqual(str(shoot_evt.get("uid")), f"bv-project-{proj_id}-shoot@bellevitesse.com")

        ret_evt = next(e for e in events if "📦" in str(e.get("summary")))
        self.assertEqual(ret_evt.get("dtstart").dt, date(2026, 10, 15))
        self.assertEqual(ret_evt.get("dtend").dt, date(2026, 10, 16))
        self.assertEqual(str(ret_evt.get("uid")), f"bv-project-{proj_id}-checkin@bellevitesse.com")

        # Vérification de la description riche
        desc = str(shoot_evt.get("description"))
        self.assertIn("Alain Prost", desc)
        self.assertIn("+33 6 11 22 33 44", desc)
        self.assertIn("Roger Deakins", desc)
        self.assertIn("Prévoir pneus pluie", desc)
        self.assertIn("SuperProd Films", desc)
        self.assertIn("PROJ-CONT-01", desc)

    def test_calendar_feed_punctual_project_with_immobilization(self):
        """
        Vérifie la génération d'un projet ponctuel :
        - Bloc de dates consécutives regroupé
        - Date isolée en bloc distinct
        - Période intermédiaire immobilisée générée avec '🔒 Immobilisé'
        - Période intermédiaire relâchée non générée (laisse le calendrier libre)
        """
        with self.app.app_context():
            p = Project(
                name="Clip Ponctuel Cascade",
                project_id="PROJ-PUNCT-02",
                production_id=self.prod_id,
                departure_date=date(2026, 10, 1),
                date_mode="punctual",
                # Tournages : 3-4 Oct (bloc 1), 8 Oct (bloc 2), 12 Oct (bloc 3)
                shoot_dates=["2026-10-03", "2026-10-04", "2026-10-08", "2026-10-12"],
                # Intervalle 1 (5 au 7 Oct) : Immobilisé sur place
                # Intervalle 2 (9 au 11 Oct) : Relâché (is_immobilized = False)
                inter_shoot_statuses=[
                    {"start": "2026-10-04", "end": "2026-10-08", "is_immobilized": True},
                    {"start": "2026-10-08", "end": "2026-10-12", "is_immobilized": False},
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

        # Devrait générer :
        # 1x Départ (1er Oct)
        # 3x Tournage (3-4 Oct, 8 Oct, 12 Oct)
        # 1x Immobilisation (5 au 7 Oct inclus)
        # 0x pour l'intervalle relâché (9 au 11 Oct reste libre)
        # 1x Retour (13 Oct)
        # Total = 6 événements
        self.assertEqual(len(events), 6)

        shoot_events = [e for e in events if "Tournage" in str(e.get("summary"))]
        self.assertEqual(len(shoot_events), 3)

        # Bloc 1 (3-4 Oct)
        self.assertEqual(shoot_events[0].get("dtstart").dt, date(2026, 10, 3))
        self.assertEqual(shoot_events[0].get("dtend").dt, date(2026, 10, 5))
        self.assertEqual(str(shoot_events[0].get("uid")), f"bv-project-{proj_id}-shoot-1@bellevitesse.com")

        # Bloc 2 (8 Oct)
        self.assertEqual(shoot_events[1].get("dtstart").dt, date(2026, 10, 8))
        self.assertEqual(shoot_events[1].get("dtend").dt, date(2026, 10, 9))
        self.assertEqual(str(shoot_events[1].get("uid")), f"bv-project-{proj_id}-shoot-2@bellevitesse.com")

        # Bloc 3 (12 Oct)
        self.assertEqual(shoot_events[2].get("dtstart").dt, date(2026, 10, 12))
        self.assertEqual(shoot_events[2].get("dtend").dt, date(2026, 10, 13))
        self.assertEqual(str(shoot_events[2].get("uid")), f"bv-project-{proj_id}-shoot-3@bellevitesse.com")

        # Événement d'immobilisation (5 au 7 Oct inclus -> dtstart: 5, dtend: 8)
        immob_events = [e for e in events if "Immobilisé" in str(e.get("summary"))]
        self.assertEqual(len(immob_events), 1)
        immob = immob_events[0]
        self.assertEqual(str(immob.get("summary")), "🔒 Immobilisé : Clip Ponctuel Cascade")
        self.assertEqual(immob.get("dtstart").dt, date(2026, 10, 5))
        self.assertEqual(immob.get("dtend").dt, date(2026, 10, 8))
        self.assertEqual(str(immob.get("uid")), f"bv-project-{proj_id}-immob-1@bellevitesse.com")
        self.assertIn("Immobilisation sur place (3j)", str(immob.get("description")))

        # Vérifier qu'aucun événement ne bloque la période relâchée du 9 au 11 Octobre
        all_dates_covered = []
        for e in events:
            cur = e.get("dtstart").dt
            end = e.get("dtend").dt
            while cur < end:
                all_dates_covered.append(cur)
                cur += timedelta(days=1)

        self.assertNotIn(date(2026, 10, 9), all_dates_covered)
        self.assertNotIn(date(2026, 10, 10), all_dates_covered)
        self.assertNotIn(date(2026, 10, 11), all_dates_covered)

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
