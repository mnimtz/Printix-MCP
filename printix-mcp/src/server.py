"""
Printix MCP Server — Home Assistant Add-on Version
===================================================
Model Context Protocol server for the Printix Cloud Print API.

Reads configuration from environment variables (set by run.sh from /data/options.json).
Includes structured logging and Bearer token authentication middleware.

Credentials (set via HA Add-on Config → env vars):
  PRINTIX_TENANT_ID             — required
  PRINTIX_PRINT_CLIENT_ID       — Print API
  PRINTIX_PRINT_CLIENT_SECRET   — Print API
  PRINTIX_CARD_CLIENT_ID        — Card Management API
  PRINTIX_CARD_CLIENT_SECRET    — Card Management API
  PRINTIX_WS_CLIENT_ID          — Workstation Monitoring API
  PRINTIX_WS_CLIENT_SECRET      — Workstation Monitoring API

Optional:
  PRINTIX_SHARED_CLIENT_ID      — Shared fallback
  PRINTIX_SHARED_CLIENT_SECRET  — Shared fallback
  MCP_BEARER_TOKEN              — Bearer token for auth middleware
  MCP_LOG_LEVEL                 — debug/info/warning/error/critical
  MCP_HOST                      — Listen host (default: 0.0.0.0)
  MCP_PORT                      — Listen port (default: 8765)

Transport: SSE on port 8765 (HTTP)
"""

import os
import sys
import json
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP
from printix_client import PrintixClient, PrintixAPIError
from auth import BearerAuthMiddleware
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
    "uvicorn.access",
):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logger = logging.getLogger("printix.mcp")
logger.info("Log-Level: %s", LOG_LEVEL)


# ─── Setup ────────────────────────────────────────────────────────────────────
# host="0.0.0.0" deaktiviert die Auto-Aktivierung des DNS-Rebinding-Schutzes.
# FastMCP aktiviert ihn nur wenn host in ("127.0.0.1", "localhost", "::1").
# Mit "0.0.0.0" bleibt transport_security=None → keine Host-Validierung.
mcp = FastMCP("Printix", host="0.0.0.0")


def _get_client() -> PrintixClient:
    """Create PrintixClient from environment variables."""
    tenant_id = os.environ.get("PRINTIX_TENANT_ID")
    if not tenant_id:
        logger.critical("PRINTIX_TENANT_ID ist nicht gesetzt!")
        raise RuntimeError("PRINTIX_TENANT_ID is not set.")
    logger.info("Initialisiere PrintixClient für Tenant: %s", tenant_id)
    return PrintixClient(
        tenant_id=tenant_id,
        print_client_id=os.environ.get("PRINTIX_PRINT_CLIENT_ID"),
        print_client_secret=os.environ.get("PRINTIX_PRINT_CLIENT_SECRET"),
        card_client_id=os.environ.get("PRINTIX_CARD_CLIENT_ID"),
        card_client_secret=os.environ.get("PRINTIX_CARD_CLIENT_SECRET"),
        ws_client_id=os.environ.get("PRINTIX_WS_CLIENT_ID"),
        ws_client_secret=os.environ.get("PRINTIX_WS_CLIENT_SECRET"),
        shared_client_id=os.environ.get("PRINTIX_SHARED_CLIENT_ID"),
        shared_client_secret=os.environ.get("PRINTIX_SHARED_CLIENT_SECRET"),
    )


# Singleton client (lazy init)
_client: Optional[PrintixClient] = None


def client() -> PrintixClient:
    global _client
    if _client is None:
        _client = _get_client()
    return _client


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
    Listet alle Drucker / Print Queues des Tenants.

    Args:
        search: Optionaler Suchbegriff (Name des Druckers).
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


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    host         = os.environ.get("MCP_HOST", "0.0.0.0")
    port         = int(os.environ.get("MCP_PORT", "8765"))
    bearer_token = os.environ.get("MCP_BEARER_TOKEN", "")
    oauth_id     = os.environ.get("OAUTH_CLIENT_ID", "")
    oauth_secret = os.environ.get("OAUTH_CLIENT_SECRET", "")

    # Basis-App
    app = mcp.sse_app()

    # Layer 1: Bearer Token Auth (schützt den MCP SSE Endpoint)
    if bearer_token:
        logger.info("Bearer Token Authentifizierung aktiviert")
        app = BearerAuthMiddleware(app, token=bearer_token)
    else:
        logger.warning("KEIN Bearer Token gesetzt — MCP-Endpoint ist UNGESCHÜTZT!")

    # Layer 2: OAuth 2.0 (sitzt vor Bearer Auth, stellt Tokens aus)
    # ChatGPT und andere OAuth-Clients authentifizieren sich hier und
    # erhalten als Access Token den Bearer Token — danach läuft alles normal.
    if oauth_id and oauth_secret and bearer_token:
        logger.info("OAuth 2.0 aktiviert (client_id=%s)", oauth_id)
        logger.info("  Authorize: https://<deine-domain>/oauth/authorize")
        logger.info("  Token:     https://<deine-domain>/oauth/token")
        app = OAuthMiddleware(app,
                              client_id=oauth_id,
                              client_secret=oauth_secret,
                              bearer_token=bearer_token)
    elif oauth_id or oauth_secret:
        logger.warning("OAuth unvollständig konfiguriert — OAUTH_CLIENT_ID und OAUTH_CLIENT_SECRET werden beide benötigt")

    logger.info("Starte Printix MCP Server auf %s:%d (SSE Transport)", host, port)
    uvicorn.run(app, host=host, port=port, log_level=LOG_LEVEL.lower())
