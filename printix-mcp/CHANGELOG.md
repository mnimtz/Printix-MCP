# Changelog

## 3.6.6 (2026-04-10)

### Bugfix: Azure SQL Auto-Pause / Transient Fault

- **Automatischer Retry bei Azure SQL Serverless Auto-Pause**: `get_connection()` versucht bis zu 3× mit 5s Pause bei transientem Fehler 40613 `"Database is not currently available"` (Serverless-Tier wacht nach Inaktivität auf). Kein manuelles Doppelklicken mehr nötig.
- **URL-Encoding für Fehlermeldungen**: Setup-Fehler werden jetzt korrekt mit `quote_plus()` in der Redirect-URL kodiert — Sonderzeichen wie `[`, `]`, `(`, `)` im FreeTDS-Fehlerstring brechen die Anzeige nicht mehr ab.

## 3.6.5 (2026-04-10)

### Bugfixes: Demo-Generierung, Report-Vorschau, SQL-ContextVar

- **Demo-Generierung — Hintergrund-Task**: `tenant_demo_generate` blockiert den HTTP-Request nicht mehr (`asyncio.create_task`). Browser-Redirect erfolgt sofort, JS pollt `/tenant/demo/status?job_id=…`. Kein Proxy-Timeout mehr (war: `await asyncio.to_thread(...)` = 20–60s Request blockiert).
- **Demo-Status-Endpoint**: Neuer `GET /tenant/demo/status` — gibt `{status, error, session_id}` zurück. Polling-JS in `tenant_demo.html` mit HA-Ingress-kompatiblem Basispfad (`window.location.pathname` statt hartkodiertem `/tenant/demo/…`). Behandelt Zustand `"unknown"` (Server-Neustart während Generierung).
- **Report-Vorschau — Datumsformat**: `_resolve_dynamic_dates()` wird jetzt in der Preview-Route aufgerufen. Symbolische Datumswerte wie `last_year_start` / `last_year_end` werden vor dem SQL-Query in `YYYY-MM-DD` aufgelöst (Fehler: `"Ungültiges Datumsformat: 'last_year_end'"`).
- **Report-Vorschau — run_query**: `run_query`-Dispatcher in `reporting/query_tools.py` hinzugefügt (fehlte → ImportError → 500-Fehler in Vorschau).
- **Report sofort ausführen — SQL-ContextVar**: `set_config_from_tenant(tenant)` wird jetzt vor `run_report_now()` aufgerufen. Behebt `"SQL nicht konfiguriert"`-Fehler beim manuellen Report-Versand.

## 3.6.0 (2026-04-10)

### Report Designer Stufe 1 — Visuelle Reports + XLSX/PDF + Vorschau

- **CSS-Balkendiagramme**: Horizontale Balkendiagramme im HTML-Report-Output — email-client-kompatibel (kein JS), erscheinen vor jeder Datentabelle. Unterstützt: print_stats, cost_report, top_users, top_printers.
- **XLSX-Output**: Excel-Export mit Branding (openpyxl) — farbige Kopfzeilen, abwechselnde Zeilenfarben, automatische Spaltenbreite. `openpyxl>=3.1.0` in requirements.txt.
- **PDF-Output**: fpdf2-basiertes PDF (Helvetica, Latin-1-kompatibel). `fpdf2>=2.7.0` in requirements.txt.
- **Report-Vorschau** (`/reports/{id}/preview`): Zeigt den generierten HTML-Report direkt im Browser — ohne Mail-Versand. Öffnet in neuem Tab mit blauem Vorschau-Banner.
- **👁 Vorschau-Button** in der Reports-Liste (neben ▶ und ✏).
- **i18n**: `rpt_preview_title` in allen 12 Sprachen ergänzt.

## 3.5.2 (2026-04-10)

### Demo-Daten UI: Performance & UX

