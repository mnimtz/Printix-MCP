"""
Datenbank — SQLite Multi-Tenant Store für Printix MCP v2.1.0
=============================================================
Datei: /data/printix_multi.db (überlebt Add-on-Updates)

Schema:
  users     — Konten (username, password, status, is_admin)
  tenants   — Printix + SQL + Mail Credentials pro Benutzer (verschlüsselt)
  audit_log — Relevante Aktionen mit Zeitstempel
  settings  — Globale Konfiguration (public_url etc.)

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
    """Erstellt alle Tabellen beim ersten Start (idempotent)."""
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id           TEXT PRIMARY KEY,
                username     TEXT NOT NULL UNIQUE,
                email        TEXT NOT NULL DEFAULT '',
                full_name    TEXT NOT NULL DEFAULT '',
                company      TEXT NOT NULL DEFAULT '',
                password_hash TEXT NOT NULL,
                is_admin     INTEGER NOT NULL DEFAULT 0,
                status       TEXT NOT NULL DEFAULT 'pending',
                created_at   TEXT NOT NULL
            );
            -- Safe migration: add new columns if they don't exist yet
            -- (no-op if columns already exist; PRAGMA table_info used for safety)

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

            CREATE TABLE IF NOT EXISTS settings (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tenant_logs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id  TEXT NOT NULL,
                timestamp  TEXT NOT NULL,
                level      TEXT NOT NULL,
                category   TEXT NOT NULL,
                message    TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_tenant_logs
                ON tenant_logs (tenant_id, id DESC);
        """)
    # Sichere Migration: neue Spalten hinzufügen falls nicht vorhanden
    with _conn() as conn:
        existing_cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "full_name" not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN full_name TEXT NOT NULL DEFAULT ''")
        if "company" not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN company TEXT NOT NULL DEFAULT ''")
    # Sichere Migration für tenants-Tabelle: Alert-Spalten hinzufügen
    with _conn() as conn:
        existing_t = {r[1] for r in conn.execute("PRAGMA table_info(tenants)").fetchall()}
        if "alert_recipients" not in existing_t:
            conn.execute("ALTER TABLE tenants ADD COLUMN alert_recipients TEXT NOT NULL DEFAULT ''")
        if "alert_min_level" not in existing_t:
            conn.execute("ALTER TABLE tenants ADD COLUMN alert_min_level TEXT NOT NULL DEFAULT 'ERROR'")
        if "mail_from_name" not in existing_t:
            conn.execute("ALTER TABLE tenants ADD COLUMN mail_from_name TEXT NOT NULL DEFAULT ''")
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


# ─── Settings ────────────────────────────────────────────────────────────────

def get_setting(key: str, default: str = "") -> str:
    """Liest einen globalen Einstellungswert."""
    with _conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    """Setzt einen globalen Einstellungswert (upsert)."""
    now = _now()
    with _conn() as conn:
        conn.execute("""
            INSERT INTO settings (key, value, updated_at) VALUES (?,?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
        """, (key, value, now))


# ─── Tenant Logs ─────────────────────────────────────────────────────────────

_LEVEL_ORDER = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}
_LOG_KEEP = 1000   # Max entries per tenant


def add_tenant_log(tenant_id: str, level: str, category: str, message: str) -> None:
    """Schreibt einen Log-Eintrag für einen Tenant. Hält max. _LOG_KEEP Einträge."""
    if not tenant_id:
        return
    now = _now()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO tenant_logs (tenant_id, timestamp, level, category, message)"
            " VALUES (?,?,?,?,?)",
            (tenant_id, now, level.upper(), category.upper(), message[:2000])
        )
        # Auto-trim: älteste Einträge löschen wenn Limit überschritten
        conn.execute("""
            DELETE FROM tenant_logs
            WHERE tenant_id=? AND id NOT IN (
                SELECT id FROM tenant_logs WHERE tenant_id=? ORDER BY id DESC LIMIT ?
            )
        """, (tenant_id, tenant_id, _LOG_KEEP))


def get_tenant_logs(
    tenant_id: str,
    min_level: str = "DEBUG",
    limit: int = 300,
    category: str = "",
) -> list[dict]:
    """Gibt Log-Einträge eines Tenants zurück, nach Level und optional Kategorie gefiltert."""
    min_val = _LEVEL_ORDER.get(min_level.upper(), 0)
    levels  = [l for l, v in _LEVEL_ORDER.items() if v >= min_val]
    placeholders = ",".join("?" * len(levels))
    params = [tenant_id] + levels
    cat_clause = ""
    if category:
        cat_clause = " AND category=?"
        params.append(category.upper())
    params.append(limit)
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT id, timestamp, level, category, message"
            f" FROM tenant_logs"
            f" WHERE tenant_id=? AND level IN ({placeholders}){cat_clause}"
            f" ORDER BY id DESC LIMIT ?",
            params
        ).fetchall()
    return [dict(r) for r in rows]


def clear_tenant_logs(tenant_id: str) -> int:
    """Löscht alle Log-Einträge eines Tenants. Gibt Anzahl gelöschter Zeilen zurück."""
    with _conn() as conn:
        cur = conn.execute("DELETE FROM tenant_logs WHERE tenant_id=?", (tenant_id,))
        return cur.rowcount


