"""
Capture Authentication — Multi-Method Verification (v4.6.1)
===========================================================
Supports the Printix/Tungsten Capture Connector authentication model:

1. Printix Native Signature (x-printix-signature)
   — The REAL header Printix sends, paired with x-printix-timestamp
     and x-printix-request-path. Signature computed over canonical string,
     result encoded as Base64. Secret may be raw UTF-8 or Base64-encoded.
2. HMAC Signature (x-printix-signature-256 / x-printix-signature-512)
   — Body-only HMAC, multiple secrets for key rotation
3. Hub Signature (x-hub-signature-256)
   — GitHub-style webhook signature
4. Connector Token (Authorization: Bearer <token> / x-connector-token)
   — Multiple tokens per profile for rotation
5. require_signature flag per profile
   — Enforces that at least one auth method must succeed

Headers checked (in priority order):
  x-printix-signature          — Printix native
  x-printix-signature-256      — HMAC-SHA256 (body only)
  x-printix-signature-512      — HMAC-SHA512 (body only)
  x-hub-signature-256          — Generic webhook signature (GitHub-style)
  authorization                — Bearer token
  x-connector-token            — Alternative connector token header

Companion headers (used in canonical string):
  x-printix-timestamp          — Unix timestamp
  x-printix-request-path       — Original request path
  x-printix-request-id         — Request correlation ID
"""

import base64
import hashlib
import hmac as _hmac
import logging
from dataclasses import dataclass

logger = logging.getLogger("printix.capture.auth")


@dataclass
class AuthResult:
    """Result of capture request authentication."""
    success: bool
    method: str = ""
    detail: str = ""
    secret_index: int = -1


def _strip_prefix(sig: str) -> str:
    """Remove optional prefix like 'sha256=' or 'sha512='."""
    for prefix in ("sha256=", "sha512=", "SHA256=", "SHA512="):
        if sig.startswith(prefix):
            return sig[len(prefix):]
    return sig


def _parse_multi(value: str) -> list[str]:
    """Parse multi-value field (newline-separated) into list of non-empty strings."""
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


def _get_key_variants(secret: str) -> list[tuple[bytes, str]]:
    """
    Get all plausible key byte representations for a secret string.
    Returns list of (key_bytes, description).

    Many webhook APIs store the shared secret as Base64. The raw bytes
    obtained by decoding are then used as HMAC key. We try both:
      1. Raw UTF-8 bytes of the secret string
      2. Base64-decoded bytes (if valid Base64)
    """
    variants: list[tuple[bytes, str]] = []

    # 1. Raw UTF-8 (most common for simple secrets)
    variants.append((secret.encode("utf-8"), "utf8"))

    # 2. Base64-decoded (common for Azure/Tungsten APIs)
    try:
        decoded = base64.b64decode(secret)
        # Only use if it actually decoded to something different
        if decoded != secret.encode("utf-8"):
            variants.append((decoded, "b64dec"))
    except Exception:
        pass

    # 3. Base64 URL-safe decoded
    try:
        decoded = base64.urlsafe_b64decode(secret)
        if decoded != secret.encode("utf-8"):
            # Avoid duplicate if same as standard b64
            existing = [v[0] for v in variants]
            if decoded not in existing:
                variants.append((decoded, "b64url_dec"))
    except Exception:
        pass

    return variants


def _compare_sig(expected_bytes: bytes, received_str: str) -> tuple[bool, str]:
    """
    Compare HMAC digest bytes against received signature string.
    Tries Base64 and hex encodings.
    Returns (matched, encoding_name).
    """
    received = _strip_prefix(received_str)

    # Base64 standard (case-sensitive)
    expected_b64 = base64.b64encode(expected_bytes).decode("ascii")
    if _hmac.compare_digest(received, expected_b64):
        return True, "base64"

    # Base64 with/without padding
    expected_b64_nopad = expected_b64.rstrip("=")
    received_nopad = received.rstrip("=")
    if _hmac.compare_digest(received_nopad, expected_b64_nopad):
        return True, "base64-nopad"

    # Base64 URL-safe
    expected_b64url = base64.urlsafe_b64encode(expected_bytes).decode("ascii")
    if _hmac.compare_digest(received, expected_b64url):
        return True, "base64url"

    # Hex (case-insensitive)
    expected_hex = expected_bytes.hex()
    if _hmac.compare_digest(received.lower(), expected_hex.lower()):
        return True, "hex"

    return False, ""


