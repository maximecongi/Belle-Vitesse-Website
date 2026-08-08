from datetime import datetime
from flask import Blueprint, jsonify, render_template, request, session, flash, redirect, url_for
from models import McpApiToken, db
from utils.decorators import require_roles

mcp_tokens_bp = Blueprint("admin_mcp_tokens", __name__, url_prefix="/admin/mcp-connector")


def _ensure_scope_column_exists():
    """Vérifie et ajoute automatiquement la colonne 'scope' dans mcp_api_tokens si elle manque."""
    try:
        from sqlalchemy import text
        db.session.execute(text("ALTER TABLE mcp_api_tokens ADD COLUMN scope VARCHAR(20) NOT NULL DEFAULT 'read_only'"))
        db.session.commit()
    except Exception:
        db.session.rollback()


def _ensure_audit_table_exists():
    """Vérifie et crée automatiquement la table mcp_audit_logs si elle manque."""
    try:
        from sqlalchemy import text
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS mcp_audit_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                token_id INT NULL,
                tool_name VARCHAR(100) NOT NULL,
                arguments_json TEXT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'success',
                error_message TEXT NULL,
                ip_address VARCHAR(45) NULL,
                execution_time_ms INT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX ix_mcp_audit_logs_user_id (user_id),
                INDEX ix_mcp_audit_logs_token_id (token_id),
                INDEX ix_mcp_audit_logs_tool_name (tool_name),
                INDEX ix_mcp_audit_logs_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """))
        db.session.commit()
    except Exception:
        db.session.rollback()


@mcp_tokens_bp.route("", methods=["GET"])
@require_roles("user", "commercial", "manager", "administrator", "super administrator")
def mcp_connector_page():
    user_id = session.get("admin_user_id")
    user_role = (session.get("admin_user_role") or "").lower()

    if not user_role and user_id:
        try:
            from models import User
            u = db.session.get(User, user_id)
            if u and u.role:
                user_role = u.role.lower()
        except Exception:
            pass

    tokens = []
    try:
        tokens = McpApiToken.query.filter_by(user_id=user_id).order_by(McpApiToken.created_at.desc()).all()
    except Exception:
        db.session.rollback()
        _ensure_scope_column_exists()
        try:
            tokens = McpApiToken.query.filter_by(user_id=user_id).order_by(McpApiToken.created_at.desc()).all()
        except Exception:
            db.session.rollback()
            tokens = []

    audit_logs = []
    if user_role == "super administrator":
        try:
            from models import McpAuditLog
            audit_logs = McpAuditLog.query.order_by(McpAuditLog.created_at.desc()).limit(50).all()
        except Exception:
            db.session.rollback()
            _ensure_audit_table_exists()
            try:
                from models import McpAuditLog
                audit_logs = McpAuditLog.query.order_by(McpAuditLog.created_at.desc()).limit(50).all()
            except Exception:
                db.session.rollback()
                audit_logs = []

    return render_template("admin/mcp_connector.html", tokens=tokens, audit_logs=audit_logs)






@mcp_tokens_bp.route("/api/tokens", methods=["GET"])
@require_roles("user", "commercial", "manager", "administrator", "super administrator")
def list_tokens():
    user_id = session.get("admin_user_id")
    try:
        tokens = McpApiToken.query.filter_by(user_id=user_id).order_by(McpApiToken.created_at.desc()).all()
    except Exception:
        db.session.rollback()
        _ensure_scope_column_exists()
        tokens = McpApiToken.query.filter_by(user_id=user_id).order_by(McpApiToken.created_at.desc()).all()

    return jsonify({"tokens": [t.to_dict() for t in tokens]})



@mcp_tokens_bp.route("/generate", methods=["POST"])
@require_roles("user", "commercial", "manager", "administrator", "super administrator")
def generate_token():
    user_id = session.get("admin_user_id")
    name = None
    if request.is_json and request.json:
        name = request.json.get("name")
    if not name:
        name = request.form.get("name")
    name = (name or "Mon Agent IA").strip()[:100]

    scope = None
    if request.is_json and request.json:
        scope = request.json.get("scope")
    if not scope:
        scope = request.form.get("scope")
    if scope not in ("read_only", "write", "admin"):
        scope = "read_only"

    raw_token = McpApiToken.generate_token_raw()
    token_prefix = raw_token[:12] + "..."
    token_hash = McpApiToken.hash_token(raw_token)

    token_record = McpApiToken(
        user_id=user_id,
        name=name,
        token_prefix=token_prefix,
        token_hash=token_hash,
        scope=scope,
        is_active=True,
    )

    db.session.add(token_record)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        try:
            from sqlalchemy import text
            db.session.execute(text("ALTER TABLE mcp_api_tokens ADD COLUMN scope VARCHAR(20) NOT NULL DEFAULT 'read_only'"))
            db.session.commit()
            db.session.add(token_record)
            db.session.commit()
        except Exception as retry_err:
            db.session.rollback()
            raise retry_err


    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "status": "success",
            "token": token_record.to_dict(),
            "raw_token": raw_token,
            "message": "Token généré avec succès. Conservez-le précieusement, il ne sera plus réaffiché !"
        }), 201

    flash("Token généré avec succès.", "success")
    return redirect(url_for("admin_mcp_tokens.mcp_connector_page"))


@mcp_tokens_bp.route("/<int:token_id>/revoke", methods=["POST"])
@require_roles("user", "commercial", "manager", "administrator", "super administrator")
def revoke_token(token_id):
    user_id = session.get("admin_user_id")
    token_rec = db.session.get(McpApiToken, token_id)

    if not token_rec or token_rec.user_id != user_id:
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "error", "message": "Token introuvable"}), 404
        flash("Token introuvable", "error")
        return redirect(url_for("admin_mcp_tokens.mcp_connector_page"))

    token_rec.is_active = not token_rec.is_active
    db.session.commit()

    status_str = "activé" if token_rec.is_active else "révoqué"
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"status": "success", "message": f"Token {status_str} avec succès.", "is_active": token_rec.is_active})

    flash(f"Token {status_str} avec succès.", "success")
    return redirect(url_for("admin_mcp_tokens.mcp_connector_page"))


@mcp_tokens_bp.route("/<int:token_id>/delete", methods=["POST", "DELETE"])
@require_roles("user", "commercial", "manager", "administrator", "super administrator")
def delete_token(token_id):
    user_id = session.get("admin_user_id")
    token_rec = db.session.get(McpApiToken, token_id)

    if not token_rec or token_rec.user_id != user_id:
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "error", "message": "Token introuvable"}), 404
        flash("Token introuvable", "error")
        return redirect(url_for("admin_mcp_tokens.mcp_connector_page"))

    db.session.delete(token_rec)
    db.session.commit()

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"status": "success", "message": "Token supprimé avec succès."})

    flash("Token supprimé avec succès.", "success")
    return redirect(url_for("admin_mcp_tokens.mcp_connector_page"))

