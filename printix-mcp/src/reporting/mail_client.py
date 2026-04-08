"""
Mail Client — Resend API
=========================
Versendet Report-E-Mails über die Resend REST-API.

Konfiguration via Umgebungsvariablen:
  MAIL_API_KEY  — Resend API-Key (re_...)
  MAIL_FROM     — Absenderadresse (z.B. reports@firma.de)
"""

import json
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


def is_configured() -> bool:
    """Prüft ob Mail-Versand konfiguriert ist."""
    return bool(os.environ.get("MAIL_API_KEY") and os.environ.get("MAIL_FROM"))


def send_report(
    recipients: list[str],
    subject: str,
    html_body: str,
    attachments: Optional[list[dict]] = None,
) -> dict:
    """
    Versendet einen Report per E-Mail über Resend.

    Args:
        recipients:  Liste von Empfänger-Adressen
        subject:     Betreffzeile
        html_body:   HTML-Inhalt der Mail
        attachments: Optional — Liste von {filename, content (base64), content_type}

    Returns:
        Resend API Response als Dict (enthält 'id' bei Erfolg)

    Raises:
        RuntimeError: bei Konfigurationsfehler oder API-Fehler
    """
    api_key  = os.environ.get("MAIL_API_KEY", "")
    mail_from = os.environ.get("MAIL_FROM", "")

    if not api_key:
        raise RuntimeError(
            "MAIL_API_KEY nicht konfiguriert. "
            "Bitte Resend API-Key in den Add-on-Einstellungen hinterlegen."
        )
    if not mail_from:
        raise RuntimeError(
            "MAIL_FROM nicht konfiguriert. "
            "Bitte Absenderadresse in den Add-on-Einstellungen hinterlegen."
        )
    if not recipients:
        raise ValueError("Keine Empfänger angegeben.")

    payload: dict = {
        "from":    mail_from,
        "to":      recipients,
        "subject": subject,
        "html":    html_body,
    }

    if attachments:
        payload["attachments"] = attachments

    logger.info(
        "Sende Mail: '%s' → %s",
        subject,
        ", ".join(recipients),
    )

    try:
        response = requests.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            data=json.dumps(payload),
            timeout=30,
        )
    except requests.RequestException as e:
        raise RuntimeError(f"HTTP-Fehler beim Mail-Versand: {e}") from e

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Resend API Fehler {response.status_code}: {response.text[:300]}"
        )

    result = response.json()
    logger.info("Mail versendet, ID: %s", result.get("id"))
    return result
