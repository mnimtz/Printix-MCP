"""
Reports Routes — Web-UI für Report-Template-Verwaltung (v3.0.0)
===============================================================
Registriert alle /reports-Routen in der FastAPI-App.

Aufruf aus app.py:
    from web.reports_routes import register_reports_routes
    register_reports_routes(app, templates, t_ctx, require_login)

Routen:
  GET  /reports                   → Template-Liste + Preset-Bibliothek
  GET  /reports/new               → Neues Template (leer oder aus Preset)
  POST /reports/new               → Template speichern (neu)
  GET  /reports/{id}/edit         → Template bearbeiten
  POST /reports/{id}/edit         → Template speichern (Update)
  POST /reports/{id}/run          → Report sofort ausführen
  GET  /reports/{id}/preview      → Report-Vorschau (HTML, kein Mail-Versand)
  POST /reports/{id}/delete       → Template löschen
"""

import json
import logging
from typing import Any, Callable, Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger("printix.reports")

# Query-Typen mit Labels
QUERY_TYPE_LABELS = {
    "print_stats":  "Druckvolumen-Statistik",
    "cost_report":  "Kostenanalyse",
    "top_users":    "Top-Benutzer",
    "top_printers": "Top-Drucker",
    "anomalies":    "Anomalie-Erkennung",
    "trend":        "Drucktrend",
}

# Frequenz-Labels
FREQ_LABELS = {
    "daily":   "Täglich",
    "weekly":  "Wöchentlich",
    "monthly": "Monatlich",
}

DOW_LABELS = {
    "0": "Montag", "1": "Dienstag", "2": "Mittwoch", "3": "Donnerstag",
    "4": "Freitag", "5": "Samstag", "6": "Sonntag",
}


