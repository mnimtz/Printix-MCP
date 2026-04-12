#!/usr/bin/with-contenv bashio
# ==============================================================================
# Printix MCP Server v4.0.0 — Home Assistant Add-on Entrypoint
#
# Startet zwei Services:
#   1. Web-Verwaltungsoberfläche  (WEB_PORT,  Standard: 8080)
#   2. MCP-Server (SSE + HTTP)   (MCP_PORT,  Standard: 8765)
#
# Alle Zugangsdaten werden in der SQLite-DB (/data/printix_multi.db) verwaltet.
# Erstkonfiguration über die Web-UI: http://<HA-IP>:<WEB_PORT>
# ==============================================================================

set -e

# ─── Fernet-Key für DB-Verschlüsselung laden / generieren ─────────────────────

if [ ! -f /data/fernet.key ]; then
    bashio::log.info "Generiere neuen Fernet-Schlüssel für DB-Verschlüsselung..."
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" > /data/fernet.key
    chmod 600 /data/fernet.key
fi
export FERNET_KEY
FERNET_KEY=$(cat /data/fernet.key)

# ─── Konfiguration aus HA-Optionen lesen ──────────────────────────────────────

export MCP_PORT=$(bashio::config 'mcp_port')
export WEB_PORT=8080              # Container-intern immer fix — HA mapped extern via Network-Tab
HOST_WEB_PORT=$(bashio::config 'web_port')   # Externer Host-Port (für Log-Ausgabe)
HOST_WEB_PORT="${HOST_WEB_PORT:-8080}"
export MCP_LOG_LEVEL=$(bashio::config 'log_level')

PUBLIC_URL=$(bashio::config 'public_url')
PUBLIC_URL="${PUBLIC_URL%/}"
export MCP_PUBLIC_URL="${PUBLIC_URL}"

# Fallback falls MCP_PORT leer
MCP_PORT="${MCP_PORT:-8765}"

# ─── Entra ID Auto-Setup (v4.3.0: Device Code Flow, keine Bootstrap-App noetig)

# ─── Verbindungsinfo im Log ────────────────────────────────────────────────────

if [ -n "${PUBLIC_URL}" ]; then
    BASE="${PUBLIC_URL}"
else
    BASE="http://<HA-IP>:${MCP_PORT}"
fi

bashio::log.info "╔══════════════════════════════════════════════════════════════╗"
bashio::log.info "║        PRINTIX MCP SERVER v4.4.1 — MULTI-TENANT             ║"
bashio::log.info "╠══════════════════════════════════════════════════════════════╣"
bashio::log.info "║ Web-Verwaltung:  http://<HA-IP>:${HOST_WEB_PORT}"
bashio::log.info "║  → Erstkonfiguration / Benutzer registrieren"
bashio::log.info "╠══════════════════════════════════════════════════════════════╣"
bashio::log.info "║ MCP-Endpunkte:"
bashio::log.info "║  claude.ai  → ${BASE}/mcp"
bashio::log.info "║  ChatGPT    → ${BASE}/sse"
bashio::log.info "║  Health     → ${BASE}/health"
bashio::log.info "║  OAuth      → ${BASE}/oauth/authorize"
bashio::log.info "╚══════════════════════════════════════════════════════════════╝"

# ─── Web-Verwaltungsoberfläche starten (Hintergrund) ──────────────────────────

bashio::log.info "Starte Web-UI auf Port ${HOST_WEB_PORT} (Host) → ${WEB_PORT} (Container)..."
export WEB_HOST="0.0.0.0"
python3 /app/web/run.py &
WEB_PID=$!
bashio::log.info "Web-UI läuft (PID: ${WEB_PID})"

# ─── MCP-Server starten (Vordergrund) ─────────────────────────────────────────

bashio::log.info "Starte MCP-Server auf Port ${MCP_PORT}..."
export MCP_HOST="0.0.0.0"
exec python3 /app/server.py
