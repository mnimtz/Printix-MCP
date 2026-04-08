"""
Template Store — Persistente Report-Definitionen
=================================================
Speichert Report-Templates als JSON in /data/report_templates.json.
Die Datei überlebt Add-on-Updates (liegt im /data-Volume).

Template-Schema:
  report_id      — UUID
  name           — Lesbarer Name
  created_prompt — Ursprüngliche Nutzeranfrage
  query_type     — print_stats | cost_report | top_users | top_printers | anomalies | trend
  query_params   — Query-Parameter als Dict
  output_formats — Liste: html | pdf | xlsx | csv | json
  layout         — Dict mit logo_base64, primary_color, company_name, footer_text
  schedule       — Dict mit frequency, day, time (oder None wenn kein Schedule)
  recipients     — Liste von E-Mail-Adressen
  mail_subject   — Betreffzeile
  created_at     — ISO-Timestamp der Erstellung
  updated_at     — ISO-Timestamp der letzten Änderung
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

TEMPLATES_FILE = os.environ.get("TEMPLATES_PATH", "/data/report_templates.json")


def _load() -> dict[str, Any]:
    """Lädt alle Templates aus der JSON-Datei."""
    if not os.path.exists(TEMPLATES_FILE):
        return {}
    try:
        with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Fehler beim Laden der Templates: %s", e)
        return {}


def _save(data: dict[str, Any]) -> None:
    """Schreibt alle Templates in die JSON-Datei."""
    try:
        os.makedirs(os.path.dirname(TEMPLATES_FILE) or ".", exist_ok=True)
        with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error("Fehler beim Speichern der Templates: %s", e)
        raise RuntimeError(f"Template konnte nicht gespeichert werden: {e}") from e


def save_template(
    name: str,
    query_type: str,
    query_params: dict[str, Any],
    recipients: list[str],
    mail_subject: str,
    output_formats: Optional[list[str]] = None,
    layout: Optional[dict[str, Any]] = None,
    schedule: Optional[dict[str, Any]] = None,
    created_prompt: str = "",
    report_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Speichert ein neues Template oder überschreibt ein bestehendes (bei report_id).

    Returns:
        Das gespeicherte Template-Dict mit allen Feldern.
    """
    templates = _load()
    now = datetime.now(timezone.utc).isoformat()

    if report_id and report_id in templates:
        # Update: bestehende Felder übernehmen, nur geänderte überschreiben
        template = templates[report_id]
        template.update({
            "name":           name,
            "query_type":     query_type,
            "query_params":   query_params,
            "output_formats": output_formats or ["html"],
            "layout":         layout or template.get("layout", {}),
            "schedule":       schedule,
            "recipients":     recipients,
            "mail_subject":   mail_subject,
            "updated_at":     now,
        })
        if created_prompt:
            template["created_prompt"] = created_prompt
    else:
        # Neu anlegen
        rid = report_id or str(uuid.uuid4())
        template = {
            "report_id":      rid,
            "name":           name,
            "created_prompt": created_prompt,
            "query_type":     query_type,
            "query_params":   query_params,
            "output_formats": output_formats or ["html"],
            "layout":         layout or {
                "primary_color": "#0078D4",
                "company_name":  "",
                "footer_text":   "",
                "logo_base64":   "",
            },
            "schedule":       schedule,
            "recipients":     recipients,
            "mail_subject":   mail_subject,
            "created_at":     now,
            "updated_at":     now,
        }
        templates[template["report_id"]] = template

    _save(templates)
    logger.info("Template gespeichert: %s (%s)", template["name"], template["report_id"])
    return template


def list_templates() -> list[dict[str, Any]]:
    """Gibt alle Templates als Liste zurück (ohne layout.logo_base64 für Lesbarkeit)."""
    templates = _load()
    result = []
    for t in templates.values():
        summary = {k: v for k, v in t.items() if k != "layout"}
        if "layout" in t:
            layout_copy = dict(t["layout"])
            layout_copy.pop("logo_base64", None)
            summary["layout"] = layout_copy
        result.append(summary)
    return sorted(result, key=lambda x: x.get("created_at", ""))


def get_template(report_id: str) -> Optional[dict[str, Any]]:
    """Gibt ein einzelnes Template zurück (None wenn nicht gefunden)."""
    return _load().get(report_id)


def delete_template(report_id: str) -> bool:
    """
    Löscht ein Template.

    Returns:
        True wenn gelöscht, False wenn nicht gefunden.
    """
    templates = _load()
    if report_id not in templates:
        return False
    del templates[report_id]
    _save(templates)
    logger.info("Template gelöscht: %s", report_id)
    return True


def get_scheduled_templates() -> list[dict[str, Any]]:
    """Gibt alle Templates mit aktivem Schedule zurück."""
    return [t for t in _load().values() if t.get("schedule")]
