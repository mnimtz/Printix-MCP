# Printix MCP Server — Home Assistant Add-on

**Version 5.8.1** · Multi-Tenant MCP Server for the Printix Cloud Print API

A Home Assistant Add-on that connects AI assistants (Claude, ChatGPT and others) to the Printix Cloud Print API using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). Manage printers, users, print jobs, and generate detailed reports — all through natural language in your AI chat.

## Features

- **45+ MCP-Tools** for Printix Cloud Print API + AI Reporting
- **Multi-Tenant Architecture** — each user manages their own OAuth2 credentials, full tenant isolation
- **Printix Capture** (v4.5+) — Scan-to-Cloud webhooks with HMAC-SHA256 signature verification and plugin system (e.g. Paperless-ngx)
- **AI Report Designer** (v4.2+) — 18 report presets, 17 SQL query types, PDF/XLSX/HTML/CSV output
- **Scheduled Reports** — daily/weekly/monthly delivery via Resend API
- **Microsoft Entra ID SSO** (v4.1+) — one-click auto-setup via Device Code Flow
- **Demo Data Generator** — realistic print data for demos and PoCs
- **Dual Transport**: Streamable HTTP (`/mcp`) for claude.ai + SSE (`/sse`) for ChatGPT
- **OAuth 2.0** Authorization Code Flow (claude.ai connectors + ChatGPT)
- **14 UI Languages** — DE, EN, FR, IT, ES, NL, NO, SV + regional dialects
- Encrypted credential storage (Fernet + SQLite)
- Configurable logging, Health-Check Endpoint

## Quick Start

1. **Install** — Add `https://github.com/mnimtz/Printix-MCP` as repository in Home Assistant Add-on Store
2. **Configure** — Open Web UI at `http://<HA-IP>:8080`, register, enter Printix OAuth2 credentials
3. **Connect** — Add MCP endpoint `http://<HA-IP>:8765/mcp` to your AI assistant with Bearer Token

## Documentation

See [printix-mcp/README.md](printix-mcp/README.md) for full documentation including:
- Installation & first-time setup
- AI assistant connection guides (Claude, ChatGPT)
- Complete MCP tool reference
- Architecture & configuration
- Changelog

## License

MIT — 2026 [Marcus Nimtz](https://github.com/mnimtz) / Tungsten Automation
