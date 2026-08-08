"""
Point d'entrée principal du serveur MCP (Model Context Protocol) Admin — Belle Vitesse (BV-MCP).
Expose les services d'administration de l'application Flask aux agents IA via Streamable HTTP.
"""
import os
import uvicorn
from mcp_server import mcp, PureAsgiAuthMiddleware, logger

if __name__ == "__main__":
    port = int(os.getenv("MCP_SERVER_PORT", "8080"))
    logger.info(f"🚀 Lancement du serveur BV-MCP (Streamable HTTP) sur 0.0.0.0:{port}/mcp ...")

    try:
        asgi_fn = getattr(mcp, "streamable_http_app", None) or getattr(mcp, "http_app", None) or getattr(mcp, "_http_app", None)
        if callable(asgi_fn):
            try:
                raw_app = asgi_fn(path="/mcp")
            except TypeError:
                raw_app = asgi_fn()
            app = PureAsgiAuthMiddleware(raw_app)
            uvicorn.run(app, host="0.0.0.0", port=port)
        else:
            mcp.run(transport="streamable-http", host="0.0.0.0", port=port, path="/mcp")
    except Exception as err:
        logger.warning(f"⚠️ Lancement avec mcp.run Streamable HTTP: {err}")
        mcp.run(transport="streamable-http", host="0.0.0.0", port=port, path="/mcp")
