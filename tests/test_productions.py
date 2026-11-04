from unittest.mock import patch
from tests.base import BaseTestCase
from models.db import db
from models.project import Production
from services.admin.productions import (
    create_production,
    delete_production,
    get_production_for_edit,
    list_productions,
    update_production,
)


class ProductionsServiceTest(BaseTestCase):
    """Suite de tests unitaires pour le service de gestion des productions."""

    def test_create_and_list_production(self):
        form_data = {
            "name": "Acme Films",
            "address": "123 Rue du Cinéma",
            "email": "contact@acme.com",
            "phone": "0123456789",
        }
        success = create_production(form_data)
        self.assertTrue(success)

        prods = list_productions()
        self.assertEqual(len(prods), 1)
        self.assertEqual(prods[0]["name"], "Acme Films")
        self.assertEqual(prods[0]["address"], "123 Rue du Cinéma")
        self.assertEqual(prods[0]["email"], "contact@acme.com")

    def test_get_production_for_edit(self):
        prod = Production(name="Studio Test", address="Paris", mail="test@studio.com", phone="0600000000")
        db.session.add(prod)
        db.session.commit()

        data = get_production_for_edit(prod.id)
        self.assertIsNotNone(data)
        self.assertEqual(data["name"], "Studio Test")
        self.assertEqual(data["address"], "Paris")
        self.assertEqual(data["email"], "test@studio.com")
        self.assertEqual(data["phone"], "0600000000")

    def test_update_production_without_name_change(self):
        prod = Production(name="Original Prod", address="Ancienne adresse")
        db.session.add(prod)
        db.session.commit()

        with patch("services.admin.productions.dispatch_rename_production") as mock_dispatch:
            form_data = {
                "name": "Original Prod",
                "address": "Nouvelle adresse",
                "email": "prod@orig.com",
                "phone": "0102030405",
            }
            res = update_production(prod.id, form_data)
            self.assertTrue(res.get("success"))
            self.assertFalse(res.get("renamed_kdrive"))
            mock_dispatch.assert_not_called()

        updated = db.session.get(Production, prod.id)
        self.assertEqual(updated.address, "Nouvelle adresse")
        self.assertEqual(updated.mail, "prod@orig.com")

    def test_update_production_with_name_change_triggers_kdrive(self):
        prod = Production(name="Ancien Nom", address="Adresse")
        db.session.add(prod)
        db.session.commit()

        with patch("services.admin.productions.dispatch_rename_production") as mock_dispatch:
            form_data = {
                "name": "Nouveau Nom",
                "address": "Adresse",
                "email": "contact@new.com",
                "phone": "0102030405",
            }
            res = update_production(prod.id, form_data)
            self.assertTrue(res.get("success"))
            self.assertTrue(res.get("renamed_kdrive"))
            mock_dispatch.assert_called_once_with("Ancien Nom", "Nouveau Nom")

        updated = db.session.get(Production, prod.id)
        self.assertEqual(updated.name, "Nouveau Nom")

    def test_delete_production(self):
        prod = Production(name="To Delete")
        db.session.add(prod)
        db.session.commit()

        res = delete_production(prod.id)
        self.assertTrue(res)
        self.assertIsNone(db.session.get(Production, prod.id))
