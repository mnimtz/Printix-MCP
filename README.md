# Printix MCP Server — Home Assistant Add-on

An MCP (Model Context Protocol) server for the Printix Cloud Print API, packaged as a Home Assistant Add-on. Connects AI assistants like **claude.ai** and **ChatGPT** to your Printix environment — enabling printer management, user administration, card operations, reporting, and more.

**Version: 2.2.0** · Multi-Tenant · EFIGS · [GitHub](https://github.com/mnimtz/Printix-MCP)

---

## Features

- **45+ MCP tools** covering the full Printix Cloud Print API
- Three API scopes: Print, Card Management, Workstation Monitoring
- **AI Reporting**: print volume, costs, top users, anomaly detection — directly from Azure SQL
- **Automated reports**: APScheduler with Resend mail delivery (daily / weekly / monthly)
- **Dual Transport**: Streamable HTTP (`/mcp`) for claude.ai + SSE (`/sse`) for ChatGPT
- **OAuth 2.0** Authorization Code Flow (compatible with claude.ai connectors and ChatGPT)
- **Multi-Tenant Web UI**: each user manages their own Printix credentials
- **EFIGS multilingual UI**: English, French, Italian, German, Spanish — auto-detected or manually switchable
- **Admin panel**: user approval, suspension, creation, password reset, server settings
- **Self-service**: users can update their own API credentials and regenerate their OAuth secret
- **Configurable Base URL** via Admin → Server Settings
- Health-Check endpoint (`/health`)
- Persistent SQLite database — survives add-on updates

---

## Architecture

The add-on runs two services side by side:

| Service | Port | Purpose |
|---------|------|---------|
| Web UI | 8080 (container) | User registration, admin panel, settings, connection guide |
| MCP Server | 8765 (container) | MCP endpoint for claude.ai and ChatGPT |

Port mapping (host side) is configurable in the add-on configuration.

---

## Installation

1. Copy the add-on folder to `/addons/printix-mcp-addon/` on your Home Assistant host.
2. In Home Assistant: **Settings → Add-ons → Add-on Store → Reload**.
3. Install **Printix MCP Server** from "Local add-ons".
4. Under **Configuration**, set `public_url` to your publicly reachable URL (e.g. via Cloudflare Tunnel).
5. Start the add-on — connection URLs appear in the log.
6. Open the Web UI (`http://<HA-IP>:<web_port>`) and register the first user (auto-approved as admin).

---

## Configuration

All Printix API credentials are managed through the **Web UI**, not the add-on configuration. The configuration file only controls server-level settings.

| Field | Description | Default |
|-------|-------------|---------|
| `mcp_port` | Internal MCP server port | `8765` |
| `web_port` | Internal Web UI port | `8080` |
| `public_url` | Publicly reachable base URL (e.g. `https://mcp.example.com`) | `""` |
| `log_level` | `debug` / `info` / `warning` / `error` / `critical` | `info` |

> **Note:** The Base URL can also be set via **Admin → Server Settings** in the Web UI. The Web UI setting takes precedence over the configuration field.

---

## First-Time Setup

1. Open the Web UI at `http://<HA-IP>:<web_port>`.
2. Click **Register** and create your user account.
3. The first registered user is automatically approved as **Administrator**.
4. Enter your Printix API credentials (Tenant ID, Client ID, Client Secret) in the registration wizard or later via **Settings**.
5. Go to **Help** in the navigation to see your personal connection guide with copy buttons.

---

## Connecting claude.ai

1. Open claude.ai → **Settings → Connectors → Add Connector**.
2. Select **MCP** as the connector type.
3. Enter the MCP URL:
   ```
   https://your-domain.com/mcp
   ```
4. Enter your **OAuth Client ID** (visible on your Dashboard and Help page).
5. Enter your **OAuth Client Secret** (visible in Settings).
6. Authorize the connection — claude.ai redirects to the OAuth consent page.

---

## Connecting ChatGPT

1. ChatGPT → **Settings → Connected Apps → Add App → Custom MCP Server**.
2. Enter the SSE URL:
   ```
   https://your-domain.com/sse
   ```
3. Enter the OAuth credentials:
   - **Client ID**: from your Dashboard
   - **Client Secret**: from Settings
   - **Auth URL**: `https://your-domain.com/oauth/authorize`
   - **Token URL**: `https://your-domain.com/oauth/token`
   - **Token auth method**: `client_secret_post`
4. Grant permission and save.

---

## Multi-Tenant User Management

Each registered user has isolated Printix credentials and their own OAuth client. The admin can:

- **Approve / suspend / delete** users
- **Create users** directly (without the self-registration wizard)
- **Reset passwords** for any user
- **Configure the server Base URL** globally

Users can:

- Update their own Printix API credentials
- Regenerate their OAuth Client Secret
- Change their password
- View their personalized connection guide (Help page)

---

## AI Reporting — Quick Start

Once SQL credentials are configured in Settings, Claude can report directly in natural language:

> "Show me the top 10 users by print cost for March, split by color and B&W."

> "Schedule that as a monthly report to controller@company.com on the 1st of each month."

Claude translates the request into SQL, returns the result, and optionally sets up an automated schedule — no SQL knowledge or BI tools required.

| Tool | Description |
|------|-------------|
| `printix_query_print_stats` | Print volume by period, user, printer, or site |
| `printix_query_cost_report` | Costs with paper/toner breakdown |
| `printix_query_top_users` | User ranking by volume or cost |
| `printix_query_top_printers` | Printer ranking by volume or cost |
| `printix_query_anomalies` | Outlier detection |
| `printix_query_trend` | Period comparison with delta percentages |
| `printix_save_report_template` | Save a report as a reusable template |
| `printix_run_report_now` | Run a template immediately and send by email |
| `printix_schedule_report` | Create an automated schedule |
| `printix_list_schedules` | View active schedules |

---

## Changelog

### v2.1.0
- Multi-tenant architecture: each user has their own Printix credentials and OAuth client
- EFIGS multilingual Web UI (EN, FR, IT, DE, ES) with auto-detection and manual switch
- Admin panel: user creation, editing, deletion, password reset
- User self-service: edit own API credentials, regenerate OAuth secret
- Help page with personalized connection guide and copy buttons
- Admin-configurable Base URL via Web UI
- SQLite database with Fernet-encrypted secrets

### v2.0.0
- Multi-Tenant foundation: SQLite DB, bcrypt passwords, ContextVar routing

### v1.14.0 (Golden Master)
- Dual Transport: Streamable HTTP + SSE
- OAuth 2.0 Authorization Code Flow
- Full Printix API coverage (45+ tools)
- AI Reporting with Azure SQL + automated mail delivery

---

## Repository

[https://github.com/mnimtz/Printix-MCP](https://github.com/mnimtz/Printix-MCP)

## License

MIT

## Author

Marcus Nimtz — Tungsten Automation
