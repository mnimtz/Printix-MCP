# Printix MCP Server — Home Assistant Add-on

**Version 6.7.118** · Multi-Tenant MCP Server + Cloud Print Gateway + Desktop & Mobile Clients for the Printix API

A Home Assistant Add-on that connects AI assistants (Claude, ChatGPT and others) to the Printix API using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io), **plus** a native Cloud Print Gateway (IPP/IPPS), native **Windows** and **macOS** desktop clients, and an **iOS MobilePrint** app with NFC card registration. Manage printers, users, print jobs, delegations, scan-to-cloud and generate detailed reports — all through natural language in your AI chat, the browser, the OS "Send to" menu, or straight from your phone.

---

## Features

### AI Integration

- **100+ MCP tools** covering printers, queues, users, groups, sites, networks, workstations, ID cards, SNMP configs, print jobs, delegations, capture profiles, report presets and fleet health
- **Dual transport** — Streamable HTTP (`/mcp`) for claude.ai connectors + SSE (`/sse`) for ChatGPT
- **OAuth 2.0 Authorization Code Flow** (claude.ai + ChatGPT) with per-tenant isolation
- **Report designer tools** — let the AI compose, preview and schedule reports for you

### Cloud Print Gateway

- **IPP/IPPS listener** (port 621) — native print endpoint for Windows, macOS and Linux; no driver install
- **TLS termination in-process** — uses `/ssl/fullchain.pem` and `/ssl/privkey.pem` from the Let's-Encrypt or DuckDNS add-on
- **Job pipeline** — PCL/PostScript → PDF via Ghostscript, optional colour → B/W, page-count extraction
- **Async fire-and-forget submission** (v6.7.43) — 202 Accepted returned immediately, Printix submit runs as background task; bypasses Cloudflare's 100 s origin timeout (HTTP 524)
- **Identity mapping** — resolves the IPP `requesting-user-name` against cached Printix users, falls back to employee parent-tenant
- **Printix Secure-Print forwarding** — 5-stage submit (convert → submit → blob upload → completeUpload → changeOwner) with full job tracking in the UI

### Employee Self-Service Portal

Each tenant can invite employees who log in with their own credentials (or Entra SSO) and get a dedicated portal:

- **Dashboard** — welcome, last jobs, status of delegations
- **My Jobs** — personal cloud-print job history, with per-job status and errors surfaced from the async pipeline
- **Upload** — drag-and-drop web upload, goes through the same conversion + Secure-Print pipeline as the desktop client
- **Delegation** — add/remove delegates (other employees of the same tenant) who can release your jobs at the printer
- **Cloud Print** (admin/user only) — queue + target configuration for the tenant
- **Send to** (admin/user only) — one-click download of the Windows desktop client (x64 / ARM64), with SmartScreen hints for the unsigned MSI
- **Employees** (admin/user only) — invite, list and manage employees of the tenant
- **Setup Guide** (admin/user only) — step-by-step OAuth2 + Entra ID + IPPS setup
- **14 UI languages** — DE, EN, FR, IT, ES, NL, NO, SV plus regional dialects (Bavarian, Hessian, Cockney, US-South)

### Desktop Client — "Printix Send" for Windows

- **.NET 8 WPF single-file EXE** packaged as **per-user MSI** (x64 + ARM64) — no admin rights required
- **Windows "Send to" integration** — right-click any file → *Send to* → *Printix Send* (one entry per target, auto-synced after login)
- **Permanent tray icon + home window** (v6.7.48) — quick status, re-login, view last jobs
- **Headless send** (v6.7.47) — no GUI flash when sending from the SendTo menu
- **Microsoft Entra SSO** via Device Code Flow + local username/password fallback
- **Targets loaded live** from `/desktop/targets` — Secure Print self, delegate print, capture profiles
- **DPAPI-encrypted token** stored per Windows user in `%LocalAppData%\PrintixSend\token.bin`
- **Auto-launch after install** (v6.7.50) — new installations open the config/login dialog automatically
- **Long-running uploads** (v6.7.50) — `HttpClient.Timeout = 15 min` so LibreOffice coldstart doesn't kill the request

### Desktop Client — "Printix Send" for macOS

