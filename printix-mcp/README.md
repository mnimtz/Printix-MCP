# Printix MCP Server — Home Assistant Add-on

**Version 3.0.0** | Multi-Tenant MCP Server für die Printix Cloud Print API

Verbindet KI-Assistenten (Claude, ChatGPT) über das **Model Context Protocol (MCP)** mit der Printix Cloud — direkt aus Home Assistant heraus. Ab v3.0.0 inklusive vollständiger Report-Verwaltung im Browser und mobilem UI.

---

## Features

### 🖨️ Druckverwaltung via KI-Chat
- Drucker auflisten, Status abfragen, SNMP konfigurieren
- Druckjobs verwalten (auflisten, löschen, Besitzer ändern, direkt einreichen)
- Benutzer, Gruppen, Netzwerke, Standorte verwalten
- ID-Codes generieren, Karten registrieren / löschen / suchen
- Workstations abfragen

### 📊 Reports & Automatisierungen _(neu in v3.0.0)_
- **Web-UI**: Report-Templates direkt im Browser erstellen, bearbeiten, ausführen
- **18 Presets**: Basierend auf dem offiziellen Printix PowerBI-Template (v2025.4)
- **7 sofort nutzbare Presets**: Druckvolumen, Trend, Top-Drucker, Standorte, Top-Benutzer, Kostenanalyse, Anomalie-Erkennung
- **Ausgabeformate**: HTML (E-Mail-Body), CSV, JSON
- **Zeitpläne**: Täglich / wöchentlich / monatlich — vollständig im Browser konfigurierbar
- **KI-Integration**: Claude kann Reports direkt per `printix_save_report_template` anlegen — sie erscheinen sofort in der Web-UI

### 📱 Responsives UI _(neu in v3.0.0)_
- Hamburger-Menü für Smartphones und Tablets (≤ 768 px)
- Alle Seiten für mobile Geräte optimiert
- iOS-Zoom-Fix bei Eingabefeldern

### 🌐 Multi-Tenant
Jeder Benutzer verwaltet seine eigenen Printix-Zugangsdaten. Mehrere Tenants gleichzeitig unterstützt.

### 🌍 12 Sprachen
Deutsch, Englisch, Französisch, Spanisch, Italienisch, Portugiesisch, Niederländisch, Polnisch, Russisch, Japanisch, Österreichisch, Schwiizerdütsch

---

## Voraussetzungen

- Home Assistant mit SSH-Zugang
- Printix Cloud-Account mit API-Zugang
- Printix OAuth2 Credentials (Tenant-ID, Client-ID, Client-Secret)
- **Optional**: Printix BI SQL Server (für Reports & Statistiken)
- **Optional**: Resend API-Key (für E-Mail-Versand von Reports)

---

## Installation

1. Repository zu Home Assistant hinzufügen
2. Add-on „Printix MCP Server" installieren
3. Add-on starten
4. Web-Oberfläche öffnen (Port 8080) und Konto registrieren
5. Printix OAuth2 Credentials eingeben (Einstellungen → Printix API)
6. Optional: SQL-Server-Zugangsdaten für Reports eintragen (Einstellungen → BI-Datenbank)
7. Claude über die MCP-URL aus der Web-Oberfläche verbinden

---

## Web-Oberfläche

| URL | Beschreibung |
|-----|-------------|
| `/` | Startseite / Weiterleitung |
| `/register` | Neues Konto registrieren |
| `/dashboard` | Benutzer-Dashboard mit MCP-URL |
| `/reports` | **Reports & Automatisierungen** |
| `/settings` | Credentials, SQL-Server, Mail-API |
| `/help` | MCP-Verbindungsanleitung |

---

## MCP-Verbindung

**Streamable HTTP (empfohlen, für Claude Desktop / claude.ai):**
```
http://<HA-IP>:8765/mcp
```

**SSE (für ältere Clients):**
```
http://<HA-IP>:8765/sse
```

OAuth2 Bearer Token aus der Web-Oberfläche unter **Dashboard** kopieren.

---

## MCP-Tools (Übersicht)

| Kategorie | Tools |
|-----------|-------|
| Status | `printix_status`, `printix_reporting_status` |
| Drucker | `printix_list_printers`, `printix_get_printer` |
| Jobs | `printix_list_jobs`, `printix_get_job`, `printix_delete_job`, `printix_submit_job`, `printix_change_job_owner` |
| Benutzer | `printix_list_users`, `printix_get_user`, `printix_create_user`, `printix_delete_user` |
| Gruppen | `printix_list_groups`, `printix_get_group`, `printix_create_group`, `printix_delete_group` |
| Netzwerke | `printix_list_networks`, `printix_get_network`, `printix_create_network`, `printix_update_network`, `printix_delete_network` |
| Standorte | `printix_list_sites`, `printix_get_site`, `printix_create_site`, `printix_update_site`, `printix_delete_site` |
| Karten | `printix_list_cards`, `printix_register_card`, `printix_delete_card`, `printix_search_card`, `printix_generate_id_code` |
| Workstations | `printix_list_workstations`, `printix_get_workstation` |
| SNMP | `printix_list_snmp_configs`, `printix_get_snmp_config`, `printix_create_snmp_config`, `printix_delete_snmp_config` |
| Reports | `printix_save_report_template`, `printix_get_report_template`, `printix_list_report_templates`, `printix_delete_report_template` |
| Report-Ausführung | `printix_run_report_now`, `printix_schedule_report`, `printix_list_schedules`, `printix_update_schedule`, `printix_delete_schedule` |
| Statistiken | `printix_query_print_stats`, `printix_query_cost_report`, `printix_query_top_users`, `printix_query_top_printers`, `printix_query_trend`, `printix_query_anomalies` |

---

## Changelog

Vollständiges Changelog: [CHANGELOG.md](CHANGELOG.md)

### v3.0.0 (2026-04-09)
- **NEU**: Reports & Automatisierungen — vollständige Web-UI für Report-Templates
- **NEU**: 18 Presets aus dem Printix PowerBI-Template v2025.4 (7 sofort verfügbar, 11 in v3.1)
- **NEU**: Responsives UI mit Hamburger-Menü für Smartphones und Tablets
- **NEU**: KI-Agent-Integration — Claude erstellt Reports direkt via `printix_save_report_template`
- Vollständige i18n in 12 Sprachen für alle neuen UI-Bereiche

### v2.13.0
- Multi-Tenant OAuth2, Dual Transport (HTTP + SSE), alle API-Bugfixes (Golden Master)

---

## Dokumentation

Vollständige technische Dokumentation: [DOCS.md](DOCS.md)

---

## Lizenz

MIT License — © 2026 Marcus Nimtz / Tungsten Automation
