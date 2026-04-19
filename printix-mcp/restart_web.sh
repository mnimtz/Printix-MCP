#!/bin/sh
# Printix MCP — Web-Server Neustart mit korrektem FERNET_KEY
# Verwendung: sh /addons/printix-mcp-addon/printix-mcp/restart_web.sh

set -e

echo "[restart_web] Suche laufende Web-Server-Prozesse..."
PIDS=$(grep -rl 'run.py' /proc/*/cmdline 2>/dev/null | sed 's|/proc/||;s|/cmdline||' | grep -v '^self$' || true)

if [ -n "$PIDS" ]; then
    echo "[restart_web] Beende PIDs: $PIDS"
    for pid in $PIDS; do
        kill "$pid" 2>/dev/null || true
    done
    sleep 1
fi

echo "[restart_web] Starte Web-Server mit FERNET_KEY..."
export FERNET_KEY
FERNET_KEY=$(cat /data/fernet.key)
export WEB_PORT=8080
export WEB_HOST=0.0.0.0
cd /app
nohup python3 /app/web/run.py > /var/log/printix_web.log 2>&1 &
sleep 2
echo "[restart_web] Web-Server gestartet (PID: $!)"
tail -3 /var/log/printix_web.log
