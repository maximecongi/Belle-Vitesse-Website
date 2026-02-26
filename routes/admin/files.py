from flask import current_app


def init_files_routes(app):
    # ── File Serving ──────────────────────────────────────────────

    @app.route("/files/<path:filename>")
    def serve_private_file(filename):
        # We don't use @require_roles here so public signature pages can also see photos
        # (seal verification page).
        from flask import send_from_directory
        private_folder = current_app.config.get("PRIVATE_FOLDER")
        directory = private_folder / "uploads"
        return send_from_directory(directory, filename)
