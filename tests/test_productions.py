import os
from unittest.mock import patch

import pytest

# Ensure testing env with sqlite before importing create_app
os.environ["FLASK_ENV"] = "testing"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["WTF_CSRF_ENABLED"] = "False"
os.environ["USE_SSH_TUNNEL"] = "false"

from app import create_app
from models.db import db
from models.project import Production, Project
from services.admin.productions import (
    create_production,
    delete_production,
    get_production_for_edit,
    list_productions,
    update_production,
)


@pytest.fixture
def app_ctx():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_create_and_list_production(app_ctx):
    form_data = {
        "name": "Acme Films",
        "address": "123 Rue du Cinéma",
        "email": "contact@acme.com",
        "phone": "0123456789",
    }
    success = create_production(form_data)
    assert success is True

    prods = list_productions()
    assert len(prods) == 1
    assert prods[0]["name"] == "Acme Films"
    assert prods[0]["address"] == "123 Rue du Cinéma"
    assert prods[0]["email"] == "contact@acme.com"


def test_get_production_for_edit(app_ctx):
    prod = Production(name="Studio Test", address="Paris", mail="test@studio.com", phone="0600000000")
    db.session.add(prod)
    db.session.commit()

    data = get_production_for_edit(prod.id)
    assert data is not None
    assert data["name"] == "Studio Test"
    assert data["address"] == "Paris"
    assert data["email"] == "test@studio.com"
    assert data["phone"] == "0600000000"


def test_update_production_without_name_change(app_ctx):
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
        assert res.get("success") is True
        assert res.get("renamed_kdrive") is False
        mock_dispatch.assert_not_called()

    # Vérifie la mise à jour en base
    updated = db.session.get(Production, prod.id)
    assert updated.address == "Nouvelle adresse"
    assert updated.mail == "prod@orig.com"


def test_update_production_with_name_change_triggers_kdrive(app_ctx):
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
        assert res.get("success") is True
        assert res.get("renamed_kdrive") is True
        mock_dispatch.assert_called_once_with("Ancien Nom", "Nouveau Nom")

    updated = db.session.get(Production, prod.id)
    assert updated.name == "Nouveau Nom"


def test_delete_production(app_ctx):
    prod = Production(name="To Delete")
    db.session.add(prod)
    db.session.commit()

    res = delete_production(prod.id)
    assert res is True
    assert db.session.get(Production, prod.id) is None
