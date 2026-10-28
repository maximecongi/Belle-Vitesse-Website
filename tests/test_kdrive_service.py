from services.common.kdrive.service import KDriveService
from services.common.kdrive.config import KDRIVE_BASE_PATH, KDRIVE_ROOT_FOLDER_ID
from models.project import Production, Project
from models.kdrive import KDriveObject
from models.db import db
from app import create_app
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
    assert f"{KDRIVE_BASE_PATH}/2026/09/MARVEL STUDIOS/AVENGERS SHOOT/BVPR-AVENGERS" in project.kdrive_path

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
        mock_client.upload.return_value = {
            "id": 9999, "name": os.path.basename(tmp_path)}

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
    mock_client.create_directory.return_value = {
        "id": 6000, "name": "PROJET RENOMME"}
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


def test_delete_entity_cgl_polymorphic(app_ctx):
    """Vérifie que delete_entity normalise 'cgl_waiver' -> 'cgl', retrouve le parent BVRA et purge la DB."""
    from models.waiver import CglWaiver

    prod = Production(name="Production CGL")
    db.session.add(prod)
    db.session.flush()

    project = Project(
        name="Tournage Pub",
        project_id="BVPR-PUB",
        production_id=prod.id,
        departure_date=date(2026, 6, 1),
        kdrive_folder_id=5000,
    )
    db.session.add(project)
    db.session.flush()

    cgl = CglWaiver(
        waiver_id="BVRA-POLY-123",
        project_id=project.id,
        project_name="Tournage Pub",
        production_name="Production CGL",
    )
    db.session.add(cgl)
    db.session.flush()

    # KDriveObject stocké comme cgl (ex: pdf dans 1_CGL)
    k_obj1 = KDriveObject(
        project_id=project.id,
        entity_type="cgl",
        entity_id="BVRA-POLY-123",
        role="pdf",
        source_key="cgl.pdf",
        kdrive_file_id=1111,
        kdrive_dir_id=2222,  # sous-dossier 1_CGL
        status="synced"
    )
    # KDriveObject avec alias cgl_waiver (compatibilité historique)
    k_obj2 = KDriveObject(
        project_id=project.id,
        entity_type="cgl_waiver",
        entity_id="BVRA-POLY-123",
        role="insurance",
        source_key="attestation.pdf",
        kdrive_file_id=3333,
        kdrive_dir_id=4444,  # sous-dossier 2_ATTESTATION_ASSURANCE
        status="synced"
    )
    db.session.add_all([k_obj1, k_obj2])
    db.session.commit()

    mock_client = MagicMock()
    # Le sous-dossier 2222 a pour parent 9999 nommé 'BVRA-POLY-123'
    # Le sous-dossier 4444 a pour parent 9999 nommé 'BVRA-POLY-123'
    mock_client.get_file.side_effect = lambda file_id: {
        2222: {"id": 2222, "name": "1_CGL", "parent_id": 9999},
        4444: {"id": 4444, "name": "2_ATTESTATION_ASSURANCE", "parent_id": 9999},
        9999: {"id": 9999, "name": "BVRA-POLY-123", "parent_id": 5000},
    }.get(file_id, {})

    service = KDriveService(client=mock_client)

    # Appel avec le type cgl_waiver
    success = service.delete_entity("cgl_waiver", "BVRA-POLY-123")

    assert success is True
    # Le dossier racine 9999 du CGL doit avoir été supprimé
    assert 9999 in [call.args[0] for call in mock_client.delete.call_args_list]
    # Les deux KDriveObjects doivent avoir été supprimés
    assert KDriveObject.query.filter_by(entity_id="BVRA-POLY-123").count() == 0


