"""PyTest Global Configuration & Isolation.

Assure l'isolation hermétique de l'ensemble des suites de tests en mémoire (SQLite),
désactive le mode CSRF et les connexions réseau distantes (SSH/MySQL/Airtable/kDrive),
et applique un mock WeasyPrint préventif pour les environnements headless.
"""
import os
import sys
from unittest.mock import MagicMock

# 1. Isolation complète de l'environnement de test (SQLite in-memory, aucun tunnel SSH/MySQL)
os.environ["FLASK_ENV"] = "testing"
os.environ["TESTING"] = "True"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["USE_SSH_TUNNEL"] = "false"
os.environ["WTF_CSRF_ENABLED"] = "False"

# 2. Mock préventif de WeasyPrint pour les environnements de test headless sans libgobject
if "weasyprint" not in sys.modules:
    mock_weasyprint = MagicMock()
    mock_html_inst = MagicMock()
    mock_html_inst.write_pdf.return_value = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
        b"0000000115 00000 n \ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
    )
    mock_weasyprint.HTML.return_value = mock_html_inst
    mock_weasyprint.CSS = MagicMock()
    sys.modules["weasyprint"] = mock_weasyprint

