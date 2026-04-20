# Printix MCP Server — Home Assistant Add-on

**Version 6.7.36** · Multi-Tenant MCP Server + Cloud Print Gateway for the Printix Cloud Print API

A Home Assistant Add-on that connects AI assistants (Claude, ChatGPT and others) to the Printix Cloud Print API using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io), **plus** a native Cloud Print Gateway (IPP/IPPS) and a Windows desktop client for Secure-Print workflows. Manage printers, users, print jobs, scan-to-cloud, and generate detailed reports — all through natural language in your AI chat or directly from the OS print dialog.

## Features

### AI Integration
- **45+ MCP-Tools** for Printix Cloud Print API + AI Reporting
- **Dual Transport**: Streamable HTTP (`/mcp`) for claude.ai + SSE (`/sse`) for ChatGPT
- **OAuth 2.0** Authorization Code Flow (claude.ai connectors + ChatGPT)

### Cloud Print Gateway (v6.x)
- **IPP/IPPS Server** — native print endpoint for Windows/macOS/Linux, no driver install
- **Job Pipeline** — PCL/PS → PDF conversion via Ghostscript, optional colour→B/W, page-count extraction
- **Delegation Model** — owner + delegates can release the same secure-print job
- **Employee Self-Service Portal** — per-employee print tokens, upload, job history, light reports
- **Printix Secure-Print forwarding** — cloud gateway submits jobs into Printix with correct owner

### Desktop Client (v6.7+)
- **Printix Send for Windows** — .NET 8 WPF app with "Send To" integration (x64 + ARM64 MSI)
- **Entra ID Device-Code Login** + local username/password fallback
- **Batch upload** to printers or Capture workflows
- See [`windows-client/`](windows-client/)

### Reporting & Capture
- **Printix Capture** (v4.5+) — Scan-to-Cloud webhooks with HMAC-SHA256 signature verification and plugin system (e.g. Paperless-ngx)
- **AI Report Designer** (v4.2+) — 18 report presets, 17 SQL query types, PDF/XLSX/HTML/CSV output
- **Scheduled Reports** — daily/weekly/monthly delivery via Resend API

### Platform
- **Multi-Tenant Architecture** — each user manages their own OAuth2 credentials, full tenant isolation
- **Microsoft Entra ID SSO** (v4.1+) — one-click auto-setup via Device Code Flow
- **Package Builder** — generates per-tenant installer packages for desktop rollouts
- **Demo Data Generator** — realistic print data for demos and PoCs
- **14 UI Languages** — DE, EN, FR, IT, ES, NL, NO, SV + regional dialects
- Encrypted credential storage (Fernet + SQLite)
- Configurable logging, Health-Check Endpoint

## Quick Start

1. **Install** — Add `https://github.com/mnimtz/Printix-MCP` as repository in Home Assistant Add-on Store
2. **Configure** — Open Web UI at `http://<HA-IP>:8080`, register, enter Printix OAuth2 credentials
3. **Connect AI** — Add MCP endpoint `http://<HA-IP>:8765/mcp` to your AI assistant with Bearer Token
4. **Cloud Print** (optional) — Expose IPPS port, set up `ipps://print.yourdomain.tld/ipp/print` on clients
5. **Desktop Client** (optional) — Install Printix Send MSI from [Releases](https://github.com/mnimtz/Printix-MCP/releases) for "Send To" workflow

## Documentation

- [printix-mcp/README.md](printix-mcp/README.md) — Server install, AI connection guides, MCP tool reference, architecture, changelog
- [windows-client/README.md](windows-client/README.md) — Windows desktop client (build, install, MSI)

## License

MIT — 2026 [Marcus Nimtz](https://github.com/mnimtz) / Tungsten Automation
