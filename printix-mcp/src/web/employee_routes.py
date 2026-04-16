"""
Employee Routes — Self-Service-Portal für Mitarbeiter (v1.0.0)
===============================================================
Registriert alle /my-Routen in der FastAPI-App.

Aufruf aus app.py:
    from web.employee_routes import register_employee_routes
    register_employee_routes(app, templates, t_ctx, require_login)

Routen (Mitarbeiter-Self-Service):
  GET  /my                           → Mitarbeiter-Dashboard
  GET  /my/jobs                      → Eigene Druckjobs
  POST /my/jobs/{id}/delete          → Druckjob löschen
  GET  /my/delegation                → Delegation verwalten
  POST /my/delegation/add            → Delegate vorschlagen
  POST /my/delegation/{id}/remove    → Delegation entfernen
  GET  /my/printer-setup             → Print-Token + Einrichtungsanleitung
  POST /my/printer-setup/generate    → Print-Token generieren
  POST /my/printer-setup/revoke      → Print-Token widerrufen
  GET  /my/reports                   → Reports Light (3 Basis-Reports)

Routen (Admin/User — Mitarbeiter-Verwaltung):
  GET  /employees                    → Mitarbeiterliste
  GET  /employees/new                → Mitarbeiter anlegen
  POST /employees/new                → Mitarbeiter speichern
  GET  /employees/{id}               → Mitarbeiter-Detail
  POST /employees/{id}/delete        → Mitarbeiter löschen
"""

import logging
import secrets
from typing import Callable, Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger("printix.employee")

# i18n-Keys beim Import patchen
try:
    from cloudprint.i18n_employee import patch_translations
    patch_translations()
except Exception as _e:
    logger.warning("Employee i18n patch fehlgeschlagen: %s", _e)


