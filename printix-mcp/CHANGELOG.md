# Changelog

## 4.3.3 (2026-04-12) — Dashboard, Fleet Health, Sustainability, Forecast

### Feature — Live Dashboard
- **KPI-Kacheln**: Druckvolumen heute/Woche/Monat, Farbanteil, Duplex-Rate, aktive Drucker
- **Sparkline**: Letzte 7 Tage als SVG-Linienchart
- **Umweltbilanz**: CO2, Bäume, Papier, Wasser, Energie auf einen Blick
- **Prognose**: Trend-Pfeil + erwartetes Volumen nächster Monat
- **Auto-Refresh**: JSON-Endpunkt `/dashboard/data` für live KPI-Updates
- Verbindungsdaten als aufklappbarer Bereich (statt Hauptinhalt)

### Feature — Fleet Health Monitor (`/fleet`)
- **Neues Hauptregister** in der Navigation
- **Drucker-Statusgrid**: Karten mit Ampel (grün/gelb/rot/grau)
- **Fleet-KPIs**: Gesamt, Heute aktiv, Inaktiv >7 Tage, Ø Auslastung
- **Warnungen**: Automatische Alerts für inaktive Drucker
- **Filter**: Suche + Status-Filter (Alle/Aktiv/Warnung/Kritisch)
- Daten: Printix API (live) + Azure SQL (historisch)

### Feature — Sustainability Report (`/reports/sustainability`)
- **Infografik-Seite**: CO2, Bäume, Wasser, Energie als große Zahlen
- **Äquivalenzen**: "X km nicht gefahren", "X Badewannen Wasser"
- **Duplex-Analyse**: Visueller Balken mit Einsparungen
- **Monatlicher Verlauf**: CSS-Balkenchart der Einsparungen
- Zeitraum-Filter (Standard: aktuelles Jahr)

### Feature — Forecast / Prognose
- **Lineare Regression** in `query_forecast()` (reine Python-Implementierung)
- Historische Daten + projizierte Werte für nächsten Zeitraum
- R²-Konfidenzwert, Trend-Erkennung (steigend/sinkend/stabil)
- Integriert in Dashboard-Prognose-Karte

### i18n
- ~65 neue Keys × 14 Sprachen für alle neuen Features

---

## 4.3.2 (2026-04-12) — Entra Login Fixes

### Fix — Redirect URI Mismatch (AADSTS50011)
- **Redirect URI wurde nicht gespeichert**: Bei Auto-Setup wurde die URI aus dem
  aktuellen Request abgeleitet (z.B. lokale IP), beim Login dann aber von der
  öffentlichen URL (z.B. `printix.cloud`). Ergebnis: `AADSTS50011 redirect_uri mismatch`.
  Fix: Redirect URI wird bei Auto-Setup in der DB gespeichert und beim Login
  immer konsistent verwendet. Auf der Admin-Seite jetzt editierbar.

### Fix — Auto-Setup nicht wiederholbar
- **Setup-Button verschwand** nach erfolgreicher Einrichtung. Jetzt als
  aufklappbarer Bereich verfügbar: _"Erneut einrichten / Auto-Setup wiederholen..."_

### Fix — E-Mail-Verknüpfung case-sensitive
- **`Marcus@nimtz.email` ≠ `marcus@nimtz.email`**: Entra-Login erstellte einen
  Duplikat-Account statt den bestehenden zu verknüpfen. Fix: `COLLATE NOCASE`
  für E-Mail-Vergleich in `get_or_create_entra_user()`.

---

## 4.3.1 (2026-04-12) — Bugfixes + Cockney & Southern US

### Fix — Entra SSO Login Callback
- **Redirect URI zeigte auf MCP-Port**: `_get_base_url()` nutzte `public_url`
  (MCP-Server), aber der Entra-Callback lebt in der Web-UI. Ergebnis war
  `401 Missing or invalid Authorization header` beim Login-Versuch.
  Fix: URL wird jetzt aus dem Request-Host-Header abgeleitet (z.B. `:8010`).
- **E-Mail-Verknuepfung** funktioniert damit automatisch: bestehende Benutzer
  mit gleicher E-Mail werden beim ersten Entra-Login verknuepft.

### Fix — Event Poller: `update_poller_state` fehlte
- **`cannot import name 'update_poller_state' from 'db'`**: Fehlte komplett.
  Neue Spalte `poller_state` in der Tenants-Tabelle + neue Funktion
  `update_poller_state(user_id, state)` in db.py. Der Event Poller (alle 30 Min)
  funktioniert jetzt ohne Fehler.

### Fix — Report: Delta-Spalte zeigte Raw-HTML
- **`<span class="delta-neg">` als Text**: `_fmt_delta()` gibt jetzt
  `markupsafe.Markup` zurueck, damit `autoescape=True` den HTML-Code
  nicht escaped. Trend-Reports zeigen jetzt korrekt gefaerbte Pfeile.

### Feature — 2 neue Sprachen
- **Cockney** (UK East London): "'Elp", "Sorted", "Yer account", "innit"
- **US Southern** (Deep South/Texas): "Y'all's", "fixin' to", "howdy", "much obliged"
- Jeweils 683 Keys — vollstaendige UI-Abdeckung.
- Gesamt: **14 Sprachen** in der Web-Oberflaeche.

### Fix — Device Code Flow Client-ID
- Microsoft Graph CLI Tools Client-ID (`14d82eec-...`) statt Azure CLI
  (`04b07795-...`), die keine Graph API Scopes unterstuetzte.

### Touched Files
- `src/web/app.py` — `_get_base_url()` nutzt Request statt `public_url`
- `src/db.py` — `poller_state` Spalte + `update_poller_state()` Funktion
- `src/reporting/report_engine.py` — `_fmt_delta()` mit `Markup()`
- `src/web/i18n.py` — Cockney + US Southern (2 x 683 Keys)
- `src/entra.py` — Graph CLI Client-ID
- `config.yaml` / `run.sh` / `src/server.py` — Version 4.3.1

---

## 4.3.0 (2026-04-12) — Device Code Flow: Echtes Ein-Klick Entra Auto-Setup

### Feature — Device Code Flow fuer Entra SSO App-Registrierung
- **Vollautomatisches Setup**: Admin klickt "Automatisch einrichten", gibt
  einen Code bei `microsoft.com/devicelogin` ein, meldet sich an und erteilt
  Consent. Die SSO-App wird via Graph API erstellt, Client-ID, Secret und
  Tenant-ID automatisch gespeichert. Keine Bootstrap-App mehr noetig.
- **Azure CLI Client-ID**: Nutzt Microsofts well-known Azure CLI Client-ID
  (`04b07795-a710-4f83-a962-d65c70e4e3c2`) fuer den Device Code Flow.
  Unterstuetzt Application.ReadWrite.All und Organization.Read.All Scopes.
- **Neue API-Endpunkte**: `POST /admin/entra/device-code` (startet Flow) und
  `GET /admin/entra/device-poll` (pollt Token-Status + erstellt App bei Erfolg).
- **Neues UI**: Device Code Box mit grossem Code-Display, Verification-Link
  (oeffnet automatisch in neuem Tab), Live-Polling-Spinner, Erfolgs- und
  Fehler-Anzeige mit Retry-Button.
- **11 neue i18n Keys** fuer Device Code Flow in allen 12 Sprachen
  (`entra_dc_step1`, `entra_dc_step2`, `entra_dc_waiting`, `entra_dc_success`,
  `entra_dc_success_sub`, `entra_dc_expired`, `entra_dc_error`,
  `entra_dc_error_declined`, `entra_dc_error_app`, `entra_dc_retry`,
  `entra_dc_starting`).

### Breaking — Bootstrap-App entfernt
- `entra_bootstrap_client_id` und `entra_bootstrap_client_secret` aus
  config.yaml entfernt — nicht mehr benoetig.
- `ENTRA_BOOTSTRAP_CLIENT_ID`/`ENTRA_BOOTSTRAP_CLIENT_SECRET` Env-Vars
  aus run.sh entfernt.
- Bootstrap-Funktionen (`get_bootstrap_config`, `is_bootstrap_available`,
  `build_auto_setup_url`, `exchange_bootstrap_code`) durch Device Code
  Flow ersetzt (`start_device_code_flow`, `poll_device_code_token`).

### Touched Files
- `src/entra.py` — Device Code Flow Funktionen, Bootstrap entfernt
- `src/web/app.py` — Neue JSON-API-Routen, Bootstrap-Routen entfernt
- `src/web/templates/admin_settings.html` — Device Code UI + JS
- `src/web/i18n.py` — 11 neue Keys x 12 Sprachen = 132 neue Eintraege
- `config.yaml` — Bootstrap-Options entfernt, Version 4.3.0
- `run.sh` — Bootstrap-Env-Vars entfernt, Version 4.3.0
- `src/server.py` — Version 4.3.0

---

## 4.2.2 (2026-04-12) — „i18n + Tenant-Isolation"

### Fix — Tenant-Isolation: Demo-Status-Endpoint
- **`/tenant/demo/status`** prüft jetzt die `user_id` im Job-Dict —
  ein Benutzer kann nicht mehr den Demo-Generierungs-Status eines anderen
  Benutzers abfragen. `_demo_jobs` speichert jetzt `user_id` bei Erstellung.

### Enhancement — Vollständige i18n für Entra-Einstellungen
- **43 neue Übersetzungsschlüssel** für die gesamte Entra-ID-Konfiguration
  in allen 12 Sprachen (de, en, fr, it, es, nl, no, sv, bar, hessisch,
  oesterreichisch, schwiizerdütsch).
- **admin_settings.html**: Alle hartkodierten Strings durch `{{ _('key') }}`
  Aufrufe ersetzt. JavaScript-Fehlermeldungen via `data-*` Attribute aus
  dem Übersetzungssystem gespeist.
- Neue Keys: `entra_title`, `entra_subtitle`, `entra_toggle`,
  `entra_auto_setup_*`, `entra_tab_*`, `entra_cli_*`, `entra_json_*`,
  `entra_manual_*`, `entra_tenant_*`, `entra_client_*`, `entra_secret_*`,
  `entra_redirect_*`, `entra_auto_approve*`, `entra_status_*`,
  `admin_settings_sub`, `admin_current_url`.

