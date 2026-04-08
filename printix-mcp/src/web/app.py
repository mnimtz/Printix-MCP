"""
Printix MCP — Web-Verwaltungsoberfläche (FastAPI)
==================================================

Routen:
  GET  /                     → Redirect zu /register oder /admin (je nach DB-Zustand)
  GET  /register             → Schritt 1: Account (Benutzername, Passwort)
  POST /register             → Account speichern → Weiter zu /register/api
  GET  /register/api         → Schritt 2: Printix API-Credentials
  POST /register/api         → API speichern → Weiter zu /register/optional
  GET  /register/optional    → Schritt 3: SQL + Mail (optional)
  POST /register/optional    → Optional speichern → Weiter zu /register/summary
  GET  /register/summary     → Schritt 4: Zusammenfassung + User anlegen
  POST /register/summary     → User in DB speichern + Tenant anlegen

  GET  /login                → Login-Seite
  POST /login                → Login prüfen → Redirect
  GET  /logout               → Session löschen → Redirect /login

  GET  /admin                → Admin-Dashboard (nur für admins)
  GET  /admin/users          → Benutzerliste
  POST /admin/users/{id}/approve  → User genehmigen
  POST /admin/users/{id}/disable  → User deaktivieren
  GET  /admin/audit          → Audit-Log
"""

import os
import logging
from typing import Optional

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

logger = logging.getLogger("printix.web")

# Templates-Verzeichnis (relativ zu diesem File)
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")


