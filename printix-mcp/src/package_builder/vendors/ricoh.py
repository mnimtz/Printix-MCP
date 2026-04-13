"""
Package Builder — Ricoh Adapter
Verarbeitet mehrstufig verschachtelte Ricoh-Installerpakete.

Paketstruktur (versionstolerant):
  äußeres ZIP
    PrintixGoRicohInstaller/
      deploysetting.json       ← steuert den Build
      config.json              ← Runtime-Launcher (read-only)
      acl.dist                 ← ACL (read-only)
      rxspServletPackage-*.zip ← inneres Paket (Version variiert)
        app_install_settings.xml
        rxspServlet-*.zip
          rxspServlet.dalp     ← Patch-Ziel 1 (Pflicht)
        rxspservletsop-*.zip
          rxspservletsop.dalp  ← Patch-Ziel 2 (optional)
"""
from __future__ import annotations

import fnmatch
import io
import json
import logging
import re
import zipfile
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

from ..models import AnalysisResult, FieldSchema, PatchResult, PatchSummary, StructureInfo
from .base import VendorBase

logger = logging.getLogger("printix.package_builder.ricoh")

# ── Erkennungskonstanten ───────────────────────────────────────────────────────

RICOH_ROOT_FOLDER = "PrintixGoRicohInstaller"
RICOH_DEPLOY_SETTING = "deploysetting.json"

# ── Muster für versionierte Dateinamen ────────────────────────────────────────

INNER_PKG_PATTERN = "rxspServletPackage-*.zip"
SERVLET_ZIP_PATTERN = "rxspServlet-*.zip"
SOP_ZIP_PATTERN = "rxspservletsop-*.zip"

# ── DALP-Patch-Regeln ─────────────────────────────────────────────────────────
# Jede Regel mappt ein UI-Feld auf eine XPath-Stelle im DALP-XML.
# attribute=None → Text-Content des Elements
# attribute="name" → Attributwert

SERVLET_DALP_RULES = [
    {
        "xpath": ".//description[@type='detail']",
        "attribute": None,
        "field": "servlet_url",
        "optional": False,
    },
    {
        "xpath": ".//property[@name='tenantId']",
        "attribute": "value",
        "field": "tenant_id",
        "optional": True,
    },
    {
        "xpath": ".//property[@name='tenantUrl']",
        "attribute": "value",
        "field": "tenant_url",
        "optional": True,
    },
    {
        "xpath": ".//property[@name='clientId']",
        "attribute": "value",
        "field": "client_id",
        "optional": True,
    },
    {
        "xpath": ".//property[@name='clientSecret']",
        "attribute": "value",
        "field": "client_secret",
        "optional": True,
    },
    # Installer-URL: Hostteil automatisch aus servlet_url ableiten
    {
        "xpath": ".//installer",
        "attribute": "url",
        "field": "__auto_installer_url",
        "optional": True,
        "derived": True,  # wird aus servlet_url hergeleitet
    },
]

# rxspservletsop.dalp: aktuell read-only; Regeln für spätere Erweiterung vorbereitet
SOP_DALP_RULES: list = []


