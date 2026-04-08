"""
Scheduler — Zeitgesteuerte Report-Ausführung
=============================================
Läuft als Background-Thread im MCP-Server-Prozess.
Liest beim Start alle Templates mit aktivem Schedule und plant sie ein.
Wenn Templates gespeichert/gelöscht werden, wird der Scheduler aktualisiert.

Schedule-Schema im Template:
  frequency: monthly | weekly | daily
  day:        1-28 (monatlich) | 0=Mo…6=So (wöchentlich) | ignoriert (täglich)
  time:       "HH:MM" — Uhrzeit der Ausführung

Voraussetzungen: APScheduler >= 3.10
"""

import logging
import os
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    logger.warning("apscheduler nicht installiert — automatische Scheduling-Funktion nicht verfügbar")


# Singleton-Scheduler-Instanz
_scheduler: Optional[Any] = None


def _get_scheduler() -> Any:
    global _scheduler
    if _scheduler is None:
        if not APSCHEDULER_AVAILABLE:
            raise RuntimeError(
                "apscheduler nicht installiert. "
                "Bitte 'pip install apscheduler' im Container ausführen."
            )
        _scheduler = BackgroundScheduler(
            job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 3600},
            timezone="UTC",
        )
        _scheduler.start()
        logger.info("APScheduler gestartet")
    return _scheduler


def _build_cron_trigger(schedule: dict) -> Any:
    """
    Baut einen CronTrigger aus dem Template-Schedule-Dict.

    frequency: monthly | weekly | daily
    day:       1-28 (monatlich) oder 0=Mo…6=So (wöchentlich)
    time:      "HH:MM"
    """
    freq = schedule.get("frequency", "monthly")
    time_str = schedule.get("time", "08:00")
    try:
        hour, minute = [int(x) for x in time_str.split(":")]
    except (ValueError, AttributeError):
        hour, minute = 8, 0

    if freq == "daily":
        return CronTrigger(hour=hour, minute=minute)
    elif freq == "weekly":
        day_of_week = int(schedule.get("day", 0))  # 0=Mo, 6=So
        dow_map = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
        return CronTrigger(day_of_week=dow_map.get(day_of_week, "mon"), hour=hour, minute=minute)
    else:  # monthly
        day = max(1, min(28, int(schedule.get("day", 1))))
        return CronTrigger(day=day, hour=hour, minute=minute)


def _run_report_job(report_id: str) -> None:
    """
    Führt einen geplanten Report aus:
    1. Template laden
    2. Query ausführen
    3. HTML generieren
    4. Mail versenden
    """
    from .template_store import get_template
    from .report_engine  import generate_report
    from .mail_client    import send_report
    from . import query_tools

    logger.info("Starte geplanten Report: %s", report_id)

    template = get_template(report_id)
    if not template:
        logger.error("Template nicht gefunden: %s — Job übersprungen", report_id)
        return

    query_type = template.get("query_type", "")
    params     = template.get("query_params", {})
    layout     = template.get("layout", {})
    recipients = template.get("recipients", [])
    subject    = template.get("mail_subject", f"Printix Report: {template.get('name','')}")
    formats    = template.get("output_formats", ["html"])

    # Dynamische Datumsbereiche auflösen wenn nötig
    params = _resolve_dynamic_dates(params)

    try:
        # Query ausführen
        query_fn = {
            "print_stats":   query_tools.query_print_stats,
            "cost_report":   query_tools.query_cost_report,
            "top_users":     query_tools.query_top_users,
            "top_printers":  query_tools.query_top_printers,
            "anomalies":     query_tools.query_anomalies,
            "trend":         query_tools.query_trend,
        }.get(query_type)

        if not query_fn:
            logger.error("Unbekannter Query-Typ: %s", query_type)
            return

        data = query_fn(**params)
        period = f"{params.get('start_date','?')} – {params.get('end_date','?')}"

        # Report generieren
        outputs = generate_report(
            query_type=query_type,
            data=data,
            period=period,
            layout=layout,
            output_formats=formats,
            currency=layout.get("currency", "€"),
        )

        html_body = outputs.get("html", "<p>Report generiert.</p>")

        # Mail versenden
        if recipients:
            send_report(recipients=recipients, subject=subject, html_body=html_body)
            logger.info("Report '%s' versendet an: %s", template.get("name"), ", ".join(recipients))
        else:
            logger.warning("Report '%s' — keine Empfänger definiert, Mail nicht versendet", template.get("name"))

    except Exception as e:
        logger.error("Fehler beim Ausführen des Reports '%s': %s", template.get("name"), e, exc_info=True)


def _resolve_dynamic_dates(params: dict) -> dict:
    """
    Löst relative Datumswerte auf:
      "last_month_start" → erster Tag des letzten Monats
      "last_month_end"   → letzter Tag des letzten Monats
      "this_month_start" → erster Tag des aktuellen Monats
      "today"            → heutiges Datum
    """
    from datetime import date
    import calendar

    today = date.today()
    first_this_month = today.replace(day=1)
    last_month_end   = first_this_month.replace(day=1) - __import__("datetime").timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    magic = {
        "last_month_start": str(last_month_start),
        "last_month_end":   str(last_month_end),
        "this_month_start": str(first_this_month),
        "today":            str(today),
    }

    resolved = {}
    for k, v in params.items():
        resolved[k] = magic.get(str(v), v)
    return resolved


