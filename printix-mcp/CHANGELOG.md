## 6.7.119 (2026-04-27) — iOS/macOS Entra-Login: Field-Name-Mismatch behoben

### Fixed
- **iOS-App "Per Microsoft-Konto einloggen" brach mit „Kein device_code vom Server" ab**: Der Server gibt aus Sicherheitsgruenden **`session_id`** zurueck (echter Microsoft-`device_code` bleibt serverseitig in `desktop_entra_pending`), die geteilte Swift-Bibliothek `PrintixSendCore` las aber `device_code` und schickte beim Poll ebenfalls `device_code` statt `session_id`. Effekt: User-Code wurde angezeigt, aber Polling startete nie / lief gegen falsches Feld.
- **Modell-Fix**: `EntraStartResponse.deviceCode` → `sessionId` (mapped auf `session_id`).
- **API-Fix**: `entraPoll(deviceCode:)` → `entraPoll(sessionId:)`, sendet jetzt Form-encoded `session_id` (Server-Endpoint nutzt FastAPI `Form(session_id)`).
- **Content-Type-Fix**: `entraStart` und `entraPoll` schicken jetzt `application/x-www-form-urlencoded` statt JSON — passend zu den FastAPI `Form()`-Parametern.
- **Betrifft beide Clients**: iOS `LoginView` und macOS `EntraDeviceView` ziehen jetzt `start.sessionId`. Damit funktioniert die Anmeldung mit der server-seitig konfigurierten Entra-App in beiden Apps korrekt — kein eigenes Setup im Client noetig, wie vom Konzept gedacht.

## 6.7.118 (2026-04-23) — Dashboard-KPIs: Cache gegen Azure-SQL-Cold-Start

### Fixed
- **Dashboard zeigte Nullen statt echter Werte**: Root-Cause aus v6.7.117 war der 12s-Cap bei gleichzeitigem Azure-SQL-Cold-Start. Die serverless Azure-SQL-Instanz pausiert bei Nicht-Nutzung — der erste Connection-Versuch dauert 30-60s (TCP-Timeout, dann Spin-Up), alle Folgeverbindungen sind schnell. Der Dashboard-Endpoint machte aber 4-5 Queries seriell, gesamt 30-90s → unser 12s-Cap killte alles → leere KPIs. Der Direkt-Call lieferte korrekte Werte (`month_pages: 65952` etc.), nur eben nach 60-90s.
- **In-Memory-Cache (60s TTL) pro User**: erfolgreiche Responses werden gecached, Folge-Requests kommen instant zurueck. Cache-Hit markiert `_cache_age_s` im Payload.
- **Per-User asyncio.Lock gegen Thundering Herd**: Wenn 5 Tabs gleichzeitig das Dashboard oeffnen, rechnet nur **einer**, die anderen warten auf das Ergebnis. Vorher: 5x Cold-Start parallel = 5x 60s Wartezeit und 5x DB-Aufweck-Druck.
- **Timeout hochgezogen**: Server 12s → 75s, Client 15s → 80s. Reicht fuer Azure-Cold-Start + 4 Queries mit Reserve.
- **Stale-Fallback bei Timeout**: wenn trotz 75s kein Ergebnis, wird der letzte bekannte Cache-Eintrag (auch >60s alt) mit Flag `_stale_after_timeout` zurueckgegeben. User sieht die Werte von letztem Mal statt 0.

## 6.7.117 (2026-04-23) — Dashboard-KPIs: Timeout + robuste Fehleranzeige

### Fixed
- **Dashboard Systemstatus zeigte dauerhaft "…"-Platzhalter**: Wenn `/dashboard/data` haengt (z.B. Printix-API blockiert ohne Response), lief der Client-`fetch` ewig, ohne jemals in `.then` oder `.catch` zu landen — Folge: die Skeleton-Punkte blieben sichtbar, keine Zahl erschien. Jetzt doppelt abgesichert:
  - **Server-Timeout (12s)**: `/dashboard/data` wrappt `asyncio.gather(_load_printers, _load_sql)` mit `asyncio.wait_for(..., timeout=12.0)`. Nach 12s antwortet der Endpoint mit Teilergebnissen (`error_printers/error_sql: "timeout"`).
  - **Client-Timeout (15s)**: `fetch()` bekommt ein `AbortController`-Signal, das nach 15s ausloest. Die Skeleton-Platzhalter werden dann garantiert auf `0` gesetzt (via `clearAll(0)`).
  - **Bessere Console-Diagnostik**: `console.warn`/`console.error` fuer HTTP-Fehler, Backend-Error-Felder und Timeouts — damit der Grund im DevTools-Log sichtbar ist.

## 6.7.116 (2026-04-23) — `network_printers` Strategie 4: Site-Fallback

### Added
- **`printix_network_printers` Strategie 4 `site_fallback`**: Ground-Truth aus dem Delta-Test v6.7.115 — die Printix-API liefert auf Printer-Objekten **weder `networkId` noch `siteId`**. Ein exakter Network→Printer-Filter ist client-seitig damit unmoeglich. Neue letzte Strategie: Network → `get_network` → `site._links` → `siteId`, dann alle Printer des Tenants als Site-scoped Ergebnis zurueckgeben — mit `resolution_strategy: "site_fallback"` und einem ehrlichen Disclaimer im `diagnostics.strategy4_disclaimer`-Feld.
- Damit liefert das Tool ab jetzt **immer** Printer, solange das Network aufloesbar ist. Bei Multi-Site-Tenants ist die Liste breiter als semantisch "richtig", aber das ist die einzige Naeherung die die API hergibt. Wenn Printix spaeter doch strukturelle Felder nachliefert (oder wir einen Site-Filter auf `list_printers` bekommen), schaltet Strategie 2/3 davor wieder auf engere Ergebnisse um — `site_fallback` bleibt ein letztes Sicherheitsnetz.

### Strategien im Ueberblick
1. `network_id_or_link` — direkter Feld/HAL-Link-Match (greift wenn API strukturierte Refs liefert)
2. `network_site_match` — Printer-`siteId` == Network-`siteId`
3. `network_name_match` — Printer-location/siteName/networkName enthaelt Network-Namen
4. `site_fallback` — alle Printer des Tenants, scoped via aufgeloeste Site-IDs
5. `no_strategy_matched` — Network nicht aufloesbar, Diagnose-Sample im Response

## 6.7.115 (2026-04-23) — Hotfix v6.7.114: fehlendes `import re` + network_printers Strategie-Ausbau

### Fixed
- **`printix_resolve_printer` warf `NameError: name 're' is not defined`**: Der v6.7.114-Fix hat `re.split()` benutzt, ohne dass `re` im `server.py` importiert war. Modul-Level-`import re` ergaenzt.

### Changed
- **`printix_network_printers` hat jetzt drei Strategien statt zwei**: Zwischen "direkter Feld-Match" und "Network-Name-Match" liegt jetzt **Strategie 2 `network_site_match`** — wenn das Network eine `siteId` hat (aus `network.siteId` oder `_links.site.href`), werden Printer ueber ihre eigene `siteId` gefiltert. Das ist die saubere Variante wenn die API Site-Referenzen pflegt.
- **Diagnose-Output bei `no_strategy_matched`**: Response enthaelt jetzt ein `diagnostics`-Dict mit den aufgeloesten Network-Namen, Site-IDs, eventuellen `get_network`-Fehlern und einem Sample der ersten 3 Printer-Keys. Damit ist im naechsten Report sofort erkennbar, welche Felder die Printix-Instanz tatsaechlich liefert — statt erneut raten zu muessen.

## 6.7.114 (2026-04-23) — Letzte zwei Delta-Test-Issues: resolve_printer Fuzzy + network_printers Fallback

### Fixed
- **`printix_resolve_printer` findet "Brother Düsseldorf" jetzt auch ueber Feld-Grenzen hinweg**: Bisher reine Substring-Suche auf dem Haystack — wenn "Brother" im `name` und "Düsseldorf" im `siteName` steht, matcht `"brother düsseldorf"` nicht als zusammenhaengender Substring. Jetzt: Query wird tokenisiert, **alle** Tokens muessen irgendwo im Haystack (name + model + vendor + location + siteName + networkName + hostname) vorkommen. Substring-Match bleibt als Schnellpfad fuer Einzelwort-Queries und bekommt einen hoeheren Score. Ergebnisse werden nach Score sortiert.

- **`printix_network_printers` hat einen mehrstufigen Fallback**: Die Printix-API liefert auf Printer-Objekten kein verlaessliches `networkId`-Feld. Der neue Resolver probiert der Reihe nach: (1) direkter Feld-Match (`networkId`, `network_id`, `networks[].id`, `_links.network.href`, `_links.networks[].href`); (2) Wenn nichts greift — Network-Details per `get_network` nachladen, dann Printer ueber `location`/`siteName`/`networkName` gegen den Network-Namen matchen. Das Response-Feld `resolution_strategy` zeigt welche Strategie gegriffen hat (`network_id_or_link` | `network_name_match` | `no_strategy_matched`), damit der naechste Bug-Report nicht raten muss.

### Remaining / bewusst nicht gefixt
- **`printix_decode_card_value` — `decoded_text` leer bei Hex-UIDs**: Delta-Test hat das als "funktional ausreichend" markiert. Hex-UIDs haben schlicht keine ASCII-Repraesentation; das Feld bleibt leer sobald die Bytes nicht 32 ≤ b ≤ 126 sind. Kein Bug.

## 6.7.113 (2026-04-23) — Vier Small-Fixes aus dem Delta-Test

### Fixed
- **`printix_decode_card_value` (leere Felder bei Hex-mit-Trennzeichen)**: `decode_printix_secret_value()` hat bisher nur Base64 versucht. Jetzt: (a) vor dem Base64-Decode werden Leerzeichen/`:`/`-` entfernt — `"04:5F:F0:02"` und `"04 5F F0 02"` funktionieren; (b) zusätzlicher Hex-Fallback für reine Hex-Strings mit `profile_hint: "hex-input"`.
- **`printix_get_card_details` (`card_id`/`owner_id` im Root leer)**: `_extract_card_id_from_api` und `_extract_owner_id_from_card` sehen jetzt rekursiv in Sub-Objects (`card`, `data`, `result`) und Listen (`cards`, `items`, `content`) nach, wenn am Top-Level nichts steht. API-Response-Wrapping bricht den Response-Root nicht mehr.
- **`printix_site_summary` (`network_count: 0` trotz 10 Networks)**: Das ID-Extract lief nur für direkt-Listen-Antworten; bei Dict-Shape (`{"networks": [...]}`) blieb die Menge leer. Neuer `_listify`-Helper normalisiert Networks und Printers einheitlich; wenn keine IDs extrahiert werden konnten (fehlende `networkId`/`id`-Felder), fällt der Counter auf `len(networks_list)` zurück.
- **`printix_capture_status` (`available_plugins: []` trotz aktivem Paperless)**: Zwei Bugs übereinander: (1) Der Import von `capture.base_plugin` triggert die `@register_plugin`-Decorators nicht — nötig ist der Side-Effect-Import von `capture.plugins`. (2) Das Klassenattribut heißt `plugin_name` (lowercase), der Code las `PLUGIN_NAME` und bekam immer den Fallback. Beides behoben; Plugin-Load-Fehler landen jetzt sichtbar im Response statt verschluckt zu werden.

## 6.7.112 (2026-04-23) — Hotfix: `u.tenant_id` existiert nicht

### Fixed
- **`printix_query_audit_log` warf `no such column: u.tenant_id`**: Der v6.7.111-Fix hat eine Regression eingebaut — das Schema der `users`-Tabelle hat gar keine `tenant_id`-Spalte. Die Tenant-Zuordnung läuft über `tenants.user_id → users.id`, nicht umgekehrt. Drei Stellen betroffen und jetzt korrigiert:
  1. **Auto-Resolve in `audit()`**: Subquery jetzt gegen `tenants` (`SELECT id FROM tenants WHERE user_id = ?`) statt gegen die nicht-existierende `users.tenant_id`.
  2. **Back-Fill-Migration**: `UPDATE audit_log SET tenant_id = (SELECT t.id FROM tenants t WHERE t.user_id = audit_log.user_id)`.
  3. **Toleranter Read in `query_audit_log_range`**: Zusätzlicher `LEFT JOIN tenants t ON t.user_id = a.user_id`, und der Fallback-Vergleich ist jetzt `t.id = ?` statt `u.tenant_id = ?`.

### Lesson
Vor einem Schema-referenzierenden Fix immer `PRAGMA table_info` checken — nicht vom Variablennamen (`user["tenant_id"]` kommt aus einem gemappten Dict, nicht aus einer DB-Spalte) auf die Spaltenexistenz schließen.

## 6.7.111 (2026-04-23) — Drei MCP-Tool-Bugs aus dem claude.ai-Full-Test-Report

### Fixed
- **`printix_bulk_import_cards` / `printix_suggest_profile` stürzten mit `ImportError` ab**: `server.py` importierte `apply_profile_transform` aus `cards.transform`, aber die Funktion war nie implementiert worden. Neue Wrapper-Funktion in `src/cards/transform.py` mit Whitelist der erlaubten Rules-Keys — unbekannte Keys werden still ignoriert, damit Profil-Schema-Drift keine Tool-Calls zerlegt. Gleichzeitig liefert `transform_card_value()` jetzt einen `final`-Alias, den die Legacy-Caller erwarten.
- **`printix_query_audit_log` gab `TypeError: '<' not supported between instances of 'datetime.datetime' and 'str'`**: SQL-Server liefert `event_time` via `pymssql` als `datetime`, Demo-Rows kommen als ISO-String. Der Sort mischte beide Typen. Neuer `_etime_sort_key`-Helper in `reporting/query_tools.py` normalisiert auf ISO-String vor dem Vergleich.
- **`printix_query_audit_log` lieferte `rows: 0` obwohl die `audit_log`-Tabelle Einträge hatte**: Alle bisherigen `audit()`-Call-Sites in `web/app.py` riefen ohne `tenant_id`-Argument auf — alle Rows hatten `tenant_id=''`, der Tool-Filter auf den Mandanten schnitt sie weg. Drei-Teile-Fix:
  1. **Auto-Resolve in `db.audit()`**: Wenn kein `tenant_id` mitgegeben wurde, wird er aus `users.tenant_id` des `user_id` nachgeschlagen. Single-Point-Fix für alle 16+ Call-Sites, ohne jede einzeln anfassen zu müssen.
  2. **Back-Fill-Migration**: Alle bestehenden `audit_log`-Rows mit `tenant_id=''` bekommen ihren Mandanten via `UPDATE ... FROM users` nachträglich gesetzt.
  3. **Toleranter Read** in `query_audit_log_range`: Legacy-Rows die trotz Migration noch `tenant_id=''` haben (z.B. System-Events ohne User), werden über das User-Join ebenfalls dem richtigen Mandanten zugeordnet.

### Effekt
Alle drei beim `claude.ai`-Full-Test-Lauf (110 Tools) identifizierten Critical-Bugs sind geschlossen. Die Tools `printix_bulk_import_cards`, `printix_suggest_profile`, `printix_query_audit_log` funktionieren wieder und der Audit-Trail ist pro Tenant sichtbar.

## 6.7.36 (2026-04-17) — Desktop-API: Admin-Tenant-Fallback (robuster als Single-Tenant-Check)

### Fixed
- **v6.7.35-Fallback griff nicht** wenn der eingeloggte User einen eigenen leeren `tenants`-Eintrag hatte (z.B. aus einem manuellen Setup oder Legacy-Zustand). `get_default_single_tenant()` sah zwei Rows, eine davon ohne `printix_tenant_id`, und gab None zurück — damit wurde weiterhin `no_queue` zurückgegeben.

### Added
- **Neue Funktion** `get_admin_tenant_with_queue()` in `cloudprint/db_extensions.py`: findet gezielt den **Admin-Tenant** (via `users.is_admin = 1`), der eine konfigurierte Queue hat. Bei mehreren Admins nimmt sie den ältesten Eintrag (`ORDER BY t.id ASC`).
- **Dreistufige Fallback-Kette** in `/desktop/send` und `/desktop/targets`:
  1. Eigene `get_cloudprint_config(user_id)` mit Parent-Resolution
  2. `get_default_single_tenant()` (nur wenn exakt 1 Tenant-Row)
  3. `get_admin_tenant_with_queue()` (findet immer einen Admin-Tenant mit Queue)
- Log-Zeile zeigt welche Quelle genutzt wurde: `fallback-tenant (single-tenant)` oder `fallback-tenant (admin-tenant)`.

### Effekt
`marcus.nimtz2` (role=user, ohne eigene Printix-Queue) bekommt jetzt `print:self` in der Target-Liste und kann Dokumente senden — der Job wird auf den Admin-Tenant gerouted, Owner via `changeOwner` auf `marcus.nimtz@kofax.com` gesetzt.

## 6.7.35 (2026-04-17) — Desktop-API: Single-Tenant-Fallback für User ohne eigenen Tenant

### Fixed
- **`/desktop/send` scheiterte mit `no_queue` für User ohne eigenen Tenant-Eintrag**: Bei Accounts mit `role_type='user'` aber ohne eigene Printix-Credentials/Queue-Config lief `get_cloudprint_config(user_id)` ins Leere — Folge: `no secure print queue configured`, obwohl der Admin-Tenant des Systems eine konfigurierte Queue hatte.
- **`/desktop/targets`**: Gleiche Seite der Medaille — `print:self` wurde gar nicht erst angeboten.

### Changed
- Beide Endpoints haben jetzt einen **Single-Tenant-Fallback** via `get_default_single_tenant()` (dieselbe Logik wie in der IPP-Routing-Resolution). Wenn der eingeloggte User selbst keine Queue-Config hat, wird bei Single-Tenant-Deployments automatisch die Queue des einzigen aktiven Tenants genutzt.
- Log-Zeile beim Fallback: `Desktop-Send [2/5] fallback-tenant — user='…' → tenant.user_id=… queue=…`.

### Effekt
User `marcus.nimtz2` (role=user) im Test sah nur 2 Delegate-Ziele aber kein `print:self`, und `/desktop/send` quittierte mit `no_queue`. Nach v6.7.35 taucht `print:self` als Default-Ziel auf und der Send läuft durch — Owner wird korrekt via `changeOwner` auf den eingeloggten User gesetzt.

## 6.7.34 (2026-04-17) — Fix: Desktop-Entra-Login — User.Read-Scope statt App-Registration-Scopes

### Fixed
- **403 Forbidden beim `/me`-Call nach Entra-Login**: Die bestehende `start_device_code_flow()`-Funktion war ursprünglich für den **Admin-Auto-App-Registration-Flow** gebaut — sie requestete `Application.ReadWrite.All` + `Organization.Read.All`-Scopes. Damit konnte man zwar SSO-Apps erstellen, aber **nicht das eigene Userprofil** via Graph `/me` abrufen (→ 403).
- **Scope-Parameter eingeführt**: `start_device_code_flow(tenant, scopes=None)`. Wenn `scopes=None`, bleibt das Default-Verhalten (App-Registration). Für Desktop-Login wird jetzt explizit `User.Read offline_access openid email profile` übergeben.
- Der Desktop-Login-Flow funktioniert damit ohne Änderung an der Azure-App-Registration — dieselbe Microsoft Graph CLI Client-ID wird verwendet, nur mit passendem Scope für den Use-Case.

## 6.7.33 (2026-04-17) — Desktop-API: Detailliertes Logging auf allen Endpoints

### Added
- **Strukturierter Request-Log pro Endpoint** (`Desktop: <METHOD /path> peer=… host=… UA=…`) mit Helper `_log_req()` und `_client_info()`.
- **Token-Masking** (`_mask_token`) — nie vollständiger Token im Log, nur letzte 8 Zeichen.
- **Login-Logs** zeigen Quelle (`(local)` / `(Entra)`), UID, Rolle, Device-Name, Peer.
- **Targets-Endpoint** loggt Aufschlüsselung `self=N delegates=M capture=K`.
- **Send-Endpoint** mit 5-stufigem Stage-Logging + Timing:
  - `[1/5] convert` — Format-Konvertierung mit Source-/Target-Größe + Dauer
  - `[2/5] resolved` — Target-Routing + Submit-Email + Queue-ID
  - `[3/5] printer resolved` / `submit OK` — Printix-Printer-ID + Job-ID
  - `[4a/5] blob-upload OK` + `[4b/5] completeUpload OK` — Azure-Upload + Complete-Call
  - `[5/5] changeOwner OK` — Ownership-Transfer
  - `COMPLETE` mit `total_dt=X.Xs` — End-to-End-Timing
- **Exception-Handler** nutzt `logger.exception()` statt `logger.error()` → voller Stack-Trace im Log für Debug-Fälle.
- **Entra-Poll** loggt jede Status-Transition (pending/expired/error/no_match/ok) mit Session-Prefix für Korrelation.

### Vorteile fürs Windows-Client-Debugging
Jeder Request erzeugt eine korrelierte Log-Sequenz. Bei einem fehlgeschlagenen Print-Job sieht man genau in welcher Stage es hakt — Konvertierung, Printix-API, Owner-Wechsel — und mit welchen Parametern.

## 6.7.32 (2026-04-17) — Desktop-API: Entra-SSO via Device-Code-Flow

### Added
- **Neue Endpoints für Entra-SSO-Login vom Desktop-Client**:
  - `POST /desktop/auth/entra/start` — startet Microsoft-Device-Code-Flow. Liefert `session_id`, `user_code` (der Code den der User auf `microsoft.com/devicelogin` eingibt), `verification_uri`, `expires_in`, `interval`.
  - `POST /desktop/auth/entra/poll` — Client pollt im vom Start gelieferten Interval. Status: `pending` / `ok` / `expired` / `no_match` / `error`. Bei `ok` kommt der Desktop-Token + User-Info zurück.
