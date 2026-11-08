"""
Tests de la fiche technique publique véhicule (page mobile, PDF, liens croisés sécurité).
"""

from tests.base import BaseTestCase
from models import db
from models.catalog import Config, Vehicle


class VehicleSheetTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.vehicle_id = "recTestSheet"
        self.vehicle_slug = "ecar-test"

        with self.app.app_context():
            db.session.add(Vehicle(
                id=self.vehicle_id,
                daily_rate=987,
                fields={
                    "name": "eCar Test",
                    "slug": self.vehicle_slug,
                    "unique_id": "ECAR-TEST",
                    "brand": "Renault",
                    "model": "Twizy",
                    "max_speed": 80,
                    "passengers": 3,
                    "battery_life": "6",
                    "weight": 673,
                    "length": 1570, "width": 1690, "height": 1460,
                    "daily_rate": 987,
                    "setups": ["Handheld", "Steadicam"],
                    "description_fr": "Véhicule caméra électrique.",
                    "description_en": "Electric camera vehicle.",
                    "powerquote_fr": "Tous les angles.",
                    "powerquote_en": "Every setups.",
                },
            ))
            db.session.add(Config(
                id="recCfgCrane",
                fields={
                    "name": "Crane", "name_fr": "Grue", "name_en": "Crane",
                    "type": "Crane", "order": 1, "vehicle": [self.vehicle_id],
                },
            ))
            db.session.add(Config(
                id="recCfgSeat",
                fields={
                    "name": "Seats Front & Side", "name_fr": "Sièges avant et côté",
                    "name_en": "Seats Front & Side", "type": "Operator", "order": 1,
                    "vehicle": [self.vehicle_id],
                },
            ))
            db.session.commit()

    def test_public_sheet_renders_specs_and_configs(self):
        response = self.client.get(f"/vehicle-sheet/v/{self.vehicle_slug}")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")

        self.assertIn("eCar Test", html)
        self.assertIn("ECAR-TEST", html)
        self.assertIn("Renault Twizy", html)
        self.assertIn("Vitesse max", html)
        self.assertIn("673 kg", html)
        self.assertIn("L 1570 × W 1690 × H 1460 mm", html)
        self.assertIn("Steadicam", html)
        self.assertIn("/static/imgs/icons/handheld.svg", html)
        self.assertIn("pdf-header-title-row", html)
        self.assertIn("Véhicule caméra électrique.", html)
        self.assertIn("Electric camera vehicle.", html)
        # Configurations groupées et traduites
        self.assertIn("Grue", html)
        self.assertIn("Sièges avant et côté", html)
        self.assertLess(html.index("Opérateur"), html.index("Grue"))
        # Liens : sécurité, PDF
        self.assertIn(f"/safety-rules/v/{self.vehicle_slug}", html)
        self.assertIn(f"/vehicle-sheet/v/{self.vehicle_slug}/pdf", html)

    def test_public_sheet_does_not_expose_price(self):
        html = self.client.get(f"/vehicle-sheet/v/{self.vehicle_id}").data.decode("utf-8")
        self.assertNotIn("987", html)

    def test_public_sheet_404_for_unknown(self):
        response = self.client.get("/vehicle-sheet/v/inexistant_999")
        self.assertEqual(response.status_code, 404)

    def test_pdf_endpoint_returns_pdf(self):
        for lang in ("fr", "en"):
            response = self.client.get(
                f"/vehicle-sheet/v/{self.vehicle_slug}/pdf?lang={lang}&download=1"
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["Content-Type"], "application/pdf")
            self.assertIn("attachment", response.headers["Content-Disposition"])
            self.assertIn(f"-{lang.upper()}.pdf", response.headers["Content-Disposition"])
            self.assertTrue(response.data.startswith(b"%PDF"))

    def test_pdf_template_is_monolingual_without_price(self):
        from flask import render_template
        from routes.public.vehicle_sheet import _build_sheet_context

        with self.app.test_request_context("/"):
            ctx = _build_sheet_context(self.vehicle_slug)
            html_en = render_template("pdf/vehicle_sheet.html", lang="en", fr=False, qr_base64="", **ctx)
            html_fr = render_template("pdf/vehicle_sheet.html", lang="fr", fr=True, qr_base64="", **ctx)

        self.assertIn("Technical specifications", html_en)
        self.assertNotIn("Caractéristiques techniques", html_en)
        self.assertIn("Caractéristiques techniques", html_fr)
        self.assertIn("Grue", html_fr)
        self.assertNotIn("987", html_fr)
        # En-tête officiel commun aux documents ERP + icônes de setups du site
        self.assertIn("pdf-header-title-row", html_fr)
        self.assertIn("pdf-header-date-row", html_fr)
        self.assertIn("/static/imgs/icons/steadicam.svg", html_fr)

    def test_safety_rules_page_links_to_sheet(self):
        html = self.client.get(f"/safety-rules/v/{self.vehicle_slug}").data.decode("utf-8")
        self.assertIn(f"/vehicle-sheet/v/{self.vehicle_slug}", html)