def _try_printix_native(
    body_bytes: bytes,
    sig_value: str,
    secrets: list[str],
    timestamp: str,
    request_path: str,
    request_id: str,
) -> tuple[bool, int, str]:
    """
    Exhaustive Printix native signature verification.

    Tries all combinations of:
      - Key variants: raw UTF-8, Base64-decoded
      - Algorithms: SHA-256, SHA-1, SHA-512
      - Canonical formats: 10+ variants
      - Signature encodings: Base64, Base64-nopad, Base64url, hex

    Returns (matched, secret_index, description_of_match).
    """
    # All hash algorithms to try
    algos: list[tuple[str, type]] = [
        ("sha256", hashlib.sha256),
        ("sha1", hashlib.sha1),
        ("sha512", hashlib.sha512),
    ]

    # All canonical payload formats to try
    def _build_payloads() -> list[tuple[bytes, str]]:
        payloads: list[tuple[bytes, str]] = []

        ts = timestamp
        path = request_path
        rid = request_id

        if ts and path:
            # Dot-separated
            payloads.append((f"{ts}.{path}.".encode() + body_bytes, "ts.path.body(dot-trail)"))
            payloads.append((f"{ts}.{path}".encode() + body_bytes, "ts.path+body(dot-notrail)"))
            # No separator between parts
            payloads.append((f"{ts}{path}".encode() + body_bytes, "ts+path+body(nosep)"))
            # Newline-separated
            payloads.append((f"{ts}\n{path}\n".encode() + body_bytes, "ts\\npath\\nbody"))

        if ts:
            payloads.append((f"{ts}.".encode() + body_bytes, "ts.body(dot-trail)"))
            payloads.append((f"{ts}".encode() + body_bytes, "ts+body(nosep)"))
            payloads.append((f"{ts}\n".encode() + body_bytes, "ts\\nbody"))

        # Body only
        payloads.append((body_bytes, "body"))

        if ts and path and rid:
            # Include request ID
            payloads.append((f"{ts}.{path}.{rid}.".encode() + body_bytes, "ts.path.rid.body"))
            payloads.append((f"{ts}.{rid}.{path}.".encode() + body_bytes, "ts.rid.path.body"))

        if ts and path:
            # Path without leading slash
            path_clean = path.lstrip("/")
            payloads.append((f"{ts}.{path_clean}.".encode() + body_bytes, "ts.path_noslash.body"))

        return payloads

    payloads = _build_payloads()

    for secret_idx, secret in enumerate(secrets):
        key_variants = _get_key_variants(secret)

        for key_bytes, key_desc in key_variants:
            for algo_name, algo in algos:
                for payload, fmt_desc in payloads:
                    mac = _hmac.new(key_bytes, payload, algo)
                    matched, enc = _compare_sig(mac.digest(), sig_value)
                    if matched:
                        desc = (f"key={key_desc}, algo={algo_name}, "
                                f"format={fmt_desc}, encoding={enc}")
                        return True, secret_idx, desc

    return False, -1, ""


