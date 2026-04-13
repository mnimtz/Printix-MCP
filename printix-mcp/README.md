# Printix MCP Server — Home Assistant Add-on

**Version 4.6.21** · Multi-Tenant MCP Server for the Printix Cloud Print API

A Home Assistant Add-on that connects AI assistants to the Printix Cloud Print API using the Model Context Protocol (MCP). Manage printers, users, cards, print jobs and reports through a browser UI or an MCP-enabled assistant.

---

## Highlights

- Multi-tenant Printix MCP server for Home Assistant
- Web management UI on port `8080`
- MCP endpoint on port `8765`
- Optional Capture endpoint on port `8775`
- Reports, demo data and Entra ID SSO support
- Advanced card tools under **Benutzer & Karten**

## Advanced card features

### v4.6.20
The user detail page includes an advanced card transformer for real-world RFID/card-reader quirks:

- decoded display for stored Base64-based card values when available
- raw input preview before saving a card
- HEX ↔ Decimal conversion
- reversed-byte HEX and Decimal preview
- prefix and suffix stripping
- leading-zero rules
- HEX normalization with optional even-length padding
- selectable final submit value

### v4.6.21
Flexible backend card lookup for plaintext vs Base64 values:

- lookup now tries multiple candidates for a card value
- plaintext input like `123456` can match a stored Base64 secret like `MTIzNDU2`
- normalized variants are also tried
- leading-zero variants are also tried
- patch is loaded for both the Web UI process and the MCP server process at startup

---

## Ports

- `8080` — Web UI
- `8765` — MCP server
- `8775` — optional Capture server

---

## Recent changelog

- **v4.6.21** — Flexible card lookup candidates for plaintext vs Base64 values, including normalized and leading-zero variants
- **v4.6.20** — Advanced card transformer UI in “Benutzer & Karten”, decoded stored card display, prefix/suffix trimming, leading-zero rules, HEX/decimal/reversed-byte previews
- **v4.6.19** — Fix Tenant URL field styling
- **v4.6.18** — Tenant URL as settings field, Package Builder prefill, UI fixes
- **v4.6.14** — Clientless / Zero Trust Package Builder (Ricoh)

---

## Notes

The add-on is configured primarily through the web interface. Credentials are stored locally in the add-on data directory. For Home Assistant updates, the add-on version is defined in `config.yaml`.
