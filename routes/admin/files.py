from flask import current_app
import os
from pathlib import Path


def init_files_routes(app):
    # ── File Serving ──────────────────────────────────────────────

    @app.route("/files/<path:filepath>")
    def serve_private_file(filepath):
        from flask import send_from_directory
        output_base = current_app.config.get(
            "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))
        private_folder = current_app.config.get("PRIVATE_FOLDER")

        # Heuristic: if it contains 1_SÉCURITÉ or starts with a year, it's new
        if "1_SÉCURITÉ" in filepath or (filepath.count('/') >= 2 and filepath.split('/')[0].isdigit()):
            return send_from_directory(output_base, filepath)
        else:
            # Legacy: relative to uploads/
            directory = Path(private_folder) / "uploads"
            return send_from_directory(directory, filepath)