def test_delete_entity_safety_rules_tree_fallback(app_ctx):
    """Vérifie que delete_entity retrouve le dossier sur kDrive même en l'absence de KDriveObject en base."""
    from models.waiver import SafetyRulesWaiver

    prod = Production(name="Prod Action")
    db.session.add(prod)
    db.session.flush()

    project = Project(
        name="Projet Cascade",
        project_id="BVPR-CASCADE",
        production_id=prod.id,
        departure_date=date(2026, 7, 10),
        kdrive_folder_id=7000,
    )
    db.session.add(project)
    db.session.flush()

    sr = SafetyRulesWaiver(
        waiver_id="BVSR-FALLBACK-789",
        project_id=project.id,
        project_name="Projet Cascade",
        production_name="Prod Action",
    )
    db.session.add(sr)
    db.session.commit()

    mock_client = MagicMock()
    # ensure_directory_path pour 4_SÉCURITÉ/2_RÈGLES_SÉCURITÉ retourne 7200
    mock_client.create_directory.return_value = {
        "id": 7200, "name": "2_RÈGLES_SÉCURITÉ"}
    # get_child_by_name dans 7200 pour 'BVSR-FALLBACK-789' retourne le dossier 7250
    mock_client.get_child_by_name.side_effect = lambda parent_id, name: {
        (7200, "BVSR-FALLBACK-789"): {"id": 7250, "name": "BVSR-FALLBACK-789", "type": "dir"},
    }.get((parent_id, name), None)

    service = KDriveService(client=mock_client)

    success = service.delete_entity("safety_rules", "BVSR-FALLBACK-789")

    assert success is True
    mock_client.delete.assert_called_once_with(7250)


def test_clean_orphaned_documents_script(app_ctx):
    """Vérifie que la fonction du script CLI détecte et nettoie les documents supprimés."""
    from datetime import datetime, timezone
    from models.waiver import CglWaiver
    from scripts.clean_orphaned_kdrive_docs import clean_orphaned_documents

    prod = Production(name="Prod Script Test")
    db.session.add(prod)
    db.session.flush()

    project = Project(
        name="Projet Test Cleanup",
        project_id="BVPR-CLEANUP",
        production_id=prod.id,
        departure_date=date(2026, 8, 1),
        kdrive_folder_id=8000,
    )
    db.session.add(project)
    db.session.flush()

    # CGL marqué comme supprimé (deleted_at != None)
    cgl_deleted = CglWaiver(
        waiver_id="BVRA-ORPHAN-1",
        project_id=project.id,
        project_name="Projet Test Cleanup",
        production_name="Prod Script Test",
        deleted_at=datetime.now(timezone.utc),
    )
    db.session.add(cgl_deleted)
    db.session.commit()

    with patch("services.common.kdrive.service.KDriveService.delete_entity") as mock_delete:
        mock_delete.return_value = True

        # Mode simulation (dry-run) : ne doit PAS appeler delete_entity
        clean_orphaned_documents(filter_type="cgl", dry_run=True)
        mock_delete.assert_not_called()

        # Mode réel (--force) : doit appeler delete_entity avec ('cgl', 'BVRA-ORPHAN-1')
        clean_orphaned_documents(filter_type="cgl", dry_run=False)
        mock_delete.assert_called_once_with("cgl", "BVRA-ORPHAN-1")


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
    # 7777 has parent 6666 (Film UGC)
    # 6666 has parent 5555 (UGC)
    # 5555 has parent KDRIVE_ROOT_FOLDER_ID (ROOT)
    mock_client.get_file.side_effect = lambda file_id: {
        7777: {"id": 7777, "name": "BVPR-UGC-01", "parent_id": 6666},
        6666: {"id": 6666, "name": "FILM UGC", "parent_id": 5555},
        5555: {"id": 5555, "name": "UGC", "parent_id": KDRIVE_ROOT_FOLDER_ID},
    }.get(file_id, {})

    # 6666 is empty, 5555 is not empty
    mock_client.list_files.side_effect = lambda file_id, limit=5, **kwargs: {
        6666: ([], None, False),  # empty -> delete!
        5555: ([{"id": 9999}], None, False),  # not empty -> STOP!
    }.get(file_id, ([], None, False))

    service = KDriveService(client=mock_client)
    success = service.delete_project_folder(project.id)

    assert success is True
    deleted_ids = [call.args[0] for call in mock_client.delete.call_args_list]
    assert deleted_ids == [7777, 6666]


