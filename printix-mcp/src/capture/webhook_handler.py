"""
Capture Webhook Handler — Kanonische Verarbeitung (v4.5.0)
==========================================================
Einziger Ort fuer die Webhook-Logik. Wird aufgerufen von:
  - capture_server.py (Capture Port, v4.5.0, source="capture")
  - server.py / DualTransportApp (MCP Port, source="mcp")
  - web/capture_routes.py (Web-UI Port, source="web")

Kein duplizierter Code — alle drei Pfade rufen handle_webhook() auf.
"""

import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger("printix.capture")

DEBUG_PROFILE_ID = "00000000-0000-0000-0000-000000000000"


async def handle_webhook(
    profile_id: str,
    method: str,
    headers: dict[str, str],
    body_bytes: bytes,
    *,
    source: str = "unknown",
) -> tuple[int, dict[str, Any]]:
    """
    Kanonischer Capture-Webhook-Handler.

    Args:
        profile_id: Profil-UUID aus der URL
        method: HTTP-Methode (GET/POST)
        headers: Request-Headers (lowercase keys)
        body_bytes: Raw request body
        source: Kennzeichnung woher der Aufruf kommt ("web" / "mcp")

    Returns:
        (http_status_code, response_dict)
    """
    # ── Debug-UUID → alles loggen ────────────────────────────────────────────
    if profile_id == DEBUG_PROFILE_ID:
        return _handle_debug(method, headers, body_bytes, source)

    # ── GET = Health-Check ────────────────────────────────────────────────────
    if method == "GET":
        return 200, {
            "status": "ok",
            "profile_id": profile_id,
            "endpoint": f"/capture/webhook/{profile_id}",
        }

    # ── Nur POST akzeptieren ─────────────────────────────────────────────────
    if method != "POST":
        return 405, {"errorMessage": "Method not allowed"}

    # ── 1. Profil laden ──────────────────────────────────────────────────────
    from db import get_capture_profile_for_webhook, add_capture_log

    logger.info("[%s] ━━━ Webhook empfangen: profile=%s ━━━", source, profile_id[:8])

    profile = get_capture_profile_for_webhook(profile_id)
    if not profile:
        logger.warning("[%s] Profil nicht gefunden: %s", source, profile_id)
        return 404, {"errorMessage": "Unknown profile"}

    tenant_id = profile["tenant_id"]
    profile_name = profile.get("name", "?")
    plugin_type = profile.get("plugin_type", "")

    logger.info("[%s] Profil: name=%s plugin=%s active=%s",
                source, profile_name, plugin_type, profile.get("is_active"))

    # ── 2. HMAC verifizieren ─────────────────────────────────────────────────
    from capture.hmac_verify import verify_hmac

    secret_key = profile.get("secret_key", "")
    if not verify_hmac(body_bytes, headers, secret_key):
        logger.warning("[%s] HMAC fehlgeschlagen für Profil %s", source, profile_id[:8])
        add_capture_log(tenant_id, profile_id, profile_name,
                        "signature_failed", "error", "HMAC signature verification failed")
        return 401, {"errorMessage": "Signature verification failed"}

    logger.info("[%s] HMAC: OK (secret=%s)", source,
                "configured" if secret_key else "none")

    # ── 3. Body parsen ───────────────────────────────────────────────────────
    try:
        body = json.loads(body_bytes) if body_bytes else {}
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("[%s] JSON parse error: %s (body=%s)",
                     source, e, body_bytes[:200].decode("utf-8", errors="replace"))
        add_capture_log(tenant_id, profile_id, profile_name,
                        "parse_error", "error",
                        f"Invalid JSON ({len(body_bytes)} bytes): {e}")
        return 400, {"errorMessage": "Invalid JSON"}

    logger.info("[%s] Body: %d bytes, keys=%s",
                source, len(body_bytes), list(body.keys()))

    # ── 4. Felder extrahieren (Printix-Format-Varianten) ─────────────────────
    event_type = (body.get("eventType")
                  or body.get("EventType", "unknown"))
    document_url = (body.get("documentUrl")
                    or body.get("DocumentUrl")
                    or body.get("documentURL")
                    or body.get("blobUrl", ""))
    filename = (body.get("fileName")
                or body.get("FileName")
                or body.get("name", "scan.pdf"))
    metadata = body.get("metadata", body.get("Metadata", {}))

    logger.info("[%s] Parsed: event=%s file=%s url=%s...",
                source, event_type, filename,
                document_url[:80] if document_url else "(none)")

    if not document_url:
        logger.warning("[%s] Keine Document-URL im Payload", source)
        add_capture_log(tenant_id, profile_id, profile_name,
                        event_type, "error",
                        f"No document URL in payload. Keys: {list(body.keys())}")
        return 400, {"errorMessage": "No document URL found in payload"}

    # ── 5. Plugin laden und Dokument verarbeiten ─────────────────────────────
    from capture.base_plugin import create_plugin_instance

    plugin = create_plugin_instance(plugin_type, profile.get("config_json", "{}"))
    if not plugin:
        logger.error("[%s] Plugin '%s' nicht gefunden", source, plugin_type)
        add_capture_log(tenant_id, profile_id, profile_name,
                        event_type, "error", f"Unknown plugin: {plugin_type}")
        return 500, {"errorMessage": f"Unknown plugin: {plugin_type}"}

    logger.info("[%s] Plugin geladen: %s (%s)", source, plugin.plugin_name, plugin_type)

    try:
        ok, msg = await plugin.process_document(document_url, filename, metadata, body)
    except Exception as e:
        logger.exception("[%s] Plugin-Fehler: %s", source, e)
        ok, msg = False, str(e)

    logger.info("[%s] Ergebnis: ok=%s msg=%s", source, ok, msg[:200] if msg else "")

    # ── 6. Capture-Log schreiben ─────────────────────────────────────────────
    add_capture_log(tenant_id, profile_id, profile_name,
                    event_type, "ok" if ok else "error", msg or "")

    # ── 7. Printix-kompatible Antwort ────────────────────────────────────────
    # Printix Capture Connector Protokoll:
    #   HTTP 200 + errorMessage="" → Erfolg
    #   HTTP 200 + errorMessage="..." → Plugin-Fehler (Printix zeigt Meldung)
    # HTTP 4xx/5xx nur bei Infrastruktur-Fehlern (Profil/HMAC/JSON).
    if ok:
        return 200, {"errorMessage": ""}
    else:
        return 200, {"errorMessage": msg}


