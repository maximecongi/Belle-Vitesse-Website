"""Middleware ASGI pur pour le serveur MCP (Rate Limiting, CORS, Auth Stricte & Sécurité)."""
import json
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs

from mcp_auth.auth import authenticate_mcp_token, McpUserContext
from mcp_server.config import (
    logger,
    MCP_RATE_LIMITER,
    MAX_MCP_REQUESTS_PER_MINUTE,
    ACTIVE_MCP_SESSIONS,
    MCP_FAILED_AUTH_IP,
    MCP_BANNED_IPS,
)
from mcp_server.context import CURRENT_MCP_USER, CURRENT_MCP_IP
from mcp_server.core import flask_app


class PureAsgiAuthMiddleware:
    """
    Middleware ASGI pur (sans BaseHTTPMiddleware) pour préserver le streaming HTTP (Streamable HTTP / SSE)
    sans altérer le protocole MCP ni provoquer d'erreur HTTP 501.
    Applique une politique de sécurité stricte Zero-Trust (Fail-Close) :
    toute requête non authentifiée sur les endpoints MCP est rejetée en HTTP 401.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            method = scope.get("method", "GET")

            # 1. Preflight CORS OPTIONS
            if method == "OPTIONS":
                response_headers = [
                    (b"access-control-allow-origin", b"*"),
                    (b"access-control-allow-methods", b"GET, POST, OPTIONS, PUT, DELETE"),
                    (b"access-control-allow-headers", b"Authorization, Content-Type, X-Requested-With, MCP-Protocol-Version"),
                ]
                await send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": response_headers,
                })
                await send({"type": "http.response.body", "body": b""})
                return

            # 2. Healthcheck public
            if path in ("/health", "/mcp/health"):
                try:
                    with flask_app.app_context():
                        from models import db
                        from sqlalchemy import text
                        db.session.execute(text("SELECT 1"))
                    body = json.dumps({"status": "healthy", "service": "BV-MCP"}).encode("utf-8")
                    status = 200
                except Exception as e:
                    body = json.dumps({"status": "unhealthy", "error": str(e)}).encode("utf-8")
                    status = 500

                await send({
                    "type": "http.response.start",
                    "status": status,
                    "headers": [(b"content-type", b"application/json"), (b"access-control-allow-origin", b"*")],
                })
                await send({"type": "http.response.body", "body": body})
                return

            headers_dict = dict(scope.get("headers", []))
            accept_header = headers_dict.get(b"accept", b"").decode("utf-8").lower()

            # 2.5 Navigateur direct sans en-tête SSE (page d'information publique)
            if method == "GET" and path in ("/mcp", "/mcp/") and "text/event-stream" not in accept_header and "application/x-ndjson" not in accept_header:
                body = json.dumps({
                    "status": "healthy",
                    "service": "BV-MCP",
                    "transport": "Streamable HTTP / SSE",
                    "endpoint": "https://team.bellevitesse.com/mcp",
                    "authentication_required": True,
                    "message": "Le serveur MCP est opérationnel et sécurisé. Connectez votre agent IA via Claude Web, Claude Code ou Cursor avec une clé API Bearer valide."
                }).encode("utf-8")
                await send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/json"), (b"access-control-allow-origin", b"*")],
                })
                await send({"type": "http.response.body", "body": body})
                return

            # 3. Extraction IP réelle (support Traefik, Nginx, Cloudflare)
            client_ip = "unknown"
            for header_name in (b"cf-connecting-ip", b"x-real-ip", b"x-forwarded-for"):
                header_val = headers_dict.get(header_name, b"").decode("utf-8").strip()
                if header_val:
                    client_ip = header_val.split(",")[0].strip()
                    break
            if client_ip == "unknown" and scope.get("client"):
                client_ip = scope["client"][0]

            now = time.time()

            # 3.1 Protection Anti-Brute-Force & Anti-Scan (IP Jail)
            if client_ip in MCP_BANNED_IPS:
                unban_time = MCP_BANNED_IPS[client_ip]
                if now < unban_time:
                    remaining_s = int(unban_time - now)
                    logger.warning(
                        f"⛔ Requête bloquée : IP {client_ip} temporairement bannie pour brute-force ({remaining_s}s restantes).")
                    body = json.dumps({
                        "status": "error",
                        "error_code": 429,
                        "message": f"⛔ Trop de tentatives d'authentification échouées. Votre adresse IP est temporairement bloquée pendant encore {remaining_s} secondes."
                    }).encode("utf-8")
                    await send({
                        "type": "http.response.start",
                        "status": 429,
                        "headers": [(b"content-type", b"application/json"), (b"access-control-allow-origin", b"*")],
                    })
                    await send({"type": "http.response.body", "body": body})
                    return
                else:
                    MCP_BANNED_IPS.pop(client_ip, None)
                    MCP_FAILED_AUTH_IP.pop(client_ip, None)

            query_string = scope.get("query_string", b"").decode("utf-8")
            query_params = parse_qs(query_string)
            session_id = query_params.get("session_id", [None])[0]

            # 4. Rate limiting par IP / Session
            rate_key = session_id or client_ip
            timestamps = [t for t in MCP_RATE_LIMITER[rate_key] if now - t < 60]
            MCP_RATE_LIMITER[rate_key] = timestamps

            if len(timestamps) >= MAX_MCP_REQUESTS_PER_MINUTE:
                logger.warning(f"⛔ Rate limit MCP dépassé pour {rate_key}.")
                body = json.dumps({
                    "status": "error",
                    "error_code": 429,
                    "message": "⛔ Rate limit dépassé (max 30 requêtes/min). Veuillez ralentir l'agent IA."
                }).encode("utf-8")
                await send({
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [(b"content-type", b"application/json"), (b"access-control-allow-origin", b"*")],
                })
                await send({"type": "http.response.body", "body": body})
                return

            MCP_RATE_LIMITER[rate_key].append(now)

            # 5. Extraction et validation stricte du Token MCP
            raw_token = None
            auth_header = headers_dict.get(b"authorization", b"").decode("utf-8")
            if auth_header and auth_header.startswith("Bearer "):
                raw_token = auth_header.split("Bearer ")[-1].strip()
            elif "token" in query_params:
                raw_token = query_params["token"][0]
            elif "api_key" in query_params:
                raw_token = query_params["api_key"][0]

            user = None
            if raw_token:
                with flask_app.app_context():
                    user = authenticate_mcp_token(raw_token)
                    if user and session_id:
                        ACTIVE_MCP_SESSIONS[session_id] = {
                            "user": user,
                            "token_id": getattr(user, "current_token_id", None),
                            "authenticated_at": now,
                            "last_seen": now,
                        }
            elif session_id and session_id in ACTIVE_MCP_SESSIONS:
                session_data = ACTIVE_MCP_SESSIONS[session_id]
                # Vérification TTL session (2 heures max d'inactivité)
                if isinstance(session_data, dict):
                    if now - session_data.get("last_seen", 0) < 7200:
                        # Kill-Switch : re-vérification en base du statut actif du token
                        token_id = session_data.get("token_id")
                        is_token_valid = True
                        if token_id:
                            with flask_app.app_context():
                                from models import McpApiToken
                                t_rec = McpApiToken.query.filter_by(id=token_id).first()
                                if not t_rec or not t_rec.is_active:
                                    is_token_valid = False
                                elif t_rec.expires_at:
                                    exp = t_rec.expires_at
                                    if exp.tzinfo is None:
                                        exp = exp.replace(tzinfo=timezone.utc)
                                    if exp < datetime.now(timezone.utc):
                                        is_token_valid = False

                        if is_token_valid:
                            session_data["last_seen"] = now
                            user = session_data["user"]
                        else:
                            logger.warning(
                                f"🛑 Kill-Switch déclenché : Session {session_id} révoquée (clé #{token_id} inactive ou expirée).")
                            ACTIVE_MCP_SESSIONS.pop(session_id, None)
                    else:
                        ACTIVE_MCP_SESSIONS.pop(session_id, None)
                else:
                    user = session_data

            # 6. Rejet strict HTTP 401 Unauthorized si non authentifié (Fail-Close)
            if not user:
                logger.warning(
                    f"⛔ Requête MCP non authentifiée ou token invalide [{method} {path}] depuis {client_ip}")

                # Enregistrement de l'échec pour la protection Anti-Brute-Force
                failures = [t for t in MCP_FAILED_AUTH_IP[client_ip] if now - t < 120]
                failures.append(now)
                MCP_FAILED_AUTH_IP[client_ip] = failures

                if len(failures) >= 5:
                    MCP_BANNED_IPS[client_ip] = now + 900  # Bannissement 15 minutes
                    logger.warning(
                        f"🚨 Bannissement temporaire (15 min) déclenché pour l'IP {client_ip} après 5 échecs consécutifs.")

                body = json.dumps({
                    "status": "error",
                    "error_code": 401,
                    "message": "⛔ Accès refusé : Authentification MCP requise. Veuillez fournir une clé API valide via l'en-tête 'Authorization: Bearer <votre_clé>' ou le paramètre '?token=<votre_clé>'."
                }).encode("utf-8")
                await send({
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"access-control-allow-origin", b"*"),
                        (b"www-authenticate", b'Bearer realm="BV-MCP"'),
                    ],
                })
                await send({"type": "http.response.body", "body": body})
                return

            # Authentification réussie : réinitialiser les échecs de cette IP
            MCP_FAILED_AUTH_IP.pop(client_ip, None)

            CURRENT_MCP_USER.set(user)
            CURRENT_MCP_IP.set(client_ip)
            flask_app.current_mcp_user = user
            flask_app.current_mcp_ip = client_ip
            logger.info(
                f"🔑 Connexion MCP autorisée : User #{getattr(user, 'id', 0)} ({getattr(user, 'mail', 'guest')}) [{method} {path}]")

        await self.app(scope, receive, send)
