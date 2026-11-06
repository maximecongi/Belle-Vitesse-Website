"""
services/admin/waivers/mock_data.py
Objets et helpers mock pour la prévisualisation en direct et l'ajustement CSS/design
des templates PDF de Conditions Générales de Location (CGL) et Règles de Sécurité (BVSR).
"""

from datetime import date, datetime


class MockProject:
    id = 999
    project_id = "BVPR-DEMO2026"
    name = "Tournage Long Métrage Alpha"
    departure_date = date(2026, 11, 10)
    shoot_start_date = date(2026, 11, 12)
    shoot_end_date = date(2026, 11, 18)
    return_date = date(2026, 11, 20)
    deposit_amount = 5000.0
    quote_number = "BVPR-DEMO2026"
    vehicle_road_legal_statuses = None

    def __init__(self):
        self.vehicle_road_legal_statuses = {}

    def is_vehicle_road_legal(self, vehicle_id: str = "", vehicle_slug: str = "", vehicle_name: str = "") -> bool:
        statuses = self.vehicle_road_legal_statuses or {}
        for k in [str(vehicle_id).strip(), (vehicle_slug or "").lower().strip(), (vehicle_name or "").lower().strip()]:
            if k and k in statuses:
                return bool(statuses[k])
        non_road_keywords = ["erover", "erider", "stark", "polar"]
        slug_l = (vehicle_slug or "").lower()
        name_l = (vehicle_name or "").lower()
        vid_l = str(vehicle_id).lower()
        if any(kw in vid_l or kw in slug_l or kw in name_l for kw in non_road_keywords):
            return False
        return True

    def set_vehicle_road_legal(self, vehicle_id: str, is_road_legal: bool):
        if self.vehicle_road_legal_statuses is None:
            self.vehicle_road_legal_statuses = {}
        vid_str = str(vehicle_id).strip()
        self.vehicle_road_legal_statuses[vid_str] = bool(is_road_legal)
        self.vehicle_road_legal_statuses[vid_str.lower()] = bool(is_road_legal)


class MockCglWaiver:
    id = 999
    waiver_id = "BVRA-DEMO-2026"
    waiver_type = "cgl"
    status = "signed"
    created_at = datetime(2026, 10, 20, 10, 0)
    generated_at = datetime(2026, 10, 20, 10, 30)
    signed_at = datetime(2026, 10, 22, 14, 45)
    signer_ip = "192.168.1.42"
    project = MockProject()
    production_name = "Antiestático Barcelona SL"
    production_representative = "Claire Delmas"
    production_siret = "B66123456"
    production_vat = "ESB66123456"
    production_address = "Carrer de Pujades, 74, 08005 Barcelona, Espagne"
    signer_phone = "+34 6 12 34 56 78"
    signer_email = "claire.delmas@antiestatico.com"
    location_of_use = "Circuit Paul Ricard & Forêt de Rambouillet"
    vehicles = "eRover Polaris Kinetic (BV-ROVER-01), eRider Stark Varg (BV-RIDER-02)"
    production_insurance_company = "Rubini & Associés"
    production_insurance_policy = "POL-78945612"

    sign_data = {
        "legal_form": "SL",
        "legal_country": "Espagne",
        "representative_role": "Directrice de Production",
        "signature_city": "Barcelone",
        "order_ref": "BVBC-202611-0042",
        "insurance_company": "Rubini & Associés",
        "insurance_policy": "POL-78945612",
    }

    @property
    def display_project_name(self):
        return self.project.name

    @property
    def display_production_name(self):
        return self.production_name

    @property
    def display_legal_form_only(self):
        return "SL"

    @property
    def display_legal_country(self):
        return "Espagne"

    @property
    def display_legal_form(self):
        return "SL (Espagne)"

    @property
    def display_representative_role(self):
        return "Directrice de Production"

    @property
    def display_signature_city(self):
        return "Barcelone"

    @property
    def display_order_ref(self):
        return "BVBC-202611-0042"

    @property
    def display_shooting_dates(self):
        return "Du 12/11/2026 au 18/11/2026"

    @property
    def display_shooting_locations(self):
        return self.location_of_use

    @property
    def signature_data_uri(self):
        # Tracé signature manuscrite SVG transparent
        return "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='80' viewBox='0 0 240 80'><path d='M20,50 Q60,10 90,45 T160,35 T220,55' fill='none' stroke='%230f172a' stroke-width='2.5' stroke-linecap='round'/></svg>"

    @property
    def bv_signature_data_uri(self):
        return "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='80' viewBox='0 0 240 80'><path d='M30,45 Q70,20 110,50 T170,25 T220,40' fill='none' stroke='%2315803d' stroke-width='2.5' stroke-linecap='round'/></svg>"


