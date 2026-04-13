"""
Capture Authentication — Multi-Method Verification (v4.6.0)
===========================================================
Supports the Printix/Tungsten Capture Connector authentication model:

1. Printix Native Signature (x-printix-signature)
   — The REAL header Printix sends, paired with x-printix-timestamp
     and x-printix-request-path. Signature is computed over a canonical
     string: "{timestamp}.{request_path}.{body}" or just the body.
2. HMAC Signature (x-printix-signature-256 / x-printix-signature-512)
   — Body-only HMAC, multiple secrets for key rotation
3. Hub Signature (x-hub-signature-256)
   — GitHub-style webhook signature
4. Connector Token (Authorization: Bearer <token> / x-connector-token)
   — Multiple tokens per profile for rotation
5. require_signature flag per profile
   — Enforces that at least one auth method must succeed

Headers checked (in priority order):
  x-printix-signature          — Printix native (SHA256, canonical string)
  x-printix-signature-256      — HMAC-SHA256 (body only)
  x-printix-signature-512      — HMAC-SHA512 (body only)
  x-hub-signature-256          — Generic webhook signature (GitHub-style)
  authorization                — Bearer token
  x-connector-token            — Alternative connector token header

Companion headers (informational, used in canonical string):
  x-printix-timestamp          — Unix timestamp or ISO datetime
  x-printix-request-path       — Original request path
  x-printix-request-id         — Request correlation ID
"""

import hashlib
import hmac as _hmac
import logging
from dataclasses import dataclass

logger = logging.getLogger("printix.capture.auth")


@dataclass
class AuthResult:
    """Result of capture request authentication."""
    success: bool
    method: str = ""        # "printix-native", "hmac-sha256", "hmac-sha512", "connector-token", "none", "skipped"
    detail: str = ""
    secret_index: int = -1  # Which secret/token matched (0-based), -1 if none


def _strip_prefix(sig: str) -> str:
    """Remove optional prefix like 'sha256=' or 'sha512='."""
    for prefix in ("sha256=", "sha512=", "SHA256=", "SHA512="):
        if sig.startswith(prefix):
            return sig[len(prefix):]
    return sig


def _parse_multi(value: str) -> list[str]:
    """
    Parse multi-value field into list of non-empty strings.
    Supports newline-separated values (for UI textarea input).
    A single value without newlines returns a one-element list.
    """
    if not value:
        return []
    return [v.strip() for v in value.split("\n") if v.strip()]


def _try_hmac(body_bytes: bytes, sig_value: str, secrets: list[str], algo) -> tuple[bool, int]:
    """Try HMAC verification against all secrets. Returns (matched, secret_index)."""
    sig_clean = _strip_prefix(sig_value).lower()
    for i, secret in enumerate(secrets):
        expected = _hmac.new(secret.encode("utf-8"), body_bytes, algo).hexdigest()
        if _hmac.compare_digest(sig_clean, expected.lower()):
            return True, i
    return False, -1


def _try_printix_native(
    body_bytes: bytes,
    sig_value: str,
    secrets: list[str],
    timestamp: str,
    request_path: str,
) -> tuple[bool, int, str]:
    """
    Try Printix native signature verification.

    Printix computes the signature over a canonical string. We try multiple
    candidate formats since the exact Printix implementation is not publicly
    documented. Candidates (all HMAC-SHA256):

      1. "{timestamp}.{request_path}.{body}"  — full canonical string
      2. "{timestamp}.{body}"                 — without path
      3. body only                            — simplest variant

    Returns (matched, secret_index, canonical_format_used).
    """
    sig_clean = _strip_prefix(sig_value).lower()

    # Build candidate signing payloads in priority order
    candidates: list[tuple[bytes, str]] = []

    if timestamp and request_path:
        canonical = f"{timestamp}.{request_path}.".encode("utf-8") + body_bytes
        candidates.append((canonical, f"{{timestamp}}.{{path}}.{{body}} (ts={timestamp}, path={request_path})"))

    if timestamp:
        canonical = f"{timestamp}.".encode("utf-8") + body_bytes
        candidates.append((canonical, f"{{timestamp}}.{{body}} (ts={timestamp})"))

    # Always try body-only as fallback
    candidates.append((body_bytes, "{body} (body only)"))

    for payload, fmt_desc in candidates:
        for i, secret in enumerate(secrets):
            expected = _hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
            if _hmac.compare_digest(sig_clean, expected.lower()):
                return True, i, fmt_desc

    return False, -1, ""


