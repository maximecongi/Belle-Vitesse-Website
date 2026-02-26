import os
from pathlib import Path

# Configurer ici le chemin vers votre dossier PRIVATE_FOLDER
# En production, cela correspond généralement à /app/private
# En local, vous pouvez pointer vers votre dossier de dev.

SEARCH_PATHS = [
    "/Users/maximecongi/kDrive/Common documents/BELLE VITESSE/2_WEBSITE/2_WEBSITE/uploads/checkins",
    "/Users/maximecongi/kDrive/Common documents/BELLE VITESSE/2_WEBSITE/2_WEBSITE/uploads/checkouts",
    "/app/private/uploads/checkins",
    "/app/private/uploads/checkouts"
]


def cleanup_empty_dirs():
    print("--- Nettoyage des dossiers vides ---")

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

                # Vérifier si le dossier est vide
                try:
                    if not any(dir_path.iterdir()):
                        print(f"🗑️ Suppression du dossier vide : {dir_path}")
                        dir_path.rmdir()
                        removed_count += 1
                except Exception as e:
                    print(f"❌ Erreur sur {dir_path} : {e}")

    print(f"\nTerminé. {removed_count} dossiers supprimés.")


if __name__ == "__main__":
    cleanup_empty_dirs()