### Touched Files
- `src/web/app.py` — Tenant-Isolation-Fix in `/tenant/demo/status`
- `src/web/i18n.py` — 43 neue Keys × 12 Sprachen = 516 neue Einträge
- `src/web/templates/admin_settings.html` — Alle Strings internationalisiert
- `config.yaml` / `run.sh` / `src/server.py` — Version 4.2.2

---

## 4.2.1 (2026-04-12) — „Entra Ein-Klick-Setup"

### Feature — Ein-Klick Entra Auto-Setup
- **Bootstrap-App-Flow**: Neuer OAuth-basierter Auto-Setup — Admin klickt
  „Mit Microsoft anmelden & App erstellen", meldet sich bei Microsoft an,
  erteilt Consent, und die SSO-App wird automatisch via Graph API erstellt.
  Client-ID, Secret und Tenant-ID werden automatisch gespeichert.
- **Bootstrap-Konfiguration**: Neue Add-on-Options `entra_bootstrap_client_id`
  und `entra_bootstrap_client_secret` in config.yaml. Einmal eine „Setup Helper"-App
  registrieren, dann können alle Admins per Klick einrichten.
- **Neue Routen**: `GET /admin/entra/auto-setup` (startet OAuth-Flow) und
  `GET /admin/entra/auto-callback` (verarbeitet Callback, erstellt App).
- **entra.py erweitert**: `get_bootstrap_config()`, `is_bootstrap_available()`,
  `exchange_bootstrap_code()` — separater Token-Exchange mit Bootstrap-Credentials.
  `auto_register_app()` verbessert: ermittelt Tenant-ID automatisch via Graph API.
- **UI-Redesign**: Setup-Wizard zeigt Ein-Klick-Button prominent wenn Bootstrap
  konfiguriert ist. CLI-Script und manuelle Anleitung als Fallback darunter.
  Setup-Bereich verschwindet automatisch wenn Entra bereits konfiguriert ist.

### Touched Files
- `config.yaml` — Bootstrap-App-Options + Version 4.2.1
- `run.sh` — Export der Bootstrap-Env-Vars
- `src/entra.py` — Bootstrap-Flow-Funktionen, verbessertes auto_register_app()
- `src/web/app.py` — Auto-Setup-Routen + bootstrap_available im Template-Kontext
- `src/web/templates/admin_settings.html` — Komplettes Redesign des Entra-Setup-Bereichs

---

## 4.2.0 (2026-04-12) — „AI Report Designer + Entra Auto-Setup"

### Feature — Entra ID Automatische Einrichtung
- **Auto-Setup-Wizard** in Admin-Settings: Azure CLI Script (PowerShell + Bash) erstellt
  die App-Registrierung automatisch. JSON-Ausgabe einfach einfügen → Felder werden befüllt.
- Tab-UI: „Automatisch einrichten" vs. „Manuell konfigurieren" mit Script-Umschalter.
- Copy-Buttons für Scripts, JSON-Paste mit Validierung und Auto-Fill.

### Feature — Erweiterte MCP Report-Design-Tools
- **`printix_list_design_options()`** — Neues MCP-Tool: listet alle verfügbaren Themes,
  Chart-Typen, Fonts, Header-Varianten, Dichten, Währungen, Logo-Positionen und Query-Typen.
  Ermöglicht der KI, dem Benutzer Design-Optionen vorzuschlagen.
- **`printix_preview_report()`** — Neues MCP-Tool: generiert eine vollständige Report-Vorschau
  mit eingebetteten SVG-Charts direkt im Chat. Unterstützt Ad-hoc-Modus (query_type + Datum)
  und Template-Modus (report_id). Alle Layout-Parameter einstellbar.
- **`printix_query_any()`** — Neues MCP-Tool: universeller Query-Zugang für alle 22
  Report-Typen (Stufe 1 + 2), inkl. printer_history, device_readings, job_history,
  user_activity, sensitive_documents, dept_comparison, waste_analysis, color_vs_bw,
  duplex_analysis, paper_size, service_desk, fleet_utilization, sustainability,
  peak_hours, cost_allocation.
- **`printix_save_report_template()`** — Erweitert um 8 neue Design-Parameter:
  `theme_id`, `chart_type`, `header_variant`, `density`, `font_family`, `currency`,
  `show_env_impact`, `logo_position`. Templates können jetzt vollständig per KI-Chat
  designed und gespeichert werden.

### Workflow: Reports per KI-Chat designen
1. `printix_list_design_options()` → Optionen anzeigen
2. `printix_preview_report(theme_id="executive_slate", chart_type="donut")` → Vorschau
3. Iterieren bis zufrieden
4. `printix_save_report_template(...)` → Als wiederverwendbares Template speichern

### Touched Files
- `src/server.py` — 3 neue MCP-Tools + erweiterte save_report_template-Parameter
- `src/web/templates/admin_settings.html` — Entra Auto-Setup-Wizard mit Script-Generator
- `config.yaml` / `run.sh` — Version-Bump auf 4.2.0

---

## 4.1.0 (2026-04-12) — „Entra ID (Azure AD) SSO"

### Feature — Entra ID Single Sign-On
- **Neues Modul `src/entra.py`** — Entra ID (Azure AD) OAuth2 Authorization Code Flow für Web-Login.
  Multi-Tenant-fähig: eine App-Registration in einem beliebigen Entra-Tenant, Login für Benutzer
  aus jedem Entra-Tenant möglich.
- **Admin-Settings** (`/admin/settings`) — neue Sektion „Entra ID — Single Sign-On":
  - Entra Tenant-ID, Client-ID, Client-Secret (Fernet-verschlüsselt)
  - Toggle: Entra-Login aktivieren/deaktivieren
  - Toggle: Neue Entra-Benutzer automatisch freischalten (Standard: aus → pending)
  - Setup-Anleitung mit direktem Link zum Azure Portal für App-Registrierung
  - Redirect-URI wird automatisch generiert und mit Copy-Button angezeigt
- **Login-Seite** — „Mit Microsoft anmelden"-Button mit Microsoft-Logo (SVG),
  erscheint nur wenn Entra in Admin-Settings aktiviert und konfiguriert ist.
  Bestehendes Username/Passwort-Login bleibt parallel verfügbar.
- **Auth-Flow**: `GET /auth/entra/login` → Microsoft-Login → `GET /auth/entra/callback` →
  User wird per Entra Object-ID oder E-Mail dem lokalen Account zugeordnet (oder neu angelegt).
  CSRF-Schutz via State-Parameter in der Session.
- **DB-Migration**: `users.entra_oid`-Spalte (automatisch beim Start, idempotent) +
  Index für schnellen Lookup. Neue Funktion `get_or_create_entra_user()`.
- **Keine neuen Dependencies** — nutzt `requests` (bereits vorhanden) für Token-Exchange,
  JWT-Payload wird ohne externe Bibliothek dekodiert (Transport-Level-Sicherheit über HTTPS).

### Touched Files
- `src/entra.py` (neu) — Entra-Konfiguration, OAuth-Flow, JWT-Decode, Graph-API-Helper
- `src/db.py` — `entra_oid`-Migration, `get_or_create_entra_user()`
- `src/web/app.py` — Entra-Routen, erweiterte Admin-Settings
- `src/web/templates/admin_settings.html` — Entra-Konfigurationssektion
- `src/web/templates/login.html` — Microsoft-Login-Button

## 4.0.3 (2026-04-12) — „Mobile Responsive UI"

### UI — Mobile & Smartphone Responsive
- **base.html** — Umfassende `@media (max-width: 768px)` und `@media (max-width: 480px)` Breakpoints:
  - Hamburger-Menü + Mobile-Drawer statt Desktop-Navigation
  - Alle Inline-Grid-Layouts (`grid-template-columns`) automatisch auf 1 Spalte via CSS-Attribut-Selektor
  - Reports-Formular-Grids (`.date-preset-row`, `.cost-grid`, `.sched-grid`) → 1 Spalte auf Mobile
  - Tabellen horizontal scrollbar, iOS-Touch-Scrolling, auto-width auf fixe `th`-Breiten
  - Preset-Cards + Demo-Grid vertikal gestapelt
  - Buttons (außer `.btn-sm`) full-width auf sehr kleinen Screens
  - iOS Font-Size-Zoom auf Inputs verhindert (`font-size: 16px`)
  - Step-Labels ausgeblendet, Tenant-Tabs horizontal scrollbar
- **dashboard.html** — Tabelle in Scroll-Wrapper, fixe `th`-Breite entfernt
- **admin_dashboard.html** — Server-Info-Tabelle in Scroll-Wrapper
- **admin_users.html** — Benutzer-Tabelle in Scroll-Wrapper
- **admin_audit.html** — Audit-Log-Tabelle in Scroll-Wrapper
- **reports_list.html** — Report-Tabelle in Scroll-Wrapper
- **register_success.html** — URL-Tabelle in Scroll-Wrapper

## 4.0.0 (2026-04-12) — „Reports & Demo-Daten Bugfix-Release"

> **Bugfix-Release.** Behebt mehrere kritische Fehler in der Demo-Daten-Verwaltung
> und in den Reports, die seit v3.5.0 / v3.9.0 unbemerkt im Code lagen. Der
> langsame Erstaufruf der Demo-Seite (Azure-SQL-Cold-Start) ist behoben.
> Update wird empfohlen, kein manueller Schritt nötig.

