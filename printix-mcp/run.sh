#!/usr/bin/with-contenv bashio
# ==============================================================================
# Printix MCP Server v4.6.21 — Home Assistant Add-on Entrypoint
#
# Startet bis zu drei Services:
#   1. Web-Verwaltungsoberfläche  (WEB_PORT,      Standard: 8080)
#   2. MCP-Server (SSE + HTTP)   (MCP_PORT,      Standard: 8765)
#   3. Capture-Server (optional) (Port 8775 fest, capture_enabled=true/false)
#
# Alle Zugangsdaten werden in der SQLite-DB (/data/printix_multi.db) verwaltet.
# Erstkonfiguration über die Web-UI: http://<HA-IP>:<WEB_PORT>
# ==============================================================================

set -e

if [ ! -f /data/fernet.key ]; then
    bashio::log.info "Generiere neuen Fernet-Schlüssel für DB-Verschlüsselung..."
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" > /data/fernet.key
    chmod 600 /data/fernet.key
fi
export FERNET_KEY
FERNET_KEY=$(cat /data/fernet.key)

export MCP_PORT=$(bashio::config 'mcp_port')
export WEB_PORT=8080
HOST_WEB_PORT=$(bashio::config 'web_port')
HOST_WEB_PORT="${HOST_WEB_PORT:-8080}"
export MCP_LOG_LEVEL=$(bashio::config 'log_level')

PUBLIC_URL=$(bashio::config 'public_url')
PUBLIC_URL="${PUBLIC_URL%/}"
export MCP_PUBLIC_URL="${PUBLIC_URL}"

MCP_PORT="${MCP_PORT:-8765}"

CAPTURE_ENABLED=$(bashio::config 'capture_enabled')
CAPTURE_ENABLED="${CAPTURE_ENABLED:-false}"
export CAPTURE_ENABLED
CAPTURE_CONTAINER_PORT=8775

CAPTURE_PUBLIC_URL=$(bashio::config 'capture_public_url' || echo "")
CAPTURE_PUBLIC_URL="${CAPTURE_PUBLIC_URL%/}"
export CAPTURE_PUBLIC_URL

bashio::log.info "Capture-Config: capture_enabled=${CAPTURE_ENABLED} container_port=${CAPTURE_CONTAINER_PORT}"
if [ "${CAPTURE_ENABLED}" = "true" ]; then
    bashio::log.info "Separater Capture-Server: AKTIV auf Container-Port ${CAPTURE_CONTAINER_PORT}"
    bashio::log.info "  WICHTIG: Host-Port muss in HA aktiviert sein!"
    bashio::log.info "  Pfad: Einstellungen > Add-ons > Printix MCP > Netzwerk > Port 8775"
else
    bashio::log.info "Separater Capture-Server: DEAKTIVIERT"
    bashio::log.info "  Capture-Webhooks laufen ueber MCP-Port (${MCP_PORT})"
    bashio::log.info "  Webhook-URL: http://<HA-IP>:${MCP_PORT}/capture/webhook/<profile_id>"
fi

if [ -n "${PUBLIC_URL}" ]; then
    BASE="${PUBLIC_URL}"
else
    BASE="http://<HA-IP>:${MCP_PORT}"
fi

bashio::log.info "╔══════════════════════════════════════════════════════════════╗"
bashio::log.info "║        PRINTIX MCP SERVER v4.6.21 — MULTI-TENANT             ║"
bashio::log.info "╠══════════════════════════════════════════════════════════════╣"
bashio::log.info "║ Web-Verwaltung:  http://<HA-IP>:${HOST_WEB_PORT}"
bashio::log.info "║  → Erstkonfiguration / Benutzer registrieren"
bashio::log.info "╠══════════════════════════════════════════════════════════════╣"
bashio::log.info "║ MCP-Endpunkte:"
bashio::log.info "║  claude.ai  → ${BASE}/mcp"
bashio::log.info "║  ChatGPT    → ${BASE}/sse"
bashio::log.info "║  Health     → ${BASE}/health"
bashio::log.info "║  OAuth      → ${BASE}/oauth/authorize"
bashio::log.info "╠══════════════════════════════════════════════════════════════╣"
if [ "${CAPTURE_ENABLED}" = "true" ]; then
    if [ -n "${CAPTURE_PUBLIC_URL}" ]; then
        CAPTURE_BASE="${CAPTURE_PUBLIC_URL}"
    else
        CAPTURE_BASE="http://<HA-IP>:${CAPTURE_CONTAINER_PORT}"
    fi
    bashio::log.info "║ Capture-Server (separat):"
    bashio::log.info "║  Webhook   → ${CAPTURE_BASE}/capture/webhook/<profile_id>"
    bashio::log.info "║  Debug     → ${CAPTURE_BASE}/capture/debug"
else
    bashio::log.info "║ Capture (via MCP):"
    bashio::log.info "║  Webhook   → ${BASE}/capture/webhook/<profile_id>"
fi
bashio::log.info "╚══════════════════════════════════════════════════════════════╝"

bashio::log.info "Starte Web-UI auf Port ${HOST_WEB_PORT} (Host) → ${WEB_PORT} (Container)..."
export WEB_HOST="0.0.0.0"
python3 -c "import flexible_card_lookup as _f; _f.install(); import runpy; runpy.run_path('/app/web/run.py', run_name='__main__')" &
WEB_PID=$!
bashio::log.info "Web-UI läuft (PID: ${WEB_PID})"

if [ "${CAPTURE_ENABLED}" = "true" ]; then
    bashio::log.info "Starte Capture-Server auf Container-Port ${CAPTURE_CONTAINER_PORT}..."
    export CAPTURE_HOST="0.0.0.0"
    export CAPTURE_PORT=${CAPTURE_CONTAINER_PORT}
    if [ ! -f /app/capture_server.py ]; then
        bashio::log.error "FEHLER: /app/capture_server.py nicht gefunden!"
        bashio::log.error "Capture-Server kann nicht gestartet werden."
    else
        python3 /app/capture_server.py 2>&1 &
        CAPTURE_PID=$!
        bashio::log.info "Capture-Server gestartet (PID: ${CAPTURE_PID})"
        sleep 2
        if kill -0 "${CAPTURE_PID}" 2>/dev/null; then
            bashio::log.info "Capture-Server laeuft auf Container-Port ${CAPTURE_CONTAINER_PORT} (PID: ${CAPTURE_PID})"
            if python3 -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1', ${CAPTURE_CONTAINER_PORT})); s.close(); print('OK')" 2>/dev/null; then
                bashio::log.info "Capture-Server antwortet auf 127.0.0.1:${CAPTURE_CONTAINER_PORT}"
            else
                bashio::log.warning "Capture-Server laeuft (PID OK), aber 127.0.0.1:${CAPTURE_CONTAINER_PORT} antwortet noch nicht"
            fi
        else
            bashio::log.error "FEHLER: Capture-Server (PID: ${CAPTURE_PID}) ist sofort beendet!"
            bashio::log.error "Mögliche Ursachen: Import-Fehler, Port-Konflikt, fehlende Abhängigkeit."
            bashio::log.error "Prüfe die Log-Ausgabe oberhalb für Details."
        fi
    fi
else
    bashio::log.info "Capture-Server deaktiviert (capture_enabled=${CAPTURE_ENABLED}) — Webhooks laufen über MCP-Port"
fi

bashio::log.info "Starte MCP-Server auf Port ${MCP_PORT}..."
export MCP_HOST="0.0.0.0"
exec python3 -c "import flexible_card_lookup as _f; _f.install(); import runpy; runpy.run_path('/app/server.py', run_name='__main__')"
