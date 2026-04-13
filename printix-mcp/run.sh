#!/usr/bin/with-contenv bashio
# ==============================================================================
# Printix MCP Server v4.5.5 — Home Assistant Add-on Entrypoint
#
# Startet bis zu drei Services:
#   1. Web-Verwaltungsoberfläche  (WEB_PORT,      Standard: 8080)
#   2. MCP-Server (SSE + HTTP)   (MCP_PORT,      Standard: 8765)
#   3. Capture-Server (optional) (CAPTURE_PORT,  Standard: 8775, 0=deaktiviert)
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

# v4.5.5: Capture-Server Konfiguration
# capture_port aus config ist NUR ein Ein/Aus-Schalter (0=aus, >0=ein).
# Im Container bindet der Capture-Server IMMER auf Port 8775 —
# das muss zum Docker-Portmapping in config.yaml passen (ports: 8775/tcp).
# Der Host-Port wird in HA unter Add-on > Netzwerk konfiguriert.
#
# WICHTIG: Capture-Webhooks funktionieren IMMER auch ueber den MCP-Port (${MCP_PORT})
# und den Web-Port (8080) — der separate Capture-Server auf 8775 ist optional.
CAPTURE_ENABLED=$(bashio::config 'capture_port' || echo "0")
CAPTURE_ENABLED="${CAPTURE_ENABLED:-0}"
CAPTURE_CONTAINER_PORT=8775

# CAPTURE_PORT nur exportieren wenn der separate Server auch wirklich startet.
# Wenn CAPTURE_PORT > 0 ist, zeigt der MCP-Server den Hinweis "laeuft auf eigenem Port".
# Wenn CAPTURE_PORT = 0, weiss der MCP-Server: Webhooks laufen nur ueber ihn selbst.
if [ "${CAPTURE_ENABLED}" -gt 0 ] 2>/dev/null; then
    export CAPTURE_PORT=${CAPTURE_CONTAINER_PORT}
else
    export CAPTURE_PORT=0
fi

CAPTURE_PUBLIC_URL=$(bashio::config 'capture_public_url' || echo "")
CAPTURE_PUBLIC_URL="${CAPTURE_PUBLIC_URL%/}"
export CAPTURE_PUBLIC_URL

# v4.5.5: Capture-Konfiguration diagnostisch loggen
bashio::log.info "Capture-Config: enabled=${CAPTURE_ENABLED} container_port=${CAPTURE_CONTAINER_PORT} CAPTURE_PORT=${CAPTURE_PORT}"
if [ "${CAPTURE_ENABLED}" -gt 0 ] 2>/dev/null; then
    bashio::log.info "HINWEIS: Port 8775 muss in HA unter Add-on > Netzwerk aktiviert sein!"
    bashio::log.info "  Pruefe: Einstellungen > Add-ons > Printix MCP > Netzwerk > 8775"
else
    bashio::log.info "Capture-Webhooks laufen ueber MCP-Port (${MCP_PORT}) — kein separater Port noetig"
    bashio::log.info "  Webhook-URL: http://<HA-IP>:${MCP_PORT}/capture/webhook/<profile_id>"
fi

# ─── Entra ID Auto-Setup (v4.3.0: Device Code Flow, keine Bootstrap-App noetig)

# ─── Verbindungsinfo im Log ────────────────────────────────────────────────────

if [ -n "${PUBLIC_URL}" ]; then
    BASE="${PUBLIC_URL}"
else
    BASE="http://<HA-IP>:${MCP_PORT}"
fi

bashio::log.info "╔══════════════════════════════════════════════════════════════╗"
bashio::log.info "║        PRINTIX MCP SERVER v4.5.5 — MULTI-TENANT             ║"
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
if [ "${CAPTURE_ENABLED}" -gt 0 ] 2>/dev/null; then
    if [ -n "${CAPTURE_PUBLIC_URL}" ]; then
        CAPTURE_BASE="${CAPTURE_PUBLIC_URL}"
    else
        CAPTURE_BASE="http://<HA-IP>:${CAPTURE_PORT}"
    fi
    bashio::log.info "║ Capture-Server (separat):"
    bashio::log.info "║  Webhook   → ${CAPTURE_BASE}/capture/webhook/<profile_id>"
    bashio::log.info "║  Debug     → ${CAPTURE_BASE}/capture/debug"
else
    bashio::log.info "║ Capture (via MCP):"
    bashio::log.info "║  Webhook   → ${BASE}/capture/webhook/<profile_id>"
fi
bashio::log.info "╚══════════════════════════════════════════════════════════════╝"

# ─── Web-Verwaltungsoberfläche starten (Hintergrund) ──────────────────────────

bashio::log.info "Starte Web-UI auf Port ${HOST_WEB_PORT} (Host) → ${WEB_PORT} (Container)..."
export WEB_HOST="0.0.0.0"
python3 /app/web/run.py &
WEB_PID=$!
bashio::log.info "Web-UI läuft (PID: ${WEB_PID})"

# ─── Capture-Server starten (optional, Hintergrund) ─────────────────────────

if [ "${CAPTURE_ENABLED}" -gt 0 ] 2>/dev/null; then
    bashio::log.info "Starte Capture-Server auf Container-Port ${CAPTURE_CONTAINER_PORT}..."
    export CAPTURE_HOST="0.0.0.0"

    # v4.5.5: Prüfe ob capture_server.py existiert
    if [ ! -f /app/capture_server.py ]; then
        bashio::log.error "FEHLER: /app/capture_server.py nicht gefunden!"
        bashio::log.error "Capture-Server kann nicht gestartet werden."
    else
        # Starte mit stderr-Weiterleitung damit Fehler sichtbar sind
        python3 /app/capture_server.py 2>&1 &
        CAPTURE_PID=$!
        bashio::log.info "Capture-Server gestartet (PID: ${CAPTURE_PID})"

        # v4.5.5: Kurze Wartezeit + Prozess-Check
        sleep 2
        if kill -0 "${CAPTURE_PID}" 2>/dev/null; then
            bashio::log.info "Capture-Server laeuft auf Container-Port ${CAPTURE_CONTAINER_PORT} (PID: ${CAPTURE_PID})"
            # v4.5.5: Lokaler Konnektivitaetstest
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
    bashio::log.info "Capture-Server deaktiviert (capture_port=${CAPTURE_ENABLED}) — Webhooks laufen über MCP-Port"
fi

# ─── MCP-Server starten (Vordergrund) ─────────────────────────────────────────

bashio::log.info "Starte MCP-Server auf Port ${MCP_PORT}..."
export MCP_HOST="0.0.0.0"
exec python3 /app/server.py
