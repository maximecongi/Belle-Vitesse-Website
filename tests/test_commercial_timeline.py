"""Timeline commerciale des projets : saisie, statut déduit, échelle de la frise, relances, accès."""
import unittest
from datetime import date, datetime, timedelta

from models import Contact, Project, ProjectCommercialEvent, db
from services.admin.commercial_timeline import (
    BREAK_THRESHOLD_DAYS,
    MIN_SEGMENT_PCT,
    NEW_CONTACT_VALUE,
    CommercialEventNotFoundError,
    add_commercial_event,
    build_commercial_timeline,
    compute_timeline_layout,
    delete_commercial_event,
    find_projects_awaiting_quote_reply,
    followup_due,
)
from tests.base import BaseTestCase

NOW = datetime(2026, 11, 12, 15, 0)


class CommercialTimelineServiceTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.create_user(firstname="Carla", lastname="Com", mail="carla@bv.fr", role="Commercial")
        self.prod = self.create_production("Prod Timeline")
        self.contact = self.create_contact(production_id=self.prod.id, first_name="Jeanne", last_name="Martin")
        self.project = Project(name="Pub Timeline", production_id=self.prod.id)
        db.session.add(self.project)
        db.session.commit()

    def _add(self, event_type, day, time_str="10:00", **kw):
        return add_commercial_event(
            self.project.id, event_type=event_type, date_str=day, time_str=time_str,
            user_id=self.user.id, now=NOW, **kw,
        )

    def test_new_project_starts_as_prospect(self):
        self.assertEqual(self.project.commercial_status, "prospect")

    def test_add_event_records_author_contact_and_summary(self):
        ev = self._add("email_in", "2026-11-01", contact_id=self.contact.id, summary="  Demande de dispo  ")
        self.assertEqual(ev.occurred_at, datetime(2026, 11, 1, 10, 0))
        self.assertEqual(ev.author_name, "Carla Com")
        self.assertEqual(ev.contact_name, "Jeanne Martin")
        self.assertEqual(ev.summary, "Demande de dispo")

    def test_status_follows_last_milestone(self):
        self._add("first_request", "2026-10-01")
        self._add("quote_sent", "2026-10-03")
        self.assertEqual(self.project.commercial_status, "quote_sent")
        self._add("email_in", "2026-10-05")  # un simple échange ne change pas le statut
        self.assertEqual(self.project.commercial_status, "quote_sent")
        confirmed = self._add("confirmed", "2026-10-08")
        self.assertEqual(self.project.commercial_status, "confirmed")
        # Un jalon saisi a posteriori à une date antérieure ne l'emporte pas
        self._add("quote_sent", "2026-10-02")
        self.assertEqual(self.project.commercial_status, "confirmed")
        delete_commercial_event(self.project.id, confirmed.id)
        self.assertEqual(self.project.commercial_status, "quote_sent")

    def test_lost_requires_reason(self):
        with self.assertRaises(ValueError):
            self._add("lost", "2026-11-01")
        ev = self._add("lost", "2026-11-01", lost_reason="price")
        self.assertEqual(ev.lost_reason_label, "Prix")
        self.assertEqual(self.project.commercial_status, "lost")

    def test_lost_reason_ignored_for_other_types(self):
        ev = self._add("call_in", "2026-11-01", lost_reason="price")
        self.assertIsNone(ev.lost_reason)

    def test_rejects_invalid_input(self):
        with self.assertRaises(ValueError):
            self._add("fax", "2026-11-01")
        with self.assertRaises(ValueError):
            self._add("call_in", "pas-une-date")
        with self.assertRaises(ValueError):
            self._add("call_in", "2026-11-01", time_str="25:99")
        with self.assertRaises(ValueError):
            self._add("call_in", "2026-11-13")  # futur
        with self.assertRaises(ValueError):
            self._add("call_in", "2026-11-01", contact_id=99999)
        self.assertEqual(ProjectCommercialEvent.query.count(), 0)

    def test_time_is_optional(self):
        ev = self._add("meeting", "2026-11-01", time_str="")
        self.assertEqual(ev.occurred_at, datetime(2026, 11, 1, 0, 0))

    def test_legacy_project_stays_untracked_until_milestone(self):
        self.project.commercial_status = None
        db.session.commit()
        call = self._add("call_in", "2026-11-01")
        self.assertIsNone(self.project.commercial_status)
        quote = self._add("quote_sent", "2026-11-02")
        self.assertEqual(self.project.commercial_status, "quote_sent")
        delete_commercial_event(self.project.id, quote.id)
        self.assertEqual(self.project.commercial_status, "prospect")
        delete_commercial_event(self.project.id, call.id)

    def test_delete_checks_project(self):
        ev = self._add("call_in", "2026-11-01")
        with self.assertRaises(CommercialEventNotFoundError):
            delete_commercial_event(self.project.id + 1, ev.id)
        with self.assertRaises(CommercialEventNotFoundError):
            add_commercial_event(999999, event_type="call_in", date_str="2026-11-01", now=NOW)

    def test_events_deleted_with_project(self):
        self._add("call_in", "2026-11-01")
        db.session.delete(self.project)
        db.session.commit()
        self.assertEqual(ProjectCommercialEvent.query.count(), 0)

    # ── Relances ───────────────────────────────────────────────

    def test_followup_due_after_unanswered_quote(self):
        self._add("quote_sent", "2026-10-20")
        self.assertEqual(followup_due(self.project.commercial_events, "quote_sent", now=NOW), 23)
        found = find_projects_awaiting_quote_reply(now=NOW)
        self.assertEqual([r["project"].id for r in found], [self.project.id])
        self.assertEqual(found[0]["days_waiting"], 23)

    def test_no_followup_when_client_answered_or_recent(self):
        self._add("quote_sent", "2026-10-20")
        self._add("email_in", "2026-10-25")
        self.assertIsNone(followup_due(self.project.commercial_events, "quote_sent", now=NOW))
        self._add("quote_followup", "2026-11-10")
        self.assertIsNone(followup_due(self.project.commercial_events, "quote_sent", now=NOW))
        self.assertEqual(find_projects_awaiting_quote_reply(now=NOW), [])

    # ── Contexte de la fiche ───────────────────────────────────

    def test_build_timeline_context(self):
        self._add("first_request", "2026-09-01")
        self._add("email_out", "2026-09-02")
        self._add("quote_sent", "2026-10-20", contact_id=self.contact.id)
        tl = build_commercial_timeline(self.project, now=NOW)
        self.assertEqual(tl["count"], 3)
        self.assertEqual(tl["status_label"], "Devis envoyé")
        self.assertEqual(tl["followup_days"], 23)
        self.assertEqual([e["pct"] for e in tl["events"]][0], 0.0)
        self.assertIsNotNone(tl["today_pct"])
        self.assertTrue(tl["segments"][1]["is_break"])  # 48 j de silence
        self.assertTrue(tl["segments"][-1]["is_pending"])
        self.assertIn((self.contact.id, "Jeanne Martin"), tl["contact_choices"]["project"])

    # ── Contacts ───────────────────────────────────────────────

    def test_contact_choices_include_whole_directory(self):
        other_prod = self.create_production("Autre Prod")
        outsider = self.create_contact(production_id=other_prod.id, first_name="Paul", last_name="Externe",
                                       mail="paul@x.fr")
        choices = build_commercial_timeline(self.project, now=NOW)["contact_choices"]
        self.assertNotIn(outsider.id, [cid for cid, _ in choices["project"]])
        self.assertIn((outsider.id, "Paul Externe — Autre Prod"), choices["others"])

    def test_new_contact_created_with_project_production(self):
        ev = self._add("call_in", "2026-11-01", contact_id=NEW_CONTACT_VALUE, new_contact={
            "first_name": " Léa ", "last_name": "Nouvelle", "phone": "0600000000", "mail": "lea@prod.fr",
        })
        self.assertEqual(ev.contact_name, "Léa Nouvelle")
        self.assertEqual(ev.contact.production_id, self.prod.id)
        self.assertEqual(ev.contact.mail, "lea@prod.fr")

    def test_new_contact_reuses_existing_homonym(self):
        self.contact.mail = None
        db.session.commit()
        ev = self._add("call_in", "2026-11-01", contact_id=NEW_CONTACT_VALUE, new_contact={
            "first_name": "jeanne", "last_name": "MARTIN", "mail": "jeanne@prod.fr",
        })
        self.assertEqual(ev.contact_id, self.contact.id)
        self.assertEqual(self.contact.mail, "jeanne@prod.fr")  # champ vide complété
        self.assertEqual(Contact.query.count(), 1)

    def test_new_contact_requires_names_and_is_not_created_on_error(self):
        with self.assertRaises(ValueError):
            self._add("call_in", "2026-11-01", contact_id=NEW_CONTACT_VALUE, new_contact={"first_name": "Solo"})
        with self.assertRaises(ValueError):  # motif d'abandon manquant : aucun contact ne doit être créé
            self._add("lost", "2026-11-01", contact_id=NEW_CONTACT_VALUE,
                      new_contact={"first_name": "Léa", "last_name": "Fantome"})
        db.session.commit()
        self.assertEqual(Contact.query.count(), 1)

    def test_closed_project_has_no_today_marker(self):
        self._add("first_request", "2026-09-01")
        self._add("lost", "2026-09-10", lost_reason="dates")
        tl = build_commercial_timeline(self.project, now=NOW)
        self.assertIsNone(tl["today_pct"])
        self.assertEqual(tl["events"][-1]["pct"], 100.0)


