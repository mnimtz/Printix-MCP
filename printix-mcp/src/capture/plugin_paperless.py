"""
Paperless-ngx Plugin — Dokumente an Paperless-ngx weiterleiten
==============================================================
Lädt das Dokument von der Azure Blob SAS URL herunter und sendet es
an die Paperless-ngx REST API: POST /api/documents/post_document/

Konfiguration:
  - paperless_url: Base-URL der Paperless-Instanz (z.B. http://192.168.1.10:8000)
  - paperless_token: API-Token für die Authentifizierung
  - default_tags: Komma-getrennte Tags (optional)
  - default_correspondent: Korrespondent-Name (optional)
  - default_document_type: Dokumenttyp (optional)
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

from capture.base_plugin import CapturePlugin, register_plugin


@register_plugin
class PaperlessNgxPlugin(CapturePlugin):
    plugin_id = "paperless_ngx"
    plugin_name = "Paperless-ngx"
    plugin_icon = "📋"
    plugin_description = "Send scanned documents to Paperless-ngx for archival and OCR processing."
    plugin_color = "#16a34a"

    def config_schema(self) -> list[dict]:
        return [
            {
                "key": "paperless_url",
                "label": "Paperless-ngx URL",
                "type": "url",
                "required": True,
                "hint": "e.g. http://192.168.1.10:8000",
                "default": "",
            },
            {
                "key": "paperless_token",
                "label": "API Token",
                "type": "password",
                "required": True,
                "hint": "Settings → API Token in Paperless-ngx",
                "default": "",
            },
            {
                "key": "default_tags",
                "label": "Default Tags",
                "type": "text",
                "required": False,
                "hint": "Comma-separated tags (e.g. printix,scan)",
                "default": "printix",
            },
            {
                "key": "default_correspondent",
                "label": "Default Correspondent",
                "type": "text",
                "required": False,
                "hint": "Correspondent name (optional)",
                "default": "",
            },
            {
                "key": "default_document_type",
                "label": "Default Document Type",
                "type": "text",
                "required": False,
                "hint": "Document type name (optional)",
                "default": "",
            },
        ]

    async def process_document(
        self,
        document_url: str,
        filename: str,
        metadata: dict[str, Any],
        event_data: dict,
    ) -> tuple[bool, str]:
        """Downloads the document from Azure Blob and uploads to Paperless-ngx."""
        import aiohttp

        paperless_url = self.config.get("paperless_url", "").rstrip("/")
        token = self.config.get("paperless_token", "")

        if not paperless_url or not token:
            return False, "Paperless-ngx URL or API token not configured"

        if not document_url:
            return False, "No document URL provided in webhook"

        try:
            async with aiohttp.ClientSession() as session:
                # 1. Download document from Azure Blob SAS URL
                logger.info("Downloading document from: %s", document_url[:80])
                async with session.get(document_url) as dl_resp:
                    if dl_resp.status != 200:
                        return False, f"Download failed: HTTP {dl_resp.status}"
                    doc_bytes = await dl_resp.read()
                    if not doc_bytes:
                        return False, "Downloaded document is empty"
                    logger.info("Downloaded %d bytes", len(doc_bytes))

                # 2. Build multipart form for Paperless-ngx
                upload_url = f"{paperless_url}/api/documents/post_document/"
                headers = {"Authorization": f"Token {token}"}

                # Content-Type aus Dateiendung ableiten (v4.4.9)
                import mimetypes
                _fn = filename or "scan.pdf"
                _ct = mimetypes.guess_type(_fn)[0] or "application/pdf"

                form = aiohttp.FormData()
                form.add_field(
                    "document",
                    doc_bytes,
                    filename=_fn,
                    content_type=_ct,
                )

                # Optional: title from metadata or filename
                title = metadata.get("title") or metadata.get("Title") or filename or ""
                if title:
                    form.add_field("title", title)

                # Tags
                tags = self.config.get("default_tags", "")
                if tags:
                    for tag in tags.split(","):
                        tag = tag.strip()
                        if tag:
                            form.add_field("tags", tag)

                # Correspondent
                correspondent = self.config.get("default_correspondent", "")
                if correspondent:
                    form.add_field("correspondent", correspondent)

                # Document type
                doc_type = self.config.get("default_document_type", "")
                if doc_type:
                    form.add_field("document_type", doc_type)

                # 3. Upload to Paperless-ngx
                logger.info("Uploading to Paperless-ngx: %s", upload_url)
                async with session.post(upload_url, data=form, headers=headers) as resp:
                    resp_text = await resp.text()
                    if resp.status in (200, 201, 202):
                        logger.info("Paperless-ngx accepted document: %s", resp_text[:200])
                        return True, f"Document uploaded successfully (HTTP {resp.status})"
                    else:
                        logger.error("Paperless-ngx rejected: HTTP %d — %s", resp.status, resp_text[:300])
                        return False, f"Paperless-ngx error: HTTP {resp.status} — {resp_text[:200]}"

        except Exception as e:
            logger.exception("Paperless-ngx plugin error: %s", e)
            return False, f"Error: {e}"

    async def test_connection(self) -> tuple[bool, str]:
        """Tests connection to Paperless-ngx by querying /api/documents/ (v4.4.11)."""
        import aiohttp

        paperless_url = self.config.get("paperless_url", "").rstrip("/")
        token = self.config.get("paperless_token", "")

        if not paperless_url:
            return False, "Paperless-ngx URL not configured"
        if not token:
            return False, "API token not configured"

        headers = {
            "Authorization": f"Token {token}",
            "Accept": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=10)

        try:
            async with aiohttp.ClientSession() as session:
                # Use /api/documents/?page_size=1 — lightweight, reliable,
                # works with DRF + Cloudflare/reverse proxies.
                # The /api/ root can return 406 with format negotiation.
                url = f"{paperless_url}/api/documents/?page_size=1"
                async with session.get(url, headers=headers, timeout=timeout) as resp:
                    if resp.status == 200:
                        ct = resp.headers.get("content-type", "")
                        if "text/html" in ct:
                            return False, (
                                f"Server returned HTML instead of JSON — "
                                f"check URL (proxy/login page?): {paperless_url}"
                            )
                        try:
                            data = await resp.json()
                        except Exception:
                            return False, f"Response is not valid JSON (Content-Type: {ct})"

                        # Extract document count for status info
                        doc_count = data.get("count", "?")

                        # Try to get version from /api/ui_settings/
                        version = ""
                        try:
                            async with session.get(
                                f"{paperless_url}/api/ui_settings/",
                                headers=headers,
                                timeout=aiohttp.ClientTimeout(total=5),
                            ) as vr:
                                if vr.status == 200:
                                    vdata = await vr.json()
                                    version = vdata.get("version", "")
                        except Exception:
                            pass

                        msg = "Connection successful"
                        if version:
                            msg += f" (Paperless-ngx {version})"
                        msg += f" — {doc_count} documents"
                        return True, msg
                    elif resp.status == 401:
                        return False, "Authentication failed — check API token"
                    elif resp.status == 403:
                        return False, "Access forbidden — check API token permissions"
                    else:
                        return False, f"Unexpected response: HTTP {resp.status}"

        except aiohttp.ClientConnectorError:
            return False, f"Cannot connect to {paperless_url} — check URL and network"
        except Exception as e:
            return False, f"Connection error: {e}"
