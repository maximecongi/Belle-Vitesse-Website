from datetime import date

from tests.base import BaseTestCase
from models import Head, Production, Project, User, Vehicle, db
from models.equipment_usage import ProjectEquipmentUsage
from services.admin.equipment_usage import (
    EquipmentUsageError,
    build_usage_export_context,
    get_usage_state,
    pending_usage_count,
    set_equipment_usage,
)


def _change(eq_type, eq_id, day, state):
    return {"equipment_type": eq_type, "equipment_id": eq_id, "date": day, "state": state}


class EquipmentUsageTest(BaseTestCase):

    def setUp(self):
        super().setUp()
        prod = Production(name="Prod Pointage")
        tech = User(firstname="Tom", lastname="Tech", mail="tech.usage@example.com", role="technicien")
        db.session.add_all([
            prod, tech,
            Vehicle(id="rec_erider", fields={"name": "eRider"}, display_order=0),
            Vehicle(id="rec_ecar", fields={"name": "eCar"}, display_order=1),
            Head(id="rec_head", fields={"name": "Titan LT"}, display_order=0),
        ])
        db.session.commit()
        project = Project(
            name="Projet Pointage",
            production_id=prod.id,
            vehicles_to_check="rec_erider,rec_ecar",
            heads_to_check="rec_head",
            departure_date=date(2026, 9, 9),
            shoot_start_date=date(2026, 9, 10),
            shoot_end_date=date(2026, 9, 12),
            return_date=date(2026, 9, 13),
        )
        db.session.add(project)
        db.session.commit()
        self.project_id = project.id
        self.tech_id = tech.id

    def _login(self, role="technicien"):
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = self.tech_id
            sess["admin_user_role"] = role

    # ── Service ─────────────────────────────────────────────────

    def test_initial_state_lists_days_and_equipment(self):
        project = db.session.get(Project, self.project_id)
        state = get_usage_state(project, today=date(2026, 9, 1))
        self.assertEqual([d["iso"] for d in state["days"]], ["2026-09-10", "2026-09-11", "2026-09-12"])
        self.assertTrue(state["days"][0]["label"].startswith("J1 · "))
        self.assertEqual([e["key"] for e in state["equipment"]],
                         ["vehicle:rec_erider", "vehicle:rec_ecar", "head:rec_head"])
        # Couleurs fixes attribuées automatiquement (palette fermée), distinctes tant que la palette suffit
        colors = [e["color"] for e in state["equipment"]]
        self.assertEqual(len(set(colors)), 3)
        self.assertTrue(all(e["pending_days"] == 3 for e in state["equipment"]))
        self.assertEqual(state["pending_count"], 0)  # aucun jour passé

    def test_three_states_and_totals(self):
        state = set_equipment_usage(self.project_id, [
            _change("vehicle", "rec_erider", "2026-09-10", "used"),
            _change("vehicle", "rec_erider", "2026-09-11", "unused"),
            _change("vehicle", "rec_ecar", "2026-09-10", "used"),
        ], user_id=self.tech_id)
        self.assertEqual(state["marks"]["vehicle:rec_erider"], {"2026-09-10": "used", "2026-09-11": "unused"})
        erider = state["equipment"][0]
        self.assertEqual((erider["used_days"], erider["unused_days"], erider["pending_days"]), (1, 1, 1))
        self.assertEqual(ProjectEquipmentUsage.query.count(), 3)
        self.assertEqual(ProjectEquipmentUsage.query.first().updated_by_id, self.tech_id)

        # Bascule utilisé → non utilisé, puis remise à « non pointé » (suppression de la ligne)
        set_equipment_usage(self.project_id, [_change("vehicle", "rec_ecar", "2026-09-10", "unused")])
        row = ProjectEquipmentUsage.query.filter_by(equipment_id="rec_ecar").one()
        self.assertFalse(row.used)
        state = set_equipment_usage(self.project_id, [_change("vehicle", "rec_ecar", "2026-09-10", "none")])
        self.assertEqual(state["marks"]["vehicle:rec_ecar"], {})
        self.assertEqual(ProjectEquipmentUsage.query.filter_by(equipment_id="rec_ecar").count(), 0)

    def test_validation_rejects_whole_batch(self):
        bad_batches = [
            [_change("vehicle", "rec_inconnu", "2026-09-10", "used")],   # matériel non engagé
            [_change("vehicle", "rec_erider", "2026-09-09", "used")],    # jour de départ, hors tournage
            [_change("vehicle", "rec_erider", "2026-09-10", "maybe")],   # état inconnu
            [_change("drone", "rec_erider", "2026-09-10", "used")],      # type inconnu
            [_change("vehicle", "rec_erider", "pas-une-date", "used")],
            [],
        ]
        for batch in bad_batches:
            with self.assertRaises(EquipmentUsageError):
                set_equipment_usage(self.project_id, [_change("head", "rec_head", "2026-09-10", "used")] + batch
                                    if batch else batch)
        self.assertEqual(ProjectEquipmentUsage.query.count(), 0)

    def test_punctual_days(self):
        project = db.session.get(Project, self.project_id)
        project.date_mode = "punctual"
        project.shoot_dates = ["2026-09-10", "2026-09-14"]
        db.session.commit()
        set_equipment_usage(self.project_id, [_change("vehicle", "rec_erider", "2026-09-14", "used")])
        with self.assertRaises(EquipmentUsageError):
            set_equipment_usage(self.project_id, [_change("vehicle", "rec_erider", "2026-09-11", "used")])

    def test_pending_count_only_counts_past_days(self):
        project = db.session.get(Project, self.project_id)
        self.assertEqual(pending_usage_count(project, today=date(2026, 9, 11)), 2)
        changes = [_change(t, i, "2026-09-10", "used")
                   for t, i in (("vehicle", "rec_erider"), ("vehicle", "rec_ecar"), ("head", "rec_head"))]
        set_equipment_usage(self.project_id, changes)
        project = db.session.get(Project, self.project_id)
        self.assertEqual(pending_usage_count(project, today=date(2026, 9, 11)), 1)
        self.assertEqual(pending_usage_count(project, today=date(2026, 9, 30)), 2)

    def test_orphans_kept_when_equipment_removed(self):
        set_equipment_usage(self.project_id, [_change("vehicle", "rec_ecar", "2026-09-10", "used")])
        project = db.session.get(Project, self.project_id)
        project.vehicles_to_check = "rec_erider"
        db.session.commit()
        state = get_usage_state(project)
        self.assertEqual(state["orphans_count"], 1)
        self.assertNotIn("vehicle:rec_ecar", state["marks"])
        self.assertEqual(ProjectEquipmentUsage.query.count(), 1)

    def test_export_context(self):
        set_equipment_usage(self.project_id, [
            _change("vehicle", "rec_erider", "2026-09-10", "used"),
            _change("vehicle", "rec_ecar", "2026-09-11", "unused"),
        ])
        ctx = build_usage_export_context(self.project_id)
        self.assertEqual(ctx["days_count"], 3)
        self.assertEqual(ctx["rows"][0]["cells"], ["used", "none", "none"])
        self.assertEqual(ctx["rows"][1]["cells"], ["none", "unused", "none"])
        self.assertEqual(ctx["pending_count"], 7)

    # ── Routes ──────────────────────────────────────────────────

    def test_route_saves_for_technician(self):
        self._login("technicien")
        resp = self.client.post(
            f"/admin/projects/{self.project_id}/equipment-usage",
            json={"changes": [_change("head", "rec_head", "2026-09-12", "used")]},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertEqual(body["usage"]["marks"]["head:rec_head"], {"2026-09-12": "used"})

    def test_route_rejects_invalid_change(self):
        self._login("technicien")
        resp = self.client.post(
            f"/admin/projects/{self.project_id}/equipment-usage",
            json={"changes": [_change("vehicle", "rec_erider", "2026-09-20", "used")]},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["status"], "error")

    def test_route_unknown_project(self):
        self._login("technicien")
        resp = self.client.post("/admin/projects/999999/equipment-usage", json={"changes": []})
        self.assertEqual(resp.status_code, 404)

    def test_export_route_returns_pdf(self):
        self._login("technicien")
        resp = self.client.get(f"/admin/projects/{self.project_id}/equipment-usage/export")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "application/pdf")

    def test_project_detail_renders_usage_mode(self):
        set_equipment_usage(self.project_id, [_change("vehicle", "rec_erider", "2026-09-10", "used")])
        self._login("technicien")
        resp = self.client.get(f"/admin/projects/{self.project_id}")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('data-usage-pending-badge', html)
        self.assertIn('"usage_url": "/admin/projects/%d/equipment-usage"' % self.project_id, html)
        self.assertIn('"vehicle:rec_erider": {"2026-09-10": "used"}', html)

    def test_project_delete_cascades(self):
        set_equipment_usage(self.project_id, [_change("vehicle", "rec_erider", "2026-09-10", "used")])
        project = db.session.get(Project, self.project_id)
        db.session.delete(project)
        db.session.commit()
        self.assertEqual(ProjectEquipmentUsage.query.count(), 0)
