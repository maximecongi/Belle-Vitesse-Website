import unittest
from datetime import date, datetime, timezone

from services.common.kdrive.paths import (
    clean_segment,
    format_year,
    format_month,
    format_name,
    build_project_rel_path,
    build_project_path,
    build_document_directory_path,
)
from services.common.kdrive.config import KDRIVE_BASE_PATH


class MockProduction:
    def __init__(self, name):
        self.name = name


class MockProject:
    def __init__(self, name, project_id, production_name, departure_date=None, shoot_start_date=None):
        self.name = name
        self.project_id = project_id
        self.production = MockProduction(production_name) if production_name else None
        self.departure_date = departure_date
        self.shoot_start_date = shoot_start_date


class KDrivePathsTestCase(unittest.TestCase):
    """Suite de tests unitaires pour la construction des chemins kDrive."""

    def test_clean_segment_valid(self):
        self.assertEqual(clean_segment("Mon Projet / Test"), "Mon Projet Test")
        self.assertEqual(clean_segment("Prod\\Sub\\Dir"), "Prod Sub Dir")
        self.assertEqual(clean_segment("   Espaces   Multiples   "), "Espaces Multiples")
        self.assertEqual(clean_segment("BVPR-12345"), "BVPR-12345")

    def test_clean_segment_invalid(self):
        for invalid in ["", "   ", None, ".", "..", "—"]:
            with self.assertRaises(ValueError):
                clean_segment(invalid)

    def test_format_year(self):
        self.assertEqual(format_year(2026), "2026")
        self.assertEqual(format_year("2026"), "2026")
        self.assertEqual(format_year(date(2025, 4, 1)), "2025")
        self.assertEqual(format_year(datetime(2024, 12, 31)), "2024")
        current_year = datetime.now(timezone.utc).strftime("%Y")
        self.assertEqual(format_year(None), current_year)
        self.assertEqual(format_year("invalide"), current_year)

    def test_format_month(self):
        self.assertEqual(format_month(9), "09")
        self.assertEqual(format_month("9"), "09")
        self.assertEqual(format_month("09"), "09")
        self.assertEqual(format_month("12"), "12")
        self.assertEqual(format_month(date(2026, 3, 15)), "03")
        self.assertEqual(format_month(datetime(2026, 11, 1)), "11")
        current_month = datetime.now(timezone.utc).strftime("%m")
        self.assertEqual(format_month(None), current_month)
        self.assertEqual(format_month("abc"), current_month)
        self.assertEqual(format_month(99), current_month)

    def test_format_name(self):
        self.assertEqual(format_name("academy films", "prod"), "ACADEMY FILMS")
        self.assertEqual(format_name("Tournage / Pub 2026", "proj"), "TOURNAGE PUB 2026")

    def test_build_project_rel_path_10_cases(self):
        test_cases = [
            (2026, 9, "ACADEMY FILMS", "PROJETS TEST", "2026/09/ACADEMY FILMS/PROJETS TEST"),
            (2026, 7, "RVZ", "PUB MATMUT", "2026/07/RVZ/PUB MATMUT"),
            (2026, "06", "Pyramide", "Anatole Latuile", "2026/06/PYRAMIDE/ANATOLE LATUILE"),
            (2026, 8, "ORSOIE", "CLEM BLOCK", "2026/08/ORSOIE/CLEM BLOCK"),
            (2026, 10, "Ami Productions", "Défilé Ami", "2026/10/AMI PRODUCTIONS/DÉFILÉ AMI"),
            (2026, "5", "PELOTON PRODUCTION", "Cannes / Festival", "2026/05/PELOTON PRODUCTION/CANNES FESTIVAL"),
            (2026, 4, "TCO", "Huck x Nike", "2026/04/TCO/HUCK X NIKE"),
            (2026, 3, "Academy films", "Interstellar\\3", "2026/03/ACADEMY FILMS/INTERSTELLAR 3"),
            (2026, 9, "Biscuit Filmworks", "Test Projet 3", "2026/09/BISCUIT FILMWORKS/TEST PROJET 3"),
            (2026, 1, "Studio Cinema", "Tournage Pub Sport", "2026/01/STUDIO CINEMA/TOURNAGE PUB SPORT"),
        ]
        for y, m, prod, proj, expected in test_cases:
            rel = build_project_rel_path(y, m, prod, proj)
            self.assertEqual(rel, expected)

    def test_build_project_path(self):
        p = MockProject(
            name="Projets Test",
            project_id="BVPR-GG96XP13R8MU",
            production_name="Academy Films",
            departure_date=date(2026, 9, 15)
        )
        full_path = build_project_path(p)
        expected = f"{KDRIVE_BASE_PATH}/2026/09/ACADEMY FILMS/PROJETS TEST/BVPR-GG96XP13R8MU"
        self.assertEqual(full_path, expected)

    def test_build_document_directory_path(self):
        p = MockProject(
            name="Pub Matmut",
            project_id="BVPR-JQUFNY20GT44",
            production_name="RVZ",
            departure_date=date(2026, 7, 10)
        )
        # Checkout
        self.assertEqual(build_document_directory_path(p, "checkout", "BVCO-1111", "pdf"), "4_SÉCURITÉ/1_CHECKOUTS/BVCO-1111")
        self.assertEqual(build_document_directory_path(p, "checkout", "BVCO-1111", "photo"), "4_SÉCURITÉ/1_CHECKOUTS/BVCO-1111/PHOTOS")
        # Checkin
        self.assertEqual(build_document_directory_path(p, "checkin", "BVCI-2222", "pdf"), "4_SÉCURITÉ/5_CHECKINS/BVCI-2222")
        self.assertEqual(build_document_directory_path(p, "checkin", "BVCI-2222", "photo"), "4_SÉCURITÉ/5_CHECKINS/BVCI-2222/PHOTOS")
        # CGL
        self.assertEqual(build_document_directory_path(p, "cgl", "BVRA-3333", "pdf"), "4_SÉCURITÉ/3_CGL/BVRA-3333/1_CGL")
        self.assertEqual(build_document_directory_path(p, "cgl", "BVRA-3333", "insurance"), "4_SÉCURITÉ/3_CGL/BVRA-3333/2_ATTESTATION_ASSURANCE")
        # Safety rules
        self.assertEqual(build_document_directory_path(p, "safety_rules", "BVSR-4444", "pdf"), "4_SÉCURITÉ/2_RÈGLES_SÉCURITÉ/BVSR-4444")
        # Pilot waiver
        self.assertEqual(build_document_directory_path(p, "pilot_waiver", "BVPA-6666", "pdf"), "4_SÉCURITÉ/4_ATTESTATIONS_PILOTES/BVPA-6666")
        # Incident
        self.assertEqual(build_document_directory_path(p, "incident", "BVIC-5555", "pdf"), "6_INCIDENTS/BVIC-5555")
        self.assertEqual(build_document_directory_path(p, "incident", "BVIC-5555", "photo"), "6_INCIDENTS/BVIC-5555/PHOTOS")
        self.assertEqual(build_document_directory_path(p, "incident", "BVIC-5555", "document"), "6_INCIDENTS/BVIC-5555/DOCUMENTS")
