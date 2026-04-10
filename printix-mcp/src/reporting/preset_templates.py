"""
Preset Templates — Vordefinierte Report-Vorlagen basierend auf Printix PowerBI-Template
========================================================================================
Alle 17 Seiten des offiziellen Printix PowerBI-Templates (v2025.4.0) sind hier als
Preset-Definitionen hinterlegt.

Jedes Preset enthält:
  key              — Eindeutiger Bezeichner (URL-safe)
  name             — Anzeigename in der UI
  description      — Kurzbeschreibung was dieser Report zeigt
  icon             — Emoji-Icon für die UI
  pbi_page         — Entsprechende Seite im PowerBI-Template (Referenz)
  query_type       — query_tools-Funktion (oder None wenn noch nicht implementiert)
  query_params     — Standardparameter für die Query
  output_formats   — Standardausgabeformate
  mail_subject     — Vorschlag für E-Mail-Betreff
  schedule_suggestion — Empfohlener Schedule-Rhythmus
  tag              — Kategorie-Tag für die UI
  available        — True wenn mit aktuellen query_tools ausführbar
  coming_soon      — Beschreibung der fehlenden Implementierung (wenn nicht available)
"""

from typing import Any, Optional

# ── Unterstützte Ausgabeformate ───────────────────────────────────────────────────
#
#  Format   | Status       | Versand         | Engine
#  ---------|--------------|-----------------|---------------------------
#  html     | ✅ verfügbar | E-Mail-Body     | report_engine.render_html()
#  csv      | ✅ verfügbar | Anhang .csv     | report_engine.render_csv()
#  json     | ✅ verfügbar | Anhang .json    | report_engine.render_json()
#  pdf      | 🔜 v2.15    | Anhang .pdf     | WeasyPrint (geplant)
#  xlsx     | 🔜 v2.15    | Anhang .xlsx    | openpyxl (geplant)
#
#  Mehrfachauswahl möglich: z.B. ["html", "csv"] sendet Mail-Body + CSV-Anhang.
#  mail_client.send_report() unterstützt Anhänge via attachments=[{filename, content, content_type}]

ALL_FORMATS = [
    {"key": "html",  "label": "📧 HTML (E-Mail-Body)",  "available": True},
    {"key": "csv",   "label": "📊 CSV (Tabelle)",        "available": True},
    {"key": "json",  "label": "{} JSON (Rohdaten)",     "available": True},
    {"key": "pdf",   "label": "📄 PDF",                  "available": False, "coming_soon": "v2.15"},
    {"key": "xlsx",  "label": "📗 Excel (XLSX)",         "available": False, "coming_soon": "v2.15"},
]

# ── Preset-Definitionen ──────────────────────────────────────────────────────────