- **asyncio.to_thread()**: Demo-Generierung läuft jetzt im Thread-Pool — uvicorn Event-Loop bleibt während der Generierung responsive (kein Browser-Timeout mehr).
- **Kleinere Defaults**: Schieberegler-Defaults reduziert (User 20→10, Drucker 6→4, Jobs/Tag 3.0→2.0); Preset-Obergrenze ebenfalls reduziert (max. 200 User / 50 Drucker).
- **Warnung bei großen Datenmengen**: JS-Schätzung zeigt vorhergesagte Job-Anzahl in Echtzeit; ab >20.000 Jobs orangefarbene Warnung.
- **i18n**: `demo_hint_large_data` in allen 12 Sprachen ergänzt (Hinweis auf lange Laufzeit bei großen Datenmengen).

## 3.5.1 (2026-04-10)

### Bugfixes & Demo-UI Verbesserungen

- **Kritischer Fix**: Demo-Daten-Generierung funktioniert jetzt korrekt mit bestehenden Printix Azure SQL-Datenbanken. Alle Custom-Tabellen liegen im `demo.*`-Schema (nicht `dbo.*`), um Konflikte mit nativen Printix-Tabellen (Liquibase-Migrations) zu vermeiden.
- **reporting.* Views**: UNION ALL-Pattern — echte `dbo.*`-Daten und Demo-`demo.*`-Daten werden korrekt zusammengeführt. Demo-Daten erscheinen nur wenn aktive Sessions für den Tenant existieren.
- **Batch-Size**: Insert-Batch-Größe von 500 auf 2000 erhöht (~4× schnellere Generierung).
- **Button „Alle Demo-Daten löschen"**: Neuer globaler Löschen-Button in der Demo-UI — funktioniert auch ohne bestehende Sessions (z.B. nach fehlgeschlagener Generierung oder für sauberes Neu-Deployment).
- **Rollback-All API**: Neues `rollback_demo_all(tenant_id)` — löscht alle Demo-Daten des Tenants über alle Tags/Sessions hinweg.
- **i18n**: `demo_btn_rollback_all` + `demo_confirm_rollback_all` in allen 12 Sprachen ergänzt.

## 3.5.0 (2026-04-10)

### Demo-Daten Web-UI & Reporting-Views

- **Demo-Daten Register (Web-UI)**: Neuer Tab „Demo-Daten" in der Tenant-Navigation (Drucker / Queues / Benutzer / Demo-Daten). Vollständige Verwaltung von Demo-Sessions direkt im Browser ohne KI-Chat.
- **Hinweis-Box**: Prominenter Hinweis im Demo-Tab erklärt, dass Demo-Daten ausschließlich in der Azure SQL-Datenbank gespeichert werden und in der Printix-Oberfläche nicht sichtbar sind.
- **Demo generieren**: Formular mit Schiebereglern für User-Anzahl, Drucker-Anzahl, Zeitraum und Sprachauswahl. Fortschrittsoverlay während der Generierung.
- **Schema einrichten**: Button zum Erstellen/Aktualisieren aller Tabellen und `reporting.*`-Views mit einem Klick.
- **Session-Verwaltung**: Tabellarische Übersicht aller Demo-Sessions mit Status, Statistiken und Löschen-Button (entfernt Demo-Daten aus allen Tabellen).
- **reporting.* SQL-Views**: `setup_schema()` erstellt jetzt automatisch `reporting`-Schema mit 8 Views (`v_tracking_data`, `v_jobs`, `v_users`, `v_printers`, `v_networks`, `v_jobs_scan`, `v_jobs_copy`, `v_jobs_copy_details`). Views filtern: echte Daten immer sichtbar, Demo-Daten nur wenn aktive Demo-Sessions für den Tenant existieren.
- **Transparente Report-Integration**: Alle Report-Abfragen in `query_tools.py` nutzen automatisch `reporting.v_*` wenn Views verfügbar sind — Fallback auf `dbo.*` für ältere Setups. Demo-Daten erscheinen so nahtlos in allen BI-Reports.
- **i18n**: Alle Demo-Tab-Texte in 12 Sprachen (DE, EN, FR, IT, ES, NL, NO, SV, Bairisch, Hessisch, Österreichisch, Schwiizerdütsch). Bugfix: Fehlende `demo_lbl_user`- und `demo_progress_*`-Schlüssel in EN-, NL- und NO-Sektionen ergänzt (waren versehentlich nur in DE eingefügt worden).

