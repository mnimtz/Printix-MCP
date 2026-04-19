import base64
import json
import re

def _safe_b64_text(s: str) -> str:
    try:
        return base64.b64encode((s or "").encode("utf-8")).decode("ascii")
    except Exception:
        return ""

def _safe_b64_bytes(data: bytes) -> str:
    try:
        return base64.b64encode(data or b"").decode("ascii")
    except Exception:
        return ""

def decode_printix_secret_value(secret_value: str) -> dict:
    result = {
        "secret_value": secret_value or "",
        "decoded_text": "",
        "decoded_bytes_hex": "",
        "profile_hint": "",
    }
    if not secret_value:
        return result
    try:
        raw_bytes = base64.b64decode(secret_value, validate=True)
    except Exception:
        return result

    result["decoded_bytes_hex"] = raw_bytes.hex().upper()
    if not raw_bytes:
        return result

    # Straight ASCII / keyboard-style readers
    if all(32 <= b <= 126 for b in raw_bytes):
        result["decoded_text"] = raw_bytes.decode("ascii", errors="ignore")
        return result

    # YSoft / Konica workflows append literal FF bytes after the visible ASCII value
    stripped = raw_bytes.rstrip(b"\xff")
    suffix = raw_bytes[len(stripped):]
    if stripped and suffix and all(32 <= b <= 126 for b in stripped) and set(suffix) == {0xFF}:
        result["decoded_text"] = stripped.decode("ascii", errors="ignore")
        result["profile_hint"] = "builtin-ysoft-konica-mifare"
        return result

    return result

def _hex_to_decimal(hex_value: str) -> str:
    try:
        return str(int(hex_value, 16)) if hex_value else ""
    except Exception:
        return ""

def _decimal_to_hex(dec_value: str, pad_even: bool = True) -> str:
    try:
        if not dec_value:
            return ""
        hex_value = format(int(dec_value), "x").upper()
        if pad_even and len(hex_value) % 2:
            hex_value = "0" + hex_value
        return hex_value
    except Exception:
        return ""

def _reverse_hex_bytes(hex_value: str) -> str:
    if not hex_value or len(hex_value) % 2:
        return ""
    parts = [hex_value[i:i+2] for i in range(0, len(hex_value), 2)]
    return "".join(reversed(parts))

def _normalize_replace_map(replace_map):
    if not replace_map:
        return {}
    if isinstance(replace_map, dict):
        return {str(k): str(v) for k, v in replace_map.items()}
    if isinstance(replace_map, str):
        try:
            parsed = json.loads(replace_map)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items()}
        except Exception:
            return {}
    return {}

def _normalize_remove_chars(remove_chars):
    if not remove_chars:
        return ""
    if isinstance(remove_chars, list):
        return "".join(str(v) for v in remove_chars if v)
    return str(remove_chars)

def _apply_char_removals(value: str, remove_chars) -> str:
    chars = _normalize_remove_chars(remove_chars)
    if not chars:
        return value
    return "".join(ch for ch in value if ch not in chars)

def _build_base64_source_bytes(source_value: str, byte_suffix_hex: str = "", byte_suffix_count: int = 0, encoding: str = "utf-8") -> bytes:
    base_value = source_value or ""
    try:
        if encoding == "latin-1":
            data = base_value.encode("latin-1", errors="ignore")
        else:
            data = base_value.encode("utf-8")
    except Exception:
        data = b""

    suffix_hex = (byte_suffix_hex or "").strip().replace(" ", "")
    if suffix_hex:
        try:
            suffix = bytes.fromhex(suffix_hex)
            if suffix:
                data += suffix * max(0, int(byte_suffix_count or 0))
        except Exception:
            pass
    return data

