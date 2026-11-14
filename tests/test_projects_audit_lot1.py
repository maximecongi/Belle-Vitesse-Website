"""
Corrections du lot 1 de l'audit Projets :
- saisie conservée après une erreur d'enregistrement (création et modification) ;
- montant de facture sur un matériel non engagé refusé explicitement ;
- analyses des risques (BVRA) synchronisées et supprimées avec le projet ;
- dates « aujourd'hui » au fuseau Europe/Paris (archives, statut de la fiche) ;
- conflits : jours de départ / retour comptés, projets abandonnés ignorés ;
- actions sur les documents masquées aux rôles qui ne peuvent pas les exécuter ;
- timeline commerciale : suppression refusée sur un projet supprimé.
"""
from datetime import date, datetime
from unittest.mock import patch

from werkzeug.datastructures import MultiDict

from models import Production, Project, RiskAssessmentWaiver, User, Vehicle, db
from services.admin.commercial_timeline import (
    CommercialEventNotFoundError,
    add_commercial_event,
    delete_commercial_event,
)
from services.admin.conflicts import check_booking_conflicts
from services.admin.projects import create_project, delete_project, list_projects, update_project
from services.admin.projects.crud import form_data_from_post
from tests.base import BaseTestCase


class ProjectsAuditLot1Test(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.prod = Production(name="Prod Lot 1")
        db.session.add_all([self.prod, Vehicle(id="rec_l1_v", fields={"name": "eRover"}, display_order=0)])
        db.session.commit()

    def _login(self, role, mail):
        user = User(firstname="Test", lastname=role, mail=mail, role=role)
        db.session.add(user)
        db.session.commit()
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = user.id
            sess["admin_user_role"] = user.role
            sess["admin_user_email"] = user.mail
        return user

    def _base_form(self, **extra):
        data = {
            "name": "Clip Lot 1", "production_id": str(self.prod.id),
            "date_mode": "continuous",
            "departure_date": "2027-03-09", "shoot_start": "2027-03-10",
            "shoot_end": "2027-03-12", "return_date": "2027-03-13",
            "vehicle_ids": "rec_l1_v", "notes": "Prévoir batteries",
            "shooting_locations": '[{"name": "Circuit Test", "address": "1 rue du Circuit"}]',
        }
        data.update(extra)
        return data

    # ── 1. Saisie conservée après une erreur ───────────────────

    def test_create_error_keeps_input(self):
        self._login("administrator", "lot1_create@example.com")
        res = self.client.post("/admin/projects/new", data=self._base_form(
            production_id="",  # production manquante → erreur du service
            invoices_present="1", **{"invoices-n1-label": "Acompte", "invoices-n1-amount": "1200",
                                     "invoices-n1-issued_on": "2027-03-01"},
        ))
        self.assertEqual(res.status_code, 422)
        html = res.get_data(as_text=True)
        self.assertIn("Veuillez sélectionner une société de production valide.", html)
        self.assertIn('value="Clip Lot 1"', html)
        self.assertIn('value="2027-03-10"', html)
        self.assertIn("Prévoir batteries", html)
        self.assertIn("Circuit Test", html)
        self.assertIn('value="Acompte"', html)
        self.assertRegex(html, r'project-checkbox-card selected"[^>]*data-item-id="rec_l1_v"')
        self.assertEqual(Project.query.count(), 0)

    def test_edit_error_keeps_input_and_stays_on_form(self):
        self._login("administrator", "lot1_edit@example.com")
        project = create_project(MultiDict(self._base_form()))
        res = self.client.post(f"/admin/projects/{project.id}/edit", data=self._base_form(
            name="Nouveau nom saisi", invoices_present="1",
            **{"invoices-0-label": "Solde", "invoices-0-amount": "abc", "invoices-0-issued_on": "2027-03-14"},
        ))
        self.assertEqual(res.status_code, 422)
        html = res.get_data(as_text=True)
        self.assertIn("Montant invalide", html)
        self.assertIn('value="Nouveau nom saisi"', html)
        self.assertIn(f'value="{project.id}"', html)
        self.assertIn('value="Solde"', html)
        db.session.expire_all()
        self.assertEqual(db.session.get(Project, project.id).name, "Clip Lot 1")

    def test_edit_unknown_project_is_404(self):
        self._login("administrator", "lot1_404@example.com")
        res = self.client.post("/admin/projects/999999/edit", data=self._base_form())
        self.assertEqual(res.status_code, 404)

    def test_form_data_from_post_matches_edit_shape(self):
        data = form_data_from_post(MultiDict([
            *self._base_form().items(), ("head_ids", "rec_h1"), ("head_ids", "rec_h2"),
            ("bv_referent_ids", "3"), ("invoices_present", "1"),
            ("invoices-0-label", "Acompte"), ("invoices-0-is_paid", "1"),
        ]))
        self.assertEqual(data["vehicle_ids"], ["rec_l1_v"])
        self.assertEqual(data["head_ids"], ["rec_h1", "rec_h2"])
        self.assertEqual(data["bv_referent_ids"], ["3"])
        self.assertEqual(data["shoot_start_raw"], "2027-03-10")
        self.assertEqual(data["locations_list"][0]["name"], "Circuit Test")
        self.assertEqual(data["invoices"][0]["label"], "Acompte")
        self.assertTrue(data["invoices"][0]["is_paid"])

    # ── 5. Montant sur un matériel non engagé ──────────────────

    def test_amount_on_non_engaged_equipment_is_refused(self):
        form = MultiDict(self._base_form(**{
            "invoices_present": "1", "invoices-0-number": "F-9", "invoices-0-issued_on": "2027-03-14",
            "invoices-0-amount": "5000", "invoices-0-equipment[vehicle:rec_l1_v]": "1000",
            "invoices-0-equipment[vehicle:rec_absent]": "800",
        }))
        with self.assertRaises(ValueError) as ctx:
            create_project(form)
        self.assertIn("n'est plus engagé", str(ctx.exception))
        self.assertIn("F-9", str(ctx.exception))
        # Montant vide ou nul sur un matériel retiré : ignoré sans erreur
        form["invoices-0-equipment[vehicle:rec_absent]"] = "0"
        project = create_project(form)
        self.assertEqual(project.invoices[0].equipment_billing, {"vehicle:rec_l1_v": 1000.0})

    # ── 6. Analyses des risques (BVRA) ─────────────────────────

    def test_bvra_synced_on_update_and_deleted_with_project(self):
        project = create_project(MultiDict(self._base_form()))
        ra = RiskAssessmentWaiver(project_id=project.id, status="to_send", project_name="Clip Lot 1",
                                  signer_first_name="Ana", signer_last_name="Risque")
        db.session.add(ra)
        db.session.commit()
        update_project(project.id, MultiDict(self._base_form(name="Clip renommé")))
        db.session.expire_all()
        ra = db.session.get(RiskAssessmentWaiver, ra.id)
        self.assertEqual(ra.project_name, "Clip renommé")
        self.assertEqual(ra.production_name, "Prod Lot 1")
        self.assertIn("2027", ra.shooting_dates or "")

        with patch("services.common.kdrive.dispatch_delete_project_folder", create=True):
            delete_project(project.id)
        db.session.expire_all()
        self.assertIsNotNone(db.session.get(RiskAssessmentWaiver, ra.id).deleted_at)

    # ── 7. Date du jour au fuseau Europe/Paris ─────────────────

    def test_archive_filter_uses_paris_today(self):
        project = create_project(MultiDict(self._base_form()))  # retour le 13/03/2027
        with patch("services.admin.projects.crud.get_today_paris", return_value=date(2027, 3, 14)):
            self.assertEqual([p["id"] for p in list_projects(is_archive=True)], [project.id])
            self.assertEqual(list_projects(is_archive=False), [])
        with patch("services.admin.projects.crud.get_today_paris", return_value=date(2027, 3, 13)):
            self.assertEqual(list_projects(is_archive=True), [])

    def test_detail_status_uses_shared_paris_logic(self):
        from services.admin.project_reports import get_project_detail_context

        project = create_project(MultiDict(self._base_form()))
        with patch("utils.formatting.get_today_paris", return_value=date(2027, 3, 11)):
            ctx = get_project_detail_context(project.id, is_admin=True)
        self.assertEqual(ctx["shoot_status"], "in_progress")
        with patch("utils.formatting.get_today_paris", return_value=date(2027, 3, 20)):
            ctx = get_project_detail_context(project.id, is_admin=True)
        self.assertEqual(ctx["shoot_status"], "completed")

    # ── 8. Conflits de réservation ─────────────────────────────

    def _existing(self, **kw):
        values = dict(name="Existant", production_id=self.prod.id, vehicles_to_check="rec_l1_v",
                      departure_date=date(2027, 6, 1), shoot_start_date=date(2027, 6, 2),
                      shoot_end_date=date(2027, 6, 4), return_date=date(2027, 6, 5))
        values.update(kw)
        project = Project(**values)
        db.session.add(project)
        db.session.commit()
        return project

    def test_conflicts_count_departure_and_return_days(self):
        self._existing()
        # Tournage demandé le jour du retour de l'autre projet : matériel encore mobilisé
        res = check_booking_conflicts("2027-06-05", "2027-06-06", vehicle_ids=["rec_l1_v"])
        self.assertTrue(res["has_conflicts"])
        self.assertEqual(res["conflicts_list"][0]["overlap_dates"], ["2027-06-05"])
        # Tournage après le retour, mais départ demandé le 31/05 : chevauche le départ de l'autre projet
        res = check_booking_conflicts("2027-05-29", "2027-05-30", vehicle_ids=["rec_l1_v"],
                                      return_date_val="2027-06-01")
        self.assertTrue(res["has_conflicts"])
        self.assertEqual(res["conflicts_list"][0]["overlap_dates"], ["2027-06-01"])
        # Hors de la période départ → retour : pas de conflit
        res = check_booking_conflicts("2027-06-06", "2027-06-08", vehicle_ids=["rec_l1_v"])
        self.assertFalse(res["has_conflicts"])

    def test_conflicts_ignore_lost_projects(self):
        lost = self._existing(commercial_status="lost")
        res = check_booking_conflicts("2027-06-02", "2027-06-03", vehicle_ids=["rec_l1_v"])
        self.assertFalse(res["has_conflicts"])
        lost.commercial_status = "quote_sent"
        db.session.commit()
        res = check_booking_conflicts("2027-06-02", "2027-06-03", vehicle_ids=["rec_l1_v"])
        self.assertTrue(res["has_conflicts"])

    # ── 11. Actions sur les documents selon le rôle ────────────

    def test_document_actions_hidden_for_technicians(self):
        project = create_project(MultiDict(self._base_form()))
        tech = self._login("technicien", "lot1_tech@example.com")
        project.bv_technicians = [tech]
        db.session.commit()
        html = self.client.get(f"/admin/projects/{project.id}").get_data(as_text=True)
        self.assertIn("Documents", html)
        self.assertNotIn("data-signer-modal-open", html)
        self.assertNotIn("Cliquez sur <strong>Inviter</strong>", html)

        self._login("administrator", "lot1_admin_docs@example.com")
        html = self.client.get(f"/admin/projects/{project.id}").get_data(as_text=True)
        self.assertIn('data-signer-modal-open="addCglSignerModal"', html)
        self.assertIn('id="addCglSignerModal"', html)

    # ── 12. Timeline commerciale ───────────────────────────────

    def test_delete_commercial_event_refused_on_deleted_project(self):
        project = create_project(MultiDict(self._base_form()))
        event = add_commercial_event(project.id, event_type="call_in", date_str="2027-01-05",
                                     now=datetime(2027, 1, 6, 10, 0))
        project.deleted_at = datetime(2027, 1, 7)
        db.session.commit()
        with self.assertRaises(CommercialEventNotFoundError):
            delete_commercial_event(project.id, event.id)
