from flask import Blueprint, jsonify, request

from extensions import limiter
from models import User, db
from services.common.auth import request_magic_link, verify_magic_link
from utils.jwt_auth import generate_token, require_api_auth

api_auth_bp = Blueprint("api_auth", __name__)


@api_auth_bp.route("/auth/login", methods=["POST"])
@limiter.limit("20 per minute")
def api_login():
    """Send a magic link to the user's email."""
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    if not email:
        return jsonify({"error": "L'adresse email est requise."}), 400

    if request_magic_link(email):
        return jsonify({"message": "Un lien de connexion a été envoyé par email."})
    else:
        return jsonify({"error": "Email non reconnu ou erreur d'envoi."}), 400


@api_auth_bp.route("/auth/verify/<token>", methods=["GET"])
def api_verify_magic_link(token):
    """Verify a magic link and return a JWT."""
    user_data = verify_magic_link(token)
    if not user_data:
        return jsonify({"error": "Lien de connexion invalide ou expiré."}), 401

    user = db.session.get(User, user_data["id"])
    if not user:
        return jsonify({"error": "Utilisateur introuvable."}), 404

    jwt_token = generate_token(user)
    return jsonify({
        "token": jwt_token,
        "user": user.to_dict(),
    })


@api_auth_bp.route("/auth/me", methods=["GET"])
@require_api_auth()
def api_me():
    """Return the current user's profile."""
    from flask import g
    return jsonify(g.current_user.to_dict())
