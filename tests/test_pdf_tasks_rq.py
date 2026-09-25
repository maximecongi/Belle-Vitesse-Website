import os
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

os.environ["FLASK_ENV"] = "testing"
os.environ["TESTING"] = "True"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["USE_SSH_TUNNEL"] = "false"
os.environ["WTF_CSRF_ENABLED"] = "False"

# Mock Weasyprint pour l'environnement sans GObject/Pango
mock_weasyprint = MagicMock()
mock_html_inst = MagicMock()
mock_html_inst.write_pdf.return_value = (
    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
    b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
)
mock_weasyprint.HTML.return_value = mock_html_inst
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from app import create_app
from models.db import db
from models.project import Project, Production
from models.waiver import PilotWaiver, PilotWaiverSignedDocument
from services.common.pdf_tasks import dispatch_pdf_generation, task_render_pdf_to_file
from services.common.redis_queue import clear_redis_cache, get_rq_queue


class PDFTasksRQTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app_context = self.app.app_context()
        self.app_context.push()
        clear_redis_cache()

    def tearDown(self):
        clear_redis_cache()
        self.app_context.pop()

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

        waiver = PilotWaiver(
            waiver_id="BVDW-TESTPDF1",
            project_id=project.id,
            pilot_first_name="Jean",
            pilot_last_name="Dupont",
            status="signed",
        )
        db.session.add(waiver)
        db.session.commit()

        signed_doc = PilotWaiverSignedDocument(
            waiver_id="BVDW-TESTPDF1",
            hash="hmac-hash-initial",
            pdf_file_hash="",
            data_snapshot={"pilot": "Jean Dupont"},
            signature="data:image/png;base64,mock",
            pdf_url="/waivers/document/BVDW-TESTPDF1.pdf",
        )
        db.session.add(signed_doc)
        db.session.commit()

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_file = os.path.join(tmp_dir, "BVDW-TESTPDF1.pdf")

            success = task_render_pdf_to_file(
                html_content="<h1>Décharge signée</h1>",
                output_file_path=output_file,
                filename="BVDW-TESTPDF1.pdf",
                compress=False,
                entity_type="waiver",
                entity_id="BVDW-TESTPDF1",
            )

            self.assertTrue(success)
            self.assertTrue(os.path.exists(output_file))

            updated_waiver = PilotWaiver.query.filter_by(waiver_id="BVDW-TESTPDF1").first()
            updated_doc = PilotWaiverSignedDocument.query.filter_by(waiver_id="BVDW-TESTPDF1").first()

            self.assertIsNotNone(updated_waiver.signed_pdf_path)
            self.assertTrue(len(updated_doc.pdf_file_hash) > 0)

            # Cleanup
            db.session.delete(signed_doc)
            db.session.delete(waiver)
            db.session.delete(project)
            db.session.delete(prod)
            db.session.commit()


if __name__ == "__main__":
    unittest.main()
