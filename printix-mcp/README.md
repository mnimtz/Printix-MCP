# Printix MCP Server — Home Assistant Add-on

**Version 3.9.2** · Multi-Tenant MCP Server for the Printix Cloud Print API

A Home Assistant Add-on that connects AI assistants (Claude, ChatGPT and others) to the Printix Cloud Print API using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). Manage printers, users, print jobs, and generate detailed reports — all through natural language in your AI chat.

---

## Features

### 🖨️ Printix Management via AI Chat

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

### 📊 Reports & Automation (since v3.0.0)

Create, manage and schedule print reporting directly in the browser — no AI chat required:

- **18 Report Presets** based on the official Printix PowerBI template (v2025.4) — **all 18 immediately executable**
- **17 SQL query types**: print stats, trends, cost, top users/printers, anomalies, printer history, device readings, job history, queue stats, user/copy/scan details, workstations, tree meter, service desk
- **Output formats**: HTML (email body), CSV, JSON, PDF, XLSX
- **Scheduled delivery**: daily, weekly, monthly — configured entirely in the browser
- **Email delivery** via Resend API (configurable per tenant)
- **Dynamic date ranges**: last week, last month, last quarter, last year, custom range

### 🎭 Demo Data Generator (since v3.5.0)

Generate realistic Printix print data directly in your Azure SQL database for demos, PoCs and testing:

- **Preset selection**: Small Business, Mid-Market, or Enterprise — pre-fills all parameters
- **Custom configuration**: define users, printers, queues, time period and site names manually
- **Progress overlay**: animated real-time progress during generation
- **Session management**: view, compare and delete individual demo datasets
- **Reporting Views**: `setup_schema()` creates a `reporting.*` schema with 8 SQL views (`v_tracking_data`, `v_jobs`, `v_users`, `v_printers`, `v_networks`, `v_jobs_scan`, `v_jobs_copy`, `v_jobs_copy_details`) — demo data is automatically included in all BI reports

### 🌐 Multi-Tenant Architecture

Each user manages their own Printix OAuth2 credentials independently. Multiple tenants can use the same server instance simultaneously. All credentials are stored encrypted in a local SQLite database.

### 🌍 12 UI Languages

The web interface is fully localized in 12 languages:

| Code | Language |
|------|----------|
| `de` | German (Hochdeutsch) |
| `en` | English |
| `fr` | French |
| `it` | Italian |
| `es` | Spanish |
| `nl` | Dutch |
| `no` | Norwegian |
| `sv` | Swedish |
| `bar` | Bavarian dialect |
| `hessisch` | Hessian dialect |
| `oesterreichisch` | Austrian German |
| `schwiizerdütsch` | Swiss German |

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

1. Open **Settings → Add-ons → Add-on Store** in Home Assistant
2. Click the three-dot menu (⋮) → **Repositories**
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

---

## Web Interface

| URL | Description |
|-----|-------------|
| `http://<your-ha-ip>:8080/` | Home / redirect to dashboard |
| `http://<your-ha-ip>:8080/register` | Register a new account |
| `http://<your-ha-ip>:8080/dashboard` | User dashboard |
| `http://<your-ha-ip>:8080/settings` | Manage credentials & preferences |
| `http://<your-ha-ip>:8080/reports` | Reports & automation |
| `http://<your-ha-ip>:8080/tenant/printers` | Printer list (live from Printix API) |
| `http://<your-ha-ip>:8080/tenant/queues` | Print queue list |
| `http://<your-ha-ip>:8080/tenant/users` | User list |
| `http://<your-ha-ip>:8080/tenant/demo` | Demo data generator |
| `http://<your-ha-ip>:8080/help` | MCP connection guide |

---

## Connecting an AI Assistant

### MCP Endpoint (HTTP Streaming)

```
http://<your-ha-ip>:8765/mcp
```

### SSE Endpoint (for legacy clients)

```
http://<your-ha-ip>:8765/sse
```

### Authentication

Use the **Bearer Token** from the web interface under **Settings**. Pass it as an HTTP header:

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

---

## Available MCP Tools

The add-on exposes the following tools to connected AI assistants:

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
| `printix_run_report_now` | Run a saved report template |
| `printix_status` | Check add-on status |

---

## Ports

| Port | Protocol | Description |
|------|----------|-------------|
| `8080` | HTTP | Web management interface |
| `8765` | HTTP | MCP server (SSE + HTTP streaming) |

Both ports must be accessible from your AI assistant. If using Claude Desktop on the same network, the Home Assistant IP is sufficient. For cloud-based AI services, expose the ports through a reverse proxy with TLS.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Home Assistant Add-on               │
│                                                     │
│  ┌──────────────────┐    ┌──────────────────────┐  │
│  │   Web UI :8080   │    │   MCP Server :8765   │  │
│  │  (FastAPI/Jinja2)│    │  (SSE + HTTP stream) │  │
│  └────────┬─────────┘    └──────────┬───────────┘  │
│           │                          │               │
│           └──────────┬───────────────┘               │
│                      ▼                               │
│            ┌─────────────────┐                       │
│            │   SQLite DB     │                       │
│            │  /data/*.db     │                       │
│            └────────┬────────┘                       │
└─────────────────────┼───────────────────────────────┘
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
   Printix API    Azure SQL    Resend API
   (Print/Card/  (Reports &   (Email
    Workstation)  Demo Data)   Delivery)
```

**Data flow:**
- Web UI and MCP server share the same SQLite database for credentials and configuration
- Printix API calls use OAuth2 (client credentials flow) — tokens are cached and refreshed automatically
- Azure SQL is optional and only required for Reports and Demo Data features
- All user data is stored locally on your Home Assistant instance

---

## Configuration

The add-on is configured entirely through the web interface. No manual YAML configuration is required. Credentials are stored encrypted in `/data/printix_multi.db`.

For advanced scenarios, the following environment variables can be set via the HA add-on options:

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_PORT` | `8080` | Web UI port |
| `MCP_PORT` | `8765` | MCP server port |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a full version history.

**v3.9.2** — Bugfix release: demo-data schema mismatch (`dbo.*` → `demo.*`), missing `/tenant/demo/rollback` route, XHR-loaded session list (30+ s → <100 ms first load), `query_off_hours_print` rewrite against real `dbo.jobs` schema, report-engine XSS fix (`|safe` removal + autoescape), OAuth client_id binding (RFC 6749 §4.1.3 defense-in-depth)  
**v3.9.1** — Security & performance hardening: OAuth redirect-URI whitelist (RFC 6749), XSS fixes in consent + admin/demo/reports templates, open-redirect fix in `/lang`, indexed bearer-token lookup (O(N) → O(1)), dead-code cleanup  
**v3.9.0** — Admin audit trail, feedback/feature-request ticket system, `audit_log` & `off_hours_print` reports  
**v3.8.1** — Hour × weekday heatmap report, `sensitive_documents` SQL fix  
**v3.8.0** — Sensitive-documents compliance report, demo-data improvements  
**v3.7.0** — Report Designer Stufe 2: 11 new query types, all 18 presets available, demo generation fix  
**v3.6.0** — Report Designer Stufe 1: CSS charts, XLSX/PDF output, report preview  
**v3.5.1** — Schema fix (demo.* vs dbo.*), rollback-all button, batch_size 2000  
**v3.5.0** — Demo Data Generator, reporting SQL views, full i18n for all demo UI  
**v3.0.0** — Reports & automation, 18 presets, browser-based management  

---

## License

MIT License — © 2026 [Marcus Nimtz](https://github.com/mnimtz) / Tungsten Automation
