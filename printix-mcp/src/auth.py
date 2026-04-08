"""
Multi-Tenant Bearer Token ASGI Middleware für Printix MCP Server.

Schützt den MCP-Endpoint. Pro Request wird der Bearer Token in der SQLite-DB
nachgeschlagen → liefert den zugehörigen Tenant. Der Tenant wird über eine
ContextVar an alle Tools im selben Request weitergegeben.

Zusätzlich wird eine zweite ContextVar für SQL-Credentials gesetzt, damit
das Reporting-Modul ohne Änderungen die richtigen Credentials nutzt.

Erlaubt ohne Auth:
  - /health          (Health-Check)
  - /.well-known/*   (OAuth Discovery)
  - /favicon.ico     (Browser-Requests)
  - /robots.txt
"""

import logging
from contextvars import ContextVar
from typing import Optional

logger = logging.getLogger("printix.auth")

# ── Context Variables ─────────────────────────────────────────────────────────
# Werden pro ASGI-Request gesetzt und sind für alle async-Funktionen im
# selben Request-Kontext sichtbar.

current_tenant: ContextVar[Optional[dict]] = ContextVar("current_tenant", default=None)
"""Aktueller Tenant-Datensatz (entschlüsselt aus DB) für den laufenden Request."""

current_sql_config: ContextVar[Optional[dict]] = ContextVar("current_sql_config", default=None)
"""SQL-Zugangsdaten des aktuellen Tenants — wird vom Reporting-Modul gelesen."""


class BearerAuthMiddleware:
    """
    ASGI Middleware: Multi-Tenant Bearer Token Authentication.

    Schaut den Token in der SQLite-DB nach, setzt `current_tenant` und
    `current_sql_config` ContextVars für den gesamten Request.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Pfade ohne Auth
        if path == "/health":
            await self._health_response(send)
            return
        if path.startswith("/.well-known/"):
            await self.app(scope, receive, send)
            return
        if path in ("/favicon.ico", "/robots.txt"):
            await self._not_found(send)
            return

        # Bearer Token aus Authorization-Header extrahieren
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("utf-8", errors="ignore")

        if not auth_header.startswith("Bearer "):
            logger.warning("Zugriff ohne Bearer Token: %s %s",
                           scope.get("method", "?"), path)
            await self._unauthorized(send, "Missing or invalid Authorization header. Use: Bearer <token>")
            return

        token = auth_header[7:]  # Strip "Bearer "

        # Tenant in DB nachschlagen
        tenant = self._lookup_tenant(token)
        if tenant is None:
            logger.warning("Ungültiger Bearer Token für: %s %s",
                           scope.get("method", "?"), path)
            await self._unauthorized(send, "Invalid bearer token.")
            return

        logger.debug("Auth OK: Tenant '%s' für %s %s",
                     tenant.get("name", tenant.get("id", "?")),
                     scope.get("method", "?"), path)

        # Tenant in ContextVar setzen (thread-safe dank contextvars)
        token_ct = current_tenant.set(tenant)

        # SQL-Konfiguration für Reporting-Modul setzen
        sql_ct = current_sql_config.set({
            "server":    tenant.get("sql_server", ""),
            "database":  tenant.get("sql_database", ""),
            "username":  tenant.get("sql_username", ""),
            "password":  tenant.get("sql_password", ""),
            "tenant_id": tenant.get("printix_tenant_id", ""),
        })

        try:
            await self.app(scope, receive, send)
        finally:
            current_tenant.reset(token_ct)
            current_sql_config.reset(sql_ct)

    def _lookup_tenant(self, token: str) -> Optional[dict]:
        """Sucht den Tenant anhand des Bearer Tokens in der SQLite-DB."""
        try:
            from db import get_tenant_by_bearer_token
            return get_tenant_by_bearer_token(token)
        except Exception as e:
            logger.error("DB-Fehler bei Token-Lookup: %s", e)
            return None

    # ── HTTP-Antworten ─────────────────────────────────────────────────────────

    async def _unauthorized(self, send, message: str):
        body = f'{{"error":"unauthorized","message":"{message}"}}'.encode()
        await send({"type": "http.response.start", "status": 401,
                    "headers": [[b"content-type", b"application/json"],
                                 [b"www-authenticate", b"Bearer"],
                                 [b"content-length", str(len(body)).encode()]]})
        await send({"type": "http.response.body", "body": body})

    async def _not_found(self, send):
        await send({"type": "http.response.start", "status": 404,
                    "headers": [[b"content-length", b"0"]]})
        await send({"type": "http.response.body", "body": b""})

    async def _health_response(self, send):
        body = b'{"status":"ok","service":"printix-mcp"}'
        await send({"type": "http.response.start", "status": 200,
                    "headers": [[b"content-type", b"application/json"],
                                 [b"content-length", str(len(body)).encode()]]})
        await send({"type": "http.response.body", "body": body})
