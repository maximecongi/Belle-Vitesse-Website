"""
Périmètre d'accès des techniciens : ils ne voient que les projets dont ils font partie de l'équipe
Belle Vitesse (Commercial, Technicien BV, Référent plateau), sur l'ERP (listes, fiche, tableau de
bord, recherche, départs/retours, incidents, rapports), le flux ICS et l'API mobile.
"""
import unittest
from datetime import date, timedelta

from icalendar import Calendar

from models import CalendarSubscription, CheckoutVehicle, Contact, Production, Project, User, db
from models.incident import Incident
from services.admin.project_access import can_access_project, project_scope_for
from tests.base import BaseTestCase
from utils.jwt_auth import generate_token


class TechnicianProjectScopeTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        prod = Production(name="Prod Périmètre")
        self.tech = User(firstname="Tina", lastname="Tech", mail="tina@bv.fr", role="Technicien")
        self.ref = User(firstname="Rémi", lastname="Ref", mail="remi@bv.fr", role="Technicien")
        self.other = User(firstname="Oscar", lastname="Autre", mail="oscar@bv.fr", role="Technicien")
        self.commercial = User(firstname="Carla", lastname="Com", mail="carla@bv.fr", role="Commercial")
        db.session.add_all([prod, self.tech, self.ref, self.other, self.commercial])
        db.session.commit()

        today = date.today()
        self.mine = Project(
            name="Tournage Mien", production_id=prod.id,
            departure_date=today, shoot_start_date=today,
            shoot_end_date=today + timedelta(days=2), return_date=today + timedelta(days=3),
        )
        self.mine.bv_technicians = [self.tech]
        self.mine.bv_referents = [self.ref]
        self.foreign = Project(
            name="Tournage Etranger", production_id=prod.id,
            departure_date=today, shoot_start_date=today,
            shoot_end_date=today + timedelta(days=2), return_date=today + timedelta(days=3),
        )
        self.foreign.bv_technicians = [self.other]
        self.old_mine = Project(
            name="Archive Mienne", production_id=prod.id,
            departure_date=date(2024, 1, 1), shoot_start_date=date(2024, 1, 2),
            shoot_end_date=date(2024, 1, 3), return_date=date(2024, 1, 4),
        )
        self.old_mine.bv_technicians = [self.tech]
        self.old_foreign = Project(
            name="Archive Etrangere", production_id=prod.id,
            departure_date=date(2024, 1, 1), shoot_start_date=date(2024, 1, 2),
            shoot_end_date=date(2024, 1, 3), return_date=date(2024, 1, 4),
        )
        db.session.add_all([self.mine, self.foreign, self.old_mine, self.old_foreign])
        db.session.commit()

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = user.id
            sess["admin_user_role"] = user.role

    # ── Service ────────────────────────────────────────────────

    def test_scope_rules(self):
        self.assertIsNone(project_scope_for("Commercial", self.commercial.id))
        self.assertIsNone(project_scope_for("Manager", 1))
        self.assertIsNone(project_scope_for("Super Administrateur", 1))
        self.assertEqual(project_scope_for("Technicien", self.tech.id), self.tech.id)
        self.assertEqual(project_scope_for("user", self.tech.id), self.tech.id)
        # Rôle inconnu : restreint par sécurité
        self.assertEqual(project_scope_for("pilot", self.tech.id), self.tech.id)

        self.assertTrue(can_access_project(self.mine.id, self.tech.id))
        self.assertTrue(can_access_project(self.mine.project_id, self.tech.id))  # code métier
        self.assertTrue(can_access_project(self.mine.id, self.ref.id))  # référent plateau
        self.assertFalse(can_access_project(self.foreign.id, self.tech.id))
        self.assertTrue(can_access_project(self.foreign.id, None))

    def test_commercial_of_project_counts_as_member(self):
        self.foreign.commercial_user_id = self.tech.id
        db.session.commit()
        self.assertTrue(can_access_project(self.foreign.id, self.tech.id))

    def test_pilot_contact_matched_by_email_counts_as_member(self):
        pilot = Contact(first_name="T.", last_name="Pseudo", mail=" TINA@bv.fr ")
        db.session.add(pilot)
        db.session.flush()
        self.foreign.pilot_contact_id = pilot.id
        db.session.commit()
        self.assertTrue(can_access_project(self.foreign.id, self.tech.id))
        self.assertFalse(can_access_project(self.foreign.id, self.ref.id))

    def test_remote_head_operator_matched_by_name_requires_a_head(self):
        operator = Contact(first_name="Tina", last_name="Tech")  # sans e-mail : rapprochement par nom
        db.session.add(operator)
        db.session.flush()
        self.foreign.remote_head_operator_contact_id = operator.id
        db.session.commit()
        # Sans tête affectée, le rôle Opérateur Remote Head n'existe pas sur le projet
        self.assertFalse(can_access_project(self.foreign.id, self.tech.id))

        self.foreign.heads_to_check = "rec_head"
        db.session.commit()
        self.assertTrue(can_access_project(self.foreign.id, self.tech.id))

    def test_contact_with_other_email_does_not_match_on_name(self):
        homonym = Contact(first_name="Tina", last_name="Tech", mail="autre@prod.fr")
        db.session.add(homonym)
        db.session.flush()
        self.foreign.pilot_contact_id = homonym.id
        db.session.commit()
        self.assertFalse(can_access_project(self.foreign.id, self.tech.id))

    # ── ERP ────────────────────────────────────────────────────

    def test_projects_list_and_archives_are_filtered(self):
        self._login(self.tech)
        html = self.client.get("/admin/projects").get_data(as_text=True)
        self.assertIn("Tournage Mien", html)
        self.assertNotIn("Tournage Etranger", html)
        self.assertNotIn("+ Nouveau projet", html)
        self.assertNotIn("CGL & Sécurité", html)

        html = self.client.get("/admin/projects/archives").get_data(as_text=True)
        self.assertIn("Archive Mienne", html)
        self.assertNotIn("Archive Etrangere", html)

    def test_commercial_still_sees_everything(self):
        self._login(self.commercial)
        html = self.client.get("/admin/projects").get_data(as_text=True)
        self.assertIn("Tournage Mien", html)
        self.assertIn("Tournage Etranger", html)
        self.assertEqual(self.client.get(f"/admin/projects/{self.foreign.id}").status_code, 200)

    def test_project_detail_and_actions_blocked_outside_scope(self):
        self._login(self.tech)
        self.assertEqual(self.client.get(f"/admin/projects/{self.mine.id}").status_code, 200)
        self.assertEqual(self.client.get(f"/admin/projects/{self.foreign.id}").status_code, 404)
        self.assertEqual(self.client.get(f"/admin/projects/{self.foreign.project_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/admin/projects/{self.foreign.id}/print").status_code, 404)
        resp = self.client.post(
            f"/admin/projects/{self.foreign.id}/notes",
            json={"notes": "intrusion"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertIsNone(db.session.get(Project, self.foreign.id).notes)

    def test_dashboard_agenda_is_filtered(self):
        self._login(self.tech)
        html = self.client.get("/admin/dashboard").get_data(as_text=True)
        self.assertIn("Tournage Mien", html)
        self.assertNotIn("Tournage Etranger", html)

    def test_events_api_is_filtered(self):
        self._login(self.tech)
        titles = " ".join(str(e) for e in self.client.get("/admin/api/events").get_json())
        self.assertIn("Tournage Mien", titles)
        self.assertNotIn("Tournage Etranger", titles)

    def test_global_search_is_filtered(self):
        self._login(self.tech)
        data = self.client.get("/admin/api/search?q=Tournage").get_json()
        titles = [r["title"] for r in data["results"]]
        self.assertIn("Tournage Mien", titles)
        self.assertNotIn("Tournage Etranger", titles)

    def test_checkouts_are_filtered(self):
        co_mine = CheckoutVehicle(project_id=self.mine.id, controller_id=self.tech.id,
                                  inspection_date=date.today(), vehicle_id="1", status="draft")
        co_foreign = CheckoutVehicle(project_id=self.foreign.id, controller_id=self.other.id,
                                     inspection_date=date.today(), vehicle_id="2", status="draft")
        db.session.add_all([co_mine, co_foreign])
        db.session.commit()

        self._login(self.tech)
        self.assertEqual(self.client.get(f"/admin/checkouts/{co_mine.id}").status_code, 200)
        self.assertEqual(self.client.get(f"/admin/checkouts/{co_foreign.id}").status_code, 404)
        html = self.client.get("/admin/checkouts").get_data(as_text=True)
        self.assertIn("Tournage Mien", html)
        self.assertNotIn("Tournage Etranger", html)
        # Impossible de créer un départ sur un projet hors périmètre
        resp = self.client.post("/admin/checkouts/new", data={"project_id": str(self.foreign.id)})
        self.assertEqual(resp.status_code, 404)
        # Statut AJAX
        self.assertEqual(self.client.get(f"/admin/api/checkouts/{co_foreign.id}/status").status_code, 404)

    def test_incidents_are_filtered(self):
        inc_mine = Incident(incident_number="BVIC-MINE", project_id=self.mine.id, title="Pneu mien",
                            incident_date=date.today())
        inc_foreign = Incident(incident_number="BVIC-FOREIGN", project_id=self.foreign.id,
                               title="Pneu etranger", incident_date=date.today())
        inc_own_no_project = Incident(incident_number="BVIC-SOLO", title="Signalement perso",
                                      reported_by_id=self.tech.id, incident_date=date.today())
        db.session.add_all([inc_mine, inc_foreign, inc_own_no_project])
        db.session.commit()

        self._login(self.tech)
        html = self.client.get("/admin/incidents").get_data(as_text=True)
        self.assertIn("Pneu mien", html)
        self.assertIn("Signalement perso", html)
        self.assertNotIn("Pneu etranger", html)
        self.assertEqual(self.client.get(f"/admin/incidents/{inc_foreign.id}").status_code, 404)

    # ── Calendrier ICS ─────────────────────────────────────────

    def test_ics_feed_contains_only_member_projects(self):
        sub = CalendarSubscription(user_id=self.tech.id, token="tech_scope_token", is_active=True)
        db.session.add(sub)
        db.session.commit()
        resp = self.client.get("/cal/tech_scope_token.ics")
        self.assertEqual(resp.status_code, 200)
        cal = Calendar.from_ical(resp.data)
        summaries = [str(c.get("summary")) for c in cal.walk("vevent")]
        self.assertTrue(any("Tournage Mien" in s for s in summaries))
        self.assertTrue(any("Archive Mienne" in s for s in summaries))
        self.assertFalse(any("Etranger" in s or "Etrangere" in s for s in summaries))

    def test_ics_feed_full_for_commercial(self):
        sub = CalendarSubscription(user_id=self.commercial.id, token="com_scope_token", is_active=True)
        db.session.add(sub)
        db.session.commit()
        cal = Calendar.from_ical(self.client.get("/cal/com_scope_token.ics").data)
        summaries = " ".join(str(c.get("summary")) for c in cal.walk("vevent"))
        self.assertIn("Tournage Etranger", summaries)

    def test_technician_can_generate_own_calendar_link(self):
        self._login(self.tech)
        self.assertEqual(self.client.get("/admin/calendar").status_code, 200)
        self.client.post("/admin/calendar/generate", data={"user_id": self.other.id})
        # Le lien est toujours créé pour soi-même, jamais pour un autre membre
        self.assertIsNotNone(
            CalendarSubscription.query.filter_by(user_id=self.tech.id, is_active=True).first()
        )
        self.assertIsNone(CalendarSubscription.query.filter_by(user_id=self.other.id).first())

    # ── API mobile ─────────────────────────────────────────────

    def test_mobile_api_is_filtered(self):
        headers = {"Authorization": f"Bearer {generate_token(self.tech)}"}
        data = self.client.get("/api/v1/projects", headers=headers).get_json()
        names = [p["name"] for p in data]
        self.assertIn("Tournage Mien", names)
        self.assertNotIn("Tournage Etranger", names)
        self.assertEqual(self.client.get(f"/api/v1/projects/{self.mine.id}", headers=headers).status_code, 200)
        self.assertEqual(self.client.get(f"/api/v1/projects/{self.foreign.id}", headers=headers).status_code, 404)
        events = " ".join(str(e) for e in self.client.get("/api/v1/calendar/events", headers=headers).get_json())
        self.assertNotIn("Tournage Etranger", events)


if __name__ == "__main__":
    unittest.main()