### Bugfix — Demo-Daten-Verwaltung (`/tenant/demo`)
- **CRITICAL** — `src/web/app.py` `tenant_demo()` GET-Handler: Die Sitzungsliste wurde gegen `dbo.demo_sessions` abgefragt, der Demo-Generator schreibt aber in `demo.demo_sessions`. Folge: die Liste war auf nicht-leerem Schema permanent leer und die Lösch-/Rollback-Aktionen schlugen mit „Invalid object name dbo.demo_sessions" fehl. Fix: konsequent `demo.*`-Schema verwenden, mit Erkennung von „Schema noch nicht initialisiert" (`Invalid object name`-Fehler → `schema_ready=False`).
- **CRITICAL** — `tenant_demo_delete()`: Übergab `[(session_id, tid)]` (Liste mit einem Tupel) an `execute_write(sql, params)`, das aber nur ein flaches Tupel erwartet. Resultat: jeder Lösch-Versuch warf eine Exception. Fix: korrekt `(session_id, tid)`-Tupel und Fremdschlüssel-konforme Reihenfolge (`jobs_copy_details` → `jobs_copy/scan/print/tracking_data` → `printers`/`users`/`networks` → `demo_sessions`).
- **CRITICAL** — Template `tenant_demo.html` postete an `/tenant/demo/rollback` (per-Session-Rollback), die Route existierte aber gar nicht — Klick produzierte einen 404. Fix: neue Route `tenant_demo_rollback` (POST), die `rollback_demo(tid, demo_tag)` aus dem Demo-Generator aufruft.
- **HIGH** — Generate-Button war dauerhaft deaktiviert: das Template prüfte `{% if not schema_ready %}`, der GET-Handler übergab die Variable aber nie. Folge: Demo-Daten konnten nur generiert werden, wenn der Benutzer das `disabled`-Attribut manuell aus dem DOM entfernte. Fix: `schema_ready` wird jetzt asynchron via JS-Fetch gesetzt (siehe Performance unten).
- **MEDIUM** — Form-Feld `queue_count` und `preset` wurden im POST gesendet, aber nie in `params_json` persistiert. Folge: in der Sitzungs-Liste fehlten Drucker-Anzahl und Preset-Badge. Fix: beide Felder werden jetzt durchgereicht (mit Whitelist-Validierung für `preset` ∈ {custom, small_business, mid_market, enterprise}).

### Performance — Demo-Seite Erstaufruf (Azure-SQL Cold-Start)
- **HIGH** — `tenant_demo()` GET-Handler führte beim Rendering eine SQL-Abfrage gegen `demo.demo_sessions` aus. Bei Azure SQL Serverless mit Auto-Pause bedeutet das einen 30–60 s-Wakeup beim Erstaufruf, während der Browser komplett blockiert war. Fix: GET-Handler rendert die Shell sofort ohne SQL-Roundtrip; ein neuer XHR-Endpunkt `/tenant/demo/sessions` lädt die Sitzungsliste asynchron, mit 30 s In-Memory-Cache pro Tenant. Erstaufruf damit von 30+ s auf < 100 ms reduziert.

### Bugfix — Reports
- **CRITICAL** — `src/reporting/query_tools.py` `query_off_hours_print()` (v3.9.0 Off-Hours-Print-Report): Die Query referenzierte drei nicht-existente Spalten (`j.finished_at`, `j.site_id`, `j.user_email`) — die echte `dbo.jobs`-Tabelle hat `submit_time`, kein direktes `site_id`, und User-Lookup geht über `tenant_user_id` → `users.email`. Zusätzlich war der `INNER JOIN reporting.v_tenants t ON t.tenant_id = ?` ohne `j.tenant_id = t.tenant_id`-Bedingung — bei Existenz der View hätte das ein Cross-Tenant-Datenleck erzeugt. Folge: der Report war seit v3.9.0 komplett gebrochen und produzierte „invalid column name"-Fehler. Fix: komplette Neuschreibung der Query gegen `j.submit_time` mit echter `j.tenant_id = ?`-Filter und JOINs gegen `printers`/`users` für die optionalen Site-/User-Filter.
- **CRITICAL** — `src/reporting/report_engine.py` Zeile 386: Tabellenzellen wurden mit `{{ cell|safe }}` gerendert — beliebiger HTML-Inhalt aus DB-Daten (z. B. Druckernamen, Benutzernamen) wurde direkt ins HTML eingebettet (Stored XSS in Reports, die per E-Mail verschickt werden). Fix: `|safe` entfernt, Jinja-Auto-Escape greift jetzt.
- **CRITICAL** — `src/reporting/report_engine.py` Zeile 1497: `Environment(loader=BaseLoader())` wurde ohne `autoescape=True` instanziiert. Damit war Auto-Escape im gesamten Report-Template-Pfad ausgeschaltet — jeder andere `{{ }}`-Ausdruck war ebenfalls XSS-anfällig. Fix: `autoescape=True` aktiviert. SVG-Charts behalten explizit `|safe` (engine-generiert, vertrauenswürdig).
- **MEDIUM** — `_plain_html_fallback()` baute den Fallback-HTML-Body per f-String ohne Escape — Titel, Section-Namen, Spalten und Zellen flossen ungefiltert ein. Fix: `html.escape`-Wrapper auf alle dynamischen Werte angewendet.

### Bugfix — OAuth-Hardening (Defense-in-Depth)
- **MEDIUM** — `src/oauth.py` `_token()`: zusätzlich zum Tenant-Binding (das de facto bereits client_id-Binding war) wird jetzt explizit geprüft, dass die `client_id` im Token-Request mit der `client_id` im Authorization-Code übereinstimmt — RFC 6749 §4.1.3 wörtlich umgesetzt. Defense-in-Depth, falls die `client_id → tenant_id`-Zuordnung jemals nicht-1:1 wird.

### Touched Files
- `src/web/app.py` — Demo-Routen-Rewrite, neuer XHR-Endpunkt `/tenant/demo/sessions`, neue Route `/tenant/demo/rollback`, In-Memory-Cache.
- `src/web/templates/tenant_demo.html` — JS-Fetch für Sitzungsliste, dynamischer `schema_ready`-Switch, `data-*`-Pattern für Rollback-Buttons.
- `src/reporting/demo_generator.py` — `preset`-Parameter durch `generate_demo_dataset()` gereicht, `params_json` enthält jetzt `queue_count` + `preset`.
- `src/reporting/query_tools.py` — `query_off_hours_print()` komplett neu gegen echtes `dbo.jobs`-Schema.
- `src/reporting/report_engine.py` — `|safe` entfernt, `autoescape=True`, `_plain_html_fallback`-Escape.
- `src/oauth.py` — explizites client_id-Binding im Token-Endpoint.
- `config.yaml`, `run.sh`, `src/server.py`, `README.md` — v3.9.1 → v4.0.0.

### Upgrade-Hinweise
- Backwards-kompatibel. Keine Schema-Änderungen, keine manuellen Schritte.
- Wer den Off-Hours-Print-Report aus v3.9.0 in einem Schedule eingebunden hat: bitte einmalig einen Probe-Lauf in der Web-UI starten — die Query produziert jetzt Daten statt SQL-Fehlern.
- Wer den Demo-Generator schon einmal benutzt hat: die existierenden Sitzungen tauchen jetzt korrekt in der Liste auf, weil das Schema endlich übereinstimmt.


## 3.9.1 (2026-04-11) — „Security & Performance Hardening"

> **Sicherheits- und Performance-Release.** Keine neuen Features, keine Schema-Änderungen
> außer einer additiven Spalte für den Bearer-Token-Index. Update wird dringend empfohlen.

### Security — OAuth 2.0 Authorization-Code-Flow (RFC 6749)
- **CRITICAL** — `src/oauth.py` `_authorize_get()` / `_authorize_post()`: Der vom Client gelieferte `redirect_uri` wurde ungeprüft in Templates und Redirects übernommen. Ein Angreifer konnte damit den Autorisierungs-Code auf eine eigene Domain umlenken (Open-Redirect / Authorization-Code-Exfiltration). Fix: harte Whitelist der erlaubten Hosts (`claude.ai`, `chat.openai.com`, `chatgpt.com`, `localhost`, `127.0.0.1`, `::1`) + erzwungenes `https` für externe Hosts. Erweiterbar über `MCP_ALLOWED_REDIRECT_HOSTS` (Komma-separiert).
- **CRITICAL** — `src/oauth.py` `_token()`: Der `/oauth/token`-Endpunkt prüfte nicht, ob der beim Code-Tausch übergebene `redirect_uri` identisch zu dem beim Autorisierungs-Request war (RFC 6749 §4.1.3). Fix: strikter Vergleich, bei Mismatch HTTP 400 `invalid_grant`.
- **HIGH** — `src/oauth.py` `_authorize_get()`: `client_id`, `redirect_uri` und `state` wurden ungefiltert in die Consent-HTML-Seite gerendert (Reflected XSS). Fix: alle Template-Werte über `html.escape(..., quote=True)` geführt; Redirects bauen die Query-String-Parameter via `urllib.parse.urlencode`.

### Security — Web-UI
- **MEDIUM** — `src/web/app.py` `lang_set()`: Die Sprachauswahl nutzte den ungeprüften `Referer`-Header als Redirect-Ziel → Open-Redirect. Fix: Referer wird mit `urlparse` zerlegt, es wird nur zurückgesprungen, wenn `netloc` leer (relativ) oder identisch zum Request-Host ist; sonst Fallback auf `/`.
- **MEDIUM** — `templates/admin_users.html`, `templates/tenant_demo.html`, `templates/reports_list.html`: JS-Kontext-Escape. `confirm('{{ value }} ?')` war anfällig, wenn Benutzernamen/Demo-Tags/Report-Namen ein `'` oder Backslash enthielten (Quote-Break → Script-Injection). Fix: Werte werden per `data-*`-Attribut übergeben (normale HTML-Attribut-Escape, also bullet-proof) und im `onclick` nur noch über `this.dataset.xxx` gelesen.
- **LOW** — `src/web/app.py`: 4 Flash-Redirects (`tenant_user_add_card`, `tenant_demo_generate`, `tenant_demo_delete`, `tenant_demo_rollback_all`) bauten `errmsg=…` per f-String zusammen → bei Fehlernachrichten mit `&`, `#` oder `?` zerlegte sich die Query-String. Fix: konsistent `urllib.parse.quote_plus`.

### Security — Auth-Middleware
- **LOW** — `src/auth.py` `_unauthorized()`: JSON-Body wurde per f-String gebaut. Bei künftigen Aufrufen mit Sonderzeichen in der Nachricht hätte das kaputtes JSON produziert. Fix: `json.dumps` + UTF-8-Encoding.