def register_reports_routes(
    app: FastAPI,
    templates: Jinja2Templates,
    t_ctx: Callable,
    require_login: Callable,
) -> None:
    """Registriert alle /reports-Routen in der übergebenen FastAPI-App."""

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _redirect_login() -> RedirectResponse:
        return RedirectResponse("/login", status_code=302)

    def _flash(request: Request, msg: str, kind: str = "success") -> None:
        request.session["flash_msg"]  = msg
        request.session["flash_kind"] = kind

    def _pop_flash(request: Request) -> tuple[str, str]:
        msg  = request.session.pop("flash_msg",  "")
        kind = request.session.pop("flash_kind", "success")
        return msg, kind

    def _reporting_available(tenant: dict = None) -> bool:
        try:
            from reporting.sql_client import is_configured, set_config_from_tenant
            if tenant:
                set_config_from_tenant(tenant)
            return is_configured()
        except Exception:
            return False

    def _mail_configured(tenant: dict) -> bool:
        return bool(tenant.get("mail_api_key") and tenant.get("mail_from"))

    def _get_tenant(user: dict) -> dict:
        try:
            from db import get_tenant_full_by_user_id
            t = get_tenant_full_by_user_id(user["id"])
            return t or {}
        except Exception:
            return {}

    def _schedule_label(schedule: Optional[dict]) -> str:
        if not schedule:
            return "—"
        freq = schedule.get("frequency", "monthly")
        time = schedule.get("time", "08:00")
        day  = schedule.get("day", 1)
        fl = FREQ_LABELS.get(freq, freq)
        if freq == "weekly":
            return f"{fl} {DOW_LABELS.get(str(day), str(day))} {time}"
        elif freq == "monthly":
            return f"{fl}, {day}. {time} Uhr"
        else:
            return f"{fl} {time} Uhr"

    # ── GET /reports — Übersicht ──────────────────────────────────────────────

    @app.get("/reports", response_class=HTMLResponse)
    async def reports_list_get(request: Request):
        user = require_login(request)
        if not user:
            return _redirect_login()
        tc = t_ctx(request)
        flash_msg, flash_kind = _pop_flash(request)
        tenant = _get_tenant(user)

        from reporting.template_store import list_templates_by_user
        from reporting.preset_templates import list_presets, get_available_tags
        from reporting.scheduler import list_scheduled_jobs

        user_templates = list_templates_by_user(user["id"])
        presets = list_presets()
        tags = get_available_tags()

        # Scheduled job IDs für is_scheduled-Flag
        scheduled_ids = {j["job_id"] for j in list_scheduled_jobs()}
        for t in user_templates:
            t["is_scheduled"]   = t.get("report_id", "") in scheduled_ids
            t["schedule_label"] = _schedule_label(t.get("schedule"))

        # Presets nach Tags gruppieren
        presets_by_tag: dict[str, list] = {}
        for tag in tags:
            presets_by_tag[tag] = [p for p in presets if p.get("tag") == tag]

        return templates.TemplateResponse("reports_list.html", {
            "request":          request,
            "user":             user,
            "tenant":           tenant,
            "templates_list":   user_templates,
            "presets_by_tag":   presets_by_tag,
            "tags":             tags,
            "reporting_ok":     _reporting_available(tenant),
            "mail_ok":          _mail_configured(tenant),
            "flash_msg":        flash_msg,
            "flash_kind":       flash_kind,
            "query_type_labels": QUERY_TYPE_LABELS,
            **tc,
        })

    # ── GET /reports/new — Formular (leer oder aus Preset) ───────────────────

    @app.get("/reports/new", response_class=HTMLResponse)
    async def reports_new_get(request: Request):
        user = require_login(request)
        if not user:
            return _redirect_login()
        tc = t_ctx(request)
        tenant = _get_tenant(user)

        preset_key = request.query_params.get("preset", "")
        prefill: dict[str, Any] = {}

        if preset_key:
            from reporting.preset_templates import preset_to_template_defaults
            prefill = preset_to_template_defaults(preset_key, user["id"]) or {}

        return templates.TemplateResponse("reports_form.html", {
            "request":    request,
            "user":       user,
            "tenant":     tenant,
            "report":     prefill,
            "is_edit":    False,
            "preset_key": preset_key,
            "error":      None,
            "query_type_labels": QUERY_TYPE_LABELS,
            **tc,
        })

    # ── POST /reports/new — Template speichern ────────────────────────────────

    @app.post("/reports/new", response_class=HTMLResponse)
    async def reports_new_post(
        request:       Request,
        name:          str  = Form(...),
        query_type:    str  = Form(...),
        mail_subject:  str  = Form(default=""),
        start_date:    str  = Form(default="last_month_start"),
        end_date:      str  = Form(default="last_month_end"),
        group_by:      str  = Form(default="day"),
        limit:         str  = Form(default="10"),
        cost_per_sheet: str = Form(default="0.01"),
        cost_per_mono:  str = Form(default="0.02"),
        cost_per_color: str = Form(default="0.08"),
        recipients:    str  = Form(default=""),
        company_name:  str  = Form(default=""),
        logo_url:      str  = Form(default=""),
        primary_color: str  = Form(default="#0078D4"),
        footer_text:   str  = Form(default=""),
        fmt_html:      str  = Form(default=""),
        fmt_csv:       str  = Form(default=""),
        fmt_json:      str  = Form(default=""),
        fmt_pdf:       str  = Form(default=""),
        fmt_xlsx:      str  = Form(default=""),
        schedule_enabled: str = Form(default=""),
        freq:          str  = Form(default="monthly"),
        sched_day:     str  = Form(default="1"),
        sched_time:    str  = Form(default="08:00"),
    ):
        user = require_login(request)
        if not user:
            return _redirect_login()
        tc = t_ctx(request)

        # Ausgabeformate aus Checkboxen
        output_formats = []
        if fmt_html:  output_formats.append("html")
        if fmt_csv:   output_formats.append("csv")
        if fmt_json:  output_formats.append("json")
        if fmt_pdf:   output_formats.append("pdf")
        if fmt_xlsx:  output_formats.append("xlsx")
        if not output_formats:
            output_formats = ["html"]

        # Query-Parameter je nach Typ
        qp: dict[str, Any] = {"start_date": start_date, "end_date": end_date}
        if query_type in ("print_stats", "trend"):
            qp["group_by"] = group_by
        elif query_type == "cost_report":
            qp["group_by"]        = group_by
            qp["cost_per_sheet"]  = float(cost_per_sheet or 0.01)
            qp["cost_per_mono"]   = float(cost_per_mono  or 0.02)
            qp["cost_per_color"]  = float(cost_per_color or 0.08)
        elif query_type in ("top_users", "top_printers"):
            qp["limit"] = int(limit or 10)

        # Schedule
        schedule = None
        if schedule_enabled:
            schedule = {
                "frequency": freq,
                "day":       int(sched_day or 1),
                "time":      sched_time or "08:00",
            }

        # Empfänger-Liste bereinigen
        recip = [r.strip() for r in recipients.replace(";", ",").split(",") if r.strip()]

        from reporting.template_store import save_template
        from reporting.scheduler import schedule_report, unschedule_report

        try:
            template = save_template(
                name=name,
                query_type=query_type,
                query_params=qp,
                recipients=recip,
                mail_subject=mail_subject or f"Printix Report: {name}",
                output_formats=output_formats,
                layout={
                    "primary_color": primary_color or "#0078D4",
                    "company_name":  company_name,
                    "footer_text":   footer_text,
                    "logo_url":      logo_url.strip() if logo_url else "",
                    "logo_base64":   "",
                },
                schedule=schedule,
                owner_user_id=user["id"],
            )
            if schedule:
                schedule_report(template["report_id"], schedule)
            else:
                unschedule_report(template["report_id"])

            _flash(request, tc["_"]("reports_saved"))
            return RedirectResponse("/reports", status_code=302)

        except Exception as e:
            logger.error("Fehler beim Speichern des Templates: %s", e)
            return templates.TemplateResponse("reports_form.html", {
                "request":    request,
                "user":       user,
                "tenant":     _get_tenant(user),
                "report":     {},
                "is_edit":    False,
                "preset_key": "",
                "error":      str(e),
                "query_type_labels": QUERY_TYPE_LABELS,
                **tc,
            })

    # ── GET /reports/{id}/edit — Bearbeitungsformular ─────────────────────────

    @app.get("/reports/{report_id}/edit", response_class=HTMLResponse)
    async def reports_edit_get(report_id: str, request: Request):
        user = require_login(request)
        if not user:
            return _redirect_login()
        tc = t_ctx(request)
        tenant = _get_tenant(user)

        from reporting.template_store import get_template
        report = get_template(report_id)
        if not report or report.get("owner_user_id", "") != user["id"]:
            _flash(request, "Template nicht gefunden.", "error")
            return RedirectResponse("/reports", status_code=302)

        return templates.TemplateResponse("reports_form.html", {
            "request":    request,
            "user":       user,
            "tenant":     tenant,
            "report":     report,
            "is_edit":    True,
            "preset_key": "",
            "error":      None,
            "query_type_labels": QUERY_TYPE_LABELS,
            **tc,
        })

    # ── POST /reports/{id}/edit — Update speichern ────────────────────────────

    @app.post("/reports/{report_id}/edit", response_class=HTMLResponse)
    async def reports_edit_post(
        report_id:     str,
        request:       Request,
        name:          str  = Form(...),
        query_type:    str  = Form(...),
        mail_subject:  str  = Form(default=""),
        start_date:    str  = Form(default="last_month_start"),
        end_date:      str  = Form(default="last_month_end"),
        group_by:      str  = Form(default="day"),
        limit:         str  = Form(default="10"),
        cost_per_sheet: str = Form(default="0.01"),
        cost_per_mono:  str = Form(default="0.02"),
        cost_per_color: str = Form(default="0.08"),
        recipients:    str  = Form(default=""),
        company_name:  str  = Form(default=""),
        logo_url:      str  = Form(default=""),
        primary_color: str  = Form(default="#0078D4"),
        footer_text:   str  = Form(default=""),
        fmt_html:      str  = Form(default=""),
        fmt_csv:       str  = Form(default=""),
        fmt_json:      str  = Form(default=""),
        fmt_pdf:       str  = Form(default=""),
        fmt_xlsx:      str  = Form(default=""),
        schedule_enabled: str = Form(default=""),
        freq:          str  = Form(default="monthly"),
        sched_day:     str  = Form(default="1"),
        sched_time:    str  = Form(default="08:00"),
    ):
        user = require_login(request)
        if not user:
            return _redirect_login()
        tc = t_ctx(request)

        from reporting.template_store import get_template, save_template
        from reporting.scheduler import schedule_report, unschedule_report

        existing = get_template(report_id)
        if not existing or existing.get("owner_user_id", "") != user["id"]:
            _flash(request, "Template nicht gefunden.", "error")
            return RedirectResponse("/reports", status_code=302)

        output_formats = []
        if fmt_html:  output_formats.append("html")
        if fmt_csv:   output_formats.append("csv")
        if fmt_json:  output_formats.append("json")
        if fmt_pdf:   output_formats.append("pdf")
        if fmt_xlsx:  output_formats.append("xlsx")
        if not output_formats:
            output_formats = ["html"]

        qp: dict[str, Any] = {"start_date": start_date, "end_date": end_date}
        if query_type in ("print_stats", "trend"):
            qp["group_by"] = group_by
        elif query_type == "cost_report":
            qp["group_by"]        = group_by
            qp["cost_per_sheet"]  = float(cost_per_sheet or 0.01)
            qp["cost_per_mono"]   = float(cost_per_mono  or 0.02)
            qp["cost_per_color"]  = float(cost_per_color or 0.08)
        elif query_type in ("top_users", "top_printers"):
            qp["limit"] = int(limit or 10)

        schedule = None
        if schedule_enabled:
            schedule = {
                "frequency": freq,
                "day":       int(sched_day or 1),
                "time":      sched_time or "08:00",
            }

        recip = [r.strip() for r in recipients.replace(";", ",").split(",") if r.strip()]

        # Layout aus bestehendem Template übernehmen, nur geänderte Felder überschreiben
        layout = dict(existing.get("layout", {}))
        layout.update({
            "primary_color": primary_color or "#0078D4",
            "company_name":  company_name,
            "footer_text":   footer_text,
            "logo_url":      logo_url.strip() if logo_url else "",
        })

        try:
            template = save_template(
                name=name,
                query_type=query_type,
                query_params=qp,
                recipients=recip,
                mail_subject=mail_subject or f"Printix Report: {name}",
                output_formats=output_formats,
                layout=layout,
                schedule=schedule,
                report_id=report_id,
                owner_user_id=user["id"],
            )
            if schedule:
                schedule_report(template["report_id"], schedule)
            else:
                unschedule_report(template["report_id"])

            _flash(request, tc["_"]("reports_saved"))
            return RedirectResponse("/reports", status_code=302)

        except Exception as e:
            logger.error("Fehler beim Update des Templates %s: %s", report_id, e)
            _flash(request, str(e), "error")
            return RedirectResponse(f"/reports/{report_id}/edit", status_code=302)

    # ── POST /reports/{id}/run — Sofort ausführen ─────────────────────────────

    @app.post("/reports/{report_id}/run", response_class=RedirectResponse)
    async def reports_run_post(report_id: str, request: Request):
        user = require_login(request)
        if not user:
            return _redirect_login()
        tc = t_ctx(request)

        from reporting.template_store import get_template
        report = get_template(report_id)
        if not report or report.get("owner_user_id", "") != user["id"]:
            _flash(request, "Template nicht gefunden.", "error")
            return RedirectResponse("/reports", status_code=302)

        tenant = _get_tenant(user)
        try:
            from reporting.sql_client import set_config_from_tenant
            set_config_from_tenant(tenant)
            from reporting.scheduler import run_report_now
            result = run_report_now(
                report_id,
                mail_api_key=tenant.get("mail_api_key", "") or "",
                mail_from=tenant.get("mail_from", "") or "",
            )
            if result.get("mail_sent"):
                recip = ", ".join(result.get("recipients", []))
                _flash(request, f"✓ Report versendet an: {recip}")
            elif result.get("mail_error"):
                _flash(request, f"Report generiert, aber Mail-Fehler: {result['mail_error']}", "warning")
            else:
                _flash(request, "Report generiert (keine Empfänger konfiguriert).", "info")
        except Exception as e:
            logger.error("Fehler bei run_report_now(%s): %s", report_id, e)
            _flash(request, f"Fehler: {e}", "error")

        return RedirectResponse("/reports", status_code=302)

    # ── GET /reports/{id}/preview — Report-Vorschau (HTML, kein Mail-Versand) ──

    @app.get("/reports/{report_id}/preview", response_class=HTMLResponse)
    async def reports_preview_get(report_id: str, request: Request):
        """
        Zeigt den generierten HTML-Report direkt im Browser ohne E-Mail-Versand.
        Nützlich zur Kontrolle vor dem ersten geplanten Versand.
        """
        user = require_login(request)
        if not user:
            return _redirect_login()

        from reporting.template_store import get_template
        report = get_template(report_id)
        if not report or report.get("owner_user_id", "") != user["id"]:
            return HTMLResponse("<h2>Report nicht gefunden.</h2>", status_code=404)

        tenant = _get_tenant(user)
        try:
            from reporting.sql_client import set_config_from_tenant, is_configured
            set_config_from_tenant(tenant)
        except Exception as e:
            return HTMLResponse(
                f"<h2>SQL nicht konfiguriert</h2><p>{e}</p>"
                "<p><a href='/reports'>← Zurück</a></p>",
                status_code=503,
            )

        if not _reporting_available(tenant):
            return HTMLResponse(
                "<h2>Kein SQL-Server konfiguriert</h2>"
                "<p>Bitte SQL-Credentials in den <a href='/settings'>Einstellungen</a> eintragen.</p>",
                status_code=503,
            )

        try:
            import sys as _sys, os as _os
            src_dir = _os.path.dirname(_os.path.dirname(__file__))
            if src_dir not in _sys.path:
                _sys.path.insert(0, src_dir)
            from reporting.query_tools import run_query
            from reporting.report_engine import generate_report
            from reporting.sql_client import get_tenant_id

            qp = report.get("query_params", {})
            data = await __import__("asyncio").to_thread(
                run_query,
                query_type=report["query_type"],
                tenant_id=get_tenant_id(),
                **qp,
            )
            layout = report.get("layout", {})
            html = generate_report(
                query_type=report["query_type"],
                data=data,
                period=f'{qp.get("start_date","?")} – {qp.get("end_date","?")}',
                layout=layout,
                output_formats=["html"],
            ).get("html", "<p>Keine Daten.</p>")

            # Vorschau-Banner oben anhängen
            banner = (
                f'<div style="background:#1a73e8;color:#fff;padding:10px 20px;font-family:sans-serif;'
                f'font-size:13px;display:flex;justify-content:space-between;align-items:center;">'
                f'<span>👁 <strong>Vorschau</strong> — {report.get("name","Report")} '
                f'(kein Mail-Versand)</span>'
                f'<a href="/reports" style="color:#fff;text-decoration:underline">← Zurück zu Reports</a>'
                f'</div>'
            )
            return HTMLResponse(banner + html)

        except Exception as e:
            logger.error("Preview-Fehler für Report %s: %s", report_id, e, exc_info=True)
            return HTMLResponse(
                f"<h2>Vorschau fehlgeschlagen</h2><pre>{e}</pre>"
                "<p><a href='/reports'>← Zurück</a></p>",
                status_code=500,
            )

    # ── POST /reports/{id}/delete — Template löschen ──────────────────────────

    @app.post("/reports/{report_id}/delete", response_class=RedirectResponse)
    async def reports_delete_post(report_id: str, request: Request):
        user = require_login(request)
        if not user:
            return _redirect_login()
        tc = t_ctx(request)

        from reporting.template_store import get_template, delete_template
        from reporting.scheduler import unschedule_report

        report = get_template(report_id)
        if not report or report.get("owner_user_id", "") != user["id"]:
            _flash(request, "Template nicht gefunden.", "error")
            return RedirectResponse("/reports", status_code=302)

        try:
            unschedule_report(report_id)
            delete_template(report_id)
            _flash(request, tc["_"]("reports_deleted"))
        except Exception as e:
            logger.error("Fehler beim Löschen von Template %s: %s", report_id, e)
            _flash(request, f"Fehler: {e}", "error")

        return RedirectResponse("/reports", status_code=302)

    logger.info("Reports-Routen registriert (/reports, /reports/new, /reports/{id}/edit|run|preview|delete)")