## 3.3.0 (2026-04-09)

## 3.2.0 (2026-04-09)

### Reports — Erweiterungen

- **Logo-URL im Report-Header**: Neues Feld „Logo-URL" im Reports-Formular — Bild wird oben rechts im HTML-Report-Header angezeigt. URL wird in der Template-DB gespeichert (`layout.logo_url`).
- **Erweiterter Datumspicker**: Start- und Enddatum bieten jetzt alle 11 Preset-Werte (letztes Jahr, letztes Quartal, letzte Woche, u.v.m.) plus eine „Benutzerdefiniert"-Option mit individuellem `<input type="date">`.
- **Mehrsprachigkeit (i18n)**: Alle Texte im Reports-Register (Formular, Liste, Abschnittsnamen, Labels, Buttons, Datums-Presets, Flash-Meldungen) nutzen jetzt das i18n-System — wechseln mit der UI-Sprache. DE und EN vollständig übersetzt.
- **CSV-Fallback**: Leere CSV-Datei wird nicht mehr übersprungen — stattdessen wird eine Hinweis-Zeile eingefügt (`Keine Daten im abgefragten Zeitraum`).

## 3.1.0 (2026-04-09)

### Fehlerbehebungen & Erweiterungen

- **FreeTDS-Fix**: `_fmt_date()` gibt jetzt Python `date`-Objekte zurück statt Strings — verhindert SQL Server Error 241 (Datumskonvertierung schlägt fehl bei FreeTDS-Verbindungen).
- **PDF/XLSX-Generierung**: `render_pdf()` (fpdf2) und `render_xlsx()` (openpyxl) hinzugefügt — vollständige Reports mit Kopfzeile, KPI-Karten und Tabellen.
- **PDF-Sonderzeichen-Fix** (`_pdf_safe()`): Em-Dash, En-Dash und andere Nicht-Latin-1-Zeichen werden vor der PDF-Ausgabe ersetzt — verhindert `FPDFUnicodeEncodingException`.
- **Anhänge in E-Mails**: Alle Formate (CSV, JSON, PDF, XLSX) werden als Base64-Anhänge mit korrektem `content_type` versendet — behebt fehlendes CSV/PDF in E-Mail-Anhängen.
- **Betreff-Platzhalter**: Neue Funktion `_resolve_subject()` löst `{year}`, `{month}`, `{month_name}`, `{quarter}`, `{period}` im Betreff auf.
- **Dynamische Datumswerte** erweitert: `last_year_start/end`, `this_year_start`, `last_week_start/end`, `last_quarter_start/end` jetzt verfügbar.
- **UI: PDF/XLSX-Checkboxen** in Reports-Formular ergänzt (Erstellen + Bearbeiten).

## 3.0.0 (2026-04-09)

### Neu — Reports & Automatisierungen (Major Feature)

