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
    commercial_stats,
    build_commercial_timeline,
    compute_timeline_layout,
    delete_commercial_event,
    update_commercial_event,
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

    # ── Modification ───────────────────────────────────────────

    def test_update_event_recomputes_status_and_keeps_author(self):
        self._add("first_request", "2026-10-01")
        ev = self._add("call_in", "2026-10-02", summary="Appel")
        updated = update_commercial_event(
            self.project.id, ev.id, event_type="confirmed", date_str="2026-10-05", time_str="",
            contact_id=self.contact.id, summary="Confirmé par tél.", now=NOW,
        )
        self.assertEqual(updated.event_type, "confirmed")
        self.assertEqual(updated.occurred_at, datetime(2026, 10, 5))
        self.assertEqual(updated.contact_id, self.contact.id)
        self.assertEqual(updated.author_name, "Carla Com")
        self.assertEqual(self.project.commercial_status, "confirmed")

    def test_update_validates_and_checks_project(self):
        ev = self._add("call_in", "2026-10-02")
        with self.assertRaises(ValueError):
            update_commercial_event(self.project.id, ev.id, event_type="lost", date_str="2026-10-02", now=NOW)
        with self.assertRaises(CommercialEventNotFoundError):
            update_commercial_event(self.project.id + 1, ev.id, event_type="call_in", date_str="2026-10-02", now=NOW)
        db.session.refresh(ev)
        self.assertEqual(ev.event_type, "call_in")

    def test_edit_payload_for_modal(self):
        self._add("lost", "2026-10-02", time_str="", lost_reason="price", summary="Trop cher",
                  contact_id=self.contact.id)
        edit = build_commercial_timeline(self.project, now=NOW)["events"][0]["edit"]
        self.assertEqual(edit, {"event_type": "lost", "is_planned": "0", "date": "2026-10-02", "time": "", "contact_id": str(self.contact.id),
                                "lost_reason": "price", "summary": "Trop cher", "quote_amount": "", "quote_file_name": ""})

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
        self.assertEqual(round(tl["segments"][1]["days"]), 48)
        self.assertFalse(tl["segments"][1]["is_break"])  # 48 j < seuil de coupure (60 j)
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

    def test_new_contact_chosen_production_and_job(self):
        other = self.create_production("Autre Prod Choisie")
        ev = self._add("call_in", "2026-11-01", contact_id=NEW_CONTACT_VALUE, new_contact={
            "first_name": "Ana", "last_name": "Ailleurs", "job_title": "Producteur.rice",
            "production_id": str(other.id),
        })
        self.assertEqual(ev.contact.production_id, other.id)
        self.assertEqual(ev.contact.job_title, "Producteur.rice")
        # Choix « Aucune / Freelance » (valeur vide) : pas de production
        ev2 = self._add("call_in", "2026-11-02", contact_id=NEW_CONTACT_VALUE, new_contact={
            "first_name": "Fred", "last_name": "Lance", "production_id": "",
        })
        self.assertIsNone(ev2.contact.production_id)
        with self.assertRaises(ValueError):
            self._add("call_in", "2026-11-03", contact_id=NEW_CONTACT_VALUE, new_contact={
                "first_name": "Ghost", "last_name": "Prod", "production_id": "999999",
            })

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

    def test_contact_headline_and_tooltip(self):
        self.contact.job_title = "Directrice de production"
        db.session.commit()
        self._add("email_out", "2026-11-01", contact_id=self.contact.id)
        self._add("call_in", "2026-11-02", contact_id=self.contact.id)
        self._add("meeting", "2026-11-03")
        events = build_commercial_timeline(self.project, now=NOW)["events"]
        self.assertEqual([e["headline"] for e in events],
                         ["Mail envoyé à Jeanne Martin", "Appel reçu de Jeanne Martin", "Rendez-vous / visio"])
        self.assertEqual(events[0]["contact_details"],
                         "Directrice de production · Prod Timeline\n0612345678\ncontact@test.com")

    def test_scale_counts_days_not_hours(self):
        # 3 événements le même jour (heures très différentes), puis un autre 10 jours plus tard
        self._add("first_request", "2026-10-01", time_str="08:00")
        self._add("email_out", "2026-10-01", time_str="08:05")
        self._add("call_in", "2026-10-01", time_str="19:30")
        self._add("quote_sent", "2026-10-11", time_str="09:00")
        tl = build_commercial_timeline(self.project, now=NOW)
        # Un seul point pour la journée du 1er octobre (3 échanges, quelle que soit l'heure), puis le 11
        self.assertEqual([n["count"] for n in tl["nodes"]], [3, 1])
        self.assertEqual(len({e["pct"] for e in tl["events"][:3]}), 1)
        self.assertEqual(tl["nodes"][0]["icon"], "inbox")  # point représentatif : le jalon du jour
        self.assertIn("3 échanges le 1 oct.", tl["nodes"][0]["title"])
        self.assertEqual([n["show_date"] for n in tl["nodes"]], [True, True])
        self.assertEqual(tl["segments"][-1]["label"], "32 j")  # silence jusqu'à aujourd'hui, en jours
        self.assertEqual(tl["default_time"], "")      # heure vide par défaut dans le formulaire

    def test_no_today_marker_when_last_event_is_today(self):
        self._add("first_request", "2026-11-12", time_str="08:00")
        self._add("email_out", "2026-11-12", time_str="")
        self.assertIsNone(build_commercial_timeline(self.project, now=NOW)["today_pct"])

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
        # Hors largeur minimale, l'écart restant suit la racine du temps : √20 / √10 = √2
        self.assertAlmostEqual((w2 - MIN_SEGMENT_PCT) / (w1 - MIN_SEGMENT_PCT), 2 ** 0.5, places=2)
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

    def test_commercial_new_contact_freelance_with_job(self):
        self._login(self.commercial)
        self._post_event(contact_id="__new__", new_contact_first_name="Iris", new_contact_last_name="Libre",
                         new_contact_job_title="Chargé.e de production", new_contact_production_id="")
        ev = ProjectCommercialEvent.query.one()
        self.assertIsNone(ev.contact.production_id)
        self.assertEqual(ev.contact.job_title, "Chargé.e de production")

    def test_timeline_new_contact_fields_rendered(self):
        self._login(self.commercial)
        html = self.client.get(f"/admin/projects/{self.project.id}").get_data(as_text=True)
        for key in ("first_name", "last_name", "phone", "mail", "job_title", "production_id"):
            self.assertIn(f'name="new_contact_{key}"', html)
        # Production du projet proposée par défaut
        self.assertRegex(html, r'<option value="%d" selected>Prod Routes</option>' % self.project.production_id)

    def test_commercial_edits_event(self):
        self._login(self.commercial)
        self._post_event(summary="Avant")
        ev = ProjectCommercialEvent.query.one()
        resp = self.client.post(
            f"/admin/projects/{self.project.id}/commercial-events/{ev.id}/edit",
            data={"event_type": "email_out", "occurred_date": date.today().isoformat(), "summary": "Après"},
        )
        self.assertEqual(resp.status_code, 302)
        db.session.refresh(ev)
        self.assertEqual((ev.event_type, ev.summary), ("email_out", "Après"))

    def test_ajax_add_edit_delete_return_card_html(self):
        self._login(self.commercial)
        xhr = {"X-Requested-With": "XMLHttpRequest"}
        url = f"/admin/projects/{self.project.id}/commercial-events"
        resp = self.client.post(url, headers=xhr, data={
            "event_type": "call_in", "occurred_date": date.today().isoformat(), "summary": "Appel AJAX"})
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        ev = ProjectCommercialEvent.query.one()
        self.assertEqual((data["status"], data["event_id"]), ("success", ev.id))
        self.assertIn('id="commercial-timeline"', data["html"])
        self.assertIn("Appel AJAX", data["html"])

        resp = self.client.post(f"{url}/{ev.id}/edit", headers=xhr, data={
            "event_type": "email_in", "occurred_date": date.today().isoformat(), "summary": "Modifié"})
        self.assertEqual(resp.get_json()["event_id"], ev.id)
        self.assertIn("Modifié", resp.get_json()["html"])

        resp = self.client.post(f"{url}/{ev.id}/delete", headers=xhr)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Aucune prise de contact", resp.get_json()["html"])

    def test_ajax_validation_error_returns_message(self):
        self._login(self.commercial)
        resp = self.client.post(f"/admin/projects/{self.project.id}/commercial-events",
                                headers={"X-Requested-With": "XMLHttpRequest"},
                                data={"event_type": "lost", "occurred_date": date.today().isoformat()})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {"status": "error", "message": "Indiquez le motif de l'abandon."})
        resp = self.client.post(f"/admin/projects/{self.project.id}/commercial-events/9999/delete",
                                headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(resp.status_code, 404)

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
        self._login(self.commercial)
        self._post_event(summary="Intact")
        ev = ProjectCommercialEvent.query.one()
        self._login(self.tech)
        self.client.post(f"/admin/projects/{self.project.id}/commercial-events/{ev.id}/edit",
                         data={"event_type": "lost", "occurred_date": date.today().isoformat(), "lost_reason": "price"})
        db.session.refresh(ev)
        self.assertEqual(ev.event_type, "call_in")


class CommercialStatusListFilterTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.commercial = self.create_user(firstname="Carla", lastname="Com", mail="carla@bv.fr", role="Commercial")
        self.tech = self.create_user(firstname="Tina", lastname="Tech", mail="tina@bv.fr", role="Technicien")
        prod = self.create_production("Prod Liste")
        self.quoted = Project(name="Projet Devis", production_id=prod.id, commercial_status="quote_sent")
        self.lost = Project(name="Projet Perdu", production_id=prod.id, commercial_status="lost")
        self.legacy = Project(name="Projet Ancien", production_id=prod.id, commercial_status=None)
        for p in (self.quoted, self.lost, self.legacy):
            p.bv_technicians = [self.tech]
        db.session.add_all([self.quoted, self.lost, self.legacy])
        db.session.commit()
        self.legacy.commercial_status = None  # projet antérieur au suivi (le défaut « prospect » s'applique à la création)
        db.session.commit()

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = user.id
            sess["admin_user_role"] = user.role

    def test_service_filter_and_counts(self):
        from services.admin.projects.crud import commercial_status_counts, list_projects
        names = lambda status: {p["name"] for p in list_projects(is_archive=False, commercial_status=status)}
        self.assertEqual(names("lost"), {"Projet Perdu"})
        self.assertEqual(names("untracked"), {"Projet Ancien"})
        self.assertEqual(len(names(None)), 3)
        self.assertEqual(len(names("n'importe quoi")), 3)
        self.assertEqual(commercial_status_counts(is_archive=False), {"quote_sent": 1, "lost": 1, None: 1})

    def test_list_page_filters_for_sales_roles(self):
        self._login(self.commercial)
        html = self.client.get("/admin/projects?commercial=quote_sent").get_data(as_text=True)
        self.assertIn("Projet Devis", html)
        self.assertNotIn("Projet Perdu", html)
        self.assertIn("ctl-filter-pill", html)
        self.assertIn('name="commercial" value="quote_sent"', html)  # conservé par la recherche

    def test_technician_ignores_filter(self):
        self._login(self.tech)
        html = self.client.get("/admin/projects?commercial=quote_sent").get_data(as_text=True)
        self.assertIn("Projet Perdu", html)
        self.assertNotIn("ctl-filter-pill", html)


class CommercialStatsTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.commercial = self.create_user(firstname="Carla", lastname="Com", mail="carla@bv.fr", role="Commercial")
        self.tech = self.create_user(firstname="Tina", lastname="Tech", mail="tina@bv.fr", role="Technicien")
        self.prod = self.create_production("Prod Stats")

    def _project(self, name, events):
        p = Project(name=name, production_id=self.prod.id)
        db.session.add(p)
        db.session.commit()
        for ev_type, day, extra in events:
            add_commercial_event(p.id, event_type=ev_type, date_str=day, now=NOW, **extra)
        return p

    def test_stats(self):
        self._project("Gagné A", [("first_request", "2026-09-01", {}), ("confirmed", "2026-09-11", {})])
        self._project("Gagné B", [("first_request", "2026-09-01", {}), ("confirmed", "2026-09-05", {}),
                                  ("invoice_paid", "2026-10-01", {})])
        self._project("Perdu prix", [("first_request", "2026-09-01", {}), ("lost", "2026-09-03", {"lost_reason": "price"})])
        self._project("Perdu prix 2", [("lost", "2026-09-03", {"lost_reason": "price"})])
        self._project("Perdu dates", [("lost", "2026-09-04", {"lost_reason": "dates"})])
        self._project("Devis", [("quote_sent", "2026-10-20", {})])
        legacy = Project(name="Ancien", production_id=self.prod.id)
        db.session.add(legacy)
        db.session.commit()
        legacy.commercial_status = None
        db.session.commit()

        st = commercial_stats(now=NOW)
        self.assertEqual(st["tracked"], 6)  # le projet non suivi est exclu
        self.assertEqual((st["won"], st["lost"]), (2, 3))
        self.assertEqual(st["conversion_rate"], 40)
        self.assertEqual(st["avg_days_to_confirm"], 7.0)  # (10 + 4) / 2
        self.assertEqual([(r["key"], r["count"], r["pct"]) for r in st["lost_reasons"]],
                         [("price", 2, 100), ("dates", 1, 50)])
        self.assertEqual([f["project"].name for f in st["followups"]], ["Devis"])
        self.assertEqual(st["quotes_pending"], 1)

    def test_empty_stats(self):
        st = commercial_stats(now=NOW)
        self.assertEqual(st["tracked"], 0)
        self.assertIsNone(st["conversion_rate"])
        self.assertIsNone(st["avg_days_to_confirm"])

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = user.id
            sess["admin_user_role"] = user.role

    def test_commercial_kpis_on_admin_indicators_page_only(self):
        self._project("Perdu", [("lost", NOW.date().isoformat(), {"lost_reason": "price"})])
        # Le commercial n'a pas accès à la page Indicateurs (réservée aux administrateurs)
        self._login(self.commercial)
        self.assertEqual(self.client.get("/admin/indicators").status_code, 302)
        # Les KPI ne sont plus sur le tableau de bord
        html = self.client.get("/admin/dashboard").get_data(as_text=True)
        self.assertNotIn("Taux de transformation", html)
        self.assertNotIn("Motifs d'abandon", html)
        self._login(self.tech)
        self.assertEqual(self.client.get("/admin/indicators").status_code, 302)
        html = self.client.get("/admin/dashboard").get_data(as_text=True)
        self.assertNotIn('id="suivi-commercial"', html)


class QuoteFollowupDigestTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.create_user(firstname="Ada", lastname="Admin", mail="ada@bv.fr", role="Administrateur")
        self.carla = self.create_user(firstname="Carla", lastname="Com", mail="carla@bv.fr", role="Commercial")
        self.cyril = self.create_user(firstname="Cyril", lastname="Com", mail="cyril@bv.fr", role="Commercial")
        self.tech = self.create_user(firstname="Tina", lastname="Tech", mail="tina@bv.fr", role="Technicien")
        prod = self.create_production("Prod Relance")
        self.p1 = Project(name="Devis Carla", production_id=prod.id, commercial_user_id=self.carla.id)
        self.p2 = Project(name="Devis Sans Commercial", production_id=prod.id)
        db.session.add_all([self.p1, self.p2])
        db.session.commit()
        for p in (self.p1, self.p2):
            add_commercial_event(p.id, event_type="quote_sent", date_str="2026-10-20", now=NOW)

    def test_recipients_by_role(self):
        from services.admin.commercial_timeline import followup_digest_recipients
        recipients = followup_digest_recipients(find_projects_awaiting_quote_reply(now=NOW))
        self.assertEqual({m: sorted(f["project"].name for f in items) for m, items in recipients.items()}, {
            "ada@bv.fr": ["Devis Carla", "Devis Sans Commercial"],
            "carla@bv.fr": ["Devis Carla"],
        })  # Cyril (aucun projet) et le technicien ne reçoivent rien

    def test_send_digest(self):
        from unittest.mock import patch
        from services.admin.commercial_timeline import send_quote_followup_digest
        with self.app.test_request_context(), \
                patch("utils.mailer.EmailService.send_templated_email", return_value=True) as send:
            result = send_quote_followup_digest(base_url="https://erp.test", now=NOW)
            self.assertEqual(result["sent"], 2)
            calls = {c.kwargs["to_email"]: c.kwargs for c in send.call_args_list}
            self.assertEqual(len(calls["carla@bv.fr"]["context"]["projects"]), 1)
            self.assertIn("https://erp.test/admin/projects/", calls["ada@bv.fr"]["context"]["projects"][0]["url"])
            self.assertEqual(calls["ada@bv.fr"]["subject"], "Suivi commercial : 2 devis à relancer")

            send.reset_mock()
            self.assertEqual(send_quote_followup_digest(base_url="https://erp.test", now=NOW, dry_run=True)["sent"], 0)
            send.assert_not_called()

            # Réponse du client : plus rien à relancer, aucun e-mail
            for p in (self.p1, self.p2):
                add_commercial_event(p.id, event_type="email_in", date_str="2026-11-01", now=NOW)
            result = send_quote_followup_digest(base_url="https://erp.test", now=NOW)
            self.assertEqual((result["followups"], result["sent"]), ([], 0))
            send.assert_not_called()

    def test_email_template_renders(self):
        from flask import render_template
        with self.app.test_request_context():
            html = render_template("emails/quote_followup_digest.html", days=10, list_url="https://x/list", projects=[{
                "name": "Pub", "production": "Prod", "commercial": "Carla Com", "last_label": "Devis envoyé",
                "last_date": "20/10/2026", "contact": "Jeanne Martin", "days": 23, "url": "https://x/p",
            }])
        self.assertIn("Devis à relancer", html)
        self.assertIn("23 j", html)
        self.assertIn("https://x/list", html)


class CommercialMcpToolsTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        from mcp_auth.auth import McpUserContext
        from mcp_server.context import CURRENT_MCP_USER
        self.manager = self.create_user(firstname="Marc", lastname="Mgr", mail="marc@bv.fr", role="Manager")
        self.prod = self.create_production("Prod MCP")
        self.contact = self.create_contact(production_id=self.prod.id, first_name="Jeanne", last_name="Martin")
        self.project = Project(name="Pub MCP", production_id=self.prod.id)
        db.session.add(self.project)
        db.session.commit()
        self.ctx = CURRENT_MCP_USER
        self.ctx.set(McpUserContext(self.manager.id, "marc@bv.fr", "Marc", "Mgr", "manager", scope="write"))

    def tearDown(self):
        self.ctx.set(None)
        super().tearDown()

    def test_full_cycle(self):
        from mcp_server.tools import commercial as tools
        res = tools.add_commercial_event(self.project.project_id, "quote_sent", "2026-11-01", time="10:30",
                                         contact_id=self.contact.id, summary="Devis v1")
        self.assertEqual(res["status"], "success", res)
        self.assertEqual(res["commercial_status"], "quote_sent")
        self.assertEqual(res["event"]["author_name"], "Marc Mgr")
        event_id = res["event"]["id"]

        res = tools.add_commercial_event(self.project.id, "call_in", "2026-11-02",
                                         new_contact_first_name="Léo", new_contact_last_name="Neuf")
        self.assertEqual(res["event"]["contact_name"], "Léo Neuf")

        res = tools.update_commercial_event(event_id, summary="Devis v2")
        self.assertEqual(res["event"]["summary"], "Devis v2")
        self.assertEqual(res["event"]["occurred_at"], "2026-11-01 10:30")  # heure conservée
        self.assertEqual(res["event"]["contact_id"], self.contact.id)    # contact conservé

        timeline = tools.get_project_commercial_timeline(self.project.id)
        self.assertEqual([e["event_type"] for e in timeline["events"]], ["quote_sent", "call_in"])

        self.assertEqual(tools.delete_commercial_event(event_id)["status"], "confirmation_required")
        res = tools.delete_commercial_event(event_id, confirm=True)
        self.assertEqual((res["status"], res["commercial_status"]), ("success", "prospect"))

        self.assertEqual(tools.add_commercial_event(self.project.id, "lost", "2026-11-02")["status"], "error")
        self.assertIn("event_types", tools.get_commercial_event_types())
        stats = tools.get_commercial_stats()
        self.assertEqual(stats["tracked"], 1)
        self.assertIsInstance(stats["by_status"][0], dict)

    def test_commercial_role_is_read_only(self):
        from mcp_auth.auth import McpUserContext
        from mcp_server.tools import commercial as tools
        self.ctx.set(McpUserContext(self.manager.id, "c@bv.fr", "Com", "Mercial", "commercial", scope="write"))
        self.assertIn("events", tools.get_project_commercial_timeline(self.project.id))
        res = tools.add_commercial_event(self.project.id, "call_in", "2026-11-02")
        self.assertEqual(res.get("error_code"), 403)
        self.ctx.set(McpUserContext(self.manager.id, "t@bv.fr", "Tech", "Nicien", "technicien", scope="admin"))
        self.assertEqual(tools.get_commercial_stats().get("error_code"), 403)


class PlannedEventsTest(BaseTestCase):
    """Événements à venir : saisie, statut, « fait », relances, frise, agenda, mail et MCP."""

    def setUp(self):
        super().setUp()
        from services.admin.commercial_timeline import complete_commercial_event, planned_agenda
        self.complete, self.agenda = complete_commercial_event, planned_agenda
        self.user = self.create_user(firstname="Carla", lastname="Com", mail="carla@bv.fr", role="Commercial")
        self.prod = self.create_production("Prod Planif")
        self.contact = self.create_contact(production_id=self.prod.id, first_name="Marie", last_name="Alègre")
        self.project = Project(name="Pub Planif", production_id=self.prod.id, commercial_user_id=self.user.id)
        db.session.add(self.project)
        db.session.commit()

    def _add(self, event_type, day, planned=False, **kw):
        return add_commercial_event(self.project.id, event_type=event_type, date_str=day, now=NOW,
                                    is_planned=planned, user_id=self.user.id, **kw)

    def test_validation(self):
        ev = self._add("meeting", "2027-03-08", planned=True, contact_id=self.contact.id, time_str="10:00")
        self.assertTrue(ev.is_planned)
        with self.assertRaises(ValueError):
            self._add("confirmed", "2026-11-20", planned=True)   # type non planifiable
        with self.assertRaises(ValueError):
            self._add("meeting", "2026-11-01", planned=True)     # à venir dans le passé
        with self.assertRaises(ValueError):
            self._add("deadline", "2026-11-01")                  # échéance : uniquement à venir
        with self.assertRaises(ValueError):
            self._add("meeting", "2026-11-20")                   # réalisé dans le futur

    def test_planned_never_changes_status(self):
        self._add("first_request", "2026-11-01")
        self._add("quote_followup", "2026-11-20", planned=True)
        self.assertEqual(self.project.commercial_status, "prospect")

    def test_complete(self):
        self._add("quote_sent", "2026-11-01")
        late = self._add("call_out", "2026-11-12", planned=True)
        early = self._add("meeting", "2026-12-01", planned=True)
        done = self.complete(self.project.id, late.id, now=datetime(2026, 11, 14, 9, 0))
        self.assertFalse(done.is_planned)
        self.assertEqual(done.occurred_at.date(), date(2026, 11, 12))      # date prévue conservée
        done = self.complete(self.project.id, early.id, now=NOW)
        self.assertEqual(done.occurred_at, datetime(2026, 11, 12, 15, 0))  # fait en avance : maintenant
        with self.assertRaises(ValueError):
            self.complete(self.project.id, early.id, now=NOW)              # déjà fait
        deadline = self._add("deadline", "2026-11-30", planned=True)
        with self.assertRaises(ValueError):
            self.complete(self.project.id, deadline.id, now=NOW)

    def test_planned_followup_silences_reminder(self):
        self._add("quote_sent", "2026-10-20")
        self.assertEqual(followup_due(self.project.commercial_events, "quote_sent", now=NOW), 23)
        self._add("quote_followup", "2026-11-15", planned=True)
        self.assertIsNone(followup_due(self.project.commercial_events, "quote_sent", now=NOW))
        self.assertEqual(find_projects_awaiting_quote_reply(now=NOW), [])

    def test_timeline_layout_with_future(self):
        self._add("first_request", "2026-11-01")
        late = self._add("call_out", "2026-11-12", planned=True)   # créé « à venir » le 12…
        self._add("meeting", "2026-11-15", planned=True, time_str="10:00")
        later = datetime(2026, 11, 13, 9, 0)                        # …et consulté le 13 : en retard
        tl = build_commercial_timeline(self.project, now=later)
        kinds = [(e["type"], e["is_planned"], e["is_late"]) for e in tl["events"]]
        self.assertEqual(kinds, [("first_request", False, False), ("call_out", True, True), ("meeting", True, False)])
        pcts = [e["pct"] for e in tl["events"]]
        self.assertTrue(pcts[1] < tl["today_pct"] < pcts[2])        # retard avant « Aujourd'hui », à venir après
        self.assertTrue(tl["future_zone"])
        self.assertEqual(tl["selected_id"], late.id)                 # le retard est mis en avant
        self.assertEqual((tl["count"], tl["upcoming_count"], tl["late_count"]), (1, 1, 1))
        self.assertEqual(tl["next_upcoming"], {"label": "Rendez-vous / visio", "relative": "dans 2 j"})
        self.assertTrue(any(s["is_future"] and s["label"] == "dans 2 j" for s in tl["segments"]))
        self.assertEqual(tl["events"][1]["relative"], "date dépassée de 1 j")
        self.assertEqual(tl["events"][2]["edit"]["is_planned"], "1")

    def test_complete_button_asks_confirmation(self):
        from flask import render_template
        self._add("first_request", "2026-11-01")
        self._add("meeting", "2026-11-15", planned=True, contact_id=self.contact.id)
        with self.app.test_request_context():
            html = render_template("admin/_commercial_timeline.html", project=self.project,
                                   tl=build_commercial_timeline(self.project, now=NOW))
        self.assertIn('data-confirm="Marquer « Rendez-vous / visio avec Marie Alègre » comme fait ?', html)
        self.assertIn("prendra la date et l'heure d'aujourd'hui (prévu dans 3 j)", html)
        self.assertIn('data-confirm-variant="primary"', html)

    def test_future_share_is_capped(self):
        from services.admin.commercial_timeline import MAX_FUTURE_SHARE_PCT
        # Passé : 4 contacts le même jour (= aujourd'hui) ; avenir : J+5 et J+8
        for t in ("email_in", "first_request", "email_out", "email_out"):
            self._add(t, "2026-11-12")
        self._add("quote_followup", "2026-11-17", planned=True)
        self._add("email_out", "2026-11-20", planned=True)
        tl = build_commercial_timeline(self.project, now=NOW)
        self.assertAlmostEqual(tl["today_pct"], 100 - MAX_FUTURE_SHARE_PCT, places=2)
        future = [e["pct"] for e in tl["events"] if e["is_planned"]]
        # Proportions conservées dans l'avenir : 5 j puis 3 j
        a, b = future[0] - tl["today_pct"], future[1] - future[0]
        self.assertAlmostEqual(a / b, (5 / 3) ** 0.5, delta=0.1)  # racine du temps : √5 / √3
        self.assertEqual(future[-1], 100.0)
        # Segments recalés sur les mêmes positions
        self.assertTrue(all(s["start_pct"] <= s["end_pct"] for s in tl["segments"]))
        self.assertAlmostEqual(tl["segments"][-1]["end_pct"], 100.0, places=2)

    def test_future_share_untouched_without_past_or_when_small(self):
        from services.admin.commercial_timeline import cap_future_share
        self.assertEqual(cap_future_share([0.0, 30.0, 100.0], [], 0), ([0.0, 30.0, 100.0], []))
        self.assertEqual(cap_future_share([0.0, 70.0, 100.0], [], 1), ([0.0, 70.0, 100.0], []))

    def test_agenda_and_digest(self):
        from unittest.mock import patch
        from services.admin.commercial_timeline import send_quote_followup_digest
        self._add("call_out", "2026-11-12", planned=True, summary="Rappeler")
        self._add("meeting", "2026-11-16", planned=True)
        self._add("deadline", "2026-12-30", planned=True)
        ag = self.agenda(now=datetime(2026, 11, 13, 8, 0))
        self.assertEqual([len(ag[k]) for k in ("overdue", "today", "upcoming")], [1, 0, 1])
        self.assertEqual(ag["overdue"][0]["days"], -1)
        with self.app.test_request_context(), \
                patch("utils.mailer.EmailService.send_templated_email", return_value=True) as send:
            result = send_quote_followup_digest(base_url="https://erp.test", now=datetime(2026, 11, 13, 8, 0))
            self.assertEqual((len(result["planned"]), result["sent"]), (1, 1))
            kw = send.call_args.kwargs
            self.assertEqual(kw["to_email"], "carla@bv.fr")
            self.assertEqual(kw["subject"], "Suivi commercial : 1 en retard")
            self.assertEqual(kw["context"]["agenda"][0]["late_days"], 1)

    def test_complete_route_and_mcp(self):
        from mcp_auth.auth import McpUserContext
        from mcp_server.context import CURRENT_MCP_USER
        from mcp_server.tools import commercial as tools
        mgr = self.create_user(firstname="Marc", lastname="Mgr", mail="marc@bv.fr", role="Manager")
        with self.client.session_transaction() as sess:
            sess.update(admin_authenticated=True, admin_user_id=self.user.id, admin_user_role=self.user.role)
        today = date.today().isoformat()
        resp = self.client.post(f"/admin/projects/{self.project.id}/commercial-events",
                                headers={"X-Requested-With": "XMLHttpRequest"},
                                data={"event_type": "call_out", "occurred_date": today, "is_planned": "1"})
        self.assertEqual(resp.status_code, 201, resp.get_json())
        ev_id = resp.get_json()["event_id"]
        self.assertIn("ctl-future-zone", resp.get_json()["html"])
        resp = self.client.post(f"/admin/projects/{self.project.id}/commercial-events/{ev_id}/complete",
                                headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(db.session.get(ProjectCommercialEvent, ev_id).is_planned)

        CURRENT_MCP_USER.set(McpUserContext(mgr.id, "marc@bv.fr", "Marc", "Mgr", "manager", scope="write"))
        try:
            res = tools.add_commercial_event(self.project.id, "meeting", "2099-01-01", is_planned=True)
            self.assertTrue(res["event"]["is_planned"])
            self.assertEqual(tools.complete_commercial_event(res["event"]["id"])["status"], "success")
            self.assertIn("agenda", tools.get_commercial_stats())
        finally:
            CURRENT_MCP_USER.set(None)


if __name__ == "__main__":
    unittest.main()
