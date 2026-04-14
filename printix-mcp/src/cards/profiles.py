BUILTIN_PROFILES = [
    {
        "name": "Plain Base64",
        "vendor": "Generic",
        "reader_model": "Any",
        "mode": "text",
        "description": "Encode visible text card value as Base64.",
        "rules_json": {
            "strip_separators": False,
            "input_mode": "text",
            "submit_mode": "base64_text",
        },
    },
    {
        "name": "Cleanup + Base64",
        "vendor": "Generic",
        "reader_model": "Any",
        "mode": "cleanup",
        "description": "Remove separators and encode cleaned value as Base64.",
        "rules_json": {
            "strip_separators": True,
            "input_mode": "text",
            "submit_mode": "base64_text",
        },
    },
    {
        "name": "HEX / Decimal Helper",
        "vendor": "Generic",
        "reader_model": "Any",
        "mode": "helper",
        "description": "Use for reader output shown as hex bytes or decimal values.",
        "rules_json": {
            "strip_separators": True,
            "input_mode": "auto",
            "submit_mode": "raw",
        },
    },
    {
        "name": "YSoft Decimal Reversed",
        "vendor": "YSoft",
        "reader_model": "Any",
        "mode": "decimal_reversed",
        "description": "Interpret input as hex/decimal and send decimal of reversed hex bytes.",
        "rules_json": {
            "strip_separators": True,
            "input_mode": "auto",
            "submit_mode": "decimal_reversed",
        },
    },
    {
        "name": "Lowercase + Base64",
        "vendor": "Generic",
        "reader_model": "Any",
        "mode": "lowercase_base64",
        "description": "Lowercase the visible value first, then Base64 encode it.",
        "rules_json": {
            "strip_separators": False,
            "input_mode": "text",
            "submit_mode": "base64_text",
            "lowercase": True,
        },
    },
    {
        "name": "Double Base64",
        "vendor": "Generic",
        "reader_model": "Any",
        "mode": "double_base64",
        "description": "For workflows that expect Base64 of a Base64 text value.",
        "rules_json": {
            "strip_separators": False,
            "input_mode": "text",
            "submit_mode": "base64_text",
            "double_base64": True,
        },
    },
]
def get_builtin_profiles():
    return BUILTIN_PROFILES
