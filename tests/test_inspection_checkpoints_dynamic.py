import os
import sys
import unittest
from datetime import date
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock weasyprint
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from app import create_app
from models import (
    db,
    Project,
    Production,
    User,
    CheckoutVehicle,
    CheckinVehicle,
    CheckpointDefinition,
    InspectionCheckpoint,
)
from services.admin.inspections import (
    apply_inspection_data,
    _format_base_inspection_admin,
    get_inspection_detail_unified,
)
from services.admin.fleet import _detect_inspection_anomalies


class DynamicInspectionCheckpointsTestCase(unittest.TestCase):
    """Tests unitaires pour le modèle relationnel dynamique des checkpoints d'inspection (fresh start)."""

    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        os.environ["WTF_CSRF_ENABLED"] = "False"
        os.environ["USE_SSH_TUNNEL"] = "false"

        self.app = create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            from extensions import cache
            cache.clear()
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            from extensions import cache
            cache.clear()
            db.session.remove()
            db.drop_all()

    def _create_mock_data(self):
        user = User(
            mail="tech.dynamic@example.com",
            firstname="Alexandre",
            lastname="Technicien",
            role="technicien"
        )
        prod = Production(name="Studio Cinéma Test")
        db.session.add_all([user, prod])
        db.session.flush()

        project = Project(
            name="Tournage Pub Électrique",
            production_id=prod.id,
            departure_date=date(2026, 10, 5),
            return_date=date(2026, 10, 8),
            vehicles_to_check="recVeh123"
        )
        db.session.add(project)
        db.session.commit()
        return user, project

    def test_dynamic_checkpoint_creation_and_association(self):
        """Vérifie la persistance d'un point de contrôle personnalisé sans colonne SQL statique."""
        with self.app.app_context():
            user, project = self._create_mock_data()

            # 1. Créer un point de contrôle personnalisé
            custom_def = CheckpointDefinition(
                key="harnais_4_points",
                label="Harnais de sécurité 4 points",
                category="Sécurité",
                type="status",
                default_detail="Contrôler la boucle et le serrage"
            )
            db.session.add(custom_def)
            db.session.commit()

            # 2. Créer un départ
            checkout = CheckoutVehicle(
                project_id=project.id,
                controller_id=user.id,
                inspection_date=date(2026, 10, 5),
                vehicle_id="recVeh123",
                status="in_progress",
                battery_level=100
            )
            checkout.set_checkpoint_status("tires", "ok")
            checkout.set_checkpoint_status("harnais_4_points", "ok", checkpoint_id=custom_def.id)
            db.session.add(checkout)
            db.session.commit()

            # 3. Vérifier en base la relation
            saved_co = CheckoutVehicle.query.get(checkout.id)
            self.assertEqual(len(saved_co.checkpoints), 2)
            statuses = saved_co.checkpoint_statuses
            self.assertEqual(statuses.get("tires"), "ok")
            self.assertEqual(statuses.get("harnais_4_points"), "ok")

            # Vérifier l'association vers CheckpointDefinition
            cp_harnais = next(c for c in saved_co.checkpoints if c.checkpoint_key == "harnais_4_points")
            self.assertEqual(cp_harnais.checkpoint_id, custom_def.id)
            self.assertEqual(cp_harnais.definition.label, "Harnais de sécurité 4 points")

    def test_apply_inspection_data_persists_checkpoints(self):
        """Vérifie que apply_inspection_data enregistre dynamiquement les formulaires."""
        with self.app.app_context():
            user, project = self._create_mock_data()

            checkout = CheckoutVehicle(
                project_id=project.id,
                controller_id=user.id,
                inspection_date=date(2026, 10, 5),
                vehicle_id="recVeh123",
                status="in_progress"
            )
            db.session.add(checkout)
            db.session.commit()

            form_data = {
                "vehicle_id": "recVeh123",
                "tires": "ok",
                "brakes": "critical",
                "battery_level": "95",
                "notes": "Pression avant gauche à vérifier",
                "custom_spotlight": "warning"
            }

            apply_inspection_data(checkout, form_data, is_checkout=True)
            db.session.commit()

            reloaded = CheckoutVehicle.query.get(checkout.id)
            statuses = reloaded.checkpoint_statuses
            self.assertEqual(statuses.get("tires"), "ok")
            self.assertEqual(statuses.get("brakes"), "critical")
            self.assertFalse(reloaded.vehicle_ready)
            self.assertEqual(reloaded.battery_level, 95)

    def test_anomaly_detection_with_dynamic_checkpoints(self):
        """Vérifie la détection d'anomalies flotte sur les checkpoints dynamiques."""
        with self.app.app_context():
            user, project = self._create_mock_data()

            checkout = CheckoutVehicle(
                project_id=project.id,
                controller_id=user.id,
                inspection_date=date(2026, 10, 5),
                vehicle_id="recVeh123",
                status="signed",
                battery_level=100
            )
            checkout.set_checkpoint_status("tires", "ok")
            checkout.set_checkpoint_status("brakes", "damage")
            db.session.add(checkout)
            db.session.commit()

            anomalies = _detect_inspection_anomalies(checkout)
            self.assertTrue(any("frein" in a.lower() for a in anomalies))

    def test_cascade_deletion(self):
        """Vérifie que la suppression d'un checkout supprime ses InspectionCheckpoint."""
        with self.app.app_context():
            user, project = self._create_mock_data()

            checkout = CheckoutVehicle(
                project_id=project.id,
                controller_id=user.id,
                inspection_date=date(2026, 10, 5),
                vehicle_id="recVeh123"
            )
            checkout.set_checkpoint_status("tires", "ok")
            checkout.set_checkpoint_status("brakes", "ok")
            db.session.add(checkout)
            db.session.commit()

            co_id = checkout.id
            self.assertEqual(InspectionCheckpoint.query.filter_by(checkout_id=co_id).count(), 2)

            db.session.delete(checkout)
            db.session.commit()

            self.assertEqual(InspectionCheckpoint.query.filter_by(checkout_id=co_id).count(), 0)

    def test_checkin_dynamic_checkpoints(self):
        """Vérifie le fonctionnement identique pour CheckinVehicle."""
        with self.app.app_context():
            user, project = self._create_mock_data()

            checkin = CheckinVehicle(
                project_id=project.id,
                controller_id=user.id,
                inspection_date=date(2026, 10, 8),
                vehicle_id="recVeh123",
                status="signed",
                battery_level=80
            )
            checkin.set_checkpoint_status("tires", "ok")
            checkin.set_checkpoint_status("roll_bar_tightness_status", "warning")
            db.session.add(checkin)
            db.session.commit()

    from unittest.mock import patch

    @patch("utils.database.get_vehicles")
    @patch("services.admin.inspections.get_vehicles")
    def test_dynamic_checkpoint_in_form_context_and_in_progress_check(self, mock_insp_veh, mock_db_veh):
        """Vérifie qu'un point de contrôle ajouté pendant un check en cours apparaît bien dans le contexte du formulaire checkin/checkout."""
        mock_vehicles = [{"id": "recVeh123", "fields": {"name": "eTrike 360", "unique_id": "ETRIKE-123"}}]
        mock_insp_veh.return_value = mock_vehicles
        mock_db_veh.return_value = mock_vehicles

        with self.app.app_context():
            from extensions import cache
            from services.admin.inspections import get_unified_form_context
            import json

            user, project = self._create_mock_data()
            veh_id = "recVeh123"

            # 1. Créer un check (checkout) en cours
            checkout = CheckoutVehicle(
                project_id=project.id,
                controller_id=user.id,
                inspection_date=date(2026, 10, 5),
                vehicle_id=veh_id,
                status="in_progress"
            )
            checkout.set_checkpoint_status("tires", "ok")
            db.session.add(checkout)
            db.session.commit()

            # 2. Ajout dynamique d'un nouveau point de contrôle en base
            new_def = CheckpointDefinition(
                key="camera_mount_dynamic",
                label="Support caméra gyrostabilisée",
                category="Équipements",
                type="status",
                default_detail="Vérifier la platine et les vis 3/8",
                order=99,
                vehicle_overrides={veh_id: {"enabled": True, "indication": "Vérifier la platine"}}
            )
            db.session.add(new_def)
            db.session.commit()
            cache.delete("checkpoint_definitions_all")

            # 3. Vérifier le contexte du formulaire checkin
            form_ctx = get_unified_form_context("checkin")
            checkpoint_keys = [cp["key"] for cp in form_ctx["checkpoints"]]
            self.assertIn("camera_mount_dynamic", checkpoint_keys)

            cfg_json = json.loads(form_ctx["checkpoints_config_json"])
            veh_cps = [item["key"] for item in cfg_json.get(veh_id, [])]
            self.assertIn("camera_mount_dynamic", veh_cps)

            # 4. Formattage du détail d'un check existant
            v_map = {v["id"]: v.get("fields", {}) for v in mock_vehicles}
            detail_data = _format_base_inspection_admin(checkout, v_map)
            detail_keys = [item["key"] for item in detail_data.get("check_items", [])]
            self.assertIn("camera_mount_dynamic", detail_keys)
            self.assertEqual(detail_data.get("camera_mount_dynamic"), "—")

            # 5. Soumission du formulaire incluant le nouveau point de contrôle
            form_payload = {
                "vehicle_id": veh_id,
                "camera_mount_dynamic": "ok",
                "tires": "ok"
            }
            apply_inspection_data(checkout, form_payload, is_checkout=True)
            db.session.commit()

            self.assertEqual(checkout.get_checkpoint_status("camera_mount_dynamic"), "ok")


if __name__ == "__main__":
    unittest.main()

