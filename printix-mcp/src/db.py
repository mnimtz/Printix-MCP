"""
Datenbank — SQLite Multi-Tenant Store für Printix MCP v2.0.0
=============================================================
Datei: /data/printix_multi.db (überlebt Add-on-Updates)

Schema:
  users     — Konten (username, password, status, is_admin)
  tenants   — Printix + SQL + Mail Credentials pro Benutzer (verschlüsselt)
  audit_log — Relevante Aktionen mit Zeitstempel

Alle Secrets (client_secrets, passwords, bearer_token) werden mit Fernet
verschlüsselt gespeichert. Der Schlüssel liegt in /data/fernet.key und wird
beim ersten Start generiert.
"""

import logging
import os
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "/data/printix_multi.db")


# ─── Datenbankverbindung ──────────────────────────────────────────────────────

@contextmanager
def _conn():
    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─── Schema ───────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Erstellt alle Tabellen beim ersten Start."""
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id           TEXT PRIMARY KEY,
                username     TEXT NOT NULL UNIQUE,
                email        TEXT NOT NULL DEFAULT '',
                password_hash TEXT NOT NULL,
                is_admin     INTEGER NOT NULL DEFAULT 0,
                status       TEXT NOT NULL DEFAULT 'pending',
                created_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tenants (
                id                   TEXT PRIMARY KEY,
                user_id              TEXT NOT NULL UNIQUE REFERENCES users(id),
                name                 TEXT NOT NULL DEFAULT '',

                -- Printix API (verschlüsselt)
                printix_tenant_id    TEXT NOT NULL DEFAULT '',
                print_client_id      TEXT NOT NULL DEFAULT '',
                print_client_secret  TEXT NOT NULL DEFAULT '',
                card_client_id       TEXT NOT NULL DEFAULT '',
                card_client_secret   TEXT NOT NULL DEFAULT '',
                ws_client_id         TEXT NOT NULL DEFAULT '',
                ws_client_secret     TEXT NOT NULL DEFAULT '',
                shared_client_id     TEXT NOT NULL DEFAULT '',
                shared_client_secret TEXT NOT NULL DEFAULT '',

                -- OAuth-Credentials (auto-generiert)
                oauth_client_id      TEXT NOT NULL UNIQUE,
                oauth_client_secret  TEXT NOT NULL,

                -- Bearer Token für MCP
                bearer_token         TEXT NOT NULL,

                -- SQL Reporting (optional, verschlüsselt)
                sql_server           TEXT NOT NULL DEFAULT '',
                sql_database         TEXT NOT NULL DEFAULT 'printix_bi_data_2_1',
                sql_username         TEXT NOT NULL DEFAULT '',
                sql_password         TEXT NOT NULL DEFAULT '',

                -- Mail (optional, verschlüsselt)
                mail_api_key         TEXT NOT NULL DEFAULT '',
                mail_from            TEXT NOT NULL DEFAULT '',

                created_at           TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT,
                action     TEXT NOT NULL,
                details    TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
        """)
    logger.info("DB initialisiert: %s", DB_PATH)


# ─── Crypto Helpers ───────────────────────────────────────────────────────────

def _enc(value: str) -> str:
    """Verschlüsselt einen String — leer bleibt leer."""
    if not value:
        return ""
    try:
        from crypto import encrypt
        return encrypt(value)
    except Exception:
        return value


def _dec(value: str) -> str:
    """Entschlüsselt einen String — leer bleibt leer."""
    if not value:
        return ""
    try:
        from crypto import decrypt
        return decrypt(value)
    except Exception:
        return value


# ─── Users ────────────────────────────────────────────────────────────────────

def has_users() -> bool:
    """True wenn mindestens ein Benutzer existiert."""
    with _conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        return count > 0


def username_exists(username: str) -> bool:
    with _conn() as conn:
        row = conn.execute("SELECT id FROM users WHERE username = ?",
                           (username.strip(),)).fetchone()
        return row is not None