def schedule_report(report_id: str, schedule: dict) -> None:
    """
    Legt einen neuen Cron-Job für ein Report-Template an.
    Überschreibt einen bestehenden Job mit gleicher ID.
    """
    sched = _get_scheduler()

    # Bestehenden Job entfernen
    if sched.get_job(report_id):
        sched.remove_job(report_id)

    trigger = _build_cron_trigger(schedule)
    sched.add_job(
        _run_report_job,
        trigger=trigger,
        id=report_id,
        args=[report_id],
        name=f"report:{report_id[:8]}",
        replace_existing=True,
    )
    logger.info(
        "Report %s eingeplant: %s %s",
        report_id,
        schedule.get("frequency"),
        schedule.get("time"),
    )


def unschedule_report(report_id: str) -> bool:
    """Entfernt einen geplanten Job. Returns True wenn vorhanden, False wenn nicht."""
    if not APSCHEDULER_AVAILABLE:
        return False
    try:
        sched = _get_scheduler()
        if sched.get_job(report_id):
            sched.remove_job(report_id)
            logger.info("Report %s aus Schedule entfernt", report_id)
            return True
        return False
    except Exception as e:
        logger.error("Fehler beim Entfernen des Schedules %s: %s", report_id, e)
        return False


def list_scheduled_jobs() -> list[dict]:
    """Gibt alle aktiven Scheduler-Jobs zurück."""
    if not APSCHEDULER_AVAILABLE:
        return []
    try:
        sched = _get_scheduler()
        jobs = []
        for job in sched.get_jobs():
            next_run = job.next_run_time
            jobs.append({
                "job_id":      job.id,
                "name":        job.name,
                "next_run_utc": str(next_run) if next_run else None,
                "trigger":     str(job.trigger),
            })
        return jobs
    except Exception as e:
        logger.error("Fehler beim Abrufen der Scheduler-Jobs: %s", e)
        return []


def init_scheduler_from_templates() -> int:
    """
    Wird beim Server-Start aufgerufen.
    Liest alle Templates mit Schedule und plant sie ein.

    Returns:
        Anzahl eingeplanter Jobs
    """
    if not APSCHEDULER_AVAILABLE:
        logger.warning("APScheduler nicht verfügbar — keine automatischen Reports möglich")
        return 0

    from .template_store import get_scheduled_templates

    templates = get_scheduled_templates()
    count = 0
    for template in templates:
        try:
            schedule_report(template["report_id"], template["schedule"])
            count += 1
        except Exception as e:
            logger.error(
                "Fehler beim Einplanen von Template %s: %s",
                template.get("report_id"),
                e,
            )
    logger.info("%d Report-Schedules aus Templates geladen", count)
    return count


def run_report_now(report_id: str) -> dict:
    """
    Führt einen Report sofort aus (on-demand, ohne Schedule).

    Returns:
        Dict mit status, message und (wenn HTML) html_preview (erste 500 Zeichen)
    """
    from .template_store import get_template
    from .report_engine  import generate_report
    from .mail_client    import send_report, is_configured as mail_configured
    from . import query_tools

    template = get_template(report_id)
    if not template:
        raise ValueError(f"Template {report_id} nicht gefunden.")

    query_type = template.get("query_type", "")
    params     = _resolve_dynamic_dates(template.get("query_params", {}))
    layout     = template.get("layout", {})
    recipients = template.get("recipients", [])
    subject    = template.get("mail_subject", f"Printix Report: {template.get('name','')}")
    formats    = template.get("output_formats", ["html"])

    query_fn = {
        "print_stats":  query_tools.query_print_stats,
        "cost_report":  query_tools.query_cost_report,
        "top_users":    query_tools.query_top_users,
        "top_printers": query_tools.query_top_printers,
        "anomalies":    query_tools.query_anomalies,
        "trend":        query_tools.query_trend,
    }.get(query_type)

    if not query_fn:
        raise ValueError(f"Unbekannter Query-Typ: {query_type}")

    data   = query_fn(**params)
    period = f"{params.get('start_date','?')} – {params.get('end_date','?')}"

    outputs = generate_report(
        query_type=query_type,
        data=data,
        period=period,
        layout=layout,
        output_formats=formats,
        currency=layout.get("currency", "€"),
    )

    mail_sent = False
    if recipients and mail_configured():
        html_body = outputs.get("html", "<p>Report</p>")
        send_report(recipients=recipients, subject=subject, html_body=html_body)
        mail_sent = True

    return {
        "status":       "ok",
        "report_name":  template.get("name"),
        "rows":         len(data) if isinstance(data, list) else "n/a",
        "mail_sent":    mail_sent,
        "recipients":   recipients,
        "html_preview": outputs.get("html", "")[:800] + "…" if "html" in outputs else None,
    }
