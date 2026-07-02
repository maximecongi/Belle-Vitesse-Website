import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER")

# Dossiers à scanner pour le nettoyage
SEARCH_PATHS = []
if OUTPUT_FOLDER:
    SEARCH_PATHS.append(OUTPUT_FOLDER)


def cleanup_empty_dirs():
    print("--- Nettoyage des dossiers vides ---")
    start_time = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    print(f"Début du processus : {start_time}")
    print(f"Dossiers à scanner : {SEARCH_PATHS}")

    removed_count = 0

    for base_path_str in SEARCH_PATHS:
        base_path = Path(base_path_str)
        if not base_path.exists():
            continue
        print(f"Scanning : {base_path}")

        # On parcourt les dossiers d'inspection (topdown=False pour supprimer les enfants d'abord)
        for root, dirs, files in os.walk(base_path, topdown=False):
            for name in dirs:
                dir_path = Path(root) / name

                # Vérifier si le dossier est vide (en ignorant .DS_Store)
                try:
                    # On liste les entrées qui ne sont pas .DS_Store
                    content = [f for f in dir_path.iterdir() if f.name !=
                               ".DS_Store"]

                    if not content:
                        # Si le dossier est "vrai" vide ou ne contient que des .DS_Store
                        for ds_file in dir_path.glob(".DS_Store"):
                            ds_file.unlink()

                        print(f"🗑️ Suppression du dossier vide : {dir_path}")
                        dir_path.rmdir()
                        removed_count += 1
                except Exception as e:
                    print(f"❌ Erreur sur {dir_path} : {e}")

    print(f"\nTerminé. {removed_count} dossiers supprimés.")


def log_cron_status(job_name, status, error=None):
    import json
    from datetime import datetime, timezone
    from pathlib import Path

    possible_paths = [
        Path("/srv/bellevitesse/logs"),
        Path("/app/logs"),
        Path(__file__).parent.parent.parent / "logs",
        Path(__file__).parent.parent / "logs",
    ]
    logs_dir = None
    for p in possible_paths:
        if p.exists() and p.is_dir():
            logs_dir = p
            break

    if not logs_dir:
        logs_dir = Path(__file__).parent.parent / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

    status_file = logs_dir / "cron_status.json"

    data = {}
    if status_file.exists():
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    data[job_name] = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "error": error
    }

    try:
        temp_file = status_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        temp_file.replace(status_file)
    except Exception as e:
        print(f"Failed to write cron status for {job_name}: {e}")


if __name__ == "__main__":
    import traceback
    log_cron_status("cleanup_empty_folders_server", "running")
    try:
        cleanup_empty_dirs()
        log_cron_status("cleanup_empty_folders_server", "success")
    except Exception as e:
        tb = traceback.format_exc()
        log_cron_status("cleanup_empty_folders_server", "failed", error=tb)
        raise e