class RicohVendor(VendorBase):
    """Herstelleradapter für Ricoh Printix Go Installerpakete."""

    VENDOR_ID = "ricoh"
    VENDOR_DISPLAY = "Ricoh"
    VENDOR_DESCRIPTION = "Printix Go für Ricoh-Geräte (rxspServlet / DALP)"

    # ── Erkennung ──────────────────────────────────────────────────────────────

    def detect(self, zip_namelist: List[str]) -> bool:
        """True wenn das Paket einen PrintixGoRicohInstaller/-Ordner mit deploysetting.json hat."""
        has_folder = any(n.startswith(RICOH_ROOT_FOLDER + "/") for n in zip_namelist)
        has_deploy = any(
            n == f"{RICOH_ROOT_FOLDER}/{RICOH_DEPLOY_SETTING}"
            or n.endswith(f"/{RICOH_DEPLOY_SETTING}")
            for n in zip_namelist
        )
        return has_folder and has_deploy

    # ── Feldschema ─────────────────────────────────────────────────────────────

    def get_fields(self) -> List[FieldSchema]:
        return [
            FieldSchema(
                key="servlet_url",
                label="Servlet-URL",
                field_type="url",
                required=True,
                placeholder="https://servername:51443/rxsp",
                help_text=(
                    "Basis-URL des rxspServlet-Endpunkts. "
                    "Wird in <description type=\"detail\"> in rxspServlet.dalp eingetragen."
                ),
                group="Verbindung",
                order=10,
            ),
            FieldSchema(
                key="tenant_id",
                label="Tenant ID",
                field_type="text",
                required=True,
                placeholder="printix-tenant-id",
                help_text="Printix Tenant ID aus den API-Einstellungen.",
                group="Authentifizierung",
                order=20,
            ),
            FieldSchema(
                key="tenant_url",
                label="Tenant URL",
                field_type="url",
                required=True,
                placeholder="https://xxx.printix.net",
                help_text="Printix Portal-URL des Tenants.",
                group="Authentifizierung",
                order=30,
            ),
            FieldSchema(
                key="client_id",
                label="Client ID (Print API)",
                field_type="text",
                required=True,
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                help_text="Print API Client ID aus den Printix API-Einstellungen.",
                group="Authentifizierung",
                order=40,
            ),
            FieldSchema(
                key="client_secret",
                label="Client Secret (Print API)",
                field_type="password",
                required=True,
                placeholder="",
                help_text="Print API Client Secret. Wird nicht gespeichert oder geloggt.",
                group="Authentifizierung",
                order=50,
            ),
        ]

    # ── Vorbelegung ────────────────────────────────────────────────────────────

    def prefill_from_tenant(self, tenant: Dict) -> Dict[str, str]:
        prefill: Dict[str, str] = {}
        if not tenant:
            return prefill
        # Tenant ID
        tid = tenant.get("tenant_id") or tenant.get("printix_tenant_id") or ""
        if tid:
            prefill["tenant_id"] = str(tid)
        # Tenant URL — aus tenant_id oder explizitem Feld ableiten
        tenant_url = tenant.get("tenant_url") or ""
        if not tenant_url and tid:
            # Heuristic: Printix-Tenant-URL basiert oft auf der Tenant-ID
            tenant_url = f"https://{tid}.printix.net"
        if tenant_url:
            prefill["tenant_url"] = tenant_url
        # Client ID (Print API)
        cid = tenant.get("client_id") or tenant.get("print_client_id") or ""
        if cid:
            prefill["client_id"] = str(cid)
        # Client Secret — Vorsicht: nur vorbelegen wenn der User es explizit gespeichert hat
        # Niemals automatisch aus DB-Verschlüsselung extrahieren — Nutzer muss es eingeben
        # Public URL als Basis für servlet_url
        public_url = tenant.get("public_url") or tenant.get("mcp_public_url") or ""
        if public_url:
            # Servlet URL ist typisch <base>:51443/rxsp oder ähnlich
            # Wir befüllen nur wenn eine sinnvolle URL vorliegt
            prefill["servlet_url"] = public_url.rstrip("/") + ":51443/rxsp"
        return prefill

    # ── Analyse ────────────────────────────────────────────────────────────────

    def analyze(self, outer_zip_path: str) -> AnalysisResult:
        try:
            return self._do_analyze(outer_zip_path)
        except Exception as exc:
            logger.warning("Ricoh analyze Fehler: %s", exc, exc_info=True)
            return AnalysisResult(ok=False, error=f"Analyse-Fehler: {exc}")

    def _do_analyze(self, outer_zip_path: str) -> AnalysisResult:
        warnings: List[str] = []
        notes: List[str] = []
        found_files: List[str] = []

        with zipfile.ZipFile(outer_zip_path, "r") as outer_zf:
            namelist = outer_zf.namelist()

            # 1. deploysetting.json finden
            deploy_path = _find_in_zip(namelist, RICOH_DEPLOY_SETTING)
            if not deploy_path:
                return AnalysisResult(
                    ok=False,
                    error="deploysetting.json nicht gefunden. Falsches Paket?",
                )
            found_files.append("deploysetting.json")

            deploy_data = json.loads(outer_zf.read(deploy_path).decode("utf-8"))

            # 2. Inneres RXSP-Paket aus deploysetting.json
            rxsp_file_path = _resolve_rxsp_path(deploy_data, namelist)
            if not rxsp_file_path:
                return AnalysisResult(
                    ok=False,
                    error=(
                        "Inneres RXSP-Paket (rxspServletPackage-*.zip) nicht gefunden. "
                        "Prüfen Sie deploysetting.json → servlet.rxsp_file_path."
                    ),
                )
            pkg_version = _extract_version(rxsp_file_path)
            found_files.append(f"rxspServletPackage ({pkg_version})")

            # 3. Inneres ZIP öffnen
            inner_bytes = outer_zf.read(rxsp_file_path)

        with zipfile.ZipFile(io.BytesIO(inner_bytes), "r") as inner_zf:
            inner_names = inner_zf.namelist()

            # 4. Servlet-ZIP finden
            servlet_zip_name = _glob_find(inner_names, SERVLET_ZIP_PATTERN)
            if not servlet_zip_name:
                return AnalysisResult(
                    ok=False,
                    error=f"rxspServlet-*.zip nicht im inneren Paket gefunden. Inhalt: {inner_names[:10]}",
                )
            found_files.append(f"rxspServlet-ZIP ({_extract_version(servlet_zip_name)})")

            # 5. SOP-ZIP finden (optional)
            sop_zip_name = _glob_find(inner_names, SOP_ZIP_PATTERN)
            if sop_zip_name:
                found_files.append(f"rxspservletsop-ZIP ({_extract_version(sop_zip_name)})")
            else:
                warnings.append("rxspservletsop-*.zip nicht gefunden (optional).")

            # 6. rxspServlet.dalp analysieren
            servlet_bytes = inner_zf.read(servlet_zip_name)
            dalp_info, dalp_warn = _analyze_dalp_zip(servlet_bytes, "rxspServlet.dalp")
            found_files.extend(dalp_info)
            warnings.extend(dalp_warn)

        notes.append(f"Erkannte Paketversion: {pkg_version}")
        notes.append("deploysetting.json, Servlet-DALP und RXSP-Struktur erfolgreich analysiert.")

        structure = StructureInfo(
            vendor=self.VENDOR_ID,
            vendor_display=self.VENDOR_DISPLAY,
            package_version=pkg_version,
            found_files=found_files,
            warnings=warnings,
            notes=notes,
            raw_info={
                "rxsp_zip_path": rxsp_file_path,
                "servlet_zip": servlet_zip_name,
                "sop_zip": sop_zip_name,
            },
        )

        return AnalysisResult(
            ok=True,
            structure=structure,
            fields=self.get_fields(),
        )

    # ── Patch ──────────────────────────────────────────────────────────────────

    def patch(
        self,
        outer_zip_path: str,
        field_values: Dict[str, str],
        output_path: str,
    ) -> PatchResult:
        try:
            return self._do_patch(outer_zip_path, field_values, output_path)
        except Exception as exc:
            logger.error("Ricoh patch Fehler: %s", exc, exc_info=True)
            return PatchResult(ok=False, error=f"Patch-Fehler: {exc}")

    def _do_patch(
        self,
        outer_zip_path: str,
        field_values: Dict[str, str],
        output_path: str,
    ) -> PatchResult:
        summary = PatchSummary()

        # ── Äußeres ZIP lesen ─────────────────────────────────────────────────
        with zipfile.ZipFile(outer_zip_path, "r") as outer_zf:
            namelist = outer_zf.namelist()
            deploy_path = _find_in_zip(namelist, RICOH_DEPLOY_SETTING)
            if not deploy_path:
                return PatchResult(ok=False, error="deploysetting.json nicht gefunden.")

            deploy_data = json.loads(outer_zf.read(deploy_path).decode("utf-8"))
            rxsp_file_path = _resolve_rxsp_path(deploy_data, namelist)
            if not rxsp_file_path:
                return PatchResult(ok=False, error="Inneres RXSP-Paket nicht gefunden.")

            # Alle Dateien des äußeren ZIP in Memory laden
            outer_files: Dict[str, bytes] = {}
            for name in namelist:
                outer_files[name] = outer_zf.read(name)

        # ── Inneres Paket patchen ──────────────────────────────────────────────
        inner_bytes = outer_files[rxsp_file_path]
        patched_inner, s = _patch_inner_package(inner_bytes, field_values)
        summary.patched_logical_files.extend(s.patched_logical_files)
        summary.patched_fields.extend(s.patched_fields)
        summary.skipped_fields.extend(s.skipped_fields)
        summary.notes.extend(s.notes)

        # ── Äußeres ZIP neu bauen ─────────────────────────────────────────────
        outer_files[rxsp_file_path] = patched_inner
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as out_zf:
            for name, data in outer_files.items():
                out_zf.writestr(name, data)
        with open(output_path, "wb") as fh:
            fh.write(buf.getvalue())

        logger.info(
            "Ricoh patch erfolgreich: %d Felder, Dateien: %s",
            len(summary.patched_fields),
            summary.patched_logical_files,
        )
        return PatchResult(ok=True, summary=summary)

    # ── Installationshinweise ──────────────────────────────────────────────────

    def get_install_notes(self, field_values: Dict[str, str]) -> List[str]:
        servlet_url = field_values.get("servlet_url", "")
        notes = [
            "Das gepatchte Paket kann direkt über das Ricoh Remote Communication Gate S (RCG/S) oder "
            "den Ricoh @Remote-Dienst deployed werden.",
            "Alternativ: Paket über das Ricoh Streamline NX-Portal hochladen.",
        ]
        if servlet_url:
            notes.append(
                f"Stellen Sie sicher, dass {servlet_url} von den Ricoh-Geräten "
                "erreichbar ist (Firewall, Port 51443)."
            )
        notes.append(
            "Nach dem Deployment: Anmeldung an einem Gerät testen "
            "(Karte einlesen oder PIN eingeben)."
        )
        return notes


