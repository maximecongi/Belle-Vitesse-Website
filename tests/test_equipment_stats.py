from datetime import date
from unittest.mock import patch

from tests.base import BaseTestCase
from models import Head, Production, Project, User, Vehicle, db
from models.equipment_usage import ProjectEquipmentUsageLog
from services.admin.equipment_stats import (
    equipment_usage_stats,
    fleet_usage_ranking,
    pointing_rate,
    projects_pending_usage,
    send_usage_reminder_digest,
    usage_digest_recipients,
)
from services.admin.equipment_usage import set_equipment_usage

TODAY = date(2026, 10, 20)


def _change(eq_id, day, state, eq_type="vehicle"):
    return {"equipment_type": eq_type, "equipment_id": eq_id, "date": day, "state": state}


class EquipmentStatsTest(BaseTestCase):

    def setUp(self):
        super().setUp()
        prod = Production(name="Prod Stats")
        admin = User(firstname="Ada", lastname="Admin", mail="admin.stats@example.com", role="Administrateur")
        manager = User(firstname="Max", lastname="Manager", mail="manager.stats@example.com", role="manager")
        tech = User(firstname="Tom", lastname="Tech", mail="tech.stats@example.com", role="technicien")
        commercial = User(firstname="Cléo", lastname="Com", mail="com.stats@example.com", role="commercial")
        db.session.add_all([
            prod, admin, manager, tech, commercial,
            Vehicle(id="rec_erider", fields={"name": "eRider"}, display_order=0),
            Vehicle(id="rec_ecar", fields={"name": "eCar"}, display_order=1),
            Head(id="rec_head", fields={"name": "Titan LT"}, display_order=0),
        ])
        db.session.commit()
        # Projet 1 : 10 → 12 octobre (passé) ; projet 2 : 19 → 22 octobre (en cours au 20)
        p1 = Project(name="Pub Octobre", production_id=prod.id, vehicles_to_check="rec_erider,rec_ecar",
                     shoot_start_date=date(2026, 10, 10), shoot_end_date=date(2026, 10, 12))
        p2 = Project(name="Clip", production_id=prod.id, vehicles_to_check="rec_erider", heads_to_check="rec_head",
                     shoot_start_date=date(2026, 10, 19), shoot_end_date=date(2026, 10, 22))
        db.session.add_all([p1, p2])
        db.session.commit()
        self.p1, self.p2 = p1.id, p2.id
        self.tech_id, self.admin_id = tech.id, admin.id

        set_equipment_usage(self.p1, [
            _change("rec_erider", "2026-10-10", "used"),
            _change("rec_erider", "2026-10-11", "used"),
            _change("rec_erider", "2026-10-12", "unused"),
            _change("rec_ecar", "2026-10-10", "used"),
        ], user_id=self.tech_id)
        set_equipment_usage(self.p2, [_change("rec_erider", "2026-10-19", "used")], user_id=self.tech_id)

    def _login(self, user_id, role):
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = user_id
            sess["admin_user_role"] = role

    # ── Historique ──────────────────────────────────────────────

    def test_history_logs_only_real_changes(self):
        self.assertEqual(ProjectEquipmentUsageLog.query.count(), 5)
        set_equipment_usage(self.p1, [_change("rec_erider", "2026-10-10", "used")], user_id=self.tech_id)  # no-op
        self.assertEqual(ProjectEquipmentUsageLog.query.count(), 5)
        set_equipment_usage(self.p1, [_change("rec_erider", "2026-10-10", "none")], user_id=self.admin_id, source="mcp")
        last = ProjectEquipmentUsageLog.query.order_by(ProjectEquipmentUsageLog.id.desc()).first()
        self.assertEqual((last.old_state, last.new_state, last.source, last.user_id),
                         ("used", "none", "mcp", self.admin_id))

    # ── Statistiques ────────────────────────────────────────────

    def test_equipment_stats(self):
        s = equipment_usage_stats("vehicle", "rec_erider", today=TODAY)
        self.assertEqual(s["used_year"], 3)
        self.assertEqual(s["used_12m"], 3)
        self.assertEqual(s["months"][9]["count"], 3)
        self.assertTrue(s["months"][9]["is_current"])
        self.assertEqual(s["usage_rate"], 75)  # 3 utilisés / 4 pointés
        self.assertEqual(s["per_project"], {self.p1: 2, self.p2: 1})
        self.assertIsNone(s["next_year"])
        # Année sans pointage : 0 jour sur l'année, le taux (tous projets confondus) reste calculé
        s2025 = equipment_usage_stats("vehicle", "rec_ecar", year=2025, today=TODAY)
        self.assertEqual((s2025["used_year"], s2025["usage_rate"]), (0, 100))
        self.assertIsNone(equipment_usage_stats("head", "rec_head", today=TODAY)["usage_rate"])

    def test_ranking_periods(self):
        r = fleet_usage_ranking("30d", today=TODAY)
        self.assertEqual([(i["name"], i["used_days"]) for i in r["rows"]],
                         [("eRider", 3), ("eCar", 1), ("Titan LT", 0)])
        self.assertEqual(r["rows"][0]["pct"], 100)
        self.assertEqual(fleet_usage_ranking("unknown", today=TODAY)["period"], "30d")
        self.assertEqual(fleet_usage_ranking("year", today=date(2027, 1, 5))["total_used"], 0)

    def test_pointing_rate_and_pending(self):
        # Attendus : p1 = 3 jours × 2 véhicules = 6 ; p2 = 2 jours passés (19, 20) × 2 matériels = 4 → 10
        # Pointés : 4 (p1) + 1 (p2) = 5
        rate = pointing_rate(today=TODAY)
        self.assertEqual((rate["expected"], rate["marked"], rate["rate"]), (10, 5, 50))
        pending = projects_pending_usage(today=TODAY)
        self.assertEqual([(p["name"], p["pending_days"]) for p in pending], [("Clip", 2), ("Pub Octobre", 2)])
        self.assertEqual(len(projects_pending_usage(today=date(2027, 3, 1), ended_within_days=60)), 0)

    # ── Rappel quotidien ────────────────────────────────────────

    def test_digest_recipients_and_sending(self):
        self.assertEqual(usage_digest_recipients(), ["admin.stats@example.com", "manager.stats@example.com"])
        dry = send_usage_reminder_digest(today=TODAY, dry_run=True)
        self.assertEqual((len(dry["projects"]), dry["sent"]), (2, 0))
        with self.app.test_request_context(), \
                patch("utils.mailer.EmailService.send_templated_email", return_value=True) as send:
            res = send_usage_reminder_digest(today=TODAY, base_url="https://erp.example.com")
        self.assertEqual(res["sent"], 2)
        kwargs = send.call_args.kwargs
        self.assertIn("2 projets", kwargs["subject"])
        self.assertTrue(kwargs["context"]["projects"][0]["url"].startswith("https://erp.example.com/admin/projects/"))
        self.assertTrue(kwargs["context"]["projects"][0]["url"].endswith("#pointage"))

    def test_digest_template_renders(self):
        with self.app.test_request_context():
            from flask import render_template
            html = render_template("emails/equipment_usage_digest.html", projects=[
                {"name": "Clip", "production": "Prod", "pending_days": 2, "last_day_fr": "20/10/2026", "url": "#"}],
                total_days=2, window_days=60, dashboard_url="#")
        self.assertIn("Pointage du matériel à compléter", html)
        self.assertIn("Clip", html)

    def test_no_digest_when_nothing_pending(self):
        with patch("utils.mailer.EmailService.send_templated_email") as send:
            res = send_usage_reminder_digest(today=date(2026, 10, 5))
        self.assertEqual(res["sent"], 0)
        send.assert_not_called()

    # ── Pages ───────────────────────────────────────────────────

    def test_dashboard_pending_projects_admin_only(self):
        self._login(self.admin_id, "administrateur")
        html = self.client.get("/admin/dashboard").get_data(as_text=True)
        self.assertIn("Projets à pointer", html)
        self.assertIn("#pointage", html)
        self.assertNotIn("Taux de pointage", html)  # déplacé sur la page Flotte

        self._login(self.admin_id, "manager")
        html = self.client.get("/admin/dashboard").get_data(as_text=True)
        self.assertNotIn("Projets à pointer", html)

    def test_fleet_usage_stats_admin_only(self):
        self._login(self.admin_id, "administrateur")
        resp = self.client.get("/admin/fleet?usage_period=year")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("Utilisation du matériel", html)
        self.assertIn("Taux de pointage", html)
        # Les deux périodes sont rendues ; « Année en cours » est la période affichée
        self.assertIn('data-usage-period-panel="30d" hidden', html)
        self.assertIn('data-usage-period="year" aria-pressed="true"', html)

        for role in ("manager", "commercial"):
            self._login(self.admin_id, role)
            html = self.client.get("/admin/fleet").get_data(as_text=True)
            self.assertNotIn("Taux de pointage", html, role)

    def test_vehicle_page_shows_usage(self):
        self._login(self.admin_id, "administrateur")
        resp = self.client.get("/admin/fleet/rec_erider")
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True)[:300])
        html = resp.get_data(as_text=True)
        self.assertIn("Taux d'utilisation", html)
        self.assertIn("vehicle-usage-col", html)

    # ── Outils MCP ──────────────────────────────────────────────

    def _mcp_user(self, role="manager", scope="write"):
        from mcp_auth.auth import McpUserContext
        from mcp_server.context import CURRENT_MCP_USER
        CURRENT_MCP_USER.set(McpUserContext(user_id=self.admin_id, mail="admin.stats@example.com",
                                            firstname="Ada", lastname="Admin", role=role, scope=scope))

    def test_mcp_tools(self):
        from mcp_server.tools import equipment_usage as tools
        self._mcp_user()

        state = tools.get_equipment_usage(self.p1)
        self.assertEqual(state["status"], "success")
        erider = next(e for e in state["equipment"] if e["name"] == "eRider")
        self.assertEqual(erider["marks"]["2026-10-12"], "unused")

        res = tools.set_equipment_usage(self.p1, [{"equipment": "ECAR", "date": "2026-10-11", "state": "unused"}])
        self.assertEqual(res["status"], "success", res)
        last = ProjectEquipmentUsageLog.query.order_by(ProjectEquipmentUsageLog.id.desc()).first()
        self.assertEqual((last.equipment_id, last.source, last.user_id), ("rec_ecar", "mcp", self.admin_id))

        bad = tools.set_equipment_usage(self.p1, [{"equipment": "Titan LT", "date": "2026-10-11", "state": "used"}])
        self.assertEqual(bad["status"], "error")
        self.assertIn("non engagé", bad["message"])

        history = tools.get_equipment_usage_history(self.p1)
        self.assertEqual(history["history"][0]["equipment_name"], "eCar")

        stats = tools.get_equipment_usage_stats("erider", year=2026)
        self.assertEqual(stats["status"], "success")
        self.assertEqual(stats["used_days_year"], 3)

        fleet = tools.get_fleet_usage_stats("30d")
        self.assertEqual(fleet["status"], "success")
        self.assertTrue(any(p["name"] == "Clip" for p in fleet["projects_to_point"]))

    def test_mcp_write_refused_for_read_only(self):
        from mcp_server.tools import equipment_usage as tools
        self._mcp_user(role="commercial", scope="read_only")
        res = tools.set_equipment_usage(self.p1, [{"equipment": "eCar", "date": "2026-10-11", "state": "used"}])
        self.assertEqual(res.get("error_code"), 403)
        self.assertEqual(tools.get_equipment_usage(self.p1)["status"], "success")
