"""
Entra ID (Azure AD) SSO — Login via Microsoft Account
=====================================================
Ermöglicht Benutzern die Anmeldung über ihr Microsoft-Konto (Entra ID).
Konfiguration erfolgt über Admin-Settings (settings-Tabelle).

Unterstützt Multi-Tenant: eine App-Registration in einem beliebigen
Entra-Tenant, Login für Benutzer aus jedem Entra-Tenant möglich.
"""

import base64
import json
import logging
import secrets
from urllib.parse import urlencode

import requests as _requests

logger = logging.getLogger(__name__)

# Microsoft Identity Platform v2.0 Endpoints
_AUTH_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
_SCOPES = "openid profile email"

# Graph API for auto app registration
_GRAPH_URL = "https://graph.microsoft.com/v1.0"
_GRAPH_SCOPES = "openid profile email Application.ReadWrite.All"


# ─── Configuration ───────────────────────────────────────────────────────────

def get_config() -> dict:
    """Liest die Entra-ID-Konfiguration aus der Settings-Tabelle."""
    from db import get_setting
    secret_enc = get_setting("entra_client_secret", "")
    # Secret ist Fernet-verschlüsselt gespeichert
    if secret_enc:
        try:
            from db import _dec
            secret = _dec(secret_enc)
        except Exception:
            secret = secret_enc
    else:
        secret = ""
    return {
        "enabled":       get_setting("entra_enabled", "0") == "1",
        "tenant_id":     get_setting("entra_tenant_id", ""),
        "client_id":     get_setting("entra_client_id", ""),
        "client_secret": secret,
        "auto_approve":  get_setting("entra_auto_approve", "0") == "1",
    }


def is_enabled() -> bool:
    """Prüft ob Entra-Login aktiviert und konfiguriert ist."""
    cfg = get_config()
    return cfg["enabled"] and bool(cfg["client_id"]) and bool(cfg["client_secret"])


# ─── OAuth2 Authorization Code Flow ─────────────────────────────────────────

def generate_state() -> str:
    """Generiert einen CSRF-State-Token für den OAuth-Flow."""
    return secrets.token_urlsafe(32)


def build_authorize_url(redirect_uri: str, state: str) -> str:
    """Baut die Microsoft-Login-URL für den Authorization Code Flow."""
    cfg = get_config()
    tenant = cfg["tenant_id"] or "common"
    params = {
        "client_id":     cfg["client_id"],
        "response_type": "code",
        "redirect_uri":  redirect_uri,
        "scope":         _SCOPES,
        "response_mode": "query",
        "state":         state,
        "prompt":        "select_account",
    }
    return _AUTH_URL.format(tenant=tenant) + "?" + urlencode(params)


def exchange_code_for_user(code: str, redirect_uri: str) -> dict | None:
    """
    Tauscht den Authorization Code gegen Tokens und extrahiert User-Info
    aus dem id_token.

    Returns dict mit keys: oid, email, name, tid — oder None bei Fehler.
    """
    cfg = get_config()
    tenant = cfg["tenant_id"] or "common"

    try:
        resp = _requests.post(
            _TOKEN_URL.format(tenant=tenant),
            data={
                "client_id":     cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "code":          code,
                "redirect_uri":  redirect_uri,
                "grant_type":    "authorization_code",
                "scope":         _SCOPES,
            },
            timeout=15,
        )
    except Exception as e:
        logger.error("Entra token exchange Netzwerkfehler: %s", e)
        return None

    if resp.status_code != 200:
        logger.error("Entra token exchange fehlgeschlagen: %s %s",
                      resp.status_code, resp.text[:500])
        return None

    data = resp.json()
    id_token = data.get("id_token", "")
    if not id_token:
        logger.error("Entra: kein id_token in der Antwort")
        return None

    # Decode JWT payload — Signatur wird nicht separat validiert, da Token
    # direkt über HTTPS vom Microsoft Token-Endpoint empfangen wurde
    payload = _decode_jwt_payload(id_token)
    if not payload:
        return None

    email = (
        payload.get("email", "")
        or payload.get("preferred_username", "")
        or payload.get("upn", "")
    )

    return {
        "oid":   payload.get("oid", ""),
        "email": email,
        "name":  payload.get("name", ""),
        "tid":   payload.get("tid", ""),
    }


# ─── Auto App Registration (Graph API) ──────────────────────────────────────