def create_user(username: str, password: str, email: str = "", is_first: bool = False) -> dict:
    """
    Legt einen neuen Benutzer an.
    Erster Benutzer (is_first=True): Admin + automatisch genehmigt.
    Alle weiteren: pending (warten auf Admin-Freischaltung).
    """
    from crypto import hash_password
    uid = str(uuid.uuid4())
    now = _now()
    status = "approved" if is_first else "pending"
    is_admin = 1 if is_first else 0
    pw_hash = hash_password(password)
    with _conn() as conn:
        conn.execute(
            "INSERT INTO users (id, username, email, password_hash, is_admin, status, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (uid, username.strip(), email.strip(), pw_hash, is_admin, status, now),
        )
    return get_user_by_id(uid)


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Prüft Benutzername + Passwort, gibt User-Dict zurück oder None."""
    from crypto import verify_password
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?",
                           (username.strip(),)).fetchone()
    if not row:
        return None
    user = dict(row)
    if not verify_password(password, user["password_hash"]):
        return None
    return _user_public(user)


def get_user_by_id(user_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _user_public(dict(row)) if row else None


def get_all_users() -> list:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        return [_user_public(dict(r)) for r in rows]


def count_tenants() -> int:
    with _conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM tenants").fetchone()[0]


def set_user_status(user_id: str, status: str) -> None:
    with _conn() as conn:
        conn.execute("UPDATE users SET status=? WHERE id=?", (status, user_id))


def _user_public(user: dict) -> dict:
    """Gibt ein User-Dict ohne password_hash zurück."""
    return {
        "id":         user["id"],
        "username":   user["username"],
        "email":      user.get("email", ""),
        "is_admin":   bool(user["is_admin"]),
        "status":     user["status"],
        "created_at": user.get("created_at", ""),
    }


# ─── Tenants ──────────────────────────────────────────────────────────────────

def create_tenant(
    user_id: str,
    printix_tenant_id: str,
    name: str = "",
    print_client_id: str = "",
    print_client_secret: str = "",
    card_client_id: str = "",
    card_client_secret: str = "",
    ws_client_id: str = "",
    ws_client_secret: str = "",
    shared_client_id: str = "",
    shared_client_secret: str = "",
    sql_server: str = "",
    sql_database: str = "printix_bi_data_2_1",
    sql_username: str = "",
    sql_password: str = "",
    mail_api_key: str = "",
    mail_from: str = "",
) -> dict:
    """
    Legt einen Tenant-Datensatz an.
    Generiert automatisch: bearer_token, oauth_client_id, oauth_client_secret.
    Gibt ein Dict mit Klartextwerten zurück (einmaliger Zugriff!).
    """
    tid = str(uuid.uuid4())
    now = _now()
    bearer_plain = secrets.token_urlsafe(48)
    oauth_id = "px-" + secrets.token_hex(8)
    oauth_secret_plain = secrets.token_urlsafe(32)

    with _conn() as conn:
        conn.execute("""
            INSERT INTO tenants (
              id, user_id, name,
              printix_tenant_id,
              print_client_id, print_client_secret,
              card_client_id,  card_client_secret,
              ws_client_id,    ws_client_secret,
              shared_client_id, shared_client_secret,
              oauth_client_id, oauth_client_secret,
              bearer_token,
              sql_server, sql_database, sql_username, sql_password,
              mail_api_key, mail_from,
              created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            tid, user_id, name or printix_tenant_id,
            printix_tenant_id,
            print_client_id, _enc(print_client_secret),
            card_client_id,  _enc(card_client_secret),
            ws_client_id,    _enc(ws_client_secret),
            shared_client_id, _enc(shared_client_secret),
            oauth_id, _enc(oauth_secret_plain),
            _enc(bearer_plain),
            sql_server, sql_database, sql_username, _enc(sql_password),
            _enc(mail_api_key), mail_from,
            now,
        ))

    return {
        "id":                 tid,
        "name":               name or printix_tenant_id,
        "printix_tenant_id":  printix_tenant_id,
        "oauth_client_id":    oauth_id,
        "oauth_client_secret": oauth_secret_plain,   # Klartext (einmalig)
        "bearer_token":       bearer_plain,            # Klartext (einmalig)
    }