PRESETS: dict[str, dict[str, Any]] = {

    # ── 1. Monatlicher Überblick (→ Overview) ─────────────────────────────────
    "overview_monthly": {
        "name": "Monatlicher Drucküberblick",
        "description": "Gesamtübersicht aller Druckaktivitäten: Seitenvolumen, "
                       "Farb-/S/W-Anteil, Duplex-Quote und Jobanzahl des letzten Monats.",
        "icon": "📋",
        "pbi_page": "Overview",
        "query_type": "print_stats",
        "query_params": {
            "start_date": "last_month_start",
            "end_date":   "last_month_end",
            "group_by":   "day",
        },
        "output_formats": ["html"],
        "mail_subject": "Printix Drucküberblick {month}",
        "schedule_suggestion": {"frequency": "monthly", "day": 1, "time": "08:00"},
        "tag": "Überblick",
        "available": True,
    },

    # ── 2. Wochen-Trend ────────────────────────────────────────────────────────
    "trend_weekly": {
        "name": "Wöchentlicher Drucktrend",
        "description": "Entwicklung des Druckvolumens der letzten 4 Wochen, "
                       "aufgeschlüsselt nach Woche. Ideal für regelmäßiges Monitoring.",
        "icon": "📈",
        "pbi_page": "Overview",
        "query_type": "trend",
        "query_params": {
            "start_date": "last_month_start",
            "end_date":   "last_month_end",
            "group_by":   "week",
        },
        "output_formats": ["html"],
        "mail_subject": "Printix Drucktrend KW{week}",
        "schedule_suggestion": {"frequency": "weekly", "day": 0, "time": "07:00"},
        "tag": "Trend",
        "available": True,
    },

    # ── 3. Drucker-Übersicht (→ Printers - Overview) ──────────────────────────
    "printers_overview": {
        "name": "Drucker-Übersicht",
        "description": "Top-Drucker nach Druckvolumen, Farb-/S/W-Anteil je Drucker, "
                       "Duplex-Quote und Modellverteilung im Überblick.",
        "icon": "🖨️",
        "pbi_page": "Printers - Overview",
        "query_type": "top_printers",
        "query_params": {
            "start_date": "last_month_start",
            "end_date":   "last_month_end",
            "limit":      20,
        },
        "output_formats": ["html"],
        "mail_subject": "Printix Drucker-Übersicht {month}",
        "schedule_suggestion": {"frequency": "monthly", "day": 1, "time": "08:30"},
        "tag": "Drucker",
        "available": True,
    },

    # ── 4. Drucker-Verlauf (→ Printer - History) ──────────────────────────────
    "printer_history": {
        "name": "Drucker-Verlauf (einzeln)",
        "description": "Jobverlauf, aktive Benutzer und Tonerstand eines einzelnen "
                       "Druckers über Zeit. Benötigt Drucker-ID als Parameter.",
        "icon": "📅",
        "pbi_page": "Printer - History",
        "query_type": None,
        "query_params": {},
        "output_formats": ["html"],
        "mail_subject": "Printix Drucker-Verlauf {printer}",
        "schedule_suggestion": {"frequency": "monthly", "day": 1, "time": "09:00"},
        "tag": "Drucker",
        "available": False,
        "coming_soon": "Erfordert printer_history Query-Typ mit Drucker-ID-Filter "
                       "und Toner-Level aus device_readings-Tabelle (geplant für v2.15.0)",
    },

    # ── 5. Drucker Service Status (→ Printers - Service Status) ───────────────
    "printer_service_status": {
        "name": "Drucker Service-Status",
        "description": "Fehlerstatus, Verbrauchsmaterial-Warnungen und letzte "
                       "gemeldete Zustände aller Drucker aus den Device-Readings.",
        "icon": "🔧",
        "pbi_page": "Printers - Service Status",
        "query_type": None,
        "query_params": {},
        "output_formats": ["html"],
        "mail_subject": "Printix Drucker Service-Status",
        "schedule_suggestion": {"frequency": "weekly", "day": 0, "time": "07:00"},
        "tag": "Service",
        "available": False,
        "coming_soon": "Erfordert device_readings-Abfrage mit Toner-Level, "
                       "Papierstau-Ereignissen und Status-Aggregation (geplant für v2.15.0)",
    },

    # ── 6. Job-Verlauf (→ Job - History) ──────────────────────────────────────
    "job_history": {
        "name": "Job-Verlauf",
        "description": "Vollständige Druckjob-Liste mit Benutzer, Drucker, "
                       "Seitenanzahl, Farbe, Duplex und Zeitstempel. Filterbar.",
        "icon": "📄",
        "pbi_page": "Job - History",
        "query_type": None,
        "query_params": {
            "start_date": "last_month_start",
            "end_date":   "last_month_end",
        },
        "output_formats": ["html", "csv"],  # xlsx sobald implementiert
        "mail_subject": "Printix Job-Verlauf {month}",
        "schedule_suggestion": {"frequency": "monthly", "day": 1, "time": "08:00"},
        "tag": "Jobs",
        "available": False,
        "coming_soon": "Erfordert job_history Query-Typ für detaillierte Job-Rohdaten "
                       "aus job_history-Tabelle (geplant für v2.15.0)",
    },

    # ── 7. Druckregeln (→ Print Rules - Overview) ─────────────────────────────
    "print_rules_overview": {
        "name": "Druckregeln-Übersicht",
        "description": "Auswertung der aktiven Print Queues: Duplex-Standardeinstellungen, "
                       "S/W-Standard, Global-/Gruppenqueues und Auslastung.",
        "icon": "📐",
        "pbi_page": "Print Rules - Overview",
        "query_type": None,
        "query_params": {},
        "output_formats": ["html"],
        "mail_subject": "Printix Druckregeln-Übersicht",
        "schedule_suggestion": {"frequency": "monthly", "day": 1, "time": "09:00"},
        "tag": "Verwaltung",
        "available": False,
        "coming_soon": "Erfordert queue_stats Query-Typ für print_queues-Tabelle "
                       "mit Regelkonfiguration (geplant für v2.15.0)",
    },

    # ── 8. Standort-Übersicht (→ Locations - Overview) ────────────────────────
    "locations_overview": {
        "name": "Standort-Übersicht",
        "description": "Druckvolumen und Kostenverteilung nach Standort/Netzwerk. "
                       "Zeigt welche Standorte am meisten drucken.",
        "icon": "📍",
        "pbi_page": "Locations - Overview",
        "query_type": "print_stats",
        "query_params": {
            "start_date": "last_month_start",
            "end_date":   "last_month_end",
            "group_by":   "site",
        },
        "output_formats": ["html"],
        "mail_subject": "Printix Standort-Auswertung {month}",
        "schedule_suggestion": {"frequency": "monthly", "day": 1, "time": "08:00"},
        "tag": "Standort",
        "available": True,
    },

    # ── 9. Benutzer-Übersicht (→ Users - Overview) ────────────────────────────
    "users_overview": {
        "name": "Benutzer-Übersicht",
        "description": "Top-Nutzer nach Druckvolumen, Gruppen-Zugehörigkeit, "
                       "Abteilung und Druckmuster. Kompakte Übersicht für HR/IT.",
        "icon": "👥",
        "pbi_page": "Users - Overview",
        "query_type": "top_users",
        "query_params": {
            "start_date": "last_month_start",
            "end_date":   "last_month_end",
            "limit":      20,
        },
        "output_formats": ["html"],
        "mail_subject": "Printix Benutzer-Übersicht {month}",
        "schedule_suggestion": {"frequency": "monthly", "day": 1, "time": "08:00"},
        "tag": "Benutzer",
        "available": True,
    },

    # ── 10. Benutzer Druckdetails (→ User - Print Details) ────────────────────
    "user_print_details": {
        "name": "Benutzer Druckdetails",
        "description": "Detailansicht eines einzelnen Benutzers: Druckverlauf, "
                       "bevorzugte Drucker, Farb-/S/W-Anteil, Duplexquote.",
        "icon": "🔍",
        "pbi_page": "User - Print Details",
        "query_type": None,
        "query_params": {},
        "output_formats": ["html"],
        "mail_subject": "Printix Druckdetails {user}",
        "schedule_suggestion": None,
        "tag": "Benutzer",
        "available": False,
        "coming_soon": "Erfordert user_detail Query-Typ mit Benutzer-ID-Filter "
                       "(geplant für v2.15.0)",
    },

    # ── 11. Benutzer Kopierdetails (→ User - Copy Details) ────────────────────
    "user_copy_details": {
        "name": "Benutzer Kopier-Details",
        "description": "Kopiervolumen pro Benutzer aus jobs_copy/jobs_copy_details: "
                       "Seiten, Farbe, Duplex, zeitlicher Verlauf.",
        "icon": "📑",
        "pbi_page": "User - Copy Details",
        "query_type": None,
        "query_params": {},
        "output_formats": ["html"],
        "mail_subject": "Printix Kopier-Details {user}",
        "schedule_suggestion": None,
        "tag": "Benutzer",
        "available": False,
        "coming_soon": "Erfordert user_copy_detail Query-Typ auf jobs_copy + "
                       "jobs_copy_details-Tabellen (geplant für v2.15.0)",
    },

    # ── 12. Benutzer Scan-Details (→ User - Scan Details) ─────────────────────
    "user_scan_details": {
        "name": "Benutzer Scan-Details",
        "description": "Scan-Aktivitäten pro Benutzer aus jobs_scan: "
                       "Scan-Workflows, Seitenanzahl, zeitlicher Verlauf.",
        "icon": "🔎",
        "pbi_page": "User - Scan Details",
        "query_type": None,
        "query_params": {},
        "output_formats": ["html"],
        "mail_subject": "Printix Scan-Details {user}",
        "schedule_suggestion": None,
        "tag": "Benutzer",
        "available": False,
        "coming_soon": "Erfordert user_scan_detail Query-Typ auf jobs_scan-Tabelle "
                       "(geplant für v2.15.0)",
    },

    # ── 13. Workstation-Übersicht (→ Workstations - Overview) ─────────────────
    "workstations_overview": {
        "name": "Workstation-Übersicht",
        "description": "Alle registrierten Workstations: OS-Verteilung, Netzwerk, "
                       "Client-Version, Druckwarteschlangen je Workstation.",
        "icon": "💻",
        "pbi_page": "Workstations - Overview",
        "query_type": None,
        "query_params": {},
        "output_formats": ["html"],
        "mail_subject": "Printix Workstation-Übersicht",
        "schedule_suggestion": {"frequency": "monthly", "day": 1, "time": "09:00"},
        "tag": "Infrastruktur",
        "available": False,
        "coming_soon": "Erfordert workstation_overview Query-Typ auf workstations + "
                       "workstation_print_queues-Tabellen (geplant für v2.15.0)",
    },

    # ── 14. Workstation-Details (→ Workstation - Details) ─────────────────────
    "workstation_details": {
        "name": "Workstation-Details (einzeln)",
        "description": "Detailansicht einer Workstation: installierte Treiber, "
                       "Druckwarteschlangen, Netzwerkadapter, Benutzer.",
        "icon": "🖥️",
        "pbi_page": "Workstation - Details",
        "query_type": None,
        "query_params": {},
        "output_formats": ["html"],
        "mail_subject": "Printix Workstation-Details {workstation}",
        "schedule_suggestion": None,
        "tag": "Infrastruktur",
        "available": False,
        "coming_soon": "Erfordert workstation_detail Query-Typ mit Workstation-ID-Filter "
                       "(geplant für v2.15.0)",
    },

    # ── 15. Tree-O-Meter / Nachhaltigkeit (→ Tree-O-Meter) ────────────────────
    "tree_o_meter": {
        "name": "Nachhaltigkeits-Report (Tree-O-Meter)",
        "description": "Umweltwirkung des Druckens: Baumverbrauch, "
                       "CO₂-Äquivalent und Einsparpotenziale durch Duplex/S/W.",
        "icon": "🌳",
        "pbi_page": "Tree-O-Meter",
        "query_type": None,
        "query_params": {
            "start_date": "last_month_start",
            "end_date":   "last_month_end",
            "sheets_per_tree": 8333,
        },
        "output_formats": ["html"],
        "mail_subject": "Printix Nachhaltigkeits-Report {month}",
        "schedule_suggestion": {"frequency": "monthly", "day": 1, "time": "09:00"},
        "tag": "Nachhaltigkeit",
        "available": False,
        "coming_soon": "Erfordert tree_meter Query-Typ mit Baumverbrauch-Berechnung "
                       "aus tracking_data.TotalTreesUsed-Measure (geplant für v2.15.0)",
    },

    # ── 16. Kostenanalyse (→ Cost) ────────────────────────────────────────────
    "cost_report_monthly": {
        "name": "Monatliche Kostenanalyse",
        "description": "Druckkosten aufgeschlüsselt nach Benutzer, Drucker und "
                       "Abteilung. Basiert auf konfigurierbaren Blatt- und Tonerkosten.",
        "icon": "💶",
        "pbi_page": "Cost",
        "query_type": "cost_report",
        "query_params": {
            "start_date":      "last_month_start",
            "end_date":        "last_month_end",
            "cost_per_sheet":  0.01,
            "cost_per_mono":   0.02,
            "cost_per_color":  0.08,
            "group_by":        "user",
        },
        "output_formats": ["html"],
        "mail_subject": "Printix Kostenanalyse {month}",
        "schedule_suggestion": {"frequency": "monthly", "day": 1, "time": "08:00"},
        "tag": "Kosten",
        "available": True,
    },

    # ── 17. Service Desk (→ Service Desk) ─────────────────────────────────────
    "service_desk": {
        "name": "Service Desk Report",
        "description": "Druckjob-Liste für den IT-Service-Desk: fehlerhafte Jobs, "
                       "gelöschte Jobs, Printer-Fehler — gefiltert nach Zeitraum.",
        "icon": "🛎️",
        "pbi_page": "Service Desk",
        "query_type": None,
        "query_params": {
            "start_date": "last_month_start",
            "end_date":   "last_month_end",
        },
        "output_formats": ["html", "csv"],  # xlsx sobald implementiert
        "mail_subject": "Printix Service Desk Report {month}",
        "schedule_suggestion": {"frequency": "weekly", "day": 0, "time": "07:00"},
        "tag": "Service",
        "available": False,
        "coming_soon": "Erfordert service_desk Query-Typ auf job_history-Tabelle "
                       "mit Fehler-/Status-Filter (geplant für v2.15.0)",
    },

    # ── Bonus: Anomalie-Erkennung (eigenständig, kein direktes PBI-Äquivalent) ─
    "anomaly_detection": {
        "name": "Anomalie-Erkennung",
        "description": "Automatische Erkennung ungewöhnlicher Druckmuster: "
                       "plötzliche Volumenspitzen, untypische Druckzeiten, Ausreißer.",
        "icon": "⚠️",
        "pbi_page": None,
        "query_type": "anomalies",
        "query_params": {
            "start_date": "last_month_start",
            "end_date":   "last_month_end",
        },
        "output_formats": ["html"],
        "mail_subject": "Printix Anomalie-Report {month}",
        "schedule_suggestion": {"frequency": "monthly", "day": 1, "time": "09:00"},
        "tag": "Analyse",
        "available": True,
    },
}


