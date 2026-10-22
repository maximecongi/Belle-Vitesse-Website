"""
Tests unitaires pour le module d'extraction unifiée de bundles kDrive (services/common/kdrive/bundles.py).
"""

import json
from services.common.kdrive.bundles import extract_bundle_file_specs, resolve_entity_info


class DummyCglWaiver:
    def __init__(self):
        self.waiver_id = "BVRA-PROD87654321"
        self.project_id = 10
        self.waiver_type = "cgl"
        self.signed_pdf_path = "2026/09/PROD/PROJ/4_SÉCURITÉ/3_CONTRATS_CGL/BVRA-PROD87654321/doc.pdf"
        self.production_insurance_path = "uploads/prod_insurance.pdf"


class DummySafetyRulesWaiver:
    def __init__(self):
        self.waiver_id = "BVSR-TEST12345678"
        self.project_id = 42
        self.waiver_type = "safety_rules"
        self.signed_pdf_path = "2026/09/PROD/PROJ/4_SÉCURITÉ/2_RÈGLES_SÉCURITÉ/BVSR-TEST12345678/doc.pdf"


class DummyInspection:
    def __init__(self, prefix="BVCO"):
        self.inspection_number = f"{prefix}-INSP99999999"
        self.project_id = 15
        self.signed_pdf_path = "2026/09/PROD/PROJ/4_SÉCURITÉ/1_CHECKOUT/BVCO-INSP99999999/doc.pdf"
        self.interior_photos = json.dumps(["photos/in1.jpg", "photos/in2.jpg"])
        self.exterior_photos = json.dumps(["photos/ex1.jpg"])


class DummyIncident:
    def __init__(self):
        self.incident_number = "BVIC-INCID1111111"
        self.project_id = 20
        self.signed_pdf_path = "2026/09/PROD/PROJ/6_INCIDENTS/BVIC-INCID1111111/doc.pdf"
        self.photos_list = ["photos/dmg1.jpg", "photos/dmg2.jpg"]
        self.documents_list = ["docs/constat.pdf"]


def test_resolve_entity_info():
    sr = DummySafetyRulesWaiver()
    assert resolve_entity_info(sr, "safety_rules") == ("safety_rules", "BVSR-TEST12345678", 42)

    cgl = DummyCglWaiver()
    assert resolve_entity_info(cgl, "cgl") == ("cgl", "BVRA-PROD87654321", 10)

    co = DummyInspection("BVCO")
    assert resolve_entity_info(co, "checkout") == ("checkout", "BVCO-INSP99999999", 15)

    ci = DummyInspection("BVCI")
    assert resolve_entity_info(ci, "checkin") == ("checkin", "BVCI-INSP99999999", 15)

    inc = DummyIncident()
    assert resolve_entity_info(inc, "incident") == ("incident", "BVIC-INCID1111111", 20)


def test_extract_safety_rules_waiver_file_specs():
    sr = DummySafetyRulesWaiver()
    specs = extract_bundle_file_specs(sr, "safety_rules")
    assert len(specs) == 1
    roles = {s["role"]: s["path"] for s in specs}
    assert roles["pdf"] == sr.signed_pdf_path


def test_extract_cgl_waiver_file_specs():
    cgl = DummyCglWaiver()
    specs = extract_bundle_file_specs(cgl, "cgl")
    assert len(specs) == 2
    roles = {s["role"]: s["path"] for s in specs}
    assert roles["pdf"] == cgl.signed_pdf_path
    assert roles["insurance"] == "uploads/prod_insurance.pdf"


def test_extract_inspection_file_specs():
    co = DummyInspection("BVCO")
    specs = extract_bundle_file_specs(co, "checkout")
    assert len(specs) == 4  # 1 PDF + 2 interior + 1 exterior
    assert specs[0]["role"] == "pdf"
    photos = [s["path"] for s in specs if s["role"] == "photo"]
    assert "photos/in1.jpg" in photos
    assert "photos/in2.jpg" in photos
    assert "photos/ex1.jpg" in photos


def test_extract_incident_file_specs():
    inc = DummyIncident()
    specs = extract_bundle_file_specs(
        inc,
        "incident",
        custom_pdf_filename="Custom_INCIDENT.pdf"
    )
    assert len(specs) == 4  # 1 PDF + 2 photos + 1 document
    assert specs[0]["filename"] == "Custom_INCIDENT.pdf"
    photos = [s["path"] for s in specs if s["role"] == "photo"]
    docs = [s["path"] for s in specs if s["role"] == "document"]
    assert len(photos) == 2
    assert len(docs) == 1
    assert "photos/dmg1.jpg" in photos
    assert "docs/constat.pdf" in docs
