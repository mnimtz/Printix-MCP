# Printix MCP Server — Dokumentation

## Übersicht

Dieser Home Assistant Add-on stellt einen MCP-Server für die Printix Cloud Print API bereit.
AI-Assistenten wie claude.ai und ChatGPT können darüber Printix-Ressourcen steuern.

**Transport-Endpunkte:**

| Endpunkt | Methode | Verwendung |
|----------|---------|------------|
| `/mcp` | POST | Streamable HTTP — **claude.ai** (Konnektoren) |
| `/sse` | GET | SSE Transport — **ChatGPT** (Neue App → OAuth) |
| `/health` | GET | Health-Check, ohne Auth |
| `/oauth/authorize` | GET/POST | OAuth 2.0 Autorisierungsseite |
| `/oauth/token` | POST | OAuth 2.0 Token-Endpoint |
| `/.well-known/oauth-authorization-server` | GET | OAuth Discovery (RFC 8414) |
| `/.well-known/oauth-protected-resource` | GET | Resource Metadata (RFC 9728) |

---

## Voraussetzungen

- **Printix Tenant** mit aktiver Cloud Print API
- **Printix Premium** Lizenz (für Benutzerverwaltung und Gast-User)
- **API-Credentials** aus dem Printix Admin-Portal

---

## Konfiguration

### Pflichtfelder

| Feld | Beschreibung |
|------|-------------|
| `tenant_id` | Printix Tenant-ID (UUID) |

### API-Credentials (mindestens ein Bereich)

| Bereich | Client ID | Client Secret | Funktionen |
|---------|-----------|---------------|------------|
| **Print API** | `print_client_id` | `print_client_secret` | Drucker, Jobs, Sites, Netzwerke, Gruppen, SNMP |
| **Card Management** | `card_client_id` | `card_client_secret` | Benutzer, Karten, ID-Codes |
| **Workstation Monitoring** | `ws_client_id` | `ws_client_secret` | Workstations |

**Shared Fallback** (`shared_client_id` / `shared_client_secret`): Wird für alle Bereiche verwendet, für die kein spezifisches Credential-Paar eingetragen ist.

### OAuth & Bearer Token (auto-generiert)

Diese Felder können leer gelassen werden — beim ersten Start werden Werte generiert und
dauerhaft in `/data/mcp_secrets.json` gespeichert. Sie überleben jeden Add-on-Update.

| Feld | Beschreibung |
|------|-------------|
| `bearer_token` | Zugangstoken für direkte Bearer-Auth (leer = auto-generiert) |
| `oauth_client_id` | OAuth Client-ID für ChatGPT/Claude (leer = `printix-mcp-client`) |
| `oauth_client_secret` | OAuth Client-Secret (leer = auto-generiert) |

**Priorität:** Konfigurationsfeld → gespeicherter Wert → neu generieren

### Öffentliche URL

| Feld | Beschreibung |
|------|-------------|
| `public_url` | Öffentlich erreichbare URL (z.B. `https://printix-mcp.example.com`) |

Wenn gesetzt, erscheinen alle Verbindungs-URLs fertig zum Kopieren im Startup-Log.
Empfohlen: Cloudflare Tunnel → `http://HA-IP:8765`

### Log-Level

`debug` · `info` · `warning` · `error` · `critical`

> Hinweis: Drittbibliotheken (MCP-intern, urllib3, uvicorn) sind immer auf `warning` fixiert
> um JSON-Payload-Spam zu vermeiden — unabhängig vom konfigurierten Level.

---

## Verbindung mit claude.ai

1. claude.ai → **Einstellungen → Konnektoren → Verbinden**
2. Werte aus dem Add-on-Startup-Log kopieren:

| Feld | Wert |
|------|------|
| Remote MCP URL | `https://deine-domain.de/mcp` ← **`/mcp`**, nicht `/sse` |
| OAuth Client-ID | aus dem Log |
| OAuth Client-Secret | aus dem Log |

3. Autorisierungsseite im Browser bestätigen

---

## Verbindung mit ChatGPT

