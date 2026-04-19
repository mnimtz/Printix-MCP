import base64
import json
import re
from db import _conn, _enc, _dec, _now

def _is_base64_like(value: str) -> bool:
    try:
        if not value:
            return False
        return base64.b64encode(base64.b64decode(value)).decode() == value
    except Exception:
        return False

def _build_mapping_preview(local_value: str, final_value: str, normalized_value: str, preview: dict | None = None, printix_secret_value: str = ""):
    preview = dict(preview or {})
    preview.setdefault("raw", local_value or "")
    preview.setdefault("normalized", normalized_value or preview.get("raw", ""))
    preview.setdefault("final_submit_value", final_value or preview.get("normalized", ""))
    preview.setdefault("base64_text", _safe_b64(preview.get("raw", "")))
    preview["printix_secret_value"] = printix_secret_value or (
        preview.get("final_submit_value", "") if _is_base64_like(preview.get("final_submit_value", "")) else _safe_b64(preview.get("final_submit_value", ""))
    )
    return preview


def init_cards_tables():
    with _conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS card_profiles (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            vendor TEXT NOT NULL DEFAULT '',
            reader_model TEXT NOT NULL DEFAULT '',
            mode TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            rules_json TEXT NOT NULL DEFAULT '{}',
            is_builtin INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_card_profiles_tenant ON card_profiles (tenant_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS card_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            printix_user_id TEXT NOT NULL DEFAULT '',
            printix_card_id TEXT NOT NULL DEFAULT '',
            local_value TEXT NOT NULL DEFAULT '',
            final_value TEXT NOT NULL DEFAULT '',
            normalized_value TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'cards_tool',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_card_mappings_tenant ON card_mappings (tenant_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_card_mappings_user ON card_mappings (tenant_id, printix_user_id);
        CREATE INDEX IF NOT EXISTS idx_card_mappings_card ON card_mappings (tenant_id, printix_card_id);
        """)

        existing = {r[1] for r in conn.execute("PRAGMA table_info(card_mappings)").fetchall()}
        wanted_columns = {
            "printix_user_id": "TEXT NOT NULL DEFAULT ''",
            "printix_card_id": "TEXT NOT NULL DEFAULT ''",
            "local_value": "TEXT NOT NULL DEFAULT ''",
            "final_value": "TEXT NOT NULL DEFAULT ''",
            "normalized_value": "TEXT NOT NULL DEFAULT ''",
            "source": "TEXT NOT NULL DEFAULT 'cards_tool'",
            "notes": "TEXT NOT NULL DEFAULT ''",
            "updated_at": "TEXT NOT NULL DEFAULT ''",
            "profile_id": "TEXT NOT NULL DEFAULT ''",
            "search_blob": "TEXT NOT NULL DEFAULT ''",
            "preview_json": "TEXT NOT NULL DEFAULT ''",
            "printix_secret_value": "TEXT NOT NULL DEFAULT ''",
        }
        for col, ddl in wanted_columns.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE card_mappings ADD COLUMN {col} {ddl}")


def _mapping_public(row):
    if not row:
        return None
    data = dict(row)
    local_value = _dec(data.get("local_value", ""))
    final_value = _dec(data.get("final_value", ""))
    preview_json = _dec(data.get("preview_json", ""))
    printix_secret_value = _dec(data.get("printix_secret_value", ""))
    data["local_value"] = local_value
    data["final_value"] = final_value
    preview = {}
    if preview_json:
        try:
            preview = json.loads(preview_json)
        except Exception:
            preview = {}
    preview = _build_mapping_preview(local_value, final_value, data.get("normalized_value", ""), preview, printix_secret_value)
    data["preview"] = preview
    data["raw_value"] = local_value
    data["display_value"] = local_value
    data["final_secret_value"] = final_value
    data["base64_value"] = _safe_b64(local_value)
    data["printix_secret_value"] = preview.get("printix_secret_value", "")
    data["working_value"] = preview.get("working", "")
    data["hex_value"] = preview.get("hex", "")
    data["hex_reversed_value"] = preview.get("hex_reversed", "")
    data["decimal_value"] = preview.get("decimal", "")
    data["decimal_reversed_value"] = preview.get("decimal_reversed", "")
    data["base64_source_bytes_hex"] = preview.get("base64_source_bytes_hex", "")
    return data


def _safe_b64(value: str) -> str:
    try:
        return base64.b64encode((value or "").encode("utf-8")).decode("ascii") if value else ""
    except Exception:
        return ""


def _search_candidates(q: str):
    q = (q or "").strip()
    if not q:
        return []
    out = []

    def add(v):
        if v and v not in out:
            out.append(v)

    add(q)
    norm = re.sub(r"[\s:\-]", "", q)
    add(norm)
    stripped = norm.lstrip("0") or "0"
    add(stripped)
    add("0" + stripped)
    for item in list(out):
        add(_safe_b64(item))
    return [v.lower() for v in out]


def list_profiles(tenant_id: str):
    init_cards_tables()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM card_profiles WHERE tenant_id IN ('', ?) ORDER BY is_builtin DESC, vendor, name",
            (tenant_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_profile(profile_id: str, tenant_id: str):
    init_cards_tables()
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM card_profiles WHERE id=? AND tenant_id IN ('', ?)",
            (profile_id, tenant_id)
        ).fetchone()
    return dict(row) if row else None


def upsert_profile(tenant_id: str, name: str, vendor: str, reader_model: str, mode: str, description: str, rules_json: str, profile_id: str = ""):
    init_cards_tables()
    now = _now()
    import uuid

    rules_json = (rules_json or "{}").strip() or "{}"
    try:
        parsed = json.loads(rules_json)
        if not isinstance(parsed, dict):
            parsed = {}
        rules_json = json.dumps(parsed, ensure_ascii=False)
    except Exception:
        rules_json = "{}"

    with _conn() as conn:
        if profile_id:
            existing = conn.execute(
                "SELECT id FROM card_profiles WHERE id=? AND tenant_id=? AND is_builtin=0",
                (profile_id, tenant_id),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE card_profiles SET name=?, vendor=?, reader_model=?, mode=?, description=?, rules_json=?, updated_at=? WHERE id=? AND tenant_id=? AND is_builtin=0",
                    (name, vendor, reader_model, mode, description, rules_json, now, profile_id, tenant_id),
                )
                return profile_id

        pid = profile_id or str(uuid.uuid4())
        conn.execute(
            "INSERT INTO card_profiles (id, tenant_id, name, vendor, reader_model, mode, description, rules_json, is_builtin, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,0,?,?)",
            (pid, tenant_id, name, vendor, reader_model, mode, description, rules_json, now, now),
        )
    return pid


def delete_profile(profile_id: str, tenant_id: str):
    with _conn() as conn:
        conn.execute("DELETE FROM card_profiles WHERE id=? AND tenant_id=? AND is_builtin=0", (profile_id, tenant_id))


def save_mapping(tenant_id: str, printix_user_id: str, printix_card_id: str, local_value: str, final_value: str, normalized_value: str, source: str, notes: str, profile_id: str = "", preview: dict | None = None, printix_secret_value: str = ""):
    init_cards_tables()
    now = _now()
    preview_data = _build_mapping_preview(local_value, final_value, normalized_value, preview, printix_secret_value)
    preview_json = json.dumps(preview_data, ensure_ascii=False, sort_keys=True)
    pieces = [
        printix_user_id or "",
        printix_card_id or "",
        local_value or "",
        final_value or "",
        normalized_value or "",
        profile_id or "",
        preview_data.get("working", "") or "",
        preview_data.get("hex", "") or "",
        preview_data.get("hex_reversed", "") or "",
        preview_data.get("decimal", "") or "",
        preview_data.get("decimal_reversed", "") or "",
        preview_data.get("printix_secret_value", "") or "",
    ]
    for v in _search_candidates(local_value):
        pieces.append(v)
    for v in _search_candidates(final_value):
        pieces.append(v)
    for key in ("working", "hex", "hex_reversed", "decimal", "decimal_reversed", "printix_secret_value"):
        for v in _search_candidates(preview_data.get(key, "")):
            pieces.append(v)
    search_blob = " | ".join([p for p in pieces if p]).lower()

    with _conn() as conn:
        row = conn.execute(
            "SELECT id FROM card_mappings WHERE tenant_id=? AND printix_user_id=? AND printix_card_id=?",
            (tenant_id, printix_user_id or "", printix_card_id or "")
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE card_mappings SET local_value=?, final_value=?, normalized_value=?, source=?, notes=?, profile_id=?, updated_at=?, search_blob=?, preview_json=?, printix_secret_value=? WHERE id=?",
                (_enc(local_value), _enc(final_value), normalized_value, source, notes, profile_id or "", now, search_blob, _enc(preview_json), _enc(preview_data.get("printix_secret_value", "")), row["id"])
            )
            return row["id"]

        conn.execute(
            "INSERT INTO card_mappings (tenant_id, printix_user_id, printix_card_id, local_value, final_value, normalized_value, source, notes, profile_id, created_at, updated_at, search_blob, preview_json, printix_secret_value) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tenant_id, printix_user_id or "", printix_card_id or "", _enc(local_value), _enc(final_value), normalized_value, source, notes, profile_id or "", now, now, search_blob, _enc(preview_json), _enc(preview_data.get("printix_secret_value", "")))
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_mapping_by_card(tenant_id: str, printix_user_id: str, printix_card_id: str):
    init_cards_tables()
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM card_mappings WHERE tenant_id=? AND printix_user_id=? AND printix_card_id=? ORDER BY id DESC LIMIT 1",
            (tenant_id, printix_user_id or "", printix_card_id or "")
        ).fetchone()
    return _mapping_public(row)


def search_mappings(tenant_id: str, q: str):
    init_cards_tables()
    q = (q or "").strip().lower()
    candidates = _search_candidates(q)
    with _conn() as conn:
        if q:
            rows = conn.execute(
                "SELECT * FROM card_mappings WHERE tenant_id=? ORDER BY updated_at DESC LIMIT 500",
                (tenant_id,)
            ).fetchall()
            results = []
            for r in rows:
                blob = (r["search_blob"] or "").lower()
                if q in blob or any(c in blob for c in candidates):
                    results.append(r)
            rows = results[:100]
        else:
            rows = conn.execute(
                "SELECT * FROM card_mappings WHERE tenant_id=? ORDER BY updated_at DESC LIMIT 100",
                (tenant_id,)
            ).fetchall()
    return [_mapping_public(r) for r in rows]


def delete_mapping(mapping_id: int, tenant_id: str):
    with _conn() as conn:
        conn.execute("DELETE FROM card_mappings WHERE id=? AND tenant_id=?", (mapping_id, tenant_id))


def delete_mappings_for_user(tenant_id: str, printix_user_id: str):
    with _conn() as conn:
        conn.execute("DELETE FROM card_mappings WHERE tenant_id=? AND printix_user_id=?", (tenant_id, printix_user_id))
