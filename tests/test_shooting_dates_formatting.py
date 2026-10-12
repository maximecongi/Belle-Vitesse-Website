import unittest
from datetime import date
from app import create_app
from utils.formatting import parse_and_format_shooting_dates


class TestShootingDatesFormatting(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_user_reported_case_16_dates(self):
        raw = (
            "12/10/2026, 13/10/2026, 14/10/2026, 16/10/2026, "
            "20/10/2026, 21/10/2026, 22/10/2026, 23/10/2026, "
            "26/10/2026, 27/10/2026, 28/10/2026, 29/10/2026, "
            "03/11/2026, 04/11/2026, 09/11/2026, 17/11/2026"
        )
        info = parse_and_format_shooting_dates(raw)

        self.assertTrue(info["is_punctual"])
        self.assertTrue(info["has_dates"])
        self.assertEqual(info["total_days"], 16)
        self.assertEqual(info["periods_count"], 7)
        self.assertEqual(info["global_label"], "Du 12 oct. au 17 nov. 2026")

        # Vérification des créneaux
        periods = info["periods"]
        self.assertEqual(len(periods), 7)

        # Créneau 1: 12 au 14 oct. (3 jours)
        self.assertEqual(periods[0]["days_count"], 3)
        self.assertEqual(periods[0]["label"], "12 au 14 oct. 2026")
        self.assertEqual(periods[0]["compact"], "12–14 oct.")

        # Créneau 2: 16 oct. (1 jour)
        self.assertEqual(periods[1]["days_count"], 1)
        self.assertEqual(periods[1]["label"], "16 oct. 2026")
        self.assertEqual(periods[1]["compact"], "16 oct.")

        # Créneau 3: 20 au 23 oct. (4 jours)
        self.assertEqual(periods[2]["days_count"], 4)
        self.assertEqual(periods[2]["label"], "20 au 23 oct. 2026")

        # Créneau 4: 26 au 29 oct. (4 jours)
        self.assertEqual(periods[3]["days_count"], 4)
        self.assertEqual(periods[3]["label"], "26 au 29 oct. 2026")

        # Créneau 5: 03 au 04 nov. (2 jours)
        self.assertEqual(periods[4]["days_count"], 2)
        self.assertEqual(periods[4]["label"], "03 au 04 nov. 2026")

        # Créneau 6: 09 nov. (1 jour)
        self.assertEqual(periods[5]["days_count"], 1)
        self.assertEqual(periods[5]["label"], "09 nov. 2026")

        # Créneau 7: 17 nov. (1 jour)
        self.assertEqual(periods[6]["days_count"], 1)
        self.assertEqual(periods[6]["label"], "17 nov. 2026")

        # Libellés résumés
        self.assertIn("16 jours", info["summary_text"])
        self.assertIn("12–14 oct.", info["summary_text"])
        self.assertIn("17 nov. 2026", info["summary_text"])

    def test_iso_list_input(self):
        iso_dates = ["2026-10-12", "2026-10-13", "2026-10-14"]
        info = parse_and_format_shooting_dates(iso_dates)
        self.assertTrue(info["has_dates"])
        self.assertEqual(info["total_days"], 3)
        self.assertEqual(info["periods_count"], 1)
        self.assertEqual(info["display_text"], "12 au 14 oct. 2026")

    def test_single_date(self):
        info = parse_and_format_shooting_dates("16/10/2026")
        self.assertFalse(info["is_punctual"])
        self.assertEqual(info["total_days"], 1)
        self.assertEqual(info["display_text"], "16 oct. 2026")

    def test_continuous_range_string(self):
        info = parse_and_format_shooting_dates("12/10/2026 au 16/10/2026")
        self.assertFalse(info["is_punctual"])
        self.assertEqual(info["display_text"], "12/10/2026 au 16/10/2026")

    def test_empty_or_dash(self):
        info1 = parse_and_format_shooting_dates("")
        self.assertFalse(info1["has_dates"])
        self.assertEqual(info1["display_text"], "—")

        info2 = parse_and_format_shooting_dates("—")
        self.assertFalse(info2["has_dates"])
        self.assertEqual(info2["display_text"], "—")

    def test_jinja_filter_rendering(self):
        template_str = "{{ (raw | parse_shooting_dates).summary_text }}"
        rendered = self.app.jinja_env.from_string(template_str).render(
            raw="12/10/2026, 13/10/2026, 16/10/2026"
        )
        self.assertIn("3 jours", rendered)
        self.assertIn("12–13 oct.", rendered)
        self.assertIn("16 oct. 2026", rendered)


if __name__ == "__main__":
    unittest.main()
