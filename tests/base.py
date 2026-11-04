"""
Classe de base unifiée pour l'ensemble des suites de tests unitaires et d'intégration.
Garantit l'isolation stricte en mémoire (sqlite:///:memory:), le mock global de WeasyPrint
et le nettoyage systématique de la base de données après chaque test (rollback & drop_all).
"""

import os
import sys
import unittest
from datetime import date
from unittest.mock import MagicMock

# 1. Configuration stricte de l'environnement de test
os.environ["FLASK_ENV"] = "testing"
os.environ["TESTING"] = "True"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["WTF_CSRF_ENABLED"] = "False"
os.environ["USE_SSH_TUNNEL"] = "false"

# 2. Mock Weasyprint global avant import de Flask
if "weasyprint" not in sys.modules:
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

from app import create_app  # noqa: E402
from models import Contact, Production, Project, User, db  # noqa: E402


class BaseTestCase(unittest.TestCase):
    """
    Classe de base pour tous les tests unitaires de Belle Vitesse ERP.
    """

    def setUp(self):
        """Initialise une application Flask et un schéma SQLite en mémoire isolé."""
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.client = self.app.test_client()

        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        """Nettoie intégralement la session et supprime les tables pour éviter toute fuite d'état."""
        try:
            db.session.rollback()
            db.session.remove()
            db.drop_all()
        except Exception:
            pass
        finally:
            self.app_context.pop()

    # ── Helpers Factory Prêts à l'Emploi ──────────────────────────

    def create_user(self, firstname="Jean", lastname="Dupont", mail="jean.dupont@bellevitesse.com", role="technicien"):
        """Crée et persiste un utilisateur de test."""
        user = User(
            firstname=firstname,
            lastname=lastname,
            mail=mail,
            role=role,
        )
        db.session.add(user)
        db.session.commit()
        return user

    def create_production(self, name="Production Test"):
        """Crée et persiste une société de production de test."""
        prod = Production(name=name)
        db.session.add(prod)
        db.session.commit()
        return prod

    def create_contact(self, production_id=None, first_name="Contact", last_name="Test", mail="contact@test.com", phone="0612345678"):
        """Crée et persiste un contact de production."""
        contact = Contact(
            first_name=first_name,
            last_name=last_name,
            mail=mail,
            phone=phone,
            production_id=production_id
        )
        db.session.add(contact)
        db.session.commit()
        return contact

    def create_project(self, name="Tournage Test", production_id=None, contact_id=None, departure_date=None, return_date=None, vehicles="1"):
        """Crée et persiste un projet de tournage avec dates et véhicules."""
        today = date.today()
        if production_id is None:
            prod = self.create_production()
            production_id = prod.id
        proj = Project(
            name=name,
            production_id=production_id,
            production_contact_id=contact_id,
            departure_date=departure_date or today,
            shoot_start_date=departure_date or today,
            shoot_end_date=return_date or today,
            return_date=return_date or today,
            vehicles_to_check=vehicles,
        )
        db.session.add(proj)
        db.session.commit()
        return proj