def _debug_log_mismatch(
    body_bytes: bytes,
    sig_value: str,
    secrets: list[str],
    timestamp: str,
    request_path: str,
):
    """Log detailed debug info for signature mismatch diagnosis."""
    sig_stripped = _strip_prefix(sig_value)
    if not secrets:
        return

    secret = secrets[0]
    key_variants = _get_key_variants(secret)

    # Show key info (without revealing the full secret)
    for key_bytes, key_desc in key_variants:
        logger.debug("Auth debug: key_variant=%s key_len=%d key_preview=%s...",
                     key_desc, len(key_bytes), key_bytes[:4].hex())

    # Show top candidates
    core_formats = [
        ("ts.path.body", f"{timestamp}.{request_path}.".encode() + body_bytes),
        ("ts.body", f"{timestamp}.".encode() + body_bytes),
        ("body", body_bytes),
    ]
    for key_bytes, key_desc in key_variants:
        for fmt_name, payload in core_formats:
            for algo_name, algo in [("sha256", hashlib.sha256), ("sha1", hashlib.sha1)]:
                mac = _hmac.new(key_bytes, payload, algo)
                exp_b64 = base64.b64encode(mac.digest()).decode("ascii")
                logger.debug("Auth debug: key=%s algo=%s fmt=%s → %s...",
                             key_desc, algo_name, fmt_name, exp_b64[:24])

    logger.debug("Auth debug: received sig=%s...", sig_stripped[:24])


def verify_capture_auth(
    body_bytes: bytes,
    headers: dict[str, str],
    profile: dict,
) -> AuthResult:
    """
    Verify incoming Capture webhook request against profile auth settings.

    Supports (in priority order):
      1. x-printix-signature (Printix native — exhaustive format discovery)
      2. x-printix-signature-256 / x-hub-signature-256 (HMAC-SHA256, body only)
      3. x-printix-signature-512 (HMAC-SHA512, body only)
      4. Connector tokens via Authorization: Bearer / x-connector-token header
      5. require_signature enforcement per profile
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

            matched, idx, desc = _try_printix_native(
                body_bytes, sig_native, secrets, timestamp, request_path, request_id
            )
            if matched:
                detail = (f"Printix native signature verified "
                          f"(secret #{idx + 1}/{len(secrets)}, {desc})")
                logger.info("Auth: %s", detail)
                return AuthResult(True, "printix-native", detail, idx)

            # Mismatch — log exhaustive debug info
            n_keys = sum(len(_get_key_variants(s)) for s in secrets)
            logger.warning("Auth: Printix native signature mismatch "
                           "(tried %d secrets, %d key variants, 3 algos, 10+ formats, 4 encodings)",
                           len(secrets), n_keys)
            _debug_log_mismatch(body_bytes, sig_native, secrets, timestamp, request_path)

            return AuthResult(False, "printix-native",
                              f"Printix native signature mismatch "
                              f"(exhaustive: {len(secrets)} secrets, "
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

        # No signature header found
        if not has_tokens:
            if require_sig:
                logger.warning("Auth: No signature header found and require_signature=True. "
                               "Expected one of: x-printix-signature, x-printix-signature-256, "
                               "x-printix-signature-512, x-hub-signature-256")
                return AuthResult(False, "none",
                                  "No signature header in request (require_signature is enabled)")
            logger.warning("Auth: No signature header — allowing (compatibility mode)")
            return AuthResult(True, "skipped",
                              "No signature header but require_signature=False (compatibility mode)")

    # ── 2. Try Connector Token ──────────────────────────────────────────────
    if has_tokens:
        auth_header = headers.get("authorization", "")
        req_token = ""
        if auth_header.lower().startswith("bearer "):
            req_token = auth_header[7:].strip()
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

        if not has_secrets:
            if require_sig:
                return AuthResult(False, "none",
                                  "No connector token in request (require_signature is enabled)")
            return AuthResult(True, "skipped",
                              "No connector token but require_signature=False (compatibility mode)")

    # ── 3. Neither secrets nor tokens configured ────────────────────────────
    if not has_secrets and not has_tokens:
        if require_sig:
            return AuthResult(False, "none",
                              "require_signature enabled but no secrets or tokens configured")
        return AuthResult(True, "skipped", "No authentication configured on profile")

    # ── 4. Both configured but neither present in request ───────────────────
    if require_sig:
        return AuthResult(False, "none",
                          "No signature header or connector token in request")
    return AuthResult(True, "skipped",
                      "No auth credentials in request (compatibility mode)")