def build_auto_setup_url(redirect_uri: str, state: str) -> str:
    """Baut die Microsoft-Login-URL mit Graph-API-Berechtigungen
    für die automatische App-Registrierung."""
    cfg = get_config()
    # Für Auto-Setup muss noch keine client_id konfiguriert sein —
    # wir nutzen hier den Bootstrap-Flow über "common"
    tenant = cfg["tenant_id"] or "common"
    # Wir brauchen eine Bootstrap-Client-ID — die aber noch nicht existiert.
    # Daher ist der Auto-Setup-Flow nur möglich, wenn bereits eine Client-ID
    # konfiguriert ist (z.B. manuell angelegt, aber noch kein Secret).
    if not cfg["client_id"]:
        return ""
    params = {
        "client_id":     cfg["client_id"],
        "response_type": "code",
        "redirect_uri":  redirect_uri,
        "scope":         _GRAPH_SCOPES,
        "response_mode": "query",
        "state":         state,
        "prompt":        "consent",
    }
    return _AUTH_URL.format(tenant=tenant) + "?" + urlencode(params)


def auto_register_app(
    access_token: str,
    redirect_uri: str,
    app_name: str = "Printix MCP Server",
) -> dict | None:
    """
    Erstellt eine neue App-Registration im Entra-Tenant des Benutzers
    über die Microsoft Graph API.

    Returns dict mit client_id + client_secret oder None bei Fehler.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    # 1. App erstellen
    app_body = {
        "displayName": app_name,
        "signInAudience": "AzureADMultipleOrgs",
        "web": {
            "redirectUris": [redirect_uri],
            "implicitGrantSettings": {
                "enableIdTokenIssuance": True,
            },
        },
        "requiredResourceAccess": [
            {
                "resourceAppId": "00000003-0000-0000-c000-000000000000",  # Microsoft Graph
                "resourceAccess": [
                    {"id": "37f7f235-527c-4136-accd-4a02d197296e", "type": "Scope"},  # openid
                    {"id": "14dad69e-099b-42c9-810b-d002981feec1", "type": "Scope"},  # profile
                    {"id": "64a6cdd6-aab1-4aaf-94b8-3cc8405e90d0", "type": "Scope"},  # email
                ],
            }
        ],
    }

    try:
        resp = _requests.post(
            f"{_GRAPH_URL}/applications",
            headers=headers,
            json=app_body,
            timeout=15,
        )
        if resp.status_code not in (200, 201):
            logger.error("Graph: App-Erstellung fehlgeschlagen: %s %s",
                          resp.status_code, resp.text[:500])
            return None

        app_data = resp.json()
        app_id = app_data["appId"]       # = client_id
        obj_id = app_data["id"]          # = object_id (für weitere API-Calls)

        # 2. Client Secret erstellen
        secret_body = {
            "passwordCredential": {
                "displayName": "Printix MCP Auto-Generated",
                "endDateTime": "2099-12-31T23:59:59Z",
            }
        }
        resp2 = _requests.post(
            f"{_GRAPH_URL}/applications/{obj_id}/addPassword",
            headers=headers,
            json=secret_body,
            timeout=15,
        )
        if resp2.status_code not in (200, 201):
            logger.error("Graph: Secret-Erstellung fehlgeschlagen: %s %s",
                          resp2.status_code, resp2.text[:500])
            return {"client_id": app_id, "client_secret": ""}

        secret_data = resp2.json()
        client_secret = secret_data.get("secretText", "")

        logger.info("Entra App automatisch erstellt: %s (client_id=%s)", app_name, app_id)
        return {
            "client_id":     app_id,
            "client_secret": client_secret,
        }

    except Exception as e:
        logger.error("Graph API Fehler: %s", e)
        return None


# ─── JWT Decode ──────────────────────────────────────────────────────────────

def _decode_jwt_payload(token: str) -> dict | None:
    """
    Dekodiert den Payload eines JWT ohne Signatur-Validierung.

    Sicher, da das Token direkt über HTTPS vom Microsoft Token-Endpoint
    empfangen wurde (Transport-Level-Authentizität).
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            logger.error("JWT: ungültiges Format (erwartet 3 Teile, bekommen %d)", len(parts))
            return None
        payload_b64 = parts[1]
        # Base64url → Base64: Padding ergänzen
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception as e:
        logger.error("JWT Decode-Fehler: %s", e)
        return None