ChatGPT → **Mein GPT → Neue App → Authentifizierung: OAuth**

| Feld | Wert |
|------|------|
| URL des MCP-Servers | `https://deine-domain.de/sse` |
| OAuth Client-ID | aus dem Log |
| OAuth Client-Secret | aus dem Log |
| Token-Authentif.-methode | `client_secret_post` |
| Auth-URL | `https://deine-domain.de/oauth/authorize` |
| Token-URL | `https://deine-domain.de/oauth/token` |
| Standard-Scopes | (leer lassen) |
| Registrierungs-URL | (leer lassen) |

---

## Verfügbare MCP-Tools

### Status
- `printix_status` — Credential-Status + Tenant-ID prüfen

### Drucker & Print Queues
- `printix_list_printers` — Drucker auflisten
- `printix_get_printer` — Druckerdetails + Capabilities

### Druckaufträge
- `printix_submit_job` — Druckauftrag anlegen (gibt Upload-URL zurück)
- `printix_complete_upload` — Upload abschließen, Druck auslösen ⚠️ siehe unten
- `printix_list_jobs` — Jobs auflisten
- `printix_get_job` — Job-Details + Status
- `printix_delete_job` — Job löschen
- `printix_change_job_owner` — Job-Eigentümer ändern

### Benutzer
- `printix_list_users` — Benutzer auflisten (role=USER oder GUEST_USER)
- `printix_get_user` — Benutzerdetails
- `printix_create_user` — Gastbenutzer erstellen ⚠️ PIN muss genau 4 Ziffern sein
- `printix_delete_user` — Benutzer löschen
- `printix_generate_id_code` — 6-stelligen ID-Code generieren

### Karten
- `printix_list_cards` — Karten eines Benutzers
- `printix_search_card` — Karte per ID oder Kartennummer suchen
- `printix_register_card` — Karte einem Benutzer zuordnen
- `printix_delete_card` — Kartenzuordnung entfernen

### Gruppen
- `printix_list_groups` — Gruppen auflisten
- `printix_get_group` — Gruppendetails
- `printix_create_group` — Gruppe erstellen ⚠️ siehe unten
- `printix_delete_group` — Gruppe löschen

### Standorte (Sites)
- `printix_list_sites` — Standorte auflisten
- `printix_get_site` — Standortdetails
- `printix_create_site` — Standort erstellen
- `printix_update_site` — Standort aktualisieren
- `printix_delete_site` — Standort löschen

### Netzwerke
- `printix_list_networks` — Netzwerke auflisten
- `printix_get_network` — Netzwerkdetails
- `printix_create_network` — Netzwerk erstellen
- `printix_update_network` — Netzwerk aktualisieren (GET-first, kein Datenverlust)
- `printix_delete_network` — Netzwerk löschen

### Workstations
- `printix_list_workstations` — Workstations auflisten
- `printix_get_workstation` — Workstation-Details

### SNMP
- `printix_list_snmp_configs` — SNMP-Konfigurationen auflisten
- `printix_get_snmp_config` — SNMP-Details
- `printix_create_snmp_config` — SNMP-Konfiguration erstellen
- `printix_update_snmp_config` — SNMP-Konfiguration aktualisieren
- `printix_delete_snmp_config` — SNMP-Konfiguration löschen

---

## Bekannte Verhaltensweisen

### ⚠️ Job-Lifecycle nach `complete_upload`

Der korrekte Druckworkflow ist:
1. `submit_job` → gibt `uploadUrl` und `jobId` zurück
2. Datei per HTTP PUT zur `uploadUrl` hochladen (direkt zu Cloud Storage)
3. `complete_upload` aufrufen → löst Druck aus

Wird `complete_upload` **ohne** vorherigen Datei-Upload aufgerufen, meldet das Backend
kurz `success`, entfernt den Job aber sofort (keine Datei vorhanden). Ein anschließendes
`get_job` liefert dann `404` — das ist korrektes Backend-Verhalten.

### ⚠️ `update_network` — site-Link in Antwort

