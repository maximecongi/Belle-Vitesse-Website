import os
import sys
import unittest
from unittest.mock import MagicMock

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- Mocking WeasyPrint to avoid OSError on environments without GObject ---
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from app import create_app
from models import db, SalaryRate, PreQuote, Production

class PreQuoteSalaryTest(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        os.environ["WTF_CSRF_ENABLED"] = "False"
        os.environ["USE_SSH_TUNNEL"] = "false"

        self.app = create_app()
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_all_rates_api(self):
        # Insert a SalaryRate
        with self.app.app_context():
            rate = SalaryRate(
                position="Cadreur",
                annexe="Annexe 1",
                group_name="Image",
                base_hourly=50.0,
                invoice_10h=600.0,
                invoice_8h=480.0,
                inter_10h=350.0,
                inter_8h=280.0,
                inter_hs=45.0,
                invoice_hs=80.0,
                display_order=1
            )
            db.session.add(rate)
            db.session.commit()

        # Set session auth
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_role"] = "administrator"

        # Call the all-rates API
        response = self.client.get("/admin/api/pre-quotes/all-rates")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        # Verify Cadreur is in the rates and includes "Annexe 1" in its name, and contains rates dictionary
        cadreur_rate = next((item for item in data if item["category"] == "salary" and "Cadreur" in item["name"]), None)
        self.assertIsNotNone(cadreur_rate)
        self.assertEqual(cadreur_rate["name"], "Cadreur (Annexe 1)")
        self.assertEqual(cadreur_rate["position"], "Cadreur")
        self.assertEqual(cadreur_rate["annexe"], "Annexe 1")
        self.assertIn("rates", cadreur_rate)
        self.assertEqual(cadreur_rate["rates"]["10h"], 350.0)
        self.assertEqual(cadreur_rate["rates"]["8h"], 280.0)

    def test_edit_enrichment(self):
        # Insert a SalaryRate
        with self.app.app_context():
            rate = SalaryRate(
                position="Cadreur",
                annexe="Annexe 1",
                group_name="Image",
                base_hourly=50.0,
                invoice_10h=600.0,
                invoice_8h=480.0,
                inter_10h=350.0,
                inter_8h=280.0,
                inter_hs=45.0,
                invoice_hs=80.0,
                display_order=1
            )
            db.session.add(rate)
            
            prod = Production(name="Prod Test")
            db.session.add(prod)
            db.session.commit()
            
            # Create a quote with a legacy salary pre-quote item (no rates / no salary_rate_type)
            quote = PreQuote(
                reference="DP-2026-999",
                production_id=prod.id,
                project_name="Test Project",
                prestations=[
                    {
                        "category": "salary",
                        "description": "Cadreur (Annexe 1)",
                        "quantity": 2,
                        "unit": "jour(s)",
                        "unit_price": 480.0,
                        "total": 960.0
                    }
                ],
                total_ht=960.0,
                total_ttc=1152.0
            )
            db.session.add(quote)
            db.session.commit()
            quote_id = quote.id

        # Set session auth
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_role"] = "administrator"

        # Load the edit page to trigger the enrichment code
        response = self.client.get(f"/admin/pre-quotes/{quote_id}/edit")
        self.assertEqual(response.status_code, 200)
        # Verify the HTML rendered includes the select dropdown and selected value for invoice_8h
        html = response.data.decode("utf-8")
        self.assertIn("salary-rate-select", html)
        self.assertIn('option value="invoice_8h" selected', html)

    def test_mad_pricing_calculation(self):
        from services.admin.pre_quote import calculate_totals
        prestations = [
            {
                "category": "equipment",
                "description": "Caméra",
                "quantity": 1.0,
                "unit": "jour(s)",
                "unit_price": 500.0,
                "discount_rate": 0.0,
                "is_mad": True
            },
            {
                "category": "equipment",
                "description": "Objectif",
                "quantity": 1.0,
                "unit": "jour(s)",
                "unit_price": 200.0,
                "discount_rate": 10.0,
                "is_mad": False
            }
        ]
        totals = calculate_totals(prestations, tva_rate=20.00, insurance_rate=10.00)
        # Check that Caméra has discount_rate = 100
        self.assertEqual(prestations[0]["discount_rate"], 100.0)
        # Check that Caméra total is 0.0
        self.assertEqual(prestations[0]["total"], 0.0)
        # Objectif total should be 200 * 0.9 = 180.0
        self.assertEqual(prestations[1]["total"], 180.0)
        # Base rental should be 180.0
        self.assertEqual(float(totals["total_rental_ht"]), 180.0)

    def test_grouped_prestations_pdf(self):
        from services.admin.pre_quote import get_pre_quote_pdf
        with self.app.app_context():
            prod = Production(name="Prod Test PDF")
            db.session.add(prod)
            db.session.commit()
            
            quote = PreQuote(
                reference="DP-2026-888",
                production_id=prod.id,
                project_name="Test PDF Grouping",
                prestations=[
                    {
                        "category": "salary",
                        "description": "Cadreur",
                        "quantity": 1,
                        "unit": "jour(s)",
                        "unit_price": 300.0,
                        "total": 300.0
                    },
                    {
                        "category": "equipment",
                        "description": "Caméra",
                        "quantity": 1,
                        "unit": "jour(s)",
                        "unit_price": 500.0,
                        "total": 500.0
                    }
                ],
                total_ht=800.0,
                total_ttc=960.0
            )
            db.session.add(quote)
            db.session.commit()
            quote_id = quote.id

        # Since weasyprint is mocked, get_pre_quote_pdf should call render_template and return mock bytes
        # Let's verify it compiles without errors
        try:
            pdf_bytes = get_pre_quote_pdf(quote_id)
            self.assertIsNotNone(pdf_bytes)
        except Exception as e:
            self.fail(f"get_pre_quote_pdf raised an exception: {e}")

    def test_intermittent_salaries_exclusion_and_annex(self):
        from services.admin.pre_quote import calculate_totals, get_pre_quote_pdf
        
        prestations = [
            {
                "category": "salary",
                "annexe": "Facture",
                "description": "Cadreur (Facture)",
                "quantity": 1.0,
                "unit": "jour(s)",
                "unit_price": 500.0,
                "discount_rate": 0.0,
                "employee_name": "Jean Dupont"
            },
            {
                "category": "salary",
                "annexe": "Annexe 1",
                "description": "Assistant Caméra (Annexe 1)",
                "quantity": 2.0,
                "unit": "jour(s)",
                "unit_price": 300.0,
                "discount_rate": 0.0,
                "employee_name": "Alice Martin"
            }
        ]
        
        totals = calculate_totals(prestations, tva_rate=20.00, insurance_rate=10.00)
        # All salary items are excluded from HT total
        # So the total rental HT should be 0.0!
        self.assertEqual(float(totals["total_rental_ht"]), 0.0)
        
        with self.app.app_context():
            prod = Production(name="Prod Test Intermittent")
            db.session.add(prod)
            db.session.commit()
            
            quote = PreQuote(
                reference="DP-2026-777",
                production_id=prod.id,
                project_name="Test Intermittent PDF",
                prestations=prestations,
                total_ht=0.0,
                total_ttc=0.0
            )
            db.session.add(quote)
            db.session.commit()
            quote_id = quote.id
            
        try:
            pdf_bytes = get_pre_quote_pdf(quote_id)
            self.assertIsNotNone(pdf_bytes)
        except Exception as e:
            self.fail(f"get_pre_quote_pdf raised an exception: {e}")

if __name__ == "__main__":
    unittest.main()
