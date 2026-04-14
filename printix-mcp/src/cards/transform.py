import base64
import re

def _safe_b64_text(s: str) -> str:
    try:
        return base64.b64encode((s or "").encode("utf-8")).decode("ascii")
    except Exception:
        return ""

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

def transform_card_value(
    raw_value: str,
    strip_separators: bool = True,
    trim_prefix: str = "",
    trim_suffix: str = "",
    leading_zero_mode: str = "keep",
    input_mode: str = "auto",
    submit_mode: str = "raw",
    pad_even_hex: bool = True,
    lowercase: bool = False,
):
    raw = (raw_value or "").strip()
    normalized = raw

    if trim_prefix and normalized.startswith(trim_prefix):
        normalized = normalized[len(trim_prefix):]
    if trim_suffix and normalized.endswith(trim_suffix):
        normalized = normalized[:-len(trim_suffix)]

    if strip_separators:
        normalized = re.sub(r"[\s:\-]", "", normalized)

    if lowercase:
        normalized = normalized.lower()

    if leading_zero_mode == "strip":
        normalized = normalized.lstrip("0") or "0"
    elif leading_zero_mode == "force_one":
        normalized = "0" + (normalized.lstrip("0") or "0")

    mode = input_mode
    if mode == "auto":
        if re.fullmatch(r"\d+", normalized or ""):
            mode = "decimal"
        elif re.fullmatch(r"[0-9A-Fa-f]+", normalized or ""):
            mode = "hex"
        else:
            mode = "text"

    hex_value = ""
    decimal_value = ""
    if mode == "hex":
        hex_value = normalized.upper()
        if pad_even_hex and hex_value and len(hex_value) % 2:
            hex_value = "0" + hex_value
        decimal_value = _hex_to_decimal(hex_value)
    elif mode == "decimal":
        decimal_value = normalized
        hex_value = _decimal_to_hex(decimal_value, pad_even_hex)
    else:
        if re.fullmatch(r"[0-9A-Fa-f]+", normalized or ""):
            hex_value = normalized.upper()
            if pad_even_hex and hex_value and len(hex_value) % 2:
                hex_value = "0" + hex_value
            decimal_value = _hex_to_decimal(hex_value)

    hex_reversed = _reverse_hex_bytes(hex_value)
    decimal_reversed = _hex_to_decimal(hex_reversed)
    base64_text = _safe_b64_text(raw)

    final_value = raw
    if submit_mode == "normalized":
        final_value = normalized
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
        "hex": hex_value,
        "hex_reversed": hex_reversed,
        "decimal": decimal_value,
        "decimal_reversed": decimal_reversed,
        "base64_text": base64_text,
        "final_submit_value": final_value,
        "input_mode_resolved": mode,
    }