### Performance — Bearer-Token-Lookup (O(N) → O(1))
- **HIGH** — `src/db.py` `get_tenant_by_bearer_token()` scanne bisher bei jedem authentifizierten Request die komplette `tenants`-Tabelle und entschlüsselte pro Zeile den gespeicherten Token mit Fernet (CPU-lastig). Bei wachsender Tenant-Zahl wurde das für jeden einzelnen MCP-Tool-Call zum Bottleneck.
  - Additive Migration: neue indizierte Spalte `tenants.bearer_token_hash` (SHA-256 hex-digest), `CREATE INDEX IF NOT EXISTS idx_tenants_bearer_hash`.
  - `_bearer_hash()`-Helper; `create_tenant()` und `_create_empty_tenant()` schreiben den Hash mit; `init_db()` backfillt bestehende Zeilen einmalig.
  - `get_tenant_by_bearer_token()` nutzt jetzt den Index (Fast-Path) und fällt nur bei Legacy-Rows ohne Hash auf den alten Scan zurück — bei erfolgreichem Treffer wird der Hash direkt nachgeschrieben (selbstheilend).
  - Zusätzlich: vorher wurden Fernet-Decrypt-Fehler mit `except: continue` geschluckt → jetzt werden sie als `logger.warning` mit Tenant-ID geloggt, damit korrupte Rows sichtbar sind.

### Chore — Aufräumen
- Entfernt: 5 verwaiste Patch-Migrations-Skripte aus früheren Releases (~688 LOC toter Code), die im laufenden Image nie importiert wurden:
  - `src/reporting/patch_rollback_all.py`
  - `src/reporting/patch_stufe2.py`
  - `src/web/patch_app_rollback_all.py`
  - `src/web/patch_i18n_rollback_all.py`
  - `src/web/patch_template_rollback_all.py`

### Touched Files
- `src/oauth.py` — Redirect-URI-Whitelist, Template-Escape, Token-Endpoint-Binding (~80 geänderte Zeilen).
- `src/web/app.py` — Same-Host-Referer-Check in `lang_set()`, 4 × `quote_plus` in Flash-Redirects.
- `src/web/templates/admin_users.html`, `tenant_demo.html`, `reports_list.html` — `data-*`-Attribut-Pattern.
- `src/db.py` — `bearer_token_hash`-Spalte + Index + Migration + Fast-Path-Lookup + Error-Logging.
- `src/auth.py` — `json.dumps` für 401-Response.
- `config.yaml`, `run.sh`, `src/server.py`, `README.md` — v3.9.0 → v3.9.1.
- 5 × gelöschte `patch_*.py`-Dateien.

### Upgrade-Hinweise
- Backwards-kompatibel. Keine manuellen Schritte nötig: Die `bearer_token_hash`-Spalte wird beim Start automatisch angelegt und für alle bestehenden Tenants befüllt.
- Wer eine öffentliche Instanz mit eigenen Clients betreibt und weitere Redirect-Hosts braucht, setzt in der Add-on-Konfiguration die Umgebungsvariable `MCP_ALLOWED_REDIRECT_HOSTS="claude.ai,chat.openai.com,chatgpt.com,meine-domain.de"`.


## 3.9.0 (2026-04-11) — „Audit & Governance + Feedback-Ticketsystem"

### Feature — Admin-Audit-Trail mit strukturiertem Objekttyp/-ID
- Erweiterter `audit()`-Helper (`db.py`) um die neuen optionalen Felder `object_type`, `object_id` und `tenant_id` — rückwärts-kompatibel mit allen bestehenden Call-Sites. Alias `audit_write` zeigt auf dieselbe Funktion für klarere Semantik in neuen Aufrufen.
- Idempotente Schema-Migration: `ALTER TABLE audit_log ADD COLUMN object_type/object_id/tenant_id` + zwei Indizes (`idx_audit_log_created`, `idx_audit_log_tenant`).
- Bestehende Mutation-Endpunkte in `src/web/app.py` wurden angereichert — `approve_user`, `disable_user`, `delete_user`, `edit_user`, `reset_password` setzen jetzt `object_type="user"` und `object_id=<user_id>`, damit der Admin-Audit-Trail-Report strukturiert filterbar wird.
- Neue Query-Funktion `query_audit_log_range()` in `db.py` (SQLite-seitig) mit Filter-Parametern: `start_date`, `end_date`, `tenant_id`, `action_prefix`, `limit`.