# ── Hilfsfunktionen ────────────────────────────────────────────────────────────

def _find_in_zip(namelist: List[str], filename: str) -> Optional[str]:
    """Findet eine Datei im ZIP (exakter Dateiname, beliebiger Pfad)."""
    for name in namelist:
        if name.split("/")[-1] == filename:
            return name
    return None


def _glob_find(namelist: List[str], pattern: str) -> Optional[str]:
    """
    Findet die erste Datei die dem Glob-Muster entspricht.
    Vergleicht nur den Dateinamen-Teil (basename), nicht den vollen Pfad.
    """
    for name in namelist:
        basename = name.split("/")[-1]
        if fnmatch.fnmatch(basename, pattern):
            return name
    return None


def _extract_version(filename: str) -> str:
    """Extrahiert die Versionsnummer aus einem Dateinamen wie rxspServletPackage-3.8.11.zip"""
    match = re.search(r"(\d+\.\d+(?:\.\d+)*)", filename)
    return match.group(1) if match else "?"


def _resolve_rxsp_path(deploy_data: Dict, namelist: List[str]) -> Optional[str]:
    """
    Ermittelt den Pfad des inneren RXSP-Pakets.
    Bevorzugt: Wert aus deploysetting.json → servlet.rxsp_file_path.
    Fallback: Glob-Suche nach rxspServletPackage-*.zip.
    """
    # Aus deploysetting.json lesen
    rxsp_path: Optional[str] = None
    servlet_cfg = deploy_data.get("servlet", {})
    if isinstance(servlet_cfg, dict):
        rxsp_path = servlet_cfg.get("rxsp_file_path") or servlet_cfg.get("rxspFilePath")
    if not rxsp_path:
        rxsp_path = deploy_data.get("rxsp_file_path") or deploy_data.get("rxspFilePath")

    if rxsp_path:
        # Normalisieren: nur basename verwenden, dann im ZIP suchen
        basename = rxsp_path.replace("\\", "/").split("/")[-1]
        # Exakter Treffer
        exact = next((n for n in namelist if n.split("/")[-1] == basename), None)
        if exact:
            return exact
        # Version könnte abweichen → Glob-Fallback
        logger.info(
            "Exakter Pfad '%s' nicht gefunden, verwende Glob-Fallback.", rxsp_path
        )

    # Glob-Fallback
    return _glob_find(namelist, INNER_PKG_PATTERN)


