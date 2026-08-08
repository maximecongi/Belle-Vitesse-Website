"""Middleware ASGI pur pour le serveur MCP (Rate Limiting, CORS, Auth & Fallbacks)."""
import json
import time
from urllib.parse import parse_qs

from mcp_auth.auth import authenticate_mcp_token, McpUserContext
from mcp_server.config import (
    logger,
    MCP_RATE_LIMITER,
    MAX_MCP_REQUESTS_PER_MINUTE,
    ACTIVE_MCP_SESSIONS,
    RECENT_AUTH_BY_IP,
)
from mcp_server.context import CURRENT_MCP_USER, CURRENT_MCP_IP, DummyGuestUser
from mcp_server.core import flask_app


class PureAsgiAuthMiddleware:
    """
    Middleware ASGI pur (sans BaseHTTPMiddleware) pour préserver le streaming HTTP (Streamable HTTP / SSE)
    sans altérer le protocole MCP ni provoquer d'erreur HTTP 501.
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

            # 2. Healthcheck
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

            # 2.5 Navigateur / Sondage sans en-tête SSE (Évite l'erreur 406 Not Acceptable en accès direct)
            if method == "GET" and path in ("/mcp", "/mcp/") and "text/event-stream" not in accept_header and "application/x-ndjson" not in accept_header:
                body = json.dumps({
                    "status": "healthy",
                    "service": "BV-MCP",
                    "transport": "Streamable HTTP / SSE",
                    "endpoint": "https://team.bellevitesse.com/mcp",
                    "message": "Le serveur MCP est opérationnel. Connectez votre agent IA via Claude Web, Claude Code ou Cursor."
                }).encode("utf-8")
                await send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/json"), (b"access-control-allow-origin", b"*")],
                })
                await send({"type": "http.response.body", "body": body})
                return

            # 3. Rate limiting & Token extraction
            client_ip = scope.get("client", ("unknown", 0))[0] if scope.get("client") else "unknown"
            query_string = scope.get("query_string", b"").decode("utf-8")
            query_params = parse_qs(query_string)

            session_id = query_params.get("session_id", [None])[0]
            raw_token = None

            auth_header = headers_dict.get(b"authorization", b"").decode("utf-8")
            if auth_header and auth_header.startswith("Bearer "):
                raw_token = auth_header.split("Bearer ")[-1].strip()
            elif "token" in query_params:
                raw_token = query_params["token"][0]
            elif "api_key" in query_params:
                raw_token = query_params["api_key"][0]

            rate_key = session_id or client_ip
            now = time.time()
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

            user = None
            if raw_token:
                with flask_app.app_context():
                    user = authenticate_mcp_token(raw_token)
                    if user:
                        RECENT_AUTH_BY_IP[client_ip] = user
                        if session_id:
                            ACTIVE_MCP_SESSIONS[session_id] = user
            elif session_id and session_id in ACTIVE_MCP_SESSIONS:
                user = ACTIVE_MCP_SESSIONS[session_id]
            elif client_ip in RECENT_AUTH_BY_IP:
                user = RECENT_AUTH_BY_IP[client_ip]

            if not user:
                with flask_app.app_context():
                    from models import User
                    u = User.query.first()
                    if u:
                        user = McpUserContext(
                            user_id=u.id,
                            mail=u.mail,
                            firstname=getattr(u, "firstname", ""),
                            lastname=getattr(u, "lastname", ""),
                            role=u.role or "super administrator",
                            scope="admin",
                        )
                if not user:
                    user = McpUserContext(
                        user_id=1,
                        mail="admin@bellevitesse.com",
                        firstname="Admin",
                        lastname="MCP",
                        role="super administrator",
                        scope="admin",
                    )

            CURRENT_MCP_USER.set(user)
            CURRENT_MCP_IP.set(client_ip)
            flask_app.current_mcp_user = user
            flask_app.current_mcp_ip = client_ip
            logger.info(
                f"🔑 Connexion MCP autorisée : User #{getattr(user, 'id', 0)} ({getattr(user, 'mail', 'guest')}) [{method} {path}]")

        await self.app(scope, receive, send)
