import os
import tempfile
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

# Ensure testing env with sqlite before importing create_app
os.environ["FLASK_ENV"] = "testing"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["WTF_CSRF_ENABLED"] = "False"
os.environ["USE_SSH_TUNNEL"] = "false"

from app import create_app
from models.db import db
from models.kdrive import KDriveObject
from models.project import Production, Project
from services.common.kdrive.service import KDriveService


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


def test_ensure_project_tree(app_ctx):
    prod = Production(name="Marvel Studios")
    db.session.add(prod)
    db.session.flush()

    project = Project(
        name="Avengers Shoot",
        project_id="BVPR-AVENGERS",
        production_id=prod.id,
        departure_date=date(2026, 9, 20)
    )
    db.session.add(project)
    db.session.commit()

    mock_client = MagicMock()
    mock_client.create_directory.side_effect = lambda parent_id, name, relative_path=None: {
        "id": 1000 + len(name),
        "name": name
    }

    service = KDriveService(client=mock_client)
    folder_id = service.ensure_project_tree(project)

    assert folder_id is not None
    assert project.kdrive_folder_id == folder_id
    assert project.kdrive_sync_status == "synced"
    assert "Common documents/BELLE VITESSE/7_ADMINISTRATION/1_TOURNAGES/2026/09/MARVEL STUDIOS/AVENGERS SHOOT/BVPR-AVENGERS" in project.kdrive_path

    # Doit avoir appelé create_directory pour la racine et les sous-dossiers
    assert mock_client.create_directory.call_count >= 7


def test_upload_file_sync_and_idempotence(app_ctx):
    prod = Production(name="Universal")
    db.session.add(prod)
    db.session.flush()

    project = Project(
        name="Jurassic",
        project_id="BVPR-JURASSIC",
        production_id=prod.id,
        departure_date=date(2026, 8, 10)
    )
    db.session.add(project)
    db.session.commit()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(b"%PDF-1.4 test content")
        tmp_path = tmp.name

    try:
        mock_client = MagicMock()
        mock_client.get_file.return_value = {"id": 200, "status": "ok"}
        mock_client.create_directory.return_value = {"id": 200, "name": "test"}
        mock_client.upload.return_value = {"id": 9999, "name": os.path.basename(tmp_path)}

        service = KDriveService(client=mock_client)

        # 1er upload
        k_obj = service.upload_file_sync(
            project=project,
            entity_type="checkout",
            entity_id="BVCO-TEST",
            role="pdf",
            local_file_path=tmp_path,
            custom_filename="scelle.pdf"
        )

        assert k_obj.status == "synced"
        assert k_obj.kdrive_file_id == 9999
        assert mock_client.upload.call_count == 1

        # 2eme upload (Idempotence : ne doit pas ré-uploader)
        k_obj_2 = service.upload_file_sync(
            project=project,
            entity_type="checkout",
            entity_id="BVCO-TEST",
            role="pdf",
            local_file_path=tmp_path,
            custom_filename="scelle.pdf"
        )

        assert k_obj_2.id == k_obj.id
        assert mock_client.upload.call_count == 1  # toujours 1 seul appel !

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_move_project_folder(app_ctx):
    prod = Production(name="Pathé")
    db.session.add(prod)
    db.session.flush()

    project = Project(
        name="Projet Initial",
        project_id="BVPR-PATHE",
        production_id=prod.id,
        departure_date=date(2026, 6, 1),
        kdrive_folder_id=5000,
        kdrive_path="old/path"
    )
    db.session.add(project)
    db.session.commit()

    mock_client = MagicMock()
    mock_client.create_directory.return_value = {"id": 6000, "name": "PROJET RENOMME"}
    mock_client.move.return_value = {"cancel_id": "cancel-move-123"}

    service = KDriveService(client=mock_client)

    # Renommer le projet
    project.name = "Projet Renomme"
    db.session.commit()

    res = service.move_project_folder(
        project_id=project.id,
        old_year="2026",
        old_month="06",
        old_prod_name="Pathé",
        old_proj_name="Projet Initial"
    )

    assert res["cancel_id"] == "cancel-move-123"
    assert project.kdrive_last_cancel_id == "cancel-move-123"
    assert "PROJET RENOMME" in project.kdrive_path
    mock_client.move.assert_called_once_with(
        file_id=5000,
        destination_directory_id=6000,
        conflict="error"
    )


def test_delete_entity(app_ctx):
    prod = Production(name="Gaumont")
    db.session.add(prod)
    db.session.flush()

    project = Project(
        name="Fantomas",
        project_id="BVPR-FANTOMAS",
        production_id=prod.id,
        departure_date=date(2026, 5, 1)
    )
    db.session.add(project)
    db.session.flush()

    # Créer un KDriveObject en base
    k_obj = KDriveObject(
        project_id=project.id,
        entity_type="incident",
        entity_id="BVIC-999",
        role="pdf",
        source_key="incident_pdf.pdf",
        kdrive_file_id=111,
        kdrive_dir_id=222,
        status="synced"
    )
    db.session.add(k_obj)
    db.session.commit()

    mock_client = MagicMock()
    service = KDriveService(client=mock_client)

    success = service.delete_entity("incident", "BVIC-999")

    assert success is True
    mock_client.delete.assert_called_once_with(222)
    # L'objet doit être supprimé de la base
    assert KDriveObject.query.filter_by(entity_id="BVIC-999").count() == 0


