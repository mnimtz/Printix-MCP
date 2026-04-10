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


# ── Tenant-aware DB-Logging für Web-Requests ─────────────────────────────────
class _WebTenantDBHandler(logging.Handler):
    """Schreibt Logs in die tenant_logs-Tabelle wenn ein Tenant-Kontext aktiv ist."""
    _CAT = {
        "printix_client": "PRINTIX_API", "printix.api": "PRINTIX_API",
        "reporting": "SQL", "sql": "SQL",
        "auth": "AUTH", "oauth": "AUTH",
    }
    def emit(self, record: logging.LogRecord) -> None:
        try:
            from auth import current_tenant as _ct
            tenant = _ct.get()
            if not tenant:
                return
            tid = tenant.get("id", "")
            if not tid:
                return
            cat = "SYSTEM"
            nl = record.name.lower()
            for k, v in self._CAT.items():
                if k in nl:
                    cat = v
                    break
            from db import add_tenant_log
            add_tenant_log(tid, record.levelname, cat, self.format(record))
        except Exception:
            pass

_web_db_handler = _WebTenantDBHandler()
_web_db_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
_web_db_handler.setLevel(logging.DEBUG)
logging.getLogger().addHandler(_web_db_handler)

# Templates-Verzeichnis (relativ zu diesem File)
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")


def create_app(session_secret: str) -> FastAPI:
    app = FastAPI(title="Printix MCP Admin", docs_url=None, redoc_url=None)
    app.add_middleware(SessionMiddleware, secret_key=session_secret, max_age=3600 * 8)

    # ── Tenant-Kontext pro Web-Request setzen (für DB-Logging) ───────────────
    @app.middleware("http")
    async def _set_web_tenant_ctx(request: Request, call_next):
        try:
            from auth import current_tenant as _ct
            uid = request.session.get("user_id") if hasattr(request, "session") else None
            if uid:
                try:
                    from db import get_tenant_full_by_user_id
                    _t = get_tenant_full_by_user_id(uid)
                    if _t:
                        _tok = _ct.set(_t)
                        try:
                            return await call_next(request)
                        finally:
                            _ct.reset(_tok)
                except Exception:
                    pass
        except Exception:
            pass
        return await call_next(request)

    templates = Jinja2Templates(directory=TEMPLATES_DIR)

    # ── Jinja2 custom filters ─────────────────────────────────────────────────
    import json as _json

    def _from_json(value):
        try:
            result = _json.loads(value or "[]")
            return result if isinstance(result, list) else ["log_error"]
        except Exception:
            return ["log_error"]

    templates.env.filters["from_json"] = _from_json

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
        return {
            "_":             make_translator(lang),
            "lang":          lang,
            "lang_names":    LANGUAGE_NAMES,
            "supported_langs": SUPPORTED_LANGUAGES,
        }

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
        referer = request.headers.get("referer", "/")
        return RedirectResponse(referer, status_code=302)

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

            # Ereignis-Benachrichtigung: user_registered — alle Admins informieren
            try:
                from db import get_all_users, get_tenant_full_by_user_id as _gtf
                from reporting.notify_helper import (
                    send_event_notification as _notify,
                    html_user_registered as _html_ur,
                )
                for _admin_user in get_all_users():
                    if not _admin_user.get("is_admin"):
                        continue
                    _admin_tenant = _gtf(_admin_user["id"])
                    if not _admin_tenant:
                        continue
                    _notify(
                        tenant=_admin_tenant,
                        event_type="user_registered",
                        subject=f"🔔 Neuer Benutzer registriert: {user.get('username','')}",
                        html_body=_html_ur(
                            username=user.get("username", ""),
                            email=user.get("email", ""),
                            company=user.get("company", ""),
                        ),
                    )
            except Exception as _ure:
                logger.debug("user_registered Benachrichtigung fehlgeschlagen: %s", _ure)

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

    @app.get("/login", response_class=HTMLResponse)
    async def login_get(request: Request):
        if get_session_user(request):
            return RedirectResponse("/", status_code=302)
        return templates.TemplateResponse("login.html", {
            "request": request, "error": None, **t_ctx(request)
        })

    @app.post("/login", response_class=HTMLResponse)
    async def login_post(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
    ):
        tc = t_ctx(request)
        _  = tc["_"]
        try:
            from db import authenticate_user, audit
            user = authenticate_user(username, password)
        except Exception as e:
            return templates.TemplateResponse("login.html", {
                "request": request, "error": f"Datenbankfehler: {e}",
                "username": username, **tc,
            })

        if not user:
            return templates.TemplateResponse("login.html", {
                "request": request, "error": _("login_error"),
                "username": username, **tc,
            })

        status = user.get("status", "")
        if status == "disabled" or status == "suspended":
            return templates.TemplateResponse("login.html", {
                "request": request, "error": _("login_suspended"),
                "username": username, **tc,
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
            from db import get_tenant_by_user_id
            tenant = get_tenant_by_user_id(user["id"])
        except Exception:
            pass

        return templates.TemplateResponse("dashboard.html", {
            "request": request, "user": user, "tenant": tenant,
            "base_url": base,
            "mcp_url":  f"{base}/mcp",
            "sse_url":  f"{base}/sse",
            **t_ctx(request),
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
        mail_from_name:       str = Form(default=""),
        alert_recipients:     str = Form(default=""),
        alert_min_level:      str = Form(default="ERROR"),
        notify_log_error:      str = Form(default=""),
        notify_new_printer:    str = Form(default=""),
        notify_new_queue:      str = Form(default=""),
        notify_new_guest_user: str = Form(default=""),
        notify_report_sent:    str = Form(default=""),
        notify_user_registered: str = Form(default=""),
    ):
        user = require_login(request)
        if not user:
            return RedirectResponse("/login", status_code=302)
        tc = t_ctx(request)

        try:
            from db import update_tenant_credentials, get_tenant_full_by_user_id, audit
            # Checkboxen → notify_events JSON-Array aufbauen
            _ne = []
            if notify_log_error:      _ne.append("log_error")
            if notify_new_printer:    _ne.append("new_printer")
            if notify_new_queue:      _ne.append("new_queue")
            if notify_new_guest_user: _ne.append("new_guest_user")
            if notify_report_sent:    _ne.append("report_sent")
            if notify_user_registered: _ne.append("user_registered")
            import json as _json
            _notify_events_json = _json.dumps(_ne)

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
                mail_from_name=mail_from_name.strip() or None,
                alert_recipients=alert_recipients.strip() or None,
                alert_min_level=alert_min_level.strip() or None,
                notify_events=_notify_events_json,
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
            audit(admin["id"], "approve_user", f"User {user_id} genehmigt")
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
            audit(admin["id"], "disable_user", f"User {user_id} deaktiviert")
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
            audit(admin["id"], "delete_user", f"User {user_id} gelöscht")
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
            audit(admin["id"], "edit_user", f"User {user_id} bearbeitet")
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
            audit(admin["id"], "reset_password", f"Passwort für User {user_id} zurückgesetzt")
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

    @app.get("/admin/settings", response_class=HTMLResponse)
    async def admin_settings_get(request: Request):
        user = get_session_user(request)
        if not user or not user.get("is_admin"):
            return RedirectResponse("/login", status_code=302)
        try:
            from db import get_setting
            public_url = get_setting("public_url", "")
        except Exception:
            public_url = os.environ.get("MCP_PUBLIC_URL", "")
        return templates.TemplateResponse("admin_settings.html", {
            "request": request, "user": user,
            "public_url": public_url,
            "saved": False, "error": None, **t_ctx(request),
        })

    @app.post("/admin/settings", response_class=HTMLResponse)
    async def admin_settings_post(
        request:    Request,
        public_url: str = Form(default=""),
    ):
        user = get_session_user(request)
        if not user or not user.get("is_admin"):
            return RedirectResponse("/login", status_code=302)
        tc = t_ctx(request)

        url = public_url.strip().rstrip("/")
        try:
            from db import set_setting, audit
            set_setting("public_url", url)
            audit(user["id"], "admin_settings", f"public_url gesetzt: {url}")
        except Exception as e:
            logger.error("Admin-Settings-Fehler: %s", e)
            return templates.TemplateResponse("admin_settings.html", {
                "request": request, "user": user,
                "public_url": url,
                "saved": False, "error": str(e), **tc,
            })

        return templates.TemplateResponse("admin_settings.html", {
            "request": request, "user": user,
            "public_url": url,
            "saved": True, "error": None, **tc,
        })


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

                # Parallel-Fetch der Karten-Anzahl pro Benutzer (max. 10 parallel, 5s Timeout)
                from concurrent.futures import ThreadPoolExecutor, as_completed
                def _fetch_card_count(uid):
                    try:
                        data = client.list_user_cards(uid)
                        cards = data.get("cards", data.get("content", []))
                        return uid, len(cards)
                    except Exception:
                        return uid, None
                with ThreadPoolExecutor(max_workers=10) as pool:
                    futs = {pool.submit(_fetch_card_count, u.get("id","")): u.get("id","")
                            for u in users if u.get("id")}
                    try:
                        for fut in as_completed(futs, timeout=5):
                            uid, count = fut.result()
                            for u in users:
                                if u.get("id") == uid:
                                    u["_card_count"] = count
                    except Exception:
                        pass  # Timeout oder Fehler — bleibt bei None

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
            return RedirectResponse(
                f"/tenant/users/{printix_user_id}?flash=error&errmsg={str(e)[:80]}", status_code=302
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



    # ── Demo-Daten Register (v3.3.0) ─────────────────────────────────────────
    @app.get("/tenant/demo", response_class=HTMLResponse)
    async def tenant_demo_get(request: Request, flash: str = "", flash_msg: str = ""):
        user = require_login(request)
        if user is None:
            return RedirectResponse("/login", status_code=302)
        tc = t_ctx(request)
        sessions = []
        schema_ready = False
        error = None
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
            if not tenant or not tenant.get("sql_server"):
                error = "no_sql"
            else:
                # SQL-Kontext setzen und Demo-Status laden
                import sys, os
                src_dir = os.path.dirname(os.path.dirname(__file__))
                if src_dir not in sys.path:
                    sys.path.insert(0, src_dir)
                from reporting.sql_client import set_config_from_tenant
                set_config_from_tenant(tenant)
                try:
                    from reporting.demo_generator import get_demo_status
                    status = get_demo_status(tenant["printix_tenant_id"])
                    if "error" not in status:
                        schema_ready = True
                        sessions = status.get("sessions", [])
                    # schema_ready = False wenn Tabelle noch nicht existiert
                except Exception as e:
                    schema_ready = "demo_sessions" in str(e).lower() is False
        except Exception as e:
            logger.error("tenant_demo_get error: %s", e)
            error = str(e)[:120]
        return templates.TemplateResponse("tenant_demo.html", {
            "request": request, "user": user,
            "sessions": sessions,
            "schema_ready": schema_ready,
            "error": error,
            "flash": flash,
            "flash_msg": flash_msg,
            "form": {},
            "active_tab": "demo",
            **tc,
        })

    @app.post("/tenant/demo/setup", response_class=HTMLResponse)
    async def tenant_demo_setup(request: Request):
        user = require_login(request)
        if user is None:
            return RedirectResponse("/login", status_code=302)
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
            if not tenant or not tenant.get("sql_server"):
                return RedirectResponse("/tenant/demo?flash=error&flash_msg=no_sql", status_code=302)
            import sys, os
            src_dir = os.path.dirname(os.path.dirname(__file__))
            if src_dir not in sys.path:
                sys.path.insert(0, src_dir)
            from reporting.sql_client import set_config_from_tenant
            set_config_from_tenant(tenant)
            from reporting.demo_generator import setup_schema
            result = setup_schema()
            if result["success"]:
                return RedirectResponse("/tenant/demo?flash=schema_ok", status_code=302)
            else:
                errs = "; ".join(e["error"] for e in result["errors"][:2])
                return RedirectResponse(f"/tenant/demo?flash=error&flash_msg={errs[:100]}", status_code=302)
        except Exception as e:
            logger.error("tenant_demo_setup error: %s", e)
            return RedirectResponse(f"/tenant/demo?flash=error&flash_msg={str(e)[:100]}", status_code=302)

    @app.post("/tenant/demo/generate", response_class=HTMLResponse)
    async def tenant_demo_generate(request: Request):
        user = require_login(request)
        if user is None:
            return RedirectResponse("/login", status_code=302)
        form_data = await request.form()
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
            if not tenant or not tenant.get("sql_server"):
                return RedirectResponse("/tenant/demo?flash=error&flash_msg=no_sql", status_code=302)
            import sys, os
            src_dir = os.path.dirname(os.path.dirname(__file__))
            if src_dir not in sys.path:
                sys.path.insert(0, src_dir)
            from reporting.sql_client import set_config_from_tenant
            set_config_from_tenant(tenant)
            # Parameter parsen
            preset        = (form_data.get("preset") or "custom").strip()
            user_count    = max(1, min(200, int(form_data.get("user_count", 10))))
            printer_count = max(1, min(50,  int(form_data.get("printer_count", 4))))
            queue_count   = max(1, min(5,   int(form_data.get("queue_count", 2))))
            months        = max(1, min(36,  int(form_data.get("months", 12))))
            jobs_per_day  = max(0.5, min(15.0, float(form_data.get("jobs_per_day", 2.0))))
            languages     = form_data.getlist("languages") or ["de", "en"]
            sites_raw     = form_data.get("sites", "Hauptsitz,Niederlassung")
            sites         = [s.strip() for s in sites_raw.split(",") if s.strip()] or ["Hauptsitz"]
            demo_tag      = (form_data.get("demo_tag") or "").strip()
            from reporting.demo_generator import generate_demo_dataset
            import asyncio as _asyncio, functools as _functools
            result = await _asyncio.to_thread(
                _functools.partial(
                    generate_demo_dataset,
                    tenant_id         = tenant["printix_tenant_id"],
                    preset            = preset,
                    user_count        = user_count,
                    printer_count     = printer_count,
                    queue_count       = queue_count,
                    months            = months,
                    languages         = languages,
                    sites             = sites,
                    demo_tag          = demo_tag or f"Demo {__import__(chr(100)+chr(97)+chr(116)+chr(101)+chr(116)+chr(105)+chr(109)+chr(101)).date.today()}",
                    jobs_per_user_day = jobs_per_day,
                )
            )
            if result.get("error"):
                errmsg = str(result["error"])[:100]
                return RedirectResponse(f"/tenant/demo?flash=error&errmsg={errmsg}", status_code=302)
            logger.info("Demo-Daten generiert: %s", result.get("session_id"))
            return RedirectResponse("/tenant/demo?flash=generate_ok", status_code=302)
        except Exception as e:
            logger.error("tenant_demo_generate error: %s", e)
            return RedirectResponse(f"/tenant/demo?flash=error&flash_msg={str(e)[:120]}", status_code=302)

    @app.post("/tenant/demo/rollback", response_class=HTMLResponse)
    async def tenant_demo_rollback(request: Request):
        user = require_login(request)
        if user is None:
            return RedirectResponse("/login", status_code=302)
        form_data = await request.form()
        demo_tag = (form_data.get("demo_tag") or "").strip()
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
            if not tenant or not tenant.get("sql_server"):
                return RedirectResponse("/tenant/demo?flash=error&flash_msg=no_sql", status_code=302)
            import sys, os
            src_dir = os.path.dirname(os.path.dirname(__file__))
            if src_dir not in sys.path:
                sys.path.insert(0, src_dir)
            from reporting.sql_client import set_config_from_tenant
            set_config_from_tenant(tenant)
            from reporting.demo_generator import rollback_demo
            result = rollback_demo(tenant["printix_tenant_id"], demo_tag)
            logger.info("Demo-Rollback: %s → %d Zeilen gelöscht", demo_tag, result.get("total_deleted", 0))
            return RedirectResponse("/tenant/demo?flash=rollback_ok", status_code=302)
        except Exception as e:
            logger.error("tenant_demo_rollback error: %s", e)
            return RedirectResponse(f"/tenant/demo?flash=error&flash_msg={str(e)[:120]}", status_code=302)

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
            return RedirectResponse(f"/tenant/demo?flash=error&flash_msg={str(e)[:120]}", status_code=302)

    # ── Reports-Register (v3.0.0) ─────────────────────────────────────────────
    try:
        from web.reports_routes import register_reports_routes
        register_reports_routes(app, templates, t_ctx, require_login)
    except Exception as _re:
        logger.error("Reports-Routen konnten nicht registriert werden: %s", _re)

    return app
