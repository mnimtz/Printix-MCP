# Printix MCP Server — Home Assistant Add-on

MCP-Server (Model Context Protocol) für die Printix Cloud Print API als Home Assistant Add-on.
Ermöglicht AI-Assistenten wie **claude.ai** und **ChatGPT** die Steuerung von Printix-Druckern,
Benutzern, Karten, Netzwerken und mehr — gesichert über OAuth 2.0 oder Bearer Token.

## Features

- 30+ MCP-Tools für die Printix Cloud Print API
- Drei API-Bereiche: Print, Card Management, Workstation Monitoring
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

## Vollständige Dokumentation

→ [DOCS.md](printix-mcp/DOCS.md)

## Lizenz

MIT

## Autor

Marcus Nimtz — Tungsten Automation
