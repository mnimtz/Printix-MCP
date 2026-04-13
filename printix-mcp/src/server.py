"""
Printix MCP Server — Home Assistant Add-on v4.6.12 (Multi-Tenant)
=================================================================
Model Context Protocol server for the Printix Cloud Print API.

v2.0.0: Multi-Tenant Betrieb — alle Zugangsdaten werden per Tenant in der SQLite-DB
(/data/printix_multi.db) verwaltet. Konfiguration erfolgt über die Web-UI (Port 8080).

Env vars (aus run.sh):
  MCP_PORT        — Listen port (default: 8765)
  MCP_HOST        — Listen host (default: 0.0.0.0)
  MCP_LOG_LEVEL   — debug/info/warning/error/critical
  MCP_PUBLIC_URL  — Öffentliche URL (für OAuth Discovery)

Pro Request wird der Tenant anhand des Bearer Tokens aus der DB nachgeschlagen.
Die Tenant-Credentials werden über ContextVars weitergegeben (thread-safe).

Transports:
  POST /mcp   → Streamable HTTP (claude.ai)
  GET  /sse   → SSE Transport   (ChatGPT)
"""

import os
import sys
import json
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP
from printix_client import PrintixClient, PrintixAPIError
from auth import BearerAuthMiddleware, current_tenant
from oauth import OAuthMiddleware


# ─── Logging Setup ────────────────────────────────────────────────────────────

LOG_LEVEL = os.environ.get("MCP_LOG_LEVEL", "info").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

# Drittbibliotheken auf WARNING festhalten — auch bei DEBUG-Modus
# (MCP-intern loggt sonst komplette JSON-Payloads, urllib3 jeden TCP-Handshake)
for _noisy in (
    "mcp.server.sse",
    "mcp.server.lowlevel.server",
    "mcp.server.fastmcp.server",
    "urllib3.connectionpool",
    "httpx",
    "httpcore",
    "python_multipart",
    "python_multipart.multipart",
):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

# uvicorn.access bleibt auf INFO — wichtig für Debugging eingehender Requests
# (v4.4.9: war vorher auf WARNING unterdrückt → Webhooks unsichtbar)

logger = logging.getLogger("printix.mcp")
logger.info("Log-Level: %s", LOG_LEVEL)


# ─── Tenant-aware DB Log Handler ──────────────────────────────────────────────

class _TenantDBHandler(logging.Handler):
    """
    Leitet Log-Einträge in die tenant_logs SQLite-Tabelle weiter,
    sofern ein Tenant-Kontext (current_tenant ContextVar) aktiv ist.
    Kategorien: PRINTIX_API | SQL | AUTH | SYSTEM
    """
    _CATEGORY_MAP = {
        "printix_client": "PRINTIX_API",
        "printix.api":    "PRINTIX_API",
        "reporting":      "SQL",
        "sql":            "SQL",
        "auth":           "AUTH",
        "oauth":          "AUTH",
    }

    def emit(self, record: logging.LogRecord) -> None:
        try:
            tenant = current_tenant.get()
            if not tenant:
                return
            tid = tenant.get("id", "")
            if not tid:
                return
            name_lower = record.name.lower()
            category = "SYSTEM"
            for key, cat in self._CATEGORY_MAP.items():
                if key in name_lower:
                    category = cat
                    break
            msg = self.format(record)
            from db import add_tenant_log
            add_tenant_log(tid, record.levelname, category, msg)
        except Exception:
            pass  # Niemals den Server wegen Logging crashen


_tenant_handler = _TenantDBHandler()
_tenant_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
_tenant_handler.setLevel(logging.DEBUG)
logging.getLogger().addHandler(_tenant_handler)  # Root-Logger → alle Tenants


# ─── Setup ────────────────────────────────────────────────────────────────────
# host="0.0.0.0" deaktiviert die Auto-Aktivierung des DNS-Rebinding-Schutzes.
# FastMCP aktiviert ihn nur wenn host in ("127.0.0.1", "localhost", "::1").
# Mit "0.0.0.0" bleibt transport_security=None → keine Host-Validierung.
mcp = FastMCP("Printix", host="0.0.0.0")


def client() -> PrintixClient:
    """
    Gibt einen PrintixClient für den aktuellen Request-Tenant zurück.

    v2.0.0: Tenant-Credentials kommen aus der SQLite-DB (via current_tenant ContextVar).
    Jeder Request bekommt seinen eigenen Client mit den Credentials des anfragenden Tenants.
    """
    tenant = current_tenant.get()
    if not tenant:
        logger.error("client() aufgerufen ohne Tenant-Kontext — kein Bearer Token?")
        raise RuntimeError("Kein Tenant-Kontext. Bearer Token fehlt oder ungültig.")

    logger.debug("Client für Tenant '%s' (ID: %s)", tenant.get("name", "?"), tenant.get("id", "?"))

    return PrintixClient(
        tenant_id=tenant.get("printix_tenant_id", ""),
        print_client_id=tenant.get("print_client_id") or None,
        print_client_secret=tenant.get("print_client_secret") or None,
        card_client_id=tenant.get("card_client_id") or None,
        card_client_secret=tenant.get("card_client_secret") or None,
        ws_client_id=tenant.get("ws_client_id") or None,
        ws_client_secret=tenant.get("ws_client_secret") or None,
        shared_client_id=tenant.get("shared_client_id") or None,
        shared_client_secret=tenant.get("shared_client_secret") or None,
    )