### Feature — Report `audit_log` (Admin-Audit-Trail)
- Neue Query-Funktion `query_audit_log()` in `src/reporting/query_tools.py` — liest den Audit-Trail aus der lokalen SQLite (kein MSSQL-Zugriff) und normalisiert die Felder auf `timestamp`, `actor`, `action`, `object_type`, `object_id`, `details`, `tenant_id`.
- Dispatcher-Eintrag + Stufe-2-Listing (`STUFE2_QUERY_TYPES`) + Form-Label.
- Preset `audit_log` (Icon 🛡️, Tag „Governance", monatlicher Schedule 8:30).
- Output-Formate: HTML, PDF, XLSX, CSV.

### Feature — Report `off_hours_print` (Druck außerhalb Geschäftszeiten)
- Neue Query-Funktion `query_off_hours_print()` mit konfigurierbarem Geschäftszeit-Fenster (Default 07:00–18:00 + Wochenende = off-hours). Aggregiert pro Tag `off_hours_jobs` vs `in_hours_jobs`.
- Preset `off_hours_print` (Icon 🌙, Tag „Compliance", monatlicher Schedule 8:45).

### Feature — Feedback-/Feature-Request-Ticketsystem
- Neue Tabelle `feature_requests` mit automatisch vergebenen Ticket-Nummern im Format `FR-YYYYMM-NNNN` (fortlaufend pro Monat).
- Helper in `db.py`: `create_feature_request()`, `list_feature_requests()`, `get_feature_request()`, `update_feature_request_status()`, `count_feature_requests_by_status()`, `_next_ticket_no()`.
- Neue Navigations-Registerkarte „Feedback" (zwischen „Hilfe" und „Logout", Desktop + Mobile-Drawer). Für Admins mit rotem Badge für neue Tickets.
- Routen in `app.py`:
  - `GET /feedback` — Listenansicht (User sehen eigene Tickets, Admins sehen alle)
  - `POST /feedback/new` — neues Ticket anlegen (Titel, Kategorie, Beschreibung — E-Mail wird automatisch aus Session übernommen)
  - `GET /feedback/{id}` — Detail-Ansicht mit Admin-Editor
  - `POST /feedback/{id}/update` — Status/Priorität/Admin-Notiz aktualisieren (nur Admin)
- 6 Status-Buckets: `new`, `planned`, `in_progress`, `done`, `rejected`, `later` — jeweils farbig gebadged.
- 4 Kategorien: `feature` (💡), `bug` (🐞), `question` (❓), `other` (📌).
- 4 Prioritäten: `low`, `normal`, `high`, `critical`.
- Alle Aktionen schreiben in den Audit-Log (`object_type="feature_request"`).
- Zwei neue Templates: `feedback.html` (Listenansicht + Formular) und `feedback_detail.html` (Detail + Admin-Editor).

### i18n — 12 Sprachen (~42 Feedback-Keys × 12 = 504 neue Strings)
- Neue Keys: `nav_feedback`, `feedback_title`, `feedback_intro`, `feedback_new`, `feedback_f_{title,title_ph,category,description,description_ph,email}`, `feedback_submit`, `feedback_{my,all}_tickets`, `feedback_col_{ticket,title,category,user,status,created}`, `feedback_view`, `feedback_back`, `feedback_no_tickets`, `feedback_cat_{feature,bug,question,other}`, `feedback_status_{new,planned,in_progress,done,rejected,later}`, `feedback_admin_note`, `feedback_admin_actions`, `feedback_priority`, `feedback_prio_{low,normal,high,critical}`, `feedback_save`, `feedback_flash_created`.
- Die v3.8.1 bereits angelegten Audit-Log- und Off-Hours-Keys werden in diesem Release produktiv genutzt (Vorziehen hat sich gelohnt — keine neue Übersetzungs-Welle nötig).

### Touched Files
- `src/db.py` — Audit-Schema-Migration, erweiterter `audit()`-Helper, `query_audit_log_range()`, `feature_requests`-Tabelle + 5 Helper.
- `src/web/app.py` — 4 neue Feedback-Routen, `t_ctx()` um `feedback_new_count` erweitert, 5 existierende `audit()`-Calls mit `object_type`/`object_id` angereichert.
- `src/web/templates/base.html` — Nav-Link „Feedback" (Desktop + Mobile) mit Admin-Badge.
- `src/web/templates/feedback.html` (neu), `feedback_detail.html` (neu).
- `src/reporting/query_tools.py` — `query_audit_log()`, `query_off_hours_print()`, Dispatcher-Einträge.
- `src/reporting/preset_templates.py` — `audit_log`- und `off_hours_print`-Presets.
- `src/web/reports_routes.py` — `QUERY_TYPE_LABELS` + `STUFE2_QUERY_TYPES` erweitert.
- `src/web/i18n.py` — ~504 neue Feedback-Keys über 12 Sprachen.
- `config.yaml`, `run.sh`, `src/server.py` — v3.8.1 → v3.9.0.


## 3.8.1 (2026-04-11) — „Visual Upgrade + Heatmap"

### Fix — v3.8.0 `sensitive_documents` SQL-Fehler „Invalid column name 'filename'"
- Problem: In Bestandsinstallationen existierte `reporting.v_jobs` bereits (aus v3.7.x), aber ohne `filename`-Spalte. Der Report fiel mit `(207, "Invalid column name 'filename'.")` um, obwohl die neue View-Definition die Spalte enthält — die stale View wurde nicht überschrieben.
- Fix: Neue Laufzeit-Column-Detection via `sys.columns` + `OBJECT_ID()`. `query_sensitive_documents()` prüft für jede View, ob die `filename`-Spalte existiert. Fehlt sie, wird direkt auf `dbo.jobs.name` zurückgegriffen (für Scans wird der Scan-Block einfach deaktiviert, weil `dbo.jobs_scan` gar kein Dateinamen-Feld hat).
- Damit läuft der Compliance-Scan auch auf Installationen, bei denen der Schema-Refresh noch nicht gelaufen ist.

### Feature — Neuer Report `hour_dow_heatmap` (Stunde × Wochentag)
- Visuelle Heatmap der Druckaktivität, aggregiert nach Stunde (0–23) × Wochentag (Mo–So). Zeigt auf einen Blick Arbeitsmuster, Stoßzeiten und Off-Hours-Druck.
- Neue Query-Funktion `query_hour_dow_heatmap(start_date, end_date, site_id, user_email)` in `src/reporting/query_tools.py`. Nutzt `SET DATEFIRST 7` + `DATEPART(weekday/hour, finished_at)` für deterministisches DoW-Ordering, gruppiert nach `(dow, hour)` und liefert zusätzlich Color- und Mono-Spalten-Breakdown.
- Neuer Report-Builder `build_hour_dow_heatmap_report()` in `src/reporting/report_engine.py` — baut KPI-Strip (Spitzen-Zeitfenster, Top-3 Slots), SVG-Heatmap-Chart und Top-Slots-Tabelle.
- Neuer Chart-Typ `heatmap` im SVG-Renderer: 24 × 7 Zellen mit quadratischer Farbskala, Achsenlabels DoW/Stunde, legendenfähig.
- Preset `hour_dow_heatmap` (Tag „Analyse", Icon 🗓️, monatlicher Schedule-Vorschlag).

### i18n — 12 Sprachen (~14 neue Keys × 12 = 168)
- `rpt_type_hour_dow_heatmap`, `rpt_eng_title_hour_dow_heatmap`, `rpt_eng_chart_hour_dow`, `rpt_eng_chart_color_vs_bw`, `rpt_eng_dow_mon..sun`, `rpt_eng_kpi_peak_slot`, `rpt_eng_section_top_slots`, `rpt_eng_col_weekday`, `rpt_eng_col_hour`, `preset_name_hour_dow_heatmap`, `preset_desc_hour_dow_heatmap`, `preset_tag_Analyse`.
- Außerdem sind die in v3.9.0 benötigten Audit-Log- und Off-Hours-Keys bereits mit angelegt (Vorziehen der i18n-Lieferung), damit v3.9.0 beim Rollout keinerlei Übersetzungen mehr braucht.

### Touched Files
- `src/reporting/query_tools.py` — `query_hour_dow_heatmap()`, Dispatcher-Zweig, `query_sensitive_documents()`-Fix.
- `src/reporting/report_engine.py` — `build_hour_dow_heatmap_report()`, Dispatcher-Zweig, Heatmap-SVG-Renderer.
- `src/reporting/preset_templates.py` — `hour_dow_heatmap`-Preset.
- `src/web/i18n.py` — ~480 neue Keys über 12 Sprachen (v3.8.1 + v3.9.0 Vorlage).
- `config.yaml`, `run.sh`, `src/server.py` — v3.8.0 → v3.8.1.


## 3.8.0 (2026-04-11) — „Sensible Dokumente + Demo-Daten"

### Feature — Neuer Compliance-Report: `sensitive_documents`
- Scannt Druck- und Scan-Jobs per `LIKE`-Match auf dem Dateinamen nach sensiblen Begriffen — zugeschnitten auf klassische Compliance-Kategorien: **HR** (Gehaltsabrechnung, Arbeitsvertrag, Kündigung, Personalakte …), **Finanzen** (Kreditkartenabrechnung, IBAN, Kontoauszug, Steuererklärung …), **Vertraulich** (VERTRAULICH, Confidential, NDA, Geheim), **Gesundheit** (Krankmeldung, Arztbrief, AU), **Recht** (Klageschrift, Anwaltsschreiben, Mahnbescheid) und **PII** (Personalausweis, Reisepass, SVN).
- Neue Query-Funktion `query_sensitive_documents(start_date, end_date, keyword_sets, custom_keywords, site_id, user_email, include_scans, page, page_size)` in `src/reporting/query_tools.py`. Verarbeitet dynamisch OR-verknüpfte `LIKE`-Klauseln (parametrisiert, Cap bei 40 Terms) über `UNION ALL(v_jobs, v_jobs_scan)` und annotiert jedes Ergebnis mit der gefundenen Keyword-Treffer-Markierung.
- Neuer Helper `_resolve_sensitive_keywords(sets, custom)`: 6 vordefinierte Keyword-Sets + freie Eingabe, Dedup + Lowercasing + Length-Cap.
- Dispatcher-Eintrag in `run_query()`: `sensitive_documents` → `query_sensitive_documents(**filtered_kwargs)`.
- Neues Preset `sensitive_documents` mit Tag „Compliance", Icon 🛡️, Schedule-Vorschlag monatlich am 1. um 08:00.
- Web-Formular (`reports_form.html`): neue Query-Params-Gruppe `qp-sensitive_documents` mit 6 Keyword-Set-Checkboxen + Freitextfeld + „Scan-Jobs einbeziehen"-Checkbox. Hidden-Field-Sync beim Submit.
- `reports_routes.py`: `_parse_csv_list()`-Helper, `_merge_query_params()` erweitert, Form-Felder (`keyword_sets`, `custom_keywords`, `include_scans`) in `reports_new_post` + `reports_edit_post`.
- `QUERY_TYPE_LABELS` + `STUFE2_QUERY_TYPES` um `sensitive_documents` ergänzt — der generische Stufe-2-Fallback in `generate_report()` rendert den Report als Tabelle, keine dedizierte Builder-Funktion nötig.

### Feature — Demo-Generator mit sensiblen Beispieldaten
- Neue Konstanten `_SENSITIVE_PRINT_TEMPLATES` (25) und `_SENSITIVE_SCAN_TEMPLATES` (12) mit realistischen Dateinamen pro Keyword-Set.
- `_filename_print()` und `_filename_scan()` picken mit Wahrscheinlichkeit `_SENSITIVE_RATIO = 0.08` aus dem sensiblen Pool — liefert bei einem typischen 12-Monats-Dataset mehrere Hundert Treffer für den Compliance-Scan.
- `_filename_print()` nutzt jetzt den User-Slug als Template-Variable `{user}` — realistisch für Gehaltsabrechnungen/Arbeitsverträge.

### Schema-Fix — `demo.jobs_scan.filename` fehlte
- Bisher versuchte `_gen_scan_jobs()` bereits `filename` in `demo.jobs_scan` zu schreiben, obwohl die Tabellendefinition die Spalte nicht enthielt. Dieser latente Fehler war nur noch nicht aufgefallen, weil kein Report die Spalte las.
- `SCHEMA_STATEMENTS`: neue Tabellendefinition inkl. `filename NVARCHAR(500) NULL` + idempotente `ALTER TABLE ADD filename` Migration für bestehende Installationen.

### Schema-Fix — `reporting.v_jobs` / `reporting.v_jobs_scan` ohne `filename`
- `v_jobs`: Union aus `dbo.jobs.name AS filename` und `demo.jobs.filename` — Compliance-Report findet jetzt echte Druck-Dateinamen.
- `v_jobs_scan`: `dbo.jobs_scan` hat keine Filename-Spalte → `CAST(NULL AS NVARCHAR(500)) AS filename`; `demo.jobs_scan.filename` wird normal mitgeführt.
- Beide Views werden per `CREATE OR ALTER VIEW` idempotent aktualisiert; `setup_schema()` triggert automatisch `invalidate_view_cache()`.

### i18n — 12 Sprachen (~240 neue Keys)
- Neue Labels: `rpt_type_sensitive_documents`, `rpt_eng_title_sensitive_documents`, `preset_tag_Compliance`, `preset_name_sensitive_documents`, `preset_desc_sensitive_documents`, `rpt_sensitive_keyword_sets[_hint]`, `rpt_sensitive_custom_keywords[_placeholder|_hint]`, `rpt_sensitive_include_scans`, `sens_kw_set_{hr,finance,confidential,health,legal,pii}`, `rpt_eng_col_{filename,matched_keyword,source}`.
- Komplett übersetzt für **de, en, fr, it, es, nl, no, sv, bar, hessisch, oesterreichisch, schwiizerdütsch**.

### Touched Files
- `src/reporting/query_tools.py` — `query_sensitive_documents()`, `_resolve_sensitive_keywords()`, `SENSITIVE_KEYWORD_SETS`, Dispatcher-Zweig.
- `src/reporting/preset_templates.py` — `sensitive_documents`-Preset.
- `src/reporting/demo_generator.py` — sensitive Templates, `_filename_print/_scan`-Bias, `demo.jobs_scan.filename` Schema + Migration, `v_jobs` + `v_jobs_scan` Views.
- `src/web/reports_routes.py` — `QUERY_TYPE_LABELS`, `STUFE2_QUERY_TYPES`, `_parse_csv_list()`, `_merge_query_params()`, Form-Felder.
- `src/web/templates/reports_form.html` — `qp-sensitive_documents`-Block + JS.
- `src/web/i18n.py` — 240 neue Keys über 12 Sprachen.
- `config.yaml`, `run.sh`, `src/server.py` — v3.7.11 → v3.8.0.


## 3.7.11 (2026-04-11)

### Fix — `run_query()`-Dispatcher stolperte über zusätzliche Preset-Kwargs
- Konkreter Fehler: Custom-Report „Top 5" (query_type=`top_users`) lieferte Preview-Fehler `query_top_users() got an unexpected keyword argument 'group_by'`. Analog zum Trend-Fix in v3.7.10 gab es eine Signatur-Diskrepanz, dieses Mal zwischen den im Stufe-2-Template hinterlegten Layout-Keys (`group_by`, `order_by`, `preset_id`, …) und den konkreten Query-Funktionen.
- Neuer Helper `_filter_kwargs_to_sig(fn, kwargs)`: schneidet via `inspect.signature` alle Keys ab, die die Ziel-Query-Funktion nicht kennt, und loggt sie auf Debug-Level. Funktionen mit `**kwargs` werden unverändert durchgereicht.
- Alle 17 Dispatch-Zweige in `run_query()` wurden umgestellt — print_stats, cost_report, top_users, top_printers, trend, anomalies, printer_history, device_readings, job_history, queue_stats, user_detail, user_copy_detail, user_scan_detail, workstation_overview, workstation_detail, tree_meter, service_desk.
- Damit sind alle Preset-basierten Reports immun gegen "unexpected keyword argument"-Fehler, sobald ein Preset-Autor einen zusätzlichen Key in `query_params` ablegt (z.B. aus UI-Feldern oder Layout-Metadaten, die nicht zur SQL-Query gehören).
- Verifiziert im laufenden Container: Filter-Test + Dispatch-Test mit dem exakten fehlschlagenden Preset (`top_users` mit `group_by` + `order_by`) — Filter entfernt beide Keys, Dispatch liefert stub-Result ohne TypeError.

### Touched Files
- `src/reporting/query_tools.py` — `_filter_kwargs_to_sig()` Helper, alle 17 `run_query()`-Dispatch-Zweige.
- `config.yaml`, `run.sh`, `src/server.py` — v3.7.10 → v3.7.11.


## 3.7.10 (2026-04-11)

### Fix 1 — Trend-Preview akzeptierte kein `start_date`/`end_date`
- `query_tools.run_query(query_type="trend", …)` leitete die Preset-Keys `start_date`/`end_date` direkt an `query_trend()` weiter, das aber nur `period1_start`, `period1_end`, `period2_start`, `period2_end` kennt → `TypeError: unexpected keyword argument 'start_date'`.
- Neuer Helper `_translate_trend_kwargs()` konvertiert `start_date/end_date` in ein Period-1-Fenster und legt automatisch ein gleich langes Period-2-Fenster unmittelbar davor an. Unbekannte Keys wie `group_by` werden gefiltert, Kostenparameter (`cost_per_sheet`, `cost_per_mono`, `cost_per_color`) werden durchgereicht.
- Betroffen: alle Stufe-2-Presets mit `query_type=trend` (z.B. "Wöchentlicher Drucktrend").

### Fix 2 — Stufe-2-Reports zeigten rohe DB-Spaltennamen als Tabellen-Header
- Der generische Fallback in `report_engine.generate_report()` übernahm `list(data[0].keys())` direkt als `columns` → Tabellen erschienen mit `job_id`, `print_time`, `user_email`, `page_count`, `color`, … statt mit lesbaren Überschriften.
- Neue Mapping-Tabelle `COLUMN_LABELS` (de + en, ~70 Spalten) plus `_translate_col(col, lang)` mit Fallback-Kette (lang → Dialekt-Fallback → en → Title-Case).
- `generate_report()` nimmt nun `lang: Optional[str]` entgegen; `reports_routes.reports_preview_get` reicht `tc["lang"]` durch, sodass HTML/PDF/XLSX-Preview in der aktiven UI-Sprache rendern.
- Beispiel `job_history` (DE): `Auftrags-ID · Druckzeit · Benutzer-E-Mail · Benutzer · Drucker · Site · Seiten · Farbe · Status` statt der Raw-Namen.
- Verifiziert mit 9 Test-Cases inkl. Dialekt-Fallback (bar→de), fehlendem Mapping (fr→en) und unbekannter Spalte (Title-Case).

### Feature — MCP-Tool `printix_save_report_template` unterstützt Custom-Logo
- Neue optionale Parameter `logo_base64`, `logo_mime`, `logo_url`. Auflösungs-Logik identisch zu `_resolve_logo` im Web-Formular: Base64 hat Vorrang vor URL, MIME wird auf `image/*` geprüft, Rohgrößen-Cap bei 1 MB, Fehler werden als `{"error": …}` zurückgegeben.
- Damit können Reports, die per AI-Chat (claude.ai, ChatGPT) über das MCP-Tool angelegt werden, ein benutzerdefiniertes Logo im Report-Header führen — vorher ging das nur über die Web-UI.
- Kein Breaking Change: alle neuen Parameter haben Defaults, bestehende Aufrufe bleiben gültig.

### Touched Files
- `src/reporting/query_tools.py` — `_translate_trend_kwargs()`, `run_query()`-Dispatch.
- `src/reporting/report_engine.py` — `COLUMN_LABELS`, `_LANG_FALLBACK`, `_translate_col()`, `generate_report(lang=…)`-Signatur + Fallback-Branch.
- `src/web/reports_routes.py` — Preview-Route reicht `tc["lang"]` durch.
- `src/server.py` — `printix_save_report_template` mit Logo-Parametern.
- `config.yaml`, `run.sh`, `src/server.py` — v3.7.9 → v3.7.10.


## 3.7.9 (2026-04-11)

### Bugfix A — Stufe-2 Report-Templates erzeugten immer einen Druckvolumen-Report

- **Root cause:** `QUERY_TYPE_LABELS` in `web/reports_routes.py` enthielt nur 6 Einträge (Stufe 1). Presets wie "Workstation-Übersicht", "Service Desk Report" oder "Drucker Service-Status" setzten zwar den korrekten `query_type` (z.B. `service_desk`, `workstation_overview`), aber beim Rendern des Form-Templates `reports_form.html` hatte das `<select name="query_type">` nur Optionen für die 6 Stufe-1-Typen. Der Browser wählte stillschweigend die erste Option (`print_stats`) — das Template wurde mit falschem `query_type` gespeichert. Zusätzlich war der `scheduler._run_report_job()` auf 6 hardcoded Query-Funktionen limitiert, sodass auch manuell gesetzte Stufe-2-Templates bei der Ausführung mit "Unbekannter Query-Typ" kommentarlos abbrachen.
- **Fix 1 — QUERY_TYPE_LABELS erweitert:** Alle 17 Query-Typen (6 Stufe 1 + 11 Stufe 2) sind jetzt im Dropdown gelistet. Neue Stufe-2-Einträge: `printer_history`, `device_readings`, `job_history`, `queue_stats`, `user_detail`, `user_copy_detail`, `user_scan_detail`, `workstation_overview`, `workstation_detail`, `tree_meter`, `service_desk`.
- **Fix 2 — `_merge_query_params()` Helper:** Neue Hilfsfunktion im `reports_routes.py` sammelt `query_params` aus drei Quellen: (a) bestehende Template-Parameter beim Edit, (b) Preset-JSON `preset_qp_json` beim Neuanlage-Flow, (c) die Form-Felder (start_date, end_date, group_by, limit, cost_*). Stufe-2-spezifische Parameter (z.B. `printer_id`, `user_id`, `network_id`) bleiben dadurch erhalten, auch wenn das Form nur die Basisfelder anzeigt.
- **Fix 3 — Hidden `preset_qp_json` Field:** `reports_form.html` enthält jetzt ein verstecktes `<input name="preset_qp_json">`, das beim Edit mit `report.query_params | tojson` befüllt wird. Beim Speichern werden dadurch alle originalen Parameter weitergereicht, auch wenn das UI sie nicht kennt.
- **Fix 4 — Scheduler-Dispatch:** `scheduler._run_report_job()` und `scheduler.run_report_now()` rufen jetzt beide den universellen `query_tools.run_query(query_type=…, **params)`-Dispatcher auf (v3.7.9 `run_query` unterstützt alle 17 Typen). Der alte 6-Entry-`query_fn`-Dict wurde ersatzlos gestrichen.
- **Fix 5 — Generic Fallback im `generate_report()`:** Für Stufe-2-Query-Typen ohne eigenes Jinja-Template fällt die Engine auf den generic-Section-Builder zurück. Neu: Der Titel wird aus `rpt_eng_title_<query_type>` per i18n aufgelöst — ohne i18n-Key wird `query_type.replace("_", " ").title()` als Fallback genommen.

### Bugfix B — Logo tauchte weder in PDF- noch in XLSX-Anhängen auf

- **Root cause:** `render_pdf()` und `render_xlsx()` hatten gar keine Logo-Behandlung. Nur `render_html()` rief `_derive_logo_src()` auf. Der HTML-Pfad funktionierte bereits, aber E-Mail-Anhänge blieben ohne Logo.
- **Fix 1 — `render_pdf()` Logo-Embedding:** Die Funktion zeichnet jetzt explizit einen Header-Hintergrund-Rect via `pdf.rect(..., style="F")` und platziert das Logo rechtsbündig im 19pt-hohen Header. Das Base64-Datum wird aus `layout.logo_base64` dekodiert (inkl. `data:image/...;base64,`-Strip) und via `pdf.image(BytesIO(...))` mit `logo_h=14`, `logo_w=28` eingebettet.
- **Fix 2 — `render_xlsx()` Logo-Embedding:** Oben rechts (Ankerzelle E1) wird das Logo per `openpyxl.drawing.image.Image` eingesetzt. Die Höhe wird auf 50px begrenzt, die Breite aus dem Originalverhältnis berechnet. Fehlerhaftes Base64 wird abgefangen und geloggt, ohne den Report zu brechen.
- **Fix 3 — HA-Variante `render_html()` (nur HA-Deploy):** Die ältere HA-Fassung von `render_html()` las nur `layout.logo_url` und ignorierte `logo_base64`. Beim User-Upload wurde daher nie ein Logo in der HTML-Vorschau angezeigt. Die HA-Seite baut jetzt — analog zu `_derive_logo_src()` auf macOS — eine `data:<mime>;base64,…`-URI aus `logo_base64`/`logo_mime` und übergibt sie dem Jinja-Template als `logo_url`. (macOS-Quelle nutzt bereits `_derive_logo_src()` und ist unverändert.)

### i18n

- 264 neue Übersetzungen (11 × 12 × 2): Für jede der 12 UI-Sprachen (de, en, fr, it, es, nl, no, sv, bar, hessisch, oesterreichisch, schwiizerdütsch) wurden 11 neue `rpt_type_*` Keys (Dropdown-Labels im Report-Form) und 11 neue `rpt_eng_title_*` Keys (Report-Titel im generierten HTML/PDF/XLSX) hinzugefügt.

### Banner

- v3.7.8 → v3.7.9 in `config.yaml`, `run.sh`, `src/server.py`.

## 3.7.8 (2026-04-11)

### Demo-Seite: Ladezeit-Fix

- **Root cause:** Der `/tenant/demo`-Handler rief `get_demo_status()` bzw. `query_fetchall()` synchron im FastAPI-Event-Loop auf. Jede Azure-SQL-Round-Trip-Zeit (Auto-Pause/Wake-up + Netz-Latenz) blockierte damit den gesamten Worker — die Seite brauchte mehrere Sekunden bis zum ersten Byte, und parallele Requests (z.B. MCP-Calls) stallten mit.
- **Fix 1 — Async-Offload:** Die blockierende SQL-Abfrage läuft jetzt in `asyncio.to_thread(...)`. Der Event-Loop bleibt frei, FastAPI kann andere Requests parallel bedienen. Python 3.11 propagiert `ContextVar` über `copy_context` automatisch durch, d.h. Tenant-Config (`set_config_from_tenant`) bleibt im Worker-Thread gültig.
- **Fix 2 — TOP 20:** Die SELECT-Abfrage auf `demo.demo_sessions` / `dbo.demo_sessions` wurde auf `SELECT TOP 20 … ORDER BY created_at DESC` begrenzt. Die Demo-Seite zeigt sowieso nur die jüngsten Sessions, und die alte Abfrage konnte bei langen Demo-Historien hunderte Zeilen aus Azure SQL ziehen.
- **Abdeckung:** Gilt für beide Code-Pfade (HA: `get_demo_status()` in `demo_generator.py` → `demo.demo_sessions`, macOS-Source: Inline-Query in `web/app.py` → `dbo.demo_sessions`). Die beiden Pfade divergieren architektonisch (unterschiedliches Schema), haben aber jetzt dieselben Performance-Charakteristika.

### Banner

- v3.7.7 → v3.7.8 in `config.yaml`, `run.sh`, `src/server.py`.

---

## 3.7.7 (2026-04-11)

### Reports-Formular: Logo-URL → Datei-Upload

- **Warum:** Die bisherige Logo-URL war ungünstig in der Praxis — Firmenlogos liegen selten unter einer öffentlich erreichbaren URL, und externe Bilder werden in PDF-Exports oft blockiert. Das Engine-Backend unterstützte `layout.logo_base64` bereits seit v3.8.0, aber das Formular bot nur ein URL-Feld.
- **UI:** Das URL-Textfeld wurde durch einen Datei-Upload (`<input type="file" accept="image/png,image/jpeg,image/gif,image/svg+xml,image/webp">`) ersetzt. Der Client liest das Bild per `FileReader.readAsDataURL()`, extrahiert den Base64-Teil und den MIME-Typ und schreibt beides in versteckte Form-Felder (`logo_base64`, `logo_mime`) — kein Multipart nötig. Preview und "Logo entfernen"-Button werden sofort aktualisiert.
- **Größenlimit:** 512 KB Rohgröße (client-seitig per JS geprüft, server-seitig per Cap in `_resolve_logo()` als Doppelsicherung — Base64 ist ~1.33× → ~683 KB bleibt unter Starlette's 1 MB Form-Limit).
- **Rückwärtskompatibilität:** Bestehende Templates mit `logo_url` werden weiter unterstützt — `_resolve_logo()` behält die URL als Legacy-Fallback wenn kein neuer Upload kommt. Der Engine-Renderer bevorzugt ohnehin `logo_base64` über `logo_url`.
- **Backend:** Neuer Helper `_resolve_logo()` in `reports_routes.py` entscheidet anhand der Form-Felder (`logo_remove`, `logo_base64`, `logo_mime`, `logo_url`), welche Werte ins Layout wandern. Beide POST-Handler (`/reports/new`, `/reports/{id}/edit`) nutzen ihn.
- **i18n:** `rpt_logo` und `rpt_logo_hint` in allen 12 Sprachen (de/en/fr/it/es/nl/no/sv + bar/hessisch/oesterreichisch/schwiizerdütsch) auf Upload-Formulierung umgestellt. Neuer Key `rpt_logo_remove` für den Entfernen-Button in jeder Sprache.

### Banner

- v3.7.6 → v3.7.7 in `config.yaml`, `run.sh`, `src/server.py`.

---

## 3.7.6 (2026-04-11)

### Reports: "Datum"-Spalte zeigte E-Mail bei Gruppierung nach Benutzer/Drucker/Standort (Fix)

- **Root cause:** `generate_report()` reichte den `group_by`-Parameter nicht an `build_print_stats_report()` und `build_cost_report_report()` weiter. Beide Build-Funktionen verwendeten ihren Default `group_by="day"` und beschrifteten die erste Spalte hardcoded mit "Datum" — auch dann, wenn die SQL-Query nach `user`, `printer` oder `site` gruppiert hatte und die Werte E-Mails, Druckernamen oder Standorte enthielten. Im Screenshot von "MNI - Druckvolumen-Report" zeigte die "Datum"-Spalte deshalb Werte wie `alessandro.weber@…`.
- **Fix:** `generate_report(query_params=...)` neuer Parameter, der `group_by` extrahiert und an die Build-Funktionen weiterreicht. `build_cost_report_report()` bekam denselben `group_by`-Parameter und ein `period_col_label`-Mapping (Datum/Woche/Monat/Benutzer/Drucker/Standort). Beide Build-Funktionen formatieren die erste Spalte jetzt nur dann mit `.split("T")[0]` wenn `group_by` ein Datum ist.
- **Chart-Label-Truncation:** für nicht-datumsbasierte Gruppierung wurde die Truncation von 10 auf 24 Zeichen erhöht — vorher zeigte die X-Achse `alessandro` und `andreas.we`, jetzt der vollständige Name. Der Chart-Achsentitel verwendet jetzt das dynamische `col_label` statt hardcoded "Periode".
- **Callsites:** alle drei `generate_report()`-Aufrufer (`scheduler._run_report_job`, `scheduler.run_report_now`, `web/reports_routes` Preview) reichen jetzt `query_params=params` weiter.

### Reports: Anzeigename statt E-Mail bei `group_by="user"`

- **Root cause:** `query_print_stats` selektierte für `group_by="user"` direkt `u.email` als `period`. Die Reports zeigten dadurch immer die E-Mail-Adresse statt des lesbaren Namens.
- **Fix:** `group_expr` und `label_col` verwenden jetzt `COALESCE(u.name, u.email)` — fällt nur dann auf E-Mail zurück, wenn kein Anzeigename vorhanden ist. Reports zeigen jetzt "Hans Müller" statt "hans.mueller@printix-demo.example".

### Demo-Daten: E-Mail-Domain stabil und ohne Doppelpräfix

- **Root cause:** `demo_generator.py` baute `email_domain = f"demo-{demo_tag.lower().replace(' ','')}.invalid"`. Der Default-`demo_tag` ist aber `"DEMO_<timestamp>"` (oder die UI vergibt `"Demo <date>"`), wodurch die Domain zu `demo-demo20260411103045.invalid` wurde — doppeltes "demo-"-Präfix und unschön.
- **Fix:** stabile Demo-Domain `printix-demo.example` (RFC 2606 reservierter `.example` TLD ist eindeutig als Demo erkennbar und kollidiert garantiert mit keiner echten Domain). Demo-User haben jetzt sauber `hans.mueller@printix-demo.example`.

### Banner

- v3.7.5 → v3.7.6 in `config.yaml`, `run.sh`, `src/server.py`.

---

## 3.7.5 (2026-04-11)

### Reports-Seite: SQL-Konfig-Warnung obwohl SQL konfiguriert (Fix)

- **Root cause:** `_reporting_available()` in `src/web/reports_routes.py` rief `is_configured()` auf, ohne vorher den `current_sql_config` ContextVar zu setzen. Im Web-Prozess (Port 8080) gibt es **keine** automatische ContextVar-Befüllung — die `BearerAuthMiddleware` läuft nur im MCP-Server-Prozess (Port 8765). Folge: `/reports` zeigte dauerhaft "SQL-Server nicht konfiguriert", obwohl die Tenant-Settings vollständig gepflegt waren.
- **Fix:** `_reporting_available(tenant)` nimmt jetzt den Tenant-Datensatz entgegen und ruft `set_config_from_tenant(tenant)` vor `is_configured()` auf. Callsite in `reports_list_get` übergibt den bereits geladenen `tenant`-Datensatz.

### Auth-Logs erscheinen jetzt in `tenant_logs` (Reihenfolgen-Fix)

- **Root cause:** `BearerAuthMiddleware.__call__()` in `src/auth.py` rief `logger.debug("Auth OK: Tenant ...")` **vor** `current_tenant.set(tenant)`. Der `_TenantDBHandler` liest `current_tenant` per ContextVar, um den Log in die richtige `tenant_logs`-Zeile zu schreiben — war noch leer, also wurde der Record verworfen. Die Auth-Kategorie zeigte deswegen "0 lines" im Log-Viewer trotz aktiver Sessions.
- **Fix:** Reihenfolge umgedreht — erst `current_tenant.set()` + `current_sql_config.set()`, dann `logger.debug("Auth OK ...")`. Kommentar an der Stelle dokumentiert die Abhängigkeit.

### demo_worker Subprozess-Logs sichtbar in Docker stdout

- **Root cause:** `src/reporting/demo_worker.py` läuft als isolierter `subprocess.Popen`-Prozess (Segfault-Schutz). Er erbte zwar Pipes, hatte aber selbst kein `logging.basicConfig()` — alle `reporting.sql_client`/`reporting.demo_generator` Logs landeten im Nirgendwo. Während der Demo-Generierung gab es deshalb keinerlei Fortschrittsanzeige in `ha addons logs`.
- **Fix:** `demo_worker.py` ruft `logging.basicConfig(stream=sys.stdout, force=True)` direkt nach den Imports, eigener Logger `printix.demo_worker` mit Lifecycle-Logs (`gestartet`, `Starte generate_demo_dataset`, `fertig: session_id=…`, `abgebrochen: …`).

### Banner

- run.sh + server.py auf v3.7.5 nachgezogen.


## 3.7.4 (2026-04-11)

### Performance: Demo-Daten-Generierung — Multi-Row VALUES Bulk Insert (kritischer Fix)

- **Root cause:** `pymssql.executemany()` führte für jede Zeile einen eigenen TDS-Round-Trip aus (kein `fast_executemany` in pymssql 2.3.13). Bei ~45.000 Print-Jobs × Azure SQL Internet-Latenz hing die Demo-Generierung Stunden bzw. unbegrenzt — der Worker-Prozess blockierte zuletzt minutenlang in `poll()` mit unbestätigten TCP-Bytes im tx_queue.
- **Fix:** Neuer `_execute_many_multirow()` Helper in `src/reporting/sql_client.py`. Erkennt aus dem SQL-Template die Spaltenzahl, baut ein einziges `INSERT … VALUES (?,?,…),(?,?,…),…` Statement pro Batch (`rows_per_stmt = min(1000, 2000 // num_cols)`) und sendet die geflatteten Parameter in **einem** Round-Trip — statt N. Das reduziert ~45k Round-Trips auf ~450 (Faktor 100×).
- `execute_many()` branched jetzt auf `_prefer_pymssql()`: pymssql nimmt den Multirow-Pfad, pyodbc behält weiterhin `fast_executemany`. Logging: "Bulk-Insert (pymssql multirow): N Zeilen à K Spalten" pro Batch.

### Logging: `printix.web` Logs jetzt sichtbar in Docker stdout

- **Root cause:** `src/web/run.py` rief nie `logging.basicConfig()` auf. Der `printix.web` Logger hatte deshalb im Web-Prozess **keinen** StreamHandler — die einzige Senke war `_WebTenantDBHandler` (SQL-Tabelle `tenant_logs`). Solange SQL hing, gingen alle Web-Logs (inkl. Demo-Job-Lifecycle, Auth-Events, Reports-Aufrufe) ins Vakuum.
- **Fix:** `run.py` ruft jetzt **vor** jeglicher Logger-Erstellung `logging.basicConfig(level=…, format=…, stream=sys.stdout, force=True)`. Damit erscheinen alle Module-Logs (`printix.web`, `printix.web.sql`, `printix.web.auth`, etc.) zuverlässig in `ha addons logs local_printix-mcp` — auch wenn die SQL-Senke gerade nicht antwortet.

### Banner

- run.sh Banner und Header-Kommentar von v3.5.x auf v3.7.4 nachgezogen.

## 3.7.3 (2026-04-11)

### Bugfixes: Mail-Versand (Resend 422), Demo-Namen, Hintergrund-Hinweise

Drei Probleme aus dem laufenden Betrieb der "Monatlichen Kostenanalyse":

- **Resend 422 "Invalid `to` field" beim Mail-Versand** — Reports schlugen mit
  `Invalid to field. The email address needs to follow the email@example.com or
  Name <email@example.com> format` fehl, sobald der Empfänger einen Anzeigenamen
  hatte oder das Template mit einem unvollständigen Eintrag (nur Name, keine Adresse)
  gespeichert wurde. Ursache: der alte naive Parser
  (`recipients.replace(";", ",").split(",")`) zerlegte `"Nimtz, Marcus" <m@firma.de>`
  am Komma innerhalb der Anführungszeichen, und es gab _keine_ Validierung vor dem
  Resend-Call.
  **Fix**: neues Modul `src/reporting/email_parser.py` mit RFC-5322-tauglichem
  Parser (respektiert Quotes und Angle-Brackets, versteht `,` und `;` als Separator,
  normalisiert auf Resend-kompatibles `Name <email@domain>`). Die Eingabe wird in
  `reports_routes.py` beim Speichern VALIDIERT — ungültige Einträge erzeugen eine
  klare Fehlermeldung im Formular statt fehlerhafte Templates zu speichern.
  Zusätzlich Pre-Flight-Check in `mail_client.send_report()`: auch bei bereits
  korrupt gespeicherten Templates wird _vor_ dem Resend-Call eine `ValueError` mit
  "Ungültige Empfänger-Adresse(n): …" ausgelöst, damit der User den Fehler sofort
  versteht. Formularfeld hat neuen Hint `rpt_recipients_hint` in allen 12 Sprachen.

- **Demo-Benutzer: "komische Schreibweisen"** — bei größeren Datensätzen (1000+
  User) entstanden durch den zu kleinen Namens-Pool (24×24 = 576 Kombinationen)
  viele Duplikate, die _nur im E-Mail-Feld_ mit einer Zufallszahl ergänzt wurden —
  der Anzeigename `Hans Müller` blieb für alle Duplikate identisch.
  **Fix** in `demo_generator.py`:
    - Namens-Banken von ~24 auf ~70 Einträge pro Sprache erweitert (knapp 5000
      Kombinationen pro Locale)
    - neue saubere Kollisionsbehandlung: doppelte Namen bekommen ein Mittelinitial
      (`Hans A. Müller`, `Hans B. Müller`, …), E-Mail folgt dem gleichen Schema
      (`hans.a.mueller@…`) — statt `hans.mueller42@…`
    - neue Helper-Funktion `_ascii_slug()` entfernt Bindestriche/Apostrophe/Spaces
      statt sie mit `-` zu ersetzen (`Jean-Luc de Vries` → `jeanluc.devries`,
      vorher `jean-luc.de-vries`)
    - Test mit 2000 Usern: 0 Duplikate bei Namen und E-Mails.

- **"Läuft das noch?" — fehlende Hintergrund-Hinweise** — beim Klick auf
  "Demo-Daten generieren" mit großen Datensätzen sah der User minutenlang nichts
  und ging davon aus, der Job sei abgestürzt.
  **Fix**: `tenant_demo.html` zeigt beim Klick sofort eine gelbe Warnung
  "Generierung läuft im Hintergrund … kann mehrere Minuten dauern … Seite kann
  offen bleiben, Schließen bricht den Job NICHT ab". Nach Abschluss der animierten
  Progress-Schritte bleibt der Balken bei 92% und pulsiert mit der Meldung "Daten
  werden weiter im Hintergrund geschrieben…" — der User sieht jetzt klar, dass der
  Worker noch läuft. 3 neue i18n-Keys in allen 12 Sprachen.
  Zusätzlich: der "Jetzt ausführen"-Button in der Report-Liste deaktiviert sich
  beim Klick und zeigt ⏳ mit Titel "Läuft … bitte warten …". Neuer Key
  `rpt_run_running` in allen 12 Sprachen.

### Nicht-Breaking

Dieses Release ändert keine Datenbank-Schemata, Migrationen oder Config-Keys.
Templates mit bereits korrupt gespeicherten Recipients werden beim nächsten Edit
gegen den neuen Parser validiert und bleiben sonst unverändert in der JSON.

---

## 3.7.2 (2026-04-10)

### Bugfix: Reports zeigen keine Demo-Daten (fehlende reporting.v_* Views)

Nach 3.7.1 lief die Demo-Generierung sauber durch (demo.* Tabellen gefüllt), aber
**alle Reports blieben leer**. Ursache: die drei wichtigsten Reporting-Views fehlten in
der Azure SQL und `_V()` in `query_tools.py` fällt dann auf `dbo.*` zurück — und dort
liegen bei Demo-Setups keine Daten.

- **`reporting.v_tracking_data`** fehlte wegen Typkonflikt bei `CREATE VIEW`:
  `dbo.tracking_data.id` ist `uniqueidentifier`, `demo.tracking_data.id` ist `bigint` →
  UNION ALL schlug mit `Operand type clash: uniqueidentifier is incompatible with bigint`
  fehl. Fix: beide Seiten explizit `CAST(id AS NVARCHAR(36))`.
- **`reporting.v_jobs`** fehlte weil die View-Definition eine Spalte `filename` auswählte,
  die in `dbo.jobs` nicht existiert (dort heißt sie `name`). Fix: `filename` aus der
  Spaltenliste entfernt (kein Report nutzt sie).
- **`reporting.v_jobs_scan`** fehlte weil die Definition `workflow_name` auswählte, das es
  in `dbo.jobs_scan` nicht gibt (dort `workflow_id`). Fix: `workflow_name` entfernt
  (kein Report nutzt sie).
- **`set_config_from_tenant()`** in `sql_client.py`: Fallback auf `tenant_id` falls
  `printix_tenant_id` leer ist — erleichtert CLI-Tests und direkten Worker-Aufruf.
- **Verifiziert**: `query_top_printers`, `query_cost_report`, `query_top_users`,
  `query_print_stats` liefern jetzt alle Demo-Daten (z.B. `[DEMO] RCH-IMC-OG1-02`,
  monatliche Kostenaufstellung, Top-User aus `demo.users`).

### Wichtig für bestehende Installationen

Nach dem Update muss einmalig das Schema-Setup neu laufen, damit die fehlenden Views
erstellt werden. Entweder über die Web-UI (Azure SQL → "Schema-Setup ausführen") oder
direkt über das `printix_demo_setup_schema` MCP-Tool.

## 3.7.1 (2026-04-10)

### Bugfix: Demo-Datengenerierung + Reports auf ARM64 (SIGSEGV)

- **pymssql als SQL-Treiber auf ARM64**: `sql_client.py` v2.1.0 — auf `aarch64`/`armv7l`
  wird jetzt automatisch `pymssql` statt `pyodbc + FreeTDS` verwendet. FreeTDS crashte
  auf Home Assistant (ARM64) mit SIGSEGV (Worker exit -11) bei Azure SQL-Verbindungen.
- **`_adapt_sql()`**: Konvertiert pyodbc-Platzhalter (`?`) automatisch zu pymssql-Format
  (`%s`) — alle vorhandenen SQL-Statements (Demo-Generator, Reports) bleiben unverändert.
- **`pymssql>=2.3.0`** in `requirements.txt` ergänzt — wird bei jedem Rebuild installiert.
- **`is_configured()`**: `tenant_id` nicht mehr Pflichtfeld (ermöglicht Verbindungen ohne
  Printix-Tenant-ID, z.B. für reine SQL-Tests).

## 3.7.0 (2026-04-10)

### Report Designer Stufe 2 — 11 neue Query-Typen + alle Presets verfügbar

- **11 neue SQL-Query-Funktionen** in `reporting/query_tools.py` (Stufe 2):
  `printer_history`, `device_readings`, `job_history` (paginiert, T-SQL OFFSET/FETCH),
  `queue_stats`, `user_detail`, `user_copy_detail`, `user_scan_detail`,
  `workstation_overview`, `workstation_detail` (graceful fallback falls Tabelle fehlt),
  `tree_meter` (Duplex-Einsparung → Bäume), `service_desk`.
- **`run_query`-Dispatcher** deckt jetzt alle 17 Query-Typen ab (Stufe 1 + 2).
- **Alle 18 Presets verfügbar**: `preset_templates.py` — sämtliche Presets auf
  `available: True` gesetzt, korrekter `query_type` zugewiesen. PDF- und XLSX-Formate
  ebenfalls freigegeben (`available: True`).
- **Bugfix Demo-Generierung (90% Hänger)**: `asyncio.create_task(_bg_generate())`
  fehlte in `app.py` — Hintergrund-Task wurde nie gestartet. Job blieb dauerhaft
  auf „running" stehen. Fix: `create_task` vor `return RedirectResponse` ergänzt.

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