# ── Public API ────────────────────────────────────────────────────────────────────

def get_preset(key: str) -> Optional[dict[str, Any]]:
    """Gibt ein einzelnes Preset zurück (None wenn nicht gefunden)."""
    return PRESETS.get(key)


def list_presets(only_available: bool = False) -> list[dict[str, Any]]:
    """
    Gibt alle Presets als Liste zurück.

    Args:
        only_available: Wenn True, werden nur sofort ausführbare Presets zurückgegeben.
    """
    result = []
    for key, preset in PRESETS.items():
        if only_available and not preset.get("available", False):
            continue
        entry = dict(preset)
        entry["key"] = key
        result.append(entry)
    return result


def list_presets_by_tag(tag: str) -> list[dict[str, Any]]:
    """Filtert Presets nach Kategorie-Tag."""
    return [
        dict(p, key=k)
        for k, p in PRESETS.items()
        if p.get("tag") == tag
    ]


def get_available_tags() -> list[str]:
    """Gibt alle vorhandenen Tags in stabiler Reihenfolge zurück."""
    seen = []
    for p in PRESETS.values():
        t = p.get("tag", "")
        if t and t not in seen:
            seen.append(t)
    return seen


def preset_to_template_defaults(key: str, owner_user_id: str = "") -> Optional[dict[str, Any]]:
    """
    Wandelt ein Preset in ein Template-Dict um (bereit für template_store.save_template).
    Gibt None zurück wenn Preset nicht gefunden.

    Der Rückgabe-Dict entspricht den Parametern von save_template() und kann
    direkt als Formular-Vorausfüllung oder für die API genutzt werden.
    """
    preset = get_preset(key)
    if not preset:
        return None

    return {
        "name":           preset["name"],
        "query_type":     preset.get("query_type") or "",
        "query_params":   dict(preset.get("query_params", {})),
        "output_formats": list(preset.get("output_formats", ["html"])),
        "layout": {
            "primary_color": "#0078D4",
            "company_name":  "",
            "footer_text":   f"Erstellt aus Preset: {preset['name']}",
            "logo_base64":   "",
        },
        "schedule":       dict(preset["schedule_suggestion"])
                          if preset.get("schedule_suggestion") else None,
        "recipients":     [],
        "mail_subject":   preset.get("mail_subject", f"Printix Report: {preset['name']}"),
        "created_prompt": f"Aus Preset erstellt: {preset['name']} "
                          f"(PowerBI-Seite: {preset.get('pbi_page', 'n/a')})",
        "owner_user_id":  owner_user_id,
    }


# ── Statistiken ───────────────────────────────────────────────────────────────────

def get_stats() -> dict[str, Any]:
    """Gibt Zusammenfassung der Preset-Bibliothek zurück."""
    total = len(PRESETS)
    available = sum(1 for p in PRESETS.values() if p.get("available", False))
    tags = get_available_tags()
    return {
        "total":      total,
        "available":  available,
        "coming_soon": total - available,
        "tags":       tags,
        "pbi_version": "2025.4.0",
    }
