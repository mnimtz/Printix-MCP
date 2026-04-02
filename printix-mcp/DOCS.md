# Printix MCP Server — Dokumentation

## Übersicht

Dieser Home Assistant Add-on stellt einen MCP-Server (Model Context Protocol) für die Printix Cloud Print API bereit. Er ermöglicht AI-Assistenten wie Claude und ChatGPT die Steuerung von Printix-Ressourcen über eine gesicherte SSE-Verbindung.

## Voraussetzungen

- **Printix Tenant** mit aktiver Cloud Print API
- **Printix Premium** Lizenz (für Benutzerverwaltung)
- **API-Credentials** aus dem Printix Admin-Portal (mindestens ein Credential-Paar)

## Konfiguration

### Pflichtfelder

| Feld | Beschreibung |
|------|-------------|
| `tenant_id` | Printix Tenant-ID (UUID) |

### API-Credentials

Es gibt drei separate API-Bereiche. Jeder Bereich benötigt eigene OAuth2 Client-Credentials:

| Bereich | Client ID Feld | Client Secret Feld | Funktionen |
|---------|---------------|-------------------|------------|
| **Print API** | `print_client_id` | `print_client_secret` | Drucker, Jobs, Sites, Netzwerke, Gruppen, SNMP |
| **Card Management** | `card_client_id` | `card_client_secret` | Benutzer, Karten, ID-Codes |
| **Workstation Monitoring** | `ws_client_id` | `ws_client_secret` | Workstations |

Optional können **Shared Fallback Credentials** (`shared_client_id` / `shared_client_secret`) konfiguriert werden, die verwendet werden, wenn bereichsspezifische Credentials fehlen.

### Bearer Token

Der `bearer_token` sichert die MCP-Verbindung ab. Wenn beim ersten Start leer, wird automatisch ein sicherer Token generiert und im Log ausgegeben. Diesen Token dann in die Konfiguration eintragen.

**Verwendung in Claude/ChatGPT:**
```
Authorization: Bearer <dein-token>
```

### Log-Level

Verfügbare Stufen: `debug`, `info`, `warning`, `error`, `critical`

- `debug`: Alle API-Aufrufe inkl. Parameter
- `info`: Schreibende Operationen + Status (empfohlen)
- `warning`: Nur Warnungen und Fehler
- `error`: Nur Fehler

## Netzwerk

Der MCP-Server lauscht auf Port **8765** (konfiguriert in config.yaml). SSE-Transport über HTTP.

### Endpunkte

| Pfad | Auth | Beschreibung |
|------|------|-------------|
| `/sse` | Bearer Token | MCP SSE Endpoint |
| `/health` | Ohne | Health-Check (gibt `{"status": "ok"}` zurück) |

## Verbindung mit Claude Desktop

In der Claude Desktop App unter Settings → MCP Servers:

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

## Verbindung mit ChatGPT (Custom GPT Actions)

Beim Erstellen eines Custom GPT unter Actions:

- **Server URL:** `http://<home-assistant-ip>:8765/sse`
- **Authentication:** Bearer Token
- **Token:** Der konfigurierte Bearer Token

## Verfügbare MCP-Tools

### Drucker & Print Queues
- `printix_status` — Credential-Status prüfen
- `printix_list_printers` — Drucker auflisten
- `printix_get_printer` — Druckerdetails abrufen

### Druckaufträge
- `printix_submit_job` — Druckauftrag erstellen
- `printix_complete_upload` — Upload abschließen
- `printix_list_jobs` — Jobs auflisten
- `printix_get_job` — Job-Details
- `printix_delete_job` — Job löschen
- `printix_change_job_owner` — Job-Eigentümer ändern

### Benutzer
- `printix_list_users` — Benutzer auflisten
- `printix_get_user` — Benutzerdetails
- `printix_create_user` — Gastbenutzer erstellen
- `printix_delete_user` — Benutzer löschen
- `printix_generate_id_code` — ID-Code generieren

### Karten
- `printix_list_cards` — Karten eines Benutzers
- `printix_search_card` — Karte suchen
- `printix_register_card` — Karte registrieren
- `printix_delete_card` — Karte löschen

### Gruppen
- `printix_list_groups` — Gruppen auflisten
- `printix_get_group` — Gruppendetails
- `printix_create_group` — Gruppe erstellen
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
- `printix_update_network` — Netzwerk aktualisieren
- `printix_delete_network` — Netzwerk löschen

### Workstations
- `printix_list_workstations` — Workstations auflisten
- `printix_get_workstation` — Workstation-Details

### SNMP
- `printix_list_snmp_configs` — SNMP-Konfigurationen auflisten
- `printix_get_snmp_config` — SNMP-Details
- `printix_create_snmp_config` — SNMP-Konfiguration erstellen
- `printix_delete_snmp_config` — SNMP-Konfiguration löschen

## Bekannte Einschränkungen

- **create_group**: Erfordert ein konfiguriertes Azure AD / externes Verzeichnis im Printix Tenant. Ohne konfiguriertes Directory schlägt die Gruppenerstellung fehl.
- **Printix API Rate Limit**: 100 Requests pro Minute pro Benutzer.
- **pageSize**: Maximal 50 Einträge pro Seite.

## Fehlerbehebung

1. **401 invalid_client**: Credentials in der Konfiguration prüfen
2. **405 Method Not Allowed**: Internes Problem — bitte Issue erstellen
3. **429 Rate Limit**: Zu viele Anfragen — kurz warten und wiederholen
4. **VALIDATION_FAILED bei update_site**: `path` Parameter mitgeben (Pflichtfeld)
