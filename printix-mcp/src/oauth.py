"""
Minimaler OAuth 2.0 Authorization Code Server für Printix MCP.

Implementiert den Authorization Code Flow (RFC 6749):
  1. GET  /oauth/authorize  → zeigt Bestätigungsseite im Browser
  2. POST /oauth/authorize  → User klickt "Erlauben" → Redirect mit Code
  3. POST /oauth/token      → Code gegen Bearer Token tauschen

Kompatibel mit ChatGPT MCP Connector (Authentifizierung: "Gemischt" / OAuth).

Konfiguration (via Umgebungsvariablen):
  OAUTH_CLIENT_ID      — Client-ID, die in ChatGPT eingetragen wird
  OAUTH_CLIENT_SECRET  — Client-Secret, das in ChatGPT eingetragen wird
  MCP_BEARER_TOKEN     — der eigentliche Access Token (wird nach OAuth ausgegeben)
"""

import json
import logging
import os
import secrets
import time

logger = logging.getLogger("printix.oauth")

# In-memory Authorization Code Store
# {code: {client_id, redirect_uri, expires_at}}
_auth_codes: dict = {}
_request_count = 0


def _cleanup_codes():
    global _request_count
    _request_count += 1
    if _request_count % 50 == 0:
        now = time.time()
        expired = [k for k, v in _auth_codes.items() if v["expires_at"] < now]
        for k in expired:
            del _auth_codes[k]


# ─── HTML Authorize-Seite ──────────────────────────────────────────────────────

