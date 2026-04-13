# Printix MCP Server — Home Assistant Add-on

**Version 4.6.10** · Multi-Tenant MCP Server for the Printix Cloud Print API

A Home Assistant Add-on that connects AI assistants (Claude, ChatGPT and others) to the Printix Cloud Print API using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). Manage printers, users, print jobs, and generate detailed reports — all through natural language in your AI chat.

---

## Features

### Printix Management via AI Chat

Control your Printix environment directly from any MCP-compatible AI assistant:

- **Printers** — list printers, check status, view details
- **Print Jobs** — list, delete, reassign jobs to different owners
- **Users** — list users, create guest users, manage ID cards
- **Groups** — create, update, delete user groups
- **Networks & Sites** — manage Printix networks and site configurations
- **Workstations** — list connected workstations
- **ID Cards** — register cards, search by card number, delete cards
- **SNMP Configurations** — create and manage SNMP configs
- **Print Submission** — submit print jobs programmatically

### Reports & Automation (since v3.0.0)

Create, manage and schedule print reporting directly in the browser — no AI chat required:

- **18 Report Presets** based on the official Printix PowerBI template (v2025.4) — all 18 immediately executable
- **17 SQL query types**: print stats, trends, cost, top users/printers, anomalies, printer history, device readings, job history, queue stats, user/copy/scan details, workstations, tree meter, service desk
- **AI Report Designer** (since v4.2.0) — design report themes, chart types, layouts, and preview via MCP tools
- **Output formats**: HTML (email body), CSV, JSON, PDF, XLSX
- **Scheduled delivery**: daily, weekly, monthly — configured entirely in the browser
- **Email delivery** via Resend API (configurable per tenant)
- **Event notifications** — automatic alerts for new printers, queues, guest users (via polling)
- **Dynamic date ranges**: last week, last month, last quarter, last year, custom range

### Microsoft Entra ID SSO (since v4.1.0)

Single Sign-On via Microsoft accounts for all users:

- **One-click auto-setup** (v4.3.0) — Admin clicks a button, enters a code at `microsoft.com/devicelogin`, and the SSO app is created automatically via Microsoft Graph API. No Azure Portal or CLI needed.
- **Multi-tenant** — one app registration, login for users from any Entra tenant
- **Auto-linking** — existing users with matching email are automatically linked on first Entra login
- **Auto-approve** — optionally auto-approve new Entra users (configurable)

### Demo Data Generator (since v3.5.0)

Generate realistic Printix print data directly in your Azure SQL database for demos, PoCs and testing:

- **Preset selection**: Small Business, Mid-Market, or Enterprise — pre-fills all parameters
- **Custom configuration**: define users, printers, queues, time period and site names manually
- **Progress overlay**: animated real-time progress during generation
- **Session management**: view, compare and delete individual demo datasets
- **Reporting Views**: `setup_schema()` creates a `reporting.*` schema with 8 SQL views — demo data is automatically included in all BI reports

### Printix Capture — Scan-to-Cloud Webhooks (since v4.5.0)

Receive scanned documents from Printix Capture and route them to external systems:

- **Webhook endpoint** — receives `FileDeliveryJobReady` events from Printix Capture
- **HMAC-SHA256 signature verification** (v4.6.7) — cryptographic authentication using the exact Printix Capture Connector API protocol: `StringToSign = "{RequestId}.{Timestamp}.{method}.{RequestPath}.{Body}"`
- **Plugin system** — extensible architecture for document processing
- **Paperless-ngx plugin** — automatic document upload with tags, correspondents, and document types
- **Standalone Capture Server** (optional) — dedicated port 8775, or use the MCP port
- **Capture profiles** — per-profile configuration with secret keys, plugin selection, and settings
- **Multi-secret key rotation** — zero-downtime key rotation with comma-separated signatures
- **Comprehensive diagnostic logging** — full signature analysis when verification fails

### Multi-Tenant Architecture

Each user manages their own Printix OAuth2 credentials independently. Multiple tenants can use the same server instance simultaneously. All credentials are stored encrypted (Fernet) in a local SQLite database. Full tenant isolation — no user can see data from another user.

### 14 UI Languages

The web interface is fully localized in 14 languages:

| Code | Language | | Code | Language |
|------|----------|-|------|----------|
| `de` | Deutsch (Hochdeutsch) | | `no` | Norsk |
| `en` | English | | `sv` | Svenska |
| `fr` | Francais | | `bar` | Boarisch (Bavarian) |
| `it` | Italiano | | `hessisch` | Hessisch |
| `es` | Espanol | | `oesterreichisch` | Oesterreichisch |
| `nl` | Nederlands | | `schwiizerduetsch` | Schwiizerdueuetsch |
| `cockney` | Cockney (UK) | | `us_south` | Southern US |

---

## Requirements

