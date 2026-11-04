from datetime import date
from tests.base import BaseTestCase
from services.admin.projects.intervals import (
    _parse_shoot_dates,
    _parse_int,
    _parse_inter_shoot_statuses,
    get_project_shoot_status,
)
from services.admin.projects.locations import _parse_shooting_locations
from models.project import Project


class ProjectIntervalsAndLocationsTest(BaseTestCase):
    """Suite de tests unitaires pour le découpage des intervalles et des lieux de tournage."""

    def test_parse_shoot_dates(self):
        # 1. Parsing depuis JSON list
        form = {"shoot_dates": '["2026-11-10", "2026-11-05"]'}
        res = _parse_shoot_dates(form)
        self.assertEqual(res, ["2026-11-05", "2026-11-10"])

        # 2. Parsing depuis chaîne séparée par virgules
        form = {"shoot_dates": " 2026-12-01 , 2026-11-15 , 2026-12-01 "}
        res = _parse_shoot_dates(form)
        self.assertEqual(res, ["2026-11-15", "2026-12-01"])

        # 3. Parsing depuis une liste Python brute
        form = {"shoot_dates": ["2026-10-02", "2026-10-01"]}
        res = _parse_shoot_dates(form)
        self.assertEqual(res, ["2026-10-01", "2026-10-02"])

        # 4. Formulaire vide ou None
        self.assertEqual(_parse_shoot_dates({}), [])
        self.assertEqual(_parse_shoot_dates({"shoot_dates": ""}), [])
        self.assertEqual(_parse_shoot_dates(None), [])

    def test_parse_int(self):
        self.assertEqual(_parse_int("123"), 123)
        self.assertEqual(_parse_int(456), 456)
        self.assertEqual(_parse_int(" 789 "), 789)
        self.assertIsNone(_parse_int(None))
        self.assertIsNone(_parse_int(""))
        self.assertIsNone(_parse_int("abc"))
        self.assertIsNone(_parse_int("12.34"))

    def test_parse_inter_shoot_statuses(self):
        # 1. Parsing depuis JSON liste
        json_data = '[{"start": "2026-11-01", "end": "2026-11-03", "is_immobilized": false}]'
        res = _parse_inter_shoot_statuses({"inter_shoot_statuses": json_data})
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["start"], "2026-11-01")
        self.assertEqual(res[0]["end"], "2026-11-03")
        self.assertFalse(res[0]["is_immobilized"])

        # 2. Parsing depuis dictionnaire avec clés 'start_end'
        dict_data = {
            "2026-11-05_2026-11-07": {"is_immobilized": True},
            "2026-11-08_2026-11-10": False,
        }
        res = _parse_inter_shoot_statuses({"inter_shoot_statuses": dict_data})
        self.assertEqual(len(res), 2)
        starts = [item["start"] for item in res]
        self.assertIn("2026-11-05", starts)
        self.assertIn("2026-11-08", starts)

        # 3. Données invalides ou vides
        self.assertEqual(_parse_inter_shoot_statuses({}), [])
        self.assertEqual(_parse_inter_shoot_statuses({"inter_shoot_statuses": "invalid-json"}), [])

    def test_parse_shooting_locations(self):
        # 1. Valide JSON avec nom et adresse
        data = '[{"name": "Circuit Paul Ricard", "address": "Le Castellet"}, {"name": "Studio A", "address": ""}]'
        res = _parse_shooting_locations({"shooting_locations": data})
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["name"], "Circuit Paul Ricard")
        self.assertEqual(res[0]["address"], "Le Castellet")
        self.assertEqual(res[1]["name"], "Studio A")
        self.assertEqual(res[1]["address"], "")

        # 2. Ignorer les éléments sans nom
        data_no_name = '[{"name": "", "address": "Nowhere"}, {"name": "   ", "address": "123"}]'
        res = _parse_shooting_locations({"shooting_locations": data_no_name})
        self.assertEqual(res, [])

        # 3. Entrée None ou chaîne vide
        self.assertEqual(_parse_shooting_locations({}), [])
        self.assertEqual(_parse_shooting_locations(None), [])
        self.assertEqual(_parse_shooting_locations({"shooting_locations": "bad-json"}), [])

    def test_get_project_shoot_status_punctual(self):
        prod = self.create_production(name="Prod Punctual Test")
        p = Project(
            name="Tournage Ponctuel",
            production_id=prod.id,
            date_mode="punctual",
            shoot_dates=["2026-11-05", "2026-11-08", "2026-11-12"],
            return_date=date(2026, 11, 13),
            is_immobilized_between=True,
        )

        # Jour de tournage exact (5 nov)
        s1 = get_project_shoot_status(p, today_date=date(2026, 11, 5))
        self.assertEqual(s1["status"], "in_progress")
        self.assertEqual(s1["label"], "En tournage")
        self.assertIn("2026", s1["dates_label"])

        # Jour entre deux tournages (6 nov) avec immobilisation active
        s2 = get_project_shoot_status(p, today_date=date(2026, 11, 6))
        self.assertEqual(s2["status"], "standby")
        self.assertEqual(s2["label"], "Immobilisé")

        # Jour entre deux tournages sans immobilisation
        p.is_immobilized_between = False
        s3 = get_project_shoot_status(p, today_date=date(2026, 11, 6))
        self.assertEqual(s3["status"], "upcoming")
        self.assertEqual(s3["label"], "À venir")

        # Date postérieure au retour (15 nov)
        s4 = get_project_shoot_status(p, today_date=date(2026, 11, 15))
        self.assertEqual(s4["status"], "completed")
        self.assertEqual(s4["label"], "Clôturé")

    def test_get_project_shoot_status_continuous(self):
        prod = self.create_production(name="Prod Continuous Test")
        p = Project(
            name="Tournage Continu",
            production_id=prod.id,
            date_mode="continuous",
            shoot_start_date=date(2026, 11, 10),
            shoot_end_date=date(2026, 11, 15),
            departure_date=date(2026, 11, 9),
            return_date=date(2026, 11, 16),
        )

        # Avant le début du tournage
        s1 = get_project_shoot_status(p, today_date=date(2026, 11, 8))
        self.assertEqual(s1["status"], "upcoming")
        self.assertEqual(s1["label"], "À venir")

        # Pendant le tournage
        s2 = get_project_shoot_status(p, today_date=date(2026, 11, 12))
        self.assertEqual(s2["status"], "in_progress")
        self.assertEqual(s2["label"], "En tournage")

        # Après la fin du tournage
        s3 = get_project_shoot_status(p, today_date=date(2026, 11, 20))
        self.assertEqual(s3["status"], "completed")
        self.assertEqual(s3["label"], "Clôturé")

    def test_get_project_shoot_status_no_dates(self):
        prod = self.create_production(name="Prod No Dates")
        p = Project(
            name="Tournage Sans Dates",
            production_id=prod.id,
        )
        s = get_project_shoot_status(p, today_date=date(2026, 11, 1))
        self.assertEqual(s["status"], "upcoming")
        self.assertEqual(s["dates_label"], "Dates à confirmer")
