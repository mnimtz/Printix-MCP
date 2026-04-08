# Printix MCP Server — Home Assistant Add-on

MCP-Server (Model Context Protocol) für die Printix Cloud Print API als Home Assistant Add-on.
Ermöglicht AI-Assistenten wie **claude.ai** und **ChatGPT** die Steuerung von Printix-Druckern,
Benutzern, Karten, Netzwerken und mehr — gesichert über OAuth 2.0 oder Bearer Token.

**Version: 1.14.0**

## Features

- **45+ MCP-Tools** für Printix Cloud Print API + AI Reporting
- Drei API-Bereiche: Print, Card Management, Workstation Monitoring
- **AI Reporting**: Druckvolumen, Kosten, Top-User, Trend-Vergleich direkt aus Azure SQL
- **Automatische Reports**: APScheduler mit Resend Mail-Versand (täglich/wöchentlich/monatlich)
- **Dual Transport**: Streamable HTTP (`/mcp`) für claude.ai + SSE (`/sse`) für ChatGPT
- **OAuth 2.0** Authorization Code Flow (kompatibel mit claude.ai Konnektoren + ChatGPT)
- Bearer Token Authentifizierung als Fallback
- Auto-Generierung von Bearer Token + OAuth-Credentials beim ersten Start
- Persistente Secrets in `/data/mcp_secrets.json` — überleben Add-on-Updates
- `public_url` Konfigurationsfeld: fertige Verbindungs-URLs direkt im Startup-Log
- Konfigurierbares Logging (debug bis critical)
- Health-Check Endpoint (`/health`)

## Installation

### Als Home Assistant Add-on (lokal)

1. Add-on-Ordner in `/addons/printix-mcp/` ablegen
2. In Home Assistant: **Einstellungen → Add-ons → Add-on Store → Neu laden**
3. **Printix MCP Server** aus „Lokale Add-ons" installieren
4. Unter **Konfiguration** mindestens `tenant_id` und ein Credentials-Paar eintragen
5. `public_url` auf die öffentlich erreichbare URL setzen (z.B. via Cloudflare Tunnel)
6. Add-on starten — alle Verbindungs-URLs erscheinen im Log

### Via GitHub Repository (geplant)

```
https://github.com/YOUR_USER/printix-mcp-addon
```

## Konfiguration

### Pflichtfelder

| Feld | Beschreibung |
|------|-------------|
| `tenant_id` | Printix Tenant-ID |

### API-Credentials

Printix stellt für drei separate API-Bereiche eigene OAuth-Apps bereit.
Trage die Credentials des Bereichs ein, den du nutzen möchtest.

| Feld | API-Bereich |
|------|------------|
| `print_client_id` / `print_client_secret` | Cloud Print API (Drucker, Jobs, Queues, Netzwerke) |
| `card_client_id` / `card_client_secret` | Card Management API (Karten registrieren/löschen) |
| `ws_client_id` / `ws_client_secret` | Workstation Monitoring API (Workstations, Queues) |
| `shared_client_id` / `shared_client_secret` | **Fallback** — wird für jeden API-Bereich verwendet, für den kein eigenes Credentials-Paar eingetragen ist. Praktisch wenn du eine einzige OAuth-App für alle Bereiche hast. |

Du musst nicht alle drei Paare eintragen — es reicht das Paar für den Bereich, den du tatsächlich nutzt.

### OAuth (für claude.ai + ChatGPT)

| Feld | Beschreibung |
|------|-------------|
| `oauth_client_id` | Frei wählbar, z.B. `printix-mcp-client`. Wird auto-generiert wenn leer. |
| `oauth_client_secret` | Wird auto-generiert wenn leer und dauerhaft in `/data/mcp_secrets.json` gespeichert. |

### Reporting (optional)

Für AI-gestütztes Reporting direkt aus der Printix BI-Datenbank.
Zugangsdaten werden von Printix/Tungsten bereitgestellt.

| Feld | Beschreibung |
|------|-------------|
| `sql_server` | Azure SQL Hostname, z.B. `printix-bi-data-2.database.windows.net` |
| `sql_database` | Datenbankname, z.B. `printix_bi_data_2_1` |
| `sql_username` | SQL-Benutzername |
| `sql_password` | SQL-Passwort |
| `mail_api_key` | Resend API-Key (`re_...`) für automatischen Mail-Versand |
| `mail_from` | Absenderadresse, z.B. `reports@firma.de` |

### Sonstige

| Feld | Beschreibung |
|------|-------------|
| `public_url` | Öffentlich erreichbare URL (z.B. Cloudflare Tunnel). Erscheint fertig formatiert im Startup-Log. |
| `bearer_token` | Statischer Bearer Token. Wird auto-generiert wenn leer. |
| `log_level` | `debug` / `info` / `warning` / `error` / `critical` |

## Verbindung mit claude.ai

1. claude.ai → **Einstellungen → Konnektoren → Verbinden**
2. Felder aus dem Add-on-Log kopieren:
   - **Remote MCP URL:** `https://deine-domain.de/mcp`  ← `/mcp`, nicht `/sse`
   - **OAuth Client-ID:** aus dem Log
   - **OAuth Client-Secret:** aus dem Log
3. OAuth-Autorisierungsseite bestätigen

## Verbindung mit ChatGPT

1. ChatGPT → **Neue App → Authentifizierung: OAuth**
2. Felder aus dem Add-on-Log kopieren:
   - **URL des MCP-Servers:** `https://deine-domain.de/sse`
   - **OAuth Client-ID / Secret:** aus dem Log
   - **Token-Authentif.-methode:** `client_secret_post`
   - **Auth-URL:** `https://deine-domain.de/oauth/authorize`
   - **Token-URL:** `https://deine-domain.de/oauth/token`
   - Scopes und Registrierungs-URL: leer lassen

## AI Reporting — Schnellstart

Sobald SQL-Credentials konfiguriert sind, kann Claude direkt in natürlicher Sprache berichten:

> „Zeig mir die Top 10 Nutzer nach Druckkosten für März, aufgeteilt nach Farbe und S/W"

> „Perfekt. Schick mir das jeden 1. des Monats als HTML an controller@firma.de"

Claude übersetzt die Anfrage in SQL, zeigt das Ergebnis, und richtet auf Wunsch einen automatischen
monatlichen Versand ein — ohne SQL-Kenntnisse oder BI-Tools.

**Verfügbare Report-Tools:**

| Tool | Beschreibung |
|------|-------------|
| `printix_query_print_stats` | Druckvolumen nach Zeitraum, User, Drucker oder Standort |
| `printix_query_cost_report` | Kosten mit Papier-/Toner-Aufschlüsselung |
| `printix_query_top_users` | Nutzer-Ranking nach Volumen oder Kosten |
| `printix_query_top_printers` | Drucker-Ranking nach Volumen oder Kosten |
| `printix_query_anomalies` | Ausreißer-Erkennung |
| `printix_query_trend` | Periodenvergleich mit Delta-Prozenten |
| `printix_save_report_template` | Report als Template speichern |
| `printix_run_report_now` | Template sofort ausführen + per Mail senden |
| `printix_schedule_report` | Automatischen Zeitplan anlegen |
| `printix_list_schedules` | Aktive Schedules anzeigen |

## Vollständige Dokumentation

→ [DOCS.md](printix-mcp/DOCS.md)

## Lizenz

MIT

## Autor

Marcus Nimtz — Tungsten Automation
