import base64
import json
import re
from typing import Any, Optional

SEP_RE = re.compile(r"[\s:\-]")
HEX_RE = re.compile(r"^[0-9a-fA-F]+$")


def is_base64(value: str) -> bool:
    if not value or len(value) < 4 or len(value) % 4 != 0:
        return False
    try:
        return base64.b64encode(base64.b64decode(value)).decode() == value
    except Exception:
        return False


def b64_text(value: str) -> str:
    return base64.b64encode((value or '').encode('utf-8')).decode('ascii')


def try_b64_decode(value: str) -> str:
    if not is_base64(value):
        return ''
    try:
        dec = base64.b64decode(value).decode('utf-8')
    except Exception:
        return ''
    if not dec:
        return ''
    printable = sum(1 for c in dec if 32 <= ord(c) <= 126 or c in '\r\n\t')
    if printable / max(len(dec), 1) < 0.9:
        return ''
    return dec


def apply_profile_rules(raw: str, rules: dict[str, Any] | None = None) -> dict[str, Any]:
    rules = rules or {}
    value = (raw or '').strip()
    original = value
    prefix = rules.get('trim_prefix', '') or ''
    suffix = rules.get('trim_suffix', '') or ''
    if prefix and value.startswith(prefix):
        value = value[len(prefix):]
    if suffix and value.endswith(suffix):
        value = value[:-len(suffix)]
    if rules.get('strip_separators', True):
        value = SEP_RE.sub('', value)
    if rules.get('to_lower'):
        value = value.lower()
    if rules.get('to_upper'):
        value = value.upper()
    leading = rules.get('leading_zero_mode', 'keep')
    if leading == 'strip':
        value = value.lstrip('0') or '0'
    elif leading == 'force_one':
        value = '0' + (value.lstrip('0') or '0')

    mode = rules.get('input_mode', 'auto')
    detected_mode = mode
    if mode == 'auto':
        if value.isdigit():
            detected_mode = 'decimal'
        elif HEX_RE.match(value or ''):
            detected_mode = 'hex'
        else:
            detected_mode = 'text'

    hex_value = ''
    decimal_value = ''
    if detected_mode == 'decimal' and value.isdigit():
        decimal_value = value
        hex_value = format(int(value), 'x').upper()
        if rules.get('pad_even_hex', True) and len(hex_value) % 2:
            hex_value = '0' + hex_value
    elif detected_mode == 'hex' and HEX_RE.match(value or ''):
        hex_value = value.upper()
        if rules.get('pad_even_hex', True) and len(hex_value) % 2:
            hex_value = '0' + hex_value
        try:
            decimal_value = str(int(hex_value, 16)) if hex_value else ''
        except Exception:
            decimal_value = ''

    reversed_hex = ''
    reversed_decimal = ''
    if hex_value and len(hex_value) % 2 == 0:
        reversed_hex = ''.join(reversed([hex_value[i:i+2] for i in range(0, len(hex_value), 2)]))
        try:
            reversed_decimal = str(int(reversed_hex, 16)) if reversed_hex else ''
        except Exception:
            reversed_decimal = ''

    submit_mode = rules.get('submit_mode', 'raw')
    final_value = original
    if submit_mode == 'normalized':
        final_value = value
    elif submit_mode == 'hex':
        final_value = hex_value or value
    elif submit_mode == 'hex_reversed':
        final_value = reversed_hex or value
    elif submit_mode == 'decimal':
        final_value = decimal_value or value
    elif submit_mode == 'decimal_reversed':
        final_value = reversed_decimal or value
    elif submit_mode == 'base64_text':
        final_value = b64_text(original)
    elif submit_mode == 'double_base64':
        final_value = b64_text(b64_text(original))

    base64_value = b64_text(original) if original else ''
    return {
        'raw_value': original,
        'normalized_value': value,
        'detected_mode': detected_mode,
        'hex_value': hex_value,
        'hex_reversed': reversed_hex,
        'decimal_value': decimal_value,
        'decimal_reversed': reversed_decimal,
        'base64_value': base64_value,
        'final_value': final_value,
        'rules': rules,
    }


def generate_lookup_candidates(value: str) -> list[str]:
    raw = (value or '').strip()
    if not raw:
        return []
    out: list[str] = []
    def add(v: Optional[str]):
        if v and v not in out:
            out.append(v)
    add(raw)
    normalized = SEP_RE.sub('', raw)
    add(normalized)
    stripped = normalized.lstrip('0') or '0'
    add(stripped)
    add('0' + stripped)
    decoded = try_b64_decode(raw)
    add(decoded)
    if decoded:
        dnorm = SEP_RE.sub('', decoded)
        add(dnorm)
        add(dnorm.lstrip('0') or '0')
        add('0' + (dnorm.lstrip('0') or '0'))
    for item in list(out):
        add(b64_text(item))
    return out


def decode_card_value_for_display(card: dict[str, Any]) -> tuple[str, str, str]:
    cid = card.get('card_id') or card.get('id', '')
    raw = card.get('secret') or card.get('cardNumber') or card.get('number') or ''
    decoded = try_b64_decode(raw)
    if decoded:
        return decoded, raw, 'decoded_from_printix_secret'
    if raw:
        return raw, raw, 'raw_printix_secret'
    return '', '', 'id_only'


def build_mapping_record(tenant_id: str, printix_user_id: str, printix_card_id: str, raw_value: str, profile_id: str = '', source: str = 'manual', rules: dict[str, Any] | None = None, notes: str = '') -> dict[str, Any]:
    preview = apply_profile_rules(raw_value, rules)
    candidates = generate_lookup_candidates(preview['final_value'] or preview['raw_value'])
    return {
        'tenant_id': tenant_id,
        'printix_user_id': printix_user_id,
        'printix_card_id': printix_card_id,
        'profile_id': profile_id,
        'raw_value': preview['raw_value'],
        'display_value': preview['raw_value'],
        'normalized_value': preview['normalized_value'],
        'hex_value': preview['hex_value'],
        'decimal_value': preview['decimal_value'],
        'base64_value': preview['base64_value'],
        'final_secret_value': preview['final_value'],
        'lookup_candidates_json': json.dumps(candidates, ensure_ascii=False),
        'source': source,
        'notes': notes,
        'meta_json': json.dumps(preview, ensure_ascii=False),
    }


def transform_preview(raw_value: str, rules: dict[str, Any] | None = None) -> dict[str, Any]:
    preview = apply_profile_rules(raw_value, rules)
    preview['lookup_candidates'] = generate_lookup_candidates(preview['final_value'] or preview['raw_value'])
    return preview
