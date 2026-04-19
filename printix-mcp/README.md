# Printix MCP Server — Home Assistant Add-on

**Version 5.18.10** · Multi-Tenant MCP Server for the Printix Cloud Print API

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

### Karten & Codes — Card Lab (since v5.0.0)

A dedicated tool for managing, transforming and locally mapping RFID/badge card values:

- **Card Lab** — enter raw card values, apply transformation profiles, preview results and optionally save as local mapping
- **Local Card Mappings** — store card ID → local value mappings per tenant, independent of Printix cloud state
- **Transformation Profiles** — define reusable reader profiles (vendor, model, mode, rules) for HEX↔Decimal, byte-reversal, prefix/suffix stripping and more
- **Built-in Profiles** — preconfigured profiles for common reader types (HID, FeliCa, Mifare, etc.)
- **Search & Filter** — full-text search across all stored card mappings
- **Sync Import** — import card data from Printix users into local mappings
- **Accessible via** the "🃏 Karten & Codes" menu entry

### Cards UX Refresh (since v5.3.10)

- **Clear split of responsibilities** — `Benutzer & Karten` stays the simple workflow, while `Karten & Codes` is the advanced workspace
- **Profile now visible and actionable** — built-in profiles can be applied directly, and copied into editable custom profiles
- **Custom profile management** — add, edit and delete your own reader/transformation profiles in the UI
- **User detail integration** — profiles are now also available when adding a card under `Benutzer & Karten`
- **Safer add-card flow** — when a profile is selected, the server recomputes the final value from the raw input before sending it to Printix
- **Reader-oriented built-ins** — added profile templates based on the project notes and Excel workflows for YSoft/Konica, Elatec, RFIDeas and Baltech
- **Richer local card evidence** — local SQLite mappings now persist preview data such as working value, HEX/Decimal derivations and the Printix secret for exact user/card context

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

**v5.10.0** — Deep object views for printers and queues plus new Sites, Networks and SNMP infrastructure registers
**v5.9.10** — True left/right alignment for compact Printix sidebar rows
**v5.9.9** — Slightly wider Printix sidebar with cleaner label and badge alignment
**v5.9.8** — Compact Printix sidebar, clearer translated status labels and Logs reordered after Capture
**v5.9.7** — Missing `python-dateutil` dependency fixed for dashboard reporting/forecast loading
**v5.9.6** — Printix overview landing page, descriptive sidebar labels and overview-first register entry
**v5.9.5** — Shared left-side navigation shell for the Printix workspace and cleaner subsection layout
**v5.9.4** — Employee role preparation plus Partner Portal visibility and role-based user management
**v5.9.3** — Fleet shortcut translation fix for the Clientless / Zero Trust Package Builder card
**v5.9.2** — Full backup and restore for local add-on state, including encryption key and demo data
**v5.9.1** — Session middleware hotfix for the invitation activation flow
**v5.9.0** — User invitation flow with localized emails, temporary passwords and invitation acceptance tracking
**v5.8.5** — Adaptive dashboard scaling for large and short desktop viewports, denser landing-page fit
**v5.8.4** — Dashboard tile translation fix for additional languages
**v5.8.3** — Dashboard tile balance and compact environmental tile layout
**v5.8.2** — Ricoh package builder repair, ZIP structure preservation, branding cleanup to Printix Management Console
**v5.8.1** — Full dashboard and cards translation pass, plus template i18n cleanup for non-DE locales
**v5.7.1** — Wider i18n coverage across cards, reports, capture and navigation polish
**v5.5.0** — Landing page tiles, broader responsive UI refresh, cleaner mobile layout foundation
**v5.3.12** — User card browser in detail view, reduced scrolling, clearer card actions
**v5.3.11** — Built-in profile detail browser, reduced sidebar scrolling, more modern master-detail layout
**v5.3.10** — Cards UX refresh, profile management UI, profile-aware add-card hardening, richer reader profile library, guided profile editor fields, improved local card mapping storage and grouped profile discoverability
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
### UI Refresh & Landing Page (since v5.5.0)

- **Modern landing page** — after login, users land on a colorful tile-based home screen with direct short links to the most important features
- **Feature tiles for daily work** — `Drucker`, `Queues`, `Workstations`, `Benutzer & Karten`, `Demo-Daten`, `Karten & Codes`, `Reports`, `Clientless / Zero Trust Builder`, `Fleet Monitor`, `Capture-Store` and `Logs`
- **Stronger responsive foundation** — global layout, cards and table wrappers now behave more robustly on mobile and small displays
- **Cleaner user card experience** — user cards and built-in profile browsing use focused master-detail layouts instead of long scrolling stacks