# ─── Users ────────────────────────────────────────────────────────────────────

def has_users() -> bool:
    """True wenn mindestens ein Benutzer existiert."""
    with _conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        return count > 0


def username_exists(username: str, exclude_id: str = "") -> bool:
    with _conn() as conn:
        if exclude_id:
            row = conn.execute("SELECT id FROM users WHERE username=? AND id!=?",
                               (username.strip(), exclude_id)).fetchone()
        else:
            row = conn.execute("SELECT id FROM users WHERE username=?",
                               (username.strip(),)).fetchone()
        return row is not None


def create_user(username: str, password: str, email: str = "", is_first: bool = False, full_name: str = "", company: str = "") -> dict:
    """
    Legt einen neuen Benutzer via Registrierungs-Wizard an.
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
            "INSERT INTO users (id, username, email, full_name, company, password_hash, is_admin, status, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (uid, username.strip(), email.strip(), full_name.strip(), company.strip(), pw_hash, is_admin, status, now),
        )
    return get_user_by_id(uid)


def create_user_admin(
    username: str,
    password: str,
    email: str = "",
    is_admin: bool = False,
    status: str = "approved",
    full_name: str = "",
    company: str = "",
) -> dict:
    """
    Legt einen Benutzer direkt durch einen Admin an (ohne Wizard-Flow).
    Status und Adminrechte werden explizit gesetzt.
    Erstellt auch einen leeren Tenant-Datensatz für den Benutzer.
    """
    from crypto import hash_password
    uid = str(uuid.uuid4())
    now = _now()
    pw_hash = hash_password(password)
    with _conn() as conn:
        conn.execute(
            "INSERT INTO users (id, username, email, full_name, company, password_hash, is_admin, status, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (uid, username.strip(), email.strip(), full_name.strip(), company.strip(), pw_hash, 1 if is_admin else 0, status, now),
        )
    # Leeren Tenant anlegen damit OAuth/Bearer sofort verfügbar sind
    _create_empty_tenant(uid, username)
    return get_user_by_id(uid)


def _create_empty_tenant(user_id: str, name: str = "") -> dict:
    """Erstellt einen leeren Tenant mit generierten Auth-Credentials."""
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
            tid, user_id, name,
            "", "", "", "", "", "", "", "", "",
            oauth_id, _enc(oauth_secret_plain),
            _enc(bearer_plain),
            "", "printix_bi_data_2_1", "", "",
            "", "",
            now,
        ))
    return {
        "bearer_token": bearer_plain,
        "oauth_client_id": oauth_id,
        "oauth_client_secret": oauth_secret_plain,
    }


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Prüft Benutzername + Passwort, gibt User-Dict zurück oder None."""
    from crypto import verify_password
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?",
                           (username.strip(),)).fetchone()
    if not row:
        return None
    user = dict(row)
    if not verify_password(password, user["password_hash"]):
        return None
    return _user_public(user)