def create_app(session_secret: str) -> FastAPI:
    app = FastAPI(title="Printix MCP Admin", docs_url=None, redoc_url=None)
    app.add_middleware(SessionMiddleware, secret_key=session_secret, max_age=3600 * 8)

    templates = Jinja2Templates(directory=TEMPLATES_DIR)

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

    def require_login(request: Request) -> dict:
        user = get_session_user(request)
        if not user:
            raise HTTPException(status_code=302, headers={"Location": "/login"})
        if user.get("status") != "approved":
            raise HTTPException(status_code=302, headers={"Location": "/pending"})
        return user

    def mcp_base_url() -> str:
        return os.environ.get("MCP_PUBLIC_URL", "").rstrip("/") or "http://<HA-IP>:8765"

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
            "request": request, "step": 1, "error": None
        })

    @app.post("/register", response_class=HTMLResponse)
    async def register_step1_post(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        password2: str = Form(...),
        email: str = Form(default=""),
    ):
        error = None
        if len(username) < 3:
            error = "Benutzername muss mindestens 3 Zeichen lang sein."
        elif len(password) < 8:
            error = "Passwort muss mindestens 8 Zeichen lang sein."
        elif password != password2:
            error = "Passwörter stimmen nicht überein."
        else:
            try:
                from db import username_exists
                if username_exists(username):
                    error = "Benutzername bereits vergeben."
            except Exception as e:
                error = f"Datenbankfehler: {e}"

        if error:
            return templates.TemplateResponse("register_step1.html", {
                "request": request, "step": 1, "error": error,
                "username": username, "email": email,
            })

        request.session["reg_username"] = username
        request.session["reg_password"] = password
        request.session["reg_email"] = email
        return RedirectResponse("/register/api", status_code=302)

    @app.get("/register/api", response_class=HTMLResponse)
    async def register_step2_get(request: Request):
        if "reg_username" not in request.session:
            return RedirectResponse("/register", status_code=302)
        return templates.TemplateResponse("register_step2.html", {
            "request": request, "step": 2, "error": None,
        })

    @app.post("/register/api", response_class=HTMLResponse)
    async def register_step2_post(
        request: Request,
        printix_tenant_id: str = Form(...),
        print_client_id: str = Form(default=""),
        print_client_secret: str = Form(default=""),
        card_client_id: str = Form(default=""),
        card_client_secret: str = Form(default=""),
        ws_client_id: str = Form(default=""),
        ws_client_secret: str = Form(default=""),
        shared_client_id: str = Form(default=""),
        shared_client_secret: str = Form(default=""),
        tenant_name: str = Form(default=""),
    ):
        if "reg_username" not in request.session:
            return RedirectResponse("/register", status_code=302)

        if not printix_tenant_id.strip():
            return templates.TemplateResponse("register_step2.html", {
                "request": request, "step": 2,
                "error": "Printix Tenant-ID ist Pflichtfeld.",
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
                "printix_tenant_id": printix_tenant_id,
                "tenant_name": tenant_name,
            })

        request.session["reg_tenant_id"] = printix_tenant_id.strip()
        request.session["reg_tenant_name"] = tenant_name.strip() or printix_tenant_id.strip()
        request.session["reg_print_client_id"] = print_client_id.strip()
        request.session["reg_print_client_secret"] = print_client_secret.strip()
        request.session["reg_card_client_id"] = card_client_id.strip()
        request.session["reg_card_client_secret"] = card_client_secret.strip()
        request.session["reg_ws_client_id"] = ws_client_id.strip()
        request.session["reg_ws_client_secret"] = ws_client_secret.strip()
        request.session["reg_shared_client_id"] = shared_client_id.strip()
        request.session["reg_shared_client_secret"] = shared_client_secret.strip()
        return RedirectResponse("/register/optional", status_code=302)

    @app.get("/register/optional", response_class=HTMLResponse)
    async def register_step3_get(request: Request):
        if "reg_tenant_id" not in request.session:
            return RedirectResponse("/register", status_code=302)
        return templates.TemplateResponse("register_step3.html", {
            "request": request, "step": 3, "error": None,
        })

    @app.post("/register/optional", response_class=HTMLResponse)
    async def register_step3_post(
        request: Request,
        sql_server: str = Form(default=""),
        sql_database: str = Form(default="printix_bi_data_2_1"),
        sql_username: str = Form(default=""),
        sql_password: str = Form(default=""),
        mail_api_key: str = Form(default=""),
        mail_from: str = Form(default=""),
    ):
        if "reg_tenant_id" not in request.session:
            return RedirectResponse("/register", status_code=302)

        request.session["reg_sql_server"] = sql_server.strip()
        request.session["reg_sql_database"] = sql_database.strip()
        request.session["reg_sql_username"] = sql_username.strip()
        request.session["reg_sql_password"] = sql_password.strip()
        request.session["reg_mail_api_key"] = mail_api_key.strip()
        request.session["reg_mail_from"] = mail_from.strip()
        return RedirectResponse("/register/summary", status_code=302)

    @app.get("/register/summary", response_class=HTMLResponse)
    async def register_step4_get(request: Request):
        if "reg_tenant_id" not in request.session:
            return RedirectResponse("/register", status_code=302)

        base = mcp_base_url()
        return templates.TemplateResponse("register_step4.html", {
            "request": request, "step": 4,
            "username": request.session.get("reg_username", ""),
            "email": request.session.get("reg_email", ""),
            "tenant_id": request.session.get("reg_tenant_id", ""),
            "tenant_name": request.session.get("reg_tenant_name", ""),
            "sql_configured": bool(request.session.get("reg_sql_server")),
            "mail_configured": bool(request.session.get("reg_mail_api_key")),
            "base_url": base,
            "error": None,
        })

    @app.post("/register/summary", response_class=HTMLResponse)
    async def register_step4_post(request: Request):
        if "reg_tenant_id" not in request.session:
            return RedirectResponse("/register", status_code=302)

        base = mcp_base_url()

        try:
            from db import create_user, create_tenant, has_users, audit

            is_first = not has_users()

            user = create_user(
                username=request.session["reg_username"],
                password=request.session["reg_password"],
                email=request.session.get("reg_email", ""),
                is_first=is_first,
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
                "username": request.session.get("reg_username", ""),
                "tenant_id": request.session.get("reg_tenant_id", ""),
                "tenant_name": request.session.get("reg_tenant_name", ""),
                "base_url": base, "sql_configured": False, "mail_configured": False,
            })

        return templates.TemplateResponse("register_success.html", {
            "request": request,
            "username": user["username"],
            "is_admin": user.get("is_admin", False),
            "bearer_token": tenant["bearer_token"],
            "oauth_client_id": tenant["oauth_client_id"],
            "oauth_client_secret": tenant["oauth_client_secret"],
            "base_url": base,
            "mcp_url": f"{base}/mcp",
            "sse_url": f"{base}/sse",
            "oauth_authorize_url": f"{base}/oauth/authorize",
            "oauth_token_url": f"{base}/oauth/token",
        })

    # ── Login ──────────────────────────────────────────────────────────────────

    @app.get("/login", response_class=HTMLResponse)
    async def login_get(request: Request):
        if get_session_user(request):
            return RedirectResponse("/", status_code=302)
        return templates.TemplateResponse("login.html", {
            "request": request, "error": None
        })

    @app.post("/login", response_class=HTMLResponse)
    async def login_post(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
    ):
        try:
            from db import authenticate_user, audit
            user = authenticate_user(username, password)
        except Exception as e:
            return templates.TemplateResponse("login.html", {
                "request": request, "error": f"Datenbankfehler: {e}", "username": username,
            })

        if not user:
            return templates.TemplateResponse("login.html", {
                "request": request, "error": "Ungültiger Benutzername oder Passwort.",
                "username": username,
            })

        if user.get("status") == "disabled":
            return templates.TemplateResponse("login.html", {
                "request": request, "error": "Dein Account ist deaktiviert.",
                "username": username,
            })

        request.session["user_id"] = user["id"]
        try:
            audit(user["id"], "login", "Eingeloggt")
        except Exception:
            pass

        if user.get("is_admin"):
            return RedirectResponse("/admin", status_code=302)
        if user.get("status") == "pending":
            return RedirectResponse("/pending", status_code=302)
        return RedirectResponse("/dashboard", status_code=302)

    @app.get("/logout", response_class=RedirectResponse)
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/login", status_code=302)

    # ── User-Seiten ───────────────────────────────────────────────────────────

    @app.get("/pending", response_class=HTMLResponse)
    async def pending(request: Request):
        user = get_session_user(request)
        return templates.TemplateResponse("pending.html", {
            "request": request, "user": user
        })

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request):
        user = get_session_user(request)
        if not user:
            return RedirectResponse("/login", status_code=302)
        if user.get("status") == "pending":
            return RedirectResponse("/pending", status_code=302)

        base = mcp_base_url()
        tenant = None
        try:
            from db import get_tenant_by_user_id
            tenant = get_tenant_by_user_id(user["id"])
        except Exception:
            pass

        return templates.TemplateResponse("dashboard.html", {
            "request": request, "user": user, "tenant": tenant,
            "base_url": base,
            "mcp_url": f"{base}/mcp",
            "sse_url": f"{base}/sse",
        })

    # ── Admin ──────────────────────────────────────────────────────────────────

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_dashboard(request: Request):
        user = get_session_user(request)
        if not user or not user.get("is_admin"):
            return RedirectResponse("/login", status_code=302)
        try:
            from db import get_all_users, count_tenants
            users = get_all_users()
            tenant_count = count_tenants()
        except Exception:
            users = []
            tenant_count = 0
        return templates.TemplateResponse("admin_dashboard.html", {
            "request": request, "user": user,
            "users": users, "tenant_count": tenant_count,
            "base_url": mcp_base_url(),
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
            "request": request, "user": user, "users": users
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
            "request": request, "user": user, "entries": entries
        })

    return app
