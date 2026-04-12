"""
HMAC Signature Verification for Printix Capture Connector
=========================================================
Supports both HMAC-SHA256 and HMAC-SHA512 as per Printix Capture API.

Headers checked:
  x-printix-signature-256  — HMAC-SHA256
  x-printix-signature-512  — HMAC-SHA512
"""

import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


def verify_hmac(body_bytes: bytes, headers: dict, secret_key: str) -> bool:
    """
    Verifies the HMAC signature of an incoming Printix Capture webhook.

    Returns True if valid, False otherwise.
    If no secret_key is configured, signature check is skipped (returns True).
    """
    if not secret_key:
        logger.debug("No secret_key configured — skipping HMAC verification")
        return True

    key_bytes = secret_key.encode("utf-8")

    # Try SHA-256 first
    sig_256 = headers.get("x-printix-signature-256", "")
    if sig_256:
        expected = hmac.new(key_bytes, body_bytes, hashlib.sha256).hexdigest()
        if hmac.compare_digest(sig_256.lower(), expected.lower()):
            return True
        logger.warning("HMAC-SHA256 mismatch: got=%s expected=%s", sig_256[:16], expected[:16])
        return False

    # Try SHA-512
    sig_512 = headers.get("x-printix-signature-512", "")
    if sig_512:
        expected = hmac.new(key_bytes, body_bytes, hashlib.sha512).hexdigest()
        if hmac.compare_digest(sig_512.lower(), expected.lower()):
            return True
        logger.warning("HMAC-SHA512 mismatch: got=%s expected=%s", sig_512[:16], expected[:16])
        return False

    # No signature header present
    logger.warning("No HMAC signature header found but secret_key is configured")
    return False
