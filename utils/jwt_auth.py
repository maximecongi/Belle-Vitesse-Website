import jwt
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import request, jsonify, g, current_app
from models import User


JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 12


def _get_secret():
    return current_app.config["SECRET_KEY"]


def generate_token(user):
    """Generate a JWT token for a given User."""
    payload = {
        "user_id": user.id,
        "role": user.role or "User",
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _get_secret(), algorithm=JWT_ALGORITHM)


def decode_token(token):
    """Decode and validate a JWT token. Returns payload dict or None."""
    try:
        return jwt.decode(token, _get_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def require_api_auth(*allowed_roles):
    """
    Decorator for API routes. Validates JWT Bearer token and checks roles.
    On success, sets g.current_user (User instance) and g.api_user_role.
    Returns JSON 401/403 on failure.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "Token manquant ou invalide"}), 401

            token = auth_header.split("Bearer ")[-1]
            payload = decode_token(token)
            if not payload:
                return jsonify({"error": "Token expiré ou invalide"}), 401

            # Load user from DB
            from models import db
            user = db.session.get(User, payload["user_id"])
            if not user:
                return jsonify({"error": "Utilisateur introuvable"}), 401

            # Check role
            user_role = (user.role or "User").lower()
            allowed = [r.lower() for r in allowed_roles]
            if allowed and user_role not in allowed:
                return jsonify({"error": "Permissions insuffisantes"}), 403

            g.current_user = user
            g.api_user_role = user_role
            return f(*args, **kwargs)
        return decorated_function
    return decorator
