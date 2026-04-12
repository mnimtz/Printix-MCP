"""
Capture Store Routes — Web-UI für Capture-Profil-Verwaltung (v4.4.0)
====================================================================
Registriert alle /capture-Routen in der FastAPI-App.

Aufruf aus app.py:
    from web.capture_routes import register_capture_routes
    register_capture_routes(app, templates, t_ctx, require_login)

Routen:
  GET  /capture                       → Capture Store (Übersicht)
  GET  /capture/new                   → Neues Profil anlegen
  POST /capture/new                   → Profil speichern (neu)
  GET  /capture/{id}/edit             → Profil bearbeiten
  POST /capture/{id}/edit             → Profil speichern (Update)
  POST /capture/{id}/delete           → Profil löschen
  POST /capture/{id}/toggle           → Profil aktivieren/deaktivieren
  POST /capture/{id}/test             → Verbindungstest
  POST /capture/webhook/{profile_id}  → Printix Capture Webhook Endpoint
"""

import json
import logging
from typing import Callable, Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger("printix.capture")


def register_capture_routes(
    app: FastAPI,
    templates: Jinja2Templates,
    t_ctx: Callable,
    require_login: Callable,
) -> None:
    """Registriert alle Capture-Store-Routen."""

    # ── Import plugins (triggers @register_plugin) ──────────────────────────
    from capture.base_plugin import get_all_plugins, create_plugin_instance
    import capture.plugin_paperless  # noqa: F401 — registers PaperlessNgxPlugin

    # ── Helper: get tenant for current user ─────────────────────────────────
    def _get_tenant(user: dict) -> Optional[dict]:
        from db import get_tenant_by_user_id
        return get_tenant_by_user_id(user["id"])

    def _get_webhook_base(request: Request) -> tuple:
        """
        Webhook Base-URL: MCP_PUBLIC_URL (env) > public_url (DB) > request URL.
        Returns (base_url, is_configured) — is_configured=False means fallback.
        """
        import os
        wb = os.environ.get("MCP_PUBLIC_URL", "").strip().rstrip("/")
        if wb:
            return wb, True
        try:
            from db import get_setting
            wb = get_setting("public_url", "").strip().rstrip("/")
        except Exception:
            pass
        if wb:
            return wb, True
        # Fallback: request URL — wahrscheinlich FALSCH für Webhooks
        return f"{request.url.scheme}://{request.url.netloc}", False

    # ── GET /capture — Store Overview ───────────────────────────────────────

    @app.get("/capture", response_class=HTMLResponse)
    async def capture_store(request: Request):
        user = require_login(request)
        if not user:
            return RedirectResponse("/login", status_code=303)

        tenant = _get_tenant(user)
        if not tenant:
            return RedirectResponse("/settings", status_code=303)

        from db import get_capture_profiles_by_tenant
        import asyncio
        profiles = await asyncio.to_thread(get_capture_profiles_by_tenant, tenant["id"])

        # Parse config for display
        for p in profiles:
            try:
                p["_config"] = json.loads(p.get("config_json", "{}"))
            except (json.JSONDecodeError, TypeError):
                p["_config"] = {}

        plugins = get_all_plugins()
        plugin_info = []
        for pid, cls in plugins.items():
            plugin_info.append({
                "id": cls.plugin_id,
                "name": cls.plugin_name,
                "icon": cls.plugin_icon,
                "description": cls.plugin_description,
                "color": cls.plugin_color,
            })

        ctx = t_ctx(request)
        ctx.update({
            "request": request,
            "user": user,
            "tenant": tenant,
            "profiles": profiles,
            "plugins": plugin_info,
            "profiles_count": len(profiles),
            "active_count": sum(1 for p in profiles if p["is_active"]),
            "webhook_base": _get_webhook_base(request)[0],
            "webhook_base_configured": _get_webhook_base(request)[1],
        })
        return templates.TemplateResponse("capture_store.html", ctx)

    # ── GET /capture/new — New Profile Form ─────────────────────────────────

    @app.get("/capture/new", response_class=HTMLResponse)
    async def capture_new_form(request: Request):
        user = require_login(request)
        if not user:
            return RedirectResponse("/login", status_code=303)

        tenant = _get_tenant(user)
        if not tenant:
            return RedirectResponse("/settings", status_code=303)

        plugin_type = request.query_params.get("plugin", "paperless_ngx")
        plugin_instance = create_plugin_instance(plugin_type)
        if not plugin_instance:
            return RedirectResponse("/capture", status_code=303)

        ctx = t_ctx(request)
        ctx.update({
            "request": request,
            "user": user,
            "tenant": tenant,
            "mode": "create",
            "profile": None,
            "plugin": {
                "id": plugin_instance.plugin_id,
                "name": plugin_instance.plugin_name,
                "icon": plugin_instance.plugin_icon,
                "color": plugin_instance.plugin_color,
            },
            "config_fields": plugin_instance.config_schema(),
            "config_values": {},
            "error": "",
            "webhook_base": _get_webhook_base(request)[0],
        })
        return templates.TemplateResponse("capture_form.html", ctx)

    # ── POST /capture/new — Create Profile ──────────────────────────────────

    @app.post("/capture/new", response_class=HTMLResponse)
    async def capture_new_save(request: Request):
        user = require_login(request)
        if not user:
            return RedirectResponse("/login", status_code=303)

        tenant = _get_tenant(user)
        if not tenant:
            return RedirectResponse("/settings", status_code=303)

        form = await request.form()
        name = form.get("name", "").strip()
        plugin_type = form.get("plugin_type", "paperless_ngx")
        secret_key = form.get("secret_key", "").strip()
        connector_token = form.get("connector_token", "").strip()

        plugin_instance = create_plugin_instance(plugin_type)
        if not plugin_instance:
            return RedirectResponse("/capture", status_code=303)

        # Build config from form fields
        config = {}
        for field in plugin_instance.config_schema():
            val = form.get(f"cfg_{field['key']}", "").strip()
            config[field["key"]] = val

        # Validate
        if not name:
            ctx = t_ctx(request)
            ctx.update({
                "request": request, "user": user, "tenant": tenant,
                "mode": "create", "profile": None,
                "plugin": {
                    "id": plugin_instance.plugin_id,
                    "name": plugin_instance.plugin_name,
                    "icon": plugin_instance.plugin_icon,
                    "color": plugin_instance.plugin_color,
                },
                "config_fields": plugin_instance.config_schema(),
                "config_values": config,
                "error": "Name is required",
                "webhook_base": _get_webhook_base(request)[0],
            })
            return templates.TemplateResponse("capture_form.html", ctx)

        from db import create_capture_profile
        import asyncio
        config_json = json.dumps(config)
        profile = await asyncio.to_thread(
            create_capture_profile,
            tenant_id=tenant["id"],
            name=name,
            plugin_type=plugin_type,
            secret_key=secret_key,
            connector_token=connector_token,
            config_json=config_json,
        )

        if profile:
            from db import add_tenant_log
            await asyncio.to_thread(
                add_tenant_log, tenant["id"], "INFO", "CAPTURE",
                f"Profile created: {name} ({plugin_type})"
            )

        return RedirectResponse("/capture", status_code=303)

    # ── GET /capture/{id}/edit — Edit Profile Form ──────────────────────────

    @app.get("/capture/{profile_id}/edit", response_class=HTMLResponse)
    async def capture_edit_form(request: Request, profile_id: str):
        user = require_login(request)
        if not user:
            return RedirectResponse("/login", status_code=303)

        tenant = _get_tenant(user)
        if not tenant:
            return RedirectResponse("/settings", status_code=303)

        from db import get_capture_profile
        import asyncio
        profile = await asyncio.to_thread(get_capture_profile, profile_id)
        if not profile or profile["tenant_id"] != tenant["id"]:
            return RedirectResponse("/capture", status_code=303)

        plugin_instance = create_plugin_instance(profile["plugin_type"], profile.get("config_json", "{}"))
        if not plugin_instance:
            return RedirectResponse("/capture", status_code=303)

        try:
            config_values = json.loads(profile.get("config_json", "{}"))
        except (json.JSONDecodeError, TypeError):
            config_values = {}

        ctx = t_ctx(request)
        ctx.update({
            "request": request, "user": user, "tenant": tenant,
            "mode": "edit", "profile": profile,
            "plugin": {
                "id": plugin_instance.plugin_id,
                "name": plugin_instance.plugin_name,
                "icon": plugin_instance.plugin_icon,
                "color": plugin_instance.plugin_color,
            },
            "config_fields": plugin_instance.config_schema(),
            "config_values": config_values,
            "error": "",
            "webhook_base": _get_webhook_base(request)[0],
        })
        return templates.TemplateResponse("capture_form.html", ctx)

    # ── POST /capture/{id}/edit — Update Profile ────────────────────────────

    @app.post("/capture/{profile_id}/edit", response_class=HTMLResponse)
    async def capture_edit_save(request: Request, profile_id: str):
        user = require_login(request)
        if not user:
            return RedirectResponse("/login", status_code=303)

        tenant = _get_tenant(user)
        if not tenant:
            return RedirectResponse("/settings", status_code=303)

        from db import get_capture_profile, update_capture_profile
        import asyncio
        profile = await asyncio.to_thread(get_capture_profile, profile_id)
        if not profile or profile["tenant_id"] != tenant["id"]:
            return RedirectResponse("/capture", status_code=303)

        form = await request.form()
        name = form.get("name", "").strip()
        secret_key = form.get("secret_key", "").strip()
        connector_token = form.get("connector_token", "").strip()

        plugin_instance = create_plugin_instance(profile["plugin_type"])
        if not plugin_instance:
            return RedirectResponse("/capture", status_code=303)

        config = {}
        for field in plugin_instance.config_schema():
            val = form.get(f"cfg_{field['key']}", "").strip()
            config[field["key"]] = val

        config_json = json.dumps(config)

        await asyncio.to_thread(
            update_capture_profile,
            profile_id=profile_id,
            name=name or None,
            secret_key=secret_key if secret_key else None,
            connector_token=connector_token if connector_token else None,
            config_json=config_json,
        )

        from db import add_tenant_log
        await asyncio.to_thread(
            add_tenant_log, tenant["id"], "INFO", "CAPTURE",
            f"Profile updated: {name or profile['name']}"
        )

        return RedirectResponse("/capture", status_code=303)

    # ── POST /capture/{id}/delete — Delete Profile ──────────────────────────

    @app.post("/capture/{profile_id}/delete")
    async def capture_delete(request: Request, profile_id: str):
        user = require_login(request)
        if not user:
            return RedirectResponse("/login", status_code=303)

        tenant = _get_tenant(user)
        if not tenant:
            return RedirectResponse("/settings", status_code=303)

        from db import get_capture_profile, delete_capture_profile, add_tenant_log
        import asyncio
        profile = await asyncio.to_thread(get_capture_profile, profile_id)
        if not profile or profile["tenant_id"] != tenant["id"]:
            return RedirectResponse("/capture", status_code=303)

        await asyncio.to_thread(delete_capture_profile, profile_id)
        await asyncio.to_thread(
            add_tenant_log, tenant["id"], "WARNING", "CAPTURE",
            f"Profile deleted: {profile['name']}"
        )

        return RedirectResponse("/capture", status_code=303)

    # ── POST /capture/{id}/toggle — Activate/Deactivate ────────────────────

    @app.post("/capture/{profile_id}/toggle")
    async def capture_toggle(request: Request, profile_id: str):
        user = require_login(request)
        if not user:
            return RedirectResponse("/login", status_code=303)

        tenant = _get_tenant(user)
        if not tenant:
            return RedirectResponse("/settings", status_code=303)

        from db import get_capture_profile, update_capture_profile
        import asyncio
        profile = await asyncio.to_thread(get_capture_profile, profile_id)
        if not profile or profile["tenant_id"] != tenant["id"]:
            return RedirectResponse("/capture", status_code=303)

        new_state = not profile["is_active"]
        await asyncio.to_thread(update_capture_profile, profile_id, is_active=new_state)

        return RedirectResponse("/capture", status_code=303)

    # ── POST /capture/{id}/test — Connection Test ───────────────────────────

    @app.post("/capture/{profile_id}/test")
    async def capture_test(request: Request, profile_id: str):
        user = require_login(request)
        if not user:
            return JSONResponse({"ok": False, "message": "Not logged in"}, status_code=401)

        tenant = _get_tenant(user)
        if not tenant:
            return JSONResponse({"ok": False, "message": "No tenant"}, status_code=400)

        from db import get_capture_profile, add_tenant_log
        import asyncio
        profile = await asyncio.to_thread(get_capture_profile, profile_id)
        if not profile or profile["tenant_id"] != tenant["id"]:
            return JSONResponse({"ok": False, "message": "Profile not found"}, status_code=404)

        plugin = create_plugin_instance(profile["plugin_type"], profile.get("config_json", "{}"))
        if not plugin:
            return JSONResponse({"ok": False, "message": "Unknown plugin type"})

        try:
            ok, msg = await plugin.test_connection()
        except Exception as e:
            logger.exception("Capture test_connection error: %s", e)
            ok, msg = False, f"Server error: {e}"

        # Log result
        await asyncio.to_thread(
            add_tenant_log, tenant["id"],
            "INFO" if ok else "WARNING", "CAPTURE",
            f"Connection test for '{profile['name']}': {'OK' if ok else 'FAILED'} — {msg}"
        )

        return JSONResponse({"ok": ok, "message": msg})

    # ── Debug-UUID — Printix akzeptiert nur /capture/webhook/{uuid} ────────
    DEBUG_PROFILE_ID = "00000000-0000-0000-0000-000000000000"

    # ── POST /capture/webhook/{profile_id} — Printix Capture Webhook ───────

    @app.post("/capture/webhook/{profile_id}")
    async def capture_webhook_handler(request: Request, profile_id: str):
        """
        Empfängt Printix Capture Notifications für ein bestimmtes Profil.
        URL-Format: /capture/webhook/{profile_id}
        Printix Connector URL: https://{FQDN}:{port}/capture/webhook/{profileId}

        Spezial: profile_id == DEBUG_PROFILE_ID → Debug-Modus (loggt alles).
        """
        # Debug-UUID → direkt an Debug-Handler weiterleiten
        if profile_id == DEBUG_PROFILE_ID:
            return await capture_debug(request)

        from capture.hmac_verify import verify_hmac
        from db import get_capture_profile_for_webhook, add_capture_log
        import asyncio

        logger.info("━━━ Capture Webhook empfangen: profile=%s method=%s ━━━",
                     profile_id[:8], request.method)
        logger.info("  Headers: %s", dict(request.headers))

        # 1. Profil laden
        profile = await asyncio.to_thread(get_capture_profile_for_webhook, profile_id)
        if not profile:
            logger.warning("Capture webhook: unknown or inactive profile %s", profile_id)
            return JSONResponse({"error": "Unknown profile"}, status_code=404)

        logger.info("  Profile found: name=%s plugin=%s active=%s",
                     profile["name"], profile["plugin_type"], profile.get("is_active"))

        # 2. Body lesen
        body_bytes = await request.body()
        headers_dict = {k.lower(): v for k, v in request.headers.items()}
        logger.info("  Body: %d bytes, Content-Type: %s",
                     len(body_bytes), headers_dict.get("content-type", "?"))

        # v4.4.1: Body-Preview für Debugging (erste 500 Zeichen)
        if body_bytes:
            logger.info("  Body preview: %s", body_bytes[:500].decode("utf-8", errors="replace"))

        # 3. HMAC verifizieren
        if not verify_hmac(body_bytes, headers_dict, profile.get("secret_key", "")):
            logger.warning("Capture webhook: HMAC verification failed for profile %s", profile_id)
            await asyncio.to_thread(
                add_capture_log, profile["tenant_id"], profile_id, profile["name"],
                "signature_failed", "error", "HMAC signature verification failed",
            )
            return JSONResponse({"error": "Signature verification failed"}, status_code=401)

        # 4. Body parsen
        try:
            body = json.loads(body_bytes)
        except (json.JSONDecodeError, ValueError) as parse_err:
            logger.error("Capture webhook: JSON parse error: %s (body=%s)",
                         parse_err, body_bytes[:200].decode("utf-8", errors="replace"))
            await asyncio.to_thread(
                add_capture_log, profile["tenant_id"], profile_id, profile["name"],
                "parse_error", "error",
                f"Invalid JSON body ({len(body_bytes)} bytes): {parse_err}",
            )
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        event_type = body.get("eventType", body.get("EventType", "unknown"))
        document_url = body.get("documentUrl", body.get("DocumentUrl",
                       body.get("documentURL", body.get("blobUrl", ""))))
        filename = body.get("fileName", body.get("FileName",
                   body.get("name", "scan.pdf")))
        metadata = body.get("metadata", body.get("Metadata", {}))

        logger.info(
            "  Parsed: event=%s file=%s docUrl=%s...",
            event_type, filename, document_url[:80] if document_url else "(none)",
        )
        logger.info("  Full body keys: %s", list(body.keys()))

        # 5. Plugin-Verarbeitung
        plugin = create_plugin_instance(profile["plugin_type"], profile.get("config_json", "{}"))
        if not plugin:
            await asyncio.to_thread(
                add_capture_log, profile["tenant_id"], profile_id, profile["name"],
                event_type, "error", f"Unknown plugin: {profile['plugin_type']}",
            )
            return JSONResponse({"errorMessage": f"Unknown plugin: {profile['plugin_type']}"})

        try:
            ok, msg = await plugin.process_document(document_url, filename, metadata, body)
        except Exception as e:
            logger.exception("Capture plugin error: %s", e)
            ok, msg = False, str(e)

        logger.info("  Result: ok=%s msg=%s", ok, msg[:200] if msg else "")

        # 6. Log
        await asyncio.to_thread(
            add_capture_log, profile["tenant_id"], profile_id, profile["name"],
            event_type, "ok" if ok else "error", msg,
        )

        # 7. Callback-Antwort (Printix-Format)
        if ok:
            return JSONResponse({"errorMessage": ""})
        else:
            return JSONResponse({"errorMessage": msg})

    # ── GET /capture/webhook/{profile_id} — Health Check ────────────────────

    @app.get("/capture/webhook/{profile_id}")
    async def capture_webhook_health(request: Request, profile_id: str):
        """Health-Check: Printix prüft ob der Endpoint erreichbar ist."""
        # Debug-UUID → auch GET an Debug-Handler
        if profile_id == DEBUG_PROFILE_ID:
            return await capture_debug(request)
        return JSONResponse({
            "status": "ok",
            "profile_id": profile_id,
            "endpoint": f"/capture/webhook/{profile_id}",
        })

    # ── Debug Endpoint — loggt ALLES was reinkommt ────────────────────────

    @app.api_route("/capture/debug", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def capture_debug(request: Request):
        """
        Debug-Endpoint: Loggt alle Details eines eingehenden Requests.
        Nützlich um zu sehen was Printix genau sendet.
        URL: /capture/debug
        """
        body_bytes = await request.body()
        headers_dict = dict(request.headers)
        query_params = dict(request.query_params)

        # Body parsen (versuchen)
        body_parsed = None
        body_text = ""
        try:
            body_parsed = json.loads(body_bytes) if body_bytes else None
        except Exception:
            body_text = body_bytes.decode("utf-8", errors="replace")[:2000] if body_bytes else ""

        debug_info = {
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": query_params,
            "headers": headers_dict,
            "body_size": len(body_bytes),
            "body_json": body_parsed,
            "body_text": body_text if not body_parsed else "",
            "client": f"{request.client.host}:{request.client.port}" if request.client else "unknown",
        }

        # In Server-Log ausgeben
        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info("  CAPTURE DEBUG ENDPOINT")
        logger.info("  Method:  %s", request.method)
        logger.info("  URL:     %s", request.url)
        logger.info("  Client:  %s", debug_info["client"])
        logger.info("  Headers:")
        for k, v in headers_dict.items():
            logger.info("    %s: %s", k, v)
        logger.info("  Query:   %s", query_params)
        logger.info("  Body (%d bytes):", len(body_bytes))
        if body_parsed:
            for k, v in body_parsed.items():
                val_str = str(v)
                if len(val_str) > 200:
                    val_str = val_str[:200] + "..."
                logger.info("    %s: %s", k, val_str)
        elif body_text:
            logger.info("    (raw) %s", body_text[:500])
        else:
            logger.info("    (empty)")
        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        # Auch ins Capture-Log schreiben (falls ein User eingeloggt ist)
        try:
            user = require_login(request)
            if user:
                from db import get_tenant_by_user_id, add_tenant_log
                import asyncio
                tenant = get_tenant_by_user_id(user["id"])
                if tenant:
                    summary = (
                        f"DEBUG {request.method} | "
                        f"Body: {len(body_bytes)}B | "
                        f"Keys: {list(body_parsed.keys()) if body_parsed else '(none)'}"
                    )
                    await asyncio.to_thread(
                        add_tenant_log, tenant["id"], "INFO", "CAPTURE",
                        f"[Debug Endpoint] {summary}"
                    )
        except Exception:
            pass

        return JSONResponse({
            "status": "ok",
            "message": "Debug info logged — check server logs and /logs (CAPTURE category)",
            "received": debug_info,
        })

    @app.api_route("/capture/debug/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def capture_debug_subpath(request: Request, path: str):
        """Catch-all für Debug mit Sub-Pfad."""
        return await capture_debug(request)
