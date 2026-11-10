"""
Invitations de signataires unifiées (CGL, BVSR, Annexe 3, BVRA) :
annuaire / autocomplétion, rattachement au contact ERP, création automatique de contacts,
choix libre du signataire des CGL et résolution du destinataire (envoi + relances).
"""
import os
import sys
import unittest
from datetime import date, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.base import BaseTestCase
from models import CglWaiver, Contact, PilotWaiver, Production, Project, SafetyRulesWaiver, User, db
from services.admin.contacts import delete_contact
from services.admin.signers import search_signers, upsert_signer_contact
from services.admin.waivers import (
    create_cgl,
    create_pilot_waiver,
    create_safety_rules_waiver,
    send_cgl,
    send_safety_rules_waiver,
)
from services.admin.waivers.common import resolve_waiver_recipient
from services.admin.waivers.reminders import auto_remind_pending_waivers


class SignerInvitationsTest(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.prod = Production(name="Prod Alpha")
        self.other_prod = Production(name="Prod Beta")
        db.session.add_all([self.prod, self.other_prod])
        db.session.flush()

        self.prod_contact = Contact(first_name="Jean", last_name="Dupont", mail="jean@alpha.fr",
                                    phone="0611", job_title="Directeur de production", production_id=self.prod.id)
        self.pilot = Contact(first_name="Luc", last_name="Pilote", mail="luc@pilote.fr", production_id=None)
        self.lawyer = Contact(first_name="Claire", last_name="Juriste", mail="claire@alpha.fr",
                              job_title="Gérante", production_id=self.prod.id)
        self.stranger = Contact(first_name="Claude", last_name="Ailleurs", mail="claude@beta.fr",
                                production_id=self.other_prod.id)
        db.session.add_all([self.prod_contact, self.pilot, self.lawyer, self.stranger])
        db.session.add(User(firstname="Camille", lastname="Technicienne", mail="camille@bellevitesse.com",
                            job="Référente sécurité", role="user"))
        db.session.flush()

        today = date.today()
        self.project = Project(
            name="Tournage Gamma",
            production_id=self.prod.id,
            production_contact_id=self.prod_contact.id,
            pilot_contact_id=self.pilot.id,
            departure_date=today + timedelta(days=1),
            shoot_start_date=today + timedelta(days=1),
            shoot_end_date=today + timedelta(days=3),
            return_date=today + timedelta(days=4),
        )
        db.session.add(self.project)
        db.session.commit()

    def _login(self, role="administrator"):
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_user_role"] = role

    # ── Annuaire ────────────────────────────────────────────────────────

    def test_search_ranks_project_then_production_then_others_then_team(self):
        results = search_signers("c", project_id=self.project.id, limit=50)
        groups = [(r["full_name"], r["group"]) for r in results]
        self.assertIn(("Luc Pilote", "project"), groups)  # « luc »
        self.assertIn(("Claire Juriste", "production"), groups)
        self.assertIn(("Claude Ailleurs", "contacts"), groups)
        self.assertIn(("Camille Technicienne", "team"), groups)
        order = ["project", "production", "contacts", "team"]
        self.assertEqual([g for _, g in groups], sorted([g for _, g in groups], key=order.index))

    def test_search_without_query_suggests_project_and_production_only(self):
        names = {r["full_name"] for r in search_signers("", project_id=self.project.id)}
        self.assertEqual(names, {"Jean Dupont", "Luc Pilote", "Claire Juriste"})
        self.assertEqual(search_signers(""), [])

    def test_search_matches_every_token_and_can_exclude_team(self):
        self.assertEqual([r["full_name"] for r in search_signers("claire alpha")], ["Claire Juriste"])
        self.assertFalse(any(r["kind"] == "user" for r in search_signers("camille", include_team=False)))

    def test_search_endpoint_requires_login_and_returns_json(self):
        res = self.client.get("/admin/api/signers/search?q=jean")
        self.assertNotEqual(res.status_code, 200)

        self._login("commercial")
        res = self.client.get(f"/admin/api/signers/search?q=jean&project_id={self.project.id}")
        self.assertEqual(res.status_code, 200)
        first = res.get_json()["results"][0]
        self.assertEqual(first["full_name"], "Jean Dupont")
        self.assertEqual(first["project_role"], "Contact production")
        self.assertEqual(first["mail"], "jean@alpha.fr")

    # ── Rattachement / création automatique de contacts ─────────────────

    def test_upsert_reuses_picked_contact_and_fills_only_empty_fields(self):
        c = upsert_signer_contact(self.project, "Luc", "Pilote", mail="autre@x.fr", phone="0699",
                                  contact_id=str(self.pilot.id))
        self.assertEqual(c.id, self.pilot.id)
        self.assertEqual(c.mail, "luc@pilote.fr")  # pas écrasé
        self.assertEqual(c.phone, "0699")  # complété

    def test_upsert_creates_contact_attached_to_project_production(self):
        before = Contact.query.count()
        c = upsert_signer_contact(self.project, "Nina", "Nouvelle", mail="nina@alpha.fr", job_title="Régisseuse")
        self.assertEqual(Contact.query.count(), before + 1)
        self.assertEqual(c.production_id, self.prod.id)
        # Seconde saisie identique (même e-mail) : pas de doublon
        again = upsert_signer_contact(self.project, "Nina", "Nouvelle", mail="NINA@alpha.fr")
        self.assertEqual(again.id, c.id)
        self.assertEqual(Contact.query.count(), before + 1)

    def test_upsert_skips_team_members_and_incomplete_names(self):
        self.assertIsNone(upsert_signer_contact(self.project, "Camille", "Technicienne", user_id="1"))
        self.assertIsNone(upsert_signer_contact(self.project, "Solo", ""))

    def test_safety_rules_with_free_signer_creates_and_links_contact(self):
        ok, _ = create_safety_rules_waiver(
            self.project.id, signer_role="operator", signer_first_name="Paul", signer_last_name="Cadreur",
            signer_email="paul@cam.fr", signer_phone="0700",
        )
        self.assertTrue(ok)
        sr = SafetyRulesWaiver.query.filter_by(project_id=self.project.id).one()
        contact = Contact.query.filter_by(mail="paul@cam.fr").one()
        self.assertEqual(sr.signer_contact_id, contact.id)
        self.assertEqual(sr.signer_name, "Paul Cadreur")
        self.assertEqual(sr.signer_company, "Prod Alpha")

    def test_pilot_waiver_without_input_falls_back_to_project_pilot(self):
        ok, _ = create_pilot_waiver(self.project.id, selected_vehicles=["Moto 1"])
        self.assertTrue(ok)
        pw = PilotWaiver.query.filter_by(project_id=self.project.id).one()
        self.assertEqual(pw.signer_contact_id, self.pilot.id)
        self.assertEqual(pw.signer_email, "luc@pilote.fr")

    def test_deleting_contact_detaches_documents_but_keeps_snapshot(self):
        create_safety_rules_waiver(self.project.id, signer_role="operator", signer_first_name="Paul",
                                   signer_last_name="Cadreur", signer_email="paul@cam.fr")
        contact = Contact.query.filter_by(mail="paul@cam.fr").one()
        delete_contact(contact.id)
        sr = SafetyRulesWaiver.query.filter_by(project_id=self.project.id).one()
        db.session.refresh(sr)
        self.assertIsNone(sr.signer_contact_id)
        self.assertEqual(sr.signer_email, "paul@cam.fr")

    # ── CGL : signataire choisi ──────────────────────────────────────────

    def test_cgl_defaults_to_production_contact(self):
        ok, _ = create_cgl(self.project.id)
        self.assertTrue(ok)
        cgl = CglWaiver.query.filter_by(project_id=self.project.id).one()
        self.assertEqual(cgl.signer_contact_id, self.prod_contact.id)
        self.assertEqual(cgl.production_representative, "Jean Dupont")
        self.assertEqual(cgl.signer_role_custom, "Directeur de production")
        self.assertEqual(resolve_waiver_recipient(cgl), ("jean@alpha.fr", "Jean Dupont"))

    @patch("utils.mailer.send_cgl_invitation_email", return_value=True)
    def test_cgl_with_other_signer_is_sent_to_that_signer(self, mock_mail):
        ok, _ = create_cgl(
            self.project.id, signer_first_name="Claire", signer_last_name="Juriste",
            signer_email="claire@alpha.fr", signer_role_custom="Gérante", signer_contact_id=str(self.lawyer.id),
        )
        self.assertTrue(ok)
        cgl = CglWaiver.query.filter_by(project_id=self.project.id).one()
        self.assertEqual(cgl.signer_contact_id, self.lawyer.id)

        ok, msg = send_cgl(cgl.waiver_id)
        self.assertTrue(ok, msg)
        kwargs = mock_mail.call_args.kwargs
        self.assertEqual(kwargs["to_email"], "claire@alpha.fr")
        self.assertEqual(kwargs["prod_contact_name"], "Claire Juriste")

    @patch("utils.mailer.send_cgl_invitation_email", return_value=True)
    @patch("utils.mailer.send_safety_rules_invitation_email", return_value=True)
    @patch("utils.mailer.send_pilot_waiver_invitation_email", return_value=True)
    def test_reminders_follow_the_document_signer_not_the_project_contact(self, _p, _s, mock_cgl):
        create_cgl(self.project.id, signer_first_name="Claire", signer_last_name="Juriste",
                   signer_email="claire@alpha.fr")
        # Le contact production du projet change après l'envoi : la relance reste pour la signataire invitée
        self.project.production_contact_id = self.stranger.id
        db.session.commit()

        auto_remind_pending_waivers(days_before=2, base_url="https://bv.test")
        self.assertEqual(mock_cgl.call_args.kwargs["to_email"], "claire@alpha.fr")

    def test_cgl_without_any_email_cannot_be_sent(self):
        self.project.production_contact_id = None
        db.session.commit()
        create_cgl(self.project.id, signer_first_name="Sans", signer_last_name="Mail")
        cgl = CglWaiver.query.filter_by(project_id=self.project.id).one()
        ok, msg = send_cgl(cgl.waiver_id)
        self.assertFalse(ok)
        self.assertIn("adresse e-mail", msg)

    @patch("utils.mailer.send_safety_rules_invitation_email", return_value=True)
    def test_send_uses_shared_recipient_resolution(self, mock_mail):
        create_safety_rules_waiver(self.project.id, signer_role="production")
        sr = SafetyRulesWaiver.query.filter_by(project_id=self.project.id).one()
        sr.signer_email = None
        db.session.commit()
        ok, _ = send_safety_rules_waiver(sr.waiver_id)
        self.assertTrue(ok)
        self.assertEqual(mock_mail.call_args.kwargs["to_email"], "jean@alpha.fr")

    # ── Routes & gabarits ───────────────────────────────────────────────

    def test_cgl_route_accepts_signer_from_modal(self):
        self._login()
        res = self.client.post(f"/admin/cgl/quick-create/{self.project.id}", data={
            "signer_first_name": "Claire", "signer_last_name": "Juriste", "signer_email": "claire@alpha.fr",
            "signer_role_custom": "Gérante", "signer_contact_id": str(self.lawyer.id),
            "return_to": f"/admin/projects/{self.project.id}",
        })
        self.assertEqual(res.status_code, 302)
        cgl = CglWaiver.query.filter_by(project_id=self.project.id).one()
        self.assertEqual(cgl.production_representative, "Claire Juriste")
        self.assertEqual(cgl.signer_email, "claire@alpha.fr")

    def test_cgl_new_page_posts_signer(self):
        self._login()
        res = self.client.get("/admin/cgl/new")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("data-signer-section", html)
        self.assertIn('"signer"', html)

        res = self.client.post("/admin/cgl/new", data={
            "project_id": str(self.project.id), "signer_first_name": "Nina", "signer_last_name": "Nouvelle",
            "signer_email": "nina@alpha.fr",
        })
        self.assertEqual(res.status_code, 302)
        cgl = CglWaiver.query.filter_by(project_id=self.project.id).one()
        self.assertEqual(cgl.signer_email, "nina@alpha.fr")
        self.assertIsNotNone(Contact.query.filter_by(mail="nina@alpha.fr").first())

    @patch("services.admin.project_reports.get_vehicles", return_value=[])
    def test_project_detail_renders_unified_modals(self, _mock):
        self._login()
        html = self.client.get(f"/admin/projects/{self.project.id}").get_data(as_text=True)
        for modal_id in ("addCglSignerModal", "addSafetyRulesSignerModal", "addPilotSignerModal", "addRiskSignerModal"):
            self.assertIn(f'id="{modal_id}"', html)
            self.assertIn(f'data-signer-modal-open="{modal_id}"', html)
        self.assertIn("/admin/api/signers/search", html)
        # CGL pré-remplies avec le contact production
        self.assertIn('value="jean@alpha.fr"', html)
        self.assertIn(f'name="signer_contact_id" value="{self.prod_contact.id}"', html)

        create_cgl(self.project.id)
        html = self.client.get(f"/admin/projects/{self.project.id}").get_data(as_text=True)
        self.assertNotIn('id="addCglSignerModal"', html)
        self.assertIn("Jean Dupont — jean@alpha.fr", " ".join(html.split()))


if __name__ == "__main__":
    unittest.main()