- **Swift-native Menu-Bar-App + CLI**, packaged as universal **DMG** (Apple Silicon + Intel) — no admin rights required
- **Finder Quick Actions integration** — right-click any file → *Quick Actions* → *Printix Send — &lt;target&gt;* (one entry per target, auto-synced after login)
- **Menu-bar icon (🖨)** — login status, target list, re-sync, configuration, logout
- **Headless send** via `printix-send-cli` invoked from the `.workflow` bundles — no GUI flash
- **Microsoft Entra SSO** via Device Code Flow + local username/password fallback
- **Targets loaded live** from `/desktop/targets` — Secure Print self, delegate print, capture profiles
- **Keychain-stored token** (`de.printix.send` / `bearer-token`, `kSecAttrAccessibleAfterFirstUnlock`)
- **Long-running uploads** — `URLSession` with 15 min request / 30 min resource timeout
- **macOS 13 Ventura** or newer

### Mobile Client — "Printix MobilePrint" for iOS

- **Native SwiftUI iOS app** (iOS 16+) for iPhone and iPad
- **NFC ID-card registration** — tap a HID / Mifare / FeliCa / DESFire badge onto the phone to enrol it for a Printix user; raw UID is passed through the Card Transformer so the encoded value matches the reader at the MFP
- **QR-code onboarding** — scan a QR from the admin portal to configure server URL + bearer token in one step, no manual setup
- **Share Extension** — send any file (PDF, Office, photos) from any iOS app directly into the Secure-Print pipeline via *Share → Printix*
- **Targets loaded live** from `/desktop/targets` — Secure Print self, delegate print recipients, capture profiles
- **Microsoft Entra SSO** via Device Code Flow + local credential fallback
- **Keychain-stored token** with Face ID / Touch ID unlock
- **Localized** for DE, EN, FR, IT, ES, NL, NO, SV

### Secure-Print Delegation

- **Per-tenant `delegations` table** — each employee can nominate one or more delegates within the same tenant
- **Delegate Print targets** automatically appear in the Windows, macOS and iOS "Send to" / target lists as *Delegate → &lt;Name&gt;*
- **Job-owner swap at submit** — the IPP/desktop pipeline submits as the actual requester, then calls `changeOwner` so the chosen delegate sees the job in their Secure-Print queue at the MFP
- **Manage from the portal** — `/my/delegation` UI to add/remove delegates with live preview
- **Audited** — every delegated submission is written to the tenant audit log with source (IPP, desktop, iOS, web-upload)

### Printix Capture — Scan-to-Cloud

- **Webhook endpoint** (`/capture/webhook`) receives `FileDeliveryJobReady` events from Printix Capture
- **HMAC-SHA256 signature verification** — `StringToSign = "{RequestId}.{Timestamp}.{method}.{RequestPath}.{Body}"`
- **Multi-secret rotation** with zero-downtime — comma-separated signatures
- **Plugin system** — Paperless-ngx plugin ships with the add-on (auto-upload with tags, correspondents, document types); other plugins pluggable via `capture/base_plugin.py`
- **Direct desktop ingest** — the Windows client can target capture profiles directly via `POST /desktop/send` → `capture:{profile-id}`, no Azure blob round-trip
- **Capture log per profile** — every ingest (webhook or desktop) is audited

### AI Report Designer

- **18 report presets** based on the official Printix PowerBI template (v2025.4) — all executable out of the box
- **17 SQL query types** — print stats, trends, cost, top users/printers, anomalies, printer history, device readings, job history, queue stats, user/copy/scan details, workstations, tree meter, service desk
- **Output formats** — HTML (email body), CSV, JSON, PDF, XLSX
- **Scheduled delivery** — daily, weekly, monthly via Resend API
- **Dynamic date ranges** — last week/month/quarter/year + custom
- **Demo data generator** — realistic multi-tenant print data for PoCs

### Platform

