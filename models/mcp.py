import hashlib
import secrets
from datetime import datetime, timezone

from models.db import db, _utcnow


class McpApiToken(db.Model):
    """Token API personnel pour l'accès MCP."""
    __tablename__ = "mcp_api_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)        # Ex: "Mon MacBook", "Claude Desktop"
    token_prefix = db.Column(db.String(30), nullable=False) # Ex: "bv_mcp_a1b2..."
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True) # SHA-256
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    last_used_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)

    scope = db.Column(db.String(20), default="read_only", nullable=False) # 'read_only', 'write', 'admin'

    user = db.relationship("User", backref=db.backref("mcp_tokens", lazy=True, cascade="all, delete-orphan"))

    @staticmethod
    def generate_token_raw():
        """Génère une chaîne de token brute aléatoire sécurisée."""
        random_part = secrets.token_hex(24) # 48 chars
        return f"bv_mcp_{random_part}"

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """Calcule le hash SHA-256 d'un token brut."""
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "token_prefix": self.token_prefix,
            "scope": self.scope or "read_only",
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    def __repr__(self):
        return f"<McpApiToken id={self.id} user_id={self.user_id} name={self.name} active={self.is_active}>"
