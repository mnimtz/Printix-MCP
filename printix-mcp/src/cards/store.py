import json
import sqlite3
from typing import List, Optional
from db import _conn, _enc, _dec, _now

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
        # safe migrations for search helper columns
        existing = {r[1] for r in conn.execute("PRAGMA table_info(card_mappings)").fetchall()}
        if "search_blob" not in existing:
            conn.execute("ALTER TABLE card_mappings ADD COLUMN search_blob TEXT NOT NULL DEFAULT ''")

def _mapping_public(row):
    if not row:
        return None
    data=dict(row)
    data["local_value"]=_dec(data.get("local_value",""))
    data["final_value"]=_dec(data.get("final_value",""))
    return data

def list_profiles(tenant_id: str):
    init_cards_tables()
    with _conn() as conn:
        rows=conn.execute(
            "SELECT * FROM card_profiles WHERE tenant_id IN ('', ?) ORDER BY is_builtin DESC, vendor, name",
            (tenant_id,)
        ).fetchall()
    return [dict(r) for r in rows]

def upsert_profile(tenant_id: str, name: str, vendor: str, reader_model: str, mode: str, description: str, rules_json: str):
    init_cards_tables()
    now=_now()
    import uuid
    pid=str(uuid.uuid4())
    with _conn() as conn:
        conn.execute(
            "INSERT INTO card_profiles (id, tenant_id, name, vendor, reader_model, mode, description, rules_json, is_builtin, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,0,?,?)",
            (pid, tenant_id, name, vendor, reader_model, mode, description, rules_json, now, now),
        )
    return pid

def delete_profile(profile_id: str, tenant_id: str):
    with _conn() as conn:
        conn.execute("DELETE FROM card_profiles WHERE id=? AND tenant_id=? AND is_builtin=0", (profile_id, tenant_id))

def save_mapping(tenant_id: str, printix_user_id: str, printix_card_id: str, local_value: str, final_value: str, normalized_value: str, source: str, notes: str):
    init_cards_tables()
    now=_now()
    search_blob = " | ".join([printix_user_id or "", printix_card_id or "", local_value or "", final_value or "", normalized_value or ""]).lower()
    with _conn() as conn:
        row = conn.execute(
            "SELECT id FROM card_mappings WHERE tenant_id=? AND printix_user_id=? AND printix_card_id=?",
            (tenant_id, printix_user_id or "", printix_card_id or "")
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE card_mappings SET local_value=?, final_value=?, normalized_value=?, source=?, notes=?, updated_at=?, search_blob=? WHERE id=?",
                (_enc(local_value), _enc(final_value), normalized_value, source, notes, now, search_blob, row["id"])
            )
            return row["id"]
        conn.execute(
            "INSERT INTO card_mappings (tenant_id, printix_user_id, printix_card_id, local_value, final_value, normalized_value, source, notes, created_at, updated_at, search_blob) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (tenant_id, printix_user_id or "", printix_card_id or "", _enc(local_value), _enc(final_value), normalized_value, source, notes, now, now, search_blob)
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

def get_mapping_by_card(tenant_id: str, printix_user_id: str, printix_card_id: str):
    init_cards_tables()
    with _conn() as conn:
        row=conn.execute(
            "SELECT * FROM card_mappings WHERE tenant_id=? AND printix_user_id=? AND printix_card_id=? ORDER BY id DESC LIMIT 1",
            (tenant_id, printix_user_id or "", printix_card_id or "")
        ).fetchone()
    return _mapping_public(row)

def search_mappings(tenant_id: str, q: str):
    init_cards_tables()
    q=(q or "").strip().lower()
    with _conn() as conn:
        if q:
            rows=conn.execute(
                "SELECT * FROM card_mappings WHERE tenant_id=? AND search_blob LIKE ? ORDER BY updated_at DESC LIMIT 100",
                (tenant_id, f"%{q}%")
            ).fetchall()
        else:
            rows=conn.execute(
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