def _handle_debug(
    method: str,
    headers: dict[str, str],
    body_bytes: bytes,
    source: str,
) -> tuple[int, dict[str, Any]]:
    """Debug-Endpoint: loggt alles, akzeptiert alles."""
    body_parsed = None
    body_text = ""
    try:
        body_parsed = json.loads(body_bytes) if body_bytes else None
    except Exception:
        body_text = body_bytes.decode("utf-8", errors="replace")[:2000] if body_bytes else ""

    debug_info = {
        "timestamp": datetime.now().isoformat(),
        "method": method,
        "source": source,
        "headers": headers,
        "body_size": len(body_bytes),
        "body_json": body_parsed,
        "body_text": body_text if not body_parsed else "",
    }

    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("  CAPTURE DEBUG (%s)", source)
    logger.info("  Method:  %s", method)
    logger.info("  Headers:")
    for k, v in headers.items():
        logger.info("    %s: %s", k, v)
    logger.info("  Body (%d bytes):", len(body_bytes))
    if body_parsed:
        for k, v in body_parsed.items():
            logger.info("    %s: %s", k, str(v)[:200])
    elif body_text:
        logger.info("    (raw) %s", body_text[:500])
    else:
        logger.info("    (empty)")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    return 200, {
        "status": "ok",
        "message": "Debug info logged — check add-on logs",
        "received": debug_info,
    }
