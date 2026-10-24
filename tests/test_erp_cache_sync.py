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
from models import GripCategory, GripProduct, Head, User, Vehicle, db
from services.admin.pricing import reorder_equipment, update_equipment_daily_rate
from services.admin.projects import get_project_form_context
from services.admin.safety_rules_config import get_all_vehicle_safety_rules_catalog
from services.admin.system import purge_system_cache
from services.admin.users import invalidate_user_cache
from utils.database import init_cache


class ERPCacheSyncTest(unittest.TestCase):
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
            init_cache(cache)
            cache.clear()

    def tearDown(self):
        with self.app.app_context():
            cache.clear()
            db.session.remove()
            db.drop_all()

    def test_pricing_cache_invalidation_vehicle(self):
        """Vérifie que la modification de prix d'un véhicule invalide les caches appropriés."""
        with self.app.app_context():
            v = Vehicle(
                id="veh_test_1",
                daily_rate=1200.0,
                fields={"name": "Tracking EV", "slug": "tracking-ev", "daily_rate": 1200.0}
            )
            db.session.add(v)
            db.session.commit()

            cache.set("vehicles", ["cached_vehicles"])
            cache.set("vehicle_tracking-ev", {"name": "Tracking EV"})

            self.assertIsNotNone(cache.get("vehicles"))
            self.assertIsNotNone(cache.get("vehicle_tracking-ev"))

            # Mise à jour via pricing service
            updated = update_equipment_daily_rate("vehicles", "veh_test_1", 1500)

            self.assertEqual(updated["daily_rate"], 1500.0)
            self.assertIsNone(cache.get("vehicles"))
            self.assertIsNone(cache.get("vehicle_tracking-ev"))

    def test_pricing_cache_invalidation_head(self):
        """Vérifie que la modification de prix d'une tête de caméra invalide ses caches."""
        with self.app.app_context():
            h = Head(
                id="head_test_1",
                daily_rate=800.0,
                fields={"name": "Shotover F1", "slug": "shotover-f1", "daily_rate": 800.0}
            )
            db.session.add(h)
            db.session.commit()

            cache.set("heads", ["cached_heads"])
            cache.set("head_shotover-f1", {"name": "Shotover F1"})

            self.assertIsNotNone(cache.get("heads"))
            self.assertIsNotNone(cache.get("head_shotover-f1"))

            updated = update_equipment_daily_rate("heads", "head_test_1", 950)

            self.assertEqual(updated["daily_rate"], 950.0)
            self.assertIsNone(cache.get("heads"))
            self.assertIsNone(cache.get("head_shotover-f1"))

    def test_pricing_cache_invalidation_grip(self):
        """Vérifie que la mise à jour de Grip products/catégories invalide le cache."""
        with self.app.app_context():
            cat = GripCategory(
                id="cat_grip_1",
                fields={"slug": "tubes-speedrail", "order": 1}
            )
            gp = GripProduct(
                id="gp_test_1",
                daily_rate=50.0,
                fields={"name": "Speedrail 2m", "category": ["cat_grip_1"], "daily_rate": 50.0}
            )
            db.session.add_all([cat, gp])
            db.session.commit()

            cache.set("grip_products", ["cached_products"])
            cache.set("grips_categories", ["cached_categories"])
            cache.set("grips_products_cat_grip_1", ["cached_cat_products"])

            self.assertIsNotNone(cache.get("grip_products"))
            self.assertIsNotNone(cache.get("grips_products_cat_grip_1"))

            updated = update_equipment_daily_rate("grip_products", "gp_test_1", 75)
            self.assertEqual(updated["daily_rate"], 75.0)

            self.assertIsNone(cache.get("grip_products"))
            self.assertIsNone(cache.get("grips_products_cat_grip_1"))

    def test_equipment_reorder_cache_invalidation(self):
        """Vérifie que le réordonnancement d'équipements purge les caches généraux."""
        with self.app.app_context():
            v1 = Vehicle(id="v1", display_order=0, fields={"name": "V1", "slug": "v1"})
            v2 = Vehicle(id="v2", display_order=1, fields={"name": "V2", "slug": "v2"})
            db.session.add_all([v1, v2])
            db.session.commit()

            cache.set("vehicles", ["cached"])
            cache.set("vehicle_v1", {"name": "V1"})
            cache.set("vehicle_v2", {"name": "V2"})

            reorder_equipment("vehicles", ["v2", "v1"])

            self.assertIsNone(cache.get("vehicles"))
            self.assertIsNone(cache.get("vehicle_v1"))
            self.assertIsNone(cache.get("vehicle_v2"))

    def test_user_cache_invalidation_v3_and_roles(self):
        """Vérifie que invalidate_user_cache supprime user_v3:{id} et toutes les variantes de rôles."""
        with self.app.app_context():
            user_id = 42
            cache.set(f"user:{user_id}", {"id": user_id})
            cache.set(f"user_v3:{user_id}", {"id": user_id})
            cache.set(f"user_v3:{user_id}:administrator", {"id": user_id, "role": "administrator"})
            cache.set(f"user_v3:{user_id}:lead_technician", {"id": user_id, "role": "lead_technician"})

            invalidate_user_cache(user_id)

            self.assertIsNone(cache.get(f"user:{user_id}"))
            self.assertIsNone(cache.get(f"user_v3:{user_id}"))
            self.assertIsNone(cache.get(f"user_v3:{user_id}:administrator"))
            self.assertIsNone(cache.get(f"user_v3:{user_id}:lead_technician"))

    def test_system_cache_purge(self):
        """Vérifie que purge_system_cache vide Flask-Caching, Jinja2 et le micro-cache MCP."""
        with self.app.app_context():
            import time
            cache.set("test_data_key", "value_123")
            self.assertIsNotNone(cache.get("test_data_key"))

            from mcp_server.cache import _MCP_TOOL_CACHE
            _MCP_TOOL_CACHE["mcp_test_key"] = (time.time(), "mcp_value")
            self.assertIn("mcp_test_key", _MCP_TOOL_CACHE)

            success = purge_system_cache()
            self.assertTrue(success)

            self.assertIsNone(cache.get("test_data_key"))
            self.assertNotIn("mcp_test_key", _MCP_TOOL_CACHE)

    def test_airtable_sync_clears_cache(self):
        """Vérifie que la synchronisation Airtable flashe le cache applicatif."""
        with self.app.app_context():
            cache.set("vehicles", ["old_data"])
            self.assertIsNotNone(cache.get("vehicles"))

            from services.sync_airtable import run_sync
            dummy_config = {
                "airtable_token": "mock",
                "airtable_base_id": "mock",
                "mysql_host": "mock",
                "mysql_user": "mock",
                "mysql_password": "mock",
                "mysql_database": "mock",
                "use_ssh_tunnel": False,
            }
            with patch("services.sync_airtable.Api"), \
                 patch("services.sync_airtable.get_sqlalchemy_engine") as mock_engine, \
                 patch("services.sync_airtable.sync_table", return_value={"total": 0, "inserted": 0, "updated": 0}), \
                 patch("services.sync_airtable.cleanup_records"):
                mock_conn = MagicMock()
                mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn
                run_sync(dummy_config, sync_db=True, sync_images=False)

            self.assertIsNone(cache.get("vehicles"))

    def test_project_form_context_includes_local_vehicles_and_heads(self):
        """Vérifie que le formulaire projet intègre les véhicules et têtes créés localement."""
        with self.app.app_context():
            v_local = Vehicle(
                id="local_veh_unique",
                daily_rate=1100.0,
                fields={"name": "Véhicule Local Test", "Label": "Véhicule Local Test"}
            )
            h_local = Head(
                id="local_head_unique",
                daily_rate=750.0,
                fields={"name": "Tête Locale Test", "Label": "Tête Locale Test"}
            )
            db.session.add_all([v_local, h_local])
            db.session.commit()

            with patch("services.admin.projects.get_vehicles", return_value=[]), \
                 patch("services.admin.projects.get_heads", return_value=[]):
                ctx = get_project_form_context()
                vehicle_ids = [v["id"] for v in ctx["vehicles"]]
                head_ids = [h["id"] for h in ctx["heads"]]

                self.assertIn("local_veh_unique", vehicle_ids)
                self.assertIn("local_head_unique", head_ids)

    def test_safety_rules_catalog_includes_local_vehicles(self):
        """Vérifie que le catalogue de consignes de sécurité inclut les véhicules SQL locaux."""
        with self.app.app_context():
            v_local = Vehicle(
                id="local_safety_veh",
                fields={"name": "Moto Caméra Locale"}
            )
            db.session.add(v_local)
            db.session.commit()

            with patch("utils.database.get_vehicles", return_value=[]):
                catalog = get_all_vehicle_safety_rules_catalog()
                self.assertIn("local_safety_veh", catalog)
                self.assertEqual(catalog["local_safety_veh"]["name"], "Moto Caméra Locale")


if __name__ == "__main__":
    unittest.main()