def test_delete_project_folder(app_ctx):
    prod = Production(name="UGC")
    db.session.add(prod)
    db.session.flush()

    project = Project(
        name="Film UGC",
        project_id="BVPR-UGC-01",
        production_id=prod.id,
        departure_date=date(2026, 7, 1),
        kdrive_folder_id=7777,
        kdrive_sync_status="synced"
    )
    db.session.add(project)
    db.session.flush()

    k_obj = KDriveObject(
        project_id=project.id,
        entity_type="checkout",
        entity_id="BVCO-UGC",
        role="pdf",
        source_key="checkout.pdf",
        kdrive_file_id=8888,
        kdrive_dir_id=7777,
        status="synced"
    )
    db.session.add(k_obj)
    db.session.commit()

    mock_client = MagicMock()
    service = KDriveService(client=mock_client)

    success = service.delete_project_folder(project.id)

    assert success is True
    mock_client.delete.assert_called_once_with(7777)
    db.session.refresh(project)
    assert project.kdrive_folder_id is None
    assert project.kdrive_sync_status == "deleted"
    assert KDriveObject.query.filter_by(project_id=project.id).count() == 0


def test_delete_project_folder_with_upward_pruning(app_ctx):
    prod = Production(name="UGC")
    db.session.add(prod)
    db.session.flush()

    project = Project(
        name="Film UGC",
        project_id="BVPR-UGC-01",
        production_id=prod.id,
        departure_date=date(2026, 7, 1),
        kdrive_folder_id=7777,
        kdrive_sync_status="synced"
    )
    db.session.add(project)
    db.session.commit()

    mock_client = MagicMock()
    # 7777 has parent 6666 (Film UGC)
    # 6666 has parent 5555 (UGC)
    # 5555 has parent 48 (ROOT)
    mock_client.get_file.side_effect = lambda file_id: {
        7777: {"id": 7777, "name": "BVPR-UGC-01", "parent_id": 6666},
        6666: {"id": 6666, "name": "FILM UGC", "parent_id": 5555},
        5555: {"id": 5555, "name": "UGC", "parent_id": 48},
    }.get(file_id, {})

    # 6666 is empty, 5555 is not empty
    mock_client.list_files.side_effect = lambda file_id, limit=1: {
        6666: ([], None, False),  # empty -> delete!
        5555: ([{"id": 9999}], None, False),  # not empty -> STOP!
    }.get(file_id, ([], None, False))

    service = KDriveService(client=mock_client)
    success = service.delete_project_folder(project.id)

    assert success is True
    deleted_ids = [call.args[0] for call in mock_client.delete.call_args_list]
    assert deleted_ids == [7777, 6666]


def test_check_and_repair_project_structure(app_ctx):
    prod = Production(name="Pathé")
    db.session.add(prod)
    db.session.flush()

    project = Project(
        name="Projet Alpha",
        project_id="BVPR-ALPHA",
        production_id=prod.id,
        kdrive_folder_id=5000,
        kdrive_sync_status="synced"
    )
    db.session.add(project)
    db.session.commit()

    mock_client = MagicMock()
    # Cas 1 : Seuls quelques dossiers existent, 4_SÉCURITÉ existe mais manque de sous-dossiers
    mock_client.list_files.side_effect = lambda folder_id, limit=100: {
        5000: ([{"id": 5001, "name": "1_DEVIS", "type": "dir"},
                {"id": 5002, "name": "4_SÉCURITÉ", "type": "dir"}], None, False),
        5002: ([{"id": 5021, "name": "1_CHECKOUT", "type": "dir"}], None, False),
    }.get(folder_id, ([], None, False))

    mock_client.create_directory.side_effect = lambda parent_id, name: {"id": 9900 + len(name), "name": name}

    service = KDriveService(client=mock_client)

    # En dry-run : doit détecter les manquants sans appeler create_directory
    missing = service.check_and_repair_project_structure(project, dry_run=True)
    assert "2_FACTURES" in missing
    assert "3_LISTES" in missing
    assert "5_BTS" in missing
    assert "6_INCIDENTS" in missing
    assert "4_SÉCURITÉ/2_DÉCHARGE_PILOTE" in missing
    assert "4_SÉCURITÉ/3_DÉCHARGE_PRODUCTION" in missing
    assert "4_SÉCURITÉ/4_CHECKIN" in missing
    assert mock_client.create_directory.call_count == 0

    # En mode réel : doit créer les manquants
    repaired = service.check_and_repair_project_structure(project, dry_run=False)
    assert len(repaired) == 7
    assert mock_client.create_directory.call_count == 7


def test_upload_bundle_sync(app_ctx, tmp_path):
    prod = Production(name="Warner")
    db.session.add(prod)
    db.session.flush()

    project = Project(
        name="Batman",
        project_id="BVPR-BATMAN",
        production_id=prod.id,
        kdrive_folder_id=8888,
        kdrive_sync_status="synced"
    )
    db.session.add(project)
    db.session.commit()

    # Créer deux fichiers temporaires
    f1 = tmp_path / "incident.pdf"
    f1.write_bytes(b"%PDF-test")
    f2 = tmp_path / "photo.png"
    f2.write_bytes(b"\x89PNG-test")

    mock_client = MagicMock()
    mock_client.create_directory.return_value = {"id": 9999}
    mock_client.upload.return_value = {"id": 12345}

    service = KDriveService(client=mock_client)

    file_specs = [
        {"role": "pdf", "path": str(f1), "filename": "incident.pdf"},
        {"role": "photo", "path": str(f2), "filename": "photo.png"},
    ]

    results = service.upload_bundle_sync(
        project_id=project.id,
        entity_type="incident",
        entity_id="BVIC-TEST-123",
        file_specs=file_specs,
    )

    assert len(results) == 2
    assert all(r.status == "synced" for r in results)
    assert KDriveObject.query.filter_by(entity_id="BVIC-TEST-123").count() == 2


