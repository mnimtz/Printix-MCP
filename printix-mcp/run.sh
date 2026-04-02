#!/usr/bin/with-contenv bashio
# ==============================================================================
# Printix MCP Server — Home Assistant Add-on Entrypoint
# Reads configuration from /data/options.json, generates bearer token if needed,
# and starts the MCP server.
#
# Persistente Secrets: /data/mcp_secrets.json
#   Einmal generierte Werte (bearer_token, oauth_secret) werden dort gespeichert
#   und überleben Add-on-Updates. Werte in der HA-Konfiguration haben Vorrang.
# ==============================================================================

set -e

SECRETS_FILE="/data/mcp_secrets.json"

# ─── Hilfsfunktionen für persistente Secrets ──────────────────────────────────

# Liest einen Wert aus /data/mcp_secrets.json (leer wenn nicht vorhanden)
secrets_get() {
    local key="$1"
    if [ -f "${SECRETS_FILE}" ]; then
        python3 -c "
import json, sys
try:
    d = json.load(open('${SECRETS_FILE}'))
    print(d.get('${key}', ''), end='')
except Exception:
    pass
"
    fi
}

# Schreibt/aktualisiert einen Wert in /data/mcp_secrets.json
secrets_set() {
    local key="$1"
    local value="$2"
    python3 -c "
import json, os
f = '${SECRETS_FILE}'
d = {}
if os.path.exists(f):
    try:
        d = json.load(open(f))
    except Exception:
        d = {}
d['${key}'] = '${value}'
json.dump(d, open(f, 'w'), indent=2)
"
}

# ─── Read options from HA config ──────────────────────────────────────────────

export PRINTIX_TENANT_ID=$(bashio::config 'tenant_id')

export PRINTIX_PRINT_CLIENT_ID=$(bashio::config 'print_client_id')
export PRINTIX_PRINT_CLIENT_SECRET=$(bashio::config 'print_client_secret')

export PRINTIX_CARD_CLIENT_ID=$(bashio::config 'card_client_id')
export PRINTIX_CARD_CLIENT_SECRET=$(bashio::config 'card_client_secret')

export PRINTIX_WS_CLIENT_ID=$(bashio::config 'ws_client_id')
export PRINTIX_WS_CLIENT_SECRET=$(bashio::config 'ws_client_secret')

export PRINTIX_SHARED_CLIENT_ID=$(bashio::config 'shared_client_id')
export PRINTIX_SHARED_CLIENT_SECRET=$(bashio::config 'shared_client_secret')

export MCP_LOG_LEVEL=$(bashio::config 'log_level')

PUBLIC_URL=$(bashio::config 'public_url')
PUBLIC_URL="${PUBLIC_URL%/}"
export MCP_PUBLIC_URL="${PUBLIC_URL}"

# ─── OAuth Credentials (persistent) ───────────────────────────────────────────
# Priorität: 1. HA-Konfiguration  2. gespeicherter Wert  3. neu generieren

OAUTH_CLIENT_ID=$(bashio::config 'oauth_client_id')
if [ -z "${OAUTH_CLIENT_ID}" ]; then
    OAUTH_CLIENT_ID=$(secrets_get 'oauth_client_id')
fi
if [ -z "${OAUTH_CLIENT_ID}" ]; then
    OAUTH_CLIENT_ID="printix-mcp-client"
fi
secrets_set 'oauth_client_id' "${OAUTH_CLIENT_ID}"

OAUTH_CLIENT_SECRET=$(bashio::config 'oauth_client_secret')
if [ -z "${OAUTH_CLIENT_SECRET}" ]; then
    OAUTH_CLIENT_SECRET=$(secrets_get 'oauth_client_secret')
fi
if [ -z "${OAUTH_CLIENT_SECRET}" ]; then
    OAUTH_CLIENT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    bashio::log.info "OAuth Client-Secret neu generiert und dauerhaft gespeichert."
fi
secrets_set 'oauth_client_secret' "${OAUTH_CLIENT_SECRET}"

export OAUTH_CLIENT_ID
export OAUTH_CLIENT_SECRET

# ─── Bearer Token (persistent) ────────────────────────────────────────────────
# Priorität: 1. HA-Konfiguration  2. gespeicherter Wert  3. neu generieren

BEARER_TOKEN=$(bashio::config 'bearer_token')
if [ -z "${BEARER_TOKEN}" ]; then
    BEARER_TOKEN=$(secrets_get 'bearer_token')
fi
if [ -z "${BEARER_TOKEN}" ]; then
    BEARER_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
    bashio::log.info "Bearer Token neu generiert und dauerhaft gespeichert."
