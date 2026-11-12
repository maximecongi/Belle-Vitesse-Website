"""Page Indicateurs : périodes et comparaisons, indicateurs commerciaux / matériel, accès et onglets."""
import re
from datetime import date, datetime

from models import Production, Project, User, Vehicle, db
from services.admin.commercial_timeline import add_commercial_event
from services.admin.equipment_usage import set_equipment_usage
from services.admin.indicators import (
    commercial_indicators,
    delta,
    equipment_indicators,
    last_12_months,
    resolve_period,
)
from tests.base import BaseTestCase

NOW = datetime(2026, 11, 12, 15, 0)
TODAY = NOW.date()


class PeriodTest(BaseTestCase):
    def test_rolling_periods_compare_to_previous_window(self):
        p = resolve_period("30d", TODAY)
        self.assertEqual((p["start"], p["end"]), (date(2026, 10, 14), TODAY))
        self.assertEqual((p["prev_start"], p["prev_end"]), (date(2026, 9, 14), date(2026, 10, 13)))
        q = resolve_period("quarter", TODAY)
        self.assertEqual(q["days"], 90)
        self.assertEqual((q["prev_end"] - q["prev_start"]).days + 1, 90)

    def test_twelve_months_and_year_to_date(self):
        p = resolve_period("12m", TODAY)
        self.assertEqual((p["start"], p["prev_start"], p["prev_end"]),
                         (date(2025, 11, 13), date(2024, 11, 13), date(2025, 11, 12)))
        y = resolve_period("year", TODAY)
        # Même portion de l'année précédente
        self.assertEqual((y["start"], y["prev_start"], y["prev_end"]),
                         (date(2026, 1, 1), date(2025, 1, 1), date(2025, 11, 12)))
        self.assertEqual(resolve_period("year", date(2028, 2, 29))["prev_end"], date(2027, 2, 28))

    def test_unknown_period_falls_back_to_twelve_months(self):
        self.assertEqual(resolve_period("nope", TODAY)["key"], "12m")

    def test_last_12_months_flags_months_in_period(self):
        months = last_12_months(resolve_period("30d", TODAY))
        self.assertEqual(len(months), 12)
        self.assertEqual((months[0]["year"], months[0]["month"]), (2025, 12))
        self.assertEqual([m["label"] for m in months if m["in_period"]], ["oct.", "nov."])

    def test_delta_tone_depends_on_desired_direction(self):
        self.assertEqual(delta(62, 54, " pts"), {"text": "+8 pts", "direction": "up", "tone": "good"})
        self.assertEqual(delta(12, 9, " j", better="down")["tone"], "bad")
        self.assertEqual(delta(3, 3)["tone"], "neutral")
        self.assertIsNone(delta(None, 4))
        self.assertEqual(delta(1500.0, 300.0, " €", better="down", money=True)["text"], "+1 200 €")


class CommercialIndicatorsTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.prod = self.create_production("Prod Indicateurs")

    def _project(self, name, events):
        p = Project(name=name, production_id=self.prod.id)
        db.session.add(p)
        db.session.commit()
        for ev_type, day, extra in events:
            add_commercial_event(p.id, event_type=ev_type, date_str=day, now=NOW, **extra)
        return p

    def test_window_counts_funnel_and_comparison(self):
        self._project("A", [("first_request", "2026-10-20", {}), ("quote_sent", "2026-10-22", {}),
                            ("confirmed", "2026-10-30", {})])
        self._project("B", [("first_request", "2026-10-25", {}), ("lost", "2026-11-02", {"lost_reason": "price"})])
        self._project("C", [("first_request", "2026-11-05", {})])
        self._project("D", [("first_request", "2026-09-20", {}), ("confirmed", "2026-09-25", {})])

        period = resolve_period("30d", TODAY)
        c = commercial_indicators(period, last_12_months(period), now=NOW)
        self.assertEqual((c["new"], c["won"], c["lost"]), (3, 1, 1))
        self.assertEqual(c["conversion_rate"], 50)
        self.assertEqual(c["avg_days_to_confirm"], 10)
        self.assertEqual(c["deltas"]["conversion_rate"]["text"], "−50 pts")  # 100 % le mois précédent
        self.assertEqual(c["deltas"]["avg_days_to_confirm"]["tone"], "bad")  # 10 j contre 5 j
        self.assertEqual(c["deltas"]["new"]["text"], "+2")
        self.assertEqual([s["count"] for s in c["funnel"]["stages"]], [3, 1, 1])
        self.assertEqual((c["funnel"]["lost"], c["funnel"]["open"]), (1, 1))
        self.assertEqual([r["key"] for r in c["lost_reasons"]], ["price"])
        # Évolution : 4 demandes (sept., oct. ×2, nov.), confirmations en sept. et oct.
        totals = {col["label"]: [pt["value"] for pt in col["points"]] for col in c["chart"]["columns"]}
        self.assertEqual(totals["oct."], [2, 1])
        self.assertEqual(totals["sept."], [1, 1])


class EquipmentIndicatorsTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        prod = Production(name="Prod Matériel")
        tech = User(firstname="Tom", lastname="Tech", mail="tech.ind@example.com", role="technicien")
        db.session.add_all([
            prod, tech,
            Vehicle(id="rec_erider", fields={"name": "eRider"}, display_order=0),
            Vehicle(id="rec_ecar", fields={"name": "eCar"}, display_order=1),
        ])
        db.session.commit()
        p = Project(name="Pub", production_id=prod.id, vehicles_to_check="rec_erider,rec_ecar",
                    shoot_start_date=date(2026, 10, 10), shoot_end_date=date(2026, 10, 12))
        db.session.add(p)
        db.session.commit()
        set_equipment_usage(p.id, [
            {"equipment_type": "vehicle", "equipment_id": "rec_erider", "date": "2026-10-10", "state": "used"},
            {"equipment_type": "vehicle", "equipment_id": "rec_erider", "date": "2026-10-11", "state": "used"},
            {"equipment_type": "vehicle", "equipment_id": "rec_erider", "date": "2026-10-12", "state": "unused"},
            {"equipment_type": "vehicle", "equipment_id": "rec_ecar", "date": "2026-10-10", "state": "used"},
        ], user_id=tech.id)

    def test_usage_rate_ranking_and_pointing(self):
        period = resolve_period("30d", date(2026, 10, 20))
        e = equipment_indicators(period, last_12_months(period))
        self.assertEqual((e["used_days"], e["pointed_days"], e["usage_rate"]), (3, 4, 75))
        self.assertEqual([(x["name"], x["count"]) for x in e["by_used"]], [("eRider", 2), ("eCar", 1)])
        self.assertEqual([(x["name"], x["count"]) for x in e["by_rate"]], [("eCar", 100), ("eRider", 67)])
        # 6 couples matériel × jour attendus, 4 pointés
        self.assertEqual((e["pointing"]["marked"], e["pointing"]["expected"]), (4, 6))
        self.assertEqual(e["pending_projects"], 1)
        self.assertIsNone(e["deltas"]["usage_rate"])  # rien de pointé sur la période précédente
        self.assertEqual(e["deltas"]["used_days"]["text"], "+3 j")


class IndicatorsPageTest(BaseTestCase):
    def _login(self, role):
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_user_role"] = role

    def test_admin_only(self):
        for role in ("Manager", "Commercial", "Technicien"):
            self._login(role)
            self.assertEqual(self.client.get("/admin/indicators").status_code, 302, role)

    def test_tabs_and_period_selector(self):
        self._login("Administrateur")
        html = self.client.get("/admin/indicators?period=quarter&tab=incidents").get_data(as_text=True)
        for key in ("commercial", "equipment", "incidents"):
            self.assertIn(f'id="ind-panel-{key}"', html)
        self.assertRegex(html, r'data-ind-panel="incidents"\s*>')  # onglet demandé affiché
        self.assertIn('data-ind-panel="commercial" hidden', html)
        self.assertIn('class="ind-period is-active" aria-current="true">Trimestre', html)
        self.assertIn("period=30d&amp;tab=incidents", html)  # les liens de période gardent l'onglet
        self.assertNotIn("indisponibles", html)

    def test_defaults(self):
        self._login("Administrateur")
        html = self.client.get("/admin/indicators").get_data(as_text=True)
        self.assertIn('aria-current="true">12 mois', html)
        self.assertRegex(html, r'data-ind-tab="commercial"[^>]*aria-selected="true"')