- **Neue Pending-Tabelle** `desktop_entra_pending (session_id, device_code, device_name, created_at, expires_at)` — speichert die laufenden Device-Code-Flows zwischen Start und Poll. Abgelaufene Einträge werden beim Poll automatisch aufgeräumt.
- **User-Mapping**: Entra-OID + Email werden via existierendes `get_or_create_entra_user()` auf einen MCP-User gemappt (gleicher Mechanismus wie beim Web-Login). Unbekannte Entra-User kriegen `status='pending'` und müssen vom Admin approved werden bevor sie einen Token bekommen.

### Flow aus Desktop-Client-Sicht
1. Client: `POST /desktop/auth/entra/start` → zeigt User-Code + `microsoft.com/devicelogin` an
2. User: öffnet die URL im Browser, gibt Code ein, loggt sich mit Entra ein
3. Client: pollt `POST /desktop/auth/entra/poll` alle N Sekunden (N aus Start-Response)
4. Microsoft bestätigt → Server mappt OID auf User → gibt Desktop-Token zurück
5. Ab da läuft der Client mit `Authorization: Bearer <token>` wie beim lokalen Login.

### Vorteile
- Kein lokaler HTTP-Server im Client nötig (funktioniert hinter Corporate-Proxies)
- Gleiche Entra-Config wie der Web-Login (entra_tenant_id / entra_client_id aus Admin-Settings)
- Dual-Login: User kann lokalen Account (`/desktop/auth/login`) ODER Entra-SSO nutzen — der Client zeigt beide Optionen an

## 6.7.31 (2026-04-17) — Desktop-Client-API (Phase A): Token + Targets + Send

### Added — API für Windows-/Desktop-Clients
- **Neues Modul** `src/desktop_auth.py` mit Token-Management:
  - Tabelle `desktop_tokens (token PK, user_id FK, device_name, created_at, last_used_at)`
  - `create_token(user_id, device_name)` → neuer 32-Byte-URL-safe Token
  - `validate_token(token)` → liefert User-Info + bumpt `last_used_at`
  - `revoke_token(token)` + `list_tokens_for_user(user_id)` für spätere UI
- **Neues Modul** `src/web/desktop_routes.py` mit 6 Endpoints:
  - `POST /desktop/auth/login` — Username/Passwort → Token (optional `device_name`)
  - `POST /desktop/auth/logout` — Token widerrufen
  - `GET /desktop/me` — Token-Validation + User-Info
  - `GET /desktop/targets` — Zielliste für aktuellen User:
    - `print:self` — eigene Secure-Print-Queue (Default)
    - `print:delegate:<id>` — pro aktiver Delegation ein Ziel
    - Capture-Profile als Stub für Phase 4
  - `POST /desktop/send` — Multipart-Upload + Dispatch:
    - Format-Auto-Konvertierung via `upload_converter` (PDF/docx/xlsx/pptx/Bilder/TXT)
    - Printix-Submit mit `release_immediately=false` + `changeOwner`
    - Max 50 MB
    - Returns: `job_id`, `printix_job_id`, `owner_email`
  - `GET /desktop/client/latest-version` — Update-Check mit `server_version`, `min_client_version`, `download_url`, `api_version`
- **Auth-Mechanik**: `Authorization: Bearer <token>`-Header wie bei Standard-OAuth — kein Cookie-Sharing mit Web-Session, damit Desktop-Client isoliert bleibt.
- **Audit**: Jeder Submit via Desktop-API landet mit `identity_source='desktop-send'` + `hostname='desktop:<device_name>'` in `cloudprint_jobs`-Tabelle → nachvollziehbar im Log.

### Nächste Phase
**Phase B (v6.7.32)**: Windows-Client-Quellcode als `.NET 8 WPF`-Projekt in `windows-client/` inkl. Build-Anleitung für Mac (`dotnet publish -r win-x64`).

## 6.7.30 (2026-04-17) — Fix: WebUpload-Kachel weiß statt blau

### Fixed
- **WebUpload-Kachel auf Admin-Dashboard** wurde als weißer Block mit winzigem Icon dargestellt. Ursache: `data-tone="sky"` existierte nicht im CSS-Tone-Catalog (nur blue/teal/amber/green/slate/rose/indigo/cyan/emerald/orange/violet). Neuer `sky`-Ton hinzugefügt als blauer Gradient (passend zu „Papier fliegt hoch").

## 6.7.29 (2026-04-17) — Feedback→Roadmap-Merge + Admin-/Mitarbeiter-Dashboards

### Added — Roadmap-Suggestions ersetzen Feedback
- **Schema-Migration**: `roadmap_items.submitted_by_user_id` + `pending_review`.
- **Neue Routen**:
  - `GET /roadmap/suggest` — User-Formular (Titel + Beschreibung)
  - `POST /roadmap/suggest` — legt Item mit `pending_review=1`, `status='idea'` an
  - `POST /roadmap/<id>/approve` — Admin gibt pending Item frei
  - `POST /roadmap/<id>/reject` — Admin lehnt ab (→ `status='rejected'`)
- **Listen-Logik**:
  - Admin sieht **alle** Items inkl. fremde pending (mit ⏳-Badge oben)
  - Normale User sehen approved + **nur ihre eigenen** pending Items
  - Pending Items haben optisch gelben Rahmen + Badge
  - Voting auf pending Items ist deaktiviert bis Review durch
- **Buttons im UI**:
  - Non-Admin sieht „💡 Vorschlag einreichen" statt „+ Neuer Eintrag"
  - Admin sieht Pending-Zähler-Badge wenn offene Reviews vorhanden
  - Approve/Reject-Buttons direkt bei jedem Pending-Item in der Liste
- **Neue Flash-Meldungen** für suggested / approved / rejected.
- **14 i18n-Keys** (Suggestions + Admin-Actions + Badges + Flash) × 14 Sprachen = 196 Übersetzungen.

### Changed
- **Feedback-Nav-Link entfernt** aus Desktop- und Mobile-Nav. Alte `/feedback`-Routen bleiben funktional (Bestandsdaten erreichbar via direkter URL), sind aber nicht mehr prominent verlinkt.

### Admin-Dashboard
- **Umweltwirkung-Kachel raus** → stattdessen **Web-Upload-Kachel** mit 📄-Icon und Link zu `/my/upload`. Das Tile-Grid auf dem Haupt-Dashboard ist jetzt konsistent action-orientiert.

### Mitarbeiter-Dashboard (`/my`)
- **Drei-Kachel-Layout** mit gradient-Karten:
  1. **📄 Dokument drucken** → `/my/upload` (blau)
  2. **🧑‍💼 Delegate Print** → `/my/delegation` (grün) mit Mini-Zählern (↗ ausgehende, ↙ eingehende Delegationen)
  3. **🌳 Umweltwirkung** → `/my/reports` (grün/dunkler)
- Hover-Effekt mit subtilem Lift + Shadow
- Statt der kleinen Kennzahl-Kacheln werden die Delegation-Zahlen direkt in der Delegate-Kachel angezeigt.

### 9 neue i18n-Keys für Dashboards
(dash_tile_web_upload + emp_dash_tile_* × 14 Sprachen)

## 6.7.28 (2026-04-17) — Upload-Konverter: Office/Bilder/Text → PDF + Karten-Seite Crash-Fix

### Added — Upload-Konvertierung
- **Neues Modul** `src/upload_converter.py` mit 3-Tier-Konverter:
  1. **PDF** → passthrough (keine Konvertierung)
  2. **Bilder** (PNG/JPG/GIF/BMP/TIFF) → PDF via **Pillow**
  3. **Text** → einfacher PDF-Renderer via Pillow (Monospace-DejaVu, A4@150dpi)
  4. **Office-Dokumente** (docx/xlsx/pptx/odt/ods/odp/rtf/doc/xls/ppt) → PDF via **LibreOffice headless**
- **Format-Detection** anhand Magic-Bytes + Dateinamen-Endung (ZIP-basierte Office-Dateien werden über die Endung disambiguiert).
- **Error-Handling**: Bei Konvertierungsfehler landet ein user-lesbarer Fehler in der Flash-Message (`upload_wrong_type` oder `upload_error`), nie ein Server-Crash.

### Dockerfile
- **libreoffice-core / libreoffice-writer / libreoffice-calc / libreoffice-impress** + **fonts-dejavu** zum Image dazu (~230 MB zusätzlich, aber dafür komplette Office-Konvertierung ohne externen Service).
- **python3-pil** (Pillow) für Image/Text-Konvertierung.

### Upload-Flow (aktualisiert)
`POST /my/upload` akzeptiert jetzt jedes erkannte Format, konvertiert es intern zu PDF, und sendet anschließend die PDF an Printix (inkl. `changeOwner`). Der Dateiname wird beim Forwarden auf `<name>.pdf` angepasst damit der Printix-Job-Titel passt.

### Fixed — Karten & Codes
- **`/cards` gibt `Internal Server Error` für User ohne Tenant-Config**: Wenn `_cards_tenant_for_user(user)` `None` zurückgab (Mitarbeiter oder frisch registrierter Admin ohne Printix-Credentials), crashte `.get("id", "")` auf None. Jetzt defensiv: fallback auf leeres Dict, `has_card_creds`- und `tenant_configured`-Flags werden ans Template gegeben damit die Seite eine klare Meldung statt Crash anzeigt.

## 6.7.27 (2026-04-17) — Web-Upload direkt in die Secure Print Queue

### Added
- **Neuer Tab „📤 Upload" im Self-Service-Portal** (alle Rollen: Admin/User/Employee). Sichtbar als Sub-Nav-Button auf allen `/my/*`-Seiten.
- **Drag & Drop-Formular** auf `/my/upload`:
  - Drop-Zone mit Hover-Highlight (JS-HTML5-Dragging)
  - Oder Klick → File Picker
  - Anzeige von Dateiname + Größe nach Auswahl
  - Optionen: Farbe on/off, Duplex on/off (Default an), Kopien 1–99
  - Zielqueue wird als Info angezeigt (aus Tenant-Config)
- **Upload-Flow** (`POST /my/upload`):
  1. Datei empfangen + Größen-/Typ-Check (max. 50 MB, PDF-Magic-Bytes)
  2. Tenant-Config + Printix-User-Email resolvieren (über `cached_printix_users`)
  3. `submit_print_job(release_immediately=False, user=…, color, duplex, copies)`
  4. Upload zu Azure Blob + `completeUpload`
  5. **`changeOwner`** auf den eingeloggten User (v6.7.15-Mechanik)
  6. `cloudprint_jobs`-Tracking-Eintrag mit `identity_source='web-upload'`
- **21 neue i18n-Keys** in allen 14 Sprachen (inkl. Dialekte).

### Fehler-Handling
- Kein File / zu groß / Nicht-PDF / keine Config / Printix-Fehler → Flash-Meldung mit klarer Ursache (`flash=upload_error&err=...`).

### Scope-Note
Diese Version unterstützt **nur PDFs**. Office-Konvertierung (docx/xlsx/pptx) ist der nächste Schritt (v6.7.28+) — Architekturentscheidung zwischen LibreOffice-in-Container vs. Gotenberg-Microservice steht noch aus.

## 6.7.26 (2026-04-17) — Öffentliche Roadmap mit Voting

### Added
- **Neue Top-Nav-Rubrik „Roadmap"** (nach „Feedback"), sichtbar für alle eingeloggten User.
- **Roadmap-Items** mit Titel, Beschreibung, Status (`idea`/`planned`/`in_progress`/`done`/`rejected`), Kategorie (`feature`/`fix`/`improvement`/`research`), Priorität (`low`/`medium`/`high`) und optionaler Ziel-Version.
- **Voting-System**: Jeder eingeloggte User hat pro Item genau eine Stimme (Toggle-Mechanik, Herz-Button) — wer schon gevotet hat sieht rotes Herz, sonst leeres. Vote-Count denormalisiert für schnelle Sortierung.
- **Pflege**: Nur Global-Admin kann Einträge anlegen/bearbeiten/löschen (`is_admin`-Check in allen Schreib-Routen). Alle anderen können nur lesen + voten.
- **Routen**: `GET /roadmap`, `GET /roadmap/new`, `POST /roadmap/new`, `GET /roadmap/{id}/edit`, `POST /roadmap/{id}/edit`, `POST /roadmap/{id}/delete`, `POST /roadmap/{id}/vote`.
- **UI**:
  - Status-Filter als Tab-Leiste mit Zählern pro Status
  - Item-Kacheln mit Status-Badge (farbig), Kategorie-Chip, Priority-Indicator und Target-Version
  - Admin-Edit/Delete-Links direkt bei jedem Item
  - Flash-Meldungen für alle Aktionen
- **Neue Tabellen**: `roadmap_items` + `roadmap_votes` (mit `ON DELETE CASCADE`, damit beim Item-Löschen auch Votes verschwinden). Schema-Migration idempotent via `init_roadmap_schema()`.
- **41 neue i18n-Keys** in allen 14 Sprachen (inkl. 6 Dialekten).

### Architektur-Notizen
- Phase 1: Listen-Ansicht + Voting + Admin-CRUD. Geplant für Phase 2: Kanban-Board-View, Kommentare pro Item, Email-Notifications bei Status-Wechsel, automatische CHANGELOG-Verlinkung bei `target_version` + `status=done`.

## 6.7.25 (2026-04-17) — Globaler Mail-Fallback

### Added
- **Admin-Settings**: neue Sektion „Globales Mail-Fallback" mit `global_mail_api_key` / `global_mail_from` / `global_mail_from_name` in `settings`-Tabelle. API-Key wird verschlüsselt gespeichert, im UI nur ein „✓ Gesetzt"-Indikator + Passwort-Placeholder (keine Klartext-Preisgabe).
- **3-stufige Fallback-Resolution** `resolve_mail_credentials(tenant)` in `reporting/notify_helper.py`:
  1. Tenant-eigene `mail_api_key` + `mail_from` aus `tenants`-Tabelle
  2. Globaler Admin-Fallback aus `settings` (neu)
  3. Env-Var `MAIL_API_KEY` / `MAIL_FROM` (bestehend)
- Alle Aufrufer nutzen die Resolution:
  - `send_event_notification` (Log-Alerts, Event-Benachrichtigungen)
  - `send_employee_invitation` (Willkommens-Mails / Bulk-Import)
  - `scheduler._load_tenant_mail_credentials` (Report-Versand)
- `source`-Feld im Resolver-Result (`'tenant'` / `'global'` / `'env'` / `'none'`) → Log-Zeilen zeigen welche Quelle genutzt wurde.
- 10 neue i18n-Keys in allen 14 Sprachen.

### Effekt
Tenants ohne eigene Resend-API-Config können jetzt trotzdem Mails versenden — der Addon-Admin pflegt einmalig einen Fallback-Key unter `/admin/settings`, und alle Tenants teilen sich diese Config als Safety-Net.

## 6.7.24 (2026-04-17) — Queue-Anzeigename + Bulk-Import aller Printix-User

### Added
- **Queue-Anzeigename** unter „Ziel Secure Print Queue" auf `/my/cloud-print`: Statt nur der UUID (`08f43443-2351-49a2-ac1a-3601e4185467`) wird jetzt der klare Name angezeigt, z.B. `Delegation (HJK-Delegation-Printer)` mit der UUID als Sub-Info in klein drunter. Lookup über die bereits geladene Queue-Liste — kein zusätzlicher API-Call.
- **Bulk-Import-Button „Alle einladen & hinzufügen"** auf `/my/employees`. Legt für **alle** gecachten Printix-User in einem Schritt MCP-Employee-Accounts an und verschickt jedem die Willkommens-Mail (via `send_employee_invitation`). 2-stufige Confirmation im UI (erst generische Warnung, dann Counter-Bestätigung `Really send N invitations?`).
- Neuer POST-Endpoint `POST /my/employees/bulk-import` und Flash-Feedback mit Statistik: `{created}` neue Accounts, `{mailed}` Mails verschickt, `{skipped}` übersprungen.
- 4 neue i18n-Keys in allen 14 Sprachen (`emp_bulk_import_action`, `emp_bulk_import_confirm1`, `emp_bulk_import_confirm2`, `emp_bulk_import_flash`) — Dialekte im jeweiligen Dialekt.

### Fixed
- **Cloud-Print-Seite**: der veraltete Printix-Setup-Hinweis mit Pfad `/ipp/<tenant-id>` und falscher Port-443-Referenz entfernt. Stattdessen kompakter Hinweis mit Button zum Setup-Guide (wo die präzise Anleitung inkl. korrektem Port 621 steht).
- Neuer i18n-Key `emp_cloudprint_setup_hint` in allen 14 Sprachen.

## 6.7.22 (2026-04-17) — Fix: verhauenes Quote-Escaping in Employee-Templates

### Fixed
- **Jinja-Template-SyntaxError** in allen Delegate-Print-Seiten (`Internal Server Error` auf `/my`, `/my/jobs`, `/my/delegation`, `/my/reports`, `/my/cloud-print`, `/my/employees`). Der v6.7.21-Bash-Replace hat fälschlich `_(\'emp_setup_guide\')` statt `_('emp_setup_guide')` eingesetzt — der Backslash vor dem Apostroph ist in Jinja-Literalen ungültig. Per `sed` in allen 6 Templates korrigiert.

## 6.7.21 (2026-04-17) — Setup-Guide + Beta-Banner raus

### Added
- **Neuer Setup-Guide-Tab** `/my/setup-guide` (nur für Admin/User). Schritt-für-Schritt-Anleitung zum manuellen Anlegen des Delegation-Druckers in Printix — inkl. konkreter UI-Schritte basierend auf echten Printix-Screenshots:
  1. Drucker manuell hinzufügen via „+" neben der Suche
  2. Netzwerk mit Internetzugriff + Printer-Address `ipps.printix.cloud $$ipps$$port:621`
  3. Manuelle Registrierung via 3-Punkte-Menü beim „1 unregistered printer"
  4. Printer Properties ausfüllen (Name, Vendor, Model, Location, Page Description Language)
  5. Print Queue anlegen („Create print queue" → „Delegation", Active=on)
- Dynamische Werte (IPPS-Host, Port) werden direkt aus der Admin-Config gezogen damit Admins copy-paste-fähige Werte sehen.
- Hints zu DNS, Zertifikat und Port-Forwarding.
- Troubleshooting-Tipp mit Hinweis auf Addon-Log + Owner-Wechsel-Zeilen.
- **24 neue i18n-Keys** in allen 14 Sprachen (DE/EN präzise, FR/IT/ES/NL/NO/SV + 6 Dialekte inhaltlich identisch). Printix-UI-Labels bleiben in Anführungszeichen englisch für bessere UX.

### Removed
- **Beta-Banner** (`_beta_banner.html`) komplett entfernt. Includes aus allen 8 Employee-Templates gestrichen, Datei gelöscht. Delegate Print ist kein Beta-Feature mehr.

## 6.7.20 (2026-04-17) — Cloud-Print-Tab nur für Admin/User sichtbar

### Changed
- **Navigation**: Der Menüpunkt „Cloud Print" in der Delegate-Print-Sub-Navigation ist jetzt für Mitarbeiter-Accounts **versteckt**. Die Seite enthält technische Konfigurationsdetails (Queue-Einrichtung, IPPS-Endpoint-URLs), die Mitarbeiter nicht brauchen und nicht verändern sollen.
- Sichtbarkeit: Admin/User sehen den Tab, Mitarbeiter nicht. Template-Patch in allen 5 relevanten Seiten: `my_dashboard`, `my_jobs`, `my_delegation`, `my_reports`, `employees_list`.

## 6.7.19 (2026-04-17) — Delegate-Titel in Englisch

### Changed
- **Delegate-Job-Titel** ist jetzt englisch — passt besser zur Printix-UI die standardmäßig auch englisch ist. Neue Form: `<Jobname> — delegated by <Owner-Name>`. Beispiel: `Microsoft Word - Test2 — delegated by Marcus Nimtz (Delegate)`.

## 6.7.18 (2026-04-17) — Delegate-Titel Format ohne verschachtelte Klammern

### Changed
- **Delegate-Job-Titel** nutzt jetzt Em-Dash statt Klammern als Separator. Vorher: `Microsoft Word - Test2 (delegiert von Marcus Nimtz (Delegate))` — Schluss-Klammer doppelt wenn der Printix-full_name selbst Klammern enthält. Jetzt: `Microsoft Word - Test2 — delegiert von Marcus Nimtz (Delegate)`.

## 6.7.17 (2026-04-17) — Delegate-Titel mit Klarnamen statt Email

### Changed
- **Delegate-Job-Titel** zeigt jetzt den Klarnamen des Owners statt der Email-Adresse. Statt `Microsoft Word - Test2 (delegiert von marcus.nimtz@marcus-nimtz.de)` erscheint jetzt `Microsoft Word - Test2 (delegiert von Marcus Nimtz)`. Lookup über `cached_printix_users.full_name` — Fallback-Kette: full_name → username → Email (wenn nichts gecached).

## 6.7.16 (2026-04-17) — SM-Filter im Delegate-Picker entfernt (Live-Test)