class TimelineLayoutTest(unittest.TestCase):
    def _moments(self, *days):
        base = datetime(2026, 1, 1)
        return [base + timedelta(days=d) for d in days]

    def test_empty_and_single(self):
        self.assertEqual(compute_timeline_layout([]), ([], []))
        self.assertEqual(compute_timeline_layout(self._moments(0)), ([50.0], []))

    def test_proportional_spacing(self):
        pos, segs = compute_timeline_layout(self._moments(0, 10, 30))
        self.assertEqual(pos[0], 0.0)
        self.assertEqual(pos[-1], 100.0)
        w1, w2 = pos[1] - pos[0], pos[2] - pos[1]
        # Hors largeur minimale, l'écart restant est proportionnel (10 j vs 20 j)
        self.assertAlmostEqual((w2 - MIN_SEGMENT_PCT) / (w1 - MIN_SEGMENT_PCT), 2.0, places=2)
        self.assertFalse(any(s["is_break"] for s in segs))

    def test_minimum_gap_for_simultaneous_events(self):
        pos, _ = compute_timeline_layout(self._moments(0, 0, 0, 20))
        gaps = [b - a for a, b in zip(pos, pos[1:])]
        self.assertTrue(all(g >= MIN_SEGMENT_PCT - 0.01 for g in gaps))

    def test_long_silence_is_capped_and_flagged(self):
        pos, segs = compute_timeline_layout(self._moments(0, BREAK_THRESHOLD_DAYS, BREAK_THRESHOLD_DAYS + 200))
        self.assertTrue(segs[1]["is_break"])
        self.assertAlmostEqual(segs[1]["days"], 200)
        # 200 j compressés pèsent autant qu'un intervalle au seuil
        self.assertAlmostEqual(pos[1], 50.0, places=2)

    def test_many_events_fit(self):
        pos, _ = compute_timeline_layout(self._moments(*range(60)))
        self.assertEqual(pos[-1], 100.0)
        self.assertTrue(all(b > a for a, b in zip(pos, pos[1:])))


class CommercialTimelineRoutesTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.commercial = self.create_user(firstname="Carla", lastname="Com", mail="carla@bv.fr", role="Commercial")
        self.tech = self.create_user(firstname="Tina", lastname="Tech", mail="tina@bv.fr", role="Technicien")
        prod = self.create_production("Prod Routes")
        today = date.today()
        self.project = Project(
            name="Tournage Routes", production_id=prod.id,
            departure_date=today, shoot_start_date=today,
            shoot_end_date=today + timedelta(days=1), return_date=today + timedelta(days=2),
        )
        self.project.bv_technicians = [self.tech]
        db.session.add(self.project)
        db.session.commit()

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = user.id
            sess["admin_user_role"] = user.role

    def _post_event(self, **data):
        payload = {"event_type": "call_in", "occurred_date": date.today().isoformat(), "occurred_time": "09:30"}
        payload.update(data)
        return self.client.post(f"/admin/projects/{self.project.id}/commercial-events", data=payload)

    def test_commercial_adds_and_sees_timeline(self):
        self._login(self.commercial)
        resp = self._post_event(summary="Premier appel")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("#commercial-timeline", resp.headers["Location"])
        self.assertEqual(ProjectCommercialEvent.query.count(), 1)

        html = self.client.get(f"/admin/projects/{self.project.id}").get_data(as_text=True)
        self.assertIn('id="commercial-timeline"', html)
        self.assertIn("Premier appel", html)

    def test_commercial_adds_event_with_new_contact(self):
        self._login(self.commercial)
        self._post_event(contact_id="__new__", new_contact_first_name="Hugo", new_contact_last_name="Prod",
                         new_contact_mail="hugo@prod.fr")
        ev = ProjectCommercialEvent.query.one()
        self.assertEqual(ev.contact.mail, "hugo@prod.fr")
        self.assertEqual(ev.contact.production_id, self.project.production_id)

    def test_commercial_deletes_event(self):
        self._login(self.commercial)
        self._post_event()
        ev = ProjectCommercialEvent.query.one()
        resp = self.client.post(f"/admin/projects/{self.project.id}/commercial-events/{ev.id}/delete")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(ProjectCommercialEvent.query.count(), 0)

    def test_invalid_event_is_rejected_without_crash(self):
        self._login(self.commercial)
        resp = self._post_event(event_type="lost")  # motif manquant
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(ProjectCommercialEvent.query.count(), 0)

    def test_technician_cannot_see_nor_write(self):
        self._login(self.tech)
        html = self.client.get(f"/admin/projects/{self.project.id}").get_data(as_text=True)
        self.assertIn("Tournage Routes", html)
        self.assertNotIn('id="commercial-timeline"', html)
        self._post_event()
        self.assertEqual(ProjectCommercialEvent.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
