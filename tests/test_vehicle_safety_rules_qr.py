"""
Tests unitaires pour la consultation publique des consignes de sécurité des véhicules
et la génération/téléchargement du sticker PDF avec QR Code.
"""

from tests.base import BaseTestCase
from models import User, db
from models.catalog import Vehicle


class VehicleSafetyRulesQRTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.vehicle_id = "recTestSafetyQR"
        self.vehicle_slug = "erover-test"

        with self.app.app_context():
            # Création d'un véhicule de test en base locale
            vehicle = Vehicle(
                id=self.vehicle_id,
                daily_rate=1250,
                fields={
                    "name": "eRover Test",
                    "slug": self.vehicle_slug,
                    "unique_id": "EROVER-TEST",
                    "brand": "Polaris",
                    "model": "Kinetic",
                    "max_speed": 60,
                    "passengers": 3,
                    "daily_rate": 1250,
                },
            )
            db.session.add(vehicle)

            # Création d'un utilisateur admin pour tester la route admin du PDF
            admin = User(
                firstname="Admin",
                lastname="BV",
                mail="admin.safety@example.com",
                role="administrator",
            )
            db.session.add(admin)
            db.session.commit()
            self.admin_id = admin.id

    def test_public_vehicle_safety_rules_view(self):
        """Vérifie que la page publique des règles de sécurité répond 200 et contient les règles et métadonnées."""
        response = self.client.get(f"/safety-rules/v/{self.vehicle_id}")
        self.assertEqual(response.status_code, 200)

        html = response.data.decode("utf-8")
        self.assertIn("eRover Test", html)
        self.assertIn("EROVER-TEST", html)
        self.assertIn("Polaris Kinetic", html)
        self.assertIn("60 km/h", html)
        self.assertIn("3 passagers", html)
        self.assertIn("Règles de Sécurité Véhicules", html)
        self.assertIn("Tous les véhicules", html)
        self.assertIn("Équipements mis à disposition", html)
        self.assertIn("Contact &amp; Assistance Plateau", html)
        self.assertIn("public-doc-footer-subtitle", html)

    def test_public_vehicle_safety_rules_slug_alias(self):
        """Vérifie que la route alias /vehicle/<slug> résout également le véhicule."""
        response = self.client.get(f"/safety-rules/vehicle/{self.vehicle_slug}")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("eRover Test", html)

    def test_public_vehicle_safety_rules_404_for_unknown(self):
        """Vérifie qu'un identifiant inexistant retourne 404."""
        response = self.client.get("/safety-rules/v/inexistant_id_999")
        self.assertEqual(response.status_code, 404)

    def test_admin_vehicle_timeline_contains_qr_code(self):
        """Vérifie que la vue timeline admin contient le QR code et l'URL publique avec le slug."""
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = self.admin_id
            sess["admin_user_role"] = "administrator"

        response = self.client.get(f"/admin/fleet/{self.vehicle_id}")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("btnOpenVehicleQrModal", html)
        self.assertIn("vehicleQrModal", html)
        self.assertIn(f"/safety-rules/v/{self.vehicle_slug}", html)

    def test_admin_vehicle_sticker_pdf_download(self):
        """Vérifie le téléchargement du sticker PDF 100x50mm pour le véhicule."""
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = self.admin_id
            sess["admin_user_role"] = "administrator"

        response = self.client.get(
            f"/admin/fleet/{self.vehicle_id}/safety-rules/sticker-pdf"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "application/pdf")
        self.assertTrue(response.data.startswith(b"%PDF"))
        self.assertIn("attachment", response.headers.get("Content-Disposition", ""))
        self.assertIn(
            "Sticker-Securite", response.headers.get("Content-Disposition", "")
        )
