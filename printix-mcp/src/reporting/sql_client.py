"""
SQL Client — Azure SQL Verbindung für Printix BI-Datenbank
==========================================================
Multi-Tenant v2.0.0: Konfiguration via ContextVar current_sql_config,
gesetzt durch BearerAuthMiddleware pro Request.

Jeder Tenant hat seine eigenen SQL-Credentials in der SQLite-DB.
Die ContextVar enthält nach Authentifizierung:
  sql_server    — z.B. printix-bi-data-2.database.windows.net
  sql_database  — z.B. printix_bi_data_2_1
  sql_username  — SQL-Benutzername
  sql_password  — SQL-Passwort (entschlüsselt)
  tenant_id     — Printix Tenant-ID für Datenfilterung
"""

import logging
from typing import Any, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

try:
    import pyodbc
    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False
    logger.warning("pyodbc nicht installiert — SQL-Reporting nicht verfügbar")

# ContextVar-Import für Multi-Tenant-Routing
try:
    from auth import current_sql_config as _current_sql_config
    _CONTEXTVAR_AVAILABLE = True
except ImportError:
    _current_sql_config = None  # type: ignore
    _CONTEXTVAR_AVAILABLE = False
    logger.warning("auth.py nicht gefunden — SQL-Config aus ContextVar nicht verfügbar")


def _detect_driver() -> str:
    """
    Erkennt den besten verfügbaren ODBC-Treiber für Azure SQL.

    Priorität:
      1. Microsoft ODBC Driver 18/17 (falls installiert)
      2. FreeTDS (auf Debian via tdsodbc-Paket)
      3. Fallback-Pfad: direkter Verweis auf libtdsodbc.so

    Loggt alle verfügbaren Treiber für einfaches Debugging.
    """
    if not PYODBC_AVAILABLE:
        return "FreeTDS"

    available = pyodbc.drivers()
    logger.debug("Verfügbare ODBC-Treiber: %s", available)

    # Bevorzugte Reihenfolge
    preferred = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "FreeTDS",
        "TDS",
    ]
    for d in preferred:
        if d in available:
            logger.debug("ODBC-Treiber gewählt: %s", d)
            return d

    # Kein passender Treiber in odbcinst.ini — direkter .so-Pfad als letzter Ausweg
    import glob
    for pattern in (
        "/usr/lib/*/odbc/libtdsodbc.so",
        "/usr/lib/libtdsodbc.so*",
        "/usr/local/lib/libtdsodbc.so*",
    ):
        matches = glob.glob(pattern)
        if matches:
            logger.warning(
                "Kein ODBC-Treiber in odbcinst.ini — verwende direkten Pfad: %s. "
                "Container neu bauen sollte das beheben.",
                matches[0],
            )
            return matches[0]

    # Letzter Fallback — schlägt mit klarer Fehlermeldung fehl
    logger.error(
        "Kein ODBC-Treiber gefunden! Verfügbar: %s. "
        "Container muss mit build.yaml (Debian-Base) neu gebaut werden.",
        available,
    )
    return "FreeTDS"


def _get_sql_config() -> dict:
    """Gibt SQL-Konfiguration aus dem aktuellen Request-Kontext zurück."""
    if _CONTEXTVAR_AVAILABLE and _current_sql_config is not None:
        cfg = _current_sql_config.get()
        if cfg:
            return cfg
    raise RuntimeError(
        "SQL-Konfiguration nicht im Request-Kontext. "
        "Bitte Bearer Token setzen — BearerAuthMiddleware muss den SQL-Kontext gesetzt haben."
    )


def _build_connection_string() -> str:
    cfg      = _get_sql_config()
    server   = cfg.get("server", "")
    database = cfg.get("database", "")
    username = cfg.get("username", "")
    password = cfg.get("password", "")
    driver   = _detect_driver()

    # FreeTDS benötigt Port im SERVER-Feld und kein Encrypt=yes
    if "FreeTDS" in driver or driver.endswith(".so") or driver.endswith(".so.0"):
        return (
            f"DRIVER={{{driver}}};"
            f"SERVER={server},1433;"
            f"DATABASE={database};"
            f"UID={username};"
            f"PWD={password};"
            f"TDS_Version=7.4;"
            f"Connection Timeout=30;"
        )

    # Microsoft ODBC Driver
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
        f"Connection Timeout=30;"
    )


def get_tenant_id() -> str:
    """Gibt die Tenant-ID aus dem aktuellen Request-Kontext zurück."""
    if _CONTEXTVAR_AVAILABLE and _current_sql_config is not None:
        cfg = _current_sql_config.get()
        if cfg:
            return cfg.get("tenant_id", "")
    return ""


