"""
Bearer Token ASGI Middleware for MCP Server.

Schützt den SSE-Endpoint mit einem Bearer Token.
Kompatibel mit Claude, ChatGPT und anderen MCP-Clients.

Verwendung:
    from auth import BearerAuthMiddleware
    app = BearerAuthMiddleware(mcp.sse_app(), token="your-secret-token")
    uvicorn.run(app, ...)
"""

import logging

logger = logging.getLogger("printix.auth")


class BearerAuthMiddleware:
    """
    ASGI Middleware that enforces Bearer token authentication.

    Prüft den Authorization-Header auf jeder Anfrage.
    Erlaubt ohne Auth:
      - /health  (Health-Check für HA / Docker)
    """

    def __init__(self, app, token: str):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Health-Check und OAuth-Discovery ohne Auth erlauben
        path = scope.get("path", "")
        if path == "/health":
            await self._health_response(send)
            return

        # OAuth Discovery Endpoints (/.well-known/*) ohne Bearer Token durchlassen
        if path.startswith("/.well-known/"):
            await self.app(scope, receive, send)
            return

        # Authorization Header prüfen
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("utf-8", errors="ignore")

        if not auth_header.startswith("Bearer "):
            logger.warning("Zugriff ohne Bearer Token abgelehnt: %s %s", scope.get("method", "?"), path)
            await self._unauthorized(send, "Missing or invalid Authorization header. Use: Bearer <token>")
            return

        provided_token = auth_header[7:]  # Strip "Bearer "
        if provided_token != self.token:
            logger.warning("Ungültiger Bearer Token für: %s %s", scope.get("method", "?"), path)
            await self._unauthorized(send, "Invalid bearer token.")
            return

        # Token gültig → Anfrage durchlassen
        logger.debug("Bearer Auth OK für: %s %s", scope.get("method", "?"), path)
        await self.app(scope, receive, send)

    async def _unauthorized(self, send, message: str):
        """Send 401 Unauthorized response."""
        body = f'{{"error": "unauthorized", "message": "{message}"}}'.encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                [b"content-type", b"application/json"],
                [b"www-authenticate", b"Bearer"],
                [b"content-length", str(len(body)).encode()],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })

    async def _health_response(self, send):
        """Send 200 OK health check response."""
        body = b'{"status": "ok", "service": "printix-mcp"}'
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(body)).encode()],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })
