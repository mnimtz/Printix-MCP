# Changelog

## 3.6.3 (2026-04-10)

### Fixed
- Demo-Generator: `preset`-Parameter aus functools.partial entfernt (TypeError verhinderte Daten-Generierung)
- Demo-Polling-JS: Absolute URL-Pfade auf `window.location.pathname`-relativ umgestellt (HA Ingress-Proxy-Kompatibilität)

## 3.4.0 (2026-04-10)

### Neu — Demo-Daten Generator (UI)

- **Demo-Daten Tab**: Neues Register "Demo-Daten" in der Printix Web-UI (neben Drucker/Queues/Benutzer)
- **3 Unternehmens-Presets**: Kleinunternehmen (15 MA/3 Drucker), Mittelstand (50 MA/10 Drucker), Großunternehmen (120 MA/30 Drucker) — je mit vorausgefüllten Werten für Volumen, Sprachen und Standorte
- **Print-Queues**: Demo-Schema enthält jetzt `demo.queues` mit konfigurierbarer Anzahl Queues pro Drucker (1–5); Jobs werden Queues zugeordnet
- **Internationales Namensset**: 11 Sprachen (neu: Portugiesisch/Brasilianisch, Polnisch, Japanisch); insgesamt 200+ Vornamen/Nachnamen
- **Abteilungs-Druckgewichtung**: FIN, VTR, PRD, LOG drucken mehr als HR oder IT — für realistische Verteilung in Reports
- **Quartalsend-Boost**: Letzter Monat jedes Quartals hat +20% Druckvolumen — saisonal realistisch
- **Migration-Guards**: Schema-Setup fügt fehlende Spalten (`queue_id`, `preset`, `queue_count`) automatisch nach, falls alte Tabellen existieren
- **Verbesserter Batch-Insert**: Chunk-Größe auf 300 reduziert, mit Progress-Logging — vermeidet Timeouts bei großen Datasets
- **Azure SQL Hinweis-Banner**: Klar sichtbarer Warnhinweis, dass die Funktion eine eigene Azure SQL (mit Schreibrechten) erfordert
- **i18n**: Alle neuen Felder (Preset, Queues, Preset-Namen) in allen 12 Sprachen übersetzt
- **`set_config_from_tenant()`**: Neue Hilfsfunktion in sql_client.py für Web-Routen ohne Bearer-Middleware

## 3.1.1 (2026-04-09)

### Bugfixes
- **Anhänge fehlten bei on-demand Reports**: run_report_now() sendete E-Mails ohne Anhänge (PDF/XLSX/CSV) — Attachment-Logik fehlte im run_report_now-Pfad (war nur in _run_report_job vorhanden). Behoben.
- **FreeTDS Date Error 241**: _fmt_date() gibt jetzt echte Python date-Objekte zurück statt Strings — FreeTDS/SQL Server Konvertierungsfehler behoben.
- **Unbekannte Magic-Keywords**: last_year_start, last_year_end, last_quarter_start/end, last_week_start/end, this_year_start in _resolve_dynamic_dates ergänzt.
- **MCP-Tool Docstring**: printix_save_report_template zeigt jetzt alle gültigen Magic-Keywords und query_types explizit an.

## 3.1.0 (2026-04-09)

### Neu — PDF/XLSX Ausgabe & alle Report-Presets verfügbar

- **PDF-Export**: Alle Reports können jetzt als PDF generiert und per E-Mail versendet werden (fpdf2-basiert). Farbiger Header, KPI-Karten als farbige Rechtecke, Tabellen mit alternierenden Zeilenfarben, automatischer Seitenumbruch.
- **XLSX-Export**: Alle Reports können jetzt als Excel-Datei (.xlsx) generiert und per E-Mail versendet werden (openpyxl-basiert). Auto-Spaltenbreiten, numerische Erkennung, farbiger Header.
- **Alle 18 Presets verfügbar**: Alle 11 bisher als "Bald verfügbar" markierten Report-Presets sind jetzt vollständig implementiert:
  - Drucker-Verlauf (printer_history)
  - Drucker-Servicestatus (device_readings — graceful fail bei fehlendem BI-Zugang)
  - Job-Historie (job_history)
  - Druckregeln-Übersicht (queue_stats — graceful fail)
  - Benutzer-Druckdetails (user_detail)
  - Benutzer-Kopierdetails (user_copy_detail)
  - Benutzer-Scandetails (user_scan_detail)
  - Workstation-Übersicht (workstation_overview — graceful fail)
  - Workstation-Details (workstation_overview — graceful fail)
  - Tree-O-Meter (tree_meter: Bäume + CO₂-Berechnung, konfigurierbare Blätter/Baum)
  - Service-Desk-Report (service_desk: alle nicht-OK Druckjobs)
- **E-Mail-Anhänge**: Scheduler und Run-Now senden CSV/JSON/PDF/XLSX als base64-kodierte Anhänge; HTML bleibt E-Mail-Body.
- **Graceful Fail**: BI-Tabellen (Workstations, Print-Queues, Device-Readings) geben strukturierte Fehlermeldung zurück wenn SQL-Zugang nicht verfügbar — kein Absturz.

### Technisch
- requirements.txt: fpdf2>=2.7.0, openpyxl>=3.1.0
- reporting/query_tools.py: 10 neue Query-Funktionen (query_job_history, query_printer_history, query_user_detail, query_user_copy_detail, query_user_scan_detail, query_tree_meter, query_service_desk, query_workstation_overview, query_queue_stats, query_device_readings)
- reporting/report_engine.py: render_pdf(), render_xlsx(), 8 neue Report-Builder, zentrales _REPORT_BUILDERS-Dict (16 Einträge), _hex_to_rgb() Hilfsfunktion
- reporting/preset_templates.py: ALL_FORMATS pdf/xlsx auf available:True; alle 11 Presets mit query_type + query_params befüllt
- reporting/scheduler.py: alle 16 Query-Typen registriert, base64-Attachment-Verarbeitung für alle Formate
- web/templates/reports_form.html: Format-Hinweis aktualisiert (HTML = Body, andere = Anhang)


## 3.0.0 (2026-04-09)

### Neu — Reports & Automatisierungen (Major Feature)

- **Reports-Register (Web-UI)**: Neuer Tab "Reports" in der Navigation — vollständige CRUD-Verwaltung für Report-Templates direkt im Browser. Kein KI-Chat mehr notwendig um Reports anzulegen oder zu verwalten.
- **Preset-Bibliothek**: 18 vordefinierte Report-Vorlagen basierend auf allen 17 Seiten des offiziellen Printix PowerBI-Templates (v2025.4). 7 Presets sofort ausführbar, 11 weitere für v3.1 geplant.
- **4-Schritte-Formular**: Intuitives Formular mit Abschnitten für Grunddaten, Abfrage-Parameter (dynamisch je nach Report-Typ), Ausgabe & Empfänger, sowie Automatisierung (Schedule).
- **Ausgabeformate im UI**: Checkboxen für HTML (E-Mail-Body), CSV (Anhang), JSON (Anhang) — Mehrfachauswahl möglich. PDF/XLSX folgen in v3.1.
- **Schedule-Verwaltung**: Zeitplan direkt im Formular konfigurieren (täglich / wöchentlich / monatlich) mit Wochentag- und Uhrzeitauswahl.
- **Run-Now-Button**: Templates aus der Liste heraus sofort ausführen (▶) — Flash-Meldung zeigt Ergebnis (versendet / generiert / Fehler).
- **Per-Tenant-Filterung**: Jeder Benutzer sieht nur seine eigenen Report-Templates (owner_user_id-basiert).
- **MCP-Tool-Verbesserungen**: printix_run_report_now() akzeptiert jetzt auch Template-Namen (case-insensitiv) statt ausschließlich UUIDs; listet verfügbare Templates wenn kein Parameter angegeben.
- **i18n**: 8 neue Übersetzungsschlüssel in allen 12 Sprachen/Dialekten.

### Technisch
- reporting/preset_templates.py (NEU): 18 Preset-Definitionen mit Metadaten
- reporting/template_store.py: list_templates_by_user(user_id) ergänzt
- web/reports_routes.py (NEU): register_reports_routes() — 7 Routen
- web/templates/reports_list.html (NEU): Template-Tabelle + Preset-Bibliothek
- web/templates/reports_form.html (NEU): 4-Abschnitte-Formular
- web/templates/base.html: Reports-Link in Navigation eingefügt
- web/app.py: register_reports_routes() am Ende von create_app() eingebunden

## 2.13.0 (2026-04-09)

### Neu — Mail Delivery Event-Benachrichtigungen
- **E-Mail Benachrichtigungen Checkboxen**: Neue Sektion in den Einstellungen — Benutzer wählen pro Ereignis-Typ ob eine E-Mail versandt werden soll
  - 🚨 Kritische Log-Fehler (ERROR/CRITICAL)
  - 🖨️ Neuer Drucker in Printix erkannt
  - 📋 Neue Drucker-Queue erkannt
  - 👤 Neuer Gast-Benutzer erkannt
  - 📊 Report erfolgreich versendet
  - 🔔 Neuer MCP-Benutzer registriert (Admin-Benachrichtigung)
- **Event Poller**: Hintergrund-Job läuft alle 30 Minuten, ruft Printix API ab und erkennt neue Drucker/Queues/Gast-Benutzer; Zustand wird per Tenant in DB gespeichert (überlebt Neustarts)
- **Notify Helper**: Zentrale Hilfsfunktionen für Ereignis-Benachrichtigungen mit HTML-E-Mail-Templates pro Ereignistyp
- **User-Registrierung**: Admin erhält E-Mail-Benachrichtigung wenn neuer Benutzer sich registriert (wenn `user_registered` aktiviert)
- **Report versendet**: Bestätigungs-E-Mail nach erfolgreichem automatischem Report (wenn `report_sent` aktiviert)

### Technisch
- `db.py`: Migration fügt `notify_events` (JSON-Array) und `poller_state` (JSON-Objekt) zu `tenants` hinzu; neue `update_poller_state()` Funktion
- `reporting/notify_helper.py`: Neu — `send_event_notification()`, `get_enabled_events()`, HTML-Templates pro Ereignistyp
- `reporting/event_poller.py`: Neu — `PrintixEventPoller` mit APScheduler-Integration; `register_event_poller()` idempotent
- `reporting/log_alert_handler.py`: Prüft jetzt ob `log_error` in `notify_events` aktiv ist
- `reporting/scheduler.py`: `report_sent` Benachrichtigung nach erfolgreichem Mail-Versand
- `web/templates/settings.html`: 6 Checkboxen in neuer Sektion „E-Mail Benachrichtigungen"
- `web/app.py`: Jinja2-Filter `from_json`; `notify_*` Form-Parameter; `update_tenant_credentials()` mit `notify_events`; `user_registered`-Hook bei Registrierung
- `server.py`: `register_event_poller()` beim Server-Start

## 2.10.0 (2026-04-09)

### Neu
- **Karten-Anzahl in User-Übersicht**: Beim Laden der Benutzerliste werden die Karten-Counts jetzt parallel (max. 10 gleichzeitige Requests, 5s Timeout) von der Printix API abgerufen — zeigt echte Zahlen statt „–"
- Falls die Karten-API nicht erreichbar ist oder timeout: zeigt weiterhin „🃏 –" als Fallback

### Technisch
- `app.py`: `tenant_users` Route nutzt `ThreadPoolExecutor(max_workers=10)` + `as_completed(timeout=5)` für parallele Card-Count-Fetches
- `tenant_users.html`: Zeigt `_card_count` aus Server-Daten; fällt zurück auf „–" wenn `None`

## 2.9.0 (2026-04-09)

### Bugfixes
- **Karten-Löschen korrigiert**: Printix API gibt 405 zurück auf `DELETE /users/{uid}/cards/{cid}` — verwendet jetzt den globalen Card-API-Endpoint `DELETE /cards/{card_id}` (war vorher 404 wegen leerer ID, jetzt korrekte UUID + korrekter Endpoint)
- **Kartenzählung in User-Liste**: `list_users` API liefert kein `cards`-Feld → zeigt jetzt „🃏 –" statt irreführender „0" an; Klick auf Benutzer öffnet Detailseite mit echter Karten-Anzahl
- **Rolle in User-Liste**: verwendet jetzt `roles[0]` (Array) statt `role` (String) — konsistent mit User-Detail-Ansicht

### Technisch
- `printix_client.py`: `delete_card()` verwendet nur noch `DELETE /cards/{card_id}` (user_id-Parameter bleibt aus Kompatibilitätsgründen, wird ignoriert)
- `tenant_users.html`: Template-Fix für Kartenzählung + Rollenanzeige aus `roles`-Array

## 2.8.0 (2026-04-09)

### Neu
- **2 neue Dialekt-Sprachen**: Österreichisch (`oesterreichisch`) und Schwiizerdütsch (`schwiizerdütsch`) — vollständige Übersetzungen aller UI-Texte mit authentischen Dialektausdrücken
  - Österreichisch: Grüß Gott, Servus, Leiwand, Bittschön, Na sicher, Geh bitte!, …
  - Schwiizerdütsch: Grüezi, Sali, Merci vielmal, Charte statt Karten, Spicherä, …
- **SUPPORTED_LANGUAGES** und **LANGUAGE_NAMES** um beide Dialekte erweitert
- Sprachauswahl in der UI zeigt jetzt 12 Sprachen/Dialekte

## 2.7.0 (2026-04-09)

### Bugfixes
- **Benutzer-Detailansicht korrigiert**: Printix API gibt `{"user": {...}}` zurück — vorher wurde die äußere Hülle nicht entpackt, sodass Name, E-Mail und Rolle als leer/falsch angezeigt wurden. Jetzt wird korrekt `user.name`, `user.email` und `user.roles[0]` ausgelesen.
- **Karten-ID-Extraktion**: Printix API-Karten haben kein `id`-Feld — die UUID wird jetzt aus `_links.self.href` extrahiert (letztes URL-Segment)
- **Karten-Löschung korrigiert**: Verwendet jetzt den user-scoped Endpoint `DELETE /users/{uid}/cards/{card_id}` statt dem fehlerhaften `DELETE /cards/{card_id}` (der ohne card_id einen 404 lieferte)
- **Rollen-Badge**: `roles` ist ein Array in der API-Antwort — `roles[0]` wird jetzt korrekt für den Badge verwendet (GUEST USER lila, USER gelb)

### Technisch
- `printix_client.py`: `delete_card()` unterstützt jetzt optionalen `user_id`-Parameter für user-scoped Löschung
- `app.py`: User-Detail-Route entpackt nested API-Response; Card-IDs werden aus `_links` extrahiert

## 2.6.0 (2026-04-09)

### Neu
- **5 neue UI-Sprachen**: Niederländisch (nl), Norwegisch (no), Schwedisch (sv), Boarisch (bar) und Hessisch (hessisch) — vollständige Übersetzungen aller UI-Texte inkl. Printix-Verwaltung
- **Benutzer-Detailansicht**: Klick auf einen Benutzer öffnet Detailseite mit Karten-Verwaltung (hinzufügen/löschen), ID-Code-Generierung und Benutzer-Löschung (nur GUEST_USER)
- **Gastbenutzer anlegen**: Neuer "➕ Neuer Benutzer"-Button öffnet Formular zum Erstellen von GUEST_USER via Printix API
- **Felder Name & Firma**: Benutzer-Registrierung und Admin-Benutzerverwaltung um die Felder "Name" (full_name) und "Firma" (company) erweitert — inkl. DB-Migration für bestehende Installationen
- **🔄 Aktualisieren-Button**: Auf allen 3 Printix-Unterseiten (Drucker, Queues, Benutzer) — lädt die Liste direkt aus der Printix API neu

### Geändert
- Benutzer-Liste (Printix-Tab): Zeilen sind jetzt anklickbar → leitet zur Detailseite weiter
- GUEST_USER-Badge in lila, USER-Badge in gelb zur optischen Unterscheidung

### Technisch
- DB-Migration: `ALTER TABLE users ADD COLUMN full_name/company` bei bestehenden Instanzen (sicher, idempotent)
- FastAPI-Routen: `/tenant/users/create` vor `/tenant/users/{id}` registriert (Reihenfolge wichtig)
- Flash-Messages für Aktionen via Query-Parameter (Post-Redirect-Get)

## 2.5.0 (2026-04-09)

### Behoben
- **Log-Zeitstempel**: Uhrzeiten in der Web-UI-Logseite werden jetzt in Lokalzeit (CEST/Europe/Berlin) angezeigt statt UTC — keine 2-Stunden-Abweichung mehr.
- **Printix API Kategorie im Log war immer leer**: `printix_client.py` hat Python `logging` nicht genutzt. Jetzt wird jeder API-Aufruf (Token-Anfragen, GET/POST/Fehler/Rate-Limit) über den Logger `printix_client` geschrieben → erscheint korrekt als Kategorie „Printix API" im Log-Filter.

## 2.4.0 (2026-04-09)

### Behoben
- **Printers-Tab**: Zeigt jetzt 10 deduplizierte physische Drucker (nach `printer_id` gruppiert), statt 19 redundante Einträge. Queues desselben Druckers erscheinen als Chips in der Queue-Spalte.
- **Queues-Tab**: Alle 19 Queues korrekt mit Queue-Name, Drucker-Modell (vendor + model), Standort und Status-Dot (grün/orange/rot/grau für ONLINE/WARNING/OFFLINE/UNKNOWN).
- Template `tenant_printers.html`: Spalte "Site" → "Location" (API liefert `location`-String, kein site-Objekt); WARNING-Status (orange); Sign-Badge für `printerSignId`.
- Template `tenant_queues.html`: Status-Spalte hinzugefügt.

### Verbessert
- **MCP-Tool `printix_list_printers`**: Docstring erklärt die API-Datenstruktur explizit — Printer-Queue-Paare, Deduplizierung für Drucker-Übersicht vs. alle Queues direkt ausgeben.

## 2.3.0 (2026-04-09)

### Neu
- **Printix-Tab** (Web-UI): Neues Register „Printix" in der Navigation mit 3 Unterseiten:
  - **Drucker**: listet alle Drucker-/Queue-Einträge des Tenants mit Status und Standort
  - **Queues**: zeigt dieselben Einträge als Queue-Übersicht (Bugfix: Daten erscheinen jetzt korrekt)
  - **Benutzer & Karten**: Übersicht aller USER/GUEST_USER mit Karten-Zähler und Rolle
- **Logs-Kategorie-Filter**: Filterzeile nach Kategorie (All / Printix API / SQL / Auth / System)
  kombinierbar mit dem Level-Filter

### Geändert
- **Nav-Tab „Printix"**: ehemals „Printers/Drucker/Imprimantes/…" — jetzt sprachübergreifend
  „Printix" (generischer Name, da Tab Drucker, Queues und Benutzer enthält)
- **Sprach-Dropdown** (Nav): Umstieg von CSS-Hover auf JS-Click-Toggle — kein versehentliches
  Schließen beim Maus-Übergang zwischen Button und Dropdown mehr
- **Nav-Reihenfolge**: Logs vor Hilfe; Printix-Tab zwischen Einstellungen und Logs

### Behoben
- **Queues-Seite zeigte 0 Einträge**: Printix-API gibt `GET /printers` als flache Liste von
  Printer-Queue-Paaren zurück (kein verschachteltes `queues`-Array). Queue-IDs werden jetzt
  korrekt aus `_links.self.href` (`/printers/{id}/queues/{id}`) extrahiert.

## 1.15.0 (2026-04-08)

### Behoben
- **FreeTDS/ODBC-Treiber nicht gefunden**: HA-Base-Image ist Debian-basiert, nicht Alpine —
  `apk add freetds` hatte keinen Effekt. Fix:
  - `build.yaml` erstellt: erzwingt `ghcr.io/home-assistant/{arch}-base-debian:latest`
  - Dockerfile auf `apt-get install tdsodbc` umgestellt (registriert Treiber automatisch)
  - Fallback im Dockerfile: findet `libtdsodbc.so` per `find` wenn `odbcinst.ini` leer
  - `echo "\n"` → `printf` (Echo schrieb Literal `\n` statt Zeilenumbruch)

### Neu
- `printix_reporting_status` Tool: zeigt ODBC-Treiber, SQL-Konfiguration und Mail-Status —
  für einfache Diagnose ohne Log-Suche

### Geändert
- `sql_client.py`: robustere Treiber-Erkennung mit priorisierter Suche, direktem `.so`-Pfad
  als letztem Fallback und hilfreichen Fehlermeldungen
- FreeTDS-Verbindungsstring: Port `,1433` + `TDS_Version=7.4` (kein `Encrypt=yes` bei FreeTDS)

## 1.14.0 (2026-04-08)

### Neu — AI Reporting & Automation (v1.0)

**Datengrundlage**: Direktzugriff auf Printix Azure SQL BI-Datenbank
(`printix-bi-data-2.database.windows.net / printix_bi_data_2_1`).
Kostenformeln aus dem offiziellen Printix PowerBI-Template übernommen.

**6 neue Query-Tools** (Datenabfrage):
- `printix_query_print_stats` — Druckvolumen nach Zeitraum/User/Drucker/Standort
- `printix_query_cost_report` — Kosten mit Papier-/Toner-/Gesamtaufschlüsselung
- `printix_query_top_users`   — Nutzer-Ranking nach Volumen oder Kosten
- `printix_query_top_printers`— Drucker-Ranking nach Volumen oder Kosten
- `printix_query_anomalies`   — Ausreißer-Erkennung via Mittelwert + StdAbw
- `printix_query_trend`       — Periodenvergleich mit Delta-Prozenten

**5 neue Template-Tools** (Wiederverwendbare Reports):
- `printix_save_report_template` — Speichert vollständige Report-Definition
- `printix_list_report_templates`— Listet alle Templates
- `printix_get_report_template`  — Ruft einzelnes Template ab
- `printix_delete_report_template`— Löscht Template + Schedule
- `printix_run_report_now`       — On-demand Ausführung mit Mail-Versand

**4 neue Schedule-Tools** (Automatische Ausführung):
- `printix_schedule_report`  — Legt Cron-Job an (täglich/wöchentlich/monatlich)
- `printix_list_schedules`   — Aktive Schedules mit nächstem Run-Zeitpunkt
- `printix_delete_schedule`  — Entfernt Schedule (Template bleibt)
- `printix_update_schedule`  — Ändert Timing oder Empfänger

**Infrastruktur**:
- `src/reporting/` Modul: sql_client, query_tools, report_engine, template_store,
  scheduler, mail_client
- APScheduler (Background Thread) für zeitgesteuerte Ausführung
- Resend API für HTML-Mail-Versand
- Jinja2 HTML-Report-Template mit Branding (Firmenfarbe, Logo, Footer)
- Templates persistent in `/data/report_templates.json`
- Dynamische Datumswerte: `last_month_start`, `last_month_end`, `this_month_start`
- Neues `config.yaml`-Schema: `sql_server`, `sql_database`, `sql_username`,
  `sql_password`, `mail_api_key`, `mail_from`
- Dockerfile: FreeTDS ODBC-Treiber für Alpine Linux

## 1.13.0 (2026-04-08)

### Behoben
- **`RuntimeError: Task group is not initialized`**: `DualTransportApp` leitete
  den ASGI-`lifespan`-Scope nicht an `http_app` weiter — dadurch wurde der
  `StreamableHTTPSessionManager` des Streamable-HTTP-Transports nie gestartet.
  Fix: `lifespan`-Scope wird jetzt zuerst an `http_app` weitergeleitet, bevor
  HTTP-Requests entgegengenommen werden. Der SSE-Transport hat nur ein No-Op-
  Lifespan und benötigt keine gesonderte Behandlung.

## 1.12.0 (2026-04-02)

### Geändert
- **Dual Transport**: Server unterstützt jetzt beide MCP-Transports parallel
  - `POST /mcp` → Streamable HTTP Transport (claude.ai, neuere Clients)
  - `GET  /sse` → SSE Transport (ChatGPT, ältere Clients)
- Claude-Konnektoren-URL muss auf `/mcp` enden (statt `/sse`)
- `/favicon.ico` und `/robots.txt` werden ohne Bearer-Token-Prüfung mit 404 beantwortet (kein 401-Spam im Log mehr beim OAuth-Dialog)
- `oauth-protected-resource` Discovery zeigt jetzt `/mcp` als primären Endpunkt

## 1.11.0 (2026-04-02)

### Dokumentation / Verhalten
- **`complete_upload`**: Tool-Beschreibung erklärt jetzt explizit, dass die Datei vor dem Aufruf bereits hochgeladen sein muss. Wird `complete_upload` ohne Datei aufgerufen, entfernt das Backend den Job sofort — das ist korrektes Backend-Verhalten, kein Skill-Fehler.
- **`update_network`**: Hinweis ergänzt, dass der Update-Endpoint eine schlankere Antwort als GET liefert (site-Link fehlt). Daten sind korrekt gespeichert — für die vollständige Ansicht `get_network` aufrufen.

## 1.10.0 (2026-04-02)

### Geändert / Behoben (Delta-Test Runde 2)
- **`generate_id_code`**: Pfad war `idcode` (lowercase) — korrigiert auf `idCode` (camelCase, API-konform)
- **`change_job_owner`**: War PUT mit JSON-Body → korrigiert auf `POST /jobs/{id}/changeOwner` mit `userEmail` als `application/x-www-form-urlencoded` (laut API-Doku)
- **`update_network` Datenverlust**: PUT-Body übernahm `gateways` und `siteId` nicht aus dem GET — beides wird jetzt aus der aktuellen Netzwerkkonfiguration übernommen, damit ein Name/Subnetz-Update keine bestehenden Zuordnungen löscht

## 1.9.0 (2026-04-02)

### Geändert / Behoben
- **Bug 1 – `generate_id_code`**: Endpoint-Pfad von `/idcodes` (falsch) auf `/idcode` (korrekt, singular) korrigiert
- **Bug 2 – `update_network`**: Client liest jetzt zuerst den aktuellen Netzwerk-Stand (GET) und befüllt die vom Backend verlangten Pflichtfelder `homeOffice`, `clientMigratePrintQueues` und `airPrint` automatisch; MCP-Tool exponiert jetzt alle Felder
- **Bug 3 – `create_snmp_config`**: Version-aware Payload — V3-spezifische Felder (`privacy`, `authentication`, `securityLevel` etc.) werden nur bei `version=V3` gesendet; für V1/V2C nur Community-Strings
- **Bug 4 – `change_job_owner`**: HTTP-Methode von PATCH (405 Method Not Allowed) auf PUT korrigiert
- **Bug 5 – Job-Lifecycle 404**: `get_print_job` gibt jetzt eine erklärende Fehlermeldung bei 404; `delete_print_job` behandelt 404 als Erfolg (Job bereits entfernt)
- **Doku A – PIN-Regel**: MCP-Tool-Beschreibung für `create_user` ergänzt: PIN muss genau 4 Ziffern sein
- **Doku B – `create_group` Voraussetzung**: MCP-Tool-Beschreibung warnt jetzt, dass eine Directory-Konfiguration im Tenant erforderlich ist

## 1.8.0 (2026-04-02)

### Geändert
- Persistente Secrets-Datei `/data/mcp_secrets.json` eingeführt
- `bearer_token`, `oauth_client_id` und `oauth_client_secret` werden beim ersten Start generiert und dauerhaft gespeichert — überleben jeden Add-on-Update
- Priorität: HA-Konfigurationsfeld > gespeicherter Wert > neu generieren
- Kein erneutes Konfigurieren der App-Verbindungen (ChatGPT, Claude) mehr nötig nach Updates

## 1.7.0 (2026-04-02)

### Geändert
- Drittbibliotheken (`mcp.server.sse`, `mcp.server.lowlevel.server`, `urllib3`, `uvicorn.access`) werden auf WARNING fixiert, unabhängig vom konfigurierten `MCP_LOG_LEVEL`
- Kein Log-Spam mehr: komplette JSON-Payloads, TCP-Handshakes und HTTP-Access-Zeilen werden bei Tool-Aufrufen nicht mehr ausgegeben
- Eigene `printix.*`-Logger behalten weiterhin den konfigurierten Level (z. B. DEBUG)

## 1.6.0 (2026-04-02)

### Geändert
- `/.well-known/*` Discovery-Endpunkte werden nicht mehr mit 401 abgelehnt
- `OAuthMiddleware` beantwortet RFC 8414 (`oauth-authorization-server`) und RFC 9728 (`oauth-protected-resource`) direkt mit den korrekten Metadaten
- `BearerAuthMiddleware` lässt `/.well-known/*` ohne Bearer Token durch
- Keine Spam-Warnungen mehr im Log für ChatGPTs automatische OAuth-Discovery

## 1.5.0 (2026-04-02)

### Neu
- OAuth Client-ID und Client-Secret werden automatisch generiert wenn leer (wie Bearer Token)
- OAuth Client-ID Default: `printix-mcp-client`
- Verbindungsinfo im Log zeigt jetzt die echten OAuth-Werte zum Kopieren (kein "(aus Konfiguration)" mehr)
- Warnung im Log wenn neue OAuth-Credentials generiert wurden

## 1.4.0 (2026-04-02)

### Geändert
- Verbindungsinfo im Log zeigt jetzt ALLE ChatGPT OAuth-Felder feldgenau:
  Token-Authentifizierungsmethode (client_secret_post), Standard-/Basis-Scopes, Registrierungs-URL
- OAuth-Endpunkte (Auth-URL, Token-URL) werden immer angezeigt, auch wenn OAuth noch nicht konfiguriert
- Warnung wenn oauth_client_id/oauth_client_secret noch nicht gesetzt

## 1.3.0 (2026-04-02)

### Geändert
- Verbindungsinfo im Log zeigt jetzt Claude Web App (claude.ai → Konnektoren) statt Claude Desktop
- Beide Apps (Claude + ChatGPT) nutzen OAuth — einheitliche Darstellung im Log
- Log zeigt feldgenau was in claude.ai und ChatGPT eingetragen werden muss

## 1.2.0 (2026-04-02)

### Neu
- Konfigurationsfeld `public_url` für die öffentliche Serveradresse (z.B. Cloudflare-Domain)
- Verbindungsinformationsblock im Log beim Start: fertige Konfiguration für Claude Desktop und ChatGPT
- Log zeigt automatisch alle Endpunkte (SSE, Health, OAuth Authorize/Token)
- Wenn `public_url` leer: Fallback auf `http://<HA-IP>:8765`

## 1.1.0 (2026-04-02)

### Neu
- OAuth 2.0 Authorization Code Flow für ChatGPT und andere OAuth-Clients
- Authorize-Seite (`/oauth/authorize`) mit Bestätigungsdialog im Browser
- Token-Endpunkt (`/oauth/token`) — tauscht Code gegen Bearer Token
- Neue Konfigurationsfelder: `oauth_client_id` und `oauth_client_secret`

## 1.0.0 (2026-04-02)

### Initial Release
- Vollständiger MCP-Server für Printix Cloud Print API
- Unterstützung für Print API, Card Management API und Workstation Monitoring API
- 30+ MCP-Tools: Drucker, Jobs, Benutzer, Karten, Gruppen, Sites, Netzwerke, SNMP
- Bearer Token Authentifizierung (kompatibel mit Claude und ChatGPT)
- Auto-Generierung des Bearer Tokens beim ersten Start
- Konfigurierbares Log-Level (debug/info/warning/error/critical)
- Health-Check Endpoint unter /health (ohne Auth)
- Home Assistant Add-on mit vollständiger Konfigurationsoberfläche
- Multi-Architektur: amd64, aarch64, armv7, i386