### Changed
- **`get_printix_delegate_candidates`** zeigt jetzt wieder **alle Printix-User** (auch System-Manager). Der in v6.7.14 eingeführte SM-Filter beruhte auf der Annahme „SM hat keine Release-Queue" — die Annahme entstand als der `user=`-Parameter ignoriert wurde und Jobs sowieso immer beim SM landeten (als OAuth-App-Owner). Mit dem `/changeOwner`-Endpoint aus v6.7.15 ist Ownership-Transfer explizit — ob das für SMs technisch klappt, können wir jetzt live testen.
- Sortierung: SMs stehen in der Liste unten (nach regulären USERs/GUESTs), als sanfter Hinweis dass das der Sonderfall ist.

### Warum
Der User wollte verifizieren ob Admin/SM als Delegate funktioniert — architektonisch möglicherweise doch OK, seit wir nicht mehr vom ignorierten submit-`user=`-Parameter abhängen sondern explizit `POST /jobs/<id>/changeOwner?userEmail=<admin>` aufrufen.

## 6.7.15 (2026-04-17) — Owner-Wechsel via `/changeOwner` — DER finale Fix

### Root-Cause-Analyse (5-Variant-Test)
Mit einem Python-Skript haben wir 5 Varianten des `submit`-Calls gegen die Printix-API gejagt (user=email / user=uuid / userId=uuid / user=uuid+userEmail / ownerId=uuid). Ergebnis: **ALLE** kamen mit identischem `ownerId` zurück — der UUID des OAuth-App-Besitzers (= System-Manager). Das `user=`/`userId=`/`ownerId=`-Feld im `submit`-Call wird **komplett ignoriert**.

Aber in jeder Response lag ein Hinweis verborgen:
```json
"_links": {
  "changeOwner": {
    "href": ".../jobs/{job_id}/changeOwner?userEmail={userEmail}",
    "templated": true
  }
}
```

Es gibt einen **separaten `/changeOwner`-Endpoint** — DER ist was Printix für Ownership-Wechsel erwartet.

### Fixed
- **Owner-Wechsel nach Submit** in beiden Forwarding-Pfaden:
  - `ipp_server.py _forward_ipp_job`: nach erfolgreichem Submit + Upload wird `client.change_job_owner(printix_job_id, user_identity)` aufgerufen → Job landet in der Release-Queue des echten Windows-Users (nicht mehr beim System-Manager).
  - `forwarder.py forward_to_delegates`: nach jedem Delegate-Submit + Upload wird `change_job_owner(sub_pjid, delegate_email)` aufgerufen → Delegate-Kopie landet endlich in der Release-Queue des Delegates.
- **Neue Printix-Client-Methode** `change_job_owner(job_id, user_email)` in `printix_client.py`.

### Effekt
- Original-User druckt aus Word → Job steht in SEINER Release-Queue (nicht mehr bei SM)
- Jede Delegate-Kopie → landet in der Release-Queue des jeweiligen Delegate
- System-Manager-Delegate funktioniert technisch nicht (SM hat keine Release-Queue in Printix) — wurde in v6.7.14 bereits ausgefiltert.

## 6.7.14 (2026-04-17) — Delegate-Picker zieht direkt aus dem Printix-Cache

### Changed
- **Delegate-Kandidaten sind jetzt alle Printix-User des Tenants** (nicht mehr nur MCP-Employees). Vorher konnte man als Delegate nur andere MCP-Accounts unter demselben Admin wählen — völlig unbrauchbar bei einem Tenant mit z.B. 5 Printix-Gästen die aber keine MCP-Accounts hatten.
- **Delegations speichern die Printix-Identität direkt** (`delegate_printix_user_id`, `delegate_email`, `delegate_full_name`). Damit ist kein zwingender MCP-Employee-Spiegel mehr nötig — der Delegate kann ein reiner Printix-User sein.

### Added
- **Schema-Migration**: `delegations`-Tabelle rebuilt mit neuen Spalten `delegate_printix_user_id`, `delegate_email`, `delegate_full_name` und ohne NOT-NULL-Constraint auf `delegate_user_id` (bleibt als optionaler MCP-Link).
- **`get_printix_delegate_candidates(tenant_id, owner_user_id)`** — liefert alle Printix-User aus `cached_printix_users` zurück, abzüglich bereits vergebener Delegationen und System-Managern (die haben keine Release-Queue).
- **`add_printix_delegate(...)`** — neue Delegation ohne MCP-Mirror-Zwang. Prüft Duplikate über Printix-User-ID oder Email.
- **`get_delegations_for_owner`** und **`get_active_delegates_for_identity`** umgestellt auf LEFT JOIN — nutzen primär die Delegations-Zeile selbst (für reine Printix-Delegations), fallen auf den users-Join zurück wenn ein MCP-Mirror existiert.

### UI
- Delegate-Picker im `my_delegation`-Formular listet jetzt alle Printix-User des Tenants mit Rollen-Hinweis (Gast-Markierung bei GUEST_USER).

## 6.7.13 (2026-04-17) — Willkommens-Mail für MCP-Portal-Zugang

### Added
- **Einladungsmail** für automatisch angelegte MCP-Employees: Beim Auto-Mirror nach Printix-User-Anlage verschickt das Addon jetzt eine HTML-Willkommens-Mail an den frischen User mit:
  - MCP-Portal-Login-URL (aus `public_url` Settings)
  - Benutzername
  - Initial-Passwort (`must_change_password=True` → Zwangsänderung beim ersten Login)
  - Admin-Name + Firma
- Neue Helfer: `html_employee_invitation()` + `send_employee_invitation()` in `reporting/notify_helper.py`.
- **Fallback im UI**: wenn Mail-Credentials nicht gesetzt sind (`mail_api_key`/`mail_from`) oder der Mail-Versand fehlschlägt, werden die MCP-Zugangsdaten einmalig im Flash-Panel auf der User-Detail-Seite angezeigt — Admin kann sie manuell weitergeben.
- Bestehender Flash für Printix-Auto-Credentials (Pin, IdCode, Password) wird jetzt tatsächlich im Template ausgespielt (war in v5.20 zwar gesetzt, aber nie gerendert).

## 6.7.12 (2026-04-17) — Delete-Button für alle Rollen + vollständiger Lokal-Cleanup

### Fixed
- **„Benutzer löschen"-Button war nur für Guest-User sichtbar** — Relikt aus v5.x als die Printix-API reguläre USER nicht löschen konnte. Mit der User-Management-API ist das heute problemlos möglich. Button ist jetzt für **alle Rollen** verfügbar (Guest + USER).

### Added
- **Vollständiger lokaler Cleanup beim User-Löschen**. Beim Klick auf 🗑 Löschen passiert jetzt in Folge:
  1. **Printix-API**: `POST /users/{id}/delete` (User in Printix löschen)
  2. **Karten-Mappings**: lokale `cards`-Tabelle für diesen User aufräumen
  3. **TenantCache** (in-memory) invalidieren
  4. **`cached_printix_users`** (persistenter Cache): Zeile entfernen
  5. **MCP-Employee-Spiegel** (Einträge in `users` mit diesem `printix_user_id` und `role_type='employee'`) löschen
  6. **Delegations** in denen der gelöschte MCP-Employee als Owner oder Delegate steht → entfernen
  7. **`cloudprint_jobs`** bleiben erhalten für Audit-Historie
- Resultat: nach dem Delete ist der User sauber weg. Kein Dead-Data mehr das später das IPP-Routing durcheinanderbringen könnte.
- Log-Zeile zum Nachvollziehen: `Delete Printix-User <id>: cache=X employees=Y delegations=Z`

## 6.7.11 (2026-04-17) — Printix-User-Anlage spiegelt MCP-Employee + Cache-Sync

### Added
- **Auto-Mirror bei Printix-User-Anlage**: Wenn ein Admin über `/tenant/users/new` einen Printix-User anlegt, wird gleichzeitig ein lokaler **MCP-Employee** angelegt, verknüpft via `printix_user_id` mit dem aktuellen Admin als `parent_user_id`. Damit ist der neue Printix-User sofort im Delegate-Picker verfügbar — keine doppelte manuelle Pflege mehr.
- **Automatischer Cache-Sync nach User-Anlage**: `sync_users_for_tenant` wird direkt nach einer erfolgreichen `create_user`-API-Antwort getriggert. Der neue User ist sofort in `cached_printix_users` sichtbar für IPP-Routing + Delegate-Validation.

### Architektur-Klarstellung
Die zwei User-Welten bleiben konzeptuell getrennt:
- **MCP-Users** — Logins für unsere App (Admin/Employee)
- **Printix-Users** — Endbenutzer im Printix-Tenant (gecached in `cached_printix_users`)

Aber beim Erzeugen eines Printix-Users über unser UI wird automatisch die Brücke (MCP-Employee mit `printix_user_id`-Link) gebaut — so ist die Delegate-Zuordnung pragmatisch und konsistent.

## 6.7.10 (2026-04-17) — `releaseImmediately=false` — Jobs landen in der Release-Queue

### Fixed
- **Delegate-Jobs waren für den Delegate nicht sichtbar**: Unser Submit-Call schickte `releaseImmediately=true` (Default von `submit_print_job`). Das bedeutet: „Job sofort am Queue-Drucker drucken, keine Release-Queue" — exakt das Gegenteil von dem was Cloud Print Port / Delegate Print braucht. Printix akzeptierte die Submits mit HTTP 200, versuchte sie aber direkt zu drucken statt in die Release-Queue des Owners bzw. Delegate zu legen → für den Delegate unsichtbar.
- **Fix**: Sowohl `ipp_server.py` (Owner-Submit) als auch `forwarder.py` (Delegate-Kopien) übergeben jetzt explizit `release_immediately=False`. Jobs landen in der Release-Queue des jeweiligen Users und können am Drucker freigegeben werden — der eigentliche Sinn von Cloud Print Port.

### Effekt
- Owner `marcus.nimtz@marcus-nimtz.de` sieht den Original-Job in seiner Release-Queue ✓
- Delegate `marcus@nimtz.email` sieht die delegierte Kopie in seiner Release-Queue ✓
- Beide können den Job an einem Drucker ihrer Wahl freigeben

## 6.7.9 (2026-04-17) — Routing-Priorität: reguläre User vor Management-Rollen

### Fixed
- **Eingehende Prints wurden nach v6.7.8 fälschlich auf SYSTEM_MANAGER geroutet**: Der synthetische System-Manager-Eintrag hatte `username` aus der MCP-User-Tabelle übernommen (falsche Annahme: MCP-Username = Printix-Username). Dadurch matchte der Windows-`requesting-user-name=marcus.nimtz` den SYSTEM_MANAGER exakt statt den eigentlich gemeinten GUEST_USER via Email-Local-Part. Resultat: Owner und Delegate waren vertauscht.
- **Zwei Korrekturen**:
  1. Synthetische SM-Einträge haben jetzt **leeren Username** — Matching läuft ausschließlich über E-Mail.
  2. `find_printix_user_by_identity` priorisiert bei mehreren Treffern jetzt **reguläre Rollen** (USER / GUEST_USER) vor Management-Rollen (SYSTEM_MANAGER, SITE_MANAGER). SM-Accounts werden nur noch als Fallback gewählt — typisch für Delegate-an-System-Manager, nicht für eingehende Prints.
- **Legacy-Fix**: Bestehender SM-Eintrag aus v6.7.8 mit falschem Username wird beim nächsten Sync automatisch bereinigt (Username-Spalte geleert).

## 6.7.8 (2026-04-17) — System-Manager automatisch in Printix-Cache

### Fixed
- **Printix-System-Manager fehlten im Cache**: Die Printix-User-Management-API gibt ausschließlich `role=USER` und `role=GUEST_USER` zurück — System/Site/Kiosk-Manager sind NIE dabei (API-Limitation, nicht unser Bug). Das führte dazu, dass der MCP-Tenant-Admin (in der Regel identisch mit dem Printix-System-Manager des Tenants) im Cache fehlte und Delegate-Print an ihn ins Leere lief (Black-Hole-Submit).
- **Auto-Upsert**: Beim regulären User-Sync wird jetzt zusätzlich der MCP-Tenant-Owner aus unserer `users`-Tabelle gezogen und mit `role=SYSTEM_MANAGER` in `cached_printix_users` eingefügt (wenn noch nicht per API-Sync vorhanden). Damit funktioniert Delegate-Print an den System-Manager out-of-the-box.
- Für **Edge-Cases** (MCP-Admin-Email ≠ Printix-System-Manager-Email): manuell in der DB nachpflegen, oder später ein Admin-UI für manuelle Overrides (TODO v6.7.9+).

## 6.7.7 (2026-04-17) — Delegate-Validation gegen Printix-Cache