def test_delete_project_folder_pruning_all_the_way_to_root(app_ctx):
    """
    Vérifie la remontée complète lorsque tous les dossiers parents sont vides :
    BVPR-SOLO -> PROJET -> PROD -> MOIS -> ANNÉE -> ARRÊT (KDRIVE_ROOT_FOLDER_ID préservé).
    """
    prod = Production(name="SoloProd")
    db.session.add(prod)
    db.session.flush()

    project = Project(
        name="Solo Project",
        project_id="BVPR-SOLO",
        production_id=prod.id,
        departure_date=date(2026, 12, 1),
        kdrive_folder_id=7001,
        kdrive_sync_status="synced"
    )
    db.session.add(project)
    db.session.commit()

    mock_client = MagicMock()
    # 7001 (BVPR-SOLO) -> 6001 (SOLO PROJECT) -> 5001 (SOLOPROD) -> 4001 (12) -> 3001 (2026) -> ROOT
    mock_client.get_file.side_effect = lambda file_id: {
        7001: {"id": 7001, "name": "BVPR-SOLO", "parent_id": 6001},
        6001: {"id": 6001, "name": "SOLO PROJECT", "parent_id": 5001},
        5001: {"id": 5001, "name": "SOLOPROD", "parent_id": 4001},
        4001: {"id": 4001, "name": "12", "parent_id": 3001},
        3001: {"id": 3001, "name": "2026", "parent_id": KDRIVE_ROOT_FOLDER_ID},
    }.get(file_id, {})

    # Tous les dossiers parents sont vides
    mock_client.list_files.side_effect = lambda file_id, limit=5, **kwargs: (
        [], None, False)

    service = KDriveService(client=mock_client)
    success = service.delete_project_folder(project.id)

    assert success is True
    deleted_ids = [call.args[0] for call in mock_client.delete.call_args_list]
    # Tous les parents vides ont été supprimés
    assert deleted_ids == [7001, 6001, 5001, 4001, 3001]
    # Le dossier racine KDRIVE_ROOT_FOLDER_ID n'a JAMAIS été supprimé
    assert KDRIVE_ROOT_FOLDER_ID not in deleted_ids


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
        5002: ([{"id": 5021, "name": "1_CHECKOUTS", "type": "dir"}], None, False),
    }.get(folder_id, ([], None, False))

    mock_client.create_directory.side_effect = lambda parent_id, name: {
        "id": 9900 + len(name), "name": name}

    service = KDriveService(client=mock_client)

    # En dry-run : doit détecter les manquants sans appeler create_directory
    missing = service.check_and_repair_project_structure(project, dry_run=True)
    assert "2_FACTURES" in missing
    assert "3_LISTES" in missing
    assert "5_BTS" in missing
    assert "6_INCIDENTS" in missing
    assert "4_SÉCURITÉ/2_RÈGLES_SÉCURITÉ" in missing
    assert "4_SÉCURITÉ/3_CGL" in missing
    assert "4_SÉCURITÉ/4_ATTESTATIONS_PILOTES" in missing
    assert "4_SÉCURITÉ/5_CHECKINS" in missing
    assert mock_client.create_directory.call_count == 0

    # En mode réel : doit créer les manquants
    repaired = service.check_and_repair_project_structure(
        project, dry_run=False)
    assert len(repaired) == 8
    assert mock_client.create_directory.call_count == 8


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


def test_rename_production_folders_direct(app_ctx):
    """Teste le renommage direct kDrive d'une production lorsqu'aucune collision n'existe."""
    prod = Production(name="NOUVEAU_NOM_PROD")
    db.session.add(prod)
    db.session.flush()

    project = Project(
        name="Projet Alpha",
        project_id="BVPR-ALPHA",
        production_id=prod.id,
        kdrive_folder_id=777,
        departure_date=date(2026, 9, 20),
        kdrive_path="10_TOURNAGES/2026/09 - SEPTEMBRE/ANCIEN_NOM/PROJET_ALPHA/BVPR-ALPHA"
    )
    db.session.add(project)
    db.session.commit()

    mock_client = MagicMock()
    # Simuler 10_TOURNAGES contenant 2026, qui contient 09 - SEPTEMBRE
    mock_client.list_files.side_effect = lambda folder_id, limit=50: {
        KDRIVE_ROOT_FOLDER_ID: ([{"id": 2026, "name": "2026", "type": "dir"}], None, False),
        2026: ([{"id": 909, "name": "09 - SEPTEMBRE", "type": "dir"}], None, False),
    }.get(folder_id, ([], None, False))

    # Dans 09 - SEPTEMBRE, l'ancien dossier existe (ID=555), mais pas le nouveau
    def mock_get_child(parent_id, name, *args, **kwargs):
        if parent_id == 909 and name == "ANCIEN_NOM":
            return {"id": 555, "name": "ANCIEN_NOM", "type": "dir"}
        return None

    mock_client.get_child_by_name.side_effect = mock_get_child

    service = KDriveService(client=mock_client)
    res = service.rename_production_folders("ANCIEN_NOM", "NOUVEAU_NOM_PROD")

    assert res["renamed"] == 1
    assert res["merged"] == 0
    assert res["total"] == 1

    # Vérifier l'appel à client.rename
    mock_client.rename.assert_called_once_with(555, "NOUVEAU_NOM_PROD")
    mock_client.move.assert_not_called()

    # Vérifier que le kdrive_path du projet en BDD a été mis à jour
    updated_project = db.session.get(Project, project.id)
    assert "NOUVEAU_NOM_PROD" in updated_project.kdrive_path