def _ok(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _err(e: PrintixAPIError) -> str:
    logger.error("API-Fehler %d: %s (ErrorID: %s)", e.status_code, e.message, e.error_id)
    return json.dumps({
        "error": True,
        "status_code": e.status_code,
        "message": e.message,
        "error_id": e.error_id,
    }, ensure_ascii=False, indent=2)


# ─── Status / Info ────────────────────────────────────────────────────────────

@mcp.tool()
def printix_status() -> str:
    """
    Zeigt, welche Credential-Bereiche konfiguriert sind und die Tenant-ID.
    Gut zum Testen ob der MCP-Server korrekt konfiguriert ist.
    """
    try:
        result = client().get_credential_status()
        logger.info("Status abgefragt: %s", result)
        return _ok(result)
    except Exception as e:
        logger.error("Status-Fehler: %s", e)
        return _ok({"error": str(e)})


# ─── Drucker / Print Queues ───────────────────────────────────────────────────

@mcp.tool()
def printix_list_printers(search: str = "", page: int = 0, size: int = 50) -> str:
    """
    Listet alle Drucker-Queues (Print Queues) des Tenants.

    WICHTIG – Datenstruktur der Antwort:
    Jedes Item in 'printers' ist ein Printer-Queue-Paar.
    Ein physischer Drucker kann mehrere Queues haben.

    - Physische Drucker ermitteln: Nach printer_id deduplizieren.
      Die printer_id steht in _links.self.href als:
      /printers/{printer_id}/queues/{queue_id}
      Felder pro Drucker: name (Modell), vendor, location, connectionStatus,
      printerSignId (Kurzcode), serialNo.

    - Print Queues anzeigen: Jedes Item direkt als Queue verwenden.
      Queue-Name = name (z.B. "HP-M577 (Printix)", "Guestprint").
      Drucker-Modell = model + vendor.

    Beispiel: Bei 10 Druckern mit 19 Queues liefert die API 19 Items.
    Frage: "Zeige meine Drucker" → deduplizieren auf 10 eindeutige printer_ids.
    Frage: "Zeige meine Queues"  → alle 19 Items direkt ausgeben.

    Args:
        search: Optionaler Suchbegriff (Queue-/Druckername).
        page:   Seitennummer (0-basiert).
        size:   Einträge pro Seite (max. 100).
    """
    try:
        logger.debug("list_printers(search=%s, page=%d, size=%d)", search, page, size)
        return _ok(client().list_printers(search=search or None, page=page, size=size))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_get_printer(printer_id: str, queue_id: str) -> str:
    """
    Gibt Details und Fähigkeiten einer bestimmten Drucker-Queue zurück.
    Beide IDs findest du im _links.self.href der printix_list_printers-Ausgabe.

    Args:
        printer_id: ID des Druckers (aus _links.self.href in list_printers).
        queue_id:   ID der Drucker-Queue (aus _links.self.href in list_printers).
    """
    try:
        logger.debug("get_printer(printer_id=%s, queue_id=%s)", printer_id, queue_id)
        return _ok(client().get_printer(printer_id, queue_id))
    except PrintixAPIError as e:
        return _err(e)


# ─── Print Jobs ───────────────────────────────────────────────────────────────

@mcp.tool()
def printix_list_jobs(queue_id: str = "", page: int = 0, size: int = 50) -> str:
    """
    Listet Druckaufträge. Optionaler Filter nach Drucker-Queue.

    Args:
        queue_id: Optionale Printer Queue ID zum Filtern.
        page:     Seitennummer (0-basiert).
        size:     Einträge pro Seite.
    """
    try:
        logger.debug("list_jobs(queue_id=%s, page=%d, size=%d)", queue_id, page, size)
        return _ok(client().list_print_jobs(queue_id=queue_id or None, page=page, size=size))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_get_job(job_id: str) -> str:
    """
    Gibt Status und Details eines bestimmten Druckauftrags zurück.

    Args:
        job_id: ID des Druckauftrags.
    """
    try:
        logger.debug("get_job(job_id=%s)", job_id)
        return _ok(client().get_print_job(job_id))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_submit_job(
    printer_id: str,
    queue_id: str,
    title: str,
    user: str = "",
    pdl: str = "",
    color: Optional[bool] = None,
    duplex: str = "",
    copies: int = 0,
    paper_size: str = "",
    orientation: str = "",
    scaling: str = "",
) -> str:
    """
    Erstellt einen neuen Druckauftrag (API v1.1) in einer bestimmten Drucker-Queue.
    Gibt Upload-URL und Job-ID zurück — danach Datei hochladen und printix_complete_upload aufrufen.
    Beide IDs findest du im _links.self.href der printix_list_printers-Ausgabe.

    Args:
        printer_id:  Drucker-ID (aus _links.self.href in list_printers).
        queue_id:    Queue-ID (aus _links.self.href in list_printers).
        title:       Name des Druckauftrags (Pflicht).
        user:        Optionale E-Mail des Benutzers, dem der Auftrag zugeordnet wird.
        pdl:         Optionales Seitenformat: PCL5 | PCLXL | POSTSCRIPT | UFRII | TEXT | XPS.
        color:       True = Farbe, False = Monochrom (leer = Drucker-Standard).
        duplex:      NONE | SHORT_EDGE | LONG_EDGE.
        copies:      Anzahl Kopien (0 = Drucker-Standard).
        paper_size:  A4 | A3 | A0–A5 | B4–B5 | LETTER | LEGAL etc.
        orientation: PORTRAIT | LANDSCAPE | AUTO.
        scaling:     NOSCALE | SHRINK | FIT.
    """
    try:
        logger.info("submit_job(printer=%s, queue=%s, title=%s)", printer_id, queue_id, title)
        return _ok(client().submit_print_job(
            printer_id=printer_id,
            queue_id=queue_id,
            title=title,
            user=user or None,
            pdl=pdl or None,
            color=color,
            duplex=duplex or None,
            copies=copies if copies > 0 else None,
            paper_size=paper_size or None,
            orientation=orientation or None,
            scaling=scaling or None,
        ))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_complete_upload(job_id: str) -> str:
    """
    Signalisiert, dass der Datei-Upload abgeschlossen ist und löst den Druckvorgang aus.

    WICHTIG – Voraussetzung: Vor diesem Aufruf MUSS die Datei bereits per HTTP PUT
    zur uploadUrl hochgeladen worden sein (die uploadUrl kommt aus printix_submit_job).
    Reihenfolge: submit_job → Datei hochladen → complete_upload.

    Wird complete_upload ohne echten Datei-Upload aufgerufen, meldet der Backend-Server
    formal Erfolg, entfernt den Job aber sofort danach (leere Datei). Ein anschließender
    get_job liefert dann 404 — das ist korrektes Backend-Verhalten, kein Skill-Fehler.

    Args:
        job_id: ID des Druckauftrags (aus printix_submit_job).
    """
    try:
        logger.info("complete_upload(job_id=%s)", job_id)
        return _ok(client().complete_upload(job_id))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_delete_job(job_id: str) -> str:
    """
    Löscht einen Druckauftrag (eingereicht oder fehlgeschlagen).

    Args:
        job_id: ID des Druckauftrags.
    """
    try:
        logger.info("delete_job(job_id=%s)", job_id)
        return _ok(client().delete_print_job(job_id))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_change_job_owner(job_id: str, new_owner_email: str) -> str:
    """
    Überträgt einen Druckauftrag an einen anderen Benutzer (per E-Mail).

    Args:
        job_id:          ID des Druckauftrags.
        new_owner_email: E-Mail-Adresse des neuen Eigentümers.
    """
    try:
        logger.info("change_job_owner(job_id=%s, new_owner=%s)", job_id, new_owner_email)
        return _ok(client().change_job_owner(job_id, new_owner_email))
    except PrintixAPIError as e:
        return _err(e)


# ─── Card Management ──────────────────────────────────────────────────────────

@mcp.tool()
def printix_list_cards(user_id: str) -> str:
    """
    Listet alle Karten eines bestimmten Benutzers.
    Hinweis: Es gibt kein tenant-weites "alle Karten"-Endpoint in der Printix API.
    Karten müssen immer über einen Benutzer abgefragt werden.

    Args:
        user_id: Benutzer-ID in Printix (aus printix_list_users).
    """
    try:
        logger.debug("list_cards(user_id=%s)", user_id)
        return _ok(client().list_user_cards(user_id=user_id))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_search_card(card_id: str = "", card_number: str = "") -> str:
    """
    Ruft eine einzelne Karte per ID oder Kartennummer ab.
    Genau eines der beiden Argumente muss angegeben werden.

    Args:
        card_id:     Karten-ID in Printix.
        card_number: Physische Kartennummer (wird automatisch base64-encodiert).
    """
    try:
        logger.debug("search_card(card_id=%s, card_number=%s)", card_id, card_number or "***")
        return _ok(client().search_card(card_id=card_id or None,
                                        card_number=card_number or None))
    except (PrintixAPIError, ValueError) as e:
        return _ok({"error": str(e)})


@mcp.tool()
def printix_register_card(user_id: str, card_number: str) -> str:
    """
    Registriert (verknüpft) eine Karte mit einem Benutzer.

    Args:
        user_id:     Benutzer-ID in Printix.
        card_number: Physische Kartennummer (wird automatisch base64-encodiert).
    """
    try:
        logger.info("register_card(user_id=%s)", user_id)
        return _ok(client().register_card(user_id, card_number))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_delete_card(card_id: str) -> str:
    """
    Entfernt eine Kartenzuordnung.

    Args:
        card_id: ID der Karte in Printix.
    """
    try:
        logger.info("delete_card(card_id=%s)", card_id)
        return _ok(client().delete_card(card_id))
    except PrintixAPIError as e:
        return _err(e)


# ─── User Management ──────────────────────────────────────────────────────────

@mcp.tool()
def printix_list_users(
    role: str = "USER",
    query: str = "",
    page: int = 0,
    page_size: int = 50,
) -> str:
    """
    Listet Benutzer im Tenant.
    WICHTIG: Die API liefert standardmäßig nur GUEST_USER. Daher ist der Default hier USER.
    Für alle Nutzer: einmal mit role='USER', einmal mit role='GUEST_USER' aufrufen.
    Voraussetzung: Printix Premium + Cloud Print API guest user feature aktiviert.

    Args:
        role:      'USER' (normale Nutzer) oder 'GUEST_USER' (Gastnutzer). Default: 'USER'.
        query:     Optionaler Suchbegriff (Name oder E-Mail-Adresse).
        page:      Seitennummer (0-basiert).
        page_size: Einträge pro Seite (max. 50).
    """
    try:
        logger.debug("list_users(role=%s, query=%s, page=%d)", role, query, page)
        return _ok(client().list_users(
            role=role or None,
            query=query or None,
            page=page,
            page_size=page_size,
        ))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_get_user(user_id: str) -> str:
    """
    Gibt Details eines bestimmten Benutzers zurück.

    Args:
        user_id: Benutzer-ID in Printix.
    """
    try:
        logger.debug("get_user(user_id=%s)", user_id)
        return _ok(client().get_user(user_id))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_create_user(
    email: str,
    display_name: str,
    pin: str = "",
    password: str = "",
) -> str:
    """
    Erstellt einen Gast-Benutzerkonto.

    Args:
        email:        E-Mail-Adresse des neuen Benutzers.
        display_name: Anzeigename.
        pin:          Optionale PIN — muss GENAU 4 Ziffern sein (z.B. "4242"). Andere Längen führen zu VALIDATION_FAILED.
        password:     Optionales Passwort.
    """
    try:
        logger.info("create_user(email=%s, name=%s)", email, display_name)
        return _ok(client().create_user(
            email=email,
            display_name=display_name,
            pin=pin or None,
            password=password or None,
        ))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_delete_user(user_id: str) -> str:
    """
    Löscht einen Gast-Benutzer.

    Args:
        user_id: Benutzer-ID in Printix.
    """
    try:
        logger.info("delete_user(user_id=%s)", user_id)
        return _ok(client().delete_user(user_id))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_generate_id_code(user_id: str) -> str:
    """
    Generiert einen neuen 6-stelligen Identifikationscode für einen Benutzer.

    Args:
        user_id: Benutzer-ID in Printix.
    """
    try:
        logger.info("generate_id_code(user_id=%s)", user_id)
        return _ok(client().generate_id_code(user_id))
    except PrintixAPIError as e:
        return _err(e)


# ─── Groups ───────────────────────────────────────────────────────────────────

@mcp.tool()
def printix_list_groups(search: str = "", page: int = 0, size: int = 50) -> str:
    """
    Listet alle Gruppen im Tenant.

    Args:
        search: Optionaler Suchbegriff.
        page:   Seitennummer.
        size:   Einträge pro Seite.
    """
    try:
        logger.debug("list_groups(search=%s, page=%d, size=%d)", search, page, size)
        return _ok(client().list_groups(search=search or None, page=page, size=size))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_get_group(group_id: str) -> str:
    """
    Gibt Details einer bestimmten Gruppe zurück.

    Args:
        group_id: Gruppen-ID in Printix.
    """
    try:
        logger.debug("get_group(group_id=%s)", group_id)
        return _ok(client().get_group(group_id))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_create_group(name: str, external_id: str) -> str:
    """
    Erstellt eine neue Gruppe.
    VORAUSSETZUNG: Der Tenant muss eine konfigurierte Directory-Anbindung haben (z.B. Azure AD,
    Google Workspace). Ohne Directory schlägt der Call fehl mit:
    "Directory ID cannot be null when no directories are configured for tenant".

    Args:
        name:        Gruppenname.
        external_id: Pflicht: ID der Gruppe im externen Verzeichnis (z.B. Azure AD GUID).
    """
    try:
        logger.info("create_group(name=%s, external_id=%s)", name, external_id)
        return _ok(client().create_group(
            name=name,
            external_id=external_id,
        ))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_delete_group(group_id: str) -> str:
    """
    Löscht eine Gruppe.

    Args:
        group_id: Gruppen-ID in Printix.
    """
    try:
        logger.info("delete_group(group_id=%s)", group_id)
        return _ok(client().delete_group(group_id))
    except PrintixAPIError as e:
        return _err(e)


# ─── Workstation Monitoring ───────────────────────────────────────────────────

@mcp.tool()
def printix_list_workstations(
    search: str = "",
    site_id: str = "",
    page: int = 0,
    size: int = 50,
) -> str:
    """
    Listet Workstations (Computer mit Printix Client). Optional nach Standort oder Name filtern.

    Args:
        search:  Optionaler Suchbegriff (Hostname / Name).
        site_id: Optionale Standort-ID zum Filtern.
        page:    Seitennummer.
        size:    Einträge pro Seite.
    """
    try:
        logger.debug("list_workstations(search=%s, site_id=%s)", search, site_id)
        return _ok(client().list_workstations(
            search=search or None,
            site_id=site_id or None,
            page=page,
            size=size,
        ))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_get_workstation(workstation_id: str) -> str:
    """
    Gibt Details einer bestimmten Workstation zurück.

    Args:
        workstation_id: Workstation-ID in Printix.
    """
    try:
        logger.debug("get_workstation(workstation_id=%s)", workstation_id)
        return _ok(client().get_workstation(workstation_id))
    except PrintixAPIError as e:
        return _err(e)


# ─── Sites ────────────────────────────────────────────────────────────────────

@mcp.tool()
def printix_list_sites(search: str = "", page: int = 0, size: int = 50) -> str:
    """
    Listet alle Standorte (Sites) im Tenant.

    Args:
        search: Optionaler Suchbegriff.
        page:   Seitennummer.
        size:   Einträge pro Seite.
    """
    try:
        logger.debug("list_sites(search=%s, page=%d, size=%d)", search, page, size)
        return _ok(client().list_sites(search=search or None, page=page, size=size))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_get_site(site_id: str) -> str:
    """
    Gibt Details eines bestimmten Standorts zurück.

    Args:
        site_id: Standort-ID in Printix.
    """
    try:
        logger.debug("get_site(site_id=%s)", site_id)
        return _ok(client().get_site(site_id))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_create_site(
    name: str,
    path: str,
    admin_group_ids: str = "",
    network_ids: str = "",
) -> str:
    """
    Erstellt einen neuen Standort.
    Hinweis: path ist Pflichtfeld laut API.

    Args:
        name:            Standortname.
        path:            Pflicht: Pfad des Standorts, z.B. '/Europe/Germany/Munich'.
        admin_group_ids: Optionale kommagetrennte Liste von Admin-Gruppen-IDs.
        network_ids:     Optionale kommagetrennte Liste von Netzwerk-IDs.
    """
    try:
        logger.info("create_site(name=%s, path=%s)", name, path)
        agids = [x.strip() for x in admin_group_ids.split(",") if x.strip()] \
            if admin_group_ids else []
        nids = [x.strip() for x in network_ids.split(",") if x.strip()] \
            if network_ids else []
        return _ok(client().create_site(
            name=name,
            path=path,
            admin_group_ids=agids or None,
            network_ids=nids or None,
        ))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_update_site(
    site_id: str,
    name: str = "",
    path: str = "",
    admin_group_ids: str = "",
    network_ids: str = "",
) -> str:
    """
    Aktualisiert einen Standort.
    Hinweis: path sollte angegeben werden, da die API sonst VALIDATION_FAILED zurückgibt.
    Aktuellen path findest du mit printix_get_site.

    Args:
        site_id:         Standort-ID.
        name:            Neuer Name (leer = unverändert).
        path:            Standort-Pfad, z.B. '/Europe/Germany/Munich' (empfohlen).
        admin_group_ids: Kommagetrennte Liste von Admin-Gruppen-IDs (leer = unverändert).
        network_ids:     Kommagetrennte Liste von Netzwerk-IDs (leer = unverändert).
    """
    try:
        logger.info("update_site(site_id=%s, name=%s, path=%s)", site_id, name, path)
        agids = [x.strip() for x in admin_group_ids.split(",") if x.strip()] \
            if admin_group_ids else None
        nids = [x.strip() for x in network_ids.split(",") if x.strip()] \
            if network_ids else None
        return _ok(client().update_site(
            site_id=site_id,
            name=name or None,
            path=path or None,
            admin_group_ids=agids,
            network_ids=nids,
        ))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_delete_site(site_id: str) -> str:
    """
    Löscht einen Standort.

    Args:
        site_id: Standort-ID in Printix.
    """
    try:
        logger.info("delete_site(site_id=%s)", site_id)
        return _ok(client().delete_site(site_id))
    except PrintixAPIError as e:
        return _err(e)


# ─── Networks ─────────────────────────────────────────────────────────────────

@mcp.tool()
def printix_list_networks(site_id: str = "", page: int = 0, size: int = 50) -> str:
    """
    Listet Netzwerke, optional gefiltert nach Standort.

    Args:
        site_id: Optionale Standort-ID.
        page:    Seitennummer.
        size:    Einträge pro Seite.
    """
    try:
        logger.debug("list_networks(site_id=%s, page=%d, size=%d)", site_id, page, size)
        return _ok(client().list_networks(site_id=site_id or None, page=page, size=size))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_get_network(network_id: str) -> str:
    """
    Gibt Details eines bestimmten Netzwerks zurück.

    Args:
        network_id: Netzwerk-ID in Printix.
    """
    try:
        logger.debug("get_network(network_id=%s)", network_id)
        return _ok(client().get_network(network_id))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_create_network(
    name: str,
    home_office: bool = False,
    client_migrate_print_queues: str = "GLOBAL_SETTING",
    air_print: bool = False,
    site_id: str = "",
    gateway_mac: str = "",
    gateway_ip: str = "",
) -> str:
    """
    Erstellt ein neues Netzwerk.
    Hinweis: home_office, client_migrate_print_queues und air_print sind laut API Pflichtfelder.

    Args:
        name:                        Netzwerkname.
        home_office:                 True wenn Home-Office-Netzwerk (Standard: False).
        client_migrate_print_queues: 'GLOBAL_SETTING', 'YES' oder 'NO' (Standard: GLOBAL_SETTING).
        air_print:                   True um AirPrint zu aktivieren (Standard: False).
        site_id:                     Optionale Standort-ID.
        gateway_mac:                 Optionale Gateway MAC-Adresse.
        gateway_ip:                  Optionale Gateway IP-Adresse.
    """
    try:
        logger.info("create_network(name=%s, site_id=%s)", name, site_id)
        return _ok(client().create_network(
            name=name,
            home_office=home_office,
            client_migrate_print_queues=client_migrate_print_queues,
            air_print=air_print,
            site_id=site_id or None,
            gateway_mac=gateway_mac or None,
            gateway_ip=gateway_ip or None,
        ))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_update_network(
    network_id: str,
    name: str = "",
    subnet: str = "",
    home_office: Optional[bool] = None,
    client_migrate_print_queues: str = "",
    air_print: Optional[bool] = None,
    site_id: str = "",
) -> str:
    """
    Aktualisiert ein Netzwerk.
    Liest zuerst den aktuellen Stand aus der API und schreibt dann alle Pflichtfelder
    (homeOffice, clientMigratePrintQueues, airPrint) zusammen mit den Änderungen zurück.

    Hinweis zur Antwort: Der Update-Endpoint liefert eine schlankere Antwortstruktur als GET —
    der site-Link fehlt in der direkten Rückgabe. Die Site-Zuordnung ist korrekt gespeichert.
    Für die vollständige Ansicht danach printix_get_network aufrufen.

    Args:
        network_id:                  Netzwerk-ID.
        name:                        Neuer Name (leer = unverändert).
        subnet:                      Neues Subnetz, z.B. '192.168.1.0/24' (leer = unverändert).
        home_office:                 True/False oder leer = unverändert.
        client_migrate_print_queues: 'GLOBAL_SETTING', 'YES' oder 'NO' (leer = unverändert).
        air_print:                   True/False oder leer = unverändert.
        site_id:                     Standort-ID (leer = unverändert).
    """
    try:
        logger.info("update_network(network_id=%s, name=%s)", network_id, name)
        return _ok(client().update_network(
            network_id=network_id,
            name=name or None,
            subnet=subnet or None,
            home_office=home_office,
            client_migrate_print_queues=client_migrate_print_queues or None,
            air_print=air_print,
            site_id=site_id or None,
        ))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_delete_network(network_id: str) -> str:
    """
    Löscht ein Netzwerk.

    Args:
        network_id: Netzwerk-ID in Printix.
    """
    try:
        logger.info("delete_network(network_id=%s)", network_id)
        return _ok(client().delete_network(network_id))
    except PrintixAPIError as e:
        return _err(e)


# ─── SNMP Configurations ──────────────────────────────────────────────────────

@mcp.tool()
def printix_list_snmp_configs(page: int = 0, size: int = 50) -> str:
    """
    Listet alle SNMP-Konfigurationen für Druckerüberwachung.

    Args:
        page: Seitennummer.
        size: Einträge pro Seite.
    """
    try:
        logger.debug("list_snmp_configs(page=%d, size=%d)", page, size)
        return _ok(client().list_snmp_configs(page=page, size=size))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_get_snmp_config(config_id: str) -> str:
    """
    Gibt Details einer SNMP-Konfiguration zurück.

    Args:
        config_id: SNMP-Konfigurations-ID.
    """
    try:
        logger.debug("get_snmp_config(config_id=%s)", config_id)
        return _ok(client().get_snmp_config(config_id))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_create_snmp_config(
    name: str,
    get_community_name: str = "",
    set_community_name: str = "",
    tenant_default: Optional[bool] = None,
    security_level: str = "",
    version: str = "",
    username: str = "",
    context_name: str = "",
    authentication: str = "",
    authentication_key: str = "",
    privacy: str = "",
    privacy_key: str = "",
) -> str:
    """
    Erstellt eine neue SNMP-Konfiguration für Druckermonitoring.
    Endpunkt: POST /snmp

    Args:
        name:               Name der Konfiguration (Pflicht).
        get_community_name: SNMP Get Community Name.
        set_community_name: SNMP Set Community Name.
        tenant_default:     True wenn dies die Standard-Konfiguration des Tenants ist.
        security_level:     NO_AUTH_NO_PRIVACY | AUTH_NO_PRIVACY | AUTH_PRIVACY.
        version:            SNMP Version: V1 | V2C | V3 (Großbuchstaben).
        username:           SNMPv3 Benutzername.
        context_name:       SNMPv3 Context Name.
        authentication:     NONE | MD5 | SHA | SHA256 | SHA384 | SHA512.
        authentication_key: SNMPv3 Authentication Key.
        privacy:            NONE | DES | AES | AES192 | ASE256.
        privacy_key:        SNMPv3 Privacy Key.
    """
    try:
        logger.info("create_snmp_config(name=%s, version=%s)", name, version)
        return _ok(client().create_snmp_config(
            name=name,
            get_community_name=get_community_name or None,
            set_community_name=set_community_name or None,
            tenant_default=tenant_default,
            security_level=security_level or None,
            version=version or None,
            username=username or None,
            context_name=context_name or None,
            authentication=authentication or None,
            authentication_key=authentication_key or None,
            privacy=privacy or None,
            privacy_key=privacy_key or None,
        ))
    except PrintixAPIError as e:
        return _err(e)


@mcp.tool()
def printix_delete_snmp_config(config_id: str) -> str:
    """
    Löscht eine SNMP-Konfiguration.

    Args:
        config_id: SNMP-Konfigurations-ID.
    """
    try:
        logger.info("delete_snmp_config(config_id=%s)", config_id)
        return _ok(client().delete_snmp_config(config_id))
    except PrintixAPIError as e:
        return _err(e)


# ─── Reporting: Import ────────────────────────────────────────────────────────
# Lazy-Import: Reporting-Module sind optional — fehlen sie (z.B. pyodbc nicht
# installiert), arbeitet der MCP-Server trotzdem normal weiter.

try:
    from reporting import query_tools, template_store, report_engine, scheduler as rep_scheduler
    from reporting.mail_client import send_report as _send_report, is_configured as _mail_configured
    from reporting.sql_client  import is_configured as _sql_configured, get_tenant_id as _get_sql_tenant_id
    from reporting.log_alert_handler import register_alert_handler as _register_alert_handler
    from reporting.event_poller      import register_event_poller as _register_event_poller
    _register_alert_handler()
    _register_event_poller()
    _REPORTING_AVAILABLE = True
    logger.info("Reporting-Modul geladen")
except ImportError as _e:
    _REPORTING_AVAILABLE = False
    logger.warning("Reporting-Modul nicht verfügbar (%s) — SQL-Pakete fehlen?", _e)


def _reporting_check() -> str | None:
    """Gibt eine Fehlermeldung zurück wenn Reporting nicht verfügbar/konfiguriert ist."""
    if not _REPORTING_AVAILABLE:
        return ("Reporting-Modul nicht verfügbar. "
                "Bitte Container neu bauen — pyodbc/jinja2/apscheduler fehlen.")
    if not _sql_configured():
        return ("SQL nicht konfiguriert. "
                "Bitte sql_server, sql_database, sql_username, sql_password "
                "in den Add-on-Einstellungen ergänzen.")
    return None


# ─── Reporting: Datenabfrage-Tools ────────────────────────────────────────────

@mcp.tool()
def printix_reporting_status() -> str:
    """
    Prüft den Status des Reporting-Moduls: ODBC-Treiber, SQL-Konfiguration und Mail.

    Nützlich zur Diagnose wenn SQL-Abfragen fehlschlagen.
    Zeigt alle erkannten ODBC-Treiber, den gewählten Treiber und ob SQL + Mail konfiguriert sind.
    """
    status: dict = {"reporting_available": _REPORTING_AVAILABLE}

    if not _REPORTING_AVAILABLE:
        status["error"] = "Reporting-Modul nicht geladen — pyodbc/jinja2/apscheduler fehlen?"
        return _ok(status)

    try:
        import pyodbc
        drivers = pyodbc.drivers()
        status["odbc_drivers_found"] = drivers
    except Exception as e:
        status["odbc_drivers_found"] = []
        status["odbc_error"] = str(e)

    from reporting.sql_client import _detect_driver, is_configured as sql_configured
    from auth import current_sql_config
    status["odbc_driver_selected"] = _detect_driver()

    # SQL-Config aus Tenant-Kontext (v2.0.0 Multi-Tenant)
    sql_cfg = current_sql_config.get() or {}
    status["sql_configured"] = bool(sql_cfg.get("server") and sql_cfg.get("username"))
    status["sql_server"]     = sql_cfg.get("server", "")
    status["sql_database"]   = sql_cfg.get("database", "")
    status["sql_username"]   = sql_cfg.get("username", "")
    status["tenant_id"]      = sql_cfg.get("tenant_id", "")

    # Mail aus Tenant-Kontext
    tenant = current_tenant.get() or {}
    from reporting.mail_client import is_configured as mail_configured
    status["mail_configured"] = bool(tenant.get("mail_api_key") and tenant.get("mail_from"))
    status["mail_from"]       = tenant.get("mail_from", "")

    if not status["odbc_drivers_found"]:
        status["hint"] = (
            "Keine ODBC-Treiber registriert. "
            "Container muss mit der neuen build.yaml (Debian-Base) neu gebaut werden: "
            "HA → Add-on → Neu bauen."
        )
    elif not status["sql_configured"]:
        status["hint"] = ("SQL-Parameter fehlen. "
                          "Bitte sql_server, sql_database, sql_username und sql_password "
                          "in der Web-UI (Port 8080) für diesen Tenant eintragen.")
    else:
        status["hint"] = "Alles konfiguriert — SQL-Abfragen sollten funktionieren."

    return _ok(status)


@mcp.tool()
def printix_query_print_stats(
    start_date: str,
    end_date: str,
    group_by: str = "month",
    site_id: str = "",
    user_email: str = "",
    printer_id: str = "",
) -> str:
    """
    Druckvolumen-Statistik aus der Printix BI-Datenbank.

    Liefert Aufträge, Seiten, Farbanteil und Duplex-Quote für den gewählten Zeitraum.
    Ermöglicht Analyse nach Zeitraum, Standort, Benutzer oder Drucker.

    Args:
        start_date:  Startdatum (YYYY-MM-DD), z.B. "2025-01-01"
        end_date:    Enddatum   (YYYY-MM-DD), z.B. "2025-01-31"
        group_by:    Aggregation: day | week | month | user | printer | site (default: month)
        site_id:     Optional — Netzwerk-ID für Standort-Filter
        user_email:  Optional — E-Mail für Benutzer-Filter
        printer_id:  Optional — Drucker-ID für Drucker-Filter
    """
    err = _reporting_check()
    if err:
        return _ok({"error": err})
    try:
        rows = query_tools.query_print_stats(
            start_date=start_date, end_date=end_date, group_by=group_by,
            site_id=site_id or None, user_email=user_email or None,
            printer_id=printer_id or None,
        )
        return _ok({"rows": rows, "count": len(rows)})
    except Exception as e:
        return _ok({"error": str(e)})


@mcp.tool()
def printix_query_cost_report(
    start_date: str,
    end_date: str,
    cost_per_sheet: float = 0.01,
    cost_per_mono: float = 0.02,
    cost_per_color: float = 0.08,
    group_by: str = "month",
    site_id: str = "",
    currency: str = "€",
) -> str:
    """
    Kostenaufstellung mit Papier-, Toner- und Gesamtkosten.

    Berechnet Kosten exakt nach der Printix PowerBI-Formel:
      Papierkosten = Blätter × cost_per_sheet (Duplex = halbe Blätter)
      Tonerkosten  = Seiten × cost_per_color/mono
      Gesamt       = Papier + Toner

    Args:
        start_date:     Startdatum (YYYY-MM-DD)
        end_date:       Enddatum   (YYYY-MM-DD)
        cost_per_sheet: Kosten pro Blatt Papier (default: 0.01 €)
        cost_per_mono:  Kosten pro S/W-Seite Toner (default: 0.02 €)
        cost_per_color: Kosten pro Farbseite Toner (default: 0.08 €)
        group_by:       day | week | month | site (default: month)
        site_id:        Optional — Netzwerk-ID für Standort-Filter
        currency:       Währungssymbol für Ausgabe (default: €)
    """
    err = _reporting_check()
    if err:
        return _ok({"error": err})
    try:
        rows = query_tools.query_cost_report(
            start_date=start_date, end_date=end_date,
            cost_per_sheet=cost_per_sheet, cost_per_mono=cost_per_mono,
            cost_per_color=cost_per_color, group_by=group_by,
            site_id=site_id or None,
        )
        # Gesamtsumme berechnen
        total = {
            "total_pages":        sum(r.get("total_pages", 0) or 0 for r in rows),
            "total_cost":         round(sum(r.get("total_cost", 0) or 0 for r in rows), 2),
            "toner_cost_color":   round(sum(r.get("toner_cost_color", 0) or 0 for r in rows), 2),
            "toner_cost_bw":      round(sum(r.get("toner_cost_bw", 0) or 0 for r in rows), 2),
            "sheet_cost":         round(sum(r.get("sheet_cost", 0) or 0 for r in rows), 2),
        }
        return _ok({"rows": rows, "totals": total, "currency": currency, "count": len(rows)})
    except Exception as e:
        return _ok({"error": str(e)})


@mcp.tool()
def printix_query_top_users(
    start_date: str,
    end_date: str,
    top_n: int = 10,
    metric: str = "pages",
    cost_per_sheet: float = 0.01,
    cost_per_mono: float = 0.02,
    cost_per_color: float = 0.08,
    site_id: str = "",
) -> str:
    """
    Ranking der aktivsten Nutzer nach Druckvolumen oder Kosten.

    Args:
        start_date:     Startdatum (YYYY-MM-DD)
        end_date:       Enddatum   (YYYY-MM-DD)
        top_n:          Anzahl Nutzer im Ranking (default: 10)
        metric:         Sortierung: pages | cost | jobs | color_pages (default: pages)
        cost_per_sheet: Kosten pro Blatt (für Kostenkalkulation)
        cost_per_mono:  Kosten pro S/W-Seite
        cost_per_color: Kosten pro Farbseite
        site_id:        Optional — Netzwerk-ID für Standort-Filter
    """
    err = _reporting_check()
    if err:
        return _ok({"error": err})
    try:
        rows = query_tools.query_top_users(
            start_date=start_date, end_date=end_date,
            top_n=top_n, metric=metric,
            cost_per_sheet=cost_per_sheet, cost_per_mono=cost_per_mono,
            cost_per_color=cost_per_color, site_id=site_id or None,
        )
        return _ok({"rows": rows, "count": len(rows), "metric": metric})
    except Exception as e:
        return _ok({"error": str(e)})


@mcp.tool()
def printix_query_top_printers(
    start_date: str,
    end_date: str,
    top_n: int = 10,
    metric: str = "pages",
    cost_per_sheet: float = 0.01,
    cost_per_mono: float = 0.02,
    cost_per_color: float = 0.08,
    site_id: str = "",
) -> str:
    """
    Ranking der meistgenutzten Drucker nach Volumen oder Kosten.

    Args:
        start_date:     Startdatum (YYYY-MM-DD)
        end_date:       Enddatum   (YYYY-MM-DD)
        top_n:          Anzahl Drucker im Ranking (default: 10)
        metric:         Sortierung: pages | cost | jobs | color_pages (default: pages)
        cost_per_sheet: Kosten pro Blatt
        cost_per_mono:  Kosten pro S/W-Seite
        cost_per_color: Kosten pro Farbseite
        site_id:        Optional — Netzwerk-ID für Standort-Filter
    """
    err = _reporting_check()
    if err:
        return _ok({"error": err})
    try:
        rows = query_tools.query_top_printers(
            start_date=start_date, end_date=end_date,
            top_n=top_n, metric=metric,
            cost_per_sheet=cost_per_sheet, cost_per_mono=cost_per_mono,
            cost_per_color=cost_per_color, site_id=site_id or None,
        )
        return _ok({"rows": rows, "count": len(rows), "metric": metric})
    except Exception as e:
        return _ok({"error": str(e)})


@mcp.tool()
def printix_query_anomalies(
    start_date: str,
    end_date: str,
    threshold_multiplier: float = 2.5,
) -> str:
    """
    Anomalie-Erkennung: Tage mit ungewöhnlich hohem oder niedrigem Druckvolumen.

    Berechnet Mittelwert und Standardabweichung des täglichen Druckvolumens
    und markiert Tage die mehr als threshold_multiplier × StdAbw abweichen.

    Args:
        start_date:           Startdatum (YYYY-MM-DD)
        end_date:             Enddatum   (YYYY-MM-DD)
        threshold_multiplier: Faktor für Ausreißer-Schwelle (default: 2.5 = 2,5 × StdAbw)
    """
    err = _reporting_check()
    if err:
        return _ok({"error": err})
    try:
        rows = query_tools.query_anomalies(
            start_date=start_date, end_date=end_date,
            threshold_multiplier=threshold_multiplier,
        )
        return _ok({"anomalies": rows, "count": len(rows)})
    except Exception as e:
        return _ok({"error": str(e)})


@mcp.tool()
def printix_query_trend(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str,
    cost_per_sheet: float = 0.01,
    cost_per_mono: float = 0.02,
    cost_per_color: float = 0.08,
) -> str:
    """
    Vergleich zweier Zeiträume — z.B. aktueller Monat vs. Vormonat.

    Liefert für beide Perioden Gesamtwerte und berechnet prozentuale Veränderungen
    für Seiten, Kosten, aktive Nutzer und Auftragsvolumen.

    Args:
        period1_start: Startdatum Periode 1 (YYYY-MM-DD), z.B. letzter Monat
        period1_end:   Enddatum   Periode 1 (YYYY-MM-DD)
        period2_start: Startdatum Periode 2 (YYYY-MM-DD), z.B. aktueller Monat
        period2_end:   Enddatum   Periode 2 (YYYY-MM-DD)
        cost_per_sheet: Kosten pro Blatt
        cost_per_mono:  Kosten pro S/W-Seite
        cost_per_color: Kosten pro Farbseite
    """
    err = _reporting_check()
    if err:
        return _ok({"error": err})
    try:
        result = query_tools.query_trend(
            period1_start=period1_start, period1_end=period1_end,
            period2_start=period2_start, period2_end=period2_end,
            cost_per_sheet=cost_per_sheet, cost_per_mono=cost_per_mono,
            cost_per_color=cost_per_color,
        )
        return _ok(result)
    except Exception as e:
        return _ok({"error": str(e)})


# ─── Reporting: Template-Management ───────────────────────────────────────────

@mcp.tool()
def printix_save_report_template(
    name: str,
    query_type: str,
    query_params: str,
    recipients: str,
    mail_subject: str,
    output_formats: str = "html",
    schedule_frequency: str = "",
    schedule_day: int = 1,
    schedule_time: str = "08:00",
    company_name: str = "",
    primary_color: str = "#0078D4",
    footer_text: str = "",
    created_prompt: str = "",
    report_id: str = "",
    logo_base64: str = "",
    logo_mime: str = "image/png",
    logo_url: str = "",
    theme_id: str = "",
    chart_type: str = "",
    header_variant: str = "",
    density: str = "",
    font_family: str = "",
    currency: str = "",
    show_env_impact: str = "",
    logo_position: str = "",
) -> str:
    """
    Speichert eine vollständige Report-Definition als wiederverwendbares Template.

    Das Template enthält alle Informationen für automatische Ausführung:
    Query-Parameter, Layout, Schedule und Empfänger.
    Bei Angabe einer report_id wird ein bestehendes Template überschrieben.

    TIPP: Nutze zuerst printix_list_design_options() um verfügbare Themes,
    Chart-Typen, Fonts etc. zu sehen. Mit printix_preview_report() kannst
    du das Design testen bevor du es als Template speicherst.

    Args:
        name:               Lesbarer Name, z.B. "Monatlicher Kostenreport Controlling"
        query_type:         print_stats | cost_report | top_users | top_printers | anomalies | trend | hour_dow_heatmap
                            sowie Stufe-2-Typen: printer_history | device_readings | job_history |
                            user_activity | sensitive_documents | dept_comparison | waste_analysis |
                            color_vs_bw | duplex_analysis | paper_size | service_desk |
                            fleet_utilization | sustainability | peak_hours | cost_allocation
        query_params:       JSON-String mit Query-Parametern, z.B. '{"start_date":"last_month_start","end_date":"last_month_end","group_by":"month"}'
        recipients:         Kommagetrennte E-Mail-Adressen, z.B. "controller@firma.de,cfo@firma.de"
        mail_subject:       Betreffzeile, z.B. "Druckkosten {month} {year}"
        output_formats:     Kommagetrennte Formate: html,csv,json,pdf,xlsx (default: html)
        schedule_frequency: Leer = kein Schedule | monthly | weekly | daily
        schedule_day:       Bei monthly: Tag 1-28. Bei weekly: 0=Mo...6=So (default: 1)
        schedule_time:      Uhrzeit der Ausführung HH:MM (default: 08:00)
        company_name:       Firmenname im Report-Header
        primary_color:      Primärfarbe im Report-Design (Hex, default: #0078D4)
        footer_text:        Optionaler Fußzeilentext
        created_prompt:     Ursprüngliche Nutzeranfrage (für spätere Regenerierung)
        report_id:          Optional — vorhandene ID zum Überschreiben
        logo_base64:        Optional — Base64-Kodierung (ohne data:-Prefix) eines Logo-Bildes
                            für den Report-Header. Max. 1 MB Rohgröße. Hat Vorrang vor logo_url.
        logo_mime:          MIME-Type des Base64-Logos, z.B. image/png, image/jpeg (default: image/png)
        logo_url:           Alternativ: externe URL zu einem Logo-Bild (nur wenn logo_base64 leer)
        theme_id:           Design-Theme: corporate_blue | modern_teal | executive_slate |
                            warm_sunset | forest_green | royal_purple | minimalist_gray
                            (leer = corporate_blue). Setzt automatisch passende Farben.
        chart_type:         Bevorzugter Chart-Typ: bar | line | donut | heatmap | sparkline
                            (leer = automatische Wahl je nach Report-Typ)
        header_variant:     Header-Stil: left | center | banner (default: left)
        density:            Tabellen-Dichte: compact | normal | comfortable (default: normal)
        font_family:        Schriftart: arial | helvetica | verdana | georgia | courier (default: arial)
        currency:           Währung: EUR | USD | GBP | CHF (default: EUR)
        show_env_impact:    Umwelt-Impact-Sektion anzeigen: true | false (default: false)
        logo_position:      Logo-Position im Header: left | right | center (default: right)
    """
    if not _REPORTING_AVAILABLE:
        return _ok({"error": "Reporting-Modul nicht verfügbar."})
    import json as _json
    try:
        params = _json.loads(query_params) if isinstance(query_params, str) else query_params
    except Exception:
        return _ok({"error": f"query_params ist kein gültiges JSON: {query_params}"})

    recipient_list = [r.strip() for r in recipients.split(",") if r.strip()]
    format_list    = [f.strip() for f in output_formats.split(",") if f.strip()]

    schedule = None
    if schedule_frequency in ("monthly", "weekly", "daily"):
        schedule = {
            "frequency": schedule_frequency,
            "day":       schedule_day,
            "time":      schedule_time,
        }

    # v3.7.10: Logo-Auflösung analog zum Web-Formular (_resolve_logo).
    # Reihenfolge: Base64 hat Vorrang vor URL; 1MB-Cap; MIME-Safety.
    _lb64  = (logo_base64 or "").strip()
    _lmime = (logo_mime   or "image/png").strip() or "image/png"
    _lurl  = (logo_url    or "").strip()
    if _lb64:
        if not _lmime.startswith("image/"):
            _lmime = "image/png"
        # Base64-Größen-Cap (Rohbytes ≈ 0.75 × len(b64))
        _approx_raw = int(len(_lb64) * 0.75)
        if _approx_raw > 1024 * 1024:
            return _ok({"error": f"Logo zu groß ({_approx_raw} bytes > 1MB). Max 1 MB Rohgröße."})
        _lurl = ""  # Base64 gewinnt gegen URL
    else:
        _lb64  = ""
        _lmime = "image/png"

    layout = {
        "company_name":  company_name,
        "primary_color": primary_color,
        "footer_text":   footer_text,
        "logo_base64":   _lb64,
        "logo_mime":     _lmime,
        "logo_url":      _lurl,
    }
    # v4.2.0: Erweiterte Design-Parameter
    if theme_id:
        layout["theme_id"] = theme_id
    if chart_type:
        layout["chart_style"] = chart_type  # maps to design_presets key
    if header_variant:
        layout["header_variant"] = header_variant
    if density:
        layout["density"] = density
    if font_family:
        layout["font_family"] = font_family
    if currency:
        layout["currency"] = currency
    if show_env_impact:
        layout["show_env_impact"] = show_env_impact.lower() in ("true", "1", "yes", "ja")
    if logo_position:
        layout["logo_position"] = logo_position

    try:
        # owner_user_id aus Tenant-Kontext holen — nötig damit der Scheduler
        # später die korrekten Mail-Credentials aus der DB laden kann
        _t = current_tenant.get() or {}
        owner_user_id = _t.get("user_id", "") or _t.get("id", "")

        template = template_store.save_template(
            name=name, query_type=query_type, query_params=params,
            recipients=recipient_list, mail_subject=mail_subject,
            output_formats=format_list, layout=layout,
            schedule=schedule, created_prompt=created_prompt,
            report_id=report_id or None,
            owner_user_id=owner_user_id or None,
        )

        # Schedule registrieren wenn vorhanden
        if schedule and _REPORTING_AVAILABLE:
            rep_scheduler.schedule_report(template["report_id"], schedule)

        return _ok({
            "saved":     True,
            "report_id": template["report_id"],
            "name":      template["name"],
            "scheduled": schedule is not None,
            "next_run":  _next_run_info(template["report_id"]) if schedule else None,
        })
    except Exception as e:
        return _ok({"error": str(e)})


def _next_run_info(report_id: str) -> str | None:
    """Gibt den nächsten geplanten Ausführungszeitpunkt zurück."""
    try:
        jobs = rep_scheduler.list_scheduled_jobs()
        for j in jobs:
            if j["job_id"] == report_id:
                return j.get("next_run_utc")
    except Exception:
        pass
    return None


@mcp.tool()
def printix_list_report_templates() -> str:
    """
    Listet alle gespeicherten Report-Templates des aktuellen Benutzers.

    WICHTIG: Dieses Tool immer zuerst aufrufen wenn der Benutzer einen Report
    ausführen, versenden, löschen oder planen möchte und keine report_id bekannt ist.
    Die report_id aus der Liste dann an printix_run_report_now oder andere Tools übergeben.

    Gibt Name, Query-Typ, Empfänger, Schedule und nächste geplante Ausführung zurück.
    """
    if not _REPORTING_AVAILABLE:
        return _ok({"error": "Reporting-Modul nicht verfügbar."})
    try:
        _t = current_tenant.get() or {}
        owner_id = _t.get("user_id", "") or ""
        all_templates = template_store.list_templates()
        # Per-Tenant-Filter: nur eigene Templates anzeigen
        if owner_id:
            templates = [t for t in all_templates if t.get("owner_user_id", "") == owner_id]
        else:
            templates = all_templates
        scheduled_ids = {j["job_id"] for j in rep_scheduler.list_scheduled_jobs()}
        for t in templates:
            t["is_scheduled"] = t.get("report_id", "") in scheduled_ids
            t["next_run"] = _next_run_info(t["report_id"]) if t.get("report_id") in scheduled_ids else None
        return _ok({"templates": templates, "count": len(templates),
                    "hint": "report_id aus dieser Liste an printix_run_report_now übergeben"})
    except Exception as e:
        return _ok({"error": str(e)})


@mcp.tool()
def printix_get_report_template(report_id: str) -> str:
    """
    Ruft ein einzelnes Report-Template vollständig ab.

    Args:
        report_id: Template-ID (aus printix_list_report_templates)
    """
    if not _REPORTING_AVAILABLE:
        return _ok({"error": "Reporting-Modul nicht verfügbar."})
    try:
        template = template_store.get_template(report_id)
        if not template:
            return _ok({"error": f"Template {report_id} nicht gefunden."})
        return _ok(template)
    except Exception as e:
        return _ok({"error": str(e)})


@mcp.tool()
def printix_delete_report_template(report_id: str) -> str:
    """
    Löscht ein Report-Template und entfernt einen eventuellen Schedule.

    Args:
        report_id: Template-ID (aus printix_list_report_templates)
    """
    if not _REPORTING_AVAILABLE:
        return _ok({"error": "Reporting-Modul nicht verfügbar."})
    try:
        rep_scheduler.unschedule_report(report_id)
        deleted = template_store.delete_template(report_id)
        if not deleted:
            return _ok({"error": f"Template {report_id} nicht gefunden."})
        return _ok({"deleted": True, "report_id": report_id})
    except Exception as e:
        return _ok({"error": str(e)})


@mcp.tool()
def printix_run_report_now(report_id: str = "", report_name: str = "") -> str:
    """
    Führt ein gespeichertes Report-Template sofort aus und versendet ihn per Mail.

    Workflow wenn der Benutzer "Report X senden" oder "schick mir den Bericht" sagt:
      1. Falls report_id unbekannt: printix_list_report_templates() aufrufen
      2. Passendes Template nach Name finden
      3. Dieses Tool mit der report_id aufrufen

    Alternativ: report_name direkt angeben — es wird automatisch nach Name gesucht
    (Groß-/Kleinschreibung egal, Teilstring reicht, z.B. "Monat" findet "Monatsbericht IT").

    Args:
        report_id:   Template-ID (aus printix_list_report_templates) — bevorzugt
        report_name: Name-Suche als Alternative wenn keine ID bekannt
    """
    err = _reporting_check()
    if err:
        return _ok({"error": err})
    try:
        _t = current_tenant.get() or {}
        owner_id = _t.get("user_id", "") or ""

        # Name-basierter Lookup wenn keine ID angegeben
        if not report_id and report_name:
            all_t = template_store.list_templates()
            own_t = [t for t in all_t if not owner_id or t.get("owner_user_id","") == owner_id]
            needle = report_name.lower()
            matches = [t for t in own_t if needle in t.get("name","").lower()]
            if not matches:
                names = [t.get("name","?") for t in own_t]
                return _ok({"error": f"Kein Template mit Name '{report_name}' gefunden.",
                            "available_templates": names})
            if len(matches) > 1:
                return _ok({"error": f"Mehrere Templates passen zu '{report_name}' — bitte genauer angeben.",
                            "matches": [{"report_id": t["report_id"], "name": t["name"]} for t in matches]})
            report_id = matches[0]["report_id"]

        if not report_id:
            # Kein ID und kein Name — Templates auflisten damit der Nutzer wählen kann
            all_t = template_store.list_templates()
            own_t = [t for t in all_t if not owner_id or t.get("owner_user_id","") == owner_id]
            return _ok({"error": "Bitte report_id oder report_name angeben.",
                        "available_templates": [{"report_id": t["report_id"], "name": t["name"]} for t in own_t]})

        result = rep_scheduler.run_report_now(
            report_id,
            mail_api_key=_t.get("mail_api_key", "") or "",
            mail_from=_t.get("mail_from", "") or "",
            mail_from_name=_t.get("mail_from_name", "") or "",
        )
        return _ok(result)
    except Exception as e:
        return _ok({"error": str(e)})


# ─── Reporting: Schedule-Management ───────────────────────────────────────────


@mcp.tool()
def printix_send_test_email(recipient: str) -> str:
    """
    Sendet eine Test-E-Mail über den konfigurierten Resend-API-Key des Tenants.
    """
    if not _REPORTING_AVAILABLE:
        return _ok({"error": "Reporting-Modul nicht verfügbar."})
    from reporting.mail_client import send_alert
    _t = current_tenant.get() or {}
    api_key        = _t.get("mail_api_key", "") or ""
    mail_from      = _t.get("mail_from", "") or ""
    mail_from_name = _t.get("mail_from_name", "") or ""
    if not api_key:
        return _ok({"error": "Kein mail_api_key konfiguriert."})
    try:
        send_alert(recipients=[recipient], subject="✅ Printix MCP Test-E-Mail",
                   text_body="Test OK — Resend-Konfiguration funktioniert.",
                   api_key=api_key, mail_from=mail_from, mail_from_name=mail_from_name)
        return _ok({"sent": True, "recipient": recipient})
    except Exception as e:
        return _ok({"error": str(e)})


@mcp.tool()
def printix_schedule_report(
    report_id: str,
    frequency: str,
    day: int = 1,
    time: str = "08:00",
) -> str:
    """
    Legt einen Zeitplan für ein bestehendes Report-Template an oder aktualisiert ihn.

    Für monatliche Reports empfiehlt sich Tag 1-3 (Anfang des Folgemonats).
    Alle Zeiten in UTC.

    Args:
        report_id: Template-ID (aus printix_list_report_templates)
        frequency: monthly | weekly | daily
        day:       Bei monthly: 1-28 (Tag des Monats).
                   Bei weekly:  0=Montag … 6=Sonntag (default: 1)
        time:      Uhrzeit UTC HH:MM (default: 08:00)
    """
    if not _REPORTING_AVAILABLE:
        return _ok({"error": "Reporting-Modul nicht verfügbar."})
    if frequency not in ("monthly", "weekly", "daily"):
        return _ok({"error": "frequency muss monthly, weekly oder daily sein."})
    try:
        template = template_store.get_template(report_id)
        if not template:
            return _ok({"error": f"Template {report_id} nicht gefunden."})

        schedule = {"frequency": frequency, "day": day, "time": time}

        # Im Template speichern
        template_store.save_template(
            report_id=report_id,
            name=template["name"],
            query_type=template["query_type"],
            query_params=template["query_params"],
            recipients=template.get("recipients", []),
            mail_subject=template.get("mail_subject", ""),
            output_formats=template.get("output_formats", ["html"]),
            layout=template.get("layout"),
            schedule=schedule,
            created_prompt=template.get("created_prompt", ""),
        )

        # Im Scheduler registrieren
        rep_scheduler.schedule_report(report_id, schedule)

        return _ok({
            "scheduled":  True,
            "report_id":  report_id,
            "frequency":  frequency,
            "day":        day,
            "time_utc":   time,
            "next_run":   _next_run_info(report_id),
        })
    except Exception as e:
        return _ok({"error": str(e)})


@mcp.tool()
def printix_list_schedules() -> str:
    """
    Listet alle aktiven Report-Schedules mit nächstem Ausführungszeitpunkt.
    """
    if not _REPORTING_AVAILABLE:
        return _ok({"error": "Reporting-Modul nicht verfügbar."})
    try:
        jobs = rep_scheduler.list_scheduled_jobs()
        return _ok({"schedules": jobs, "count": len(jobs)})
    except Exception as e:
        return _ok({"error": str(e)})


@mcp.tool()
def printix_delete_schedule(report_id: str) -> str:
    """
    Entfernt den Zeitplan eines Reports (Template bleibt erhalten).

    Args:
        report_id: Template-ID deren Schedule entfernt werden soll
    """
    if not _REPORTING_AVAILABLE:
        return _ok({"error": "Reporting-Modul nicht verfügbar."})
    try:
        removed = rep_scheduler.unschedule_report(report_id)

        # Schedule im Template auf None setzen
        template = template_store.get_template(report_id)
        if template:
            template_store.save_template(
                report_id=report_id,
                name=template["name"],
                query_type=template["query_type"],
                query_params=template["query_params"],
                recipients=template.get("recipients", []),
                mail_subject=template.get("mail_subject", ""),
                output_formats=template.get("output_formats", ["html"]),
                layout=template.get("layout"),
                schedule=None,
            )

        return _ok({"removed": removed, "report_id": report_id})
    except Exception as e:
        return _ok({"error": str(e)})


@mcp.tool()
def printix_update_schedule(
    report_id: str,
    frequency: str = "",
    day: int = 0,
    time: str = "",
    recipients: str = "",
) -> str:
    """
    Ändert Timing oder Empfänger eines bestehenden Schedules.

    Nur angegebene Parameter werden geändert — alle anderen bleiben unverändert.

    Args:
        report_id:  Template-ID
        frequency:  Neu: monthly | weekly | daily (leer = unverändert)
        day:        Neu: Tag (0 = unverändert)
        time:       Neu: Uhrzeit UTC HH:MM (leer = unverändert)
        recipients: Neue kommagetrennte Empfängerliste (leer = unverändert)
    """
    if not _REPORTING_AVAILABLE:
        return _ok({"error": "Reporting-Modul nicht verfügbar."})
    try:
        template = template_store.get_template(report_id)
        if not template:
            return _ok({"error": f"Template {report_id} nicht gefunden."})

        current_schedule = template.get("schedule") or {}
        new_schedule = {
            "frequency": frequency or current_schedule.get("frequency", "monthly"),
            "day":       day       or current_schedule.get("day", 1),
            "time":      time      or current_schedule.get("time", "08:00"),
        }
        new_recipients = (
            [r.strip() for r in recipients.split(",") if r.strip()]
            if recipients else template.get("recipients", [])
        )

        template_store.save_template(
            report_id=report_id,
            name=template["name"],
            query_type=template["query_type"],
            query_params=template["query_params"],
            recipients=new_recipients,
            mail_subject=template.get("mail_subject", ""),
            output_formats=template.get("output_formats", ["html"]),
            layout=template.get("layout"),
            schedule=new_schedule,
        )
        rep_scheduler.schedule_report(report_id, new_schedule)

        return _ok({
            "updated":   True,
            "report_id": report_id,
            "schedule":  new_schedule,
            "recipients": new_recipients,
            "next_run":  _next_run_info(report_id),
        })
    except Exception as e:
        return _ok({"error": str(e)})


# ─── Reporting: Design & Preview ─────────────────────────────────────────────

@mcp.tool()
def printix_list_design_options() -> str:
    """
    Listet alle verfügbaren Design-Optionen für Report-Templates:
    Themes, Chart-Typen, Fonts, Header-Varianten, Dichte-Stufen, Währungen.

    Nutze diese Informationen beim Erstellen oder Bearbeiten von Report-Templates,
    um dem Benutzer passende Optionen vorzuschlagen.

    Beispiel-Workflow:
      1. printix_list_design_options() → zeigt alle Themes
      2. Benutzer wählt "executive_slate" als Theme
      3. printix_save_report_template(..., theme_id="executive_slate") → speichert
    """
    if not _REPORTING_AVAILABLE:
        return _ok({"error": "Reporting-Modul nicht verfügbar."})

    from reporting.design_presets import (
        THEMES, FONTS, HEADER_VARIANTS, CHART_STYLES, CURRENCIES, DEFAULT_LAYOUT,
    )

    themes = {}
    for key, t in THEMES.items():
        themes[key] = {
            "name": t["name"],
            "primary_color": t["primary_color"],
            "accent_color": t["accent_color"],
            "background_color": t["background_color"],
        }

    fonts = [{"key": f["key"], "name": f.get("name", f["key"])} for f in FONTS]

    return _ok({
        "themes": themes,
        "chart_types": [
            {"key": "auto",     "description": "Automatisch — Engine wählt basierend auf Daten"},
            {"key": "bar",      "description": "Horizontale Balkendiagramme"},
            {"key": "line",     "description": "Liniendiagramm mit Fläche (ideal für Zeitreihen)"},
            {"key": "donut",    "description": "Kreisdiagramm (ideal für Anteile/Prozent)"},
            {"key": "heatmap",  "description": "Heatmap (ideal für Stunde×Wochentag-Daten)"},
            {"key": "sparkline","description": "Mini-Trend-Linien in KPI-Karten"},
        ],
        "chart_styles": [cs["key"] for cs in CHART_STYLES],
        "fonts": fonts,
        "header_variants": [hv["key"] for hv in HEADER_VARIANTS],
        "densities": ["compact", "normal", "airy"],
        "currencies": [{"key": c["key"], "symbol": c["symbol"]} for c in CURRENCIES],
        "logo_positions": ["left", "right", "center"],
        "default_layout": DEFAULT_LAYOUT,
        "available_query_types": [
            "print_stats", "cost_report", "top_users", "top_printers",
            "anomalies", "trend", "hour_dow_heatmap",
            "printer_history", "device_readings", "job_history", "queue_stats",
            "user_detail", "user_copy_detail", "user_scan_detail",
            "workstation_overview", "workstation_detail",
            "tree_meter", "service_desk", "sensitive_documents",
            "off_hours_print", "audit_log",
        ],
    })


@mcp.tool()
def printix_preview_report(
    query_type: str,
    start_date: str = "last_month_start",
    end_date: str = "last_month_end",
    query_params_json: str = "",
    theme_id: str = "",
    primary_color: str = "",
    chart_type: str = "auto",
    company_name: str = "",
    header_variant: str = "",
    density: str = "",
    font_family: str = "",
    logo_base64: str = "",
    logo_mime: str = "image/png",
    footer_text: str = "",
    currency: str = "",
    show_env_impact: bool = False,
    output_format: str = "html",
    report_id: str = "",
) -> str:
    """
    Erzeugt eine Report-Vorschau OHNE E-Mail-Versand — ideal zum iterativen
    Design im AI-Chat. Gibt den vollständigen Report als HTML (mit eingebetteten
    SVG-Charts) oder als JSON-Datenstruktur zurück.

    Zwei Modi:
      1. Ad-hoc: query_type + Datumsbereich angeben → Daten frisch abfragen
      2. Template: report_id angeben → gespeichertes Template als Basis

    Bei Ad-hoc wird ein kompletter Report gerendert inkl. KPIs, Charts und Tabellen.

    Workflow für AI-gesteuertes Report-Design:
      1. printix_list_design_options() → verfügbare Themes etc.
      2. printix_preview_report(query_type="print_stats", theme_id="executive_slate")
         → Vorschau ansehen
      3. "Kannst du die Farbe auf Grün ändern?" → printix_preview_report(..., primary_color="#1BA17D")
      4. Zufrieden? → printix_save_report_template(...) zum Speichern

    Args:
        query_type:        Report-Typ (print_stats, cost_report, top_users, etc.)
        start_date:        Start-Datum oder Preset (last_month_start, this_year_start, etc.)
        end_date:          End-Datum oder Preset
        query_params_json: Zusätzliche Query-Parameter als JSON-String
                           z.B. '{"group_by":"month","site_id":"123"}'
        theme_id:          Theme (corporate_blue, executive_slate, dark_mode, etc.)
        primary_color:     Überschreibt die Theme-Primärfarbe (Hex, z.B. #0078D4)
        chart_type:        Bevorzugter Chart-Typ: auto | bar | line | donut | heatmap
        company_name:      Firmenname im Header
        header_variant:    left | center | banner | minimal
        density:           compact | normal | airy
        font_family:       arial | georgia | roboto | fira_code | etc.
        logo_base64:       Base64-kodiertes Logo (ohne data:-Prefix)
        logo_mime:         MIME-Type des Logos (default: image/png)
        footer_text:       Fußzeile
        currency:          EUR | USD | GBP | CHF
        show_env_impact:   Umwelt-Auswirkung anzeigen (Papier, Bäume, CO₂)
        output_format:     html (Standard, mit Charts) | json (nur Rohdaten)
        report_id:         Optional — vorhandenes Template als Basis laden
    """
    err = _reporting_check()
    if err:
        return _ok({"error": err})

    import json as _json
    from reporting.design_presets import apply_theme, normalize_layout

    # ── Layout bauen ──────────────────────────────────────────────────────────
    layout = {}

    # Template als Basis laden?
    template = None
    if report_id:
        template = template_store.get_template(report_id)
        if template:
            layout = dict(template.get("layout", {}))
            if not query_type:
                query_type = template.get("query_type", "print_stats")

    # Explizite Werte überschreiben Template-Werte
    if theme_id:
        layout = apply_theme(layout, theme_id)
    if primary_color:
        layout["primary_color"] = primary_color
    if company_name:
        layout["company_name"] = company_name
    if header_variant:
        layout["header_variant"] = header_variant
    if density:
        layout["density"] = density
    if font_family:
        layout["font_family"] = font_family
    if footer_text:
        layout["footer_text"] = footer_text
    if currency:
        layout["currency"] = currency
    if logo_base64:
        layout["logo_base64"] = logo_base64
        layout["logo_mime"] = logo_mime
    if show_env_impact:
        layout["show_env_impact"] = True
    if chart_type and chart_type != "auto":
        layout["preferred_chart_type"] = chart_type
    layout["charts_enabled"] = True

    layout = normalize_layout(layout)

    # ── Query-Parameter ───────────────────────────────────────────────────────
    params = {"start_date": start_date, "end_date": end_date}
    if query_params_json:
        try:
            extra = _json.loads(query_params_json)
            params.update(extra)
        except Exception:
            return _ok({"error": f"query_params_json ist kein gültiges JSON: {query_params_json}"})

    # Template-Parameter als Fallback
    if template and not query_params_json:
        tp = template.get("query_params", {})
        for k, v in tp.items():
            if k not in params:
                params[k] = v

    # Dynamische Datums-Presets auflösen
    from reporting.scheduler import _resolve_dynamic_dates
    params = _resolve_dynamic_dates(params)

    # ── Daten abfragen ────────────────────────────────────────────────────────
    try:
        data = query_tools.run_query(query_type=query_type, **params)
    except Exception as e:
        return _ok({"error": f"Query fehlgeschlagen: {e}", "query_type": query_type})

    period = f"{params.get('start_date', '?')} — {params.get('end_date', '?')}"

    if output_format == "json":
        return _ok({
            "query_type": query_type,
            "period": period,
            "row_count": len(data) if isinstance(data, list) else "n/a",
            "data": data,
        })

    # ── Report rendern ────────────────────────────────────────────────────────
    try:
        outputs = report_engine.generate_report(
            query_type=query_type,
            data=data,
            period=period,
            layout=layout,
            output_formats=[output_format],
            currency=layout.get("currency", "EUR"),
            query_params=params,
        )
    except Exception as e:
        return _ok({"error": f"Report-Rendering fehlgeschlagen: {e}"})

    html = outputs.get("html", outputs.get(output_format, ""))

    # Für MCP-Antwort: HTML-Größe begrenzen (sehr große Reports > 100KB)
    if len(html) > 120_000:
        html = html[:120_000] + "\n<!-- ... (gekürzt, Report zu groß für Chat) -->"

    return _ok({
        "query_type": query_type,
        "period": period,
        "row_count": len(data) if isinstance(data, list) else "n/a",
        "format": output_format,
        "html": html,
        "layout_used": {
            "theme_id": layout.get("theme_id", ""),
            "primary_color": layout.get("primary_color", ""),
            "header_variant": layout.get("header_variant", ""),
            "density": layout.get("density", ""),
            "font_family": layout.get("font_family", ""),
            "chart_type": chart_type,
            "currency": layout.get("currency", ""),
        },
        "hint": "Zufrieden? → printix_save_report_template() zum Speichern als Template.",
    })


@mcp.tool()
def printix_query_any(
    query_type: str,
    start_date: str = "last_month_start",
    end_date: str = "last_month_end",
    query_params_json: str = "",
) -> str:
    """
    Universelles Query-Tool für alle 22 Report-Typen (Stufe 1 + 2).

    Ersetzt die Notwendigkeit, für jeden Query-Typ ein eigenes MCP-Tool zu kennen.
    Gibt die Rohdaten als JSON zurück — ideal für AI-Analyse, Visualisierung
    oder als Basis für printix_preview_report.

    Verfügbare query_type-Werte:
      Stufe 1: print_stats, cost_report, top_users, top_printers, anomalies, trend
      Stufe 2: printer_history, device_readings, job_history, queue_stats,
               user_detail, user_copy_detail, user_scan_detail,
               workstation_overview, workstation_detail,
               tree_meter, service_desk, sensitive_documents,
               hour_dow_heatmap, off_hours_print, audit_log

    Args:
        query_type:        Einer der oben genannten Query-Typen
        start_date:        Start (Datum oder Preset: last_month_start, this_year_start, today, etc.)
        end_date:          Ende (Datum oder Preset)
        query_params_json: Weitere Parameter als JSON, z.B.:
                           '{"group_by":"user","site_id":"abc","top_n":20}'
                           '{"user_email":"max@firma.de"}'
                           '{"keyword_sets":"hr,finance","include_scans":true}'
    """
    err = _reporting_check()
    if err:
        return _ok({"error": err})

    import json as _json
    from reporting.scheduler import _resolve_dynamic_dates

    params = {"start_date": start_date, "end_date": end_date}
    if query_params_json:
        try:
            extra = _json.loads(query_params_json)
            params.update(extra)
        except Exception:
            return _ok({"error": f"query_params_json ist kein gültiges JSON: {query_params_json}"})

    params = _resolve_dynamic_dates(params)

    try:
        data = query_tools.run_query(query_type=query_type, **params)
    except ValueError as e:
        return _ok({"error": str(e), "hint": "printix_list_design_options() zeigt alle query_types."})
    except Exception as e:
        return _ok({"error": f"Query fehlgeschlagen: {e}"})

    return _ok({
        "query_type": query_type,
        "period": f"{params.get('start_date','?')} — {params.get('end_date','?')}",
        "row_count": len(data) if isinstance(data, list) else "n/a",
        "data": data,
    })


# ─── Demo Data Generator ─────────────────────────────────────────────────────

try:
    from reporting import demo_generator as _demo_gen
    _DEMO_AVAILABLE = True
except Exception as _de:
    _demo_gen = None  # type: ignore
    _DEMO_AVAILABLE = False
    logger.warning("Demo-Generator nicht verfügbar: %s", _de)


def _demo_check() -> str | None:
    if not _DEMO_AVAILABLE:
        return "Demo-Generator nicht verfügbar — bitte Container neu bauen."
    # v4.4.7: Demo läuft auf lokaler SQLite — kein Azure SQL nötig.
    # Nur prüfen ob tenant_id verfügbar ist.
    tid = _get_sql_tenant_id() if _REPORTING_AVAILABLE else ""
    if not tid:
        return "Kein Tenant-Kontext — bitte mit gültigem Bearer Token authentifizieren."
    return None


@mcp.tool()
def printix_demo_setup_schema() -> str:
    """
    Initialisiert die lokale Demo-SQLite-Datenbank (idempotent).

    Legt folgende Demo-Tabellen an (nur wenn sie noch nicht existieren):
      demo_networks, demo_users, demo_printers, demo_jobs, demo_tracking_data,
      demo_jobs_scan, demo_jobs_copy, demo_jobs_copy_details, demo_sessions

    Idempotent — kann mehrfach ohne Schaden ausgeführt werden.
    Kein Azure SQL erforderlich — Demo-Daten liegen lokal auf SQLite.
    """
    err = _demo_check()
    if err:
        return _ok({"error": err})
    try:
        result = _demo_gen.setup_schema()
        return _ok(result)
    except Exception as e:
        return _ok({"error": str(e)})


@mcp.tool()
def printix_demo_generate(
    user_count: int = 15,
    printer_count: int = 6,
    months: int = 12,
    languages: str = "de,en,fr",
    sites: str = "Hauptsitz,Niederlassung",
    demo_tag: str = "",
    jobs_per_user_day: float = 3.0,
) -> str:
    """
    Generiert ein vollständiges Demo-Dataset in der lokalen SQLite-Datenbank.

    Erstellt realistische Druck-, Scan- und Kopierjobs für den angegebenen Zeitraum
    — rückwirkend ab heute. Alle Reports (Volumen, Kosten, Top-User, Trends usw.)
    zeigen danach aussagekräftige Demo-Daten. Kein Azure SQL erforderlich.

    Args:
        user_count:        Anzahl Demo-User (1–200, default: 15)
        printer_count:     Anzahl Demo-Drucker (1–50, default: 6)
        months:            Anzahl Monate rückwirkend ab heute (1–36, default: 12)
        languages:         Kommagetrennte Sprachliste für Benutzernamen
                           Verfügbar: de, en, fr, it, es, nl, sv, no
                           Beispiel: "de,fr,en" → gemischte Herkunft
        sites:             Kommagetrennte Standortnamen
                           Beispiel: "Hauptsitz,München,Wien,Zürich"
        demo_tag:          Name für diese Demo-Session (für späteres Rollback)
                           Beispiel: "DEMO_ACME_2025" — leer = automatisch generiert
        jobs_per_user_day: Durchschnittliche Druckjobs pro User pro Werktag (default: 3.0)

    Beispiel-Aufruf:
        "Erstelle Demo-Daten: 20 User, 8 Drucker, 12 Monate, Sprachen DE/FR/EN,
         Standorte Berlin/Hamburg/München, Tag DEMO_KUNDE_2025"
    """
    err = _demo_check()
    if err:
        return _ok({"error": err})
    try:
        tenant_id = _get_sql_tenant_id()
        lang_list = [l.strip() for l in languages.split(",") if l.strip()]
        site_list = [s.strip() for s in sites.split(",") if s.strip()]
        result = _demo_gen.generate_demo_dataset(
            tenant_id        = tenant_id,
            user_count       = user_count,
            printer_count    = printer_count,
            months           = months,
            languages        = lang_list,
            sites            = site_list,
            demo_tag         = demo_tag,
            jobs_per_user_day= jobs_per_user_day,
        )
        return _ok(result)
    except Exception as e:
        logger.error("Demo-Generator Fehler: %s", e, exc_info=True)
        return _ok({"error": str(e)})


@mcp.tool()
def printix_demo_rollback(demo_tag: str) -> str:
    """
    Löscht alle Demo-Daten einer bestimmten Session aus der lokalen SQLite-DB.

    Entfernt alle Zeilen aus demo_tracking_data, demo_jobs, demo_jobs_scan,
    demo_jobs_copy, demo_jobs_copy_details, demo_printers, demo_users,
    demo_networks und demo_sessions für den angegebenen demo_tag.

    Voraussetzung: printix_demo_status zeigt vorhandene Tags.

    Args:
        demo_tag: Name der Demo-Session, z.B. "DEMO_ACME_2025"
                  (sichtbar in printix_demo_status)
    """
    err = _demo_check()
    if err:
        return _ok({"error": err})
    if not demo_tag.strip():
        return _ok({"error": "demo_tag darf nicht leer sein. Verfügbare Tags via printix_demo_status."})
    try:
        tenant_id = _get_sql_tenant_id()
        result = _demo_gen.rollback_demo(tenant_id, demo_tag.strip())
        return _ok(result)
    except Exception as e:
        return _ok({"error": str(e)})


@mcp.tool()
def printix_demo_status() -> str:
    """
    Zeigt alle aktiven Demo-Sessions im aktuellen Tenant.

    Listet jede Session mit demo_tag, Erstellungsdatum, Anzahl User/Drucker/Jobs.
    Nützlich um Tags für printix_demo_rollback zu ermitteln.
    """
    err = _demo_check()
    if err:
        return _ok({"error": err})
    try:
        tenant_id = _get_sql_tenant_id()
        result = _demo_gen.get_demo_status(tenant_id)
        return _ok(result)
    except Exception as e:
        return _ok({"error": str(e)})


# ─── Dual Transport Router ────────────────────────────────────────────────────

class DualTransportApp:
    """
    ASGI-Router: leitet Anfragen an den passenden MCP-Transport weiter.

      POST /mcp                    → Streamable HTTP Transport (claude.ai)
      GET  /sse                    → SSE Transport (ChatGPT)
      POST /capture/webhook/{id}   → Capture Webhook (shared handler)

    Capture Webhooks werden in BearerAuthMiddleware von der Bearer-Prüfung
    ausgenommen — sie nutzen HMAC-Verifizierung.

    v4.6.7: Wenn CAPTURE_ENABLED=true, laeuft ein separater Capture-Server
    auf Port 8775. Der MCP-Server akzeptiert Capture-Requests weiterhin
    fuer Rueckwaertskompatibilitaet, loggt aber einen Hinweis.
    """

    def __init__(self, sse_app, http_app):
        self.sse_app = sse_app
        self.http_app = http_app
        # v4.6.7: Pruefe ob separater Capture-Server aktiv (bool statt Port)
        self._capture_separate = os.environ.get("CAPTURE_ENABLED", "false").lower() == "true"

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            await self.http_app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "?")
        if path == "/mcp" or path.startswith("/mcp/"):
            await self.http_app(scope, receive, send)
        elif path.startswith("/capture/webhook/") or path.startswith("/capture/debug"):
            if self._capture_separate:
                logger.info("▶ CAPTURE REQUEST [mcp-compat]: %s %s "
                            "(Hinweis: Capture-Server laeuft auf eigenem Port)", method, path)
            else:
                logger.info("▶ CAPTURE REQUEST [mcp]: %s %s", method, path)
            await self._handle_capture(scope, receive, send)
        else:
            await self.sse_app(scope, receive, send)

    # ── Capture Webhook — delegiert an shared handler (v4.4.6) ─────────────

    async def _read_body(self, receive) -> bytes:
        body = b""
        while True:
            msg = await receive()
            body += msg.get("body", b"")
            if not msg.get("more_body", False):
                break
        return body

    async def _json_response(self, send, status: int, data: dict):
        import json as _j
        body = _j.dumps(data, ensure_ascii=False).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                [b"content-type", b"application/json; charset=utf-8"],
            ],
        })
        await send({"type": "http.response.body", "body": body})

    async def _handle_capture(self, scope, receive, send):
        """Delegiert an den shared capture webhook handler (v4.4.6)."""
        from capture.webhook_handler import handle_webhook

        path = scope.get("path", "")
        method = scope.get("method", "GET")
        raw_headers = dict(scope.get("headers", []))
        headers_str = {
            k.decode("utf-8", errors="replace"): v.decode("utf-8", errors="replace")
            for k, v in raw_headers.items()
        }
        body_bytes = await self._read_body(receive)

        # Profile-ID aus Pfad extrahieren
        if path.startswith("/capture/webhook/"):
            profile_id = path[len("/capture/webhook/"):].strip("/")
        elif path.startswith("/capture/debug"):
            profile_id = "00000000-0000-0000-0000-000000000000"
        else:
            profile_id = ""

        try:
            status, data = await handle_webhook(
                profile_id=profile_id,
                method=method,
                headers=headers_str,
                body_bytes=body_bytes,
                source="mcp",
            )
        except Exception as e:
            logger.error("Capture handler error: %s", e, exc_info=True)
            status, data = 500, {"error": str(e)}

        await self._json_response(send, status, data)


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8765"))
    base = os.environ.get("MCP_PUBLIC_URL", "").rstrip("/") or f"http://{host}:{port}"

    # Beide MCP-Transport-Apps
    sse_transport  = mcp.sse_app()
    http_transport = mcp.streamable_http_app()
    app = DualTransportApp(sse_transport, http_transport)

    # Layer 1: Multi-Tenant Bearer Auth (schlägt Token pro Request in der DB nach)
    app = BearerAuthMiddleware(app)

    # Layer 2: Multi-Tenant OAuth 2.0 (client_id/secret werden pro Request aus DB gelesen)
    app = OAuthMiddleware(app)

    # Gespeicherte Report-Schedules laden
    if _REPORTING_AVAILABLE:
        try:
            n = rep_scheduler.init_scheduler_from_templates()
            if n:
                logger.info("  %d Report-Schedule(s) aus Templates geladen", n)
        except Exception as _sched_err:
            logger.warning("Scheduler-Init fehlgeschlagen: %s", _sched_err)

    logger.info("╔══════════════════════════════════════════════════════════════╗")
    logger.info("║        PRINTIX MCP SERVER v4.6.12 — MULTI-TENANT            ║")
    logger.info("╠══════════════════════════════════════════════════════════════╣")
    logger.info("║  MCP (claude.ai):  %s/mcp", base)
    logger.info("║  SSE (ChatGPT):    %s/sse", base)
    logger.info("║  OAuth Authorize:  %s/oauth/authorize", base)
    logger.info("║  OAuth Token:      %s/oauth/token", base)
    logger.info("║  Health-Check:     %s/health", base)
    logger.info("╠══════════════════════════════════════════════════════════════╣")
    # Host-Port aus /data/options.json lesen (= externer Port wie in HA-Netzwerk-Tab konfiguriert)
    try:
        import json as _json
        with open("/data/options.json") as _f:
            _opts = _json.load(_f)
        _host_web_port = int(_opts.get("web_port", os.environ.get("WEB_PORT", "8080")))
    except Exception:
        _host_web_port = int(os.environ.get("WEB_PORT", "8080"))
    logger.info("║  Benutzer registrieren:  http://<HA-IP>:%d", _host_web_port)
    # v4.6.7: Capture-Status (bool statt Port)
    _capture_enabled = os.environ.get("CAPTURE_ENABLED", "false").lower() == "true"
    if _capture_enabled:
        _cap_url = os.environ.get("CAPTURE_PUBLIC_URL", "").rstrip("/") or "http://<HA-IP>:8775"
        logger.info("║  Capture (separat): %s/capture/webhook/<id>", _cap_url)
    else:
        logger.info("║  Capture (via MCP): %s/capture/webhook/<id>", base)
    logger.info("╚══════════════════════════════════════════════════════════════╝")

    uvicorn.run(app, host=host, port=port, log_level=LOG_LEVEL.lower())
