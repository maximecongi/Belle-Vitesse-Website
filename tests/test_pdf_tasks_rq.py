from tests.base import BaseTestCase
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from models.db import db
from models.project import Project, Production
from models.waiver import SafetyRulesWaiver, WaiverSignedDocument
from services.common.pdf_tasks import dispatch_pdf_generation, task_render_pdf_to_file
from services.common.redis_queue import clear_redis_cache


class PDFTasksRQTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        clear_redis_cache()

    def tearDown(self):
        clear_redis_cache()
        super().tearDown()

    def test_sync_execution_in_testing_mode(self):
        """Vérifie que la compilation s'exécute de façon synchrone et écrit le fichier en mode test."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_path = os.path.join(tmp_dir, "test_sync.pdf")
            ok = dispatch_pdf_generation(
                html_content="<h1>Test PDF Sync</h1>",
                output_file_path=target_path,
                filename="test_sync.pdf",
                compress=False,
                sync=True,
            )

            self.assertTrue(ok)
            self.assertTrue(os.path.exists(target_path))
            with open(target_path, "rb") as f:
                content = f.read()
            self.assertTrue(content.startswith(b"%PDF"))

    @patch("services.common.pdf_tasks.get_rq_queue")
    def test_async_dispatch_enqueues_to_rq(self, mock_get_rq_queue):
        """Vérifie que dispatch_pdf_generation enfile le job dans la queue RQ 'pdf' hors testing."""
        mock_queue = MagicMock()
        mock_job = MagicMock()
        mock_job.id = "rq-job-pdf-987"
        mock_queue.enqueue.return_value = mock_job
        mock_get_rq_queue.return_value = mock_queue

        with patch.dict(os.environ, {"FLASK_ENV": "production", "TESTING": "False"}):
            self.app.config["TESTING"] = False
            self.app.testing = False

            ok = dispatch_pdf_generation(
                html_content="<p>Async RQ</p>",
                output_file_path="/app/output/test_rq.pdf",
                filename="test_rq.pdf",
                compress=True,
                sync=False,
            )

            self.assertTrue(ok)
            mock_get_rq_queue.assert_called_with("pdf")
            mock_queue.enqueue.assert_called_once()
            args, kwargs = mock_queue.enqueue.call_args
            self.assertEqual(args[0], "services.common.pdf_tasks.task_render_pdf_to_file")
            self.assertEqual(kwargs["html_content"], "<p>Async RQ</p>")
            self.assertEqual(kwargs["output_file_path"], "/app/output/test_rq.pdf")
            self.assertEqual(kwargs["filename"], "test_rq.pdf")

    @patch("services.common.pdf_tasks.get_rq_queue", return_value=None)
    @patch("threading.Thread.start")
    def test_async_dispatch_falls_back_to_daemon_thread_when_redis_unavailable(
        self, mock_thread_start, mock_get_rq_queue
    ):
        """Vérifie le repli automatique sur un thread daemon lorsque Redis est indisponible."""
        with patch.dict(os.environ, {"FLASK_ENV": "production", "TESTING": "False"}):
            self.app.config["TESTING"] = False
            self.app.testing = False

            ok = dispatch_pdf_generation(
                html_content="<p>Test Thread Fallback</p>",
                output_file_path="/app/output/test_thread.pdf",
                sync=False,
            )

            self.assertTrue(ok)
            mock_thread_start.assert_called_once()

    def test_task_render_pdf_updates_waiver_entity(self):
        """Vérifie que la tâche worker met à jour les chemins et hashes de l'entité décharge."""
        prod = Production(name="Production Test PDF")
        db.session.add(prod)
        db.session.commit()

        project = Project(name="Projet Test PDF", production_id=prod.id)
        db.session.add(project)
        db.session.commit()

        waiver = SafetyRulesWaiver(
            waiver_id="BVSR-TESTPDF1",
            project_id=project.id,
            signer_first_name="Jean",
            signer_last_name="Dupont",
            status="signed",
        )
        db.session.add(waiver)
        db.session.commit()

        signed_doc = WaiverSignedDocument(
            waiver_id="BVSR-TESTPDF1",
            hash="hmac-hash-initial",
            pdf_file_hash="",
            data_snapshot={"signer": "Jean Dupont"},
            signature="data:image/png;base64,mock",
            pdf_url="/waivers/document/BVSR-TESTPDF1.pdf",
        )
        db.session.add(signed_doc)
        db.session.commit()

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_file = os.path.join(tmp_dir, "BVSR-TESTPDF1.pdf")

            success = task_render_pdf_to_file(
                html_content="<h1>Règles de sécurité signées</h1>",
                output_file_path=output_file,
                filename="BVSR-TESTPDF1.pdf",
                compress=False,
                entity_type="waiver",
                entity_id="BVSR-TESTPDF1",
            )

            self.assertTrue(success)
            self.assertTrue(os.path.exists(output_file))

            updated_waiver = SafetyRulesWaiver.query.filter_by(waiver_id="BVSR-TESTPDF1").first()
            updated_doc = WaiverSignedDocument.query.filter_by(waiver_id="BVSR-TESTPDF1").first()

            self.assertIsNotNone(updated_waiver.signed_pdf_path)
            self.assertTrue(len(updated_doc.pdf_file_hash) > 0)

            # Cleanup
            db.session.delete(signed_doc)
            db.session.delete(waiver)
            db.session.delete(project)
            db.session.delete(prod)
            db.session.commit()

    def test_task_render_pdf_builds_signer_copy_and_splits_emails(self):
        """
        Double exemplaire : archive « Belle Vitesse » + copie signataire à son nom.
        Le signataire reçoit sa copie (sans CCI), l'archive mail reçoit l'exemplaire d'archive.
        Les deux empreintes sont enregistrées et distinctes.
        """
        from utils.document_utils import compute_pdf_hash, signer_copy_path

        prod = Production(name="Production Test Copie")
        db.session.add(prod)
        db.session.commit()
        project = Project(name="Projet Test Copie", production_id=prod.id)
        db.session.add(project)
        db.session.commit()
        waiver = SafetyRulesWaiver(
            waiver_id="BVSR-TESTCOPY1",
            project_id=project.id,
            signer_first_name="Jean",
            signer_last_name="Dupont",
            signer_email="jean@prod.test",
            status="signed",
        )
        db.session.add(waiver)
        signed_doc = WaiverSignedDocument(
            waiver_id="BVSR-TESTCOPY1",
            hash="hmac-hash-copy",
            pdf_file_hash="",
            data_snapshot={"signer": "Jean Dupont"},
            pdf_url="/safety-rules/document/BVSR-TESTCOPY1.pdf",
        )
        db.session.add(signed_doc)
        db.session.commit()

        with tempfile.TemporaryDirectory() as tmp_dir, \
                patch.dict(os.environ, {"ARCHIVE_EMAIL": "archive@bellevitesse.com"}), \
                patch("utils.mailer.EmailService.send_templated_email") as mock_send, \
                patch("services.common.signatures._dispatch_kdrive_document_bundle") as mock_kdrive, \
                patch("services.common.pdf_tasks.render_pdf_from_template",
                      side_effect=lambda **kw: b"%PDF-1.7\n" + kw["html_content"].encode()):
            # WeasyPrint est simulé dans les tests : rendu factice dépendant du HTML
            output_file = os.path.join(tmp_dir, "BVSR-TESTCOPY1.pdf")
            success = task_render_pdf_to_file(
                html_content="<h1>Archive</h1><p>Belle Vitesse</p>",
                output_file_path=output_file,
                filename="BVSR-TESTCOPY1.pdf",
                compress=False,
                entity_type="waiver",
                entity_id="BVSR-TESTCOPY1",
                post_action="waiver_post_actions",
                extra_context={
                    "mode": "safety_rules",
                    "current_hash": "hmac-hash-copy",
                    "signer_html_content": "<h1>Copie</h1><p>Jean Dupont</p>",
                },
            )
            self.assertTrue(success)

            signer_file = signer_copy_path(output_file)
            self.assertTrue(os.path.exists(output_file))
            self.assertTrue(os.path.exists(signer_file))

            doc = WaiverSignedDocument.query.filter_by(waiver_id="BVSR-TESTCOPY1").first()
            with open(output_file, "rb") as f:
                self.assertEqual(doc.pdf_file_hash, compute_pdf_hash(f.read()))
            with open(signer_file, "rb") as f:
                self.assertEqual(doc.signer_pdf_file_hash, compute_pdf_hash(f.read()))
            self.assertNotEqual(doc.pdf_file_hash, doc.signer_pdf_file_hash)

            # kDrive : uniquement l'archive
            self.assertTrue(mock_kdrive.call_args.args[2].endswith("BVSR-TESTCOPY1.pdf"))

            # E-mails : signataire (copie nominative, sans CCI) puis archive (exemplaire BV)
            calls = {c.kwargs["to_email"]: c.kwargs for c in mock_send.call_args_list}
            self.assertEqual(set(calls), {"jean@prod.test", "archive@bellevitesse.com"})
            self.assertEqual(calls["jean@prod.test"]["attachments"], [signer_file])
            self.assertIsNone(calls["jean@prod.test"]["bcc"])
            self.assertEqual(calls["archive@bellevitesse.com"]["attachments"], [output_file])
            self.assertTrue(calls["archive@bellevitesse.com"]["subject"].startswith("[Archive] "))

        db.session.delete(doc)
        db.session.delete(waiver)
        db.session.delete(project)
        db.session.delete(prod)
        db.session.commit()

    def test_task_render_pdf_updates_inspection_entity(self):
        """Vérifie que la tâche worker met à jour les chemins et hashes de l'entité inspection."""
        from models.inspection import CheckoutVehicle
        from models.waiver import CheckoutSignedDocument

        prod = Production(name="Production Inspection Test")
        db.session.add(prod)
        db.session.commit()

        project = Project(name="Projet Inspection Test", production_id=prod.id)
        db.session.add(project)
        db.session.commit()

        checkout = CheckoutVehicle(
            inspection_number="BVCO-TESTPDF01",
            project_id=project.id,
            status="signed",
            vehicle_id="ecar_01",
        )
        db.session.add(checkout)
        db.session.commit()

        signed_doc = CheckoutSignedDocument(
            inspection_id="BVCO-TESTPDF01",
            hash="hmac-hash-checkout",
            pdf_file_hash="",
            data_snapshot={"vehicle": "ecar_01"},
            signature="signatures/inspections/BVCO-TESTPDF01.png",
            pdf_url="/checkout/document/BVCO-TESTPDF01.pdf",
        )
        db.session.add(signed_doc)
        db.session.commit()

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_file = os.path.join(tmp_dir, "BVCO-TESTPDF01.pdf")

            success = task_render_pdf_to_file(
                html_content="<h1>Inspection départ signée</h1>",
                output_file_path=output_file,
                filename="BVCO-TESTPDF01.pdf",
                compress=False,
                entity_type="inspection",
                entity_id="BVCO-TESTPDF01",
            )

            self.assertTrue(success)
            self.assertTrue(os.path.exists(output_file))

            updated_checkout = CheckoutVehicle.query.filter_by(inspection_number="BVCO-TESTPDF01").first()
            updated_doc = CheckoutSignedDocument.query.filter_by(inspection_id="BVCO-TESTPDF01").first()

            self.assertIsNotNone(updated_checkout.signed_pdf_path)
            self.assertTrue(len(updated_doc.pdf_file_hash) > 0)

            # Cleanup
            db.session.delete(signed_doc)
            db.session.delete(checkout)
            db.session.delete(project)
            db.session.delete(prod)
            db.session.commit()


if __name__ == "__main__":
    unittest.main()