- **Reports-Register (Web-UI)**: Neuer Tab "Reports" in der Navigation — vollständige CRUD-Verwaltung für Report-Templates direkt im Browser. Kein KI-Chat mehr notwendig um Reports anzulegen oder zu verwalten.
- **Preset-Bibliothek**: 18 vordefinierte Report-Vorlagen basierend auf allen 17 Seiten des offiziellen Printix PowerBI-Templates (v2025.4). 7 Presets sofort ausführbar, 11 weitere für v3.1 geplant.
- **4-Schritte-Formular**: Intuitives Formular mit Abschnitten für Grunddaten, Abfrage-Parameter (dynamisch je nach Report-Typ), Ausgabe & Empfänger, sowie Automatisierung (Schedule).
- **Ausgabeformate im UI**: Checkboxen für HTML (E-Mail-Body), CSV (Anhang), JSON (Anhang) — Mehrfachauswahl möglich. PDF/XLSX folgen in v3.1.
- **Schedule-Verwaltung**: Zeitplan direkt im Formular konfigurieren (täglich / wöchentlich / monatlich) mit Wochentag- und Uhrzeitauswahl.
- **Run-Now-Button**: Templates aus der Liste heraus sofort ausführen (▶) — Flash-Meldung zeigt Ergebnis (versendet / generiert / Fehler).
- **Per-Tenant-Filterung**: Jeder Benutzer sieht nur seine eigenen Report-Templates (owner_user_id-basiert).
- **MCP-Tool-Verbesserungen**: `printix_run_report_now()` akzeptiert jetzt auch Template-Namen (case-insensitiv) statt ausschließlich UUIDs; listet verfügbare Templates wenn kein Parameter angegeben.
- **i18n**: 8 neue Übersetzungsschlüssel in allen 12 Sprachen/Dialekten (nav_reports, reports_title, reports_new, reports_saved, reports_deleted, reports_run_ok, reports_run_error, reports_no_templates).

### Technisch
- `reporting/preset_templates.py` (NEU): 18 Preset-Definitionen mit Metadaten (icon, PBI-Seite, query_type, query_params, schedule_suggestion, tag, available-Flag)
- `reporting/template_store.py`: `list_templates_by_user(user_id)` ergänzt für per-Tenant-Filterung
- `web/reports_routes.py` (NEU): `register_reports_routes()` — 7 Routen (GET+POST /reports, /reports/new, /reports/{id}/edit, POST /reports/{id}/run, /reports/{id}/delete)
- `web/templates/reports_list.html` (NEU): Template-Tabelle + Preset-Bibliothek mit Tag-Gruppen
- `web/templates/reports_form.html` (NEU): 4-Abschnitte-Formular mit dynamischer Query-Parameter-Anzeige (JavaScript switchQueryType)
- `web/templates/base.html`: Reports-Link in Navigation eingefügt
- `web/app.py`: `register_reports_routes()` am Ende von `create_app()` eingebunden

## 2.11.0 (2026-04-09)

### Bugfixes
- **E-Mail-Versand repariert**: `mail_client.py` las bisher `MAIL_API_KEY` aus der Umgebungsvariablen — die aber nie gesetzt wird, da Credentials in der SQLite-DB liegen. Jetzt werden API-Key und Absender direkt aus dem Tenant-Kontext übergeben.
- **Karten-Löschung korrigiert (v2.9.0-Nachfolge)**: `DELETE /users/{uid}/cards/{cid}` liefert 405 Method Not Allowed — der globale Endpoint `DELETE /cards/{card_id}` wird jetzt ausschließlich genutzt.

### Neu
- **Log-Alert-E-Mails**: Kritische Logs (WARNING / ERROR / CRITICAL, konfigurierbar) werden automatisch per E-Mail versendet — pro Tenant konfigurierbar in den Einstellungen (Empfänger + Mindest-Level). Rate-Limiting: max. 1 Alert alle 5 Minuten pro Tenant.
- **Report-Owner**: Gespeicherte Report-Templates speichern jetzt die `owner_user_id` des erstellenden Tenants — der Hintergrund-Scheduler kann damit auch ohne Request-Kontext die richtigen Mail-Credentials aus der DB laden.
- **DB-Migration**: Tenants-Tabelle um `alert_recipients` und `alert_min_level` erweitert (sicher, idempotent via PRAGMA table_info).

### Technisch
- `reporting/mail_client.py`: `send_report()` und `send_alert()` akzeptieren optionale `api_key`/`mail_from`-Parameter mit Priorität: explizit → Modul-Override → os.environ
- `reporting/scheduler.py`: `run_report_now()` nimmt `mail_api_key`/`mail_from` entgegen; `_run_report_job()` lädt Credentials über `owner_user_id` aus der DB (`_load_tenant_mail_credentials()`)
- `reporting/template_store.py`: Neues Feld `owner_user_id` im Template-Schema
- `reporting/log_alert_handler.py`: Neuer `PrintixAlertHandler` — logging.Handler-Subklasse mit Rekursionsschutz, Threading-Lock und Rate-Limiting
- `db.py`: `update_tenant_credentials()` und `get_tenant_full_by_user_id()` um Alert-Felder erweitert; Migration für bestehende DBs
- `server.py`: Alert-Handler wird beim Laden des Reporting-Moduls registriert; `printix_run_report_now()` gibt Mail-Credentials aus Tenant-Kontext weiter; `printix_save_report_template()` speichert `owner_user_id`

