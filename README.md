# Printix MCP Server — Home Assistant Add-on

MCP-Server (Model Context Protocol) für die Printix Cloud Print API als Home Assistant Add-on. Ermöglicht die Steuerung von Printix-Druckern, Benutzern, Karten und mehr über AI-Assistenten wie Claude und ChatGPT.

## Features

- 30+ MCP-Tools für Printix Cloud Print API
- Drei API-Bereiche: Print, Card Management, Workstation Monitoring
- Bearer Token Authentifizierung (kompatibel mit Claude & ChatGPT)
- Auto-Generierung des Bearer Tokens beim ersten Start
- Konfigurierbares Logging (debug bis critical)
- Health-Check Endpoint
- Multi-Architektur: amd64, aarch64, armv7, i386

## Installation

### Als Home Assistant Add-on

1. In Home Assistant unter **Einstellungen → Add-ons → Add-on Store** auf die drei Punkte klicken
2. **Repositories** wählen und die Repository-URL eintragen:
   ```
   https://github.com/YOUR_USER/printix-mcp-addon
   ```
3. **Printix MCP Server** aus der Liste installieren
4. Unter **Konfiguration** die Printix-Credentials eintragen
5. Add-on starten
6. Bearer Token aus dem Log kopieren und in die Konfiguration eintragen

### Standalone (Docker)

```bash
docker build -t printix-mcp ./printix-mcp
docker run -d \
  -p 8765:8765 \
  -e PRINTIX_TENANT_ID=your-tenant-id \
  -e PRINTIX_PRINT_CLIENT_ID=your-client-id \
  -e PRINTIX_PRINT_CLIENT_SECRET=your-secret \
  -e MCP_BEARER_TOKEN=your-token \
  printix-mcp
```

## Schnellstart

Nach der Installation und Konfiguration den Bearer Token in Claude Desktop eintragen:

```json
{
  "printix": {
    "url": "http://<home-assistant-ip>:8765/sse",
    "headers": {
      "Authorization": "Bearer <dein-token>"
    }
  }
}
```

## Dokumentation

Vollständige Dokumentation: [DOCS.md](printix-mcp/DOCS.md)

## Lizenz

MIT

## Autor

Marcus Nimtz — Tungsten Automation
