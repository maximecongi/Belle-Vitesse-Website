import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock weasyprint
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from app import create_app
from models import db, Project, Production, AppSetting
from services.admin.utils import handle_admin_service_error
from services.admin.projects import create_project
from services.admin.project_reports import add_project_report


class TransactionRollbackTest(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        os.environ["WTF_CSRF_ENABLED"] = "False"
        os.environ["USE_SSH_TUNNEL"] = "false"

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_handle_admin_service_error_decorator_rolls_back(self):
        """Vérifie que le décorateur handle_admin_service_error rollback la session sur exception."""
        with self.app.app_context():
            @handle_admin_service_error
            def faulty_mutation():
                # Add a dummy setting without committing
                s = AppSetting(key="pending_rollback_key", value="temp")
                db.session.add(s)
                db.session.flush()
                # Confirm it is in the session
                self.assertIn(s, db.session)
                # Raise an error to trigger decorator rollback
                raise RuntimeError("Simulation d'erreur fatale")

            with patch.object(db.session, 'rollback', wraps=db.session.rollback) as spy_rollback:
                with self.assertRaises(RuntimeError):
                    faulty_mutation()
                # Verify rollback was called
                spy_rollback.assert_called_once()

            # Verify that the session is clean (no uncommitted dirty objects)
            self.assertEqual(len(db.session.dirty), 0)
            self.assertEqual(len(db.session.new), 0)
            self.assertIsNone(AppSetting.query.filter_by(key="pending_rollback_key").first())

    def test_create_project_rollback_on_failure(self):
        """Vérifie que create_project rollback systématiquement en cas d'échec de commit."""
        with self.app.app_context():
            prod = Production(name="Test Production")
            db.session.add(prod)
            db.session.commit()

            form = {
                "name": "Projet Crash Test",
                "production_id": str(prod.id),
            }
            with patch.object(db.session, 'commit', side_effect=Exception("DB Commit Failure")):
                with patch.object(db.session, 'rollback', wraps=db.session.rollback) as spy_rollback:
                    with self.assertRaises(Exception):
                        create_project(form)
                    spy_rollback.assert_called()

            # Session is clean
            self.assertEqual(len(db.session.dirty), 0)
            self.assertEqual(len(db.session.new), 0)

    def test_add_project_report_rollback_on_failure(self):
        """Vérifie que add_project_report rollback systématiquement en cas d'échec."""
        with self.app.app_context():
            prod = Production(name="Test Production")
            db.session.add(prod)
            db.session.flush()

            p = Project(name="Test Project", production_id=prod.id)
            db.session.add(p)
            db.session.commit()

            with patch.object(db.session, 'commit', side_effect=Exception("DB Failure")):
                with patch.object(db.session, 'rollback', wraps=db.session.rollback) as spy_rollback:
                    with self.assertRaises(Exception):
                        add_project_report(p.id, None, "Contenu du rapport", title="Titre")
                    spy_rollback.assert_called()

            self.assertEqual(len(db.session.dirty), 0)
            self.assertEqual(len(db.session.new), 0)

    def test_teardown_request_rolls_back_on_unhandled_exception(self):
        """Vérifie que le teardown_request global rollback une session dirty si une exception non gérée survient."""
        with self.app.app_context():
            prod = Production(name="Crash Prod")
            db.session.add(prod)
            db.session.commit()
            prod_id = prod.id

        @self.app.route("/test-crash")
        def crash_route():
            p = Project(name="Crash Route Dirty Project", production_id=prod_id)
            db.session.add(p)
            # Ne fait pas commit, simule un crash
            raise RuntimeError("Crash in route")

        with patch.object(db.session, 'rollback', wraps=db.session.rollback) as spy_rollback:
            with self.assertRaises(RuntimeError):
                self.client.get("/test-crash")
            spy_rollback.assert_called()

        with self.app.app_context():
            self.assertIsNone(Project.query.filter_by(name="Crash Route Dirty Project").first())


if __name__ == '__main__':
    unittest.main()