### Fixed
- **Black-Hole-Submits für nicht-existente Delegate-Emails**: wenn eine Delegate-Email in unserer Delegations-Tabelle nicht zu einem realen Printix-User passt, hat Printix den Submit zwar mit HTTP 200 quittiert, der Job war aber für niemanden sichtbar (kein Owner zuordenbar) → Job verschwand spurlos. Jetzt prüft `forward_to_delegates` vor dem Submit gegen `cached_printix_users`. Bei Mismatch: WARNING ins Log + Tenant-Log mit klarer Anweisung („User in Printix anlegen + Cache neu syncen"), Submit wird übersprungen.

## 6.7.6 (2026-04-17) — Log-Kosmetik nach erstem erfolgreichen End-to-End-Print

### Changed
- **Tenant-Resolution-Log** zeigt jetzt aussagekräftiger: `Printix-User '<display>' (id=…, email=…)` statt nur `printix-user=''` wenn der User in Printix kein `username`-Feld hatte (Fall: Account nur mit Email registriert). Display-Wert ist `username` → `email` → `printix_user_id` Fallback-Kette.
- **User-Resolution-Log** korrigiert auf „via persistenter Printix-Cache" (war noch alter Text aus v6.7.4 als wir die MCP-`users`-Tabelle benutzt haben).

## 6.7.5 (2026-04-17) — Persistenter Printix-User-Cache (P1: Foundation für sauberes Multi-Tenant-Routing)

### Architektur-Korrektur
v6.7.4 hatte den IPP-Username gegen die **MCP-Users-Tabelle** gematcht — das war architektonisch falsch. Die MCP-Users sind unsere App-Logins (Admin/Employee), die Printix-Users sind die Endbenutzer im jeweiligen Printix-Tenant. Beide Welten müssen separat bleiben.

### Added — Persistenter Printix-Cache
- **Neue Tabelle `cached_printix_users`** — Spiegel der Printix-User pro Tenant. Felder: `tenant_id`, `printix_tenant_id`, `printix_user_id`, `username`, `email`, `full_name`, `role`, `raw_json`, `synced_at`. Indices auf `LOWER(username)`, `LOWER(email)`, `tenant_id`.
- **Neue Tabelle `cached_sync_status`** — wann lief der letzte Sync pro Tenant pro Entity-Typ, mit Status und Fehlermeldung.
- **Neues Modul `cloudprint/printix_cache_db.py`** mit:
  - `sync_users_for_tenant(tenant_id, printix_tenant_id, client)` — UPSERT aller Printix-User via `client.list_all_users()`. Stale-User bleiben in der DB (für Log-Nachvollziehbarkeit).
  - `find_printix_user_by_identity(identity)` — Lookup über Username, E-Mail oder Lokal-Part. Detektiert Cross-Tenant-Kollisionen und lehnt Routing in dem Fall sauber ab.
  - `_check_username_collisions(tenant_id)` — Sync-Hook der WARNINGs ins Log schreibt wenn ein Username in mehreren Tenants vorkommt.
- **`resolve_tenant_by_user_identity()` umgebaut** — schaut jetzt in `cached_printix_users` (vorher MCP-`users`).
- **`resolve_user_email()` umgebaut** — gleiche Datenquelle.

### Sync-Trigger
- **Auto-Sync nach Credentials-Save**: wenn der Tenant User-Management-Credentials gesetzt hat → Background-Task pullt alle Printix-User in den DB-Cache. Macht das IPP-Routing sofort einsatzbereit.
- **Manueller Refresh-Endpoint** `POST /tenant/cache/refresh-users` — User-getriggertes Re-Sync. Liefert JSON mit `{ok, count, inserted, updated}` zurück.

### Was ein Admin tun muss damit IPP-Routing funktioniert
1. Unter `/settings` die User-Management-Credentials (`um_client_id` / `um_client_secret`) eintragen + speichern → triggert automatisch den ersten Sync.
2. Optional: später per `POST /tenant/cache/refresh-users` (oder Refresh-Button in v6.7.6) neu syncen.

### Geplant für v6.7.6+
- Refresh-Button im Settings-UI
- Cache für Printer / Queues / Workstations (gleiche Architektur)
- Auto-Refresh wenn Cache älter als 24h beim Login
- Migration der aktuellen TenantCache-Aufrufer (admin/users-Page, employee/cloud-print) auf den DB-Cache als Primary

## 6.7.4 (2026-04-17) — Multi-Tenant-Routing für IPPS via Username-Lookup

### Added
- **3-stufige Tenant-Resolution-Kette** in `_forward_ipp_job`:
  1. **URL-Pfad** — wenn der Pfad eine UUID ist (`/ipp/<tenant-uuid>`), benutze die direkt. Praktisch für curl-Tests + manuelle Setups die explizit die Tenant-ID mitschicken.
  2. **Username-Lookup** — neue Funktion `resolve_tenant_by_user_identity(name)` mappt das `requesting-user-name`-IPP-Attribut über die lokale `users`-Tabelle auf den passenden Tenant. Lookup matcht username UND email (inkl. Local-Part-Match: `marcus.nimtz` matcht `marcus.nimtz@firma.de`). Bei Employees wird der Parent-User zur Tenant-Auflösung verwendet.
  3. **Single-Tenant-Fallback** — neue Funktion `get_default_single_tenant()` liefert den einzigen aktiven Tenant zurück (wenn genau 1 in der DB steht). Damit funktioniert das Setup für Single-Tenant-Installationen ohne weitere Konfiguration.
- **Username → E-Mail-Resolver** `resolve_user_email()` für Printix-`submit_print_job(user=...)` und Delegate-Forwarding. Der Printix-Workstation-Client schickt nur den Username (z.B. `marcus.nimtz`), für Printix-API + Delegate-Lookup brauchen wir aber die E-Mail.
- **Ambiguous-Match-Detection**: wenn ein Username in mehreren Tenants existiert → WARNING im Log, Job wird nicht weitergeleitet (statt falsch geroutet).

### Architektur-Erkenntnis
Im Live-Test mit dem Printix-Workstation-Client haben wir gesehen: **Printix-Cloud schickt die Jobs nicht selbst an unseren IPPS-Endpoint** — der lokale Printix-Client auf dem User-PC macht das direkt. Konsequenz:
- Tenant-ID kommt nicht im URL-Pfad mit (Printix hardcoded `/ipp/printer`)
- Keine HTTP-Header mit Tenant-Info
- Keine TLS-SNI-Info (Uvicorn reicht's nicht durch)
- Einziger eindeutiger Hook ist der `requesting-user-name` (= Windows/Printix-Username)

→ Username-basiertes Routing ist die saubere Lösung für Multi-Tenant in dieser Architektur.

## 6.7.3 (2026-04-17) — Maximal-Logging + Get-Job-Attributes + alle IPP-Gruppen

### Added
- **Vollständiges HTTP-Header-Dump pro IPP-Request** — auf INFO-Level eine kompakte Zeile mit allen empfangenen Headern (`IPP-HTTP: peer=… url=… headers={…}`). Damit sehen wir ob Printix evtl. einen Custom-Header (`X-Printix-Tenant` oder so) sendet, den wir bisher übersehen.
- **Scope-Dump auf DEBUG-Level** — ASGI-Scope inkl. TLS-Extension, Server-Tuple, Client-Tuple, Query-String. Wenn Uvicorn die SNI-Hostname-Info weiterreicht (`scope['extensions']['tls']`), sehen wir's hier — Voraussetzung für späteres Subdomain-Routing.
- **ALLE IPP-Attribut-Gruppen werden geloggt** (nicht mehr nur `operation` + `job`) — `printer`, `document`, `subscription`, `event-notification`, `resource` sowie alle Custom-Gruppen. Jede Zeile zeigt Group + Name + Tag-Hex + alle Werte.
- **Get-Job-Attributes (0x0009) implementiert** — Printix fragte nach dem Submit den Job-Status ab, wir antworteten „Nicht unterstützt" → Printix dachte der Job ist verloren. Jetzt: Dummy-Antwort mit `job-state=completed (9)`. Printix nimmt den Job aus der Outbound-Queue raus.

### Changed
- **`IppRequest`-Datenklasse** um `other_groups: dict[int, dict]` erweitert. Vorher landeten alle Nicht-Operation-Attribute in `job_attrs` als Catch-All — jetzt sauber pro Group-Tag separiert. Neue Convenience-Methode `req.all_groups()` für Logging.

## 6.7.2 (2026-04-17) — Fix: NameError im IPP-Request-Handler

### Fixed
- **`NameError: name '_ipp_op_name' is not defined`** im IPP-Request-Handler — in v6.6.2 hatte ich die Logging-Erweiterung (Operation-Name in der Request-Log-Zeile) ergänzt, aber die `_ipp_op_name`-Funktion nie definiert. Resultat: jeder POST `/ipp/<tenant>` quittierte mit HTTP 500 + Traceback. Helper jetzt mit Mapping aller wichtigen IPP-Operations-IDs (Print-Job, Validate-Job, Get-Printer-Attributes, …) eingebaut.

## 6.7.1 (2026-04-17) — Fix: VERSION ins Container-Image kopieren

### Fixed
- **Banner zeigte alte Version v5.18.10**: das Dockerfile kopierte nur `src/` ins Image, nicht die Top-Level-`VERSION`. In v6.7.0 hatten wir `src/VERSION` gelöscht (Single-Source-of-Truth-Refactor) — dadurch wurde im Container eine alte gecachte VERSION-Layer-Schicht weiterverwendet. Neu: `COPY VERSION /app/VERSION` im Dockerfile sorgt dafür dass die Top-Level-Version garantiert ins Image kommt.

## 6.7.0 (2026-04-17) — TLS direkt im IPP-Listener (echtes IPPS ohne Reverse-Proxy)

### Fixed
- **Single Source of Truth für Version**: vorher gab es zwei `VERSION`-Dateien (`/VERSION` und `/src/VERSION`), die regelmäßig auseinanderliefen — das HA-Addon-Manifest las die eine, der Python-Banner in `server.py` die andere. Resultat: Banner zeigte `v5.18.10` obwohl das Addon bereits auf `v6.6.x` lief. `app_version.py` sucht die Datei jetzt in `/app/VERSION` → Repo-Root → Legacy-Pfad. `src/VERSION` ist gelöscht.

### Added
- **TLS-Termination im Uvicorn-Listener** für den IPP-Port. Printix spricht IPPS = IPP über TLS, das Addon kann jetzt direkt mit Cert/Key terminieren — kein Cloudflare-Tunnel oder Nginx-Proxy mehr nötig.
- Neue Addon-Optionen `ipps_certfile` + `ipps_keyfile` (Default: `/ssl/fullchain.pem` und `/ssl/privkey.pem`). Das ist exakt der Standardpfad, den die HA-Addons **„Let's Encrypt"** und **„DuckDNS"** befüllen.
- Neuer Volume-Mount `ssl:ro` in `config.yaml` damit das Addon auf das `/ssl/`-Verzeichnis von HA zugreifen kann.
- Startup-Log zeigt jetzt explizit `TLS=ENABLED cert=… key=…` oder eine **WARNING**, wenn die Cert-Files fehlen — dann läuft der Listener als Plain-HTTP, und es gibt einen klaren Hinweis warum Printix nicht durchkommt.

### Setup-Hinweis (Empfohlene Architektur)
1. HA-Addon „Let's Encrypt" oder „DuckDNS" installieren und konfigurieren (DNS-01-Challenge via Cloudflare API empfohlen — keine Port-80-Öffnung nötig).
2. Im Router Port-Forward: WAN:621 → HA-IP:621 (TCP).
3. In Printix als Drucker-Host die eigene Domain eintragen (z.B. `ipps.deinedomain.de $$ipps$$port:621`).
4. Cloudflare-Tunnel für IPPS kann komplett entfernt werden — nicht mehr nötig.

## 6.6.2 (2026-04-17) — IPP-Logging auf LPR-Parität + Access-Log an

### Added
- **GET-Handler-Log**: `GET /ipp/<tenant>` (z.B. `curl`-Probe) schreibt jetzt eine Zeile `IPP: GET-Probe von <peer> → tenant=… host=… UA=…`. Vorher schwieg der Handler komplett, wodurch Erreichbarkeitschecks nicht im Log sichtbar waren.
- **Vollständiges PRINT-JOB-Log** mit LPR-Parität: Peer-IP, User-Agent, User, **Identity-Source** (welches IPP-Attribut), Host, Job-Name, Document-Name, Format, Copies, Size, Spool-Pfad — alles in einer kompakten Zeile.
- **WARNING bei leerer User-Identität** — wenn Printix weder `requesting-user-name` noch `job-originating-user-name` setzt, gibt es jetzt eine explizite Warnung im Log (bisher still → Delegate-Forwarding lief ins Leere).
- **DEBUG-Dump aller IPP-Attribute** auf `log_level=debug` (operation + job group) — für Deep-Debugging wenn Printix Felder anders benennt als erwartet.
- **Validate-Job / Get-Printer-Attributes / Get-Jobs / Unsupported-Op** loggen jetzt je eine INFO-Zeile mit Peer + Tenant (vorher nur DEBUG oder gar nicht).
- **Request-Header-Info** in jedem POST: Auth-Header-Präsenz (`auth=yes/no`), Host-Header, User-Agent, Body-Size, Operation-Name.

### Changed
- **`access_log=True`** für den zweiten Uvicorn-Listener auf dem IPP-Port — damit jede Verbindung (inkl. 404 auf falsche Pfade) im Stdout auftaucht. Vorher war er auf `False` gesetzt → unsichtbare Fehlzugriffe.

## 6.6.1 (2026-04-17) — Fix: IPP-Listener-Startup-Rekursion

### Fixed
- **`_start_ipp_listener` rekursiver Spawn** — der zweite Uvicorn-Server hostet die gleiche FastAPI-App, wodurch dessen Startup-Phase unser `@app.on_event("startup")` erneut triggerte. Das führte zu einer Kette von Versuchen, erneut auf Port 621 zu binden → `[Errno 98] address already in use` und Prozess-Abbruch.
- Neuer Guard: Vor dem `create_task(server.serve())` setzen wir `os.environ["_IPP_LISTENER_SPAWNED"] = "1"`. Weitere Startup-Durchläufe (aus der zweiten Uvicorn-Instanz) erkennen das Flag und überspringen den Spawn.

## 6.6.0 (2026-04-17) — LPR komplett entfernt — IPPS ist der einzige Cloud-Print-Eingang

### Removed
- **LPR-Server** (`cloudprint/lpr_server.py`) — komplett gelöscht. Der gesamte RFC-1179-Daemon inkl. Payload-Parser, Workstation-Identity-Resolution und `start_lpr_server()`-Entrypoint entfällt.
- **Admin-LPR-Debug** (`/admin/lpr-debug` + Template `admin_lpr_debug.html`) entfernt — zugehöriger Spool-Viewer und Payload-Hinweise waren nur für das LPR-Tracking relevant.
- **Admin-Settings**: Die LPR-Sektion (URL, Listener-Port, Printix-Setup-Hinweis, „LPR-Debug öffnen") ist aus `admin_settings.html` verschwunden. `lpr_public_url` wird nicht mehr gespeichert.
- **Mitarbeiter-Cloud-Print**: Der aufklappbare Legacy-LPR-Block auf `/my/cloud-print` ist entfernt.
- **Add-on Manifest**: Port `5515/tcp` und die Addon-Option `lpr_port` sind aus `config.yaml` gestrichen. In `run.sh` ist der LPR-Export und die LPR-Banner-Zeile raus.
- **Startup-Event** `_start_lpr_server()` in `web/app.py` gelöscht — es wird nur noch `_start_ipp_listener()` gestartet.

### Changed
- **Neues Modul** `cloudprint/forwarder.py` mit der protokoll-agnostischen Funktion `forward_to_delegates()` (vormals privat in `lpr_server.py`). `ipp_server.py` importiert jetzt von dort.
- **Grund**: IPPS liefert die User-Identität als IPP-Attribut direkt im Request — kein UUID-Lookup über die Printix-API nötig. System-Manager-Jobs werden damit korrekt zugeordnet (was der Haupt-Painpoint bei LPR war).

### Deployment-Hinweis
**Rebuild des Home-Assistant-Addons** nötig (nicht nur Restart!). Home Assistant übernimmt die geänderten Ports erst beim Rebuild. Port 5515 kann anschließend im Router/Firewall/Cloudflare-Tunnel freigegeben werden — er wird nicht mehr belegt.

## 6.5.2 (2026-04-17) — IPP-Port in Addon-Manifest + IPP_PORT-Env aus Options

### Fixed
- Addon-Manifest `config.yaml` exposed jetzt Port **621/tcp** unter `ports:` — ohne das war der IPP-Listener im Container nicht von außen erreichbar (`Connection refused`).
- Neue Addon-Option `ipp_port: 621` in Schema + `run.sh`: Port wird als `IPP_PORT`-Env in den Container exportiert → `_start_ipp_listener` im FastAPI-Startup findet den Port und startet den zusätzlichen Uvicorn-Listener.
- Startup-Banner in `run.sh` zeigt jetzt explizit `IPP/IPPS Listener: Container-Port 621` neben dem LPR-Eintrag.
- `VERSION`-File ergänzt (fehlte) — Fallback auf `0.0.0` bei Startup-Log behoben.

### Deployment-Hinweis
**Für das Update ist ein Rebuild** des HA-Addons nötig (nicht nur Restart!). Home Assistant übernimmt neue Ports im `config.yaml` erst beim Rebuild.

## 6.5.1 (2026-04-17) — Beta-Hinweis für Delegate Print

### Added
- **Beta-Banner** 🧪 oben auf allen Delegate-Print-Seiten (`my_dashboard`, `my_jobs`, `my_delegation`, `my_reports`, `my_cloud_print`, `employees_list`, `employees_detail`, `employees_new`).
- Orange/Gelb-Gradient mit klarem „BETA"-Pill-Badge — dezent aber sichtbar.
- Wiederverwendbares Include `employee/_beta_banner.html` (1 Stelle ändern = alle Seiten aktualisiert).
- 3 neue i18n-Keys (`emp_beta_title`, `emp_beta_subtitle`, `emp_beta_hint`) in 12 Sprachen.

## 6.5.0 (2026-04-17) — IPPS-Endpoint als empfohlener Cloud-Print-Kanal

### Added
- **IPP/IPPS Server** (`cloudprint/ipp_parser.py` + `cloudprint/ipp_server.py`): minimal-viable Implementation von RFC 8010/8011. Akzeptiert Print-Job, Validate-Job, Get-Printer-Attributes, Get-Jobs. Unterstützte IPP-Version 1.1 + 2.0. Reine HTTP-Ebene — TLS-Termination macht Cloudflare-Tunnel oder Reverse-Proxy.
- **Killer-Vorteil**: Die User-Identität kommt als IPP-Attribut (`requesting-user-name` / `job-originating-user-name`) direkt im Request mit — keine UUID-Auflösung via Printix-API mehr nötig. System-Manager-Jobs werden damit endlich auch korrekt zugeordnet.
- **Zusätzlicher Uvicorn-Listener** auf konfigurierbarem IPPS-Port (z.B. 621) neben dem Haupt-Web-Port. Läuft als asyncio-Task. Wird nur gestartet wenn `ipps_port` in Admin-Settings != WEB_PORT.
- **Admin-Settings**: Neue Felder "IPPS Endpoint-URL" + "IPPS Listener-Port" inkl. Cloudflare-Hinweis.
- **Employee Cloud-Print-UI**: IPPS-Endpoint wird prominent als empfohlenes Protokoll angezeigt, LPR ist unter aufklappbaren "Legacy"-Block verschoben.
- **Delegate-Forwarding** funktioniert identisch für IPPS — die `_forward_to_delegates()`-Funktion wird wiederverwendet.

### Fixed
- `rpt_eng_title_hour_dow_heatmap` (und weitere Stufe-2-Report-Titel) wurden als roher i18n-Key im Report-Titel angezeigt. Zwei Ursachen: (1) `_LBL_DEFAULTS` in `report_engine.py` hatte für Stufe-2-Reports keine englischen Fallbacks → ergänzt. (2) Weder Scheduler noch Preview-Handler hatten `labels=` an `generate_report()` übergeben → jetzt wird `rpt_eng_*`-Dict aus `TRANSLATIONS[lang]` gebaut und durchgereicht.

### i18n (12 Sprachen)
- 20 neue IPPS-Keys: `admin_ipps_*` (9), `emp_ipps_*` (9), `emp_lpr_legacy_*` (2).

### Architektur-Hinweis
LPR bleibt weiterhin verfügbar und unverändert — wir erzwingen keine Migration. Im UI sind IPPS und LPR jetzt aber klar als "empfohlen" / "Legacy" gekennzeichnet, und die Printix-Drucker-Syntax für IPPS (`host $$ipps`) wird im Admin-Banner direkt zum Kopieren angezeigt.

## 6.4.2 (2026-04-17) — Delegate Print: UX-Verbesserungen + Admin-Hilfen

### UX
- **Navigation für Employees aufgeräumt**: Mitarbeiter-Accounts (`role_type = 'employee'`) sehen jetzt **nur noch** „Delegate Print" / „Hilfe" / „Abmelden" — die Register Dashboard, Settings, Management, Cards, Reports, Capture, Logs, Feedback sind versteckt. Keine toten Links mehr für Mitarbeiter.
- **Delegation-Picker vereinfacht**: Das Typeahead-Dropdown wurde durch ein simples, browser-natives `<select>` mit allen verfügbaren Kollegen ersetzt. Robuster, immer funktionsfähig, keine JS-Debugging-Fallstricke mehr.
- **„Meine Druckjobs" Debug-Hilfe**: Wenn Deine Match-Liste leer ist, aber im Tenant Jobs empfangen wurden, zeigt ein Warnhinweis die letzten 5 Jobs mit ihrer `detected_identity`. So sieht der User welche UUID Printix für ihn meldet und kann die passende `printix_user_id` im Admin-User-Edit eintragen.

### Auto-Resolve
- **Neuer Button „🔍 Automatisch suchen"** neben dem Printix-User-ID-Feld unter `/admin/users/{id}/edit`. Probiert zuerst `list_users?query=<email>` (funktioniert für USER/GUEST_USER), fällt zurück auf `list_print_jobs` + Scan nach `ownerEmail = target.email` (funktioniert auch für System Manager, die Print-Jobs produziert haben). Setzt die gefundene UUID direkt in das Feld.

### Match-Logik
- `get_cloudprint_jobs_for_employee()` matched jetzt zusätzlich gegen `delegated_from` — Delegate-Kind-Einträge werden damit korrekt dem Delegate zugeordnet.

### Neue i18n-Keys (12 Sprachen)
- `admin_printix_user_id_resolve`, `_searching`, `_found`, `_notfound`, `_via_list`, `_via_jobs` — UI-Texte für Auto-Resolve-Button
- `emp_unmatched_recent_title`, `emp_unmatched_recent_hint` — Debug-Hinweis bei leerer Job-Liste
- `emp_delegate_no_candidates` — Info wenn keine Kollegen für Delegation vorhanden sind
- `admin_printix_user_id`, `admin_printix_user_id_hint` — Label + Hilfetext für das Manual-ID-Feld

### LPR-Server
- Beim Failed-Owner-Lookup (System Manager Case) gibt es einen **zusätzlichen Fallback auf die lokale DB**: Wenn ein Admin die `printix_user_id` eines lokalen User-Accounts manuell gesetzt hat, wird diese Zuordnung auch ohne Printix-API-Auflösung erkannt. Plus eine Warnung ins Tenant-Log mit Handlungsanweisung.

## 6.4.1 (2026-04-17) — Delegate Print: Owner-Resolution via list_users-Fallback

### Fixed
- Bei Tenants die **nur** User-Management-Credentials konfiguriert haben (ohne Card Management) schlug `get_user(owner_id)` mit 404 fehl — die UM-API unterstützt den `/users/{id}`-Detail-Endpoint nicht.
- Folge: Der LPR-Forwarder kannte als Owner nur die nackte Printix-UUID, das Delegate-Lookup in der lokalen DB matched aber primär auf E-Mail → Delegate-Forwarding wurde übersprungen („keine aktiven Delegates für &lt;uuid&gt;").

### Neuer Flow
1. `get_user(owner_id)` wird probiert (funktioniert mit Card-API).
2. Bei Fehler: `list_all_users()` via `tenant_cache` (Login-Prefetch hält ihn warm).
3. Suche nach `id == owner_id` in der Liste → E-Mail extrahieren.
4. Diese E-Mail wird als `owner_identity` für das `delegations`-Lookup genutzt.

Damit klappt die Delegate-Resolution auch wenn nur UM-Credentials gesetzt sind. Im Log erscheint jetzt `identity_source = "printix-list-lookup"` statt `"printix-owner-id"`.

## 6.4.0 (2026-04-17) — Delegate Print: echte Job-Duplizierung für Delegates

### Added
- **Delegate-Forwarding im LPR-Server**: Nach erfolgreichem Original-Submit wird der Job für jeden **aktiven** Delegate des erkannten Owners zusätzlich an Printix gesendet — mit dem Delegate als `user=` Parameter. Damit sieht jeder Delegate eine eigene Job-Kopie am Drucker-Display und kann ihn dort releasen.
- **DB-Schema**: `cloudprint_jobs.parent_job_id` + `cloudprint_jobs.delegated_from` (beide optional, leer bei normalen Jobs) — Kind-Einträge referenzieren den Haupt-Job und speichern den Original-Owner.
- **Helper `get_active_delegates_for_identity(tenant_id, owner_identity)`**: Matched die Owner-Identität (E-Mail oder Printix-User-ID) gegen `users` und liefert alle Delegates mit `delegations.status = 'active'` und `users.status = 'approved'`.
- **Auto-aktive Delegationen**: Neu angelegte Delegations landen direkt auf `status='active'` — kein Genehmigungsschritt mehr nötig. Employees können ihre Delegates sofort nutzen.
- **Delegation-Badge** in „Meine Druckjobs": Kind-Einträge zeigen „🤝 delegiert von &lt;Owner&gt;" + Tooltip-Hinweis dass der Job am Drucker abgeholt werden kann.

### Flow-Beispiel
```
1. Anja druckt via Printix Client → LPR-Gateway empfängt Job
2. Gateway identifiziert Owner via ownerId → „anja@firma.de"
3. Gateway submittet Job an Printix Secure Print Queue (Owner: Anja)
4. DB-Lookup: Anja hat aktive Delegation → Delegate: Marcus
5. Gateway submittet Kopie mit user=marcus@firma.de
6. Am Drucker: Anja UND Marcus sehen je ein Job-Exemplar
7. Wer auch immer zuerst rausholt, druckt ihn
```

### UI
- `emp_cloud_job_delegated_from` + `emp_cloud_job_delegated_tooltip` in 12 Sprachen.
- `.delegation-badge` CSS — gelbes Pill-Badge neben dem Job-Titel bei delegierten Einträgen.

### Backwards-Kompat
- Bestehende Delegations mit `status='pending'` bleiben pending (werden nicht automatisch aktiviert). Nur neue Einträge sind sofort aktiv.
- Jobs ohne Delegates verhalten sich wie bisher (kein Mehrfach-Submit).
- Fehler beim Delegate-Submit loggen nur — der Original-Job ist bereits erfolgreich weitergeleitet.

## 6.3.0 (2026-04-17) — Report „Benutzer Druckdetails": E-Mail-Feld im Formular

### Added
- Neues Formular-Feld **„Benutzer (E-Mail)"** in `reports_form.html` für die drei User-Detail-Report-Typen (`user_detail`, `user_copy_detail`, `user_scan_detail`).
- Leer lassen = aggregierte Übersicht aller User. E-Mail eintragen = Report auf diesen einen Benutzer gefiltert.
- Backend-Param `user_email` in beiden POST-Routen (`/reports/new` + `/reports/{id}/edit`) + `_merge_query_params()` schreibt den Wert in `query_params["user_email"]`.
- Neue i18n-Keys `rpt_user_email` + `rpt_user_email_hint` in 12 Sprachen.

## 6.2.2 (2026-04-17) — SQL-Client Log-Spam reduziert

### Fixed
- `_prefer_pymssql()` loggte die Treiber-Auswahl bei **jeder** SQL-Query erneut — damit wurde der Log mit Einträgen wie `"ARM64 erkannt (aarch64) — verwende pymssql statt pyodbc/FreeTDS"` regelrecht geflutet (3-4 × pro Dashboard-Request).
- Jetzt wird die Entscheidung beim ersten Aufruf in `_PYMSSQL_DECISION` gecacht, der Info-Log erscheint **einmalig** beim Start und ist auf Level `INFO` hochgezogen (statt `DEBUG`) damit man ihn im normalen Betrieb-Log sieht.

## 6.2.1 (2026-04-17) — Fix Report „Benutzer Druckdetails" Preview-Crash

### Fixed
- `/reports/{id}/preview` warf 500 beim Preset **„Benutzer Druckdetails"** (`user_detail`):
  `TypeError: query_user_detail() missing 1 required positional argument: 'user_email'`. Das Preset liefert kein `user_email`, der `_filter_kwargs_to_sig()`-Dispatcher reichte das fehlende Pflicht-Argument direkt weiter.
- `query_user_detail()` nimmt `user_email` jetzt als optionalen Parameter (default `""`). Bei leerem Wert entfällt der WHERE-Filter und die Query liefert eine aggregierte Übersicht aller User — ideal für Preset-Previews.

## 6.2.0 (2026-04-17) — Login-Prefetch (Cache Stufe 2) + Rename „Printix → Management"

### Login-Prefetch (Stufe 2)
- **`cache.prefetch_tenant(tenant, client)`** lädt parallel via `asyncio.gather` die wichtigsten Topics (users, printers, workstations, sites, networks, groups) und legt sie im zentralen TenantCache ab. Einzelne Topic-Fehler stoppen die anderen nicht.
- **`cache.schedule_prefetch(tenant, client_factory)`** startet das Prefetch als Background-Task via `asyncio.create_task` — der Login-Handler blockiert nicht, der User landet sofort auf dem Dashboard. Der Prefetch läuft parallel weiter.
- **Skip-Logik**: Wenn bereits ein Prefetch für den Tenant läuft ODER der Users-Cache noch frisch ist (< 2 Min), wird nicht noch einmal geladen.
- **`cache.prefetch_status(tenant_id)`** liefert „idle" / „running" / „done" / „error" — Basis für spätere UI-Indikatoren.
- Eingehängt an **beiden Login-Pfaden**: klassischer `POST /login` und der Entra-ID OAuth-Callback `/auth/entra/callback`.
- Alle Prefetch-Fehler werden nur geloggt — Login-Flow bleibt unangetastet.

### Umbenennung
- Nav-Eintrag „Printix" → **„Management"** in allen 14 Sprachen. Die Route `/tenant/*` bleibt unverändert, nur das Label ändert sich.

## 6.1.0 (2026-04-17) — Globaler Tenant-Cache (Stufe 1)

### Neuer zentraler In-Memory-Cache
- **`cache.py`** — TenantCache-Singleton mit TTL pro Topic (Users 10 min, Workstations 2 min, Printers/Queues 10 min, Sites/Networks/SNMP 30 min, Karten pro User 15 min). Thread-safe via `RLock`, Sub-Keys für Detail-Objekte (z. B. Cards pro User-ID).
- **`format_age()`** Helper für UI: „gerade eben" / „vor 45 s" / „vor 3 Min." / „vor 2 Std."

### Gecachte Tenant-Routes
- `/tenant/users` nutzt den zentralen Cache statt des alten einzelnen User-Caches. Filter-Chips und Pagination sind ab dem 1. Aufruf sofort.
- `/tenant/printers` und `/tenant/queues` teilen sich einen Cache (beide basieren auf `list_printers`). Suche wird lokal nach dem Cache-Hit angewendet — kein API-Call pro Filter-Klick mehr.
- `/tenant/workstations` cached mit 2 min TTL (Status ändert sich häufiger). Suche lokal.

### Cache-Verwaltung
- **`POST /tenant/refresh?topic=users&back=…`** invalidiert gezielt ein Topic (oder alles mit `topic=all`) und springt zurück zur Quell-Seite.
- **Cache-Refresh-Widget** `templates/_cache_refresh.html` — wiederverwendbares Include mit „🔄 Aktualisieren"-Button + „Stand: vor 3 Min."-Anzeige.
- **Logout löscht** den Cache des Users (frische Daten beim nächsten Login).
- **Automatische Invalidierung** bei `/tenant/users/create` und `/tenant/users/{id}/delete` (war schon in v6.0.1 verankert, nutzt jetzt das zentrale Modul).

### Bugfixes
- `/dashboard/data` stürzte mit `TypeError: Object of type date is not JSON serializable` ab, wenn die SQL-Queries `datetime.date`-Objekte lieferten. Neuer `_json_safe()`-Rekursiv-Konverter übersetzt `date`/`datetime`/`Decimal`/`bytes` in primitive JSON-Typen bevor die Response gerendert wird.

### Neue i18n-Keys (12 Sprachen)
- `cache_last_loaded` — „Stand" / „Last loaded" / „Actualité" / …
- `cache_refresh_title` — Tooltip „Daten frisch von Printix laden"

## 6.0.1 (2026-04-17) — Users-Cache + Fix Checkbox-Layout

### Performance
- **In-Memory-Cache für Tenant-User-Liste** (60 s TTL pro Tenant): `list_all_users()` wird nicht mehr bei jedem Filter-Klick erneut gegen Printix ausgeführt. Filter-Chips sind sofort.
- **Parallele Karten-Zählung**: Die ~10 `list_user_cards()`-Calls pro sichtbarer Seite laufen jetzt über `asyncio.gather` parallel statt seriell (~2 s → ~200 ms). Zusätzlich 2-Minuten-Cache pro User-ID.
- **Cache-Invalidierung** bei `/tenant/users/create` und `/tenant/users/{id}/delete`, damit Änderungen sofort sichtbar sind.

### UI-Fix
- Checkboxen im User-Create-Formular (E-Mail-Optionen) waren versetzt weil die Labels den Block-Stil aus `.form-group label` geerbt hatten. Jetzt mit eigenem Flex-Layout: Checkbox links, fette Überschrift + Hinweistext rechts, ganze Zeile anklickbar, Hover-Highlight.

## 6.0.0 (2026-04-17) — Users, Cards, Delegate Print & Dashboard-Refresh

### Users & Cards (Printix-Verwaltung)
- **User Management API integriert**: `create_user()` akzeptiert jetzt `role="USER"` für dauerhafte E-Mail-Accounts (zusätzlich zu `GUEST_USER`), nutzt die neue User-Management-Client-Credentials wenn vorhanden. `delete_user()` funktioniert entsprechend für beide Rollen.
- **Ein-Call-Listing**: `list_users()` schickt per Default `role=USER,GUEST_USER` als Komma-Liste — beide Gruppen in einer API-Response. Neue Hilfsfunktion `list_all_users(query=…)` paginiert automatisch durch alle Seiten.
- **`create_user`-Response-Unwrapping**: Neue `PrintixClient.extract_created_user(response)` liefert das erzeugte User-Dict aus dem `{"users":[{…}], "page":{…}}`-Wrapper. Auto-generiertes `pin`, `idCode`, `password` werden einmalig in der Flash-Session abgelegt.
- **Create-Formular überarbeitet** (`/tenant/users/create`): Role-Umschalter (Gast / Benutzer), Welcome-Mail + Expiration-Mail Checkboxen, aufklappbare Advanced-Optionen (PIN, Passwort, Ablaufdatum).
- **Karte direkt beim Anlegen** (optional): Neuer Abschnitt im Create-Formular — Kartennummer + Profildropdown. Nach User-Erstellung wird `register_card()` ausgeführt und das lokale Card-Mapping (inkl. Transform-Preview) persistiert.
- **Benutzer-Suche erkennt Kartennummern**: `/tenant/users?search=…` durchsucht zusätzlich `card_mappings.search_blob` — gefundene Karten-Treffer landen als roter Badge in der Liste.
- **Filter-Chips**: `All` / `Users` / `Guests` oben auf der Liste; Rollen-Labels umbenannt auf "Benutzer" / "Gast".

### Delegate Print (Employee-Portal)
- **Meine Cloud-Print-Jobs**: Neue hübsche Darstellung unter `/my/jobs` — LPR-getrackte Jobs mit Status-Pills, Stats-Kacheln, Format-Icons, Fehler-Banner.
- **Identitäts-basierter Filter**: `get_cloudprint_jobs_for_employee()` matched `detected_identity` / `username` gegen alle bekannten Identity-Felder des eingeloggten Users (`printix_user_id`, `email`, `username`, `full_name`).
- **Delegation-Typeahead**: Statt Vollliste-Dropdown gibt es jetzt Live-Suche via `GET /my/delegation/search?q=` — skaliert auf Tenants mit vielen Mitarbeitern. Neue DB-Funktion `search_available_delegates()`.

### Dashboard
- **Lazy-Loading**: `/dashboard` rendert sofort ohne API-/SQL-Calls (< 100 ms), alle KPIs/Umwelt-Daten werden per JS über `/dashboard/data` nachgeladen.
- **Parallel-Calls**: `/dashboard/data` ruft Printix-Printer-Count und SQL-KPIs via `asyncio.gather` parallel — keine Latenz-Addition mehr.
- **Umweltkachel responsive**: Zahlen werden kompakt formatiert (z. B. `12,3K`), `clamp()`-Schriftgröße + `text-overflow: ellipsis` verhindern Überlaufen der Kachel.
- **Skeleton-Placeholder**: Statt `0` erscheint `…` bis die Daten da sind.
- **Druckerflotte entfernt**: Nav-Eintrag `/fleet` + Dashboard-Kachel raus; der Zero-Trust-Package-Builder bleibt erreichbar über seine eigene Kachel.
- **Delegate-Print-Kachel**: Neue Kachel im gleichen Muster (🧑‍💼 → `/my`).

### Neue i18n-Keys (14 Sprachen)
- Tenant-Liste: `tenant_search_all`, `tenant_filter_*`, `tenant_role_user`, `tenant_role_guest`, `tenant_card_match_*`
- User-Create: `user_create_role_*`, `user_create_add_card*`, `user_create_card_*`, `user_create_email_options`, `user_create_send_*`, `user_create_advanced`, `user_create_password*`, `user_create_expiration*`, `user_create_needs_um_creds`
- Delegation: `emp_delegate_search_placeholder`, `emp_delegate_no_results`
- Employee-Jobs: `emp_my_cloud_jobs_title`, `emp_my_cloud_jobs_sub`, `emp_cp_stat_total`, `emp_no_cloud_jobs`, `emp_printix_jobs_sub`
- Dashboard: `dash_tile_delegate_print`, `dash_tile_delegate_print_sub`

## 5.19.0 (2026-04-17) — User Management API Credentials

### Added
- New **User Management API** credentials section in registration wizard (step 2) and tenant settings, right after the Workstation API block.
- DB schema columns `tenants.um_client_id` and `tenants.um_client_secret` (secret encrypted at rest via Fernet) — applied via idempotent migration.
- `PrintixClient` now accepts `um_client_id` / `um_client_secret` and manages a separate token for the User Management area (falls back to shared credentials when not set).
- User Management credentials are propagated through every PrintixClient instantiation (web app, MCP server, LPR forwarder, event poller, employee self-service).
- i18n keys `px_um_client_id`, `px_um_secret`, `settings_user_management_api`, `reg_api_user_management_summary` across all 14 supported languages.

## 5.18.10 (2026-04-16) — User Assignment Visibility

### Changed
- Added a new assignment view in `Administration > Benutzer` so the global administrator can immediately see which accounts are global admins, tenant admins, or employees linked to a specific tenant admin.

## 5.18.8 (2026-04-16) — Employee Self-Service Guard

### Fixed
- Fixed imported `employee` users to land in `Delegate Print` after login and password activation instead of the general dashboard.
- Added a dedicated web guard so `employee` users are redirected away from the main admin/tenant areas and stay inside the self-service `Delegate Print` area.

## 5.18.7 (2026-04-16) — Delegate Print Tenant Import

### Added
- Moved the employee management flow under `Delegate Print` and added direct tenant-user import from Printix to create employee logins linked to a real `printix_user_id`.
- Added temporary-password onboarding for imported Delegate Print users so they can sign in immediately and change their password on first login.

### Changed
- Renamed the former `My Portal` navigation entry to `Delegate Print` across all supported languages.

## 5.18.6 (2026-04-16) — LPR Workstation Identity Hints

### Added
- Added hostname-based workstation matching for LPR jobs to derive stronger user/owner hints from Printix workstation data when available.
- Added identity source tracking so the debug view now shows whether a hint came from the LPR payload, a workstation match or the Printix job owner.

## 5.18.5 (2026-04-16) — LPR Owner Lookup Fallback

### Fixed
- Fixed read-only Printix user lookups to fall back to Print API credentials when Card Management credentials are not configured.
- This allows LPR owner hints from `ownerId` to resolve more often in Cloud Print setups that only use Print API credentials.

## 5.18.4 (2026-04-16) — LPR Submit Response Handling

### Fixed
- Fixed LPR forwarding to handle the current Printix `submit` response shape with nested `job` payloads and `uploadLinks`, so successful submits are no longer treated as errors.
- Added owner lookup via `ownerId` from the Printix job response and reuse that identity as a stronger job-origin hint when available.
- Added support for upload-specific response headers when sending the print file to the Printix storage URL.

## 5.18.3 (2026-04-16) — LPR Metadata Visibility

### Added
- Added deeper LPR job tracking with stored control-file fields, payload preview hints and a best-effort detected identity for each received cloud print job.
- Expanded the admin LPR debug view so each job now shows raw LPR control fields and readable payload hints in all supported languages.

## 5.18.2 (2026-04-16) — LPR Submit Payload Hotfix

### Fixed
- Fixed Printix LPR forwarding so `submit` now normalizes detected MIME types like `application/vnd.hp-pcl` to valid Printix PDL values such as `PCL5`.
- Fixed the v1.1 `submit` call to always send a structured JSON body with the required `version` header, avoiding 400 errors about wrong body format.

## 5.18.1 (2026-04-16) — LPR Port Startup Hotfix

### Fixed
- Fixed the LPR listener startup so stale database values no longer force port `515` when the add-on is configured to run on `5515`.
- Updated Cloud Print/LPR UI hints across languages to consistently show the current default listener port `5515`.

## 5.18.0 (2026-04-16) — LPR Listener Setup And Debug UX

### Added
- Added a dedicated LPR port exposure (`5515/tcp`) to the add-on configuration for Cloud Print forwarding.
- Added a dedicated admin LPR debug page with listener, spool and recent-job visibility.
- Added clearer LPR listener information to admin settings and employee Cloud Print views.

### Changed
- Split the global LPR listener setup from the tenant-specific forwarding queue configuration so users no longer edit the listener port per tenant.

## 5.17.1 (2026-04-16) — LPR Forwarding Hotfix

### Fixed
- Fixed Cloud Print LPR forwarding to resolve the target `printer_id` for a configured queue before submitting the Printix job.
- Fixed LPR upload MIME handling so the spool file is uploaded with the detected print data type instead of the document name as content type.
- Fixed LPR startup to honor the saved admin `lpr_port` setting instead of only reading the environment default.

## 5.17.0 (2026-04-16) — MCP Context Tools For Cards, Networks And Queues

### Added
- Enriched MCP card lookups so `printix_search_card` and `printix_list_cards` now include local SQLite mapping context, decoded secret hints and richer card metadata where available.
- New MCP tool `printix_get_user_card_context` for full user + card + local mapping context in one call.
- New MCP tool `printix_get_queue_context` for queue, printer pair and recent print-job context.
- New MCP tool `printix_get_network_context` for network, site, printers and related SNMP configurations.
- New MCP tool `printix_get_snmp_context` for SNMP configuration context across assigned networks, sites and printers.

### Fixed
- Synchronized runtime/add-on/docs versioning again so VERSION, config and README no longer drift apart.

## 5.14.0 (2026-04-16) — Cloud Print: Logging, Job-Tracking, Admin-Settings

### Added
- **cloudprint_jobs Tabelle**: Lokales Tracking aller empfangenen LPR-Jobs mit Status (received → forwarding → forwarded/error)
- **Tenant-Logging**: LPR-Events erscheinen jetzt im Web-UI unter `/logs` (Kategorie CLOUDPRINT)
- **Cloud Print Jobs** in `/my/jobs`: Zeigt empfangene LPR-Jobs mit Status, Größe, Format und Printix-Job-ID
- **Admin-Settings**: LPR Endpoint-URL und Port konfigurierbar unter `/admin/settings` mit Printix-Drucker-Einrichtungsanleitung

### Fixed
- Default LPR-Port auf **5515** geändert (Port 515 braucht Root-Rechte)
- LPR-Server loggt jetzt bei jeder Verbindung, jedem Job-Empfang und jeder Weiterleitung

## 5.13.0 (2026-04-16) — Cloud Print Port: LPR-Server + Portal-Umbau

### Added
- **LPR-Server** (`cloudprint/lpr_server.py`): Asyncio-TCP-Server der Druckjobs via LPR-Protokoll (RFC 1179) von Printix empfängt
- **Cloud Print Weiterleitung** (`/my/cloud-print`): Konfiguration der Ziel Secure Print Queue, LPR-Endpoint-Info für Admins
- **Job-Pipeline**: Empfang → Tenant-Identifikation (Queue = Tenant-ID) → Format-Erkennung (PDF/PS/PCL) → Weiterleitung an Printix Secure Print API
- LPR-Server startet automatisch als Background-Task (konfigurierbar via `LPR_PORT`, `LPR_ENABLED`)
- DB-Schema: `tenants.lpr_target_queue`, `tenants.lpr_port`

### Changed
- "Drucker einrichten" → "Cloud Print" umbenannt: zeigt LPR-Endpoint-Infos und Queue-Konfiguration statt Drucker-Setup-Anleitung
- Print-Token-Konzept entfernt (nicht nötig — Printix sendet Jobs direkt, Auth über Queue-Name/Tenant-ID)

### Removed
- Partner-Portal komplett entfernt (Route, Template, Helper, i18n-Keys in 8 Sprachen)
- `can_access_partner_portal` aus User-Dict entfernt

## 5.12.0 (2026-04-16) — Cloud Print Port Phase 1: Mitarbeiter-Portal & Delegation

### Added
- Neuer Benutzertyp „Mitarbeiter" (employee): Self-Service-Portal unter `/my/*` — Dashboard, Druckjobs, Delegation, Printer-Setup, Reports Light
- Delegation-System: Mitarbeiter schlagen Delegates vor, Admin/User genehmigt. Delegates können Jobs am Drucker releasen
- Mitarbeiter-Verwaltung (`/employees/*`): Anlegen, einsehen, löschen
- Print-Token (`ptk_*`): Dedizierter Token mit SHA-256 Hash-Lookup für Cloud-Print-Drucker-Auth
- Reports Light: 3 Report-Platzhalter (Druckübersicht, Kostenanalyse, Druckverlauf)
- DB-Schema: `delegations`-Tabelle, `users.role_type`, `users.parent_user_id`, `tenants.print_token`
- i18n: ~100 neue Keys in DE, EN, FR, IT, ES, NL
- Navigation: Neue Links „Mitarbeiter" + „Mein Portal" (Desktop + Mobile)

## 5.11.0 (2026-04-16) — MCP Tool Expansion (+16 Tools)

### Added
- 7 Card Management tools: list_card_profiles, get_card_profile, search_card_mappings, get_card_details (enriched with local DB), decode_card_value, transform_card_value
- 3 Audit & Governance tools: query_audit_log, list_feature_requests, get_feature_request
- 2 Backup tools: list_backups, create_backup
- 2 Capture tools: list_capture_profiles, capture_status
- 2 Site/Network aggregation tools: site_summary (site + networks + printers in one call), network_printers (filter by network or site)
- Card enrichment: printix_get_card_details combines Printix API with local card_mappings DB for richer card information

### Changed
- Total MCP tools now 79 (up from 63)

## 5.10.11 (2026-04-16) — Builder Upload Analysis Hotfix

### Fixed
- Removed a broken JavaScript translation call in the Clientless / Zero Trust Package Builder that caused `Network error: t is not defined` during ZIP upload analysis.

## 5.10.10 (2026-04-16) — Card Conversion Consistency Fixes

### Fixed
- Unified the browser and server-side card transformation order so previews and stored values no longer diverge on replace/remove/lowercase/leading-zero rules.
- Corrected the YSoft Konica profile to Base64-encode real `FF` bytes, matching the documented Logic App examples instead of UTF-8 text encoding.

## 5.10.9 (2026-04-16) — Shared Nav And Content Width

### Changed
- Unified the top navigation and page content on the same shared workspace width so the page layout now follows the same horizontal rhythm as the register bar.
- Moved the shared width and gutter values into central CSS variables for easier future tuning.

## 5.10.8 (2026-04-16) — Wider Main Workspace Layout

### Changed
- Increased the shared page container width in the base layout so the app no longer leaves excessive unused space on large screens.
- Expanded the main working views such as Printix, Druckerflotte and Karten & Codes to use the wider layout more consistently.

## 5.10.7 (2026-04-16) — Wider Printix Overview

### Changed
- Increased the usable page width on the Printix overview so the content no longer leaves so much unused space on large screens.
- Restored the section card helper text with a 3-column card grid and tighter text clamping for a more informative but still compact layout.

## 5.10.6 (2026-04-16) — Printix Overview Layout Rebalance

### Changed
- Rebalanced the Printix overview so the `Bereiche` section gets more width and the readiness panel no longer squeezes the cards unnecessarily.
- Removed the section card helper text on the overview cards to keep the page visible with less vertical scrolling.

## 5.10.5 (2026-04-16) — Curated Detail Summaries

### Changed
- Added curated summary panels for Sites, Networks and SNMP so useful metadata remains visible after removing raw API payload blocks.
- Resolved linked names such as assigned networks, admin groups and site names into readable UI summaries.

## 5.10.4 (2026-04-16) — Printix Detail View Cleanup

### Changed
- Removed raw API payload panels from Printix object detail pages so printer, queue, site, network and SNMP views stay focused on the curated information.
- Expanded the remaining edit/detail cards to use the freed space more effectively.

## 5.10.3 (2026-04-16) — Fluid Printix Overview Cards

### Changed
- Made the Printix overview section cards scale fluidly with available width so card size, icon size and typography shrink and expand together.
- Improved handling of longer labels such as `Workstations` to reduce awkward wrapping on medium viewport sizes.

## 5.10.2 (2026-04-16) — Printix Overview Card Compaction

### Changed
- Reworked the `Bereiche` card grid on the Printix overview into a denser, more square layout to reduce unnecessary scrolling.
- Reduced visible card copy with tighter typography and line clamping so the overview stays compact even as more sections are added.

## 5.10.1 (2026-04-16) — Dashboard Version Badge

### Changed
- Added the current add-on version as a dashboard badge, sourced from the shared VERSION file so UI and package metadata stay in sync.

## 5.10.0 (2026-04-16) — Printix Deep Object Views & Infrastructure Registers

### Changed
- Added dedicated detail views for printers and queues, including capabilities, queue pairing and recent jobs.
- Expanded the Printix navigation with Sites, Networks and SNMP, including list and detail views plus create, update and delete flows backed by the existing API client.
- Extended the Printix overview with direct entry cards for Sites, Networks and SNMP and added complete i18n coverage for the new structure.

## 5.9.11 (2026-04-16) — Printix Sidebar Final Alignment & i18n Cleanup

### Changed
- Reworked the compact Printix sidebar rows so icon and label stay truly left-aligned while the numeric badge anchors on the far right, even for longer labels.
- Removed the last hardcoded pagination labels in the Printix user list and switched them to shared translations.

## 5.9.10 (2026-04-16) — Printix Sidebar Row Alignment

### Changed
- Adjusted the compact Printix sidebar rows so icon and label stay truly left-aligned while the numeric badge stays right-aligned

## 5.9.9 (2026-04-16) — Printix Sidebar Alignment Tweak

### Changed
- Widened the Printix sidebar slightly and tightened label/number alignment so longer entries like `Users & Cards` stay visually balanced

## 5.9.8 (2026-04-16) — Printix UI Polish & Nav Order

### Changed
- Compact, simplified the Printix left navigation to stay scalable as more sub-sections are added
- Improved the Printix readiness panel with translated state labels and clearer SQL status messaging
- Moved the main `Logs` register to directly follow `Capture Store` in the primary navigation

## 5.9.7 (2026-04-16) — Reporting Dependency Fix

### Fixed
- Added the missing `python-dateutil` dependency so dashboard forecasting no longer fails with `No module named 'dateutil'`

## 5.9.6 (2026-04-16) — Printix Overview Landing

### Changed
- Added a dedicated Printix overview landing page with KPI cards, readiness states and direct section entry points
- Upgraded the shared Printix sidebar with descriptive sublabels and a first-class overview entry
- Switched the main Printix navigation entry to open the new overview instead of jumping straight into printers

## 5.9.5 (2026-04-16) — Printix Navigation Layout Refresh

### Changed
- Reworked the Printix area into a shared left-side navigation shell for printers, queues, users, workstations and demo data
- Improved future extensibility for additional Printix sub-sections by centralizing the sub-navigation in one reusable template
- Updated the main Printix content views to render in a clearer master-detail layout with the active section shown in the main content area

## 5.9.4 (2026-04-15) — Employee Role & Partner Portal Prep

### Added
- New user role `Employee` prepared alongside `User` and `Admin`
- New protected `Partner Portal` section visible for admins and employees
- Role selection in admin user creation, editing and invitation flows

### Changed
- User management now stores a normalized role type in addition to legacy admin compatibility flags

## 5.9.3 (2026-04-15) — Fleet Builder Translation Fix

### Fixed
- Fixed the Fleet Monitor shortcut card for `Clientless / Zero Trust Package Builder` so both title and description are translated correctly instead of staying hardcoded in German

## 5.9.2 (2026-04-15) — Full Backup & Restore

### Added
- Full local backup and restore flow under `Administration > Server Settings`, covering users, password hashes, tenant credentials, card/SQL-related local state, demo data, report templates and the local encryption key
- Backup ZIP export to the add-on backup directory with download list in the admin UI
- Restore flow from uploaded backup ZIP with explicit restart notice after restore

## 5.9.1 (2026-04-15) — Session Middleware Hotfix

### Fixed
- Fixed a startup/runtime error in the invitation activation middleware by ensuring session middleware is registered in the correct order and by safely handling requests without an initialized session scope

## 5.9.0 (2026-04-15) — User Invitations

### Added
- New admin flow `Benutzer einladen` under `Administration > Benutzer` to create a user, generate a temporary password automatically and send a localized invitation email
- Invitation emails in all supported main languages with login link, credentials and a localized “top 5 highlights” overview of the platform
- User invitation tracking in the admin user list so admins can see whether an invitation is still open or has already been accepted
- Forced first-login activation flow that requires invited users to set their own password before they can continue into the console

### Changed
- Extended the user schema with invitation metadata and first-login password-change enforcement for invitation-based onboarding

## 5.8.6 (2026-04-15) — Dashboard Link Trim

### Changed
- Removed the feedback quick link from the dashboard side panel to reduce the landing page height and help keep the full start page visible without scrolling

## 5.8.5 (2026-04-15) — Adaptive Dashboard Fit

### Changed
- Reworked the dashboard landing page to scale more aggressively with available screen width and height so the start page needs less vertical scrolling on common desktop resolutions
- Expanded the quick-access grid to four columns on larger screens and tightened hero, badge, card and side-panel spacing for a denser but still readable overview
- Added an extra compact layout mode for shorter desktop viewports so the start page remains more likely to fit above the fold without harming the mobile layout

## 5.8.4 (2026-04-15) — Dashboard Tile Translation Fix

### Fixed
- Corrected missing dashboard tile subtitle translations for the `Clientless / Zero Trust Builder` and `Druckerflotte` tiles in additional languages so they no longer fall back to the wrong language
- Extended the newer branding/landing-page translation layer with the affected tile texts for ES, NO and SV

## 5.8.3 (2026-04-15) — Dashboard Tile Balance

### Changed
- Balanced the dashboard quick-access grid so all tiles keep the same visual card height on desktop instead of the final row feeling larger
- Compressed the environmental tile into the same card footprint and replaced the metric labels with compact symbols for a cleaner, less text-heavy look
- Kept the metric meaning accessible through localized hover titles while preserving a tighter dashboard layout

## 5.8.2 (2026-04-15) — Ricoh Builder Repair & Branding Cleanup

### Fixed
- Repaired the Ricoh package analyzer so real DALP packages no longer fail during XML inspection because of a translator-variable collision
- Preserved ZIP entry structure more carefully while rebuilding patched vendor packages so simple Ricoh uploads keep their original folder and file layout intact
- Continued the localization pass in the package builder by moving the visible package-version label behind translation keys

### Changed
- Renamed the visible product branding from `Printix MCP Admin` / `Printix MCP Server` to `Printix Management Console` in the login/runtime-facing console surfaces touched by this update
- Bumped the shared runtime/add-on version to `5.8.2` for consistent banners, health output and package metadata

## 5.8.1 (2026-04-15) — Dashboard & Cards Translation Completion

### Changed
- Completed the translation follow-up for the new dashboard landing page so tile labels, helper texts and status cards no longer default back to English in non-DE locales like Dutch
- Extended the cards-related i18n coverage for `Karten & Codes` and `Benutzer & Karten`, including profile selectors, built-in browser metadata, Base64 source labels and vendor recommendation hints
- Removed remaining hard-coded fallback words such as `Generic`, `Any`, `Custom` and inline recommendation text from the cards templates so the active UI language can fully drive those surfaces

## 5.8.0 (2026-04-15) — Cross-Language UI Cleanup & Responsive Follow-Up

### Changed
- Continued the translation cleanup across `Settings`, `Demo-Daten`, `Fleet Package Builder` and remaining helper flows so more UI text now follows the selected language
- Added new translation keys not only for DE/EN but also for FR, IT, ES, NL, NO and SV in the newly touched areas
- Improved mobile behavior for the package builder and demo pages so step bars, action rows, preset cards and summary boxes stack more cleanly on smaller screens

## 5.7.1 (2026-04-15) — Extended I18n Coverage

### Changed
- Continued the localization cleanup in navigation, admin settings, reports, capture workflows and the cards/user conversion helpers
- Replaced remaining hard-coded labels in `Karten & Codes` and `Benutzer & Karten` for input modes, submit modes, preview tables and profile editing fields
- Moved more capture and report feedback text, copy actions and upload warnings behind translation keys so the active UI language is reflected more consistently

## 5.7.0 (2026-04-15) — I18n Cleanup & Cards UI Consistency

### Changed
- Replaced many remaining hard-coded UI texts in the registration flow, settings, tenant views and card workflows with centralized translation keys
- Normalized `Karten & Codes` and `Benutzer & Karten` so helper texts, messages, buttons, placeholders and JavaScript alerts follow the active UI language
- Cleaned up Printix tenant pages (`Drucker`, `Queues`, `Workstations`, `Benutzer`) to reduce mixed-language output in search bars, counters, status labels and empty states

### Added
- Centralized extra translation key layer for newly normalized UI sections with automatic fallback wiring for all supported languages
- New versioned release notes for the wider localization pass and cards/user-flow consistency work

## 5.5.0 (2026-04-15) — Landing Page & Responsive UI Refresh

### Changed
- Reworked `/dashboard` into a modern landing page with colorful feature tiles and direct short links to the most important product areas
- Improved the global UI foundation in `base.html` so containers, cards, forms and table wrappers behave more reliably on smaller screens
- Continued the master-detail direction in cards/profile workflows to reduce long scrolling areas and improve focus

### Added
- Landing page shortcuts for `Drucker`, `Queues`, `Workstations`, `Benutzer & Karten`, `Demo-Daten`, `Karten & Codes`, `Reports`, `Clientless / Zero Trust Builder`, `Fleet Monitor`, `Capture-Store` and `Logs`
- New status and quick-access panels on the landing page for a clearer first step after login

## 5.3.12 (2026-04-15) — User Card Detail Browser

### Changed
- Replaced the long scrolling card stack in the user detail page with a master-detail browser
- Existing cards are now selected from a compact left-side list and shown in a focused detail panel
- Card delete and local value repair actions stay directly available without forcing the page to grow endlessly

## 5.3.11 (2026-04-15) — Built-in Profile Detail Browser

### Changed
- Replaced the long scrolling built-in profile stack in `Karten & Codes` with a master-detail browser
- Built-in profiles now open in a dedicated detail panel with description, rule chips and direct actions
- The right column is more compact and modern while staying editable and extensible

## 5.3.10 (2026-04-15) — Cards UX Refresh & Version Consistency

### Changed
- `Karten & Codes` redesigned as the dedicated advanced workspace for card values, mappings and transformation profiles
- Clearer separation between `Benutzer & Karten` (standard workflow) and `Karten & Codes` (advanced workflow)
- User detail card add form now supports direct profile selection with a reduced default UI and collapsible advanced options
- Flexible card transformation rules now support `remove_chars`, `replace_map`, `prepend_text`, `append_text`, `append_char`, `append_count`, `base64_source` and the `working` submit mode
- `Benutzer & Karten` now surfaces stored Printix secret, working value and derived HEX/Decimal values when a local mapping exists
- Grouped profile selects in both `Karten & Codes` and `Benutzer & Karten` make built-ins easier to find by manufacturer
- Built-in profile list in `Karten & Codes` is now grouped by vendor with recommendation hints for common reader families
- Selection labels now surface vendor and reader context more clearly for faster profile picking

### Added
- Custom profile editing directly in the `Karten & Codes` UI
- Built-in profile actions to apply them in Card Lab or duplicate them into editable custom profiles
- Shared profile availability in both the advanced card tool and the user detail page
- Central runtime version file for consistent server, capture and health responses
- Reader-oriented built-in profiles derived from the project notes and Excel workflows, including YSoft/Konica, Elatec, RFIDeas, Baltech, Inepro Spider, MiCard RFIDeas, HP MFP24 and double-Base64 cases
- Guided profile editor fields for common rule options such as submit mode, Base64 source, cleanup, replacements and append logic
- Richer mapping persistence in SQLite with stored preview JSON and Printix secret values for exact user/card context

### Fixed
- When adding a card with a selected profile, the server now recomputes the final submit value from the raw value before registering the card in Printix
- Removed the unused legacy `cards.html` template to avoid parallel UI implementations drifting apart
- Version strings aligned across `config.yaml`, startup banners, health endpoints and README files
- Tenant user detail now actually receives the richer locally stored card mapping fields instead of silently dropping them

---

## 5.3.9 (2026-04-14) — Cards Schema Repair & Profile Save Fix

### Fixed
- `card_mappings` migration now adds all missing columns for existing SQLite databases, including `local_value`, `final_value`, `normalized_value`, `source`, `notes`, `updated_at`, `profile_id` and `search_blob`
- Fix for `❌ table card_mappings has no column named local_value` when adding a new card under **Benutzer & Karten**
- `upsert_profile()` is now a real update-or-insert instead of always creating a new profile
- `/cards/profiles/save` now stores `rules_json` consistently as an object default (`{}`) instead of `[]`
- Local card mappings can now persist the selected `profile_id` in a dedicated DB column instead of overloading `notes`

---

## 5.3.8 (2026-04-14) — Cards & Codes Final Release

### New
- **Karten & Codes** page (`/cards`) — full Card Lab with local mappings, transformation profiles and search
- Cards routes fully wired: GET `/cards`, POST `/cards/mappings/save|delete`, `/cards/profiles/save|delete`, `/cards/sync-import`
- Built-in transformation profiles for common RFID reader types

### Fixed
- `/cards` route 404 (missing handler in app.py)
- `require_login` None-check corrected (`user is None` instead of `isinstance`)
- Template context missing `request` key
- `public_url` schema changed from `url?` to `str?` for HA compatibility

---

# Changelog

## 4.6.19 (2026-04-13) — Fix Tenant URL Feld-Styling

### Fix — `input[type=url]` fehlte im globalen CSS
- `input[type=url]` zu den CSS-Selektoren in `base.html` hinzugefügt (Haupt-Styling + Responsive)
- Tenant URL Feld hat jetzt identisches Padding, Border-Radius und Breite wie alle anderen Felder

## 4.6.18 (2026-04-13) — Tenant URL als Pflichtfeld in Einstellungen

### Änderung — Einstellungsseite: Tenant URL statt Tenant Name
- Neues Pflichtfeld "Tenant URL" ersetzt "Tenant Name" unter Einstellungen
- Placeholder: `https://firmenname.printix.net`
- DB-Migration: neue Spalte `tenant_url` in tenants
- Trailing Slash wird automatisch entfernt beim Speichern
- Package Builder nutzt die gespeicherte Tenant URL für Vorbelegung
- Kein Fallback-Raten mehr aus der Tenant ID

## 4.6.14 (2026-04-13) — Clientless / Zero Trust Package Builder

### Neu — Package Builder unter Druckerflotte → `/fleet/package-builder`

Wizard-Assistent für herstellerspezifische Clientless-/Zero-Trust-Installerpakete.

**Ricoh-Adapter (erster Hersteller):**
- Erkennt Ricoh-Pakete via `PrintixGoRicohInstaller/deploysetting.json`
- Versionstolerant: sucht nach Glob-Mustern statt fixen Dateinamen
  (`rxspServletPackage-*.zip`, `rxspServlet-*.zip`, `rxspservletsop-*.zip`)
- Öffnet 3-stufige ZIP-Verschachtelung vollständig in-Memory
- Patcht DALP-XML strukturiert via `xml.etree.ElementTree` (kein String-Replacement)
- Liest `deploysetting.json` aus → findet inneres RXSP-Paket dynamisch
- Patcht `rxspServlet.dalp`: `<description type="detail">` → `servlet_url`
- `rxspservletsop.dalp` bereits erkannt (read-only, Regeln vorbereitet)
- Baut alle ZIP-Ebenen korrekt neu (äußer → inner → sub-ZIPs)

**Vorbelegung aus Tenant-Kontext:**
- `tenant_id`, `tenant_url`, `client_id`, `public_url` (→ servlet_url-Basis) vorausgefüllt
- Client Secret nie automatisch befüllt (Security)

**Architektur (mehrherstellerfähig):**
- `src/package_builder/core.py` — Orchestrator, Session-Management
- `src/package_builder/vendors/base.py` — Abstrakte Basisklasse
- `src/package_builder/vendors/__init__.py` — Auto-Discovery (pkgutil)
- `src/package_builder/vendors/ricoh.py` — Ricoh-Adapter
- `src/package_builder/models.py` — Datenmodelle (FieldSchema, AnalysisResult etc.)

**Sicherheit:**
- ZIPs temporär (`tempfile.mkdtemp`), automatische Bereinigung nach 1h oder Download
- Secrets erscheinen nie in Logs
- Tenantbezogene Isolation (nur eigene Daten)

## 4.6.13 (2026-04-13) — Workstation Online/Offline Toggle-Filter

### Neu — Status-Filter für Workstations
- Toggle-Buttons: **Alle** | **🟢 Online** | **🔴 Offline**
- Serverseitiger Filter per `?status=online` / `?status=offline`
- Zusammenfassung zeigt Gesamtzahl + gefilterte Anzahl
- i18n in allen 14 Sprachen

## 4.6.12 (2026-04-13) — Workstation-Status Fix + User-Paginierung

### Fix — Workstation-Status korrekt anzeigen
- API-Feld `active` ist ein **Boolean** (nicht String wie `connectionStatus`)
- Template komplett überarbeitet: zeigt nur die 5 echten API-Felder
  (`id`, `name`, `active`, `lastConnectTime`, `lastDisconnectTime`)
- Status-Dot grün/rot basiert auf `ws.get('active')` (Boolean-Check)

### Neu — User-Liste mit Paginierung + Karten-Anzahl
- User-Liste zeigt 10 Benutzer pro Seite mit Vor-/Zurück-Navigation
- Karten-Anzahl (`_card_count`) wird nur für sichtbare User geladen
  (vorher: immer 0, weil `list_users()` keine Karten zurückgibt)
- Seitennavigation mit Seitenzahlen, Ellipsis und direkten Links

## 4.6.11 (2026-04-13) — Workstations UI-Tab + Report-Fix + Plugin-Architektur

### Neu — Workstations Tab im Web-UI
- Neuer Tab unter Printix: Drucker → Queues → Benutzer → **Workstations** → Demo
- Route `/tenant/workstations` — live aus der Printix Workstation Monitoring API
- Zeigt Status (active Boolean), Name, Last Connected, Last Disconnected
- i18n in allen 14 Sprachen

### Fix — Workstation Reports: vollständig dynamische Schema-Erkennung
- **workstation_overview**: Fragt `INFORMATION_SCHEMA.COLUMNS` ab, um die
  tatsächlichen Spalten der workstations-Tabelle zu ermitteln. Keine harten
  Annahmen mehr über `os_type`, `network_id`, `workstation_id` etc.
  - Wenn `workstation_id` in jobs vorhanden → volle Statistik
  - Wenn nicht → Workstation-Stammdaten (nur vorhandene Spalten)
- **workstation_detail**: `workstation_id` optional, Preset auf `available: false`
  gesetzt (Vorschau ohne ID nicht möglich)

### Neu — Plugin-Architektur: `capture/plugins/` Unterordner
- Jedes Capture-Ziel-Plugin in eigener Datei unter `capture/plugins/`
- `pkgutil` Auto-Discovery — neue Plugins werden automatisch erkannt
- `plugin_paperless.py` → `plugins/paperless.py` (saubere Trennung)

## 4.6.9 (2026-04-13) — Fix: Workstation Report SQL-Fehler + metadataUrl + Error-Parsing

### Fix — Workstation Report: `Invalid column name 'network_id'`
- **Ursache**: `query_workstation_overview()` referenzierte `w.network_id` auf der
  Workstations-Tabelle, die kein `network_id`-Feld hat. Nur die Printers-Tabelle
  hat `network_id`.
- **Lösung**: JOIN-Pfad geändert: `workstations → jobs → printers → networks`
  statt dem ungültigen direkten `workstations → networks` JOIN.

### Neu — Printix metadataUrl Fetch (v4.6.8)
- Webhook-Handler lädt Metadaten von der Printix `metadataUrl` mit signiertem
  GET-Request (HMAC-SHA256, Printix Capture Connector Protokoll)
- Plugin-Metadata angereichert mit `_printix_metadata`, `_scan_timestamp`,
  `_user_name`, `_device_name`, `_job_id`, `_scan_id`

### Fix — API Error-Parsing (v4.6.8)
- `_handle_response()` parst jetzt `errorText`/`message` statt `description`,
  und `printix-errorId` statt `errorId` — zeigt saubere Fehlermeldung statt rohem JSON

## 4.6.7 (2026-04-13) — Fix: Printix Capture Signaturverifikation

### Fix — Korrekte Printix Capture Connector Signaturformel implementiert
- **Ursache**: Die exakte Signaturformel war unbekannt. Die offizielle Tungsten-Doku
  beschreibt nur vage "some details of the HTTP request", ohne die genaue Formel
  zu dokumentieren. Alle bisherigen ~84 Kombinationen (body-only, ts.path.body,
  POST.ts.path.body, etc.) scheiterten.
- **Lösung**: Die korrekte Formel wurde im Tungsten Sample Connector (Python)
  gefunden — ein 5-Komponenten dot-separierter StringToSign:
  ```
  StringToSign = "{RequestId}.{Timestamp}.{method}.{RequestPath}.{Body}"
  ```
  - **RequestId** — aus `X-Printix-Request-Id` Header (UUID)
  - **Timestamp** — aus `X-Printix-Timestamp` Header (Unix Epoch Sekunden)
  - **method** — HTTP-Methode in **Kleinbuchstaben** (z.B. `post`)
  - **RequestPath** — aus `X-Printix-Request-Path` Header (URL-Pfad)
  - **Body** — Raw Request Body als UTF-8 String
- **HMAC-Berechnung**:
  - Key = Base64-dekodiert (32 Bytes für SHA-256, 64 Bytes für SHA-512)
  - Gesamter StringToSign als UTF-8 kodiert → HMAC
  - Ergebnis = Base64-kodiert (44 Zeichen für SHA-256)
- **Zwei verschiedene Printix-APIs, zwei verschiedene Formate**:
  - Cloud Print API Webhooks: `"{timestamp}.{body}"` + HMAC-SHA-512 + Hex
  - Capture Connector API: `"{rid}.{ts}.{method}.{path}.{body}"` + HMAC-SHA-256 + Base64

### Verbesserung — HTTP-Methode durchgereicht
- `verify_capture_auth()` akzeptiert jetzt den `method`-Parameter
- `webhook_handler.py` übergibt die HTTP-Methode aus dem Request

### Verbesserung — Diagnose bei fehlenden Headers
- Wenn `X-Printix-Timestamp`, `X-Printix-Request-Path` oder `X-Printix-Request-Id`
  fehlen, warnt das Diagnose-Log explizit und empfiehlt Proxy-Konfiguration zu prüfen
- Vollständiger Header-Dump (alle Headers, nicht nur x-printix-*)

---

## 4.6.6 (2026-04-13) — Fix: Plugin-Registry im Capture-Server

### Fix — Plugin 'paperless_ngx' nicht gefunden im Standalone-Capture-Server
- **Ursache**: `capture.plugin_paperless` wurde nur in `capture_routes.py` (Web-UI)
  importiert, nicht im `webhook_handler.py`. Ohne diesen Import läuft der
  `@register_plugin`-Decorator nicht → Plugin-Registry leer → HTTP 500.
- **Fix**: `import capture.plugin_paperless` direkt in `webhook_handler.py` vor
  dem `create_plugin_instance()`-Aufruf. Damit ist das Plugin unabhängig vom
  Aufrufpfad (Capture-Server, MCP-Server, Web-UI) immer registriert.

---

## 4.6.5 (2026-04-13) — Erweiterte Body-Integritätsprüfung + Neue Canonical Formate

### Neu — Raw-Body-Analyse im Diagnose-Log
- **body_first32** / **body_last32**: Erste und letzte 32 Bytes als Hex-Dump
- **body_has_crlf**: Prüft ob Body `\r\n` enthält (Proxy-Normalisierung)
- **body_ends_nl**: Letztes Byte + ob Body auf `\n` endet
- **body_has_bom**: UTF-8 BOM-Erkennung
- **Content-Type**, **Content-Length**, **Host** aus Request-Headers

### Neu — Erweiterte Canonical-String-Formate
- **Body-Varianten**: `\r\n`→`\n` normalisiert, trailing-whitespace gestrippt
- **Double-Hash**: HMAC über `SHA256(body)` als Hex-String und Raw-Bytes
- **URL-basiert**: `https://host/path + body`, `ts.https-url.body`
- **Content-Type**: `ts.content-type.path.body`
- Insgesamt ~30 Kandidaten pro Key-Variante (vorher ~15)

### Verbesserung — Headers durchgereicht
- `_try_printix_native()` und `_diagnostic_log()` erhalten jetzt
  das vollständige Headers-Dict für URL-basierte Canonical Strings

---

## 4.6.4 (2026-04-13) — Fokussierte SHA-256 Signatur-Diagnose

### Fix — Algorithmus-Erkennung aus Signaturlänge
- **44 Zeichen Base64 = SHA-256** (32 Bytes), 88 Zeichen = SHA-512 (64 Bytes)
- Erkannter Algorithmus wird ZUERST versucht → kein blindes Raten mehr
- Signaturlänge wird im Log explizit geloggt und der Algorithmus bestimmt

### Neu — Vollständiges Diagnose-Log bei Mismatch
- **Jeder einzelne Kandidat** (Key × Format × Algo) wird mit vollem
  erwarteten Base64-Wert geloggt — direkt vergleichbar mit der empfangenen Signatur
- **Keine Trunkierung** mehr — vollständige Werte für echten Vergleich
- **Body-SHA256-Hash** wird geloggt für unabhängige Verifizierung
- **Key-Material klar dokumentiert**: Typ (utf8/b64dec), Länge, Preview
- Alles auf **INFO-Level** — sichtbar im Standard-Log ohne log_level=debug

### Neu — Erweiterte Canonical-String-Formate
- `path.ts.body` (umgekehrte Reihenfolge)
- `POST.path.ts.body` und `POST.ts.path.body` (mit HTTP-Methode)
- Alle Formate zentral in `_build_canonical_payloads()` definiert

### Beibehaltung aus v4.6.3
- Komma-getrennte Multi-Signaturen (Key Rotation)
- `require_signature=False` Bypass mit Debug-Dump
- Body-only wird ZUERST versucht (vor Canonical Strings)

---

## 4.6.3 (2026-04-13) — Printix Signatur: Dokumentiertes Format + Bypass

### Fix — Signaturprüfung basiert auf offizieller Doku
- Verifikationsreihenfolge: body-only + SHA-512 zuerst, dann Canonical Strings

### Neu — Komma-getrennte Multi-Signaturen und Bypass-Modus
- `require_signature=False` erlaubt Webhook-Verarbeitung trotz Mismatch

---

## 4.6.2 (2026-04-13) — Printix Signatur: Exhaustive Discovery

### Fix — Signatur-Mismatch trotz Base64-Vergleich
- **Problem**: v4.6.1 verglich korrekt als Base64, aber keins der drei kanonischen
  Formate (ts.path.body / ts.body / body) mit SHA-256 und UTF-8-Key matchte.
- **Neue Discovery-Engine**: `_try_printix_native()` probiert jetzt systematisch
  ALLE Kombinationen durch:
  - **Key-Varianten**: Raw UTF-8, Base64-dekodiert, Base64-URL-safe-dekodiert
    (viele APIs wie Azure/Tungsten speichern den Secret als Base64 — der dekodierte
    Wert ist dann der HMAC-Key)
  - **Algorithmen**: SHA-256, SHA-1, SHA-512
  - **10+ Canonical Formats**: `ts.path.body`, `ts.body`, `body`, mit/ohne
    Trennzeichen (`.`, `\n`, keins), mit/ohne Request-ID, Pfad mit/ohne `/`
  - **4 Signature-Encodings**: Base64 (mit/ohne Padding), Base64-URL-safe, Hex
- **Debug-Logging**: Bei Mismatch zeigt das Log für jede Key-Variante × Algo × Format
  den erwarteten Base64-Wert — damit sieht man sofort welche Kombination am
  nächsten kommt oder ob das Secret falsch ist

---

## 4.6.1 (2026-04-13) — Printix Signatur Base64 Fix

### Fix — Printix-Signatur Base64 statt Hex
- Printix sendet `x-printix-signature` als **Base64** (z.B. `YmTIM5AjLATJA97t...`)
- Der Code verglich nur gegen `hexdigest().lower()` — Base64 ist case-sensitive,
  `.lower()` zerstört den Wert → Mismatch bei jedem Request
- `_try_printix_native()` vergleicht jetzt gegen drei Encodings pro Format:
  1. Base64 standard (case-sensitive) — Printix Default
  2. Base64 URL-safe (case-sensitive) — Fallback
  3. Hex (case-insensitive) — Rückwärtskompatibilität
- Debug-Log zeigt `expected_b64` und `expected_hex` nebeneinander

---

## 4.6.0 (2026-04-13) — Capture Architektur-Redesign

### Breaking Change — `capture_port` durch `capture_enabled` ersetzt
- **Alt**: `capture_port: 0` (int) — diente gleichzeitig als Ein/Aus-Schalter UND
  als Port-Nummer. Das war ein Designfehler: der Wert suggerierte, dass er den
  externen Port steuert, tatsächlich kontrolliert er nur den internen Listen-Port.
  Das Docker-Portmapping (config.yaml `ports: 8775/tcp`) ist davon völlig unabhängig.
- **Neu**: `capture_enabled: false` (bool) — reiner Ein/Aus-Schalter.
  Der Container-Port ist **immer** 8775 (feste Konstante, nicht konfigurierbar).
  Den Host-Port konfiguriert man in HA unter Add-on → Netzwerk.

### Saubere Trennung der Verantwortlichkeiten
- **config.yaml `ports: 8775/tcp`** — definiert das Docker-Portmapping (HA Supervisor)
- **config.yaml `capture_enabled: bool`** — startet/stoppt den Capture-Server-Prozess
- **HA Netzwerk-Tab** — aktiviert/deaktiviert den Host-Port (unabhängig vom Code)
- Diese drei Ebenen sind jetzt klar getrennt statt vermischt

### Änderungen im Detail
- **config.yaml**: `capture_port: int` → `capture_enabled: bool` (Option + Schema)
- **run.sh**: Liest `capture_enabled` (true/false) statt `capture_port` (int).
  `CAPTURE_ENABLED` env var ist jetzt "true"/"false" statt einer Portnummer.
  `CAPTURE_PORT` env var wird nur noch lokal gesetzt wenn der Server startet.
  Container-Port ist die Konstante `CAPTURE_CONTAINER_PORT=8775`.
- **server.py**: Middleware und Startup-Log prüfen `CAPTURE_ENABLED` env var
  (true/false) statt `CAPTURE_PORT > 0`
- **capture_routes.py**: `_is_capture_separate()` prüft `CAPTURE_ENABLED`
- **capture_server.py**: Docstring aktualisiert — Port ist fest 8775
- **Logging**: Klare Unterscheidung zwischen Container-Port (intern, fest) und
  Host-Port (extern, HA-Netzwerk-Tab)

### Fix — Printix-Signatur `x-printix-signature` wird nicht erkannt
- **Symptom**: Echte Printix-Webhooks kommen mit `x-printix-signature`,
  `x-printix-timestamp`, `x-printix-request-path` und `x-printix-request-id`.
  Der Auth-Code suchte aber nur nach `x-printix-signature-256` und `-512`.
  Ergebnis: `Auth: No signature header and require_signature=True` → 401.
- **auth.py**: Neuer Auth-Modus `printix-native` — höchste Priorität.
  Erkennt `x-printix-signature` Header und verifiziert gegen kanonische Formate:
  1. `{timestamp}.{request_path}.{body}` (vollständig)
  2. `{timestamp}.{body}` (ohne Pfad)
  3. `{body}` (nur Body, Fallback)
  Alle Formate werden mit HMAC-SHA256 gegen alle konfigurierten Secrets geprüft.
- **auth.py**: Ausführliches Logging: erkannter Modus, Timestamp, Pfad, Request-ID,
  welches kanonische Format gematcht hat, bei Mismatch Debug-Ausgabe der erwarteten
  Werte pro Format
- **webhook_handler.py**: Debug-Endpoint erkennt `x-printix-signature` und zeigt
  Timestamp, Request-Path und Request-ID in der Debug-Ausgabe
- Rückwärtskompatibel: `x-printix-signature-256`, `-512`, `x-hub-signature-256`,
  Bearer Token und `x-connector-token` funktionieren weiterhin

### Migration
Wer `capture_port: 8775` (oder einen anderen Wert > 0) hatte:
→ Ersetzen durch `capture_enabled: true`

Wer `capture_port: 0` hatte:
→ Ersetzen durch `capture_enabled: false` (oder Option weglassen, Default ist false)

---

## 4.5.5 (2026-04-13) — Capture Webhook ohne separaten Port

### Fix — Port 8775 wird von HA nicht nach außen gemappt
- **Root Cause**: HA Supervisor mappt nachträglich hinzugefügte Ports (8775) nicht
  automatisch nach außen. Im `docker ps` steht nur `8775/tcp` (intern), aber kein
  `0.0.0.0:8775->8775/tcp`. Der User muss den Port unter Add-on → Netzwerk manuell
  aktivieren — das ist HA-Standardverhalten, kein Code-Bug.
- **Lösung**: Capture-Webhooks funktionieren **immer** über den MCP-Port (8765) und
  den Web-Port (8080). Der separate Server auf 8775 ist rein optional.
- **run.sh**: `CAPTURE_PORT` env var wird jetzt nur exportiert wenn der separate
  Capture-Server tatsächlich aktiv ist (CAPTURE_ENABLED > 0). Vorher wurde immer
  `CAPTURE_PORT=8775` exportiert — dadurch dachte der MCP-Server fälschlicherweise,
  der separate Capture-Server laufe, und zeigte irreführende Log-Meldungen.
- **run.sh**: Klare Log-Meldung wenn kein separater Port aktiv:
  `"Capture-Webhooks laufen über MCP-Port (8765) — kein separater Port nötig"`
- **run.sh**: Wenn separater Port aktiv, Hinweis mit Pfad:
  `"Einstellungen > Add-ons > Printix MCP > Netzwerk > 8775"`
- **server.py**: MCP-Server erkennt jetzt korrekt ob separate Capture läuft
  (CAPTURE_PORT=0 wenn deaktiviert, statt fälschlicherweise 8775)

### Hinweis für Benutzer
Capture-Webhooks funktionieren über **drei** Endpunkte:
- `http://<HA-IP>:8765/capture/webhook/<profile_id>` — MCP-Port (immer aktiv)
- `http://<HA-IP>:8080/capture/webhook/<profile_id>` — Web-Port (immer aktiv)
- `http://<HA-IP>:8775/capture/webhook/<profile_id>` — Separater Port (optional, capture_port > 0)

Wenn Port 8775 nicht von außen erreichbar ist:
1. Webhooks über Port 8765 (MCP) oder 8080 (Web) routen — kein Konfigurationsaufwand
2. Oder: HA → Einstellungen → Add-ons → Printix MCP → Netzwerk → Port 8775 aktivieren

---

## 4.5.4 (2026-04-13) — Capture Port Architecture Fix

### Fix — Capture-Port wird im Container nicht veröffentlicht
- **Root Cause**: `capture_port` Config-Option diente gleichzeitig als Ein/Aus-Schalter
  UND als Port-Nummer. Docker mapped aber immer den fixen Container-Port 8775
  (definiert in `config.yaml ports:`). Wenn z.B. `capture_port=8775` gesetzt war,
  band der Server zwar auf 8775, aber die Config-Logik war fragil.
  Bei `capture_port=0` (Standard) startete nichts — korrekt, aber undurchsichtig.
- **run.sh**: Architektur-Fix — `capture_port` ist jetzt NUR ein Ein/Aus-Schalter
  (0=aus, >0=ein). Der Container-Port ist IMMER 8775 (Konstante `CAPTURE_CONTAINER_PORT`),
  passend zum Docker-Portmapping in `config.yaml`. Der Host-Port wird in HA unter
  Add-on → Netzwerk konfiguriert (wie bei Web-Port 8080).
- **run.sh**: Neuer Hinweis im Log: "Port 8775 muss in HA unter Add-on > Netzwerk
  aktiviert sein!" — wichtig weil HA Supervisor neue Ports bei Updates ggf. deaktiviert
- **run.sh**: Lokaler Konnektivitätstest nach Startup — prüft ob 127.0.0.1:8775
  tatsächlich antwortet (nicht nur ob der Prozess lebt)
- **config.yaml**: Kommentar verdeutlicht dass `capture_port` ein Ein/Aus-Schalter ist

---

## 4.5.3 (2026-04-13) — Capture-Server Startup Fix

### Fix — Separater Capture-Server startet nicht
- **Dockerfile**: `EXPOSE 8775` fehlte — Port war im Container nicht freigegeben
- **run.sh**: Diagnostisches Logging fuer `CAPTURE_PORT` und `CAPTURE_PUBLIC_URL`
  direkt nach dem Lesen aus bashio::config — Werte jetzt im Add-on-Log sichtbar
- **run.sh**: Existenz-Check fuer `/app/capture_server.py` vor dem Start
- **run.sh**: `stderr` des Capture-Prozesses wird jetzt nach `stdout` umgeleitet
  (`2>&1`) — Import-Fehler und Crashes sind im Add-on-Log sichtbar
- **run.sh**: Nach 2s Wartezeit Prozess-Check (`kill -0`) — bei sofortigem
  Crash erscheint eine klare Fehlermeldung im Log
- **capture_server.py**: Sofort-Logging via `print()` noch vor allen Imports —
  zeigt PID, CAPTURE_PORT und CAPTURE_HOST sofort im Log
- **capture_server.py**: FastAPI/uvicorn Imports in try/except mit klarer
  Fehlermeldung bei fehlendem Paket
- **capture_server.py**: Port-Validierung (muss Integer 1-65535 sein)
- **capture_server.py**: App-Erstellung und `uvicorn.run()` in try/except —
  jeder Fehler wird geloggt und endet mit `sys.exit(1)` statt stillem Crash

---

## 4.5.2 (2026-04-13) — Capture Connector Model

### Feature — Printix/Tungsten Capture Connector Alignment
- **Multi-Secret HMAC**: Mehrere HMAC-Secrets pro Profil (zeilengetrennt) —
  Key-Rotation ohne Downtime, alle Secrets werden bei Verifizierung durchprobiert
- **Multi-Token Connector Auth**: Mehrere Connector-Tokens pro Profil —
  `Authorization: Bearer <token>` und `x-connector-token` Header
- **`require_signature` Flag**: Pro Profil konfigurierbar ob Authentifizierung
  Pflicht ist — ohne Flag gilt Printix-Kompatibilitaetsmodus (Requests ohne
  Credentials werden akzeptiert)
- **Neues `capture/auth.py` Modul**: Ersetzt `hmac_verify.py` mit `AuthResult`
  Dataclass, Multi-Secret/Token-Support, `x-hub-signature-256` Support

### Feature — CaptureEvent Model
- **Strukturiertes Event-Modell**: `CaptureEvent` Dataclass mit event_type,
  document_url, filename, system_metadata, index_fields, content_type, file_size,
  user_name, device_name, timestamp
- **Bekannte Event-Typen**: FileDeliveryJobReady, DocumentCaptured, ScanComplete,
  ScanJobCompleted, JobCreated/Completed/Failed/Cancelled, etc.
- **System-Metadaten vs. Index Fields**: Klare Trennung zwischen
  Plattform-Metadaten (tenant_id, user, device, job_id) und benutzerdefinierten
  Index-Feldern (indexFields/metadata)
- **Payload-Validierung**: Strukturierte Pruefung mit Warnungen fuer fehlende/
  unbekannte Felder

### Feature — Erweitertes Capture-Profilmodell
- **3 neue DB-Spalten**: `require_signature`, `metadata_format`, `index_fields_json`
- **Metadata Format**: flat (key-value), structured (system + index), passthrough
- **Index Field Definitions**: JSON-Array zur Definition erwarteter Custom-Felder
- **UI-Update**: Textarea fuer Multi-Secrets/Tokens, Checkbox fuer
  require_signature, Select fuer metadata_format, Textarea fuer index_fields

### Feature — Enhanced Debug Endpoint
- Debug-Antwort zeigt jetzt: erkannte Auth-Methode, geparseter Event-Typ,
  vorhandene/fehlende Pflichtfelder, ob Payload dem Capture-Format entspricht,
  System-Metadaten und Validierungswarnungen

### Feature — Strukturiertes Capture-Logging
- Jeder Verarbeitungsschritt mit eigenem Log-Marker:
  `[step:profile]`, `[step:auth]`, `[step:parse]`, `[step:event]`,
  `[step:validate]`, `[step:plugin]`, `[step:process]`
- Auth-Methode und Event-Details im Capture-Log (details-Feld)

---

## 4.5.1 (2026-04-13) — Fleet Fix + HA Schema Fix

### Fix — config.yaml Schema-Validierung (KRITISCH)
- `capture_public_url` Schema von `url?` auf `str?` geaendert — HA-Validator
  lehnte leere Strings ab, was Add-on-Updates blockierte:
  `"expected a URL. Got {'capture_public_url': '', ...}"`

### Fix — /fleet Internal Server Error
- **Crash behoben**: `_load_fleet_data()` als shared async Funktion extrahiert,
  wird von `/fleet` (HTML) und `/fleet/data` (JSON) gemeinsam genutzt
- **Error Rate**: Berechnung aus SQL `tracking_data` (failed vs. total jobs, 90 Tage)
- **API/SQL Merge**: Primaer ueber `printer_id`, Fallback ueber `printer_name`
- **Template robust**: `| default(0)` fuer `error_rate`, `total_jobs`, `total_pages`
  — kein Crash mehr wenn Felder fehlen
- **KPI-Logik**: `active_today` zaehlt `status=="active"`, `inactive_7d` zaehlt
  `status=="critical"`, `avg_utilization` basiert auf `active_days/90`
- **Alerts**: Inactive-Drucker + High Error Rate (>10%) als Warnungen
- **`/fleet/data` Endpunkt**: Liefert echte Fleet-Daten als JSON fuer Auto-Refresh
- **Fehlerbehandlung**: try/except um gesamte Fleet-Logik, Fallback auf leere Daten

---

## 4.5.0 (2026-04-13) — Capture-Server Entkopplung

### Feature — Separater Capture-Server (optional)
- **Neuer eigenstaendiger Capture-Server** (`capture_server.py`): FastAPI/Uvicorn-App
  nur fuer Capture Webhooks, laeuft auf eigenem Port getrennt vom MCP-Server
- **Neue Konfigurationsoptionen** in `config.yaml`:
  - `capture_port` (Standard: 0 = deaktiviert) — eigener Port fuer Capture-Webhooks
  - `capture_public_url` — eigene oeffentliche URL (z.B. `https://capture.printix.cloud`)
- **Drei-Server-Architektur** (optional): Web-UI (8080) + MCP (8765) + Capture (8775)
- **Rueckwaertskompatibel**: Wenn `capture_port=0`, laufen Webhooks wie bisher ueber MCP-Port

### Feature — Capture-URL in Web-UI konfigurierbar
- **Admin-Einstellungen**: Neues Feld `Capture Webhook URL` zum Konfigurieren
  einer separaten Capture-Domain
- **Capture Store**: Zeigt Info-Banner wenn Capture separat konfiguriert ist
- **URL-Prioritaet**: `capture_public_url` > `public_url` > Request-Fallback
- Webhook-URLs in der UI werden automatisch aus der richtigen Basis-URL generiert

### Feature — Verbessertes Logging fuer Capture
- Eigener Log-Marker `[capture-server]` fuer Requests auf dem Capture-Port
- MCP-Server loggt `[mcp-compat]` wenn Capture-Requests trotz separatem Server
  noch ueber den MCP-Port kommen
- Eigene Startup-Banner fuer den Capture-Server

### Architektur
- `capture/webhook_handler.py` bleibt der kanonische Handler — wird jetzt von
  drei Quellen aufgerufen: `capture_server.py`, `server.py`, `web/capture_routes.py`
- Kein duplizierter Code — alle Pfade nutzen denselben Handler
- `run.sh` startet den Capture-Server als Hintergrund-Prozess wenn `capture_port > 0`

---

## 4.4.15 (2026-04-13) — Demo-Merge Qualitaetsfixes

### Fix — Key-based Merge statt Blind-Append
- **printer_history**: Merge auf `(period, printer_name)` Key — verhindert Duplikate
  wenn SQL- und Demo-Daten denselben Drucker/Zeitraum betreffen
- **queue_stats**: Merge auf `(paper_size, color, duplex)` Key — korrekte Aggregation
  statt doppelter Zeilen fuer identische Kombinationen
- **service_desk**: Merge auf `(group_key, status)` Key — keine doppelten Fehlertypen

### Fix — Trend: Distinct User/Printer-Zaehlung
- `query_trend` holt jetzt per separater SQL-Abfrage die tatsaechlichen distinct
  `tenant_user_id` und `printer_id` Sets und bildet die Union mit Demo-IDs —
  kein additives Zaehlen mehr bei `active_users` / `active_printers`

### Fix — Anomalien: Vollstaendige Neuberechnung auf kombinierten Daten
- `query_anomalies` fuehrt jetzt eine separate SQL-Abfrage fuer ALLE Tageswerte
  durch (nicht nur Anomalie-Tage), merged diese mit Demo-Tageswerten, und
  berechnet Durchschnitt, Standardabweichung und z-Scores komplett neu auf
  den kombinierten Daten

### Fix — Sensitive Documents: demo.jobs_scan entfernt
- `query_sensitive_documents` referenziert nicht mehr `demo.jobs_scan` als
  SQL-Fallback (existiert nicht in Azure SQL seit v4.4.0)
- SQL-Scan-Branch wird deaktiviert wenn View nicht vorhanden — Demo-Scan-Daten
  kommen per Python-Merge aus lokaler SQLite

### Fix — Workstation-Reports: Klare Demo-Modus-Meldung
- `query_workstation_overview` und `query_workstation_detail` zeigen eine klare
  Meldung wenn nur Demo-Daten aktiv und keine dbo.workstations-Tabelle vorhanden

### Feature — Demo-Generator: Realistische Fehlerquoten
- 3% aller Demo-Jobs erhalten jetzt einen Fehlerstatus:
  PRINT_FAILED, PRINT_CANCELLED, PRINTER_OFFLINE, PAPER_JAM, TONER_EMPTY
- Ermoeglicht endlich nicht-leere `service_desk`-Reports mit Demo-Daten

---

## 4.4.14 (2026-04-12) — Demo-Daten Merge fuer ALLE Reports

### Feature — Demo-Merge-Layer auf alle Report-Typen erweitert
- **Vorher**: Nur 4 von ~20 Reports nutzten Demo-Daten (print_stats, cost_report, top_users, top_printers)
- **Nachher**: Alle relevanten Reports mergen jetzt Demo-Daten aus lokaler SQLite:
  - `query_printer_history` — Drucker-Historie mit Demo-Druckern
  - `query_device_readings` — Geraeteuebersicht mit Demo-Druckern
  - `query_job_history` — Job-Verlauf inkl. Demo-Jobs (paginiert)
  - `query_queue_stats` — Papierformat/Farb-Verteilung mit Demo-Daten
  - `query_user_detail` — Benutzer-Drill-Down mit Demo-Usern
  - `query_tree_meter` — Nachhaltigkeits-Kennzahlen mit Demo-Duplex-Daten
  - `query_anomalies` — Anomalie-Erkennung mit Demo-Tageswerten (Z-Score in Python)
  - `query_trend` — Perioden-Vergleich mit Demo-Daten in beiden Zeitraeumen
  - `query_hour_dow_heatmap` — Nutzungs-Heatmap mit Demo-Zeitstempeln
  - `query_user_scan_detail` — Scan-Reports mit Demo-Scan-Jobs
  - `query_user_copy_detail` — Copy-Reports mit Demo-Copy-Jobs
  - `query_service_desk` — Fehlgeschlagene Jobs mit Demo-Fehlerstatus
  - `query_off_hours_print` — Off-Hours-Analyse mit Demo-Submit-Zeiten
  - `query_sensitive_documents` — Keyword-Suche in Demo-Job-Filenames + Demo-Scans
- Nicht geaendert: `query_workstation_*` (keine Demo-Daten), `query_audit_log` (Admin-DB),
  `query_forecast` (nutzt bereits query_print_stats indirekt)

### Feature — Neue Demo-Datenquellen in local_demo_db.py
- `query_demo_scan_jobs()` — Demo-Scan-Jobs mit User/Printer/Network JOINs
- `query_demo_copy_jobs()` — Demo-Copy-Jobs + Copy-Details mit JOINs
- `query_demo_jobs()` — Demo-Jobs fuer Off-Hours/Sensitive-Docs/Queue-Stats
- `query_demo_tracking_data()` liefert jetzt auch `paper_size` (fuer Queue-Stats)

### Fix — Alle SQL-Queries in try/except gewrappt
- Reports die bisher bei SQL-Fehlern mit 500 abstürzten, fallen jetzt auf Demo-Daten zurück
- Betrifft: printer_history, device_readings, job_history, queue_stats, user_detail,
  user_copy_detail, user_scan_detail, anomalies, trend, heatmap, service_desk, off_hours

## 4.4.13 (2026-04-12) — Versionen, Log-Marker, Cleanup

### Fix — Startup-Banner im MCP-Server zeigte v4.4.5 statt aktuelle Version
- `server.py` Python-Startup-Banner (logger.info) war auf v4.4.5 stehen geblieben
- Jetzt konsistent v4.4.13 in allen 4 Stellen (config.yaml, run.sh, server.py Kopf + Banner)

### Fix — CAPTURE REQUEST Log-Marker fehlte im Web-Route-Handler (Port 8080)
- Der `▶ CAPTURE REQUEST` Marker existierte nur im MCP-Router (Port 8765)
- Wenn Webhooks über den Web-Port (8080/8010) eingingen, fehlte der Marker komplett
- Fix: Marker in allen 3 Web-Route-Handlern (POST webhook, GET health, debug)

### Fix — Dummy-Code in capture_routes.py entfernt
- `await asyncio.to_thread(lambda: None) if False else await handle_webhook(...)`
- War übriggebliebener Platzhalter-Code — jetzt direkt `await handle_webhook(...)`

### Docs — Webhook-Response-Protokoll dokumentiert
- HTTP-Status-Strategie im webhook_handler.py erklärt:
  - HTTP 4xx/5xx nur bei Infrastruktur-Fehlern (Profil/HMAC/JSON)
  - HTTP 200 + `errorMessage` für Plugin-Ergebnisse (Printix Capture Protokoll)

### Docs — HMAC soft-verify Warnung verbessert
- Explizitere Log-Meldung wenn Request ohne Signatur-Header durchgelassen wird
- Hinweis auf zukünftiges `require_signature` Flag

## 4.4.12 (2026-04-12) — Paperless Upload: Name→ID Auflösung

### Fix — Tags, Correspondent, Document Type wurden als Namen statt IDs gesendet
- Paperless-ngx API `/api/documents/post_document/` erwartet **IDs** (integers)
- Plugin sendete bisher **Namen** (strings) → wurden silently ignoriert
- Fix: Automatische Name→ID Auflösung via Paperless REST API
  - Tags: `/api/tags/?name__iexact=...` — pro Tag einzeln aufgelöst
  - Correspondent: `/api/correspondents/?name__iexact=...`
  - Document Type: `/api/document_types/?name__iexact=...`
- **Auto-Create**: Existiert ein Tag/Correspondent/DocType noch nicht, wird er automatisch angelegt
- Upload-Log zeigt jetzt aufgelöste IDs: `tags=[1,3], corr=5, dtype=2`
- `Accept: application/json` Header auch beim Upload-Request
- Pattern aligned mit `mnimtz/Paperless-MCP` Client (`paperless_client.py`)

## 4.4.11 (2026-04-12) — Paperless test_connection: HTTP 406 fix

### Fix — Paperless test_connection HTTP 406
- `/api/?format=json` root endpoint caused DRF to return 406 "Not Acceptable"
- Fix: Use `/api/documents/?page_size=1` instead — lightweight, reliable, works behind reverse proxies
- Also removed `?format=json` from `/api/ui_settings/` version check
- `Accept: application/json` header is sufficient (no query param needed)
- Bonus: Shows document count in success message ("Connection successful — 42 documents")
- Pattern aligned with user's working Paperless-MCP client (`mnimtz/Paperless-MCP`)

## 4.4.10 (2026-04-12) — Paperless test_connection: Accept-Header

### Fix — Paperless test_connection gibt "HTML instead of JSON"
- `test_connection()` sendete keinen `Accept: application/json` Header
- Paperless-ngx DRF Browsable API oder Reverse-Proxy antwortet dann mit HTML
- Fix: `Accept: application/json` Header + `?format=json` Query-Parameter
- Betrifft auch den Version-Check via `/api/ui_settings/`

## 4.4.9 (2026-04-12) — Log-Sichtbarkeit, Versionskonsistenz, Webhook-Cleanup

### Fix — Versionsangaben konsistent
- README.md (war 4.3.1), run.sh Kommentar (war v4.0.0), webhook_handler (war v4.4.6) alle auf 4.4.9

### Fix — Capture-Webhooks im Log unsichtbar
- `uvicorn.access` war auf WARNING unterdrückt → eingehende HTTP-Requests komplett unsichtbar
- Fix: Access-Logger wieder auf INFO belassen
- Zusätzlich: `▶ CAPTURE REQUEST: POST /capture/webhook/...` im DualTransportApp bei jedem Capture-Request

### Fix — Webhook-Antworten uneinheitlich
- Frühe Fehler (404, 401, 400) gaben `{"error": "..."}` zurück
- Plugin-Ergebnisse gaben `{"errorMessage": "..."}` zurück
- Fix: Alle Antworten jetzt einheitlich `{"errorMessage": "..."}` (Printix-kompatibel)

### Fix — Paperless erzwang immer application/pdf
- Content-Type wurde hardcoded als `application/pdf` gesetzt
- Fix: Automatische Erkennung via `mimetypes.guess_type()` aus Dateiendung

## 4.4.8 (2026-04-12) — reporting.v_* Views abgeschafft

### Fix — "Invalid object name 'demo.jobs_scan'" bei Reports
- **Ursache**: Die `reporting.v_*` Views machten `UNION ALL` aus `dbo.*` + `demo.*`
- Seit v4.4.0 existieren `demo.*` Tabellen in Azure SQL nicht mehr (Demo auf SQLite)
- Jede Query die über eine `reporting.v_*` View lief → 500er
- **Fix**: `_V()` gibt jetzt immer `dbo.{table}` zurück — Views werden nicht mehr verwendet
- Demo-Daten werden bereits in Python gemerged (`_has_active_demo()` / `_merge_aggregated()`)

## 4.4.7 (2026-04-12) — Demo-System Fix + View-Detection + Cleanup

### Fix — Rollback-All kaputt (demo_jobs_copy_details)
- `demo_jobs_copy_details` hat kein `tenant_id` — `rollback_all_demos()` schlug fehl
- Fix: Löscht jetzt via `WHERE job_id IN (SELECT id FROM demo_jobs_copy WHERE tenant_id = ?)`
- `rollback_demo_session()` war nicht betroffen (nutzt `demo_session_id`)

### Fix — Demo-MCP-Tools blockiert ohne Azure SQL
- `_demo_check()` verlangte Azure SQL Credentials obwohl Demo seit v4.4.0 auf SQLite läuft
- Fix: Prüft nur noch ob Tenant-Kontext (Bearer Token) vorhanden ist
- Alle 4 Demo-Tool-Beschreibungen von "Azure SQL" auf "lokale SQLite" aktualisiert

### Fix — Druckerflotte / Reports: 500 Internal Server Error
- `_V()` prüfte nur einmal ob `reporting.v_tracking_data` existiert
- Dann wurden ALLE anderen Views (`v_printers`, `v_networks` usw.) vorausgesetzt
- Fehlte eine View → "Invalid object name" → 500er
- Fix: Jede View pro Tabelle einzeln prüfen + cachen (per-table Fallback auf `dbo.*`)

### Fix — Paperless test_connection bei Proxy/HTML-Antwort
- `test_connection()` rief `resp.json()` ohne Content-Type-Prüfung auf
- Proxy/Login-Seiten die HTML zurückgeben → unsauberer Crash
- Fix: Content-Type prüfen, bei HTML klare Fehlermeldung

### Fix — Multipart-Debug-Logs zu laut
- `python_multipart` und `python_multipart.multipart` Logger auf WARNING gesetzt

### Cleanup — Legacy Azure SQL Demo-Code entfernt
- 348 Zeilen `SCHEMA_STATEMENTS` und `_create_v_jobs_view()` aus `demo_generator.py` entfernt
- Waren seit v4.4.0 komplett toter Code (Demo läuft auf lokaler SQLite)

## 4.4.6 (2026-04-12) — Kanonischer Capture Handler + Demo-Data Fix

### Architektur — Ein einziger Capture Webhook Handler
- **NEU**: `capture/webhook_handler.py` — kanonischer Handler für alle Capture Webhooks
- Sowohl Web-UI (Port 8080) als auch MCP-Server (Port 8765) delegieren an `handle_webhook()`
- Eliminiert ~180 Zeilen duplizierten Code aus `server.py` und `capture_routes.py`
- Korrekte HMAC-Verifizierung: `verify_hmac(body_bytes, headers, secret_key)`
- Korrekte Plugin-Instanziierung: `create_plugin_instance(plugin_type, config_json)`
- Korrekte Plugin-API: `plugin.process_document(document_url, filename, metadata, body)`
- Korrekte Capture-Log-Signatur: `add_capture_log(tenant_id, profile_id, profile_name, event_type, status, msg)`
- Strukturiertes Logging mit `[source]` Prefix (web/mcp)

### Fix — MCP Capture Handler hatte 6 kritische Bugs
1. HMAC-Parameter in falscher Reihenfolge (`headers, body` statt `body, headers`)
2. Secret-Key aus `config_json` statt aus `profile["secret_key"]` gelesen
3. `plugin_id` statt `plugin_type` für Plugin-Instanziierung verwendet
4. Dokument manuell heruntergeladen statt URL an Plugin zu übergeben
5. Falsche `add_capture_log` Signatur (4 statt 6 Parameter)
6. Plugin.process_document mit falscher Signatur aufgerufen

### Fix — Demo-Daten in Reports nicht sichtbar
- Wenn Azure SQL fehlschlägt (z.B. Free-Tier Limit), blockierte die Exception den Demo-Merge
- `query_fetchall()` in allen 4 Report-Funktionen jetzt mit try/except geschützt
- Bei SQL-Fehler: `sql_results = []` → Demo-Daten werden trotzdem angezeigt
- Betrifft: `query_print_stats`, `query_cost_report`, `query_top_users`, `query_top_printers`

## 4.4.5 (2026-04-12) — Webhook-URL Warnung + korrekte Anzeige

### Fix — Webhook Base-URL im Capture Store
- `_get_webhook_base()` gibt jetzt `(url, is_configured)` Tuple zurück
- **Warnung** auf der Capture Store Seite wenn `public_url` nicht konfiguriert ist
- Erklärt dem Benutzer: Webhook-URLs müssen auf den MCP-Port zeigen
- Link zu Admin-Einstellungen zum Konfigurieren der `public_url`

## 4.4.4 (2026-04-12) — Capture Webhook auf MCP-Port

### Fix — Webhook auf falschem Port
- **Ursache**: Capture-Webhook-Routen waren nur auf Port 8080 (Web-UI) registriert
- Printix sendet an die `public_url` → Port 8765 (MCP) → keine Route → nichts passiert
- **Fix**: Capture-Webhook-Handler jetzt auch auf dem MCP-Port (8765) im `DualTransportApp`
- `BearerAuthMiddleware` lässt `/capture/webhook/` und `/capture/debug` ohne Bearer Token durch
- Voller Webhook-Support auf MCP-Port: HMAC-Verify, Plugin-Dispatch, Debug-Modus
- Web-UI-Port (8080) behält ebenfalls die Webhook-Routen (Dual-Port)

## 4.4.3 (2026-04-12) — Debug Webhook URL für Printix

### Fix — Debug-URL Printix-kompatibel
- Printix akzeptiert nur URLs im Format `/capture/webhook/{uuid}`
- Debug-Endpoint jetzt erreichbar über: `/capture/webhook/00000000-0000-0000-0000-000000000000`
- POST + GET (Health-Check) auf die Debug-UUID leiten an Debug-Handler weiter
- Bisherige `/capture/debug` Pfade funktionieren weiterhin

## 4.4.2 (2026-04-12) — Capture Debug Endpoint + aiohttp Fix

### Feature — Debug Endpoint
- **`/capture/debug`**: Neuer Test-Endpoint zum Analysieren eingehender Printix Webhooks
- Loggt alle Headers, Body, Query-Params und gibt alles als JSON zurück
- Catch-All für Sub-Pfade (`/capture/debug/{path}`)
- Hilfreich zum Debuggen des Printix Capture Connector Formats

### Fix — aiohttp fehlte in requirements.txt
- **`aiohttp>=3.9.0`** war nicht in `requirements.txt` — Ursache für ALLE Capture-Store-Fehler
- Paperless-ngx Plugin konnte `import aiohttp` nicht ausführen → "The string did not match the expected pattern"
- Test-Button und Webhook-Verarbeitung schlugen beide fehl

### Fix — Capture Webhook
- **Verbose Logging**: Webhook-Handler loggt jetzt alle eingehenden Headers, Body-Preview, parsed Keys
- **HMAC toleranter**: Wenn Printix keine Signatur-Header sendet (aber Secret konfiguriert), wird der Request trotzdem durchgelassen statt 401
- **HMAC Prefix-Handling**: Unterstützt jetzt `sha256=HEXDIGEST` Format (wie GitHub Webhooks)
- **Flexible Feld-Erkennung**: `documentUrl`/`DocumentUrl`/`blobUrl`, `fileName`/`FileName`/`name`, `eventType`/`EventType`
- **JSON-Parse-Fehler** werden jetzt ins Capture-Log geschrieben (mit Body-Preview)
- **CAPTURE Log-Kategorie** im `/logs`-Filter ergänzt (fehlte vorher)
- **test_connection()**: Exception-Handling für fehlende Abhängigkeiten

### Fix — Webhook URL HTTPS
- Capture Store + Form nutzen jetzt `MCP_PUBLIC_URL`/`public_url` statt `request.url.scheme`
- Zeigt korrekte HTTPS-URL statt internes HTTP

## 4.4.0 (2026-04-12) — Capture Store, Fleet/Dashboard API-First, Demo Local SQLite

### Feature — Capture Store (`/capture`)
- **Neues Hauptregister** "Capture Store" in der Navigation (vor Hilfe)
- **Plugin-System**: Erweiterbare Architektur für Capture-Ziele
- **Paperless-ngx Plugin**: Gescannte Dokumente automatisch an Paperless-ngx senden (OCR + Archivierung)
- **Profil-Verwaltung**: Beliebig viele Capture-Profile pro Tenant anlegen/bearbeiten/löschen
- **HMAC-Verifizierung**: SHA-256/SHA-512 Signaturprüfung für eingehende Printix Webhooks
- **Verbindungstest**: Integrierter Test-Button prüft Erreichbarkeit des Ziel-Systems
- **Webhook-Endpoint**: `/capture/webhook/{profileId}` — pro Profil individuelle URL
- **Capture-Logs**: Alle Capture-Events in den Tenant-Logs unter Kategorie "CAPTURE"
- **14 Sprachen**: Vollständige Übersetzung aller Capture Store Texte
- **Webhook-URL nutzt public_url** (HTTPS) statt request scheme (HTTP)

### Feature — Demo-Daten: Lokale SQLite statt Azure SQL
- **Kein Azure SQL Schreibzugriff** mehr nötig für Demo-Daten!
- Demo-Daten werden in `/data/demo_data.db` (SQLite) gespeichert
- Azure SQL bleibt rein **lesend** (dbo.* Tabellen für echte Printix-Daten)
- Reports mergen automatisch: Azure SQL (echte Daten) + SQLite (Demo-Daten)
- Demo-Generator (`demo_generator.py`) schreibt direkt in lokale SQLite
- Demo-Worker (`demo_worker.py`) braucht keine SQL-Credentials mehr
- Web-UI Demo-Seite funktioniert ohne SQL-Konfiguration
- Erlaubt Downgrade auf **kostenlose Printix Azure SQL** (rein lesend)

### Fix — Fleet Health: API-First
- **Druckerdaten jetzt primär von Printix API** (nicht mehr SQL-abhängig)
- Drucker-Deduplizierung nach printer_id (wie Printix → Drucker Tab)
- `connectionStatus` aus API als primärer Status-Indikator
- SQL-Daten optional als Enrichment (historische Jobs/Seiten/Auslastung)

### Fix — Dashboard: API-First
- **Aktive Drucker** werden jetzt live von der Printix API gezählt
- KPI-Kacheln erscheinen auch ohne Azure SQL (Druckerzahl immer sichtbar)
- SQL nur noch für historische Druckvolumen, Sparkline, Forecast, Umweltbilanz
- Banner: erklärt, dass SQL optional ist für historische Daten

### Fix — Fehlende Übersetzungen
- 14 fehlende Dashboard-Keys ergänzt (alle 14 Sprachen)
- `dash_sparkline_nodata`, `dash_forecast_nodata`, `dash_creds_title` u.a.

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

### Capture Connector — Test-Endpoint
- `POST /capture/webhook` — empfängt Printix Capture Notifications (Test/Debug)
- `GET /capture/webhook` — Health-Check für den Capture Endpoint
- `GET /capture/log` — Admin-only: letzte empfangene Webhooks als JSON
- Loggt Headers, Body, Signatur-Daten in `/data/capture_webhooks.jsonl`

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
