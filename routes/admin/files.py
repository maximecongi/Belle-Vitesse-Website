from flask import current_app
import os


def init_files_routes(app):
    # ── File Serving ──────────────────────────────────────────────

    @app.route("/files/<path:filepath>")
    def serve_private_file(filepath):
        from flask import send_from_directory, abort
        output_base = current_app.config.get(
            "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

        # Serve from hierarchical storage
        if os.path.exists(os.path.join(output_base, filepath)):
            return send_from_directory(output_base, filepath)

        abort(404)
