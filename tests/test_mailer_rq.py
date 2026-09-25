import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from app import create_app
from models.db import db
from services.common.mailer_tasks import dispatch_email, task_send_email
from services.common.redis_queue import (
    clear_redis_cache,
    get_redis_connection,
    get_rq_queue,
)
from utils.mailer import EmailService


class MailerRQTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app_context = self.app.app_context()
        self.app_context.push()
        clear_redis_cache()

    def tearDown(self):
        clear_redis_cache()
        self.app_context.pop()

    @patch("utils.mailer.EmailService._send_smtp_message", return_value=True)
    def test_sync_execution_in_testing_mode(self, mock_send_smtp):
        """Vérifie qu'en mode test (ou sync=True), l'envoi s'exécute de façon synchrone."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp_file:
            tmp_file.write(b"Test attachment content")
            tmp_file_path = tmp_file.name

        try:
            ok = EmailService.send_templated_email(
                to_email="test.client@example.com",
                subject="Test Synchrone",
                template_name="emails/magic_link.html",
                context={"firstname": "Jean", "magic_link": "https://example.com/magic"},
                text_content="Texte alternatif brut",
                sender_type="admin",
                cc=["copy@example.com"],
                attachments=[tmp_file_path],
                extra_headers={"X-Test-Id": "12345"},
                sync=True,
            )

            self.assertTrue(ok)
            mock_send_smtp.assert_called_once()
            msg = mock_send_smtp.call_args[0][0]
            recipients = mock_send_smtp.call_args[0][1]

            self.assertEqual(msg["Subject"], "Test Synchrone")
            self.assertEqual(msg["To"], "test.client@example.com")
            self.assertEqual(msg["Cc"], "copy@example.com")
            self.assertEqual(msg["X-Test-Id"], "12345")
            self.assertIn("test.client@example.com", recipients)
            self.assertIn("copy@example.com", recipients)
        finally:
            if os.path.exists(tmp_file_path):
                os.remove(tmp_file_path)

    @patch("services.common.mailer_tasks.get_rq_queue")
    def test_async_dispatch_enqueues_to_rq(self, mock_get_rq_queue):
        """Vérifie que dispatch_email enfile le job dans la queue RQ 'emails' hors testing."""
        mock_queue = MagicMock()
        mock_job = MagicMock()
        mock_job.id = "rq-job-abc-123"
        mock_queue.enqueue.return_value = mock_job
        mock_get_rq_queue.return_value = mock_queue

        with patch.dict(os.environ, {"FLASK_ENV": "production", "TESTING": "False"}):
            self.app.config["TESTING"] = False
            self.app.testing = False

            ok = dispatch_email(
                to_email="client@production.com",
                subject="Test RQ Enqueue",
                html_content="<p>Corps HTML</p>",
                text_content="Corps texte",
                sender_type="contact",
                cc="admin@example.com",
                attachments=None,
                extra_headers={"X-Priority": "1"},
                timeout=15,
                sync=False,
            )

            self.assertTrue(ok)
            mock_get_rq_queue.assert_called_with("emails")
            mock_queue.enqueue.assert_called_once()
            args, kwargs = mock_queue.enqueue.call_args
            self.assertEqual(args[0], "services.common.mailer_tasks.task_send_email")
            self.assertEqual(kwargs["to_email"], "client@production.com")
            self.assertEqual(kwargs["subject"], "Test RQ Enqueue")
            self.assertEqual(kwargs["html_content"], "<p>Corps HTML</p>")
            self.assertEqual(kwargs["text_content"], "Corps texte")
            self.assertEqual(kwargs["sender_type"], "contact")
            self.assertEqual(kwargs["cc"], "admin@example.com")
            self.assertEqual(kwargs["extra_headers"], {"X-Priority": "1"})

    @patch("services.common.mailer_tasks.get_rq_queue", return_value=None)
    @patch("threading.Thread.start")
    def test_async_dispatch_falls_back_to_daemon_thread_when_redis_unavailable(
        self, mock_thread_start, mock_get_rq_queue
    ):
        """Vérifie le repli automatique sur un thread daemon lorsque Redis est indisponible."""
        with patch.dict(os.environ, {"FLASK_ENV": "production", "TESTING": "False"}):
            self.app.config["TESTING"] = False
            self.app.testing = False

            ok = dispatch_email(
                to_email="thread.fallback@example.com",
                subject="Test Thread Fallback",
                html_content="<p>Test Thread</p>",
                text_content="Test Thread",
                sender_type="contact",
                sync=False,
            )

            self.assertTrue(ok)
            mock_thread_start.assert_called_once()

    @patch("utils.mailer.EmailService._send_smtp_message", return_value=True)
    def test_task_send_email_executes_correctly(self, mock_send_smtp):
        """Vérifie l'exécution directe de task_send_email avec construction MIME."""
        result = task_send_email(
            to_email="worker.target@example.com",
            subject="Job RQ Exécuté",
            html_content="<h1>Message HTML</h1>",
            text_content="Message texte",
            sender_type="admin",
            cc=["admin1@example.com", "admin2@example.com"],
            extra_headers={"X-Custom": "Value"},
            timeout=20,
        )

        self.assertTrue(result)
        mock_send_smtp.assert_called_once()
        msg = mock_send_smtp.call_args[0][0]
        recipients = mock_send_smtp.call_args[0][1]

        self.assertEqual(msg["Subject"], "Job RQ Exécuté")
        self.assertEqual(msg["To"], "worker.target@example.com")
        self.assertEqual(msg["Cc"], "admin1@example.com, admin2@example.com")
        self.assertEqual(msg["X-Custom"], "Value")
        self.assertEqual(
            recipients,
            ["worker.target@example.com", "admin1@example.com", "admin2@example.com"],
        )

    def test_build_mime_message_structure(self):
        """Vérifie la bonne construction de l'objet MIME avec et sans pièces jointes."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            tmp_pdf.write(b"%PDF-1.4 test payload")
            tmp_pdf_path = tmp_pdf.name

        try:
            msg = EmailService.build_mime_message(
                to_email="test.mime@example.com",
                subject="Sujet MIME",
                html_content="<p>Contenu HTML</p>",
                text_content="Contenu texte",
                cc=["copy1@example.com", "copy2@example.com"],
                attachments=[tmp_pdf_path, "/non/existent/path.pdf"],
                extra_headers={"X-Mime-Test": "Passed"},
            )

            self.assertEqual(msg["Subject"], "Sujet MIME")
            self.assertEqual(msg["To"], "test.mime@example.com")
            self.assertEqual(msg["Cc"], "copy1@example.com, copy2@example.com")
            self.assertEqual(msg["X-Mime-Test"], "Passed")
            self.assertTrue(msg.is_multipart())
        finally:
            if os.path.exists(tmp_pdf_path):
                os.remove(tmp_pdf_path)

    @patch("services.common.redis_queue.Redis")
    def test_redis_queue_provider(self, mock_redis_cls):
        """Vérifie la mise en cache et la récupération des connexions Redis et files RQ."""
        mock_redis_instance = MagicMock()
        mock_redis_instance.ping.return_value = True
        mock_redis_cls.return_value = mock_redis_instance

        clear_redis_cache()
        conn1 = get_redis_connection(db_index=1)
        conn2 = get_redis_connection(db_index=1)
        self.assertIs(conn1, conn2)
        mock_redis_instance.ping.assert_called_once()

        q_emails = get_rq_queue("emails")
        self.assertIsNotNone(q_emails)
        self.assertEqual(q_emails.name, "emails")

        # Test failure handling: ping raises Exception
        clear_redis_cache()
        mock_failing_redis = MagicMock()
        mock_failing_redis.ping.side_effect = ConnectionError("Redis unreachable")
        mock_redis_cls.return_value = mock_failing_redis

        conn_failed = get_redis_connection(db_index=2)
        self.assertIsNone(conn_failed)
        q_failed = get_rq_queue("emails", db_index=2)
        self.assertIsNone(q_failed)


if __name__ == "__main__":
    unittest.main()