- **Multi-tenant** — each user manages their own Printix OAuth2 credentials; full isolation
- **Microsoft Entra ID SSO** — one-click auto-setup via Device Code Flow, no Azure Portal needed
- **Invitation flow** — localized emails, temporary passwords, activation tracking
- **Backup & restore** — full add-on state export/import including encryption key; scheduled auto-backups to Printix tenant storage
- **Fleet Health Monitor** — SNMP + API polling surfaces offline devices, low toner, paper jams and stuck jobs; exposed to the AI via `printix_printer_health_report` and `printix_jobs_stuck`
- **Advanced card transformer + Card Lab** — HEX↔Decimal, byte-reversal, prefix/suffix strip, per-reader profiles (HID, FeliCa, Mifare, YSoft/Konica, Elatec, RFIDeas, Baltech)
- **Package Builder** — per-tenant clientless / Zero-Trust MSI packages for Ricoh rollouts
- **Fernet-encrypted credentials** in SQLite, session-protected web UI, health-check endpoint
- **Configurable logging** — `debug` / `info` / `warning` / `error` / `critical`

---

## Quick Start

1. **Install the add-on** — add `https://github.com/mnimtz/Printix-MCP` as a repository in the Home Assistant Add-on Store
2. **Configure** — open the Web UI at `http://<HA-IP>:8080`, register, enter your Printix OAuth2 credentials (or run the Entra ID auto-setup)
3. **Connect your AI** — add the MCP endpoint `http://<HA-IP>:8765/mcp` (claude.ai) or `/sse` (ChatGPT) with your bearer token
4. **Cloud Print** *(optional)* — expose port 621 via a Cloudflare tunnel / reverse proxy, then register `ipps://print.yourdomain.tld` on clients
5. **Desktop Client** *(optional)* — install "Printix Send" from [Releases](https://github.com/mnimtz/Printix-MCP/releases/latest):
   - **Windows** — MSI (x64 / ARM64), per-user, no admin needed. First launch opens the config/login dialog automatically.
   - **macOS** — DMG (universal, Apple Silicon + Intel). Drag to *Applications*, configure server URL, sign in. Right-click → *Quick Actions* to send.
   - **iOS** — MobilePrint from TestFlight / App Store. Scan the QR from `/my/setup-guide` to configure, then tap-to-enrol NFC cards and send files from any app via the Share Extension.
6. **Invite employees** *(optional)* — use the Employees register to send invitation emails; each employee gets their own portal and can configure delegations and delegate-print targets

---

## Ports

| Port | Purpose |
|------|---------|
| `8765` | MCP endpoint (SSE for ChatGPT + Streamable HTTP for claude.ai) |
| `8080` | Web management UI (registration + admin + employee portal) |
| `8775` | Capture webhook endpoint (optional, separate from MCP) |
| `621`  | IPP/IPPS listener for Cloud Print forwarding |

---

## Site Map — where do I find what?

The web UI at `http://<HA-IP>:8080` groups features into four functional areas. Navigation header = top-level entries; indented items live inside that page (sub-tabs, sidebars or cards).

```
🔑 /login · /register                       Public entry (+ Entra SSO one-click)

🏠 /dashboard                               Landing page with tiles — direct shortcuts
                                            to every main feature below.

🖨️ /tenant  (Printix workspace)             Everything read/written against Printix.
   ├── /tenant/printers                     Printer fleet, online/offline, SNMP, details
   ├── /tenant/queues                       Print queues per printer, detail views
   ├── /tenant/sites                        Site definitions (addresses, timezones)
   ├── /tenant/networks                     Network definitions, subnets, gateways
   ├── /tenant/snmp                         SNMP v1/v2c/v3 configs, detail editor
   ├── /tenant/users                        Users + ID cards (Card Transformer inline)
   ├── /tenant/workstations                 Connected workstations, online filter
   └── /tenant/demo                         Demo-data generator (presets, sessions)

🃏 /cards  (Card Lab)                       Advanced RFID/badge tooling, independent
                                            of Printix backend state.
   ├── Card Lab                             Enter raw values, apply profiles, preview
   ├── Local Card Mappings                  card-id → local value per tenant
   ├── Transformation Profiles              HEX/Dec, byte-reverse, strip, leading-zero
   └── Built-in Reader Profiles             HID, FeliCa, Mifare, YSoft, Elatec …

📊 /reports                                 AI Report Designer
   ├── 18 Preset templates                  Print stats, cost, top users, anomalies …
   ├── Designer (new/edit)                  Chart types, layouts, date ranges
   ├── Schedules                            Daily/weekly/monthly via Resend API
   └── Run history                          PDF / XLSX / HTML / CSV / JSON downloads

📥 /capture                                 Scan-to-Cloud webhook backend
   ├── Profiles                             HMAC-SHA256 secrets, plugin per profile
   ├── Plugins                              Paperless-ngx built-in, extensible
   ├── Capture Log                          Every webhook + desktop ingest audited
   └── Port 8775 standalone                 Optional — or use the MCP port

🧑‍💼 /my  (Employee self-service portal)      Any logged-in user + invited employees
   ├── /my                                  Dashboard (recent jobs, delegations)
   ├── /my/jobs                             Personal cloud-print job history
   ├── /my/upload                           Drag-and-drop web upload → Secure Print
   ├── /my/delegation                       Manage delegates (fellow employees)
   ├── /my/cloud-print        (admin/user)  Queue + target configuration
   ├── /my/send-to            (admin/user)  Windows desktop client download
   ├── /my/employees          (admin/user)  Invite + manage employees
   └── /my/setup-guide        (admin/user)  Step-by-step OAuth2/Entra/IPPS setup

📋 /logs                                    Structured event + request logs
⚙️ /settings                                Per-user preferences (language, email)
🗺️ /roadmap · ❓ /help                      Static reference pages

⚙️ /admin  (global admin only)              Cross-tenant operations
   ├── /admin/users                         All users across all tenants
   ├── /admin/audit                         Audit log (logins, changes, invites)
   └── /admin/settings                      Global Resend / Entra / MCP settings
```

### API & machine endpoints (no UI)

| Endpoint | Purpose |
|----------|---------|
| `:8765/mcp`            | MCP Streamable HTTP (claude.ai connector) |
| `:8765/sse`            | MCP SSE (ChatGPT connector) |
| `:8080/desktop/*`      | Desktop-client API (login, targets, send, latest-version) |
| `:8080/capture/webhook`| Printix Capture webhook (HMAC-signed) |
| `:8775/*`              | Capture webhook on dedicated port (optional) |
| `:621/ipp/print`       | IPP/IPPS print endpoint |

---

## Documentation

- [printix-mcp/README.md](printix-mcp/README.md) — server install, AI connection guides, MCP tool reference, architecture, changelog
- [printix-mcp/CHANGELOG.md](printix-mcp/CHANGELOG.md) — full per-version history
- [windows-client/README.md](windows-client/README.md) — Windows desktop client (features, build, MSI, release tags)
- [macos-client/README.md](macos-client/README.md) — macOS desktop client (menu-bar app + Quick Actions, build, DMG, release tags)
- [ios-client/README.md](ios-client/README.md) — iOS MobilePrint app (NFC card enrolment, QR onboarding, Share Extension, TestFlight)

---

## License

MIT — 2026 [Marcus Nimtz](https://github.com/mnimtz)

---

## ⚠️ Disclaimer · Rechtlicher Hinweis

**DE:** Dies ist ein **privates Entwicklungsprojekt** und steht in **keinerlei
offizieller Verbindung** zu Printix oder Tungsten Automation. Es handelt sich
ausschließlich um eine **Beispielimplementierung**, die zeigt, was mit der
öffentlichen Printix-API umgesetzt werden kann. „Printix" und zugehörige Logos
sind Marken ihrer jeweiligen Inhaber und werden hier lediglich beschreibend
verwendet. Die Nutzung dieses Projekts erfolgt **auf eigene Gefahr** — es gibt
**keine Gewährleistung, keinen Support und keine Haftung** für Datenverluste,
Ausfälle oder Schäden jeglicher Art, die aus der Verwendung entstehen.

**EN:** This is a **private development project** with **no official affiliation**
to Printix or Tungsten Automation. It is provided solely as an **example
implementation** demonstrating what can be built with the public Printix API.
"Printix" and related logos are trademarks of their respective owners and are
used here for descriptive purposes only. Use of this project is **at your own
risk** — **no warranty, no support, and no liability** is provided for data
loss, outages, or damages of any kind arising from its use.
