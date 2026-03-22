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


if __name__ == "__main__":
    cleanup_empty_dirs()
