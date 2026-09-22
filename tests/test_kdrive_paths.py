from datetime import date, datetime, timezone
import pytest

from services.common.kdrive.paths import (
    clean_segment,
    format_year,
    format_month,
    format_name,
    build_project_rel_path,
    build_project_path,
    build_document_directory_path,
    PROJECT_SUBFOLDERS,
    DOC_FOLDERS,
    ROLE_SUBFOLDERS,
)


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


def test_clean_segment_valid():
    assert clean_segment("Mon Projet / Test") == "Mon Projet Test"
    assert clean_segment("Prod\\Sub\\Dir") == "Prod Sub Dir"
    assert clean_segment("   Espaces   Multiples   ") == "Espaces Multiples"
    assert clean_segment("BVPR-12345") == "BVPR-12345"


def test_clean_segment_invalid():
    with pytest.raises(ValueError):
        clean_segment("")

    with pytest.raises(ValueError):
        clean_segment("   ")

    with pytest.raises(ValueError):
        clean_segment(None)

    with pytest.raises(ValueError):
        clean_segment(".")

    with pytest.raises(ValueError):
        clean_segment("..")

    with pytest.raises(ValueError):
        clean_segment("—")


def test_format_year():
    assert format_year(2026) == "2026"
    assert format_year("2026") == "2026"
    assert format_year(date(2025, 4, 1)) == "2025"
    assert format_year(datetime(2024, 12, 31)) == "2024"
    # Fallback si absent ou invalide : ne doit JAMAIS être "—"
    current_year = datetime.now(timezone.utc).strftime("%Y")
    assert format_year(None) == current_year
    assert format_year("invalide") == current_year


def test_format_month():
    assert format_month(9) == "09"
    assert format_month("9") == "09"
    assert format_month("09") == "09"
    assert format_month("12") == "12"
    assert format_month(date(2026, 3, 15)) == "03"
    assert format_month(datetime(2026, 11, 1)) == "11"
    # Fallback si absent ou invalide
    current_month = datetime.now(timezone.utc).strftime("%m")
    assert format_month(None) == current_month
    assert format_month("abc") == current_month
    assert format_month(99) == current_month


def test_format_name():
    assert format_name("academy films", "prod") == "ACADEMY FILMS"
    assert format_name("Tournage / Pub 2026", "proj") == "TOURNAGE PUB 2026"


def test_build_project_rel_path_10_cases():
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
        assert rel == expected


def test_build_project_path():
    p = MockProject(
        name="Projets Test",
        project_id="BVPR-GG96XP13R8MU",
        production_name="Academy Films",
        departure_date=date(2026, 9, 15)
    )
    full_path = build_project_path(p)
    expected = "Common documents/BELLE VITESSE/7_ADMINISTRATION/1_TOURNAGES/2026/09/ACADEMY FILMS/PROJETS TEST/BVPR-GG96XP13R8MU"
    assert full_path == expected


def test_build_document_directory_path():
    p = MockProject(
        name="Pub Matmut",
        project_id="BVPR-JQUFNY20GT44",
        production_name="RVZ",
        departure_date=date(2026, 7, 10)
    )

    # 1. Checkout (root PDF & photos)
    assert build_document_directory_path(p, "checkout", "BVCO-1111", "pdf") == "4_SÉCURITÉ/1_CHECKOUT/BVCO-1111"
    assert build_document_directory_path(p, "checkout", "BVCO-1111", "photo") == "4_SÉCURITÉ/1_CHECKOUT/BVCO-1111/PHOTOS"

    # 2. Checkin
    assert build_document_directory_path(p, "checkin", "BVCI-2222", "pdf") == "4_SÉCURITÉ/4_CHECKIN/BVCI-2222"
    assert build_document_directory_path(p, "checkin", "BVCI-2222", "photo") == "4_SÉCURITÉ/4_CHECKIN/BVCI-2222/PHOTOS"

    # 3. Pilot waiver
    assert build_document_directory_path(p, "pilot_waiver", "BVPW-3333", "pdf") == "4_SÉCURITÉ/2_DÉCHARGE_PILOTE/BVPW-3333/1_DÉCHARGE"
    assert build_document_directory_path(p, "pilot_waiver", "BVPW-3333", "insurance") == "4_SÉCURITÉ/2_DÉCHARGE_PILOTE/BVPW-3333/2_ATTESTATION_ASSURANCE"
    assert build_document_directory_path(p, "pilot_waiver", "BVPW-3333", "license") == "4_SÉCURITÉ/2_DÉCHARGE_PILOTE/BVPW-3333/3_PERMIS_DE_CONDUIRE"
    assert build_document_directory_path(p, "pilot_waiver", "BVPW-3333", "identity") == "4_SÉCURITÉ/2_DÉCHARGE_PILOTE/BVPW-3333/4_CARTE_IDENTITÉ"

    # 4. Production waiver
    assert build_document_directory_path(p, "production_waiver", "BVRW-4444", "pdf") == "4_SÉCURITÉ/3_DÉCHARGE_PRODUCTION/BVRW-4444/1_DÉCHARGE"
    assert build_document_directory_path(p, "production_waiver", "BVRW-4444", "insurance") == "4_SÉCURITÉ/3_DÉCHARGE_PRODUCTION/BVRW-4444/2_ATTESTATION_ASSURANCE"

    # 5. Incident (top-level subfolder 6_INCIDENTS)
    assert build_document_directory_path(p, "incident", "BVIC-5555", "pdf") == "6_INCIDENTS/BVIC-5555"
    assert build_document_directory_path(p, "incident", "BVIC-5555", "photo") == "6_INCIDENTS/BVIC-5555/PHOTOS"
    assert build_document_directory_path(p, "incident", "BVIC-5555", "document") == "6_INCIDENTS/BVIC-5555/DOCUMENTS"