def get_user_by_id(user_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
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


def set_user_admin(user_id: str, is_admin: bool) -> None:
    with _conn() as conn:
        conn.execute("UPDATE users SET is_admin=? WHERE id=?", (1 if is_admin else 0, user_id))


def update_user(
    user_id: str,
    username: Optional[str] = None,
    email: Optional[str] = None,
    is_admin: Optional[bool] = None,
    status: Optional[str] = None,
    full_name: Optional[str] = None,
    company: Optional[str] = None,
) -> Optional[dict]:
    """Aktualisiert Benutzerdaten (nur gesetzte Felder)."""
    parts, params = [], []
    if username is not None:
        parts.append("username=?"); params.append(username.strip())
    if email is not None:
        parts.append("email=?"); params.append(email.strip())
    if full_name is not None:
        parts.append("full_name=?"); params.append(full_name.strip())
    if company is not None:
        parts.append("company=?"); params.append(company.strip())
    if is_admin is not None:
        parts.append("is_admin=?"); params.append(1 if is_admin else 0)
    if status is not None:
        parts.append("status=?"); params.append(status)
    if not parts:
        return get_user_by_id(user_id)
    params.append(user_id)
    with _conn() as conn:
        conn.execute(f"UPDATE users SET {', '.join(parts)} WHERE id=?", params)
    return get_user_by_id(user_id)


def reset_user_password(user_id: str, new_password: str) -> bool:
    """Setzt Passwort zurück (Admin-Funktion oder Self-Service)."""
    from crypto import hash_password
    pw_hash = hash_password(new_password)
    with _conn() as conn:
        cur = conn.execute("UPDATE users SET password_hash=? WHERE id=?", (pw_hash, user_id))
    return cur.rowcount > 0


def delete_user(user_id: str) -> bool:
    """
    Löscht einen Benutzer und seinen zugehörigen Tenant.
    Gibt False zurück wenn der Benutzer nicht existiert.
    """
    with _conn() as conn:
        conn.execute("DELETE FROM tenants WHERE user_id=?", (user_id,))
        cur = conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    return cur.rowcount > 0


def _user_public(user: dict) -> dict:
    """Gibt ein User-Dict ohne password_hash zurück."""
    return {
        "id":         user["id"],
        "username":   user["username"],
        "email":      user.get("email", ""),
        "full_name":  user.get("full_name", ""),
        "company":    user.get("company", ""),
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
    Legt einen Tenant-Datensatz via Wizard an.
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
        "id":                  tid,
        "name":                name or printix_tenant_id,
        "printix_tenant_id":   printix_tenant_id,
        "oauth_client_id":     oauth_id,
        "oauth_client_secret": oauth_secret_plain,
        "bearer_token":        bearer_plain,
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
        "print_client_id":   d["print_client_id"],
        "card_client_id":    d["card_client_id"],
        "ws_client_id":      d["ws_client_id"],
        "shared_client_id":  d.get("shared_client_id", ""),
        "sql_server":        d["sql_server"],
        "sql_database":      d["sql_database"],
        "sql_username":      d["sql_username"],
        "mail_from":         d["mail_from"],
        # Bearer Token für Dashboard-Anzeige (entschlüsselt)
        "bearer_token":      _dec(d.get("bearer_token", "")),
    }


def get_tenant_full_by_user_id(user_id: str) -> Optional[dict]:
    """
    Gibt alle Tenant-Felder für die Einstellungsseite zurück.
    Secrets werden entschlüsselt — nur für den Benutzer selbst verwenden!
    """
    with _conn() as conn:
        row = conn.execute("SELECT * FROM tenants WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    return {
        "id":                  d["id"],
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
        "oauth_client_secret": _dec(d.get("oauth_client_secret", "")),
        "bearer_token":        _dec(d.get("bearer_token", "")),
        "sql_server":          d["sql_server"],
        "sql_database":        d["sql_database"],
        "sql_username":        d["sql_username"],
        "sql_password":        _dec(d.get("sql_password", "")),
        "mail_api_key":        _dec(d.get("mail_api_key", "")),
        "mail_from":           d["mail_from"],
        "mail_from_name":      d.get("mail_from_name", ""),
        "alert_recipients":    d.get("alert_recipients", ""),
        "alert_min_level":     d.get("alert_min_level", "ERROR"),
    }


def update_tenant_credentials(
    user_id: str,
    printix_tenant_id: Optional[str] = None,
    name: Optional[str] = None,
    print_client_id: Optional[str] = None,
    print_client_secret: Optional[str] = None,
    card_client_id: Optional[str] = None,
    card_client_secret: Optional[str] = None,
    ws_client_id: Optional[str] = None,
    ws_client_secret: Optional[str] = None,
    shared_client_id: Optional[str] = None,
    shared_client_secret: Optional[str] = None,
    sql_server: Optional[str] = None,
    sql_database: Optional[str] = None,
    sql_username: Optional[str] = None,
    sql_password: Optional[str] = None,
    mail_api_key: Optional[str] = None,
    mail_from: Optional[str] = None,
    mail_from_name: Optional[str] = None,
    alert_recipients: Optional[str] = None,
    alert_min_level: Optional[str] = None,
) -> bool:
    """
    Aktualisiert Tenant-Credentials (nur gesetzte Felder).
    Secrets werden automatisch verschlüsselt.
    """
    parts, params = [], []

    def _add(col: str, val, encrypt: bool = False):
        if val is not None:
            parts.append(f"{col}=?")
            params.append(_enc(val) if encrypt and val else val)

    _add("name",                 name)
    _add("printix_tenant_id",    printix_tenant_id)
    _add("print_client_id",      print_client_id)
    _add("print_client_secret",  print_client_secret, encrypt=True)
    _add("card_client_id",       card_client_id)
    _add("card_client_secret",   card_client_secret,  encrypt=True)
    _add("ws_client_id",         ws_client_id)
    _add("ws_client_secret",     ws_client_secret,    encrypt=True)
    _add("shared_client_id",     shared_client_id)
    _add("shared_client_secret", shared_client_secret, encrypt=True)
    _add("sql_server",           sql_server)
    _add("sql_database",         sql_database)
    _add("sql_username",         sql_username)
    _add("sql_password",         sql_password,        encrypt=True)
    _add("mail_api_key",         mail_api_key,        encrypt=True)
    _add("mail_from",            mail_from)
    _add("mail_from_name",       mail_from_name)
    _add("alert_recipients",     alert_recipients)
    _add("alert_min_level",      alert_min_level)

    if not parts:
        return True

    params.append(user_id)
    with _conn() as conn:
        cur = conn.execute(
            f"UPDATE tenants SET {', '.join(parts)} WHERE user_id=?", params
        )
    return cur.rowcount > 0


def regenerate_oauth_secret(user_id: str) -> Optional[str]:
    """
    Generiert ein neues OAuth Client-Secret für den Tenant des Benutzers.
    Gibt das neue Secret im Klartext zurück (einmalig!), oder None wenn kein Tenant.
    """
    new_secret = secrets.token_urlsafe(32)
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE tenants SET oauth_client_secret=? WHERE user_id=?",
            (_enc(new_secret), user_id)
        )
    return new_secret if cur.rowcount > 0 else None


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
