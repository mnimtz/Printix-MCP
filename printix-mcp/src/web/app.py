"""
Printix MCP — Web-Verwaltungsoberfläche (FastAPI)
==================================================

Routen:
  GET  /                          → Redirect je nach Zustand
  GET  /register                  → Schritt 1: Account
  POST /register                  → Account speichern
  GET  /register/api              → Schritt 2: Printix API-Credentials
  POST /register/api              → API speichern
  GET  /register/optional         → Schritt 3: SQL + Mail (optional)
  POST /register/optional         → Optional speichern
  GET  /register/summary          → Schritt 4: Zusammenfassung
  POST /register/summary          → User + Tenant anlegen

  GET  /login                     → Login-Seite
  POST /login                     → Login prüfen → Redirect
  GET  /logout                    → Session löschen → Redirect /login
  GET  /pending                   → Warteseite für noch nicht genehmigte User

  GET  /dashboard                 → Benutzer-Dashboard
  GET  /settings                  → Credentials / API-Daten bearbeiten (Selbstverwaltung)
  POST /settings                  → Credentials speichern
  POST /settings/regenerate-oauth → OAuth-Secret neu generieren
  GET  /settings/password         → Passwort ändern
  POST /settings/password         → Passwort ändern speichern
  GET  /help                      → Verbindungsanleitung (personalisiert)

  GET  /admin                     → Admin-Dashboard
  GET  /admin/users               → Benutzerliste
  POST /admin/users/{id}/approve  → User genehmigen
  POST /admin/users/{id}/disable  → User deaktivieren / sperren
  POST /admin/users/{id}/delete   → User löschen (inkl. Tenant)
  GET  /admin/users/{id}/edit     → User bearbeiten
  POST /admin/users/{id}/edit     → User-Edit speichern
  GET  /admin/users/create        → Admin: neuen User anlegen
  POST /admin/users/create        → Admin: neuen User speichern
  GET  /admin/audit               → Audit-Log
  GET  /admin/settings            → Server-Einstellungen (Base URL etc.)
  POST /admin/settings            → Server-Einstellungen speichern

  GET  /lang/{code}               → Sprache wechseln (EFIGS)
"""

import os
import logging
from typing import Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

logger = logging.getLogger("printix.web")

# Templates-Verzeichnis (relativ zu diesem File)
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")


