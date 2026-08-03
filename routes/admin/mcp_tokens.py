from datetime import datetime
from flask import Blueprint, jsonify, request, session, flash, redirect, url_for
from models import McpApiToken, db
from utils.decorators import require_roles

mcp_tokens_bp = Blueprint("admin_mcp_tokens", __name__, url_prefix="/admin/settings/mcp-tokens")


@mcp_tokens_bp.route("", methods=["GET"])
@require_roles("user", "commercial", "manager", "administrator", "super administrator")
def list_tokens():
    user_id = session.get("admin_user_id")
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

    raw_token = McpApiToken.generate_token_raw()
    token_prefix = raw_token[:12] + "..."
    token_hash = McpApiToken.hash_token(raw_token)

    token_record = McpApiToken(
        user_id=user_id,
        name=name,
        token_prefix=token_prefix,
        token_hash=token_hash,
        is_active=True,
    )

    db.session.add(token_record)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        # Auto-fix : augmenter automatiquement la colonne en base de données si elle était en VARCHAR(12)
        try:
            from sqlalchemy import text
            db.session.execute(text("ALTER TABLE mcp_api_tokens MODIFY token_prefix VARCHAR(30) NOT NULL"))
            db.session.commit()
            # Réessayer l'insertion
            db.session.add(token_record)
            db.session.commit()
        except Exception as retry_err:
            db.session.rollback()
            raise retry_err

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "status": "success",
            "token": token_record.to_dict(),
            "raw_token": raw_token,  # Contenu affiché UNE SEULE FOIS à l'utilisateur
            "message": "Token généré avec succès. Conservez-le précieusement, il ne sera plus réaffiché !"
        }), 201

    flash("Token généré avec succès. Copiez le token : " + raw_token, "success")
    return redirect(url_for("admin_settings.admin_settings_edit"))


@mcp_tokens_bp.route("/<int:token_id>/revoke", methods=["POST"])
@require_roles("user", "commercial", "manager", "administrator", "super administrator")
def revoke_token(token_id):
    user_id = session.get("admin_user_id")
    token_rec = db.session.get(McpApiToken, token_id)

    if not token_rec or token_rec.user_id != user_id:
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "error", "message": "Token introuvable"}), 404
        flash("Token introuvable", "error")
        return redirect(url_for("admin_settings.admin_settings_edit"))

    token_rec.is_active = not token_rec.is_active
    db.session.commit()

    status_str = "activé" if token_rec.is_active else "révoqué"
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"status": "success", "message": f"Token {status_str} avec succès.", "is_active": token_rec.is_active})

    flash(f"Token {status_str} avec succès.", "success")
    return redirect(url_for("admin_settings.admin_settings_edit"))


@mcp_tokens_bp.route("/<int:token_id>/delete", methods=["POST", "DELETE"])
@require_roles("user", "commercial", "manager", "administrator", "super administrator")
def delete_token(token_id):
    user_id = session.get("admin_user_id")
    token_rec = db.session.get(McpApiToken, token_id)

    if not token_rec or token_rec.user_id != user_id:
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "error", "message": "Token introuvable"}), 404
        flash("Token introuvable", "error")
        return redirect(url_for("admin_settings.admin_settings_edit"))

    db.session.delete(token_rec)
    db.session.commit()

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"status": "success", "message": "Token supprimé avec succès."})

    flash("Token supprimé avec succès.", "success")
    return redirect(url_for("admin_settings.admin_settings_edit"))
