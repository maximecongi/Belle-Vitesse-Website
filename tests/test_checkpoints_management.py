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

        # Test route standard sans slash
        resp = self.client.get("/admin/checkpoints")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("Points de Contr", html)
        self.assertIn("Pression des pneus", html)
        self.assertIn("Matrice Flotte", html)

        # Test tolérance au slash terminal (évite l'erreur 404)
        resp_slash = self.client.get("/admin/checkpoints/")
        self.assertEqual(resp_slash.status_code, 200)

        # Test alias singulier /admin/checkpoint
        resp_singular = self.client.get("/admin/checkpoint")
        self.assertEqual(resp_singular.status_code, 200)

        # Test réponse JSON via en-tête Accept
        resp_json = self.client.get("/admin/checkpoints", headers={"Accept": "application/json"})
        self.assertEqual(resp_json.status_code, 200)
        self.assertTrue(resp_json.is_json)
        data = resp_json.get_json()
        self.assertTrue(data.get("success"))
        self.assertGreater(data.get("stats", {}).get("total", 0), 0)

        # Test endpoint API /admin/api/checkpoints
        resp_api = self.client.get("/admin/api/checkpoints")
        self.assertEqual(resp_api.status_code, 200)
        self.assertTrue(resp_api.is_json)

        # Test alias protocole /admin/check-vehicles
        resp_proto = self.client.get("/admin/check-vehicles")
        self.assertEqual(resp_proto.status_code, 200)

        # Test génération PDF protocole continu
        resp_pdf = self.client.get("/admin/tools/check-vehicles/pdf")
        self.assertEqual(resp_pdf.status_code, 200)
        self.assertEqual(resp_pdf.headers.get("Content-Type"), "application/pdf")
        self.assertTrue(resp_pdf.data.startswith(b"%PDF"))
        self.assertGreater(len(resp_pdf.data), 200)

        resp_pdf_alias = self.client.get("/admin/check-vehicles/pdf")
        self.assertEqual(resp_pdf_alias.status_code, 200)
        self.assertEqual(resp_pdf_alias.headers.get("Content-Type"), "application/pdf")
        self.assertTrue(resp_pdf_alias.data.startswith(b"%PDF"))

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
            updated_cp = db.session.get(CheckpointDefinition, cp_id)
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
            first_cp = db.session.get(CheckpointDefinition, reversed_ids[0])
            last_cp = db.session.get(CheckpointDefinition, reversed_ids[-1])
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
            deleted = db.session.get(CheckpointDefinition, new_id)
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

    @patch("services.admin.vehicle_config.get_vehicles")
    def test_get_protocol_data_matrix(self, mock_get_vehicles):
        mock_get_vehicles.return_value = [
            {"id": "recCar1", "fields": {"name": "eCar Proto"}},
            {"id": "recTrike1", "fields": {"name": "eTrike 360"}},
            {"id": "recBike1", "fields": {"name": "eRider Street"}},
        ]
        with self.app.app_context():
            ensure_default_checkpoints()
            from services.admin.vehicle_config import get_protocol_data
            data = get_protocol_data()

            self.assertIn("columns", data)
            self.assertIn("categories", data)
            self.assertEqual(len(data["columns"]), 3)
            col_keys = [c["key"] for c in data["columns"]]
            self.assertEqual(col_keys, ["etrike", "ebike", "ecar"])

            cat_names = [c["name"] for c in data["categories"]]
            self.assertIn("Sécurité", cat_names)
            self.assertIn("Équipements", cat_names)

            # Vérifier que chaque point contient l'état pour les 3 types de véhicules
            sec_group = next(c for c in data["categories"] if c["name"] == "Sécurité")
            self.assertGreater(len(sec_group["checkpoints"]), 0)
            tires_cp = next(cp for cp in sec_group["checkpoints"] if cp["key"] == "tires")
            self.assertTrue(tires_cp["vehicles"]["etrike"])
            self.assertTrue(tires_cp["vehicles"]["ebike"])
            self.assertTrue(tires_cp["vehicles"]["ecar"])

    @patch("services.admin.vehicle_config.get_vehicles")
    def test_admin_check_vehicles_and_pdf_generation(self, mock_get_vehicles):
        mock_get_vehicles.return_value = [
            {"id": "recCar1", "fields": {"name": "eCar Proto"}},
            {"id": "recTrike1", "fields": {"name": "eTrike 360"}},
            {"id": "recBike1", "fields": {"name": "eRider Street"}},
        ]
        self._login_as("administrator")

        # 1. Vérification de la page HTML
        resp = self.client.get("/admin/tools/check-vehicles")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("Contrôle Technique Véhicules", html)
        self.assertIn("/admin/tools/check-vehicles/pdf", html)
        self.assertIn("eTrike 360 / eTrike", html)
        self.assertIn("Pression des pneus", html)
        # Vérification qu'aucun script inline n'est présent
        self.assertNotIn("<script>", html)
        self.assertNotIn("lucide.createIcons()", html)

        # Vérification de l'alias /admin/check-vehicles
        resp_alias = self.client.get("/admin/check-vehicles")
        self.assertEqual(resp_alias.status_code, 200)

        # 2. Vérification de l'endpoint de téléchargement PDF dynamique
        resp_pdf = self.client.get("/admin/tools/check-vehicles/pdf")
        self.assertEqual(resp_pdf.status_code, 200)
        self.assertEqual(resp_pdf.content_type, "application/pdf")
        self.assertTrue(resp_pdf.data.startswith(b"%PDF"))

        # Vérification de l'alias PDF /admin/check-vehicles/pdf
        resp_pdf_alias = self.client.get("/admin/check-vehicles/pdf")
        self.assertEqual(resp_pdf_alias.status_code, 200)
        self.assertEqual(resp_pdf_alias.content_type, "application/pdf")

    @patch("services.admin.vehicle_config.get_vehicles")
    def test_dynamic_clustering_by_checkpoints_signature(self, mock_get_vehicles):
        """Vérifie le regroupement automatique des véhicules par signature identique (Option D)."""
        mock_get_vehicles.return_value = [
            {"id": "v_trike_1", "fields": {"name": "eTrike 360", "status": "Online", "order": 4}},
            {"id": "v_trike_2", "fields": {"name": "eTrike", "status": "Online", "order": 5}},
            {"id": "v_car", "fields": {"name": "eCar", "status": "Online", "order": 2}},
            {"id": "v_segway", "fields": {"name": "Segway x2", "status": "Online", "order": 6}},
            {"id": "v_empty", "fields": {"name": "Jackal Rickshaw", "status": "Online", "order": 8}},
            {"id": "test_car", "fields": {"name": "Mercedes Test", "status": "Online"}},
        ]
        with self.app.app_context():
            ensure_default_checkpoints()
            from models import CheckpointDefinition, db
            from services.admin.vehicle_config import get_protocol_data
            from sqlalchemy.orm.attributes import flag_modified
            from extensions import cache

            # Assigner explicitement des configurations :
            # v_trike_1 et v_trike_2 : tires + brakes (signature identique)
            # v_car : tires + brakes + ceinture_securite (signature distincte)
            # v_segway : tires (signature distincte)
            # v_empty : aucun point actif
            # test_car : ignoré car préfixe test
            for cp in CheckpointDefinition.query.all():
                overrides = {
                    "v_trike_1": {"enabled": cp.key in ("tires", "brakes")},
                    "v_trike_2": {"enabled": cp.key in ("tires", "brakes")},
                    "v_car": {"enabled": cp.key in ("tires", "brakes", "ceinture_securite")},
                    "v_segway": {"enabled": cp.key == "tires"},
                    "v_empty": {"enabled": False},
                    "test_car": {"enabled": True},
                }
                cp.vehicle_overrides = overrides
                flag_modified(cp, "vehicle_overrides")
            db.session.commit()
            cache.clear()

            data = get_protocol_data()
            cols = data["columns"]

            # 3 colonnes actives : (Trikes regroupés), (eCar), (Segway)
            self.assertEqual(len(cols), 3)

            col_keys = [c["key"] for c in cols]
            self.assertIn("etrike", col_keys)
            self.assertIn("ecar", col_keys)
            self.assertIn("segway", col_keys)

            trike_col = next(c for c in cols if c["key"] == "etrike")
            self.assertEqual(set(trike_col["vehicle_ids"]), {"v_trike_1", "v_trike_2"})
            self.assertIn("eTrike 360", trike_col["name"])

            car_col = next(c for c in cols if c["key"] == "ecar")
            self.assertEqual(car_col["vehicle_ids"], ["v_car"])

            segway_col = next(c for c in cols if c["key"] == "segway")
            self.assertEqual(segway_col["vehicle_ids"], ["v_segway"])

            # Vérifier que le véhicule vide et le véhicule test sont exclus de tous les groupes
            all_grouped_ids = [vid for c in cols for vid in c["vehicle_ids"]]
            self.assertNotIn("v_empty", all_grouped_ids)
            self.assertNotIn("test_car", all_grouped_ids)


if __name__ == "__main__":
    unittest.main()