## 2.8.0 (2026-04-09)

### Neu
- **2 neue Dialekt-Sprachen**: Österreichisch (`oesterreichisch`) und Schwiizerdütsch (`schwiizerdütsch`) — vollständige Übersetzungen aller UI-Texte mit authentischen Dialektausdrücken
  - Österreichisch: Grüß Gott, Servus, Leiwand, Bittschön, Pfiat di, Na sicher, Geh bitte!, …
  - Schwiizerdütsch: Grüezi, Sali, Merci vielmal, Uf Wiederluege, Charte statt Karten, Spicherä, …
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
- **Sprach-Dropdown** (Nav): Umstieg von CSS-Hover auf JS-Click-Toggle
- **Nav-Reihenfolge**: Logs vor Hilfe; Printix-Tab zwischen Einstellungen und Logs

### Behoben
- **Queues-Seite zeigte 0 Einträge**: Printix-API gibt `GET /printers` als flache Liste von
  Printer-Queue-Paaren zurück. Queue-IDs werden jetzt korrekt aus `_links.self.href` extrahiert.

## 2.1.0 (2026-04-09)

### Neu — EFIGS Mehrsprachigkeit + Benutzerverwaltung 2.0

**Mehrsprachigkeit (EFIGS)**
- `src/web/i18n.py`: Vollständige Übersetzungen in DE, EN, FR, IT, ES
- Language-Switcher in der Navigation (alle Seiten)
- Automatische Spracherkennung via `Accept-Language`-Header
- Sprachauswahl wird in der Session gespeichert und bleibt nach Logout erhalten
- `_()` Übersetzungsfunktion in allen Templates verfügbar

**Admin: Vollständige Benutzerverwaltung**
- Neuer User direkt anlegen (ohne Wizard): `GET/POST /admin/users/create`
- Benutzer bearbeiten (Name, E-Mail, Status, Admin-Flag): `GET/POST /admin/users/{id}/edit`
- Passwort zurücksetzen (Admin): `POST /admin/users/{id}/reset-password`
- Benutzer löschen (inkl. Tenant): `POST /admin/users/{id}/delete`
- Server-Einstellungen (Base URL): `GET/POST /admin/settings`

**Self-Service für Benutzer**
- Einstellungsseite: Printix API-Credentials, SQL, Mail bearbeiten: `GET/POST /settings`
- OAuth-Secret neu generieren (AJAX): `POST /settings/regenerate-oauth`
- Passwort ändern (mit Verifikation): `GET/POST /settings/password`
- Hilfeseite mit personalisierten Verbindungsdaten: `GET /help`

**Dashboard-Verbesserungen**
- Bearer Token direkt im Dashboard sichtbar und kopierbar
- Links zu Einstellungen und Hilfe im Dashboard

**Base-URL konfigurierbar über Web-UI**
- `db.py`: Neue `settings`-Tabelle (`get_setting` / `set_setting`)
- Admin kann die öffentliche URL in der Web-UI setzen (überschreibt `MCP_PUBLIC_URL` ENV)

### Geändert
- `config.yaml`: Version 2.1.0
- `run.sh`: Banner auf v2.1.0
- Alle Templates: i18n-Strings via `_()`, Language-Switcher in `base.html`
- `admin_users.html`: Edit- und Delete-Links hinzugefügt
- `dashboard.html`: Bearer Token + Schnellzugriff auf Einstellungen/Hilfe

## 2.0.1 (2026-04-09)

### Bugfixes

