# Changelog

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
