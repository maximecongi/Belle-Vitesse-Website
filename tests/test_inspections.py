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

        from unittest.mock import patch
        self.get_vehicles_patcher = patch(
            "utils.database.get_vehicles",
            return_value=[{"id": "1", "fields": {"name": "Test Car 1"}}]
        )
        self.get_vehicles_patcher.start()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        self.get_vehicles_patcher.stop()
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
            self.assertTrue(any("Charge" in f for f in detail_failed["failures"]))
            self.assertEqual(detail_failed["failure_count"], 2)
            self.assertEqual(detail_failed["ready"], "false")

            # Vérifie que la batterie dans les check_items porte son état de validité et ses bornes
            battery_item = next((i for i in detail_failed["check_items"] if i["key"] in ("battery", "battery_level")), None)
            self.assertIsNotNone(battery_item)
            self.assertFalse(battery_item["is_valid"])
            self.assertIsNotNone(battery_item.get("goal"))

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

            checkout = CheckoutVehicle.query.filter_by(project_id=proj.id).first()
            self.assertIsNotNone(checkout)
            self.assertEqual(checkout.battery_level, 100)
            self.assertEqual(res.status_code, 302)
            self.assertEqual(res.headers.get("Location"), f"/admin/checkouts/{checkout.id}")

            # Mark checkout as signed with sealed document so checkin is permitted by business rule
            checkout.status = 'signed'
            from models import CheckoutSignedDocument
            signed_co_doc = CheckoutSignedDocument(
                inspection_id=checkout.inspection_number,
                hash="mock_signed_co_hash_abc123",
                data_snapshot={"status": "signed"}
            )
            db.session.add(signed_co_doc)
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

            checkin = CheckinVehicle.query.filter_by(project_id=proj.id).first()
            self.assertIsNotNone(checkin)
            self.assertEqual(checkin.battery_level, 90)
            self.assertEqual(res_in.status_code, 302)
            self.assertEqual(res_in.headers.get("Location"), f"/admin/checkins/{checkin.id}")

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

            from utils.document_utils import generate_document_verification_token
            co_token = generate_document_verification_token("checkout", "BVCO-TEST1234", 1, doc_co.hash)
            ci_token = generate_document_verification_token("checkin", "BVCI-TEST5678", 1, doc_ci.hash)

        # Test GET /checkout/verify/BVCO-TEST1234
        res_co = self.client.get(f"/checkout/verify/BVCO-TEST1234?version=1&t={co_token}")
        self.assertEqual(res_co.status_code, 200)
        self.assertIn(b"BVCO-TEST1234", res_co.data)
        self.assertIn("Données Scellées".encode("utf-8"), res_co.data)

        # Test GET /checkin/verify/BVCI-TEST5678
        res_ci = self.client.get(f"/checkin/verify/BVCI-TEST5678?version=1&t={ci_token}")
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
            saved_ci = CheckinVehicle.query.filter_by(project_id=proj.id).first()
            self.assertIsNotNone(saved_ci)
            self.assertEqual(res_ok.status_code, 302)
            self.assertEqual(res_ok.headers.get("Location"), f"/admin/checkins/{saved_ci.id}")
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

            # 2. Tentative de génération d'un token sur document déjà signé -> doit échouer (immuabilité stricte)
            with self.assertRaises(ValueError) as ctx_tok:
                generate_inspection_token(checkout.id, "checkout")
            self.assertIn("déjà été signé", str(ctx_tok.exception))
            self.assertEqual(CheckoutVehicle.query.get(checkout.id).status, "signed")

            # 3. Tentative de re-signature / écrasement direct -> doit être strictement interdit (ValueError)
            dummy_sig2 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            with self.assertRaises(ValueError) as ctx_sig:
                finalize_signed_document("checkout", checkout.id, dummy_sig2, "127.0.0.1")
            self.assertIn("déjà été signé et scellé de manière immuable", str(ctx_sig.exception))

            # Vérifie que l'archive originale reste inchangée et intacte
            signed_docs = CheckoutSignedDocument.query.filter_by(inspection_id="BVCO-TESTUPSERT1").all()
            self.assertEqual(len(signed_docs), 1)
            self.assertEqual(signed_docs[0].hash, res1["hash"])

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

    def test_parse_photos_json_includes_rel_path(self):
        """Vérifie que _parse_photos_json inclut la clé rel_path pour permettre la suppression ciblée."""
        from services.admin.utils import _parse_photos_json
        sample_json = '["2026/PROJ_1/BVCO-01/exterior/photo1.jpg", "2026/PROJ_1/BVCO-01/exterior/photo2.jpg"]'
        parsed = _parse_photos_json(sample_json)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["rel_path"], "2026/PROJ_1/BVCO-01/exterior/photo1.jpg")
        self.assertEqual(parsed[0]["label"], "photo1.jpg")
        self.assertEqual(parsed[0]["url"], "/files/2026/PROJ_1/BVCO-01/exterior/photo1.jpg")

    def test_delete_existing_inspection_photos_in_edit_route(self):
        """Vérifie la suppression d'une photo existante lors de la modification d'un checkout et d'un checkin."""
        import json
        from pathlib import Path
        output_base = Path(self.app.config.get("OUTPUT_FOLDER", os.path.join(self.app.root_path, "output")))

        with self.app.app_context():
            user, proj = self._create_mock_data()

            with self.client.session_transaction() as sess:
                sess['admin_authenticated'] = True
                sess['admin_user_id'] = user.id
                sess['admin_user_firstname'] = user.firstname
                sess['admin_user_lastname'] = user.lastname
                sess['admin_user_role'] = 'administrator'
                sess['admin_logged_in'] = True

            # 1. Préparer deux fichiers physiques de test pour le checkout
            rel_photo1 = f"test_del_co_{proj.id}_1.jpg"
            rel_photo2 = f"test_del_co_{proj.id}_2.jpg"
            file1_path = output_base / rel_photo1
            file2_path = output_base / rel_photo2
            file1_path.parent.mkdir(parents=True, exist_ok=True)
            file1_path.write_bytes(b"dummy photo 1")
            file2_path.write_bytes(b"dummy photo 2")

            co = CheckoutVehicle(
                inspection_number="BVCO-TEST-DEL",
                status="in_progress",
                inspection_date=date(2026, 10, 5),
                project_id=proj.id,
                controller_id=user.id,
                vehicle_id="1",
                exterior_photos=json.dumps([rel_photo1, rel_photo2])
            )
            db.session.add(co)
            db.session.commit()

            # 2. POST /admin/checkouts/<id>/edit en demandant la suppression de photo1
            res = self.client.post(f"/admin/checkouts/{co.id}/edit", data={
                "project_id": str(proj.id),
                "vehicle_id": "1",
                "controller_id": user.id,
                "notes": "Updated checkout notes",
                "delete_photos_exterior_photos": rel_photo1
            }, follow_redirects=False)

            self.assertEqual(res.status_code, 302)
            self.assertEqual(res.headers.get("Location"), f"/admin/checkouts/{co.id}")

            # Vérifier que le fichier photo1 a été supprimé du disque et que photo2 existe toujours
            self.assertFalse(file1_path.exists())
            self.assertTrue(file2_path.exists())

            # Vérifier la BDD
            db.session.refresh(co)
            ext_photos = json.loads(co.exterior_photos)
            self.assertEqual(len(ext_photos), 1)
            self.assertIn(rel_photo2, ext_photos)
            self.assertNotIn(rel_photo1, ext_photos)

            # Nettoyer photo2
            if file2_path.exists():
                file2_path.unlink()

            # 3. Test similaire pour Checkin
            rel_ci_photo = f"test_del_ci_{proj.id}.jpg"
            ci_file_path = output_base / rel_ci_photo
            ci_file_path.write_bytes(b"dummy ci photo")

            ci = CheckinVehicle(
                inspection_number="BVCI-TEST-DEL",
                status="in_progress",
                inspection_date=date(2026, 10, 6),
                project_id=proj.id,
                controller_id=user.id,
                vehicle_id="1",
                interior_photos=json.dumps([rel_ci_photo])
            )
            db.session.add(ci)
            db.session.commit()

            res_ci = self.client.post(f"/admin/checkins/{ci.id}/edit", data={
                "project_id": str(proj.id),
                "vehicle_id": "1",
                "controller_id": user.id,
                "delete_photos_interior_photos": rel_ci_photo
            }, follow_redirects=False)

            self.assertEqual(res_ci.status_code, 302)
            self.assertEqual(res_ci.headers.get("Location"), f"/admin/checkins/{ci.id}")

            self.assertFalse(ci_file_path.exists())
            db.session.refresh(ci)
            self.assertIsNone(ci.interior_photos)

    def test_serve_private_file_image_inline_display(self):
        """Vérifie que les images servies sous /files/ s'affichent inline (dans l'onglet) et non en téléchargement forcé."""
        from pathlib import Path
        output_base = Path(self.app.config.get("OUTPUT_FOLDER", os.path.join(self.app.root_path, "output")))

        with self.app.app_context():
            user, proj = self._create_mock_data()

            with self.client.session_transaction() as sess:
                sess['admin_authenticated'] = True
                sess['admin_user_id'] = user.id
                sess['admin_user_role'] = 'administrator'
                sess['admin_logged_in'] = True

            test_img_rel = f"test_inline_img_{proj.id}.jpg"
            test_img_path = output_base / test_img_rel
            test_img_path.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00")

            try:
                # 1. Requête standard pour affichage dans un onglet : doit être inline
                res = self.client.get(f"/files/{test_img_rel}")
                self.assertEqual(res.status_code, 200)
                self.assertIn("image/jpeg", res.headers.get("Content-Type", ""))
                disposition = res.headers.get("Content-Disposition", "")
                self.assertIn("inline", disposition)
                self.assertNotIn("attachment", disposition)

                # 2. Requête explicite avec ?download=1 : doit forcer le téléchargement
                res_download = self.client.get(f"/files/{test_img_rel}?download=1")
                self.assertEqual(res_download.status_code, 200)
                disposition_dl = res_download.headers.get("Content-Disposition", "")
                self.assertIn("attachment", disposition_dl)
            finally:
                if test_img_path.exists():
                    test_img_path.unlink()

    def test_pdf_vehicle_card_rendering_and_no_status_box(self):
        """Vérifie que le template PDF affiche la carte de véhicule harmonisée CGL et ne contient plus la case État du contrôle."""
        from flask import render_template

        with self.app.app_context():
            mock_data = {
                "inspection_id": "BVCO-TEST-CARD",
                "control_date": "02/11/2026",
                "project": "Projet Alpha",
                "production": "Prod Beta",
                "departure_date": "02/11/2026",
                "shoot_start": "03/11/2026",
                "shoot_end": "05/11/2026",
                "controller": {"name": "Alex Tech"},
                "vehicle": {
                    "fields": {
                        "name": "eCar",
                        "unique_id": "ECAR-FYGT",
                        "thumbnail": "https://example.com/ecar.png"
                    }
                },
                "status_id": "in_progress",
                "check_items": [],
                "exterior_photos": [],
                "interior_photos": [],
            }

            rendered_co = render_template("pdf/checkout.html", data=mock_data, company_name="Belle Vitesse")
            # 1. Vérifier la présence de la carte véhicule de type CGL
            self.assertIn("public-doc-vehicle-card", rendered_co)
            self.assertIn("public-doc-vehicle-thumb-wrapper", rendered_co)
            self.assertIn("eCar", rendered_co)
            self.assertIn("ECAR-FYGT", rendered_co)
            self.assertIn("checkout-doc-id", rendered_co)

            # 2. Vérifier que la case État du contrôle a bien été supprimée
            self.assertNotIn("État du contrôle", rendered_co)
            self.assertNotIn("Etat du contrôle", rendered_co)

            # 3. Vérifier également pour checkin.html
            rendered_ci = render_template("pdf/checkin.html", data=mock_data, company_name="Belle Vitesse")
            self.assertIn("public-doc-vehicle-card", rendered_ci)
            self.assertIn("public-doc-vehicle-thumb-wrapper", rendered_ci)
            self.assertIn("eCar", rendered_ci)
            self.assertIn("ECAR-FYGT", rendered_ci)
            self.assertNotIn("État du contrôle", rendered_ci)
            self.assertNotIn("Etat du contrôle", rendered_ci)

    def test_checkout_and_checkin_preview_routes(self):
        """Vérifie le bon fonctionnement des pages de prévisualisation PDF (écran et compilation)."""
        with self.app.app_context():
            user, proj = self._create_mock_data()

            # 1. Prévisualisation générale Checkout (mock)
            res_co_mock = self.client.get("/admin/checkouts/preview")
            self.assertEqual(res_co_mock.status_code, 200)
            html_co = res_co_mock.get_data(as_text=True)
            self.assertIn("pdf-preview-toolbar", html_co)
            self.assertIn("Fiche de Contrôle au Départ (Check-Out)", html_co)
            self.assertIn("public-doc-vehicle-card", html_co)
            self.assertIn("ECAR-FYGT", html_co)

            # 2. Alias direct /preview/pdf/checkout
            res_alias = self.client.get("/preview/pdf/checkout")
            self.assertEqual(res_alias.status_code, 200)

            # 3. Prévisualisation avec ID d'un checkout réel
            co = CheckoutVehicle(
                project_id=proj.id,
                controller_id=user.id,
                vehicle_id="recFyGTcZSNKWuOMY",
                status="in_progress",
                inspection_date=date.today(),
            )
            db.session.add(co)
            db.session.commit()

            res_co_real = self.client.get(f"/admin/checkouts/{co.id}/preview")
            self.assertEqual(res_co_real.status_code, 200)
            html_real = res_co_real.get_data(as_text=True)
            self.assertIn(co.inspection_number, html_real)
            self.assertIn("pdf-preview-toolbar", html_real)

            # 4. Compilation directe en PDF WeasyPrint via ?format=pdf
            res_pdf = self.client.get(f"/admin/checkouts/{co.id}/preview?format=pdf")
            self.assertEqual(res_pdf.status_code, 200)
            self.assertEqual(res_pdf.headers.get("Content-Type"), "application/pdf")
            self.assertTrue(res_pdf.data.startswith(b"%PDF"))

            # 5. Prévisualisation Checkin (mock et alias)
            res_ci_mock = self.client.get("/admin/checkins/preview")
            self.assertEqual(res_ci_mock.status_code, 200)
            html_ci = res_ci_mock.get_data(as_text=True)
            self.assertIn("Fiche de Contrôle au Retour (Check-In)", html_ci)

            res_ci_alias = self.client.get("/preview/pdf/checkin")
            self.assertEqual(res_ci_alias.status_code, 200)


if __name__ == "__main__":
    unittest.main()