def test_rename_production_folders_collision(app_ctx):
    """Teste le renommage kDrive d'une production avec collision (fusion du contenu et suppression de l'ancien dossier)."""
    mock_client = MagicMock()
    mock_client.list_files.side_effect = lambda folder_id, limit=50: {
        KDRIVE_ROOT_FOLDER_ID: ([{"id": 2026, "name": "2026", "type": "dir"}], None, False),
        2026: ([{"id": 909, "name": "09 - SEPTEMBRE", "type": "dir"}], None, False),
        555: ([{"id": 888, "name": "PROJET_ALPHA", "type": "dir"}], None, False),
    }.get(folder_id, ([], None, False))

    # Les deux dossiers existent (collision)
    def mock_get_child(parent_id, name, *args, **kwargs):
        if parent_id == 909 and name == "ANCIEN_NOM":
            return {"id": 555, "name": "ANCIEN_NOM", "type": "dir"}
        if parent_id == 909 and name == "NOUVEAU_NOM":
            return {"id": 666, "name": "NOUVEAU_NOM", "type": "dir"}
        return None

    mock_client.get_child_by_name.side_effect = mock_get_child

    service = KDriveService(client=mock_client)
    res = service.rename_production_folders("ANCIEN_NOM", "NOUVEAU_NOM")

    assert res["renamed"] == 0
    assert res["merged"] == 1
    assert res["total"] == 1

    # Doit avoir déplacé le projet dans le dossier existant (ID 666) puis supprimé l'ancien dossier 555
    mock_client.move.assert_called_once_with(888, 666, conflict="error")
    mock_client.delete.assert_called_once_with(555)
    mock_client.rename.assert_not_called()


def test_rename_production_folders_case_insensitivity_and_uppercase(app_ctx):
    """Vérifie que la recherche trouve les dossiers en majuscules sur kDrive et renomme en UPPERCASE."""
    prod = Production(name="Academy films international")
    db.session.add(prod)
    db.session.flush()

    project = Project(
        name="Pub Nike",
        project_id="BVPR-NIKE",
        production_id=prod.id,
        kdrive_folder_id=1234,
        departure_date=date(2026, 9, 20),
        kdrive_path="10_TOURNAGES/2026/09 - SEPTEMBRE/ACADEMY FILMS/PUB_NIKE/BVPR-NIKE"
    )
    db.session.add(project)
    db.session.commit()

    mock_client = MagicMock()
    mock_client.list_files.side_effect = lambda folder_id, limit=50: {
        KDRIVE_ROOT_FOLDER_ID: ([{"id": 2026, "name": "2026", "type": "dir"}], None, False),
        2026: ([{"id": 909, "name": "09 - SEPTEMBRE", "type": "dir"}], None, False),
    }.get(folder_id, ([], None, False))

    # Sur kDrive, le dossier existe en UPPERCASE : "ACADEMY FILMS"
    def mock_get_child(parent_id, name, case_insensitive=False):
        if parent_id == 909 and (name == "ACADEMY FILMS" or (case_insensitive and name.lower() == "academy films")):
            return {"id": 111, "name": "ACADEMY FILMS", "type": "dir"}
        return None

    mock_client.get_child_by_name.side_effect = mock_get_child

    service = KDriveService(client=mock_client)
    # L'utilisateur renomme "Academy films" -> "Academy films international"
    res = service.rename_production_folders(
        "Academy films", "Academy films international")

    assert res["renamed"] == 1
    assert res["merged"] == 0

    # Vérifie que rename a été appelé avec le nouveau nom en MAJUSCULES
    mock_client.rename.assert_called_once_with(
        111, "ACADEMY FILMS INTERNATIONAL")

    # Vérifie que le kdrive_path a été mis à jour avec le nom en majuscules
    updated_project = db.session.get(Project, project.id)
    assert "ACADEMY FILMS INTERNATIONAL" in updated_project.kdrive_path
