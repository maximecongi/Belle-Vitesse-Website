import gzip
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import scripts.backup_sql as backup_module


class BackupSQLTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.backup_dir = Path(self.temp_dir.name)
        # Patch du dossier BACKUP_DIR
        self.orig_backup_dir = backup_module.BACKUP_DIR
        backup_module.BACKUP_DIR = self.backup_dir

    def tearDown(self):
        backup_module.BACKUP_DIR = self.orig_backup_dir
        self.temp_dir.cleanup()

    @patch("subprocess.Popen")
    def test_run_backup_creates_valid_gzip(self, mock_popen):
        """Vérifie que run_backup produit bien un fichier .sql.gz lisible et valide."""
        dummy_sql = b"CREATE TABLE test (id INT); INSERT INTO test VALUES (1);\n"

        # Simuler le processus mysqldump
        mock_proc = MagicMock()
        mock_proc.stdout.read = MagicMock(side_effect=[dummy_sql, b""])
        mock_proc.stderr.read.return_value = b""
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        # Exécuter la sauvegarde
        with patch.object(backup_module, "MYSQL_USER", "user"), \
             patch.object(backup_module, "MYSQL_PASSWORD", "pass"), \
             patch.object(backup_module, "MYSQL_DB", "bellevitesse"):
            result_file = backup_module.run_backup("127.0.0.1", 3306)

        self.assertTrue(result_file.exists())
        self.assertTrue(result_file.name.endswith(".sql.gz"))

        # Décompresser pour vérifier le contenu
        with gzip.open(result_file, "rb") as gz_in:
            decompressed = gz_in.read()
            self.assertEqual(decompressed, dummy_sql)

    def test_purge_old_local_backups(self):
        """Vérifie que les archives locales antérieures au seuil de rétention sont supprimées."""
        now = datetime.now().timestamp()
        old_time = now - (35 * 86400)   # 35 jours avant
        recent_time = now - (5 * 86400) # 5 jours avant

        old_file = self.backup_dir / "dump_2026-08-01_04-00-00.sql.gz"
        recent_file = self.backup_dir / "dump_2026-10-05_04-00-00.sql.gz"

        old_file.write_bytes(b"old")
        recent_file.write_bytes(b"recent")

        os.utime(old_file, (old_time, old_time))
        os.utime(recent_file, (recent_time, recent_time))

        backup_module.purge_old_local_backups(retention_days=30)

        self.assertFalse(old_file.exists())
        self.assertTrue(recent_file.exists())

    @patch("scripts.backup_sql.KDriveClient")
    def test_sync_backup_to_kdrive(self, mock_client_cls):
        """Vérifie l'arborescence kDrive et le téléversement de l'archive SQL sous 6_VPS/1_BACKUPS_SQL."""
        mock_client = MagicMock()
        mock_client.token = "fake_kdrive_token"
        mock_client.create_directory.return_value = {"id": 1002, "name": "2026-10"}
        mock_client.upload.return_value = {"id": 9999, "name": "dump_test.sql.gz"}
        mock_client_cls.return_value = mock_client

        dummy_file = self.backup_dir / "dump_2026-10-10_04-00-00.sql.gz"
        dummy_file.write_bytes(b"compressed_data")

        res = backup_module.sync_backup_to_kdrive(dummy_file)

        self.assertIsNotNone(res)
        self.assertEqual(res["id"], 9999)
        self.assertEqual(mock_client.create_directory.call_count, 1)
        mock_client.upload.assert_called_once()

    @patch("scripts.backup_sql.KDriveClient")
    def test_purge_old_kdrive_backups(self, mock_client_cls):
        """Vérifie la détection et la suppression des anciennes archives sur kDrive."""
        mock_client = MagicMock()
        mock_client.token = "fake_kdrive_token"
        mock_client.list_files.side_effect = [
            # 1. Mois sous 1_BACKUPS_SQL
            ([{"id": 2001, "name": "2026-08", "type": "dir"}], None, False),
            # 2. Fichiers sous 2026-08
            ([
                {"id": 3001, "name": "dump_2026-08-01_04-00-00.sql.gz", "type": "file"},
                {"id": 3002, "name": "dump_2026-10-09_04-00-00.sql.gz", "type": "file"},
            ], None, False),
        ]
        mock_client_cls.return_value = mock_client

        backup_module.purge_old_kdrive_backups(retention_days=30)

        # Seul le dump du 2026-08-01 doit être supprimé (> 30 jours)
        mock_client.delete.assert_called_once_with(3001)


if __name__ == "__main__":
    unittest.main()