def get_current_db_key() -> tuple:
    """Gibt (server, database) Tupel aus dem aktuellen Request-Kontext zurück.
    Wird als Cache-Schlüssel für View-Verfügbarkeits-Check verwendet."""
    if _CONTEXTVAR_AVAILABLE and _current_sql_config is not None:
        cfg = _current_sql_config.get()
        if cfg:
            return (cfg.get("server", ""), cfg.get("database", ""))
    return ("", "")


def is_configured() -> bool:
    """Prüft ob alle SQL-Konfigurationsparameter im aktuellen Kontext gesetzt sind."""
    if not _CONTEXTVAR_AVAILABLE or _current_sql_config is None:
        return False
    cfg = _current_sql_config.get()
    if not cfg:
        return False
    return all([
        cfg.get("server"),
        cfg.get("database"),
        cfg.get("username"),
        cfg.get("password"),
        cfg.get("tenant_id"),
    ])


@contextmanager
def get_connection():
    """
    Context Manager für eine Azure SQL-Verbindung.

    Usage:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ...")
    """
    if not PYODBC_AVAILABLE:
        raise RuntimeError(
            "pyodbc nicht installiert. Bitte 'pip install pyodbc' im Container ausführen."
        )
    if not is_configured():
        raise RuntimeError(
            "SQL nicht konfiguriert. Bitte SQL-Credentials für diesen Tenant in der Web-UI eintragen."
        )

    cfg = _get_sql_config()
    conn_str = _build_connection_string()
    conn = None
    try:
        logger.debug("Öffne Azure SQL Verbindung zu %s", cfg.get("server", ""))
        conn = pyodbc.connect(conn_str, timeout=30)
        yield conn
    except pyodbc.Error as e:
        logger.error("SQL-Verbindungsfehler: %s", e)
        raise RuntimeError(f"Datenbankverbindung fehlgeschlagen: {e}") from e
    finally:
        if conn:
            conn.close()


def query_fetchall(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """
    Führt ein SQL-Statement aus und gibt alle Zeilen als Liste von Dicts zurück.

    Args:
        sql:    Parameterisiertes SQL (? als Platzhalter)
        params: Tuple mit Parameterwerten

    Returns:
        Liste von Dicts {spaltenname: wert}
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        logger.debug("SQL: %s | params: %s", sql[:200], params)
        cursor.execute(sql, params)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]


def query_fetchone(sql: str, params: tuple = ()) -> Optional[dict[str, Any]]:
    """Wie query_fetchall, gibt aber nur die erste Zeile zurück (oder None)."""
    results = query_fetchall(sql, params)
    return results[0] if results else None


def execute_write(sql: str, params: tuple = ()) -> int:
    """
    Führt ein schreibendes SQL-Statement aus (INSERT, UPDATE, DELETE).

    Args:
        sql:    Parameterisiertes SQL (? als Platzhalter)
        params: Tuple mit Parameterwerten

    Returns:
        Anzahl der betroffenen Zeilen (rowcount)
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        logger.debug("SQL-Write: %s | params: %s", sql[:200], params)
        cursor.execute(sql, params)
        conn.commit()
        return cursor.rowcount if cursor.rowcount >= 0 else 0


def execute_many(sql: str, params_list: list, batch_size: int = 500) -> int:
    """
    Führt ein SQL-Statement für viele Parametersätze aus (Bulk-INSERT).
    Verarbeitet in Batches um Timeouts zu vermeiden.

    Args:
        sql:         Parameterisiertes SQL (? als Platzhalter)
        params_list: Liste von Tuples mit Parameterwerten
        batch_size:  Batch-Größe (default 500)

    Returns:
        Gesamtanzahl verarbeiteter Zeilen
    """
    if not params_list:
        return 0
    total = 0
    with get_connection() as conn:
        cursor = conn.cursor()
        # fast_executemany nur für Microsoft ODBC Driver (nicht FreeTDS)
        try:
            cursor.fast_executemany = True
        except AttributeError:
            pass
        for i in range(0, len(params_list), batch_size):
            batch = params_list[i:i + batch_size]
            cursor.executemany(sql, batch)
            total += len(batch)
        conn.commit()
    return total


def execute_script(statements: list[str]) -> None:
    """
    Führt eine Liste von SQL-Statements in einer Verbindung aus.
    Jedes Statement wird einzeln committed (für DDL wie CREATE TABLE).

    Args:
        statements: Liste von SQL-Strings (z.B. CREATE TABLE ...)
    """
    with get_connection() as conn:
        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue
            cursor = conn.cursor()
            logger.debug("SQL-Script: %s", stmt[:100])
            cursor.execute(stmt)
            try:
                conn.commit()
            except Exception:
                pass  # Manche DDL-Statements committen automatisch
