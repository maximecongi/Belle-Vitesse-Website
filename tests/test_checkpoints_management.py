import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock weasyprint if not present
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from app import create_app
from extensions import cache
from models import CheckpointDefinition, User, VehicleCheckpointConfig, db
from services.admin.vehicle_config import (
    ensure_default_checkpoints,
    get_all_checkpoints,
    get_checkpoint_by_id,
    save_vehicle_checkpoint_config,
    update_checkpoint,
)
from utils.checkpoints import get_checkpoints_for_vehicle


class CheckpointsManagementTest(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        os.environ["WTF_CSRF_ENABLED"] = "False"
        os.environ["USE_SSH_TUNNEL"] = "false"

        self.app = create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            cache.clear()

    def tearDown(self):
        with self.app.app_context():
            cache.clear()
            db.session.remove()
            db.drop_all()

    def _login_as(self, role="administrator"):
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_user_firstname"] = "Admin"
            sess["admin_user_lastname"] = "Test"
            sess["admin_user_role"] = role

    @patch("services.admin.vehicle_config.get_vehicles")
    def test_auto_seeding_checkpoints(self, mock_get_vehicles):
        mock_get_vehicles.return_value = [
            {"id": "recCar1", "fields": {"name": "eCar Proto"}},
            {"id": "recTrike1", "fields": {"name": "eTrike 360"}},
        ]
        with self.app.app_context():
            ensure_default_checkpoints()
            cps = CheckpointDefinition.query.all()
            self.assertGreater(len(cps), 10)

            tires_cp = CheckpointDefinition.query.filter_by(key="tires").first()
            self.assertIsNotNone(tires_cp)
            self.assertEqual(tires_cp.label, "Pression des pneus")
            self.assertIn("recCar1", tires_cp.vehicle_overrides)
            self.assertEqual(tires_cp.vehicle_overrides["recCar1"]["indication"], "eCar : 2 bar")

    @patch("services.admin.vehicle_config.get_vehicles")
    def test_admin_checkpoints_list_view(self, mock_get_vehicles):
        mock_get_vehicles.return_value = [
            {"id": "recCar1", "fields": {"name": "eCar Proto"}},
        ]
        self._login_as("administrator")

        resp = self.client.get("/admin/checkpoints")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("Points de Contr", html)
        self.assertIn("Pression des pneus", html)
        self.assertIn("Matrice Flotte", html)

    @patch("services.admin.vehicle_config.get_vehicles")
    def test_admin_checkpoint_edit_get_and_post(self, mock_get_vehicles):
        mock_get_vehicles.return_value = [
            {"id": "recCar1", "fields": {"name": "eCar Proto"}},
            {"id": "recBike1", "fields": {"name": "eBike Stealth"}},
        ]
        self._login_as("administrator")

        with self.app.app_context():
            ensure_default_checkpoints()
            cp = CheckpointDefinition.query.filter_by(key="tires").first()
            cp_id = cp.id

        # GET edit page
        resp_get = self.client.get(f"/admin/checkpoints/{cp_id}/edit")
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn("Modifier", resp_get.data.decode("utf-8"))

        # POST update: change label, category, default indication, and vehicle indication
        form_data = {
            "label": "Pression pneumatiques haute performance",
            "category": "Sécurité",
            "default_detail": "Contrôle visuel systématique",
            "vehicle_enabled_recCar1": "1",
            "vehicle_indication_recCar1": "2.4 bar AV / 2.6 bar AR",
            # recBike1 not enabled
            "vehicle_indication_recBike1": "",
        }
        resp_post = self.client.post(f"/admin/checkpoints/{cp_id}/edit", data=form_data, follow_redirects=True)
        self.assertEqual(resp_post.status_code, 200)
        self.assertIn("Point de contrôle mis à jour avec succès", resp_post.data.decode("utf-8"))

        with self.app.app_context():
            updated_cp = CheckpointDefinition.query.get(cp_id)
            self.assertEqual(updated_cp.label, "Pression pneumatiques haute performance")
            self.assertEqual(updated_cp.default_detail, "Contrôle visuel systématique")
            self.assertTrue(updated_cp.is_vehicle_enabled("recCar1"))
            self.assertFalse(updated_cp.is_vehicle_enabled("recBike1"))
            self.assertEqual(updated_cp.get_indication_for_vehicle("recCar1"), "2.4 bar AV / 2.6 bar AR")
            self.assertEqual(updated_cp.get_indication_for_vehicle("recBike1"), "Contrôle visuel systématique")

    @patch("utils.database.get_vehicles")
    @patch("services.admin.vehicle_config.get_vehicles")
    def test_utils_get_checkpoints_for_vehicle_with_custom_definition(
        self, mock_get_vehicles_service, mock_get_vehicles_utils
    ):
        vehicles_mock = [
            {"id": "recCar1", "fields": {"name": "eCar Proto"}},
            {"id": "recBike1", "fields": {"name": "eBike Stealth"}},
        ]
        mock_get_vehicles_service.return_value = vehicles_mock
        mock_get_vehicles_utils.return_value = vehicles_mock

        with self.app.app_context():
            ensure_default_checkpoints()
            cp = CheckpointDefinition.query.filter_by(key="tires").first()

            # Custom update
            update_checkpoint(
                cp.id,
                {
                    "label": "Pression pneumatiques sur-mesure",
                    "category": "Sécurité",
                    "default_detail": "Voir manuel",
                    "vehicle_enabled_recCar1": "1",
                    "vehicle_indication_recCar1": "2.3 bar",
                    "vehicle_enabled_recBike1": "",
                },
            )

            # Checkpoints for recCar1 should contain custom label and indication
            car_cps = get_checkpoints_for_vehicle("recCar1")
            tires_found = [c for c in car_cps if c["key"] == "tires"]
            self.assertEqual(len(tires_found), 1)
            self.assertEqual(tires_found[0]["label"], "Pression pneumatiques sur-mesure")
            self.assertEqual(tires_found[0]["detail"], "2.3 bar")

            # Checkpoints for recBike1 should NOT contain tires because it is disabled
            bike_cps = get_checkpoints_for_vehicle("recBike1")
            bike_tires = [c for c in bike_cps if c["key"] == "tires"]
            self.assertEqual(len(bike_tires), 0)

    @patch("services.admin.vehicle_config.get_vehicles")
    def test_matrix_config_sync(self, mock_get_vehicles):
        mock_get_vehicles.return_value = [
            {"id": "recCar1", "fields": {"name": "eCar Proto"}},
        ]
        with self.app.app_context():
            ensure_default_checkpoints()
            # Save matrix config with only 'brakes' enabled
            save_vehicle_checkpoint_config("recCar1", ["brakes"])

            brakes_cp = CheckpointDefinition.query.filter_by(key="brakes").first()
            tires_cp = CheckpointDefinition.query.filter_by(key="tires").first()

            self.assertTrue(brakes_cp.is_vehicle_enabled("recCar1"))
            self.assertFalse(tires_cp.is_vehicle_enabled("recCar1"))

    @patch("services.admin.vehicle_config.get_vehicles")
    def test_reorder_checkpoints_api(self, mock_get_vehicles):
        self._login_as("administrator")
        mock_get_vehicles.return_value = [
            {"id": "recCar1", "fields": {"name": "eCar Proto"}},
        ]
        with self.app.app_context():
            ensure_default_checkpoints()
            cps = CheckpointDefinition.query.order_by(CheckpointDefinition.id).all()
            ids = [c.id for c in cps]
            reversed_ids = list(reversed(ids))

        # Test API reorder PATCH
        resp = self.client.patch(
            "/admin/api/checkpoints/reorder",
            json={"ids": reversed_ids},
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))

        with self.app.app_context():
            first_cp = CheckpointDefinition.query.get(reversed_ids[0])
            last_cp = CheckpointDefinition.query.get(reversed_ids[-1])
            self.assertEqual(first_cp.order, 1)
            self.assertEqual(last_cp.order, len(reversed_ids))

    @patch("services.admin.vehicle_config.get_vehicles")
    def test_delete_checkpoint_route(self, mock_get_vehicles):
        self._login_as("administrator")
        mock_get_vehicles.return_value = [
            {"id": "recCar1", "fields": {"name": "eCar Proto"}},
        ]
        with self.app.app_context():
            ensure_default_checkpoints()
            from services.admin.vehicle_config import create_checkpoint
            new_cp = create_checkpoint({"label": "Point Temporaire à supprimer", "category": "Sécurité"})
            new_id = new_cp.id

        # POST delete
        resp = self.client.post(f"/admin/checkpoints/{new_id}/delete", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("supprimé avec succès", resp.data.decode("utf-8"))

        with self.app.app_context():
            deleted = CheckpointDefinition.query.get(new_id)
            self.assertIsNone(deleted)

    @patch("services.admin.vehicle_config.get_vehicles")
    def test_category_grouping_order(self, mock_get_vehicles):
        mock_get_vehicles.return_value = [
            {"id": "recCar1", "fields": {"name": "eCar Proto"}},
        ]
        with self.app.app_context():
            ensure_default_checkpoints()
            from services.admin.vehicle_config import create_checkpoint
            # Créer un point sécurité avec un ordre élevé
            new_sec = create_checkpoint({"label": "Nouveau Point Sécurité", "category": "Sécurité", "order": 999})
            cps = get_all_checkpoints()

            # Vérifier que tous les points Sécurité précèdent les points Équipements
            sec_indices = [i for i, c in enumerate(cps) if c["category"] == "Sécurité"]
            eq_indices = [i for i, c in enumerate(cps) if c["category"] == "Équipements"]

            self.assertTrue(len(sec_indices) > 0)
            self.assertTrue(len(eq_indices) > 0)
            self.assertLess(max(sec_indices), min(eq_indices))

            # Vérifier que le nouveau point sécurité est bien dans le groupe sécurité
            new_sec_idx = next(i for i, c in enumerate(cps) if c["id"] == new_sec.id)
            self.assertLess(new_sec_idx, min(eq_indices))


if __name__ == "__main__":
    unittest.main()
