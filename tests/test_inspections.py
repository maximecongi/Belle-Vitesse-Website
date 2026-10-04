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
from models import db, Project, Production, User, CheckoutVehicle, CheckinVehicle
from services.admin.inspections import (
    list_inspections_unified,
    get_inspection_detail_unified,
    delete_inspection_unified,
    get_unified_form_context
)

class InspectionsTest(unittest.TestCase):
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

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _create_mock_data(self):
        # Create user
        user = User(firstname="John", lastname="Doe", mail="john.doe@example.com", role="administrator")
        db.session.add(user)
        
        # Create production
        prod = Production(name="Test Prod")
        db.session.add(prod)
        db.session.flush()

        # Create project
        proj = Project(
            name="Test Project",
            production_id=prod.id,
            departure_date=date(2026, 6, 2),
            return_date=date(2026, 6, 5),
            vehicles_to_check="1"
        )
        db.session.add(proj)
        db.session.commit()

        return user, proj

    def test_list_and_details(self):
        with self.app.app_context():
            user, proj = self._create_mock_data()

            from utils.checkpoints import get_checkpoints_for_vehicle

            # Create checkout vehicle conforme
            checkout = CheckoutVehicle(
                project_id=proj.id,
                controller_id=user.id,
                inspection_date=date(2026, 6, 2),
                vehicle_id="1",
                status="completed",
                vehicle_ready=True,
                battery_level=100.0,
            )
            for cp in get_checkpoints_for_vehicle("1"):
                if cp.get("type") == "status":
                    checkout.set_checkpoint_status(cp["key"], "ok")
            db.session.add(checkout)
            db.session.commit()

            # Test list unified
            res = list_inspections_unified("checkout")
            self.assertEqual(res["stats"]["total_checkouts"], 1)
            self.assertEqual(res["checkouts"][0]["project"], "Test Project")

            # Test details unified
            detail = get_inspection_detail_unified("checkout", checkout.id)
            self.assertIsNotNone(detail)
            self.assertEqual(detail["tires"], "ok")
            self.assertEqual(detail["failures"], [])
            self.assertFalse(detail["has_failures"])
            self.assertEqual(detail["ready"], "true")

            # Test details with failure and low battery
            checkout.set_checkpoint_status("tires", "critical")
            checkout.battery_level = 85
            db.session.commit()

            detail_failed = get_inspection_detail_unified("checkout", checkout.id)
            self.assertTrue(detail_failed["has_failures"])
            self.assertIn("Charge batterie (< 100%)", detail_failed["failures"])
            self.assertEqual(detail_failed["failure_count"], 2)
            self.assertEqual(detail_failed["ready"], "false")

    def test_unfilled_checkpoints_appear_in_failures(self):
        """Vérifie que les points non renseignés ('—', '--', None) apparaissent bien dans failures."""
        with self.app.app_context():
            user, proj = self._create_mock_data()
            from utils.checkpoints import get_checkpoints_for_vehicle

            checkout = CheckoutVehicle(
                project_id=proj.id,
                controller_id=user.id,
                inspection_date=date(2026, 6, 2),
                vehicle_id="1",
                status="in_progress",
                battery_level=100.0,
            )
            # On ne valide que les pneus, tous les autres points restent non renseignés (None / —)
            checkout.set_checkpoint_status("tires", "ok")
            db.session.add(checkout)
            db.session.commit()

            detail = get_inspection_detail_unified("checkout", checkout.id)
            self.assertTrue(detail["has_failures"])
            self.assertEqual(detail["ready"], "false")

            # 'Contrôle des freins' (brakes) est non renseigné par défaut (valeur '—')
            self.assertIn("Contrôle des freins", detail["failures"])
            # 'Pression des pneus' (tires) est à 'ok', ne doit pas figurer dans failures
            tires_label = next((cp["label"] for cp in get_checkpoints_for_vehicle("1") if cp["key"] == "tires"), "tires")
            self.assertNotIn(tires_label, detail["failures"])

    def test_soft_delete(self):
        with self.app.app_context():
            user, proj = self._create_mock_data()

            checkout = CheckoutVehicle(
                project_id=proj.id,
                controller_id=user.id,
                inspection_date=date(2026, 6, 2),
                vehicle_id="1",
                status="completed"
            )
            db.session.add(checkout)
            db.session.commit()

            # Delete
            success = delete_inspection_unified("checkout", checkout.id)
            self.assertTrue(success)

            # Retrieve again - unified list should be empty
            res = list_inspections_unified("checkout")
            self.assertEqual(res["stats"]["total_checkouts"], 0)

            # Unified detail should be None
            detail = get_inspection_detail_unified("checkout", checkout.id)
            self.assertIsNone(detail)

            # Check DB directly to verify deleted_at is filled
            db_checkout = db.session.get(CheckoutVehicle, checkout.id)
            self.assertIsNotNone(db_checkout)
            self.assertIsNotNone(db_checkout.deleted_at)

    def test_unified_form_context(self):
        with self.app.app_context():
            user, proj = self._create_mock_data()
            context = get_unified_form_context("checkout")
            self.assertIn("projects", context)
            self.assertIn("users", context)
            self.assertIn("vehicles", context)

    def test_create_checkout_and_checkin_routes(self):
        with self.app.app_context():
            user, proj = self._create_mock_data()

            with self.client.session_transaction() as sess:
                sess['admin_authenticated'] = True
                sess['admin_user_id'] = user.id
                sess['admin_user_firstname'] = user.firstname
                sess['admin_user_lastname'] = user.lastname
                sess['admin_user_role'] = 'administrator'
                sess['admin_logged_in'] = True

            # POST /admin/checkouts/new without photos
            res = self.client.post("/admin/checkouts/new", data={
                "project_id": str(proj.id),
                "vehicle_id": "1",
                "controller_id": user.id,
                "battery_level": "100",
                "notes": "Test creation checkout",
                "tires": "ok",
                "brakes": "ok"
            }, follow_redirects=False)

            self.assertEqual(res.status_code, 302)
            self.assertIn("/admin/checkouts", res.headers.get("Location", ""))

            checkout = CheckoutVehicle.query.filter_by(project_id=proj.id).first()
            self.assertIsNotNone(checkout)
            self.assertEqual(checkout.battery_level, 100)

            # Mark checkout as signed so checkin is permitted by business rule
            checkout.status = 'signed'
            db.session.commit()

            # POST /admin/checkins/new without photos
            res_in = self.client.post("/admin/checkins/new", data={
                "project_id": str(proj.id),
                "vehicle_id": "1",
                "controller_id": user.id,
                "battery_level": "90",
                "notes": "Test creation checkin",
                "tires": "ok",
                "brakes": "ok"
            }, follow_redirects=False)

            self.assertEqual(res_in.status_code, 302)
            self.assertIn("/admin/checkins", res_in.headers.get("Location", ""))

            checkin = CheckinVehicle.query.filter_by(project_id=proj.id).first()
            self.assertIsNotNone(checkin)
            self.assertEqual(checkin.battery_level, 90)

    def test_verify_public_routes(self):
        from models import CheckoutSignedDocument, CheckinSignedDocument
        with self.app.app_context():
            user, proj = self._create_mock_data()

            doc_co = CheckoutSignedDocument(
                inspection_id="BVCO-TEST1234",
                hash="mock_hash_123",
                data_snapshot={
                    "inspection_id": "BVCO-TEST1234",
                    "project": "Test Project",
                    "production": "Test Prod",
                    "control_date": "05/09/2026",
                    "controller": {"name": "John Doe"},
                    "vehicle": {"fields": {"name": "Test Car", "unique_id": "CAR-01"}},
                    "vehicle_id": "1",
                    "signed_at": "2026-09-05T12:00:00"
                },
                signature="data:image/png;base64,mock",
                pdf_url="/checkout/document/test.pdf"
            )
            db.session.add(doc_co)

            doc_ci = CheckinSignedDocument(
                inspection_id="BVCI-TEST5678",
                hash="mock_hash_456",
                data_snapshot={
                    "inspection_id": "BVCI-TEST5678",
                    "project": "Test Project",
                    "production": "Test Prod",
                    "control_date": "05/09/2026",
                    "controller": {"name": "John Doe"},
                    "vehicle": {"fields": {"name": "Test Car", "unique_id": "CAR-01"}},
                    "vehicle_id": "1",
                    "signed_at": "2026-09-05T12:00:00"
                },
                signature="data:image/png;base64,mock",
                pdf_url="/checkin/document/test.pdf"
            )
            db.session.add(doc_ci)
            db.session.commit()

        # Test GET /checkout/verify/BVCO-TEST1234
        res_co = self.client.get("/checkout/verify/BVCO-TEST1234")
        self.assertEqual(res_co.status_code, 200)
        self.assertIn(b"BVCO-TEST1234", res_co.data)
        self.assertIn("Données Scellées".encode("utf-8"), res_co.data)

        # Test GET /checkin/verify/BVCI-TEST5678
        res_ci = self.client.get("/checkin/verify/BVCI-TEST5678")
        self.assertEqual(res_ci.status_code, 200)
        self.assertIn(b"BVCI-TEST5678", res_ci.data)
        self.assertIn("Données Scellées".encode("utf-8"), res_ci.data)

    def test_create_checkin_force_checkin(self):
        with self.app.app_context():
            user, proj = self._create_mock_data()

            with self.client.session_transaction() as sess:
                sess['admin_authenticated'] = True
                sess['admin_user_id'] = user.id
                sess['admin_user_firstname'] = user.firstname
                sess['admin_user_lastname'] = user.lastname
                sess['admin_user_role'] = 'administrator'
                sess['admin_logged_in'] = True

            # Checkout exists but is in_progress (NOT signed)
            checkout = CheckoutVehicle(
                status="in_progress",
                project_id=proj.id,
                vehicle_id="1",
                controller_id=user.id
            )
            db.session.add(checkout)
            db.session.commit()

            # 1. Attempt checkin without force_checkin -> fails with warning flash
            res_fail = self.client.post("/admin/checkins/new", data={
                "project_id": str(proj.id),
                "vehicle_id": "1",
                "controller_id": user.id,
                "battery_level": "80",
                "notes": "Attempt without force",
            }, follow_redirects=True)
            self.assertEqual(res_fail.status_code, 200)
            self.assertIn("Le départ de ce véhicule".encode("utf-8"), res_fail.data)

            # 2. Attempt checkin with force_checkin="1" -> succeeds
            res_ok = self.client.post("/admin/checkins/new", data={
                "project_id": str(proj.id),
                "vehicle_id": "1",
                "controller_id": user.id,
                "battery_level": "80",
                "notes": "Attempt with force",
                "force_checkin": "1"
            }, follow_redirects=False)
            self.assertEqual(res_ok.status_code, 302)
            self.assertIn("/admin/checkins", res_ok.headers.get("Location", ""))

            # Check that record notes include the exceptional mention
            saved_ci = CheckinVehicle.query.filter_by(project_id=proj.id).first()
            self.assertIsNotNone(saved_ci)
            self.assertIn("Retour exceptionnel", saved_ci.notes)

    def test_create_checkin_blocked_when_already_exists(self):
        with self.app.app_context():
            user, proj = self._create_mock_data()

            with self.client.session_transaction() as sess:
                sess['admin_authenticated'] = True
                sess['admin_user_id'] = user.id
                sess['admin_user_firstname'] = user.firstname
                sess['admin_user_lastname'] = user.lastname
                sess['admin_user_role'] = 'administrator'
                sess['admin_logged_in'] = True

            # Existing checkin already in progress
            existing_ci = CheckinVehicle(
                status="in_progress",
                inspection_number="BVCI-TESTEXISTING1",
                project_id=proj.id,
                vehicle_id="1",
                controller_id=user.id
            )
            db.session.add(existing_ci)
            db.session.commit()

            # Attempt to create another checkin for the same vehicle and project
            res = self.client.post("/admin/checkins/new", data={
                "project_id": str(proj.id),
                "vehicle_id": "1",
                "controller_id": user.id,
                "battery_level": "80",
                "notes": "Attempt duplicate checkin",
            }, follow_redirects=True)

            self.assertEqual(res.status_code, 200)
            self.assertIn("un retour est déjà en cours (BVCI-TESTEXISTING1)".encode("utf-8"), res.data)

    def test_re_sign_checkout_upsert_and_abandon_protection(self):
        """Vérifie que re-signer un checkout met à jour le SignedDocument sans IntegrityError
        et que l'abandon ne rétrograde jamais un checkout déjà signé."""
        from models import CheckoutSignedDocument
        from services.common.signatures import (
            abandon_inspection_signature,
            finalize_signed_document,
            generate_inspection_token,
        )

        with self.app.app_context(), self.app.test_request_context("/"):
            user, proj = self._create_mock_data()

            checkout = CheckoutVehicle(
                inspection_number="BVCO-TESTUPSERT1",
                status="in_progress",
                project_id=proj.id,
                vehicle_id="1",
                controller_id=user.id,
            )
            db.session.add(checkout)
            db.session.commit()

            # 1. Première signature
            dummy_sig = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            res1 = finalize_signed_document("checkout", checkout.id, dummy_sig, "127.0.0.1")
            self.assertEqual(res1["document_id"], "BVCO-TESTUPSERT1")

            updated_co = CheckoutVehicle.query.get(checkout.id)
            self.assertEqual(updated_co.status, "signed")

            signed_doc1 = CheckoutSignedDocument.query.filter_by(inspection_id="BVCO-TESTUPSERT1").first()
            self.assertIsNotNone(signed_doc1)

            # 2. Génération d'un token puis tentative d'abandon sur document déjà signé
            token_res = generate_inspection_token(checkout.id, "checkout")
            self.assertIsNotNone(token_res)
            # Le statut doit rester signed
            self.assertEqual(CheckoutVehicle.query.get(checkout.id).status, "signed")

            abandon_ok = abandon_inspection_signature(token_res["token"], "checkout")
            self.assertTrue(abandon_ok)
            # Le statut ne doit JAMAIS rétrograder à in_progress
            self.assertEqual(CheckoutVehicle.query.get(checkout.id).status, "signed")

            # 3. Re-signature (doit faire un upsert sans IntegrityError Duplicate entry)
            dummy_sig2 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            res2 = finalize_signed_document("checkout", checkout.id, dummy_sig2, "127.0.0.1")
            self.assertEqual(res2["document_id"], "BVCO-TESTUPSERT1")

            # Vérifie qu'il n'y a toujours qu'une seule ligne d'archive et qu'elle est mise à jour
            signed_docs = CheckoutSignedDocument.query.filter_by(inspection_id="BVCO-TESTUPSERT1").all()
            self.assertEqual(len(signed_docs), 1)
            self.assertEqual(signed_docs[0].hash, res2["hash"])

    def test_checkpoint_deletion_cleans_in_progress_and_recomputes_readiness(self):
        """Vérifie que la suppression d'un checkpoint nettoie les inspections en cours et rétablit la conformité."""
        from services.admin.inspections import apply_inspection_data
        from services.admin.checkouts import get_checkout_detail
        from services.admin.vehicle_config import create_checkpoint, delete_checkpoint

        with self.app.app_context(), self.app.test_request_context("/"):
            user, proj = self._create_mock_data()

            # 1. Créer un checkpoint personnalisé
            new_cp = create_checkpoint({
                "label": "Point Temporaire Bug",
                "category": "Sécurité",
                "type": "status"
            })
            self.assertIsNotNone(new_cp)
            cp_key = new_cp.key

            # 2. Créer une inspection avec tous les points OK sauf le point temporaire
            co = CheckoutVehicle(
                status="in_progress",
                inspection_number="BVCO-TESTCLEAN1",
                project_id=proj.id,
                vehicle_id="1",
                battery_level=100,
                controller_id=user.id
            )
            from utils.checkpoints import get_checkpoints_for_vehicle
            form_data = {
                "vehicle_id": "1",
                "project_id": str(proj.id),
                "battery_level": "100",
            }
            for cp_item in get_checkpoints_for_vehicle("1"):
                if cp_item.get("type") == "value":
                    form_data[cp_item["key"]] = "100" if cp_item["key"] in ("battery", "battery_level") else "10"
                else:
                    form_data[cp_item["key"]] = "ok"
            form_data[cp_key] = "warning"  # Seul point non conforme

            apply_inspection_data(co, form_data, is_checkout=True)
            db.session.add(co)
            db.session.commit()

            # Le véhicule ne doit pas être prêt
            self.assertFalse(co.vehicle_ready)
            detail = get_checkout_detail(co.id)
            self.assertEqual(detail["ready"], "false")
            self.assertTrue(detail["has_failures"])
            self.assertIn("Point Temporaire Bug", detail["failures"])

            # 3. Supprimer le point de contrôle
            success, msg = delete_checkpoint(new_cp.id)
            self.assertTrue(success)

            # 4. Vérifier que l'inspection en cours est redevenue conforme
            updated_co = CheckoutVehicle.query.get(co.id)
            self.assertTrue(updated_co.vehicle_ready)
            updated_detail = get_checkout_detail(co.id)
            self.assertEqual(updated_detail["ready"], "true")
            self.assertEqual(updated_detail["failures"], [])
            self.assertFalse(updated_detail["has_failures"])

    def test_upload_inspection_photos_annotated_base64_and_multipart(self):
        """Vérifie que upload_inspection_photos_shared prend en compte les photos annotées encodées en base64."""
        import json
        from services.admin.inspections import upload_inspection_photos_shared
        from werkzeug.datastructures import MultiDict

        with self.app.app_context():
            user, proj = self._create_mock_data()
            co = CheckoutVehicle(
                inspection_number="BVCO-2026-TEST-PHOTOS",
                status="in_progress",
                inspection_date=date(2026, 10, 5),
                project_id=proj.id,
                controller_id=user.id,
                vehicle_id="1"
            )
            db.session.add(co)
            db.session.commit()

            # 1x1 transparent/valid base64 JPEG
            tiny_b64 = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
            form = {
                "exterior_photos_annotated_0": tiny_b64
            }

            upload_inspection_photos_shared("checkout", co, files=None, form=form)

            self.assertIsNotNone(co.exterior_photos)
            paths = json.loads(co.exterior_photos)
            self.assertEqual(len(paths), 1)
            self.assertTrue(paths[0].endswith(".jpg"))

            # Nettoyer les fichiers créés sur le disque
            output_base = self.app.config.get("OUTPUT_FOLDER", os.path.join(self.app.root_path, "output"))
            saved_file = os.path.join(output_base, paths[0])
            if os.path.exists(saved_file):
                os.remove(saved_file)


if __name__ == "__main__":
    unittest.main()
