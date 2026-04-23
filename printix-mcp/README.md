# Printix MCP Server — Home Assistant Add-on

**Version 6.7.118** · Multi-Tenant MCP Server for the Printix Cloud Print API
**Licence:** MIT · **Author:** [Marcus Nimtz](https://github.com/mnimtz) / Tungsten Automation

A Home Assistant add-on that connects any MCP-capable AI assistant (claude.ai, ChatGPT, Claude Desktop, Cursor, etc.) to the Printix Cloud Print API via the [Model Context Protocol](https://modelcontextprotocol.io). More than **100 tools** cover everything from everyday helpdesk work to deep analytics, infrastructure automation, RFID card handling, capture/scan-to-cloud routing, and IPP/IPPS cloud print forwarding.

> **Full end-user manual:** [`docs/MCP_MANUAL_EN.pdf`](docs/MCP_MANUAL_EN.pdf) · German: [`docs/MCP_MANUAL_DE.pdf`](docs/MCP_MANUAL_DE.pdf)

---

## Table of Contents

- [Highlights](#highlights)
- [Architecture & Ports](#architecture--ports)
- [Quick Start](#quick-start)
- [MCP Tool Catalogue](#mcp-tool-catalogue)
  - [1. System & Self-Diagnostics](#1-system--self-diagnostics)
  - [2. Printers, Sites & Networks](#2-printers-sites--networks)
  - [3. Print Jobs & Cloud Print](#3-print-jobs--cloud-print)
  - [4. Users, Groups & Workstations](#4-users-groups--workstations)
  - [5. Cards & Card Profiles](#5-cards--card-profiles)
  - [6. Reports & Analytics](#6-reports--analytics)
  - [7. Report Templates & Scheduling](#7-report-templates--scheduling)
  - [8. Capture / Workflow Automation](#8-capture--workflow-automation)
  - [9. Operations, Maintenance & Audit](#9-operations-maintenance--audit)
- [Web Administration UI](#web-administration-ui)
- [Configuration](#configuration)
- [Changelog](#changelog)

---

## Highlights

### AI-Driven Printix Control (MCP)

- **100+ tools** spanning printers, queues, jobs, users, cards, sites, networks, workstations, SNMP, reports, capture, and operations.
- **Natural-language access** — assistants pick the right tool from your question; no command memorisation required.
- **Aggregated 360° views** (`printix_user_360`, `printix_site_summary`, `printix_get_queue_context`, `printix_get_network_context`, `printix_get_snmp_context`) reduce multiple API round-trips into single calls.
- **Fuzzy & diagnostic helpers** such as `printix_resolve_printer`, `printix_diagnose_user`, `printix_explain_error`, and `printix_suggest_next_action`.
- **Bulk & automation tools**: `printix_bulk_import_cards`, `printix_onboard_user`, `printix_offboard_user`, `printix_quick_print`, `printix_send_to_user`.

### Reporting & Analytics

- **18 report presets** based on the official Printix PowerBI template, all immediately executable against your Azure SQL data warehouse.
- **17 SQL query types** — print stats, trends, cost, top users/printers, anomalies, printer history, device readings, job history, queue stats, workstations, tree meter, service desk, and more.
- **AI Report Designer** — design report themes, chart types, layouts, and preview through MCP tools.
- **Output formats**: HTML, CSV, JSON, PDF, XLSX.
- **Scheduled delivery** (daily / weekly / monthly) via cron, e-mail via Resend API.
- **Event notifications** for new printers, queues, guest users.
- **Dynamic date ranges**: last week/month/quarter/year or custom.

### Cards & Codes (since v5.0.0)

- **Card Lab** — enter raw RFID/badge values, apply transformation profiles, preview results, optionally save as local mapping.
- **Local Card Mappings** — per-tenant card ID → local value mappings, independent of Printix cloud state.
- **Transformation Profiles** — vendor/model/mode rules for HEX↔Decimal, byte reversal, prefix/suffix stripping, leading-zero rules, and Base64 decoding.
- **Built-in profiles** for HID, FeliCa, Mifare, YSoft/Konica, Elatec, RFIDeas, Baltech.
- **Bulk import** via CSV/JSON with profile selection and dry-run mode.
- **Profile suggestion** based on a sample UID (top-10 ranked).

### Capture — Scan-to-Cloud Webhooks (since v4.5.0)

- Receives `FileDeliveryJobReady` events from Printix Capture Connector.
- **HMAC-SHA256 signature verification** using the exact Capture Connector API protocol (`StringToSign = "{RequestId}.{Timestamp}.{method}.{RequestPath}.{Body}"`).
- **Plugin architecture** — extensible; currently ships Paperless-ngx plugin (tags, correspondents, document types).
- **Standalone capture server** (optional) on port 8775, or share the MCP port.
- **Multi-secret key rotation** for zero-downtime re-keying.

### Cloud Print Forwarding (IPP/IPPS, since v6.5.0)

- Built-in **IPP/IPPS listener** on port 621 — Printix clients can forward print jobs directly into your infrastructure.
- **TLS termination** in-listener (v6.7.0+) with automatic pickup of Let's-Encrypt / DuckDNS certificates via `/ssl`.

### Microsoft Entra ID SSO (since v4.1.0)

- **One-click auto-setup** — admin enters a device-code at `microsoft.com/devicelogin`; the SSO app is then provisioned automatically via Microsoft Graph API. No Azure Portal or CLI needed.
- **Multi-tenant** — one app registration handles sign-in from any Entra tenant.
- **Auto-linking** of existing users by matching e-mail; optional auto-approve for new Entra users.

### Employee Portal (since v6.x)

- Dedicated `/my/*` routes for end-users: upload-to-print, delegation, mobile-app onboarding, job list, setup guide.
- iOS & macOS companion clients, Windows package builder (Ricoh Zero Trust).
- Multilingual UI (DE, EN, FR) across all dashboards, tables, and dialogs.

### Demo Data Generator (since v3.5.0)

- Preset selection: Small Business, Mid-Market, Enterprise.
- Custom configuration: users, printers, queues, time period, site names.
- Progress overlay; session-level inspect, compare, delete.
- Auto-creates a `reporting.*` schema with 8 SQL views — demo data is visible to all reports.

### Multi-Tenant Architecture

- Each user manages their own OAuth2 credentials independently.
- Credentials are Fernet-encrypted at rest in a local SQLite DB.
- Full tenant isolation — no cross-tenant data leaks.
- In-memory dashboard cache (60 s TTL) + per-user `asyncio.Lock` to handle Azure SQL cold-start gracefully.

---

## Architecture & Ports

```
 ┌────────────────────────────────────────────────────────────────┐
 │              Printix MCP Server (Home Assistant Add-on)        │
 ├──────────────┬──────────────┬──────────────┬──────────────────┤
 │  Port 8765   │  Port 8080   │  Port 8775   │   Port 621       │
 │   MCP API    │   Web UI     │ Capture WH   │   IPP/IPPS       │
 ├──────────────┴──────────────┴──────────────┴──────────────────┤
 │                                                                │
 │   FastMCP (SSE + Streamable HTTP)  ◄── claude.ai / ChatGPT   │
 │   FastAPI + Jinja2 (Admin + Employee portal)                   │
 │   SQLite (Fernet-encrypted secrets) + Tenant cache             │
 │   Printix Client (Print TM, Card TM, Workstation TM, UM)       │
 │   Reporting Engine (pymssql → Azure SQL / SQL Server)          │
 │   Capture Plugin Host (HMAC-verified webhooks)                 │
 │   IPP/IPPS Listener (TLS, Printix-forwarded cloud jobs)        │
 │                                                                │
 └────────────────────────────────────────────────────────────────┘
```

| Port | Purpose |
|------|---------|
| **8765** | MCP endpoint — SSE (ChatGPT) and Streamable HTTP (claude.ai). |
| **8080** | Web administration + employee portal. |
| **8775** | Optional capture webhook endpoint (can share the MCP port). |
| **621**  | IPP/IPPS listener for Cloud Print forwarding (since v6.5.0; v6.6.0 removed LPR). |

---

## Quick Start

1. Add the repository to Home Assistant (Settings → Add-ons → ⋮ → Repositories) with URL
   `https://github.com/mnimtz/Printix-MCP`.
2. Install **Printix MCP Server** and start it.
3. Open the web UI (`http://<ha-host>:8080`), register an admin account, and add your Printix OAuth2 credentials.
4. Configure an MCP client (claude.ai, ChatGPT, Claude Desktop) with your tenant URL, e.g.
   `https://mcp.printix.cloud/mcp`.
5. Ask your assistant: *"Give me a Printix tenant summary."*

All credentials stay local; the add-on never forwards them to any third party.

---

## MCP Tool Catalogue

Every tool is callable by name from any MCP client, but in practice you simply _talk to your assistant_ and it picks the right tool. Below is the full catalogue, grouped by intent.

### 1. System & Self-Diagnostics

| Tool | Purpose |
|------|---------|
| `printix_status` | Health check: server running, tenant reachable, API versions. |
| `printix_whoami` | Current tenant + your own Printix user. |
| `printix_tenant_summary` | Compact snapshot: printers / users / sites / cards / open jobs. |
| `printix_explain_error` | Translates a Printix error code into plain language plus a fix. |
| `printix_suggest_next_action` | Suggests the next sensible step from a context string. |
| `printix_natural_query` | Maps a natural-language question to the matching reporting tool. |

**Example:** *"Is everything OK with Printix?"* → `printix_status`
*"Give me a snapshot of my Printix tenant."* → `printix_tenant_summary`

### 2. Printers, Sites & Networks

| Tool | Purpose |
|------|---------|
| `printix_list_printers` | All printers (optional search). |
| `printix_get_printer` | Printer details + capabilities. |
| `printix_resolve_printer` | Fuzzy match across name + location + vendor + site. |
| `printix_network_printers` | Printers of a network or site (4-strategy fallback). |
| `printix_get_queue_context` | Queue + printer + recent jobs in one call. |
| `printix_printer_health_report` | Online/offline/error grouping. |
| `printix_top_printers` | Top-N by volume (days / limit / metric). |
| `printix_list_sites` · `printix_get_site` | Site list / details. |
| `printix_create_site` · `printix_update_site` · `printix_delete_site` | Site management. |
| `printix_site_summary` | Site + networks + printers aggregated. |
| `printix_list_networks` · `printix_get_network` | Networks, optionally filtered by site. |
| `printix_create_network` · `printix_update_network` · `printix_delete_network` | Network management. |
| `printix_get_network_context` | Network + site + printers in one block. |
| `printix_list_snmp_configs` · `printix_get_snmp_config` | SNMP configs. |
| `printix_create_snmp_config` · `printix_delete_snmp_config` | SNMP lifecycle. |
| `printix_get_snmp_context` | SNMP config + affected printers + network. |

**Example:** *"Which Brother printers are in Düsseldorf?"* → `printix_resolve_printer("Brother Düsseldorf")`
*"Show all printers in network 9cfa4bf0."* → `printix_network_printers(network_id="9cfa4bf0")`

### 3. Print Jobs & Cloud Print

| Tool | Purpose |
|------|---------|
| `printix_list_jobs` | All jobs, optionally filtered by queue. |
| `printix_get_job` | Job details. |
| `printix_submit_job` | Submit a print job (step 1/3). |
| `printix_complete_upload` | Complete the upload + release job (step 3/3). |
| `printix_delete_job` | Cancel a job. |
| `printix_change_job_owner` | Delegate a job to another user. |
| `printix_jobs_stuck` | Jobs hanging longer than *N* minutes. |
| `printix_quick_print` | One-shot: URL + recipient → print. |
| `printix_send_to_user` | Forward a document to another user. |

**Example:** *"Send this PDF to marcus@company.com as secure print."* → `printix_quick_print(...)`
*"Which jobs have been stuck for more than 30 minutes?"* → `printix_jobs_stuck(minutes=30)`

### 4. Users, Groups & Workstations

| Tool | Purpose |
|------|---------|
| `printix_list_users` | Tenant users (pagination + role filter). |
| `printix_get_user` · `printix_find_user` | Details / fuzzy lookup. |
| `printix_user_360` | Full 360°: master data + cards + groups + workstations + recent jobs. |
| `printix_diagnose_user` | Helpdesk diagnosis: what works, what doesn't, why. |
| `printix_create_user` · `printix_delete_user` | Lifecycle. |
| `printix_generate_id_code` | New self-service ID code. |
| `printix_onboard_user` · `printix_offboard_user` | Multi-step guided flows. |
| `printix_list_admins` · `printix_permission_matrix` | Admin overview + permission matrix. |
| `printix_inactive_users` | Users with no recent print activity. |
| `printix_sso_status` | SSO mapping check for an e-mail. |
| `printix_list_groups` · `printix_get_group` · `printix_create_group` · `printix_delete_group` | Groups. |
| `printix_list_workstations` · `printix_get_workstation` | Workstation registry. |

**Example:** *"Tell me everything you know about marcus@company.com."* → `printix_user_360(query="marcus@company.com")`
*"Why can't Anna print anymore?"* → `printix_diagnose_user(email="anna@company.com")`

### 5. Cards & Card Profiles

| Tool | Purpose |
|------|---------|
| `printix_list_cards` | Cards of a specific user. |
| `printix_list_cards_by_tenant` | All cards (filter: `all`/`registered`/`orphaned`). |
| `printix_search_card` | Find by ID or card number. |
| `printix_register_card` · `printix_delete_card` | Assign / remove a card. |
| `printix_get_card_details` | Card + local mapping + owner. |
| `printix_decode_card_value` | Decode Base64 / hex / YSoft / Konica variants. |
| `printix_transform_card_value` | Run value through the transformation chain. |
| `printix_get_user_card_context` | User + all their cards + profiles. |
| `printix_list_card_profiles` · `printix_get_card_profile` | Profile catalogue. |
| `printix_search_card_mappings` | Search the local mapping DB. |
| `printix_bulk_import_cards` | CSV / JSON bulk import (profile + dry-run). |
| `printix_suggest_profile` | Top-10 profile suggestions for a sample UID. |
| `printix_card_audit` | Audit trail of all card changes for a user. |
| `printix_find_orphaned_mappings` | Local mappings without a Printix user. |

**Example:** *"What's the card with UID `04:5F:F0:02:AB:3C`?"* → `printix_decode_card_value("04:5F:F0:02:AB:3C")`
*"Import 500 cards from this CSV — dry-run first."* → `printix_bulk_import_cards(..., dry_run=True)`

### 6. Reports & Analytics

| Tool | Purpose |
|------|---------|
| `printix_reporting_status` | Reporting engine health (DB, last runs, presets). |
| `printix_query_any` | Universal: preset + filters → table. |
| `printix_query_print_stats` | Volume across arbitrary dimensions. |
| `printix_query_cost_report` | Cost per department / user. |
| `printix_query_top_users` · `printix_query_top_printers` | Top-N. |
| `printix_query_anomalies` | Outlier detection. |
| `printix_query_trend` | Trend lines over time. |
| `printix_query_audit_log` | Structured audit of the MCP server itself. |
| `printix_top_printers` · `printix_top_users` | Shortcut (days + limit + metric). |
| `printix_print_trends` | Day / week / month grouping. |
| `printix_cost_by_department` | Department cost aggregation. |
| `printix_compare_periods` | Period-A vs period-B delta KPIs. |

**Example:** *"Who printed the most last month?"* → `printix_top_users(days=30, limit=10, metric="pages")`
*"Compare the last 30 days to the 30 before."* → `printix_compare_periods(days_a=30, days_b=30)`

### 7. Report Templates & Scheduling

| Tool | Purpose |
|------|---------|
| `printix_save_report_template` | Persist a query + design. |
| `printix_list_report_templates` · `printix_get_report_template` · `printix_delete_report_template` | Template catalogue. |
| `printix_run_report_now` | One-off execution + delivery. |
| `printix_send_test_email` | SMTP verification mail. |
| `printix_schedule_report` | Cron schedule for a template. |
| `printix_list_schedules` · `printix_update_schedule` · `printix_delete_schedule` | Schedule lifecycle. |
| `printix_list_design_options` | Colour schemes, logos, layouts. |
| `printix_preview_report` | Preview PDF without delivery. |

**Example:** *"Deliver this template on the 1st of every month to mgmt@company.com."* → `printix_schedule_report(report_id=…, cron="0 8 1 * *", recipients=["mgmt@company.com"])`

### 8. Capture / Workflow Automation

| Tool | Purpose |
|------|---------|
| `printix_list_capture_profiles` | All capture profiles. |
| `printix_capture_status` | Server port, webhook base URL, plugins, profile count. |

**Example:** *"Is capture active, and which plugins are installed?"* → `printix_capture_status`

### 9. Operations, Maintenance & Audit

| Tool | Purpose |
|------|---------|
| `printix_list_backups` · `printix_create_backup` | Local config + DB backup. |
| `printix_demo_setup_schema` | Create the demo reporting schema. |
| `printix_demo_generate` | Generate synthetic demo data. |
| `printix_demo_rollback` · `printix_demo_status` | Demo-set lifecycle. |
| `printix_list_feature_requests` · `printix_get_feature_request` | Feature ticket system. |

**Example:** *"Take a backup before I change something."* → `printix_create_backup`
*"Set up a demo environment with 50 users and 500 jobs."* → `printix_demo_setup_schema` + `printix_demo_generate(users=50, jobs=500)`

---

## Web Administration UI

Port 8080 hosts a full Jinja2/FastAPI dashboard:

- **Landing page** — tile-based home screen with direct shortcuts.
- **System status** — printers, active online, month pages, jobs today (lazy-loaded via `/dashboard/data` with 60 s in-memory cache and 75 s timeout, hardened against Azure-SQL cold-start since v6.7.118).
- **Printix Management** — printers, queues, users & cards, sites, networks, workstations, SNMP, groups.
- **Printjob Management** — job list, delegation, forwarding.
- **Karten & Codes** — Card Lab, local mappings, profile editor, sync import.
- **Reports** — 18 presets, AI report designer, schedules, preview.
- **Capture Store** — plugin config, profile management, HMAC secret rotation.
- **Clientless / Zero Trust Package Builder** (Ricoh).
- **Fleet Monitor** — online/offline, utilisation, alerts.
- **Employee Portal** (`/my/*`) — upload, delegation, setup guide, jobs, mobile-app onboarding.
- **Admin Settings** — Entra SSO, demo data, backups, audit log, i18n.
- **Localised UI** — DE, EN, FR throughout.

---

## Configuration

All options live in `config.yaml` and can be edited in the HA add-on UI:

| Option | Default | Description |
|--------|---------|-------------|
| `mcp_port` | `8765` | MCP endpoint port. |
| `web_port` | `8080` | Web UI port. |
| `public_url` | `https://mcp.printix.cloud` | Externally reachable URL (shown in the UI + logs). |
| `capture_enabled` | `false` | Run Capture on its own port 8775 (otherwise shares 8765). |
| `capture_public_url` | `""` | Optional dedicated public URL for capture webhooks. |
| `ipp_port` | `621` | IPP/IPPS listener port (0 = disabled). |
| `ipps_certfile` | `/ssl/fullchain.pem` | TLS cert for IPPS (picked up from HA's SSL store). |
| `ipps_keyfile` | `/ssl/privkey.pem` | TLS private key for IPPS. |
| `log_level` | `info` | `debug` / `info` / `warning` / `error` / `critical`. |

Per-tenant settings (OAuth credentials, SQL server, mail API key, alert recipients, Entra SSO) live in the web UI. The SQLite DB + encryption key persist across updates via the `config:rw` volume.

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full history. A few recent highlights:

- **v6.7.118** — Dashboard cache + per-user lock + 75 s timeout; cures Azure-SQL cold-start dropping KPIs to zero.
- **v6.7.117** — Client-side fetch timeout + abort controller + richer console diagnostics.
- **v6.7.116** — `printix_network_printers` strategy 4 (site fallback); always returns printers when a network resolves, with honest `site_fallback` disclaimer.
- **v6.7.115** — Hotfix: missing `re` import in `server.py`; `network_printers` strategy expansion (name match + site match + diagnostics dict).
- **v6.7.114** — Fuzzy token match for `printix_resolve_printer`; diagnostics returned when no strategy matches.
- **v6.7.113** — Helpdesk polish: `decode_card_value` hex-first fallback, `capture_status` plugin registration fix, `site_summary` response normalisation.
- **v6.7.112** — `query_audit_log` regression fix (`users` has no `tenant_id` column — now joins via `tenants.user_id`).
- **v6.7.111** — Three critical claude.ai full-test fixes: `apply_profile_transform`, datetime-sort `TypeError`, empty `audit_log.tenant_id`.
- **v6.7.0** — IPPS TLS termination in the listener; `/ssl` read-only mount for Let's-Encrypt certs.
- **v6.6.0** — LPR removed; IPPS is the sole cloud-print ingress.
- **v6.5.0** — IPP/IPPS listener on port 621, user identity from IPP attributes.
- **v6.0.0** — Dashboard lazy-loading; landing page renders instantly even when Azure SQL is asleep.
- **v5.9.0** — User invitation flow, localised e-mails, invitation acceptance tracking.
- **v5.3.10** — Cards UX refresh, profile management UI, reader-oriented built-ins, richer local card evidence.
- **v5.0.0** — Cards & Codes / Card Lab; local mappings + transformation profiles.
- **v4.5.0** — Printix Capture webhooks, plugin architecture, Paperless-ngx plugin.
- **v4.3.0** — Entra SSO one-click auto-setup via Device Code + Microsoft Graph.
- **v4.2.0** — AI Report Designer, preview tools.
- **v3.5.0** — Demo Data Generator with reporting schema.
- **v3.0.0** — Reports & Automation engine: 18 presets, 17 SQL query types, scheduled delivery.

---

## Licence

MIT Licence — © 2026 [Marcus Nimtz](https://github.com/mnimtz) / Tungsten Automation.