def _analyze_dalp_zip(zip_bytes: bytes, dalp_filename: str) -> Tuple[List[str], List[str]]:
    """Öffnet ein Sub-ZIP und analysiert eine DALP-Datei."""
    found: List[str] = []
    warnings: List[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            names = zf.namelist()
            dalp_name = _find_in_zip(names, dalp_filename)
            if not dalp_name:
                warnings.append(f"{dalp_filename} nicht im ZIP gefunden.")
                return found, warnings
            found.append(dalp_filename)
            dalp_bytes = zf.read(dalp_name)
            try:
                ET.fromstring(dalp_bytes.decode("utf-8"))
                found.append(f"{dalp_filename} (XML gültig)")
            except ET.ParseError as e:
                warnings.append(f"{dalp_filename} XML-Fehler: {e}")
    except zipfile.BadZipFile as e:
        warnings.append(f"Sub-ZIP nicht lesbar: {e}")
    return found, warnings


def _patch_inner_package(inner_bytes: bytes, field_values: Dict[str, str]) -> Tuple[bytes, PatchSummary]:
    """
    Öffnet das innere rxspServletPackage-*.zip, patcht die DALP-Dateien
    und gibt das neu verpackte ZIP als Bytes zurück.
    """
    summary = PatchSummary()

    with zipfile.ZipFile(io.BytesIO(inner_bytes), "r") as inner_zf:
        inner_names = inner_zf.namelist()
        inner_files: Dict[str, bytes] = {}
        for name in inner_names:
            inner_files[name] = inner_zf.read(name)

    # Servlet-ZIP patchen
    servlet_zip_name = _glob_find(inner_names, SERVLET_ZIP_PATTERN)
    if servlet_zip_name:
        patched_servlet, s = _patch_dalp_zip(
            inner_files[servlet_zip_name],
            "rxspServlet.dalp",
            SERVLET_DALP_RULES,
            field_values,
        )
        inner_files[servlet_zip_name] = patched_servlet
        summary.patched_logical_files.extend(s.patched_logical_files)
        summary.patched_fields.extend(s.patched_fields)
        summary.skipped_fields.extend(s.skipped_fields)
        summary.notes.extend(s.notes)
    else:
        summary.notes.append("rxspServlet-*.zip nicht gefunden — kein Servlet-Patch.")

    # SOP-ZIP: aktuell read-only, Regeln für spätere Erweiterung vorbereitet
    sop_zip_name = _glob_find(inner_names, SOP_ZIP_PATTERN)
    if sop_zip_name and SOP_DALP_RULES:
        patched_sop, s2 = _patch_dalp_zip(
            inner_files[sop_zip_name],
            "rxspservletsop.dalp",
            SOP_DALP_RULES,
            field_values,
        )
        inner_files[sop_zip_name] = patched_sop
        summary.patched_logical_files.extend(s2.patched_logical_files)
        summary.patched_fields.extend(s2.patched_fields)
    elif sop_zip_name:
        summary.notes.append("rxspservletsop.dalp erkannt (read-only, aktuell kein Patch nötig).")

    # Inneres ZIP neu bauen
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as out_zf:
        for name, data in inner_files.items():
            out_zf.writestr(name, data)
    return buf.getvalue(), summary


def _patch_dalp_zip(
    zip_bytes: bytes,
    dalp_filename: str,
    rules: List[Dict],
    field_values: Dict[str, str],
) -> Tuple[bytes, PatchSummary]:
    """
    Öffnet ein Sub-ZIP, patcht die angegebene DALP-Datei per XML-Parser
    und gibt das neu verpackte ZIP als Bytes zurück.
    """
    summary = PatchSummary()

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        names = zf.namelist()
        sub_files: Dict[str, bytes] = {}
        for n in names:
            sub_files[n] = zf.read(n)

    dalp_name = _find_in_zip(names, dalp_filename)
    if not dalp_name:
        summary.notes.append(f"{dalp_filename} nicht im Sub-ZIP gefunden — übersprungen.")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as out_zf:
            for n, d in sub_files.items():
                out_zf.writestr(n, d)
        return buf.getvalue(), summary

    # XML parsen
    dalp_bytes = sub_files[dalp_name]
    try:
        # Namespace-Registrierung verhindern (ElementTree fügt ns0: hinzu)
        root = ET.fromstring(dalp_bytes.decode("utf-8"))
    except ET.ParseError as e:
        return zip_bytes, PatchSummary(notes=[f"XML-Parse-Fehler in {dalp_filename}: {e}"])

    # Regeln anwenden
    for rule in rules:
        if rule.get("derived"):
            continue  # wird separat behandelt
        field_key = rule["field"]
        value = field_values.get(field_key)
        if not value:
            if not rule.get("optional", True):
                summary.skipped_fields.append(field_key)
            continue

        xpath = rule["xpath"]
        attr = rule.get("attribute")
        elements = root.findall(xpath)

        if not elements:
            if not rule.get("optional", True):
                summary.skipped_fields.append(field_key)
                summary.notes.append(
                    f"Pflichtfeld '{field_key}': XPath '{xpath}' nicht in {dalp_filename} gefunden."
                )
            continue

        for elem in elements:
            if attr is None:
                elem.text = value
            else:
                elem.set(attr, value)
        summary.patched_fields.append(field_key)

    # Installer-URL aus servlet_url ableiten (falls Regel vorhanden)
    _apply_installer_url_rule(root, field_values, summary)

    # XML serialisieren — Original-Encoding beibehalten
    encoding, xml_declaration = _detect_xml_encoding(dalp_bytes)
    patched_xml = _serialize_xml(root, encoding, xml_declaration)
    sub_files[dalp_name] = patched_xml
    summary.patched_logical_files.append(dalp_filename)

    # Validierung: gepatchtes XML muss parsebar sein
    try:
        ET.fromstring(patched_xml.decode(encoding))
    except ET.ParseError as e:
        return zip_bytes, PatchSummary(notes=[f"Patch-Validierungsfehler: {e}"])

    # Sub-ZIP neu bauen
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as out_zf:
        for n, d in sub_files.items():
            out_zf.writestr(n, d)
    return buf.getvalue(), summary


def _apply_installer_url_rule(root: ET.Element, field_values: Dict[str, str], summary: PatchSummary):
    """
    Leitet die Installer-URL aus der servlet_url ab und aktualisiert <installer url="...">.
    Heuristik: ersetzt den Host-Teil der bestehenden Installer-URL.
    """
    servlet_url = field_values.get("servlet_url", "").rstrip("/")
    if not servlet_url:
        return
    # Host aus servlet_url extrahieren
    new_host = _extract_url_host(servlet_url)
    if not new_host:
        return

    for installer_elem in root.findall(".//installer"):
        old_url = installer_elem.get("url", "")
        if not old_url:
            continue
        old_host = _extract_url_host(old_url)
        if old_host and old_host != new_host:
            updated_url = old_url.replace(old_host, new_host, 1)
            installer_elem.set("url", updated_url)
            if "installer_url" not in summary.patched_fields:
                summary.patched_fields.append("installer_url (abgeleitet)")


def _extract_url_host(url: str) -> Optional[str]:
    """Extrahiert 'host:port' aus einer URL wie https://host:51443/path"""
    match = re.match(r"https?://([^/]+)", url)
    return match.group(1) if match else None


def _detect_xml_encoding(xml_bytes: bytes) -> Tuple[str, bool]:
    """Erkennt das Encoding aus der XML-Deklaration."""
    try:
        header = xml_bytes[:200].decode("ascii", errors="replace")
        enc_match = re.search(r'encoding=["\']([^"\']+)["\']', header)
        encoding = enc_match.group(1).lower() if enc_match else "utf-8"
        has_decl = header.strip().startswith("<?xml")
        return encoding, has_decl
    except Exception:
        return "utf-8", True


def _serialize_xml(root: ET.Element, encoding: str = "utf-8", include_declaration: bool = True) -> bytes:
    """Serialisiert einen ElementTree-Root zurück zu Bytes."""
    buf = io.BytesIO()
    tree = ET.ElementTree(root)
    if include_declaration:
        tree.write(buf, encoding=encoding, xml_declaration=True)
    else:
        tree.write(buf, encoding=encoding)
    return buf.getvalue()
