import argparse
import gzip
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Setup path for local imports
_root = Path(__file__).parent.parent
sys.path.append(str(_root))

from utils.cron_helper import monitor_cron_job
from utils.ssh_helper import get_ssh_tunnel

try:
    from services.common.kdrive.client import KDriveClient
    from services.common.kdrive.config import (
        KDRIVE_ROOT_FOLDER_ID,
        KDRIVE_SQL_BACKUP_FOLDER_ID,
        KDRIVE_SQL_BACKUP_PATH,
    )
except ImportError:
    KDriveClient = None
    KDRIVE_ROOT_FOLDER_ID = 48
    KDRIVE_SQL_BACKUP_FOLDER_ID = 133270
    KDRIVE_SQL_BACKUP_PATH = "Common documents/BELLE VITESSE/6_VPS/1_BACKUPS_SQL"

# Load environment variables
load_dotenv(_root / '.env')

MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_DB = os.getenv("MYSQL_DATABASE")
BACKUP_RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))

# Add common Homebrew paths to PATH for mysqldump
os.environ["PATH"] += os.pathsep + "/opt/homebrew/bin" + os.pathsep + \
    "/usr/local/bin" + os.pathsep + "/opt/homebrew/Cellar/mysql-client/9.6.0/bin"

BACKUP_DIR = _root / "backups" / "sql"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def run_backup(host, port):
    """
    Exécute mysqldump avec compression gzip directe (niveau 9).
    Retourne le chemin du fichier compressé .sql.gz généré.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = BACKUP_DIR / f"dump_{timestamp}.sql.gz"

    cmd = [
        "mysqldump",
        f"-h{host}",
        f"-P{port}",
        f"-u{MYSQL_USER}",
        f"-p{MYSQL_PASSWORD}",
        "--skip-ssl" if os.getenv("FLASK_ENV") == "production" else "--ssl-mode=DISABLED",
        "--single-transaction",
        "--quick",
        MYSQL_DB
    ]

    print(f"📦 Démarrage de la sauvegarde MySQL vers {backup_file.name} via port {port}...")
    try:
        with gzip.open(backup_file, "wb", compresslevel=9) as gz_out:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            shutil.copyfileobj(proc.stdout, gz_out)
            stderr_output = proc.stderr.read().decode("utf-8", errors="ignore")
            proc.wait()

            if proc.returncode != 0:
                raise RuntimeError(
                    f"mysqldump a échoué avec le code {proc.returncode} : {stderr_output.strip()}"
                )

        file_size_kb = backup_file.stat().st_size / 1024
        print(f"✅ Sauvegarde locale compressée réussie ({file_size_kb:.1f} Ko) : {backup_file}")
        return backup_file
    except Exception as e:
        print(f"❌ Échec de la sauvegarde locale : {e}")
        if backup_file.exists():
            backup_file.unlink()
        raise


def sync_backup_to_kdrive(local_file: Path):
    """
    Téléverse l'archive compressée sur Infomaniak kDrive dans :
    Common documents/BELLE VITESSE/6_VPS/1_BACKUPS_SQL / YYYY-MM / dump_YYYY-MM-DD_HH-MM-SS.sql.gz
    """
    if not KDriveClient:
        print("ℹ️ Module KDriveClient non disponible, saut du transfert distant.")
        return None

    client = KDriveClient()
    if not client.token:
        print("ℹ️ Aucun token kDrive configuré (KDRIVE_API_TOKEN manquant), saut du transfert distant.")
        return None

    year_month = datetime.now().strftime("%Y-%m")

    try:
        print(f"☁️ Préparation du dossier de sauvegarde sur kDrive ({KDRIVE_SQL_BACKUP_PATH}/{year_month})...")
        # 1. Sous-dossier par mois (YYYY-MM) directement sous 1_BACKUPS_SQL
        month_dir = client.create_directory(
            parent_id=KDRIVE_SQL_BACKUP_FOLDER_ID,
            name=year_month
        )
        month_dir_id = month_dir.get("id")

        # 2. Upload du fichier .sql.gz
        with open(local_file, "rb") as f:
            file_bytes = f.read()

        file_size_kb = len(file_bytes) / 1024
        print(f"🚀 Upload de {local_file.name} vers kDrive ({file_size_kb:.1f} Ko)...")
        uploaded = client.upload(
            directory_id=month_dir_id,
            filename=local_file.name,
            content_bytes=file_bytes,
            conflict="replace"
        )
        print(f"✅ Sauvegarde synchronisée sur kDrive avec succès sous {KDRIVE_SQL_BACKUP_PATH}/{year_month}/ (ID: {uploaded.get('id')}) !")
        return uploaded
    except Exception as err:
        print(f"⚠️ Avertissement : Échec de la réplication sur kDrive ({err}). La sauvegarde locale est préservée.")
        return None


def purge_old_local_backups(retention_days: int = BACKUP_RETENTION_DAYS):
    """
    Supprime les fichiers de sauvegarde locaux (.sql ou .sql.gz) plus anciens que la durée de rétention.
    """
    now = datetime.now().timestamp()
    cutoff = now - (retention_days * 86400)
    purged = 0

    for f in BACKUP_DIR.glob("dump_*"):
        if f.is_file() and f.stat().st_mtime < cutoff:
            try:
                f.unlink()
                purged += 1
            except Exception as err:
                print(f"⚠️ Impossible de supprimer {f.name} : {err}")

    if purged > 0:
        print(f"🧹 Purge locale : {purged} ancienne(s) sauvegarde(s) supprimée(s) (> {retention_days} jours).")


def purge_old_kdrive_backups(retention_days: int = BACKUP_RETENTION_DAYS):
    """
    Supprime les sauvegardes SQL sur kDrive antérieures au seuil de rétention dans 6_VPS/1_BACKUPS_SQL/.
    """
    if not KDriveClient:
        return

    client = KDriveClient()
    if not client.token:
        return

    cutoff_date = datetime.now() - timedelta(days=retention_days)

    try:
        month_folders, _, _ = client.list_files(KDRIVE_SQL_BACKUP_FOLDER_ID)
        purged_kdrive = 0

        for m_folder in month_folders:
            if m_folder.get("type") != "dir":
                continue

            files, _, _ = client.list_files(m_folder["id"])
            for item in files:
                fname = item.get("name", "")
                match = re.match(r"dump_(\d{4}-\d{2}-\d{2})_\d{2}-\d{2}-\d{2}\.sql(?:\.gz)?", fname)
                if match:
                    try:
                        dump_date = datetime.strptime(match.group(1), "%Y-%m-%d")
                        if dump_date < cutoff_date:
                            client.delete(item["id"])
                            purged_kdrive += 1
                    except Exception:
                        pass

        if purged_kdrive > 0:
            print(f"🧹 Purge kDrive : {purged_kdrive} ancienne(s) archive(s) supprimée(s) (> {retention_days} jours).")
    except Exception as err:
        print(f"⚠️ Avertissement lors de la purge kDrive : {err}")


def main():
    parser = argparse.ArgumentParser(description="Sauvegarde SQL MySQL Belle Vitesse avec réplication kDrive.")
    parser.add_argument("--skip-kdrive", action="store_true", help="Désactive le téléversement sur kDrive.")
    parser.add_argument("--retention", type=int, default=BACKUP_RETENTION_DAYS, help="Durée de rétention en jours.")
    args = parser.parse_args()

    if not all([MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB]):
        print("❌ Variables d'environnement MySQL manquantes (MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE).")
        sys.exit(1)

    backup_file = None
    if os.getenv("FLASK_ENV", "production").lower() != "production":
        print("🔗 Ouverture éventuelle du tunnel SSH en environnement local...")
        tunnel, local_port = get_ssh_tunnel()
        if tunnel:
            backup_file = run_backup("127.0.0.1", local_port)
        else:
            print("⚠️ Tunnel SSH non disponible, tentative de connexion directe...")
            backup_file = run_backup(MYSQL_HOST, 3306)
    else:
        backup_file = run_backup(MYSQL_HOST, 3306)

    # Réplication sur kDrive si demandée
    if backup_file and not args.skip_kdrive:
        sync_backup_to_kdrive(backup_file)

    # Purge des anciennes sauvegardes
    purge_old_local_backups(args.retention)
    if not args.skip_kdrive:
        purge_old_kdrive_backups(args.retention)


if __name__ == "__main__":
    with monitor_cron_job("backup_sql"):
        main()
