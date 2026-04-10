"""
Notify Helper — Event-basierte E-Mail-Benachrichtigungen
=========================================================
Prüft ob ein Ereignis für den Tenant aktiviert ist und versendet
die Benachrichtigungs-Mail über den konfigurierten Resend API-Key.

Event-Typen (in notify_events JSON-Array):
  log_error       — Kritische Log-Fehler (ERROR/CRITICAL)
  new_printer     — Neuer Drucker in Printix erkannt
  new_queue       — Neue Drucker-Queue in Printix erkannt
  new_guest_user  — Neuer Gast-Benutzer in Printix erkannt
  report_sent     — Automatischer Report wurde erfolgreich versendet
  user_registered — Neuer MCP-Benutzer hat sich registriert (Admin)
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Standard-Ereignisse die immer aktiv sind (wenn Mail konfiguriert)
DEFAULT_EVENTS: list[str] = ["log_error"]


def get_enabled_events(tenant: dict) -> list[str]:
    """Gibt die Liste der aktivierten Ereignis-Typen für diesen Tenant zurück."""
    raw = tenant.get("notify_events", "") or ""
    try:
        events = json.loads(raw)
        if isinstance(events, list):
            return [str(e) for e in events]
    except (json.JSONDecodeError, TypeError):
        pass
    return DEFAULT_EVENTS[:]


def is_event_enabled(tenant: dict, event_type: str) -> bool:
    """Prüft ob ein bestimmtes Ereignis für den Tenant aktiviert ist."""
    return event_type in get_enabled_events(tenant)


def send_event_notification(
    tenant: dict,
    event_type: str,
    subject: str,
    html_body: str,
    check_enabled: bool = True,
) -> bool:
    """
    Versendet eine Ereignis-Benachrichtigung wenn:
      1. check_enabled=True → event_type ist in notify_events
      2. alert_recipients ist konfiguriert
      3. Mail-Credentials (mail_api_key, mail_from) sind vorhanden

    Args:
        tenant:        Tenant-Dict aus get_tenant_full_by_user_id()
        event_type:    Ereignis-Schlüssel (z.B. 'new_printer')
        subject:       Betreffzeile der E-Mail
        html_body:     HTML-Body der E-Mail
        check_enabled: Wenn True, wird notify_events geprüft (Standard)

    Returns:
        True wenn Mail versendet, False wenn übersprungen oder Fehler
    """
    # Ereignis aktiviert?
    if check_enabled and not is_event_enabled(tenant, event_type):
        return False

    # Empfänger konfiguriert?
    recipients_str = tenant.get("alert_recipients", "") or ""
    recipients = [r.strip() for r in recipients_str.split(",") if r.strip()]
    if not recipients:
        logger.debug("Kein alert_recipients konfiguriert für Ereignis '%s'", event_type)
        return False

    # Mail-Credentials vorhanden?
    api_key   = tenant.get("mail_api_key", "") or ""
    mail_from = tenant.get("mail_from", "") or ""
    if not api_key or not mail_from:
        logger.debug("Keine Mail-Credentials für Ereignis '%s'", event_type)
        return False

    mail_from_name = tenant.get("mail_from_name", "") or ""

    try:
        from reporting.mail_client import send_report
        send_report(
            recipients=recipients,
            subject=subject,
            html_body=html_body,
            api_key=api_key,
            mail_from=mail_from,
            mail_from_name=mail_from_name,
        )
        logger.info("Ereignis-Benachrichtigung '%s' versendet → %s", event_type, ", ".join(recipients))
        return True
    except Exception as e:
        logger.error("Ereignis-Benachrichtigung '%s' fehlgeschlagen: %s", event_type, e)
        return False


# ─── HTML-Templates für häufige Ereignisse ───────────────────────────────────

def _base_html(title: str, color: str, icon: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px;">
  <div style="background:{color};border-left:4px solid #374151;padding:16px;border-radius:4px;">
    <h2 style="margin:0 0 8px;color:#111827;">{icon} {title}</h2>
    {body_html}
  </div>
  <p style="color:#6b7280;font-size:.8em;margin-top:16px;">
    Automatische Benachrichtigung vom Printix MCP Add-on
  </p>
</body></html>"""


def html_new_printer(printer_name: str, printer_id: str, tenant_name: str = "") -> str:
    tenant_hint = f" (Tenant: {tenant_name})" if tenant_name else ""
    body = f"""<p style="margin:4px 0;color:#1f2937;">
      Neuer Drucker erkannt{tenant_hint}:<br>
      <strong>{printer_name}</strong><br>
      <small style="color:#6b7280;">ID: {printer_id}</small>
    </p>"""
    return _base_html("Neuer Drucker erkannt", "#dbeafe", "🖨️", body)


def html_new_queue(queue_name: str, queue_id: str, printer_name: str = "", tenant_name: str = "") -> str:
    printer_hint = f" am Drucker <em>{printer_name}</em>" if printer_name else ""
    tenant_hint  = f" (Tenant: {tenant_name})" if tenant_name else ""
    body = f"""<p style="margin:4px 0;color:#1f2937;">
      Neue Queue erkannt{printer_hint}{tenant_hint}:<br>
      <strong>{queue_name}</strong><br>
      <small style="color:#6b7280;">ID: {queue_id}</small>
    </p>"""
    return _base_html("Neue Drucker-Queue erkannt", "#d1fae5", "📋", body)


def html_new_guest_user(display_name: str, email: str, user_id: str, tenant_name: str = "") -> str:
    tenant_hint = f" (Tenant: {tenant_name})" if tenant_name else ""
    body = f"""<p style="margin:4px 0;color:#1f2937;">
      Neuer Gast-Benutzer erkannt{tenant_hint}:<br>
      <strong>{display_name}</strong><br>
      <small style="color:#6b7280;">{email} · ID: {user_id}</small>
    </p>"""
    return _base_html("Neuer Gast-Benutzer erkannt", "#fef9c3", "👤", body)


def html_report_sent(report_name: str, recipients: list[str], tenant_name: str = "") -> str:
    tenant_hint = f" (Tenant: {tenant_name})" if tenant_name else ""
    recip_str = ", ".join(recipients)
    body = f"""<p style="margin:4px 0;color:#1f2937;">
      Report erfolgreich versendet{tenant_hint}:<br>
      <strong>{report_name}</strong><br>
      <small style="color:#6b7280;">Empfänger: {recip_str}</small>
    </p>"""
    return _base_html("Report versendet", "#f0fdf4", "📊", body)


def html_user_registered(username: str, email: str, company: str = "") -> str:
    company_hint = f" ({company})" if company else ""
    body = f"""<p style="margin:4px 0;color:#1f2937;">
      Neuer Benutzer hat sich registriert{company_hint}:<br>
      <strong>{username}</strong><br>
      <small style="color:#6b7280;">{email}</small>
    </p>
    <p style="margin:8px 0 0;color:#374151;font-size:.9em;">
      Bitte in der Admin-Oberfläche prüfen und genehmigen oder ablehnen.
    </p>"""
    return _base_html("Neuer Benutzer registriert", "#fef3c7", "🔔", body)
