from routes.public.shared_docs import handle_document_download


def init_files_routes(app):
    # ── Distribution Sécurisée des Fichiers (Option A : Équipe BV ou Token HMAC/JWT) ──

    @app.route("/files/<path:filepath>")
    def serve_private_file(filepath):
        return handle_document_download(filepath)

