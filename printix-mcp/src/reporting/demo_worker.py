"""
Demo Worker — Subprocess-Isolierung für pyodbc/FreeTDS Segfault-Schutz
======================================================================
Wird von app.py via subprocess.Popen gestartet. Läuft im eigenen Prozess,
damit ein pyodbc-Segfault (FreeTDS ARM64-Bug) den Web-Server nicht tötet.

Eingabe:  Umgebungsvariablen DEMO_TENANT_CONFIG (JSON) + DEMO_PARAMS (JSON)
          + DEMO_OUTPUT_FILE (Pfad zur Ergebnisdatei)
Ausgabe:  JSON-Datei an DEMO_OUTPUT_FILE mit {"session_id": ..., "error": ...}
"""

import json
import logging
import os
import sys
import traceback

# /app in den Suchpfad
sys.path.insert(0, "/app")

# Logging zentral konfigurieren BEVOR irgendein Modul Logger holt — sonst
# verschwinden alle reporting.* / printix.* Logs des Subprozesses (kein
# StreamHandler an stdout, _WebTenantDBHandler ist hier sowieso nicht aktiv).
logging.basicConfig(
    level=os.environ.get("MCP_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger("printix.demo_worker")

def main():
    output_file = os.environ.get("DEMO_OUTPUT_FILE", "/tmp/demo_result.json")
    logger.info("demo_worker gestartet (output=%s)", output_file)

    try:
        # SQL-Config aus Umgebung lesen und setzen
        tenant_config_str = os.environ.get("DEMO_TENANT_CONFIG", "")
        if not tenant_config_str:
            raise RuntimeError("DEMO_TENANT_CONFIG nicht gesetzt")
        tenant_config = json.loads(tenant_config_str)

        from reporting.sql_client import set_config_from_tenant
        set_config_from_tenant(tenant_config)

        # Generation-Parameter
        params_str = os.environ.get("DEMO_PARAMS", "{}")
        params = json.loads(params_str)
        logger.info("Starte generate_demo_dataset(**%s)", params)

        from reporting.demo_generator import generate_demo_dataset
        result = generate_demo_dataset(**params)
        logger.info("generate_demo_dataset fertig: session_id=%s", result.get("session_id", "?"))

        # Ergebnis schreiben
        with open(output_file, "w") as f:
            json.dump(result, f)

        # Exit-Code 0 = Erfolg
        sys.exit(0)

    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("demo_worker abgebrochen: %s\n%s", exc, tb)
        error_result = {
            "error": str(exc),
            "traceback": tb[:1000],
            "session_id": "",
        }
        try:
            with open(output_file, "w") as f:
                json.dump(error_result, f)
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