def transform_card_value(
    raw_value: str,
    strip_separators: bool = True,
    remove_chars = "",
    replace_map = None,
    trim_prefix: str = "",
    trim_suffix: str = "",
    prepend_text: str = "",
    append_text: str = "",
    append_char: str = "",
    append_count: int = 0,
    leading_zero_mode: str = "keep",
    input_mode: str = "auto",
    submit_mode: str = "raw",
    base64_source: str = "raw",
    pad_even_hex: bool = True,
    lowercase: bool = False,
    double_base64: bool = False,
    base64_encoding: str = "utf-8",
    base64_suffix_hex: str = "",
    base64_suffix_count: int = 0,
):
    raw = (raw_value or "").strip()
    normalized = raw
    replace_rules = _normalize_replace_map(replace_map)

    if trim_prefix and normalized.startswith(trim_prefix):
        normalized = normalized[len(trim_prefix):]
    if trim_suffix and normalized.endswith(trim_suffix):
        normalized = normalized[:-len(trim_suffix)]

    for old, new in replace_rules.items():
        normalized = normalized.replace(old, new)

    if strip_separators:
        normalized = re.sub(r"[\s:\-]", "", normalized)

    normalized = _apply_char_removals(normalized, remove_chars)

    if lowercase:
        normalized = normalized.lower()

    if leading_zero_mode == "strip":
        normalized = normalized.lstrip("0") or "0"
    elif leading_zero_mode == "force_one":
        normalized = "0" + (normalized.lstrip("0") or "0")

    working_value = f"{prepend_text or ''}{normalized}{append_text or ''}"
    if append_char and append_count:
        try:
            working_value += str(append_char) * max(0, int(append_count))
        except Exception:
            pass

    mode = input_mode
    if mode == "auto":
        if re.fullmatch(r"\d+", working_value or ""):
            mode = "decimal"
        elif re.fullmatch(r"[0-9A-Fa-f]+", working_value or ""):
            mode = "hex"
        else:
            mode = "text"

    hex_value = ""
    decimal_value = ""
    if mode == "hex":
        hex_value = working_value.upper()
        if pad_even_hex and hex_value and len(hex_value) % 2:
            hex_value = "0" + hex_value
        decimal_value = _hex_to_decimal(hex_value)
    elif mode == "decimal":
        decimal_value = working_value
        hex_value = _decimal_to_hex(decimal_value, pad_even_hex)
    else:
        if re.fullmatch(r"[0-9A-Fa-f]+", working_value or ""):
            hex_value = working_value.upper()
            if pad_even_hex and hex_value and len(hex_value) % 2:
                hex_value = "0" + hex_value
            decimal_value = _hex_to_decimal(hex_value)

    hex_reversed = _reverse_hex_bytes(hex_value)
    decimal_reversed = _hex_to_decimal(hex_reversed)
    base64_candidates = {
        "raw": raw,
        "normalized": normalized,
        "working": working_value,
        "hex": hex_value,
        "hex_reversed": hex_reversed,
        "decimal": decimal_value,
        "decimal_reversed": decimal_reversed,
    }
    base64_input_value = base64_candidates.get(base64_source or "raw", raw)
    base64_bytes = _build_base64_source_bytes(
        base64_input_value,
        byte_suffix_hex=base64_suffix_hex,
        byte_suffix_count=base64_suffix_count,
        encoding=base64_encoding or "utf-8",
    )
    base64_text = _safe_b64_bytes(base64_bytes)
    if double_base64 and base64_text:
        base64_text = _safe_b64_text(base64_text)

    final_value = raw
    if submit_mode == "normalized":
        final_value = normalized
    elif submit_mode == "working":
        final_value = working_value
    elif submit_mode == "hex":
        final_value = hex_value
    elif submit_mode == "hex_reversed":
        final_value = hex_reversed
    elif submit_mode == "decimal":
        final_value = decimal_value
    elif submit_mode == "decimal_reversed":
        final_value = decimal_reversed
    elif submit_mode == "base64_text":
        final_value = base64_text

    return {
        "raw": raw,
        "normalized": normalized,
        "working": working_value,
        "hex": hex_value,
        "hex_reversed": hex_reversed,
        "decimal": decimal_value,
        "decimal_reversed": decimal_reversed,
        "base64_text": base64_text,
        "base64_source_value": base64_input_value,
        "base64_source_bytes_hex": base64_bytes.hex().upper(),
        "final_submit_value": final_value,
        "input_mode_resolved": mode,
    }