- **Home Assistant** (any recent version)
- **Printix Cloud account** with API access
- **Printix OAuth2 credentials** — Tenant ID, Client ID, Client Secret (Print API)
- **Optional**: Printix Card API credentials (for card management)
- **Optional**: Azure SQL / SQL Server (for Reports and Demo Data)
- **Optional**: [Resend](https://resend.com) API key (for scheduled email delivery)

---

## Installation

### Via Home Assistant Add-on Store

1. Open **Settings > Add-ons > Add-on Store** in Home Assistant
2. Click the three-dot menu > **Repositories**
3. Add the repository URL: `https://github.com/mnimtz/Printix-MCP`
4. Find **Printix MCP Server** in the list and click **Install**
5. Start the add-on
6. Click **Open Web UI** or navigate to `http://<your-ha-ip>:8080`

### First-Time Setup

1. Open the web interface at `http://<your-ha-ip>:8080`
2. Click **Register** and create your admin account
3. Go to **Settings** and enter your Printix OAuth2 credentials
4. Copy your **MCP Bearer Token** from the Settings page
5. Connect your AI assistant using the MCP endpoint (see below)

### Entra ID SSO Setup (optional)

1. Go to **Admin > Settings**
2. Enable **Entra-Login**
3. Click **"Sign in with Microsoft & create app"** — the one-click auto-setup handles everything
4. Alternatively: use the Azure CLI script or manual Azure Portal setup

---

## Connecting an AI Assistant

### MCP Endpoint (HTTP Streaming — for claude.ai)

```
http://<your-ha-ip>:8765/mcp
```

### SSE Endpoint (for ChatGPT / legacy clients)

```
http://<your-ha-ip>:8765/sse
```

### Authentication

Use the **Bearer Token** from the web interface under **Settings**:

```
Authorization: Bearer <your-token>
```

### Claude (claude.ai / Claude Desktop)

In Claude's MCP settings, add a new server:

```json
{
  "name": "Printix",
  "url": "http://<your-ha-ip>:8765/mcp",
  "headers": {
    "Authorization": "Bearer <your-token>"
  }
}
```

Once connected, you can ask Claude things like:
- *"List all printers at the main office"*
- *"Show me the top 5 users by print volume this month"*
- *"Generate a demo dataset for a mid-market company"*
- *"Run the monthly cost analysis report and send it to my email"*
- *"Design a report with a dark blue theme and donut charts"*

---

## Web Interface

| URL | Description |
|-----|-------------|
| `/` | Home / redirect to dashboard |
| `/register` | Register a new account |
| `/login` | Login (local + Entra SSO) |
| `/dashboard` | User dashboard |
| `/settings` | Manage credentials & preferences |
| `/reports` | Reports & automation |
| `/tenant/printers` | Printer list (live from Printix API) |
| `/tenant/queues` | Print queue list |
| `/tenant/users` | User list |
| `/tenant/demo` | Demo data generator |
| `/help` | MCP connection guide |
| `/admin` | Admin panel (user management) |
| `/admin/settings` | Server settings (Entra SSO, Public URL) |
| `/admin/logs` | Server logs |
| `/feedback` | Feedback & feature requests |

---

## Available MCP Tools

The add-on exposes the following tools to connected AI assistants:

### Printix Management
| Tool | Description |
|------|-------------|
| `printix_list_printers` | List all printers |
| `printix_get_printer` | Get printer details |
| `printix_list_jobs` | List print jobs |
| `printix_get_job` | Get job details |
| `printix_delete_job` | Delete a print job |
| `printix_change_job_owner` | Reassign a job to a different user |
| `printix_list_users` | List all users |
| `printix_get_user` | Get user details |
| `printix_create_user` | Create a guest user |
| `printix_delete_user` | Delete a user |
| `printix_list_cards` | List ID cards |
| `printix_register_card` | Register a new ID card |
| `printix_delete_card` | Delete an ID card |
| `printix_search_card` | Search cards by number |
| `printix_generate_id_code` | Generate an ID code |
| `printix_list_groups` | List user groups |
| `printix_get_group` | Get group details |
| `printix_create_group` | Create a group |
| `printix_delete_group` | Delete a group |
| `printix_list_networks` | List Printix networks |
| `printix_list_sites` | List sites |
| `printix_list_workstations` | List workstations |
| `printix_list_snmp_configs` | List SNMP configurations |

### Reports & Queries
| Tool | Description |
|------|-------------|
| `printix_query_print_stats` | Query print statistics |
| `printix_query_top_printers` | Top printers by volume |
| `printix_query_top_users` | Top users by volume |
| `printix_query_trend` | Print volume trend |
| `printix_query_cost_report` | Cost analysis |
| `printix_query_anomalies` | Anomaly detection |
| `printix_query_printer_history` | Printer job history over time |
| `printix_query_device_readings` | Device activity & usage readings |
| `printix_query_job_history` | Full job list, paginated & filterable |
| `printix_query_queue_stats` | Paper format, color & duplex distribution |
| `printix_query_user_detail` | Per-user print detail over time |
| `printix_query_user_copy_detail` | Per-user copy detail |
| `printix_query_user_scan_detail` | Per-user scan detail |
| `printix_query_workstation_overview` | All workstations with print volume |
| `printix_query_workstation_detail` | Single workstation history |
| `printix_query_tree_meter` | Duplex savings in trees (sustainability) |
| `printix_query_service_desk` | Failed/cancelled jobs for IT service desk |
| `printix_query_any` | Run any custom SQL query (v4.2.0) |
| `printix_run_report_now` | Run a saved report template |

### Report Designer (since v4.2.0)
| Tool | Description |
|------|-------------|
| `printix_list_design_options` | List available themes, chart types, fonts |
| `printix_preview_report` | Preview a report with custom design settings |
| `printix_save_report_template` | Save/update a report template with full layout |

### System
| Tool | Description |
|------|-------------|
| `printix_status` | Check add-on status |

---

## Ports

| Port | Protocol | Description |
|------|----------|-------------|
| `8080` | HTTP | Web management interface |
| `8765` | HTTP | MCP server (SSE + HTTP streaming) |
| `8775` | HTTP | Capture webhook server (optional, when `capture_enabled=true`) |

Ports 8080 and 8765 are always active. Port 8775 is only active when `capture_enabled=true`. Capture webhooks also work through the MCP port (8765) — the dedicated Capture server on 8775 is optional.

For cloud-based AI services, expose the MCP port through a reverse proxy with TLS. **Important**: When using a reverse proxy for Capture webhooks, ensure `X-Printix-*` custom headers are forwarded (not stripped).

---

## Architecture

```
+------------------------------------------------------------------+
|                    Home Assistant Add-on                          |
|                                                                  |
|  +------------------+ +------------------+ +------------------+  |
|  |  Web UI :8080    | | MCP Server :8765 | | Capture :8775    |  |
|  | (FastAPI/Jinja2) | | (SSE+HTTP stream)| | (optional)       |  |
|  +--------+---------+ +--------+---------+ +--------+---------+  |
|           |                     |                    |            |
|           +----------+----------+----------+---------+           |
|                      v                     v                     |
|            +---------+----+  +---+-------+---+--------+         |
|            |   SQLite DB  |  | Entra ID  | Plugin Sys |         |
|            |  /data/*.db  |  |   (SSO)   | (Paperless)|         |
|            +------+-------+  +-----------+---+--------+         |
+--------------------+----------------------------+----+-----------+
                     |                            |    |
         +-----------+-----------+                |    |
         v           v           v                v    v
  Printix API    Azure SQL    Resend API    Microsoft  Paperless-ngx
  (Print/Card/  (Reports &   (Email        Graph API  (Document
   Capture)      Demo Data)   Delivery)    (SSO)       Upload)
```

**Data flow:**
- Web UI, MCP server, and Capture server share the same SQLite database
- Printix API calls use OAuth2 (client credentials flow) — tokens are cached and refreshed automatically
- Printix Capture webhooks are authenticated via HMAC-SHA256/512 signatures
- Capture plugins (e.g. Paperless-ngx) process documents from webhook events
- Azure SQL is optional and only required for Reports and Demo Data features
- Entra ID SSO uses OAuth2 Authorization Code Flow for user login
- Device Code Flow + Graph API for automatic app registration
- All user data is stored locally on your Home Assistant instance

---

## Configuration

The add-on is configured entirely through the web interface. No manual YAML configuration is required. Credentials are stored encrypted in `/data/printix_multi.db`.

Add-on options (via HA UI):

| Option | Default | Description |
|--------|---------|-------------|
| `mcp_port` | `8765` | MCP server port |
| `web_port` | `8080` | Web UI port (external mapping) |
| `public_url` | | Public URL for MCP endpoint (e.g. via Cloudflare Tunnel) |
| `capture_enabled` | `false` | Enable separate Capture webhook server on port 8775 |
| `capture_public_url` | | Public URL for Capture webhooks (e.g. `https://capture.example.com`) |
| `log_level` | `info` | Logging verbosity (debug/info/warning/error/critical) |

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a full version history.

**v4.6.10** — Workstation Reports dynamic schema detection, plugin subfolder architecture
**v4.6.7** — Printix Capture signature verification fixed (exact 5-component StringToSign formula)
**v4.6.6** — Plugin registry fix for standalone Capture Server
**v4.6.0** — Capture architecture redesign (`capture_enabled` bool, fixed port 8775)
**v4.5.0** — Printix Capture webhooks, Paperless-ngx plugin, capture profiles
**v4.3.1** — Entra callback redirect fix, Cockney + US Southern dialects (14 languages)
**v4.3.0** — Device Code Flow: true one-click Entra auto-setup
**v4.2.0** — AI Report Designer tools (list_design_options, preview_report, query_any)
**v4.1.0** — Entra ID (Azure AD) SSO login
**v4.0.0** — Bugfix release: demo-data schema, XSS fix, OAuth binding
**v3.9.0** — Admin audit trail, feedback/feature-request ticket system
**v3.5.0** — Demo Data Generator, reporting SQL views
**v3.0.0** — Reports & automation, 18 presets, browser-based management

---

## License

MIT License — 2026 [Marcus Nimtz](https://github.com/mnimtz) / Tungsten Automation
