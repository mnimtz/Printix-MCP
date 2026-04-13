# Printix MCP Server — Home Assistant Add-on

**Version 4.6.20** · Multi-Tenant MCP Server for the Printix Cloud Print API

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

### Advanced Card Transformer in “Benutzer & Karten” (since v4.6.20)

The user detail page now includes a first advanced card-value helper for real-world RFID/card-reader quirks:

- **Decoded display for stored values** when Printix returns a Base64-based card secret
- **Raw input preview** before saving a card
- **HEX ↔ Decimal conversion**
- **Reversed-byte HEX and Decimal preview**
- **Prefix and suffix stripping**
- **Leading-zero rules** (keep, remove, force one leading zero)
- **HEX normalization** with optional even-length padding
- **Selectable final submit value** — the admin decides which transformed value is actually sent to Printix

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

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a full version history.

**v4.6.20** — Advanced card transformer UI in “Benutzer & Karten”, decoded stored card display, prefix/suffix trimming, leading-zero rules, HEX/decimal/reversed-byte previews
**v4.6.19** — Fix Tenant URL field styling (input[type=url] in global CSS)
**v4.6.18** — Tenant URL as settings field, Package Builder prefill, UI fixes
**v4.6.14** — Clientless / Zero Trust Package Builder (Ricoh)
**v4.6.13** — Workstation online/offline toggle filter
**v4.6.12** — Workstation status fix (Boolean), user pagination with card counts
**v4.6.11** — Workstations UI tab, dynamic schema detection for reports, plugin subfolder architecture

---

## License

MIT License — 2026 [Marcus Nimtz](https://github.com/mnimtz) / Tungsten Automation