def get_tenant_by_user_id(user_id: str) -> Optional[dict]:
    """Gibt Tenant-Infos für das Dashboard zurück (keine Secrets)."""
    with _conn() as conn:
        row = conn.execute("SELECT * FROM tenants WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    return {
        "id":                d["id"],
        "name":              d["name"],
        "printix_tenant_id": d["printix_tenant_id"],
        "oauth_client_id":   d["oauth_client_id"],
    }


def get_tenant_by_bearer_token(bearer_token: str) -> Optional[dict]:
    """
    Sucht Tenant anhand des Bearer Tokens.
    Alle verschlüsselten Felder werden entschlüsselt zurückgegeben.
    """
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM tenants").fetchall()
    for row in rows:
        d = dict(row)
        try:
            if _dec(d.get("bearer_token", "")) == bearer_token:
                return _tenant_decrypted(d)
        except Exception:
            continue
    return None


def get_tenant_by_oauth_client_id(client_id: str) -> Optional[dict]:
    """Gibt Tenant anhand oauth_client_id zurück (für OAuth Authorize-Seite)."""
    with _conn() as conn:
        row = conn.execute("SELECT * FROM tenants WHERE oauth_client_id=?",
                           (client_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    return {
        "id":               d["id"],
        "name":             d["name"],
        "oauth_client_id":  d["oauth_client_id"],
        "bearer_token":     _dec(d.get("bearer_token", "")),
    }


def verify_tenant_oauth_secret(tenant_id: str, client_secret: str) -> bool:
    """Prüft das OAuth Client-Secret für einen Tenant."""
    with _conn() as conn:
        row = conn.execute("SELECT oauth_client_secret FROM tenants WHERE id=?",
                           (tenant_id,)).fetchone()
    if not row:
        return False
    return _dec(row["oauth_client_secret"]) == client_secret


def _tenant_decrypted(d: dict) -> dict:
    """Gibt alle Felder eines Tenants entschlüsselt zurück."""
    return {
        "id":                  d["id"],
        "user_id":             d["user_id"],
        "name":                d["name"],
        "printix_tenant_id":   d["printix_tenant_id"],
        "print_client_id":     d["print_client_id"],
        "print_client_secret": _dec(d.get("print_client_secret", "")),
        "card_client_id":      d["card_client_id"],
        "card_client_secret":  _dec(d.get("card_client_secret", "")),
        "ws_client_id":        d["ws_client_id"],
        "ws_client_secret":    _dec(d.get("ws_client_secret", "")),
        "shared_client_id":    d.get("shared_client_id", ""),
        "shared_client_secret": _dec(d.get("shared_client_secret", "")),
        "oauth_client_id":     d["oauth_client_id"],
        "bearer_token":        _dec(d.get("bearer_token", "")),
        "sql_server":          d["sql_server"],
        "sql_database":        d["sql_database"],
        "sql_username":        d["sql_username"],
        "sql_password":        _dec(d.get("sql_password", "")),
        "mail_api_key":        _dec(d.get("mail_api_key", "")),
        "mail_from":           d["mail_from"],
    }


# ─── Audit Log ────────────────────────────────────────────────────────────────

def audit(user_id: Optional[str], action: str, details: str = "") -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO audit_log (user_id, action, details, created_at) VALUES (?,?,?,?)",
            (user_id, action, details, _now()),
        )


def get_audit_log(limit: int = 200) -> list:
    with _conn() as conn:
        rows = conn.execute("""
            SELECT a.*, u.username
            FROM audit_log a
            LEFT JOIN users u ON u.id = a.user_id
            ORDER BY a.created_at DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


# ─── Hilfsfunktionen ──────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── DB beim Import initialisieren ────────────────────────────────────────────

try:
    init_db()
except Exception as _e:
    logger.warning("DB init beim Import fehlgeschlagen: %s", _e)