- **`requirements.txt`**: `starlette<1.0.0` hinzugefügt — Starlette 1.0.0 hat einen
  Breaking Change (`TypeError: unhashable type: 'dict'` in `TemplateResponse`), der die
  Web-UI lautlos zum Absturz brachte.
- **`run.sh`**: `WEB_PORT` auf festen Wert `8080` gesetzt — zuvor wurde der externe
  Host-Port aus der HA-Konfiguration als interner Container-Port verwendet, wodurch
  uvicorn auf dem falschen Port lauschte und die Web-UI nicht erreichbar war.

## 2.0.0 (2026-04-08)

### Architektur-Upgrade: Multi-Tenant

Vollständige Umstellung auf ein Multi-Tenant-Modell. Alle Credentials werden nicht
mehr in der HA-Konfiguration hinterlegt, sondern in einer verschlüsselten SQLite-Datenbank
verwaltet. Mehrere Benutzer können sich registrieren und jeweils ihre eigene Printix-Instanz
über denselben MCP-Server betreiben.

### Neu

**Web-Verwaltungsoberfläche (Port 8080)**
- 4-Schritt-Registrierungs-Wizard: Account → Printix API-Credentials → Optional (SQL + Mail) → Zusammenfassung
- Dashboard: zeigt Bearer Token, OAuth-Credentials und Verbindungsanleitung
- Admin-Bereich: Benutzer genehmigen / sperren, Audit-Log einsehen
- Erster Benutzer wird automatisch Admin und genehmigt

**SQLite Multi-Tenant Store (`/data/printix_multi.db`)**
- Tabellen: `users`, `tenants`, `audit_log`
- Alle Secrets (Printix API-Keys, SQL-Passwörter, Bearer Token, OAuth-Secret) mit Fernet verschlüsselt
- Fernet-Schlüssel wird beim ersten Start generiert und in `/data/fernet.key` gespeichert
- Passwörter mit bcrypt gehasht

**Pro-Tenant automatisch generierte Credentials**
- `bearer_token` — 48-Byte URL-safe Token
- `oauth_client_id` — `px-` + 8 Hex-Bytes
- `oauth_client_secret` — 32-Byte URL-safe Secret

**Multi-Tenant Request-Routing**
- `BearerAuthMiddleware` sucht Tenant anhand Bearer Token in der DB
- ContextVars `current_tenant` + `current_sql_config` pro Request gesetzt
- `PrintixClient` wird per Request aus `current_tenant` instantiiert (kein Singleton mehr)
- `sql_client.py` liest SQL-Credentials aus `current_sql_config` ContextVar

**Admin-Approval-Workflow**
- Neue Benutzer landen im Status `pending` und werden im Audit-Log erfasst
- Admin kann über Web-UI freischalten oder sperren
- Genehmigter Benutzer erhält Zugang zu Dashboard mit seinen Credentials

### Geändert

- `config.yaml`: Credential-Felder entfernt, nur noch `mcp_port`, `web_port`, `public_url`, `log_level`
- `run.sh`: Startet Web-UI (Port 8080) im Hintergrund + MCP-Server im Vordergrund; generiert Fernet-Key
- `oauth.py`: Vollständig DB-gestützt — kein statisches Client-Secret mehr
- `auth.py`: Kein Token-Parameter mehr; Tenant-Lookup dynamisch aus DB
- `Dockerfile`: Ports 8765 + 8080 exposed
- `requirements.txt`: `fastapi`, `python-multipart`, `itsdangerous`, `cryptography`, `bcrypt` ergänzt

### Migration von v1.x

v1.x-Credentials (aus `mcp_secrets.json` oder HA-Konfiguration) werden nicht automatisch
übernommen. Nach dem Update auf v2.0.0:
1. Web-UI öffnen: `http://<HA-IP>:8080`
2. Ersten Benutzer registrieren (wird automatisch Admin)
3. Printix API-Credentials im Wizard eintragen
4. Bearer Token + OAuth-Credentials aus dem Dashboard in claude.ai / ChatGPT eintragen

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