_AUTHORIZE_HTML = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Printix MCP – Zugriff erlauben</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, sans-serif;
      background: #f0f2f5;
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh;
    }}
    .card {{
      background: #fff;
      border-radius: 16px;
      padding: 40px 36px;
      max-width: 440px;
      width: 100%;
      box-shadow: 0 8px 32px rgba(0,0,0,.10);
    }}
    .icon {{ font-size: 2.4em; margin-bottom: 12px; }}
    h1 {{ font-size: 1.4em; color: #111; margin-bottom: 8px; }}
    .sub {{ color: #555; font-size: .95em; line-height: 1.55; margin-bottom: 24px; }}
    .client-box {{
      background: #eff6ff;
      border: 1px solid #bfdbfe;
      border-radius: 8px;
      padding: 12px 16px;
      margin-bottom: 28px;
      font-size: .9em;
      color: #1d4ed8;
      font-weight: 600;
    }}
    .btn {{
      display: block; width: 100%; padding: 14px;
      border: none; border-radius: 10px; font-size: 1em;
      font-weight: 600; cursor: pointer; transition: background .15s;
    }}
    .btn-approve {{
      background: #2563eb; color: #fff; margin-bottom: 10px;
    }}
    .btn-approve:hover {{ background: #1d4ed8; }}
    .btn-deny {{
      background: #f1f5f9; color: #374151;
    }}
    .btn-deny:hover {{ background: #e2e8f0; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">🖨️</div>
    <h1>Printix MCP Server</h1>
    <p class="sub">
      Eine externe App möchte auf deinen Printix MCP Server zugreifen
      und Printix-Ressourcen in deinem Namen verwalten.
    </p>
    <div class="client-box">App: {client_id}</div>

    <form method="post" action="/oauth/authorize">
      <input type="hidden" name="client_id"    value="{client_id}">
      <input type="hidden" name="redirect_uri" value="{redirect_uri}">
      <input type="hidden" name="state"        value="{state}">
      <input type="hidden" name="approved"     value="true">
      <button type="submit" class="btn btn-approve">✓ Zugriff erlauben</button>
    </form>

    <form method="post" action="/oauth/authorize">
      <input type="hidden" name="client_id"    value="{client_id}">
      <input type="hidden" name="redirect_uri" value="{redirect_uri}">
      <input type="hidden" name="state"        value="{state}">
      <input type="hidden" name="approved"     value="false">
      <button type="submit" class="btn btn-deny">✗ Ablehnen</button>
    </form>
  </div>
</body>
</html>"""


# ─── OAuth ASGI Middleware ─────────────────────────────────────────────────────

class OAuthMiddleware:
    """
    ASGI Middleware: OAuth 2.0 Authorization Code Flow.

    Routet:
      GET/POST /oauth/authorize  → Authorize-Logik
      POST     /oauth/token      → Token-Endpunkt
      GET      /health           → Health-Check (ohne Auth)
      *                          → BearerAuthMiddleware → MCP SSE App
    """

    def __init__(self, app, client_id: str, client_secret: str, bearer_token: str):
        self.app = app
        self.client_id = client_id
        self.client_secret = client_secret
        self.bearer_token = bearer_token

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")

        if path == "/health":
            await self._health(send)
        elif path.startswith("/.well-known/"):
            await self._well_known(path, send)
        elif path == "/oauth/authorize":
            if method == "GET":
                await self._authorize_get(scope, send)
            elif method == "POST":
                await self._authorize_post(scope, receive, send)
            else:
                await self._json(send, 405, {"error": "method_not_allowed"})
        elif path == "/oauth/token" and method == "POST":
            await self._token(scope, receive, send)
        else:
            await self.app(scope, receive, send)

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _read_body(self, receive) -> bytes:
        body = b""
        more = True
        while more:
            msg = await receive()
            body += msg.get("body", b"")
            more = msg.get("more_body", False)
        return body

    @staticmethod
    def _parse_form(raw: bytes) -> dict:
        from urllib.parse import parse_qs
        parsed = parse_qs(raw.decode("utf-8", errors="ignore"))
        return {k: v[0] for k, v in parsed.items()}

    @staticmethod
    def _parse_query(qs: bytes) -> dict:
        from urllib.parse import parse_qs
        parsed = parse_qs(qs.decode("utf-8", errors="ignore"))
        return {k: v[0] for k, v in parsed.items()}

    async def _json(self, send, status: int, data: dict):
        body = json.dumps(data).encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [[b"content-type", b"application/json"],
                                 [b"content-length", str(len(body)).encode()]]})
        await send({"type": "http.response.body", "body": body})

    async def _redirect(self, send, location: str):
        await send({"type": "http.response.start", "status": 302,
                    "headers": [[b"location", location.encode()],
                                 [b"content-length", b"0"]]})
        await send({"type": "http.response.body", "body": b""})

    async def _health(self, send):
        body = b'{"status":"ok","service":"printix-mcp"}'
        await send({"type": "http.response.start", "status": 200,
                    "headers": [[b"content-type", b"application/json"],
                                 [b"content-length", str(len(body)).encode()]]})
        await send({"type": "http.response.body", "body": body})

    # ── OAuth Discovery ────────────────────────────────────────────────────────

    async def _well_known(self, path: str, send):
        """
        RFC 8414 / RFC 9728 OAuth Discovery Endpoints.

        ChatGPT fragt diese Endpunkte beim Einrichten einer OAuth-App ab:
          /.well-known/oauth-authorization-server
          /.well-known/oauth-authorization-server/sse   (Ressourcen-Pfad-Variante)
          /.well-known/oauth-protected-resource
          /.well-known/oauth-protected-resource/sse
          /.well-known/openid-configuration
        """
        base = os.environ.get("MCP_PUBLIC_URL", "").rstrip("/") or "http://localhost:8765"

        if "oauth-authorization-server" in path or "openid-configuration" in path:
            # RFC 8414 Authorization Server Metadata
            data = {
                "issuer": base,
                "authorization_endpoint": f"{base}/oauth/authorize",
                "token_endpoint": f"{base}/oauth/token",
                "token_endpoint_auth_methods_supported": ["client_secret_post"],
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code"],
                "code_challenge_methods_supported": [],
            }
        elif "oauth-protected-resource" in path:
            # RFC 9728 Protected Resource Metadata
            data = {
                "resource": f"{base}/sse",
                "authorization_servers": [base],
            }
        else:
            await self._json(send, 404, {"error": "not_found"})
            return

        logger.debug("OAuth Discovery: %s", path)
        await self._json(send, 200, data)

    # ── OAuth Endpunkte ────────────────────────────────────────────────────────

    async def _authorize_get(self, scope, send):
        """Zeigt die Bestätigungsseite."""
        params = self._parse_query(scope.get("query_string", b""))
        client_id = params.get("client_id", "")
        redirect_uri = params.get("redirect_uri", "")
        state = params.get("state", "")

        if not client_id or not redirect_uri:
            await self._json(send, 400, {"error": "invalid_request",
                                          "error_description": "client_id und redirect_uri erforderlich"})
            return

        logger.info("OAuth: Authorize-Anfrage von client_id=%s", client_id)
        html = _AUTHORIZE_HTML.format(
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
        )
        body = html.encode("utf-8")
        await send({"type": "http.response.start", "status": 200,
                    "headers": [[b"content-type", b"text/html; charset=utf-8"],
                                 [b"content-length", str(len(body)).encode()]]})
        await send({"type": "http.response.body", "body": body})

    async def _authorize_post(self, scope, receive, send):
        """Verarbeitet Formular-Submit (Erlauben / Ablehnen)."""
        raw = await self._read_body(receive)
        params = self._parse_form(raw)

        client_id = params.get("client_id", "")
        redirect_uri = params.get("redirect_uri", "")
        state = params.get("state", "")
        approved = params.get("approved", "false") == "true"

        if not approved:
            logger.info("OAuth: Zugriff abgelehnt für client_id=%s", client_id)
            await self._redirect(send, f"{redirect_uri}?error=access_denied&state={state}")
            return

        if client_id != self.client_id:
            logger.warning("OAuth: Unbekannte client_id=%s", client_id)
            await self._redirect(send, f"{redirect_uri}?error=unauthorized_client&state={state}")
            return

        # Authorization Code generieren (gültig 10 Min.)
        code = secrets.token_urlsafe(32)
        _auth_codes[code] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "expires_at": time.time() + 600,
        }
        _cleanup_codes()

        logger.info("OAuth: Code ausgestellt für client_id=%s → Redirect", client_id)
        await self._redirect(send, f"{redirect_uri}?code={code}&state={state}")

    async def _token(self, scope, receive, send):
        """Tauscht Authorization Code gegen Access Token."""
        raw = await self._read_body(receive)

        # Content-Type erkennen (form-encoded oder JSON)
        ct = ""
        for k, v in scope.get("headers", []):
            if k == b"content-type":
                ct = v.decode("utf-8", errors="ignore")
                break

        if "application/json" in ct:
            try:
                params = json.loads(raw)
            except Exception:
                params = {}
        else:
            params = self._parse_form(raw)

        grant_type = params.get("grant_type", "")
        code = params.get("code", "")
        client_id = params.get("client_id", "")
        client_secret = params.get("client_secret", "")

        # Client-Credentials prüfen
        if client_id != self.client_id or client_secret != self.client_secret:
            logger.warning("OAuth: Token-Anfrage mit ungültigen Client-Credentials (client_id=%s)", client_id)
            await self._json(send, 401, {
                "error": "invalid_client",
                "error_description": "Ungültige Client-ID oder Client-Secret"
            })
            return

        if grant_type != "authorization_code":
            await self._json(send, 400, {
                "error": "unsupported_grant_type",
                "error_description": "Nur authorization_code wird unterstützt"
            })
            return

        # Authorization Code validieren
        code_data = _auth_codes.pop(code, None)
        if not code_data or code_data["expires_at"] < time.time():
            logger.warning("OAuth: Ungültiger oder abgelaufener Code")
            await self._json(send, 400, {
                "error": "invalid_grant",
                "error_description": "Authorization Code ungültig oder abgelaufen"
            })
            return

        logger.info("OAuth: Access Token ausgestellt für client_id=%s", client_id)
        await self._json(send, 200, {
            "access_token": self.bearer_token,
            "token_type": "bearer",
            "expires_in": 31536000,  # 1 Jahr
        })