def register_employee_routes(
    app: FastAPI,
    templates: Jinja2Templates,
    t_ctx: Callable,
    require_login: Callable,
) -> None:
    """Registriert alle Mitarbeiter- und Employee-Self-Service-Routen."""

    # ── Helpers ────────────────────────────────────────────────────────────

    def _require_employee(request: Request) -> Optional[dict]:
        """Prüft ob der User ein Employee ist und gibt ihn zurück."""
        user = require_login(request)
        if not user:
            return None
        # Employees und normale User/Admins dürfen die /my-Routen nutzen
        return user

    def _require_manager(request: Request) -> Optional[dict]:
        """Prüft ob der User Admin oder normaler User (kein Employee) ist."""
        user = require_login(request)
        if not user:
            return None
        role = user.get("role_type", "user")
        if role == "employee":
            return None
        return user

    def _get_parent_id(user: dict) -> str:
        """Ermittelt den Parent-User-ID (sich selbst für Admin/User)."""
        from cloudprint.db_extensions import get_parent_user_id
        return get_parent_user_id(user["id"]) or user["id"]

    # ══════════════════════════════════════════════════════════════════════
    # MITARBEITER SELF-SERVICE (/my/*)
    # ══════════════════════════════════════════════════════════════════════

    @app.get("/my", response_class=HTMLResponse)
    async def my_dashboard(request: Request):
        user = _require_employee(request)
        if not user:
            return RedirectResponse("/login", status_code=302)

        from cloudprint.db_extensions import (
            get_delegations_for_owner, get_delegations_for_delegate,
            get_tenant_for_user,
        )
        tenant = get_tenant_for_user(user["id"])
        delegations_out = get_delegations_for_owner(user["id"])
        delegations_in = get_delegations_for_delegate(user["id"])

        return templates.TemplateResponse("employee/my_dashboard.html", {
            "request": request, "user": user, "tenant": tenant,
            "delegations_out": delegations_out,
            "delegations_in": delegations_in,
            **t_ctx(request),
        })

    # ── Druckjobs ─────────────────────────────────────────────────────────

    @app.get("/my/jobs", response_class=HTMLResponse)
    async def my_jobs(request: Request):
        user = _require_employee(request)
        if not user:
            return RedirectResponse("/login", status_code=302)

        from cloudprint.db_extensions import get_tenant_for_user
        tenant = get_tenant_for_user(user["id"])
        jobs = []

        if tenant and tenant.get("printix_tenant_id"):
            try:
                from db import get_tenant_full_by_user_id
                from cloudprint.db_extensions import get_parent_user_id
                parent_id = get_parent_user_id(user["id"])
                full_tenant = get_tenant_full_by_user_id(parent_id)
                if full_tenant:
                    from printix_client import PrintixClient
                    client = PrintixClient(
                        tenant_id=full_tenant["printix_tenant_id"],
                        client_id=full_tenant.get("print_client_id") or full_tenant.get("shared_client_id", ""),
                        client_secret=full_tenant.get("print_client_secret") or full_tenant.get("shared_client_secret", ""),
                    )
                    all_jobs = client.list_jobs(limit=100)
                    # Nur Jobs des eingeloggten Users filtern
                    user_email = user.get("email", "").lower()
                    jobs = [
                        j for j in all_jobs
                        if j.get("ownerEmail", "").lower() == user_email
                        or j.get("ownerName", "").lower() == user.get("username", "").lower()
                    ]
            except Exception as e:
                logger.warning("Jobs-Abruf fehlgeschlagen: %s", e)

        return templates.TemplateResponse("employee/my_jobs.html", {
            "request": request, "user": user, "jobs": jobs,
            **t_ctx(request),
        })

    @app.post("/my/jobs/{job_id}/delete")
    async def my_job_delete(request: Request, job_id: str):
        user = _require_employee(request)
        if not user:
            return RedirectResponse("/login", status_code=302)

        try:
            from db import get_tenant_full_by_user_id
            from cloudprint.db_extensions import get_parent_user_id
            parent_id = get_parent_user_id(user["id"])
            full_tenant = get_tenant_full_by_user_id(parent_id)
            if full_tenant:
                from printix_client import PrintixClient
                client = PrintixClient(
                    tenant_id=full_tenant["printix_tenant_id"],
                    client_id=full_tenant.get("print_client_id") or full_tenant.get("shared_client_id", ""),
                    client_secret=full_tenant.get("print_client_secret") or full_tenant.get("shared_client_secret", ""),
                )
                client.delete_job(job_id)
        except Exception as e:
            logger.warning("Job-Löschung fehlgeschlagen: %s", e)

        return RedirectResponse("/my/jobs?flash=job_deleted", status_code=302)

    # ── Delegation ────────────────────────────────────────────────────────

    @app.get("/my/delegation", response_class=HTMLResponse)
    async def my_delegation(request: Request):
        user = _require_employee(request)
        if not user:
            return RedirectResponse("/login", status_code=302)

        from cloudprint.db_extensions import (
            get_delegations_for_owner, get_delegations_for_delegate,
            get_available_delegates, get_parent_user_id,
        )
        parent_id = get_parent_user_id(user["id"])
        delegations_out = get_delegations_for_owner(user["id"])
        delegations_in = get_delegations_for_delegate(user["id"])
        available = get_available_delegates(parent_id, exclude_user_id=user["id"])

        # Bereits delegierte User-IDs ausfiltern
        existing_ids = {d["delegate_user_id"] for d in delegations_out}
        available = [a for a in available if a["id"] not in existing_ids]

        flash = request.query_params.get("flash", "")
        return templates.TemplateResponse("employee/my_delegation.html", {
            "request": request, "user": user,
            "delegations_out": delegations_out,
            "delegations_in": delegations_in,
            "available_delegates": available,
            "flash": flash,
            **t_ctx(request),
        })

    @app.post("/my/delegation/add")
    async def my_delegation_add(
        request: Request,
        delegate_user_id: str = Form(...),
    ):
        user = _require_employee(request)
        if not user:
            return RedirectResponse("/login", status_code=302)

        from cloudprint.db_extensions import create_delegation
        role = user.get("role_type", "user")
        # Employees schlagen vor (pending), Admins/Users aktivieren direkt
        status = "active" if role != "employee" else "pending"
        create_delegation(
            owner_user_id=user["id"],
            delegate_user_id=delegate_user_id,
            created_by=user["id"],
            status=status,
        )
        flash = "delegation_added" if status == "active" else "delegation_pending"
        return RedirectResponse(f"/my/delegation?flash={flash}", status_code=302)

    @app.post("/my/delegation/{delegation_id}/remove")
    async def my_delegation_remove(request: Request, delegation_id: int):
        user = _require_employee(request)
        if not user:
            return RedirectResponse("/login", status_code=302)

        from cloudprint.db_extensions import get_delegation_by_id, delete_delegation
        deleg = get_delegation_by_id(delegation_id)
        if deleg and (deleg["owner_user_id"] == user["id"] or deleg["delegate_user_id"] == user["id"]):
            delete_delegation(delegation_id)

        return RedirectResponse("/my/delegation?flash=delegation_removed", status_code=302)

    # ── Printer Setup ─────────────────────────────────────────────────────

    @app.get("/my/printer-setup", response_class=HTMLResponse)
    async def my_printer_setup(request: Request):
        user = _require_employee(request)
        if not user:
            return RedirectResponse("/login", status_code=302)

        from cloudprint.db_extensions import get_tenant_for_user
        tenant = get_tenant_for_user(user["id"])
        has_token = bool(tenant and tenant.get("print_token_hash"))
        flash = request.query_params.get("flash", "")

        return templates.TemplateResponse("employee/my_printer_setup.html", {
            "request": request, "user": user,
            "has_token": has_token,
            "new_token": request.session.pop("new_print_token", None),
            "flash": flash,
            **t_ctx(request),
        })

    @app.post("/my/printer-setup/generate")
    async def my_printer_setup_generate(request: Request):
        user = _require_employee(request)
        if not user:
            return RedirectResponse("/login", status_code=302)

        from cloudprint.db_extensions import generate_print_token, get_parent_user_id
        parent_id = get_parent_user_id(user["id"])
        token = generate_print_token(parent_id)
        request.session["new_print_token"] = token
        return RedirectResponse("/my/printer-setup?flash=token_generated", status_code=302)

    @app.post("/my/printer-setup/revoke")
    async def my_printer_setup_revoke(request: Request):
        user = _require_employee(request)
        if not user:
            return RedirectResponse("/login", status_code=302)

        from cloudprint.db_extensions import revoke_print_token, get_parent_user_id
        parent_id = get_parent_user_id(user["id"])
        revoke_print_token(parent_id)
        return RedirectResponse("/my/printer-setup?flash=token_revoked", status_code=302)

    # ── Reports Light ─────────────────────────────────────────────────────

    @app.get("/my/reports", response_class=HTMLResponse)
    async def my_reports(request: Request):
        user = _require_employee(request)
        if not user:
            return RedirectResponse("/login", status_code=302)

        return templates.TemplateResponse("employee/my_reports.html", {
            "request": request, "user": user,
            **t_ctx(request),
        })

    # ══════════════════════════════════════════════════════════════════════
    # MITARBEITER-VERWALTUNG (/employees/*) — nur für Admin/User
    # ══════════════════════════════════════════════════════════════════════

    @app.get("/employees", response_class=HTMLResponse)
    async def employees_list(request: Request):
        user = _require_manager(request)
        if not user:
            return RedirectResponse("/login", status_code=302)

        from cloudprint.db_extensions import get_employees
        employees = get_employees(user["id"])
        flash = request.query_params.get("flash", "")

        return templates.TemplateResponse("employee/employees_list.html", {
            "request": request, "user": user,
            "employees": employees, "flash": flash,
            **t_ctx(request),
        })

    @app.get("/employees/new", response_class=HTMLResponse)
    async def employees_new(request: Request):
        user = _require_manager(request)
        if not user:
            return RedirectResponse("/login", status_code=302)

        return templates.TemplateResponse("employee/employees_new.html", {
            "request": request, "user": user, "error": "",
            **t_ctx(request),
        })

    @app.post("/employees/new")
    async def employees_create(
        request: Request,
        username: str = Form(...),
        email: str = Form(""),
        full_name: str = Form(""),
        password: str = Form(""),
    ):
        user = _require_manager(request)
        if not user:
            return RedirectResponse("/login", status_code=302)

        from db import username_exists
        if username_exists(username):
            return templates.TemplateResponse("employee/employees_new.html", {
                "request": request, "user": user,
                "error": "username_exists",
                **t_ctx(request),
            })

        if not password:
            password = secrets.token_urlsafe(12)

        from cloudprint.db_extensions import create_employee
        create_employee(
            parent_user_id=user["id"],
            username=username,
            password=password,
            email=email,
            full_name=full_name,
        )
        return RedirectResponse("/employees?flash=employee_created", status_code=302)

    @app.get("/employees/{employee_id}", response_class=HTMLResponse)
    async def employees_detail(request: Request, employee_id: str):
        user = _require_manager(request)
        if not user:
            return RedirectResponse("/login", status_code=302)

        from cloudprint.db_extensions import (
            get_employee_by_id, get_delegations_for_owner,
            get_delegations_for_delegate,
        )
        employee = get_employee_by_id(employee_id, user["id"])
        if not employee:
            return RedirectResponse("/employees", status_code=302)

        delegations_out = get_delegations_for_owner(employee_id)
        delegations_in = get_delegations_for_delegate(employee_id)

        return templates.TemplateResponse("employee/employees_detail.html", {
            "request": request, "user": user,
            "employee": employee,
            "delegations_out": delegations_out,
            "delegations_in": delegations_in,
            **t_ctx(request),
        })

    @app.post("/employees/{employee_id}/delete")
    async def employees_delete(request: Request, employee_id: str):
        user = _require_manager(request)
        if not user:
            return RedirectResponse("/login", status_code=302)

        from cloudprint.db_extensions import delete_employee
        delete_employee(employee_id, user["id"])
        return RedirectResponse("/employees?flash=employee_deleted", status_code=302)

    # ── Admin: Delegationen genehmigen ────────────────────────────────────

    @app.post("/employees/delegation/{delegation_id}/approve")
    async def delegation_approve(request: Request, delegation_id: int):
        user = _require_manager(request)
        if not user:
            return RedirectResponse("/login", status_code=302)

        from cloudprint.db_extensions import update_delegation_status
        update_delegation_status(delegation_id, "active")
        return RedirectResponse(request.headers.get("referer", "/employees"), status_code=302)

    @app.post("/employees/delegation/{delegation_id}/reject")
    async def delegation_reject(request: Request, delegation_id: int):
        user = _require_manager(request)
        if not user:
            return RedirectResponse("/login", status_code=302)

        from cloudprint.db_extensions import delete_delegation
        delete_delegation(delegation_id)
        return RedirectResponse(request.headers.get("referer", "/employees"), status_code=302)