class MockSafetyRulesWaiver:
    id = 998
    waiver_id = "BVSR-DEMO-2026"
    waiver_type = "safety_rules"
    status = "signed"
    created_at = datetime(2026, 10, 20, 10, 0)
    generated_at = datetime(2026, 10, 20, 10, 30)
    signed_at = datetime(2026, 10, 22, 15, 30)
    bv_signed_at = datetime(2026, 10, 22, 16, 0)
    signer_ip = "192.168.1.42"
    project = MockProject()

    signer_role = "pilot"
    signer_role_custom = ""
    signer_first_name = "Alexandre"
    signer_last_name = "Mercier"
    signer_email = "alexandre.mercier@stunt-pro.com"
    signer_phone = "+33 6 98 76 54 32"
    signer_company = "Stunt Precision Drivers"
    safety_technicians = "Maxime Perrard, Ewen Gicquel"

    vehicles = "eRover Polaris Kinetic, eRider Stark Varg"
    vehicles_details = [
        {"name": "eRover (Polaris Kinetic)", "slug": "erover", "unique_id": "BV-ROVER-01"},
        {"name": "eRider (Stark Varg)", "slug": "erider", "unique_id": "BV-RIDER-02"},
    ]

    all_road_legal = False

    def __init__(self, all_road_legal: bool = False):
        self.project = MockProject()
        self.all_road_legal = all_road_legal
        if all_road_legal:
            for v in self.vehicles_details:
                self.project.set_vehicle_road_legal(v.get("slug", ""), True)
                self.project.set_vehicle_road_legal(v.get("name", ""), True)

    @property
    def non_road_legal_vehicles(self):
        if getattr(self, "all_road_legal", False):
            return []
        p = getattr(self, "project", None)
        if p and hasattr(p, "is_vehicle_road_legal"):
            return [
                v for v in self.vehicles_details
                if not p.is_vehicle_road_legal(v.get("id", ""), v.get("slug", ""), v.get("name", ""))
            ]
        non_road_keywords = ["erover", "erider", "stark", "polar"]
        return [
            v for v in self.vehicles_details
            if any(k in (v.get("slug") or "").lower() or k in (v.get("name") or "").lower() for k in non_road_keywords)
        ]
    helmets_inventory = {
        "S": 2,
        "M": 4,
        "L": 4,
        "XL": 2,
    }

    bv_signer_name = "Maxime Perrard (Supervision Technique Belle Vitesse)"
    hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    @property
    def signer_name(self):
        return f"{self.signer_first_name} {self.signer_last_name}"

    @property
    def signer_role_label(self):
        return "Pilote / Conducteur de Précision"

    @property
    def display_project_name(self):
        return self.project.name

    @property
    def display_production_name(self):
        return "Antiestático Barcelona SL"

    @property
    def display_shooting_dates(self):
        return "Du 12/11/2026 au 18/11/2026"

    @property
    def signature_data_uri(self):
        return "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='80' viewBox='0 0 240 80'><path d='M25,55 Q55,15 85,40 T150,30 T210,60' fill='none' stroke='%231e3a8a' stroke-width='2.5' stroke-linecap='round'/></svg>"

    @property
    def bv_signature_data_uri(self):
        return "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='80' viewBox='0 0 240 80'><path d='M30,45 Q70,20 110,50 T170,25 T220,40' fill='none' stroke='%2315803d' stroke-width='2.5' stroke-linecap='round'/></svg>"


class MockPilotWaiver:
    """Mock représentatif fidèle d'une Attestation Pilote (BVPA / Annexe 3 aux CGL)."""
    id = 997
    waiver_id = "BVPA-DEMO-2026"
    waiver_type = "pilot_waiver"
    status = "signed"
    created_at = datetime(2026, 10, 20, 10, 0)
    generated_at = datetime(2026, 10, 20, 10, 30)
    signed_at = datetime(2026, 10, 22, 15, 30)
    signer_ip = "192.168.1.42"
    project = MockProject()

    signer_role = "pilot"
    signer_role_custom = ""
    signer_first_name = "Alexandre"
    signer_last_name = "Mercier"
    signer_email = "alexandre.mercier@stunt-pro.com"
    signer_phone = "+33 6 98 76 54 32"
    signer_company = "Stunt Precision Drivers"

    vehicles = "eCar, eBike, Titan LT"
    vehicles_details = [
        {
            "name": "eCar",
            "slug": "ecar",
            "unique_id": "BV-ECAR-01",
            "checkout_doc_id": "BVCO-ECAR-01",
            "thumbnail": "/static/imgs/vehicles/ecar-thumbnail.png",
        },
        {
            "name": "eBike",
            "slug": "ebike",
            "unique_id": "BV-EBIKE-02",
            "checkout_doc_id": "BVCO-EBIKE-02",
            "thumbnail": "/static/imgs/vehicles/ebike-thumbnail.png",
        },
        {
            "name": "Titan LT",
            "slug": "titan-lt",
            "unique_id": "BV-TITAN-03",
            "checkout_doc_id": "BVCO-TITAN-03",
            "thumbnail": "/static/imgs/vehicles/titan-lt-thumbnail.png",
        },
    ]

    hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    @property
    def signer_name(self):
        return f"{self.signer_first_name} {self.signer_last_name}"

    @property
    def pilot_function_label(self):
        return "Pilote"

    @property
    def signer_role_label(self):
        return "Pilote Déclarant"

    @property
    def display_project_name(self):
        return self.project.name

    @property
    def display_production_name(self):
        return "Antiestático Barcelona SL"

    @property
    def display_shooting_dates(self):
        return "Du 12/11/2026 au 18/11/2026"

    @property
    def display_shooting_locations(self):
        return "Circuit de Mornay ; Plateau 3 Studios de Bry"

    @property
    def signature_data_uri(self):
        return "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='80' viewBox='0 0 240 80'><path d='M25,55 Q55,15 85,40 T150,30 T210,60' fill='none' stroke='%231e3a8a' stroke-width='2.5' stroke-linecap='round'/></svg>"