def create_app(session_secret: str) -> FastAPI:
    app = FastAPI(title="Printix MCP Admin", docs_url=None, redoc_url=None)
    app.add_middleware(SessionMiddleware, secret_key=session_secret, max_age=3600 * 8)

    templates = Jinja2Templates(directory=TEMPLATES_DIR)

    # ── i18n ──────────────────────────────────────────────────────────────────

    from i18n import (
        detect_language, make_translator,
        SUPPORTED_LANGUAGES, LANGUAGE_NAMES, DEFAULT_LANGUAGE,
    )

    def get_lang(request: Request) -> str:
        """Gibt den aktiven Sprachcode zurück (Session → Accept-Language → Default)."""
        lang = request.session.get("lang")
        if lang in SUPPORTED_LANGUAGES:
            return lang
        return detect_language(request.headers.get("accept-language"))

    def t_ctx(request: Request) -> dict:
        """Gibt den i18n-Kontext für Templates zurück."""
        lang = get_lang(request)
        ctx = {
            "_":             make_translator(lang),
            "lang":          lang,
            "lang_names":    LANGUAGE_NAMES,
            "supported_langs": SUPPORTED_LANGUAGES,
        }
        # v3.9.0 — Badge "offene Tickets" im Nav (nur für Admins relevant)
        try:
            from db import count_feature_requests_by_status
            counts = count_feature_requests_by_status()
            ctx["feedback_new_count"] = counts.get("new", 0)
        except Exception:
            ctx["feedback_new_count"] = 0
        return ctx

    # ── Helpers ────────────────────────────────────────────────────────────────

    def get_session_user(request: Request) -> Optional[dict]:
        user_id = request.session.get("user_id")
        if not user_id:
            return None
        try:
            from db import get_user_by_id
            return get_user_by_id(user_id)
        except Exception:
            return None

    def require_login(request: Request) -> Optional[dict]:
        user = get_session_user(request)
        if not user:
            return None
        if user.get("status") != "approved":
            return None
        return user

    def mcp_base_url() -> str:
        """Gibt die öffentliche MCP-Basis-URL zurück (DB-Setting > ENV > Fallback)."""
        try:
            from db import get_setting
            db_url = get_setting("public_url", "")
            if db_url:
                return db_url.rstrip("/")
        except Exception:
            pass
        env_url = os.environ.get("MCP_PUBLIC_URL", "").rstrip("/")
        if env_url:
            return env_url
        return "http://<HA-IP>:8765"

    # ── Sprach-Route ──────────────────────────────────────────────────────────

    @app.get("/lang/{code}", response_class=RedirectResponse)
    async def switch_language(code: str, request: Request):
        if code in SUPPORTED_LANGUAGES:
            request.session["lang"] = code
        # Open-Redirect-Schutz: Referer-Header darf nur zurückführen, wenn er
        # same-origin ist. Andernfalls fallen wir auf "/" zurück.
        referer = request.headers.get("referer", "")
        safe_target = "/"
        if referer:
            try:
                from urllib.parse import urlparse
                ref = urlparse(referer)
                if not ref.netloc or ref.netloc == request.url.netloc:
                    # Relative Pfade oder gleiche Origin akzeptieren
                    safe_target = referer
            except Exception:
                safe_target = "/"
        return RedirectResponse(safe_target, status_code=302)

    # ── Root ──────────────────────────────────────────────────────────────────

    @app.get("/", response_class=RedirectResponse)
    async def root(request: Request):
        try:
            from db import has_users
            if not has_users():
                return RedirectResponse("/register", status_code=302)
        except Exception:
            return RedirectResponse("/register", status_code=302)
        user = get_session_user(request)
        if user and user.get("is_admin"):
            return RedirectResponse("/admin", status_code=302)
        if user:
            return RedirectResponse("/dashboard", status_code=302)
        return RedirectResponse("/login", status_code=302)

    # ── Registrierung ─────────────────────────────────────────────────────────

    @app.get("/register", response_class=HTMLResponse)
    async def register_step1_get(request: Request):
        return templates.TemplateResponse("register_step1.html", {
            "request": request, "step": 1, "error": None, **t_ctx(request)
        })

    @app.post("/register", response_class=HTMLResponse)
    async def register_step1_post(
        request: Request,
        username:  str = Form(...),
        password:  str = Form(...),
        password2: str = Form(...),
        email:     str = Form(default=""),
        full_name: str = Form(default=""),
        company:   str = Form(default=""),
    ):
        tc = t_ctx(request)
        _  = tc["_"]
        error = None
        if len(username) < 3:
            error = "Benutzername muss mindestens 3 Zeichen lang sein."
        elif len(password) < 8:
            error = "Passwort muss mindestens 8 Zeichen lang sein."
        elif password != password2:
            error = _("reg_pw_mismatch")
        else:
            try:
                from db import username_exists
                if username_exists(username):
                    error = _("reg_user_exists")
            except Exception as e:
                error = f"Datenbankfehler: {e}"

        if error:
            return templates.TemplateResponse("register_step1.html", {
                "request": request, "step": 1, "error": error,
                "username": username, "email": email,
                "full_name": full_name, "company": company, **tc,
            })

        request.session["reg_username"]  = username
        request.session["reg_password"]  = password
        request.session["reg_email"]     = email
        request.session["reg_full_name"] = full_name
        request.session["reg_company"]   = company
        return RedirectResponse("/register/api", status_code=302)

    @app.get("/register/api", response_class=HTMLResponse)
    async def register_step2_get(request: Request):
        if "reg_username" not in request.session:
            return RedirectResponse("/register", status_code=302)
        return templates.TemplateResponse("register_step2.html", {
            "request": request, "step": 2, "error": None, **t_ctx(request)
        })

    @app.post("/register/api", response_class=HTMLResponse)
    async def register_step2_post(
        request: Request,
        printix_tenant_id:     str = Form(...),
        print_client_id:       str = Form(default=""),
        print_client_secret:   str = Form(default=""),
        card_client_id:        str = Form(default=""),
        card_client_secret:    str = Form(default=""),
        ws_client_id:          str = Form(default=""),
        ws_client_secret:      str = Form(default=""),
        shared_client_id:      str = Form(default=""),
        shared_client_secret:  str = Form(default=""),
        tenant_name:           str = Form(default=""),
    ):
        if "reg_username" not in request.session:
            return RedirectResponse("/register", status_code=302)
        tc = t_ctx(request)

        if not printix_tenant_id.strip():
            return templates.TemplateResponse("register_step2.html", {
                "request": request, "step": 2,
                "error": "Printix Tenant-ID ist Pflichtfeld.", **tc,
            })

        has_creds = any([
            print_client_id and print_client_secret,
            card_client_id and card_client_secret,
            ws_client_id and ws_client_secret,
            shared_client_id and shared_client_secret,
        ])
        if not has_creds:
            return templates.TemplateResponse("register_step2.html", {
                "request": request, "step": 2,
                "error": "Mindestens ein vollständiges API-Credentials-Paar wird benötigt.",
                "printix_tenant_id": printix_tenant_id, "tenant_name": tenant_name, **tc,
            })

        request.session["reg_tenant_id"]           = printix_tenant_id.strip()
        request.session["reg_tenant_name"]          = tenant_name.strip() or printix_tenant_id.strip()
        request.session["reg_print_client_id"]      = print_client_id.strip()
        request.session["reg_print_client_secret"]  = print_client_secret.strip()
        request.session["reg_card_client_id"]       = card_client_id.strip()
        request.session["reg_card_client_secret"]   = card_client_secret.strip()
        request.session["reg_ws_client_id"]         = ws_client_id.strip()
        request.session["reg_ws_client_secret"]     = ws_client_secret.strip()
        request.session["reg_shared_client_id"]     = shared_client_id.strip()
        request.session["reg_shared_client_secret"] = shared_client_secret.strip()
        return RedirectResponse("/register/optional", status_code=302)

    @app.get("/register/optional", response_class=HTMLResponse)
    async def register_step3_get(request: Request):
        if "reg_tenant_id" not in request.session:
            return RedirectResponse("/register", status_code=302)
        return templates.TemplateResponse("register_step3.html", {
            "request": request, "step": 3, "error": None, **t_ctx(request)
        })

    @app.post("/register/optional", response_class=HTMLResponse)
    async def register_step3_post(
        request: Request,
        sql_server:   str = Form(default=""),
        sql_database: str = Form(default="printix_bi_data_2_1"),
        sql_username: str = Form(default=""),
        sql_password: str = Form(default=""),
        mail_api_key: str = Form(default=""),
        mail_from:    str = Form(default=""),
    ):
        if "reg_tenant_id" not in request.session:
            return RedirectResponse("/register", status_code=302)

        request.session["reg_sql_server"]   = sql_server.strip()
        request.session["reg_sql_database"] = sql_database.strip()
        request.session["reg_sql_username"] = sql_username.strip()
        request.session["reg_sql_password"] = sql_password.strip()
        request.session["reg_mail_api_key"] = mail_api_key.strip()
        request.session["reg_mail_from"]    = mail_from.strip()
        return RedirectResponse("/register/summary", status_code=302)

    @app.get("/register/summary", response_class=HTMLResponse)
    async def register_step4_get(request: Request):
        if "reg_tenant_id" not in request.session:
            return RedirectResponse("/register", status_code=302)

        base = mcp_base_url()
        return templates.TemplateResponse("register_step4.html", {
            "request": request, "step": 4,
            "username":       request.session.get("reg_username", ""),
            "email":          request.session.get("reg_email", ""),
            "tenant_id":      request.session.get("reg_tenant_id", ""),
            "tenant_name":    request.session.get("reg_tenant_name", ""),
            "sql_configured": bool(request.session.get("reg_sql_server")),
            "mail_configured":bool(request.session.get("reg_mail_api_key")),
            "base_url": base,
            "error": None, **t_ctx(request),
        })

    @app.post("/register/summary", response_class=HTMLResponse)
    async def register_step4_post(request: Request):
        if "reg_tenant_id" not in request.session:
            return RedirectResponse("/register", status_code=302)

        base = mcp_base_url()
        tc   = t_ctx(request)

        try:
            from db import create_user, create_tenant, has_users, audit

            is_first = not has_users()

            user = create_user(
                username=request.session["reg_username"],
                password=request.session["reg_password"],
                email=request.session.get("reg_email", ""),
                is_first=is_first,
                full_name=request.session.get("reg_full_name", ""),
                company=request.session.get("reg_company", ""),
            )

            tenant = create_tenant(
                user_id=user["id"],
                printix_tenant_id=request.session["reg_tenant_id"],
                name=request.session.get("reg_tenant_name", ""),
                print_client_id=request.session.get("reg_print_client_id", ""),
                print_client_secret=request.session.get("reg_print_client_secret", ""),
                card_client_id=request.session.get("reg_card_client_id", ""),
                card_client_secret=request.session.get("reg_card_client_secret", ""),
                ws_client_id=request.session.get("reg_ws_client_id", ""),
                ws_client_secret=request.session.get("reg_ws_client_secret", ""),
                shared_client_id=request.session.get("reg_shared_client_id", ""),
                shared_client_secret=request.session.get("reg_shared_client_secret", ""),
                sql_server=request.session.get("reg_sql_server", ""),
                sql_database=request.session.get("reg_sql_database", ""),
                sql_username=request.session.get("reg_sql_username", ""),
                sql_password=request.session.get("reg_sql_password", ""),
                mail_api_key=request.session.get("reg_mail_api_key", ""),
                mail_from=request.session.get("reg_mail_from", ""),
            )

            audit(user["id"], "register", f"Tenant '{tenant['name']}' registriert")

            for key in list(request.session.keys()):
                if key.startswith("reg_"):
                    del request.session[key]

        except Exception as e:
            logger.error("Registrierung fehlgeschlagen: %s", e)
            return templates.TemplateResponse("register_step4.html", {
                "request": request, "step": 4, "error": str(e),
                "username":    request.session.get("reg_username", ""),
                "tenant_id":   request.session.get("reg_tenant_id", ""),
                "tenant_name": request.session.get("reg_tenant_name", ""),
                "base_url": base, "sql_configured": False, "mail_configured": False, **tc,
            })

        return templates.TemplateResponse("register_success.html", {
            "request": request,
            "username":           user["username"],
            "is_admin":           user.get("is_admin", False),
            "bearer_token":       tenant["bearer_token"],
            "oauth_client_id":    tenant["oauth_client_id"],
            "oauth_client_secret":tenant["oauth_client_secret"],
            "base_url":           base,
            "mcp_url":            f"{base}/mcp",
            "sse_url":            f"{base}/sse",
            "oauth_authorize_url":f"{base}/oauth/authorize",
            "oauth_token_url":    f"{base}/oauth/token",
            **tc,
        })

    # ── Login ──────────────────────────────────────────────────────────────────

    def _entra_login_enabled() -> bool:
        """Prüft ob Entra-Login für die Login-Seite angezeigt werden soll."""
        try:
            from entra import is_enabled
            return is_enabled()
        except Exception:
            return False

    @app.get("/login", response_class=HTMLResponse)
    async def login_get(request: Request):
        if get_session_user(request):
            return RedirectResponse("/", status_code=302)
        return templates.TemplateResponse("login.html", {
            "request": request, "error": None,
            "entra_enabled": _entra_login_enabled(),
            **t_ctx(request),
        })

    @app.post("/login", response_class=HTMLResponse)
    async def login_post(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
    ):
        tc = t_ctx(request)
        _  = tc["_"]
        entra_on = _entra_login_enabled()
        try:
            from db import authenticate_user, audit
            user = authenticate_user(username, password)
        except Exception as e:
            return templates.TemplateResponse("login.html", {
                "request": request, "error": f"Datenbankfehler: {e}",
                "username": username, "entra_enabled": entra_on, **tc,
            })

        if not user:
            return templates.TemplateResponse("login.html", {
                "request": request, "error": _("login_error"),
                "username": username, "entra_enabled": entra_on, **tc,
            })

        status = user.get("status", "")
        if status == "disabled" or status == "suspended":
            return templates.TemplateResponse("login.html", {
                "request": request, "error": _("login_suspended"),
                "username": username, "entra_enabled": entra_on, **tc,
            })

        request.session["user_id"] = user["id"]
        try:
            audit(user["id"], "login", "Eingeloggt")
        except Exception:
            pass

        if user.get("is_admin"):
            return RedirectResponse("/admin", status_code=302)
        if status == "pending":
            return RedirectResponse("/pending", status_code=302)
        return RedirectResponse("/dashboard", status_code=302)

    @app.get("/logout", response_class=RedirectResponse)
    async def logout(request: Request):
        lang = request.session.get("lang")
        request.session.clear()
        if lang:
            request.session["lang"] = lang
        return RedirectResponse("/login", status_code=302)

    # ── Entra ID (Azure AD) SSO ────────────────────────────────────────────────

    @app.get("/auth/entra/login")
    async def entra_login(request: Request):
        """Leitet den Benutzer zur Microsoft-Anmeldeseite weiter."""
        try:
            from entra import is_enabled, build_authorize_url, generate_state
        except ImportError:
            return RedirectResponse("/login", status_code=302)

        if not is_enabled():
            return RedirectResponse("/login", status_code=302)

        state = generate_state()
        request.session["entra_state"] = state
        # Gespeicherte Redirect URI verwenden (konsistent mit App-Registrierung)
        try:
            from db import get_setting
            saved_uri = get_setting("entra_redirect_uri", "")
        except Exception:
            saved_uri = ""
        if not saved_uri:
            base = _get_base_url(request)
            saved_uri = f"{base}/auth/entra/callback"
        redirect_uri = saved_uri
        url = build_authorize_url(redirect_uri, state)
        return RedirectResponse(url, status_code=302)

    @app.get("/auth/entra/callback")
    async def entra_callback(request: Request):
        """Callback von Microsoft nach erfolgreicher Anmeldung."""
        tc = t_ctx(request)
        _ = tc["_"]
        _e = {"entra_enabled": True}  # Entra ist aktiv (wir sind im Callback)

        code = request.query_params.get("code", "")
        state = request.query_params.get("state", "")
        error = request.query_params.get("error", "")
        error_desc = request.query_params.get("error_description", "")

        if error:
            logger.warning("Entra callback error: %s — %s", error, error_desc)
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": f"Microsoft-Anmeldung fehlgeschlagen: {error_desc or error}",
                **_e, **tc,
            })

        # CSRF-State prüfen
        expected_state = request.session.pop("entra_state", "")
        if not state or state != expected_state:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Ungültiger State-Parameter — bitte erneut versuchen.",
                **_e, **tc,
            })

        if not code:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Kein Authorization Code erhalten.",
                **_e, **tc,
            })

        # Code gegen Token tauschen
        try:
            from entra import exchange_code_for_user
        except ImportError:
            return templates.TemplateResponse("login.html", {
                "request": request, "error": "Entra-Modul nicht verfügbar.",
                **_e, **tc,
            })

        # Gespeicherte Redirect URI verwenden (muss mit Login-Request übereinstimmen)
        try:
            from db import get_setting as _gs
            saved_uri = _gs("entra_redirect_uri", "")
        except Exception:
            saved_uri = ""
        if not saved_uri:
            base = _get_base_url(request)
            saved_uri = f"{base}/auth/entra/callback"
        redirect_uri = saved_uri
        user_info = exchange_code_for_user(code, redirect_uri)

        if not user_info or not user_info.get("oid"):
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Microsoft-Anmeldung fehlgeschlagen — kein Benutzerprofil erhalten.",
                **_e, **tc,
            })

        # User finden oder erstellen
        try:
            from db import get_or_create_entra_user, audit
            user = get_or_create_entra_user(
                entra_oid=user_info["oid"],
                email=user_info.get("email", ""),
                display_name=user_info.get("name", ""),
            )
        except Exception as e:
            logger.error("Entra user lookup/create Fehler: %s", e)
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": f"Datenbankfehler: {e}",
                **_e, **tc,
            })

        if not user:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Benutzer konnte nicht angelegt werden.",
                **_e, **tc,
            })

        # Status prüfen
        status = user.get("status", "")
        if status in ("disabled", "suspended"):
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": _("login_suspended"),
                **_e, **tc,
            })

        # Session setzen
        request.session["user_id"] = user["id"]
        try:
            audit(user["id"], "login", f"Entra-Login ({user_info.get('email', '')})")
        except Exception:
            pass

        if user.get("is_admin"):
            return RedirectResponse("/admin", status_code=302)
        if status == "pending":
            return RedirectResponse("/pending", status_code=302)
        return RedirectResponse("/dashboard", status_code=302)

    # ── Entra Auto-Setup (Ein-Klick via Bootstrap-App) ─────────────────────
    #
    # ─── Device Code Flow: Admin klickt Button → Code anzeigen → automatische
    # App-Registration via Graph API. Keine Bootstrap-App nötig.

    @app.post("/admin/entra/device-code")
    async def entra_device_code_start(request: Request):
        """Startet den Device Code Flow fuer Entra Auto-Setup."""
        user = get_session_user(request)
        if not user or not user.get("is_admin"):
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        try:
            from entra import start_device_code_flow
        except ImportError:
            return JSONResponse({"error": "entra module not available"}, status_code=500)

        result = start_device_code_flow()
        if not result or not result.get("device_code"):
            return JSONResponse({"error": "device_code_failed"}, status_code=502)

        # Device code in Session speichern (fuer Polling)
        request.session["entra_device_code"] = result["device_code"]
        request.session["entra_device_interval"] = result.get("interval", 5)

        return JSONResponse({
            "user_code":        result["user_code"],
            "verification_uri": result["verification_uri"],
            "expires_in":       result["expires_in"],
            "interval":         result.get("interval", 5),
            "message":          result.get("message", ""),
        })

    @app.get("/admin/entra/device-poll")
    async def entra_device_code_poll(request: Request):
        """Pollt den Token-Status des laufenden Device Code Flows."""
        user = get_session_user(request)
        if not user or not user.get("is_admin"):
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        device_code = request.session.get("entra_device_code", "")
        if not device_code:
            return JSONResponse({"status": "error", "error": "no_device_code"})

        try:
            from entra import poll_device_code_token, auto_register_app
        except ImportError:
            return JSONResponse({"status": "error", "error": "entra module not available"})

        poll_result = poll_device_code_token(device_code)

        if poll_result["status"] == "pending":
            return JSONResponse({"status": "pending"})

        if poll_result["status"] == "expired":
            request.session.pop("entra_device_code", None)
            return JSONResponse({"status": "expired"})

        if poll_result["status"] == "error":
            request.session.pop("entra_device_code", None)
            return JSONResponse({"status": "error", "error": poll_result.get("error", "")})

        # status == "success" — Token erhalten, App erstellen
        access_token = poll_result["access_token"]
        request.session.pop("entra_device_code", None)

        base = _get_base_url(request)
        sso_redirect_uri = f"{base}/auth/entra/callback"
        result = auto_register_app(access_token, sso_redirect_uri)

        if not result or not result.get("client_id"):
            return JSONResponse({
                "status": "error",
                "error": "app_creation_failed",
            })

        # Credentials in Settings speichern
        try:
            from db import set_setting, _enc, audit
            set_setting("entra_enabled", "1")
            set_setting("entra_client_id", result["client_id"])
            if result.get("client_secret"):
                set_setting("entra_client_secret", _enc(result["client_secret"]))
            if result.get("tenant_id"):
                set_setting("entra_tenant_id", result["tenant_id"])
            set_setting("entra_auto_approve", "0")

            set_setting("entra_redirect_uri", sso_redirect_uri)

            audit(user["id"], "entra_auto_setup",
                  f"SSO-App via Device Code Flow erstellt (client_id={result['client_id']}, redirect_uri={sso_redirect_uri})")
            logger.info("Entra Auto-Setup erfolgreich: client_id=%s, redirect_uri=%s",
                        result["client_id"], sso_redirect_uri)
        except Exception as e:
            logger.error("Entra Auto-Setup DB-Fehler: %s", e)
            return JSONResponse({
                "status": "error",
                "error": f"App erstellt, aber Speichern fehlgeschlagen: {e}",
            })

        return JSONResponse({
            "status": "success",
            "client_id": result["client_id"],
            "tenant_id": result.get("tenant_id", ""),
        })

    def _get_base_url(request: Request) -> str:
        """Ermittelt die Base-URL der Web-UI aus dem eingehenden Request.

        Wichtig: Verwendet NICHT public_url (das ist fuer den MCP-Server).
        Stattdessen wird die URL aus dem Request abgeleitet (Host-Header,
        x-forwarded-* bei Reverse-Proxy).
        """
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = (
            request.headers.get("x-forwarded-host")
            or request.headers.get("host", "")
        )
        if host:
            # Host-Header enthaelt bereits den externen Port (z.B. "192.168.1.100:8010")
            return f"{scheme}://{host}".rstrip("/")
        # Fallback: aus request.url
        hostname = request.url.hostname
        port = request.url.port
        if port and port not in (80, 443):
            return f"{scheme}://{hostname}:{port}"
        return f"{scheme}://{hostname}"

    # ── Warteseite ────────────────────────────────────────────────────────────

    @app.get("/pending", response_class=HTMLResponse)
    async def pending(request: Request):
        user = get_session_user(request)
        return templates.TemplateResponse("pending.html", {
            "request": request, "user": user, **t_ctx(request)
        })

    # ── Dashboard ─────────────────────────────────────────────────────────────

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request):
        user = get_session_user(request)
        if not user:
            return RedirectResponse("/login", status_code=302)
        if user.get("status") == "pending":
            return RedirectResponse("/pending", status_code=302)

        base   = mcp_base_url()
        tenant = None
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
        except Exception:
            pass

        # KPIs aus SQL laden (falls verfügbar)
        has_sql = bool(tenant and tenant.get("sql_server"))
        kpis = {}
        env_summary = {}
        sparkline_data = []
        forecast = {}

        if has_sql:
            try:
                import asyncio as _aio
                from reporting.sql_client import set_config_from_tenant
                set_config_from_tenant(tenant)

                from datetime import date as _date, timedelta as _td
                today = _date.today()
                week_start = today - _td(days=today.weekday())
                month_start = today.replace(day=1)

                def _load_dashboard_data():
                    from reporting.query_tools import query_print_stats, query_tree_meter, query_forecast
                    # Tages/Wochen/Monats-Statistiken
                    day_data = query_print_stats(str(today), str(today), group_by="day")
                    week_data = query_print_stats(str(week_start), str(today), group_by="day")
                    month_data = query_print_stats(str(month_start), str(today), group_by="day")

                    def _sum_field(rows, field):
                        return sum(int(r.get(field) or 0) for r in rows)

                    today_pages = _sum_field(day_data, "total_pages")
                    today_jobs  = _sum_field(day_data, "total_jobs")
                    week_pages  = _sum_field(week_data, "total_pages")
                    week_jobs   = _sum_field(week_data, "total_jobs")
                    month_pages = _sum_field(month_data, "total_pages")
                    month_jobs  = _sum_field(month_data, "total_jobs")

                    # Farb/Duplex-Raten aus Monatsdaten
                    month_color  = _sum_field(month_data, "color_pages")
                    month_duplex = _sum_field(month_data, "duplex_pages")
                    color_ratio  = round(month_color / month_pages * 100, 1) if month_pages else 0
                    duplex_rate  = round(month_duplex / month_pages * 100, 1) if month_pages else 0

                    # Aktive Drucker
                    active_printers = 0
                    for r in month_data:
                        active_printers = max(active_printers, int(r.get("active_printers") or 0))

                    _kpis = {
                        "today_pages": today_pages, "today_jobs": today_jobs,
                        "week_pages": week_pages, "week_jobs": week_jobs,
                        "month_pages": month_pages, "month_jobs": month_jobs,
                        "color_ratio": color_ratio, "duplex_rate": duplex_rate,
                        "active_printers": active_printers,
                    }

                    # Sparkline: letzte 7 Tage
                    spark_start = today - _td(days=6)
                    spark_data = query_print_stats(str(spark_start), str(today), group_by="day")
                    _sparkline = [0] * 7
                    for r in spark_data:
                        try:
                            from reporting.query_tools import _fmt_date
                            d = _fmt_date(r["period"])
                            idx = (d - spark_start).days
                            if 0 <= idx < 7:
                                _sparkline[idx] = int(r.get("total_pages") or 0)
                        except Exception:
                            pass

                    # Umwelt-Summary (ganzer Monat)
                    tree = query_tree_meter(str(month_start), str(today))
                    from reporting.report_engine import compute_env_impact
                    _env = compute_env_impact(
                        tree.get("total_pages", 0),
                        tree.get("duplex_pages", 0),
                        tree.get("saved_sheets_duplex", 0),
                    )

                    # Forecast (letzte 6 Monate → nächster Monat)
                    from dateutil.relativedelta import relativedelta
                    fc_start = (today - relativedelta(months=6)).replace(day=1)
                    try:
                        _fc = query_forecast(str(fc_start), str(today), group_by="month")
                    except Exception:
                        _fc = {}

                    return _kpis, _sparkline, _env, _fc

                kpis, sparkline_data, env_summary, forecast = await _aio.to_thread(
                    _load_dashboard_data
                )
            except Exception as e:
                logger.warning("Dashboard-KPI-Laden fehlgeschlagen: %s", e)

        return templates.TemplateResponse("dashboard.html", {
            "request": request, "user": user, "tenant": tenant,
            "base_url": base,
            "mcp_url":  f"{base}/mcp",
            "sse_url":  f"{base}/sse",
            "has_sql": has_sql,
            "kpis": kpis,
            "env_summary": env_summary,
            "sparkline_data": sparkline_data,
            "forecast": forecast,
            **t_ctx(request),
        })

    @app.get("/dashboard/data")
    async def dashboard_data(request: Request):
        """JSON-Endpunkt für Auto-Refresh des Dashboards."""
        user = get_session_user(request)
        if not user:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
        except Exception:
            return JSONResponse({"has_sql": False})

        if not tenant or not tenant.get("sql_server"):
            return JSONResponse({"has_sql": False})

        try:
            import asyncio as _aio
            from reporting.sql_client import set_config_from_tenant
            set_config_from_tenant(tenant)

            from datetime import date as _date, timedelta as _td
            today = _date.today()
            week_start = today - _td(days=today.weekday())
            month_start = today.replace(day=1)

            def _load():
                from reporting.query_tools import query_print_stats
                day_data = query_print_stats(str(today), str(today), group_by="day")
                week_data = query_print_stats(str(week_start), str(today), group_by="day")
                month_data = query_print_stats(str(month_start), str(today), group_by="day")

                def _s(rows, f):
                    return sum(int(r.get(f) or 0) for r in rows)

                mp = _s(month_data, "total_pages")
                return {
                    "has_sql": True,
                    "today_pages": _s(day_data, "total_pages"),
                    "today_jobs": _s(day_data, "total_jobs"),
                    "week_pages": _s(week_data, "total_pages"),
                    "week_jobs": _s(week_data, "total_jobs"),
                    "month_pages": mp,
                    "month_jobs": _s(month_data, "total_jobs"),
                    "color_ratio": round(_s(month_data, "color_pages") / mp * 100, 1) if mp else 0,
                    "duplex_rate": round(_s(month_data, "duplex_pages") / mp * 100, 1) if mp else 0,
                }

            return JSONResponse(await _aio.to_thread(_load))
        except Exception as e:
            logger.warning("Dashboard-Data-Fehler: %s", e)
            return JSONResponse({"has_sql": True, "error": str(e)})

    # ── Fleet Health Monitor (v4.3.3) ─────────────────────────────────────────

    @app.get("/fleet", response_class=HTMLResponse)
    async def fleet_health(request: Request):
        user = get_session_user(request)
        if not user:
            return RedirectResponse("/login", status_code=302)
        if user.get("status") == "pending":
            return RedirectResponse("/pending", status_code=302)

        tc = t_ctx(request)
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
        except Exception:
            tenant = None

        has_printers = bool(tenant and tenant.get("printix_tenant_id"))
        has_sql = bool(tenant and tenant.get("sql_server"))
        printers_list = []
        fleet_kpis = {"total": 0, "active_today": 0, "inactive_7d": 0, "avg_utilization": 0}
        alerts = []

        if has_printers and tenant:
            # Drucker von Printix API laden
            try:
                import asyncio as _aio
                client = _make_printix_client(tenant)
                api_printers = await _aio.to_thread(client.list_printers)
                if isinstance(api_printers, dict):
                    api_printers = api_printers.get("value", [])
            except Exception as e:
                logger.warning("Fleet: Printix API Fehler: %s", e)
                api_printers = []

            # SQL-Daten laden (falls verfügbar)
            sql_readings = {}
            if has_sql:
                try:
                    import asyncio as _aio
                    from reporting.sql_client import set_config_from_tenant
                    set_config_from_tenant(tenant)

                    from datetime import date as _date, timedelta as _td
                    today = _date.today()
                    start_90d = today - _td(days=90)

                    def _load_fleet_sql():
                        from reporting.query_tools import query_device_readings
                        readings = query_device_readings(str(start_90d), str(today))
                        return {r.get("printer_name", ""): r for r in readings}

                    sql_readings = await _aio.to_thread(_load_fleet_sql)
                except Exception as e:
                    logger.warning("Fleet: SQL-Daten Fehler: %s", e)

            # API + SQL mergen
            from datetime import date as _date, timedelta as _td, datetime as _dt
            today = _date.today()
            total_util = 0
            util_count = 0

            for p in api_printers:
                name = p.get("name", "Unknown")
                sql_data = sql_readings.get(name, {})

                last_act = sql_data.get("last_activity")
                total_jobs = int(sql_data.get("total_jobs") or 0)
                total_pages = int(sql_data.get("total_pages") or 0)
                active_days = int(sql_data.get("active_days") or 0)
                error_rate = 0  # Wird ggf. aus service_desk erweitert

                # Status bestimmen
                if last_act:
                    try:
                        last_date = _dt.fromisoformat(str(last_act)).date() if not isinstance(last_act, _date) else last_act
                        days_ago = (today - last_date).days
                    except Exception:
                        days_ago = 999
                else:
                    days_ago = 999

                if days_ago == 0:
                    status = "active"
                elif days_ago <= 7:
                    status = "warning"
                elif days_ago > 7 and last_act:
                    status = "critical"
                else:
                    status = "unknown"

                # Utilization (active_days / 90 Tage)
                utilization = round(active_days / 90 * 100, 1) if active_days else 0
                total_util += utilization
                util_count += 1

                printers_list.append({
                    "name": name,
                    "model": sql_data.get("model_name") or p.get("model", ""),
                    "location": sql_data.get("location") or p.get("location", ""),
                    "site": sql_data.get("site_name", ""),
                    "status": status,
                    "last_activity": str(last_act) if last_act else None,
                    "days_ago": days_ago if days_ago < 999 else None,
                    "total_jobs": total_jobs,
                    "total_pages": total_pages,
                    "utilization": utilization,
                    "error_rate": error_rate,
                })

            # Sortieren: Critical zuerst, dann Warning, dann Active
            status_order = {"critical": 0, "warning": 1, "unknown": 2, "active": 3}
            printers_list.sort(key=lambda p: status_order.get(p["status"], 9))

            # KPIs
            fleet_kpis = {
                "total": len(printers_list),
                "active_today": sum(1 for p in printers_list if p["status"] == "active"),
                "inactive_7d": sum(1 for p in printers_list if p["status"] == "critical"),
                "avg_utilization": round(total_util / util_count, 1) if util_count else 0,
            }

            # Alerts
            for p in printers_list:
                if p["status"] == "critical":
                    alerts.append({
                        "type": "inactive",
                        "printer_name": p["name"],
                        "detail": f"{p.get('days_ago', '?')} days",
                    })
                if p["error_rate"] > 10:
                    alerts.append({
                        "type": "high_errors",
                        "printer_name": p["name"],
                        "detail": f"{p['error_rate']:.1f}%",
                    })

        return templates.TemplateResponse("fleet.html", {
            "request": request, "user": user,
            "has_printers": has_printers, "has_sql": has_sql,
            "fleet_kpis": fleet_kpis,
            "printers": printers_list,
            "alerts": alerts,
            **tc,
        })

    @app.get("/fleet/data")
    async def fleet_data(request: Request):
        """JSON-Endpunkt für Fleet Auto-Refresh."""
        user = get_session_user(request)
        if not user:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        # Für Auto-Refresh: Fleet-Daten als JSON
        # (vereinfachte Version — vollständiger Reload)
        return JSONResponse({"reload": True})

    # ── Sustainability Report (v4.3.3) ────────────────────────────────────────

    @app.get("/reports/sustainability", response_class=HTMLResponse)
    async def sustainability_report(request: Request):
        user = get_session_user(request)
        if not user:
            return RedirectResponse("/login", status_code=302)
        if user.get("status") == "pending":
            return RedirectResponse("/pending", status_code=302)

        tc = t_ctx(request)
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
        except Exception:
            tenant = None

        has_sql = bool(tenant and tenant.get("sql_server"))

        # Default-Zeitraum: aktuelles Jahr
        from datetime import date as _date
        today = _date.today()
        start_date = request.query_params.get("start_date", str(today.replace(month=1, day=1)))
        end_date = request.query_params.get("end_date", str(today))

        env = {}
        tree_data = {}
        equivalents = {}
        monthly_trend = []

        if has_sql:
            try:
                import asyncio as _aio
                from reporting.sql_client import set_config_from_tenant
                set_config_from_tenant(tenant)

                def _load_sustainability():
                    from reporting.query_tools import query_tree_meter, query_print_stats
                    from reporting.report_engine import compute_env_impact

                    tree = query_tree_meter(start_date, end_date)
                    _env = compute_env_impact(
                        tree.get("total_pages", 0),
                        tree.get("duplex_pages", 0),
                        tree.get("saved_sheets_duplex", 0),
                    )

                    # Äquivalenzen berechnen
                    _eq = {
                        "car_km": round(_env.get("co2_kg", 0) / 0.21, 1),     # 210g CO2/km
                        "bathtubs": round(_env.get("water_l", 0) / 150, 1),    # 150L/Wanne
                        "phone_charges": round(_env.get("energy_kwh", 0) * 1000 / 12, 0),  # 12Wh/Ladung
                    }

                    # Monatlicher Trend
                    monthly = query_print_stats(start_date, end_date, group_by="month")
                    _trend = []
                    for m in monthly:
                        m_tree = query_tree_meter(str(m["period"]), str(m["period"]))
                        m_env = compute_env_impact(
                            m_tree.get("total_pages", 0),
                            m_tree.get("duplex_pages", 0),
                            m_tree.get("saved_sheets_duplex", 0),
                        )
                        _trend.append({
                            "period": str(m["period"]),
                            "co2_kg": m_env.get("co2_kg", 0),
                            "trees": m_env.get("trees", 0),
                            "water_l": m_env.get("water_l", 0),
                            "saved_sheets": m_tree.get("saved_sheets_duplex", 0),
                        })

                    return tree, _env, _eq, _trend

                tree_data, env, equivalents, monthly_trend = await _aio.to_thread(
                    _load_sustainability
                )
            except Exception as e:
                logger.warning("Sustainability-Laden fehlgeschlagen: %s", e)

        return templates.TemplateResponse("sustainability.html", {
            "request": request, "user": user,
            "has_sql": has_sql,
            "env": env,
            "tree_data": tree_data,
            "equivalents": equivalents,
            "monthly_trend": monthly_trend,
            "start_date": start_date,
            "end_date": end_date,
            **tc,
        })

    # ── Settings (Selbstverwaltung) ────────────────────────────────────────────

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_get(request: Request):
        user = require_login(request)
        if not user:
            return RedirectResponse("/login", status_code=302)
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
        except Exception:
            tenant = {}
        return templates.TemplateResponse("settings.html", {
            "request": request, "user": user, "tenant": tenant,
            "saved": False, "error": None, **t_ctx(request),
        })

    @app.post("/settings", response_class=HTMLResponse)
    async def settings_post(
        request: Request,
        printix_tenant_id:    str = Form(default=""),
        tenant_name:          str = Form(default=""),
        print_client_id:      str = Form(default=""),
        print_client_secret:  str = Form(default=""),
        card_client_id:       str = Form(default=""),
        card_client_secret:   str = Form(default=""),
        ws_client_id:         str = Form(default=""),
        ws_client_secret:     str = Form(default=""),
        shared_client_id:     str = Form(default=""),
        shared_client_secret: str = Form(default=""),
        sql_server:           str = Form(default=""),
        sql_database:         str = Form(default=""),
        sql_username:         str = Form(default=""),
        sql_password:         str = Form(default=""),
        mail_api_key:         str = Form(default=""),
        mail_from:            str = Form(default=""),
    ):
        user = require_login(request)
        if not user:
            return RedirectResponse("/login", status_code=302)
        tc = t_ctx(request)

        try:
            from db import update_tenant_credentials, get_tenant_full_by_user_id, audit
            update_tenant_credentials(
                user_id=user["id"],
                printix_tenant_id=printix_tenant_id.strip() or None,
                name=tenant_name.strip() or None,
                print_client_id=print_client_id.strip() or None,
                print_client_secret=print_client_secret.strip() or None,
                card_client_id=card_client_id.strip() or None,
                card_client_secret=card_client_secret.strip() or None,
                ws_client_id=ws_client_id.strip() or None,
                ws_client_secret=ws_client_secret.strip() or None,
                shared_client_id=shared_client_id.strip() or None,
                shared_client_secret=shared_client_secret.strip() or None,
                sql_server=sql_server.strip() or None,
                sql_database=sql_database.strip() or None,
                sql_username=sql_username.strip() or None,
                sql_password=sql_password.strip() or None,
                mail_api_key=mail_api_key.strip() or None,
                mail_from=mail_from.strip() or None,
            )
            audit(user["id"], "update_settings", "Credentials aktualisiert")
            tenant = get_tenant_full_by_user_id(user["id"])
        except Exception as e:
            logger.error("Settings-Fehler: %s", e)
            return templates.TemplateResponse("settings.html", {
                "request": request, "user": user, "tenant": {},
                "saved": False, "error": str(e), **tc,
            })

        return templates.TemplateResponse("settings.html", {
            "request": request, "user": user, "tenant": tenant,
            "saved": True, "error": None, **tc,
        })

    @app.post("/settings/regenerate-oauth", response_class=JSONResponse)
    async def settings_regenerate_oauth(request: Request):
        user = require_login(request)
        if not user:
            return JSONResponse({"error": "Nicht authentifiziert"}, status_code=401)
        try:
            from db import regenerate_oauth_secret, audit
            new_secret = regenerate_oauth_secret(user["id"])
            audit(user["id"], "regen_oauth_secret", "OAuth-Secret neu generiert")
            return JSONResponse({"oauth_client_secret": new_secret})
        except Exception as e:
            logger.error("Regen-OAuth-Fehler: %s", e)
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.get("/settings/password", response_class=HTMLResponse)
    async def settings_password_get(request: Request):
        user = require_login(request)
        if not user:
            return RedirectResponse("/login", status_code=302)
        return templates.TemplateResponse("settings_password.html", {
            "request": request, "user": user,
            "saved": False, "error": None, **t_ctx(request),
        })

    @app.post("/settings/password", response_class=HTMLResponse)
    async def settings_password_post(
        request: Request,
        old_password:  str = Form(...),
        new_password:  str = Form(...),
        new_password2: str = Form(...),
    ):
        user = require_login(request)
        if not user:
            return RedirectResponse("/login", status_code=302)
        tc = t_ctx(request)
        _ = tc["_"]
        error = None

        if new_password != new_password2:
            error = _("reg_pw_mismatch")
        elif len(new_password) < 8:
            error = "Passwort muss mindestens 8 Zeichen lang sein."
        else:
            try:
                from db import authenticate_user, reset_user_password, audit
                if not authenticate_user(user["username"], old_password):
                    error = _("settings_pw_wrong")
                else:
                    reset_user_password(user["id"], new_password)
                    audit(user["id"], "change_password", "Passwort geändert")
            except Exception as e:
                error = str(e)

        if error:
            return templates.TemplateResponse("settings_password.html", {
                "request": request, "user": user,
                "saved": False, "error": error, **tc,
            })
        return templates.TemplateResponse("settings_password.html", {
            "request": request, "user": user,
            "saved": True, "error": None, **tc,
        })

    # ── Hilfe / Verbindungsanleitung ──────────────────────────────────────────

    @app.get("/help", response_class=HTMLResponse)
    async def help_page(request: Request):
        user = require_login(request)
        if not user:
            return RedirectResponse("/login", status_code=302)

        base   = mcp_base_url()
        tenant = None
        try:
            from db import get_tenant_by_user_id
            tenant = get_tenant_by_user_id(user["id"])
        except Exception:
            pass

        return templates.TemplateResponse("help.html", {
            "request": request, "user": user, "tenant": tenant,
            "base_url":           base,
            "mcp_url":            f"{base}/mcp",
            "sse_url":            f"{base}/sse",
            "oauth_authorize_url":f"{base}/oauth/authorize",
            "oauth_token_url":    f"{base}/oauth/token",
            **t_ctx(request),
        })

    # ── Admin ──────────────────────────────────────────────────────────────────

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_dashboard(request: Request):
        user = get_session_user(request)
        if not user or not user.get("is_admin"):
            return RedirectResponse("/login", status_code=302)
        try:
            from db import get_all_users, count_tenants
            users        = get_all_users()
            tenant_count = count_tenants()
        except Exception:
            users = []; tenant_count = 0
        return templates.TemplateResponse("admin_dashboard.html", {
            "request": request, "user": user,
            "users": users, "tenant_count": tenant_count,
            "base_url": mcp_base_url(), **t_ctx(request),
        })

    @app.get("/admin/users", response_class=HTMLResponse)
    async def admin_users(request: Request):
        user = get_session_user(request)
        if not user or not user.get("is_admin"):
            return RedirectResponse("/login", status_code=302)
        try:
            from db import get_all_users
            users = get_all_users()
        except Exception:
            users = []
        return templates.TemplateResponse("admin_users.html", {
            "request": request, "user": user, "users": users, **t_ctx(request)
        })

    @app.post("/admin/users/{user_id}/approve")
    async def admin_approve(user_id: str, request: Request):
        admin = get_session_user(request)
        if not admin or not admin.get("is_admin"):
            return RedirectResponse("/login", status_code=302)
        try:
            from db import set_user_status, audit
            set_user_status(user_id, "approved")
            audit(admin["id"], "approve_user", f"User {user_id} genehmigt", object_type="user", object_id=user_id)
        except Exception as e:
            logger.error("Approve-Fehler: %s", e)
        return RedirectResponse("/admin/users", status_code=302)

    @app.post("/admin/users/{user_id}/disable")
    async def admin_disable(user_id: str, request: Request):
        admin = get_session_user(request)
        if not admin or not admin.get("is_admin"):
            return RedirectResponse("/login", status_code=302)
        if user_id == admin["id"]:
            return RedirectResponse("/admin/users", status_code=302)
        try:
            from db import set_user_status, audit
            set_user_status(user_id, "disabled")
            audit(admin["id"], "disable_user", f"User {user_id} deaktiviert", object_type="user", object_id=user_id)
        except Exception as e:
            logger.error("Disable-Fehler: %s", e)
        return RedirectResponse("/admin/users", status_code=302)

    @app.post("/admin/users/{user_id}/delete")
    async def admin_delete_user(user_id: str, request: Request):
        admin = get_session_user(request)
        if not admin or not admin.get("is_admin"):
            return RedirectResponse("/login", status_code=302)
        if user_id == admin["id"]:
            return RedirectResponse("/admin/users", status_code=302)
        try:
            from db import delete_user, audit
            delete_user(user_id)
            audit(admin["id"], "delete_user", f"User {user_id} gelöscht", object_type="user", object_id=user_id)
        except Exception as e:
            logger.error("Delete-Fehler: %s", e)
        return RedirectResponse("/admin/users", status_code=302)

    @app.get("/admin/users/create", response_class=HTMLResponse)
    async def admin_create_user_get(request: Request):
        admin = get_session_user(request)
        if not admin or not admin.get("is_admin"):
            return RedirectResponse("/login", status_code=302)
        return templates.TemplateResponse("admin_user_create.html", {
            "request": request, "user": admin,
            "saved": False, "error": None, **t_ctx(request),
        })

    @app.post("/admin/users/create", response_class=HTMLResponse)
    async def admin_create_user_post(
        request:   Request,
        username:  str = Form(...),
        password:  str = Form(...),
        password2: str = Form(...),
        email:     str = Form(default=""),
        full_name: str = Form(default=""),
        company:   str = Form(default=""),
        is_admin:  str = Form(default=""),
        status:    str = Form(default="approved"),
    ):
        admin = get_session_user(request)
        if not admin or not admin.get("is_admin"):
            return RedirectResponse("/login", status_code=302)
        tc = t_ctx(request)
        _  = tc["_"]
        error = None

        if len(username) < 3:
            error = "Benutzername muss mindestens 3 Zeichen lang sein."
        elif len(password) < 8:
            error = "Passwort muss mindestens 8 Zeichen lang sein."
        elif password != password2:
            error = _("reg_pw_mismatch")
        else:
            try:
                from db import username_exists
                if username_exists(username):
                    error = _("reg_user_exists")
            except Exception as e:
                error = str(e)

        if error:
            return templates.TemplateResponse("admin_user_create.html", {
                "request": request, "user": admin,
                "saved": False, "error": error,
                "f_username": username, "f_email": email,
                "f_is_admin": is_admin, "f_status": status, **tc,
            })

        try:
            from db import create_user_admin, audit
            new_user = create_user_admin(
                username=username.strip(),
                password=password,
                email=email.strip(),
                is_admin=(is_admin == "1"),
                status=status,
                full_name=full_name.strip(),
                company=company.strip(),
            )
            audit(admin["id"], "create_user", f"User '{username}' direkt angelegt (Status: {status})")
        except Exception as e:
            logger.error("Create-User-Fehler: %s", e)
            return templates.TemplateResponse("admin_user_create.html", {
                "request": request, "user": admin,
                "saved": False, "error": str(e), **tc,
            })

        return templates.TemplateResponse("admin_user_create.html", {
            "request": request, "user": admin,
            "saved": True, "error": None,
            "created_username": new_user["username"], **tc,
        })

    @app.get("/admin/users/{user_id}/edit", response_class=HTMLResponse)
    async def admin_edit_user_get(user_id: str, request: Request):
        admin = get_session_user(request)
        if not admin or not admin.get("is_admin"):
            return RedirectResponse("/login", status_code=302)
        try:
            from db import get_user_by_id
            target = get_user_by_id(user_id)
        except Exception:
            target = None
        if not target:
            return RedirectResponse("/admin/users", status_code=302)
        return templates.TemplateResponse("admin_user_edit.html", {
            "request": request, "user": admin, "target": target,
            "saved": False, "error": None, **t_ctx(request),
        })

    @app.post("/admin/users/{user_id}/edit", response_class=HTMLResponse)
    async def admin_edit_user_post(
        user_id:   str,
        request:   Request,
        username:  str = Form(...),
        email:     str = Form(default=""),
        full_name: str = Form(default=""),
        company:   str = Form(default=""),
        is_admin:  str = Form(default=""),
        status:    str = Form(default="approved"),
    ):
        admin = get_session_user(request)
        if not admin or not admin.get("is_admin"):
            return RedirectResponse("/login", status_code=302)
        tc = t_ctx(request)

        try:
            from db import update_user, username_exists, get_user_by_id, audit
            if username_exists(username, exclude_id=user_id):
                target = get_user_by_id(user_id)
                return templates.TemplateResponse("admin_user_edit.html", {
                    "request": request, "user": admin, "target": target,
                    "saved": False, "error": tc["_"]("reg_user_exists"), **tc,
                })
            update_user(
                user_id=user_id,
                username=username.strip(),
                email=email.strip(),
                full_name=full_name.strip(),
                company=company.strip(),
                is_admin=(is_admin == "1"),
                status=status,
            )
            audit(admin["id"], "edit_user", f"User {user_id} bearbeitet", object_type="user", object_id=user_id)
            target = get_user_by_id(user_id)
        except Exception as e:
            logger.error("Edit-Fehler: %s", e)
            return templates.TemplateResponse("admin_user_edit.html", {
                "request": request, "user": admin,
                "target": {"id": user_id, "username": username, "email": email},
                "saved": False, "error": str(e), **tc,
            })

        return templates.TemplateResponse("admin_user_edit.html", {
            "request": request, "user": admin, "target": target,
            "saved": True, "error": None, **tc,
        })

    @app.post("/admin/users/{user_id}/reset-password")
    async def admin_reset_password(
        user_id:      str,
        request:      Request,
        new_password: str = Form(...),
    ):
        admin = get_session_user(request)
        if not admin or not admin.get("is_admin"):
            return RedirectResponse("/login", status_code=302)
        try:
            from db import reset_user_password, audit
            reset_user_password(user_id, new_password)
            audit(admin["id"], "reset_password", f"Passwort für User {user_id} zurückgesetzt", object_type="user", object_id=user_id)
        except Exception as e:
            logger.error("Reset-PW-Fehler: %s", e)
        return RedirectResponse(f"/admin/users/{user_id}/edit?pw_saved=1", status_code=302)

    @app.get("/admin/audit", response_class=HTMLResponse)
    async def admin_audit(request: Request):
        user = get_session_user(request)
        if not user or not user.get("is_admin"):
            return RedirectResponse("/login", status_code=302)
        try:
            from db import get_audit_log
            entries = get_audit_log(limit=200)
        except Exception:
            entries = []
        return templates.TemplateResponse("admin_audit.html", {
            "request": request, "user": user, "entries": entries, **t_ctx(request)
        })

    # ─── Feedback / Feature-Request-Ticketsystem (v3.9.0) ─────────────────────
    @app.get("/feedback", response_class=HTMLResponse)
    async def feedback_list(request: Request):
        user = get_session_user(request)
        if not user:
            return RedirectResponse("/login", status_code=302)
        try:
            from db import list_feature_requests
            if user.get("is_admin"):
                tickets = list_feature_requests(limit=500)
            else:
                tickets = list_feature_requests(user_id=user["id"], limit=500)
        except Exception as e:
            logger.error("feedback_list-Fehler: %s", e)
            tickets = []
        flash = request.query_params.get("flash", "")
        return templates.TemplateResponse("feedback.html", {
            "request": request, "user": user,
            "tickets": tickets, "flash": flash,
            **t_ctx(request),
        })

    @app.post("/feedback/new", response_class=HTMLResponse)
    async def feedback_new(
        request: Request,
        title: str = Form(...),
        description: str = Form(default=""),
        category: str = Form(default="feature"),
    ):
        user = get_session_user(request)
        if not user:
            return RedirectResponse("/login", status_code=302)
        if not title.strip():
            return RedirectResponse("/feedback", status_code=302)
        try:
            from db import create_feature_request, audit, get_tenant_by_user_id
            t = get_tenant_by_user_id(user["id"]) or {}
            ticket = create_feature_request(
                user_id=user["id"],
                user_email=user.get("email") or user.get("username", ""),
                title=title.strip()[:200],
                description=(description or "").strip()[:4000],
                category=(category or "feature").strip(),
                tenant_id=t.get("id", ""),
            )
            audit(user["id"], "feedback_create",
                  f"Ticket {ticket.get('ticket_no', '?')}: {title[:80]}",
                  object_type="feature_request", object_id=str(ticket.get("id", "")))
        except Exception as e:
            logger.error("feedback_new-Fehler: %s", e)
            return RedirectResponse("/feedback?flash=Fehler", status_code=302)
        tc = t_ctx(request)
        flash = tc["_"]("feedback_flash_created") + f" {ticket.get('ticket_no','')}"
        from urllib.parse import quote
        return RedirectResponse(f"/feedback?flash={quote(flash)}", status_code=302)

    @app.get("/feedback/{ticket_id}", response_class=HTMLResponse)
    async def feedback_detail(ticket_id: int, request: Request):
        user = get_session_user(request)
        if not user:
            return RedirectResponse("/login", status_code=302)
        try:
            from db import get_feature_request
            ticket = get_feature_request(ticket_id)
        except Exception:
            ticket = None
        if not ticket:
            return RedirectResponse("/feedback", status_code=302)
        # Nicht-Admins dürfen nur ihre eigenen Tickets sehen
        if not user.get("is_admin") and ticket.get("user_id") != user["id"]:
            return RedirectResponse("/feedback", status_code=302)
        return templates.TemplateResponse("feedback_detail.html", {
            "request": request, "user": user, "ticket": ticket,
            **t_ctx(request),
        })

    @app.post("/feedback/{ticket_id}/update", response_class=HTMLResponse)
    async def feedback_update(
        ticket_id: int,
        request: Request,
        status: str = Form(...),
        priority: str = Form(default="normal"),
        admin_note: str = Form(default=""),
    ):
        admin = get_session_user(request)
        if not admin or not admin.get("is_admin"):
            return RedirectResponse("/login", status_code=302)
        try:
            from db import update_feature_request_status, audit, get_feature_request
            ok = update_feature_request_status(
                ticket_id, status=status, admin_note=admin_note, priority=priority,
            )
            if ok:
                t = get_feature_request(ticket_id) or {}
                audit(admin["id"], "feedback_update",
                      f"Ticket {t.get('ticket_no','?')} → {status}",
                      object_type="feature_request", object_id=str(ticket_id))
        except Exception as e:
            logger.error("feedback_update-Fehler: %s", e)
        return RedirectResponse(f"/feedback/{ticket_id}", status_code=302)

    def _admin_settings_ctx(request, user, saved=False, error=None,
                            auto_setup_success=False):
        """Baut den Template-Kontext für admin_settings.html."""
        try:
            from db import get_setting
            public_url = get_setting("public_url", "")
        except Exception:
            public_url = os.environ.get("MCP_PUBLIC_URL", "")
        # Entra-Konfiguration
        try:
            from db import get_setting as gs
            entra_cfg = {
                "enabled":      gs("entra_enabled", "0") == "1",
                "tenant_id":    gs("entra_tenant_id", ""),
                "client_id":    gs("entra_client_id", ""),
                "has_secret":   bool(gs("entra_client_secret", "")),
                "auto_approve": gs("entra_auto_approve", "0") == "1",
            }
        except Exception:
            entra_cfg = {"enabled": False, "tenant_id": "", "client_id": "",
                         "has_secret": False, "auto_approve": False}
        # Gespeicherte Redirect URI (aus Auto-Setup oder manuell gesetzt)
        try:
            saved_redirect = gs("entra_redirect_uri", "")
        except Exception:
            saved_redirect = ""
        if not saved_redirect:
            base = _get_base_url(request)
            saved_redirect = f"{base}/auth/entra/callback"
        return {
            "request": request, "user": user,
            "public_url": public_url,
            "entra": entra_cfg,
            "entra_redirect_uri": saved_redirect,
            "auto_setup_success": auto_setup_success,
            "saved": saved, "error": error,
            **t_ctx(request),
        }

    @app.get("/admin/settings", response_class=HTMLResponse)
    async def admin_settings_get(request: Request):
        user = get_session_user(request)
        if not user or not user.get("is_admin"):
            return RedirectResponse("/login", status_code=302)
        return templates.TemplateResponse("admin_settings.html",
            _admin_settings_ctx(request, user))

    @app.post("/admin/settings", response_class=HTMLResponse)
    async def admin_settings_post(
        request:              Request,
        public_url:           str = Form(default=""),
        entra_enabled:        str = Form(default=""),
        entra_tenant_id:      str = Form(default=""),
        entra_client_id:      str = Form(default=""),
        entra_client_secret:  str = Form(default=""),
        entra_auto_approve:   str = Form(default=""),
        entra_redirect_uri:   str = Form(default=""),
    ):
        user = get_session_user(request)
        if not user or not user.get("is_admin"):
            return RedirectResponse("/login", status_code=302)

        url = public_url.strip().rstrip("/")
        try:
            from db import set_setting, _enc, audit
            set_setting("public_url", url)

            # Entra-Settings speichern
            set_setting("entra_enabled", "1" if entra_enabled else "0")
            set_setting("entra_tenant_id", entra_tenant_id.strip())
            set_setting("entra_client_id", entra_client_id.strip())
            set_setting("entra_auto_approve", "1" if entra_auto_approve else "0")
            # Secret nur überschreiben wenn neuer Wert eingegeben wurde
            if entra_client_secret.strip():
                set_setting("entra_client_secret", _enc(entra_client_secret.strip()))
            # Redirect URI speichern (muss mit Azure App Registration übereinstimmen)
            if entra_redirect_uri.strip():
                set_setting("entra_redirect_uri", entra_redirect_uri.strip().rstrip("/"))

            changes = [f"public_url={url}"]
            if entra_enabled:
                changes.append("entra=aktiviert")
            audit(user["id"], "admin_settings", ", ".join(changes))
        except Exception as e:
            logger.error("Admin-Settings-Fehler: %s", e)
            return templates.TemplateResponse("admin_settings.html",
                _admin_settings_ctx(request, user, error=str(e)))

        return templates.TemplateResponse("admin_settings.html",
            _admin_settings_ctx(request, user, saved=True))


    # ─── Logs ────────────────────────────────────────────────────────────────────

    @app.get("/logs", response_class=HTMLResponse)
    async def logs_get(
        request:   Request,
        min_level: str = "DEBUG",
        category:  str = "",
    ):
        user = require_login(request)
        if user is None:
            return RedirectResponse("/login", status_code=302)
        tc = t_ctx(request)
        try:
            from db import get_tenant_by_user_id, get_tenant_logs
            tenant = get_tenant_by_user_id(user["id"])
            tid    = tenant["id"] if tenant else None
            entries = get_tenant_logs(tid, min_level=min_level, category=category) if tid else []
        except Exception as e:
            logger.error("Logs-Fehler: %s", e)
            entries = []
            tid = None
        # UTC → Lokale Zeit konvertieren (TZ-Umgebungsvariable, Fallback Europe/Berlin)
        try:
            import datetime as _dt
            from zoneinfo import ZoneInfo as _ZI
            _tz = _ZI(os.environ.get("TZ", "Europe/Berlin"))
            for _e in entries:
                try:
                    _ts = _dt.datetime.fromisoformat(_e["timestamp"])
                    if _ts.tzinfo:
                        _e["timestamp"] = _ts.astimezone(_tz).isoformat()
                except Exception:
                    pass
        except Exception:
            pass
        return templates.TemplateResponse("logs.html", {
            "request": request, "user": user,
            "entries": entries,
            "min_level": min_level.upper(),
            "levels": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            "category": category.upper(),
            "categories": ["", "PRINTIX_API", "SQL", "AUTH", "SYSTEM"],
            **tc,
        })

    @app.post("/logs/clear", response_class=JSONResponse)
    async def logs_clear(request: Request):
        user = require_login(request)
        if user is None:
            return JSONResponse({"ok": False, "error": "not logged in"}, status_code=401)
        try:
            from db import get_tenant_by_user_id, clear_tenant_logs
            tenant = get_tenant_by_user_id(user["id"])
            if not tenant:
                return JSONResponse({"ok": False, "error": "no tenant"})
            n = clear_tenant_logs(tenant["id"])
            return JSONResponse({"ok": True, "deleted": n})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)})


    # ─── Tenant: Printers / Queues / Users+Cards ─────────────────────────────────

    def _make_printix_client(tenant: dict):
        """Erstellt einen PrintixClient aus Tenant-Credentials (Full-Record mit Secrets)."""
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from printix_client import PrintixClient
        return PrintixClient(
            tenant_id=tenant.get("printix_tenant_id", ""),
            print_client_id=tenant.get("print_client_id") or None,
            print_client_secret=tenant.get("print_client_secret") or None,
            card_client_id=tenant.get("card_client_id") or None,
            card_client_secret=tenant.get("card_client_secret") or None,
            ws_client_id=tenant.get("ws_client_id") or None,
            ws_client_secret=tenant.get("ws_client_secret") or None,
            shared_client_id=tenant.get("shared_client_id") or None,
            shared_client_secret=tenant.get("shared_client_secret") or None,
        )

    @app.get("/tenant/printers", response_class=HTMLResponse)
    async def tenant_printers(request: Request, search: str = ""):
        user = require_login(request)
        if user is None: return RedirectResponse("/login", status_code=302)
        tc = t_ctx(request)
        printers = []
        error = None
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
            if tenant and (tenant.get("print_client_id") or tenant.get("shared_client_id")):
                client = _make_printix_client(tenant)
                data = client.list_printers(search=search or None, size=100)
                import re as _re
                raw = data.get("printers", data.get("content", []))
                # Deduplizieren nach printer_id – jedes Item im API-Response ist ein
                # Printer-Queue-Paar. Queues desselben Druckers werden gruppiert.
                printer_map = {}
                for p in raw:
                    href = (p.get("_links") or {}).get("self", {}).get("href", "")
                    m = _re.search(r"/printers/([^/]+)/queues/([^/?]+)", href)
                    pid = m.group(1) if m else p.get("id", "")
                    qid = m.group(2) if m else ""
                    if pid not in printer_map:
                        vendor = p.get("vendor", "")
                        model  = p.get("model", "")
                        printer_map[pid] = {
                            "printer_id":    pid,
                            "name":          f"{vendor} {model}".strip() if (vendor or model) else p.get("name", ""),
                            "vendor":        vendor,
                            "location":      p.get("location", ""),
                            "status":        p.get("connectionStatus", ""),
                            "printerSignId": p.get("printerSignId", ""),
                            "queues":        [],
                        }
                    printer_map[pid]["queues"].append({
                        "name":     p.get("name", ""),
                        "queue_id": qid,
                    })
                printers = list(printer_map.values())
            elif not tenant:
                error = "no_tenant"
            else:
                error = "no_print_creds"
        except Exception as e:
            logger.error("tenant_printers error: %s", e)
            error = str(e)
        return templates.TemplateResponse("tenant_printers.html", {
            "request": request, "user": user,
            "printers": printers, "search": search, "error": error,
            "active_tab": "printers", **tc,
        })

    @app.get("/tenant/queues", response_class=HTMLResponse)
    async def tenant_queues(request: Request, search: str = ""):
        user = require_login(request)
        if user is None: return RedirectResponse("/login", status_code=302)
        tc = t_ctx(request)
        queues = []
        error = None
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
            if tenant and (tenant.get("print_client_id") or tenant.get("shared_client_id")):
                client = _make_printix_client(tenant)
                data = client.list_printers(search=search or None, size=100)
                raw = data.get("printers", data.get("content", []))
                import re as _re
                for p in raw:
                    # Printix API: jedes Item ist ein Printer-Queue-Paar.
                    # _links.self.href = /printers/{printer_id}/queues/{queue_id}
                    href = (p.get("_links") or {}).get("self", {}).get("href", "")
                    m = _re.search(r"/printers/([^/]+)/queues/([^/?]+)", href)
                    printer_id = m.group(1) if m else ""
                    queue_id   = m.group(2) if m else p.get("id", "")
                    vendor = p.get("vendor", "")
                    model  = p.get("model", "")
                    printer_name = f"{vendor} {model}".strip() if (vendor or model) else p.get("name", "")
                    queues.append({
                        "queue_name":   p.get("name", ""),
                        "queue_id":     queue_id,
                        "printer_name": printer_name,
                        "printer_id":   printer_id,
                        "location":     p.get("location", ""),
                        "status":       p.get("connectionStatus", ""),
                        "queue_type":   p.get("type", p.get("queueType", "")),
                    })
            elif not tenant:
                error = "no_tenant"
            else:
                error = "no_print_creds"
        except Exception as e:
            logger.error("tenant_queues error: %s", e)
            error = str(e)
        return templates.TemplateResponse("tenant_queues.html", {
            "request": request, "user": user,
            "queues": queues, "search": search, "error": error,
            "active_tab": "queues", **tc,
        })

    @app.get("/tenant/users", response_class=HTMLResponse)
    async def tenant_users(request: Request, search: str = ""):
        user = require_login(request)
        if user is None: return RedirectResponse("/login", status_code=302)
        tc = t_ctx(request)
        users = []
        error = None
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
            if tenant and (tenant.get("card_client_id") or tenant.get("shared_client_id")):
                client = _make_printix_client(tenant)
                regular = client.list_users(role="USER", query=search or None, page_size=100)
                guests  = client.list_users(role="GUEST_USER", query=search or None, page_size=100)
                seen = set()
                for u in (regular.get("users", regular.get("content", []))
                         + guests.get("users", guests.get("content", []))):
                    uid = u.get("id", "")
                    if uid not in seen:
                        seen.add(uid)
                        users.append(u)
            elif not tenant:
                error = "no_tenant"
            else:
                error = "no_card_creds"
        except Exception as e:
            logger.error("tenant_users error: %s", e)
            error = str(e)
        return templates.TemplateResponse("tenant_users.html", {
            "request": request, "user": user,
            "users": users, "search": search, "error": error,
            "active_tab": "users", **tc,
        })

    # ─── Printix Tenant: Users/Cards (create must be before {user_id}) ──────────

    @app.get("/tenant/users/create", response_class=HTMLResponse)
    async def tenant_user_create_get(request: Request):
        user = require_login(request)
        if user is None: return RedirectResponse("/login", status_code=302)
        tc = t_ctx(request)
        return templates.TemplateResponse("tenant_user_create.html", {
            "request": request, "user": user, "error": None, **tc,
        })

    @app.post("/tenant/users/create", response_class=HTMLResponse)
    async def tenant_user_create_post(
        request: Request,
        email:        str = Form(...),
        display_name: str = Form(...),
        pin:          str = Form(""),
    ):
        user = require_login(request)
        if user is None: return RedirectResponse("/login", status_code=302)
        tc = t_ctx(request)
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
            if not tenant or not (tenant.get("card_client_id") or tenant.get("shared_client_id")):
                return templates.TemplateResponse("tenant_user_create.html", {
                    "request": request, "user": user, "error": "no_card_creds", **tc,
                })
            client = _make_printix_client(tenant)
            result = client.create_user(
                email=email.strip(),
                display_name=display_name.strip(),
                pin=pin.strip() if pin.strip() else None,
            )
            new_id = result.get("id", "")
            return RedirectResponse(
                f"/tenant/users/{new_id}?flash=created" if new_id else "/tenant/users?flash=created",
                status_code=302
            )
        except Exception as e:
            logger.error("tenant_user_create error: %s", e)
            return templates.TemplateResponse("tenant_user_create.html", {
                "request": request, "user": user, "error": str(e), **tc,
            })

    @app.get("/tenant/users/{printix_user_id}", response_class=HTMLResponse)
    async def tenant_user_detail(request: Request, printix_user_id: str, flash: str = ""):
        user = require_login(request)
        if user is None: return RedirectResponse("/login", status_code=302)
        tc = t_ctx(request)
        px_user = None
        cards   = []
        error   = None
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
            if not tenant or not (tenant.get("card_client_id") or tenant.get("shared_client_id")):
                error = "no_card_creds"
            else:
                client = _make_printix_client(tenant)
                px_user_raw = client.get_user(printix_user_id)
                # Printix API returns {"user": {...}, "success": true} — unwrap nested
                px_user = px_user_raw.get("user", px_user_raw) if isinstance(px_user_raw, dict) else {}
                try:
                    cards_data = client.list_user_cards(printix_user_id)
                    raw_cards = cards_data.get("cards", cards_data.get("content", []))
                    # Extract card ID from _links.self.href (no "id" field in API response)
                    cards = []
                    for c in raw_cards:
                        href = (c.get("_links") or {}).get("self", {}).get("href", "")
                        c["card_id"] = href.split("/")[-1] if href else c.get("id", "")
                        cards.append(c)
                except Exception:
                    cards = []
        except Exception as e:
            logger.error("tenant_user_detail error: %s", e)
            error = str(e)
        return templates.TemplateResponse("tenant_user_detail.html", {
            "request": request, "user": user,
            "px_user": px_user, "cards": cards,
            "printix_user_id": printix_user_id,
            "flash": flash, "error": error,
            **tc,
        })

    @app.post("/tenant/users/{printix_user_id}/add-card")
    async def tenant_user_add_card(
        request: Request,
        printix_user_id: str,
        card_number: str = Form(...),
    ):
        user = require_login(request)
        if user is None:
            return JSONResponse({"ok": False, "error": "not logged in"}, status_code=401)
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
            client = _make_printix_client(tenant)
            client.register_card(printix_user_id, card_number.strip())
            return RedirectResponse(
                f"/tenant/users/{printix_user_id}?flash=card_added", status_code=302
            )
        except Exception as e:
            logger.error("tenant_user_add_card error: %s", e)
            from urllib.parse import quote_plus as _qp
            return RedirectResponse(
                f"/tenant/users/{printix_user_id}?flash=error&errmsg={_qp(str(e)[:80])}",
                status_code=302,
            )

    @app.post("/tenant/users/{printix_user_id}/delete-card")
    async def tenant_user_delete_card(
        request: Request,
        printix_user_id: str,
        card_id: str = Form(...),
    ):
        user = require_login(request)
        if user is None:
            return JSONResponse({"ok": False, "error": "not logged in"}, status_code=401)
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
            client = _make_printix_client(tenant)
            # Use user-scoped delete: DELETE /users/{uid}/cards/{card_id}
            client.delete_card(card_id, user_id=printix_user_id)
            return RedirectResponse(
                f"/tenant/users/{printix_user_id}?flash=card_deleted", status_code=302
            )
        except Exception as e:
            logger.error("tenant_user_delete_card error: %s", e)
            return RedirectResponse(
                f"/tenant/users/{printix_user_id}?flash=error", status_code=302
            )

    @app.post("/tenant/users/{printix_user_id}/generate-id-code")
    async def tenant_user_gen_code(request: Request, printix_user_id: str):
        user = require_login(request)
        if user is None:
            return JSONResponse({"ok": False, "error": "not logged in"}, status_code=401)
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
            client = _make_printix_client(tenant)
            result = client.generate_id_code(printix_user_id)
            code = result.get("idCode", result.get("code", ""))
            return RedirectResponse(
                f"/tenant/users/{printix_user_id}?flash=code_generated&idcode={code}", status_code=302
            )
        except Exception as e:
            logger.error("tenant_user_gen_code error: %s", e)
            return RedirectResponse(
                f"/tenant/users/{printix_user_id}?flash=error", status_code=302
            )

    @app.post("/tenant/users/{printix_user_id}/delete")
    async def tenant_user_delete(request: Request, printix_user_id: str):
        user = require_login(request)
        if user is None:
            return JSONResponse({"ok": False, "error": "not logged in"}, status_code=401)
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
            client = _make_printix_client(tenant)
            client.delete_user(printix_user_id)
            return RedirectResponse("/tenant/users?flash=deleted", status_code=302)
        except Exception as e:
            logger.error("tenant_user_delete error: %s", e)
            return RedirectResponse(
                f"/tenant/users/{printix_user_id}?flash=error", status_code=302
            )


    # ── Demo-Daten-Register (v3.5.0) ─────────────────────────────────────────
    import uuid as _uuid
    import time as _time
    import asyncio as _asyncio
    import functools as _functools
    _demo_jobs: dict = {}  # job_id → {status, error, session_id, started}

    @app.get("/tenant/demo/status")
    async def tenant_demo_status(request: Request, job_id: str = ""):
        user = require_login(request)
        if user is None:
            return JSONResponse({"status": "error", "error": "not_logged_in"})
        job = _demo_jobs.get(job_id)
        if not job:
            return JSONResponse({"status": "unknown"})
        # Tenant-Isolation: nur eigene Jobs anzeigen
        if job.get("user_id") and job["user_id"] != user["id"]:
            return JSONResponse({"status": "unknown"})
        return JSONResponse({
            "status": job.get("status"),
            "error": job.get("error", ""),
            "session_id": job.get("session_id", ""),
        })

    @app.get("/tenant/demo", response_class=HTMLResponse)
    async def tenant_demo(request: Request):
        """
        Demo-Übersicht.

        v3.9.2: Rendert die Seite SOFORT ohne Azure SQL-Aufruf — die
        Session-Liste und das schema_ready-Flag werden per JS aus
        /tenant/demo/sessions nachgeladen. Damit verschwindet der
        30–60s lange Erstaufruf bei Azure SQL Serverless (Auto-Pause-
        Wake-up). Spätere Aufrufe sind ebenfalls instant, die SQL-Last
        verlagert sich in den XHR-Endpunkt.
        """
        user = require_login(request)
        if user is None:
            return RedirectResponse("/login", status_code=302)
        tc = t_ctx(request)
        flash     = request.query_params.get("flash")
        flash_msg = request.query_params.get("errmsg", request.query_params.get("flash_msg", ""))
        job_id    = request.query_params.get("job_id", "")
        # Schneller Check: ist überhaupt SQL konfiguriert? — kein Roundtrip,
        # nur ein Lookup im Tenant-Datensatz aus der lokalen SQLite.
        has_sql = False
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
            has_sql = bool(tenant and tenant.get("sql_server"))
        except Exception as e:
            logger.warning("tenant_demo tenant lookup error: %s", e)
        return templates.TemplateResponse("tenant_demo.html", {
            "request": request, "user": user,
            "has_sql": has_sql,
            # sessions + schema_ready werden per XHR nachgeladen
            "sessions": None,
            "schema_ready": None,
            "flash": flash, "flash_msg": flash_msg,
            "job_id": job_id,
            "form_defaults": {}, "form": {}, "active_tab": "demo", **tc,
        })

    # ── In-Memory-Cache für Demo-Sessions (per Tenant, 30s TTL) ──────────
    # Hauptzweck: zweiter Aufruf der Demo-Seite spart einen Azure-SQL-RTT.
    # Größe ist beschränkt auf wenige Tenants — kein Memory-Leak.
    _demo_session_cache: dict = {}  # tenant_id -> (expires_ts, payload)

    @app.get("/tenant/demo/sessions")
    async def tenant_demo_sessions(request: Request):
        """
        Liefert {schema_ready, sessions} als JSON. Wird vom Demo-Template
        per fetch() aufgerufen, sodass die Seite ohne Azure SQL gerendert
        werden kann.
        """
        user = require_login(request)
        if user is None:
            return JSONResponse({"error": "not_logged_in"}, status_code=401)
        try:
            from db import get_tenant_full_by_user_id
            from reporting.sql_client import set_config_from_tenant, is_configured
            tenant = get_tenant_full_by_user_id(user["id"])
            if not tenant or not tenant.get("sql_server"):
                return JSONResponse({"schema_ready": False, "sessions": [], "has_sql": False})
            set_config_from_tenant(tenant)
            if not is_configured():
                return JSONResponse({"schema_ready": False, "sessions": [], "has_sql": False})

            tid = tenant.get("printix_tenant_id", "")
            cached = _demo_session_cache.get(tid)
            if cached and cached[0] > _time.time():
                return JSONResponse(cached[1])

            import asyncio as _aio
            from reporting.sql_client import query_fetchall
            try:
                rows = await _aio.to_thread(
                    query_fetchall,
                    # WICHTIG: demo.* (nicht dbo.*) — der Generator legt die
                    # Tabellen im 'demo'-Schema an (siehe demo_generator.py).
                    "SELECT TOP 20 session_id, tenant_id, demo_tag, created_at, "
                    "user_count, printer_count, network_count, "
                    "print_job_count, scan_job_count, copy_job_count, "
                    "status, params_json "
                    "FROM demo.demo_sessions WHERE tenant_id = ? "
                    "ORDER BY created_at DESC",
                    (tid,),
                )
                schema_ready = True
                sessions = rows or []
            except Exception as ex:
                # "Invalid object name 'demo.demo_sessions'" → Schema noch
                # nicht eingerichtet. Das ist KEIN Fehler, sondern der
                # Initial-Zustand: User soll den Setup-Button sehen.
                msg = str(ex)
                if "Invalid object name" in msg or "demo.demo_sessions" in msg:
                    schema_ready = False
                    sessions = []
                else:
                    logger.warning("tenant_demo_sessions SQL error: %s", ex)
                    return JSONResponse({"error": str(ex)[:200], "has_sql": True}, status_code=500)

            # ISO-Strings für JSON
            def _ser(s):
                out = dict(s)
                if out.get("created_at") is not None:
                    out["created_at"] = str(out["created_at"])
                # preset aus params_json extrahieren (falls vorhanden)
                pj = out.get("params_json") or ""
                try:
                    import json as _j
                    pdata = _j.loads(pj) if pj else {}
                    out["preset"] = pdata.get("preset", "custom")
                    out["queue_count"] = pdata.get("queue_count", 0)
                except Exception:
                    out["preset"] = "custom"
                    out["queue_count"] = 0
                # params_json selbst nicht ans Frontend schicken
                out.pop("params_json", None)
                return out

            payload = {
                "has_sql": True,
                "schema_ready": schema_ready,
                "sessions": [_ser(s) for s in sessions],
            }
            _demo_session_cache[tid] = (_time.time() + 30, payload)
            return JSONResponse(payload)
        except Exception as e:
            logger.warning("tenant_demo_sessions error: %s", e)
            return JSONResponse({"error": str(e)[:200]}, status_code=500)

    def _demo_cache_invalidate(tenant_id: str) -> None:
        """Aufruf nach generate / delete / rollback, damit der nächste GET frisch lädt."""
        _demo_session_cache.pop(tenant_id, None)

    @app.post("/tenant/demo/setup", response_class=HTMLResponse)
    async def tenant_demo_setup(request: Request):
        user = require_login(request)
        if user is None: return RedirectResponse("/login", status_code=302)
        try:
            from db import get_tenant_full_by_user_id
            from reporting.sql_client import set_config_from_tenant
            from reporting.demo_generator import setup_schema
            tenant = get_tenant_full_by_user_id(user["id"])
            if not tenant or not tenant.get("sql_server"):
                return RedirectResponse("/tenant/demo?flash=error&errmsg=SQL+nicht+konfiguriert", status_code=302)
            set_config_from_tenant(tenant)
            result = setup_schema()
            if result.get("success"):
                return RedirectResponse("/tenant/demo?flash=setup_ok", status_code=302)
            errmsg = "; ".join(e.get("error","") for e in result.get("errors", []))[:200]
            from urllib.parse import quote_plus as _qp
            return RedirectResponse(f"/tenant/demo?flash=error&errmsg={_qp(errmsg)}", status_code=302)
        except Exception as e:
            logger.error("tenant_demo_setup error: %s", e)
            from urllib.parse import quote_plus as _qp
            return RedirectResponse(f"/tenant/demo?flash=error&errmsg={_qp(str(e)[:200])}", status_code=302)

    @app.post("/tenant/demo/generate", response_class=HTMLResponse)
    async def tenant_demo_generate(request: Request):
        user = require_login(request)
        if user is None: return RedirectResponse("/login", status_code=302)
        try:
            from db import get_tenant_full_by_user_id
            from reporting.sql_client import set_config_from_tenant, get_tenant_id
            from reporting.demo_generator import generate_demo_dataset
            tenant = get_tenant_full_by_user_id(user["id"])
            if not tenant or not tenant.get("sql_server"):
                return RedirectResponse("/tenant/demo?flash=error&errmsg=SQL+nicht+konfiguriert", status_code=302)
            set_config_from_tenant(tenant)
            form_data = await request.form()
            user_count    = max(1, min(200, int(form_data.get("user_count",    10))))
            printer_count = max(1, min(50,  int(form_data.get("printer_count",  4))))
            queue_count   = max(1, min(5,   int(form_data.get("queue_count",    2))))
            months        = max(1, min(36,  int(form_data.get("months",        12))))
            jobs_per_day  = max(0.5, min(15.0, float(form_data.get("jobs_per_day", 2.0))))
            languages     = form_data.getlist("languages") or ["de", "en"]
            sites_raw     = form_data.get("sites", "")
            sites         = [s.strip() for s in sites_raw.split(",") if s.strip()] or ["Hauptsitz"]
            demo_tag      = (form_data.get("demo_tag") or "").strip()[:80]
            preset        = (form_data.get("preset") or "custom").strip()[:20]
            if preset not in ("small", "medium", "large", "custom"):
                preset = "custom"
            tid = get_tenant_id()
            # Hintergrund-Task: sofort Redirect, Browser pollt /tenant/demo/status
            # SUBPROCESS-Isolation: pyodbc/FreeTDS Segfaults töten nicht den Web-Server
            job_id = _uuid.uuid4().hex[:10]
            _demo_jobs[job_id] = {"status": "running", "started": _time.time(),
                                  "user_id": user["id"]}
            async def _bg_generate():
                import json as _json, sys as _sys, os as _os
                output_file = f"/tmp/demo_result_{job_id}.json"
                try:
                    # Tenant-Config und Parameter als JSON an den Worker-Prozess übergeben
                    tenant_config = {
                        "sql_server":        tenant.get("sql_server", ""),
                        "sql_database":      tenant.get("sql_database", ""),
                        "sql_username":      tenant.get("sql_username", ""),
                        "sql_password":      tenant.get("sql_password", ""),
                        "printix_tenant_id": tenant.get("printix_tenant_id", ""),
                    }
                    demo_params = {
                        "tenant_id":         tid,
                        "user_count":        user_count,
                        "printer_count":     printer_count,
                        "queue_count":       queue_count,
                        "months":            months,
                        "jobs_per_user_day": jobs_per_day,
                        "languages":         languages,
                        "sites":             sites,
                        "demo_tag":          demo_tag or f"Demo {__import__('datetime').date.today()}",
                        "preset":            preset,
                    }
                    env = dict(_os.environ)
                    env["DEMO_TENANT_CONFIG"] = _json.dumps(tenant_config)
                    env["DEMO_PARAMS"]        = _json.dumps(demo_params)
                    env["DEMO_OUTPUT_FILE"]   = output_file
                    proc = await _asyncio.create_subprocess_exec(
                        _sys.executable, "/app/reporting/demo_worker.py",
                        env=env,
                        stdout=_asyncio.subprocess.PIPE,
                        stderr=_asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await proc.communicate()
                    if proc.returncode == 0:
                        try:
                            with open(output_file) as _f:
                                result = _json.load(_f)
                        except Exception:
                            result = {}
                        if result.get("error"):
                            _demo_jobs[job_id] = {"status": "error", "error": str(result["error"])[:200]}
                        else:
                            _demo_jobs[job_id] = {"status": "done", "session_id": result.get("session_id", "")}
                            # Cache invalidieren, damit die Sessions-Liste sofort aktualisiert wird
                            _demo_cache_invalidate(tid)
                    else:
                        # Subprocess fehlgeschlagen (auch Segfault = exit -11)
                        err = ""
                        try:
                            with open(output_file) as _f:
                                err = _json.load(_f).get("error", "")[:200]
                        except Exception:
                            pass
                        if not err:
                            err = (stderr.decode("utf-8", errors="replace") or "").strip()[-200:]
                        if not err:
                            err = f"Worker exit {proc.returncode}"
                        logger.error("Demo-Worker exit %d: %s", proc.returncode, err)
                        _demo_jobs[job_id] = {"status": "error", "error": err}
                except Exception as exc:
                    logger.error("bg_generate error: %s", exc)
                    _demo_jobs[job_id] = {"status": "error", "error": str(exc)[:200]}
                finally:
                    try:
                        _os.unlink(output_file)
                    except Exception:
                        pass
            _asyncio.create_task(_bg_generate())
            return RedirectResponse(f"/tenant/demo?job_id={job_id}", status_code=302)
        except Exception as e:
            logger.error("tenant_demo_generate error: %s", e)
            from urllib.parse import quote_plus as _qp
            return RedirectResponse(
                f"/tenant/demo?flash=error&errmsg={_qp(str(e)[:100])}",
                status_code=302,
            )

    @app.post("/tenant/demo/delete/{session_id}", response_class=HTMLResponse)
    async def tenant_demo_delete(request: Request, session_id: str):
        """
        Löscht alle Demo-Datenzeilen einer einzelnen Session.

        v3.9.2 — Bug-Fix: vorher wurden Tabellen aus dem `dbo.*`-Schema
        gelöscht, der Generator schreibt aber nach `demo.*`. Außerdem
        wurde `execute_write` mit `[(a,b)]` aufgerufen statt mit `(a,b)` —
        das hätte zur Laufzeit „wrong number of parameters" geworfen.
        Beide Bugs sind hier behoben, plus jobs_copy_details wird in
        DERSELBEN Verbindung VOR jobs_copy gelöscht (Reihenfolge wichtig).
        """
        user = require_login(request)
        if user is None:
            return RedirectResponse("/login", status_code=302)
        try:
            from db import get_tenant_full_by_user_id
            from reporting.sql_client import set_config_from_tenant, get_tenant_id, execute_write
            tenant = get_tenant_full_by_user_id(user["id"])
            if not tenant or not tenant.get("sql_server"):
                return RedirectResponse("/tenant/demo?flash=error", status_code=302)
            set_config_from_tenant(tenant)
            tid = get_tenant_id()
            # 1) jobs_copy_details ZUERST (FK-Reihenfolge auch wenn keine
            #    explizite Constraint existiert — bei Subquery muss jobs_copy
            #    noch da sein, damit der Lookup klappt).
            try:
                execute_write(
                    "DELETE FROM demo.jobs_copy_details WHERE job_id IN "
                    "(SELECT id FROM demo.jobs_copy WHERE demo_session_id=? AND tenant_id=?)",
                    (session_id, tid),
                )
            except Exception as ex:
                logger.warning("delete jobs_copy_details: %s", ex)
            # 2) Restliche Daten-Tabellen
            for tbl in ("tracking_data", "jobs", "jobs_scan", "jobs_copy",
                        "users", "printers", "networks"):
                try:
                    execute_write(
                        f"DELETE FROM demo.{tbl} WHERE demo_session_id=? AND tenant_id=?",
                        (session_id, tid),
                    )
                except Exception as ex:
                    logger.warning("delete demo.%s: %s", tbl, ex)
            # 3) Session-Eintrag selbst
            try:
                execute_write(
                    "DELETE FROM demo.demo_sessions WHERE session_id=? AND tenant_id=?",
                    (session_id, tid),
                )
            except Exception as ex:
                logger.warning("delete demo.demo_sessions: %s", ex)
            _demo_cache_invalidate(tid)
            return RedirectResponse("/tenant/demo?flash=deleted", status_code=302)
        except Exception as e:
            logger.error("tenant_demo_delete error: %s", e)
            from urllib.parse import quote_plus as _qp
            return RedirectResponse(
                f"/tenant/demo?flash=error&errmsg={_qp(str(e)[:100])}",
                status_code=302,
            )

    @app.post("/tenant/demo/rollback", response_class=HTMLResponse)
    async def tenant_demo_rollback(request: Request):
        """
        Rollback per demo_tag — löscht ALLE Sessions mit dem angegebenen Tag.

        v3.9.2: Diese Route fehlte, das Template (tenant_demo.html) hat aber
        per <form action="/tenant/demo/rollback"> auf sie gepostet → 404.
        Das hat den Per-Session-Rollback-Button komplett unbrauchbar gemacht.
        """
        user = require_login(request)
        if user is None:
            return RedirectResponse("/login", status_code=302)
        try:
            from db import get_tenant_full_by_user_id
            from reporting.sql_client import set_config_from_tenant, get_tenant_id
            from reporting.demo_generator import rollback_demo
            tenant = get_tenant_full_by_user_id(user["id"])
            if not tenant or not tenant.get("sql_server"):
                return RedirectResponse("/tenant/demo?flash=error&flash_msg=no_sql", status_code=302)
            set_config_from_tenant(tenant)
            form_data = await request.form()
            demo_tag = (form_data.get("demo_tag") or "").strip()[:80]
            if not demo_tag:
                return RedirectResponse("/tenant/demo?flash=error&flash_msg=missing_tag",
                                        status_code=302)
            tid = get_tenant_id()
            result = await _asyncio.to_thread(rollback_demo, tid, demo_tag)
            logger.info("Demo-Rollback (tag=%s): %d Zeilen gelöscht",
                        demo_tag, result.get("total_deleted", 0))
            _demo_cache_invalidate(tid)
            return RedirectResponse("/tenant/demo?flash=rollback_ok", status_code=302)
        except Exception as e:
            logger.error("tenant_demo_rollback error: %s", e)
            from urllib.parse import quote_plus as _qp
            return RedirectResponse(
                f"/tenant/demo?flash=error&flash_msg={_qp(str(e)[:120])}",
                status_code=302,
            )


    @app.post("/tenant/demo/rollback-all", response_class=HTMLResponse)
    async def tenant_demo_rollback_all(request: Request):
        """Löscht ALLE Demo-Daten des Tenants – auch ohne bestehende Sessions."""
        user = require_login(request)
        if user is None:
            return RedirectResponse("/login", status_code=302)
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
            if not tenant or not tenant.get("sql_server"):
                return RedirectResponse("/tenant/demo?flash=error&flash_msg=no_sql", status_code=302)
            import sys as _sys, os as _os
            src_dir = _os.path.dirname(_os.path.dirname(__file__))
            if src_dir not in _sys.path:
                _sys.path.insert(0, src_dir)
            from reporting.sql_client import set_config_from_tenant
            set_config_from_tenant(tenant)
            from reporting.demo_generator import rollback_demo_all
            result = rollback_demo_all(tenant["printix_tenant_id"])
            logger.info("Demo-Rollback-All: %d Zeilen gelöscht", result.get("total_deleted", 0))
            return RedirectResponse("/tenant/demo?flash=rollback_ok", status_code=302)
        except Exception as e:
            logger.error("tenant_demo_rollback_all error: %s", e)
            from urllib.parse import quote_plus as _qp
            return RedirectResponse(
                f"/tenant/demo?flash=error&flash_msg={_qp(str(e)[:120])}",
                status_code=302,
            )

    # ── Reports-Register (v3.0.0) ─────────────────────────────────────────────
    try:
        from web.reports_routes import register_reports_routes
        register_reports_routes(app, templates, t_ctx, require_login)
    except Exception as _re:
        logger.error("Reports-Routen konnten nicht registriert werden: %s", _re)

    return app
