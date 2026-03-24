import os

from flask import current_app


def init_files_routes(app):
    # ── Distribution des Fichiers ─────────────────────────────────

    @app.route("/files/<path:filepath>")
    def serve_private_file(filepath):
        from flask import abort, send_from_directory
        output_base = current_app.config.get(
            "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

        # Distribution depuis le stockage hiérarchique
        if os.path.exists(os.path.join(output_base, filepath)):
            return send_from_directory(output_base, filepath)

        abort(404)
