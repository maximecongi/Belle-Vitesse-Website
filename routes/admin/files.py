from flask import Blueprint
from routes.public.shared_docs import handle_document_download

files_bp = Blueprint("admin_files", __name__)


# ── Distribution Sécurisée des Fichiers (Option A : Équipe BV ou Token HMAC/JWT) ──

@files_bp.route("/files/<path:filepath>", endpoint="serve_private_file")
def serve_private_file(filepath):
    return handle_document_download(filepath)


def init_files_routes(app):
    """Enregistre le blueprint des fichiers sécurisés (compatibilité ascendante)."""
    if "admin_files" not in app.blueprints:
        app.register_blueprint(files_bp)


