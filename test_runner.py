import os
import sys
import unittest

# 1. Isolation complète de l'environnement de test (SQLite in-memory, aucun tunnel SSH/MySQL)
os.environ["FLASK_ENV"] = "testing"
os.environ["TESTING"] = "True"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["USE_SSH_TUNNEL"] = "false"
os.environ["WTF_CSRF_ENABLED"] = "False"

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# 2. Mock weasyprint avant l'importation de l'application Flask
from unittest.mock import MagicMock
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint


class DualStream:
    """Diffuse la sortie des tests à la fois sur stdout et dans le fichier de log."""

    def __init__(self, file_stream, console_stream):
        self.file_stream = file_stream
        self.console_stream = console_stream

    def write(self, data):
        self.file_stream.write(data)
        self.console_stream.write(data)

    def flush(self):
        self.file_stream.flush()
        self.console_stream.flush()


# 3. Découverte et exécution de l'intégralité des tests
suite = unittest.defaultTestLoader.discover('tests')
with open('test_results.txt', 'w') as f:
    dual_stream = DualStream(f, sys.stdout)
    runner = unittest.TextTestRunner(stream=dual_stream, verbosity=2)
    result = runner.run(suite)

    if result.errors:
        f.write("\n=== DETAILED ERRORS ===\n")
        for err in result.errors:
            f.write(f"\nERROR in {err[0]}:\n{err[1]}\n")

    if result.failures:
        f.write("\n=== DETAILED FAILURES ===\n")
        for fail in result.failures:
            f.write(f"\nFAIL in {fail[0]}:\n{fail[1]}\n")

# 4. Code de retour conforme pour l'intégration continue (CI)
sys.exit(0 if result.wasSuccessful() else 1)