fi
secrets_set 'bearer_token' "${BEARER_TOKEN}"

export MCP_BEARER_TOKEN="${BEARER_TOKEN}"

# ─── Validation ───────────────────────────────────────────────────────────────

if [ -z "${PRINTIX_TENANT_ID}" ]; then
    bashio::log.error "PRINTIX_TENANT_ID ist nicht konfiguriert!"
    bashio::log.error "Bitte Tenant-ID in den Add-on-Einstellungen angeben."
    exit 1
fi

HAS_CREDS=false
if [ -n "${PRINTIX_PRINT_CLIENT_ID}" ] && [ -n "${PRINTIX_PRINT_CLIENT_SECRET}" ]; then HAS_CREDS=true; fi
if [ -n "${PRINTIX_CARD_CLIENT_ID}" ] && [ -n "${PRINTIX_CARD_CLIENT_SECRET}" ]; then HAS_CREDS=true; fi
if [ -n "${PRINTIX_WS_CLIENT_ID}" ] && [ -n "${PRINTIX_WS_CLIENT_SECRET}" ]; then HAS_CREDS=true; fi
if [ -n "${PRINTIX_SHARED_CLIENT_ID}" ] && [ -n "${PRINTIX_SHARED_CLIENT_SECRET}" ]; then HAS_CREDS=true; fi

if [ "${HAS_CREDS}" = false ]; then
    bashio::log.warning "Keine API-Credentials konfiguriert! Mindestens ein Paar (Print/Card/WS) wird benötigt."
fi

# ─── Verbindungsinformationen im Log ausgeben ──────────────────────────────────

# Basis-URL bestimmen (public_url oder lokale IP-Fallback)
if [ -n "${PUBLIC_URL}" ]; then
    BASE="${PUBLIC_URL}"
else
    BASE="http://<HA-IP>:8765"
fi

bashio::log.info "╔══════════════════════════════════════════════════════════════╗"
bashio::log.info "║           PRINTIX MCP SERVER — VERBINDUNGSINFO              ║"
bashio::log.info "╠══════════════════════════════════════════════════════════════╣"
bashio::log.info "║ Version: 1.11.0"
bashio::log.info "║ Tenant:  ${PRINTIX_TENANT_ID}"
bashio::log.info "║ Secrets: ${SECRETS_FILE} (persistent über Updates)"
bashio::log.info "╠══════════════════════════════════════════════════════════════╣"
bashio::log.info "║ SERVER ENDPUNKTE"
bashio::log.info "║  MCP SSE:             ${BASE}/sse"
bashio::log.info "║  Health-Check:        ${BASE}/health"
bashio::log.info "║  OAuth Authorize:     ${BASE}/oauth/authorize"
bashio::log.info "║  OAuth Token:         ${BASE}/oauth/token"
bashio::log.info "║  OAuth Registrierung: (nicht benötigt / leer lassen)"
bashio::log.info "╠══════════════════════════════════════════════════════════════╣"
bashio::log.info "║ CLAUDE (claude.ai) → Einstellungen → Konnektoren"
bashio::log.info "║  Name:                Printix"
bashio::log.info "║  Remote MCP URL:      ${BASE}/sse"
bashio::log.info "║  OAuth Client-ID:     ${OAUTH_CLIENT_ID}"
bashio::log.info "║  OAuth Client-Secret: ${OAUTH_CLIENT_SECRET}"
bashio::log.info "╠══════════════════════════════════════════════════════════════╣"
bashio::log.info "║ CHATGPT → Neue App → Authentifizierung: OAuth"
bashio::log.info "║  URL des MCP-Servers:       ${BASE}/sse"
bashio::log.info "║  OAuth Client-ID:            ${OAUTH_CLIENT_ID}"
bashio::log.info "║  OAuth Client-Secret:        ${OAUTH_CLIENT_SECRET}"
bashio::log.info "║  Token-Authentif.-methode:   client_secret_post"
bashio::log.info "║  Standard-Scopes:            (leer lassen)"
bashio::log.info "║  Basis-Scopes:               (leer lassen)"
bashio::log.info "║  Auth-URL:                   ${BASE}/oauth/authorize"
bashio::log.info "║  Token-URL:                  ${BASE}/oauth/token"
bashio::log.info "║  Registrierungs-URL:         (leer lassen)"
bashio::log.info "╚══════════════════════════════════════════════════════════════╝"

# ─── Server starten ───────────────────────────────────────────────────────────

exec python3 /app/server.py
