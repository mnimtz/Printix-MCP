"""
Cloud Print Port — DB-Schema-Erweiterungen
==========================================
Erweitert die bestehende SQLite-DB um:
  - users.role_type      (admin | user | employee)
  - users.parent_user_id (FK → users.id, für Mitarbeiter-Zugehörigkeit)
  - tenants.print_token  (dedizierter Druck-Token, verschlüsselt)
  - tenants.print_token_hash (SHA-256 Hash für schnellen Lookup)
  - delegations-Tabelle  (Owner → Delegate Beziehungen)

Aufruf: init_cloudprint_schema() — idempotent, nutzt PRAGMA table_info.
"""

import hashlib
import logging
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("printix.cloudprint.db")


# ─── Schema-Migration ────────────────────────────────────────────────────────

def init_cloudprint_schema() -> None:
    """Erweitert die bestehende DB um Cloud-Print-Felder (idempotent)."""
    from db import _conn

    # 1) users: role_type + parent_user_id
    with _conn() as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "role_type" not in cols:
            conn.execute(
                "ALTER TABLE users ADD COLUMN role_type TEXT NOT NULL DEFAULT 'user'"
            )
            # Bestehende Admins korrekt setzen
            conn.execute("UPDATE users SET role_type = 'admin' WHERE is_admin = 1")
            logger.info("Migration: users.role_type hinzugefügt")
        if "parent_user_id" not in cols:
            conn.execute(
                "ALTER TABLE users ADD COLUMN parent_user_id TEXT DEFAULT NULL"
            )
            logger.info("Migration: users.parent_user_id hinzugefügt")

    # 2) tenants: print_token + print_token_hash
    with _conn() as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(tenants)").fetchall()}
        if "print_token" not in cols:
            conn.execute(
                "ALTER TABLE tenants ADD COLUMN print_token TEXT NOT NULL DEFAULT ''"
            )
            logger.info("Migration: tenants.print_token hinzugefügt")
        if "print_token_hash" not in cols:
            conn.execute(
                "ALTER TABLE tenants ADD COLUMN print_token_hash TEXT NOT NULL DEFAULT ''"
            )
            logger.info("Migration: tenants.print_token_hash hinzugefügt")

    # 3) delegations-Tabelle
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS delegations (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_user_id     TEXT NOT NULL REFERENCES users(id),
                delegate_user_id  TEXT NOT NULL REFERENCES users(id),
                status            TEXT NOT NULL DEFAULT 'active',
                created_by        TEXT NOT NULL DEFAULT '',
                created_at        TEXT NOT NULL,
                updated_at        TEXT NOT NULL,
                UNIQUE(owner_user_id, delegate_user_id)
            );
            CREATE INDEX IF NOT EXISTS idx_deleg_owner
                ON delegations (owner_user_id);
            CREATE INDEX IF NOT EXISTS idx_deleg_delegate
                ON delegations (delegate_user_id);
        """)
        logger.info("Migration: delegations-Tabelle geprüft/erstellt")


# ─── Print Token ──────────────────────────────────────────────────────────────

def _hash_token(token: str) -> str:
    """SHA-256 Hash eines Print-Tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_print_token(user_id: str) -> str:
    """Erzeugt einen neuen Print-Token für einen Tenant und gibt ihn zurück.

    Format: ptk_{32 Hex-Zeichen}
    Der Token wird verschlüsselt gespeichert, der Hash indiziert.
    Gibt den Klartext-Token zurück (einmalige Anzeige).
    """
    from db import _conn, _enc

    # Tenant des Users finden
    with _conn() as conn:
        row = conn.execute(
            "SELECT id FROM tenants WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"Kein Tenant für User {user_id}")

    token = f"ptk_{secrets.token_hex(16)}"
    token_hash = _hash_token(token)
    encrypted = _enc(token)

    with _conn() as conn:
        conn.execute(
            "UPDATE tenants SET print_token = ?, print_token_hash = ? WHERE user_id = ?",
            (encrypted, token_hash, user_id),
        )
    logger.info("Print-Token generiert für User %s", user_id)
    return token


def revoke_print_token(user_id: str) -> None:
    """Widerruft den Print-Token eines Users."""
    from db import _conn
    with _conn() as conn:
        conn.execute(
            "UPDATE tenants SET print_token = '', print_token_hash = '' WHERE user_id = ?",
            (user_id,),
        )
    logger.info("Print-Token widerrufen für User %s", user_id)


def verify_print_token(token: str) -> Optional[dict]:
    """Prüft einen Print-Token und gibt den zugehörigen Tenant+User zurück.

    Returns: {"tenant_id": ..., "user_id": ..., "username": ..., "email": ...} oder None.
    """
    from db import _conn
    token_hash = _hash_token(token)
    with _conn() as conn:
        row = conn.execute(
            """SELECT t.id AS tenant_id, t.user_id, u.username, u.email
               FROM tenants t
               JOIN users u ON u.id = t.user_id
               WHERE t.print_token_hash = ? AND u.status = 'approved'""",
            (token_hash,),
        ).fetchone()
    return dict(row) if row else None


# ─── Employee (Mitarbeiter) ──────────────────────────────────────────────────

def create_employee(
    parent_user_id: str,
    username: str,
    password: str,
    email: str = "",
    full_name: str = "",
) -> dict:
    """Erstellt einen Mitarbeiter-Account, verknüpft mit dem Parent-User/Tenant."""
    from crypto import hash_password
    from db import _conn, get_user_by_id
    import uuid

    uid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    pw_hash = hash_password(password)

    with _conn() as conn:
        conn.execute(
            """INSERT INTO users
               (id, username, email, full_name, company, password_hash,
                is_admin, status, role_type, parent_user_id, created_at)
               VALUES (?,?,?,?,?,?, 0,'approved','employee',?,?)""",
            (uid, username.strip(), email.strip(), full_name.strip(), "",
             pw_hash, parent_user_id, now),
        )
    logger.info("Mitarbeiter erstellt: %s (Parent: %s)", username, parent_user_id)
    return get_user_by_id(uid)


def get_employees(parent_user_id: str) -> list[dict]:
    """Gibt alle Mitarbeiter eines Users zurück."""
    from db import _conn
    with _conn() as conn:
        rows = conn.execute(
            """SELECT id, username, email, full_name, status, role_type, created_at
               FROM users
               WHERE parent_user_id = ? AND role_type = 'employee'
               ORDER BY full_name, username""",
            (parent_user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_employee_by_id(employee_id: str, parent_user_id: str) -> Optional[dict]:
    """Gibt einen Mitarbeiter zurück, nur wenn er zum Parent gehört."""
    from db import _conn
    with _conn() as conn:
        row = conn.execute(
            """SELECT id, username, email, full_name, status, role_type,
                      parent_user_id, created_at
               FROM users
               WHERE id = ? AND parent_user_id = ? AND role_type = 'employee'""",
            (employee_id, parent_user_id),
        ).fetchone()
    return dict(row) if row else None


def delete_employee(employee_id: str, parent_user_id: str) -> bool:
    """Löscht einen Mitarbeiter (nur wenn er zum Parent gehört)."""
    from db import _conn
    with _conn() as conn:
        # Erst Delegationen dieses Employees löschen
        conn.execute(
            "DELETE FROM delegations WHERE owner_user_id = ? OR delegate_user_id = ?",
            (employee_id, employee_id),
        )
        cur = conn.execute(
            "DELETE FROM users WHERE id = ? AND parent_user_id = ? AND role_type = 'employee'",
            (employee_id, parent_user_id),
        )
    return cur.rowcount > 0


def get_parent_user_id(user_id: str) -> Optional[str]:
    """Ermittelt den Parent-User eines Mitarbeiters (oder sich selbst für Admin/User)."""
    from db import _conn
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, role_type, parent_user_id FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    if row["role_type"] == "employee" and row["parent_user_id"]:
        return row["parent_user_id"]
    return row["id"]


def get_tenant_for_user(user_id: str) -> Optional[dict]:
    """Gibt den Tenant für einen User zurück — auch für Employees (über Parent)."""
    from db import get_tenant_by_user_id
    parent_id = get_parent_user_id(user_id)
    if not parent_id:
        return None
    return get_tenant_by_user_id(parent_id)


# ─── Delegations ──────────────────────────────────────────────────────────────

def create_delegation(
    owner_user_id: str,
    delegate_user_id: str,
    created_by: str = "",
    status: str = "active",
) -> Optional[dict]:
    """Erstellt eine Delegation (Owner → Delegate).

    status: 'active' (Admin-erstellt) oder 'pending' (Mitarbeiter-Vorschlag).
    """
    from db import _conn
    now = datetime.now(timezone.utc).isoformat()
    try:
        with _conn() as conn:
            conn.execute(
                """INSERT INTO delegations
                   (owner_user_id, delegate_user_id, status, created_by, created_at, updated_at)
                   VALUES (?,?,?,?,?,?)""",
                (owner_user_id, delegate_user_id, status, created_by, now, now),
            )
            row = conn.execute(
                "SELECT * FROM delegations WHERE owner_user_id = ? AND delegate_user_id = ?",
                (owner_user_id, delegate_user_id),
            ).fetchone()
        return dict(row) if row else None
    except sqlite3.IntegrityError:
        logger.warning("Delegation existiert bereits: %s → %s", owner_user_id, delegate_user_id)
        return None


def get_delegations_for_owner(owner_user_id: str) -> list[dict]:
    """Gibt alle Delegationen zurück, bei denen der User Owner ist."""
    from db import _conn
    with _conn() as conn:
        rows = conn.execute(
            """SELECT d.*, u.username AS delegate_username, u.email AS delegate_email,
                      u.full_name AS delegate_full_name
               FROM delegations d
               JOIN users u ON u.id = d.delegate_user_id
               WHERE d.owner_user_id = ?
               ORDER BY d.created_at DESC""",
            (owner_user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_delegations_for_delegate(delegate_user_id: str) -> list[dict]:
    """Gibt alle Delegationen zurück, bei denen der User Delegate ist."""
    from db import _conn
    with _conn() as conn:
        rows = conn.execute(
            """SELECT d.*, u.username AS owner_username, u.email AS owner_email,
                      u.full_name AS owner_full_name
               FROM delegations d
               JOIN users u ON u.id = d.owner_user_id
               WHERE d.delegate_user_id = ? AND d.status = 'active'
               ORDER BY d.created_at DESC""",
            (delegate_user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_delegation_status(delegation_id: int, status: str) -> bool:
    """Aktualisiert den Status einer Delegation (active/pending/revoked)."""
    from db import _conn
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE delegations SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, delegation_id),
        )
    return cur.rowcount > 0


def delete_delegation(delegation_id: int) -> bool:
    """Löscht eine Delegation."""
    from db import _conn
    with _conn() as conn:
        cur = conn.execute("DELETE FROM delegations WHERE id = ?", (delegation_id,))
    return cur.rowcount > 0


def get_delegation_by_id(delegation_id: int) -> Optional[dict]:
    """Gibt eine Delegation anhand der ID zurück."""
    from db import _conn
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM delegations WHERE id = ?", (delegation_id,)
        ).fetchone()
    return dict(row) if row else None


def get_available_delegates(parent_user_id: str, exclude_user_id: str = "") -> list[dict]:
    """Gibt alle möglichen Delegates zurück (alle Mitarbeiter + den Parent selbst)."""
    from db import _conn
    with _conn() as conn:
        rows = conn.execute(
            """SELECT id, username, email, full_name, role_type
               FROM users
               WHERE (parent_user_id = ? OR id = ?)
                 AND status = 'approved'
                 AND id != ?
               ORDER BY full_name, username""",
            (parent_user_id, parent_user_id, exclude_user_id),
        ).fetchall()
    return [dict(r) for r in rows]