class MockRiskAssessmentWaiver:
    """Mock représentatif fidèle d'une Analyse des Risques (Risk Assessment - BVRS)."""
    id = 996
    waiver_id = "BVRS-DEMO-2026"
    waiver_type = "risk_assessment"
    status = "signed"
    created_at = datetime(2026, 10, 20, 10, 0)
    generated_at = datetime(2026, 10, 20, 10, 30)
    signed_at = datetime(2026, 10, 22, 15, 30)
    signer_ip = "192.168.1.42"
    project = MockProject()

    signer_role = "key_grip"
    signer_role_custom = ""
    signer_first_name = "Marc"
    signer_last_name = "Duval"
    signer_email = "marc.duval@grips-france.com"
    signer_phone = "+33 6 12 34 56 78"
    signer_company = "Machinerie Ciné Paris"
    safety_technicians = "Maxime Perrard, Ewen Gicquel"

    vehicles = "eRover Polaris Kinetic, eRider Stark Varg"
    vehicles_details = [
        {"name": "eRover (Polaris Kinetic)", "slug": "erover", "unique_id": "BV-ROVER-01"},
        {"name": "eRider (Stark Varg)", "slug": "erider", "unique_id": "BV-RIDER-02"},
    ]

    all_road_legal = False

    def __init__(self, all_road_legal: bool = False):
        self.project = MockProject()
        self.all_road_legal = all_road_legal
        if all_road_legal:
            for v in self.vehicles_details:
                self.project.set_vehicle_road_legal(v.get("slug", ""), True)
                self.project.set_vehicle_road_legal(v.get("name", ""), True)

    @property
    def non_road_legal_vehicles(self):
        if getattr(self, "all_road_legal", False):
            return []
        p = getattr(self, "project", None)
        if p and hasattr(p, "is_vehicle_road_legal"):
            return [
                v for v in self.vehicles_details
                if not p.is_vehicle_road_legal(v.get("id", ""), v.get("slug", ""), v.get("name", ""))
            ]
        non_road_keywords = ["erover", "erider", "stark", "polar"]
        return [
            v for v in self.vehicles_details
            if any(k in (v.get("slug") or "").lower() or k in (v.get("name") or "").lower() for k in non_road_keywords)
        ]
    sign_data = {
        "signer_name": "Marc Duval",
        "signer_role": "Chef Machiniste",
        "signer_email": "marc.duval@grips-france.com",
    }
    hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    @property
    def signer_name(self):
        return f"{self.signer_first_name} {self.signer_last_name}"

    @property
    def signer_role_label(self):
        return "Chef Machiniste"

    @property
    def display_project_name(self):
        return self.project.name

    @property
    def display_production_name(self):
        return "Antiestático Barcelona SL"

    @property
    def display_shooting_dates(self):
        return "Du 12/11/2026 au 18/11/2026"

    @property
    def display_shooting_locations(self):
        return "Circuit Paul Ricard, Le Castellet, France"

    @property
    def display_shooting_locations_list(self):
        return [{"name": "Circuit Paul Ricard", "address": "Le Castellet, France"}]

    @property
    def display_safety_technicians(self):
        return self.safety_technicians

    @property
    def signature_data_uri(self):
        return "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='80' viewBox='0 0 240 80'><path d='M25,55 Q55,15 85,40 T150,30 T210,60' fill='none' stroke='%231e3a8a' stroke-width='2.5' stroke-linecap='round'/></svg>"