Der Update-Endpoint liefert eine schlankere HAL-Response als GET (kein `site`-Link).
Die Daten sind korrekt gespeichert. Für die vollständige Ansicht danach
`printix_get_network` aufrufen.

### ⚠️ `create_user` — PIN-Länge

Die PIN muss **genau 4 Ziffern** haben (z.B. `"4242"`). Andere Längen führen zu
`VALIDATION_FAILED`.

### ⚠️ `create_group` — Directory-Voraussetzung

Erfordert eine konfigurierte Directory-Anbindung im Printix Tenant (z.B. Azure AD,
Google Workspace). Ohne Directory schlägt der Aufruf fehl.

---


---

## E-Mail Benachrichtigungen (v2.13.0+)

Der MCP-Server kann E-Mails über die **Resend API** versenden.
Konfiguration in der Web-Oberfläche unter **Einstellungen → E-Mail**.

### Voraussetzung
- Resend-Account mit verifizierter Absenderadresse
- Resend API-Key

### Konfigurationsfelder

| Feld | Beschreibung |
|------|-------------|
| **Mail API-Key** | Resend API-Key (beginnt mit `re_...`) |
| **Absender-E-Mail** | Verifizierte Absenderadresse in Resend |
| **Absender-Anzeigename** | Anzeigename im Postfach (z.B. „Printix Reports") — verhindert Spam-Klassifizierung |
| **Alert-Empfänger** | Kommagetrennte Empfänger-Adressen für alle Benachrichtigungen |
| **Alert-Mindest-Level** | Minimaler Log-Level für Log-Fehler-Benachrichtigungen (WARNING/ERROR/CRITICAL) |

### Benachrichtigungs-Ereignisse (Checkboxen)

| Ereignis | Beschreibung | Prüfintervall |
|----------|-------------|---------------|
| 🚨 **Kritische Log-Fehler** | Server-Log-Einträge auf ERROR/CRITICAL-Niveau | Sofort (Rate-Limit: 5 min) |
| 🖨️ **Neuer Drucker** | Neuer Drucker in Printix erkannt | 30 Minuten |
| 📋 **Neue Drucker-Queue** | Neue Queue in Printix erkannt | 30 Minuten |
| 👤 **Neuer Gast-Benutzer** | Neuer Gast-Benutzer in Printix erkannt | 30 Minuten |
| 📊 **Report versendet** | Bestätigung nach jedem automatischen Report | Bei Versand |
| 🔔 **Neuer MCP-Benutzer** | Admin-Benachrichtigung wenn sich ein neuer Benutzer registriert | Sofort |

### MCP-Tools für E-Mail

| Tool | Beschreibung |
|------|-------------|
| `printix_send_test_email` | Test-E-Mail senden um die Konfiguration zu prüfen |
| `printix_run_report_now` | Report sofort ausführen und per Mail versenden |
| `printix_reporting_status` | Status des Reporting-Moduls prüfen |

---

## Reports & Automatisierungen (v3.0.0+)

Ab v3.0.0 bietet Printix MCP eine vollständige Report-Verwaltung direkt im Web-Browser.

### Reports-Register öffnen

Navigiere zu **Reports** in der oberen Navigationsleiste (erfordert Anmeldung).

### Eigene Report-Templates

In der Listenansicht erscheinen alle gespeicherten Report-Templates des angemeldeten Benutzers:

| Spalte | Beschreibung |
|--------|-------------|
| Name | Template-Name, ggf. mit ⏰-Badge wenn aktiver Zeitplan |
| Typ | Report-Typ (Druckvolumen, Kostenanalyse, Top-Benutzer, …) |
| Empfänger | Kommagetrennte E-Mail-Empfänger |
| Schedule | Automatisierungs-Rhythmus (täglich / wöchentlich / monatlich) |
| Aktionen | ▶ Jetzt ausführen · ✏ Bearbeiten · 🗑 Löschen |

### Neuen Report erstellen

Klicke auf **+ Neuer Report** oder wähle ein Preset aus der Bibliothek (→ „Verwenden").

Das Formular ist in 4 Abschnitte unterteilt:

1. **Grunddaten** — Name, Report-Typ, E-Mail-Betreff
2. **Abfrage-Parameter** — Zeitraum, Gruppierung, Kostenparameter (je nach Typ)
3. **Ausgabe & Empfänger** — Formate (HTML / CSV / JSON), Empfänger, Firmenname, Akzentfarbe
4. **Automatisierung** — optionaler Zeitplan (täglich / wöchentlich / monatlich)

### Preset-Bibliothek

Die Preset-Bibliothek enthält 18 vordefinierte Vorlagen basierend auf dem offiziellen
Printix PowerBI-Template (v2025.4). Presets sind nach Kategorien gruppiert:

| Kategorie | Presets |
|-----------|---------|
| Überblick | Monatlicher Drucküberblick |
| Trend | Wöchentlicher Drucktrend |
| Drucker | Drucker-Übersicht, Drucker-Verlauf* |
| Standort | Standort-Übersicht |
| Benutzer | Benutzer-Übersicht, Druckdetails*, Kopier-Details*, Scan-Details* |
| Kosten | Monatliche Kostenanalyse |
| Analyse | Anomalie-Erkennung |
| Service | Drucker Service-Status*, Service Desk* |
| Infrastruktur | Workstation-Übersicht*, Workstation-Details* |
| Nachhaltigkeit | Tree-O-Meter (CO₂)* |
| Verwaltung | Druckregeln-Übersicht* |
| Jobs | Job-Verlauf* |

*) Presets mit * sind für v3.1 geplant (erscheinen als „Bald verfügbar")

### Voraussetzungen

- **BI-Datenbank**: Für die Report-Ausführung wird eine Printix BI SQL Server-Verbindung benötigt. Ohne SQL-Verbindung können Templates gespeichert, aber nicht ausgeführt werden.
- **E-Mail**: Für den Versand ist ein Resend API-Key erforderlich. Ohne Mail-Konfiguration werden Reports generiert, aber nicht versendet.

### MCP-Tools für Reports

| Tool | Beschreibung |
|------|-------------|
| `printix_list_report_templates` | Alle eigenen Templates anzeigen |
| `printix_save_report_template` | Template per KI-Chat erstellen/speichern |
| `printix_run_report_now` | Report sofort ausführen (nach Name oder ID) |
| `printix_schedule_report` | Automatischen Zeitplan einrichten |
| `printix_delete_report_template` | Template löschen |

---

## Fehlerbehebung

| Fehler | Ursache | Lösung |
|--------|---------|--------|
| `401 invalid_client` | Falsche Printix API Credentials | Credentials in HA-Konfiguration prüfen |
| `401 Unauthorized` auf `/mcp` oder `/sse` | Kein / falscher Bearer Token | OAuth-Flow neu durchführen oder Token prüfen |
| `502` auf allen Endpunkten | Add-on nicht gestartet | HA Log prüfen, Rebuild durchführen |
| `429 Rate Limit` | Zu viele API-Anfragen | Kurz warten, dann wiederholen (Limit: 100 req/min) |
| `VALIDATION_FAILED` bei `update_site` | `path`-Parameter fehlt | Aktuellen Pfad mit `get_site` holen und mitgeben |
| `create_group` schlägt fehl | Kein Directory konfiguriert | Azure AD / Google Workspace im Printix-Portal einrichten |

---

## Architektur

```
claude.ai          ChatGPT
    │                 │
POST /mcp        GET /sse
    │                 │
    └──── OAuthMiddleware ────────────────┐
               │                         │
        GET /oauth/authorize              │
        POST /oauth/token                 │
        GET /.well-known/*                │
               │                         │
         BearerAuthMiddleware             │
               │                         │
         DualTransportApp                 │
          /mcp → StreamableHTTP           │
          /sse → SSE Transport            │
               │                         │
         FastMCP (30+ Tools)              │
               │                         │
         PrintixClient ──────────────────┘
               │
     Printix Cloud Print API
```

**Persistente Daten:** `/data/mcp_secrets.json` — Bearer Token + OAuth-Credentials
**Port:** 8765
**MCP-Version:** 2025-11-25