def verify_capture_auth(
    body_bytes: bytes,
    headers: dict[str, str],
    profile: dict,
) -> AuthResult:
    """
    Verify incoming Capture webhook request against profile auth settings.

    Supports (in priority order):
      1. x-printix-signature (Printix native — canonical string with timestamp/path)
      2. x-printix-signature-256 / x-hub-signature-256 (HMAC-SHA256, body only)
      3. x-printix-signature-512 (HMAC-SHA512, body only)
      4. Connector tokens via Authorization: Bearer / x-connector-token header
      5. require_signature enforcement per profile

    Args:
        body_bytes: Raw request body
        headers: Request headers (lowercase keys)
        profile: Capture profile dict from DB

    Returns:
        AuthResult with success, method, detail
    """
    secrets = _parse_multi(profile.get("secret_key", ""))
    tokens = _parse_multi(profile.get("connector_token", ""))
    require_sig = bool(profile.get("require_signature", False))

    has_secrets = bool(secrets)
    has_tokens = bool(tokens)

    # Log all auth-related headers for diagnostics
    auth_headers = {k: v for k, v in headers.items()
                    if any(x in k for x in ("signature", "hmac", "printix",
                                            "authorization", "connector-token"))}
    if auth_headers:
        logger.info("Auth: Relevant headers: %s",
                    {k: v[:40] + "..." if len(v) > 40 else v for k, v in auth_headers.items()})

    logger.debug("Auth config: secrets=%d, tokens=%d, require_signature=%s",
                 len(secrets), len(tokens), require_sig)

    # ── 1. Try HMAC/Signature methods ──────────────────────────────────────
    if has_secrets:
        # ── 1a. Printix Native: x-printix-signature ────────────────────────
        sig_native = headers.get("x-printix-signature", "")
        if sig_native:
            timestamp = headers.get("x-printix-timestamp", "")
            request_path = headers.get("x-printix-request-path", "")
            request_id = headers.get("x-printix-request-id", "")

            logger.info("Auth: Printix native signature detected "
                        "(timestamp=%s, path=%s, request_id=%s)",
                        timestamp or "(none)", request_path or "(none)",
                        request_id or "(none)")

            matched, idx, fmt = _try_printix_native(
                body_bytes, sig_native, secrets, timestamp, request_path
            )
            if matched:
                detail = (f"Printix native signature verified "
                          f"(secret #{idx + 1}/{len(secrets)}, format={fmt})")
                logger.info("Auth: %s", detail)
                return AuthResult(True, "printix-native", detail, idx)

            logger.warning("Auth: Printix native signature mismatch "
                           "(tried %d secrets x 3 canonical formats)", len(secrets))
            # Log expected vs received for first secret (debug aid)
            if secrets:
                for payload_desc, payload in [
                    ("ts.path.body", f"{timestamp}.{request_path}.".encode() + body_bytes),
                    ("ts.body", f"{timestamp}.".encode() + body_bytes),
                    ("body", body_bytes),
                ]:
                    exp = _hmac.new(secrets[0].encode(), payload, hashlib.sha256).hexdigest()
                    logger.debug("Auth debug: format=%s expected=%s... got=%s...",
                                 payload_desc, exp[:16], _strip_prefix(sig_native).lower()[:16])

            return AuthResult(False, "printix-native",
                              f"Printix native signature mismatch "
                              f"(tried {len(secrets)} secrets, "
                              f"timestamp={timestamp or '(none)'}, "
                              f"path={request_path or '(none)'})")

        # ── 1b. x-printix-signature-256 / x-hub-signature-256 ─────────────
        sig_256 = headers.get("x-printix-signature-256", "") or headers.get("x-hub-signature-256", "")
        if sig_256:
            matched, idx = _try_hmac(body_bytes, sig_256, secrets, hashlib.sha256)
            if matched:
                return AuthResult(True, "hmac-sha256",
                                  f"HMAC-SHA256 verified (secret #{idx + 1}/{len(secrets)})",
                                  idx)
            logger.warning("Auth: HMAC-SHA256 mismatch (tried %d secrets)", len(secrets))
            return AuthResult(False, "hmac-sha256",
                              f"HMAC-SHA256 signature mismatch (tried {len(secrets)} secrets)")

        # ── 1c. x-printix-signature-512 ───────────────────────────────────
        sig_512 = headers.get("x-printix-signature-512", "")
        if sig_512:
            matched, idx = _try_hmac(body_bytes, sig_512, secrets, hashlib.sha512)
            if matched:
                return AuthResult(True, "hmac-sha512",
                                  f"HMAC-SHA512 verified (secret #{idx + 1}/{len(secrets)})",
                                  idx)
            logger.warning("Auth: HMAC-SHA512 mismatch (tried %d secrets)", len(secrets))
            return AuthResult(False, "hmac-sha512",
                              f"HMAC-SHA512 signature mismatch (tried {len(secrets)} secrets)")

        # No signature header found — fall through to token check or compat mode
        if not has_tokens:
            if require_sig:
                logger.warning("Auth: No signature header found and require_signature=True. "
                               "Expected one of: x-printix-signature, x-printix-signature-256, "
                               "x-printix-signature-512, x-hub-signature-256")
                return AuthResult(False, "none",
                                  "No signature header in request (require_signature is enabled). "
                                  "Expected: x-printix-signature or x-printix-signature-256")
            logger.warning("Auth: No signature header — allowing (Printix compatibility mode)")
            return AuthResult(True, "skipped",
                              "No signature header but require_signature=False (compatibility mode)")

    # ── 2. Try Connector Token ──────────────────────────────────────────────
    if has_tokens:
        # Check Authorization: Bearer <token>
        auth_header = headers.get("authorization", "")
        req_token = ""
        if auth_header.lower().startswith("bearer "):
            req_token = auth_header[7:].strip()

        # Also check x-connector-token header
        if not req_token:
            req_token = headers.get("x-connector-token", "").strip()

        if req_token:
            for i, valid_token in enumerate(tokens):
                if _hmac.compare_digest(req_token, valid_token):
                    return AuthResult(True, "connector-token",
                                      f"Connector token verified (token #{i + 1}/{len(tokens)})",
                                      i)
            logger.warning("Auth: Connector token mismatch (tried %d tokens)", len(tokens))
            return AuthResult(False, "connector-token",
                              f"Invalid connector token (tried {len(tokens)} tokens)")

        # No token in request
        if not has_secrets:
            if require_sig:
                logger.warning("Auth: No token in request and require_signature=True")
                return AuthResult(False, "none",
                                  "No connector token in request (require_signature is enabled)")
            logger.warning("Auth: No token in request — allowing (compatibility mode)")
            return AuthResult(True, "skipped",
                              "No connector token but require_signature=False (compatibility mode)")

    # ── 3. Neither secrets nor tokens configured ────────────────────────────
    if not has_secrets and not has_tokens:
        if require_sig:
            logger.warning("Auth: require_signature=True but no secrets/tokens configured")
            return AuthResult(False, "none",
                              "require_signature enabled but no secrets or tokens configured")
        logger.debug("Auth: No auth configured — skipping verification")
        return AuthResult(True, "skipped", "No authentication configured on profile")

    # ── 4. Both configured but neither present in request ───────────────────
    if require_sig:
        return AuthResult(False, "none",
                          "No signature header or connector token in request")
    logger.warning("Auth: Both HMAC and tokens configured but neither present — "
                   "allowing (compatibility mode)")
    return AuthResult(True, "skipped",
                      "No auth credentials in request (compatibility mode)")
