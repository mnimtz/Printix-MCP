"""
Query Tools — Printix BI Datenabfragen
=======================================
Alle Abfragen gegen dbo-Schema der printix_bi_data_2_1 Datenbank.

Tabellenstruktur (aus PowerBI-Template extrahiert):
  dbo.tracking_data  — Druckaufträge (page_count, color, duplex, print_time, printer_id, job_id, tenant_id)
  dbo.jobs           — Jobs (id, tenant_id, color, duplex, page_count, paper_size, printer_id, submit_time, tenant_user_id, name)
  dbo.users          — Benutzer (id, tenant_id, email, name, department)
  dbo.printers       — Drucker (id, tenant_id, name, model_name, vendor_name, network_id, location)
  dbo.networks       — Netzwerke/Standorte (id, tenant_id, name)
  dbo.jobs_scan      — Scan-Jobs (id, tenant_id, printer_id, tenant_user_id, scan_time, page_count, color)
  dbo.jobs_copy      — Kopier-Jobs (id, tenant_id, printer_id, tenant_user_id, copy_time)
  dbo.jobs_copy_details — Kopier-Details (id, job_id, page_count, paper_size, duplex, color)

Kostenformel (aus PowerBI DAX):
  sheet_count  = CEIL(page_count / 2) wenn duplex, sonst page_count
  toner_color  = page_count × cost_per_color  (wenn color=True)
  toner_bw     = page_count × cost_per_mono   (wenn color=False)
  sheet_cost   = sheet_count × cost_per_sheet
  total_cost   = sheet_cost + toner_color + toner_bw
"""

import logging
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Optional

from .sql_client import query_fetchall, get_tenant_id

logger = logging.getLogger(__name__)


# ─── Demo-Daten Merge-Layer (v4.4.0) ────────────────────────────────────────
# Demo-Daten liegen lokal in SQLite, echte Daten in Azure SQL.
# Dieser Merge-Layer kombiniert beide Quellen für Reports.

def _has_active_demo() -> bool:
    """Prüft ob aktive lokale Demo-Daten für den aktuellen Tenant existieren."""
    try:
        from .local_demo_db import has_active_demo
        tid = get_tenant_id()
        return has_active_demo(tid) if tid else False
    except Exception:
        return False


def _get_demo_rows(start_date, end_date) -> list[dict]:
    """Holt Demo-Tracking-Rohdaten aus lokaler SQLite für den Merge."""
    try:
        from .local_demo_db import query_demo_tracking_data
        tid = get_tenant_id()
        if not tid:
            return []
        s = str(_fmt_date(start_date))
        e = str(_fmt_date(end_date))
        return query_demo_tracking_data(tid, s, e)
    except Exception as ex:
        logger.debug("Demo-Daten Merge fehlgeschlagen: %s", ex)
        return []


def _parse_demo_date(val) -> date:
    """Parst ein Datum aus SQLite-Ergebnis."""
    if isinstance(val, date):
        return val
    s = str(val).strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return date.today()


def _demo_week_start(d: date) -> date:
    """Montag der Woche."""
    return d - timedelta(days=d.weekday())


def _demo_month_start(d: date) -> date:
    """Erster Tag des Monats."""
    return d.replace(day=1)


def _aggregate_demo_print_stats(demo_rows: list[dict], group_by: str,
                                 site_id=None, user_email=None,
                                 printer_id=None) -> list[dict]:
    """
    Aggregiert Demo-Tracking-Rohdaten wie query_print_stats.
    Gibt list[dict] mit gleicher Struktur zurück.
    """
    # Filter anwenden
    filtered = demo_rows
    if site_id:
        filtered = [r for r in filtered if r.get("network_id") == site_id]
    if user_email:
        filtered = [r for r in filtered if r.get("user_email") == user_email]
    if printer_id:
        filtered = [r for r in filtered if r.get("printer_id") == printer_id]

    if not filtered:
        return []

    # Gruppierung
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in filtered:
        pt = str(r.get("print_time", ""))
        d = _parse_demo_date(pt)
        if group_by == "day":
            key = str(d)
        elif group_by == "week":
            key = str(_demo_week_start(d))
        elif group_by == "month":
            key = str(_demo_month_start(d))
        elif group_by == "user":
            key = r.get("user_name") or r.get("user_email", "Unknown")
        elif group_by == "printer":
            key = r.get("printer_name", "Unknown")
        elif group_by == "site":
            key = r.get("network_name", "Unknown")
        else:
            key = str(d)
        groups[key].append(r)

    # Aggregation
    results = []
    for period, rows in groups.items():
        job_ids = set()
        total_pages = 0
        color_pages = 0
        bw_pages = 0
        duplex_pages = 0
        saved_sheets = 0
        for r in rows:
            jid = r.get("job_id", "")
            job_ids.add(jid)
            pc = int(r.get("page_count") or 0)
            is_color = bool(int(r.get("color") or 0))
            is_duplex = bool(int(r.get("duplex") or 0))
            total_pages += pc
            if is_color:
                color_pages += pc
            else:
                bw_pages += pc
            if is_duplex:
                duplex_pages += pc
                saved_sheets += pc - math.ceil(pc / 2)

        color_pct = round(color_pages * 100.0 / total_pages, 1) if total_pages else 0
        duplex_pct = round(duplex_pages * 100.0 / total_pages, 1) if total_pages else 0

        results.append({
            "period": period,
            "total_jobs": len(job_ids),
            "total_pages": total_pages,
            "color_pages": color_pages,
            "bw_pages": bw_pages,
            "duplex_pages": duplex_pages,
            "color_pct": color_pct,
            "duplex_pct": duplex_pct,
            "saved_sheets_duplex": saved_sheets,
        })

    return results


def _aggregate_demo_cost_report(demo_rows: list[dict], group_by: str,
                                 cost_per_sheet: float, cost_per_mono: float,
                                 cost_per_color: float,
                                 site_id=None) -> list[dict]:
    """Aggregiert Demo-Daten wie query_cost_report."""
    filtered = demo_rows
    if site_id:
        filtered = [r for r in filtered if r.get("network_id") == site_id]
    if not filtered:
        return []

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in filtered:
        d = _parse_demo_date(str(r.get("print_time", "")))
        if group_by == "day":
            key = str(d)
        elif group_by == "week":
            key = str(_demo_week_start(d))
        elif group_by == "site":
            key = r.get("network_name", "Unknown")
        else:
            key = str(_demo_month_start(d))
        groups[key].append(r)

    results = []
    for period, rows in groups.items():
        total_pages = color_pages = bw_pages = 0
        total_sheets = 0.0
        toner_color = toner_bw = sheet_cost = total_cost = 0.0
        for r in rows:
            pc = int(r.get("page_count") or 0)
            is_color = bool(int(r.get("color") or 0))
            is_duplex = bool(int(r.get("duplex") or 0))
            total_pages += pc
            sheets = math.ceil(pc / 2) if is_duplex else pc
            total_sheets += sheets
            if is_color:
                color_pages += pc
                tc = pc * cost_per_color
                toner_color += tc
            else:
                bw_pages += pc
                tc = pc * cost_per_mono
                toner_bw += tc
            sc = sheets * cost_per_sheet
            sheet_cost += sc
            total_cost += sc + tc

        results.append({
            "period": period,
            "total_pages": total_pages,
            "color_pages": color_pages,
            "bw_pages": bw_pages,
            "total_sheets": int(total_sheets),
            "toner_cost_color": round(toner_color, 2),
            "toner_cost_bw": round(toner_bw, 2),
            "sheet_cost": round(sheet_cost, 2),
            "total_cost": round(total_cost, 2),
        })
    return results


def _aggregate_demo_top_users(demo_rows: list[dict], top_n: int,
                               metric: str, cost_per_sheet: float,
                               cost_per_mono: float, cost_per_color: float,
                               site_id=None) -> list[dict]:
    """Aggregiert Demo-Daten wie query_top_users."""
    filtered = demo_rows
    if site_id:
        filtered = [r for r in filtered if r.get("network_id") == site_id]
    if not filtered:
        return []

    users: dict[str, dict] = {}
    for r in filtered:
        email = r.get("user_email") or "unknown"
        if email not in users:
            users[email] = {
                "email": email, "name": r.get("user_name", ""),
                "department": r.get("department", ""),
                "job_ids": set(), "total_pages": 0, "color_pages": 0,
                "bw_pages": 0, "duplex_pages": 0, "total_cost": 0.0,
            }
        u = users[email]
        u["job_ids"].add(r.get("job_id", ""))
        pc = int(r.get("page_count") or 0)
        is_color = bool(int(r.get("color") or 0))
        is_duplex = bool(int(r.get("duplex") or 0))
        u["total_pages"] += pc
        if is_color:
            u["color_pages"] += pc
        else:
            u["bw_pages"] += pc
        if is_duplex:
            u["duplex_pages"] += pc
        sheets = math.ceil(pc / 2) if is_duplex else pc
        cost = sheets * cost_per_sheet
        cost += pc * (cost_per_color if is_color else cost_per_mono)
        u["total_cost"] += cost

    results = []
    for u in users.values():
        tp = u["total_pages"]
        results.append({
            "email": u["email"], "name": u["name"], "department": u["department"],
            "total_jobs": len(u["job_ids"]),
            "total_pages": tp,
            "color_pages": u["color_pages"],
            "bw_pages": u["bw_pages"],
            "duplex_pages": u["duplex_pages"],
            "color_pct": round(u["color_pages"] * 100.0 / tp, 1) if tp else 0,
            "total_cost": round(u["total_cost"], 2),
        })

    sort_key = {"pages": "total_pages", "cost": "total_cost",
                "jobs": "total_jobs", "color_pages": "color_pages"}.get(metric, "total_pages")
    results.sort(key=lambda x: x.get(sort_key, 0), reverse=True)
    return results[:top_n]


def _aggregate_demo_top_printers(demo_rows: list[dict], top_n: int,
                                  metric: str, cost_per_sheet: float,
                                  cost_per_mono: float, cost_per_color: float,
                                  site_id=None) -> list[dict]:
    """Aggregiert Demo-Daten wie query_top_printers."""
    filtered = demo_rows
    if site_id:
        filtered = [r for r in filtered if r.get("network_id") == site_id]
    if not filtered:
        return []

    printers: dict[str, dict] = {}
    for r in filtered:
        pid = r.get("printer_id") or "unknown"
        if pid not in printers:
            printers[pid] = {
                "printer_name": r.get("printer_name", "Unknown"),
                "model_name": r.get("model_name", ""),
                "vendor_name": r.get("vendor_name", ""),
                "location": r.get("location", ""),
                "site_name": r.get("network_name", ""),
                "job_ids": set(), "total_pages": 0, "color_pages": 0,
                "bw_pages": 0, "total_cost": 0.0,
            }
        p = printers[pid]
        p["job_ids"].add(r.get("job_id", ""))
        pc = int(r.get("page_count") or 0)
        is_color = bool(int(r.get("color") or 0))
        is_duplex = bool(int(r.get("duplex") or 0))
        p["total_pages"] += pc
        if is_color:
            p["color_pages"] += pc
        else:
            p["bw_pages"] += pc
        sheets = math.ceil(pc / 2) if is_duplex else pc
        cost = sheets * cost_per_sheet + pc * (cost_per_color if is_color else cost_per_mono)
        p["total_cost"] += cost

    results = []
    for p in printers.values():
        tp = p["total_pages"]
        results.append({
            "printer_name": p["printer_name"], "model_name": p["model_name"],
            "vendor_name": p["vendor_name"], "location": p["location"],
            "site_name": p["site_name"],
            "total_jobs": len(p["job_ids"]),
            "total_pages": tp,
            "color_pages": p["color_pages"],
            "bw_pages": p["bw_pages"],
            "color_pct": round(p["color_pages"] * 100.0 / tp, 1) if tp else 0,
            "total_cost": round(p["total_cost"], 2),
        })

    sort_key = {"pages": "total_pages", "cost": "total_cost",
                "jobs": "total_jobs", "color_pages": "color_pages"}.get(metric, "total_pages")
    results.sort(key=lambda x: x.get(sort_key, 0), reverse=True)
    return results[:top_n]


def _merge_aggregated(sql_rows: list[dict], demo_rows: list[dict],
                       key_field: str = "period") -> list[dict]:
    """
    Mergt SQL- und Demo-Ergebnisse. Bei gleichem Schlüssel (period/name)
    werden numerische Felder addiert.
    """
    if not demo_rows:
        return sql_rows

    merged: dict[str, dict] = {}
    for r in sql_rows:
        k = str(r.get(key_field, ""))
        merged[k] = dict(r)

    for r in demo_rows:
        k = str(r.get(key_field, ""))
        if k in merged:
            existing = merged[k]
            for field, val in r.items():
                if field == key_field:
                    continue
                if isinstance(val, (int, float)) and isinstance(existing.get(field), (int, float)):
                    existing[field] = existing[field] + val
            # Prozente neu berechnen
            tp = existing.get("total_pages", 0)
            if tp and "color_pct" in existing:
                existing["color_pct"] = round(existing.get("color_pages", 0) * 100.0 / tp, 1)
            if tp and "duplex_pct" in existing:
                existing["duplex_pct"] = round(existing.get("duplex_pages", 0) * 100.0 / tp, 1)
        else:
            merged[k] = dict(r)

    return list(merged.values())


# ─── Reporting-View Fallback ──────────────────────────────────────────────────

_view_cache: dict[tuple, bool] = {}


def _V(table: str) -> str:
    """
    Gibt 'reporting.v_{table}' zurück wenn reporting-Views in der aktuellen DB
    vorhanden sind, sonst 'dbo.{table}' als Fallback.
    Gecacht pro (server, database) Kombination.
    """
    from .sql_client import get_current_db_key, query_fetchone
    key = get_current_db_key()
    if key not in _view_cache:
        try:
            r = query_fetchone(
                "SELECT COUNT(*) AS cnt FROM sys.views "
                "WHERE schema_id = SCHEMA_ID('reporting') AND name = 'v_tracking_data'"
            )
            _view_cache[key] = bool((r or {}).get("cnt", 0) > 0)
        except Exception:
            _view_cache[key] = False
    return f"reporting.v_{table}" if _view_cache[key] else f"dbo.{table}"


def invalidate_view_cache() -> None:
    """Leert den View-Verfügbarkeits-Cache (nach setup_schema() aufrufen)."""
    _view_cache.clear()


# ─── Hilfsfunktionen ──────────────────────────────────────────────────────────

def _fmt_date(d) -> date:
    """
    Konvertiert date/datetime/str in ein Python-date-Objekt.
    pyodbc übergibt date-Objekte als native ODBC DATE — kein FreeTDS varchar-Cast-Problem.
    """
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    s = str(d).strip()
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        try:
            return datetime.strptime(s, "%d.%m.%Y").date()
        except ValueError:
            raise ValueError(f"Ungültiges Datumsformat: {s!r} — erwartet YYYY-MM-DD")


def _cost_columns(cost_per_sheet: float, cost_per_mono: float, cost_per_color: float) -> str:
    """
    Generiert SQL-Ausdrücke für die Kostenberechnung.
    Bildet die PowerBI DAX-Formeln in T-SQL nach.
    """
    return f"""
        -- Sheet count: ROUNDUP(page_count/2) bei Duplex, sonst page_count
        CASE WHEN td.duplex = 1
             THEN CEILING(CAST(td.page_count AS FLOAT) / 2)
             ELSE td.page_count
        END AS sheet_count,

        -- Toner Farbe
        CASE WHEN td.color = 1 THEN td.page_count * {cost_per_color} ELSE 0 END AS toner_cost_color,

        -- Toner S/W
        CASE WHEN td.color = 0 THEN td.page_count * {cost_per_mono} ELSE 0 END AS toner_cost_bw,

        -- Sheet-Kosten
        CASE WHEN td.duplex = 1
             THEN CEILING(CAST(td.page_count AS FLOAT) / 2) * {cost_per_sheet}
             ELSE td.page_count * {cost_per_sheet}
        END AS sheet_cost,

        -- Gesamtkosten
        (CASE WHEN td.duplex = 1
              THEN CEILING(CAST(td.page_count AS FLOAT) / 2) * {cost_per_sheet}
              ELSE td.page_count * {cost_per_sheet}
         END)
        + (CASE WHEN td.color = 1 THEN td.page_count * {cost_per_color} ELSE 0 END)
        + (CASE WHEN td.color = 0 THEN td.page_count * {cost_per_mono} ELSE 0 END)
        AS total_cost
    """


# ─── 1. Druckvolumen-Statistik ────────────────────────────────────────────────

def query_print_stats(
    start_date: str,
    end_date: str,
    group_by: str = "day",        # day | week | month | user | printer | site
    site_id: Optional[str] = None,
    user_email: Optional[str] = None,
    printer_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Druckvolumen nach Zeitraum, User, Drucker oder Standort.

    group_by-Optionen:
      day     — Tagesweise Aggregation
      week    — Wochenweise
      month   — Monatsweise
      user    — Nach Benutzer
      printer — Nach Drucker
      site    — Nach Netzwerk/Standort
    """
    tenant_id = get_tenant_id()

    # Bei Gruppierung nach Benutzer verwenden wir COALESCE(u.name, u.email),
    # damit die Reports den lesbaren Anzeigenamen ('Hans Müller') zeigen
    # statt nur den abgeschnittenen E-Mail-Local-Part ('hans.mu').
    group_expr = {
        "day":     "CAST(td.print_time AS DATE)",
        "week":    "DATEADD(day, -(DATEPART(weekday, td.print_time) - 1), CAST(td.print_time AS DATE))",
        "month":   "DATEFROMPARTS(YEAR(td.print_time), MONTH(td.print_time), 1)",
        "user":    "COALESCE(u.name, u.email)",
        "printer": "p.name",
        "site":    "n.name",
    }.get(group_by, "CAST(td.print_time AS DATE)")

    label_col = {
        "day":     "CAST(td.print_time AS DATE) AS period",
        "week":    "DATEADD(day, -(DATEPART(weekday, td.print_time) - 1), CAST(td.print_time AS DATE)) AS period",
        "month":   "DATEFROMPARTS(YEAR(td.print_time), MONTH(td.print_time), 1) AS period",
        "user":    "COALESCE(u.name, u.email) AS period",
        "printer": "p.name AS period",
        "site":    "n.name AS period",
    }.get(group_by, "CAST(td.print_time AS DATE) AS period")

    where_extra = ""
    params_extra: list = []
    if site_id:
        where_extra += " AND p.network_id = ?"
        params_extra.append(site_id)
    if user_email:
        where_extra += " AND u.email = ?"
        params_extra.append(user_email)
    if printer_id:
        where_extra += " AND td.printer_id = ?"
        params_extra.append(printer_id)

    sql = f"""
        SELECT
            {label_col},
            COUNT(DISTINCT td.job_id)              AS total_jobs,
            SUM(td.page_count)                     AS total_pages,
            SUM(CASE WHEN td.color = 1 THEN td.page_count ELSE 0 END)  AS color_pages,
            SUM(CASE WHEN td.color = 0 THEN td.page_count ELSE 0 END)  AS bw_pages,
            SUM(CASE WHEN td.duplex = 1 THEN td.page_count ELSE 0 END) AS duplex_pages,
            CAST(SUM(CASE WHEN td.color = 1 THEN td.page_count ELSE 0 END) * 100.0
                 / NULLIF(SUM(td.page_count), 0) AS DECIMAL(5,1))      AS color_pct,
            CAST(SUM(CASE WHEN td.duplex = 1 THEN td.page_count ELSE 0 END) * 100.0
                 / NULLIF(SUM(td.page_count), 0) AS DECIMAL(5,1))      AS duplex_pct,
            -- Eingespartes Papier durch Duplex
            SUM(CASE WHEN td.duplex = 1
                     THEN td.page_count - CEILING(CAST(td.page_count AS FLOAT)/2)
                     ELSE 0 END)                   AS saved_sheets_duplex
        FROM {_V('tracking_data')} td
        LEFT JOIN {_V('jobs')}     j ON j.id = td.job_id AND j.tenant_id = td.tenant_id
        LEFT JOIN {_V('users')}    u ON u.id = j.tenant_user_id AND u.tenant_id = td.tenant_id
        LEFT JOIN {_V('printers')} p ON p.id = td.printer_id AND p.tenant_id = td.tenant_id
        LEFT JOIN {_V('networks')} n ON n.id = p.network_id AND n.tenant_id = td.tenant_id
        WHERE td.tenant_id = ?
          AND td.print_time >= ?
          AND td.print_time <  DATEADD(day, 1, CAST(? AS DATE))
          AND td.print_job_status = 'PRINT_OK'
          {where_extra}
        GROUP BY {group_expr}
        ORDER BY {group_expr}
    """
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date)) + tuple(params_extra)
    sql_results = query_fetchall(sql, params)

    # v4.4.0: Demo-Daten aus lokaler SQLite mergen
    if _has_active_demo():
        demo_rows = _get_demo_rows(start_date, end_date)
        if demo_rows:
            demo_agg = _aggregate_demo_print_stats(
                demo_rows, group_by, site_id=site_id,
                user_email=user_email, printer_id=printer_id)
            sql_results = _merge_aggregated(sql_results, demo_agg, "period")

    return sql_results


# ─── 2. Kostenaufstellung ─────────────────────────────────────────────────────

def query_cost_report(
    start_date: str,
    end_date: str,
    cost_per_sheet: float = 0.01,
    cost_per_mono: float  = 0.02,
    cost_per_color: float = 0.08,
    group_by: str = "month",
    site_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Kostenaufstellung mit Farb-/S&W-Aufschlüsselung.
    """
    tenant_id = get_tenant_id()

    group_expr = {
        "day":   "CAST(td.print_time AS DATE)",
        "week":  "DATEADD(day, -(DATEPART(weekday, td.print_time) - 1), CAST(td.print_time AS DATE))",
        "month": "DATEFROMPARTS(YEAR(td.print_time), MONTH(td.print_time), 1)",
        "site":  "n.name",
    }.get(group_by, "DATEFROMPARTS(YEAR(td.print_time), MONTH(td.print_time), 1)")

    label_col = {
        "day":   "CAST(td.print_time AS DATE) AS period",
        "week":  "DATEADD(day, -(DATEPART(weekday, td.print_time) - 1), CAST(td.print_time AS DATE)) AS period",
        "month": "DATEFROMPARTS(YEAR(td.print_time), MONTH(td.print_time), 1) AS period",
        "site":  "n.name AS period",
    }.get(group_by, "DATEFROMPARTS(YEAR(td.print_time), MONTH(td.print_time), 1) AS period")

    where_extra = ""
    params_extra: list = []
    if site_id:
        where_extra += " AND p.network_id = ?"
        params_extra.append(site_id)

    sql = f"""
        SELECT
            {label_col},
            SUM(td.page_count)                                            AS total_pages,
            SUM(CASE WHEN td.color = 1 THEN td.page_count ELSE 0 END)    AS color_pages,
            SUM(CASE WHEN td.color = 0 THEN td.page_count ELSE 0 END)    AS bw_pages,
            SUM(CASE WHEN td.duplex = 1
                     THEN CEILING(CAST(td.page_count AS FLOAT) / 2)
                     ELSE td.page_count END)                              AS total_sheets,
            SUM(CASE WHEN td.color = 1 THEN td.page_count * {cost_per_color} ELSE 0 END)   AS toner_cost_color,
            SUM(CASE WHEN td.color = 0 THEN td.page_count * {cost_per_mono}  ELSE 0 END)   AS toner_cost_bw,
            SUM(CASE WHEN td.duplex = 1
                     THEN CEILING(CAST(td.page_count AS FLOAT) / 2) * {cost_per_sheet}
                     ELSE td.page_count * {cost_per_sheet} END)           AS sheet_cost,
            SUM(
                (CASE WHEN td.duplex = 1
                      THEN CEILING(CAST(td.page_count AS FLOAT) / 2) * {cost_per_sheet}
                      ELSE td.page_count * {cost_per_sheet} END)
                + (CASE WHEN td.color = 1 THEN td.page_count * {cost_per_color} ELSE 0 END)
                + (CASE WHEN td.color = 0 THEN td.page_count * {cost_per_mono}  ELSE 0 END)
            )                                                             AS total_cost
        FROM {_V('tracking_data')} td
        LEFT JOIN {_V('printers')} p ON p.id = td.printer_id AND p.tenant_id = td.tenant_id
        LEFT JOIN {_V('networks')} n ON n.id = p.network_id  AND n.tenant_id = td.tenant_id
        WHERE td.tenant_id = ?
          AND td.print_time >= ?
          AND td.print_time <  DATEADD(day, 1, CAST(? AS DATE))
          AND td.print_job_status = 'PRINT_OK'
          {where_extra}
        GROUP BY {group_expr}
        ORDER BY {group_expr}
    """
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date)) + tuple(params_extra)
    sql_results = query_fetchall(sql, params)

    # v4.4.0: Demo-Daten aus lokaler SQLite mergen
    if _has_active_demo():
        demo_rows = _get_demo_rows(start_date, end_date)
        if demo_rows:
            demo_agg = _aggregate_demo_cost_report(
                demo_rows, group_by, cost_per_sheet, cost_per_mono,
                cost_per_color, site_id=site_id)
            sql_results = _merge_aggregated(sql_results, demo_agg, "period")

    return sql_results


# ─── 3. Top User ──────────────────────────────────────────────────────────────

def query_top_users(
    start_date: str,
    end_date: str,
    top_n: int = 10,
    metric: str = "pages",
    cost_per_sheet: float = 0.01,
    cost_per_mono: float  = 0.02,
    cost_per_color: float = 0.08,
    site_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Ranking der aktivsten Nutzer nach Volumen oder Kosten."""
    tenant_id = get_tenant_id()

    order_col = {
        "pages":       "total_pages DESC",
        "cost":        "total_cost DESC",
        "jobs":        "total_jobs DESC",
        "color_pages": "color_pages DESC",
    }.get(metric, "total_pages DESC")

    where_extra = ""
    params_extra: list = []
    if site_id:
        where_extra += " AND p.network_id = ?"
        params_extra.append(site_id)

    sql = f"""
        SELECT TOP {int(top_n)}
            u.email,
            u.name,
            u.department,
            COUNT(DISTINCT td.job_id)                                           AS total_jobs,
            SUM(td.page_count)                                                  AS total_pages,
            SUM(CASE WHEN td.color = 1 THEN td.page_count ELSE 0 END)          AS color_pages,
            SUM(CASE WHEN td.color = 0 THEN td.page_count ELSE 0 END)          AS bw_pages,
            SUM(CASE WHEN td.duplex = 1 THEN td.page_count ELSE 0 END)         AS duplex_pages,
            CAST(SUM(CASE WHEN td.color = 1 THEN td.page_count ELSE 0 END) * 100.0
                 / NULLIF(SUM(td.page_count), 0) AS DECIMAL(5,1))              AS color_pct,
            SUM(
                (CASE WHEN td.duplex = 1
                      THEN CEILING(CAST(td.page_count AS FLOAT) / 2) * {cost_per_sheet}
                      ELSE td.page_count * {cost_per_sheet} END)
                + (CASE WHEN td.color = 1 THEN td.page_count * {cost_per_color} ELSE 0 END)
                + (CASE WHEN td.color = 0 THEN td.page_count * {cost_per_mono}  ELSE 0 END)
            )                                                                   AS total_cost
        FROM {_V('tracking_data')} td
        JOIN  {_V('jobs')}     j ON j.id = td.job_id       AND j.tenant_id = td.tenant_id
        JOIN  {_V('users')}    u ON u.id = j.tenant_user_id AND u.tenant_id = td.tenant_id
        LEFT JOIN {_V('printers')} p ON p.id = td.printer_id AND p.tenant_id = td.tenant_id
        WHERE td.tenant_id = ?
          AND td.print_time >= ?
          AND td.print_time <  DATEADD(day, 1, CAST(? AS DATE))
          AND td.print_job_status = 'PRINT_OK'
          {where_extra}
        GROUP BY u.email, u.name, u.department
        ORDER BY {order_col}
    """
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date)) + tuple(params_extra)
    sql_results = query_fetchall(sql, params)

    # v4.4.0: Demo-Daten aus lokaler SQLite mergen
    if _has_active_demo():
        demo_rows = _get_demo_rows(start_date, end_date)
        if demo_rows:
            demo_agg = _aggregate_demo_top_users(
                demo_rows, top_n, metric, cost_per_sheet,
                cost_per_mono, cost_per_color, site_id=site_id)
            # Für Top-User: Demo-User zur Liste hinzufügen, re-sortieren, top_n
            combined = list(sql_results) + demo_agg
            sort_key = {"pages": "total_pages", "cost": "total_cost",
                        "jobs": "total_jobs", "color_pages": "color_pages"}.get(metric, "total_pages")
            combined.sort(key=lambda x: x.get(sort_key, 0), reverse=True)
            sql_results = combined[:top_n]

    return sql_results


# ─── 4. Top Drucker ───────────────────────────────────────────────────────────

def query_top_printers(
    start_date: str,
    end_date: str,
    top_n: int = 10,
    metric: str = "pages",
    cost_per_sheet: float = 0.01,
    cost_per_mono: float  = 0.02,
    cost_per_color: float = 0.08,
    site_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Ranking der meistgenutzten Drucker nach Volumen oder Kosten."""
    tenant_id = get_tenant_id()

    order_col = {
        "pages":       "total_pages DESC",
        "cost":        "total_cost DESC",
        "jobs":        "total_jobs DESC",
        "color_pages": "color_pages DESC",
    }.get(metric, "total_pages DESC")

    where_extra = ""
    params_extra: list = []
    if site_id:
        where_extra += " AND p.network_id = ?"
        params_extra.append(site_id)

    sql = f"""
        SELECT TOP {int(top_n)}
            p.name                                                              AS printer_name,
            p.model_name,
            p.vendor_name,
            p.location,
            n.name                                                              AS site_name,
            COUNT(DISTINCT td.job_id)                                           AS total_jobs,
            SUM(td.page_count)                                                  AS total_pages,
            SUM(CASE WHEN td.color = 1 THEN td.page_count ELSE 0 END)          AS color_pages,
            SUM(CASE WHEN td.color = 0 THEN td.page_count ELSE 0 END)          AS bw_pages,
            CAST(SUM(CASE WHEN td.color = 1 THEN td.page_count ELSE 0 END) * 100.0
                 / NULLIF(SUM(td.page_count), 0) AS DECIMAL(5,1))              AS color_pct,
            SUM(
                (CASE WHEN td.duplex = 1
                      THEN CEILING(CAST(td.page_count AS FLOAT) / 2) * {cost_per_sheet}
                      ELSE td.page_count * {cost_per_sheet} END)
                + (CASE WHEN td.color = 1 THEN td.page_count * {cost_per_color} ELSE 0 END)
                + (CASE WHEN td.color = 0 THEN td.page_count * {cost_per_mono}  ELSE 0 END)
            )                                                                   AS total_cost
        FROM {_V('tracking_data')} td
        LEFT JOIN {_V('printers')} p ON p.id = td.printer_id AND p.tenant_id = td.tenant_id
        LEFT JOIN {_V('networks')} n ON n.id = p.network_id  AND n.tenant_id = td.tenant_id
        WHERE td.tenant_id = ?
          AND td.print_time >= ?
          AND td.print_time <  DATEADD(day, 1, CAST(? AS DATE))
          AND td.print_job_status = 'PRINT_OK'
          {where_extra}
        GROUP BY p.name, p.model_name, p.vendor_name, p.location, n.name
        ORDER BY {order_col}
    """
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date)) + tuple(params_extra)
    sql_results = query_fetchall(sql, params)

    # v4.4.0: Demo-Daten aus lokaler SQLite mergen
    if _has_active_demo():
        demo_rows = _get_demo_rows(start_date, end_date)
        if demo_rows:
            demo_agg = _aggregate_demo_top_printers(
                demo_rows, top_n, metric, cost_per_sheet,
                cost_per_mono, cost_per_color, site_id=site_id)
            combined = list(sql_results) + demo_agg
            sort_key = {"pages": "total_pages", "cost": "total_cost",
                        "jobs": "total_jobs", "color_pages": "color_pages"}.get(metric, "total_pages")
            combined.sort(key=lambda x: x.get(sort_key, 0), reverse=True)
            sql_results = combined[:top_n]

    return sql_results


# ─── 5. Anomalie-Erkennung ────────────────────────────────────────────────────

def query_anomalies(
    start_date: str,
    end_date: str,
    threshold_multiplier: float = 2.5,
) -> list[dict[str, Any]]:
    """Erkennt Ausreißer: Tage mit ungewöhnlich hohem Druckvolumen."""
    tenant_id = get_tenant_id()

    sql = f"""
        WITH daily AS (
            SELECT
                CAST(print_time AS DATE)   AS print_day,
                SUM(page_count)            AS daily_pages,
                COUNT(DISTINCT job_id)     AS daily_jobs
            FROM {_V('tracking_data')}
            WHERE tenant_id = ?
              AND print_time >= ?
              AND print_time <  DATEADD(day, 1, CAST(? AS DATE))
              AND print_job_status = 'PRINT_OK'
            GROUP BY CAST(print_time AS DATE)
        ),
        stats AS (
            SELECT
                AVG(CAST(daily_pages AS FLOAT))   AS avg_pages,
                STDEV(CAST(daily_pages AS FLOAT)) AS std_pages
            FROM daily
        )
        SELECT
            d.print_day,
            d.daily_pages,
            d.daily_jobs,
            ROUND(s.avg_pages, 0)              AS avg_pages,
            ROUND(s.std_pages, 0)              AS std_pages,
            ROUND(s.avg_pages + {threshold_multiplier} * s.std_pages, 0) AS threshold,
            ROUND((d.daily_pages - s.avg_pages) / NULLIF(s.std_pages, 0), 2) AS z_score,
            CASE WHEN d.daily_pages > s.avg_pages + {threshold_multiplier} * s.std_pages
                 THEN 'ANOMALIE_HOCH'
                 WHEN d.daily_pages < GREATEST(0, s.avg_pages - {threshold_multiplier} * s.std_pages)
                 THEN 'ANOMALIE_NIEDRIG'
                 ELSE 'NORMAL'
            END                                AS status
        FROM daily d
        CROSS JOIN stats s
        WHERE d.daily_pages > s.avg_pages + {threshold_multiplier} * s.std_pages
           OR d.daily_pages < GREATEST(0, s.avg_pages - {threshold_multiplier} * s.std_pages)
        ORDER BY ABS(d.daily_pages - s.avg_pages) DESC
    """
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date))
    return query_fetchall(sql, params)


# ─── 6. Trend-Vergleich ───────────────────────────────────────────────────────

def query_trend(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str,
    cost_per_sheet: float = 0.01,
    cost_per_mono: float  = 0.02,
    cost_per_color: float = 0.08,
) -> dict[str, Any]:
    """Vergleich zweier Zeiträume."""
    tenant_id = get_tenant_id()

    def _period_sql(start: str, end: str) -> tuple[str, tuple]:
        sql = f"""
            SELECT
                COUNT(DISTINCT td.job_id)                                       AS total_jobs,
                SUM(td.page_count)                                              AS total_pages,
                SUM(CASE WHEN td.color = 1 THEN td.page_count ELSE 0 END)      AS color_pages,
                SUM(CASE WHEN td.color = 0 THEN td.page_count ELSE 0 END)      AS bw_pages,
                SUM(CASE WHEN td.duplex = 1 THEN td.page_count ELSE 0 END)     AS duplex_pages,
                COUNT(DISTINCT j.tenant_user_id)                                AS active_users,
                COUNT(DISTINCT td.printer_id)                                   AS active_printers,
                SUM(
                    (CASE WHEN td.duplex = 1
                          THEN CEILING(CAST(td.page_count AS FLOAT) / 2) * {cost_per_sheet}
                          ELSE td.page_count * {cost_per_sheet} END)
                    + (CASE WHEN td.color = 1 THEN td.page_count * {cost_per_color} ELSE 0 END)
                    + (CASE WHEN td.color = 0 THEN td.page_count * {cost_per_mono}  ELSE 0 END)
                )                                                               AS total_cost
            FROM {_V('tracking_data')} td
            JOIN {_V('jobs')} j ON j.id = td.job_id AND j.tenant_id = td.tenant_id
            WHERE td.tenant_id = ?
              AND td.print_time >= ?
              AND td.print_time <  DATEADD(day, 1, CAST(? AS DATE))
              AND td.print_job_status = 'PRINT_OK'
        """
        return sql, (tenant_id, _fmt_date(start), _fmt_date(end))

    sql1, params1 = _period_sql(period1_start, period1_end)
    sql2, params2 = _period_sql(period2_start, period2_end)

    from .sql_client import query_fetchone
    p1 = query_fetchone(sql1, params1) or {}
    p2 = query_fetchone(sql2, params2) or {}

    def _delta_pct(new_val, old_val):
        if not old_val:
            return None
        return round((new_val - old_val) / old_val * 100, 1)

    return {
        "period1": {"start": period1_start, "end": period1_end, **p1},
        "period2": {"start": period2_start, "end": period2_end, **p2},
        "delta": {
            "total_pages":    _delta_pct(p2.get("total_pages", 0), p1.get("total_pages", 0)),
            "color_pages":    _delta_pct(p2.get("color_pages", 0), p1.get("color_pages", 0)),
            "total_cost":     _delta_pct(p2.get("total_cost", 0),  p1.get("total_cost", 0)),
            "active_users":   _delta_pct(p2.get("active_users", 0), p1.get("active_users", 0)),
            "total_jobs":     _delta_pct(p2.get("total_jobs", 0),  p1.get("total_jobs", 0)),
        },
    }


# ─── 7. Drucker-Historie ──────────────────────────────────────────────────────

def query_printer_history(
    start_date: str,
    end_date: str,
    printer_id: Optional[str] = None,
    group_by: str = "month",
    site_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Per-Drucker Druckvolumen über Zeit.
    printer_id: wenn gesetzt, nur dieser eine Drucker (UUID-String).
    group_by: day | week | month
    """
    tenant_id = get_tenant_id()

    group_expr = {
        "day":   "CAST(td.print_time AS DATE)",
        "week":  "DATEADD(day, -(DATEPART(weekday, td.print_time) - 1), CAST(td.print_time AS DATE))",
        "month": "DATEFROMPARTS(YEAR(td.print_time), MONTH(td.print_time), 1)",
    }.get(group_by, "DATEFROMPARTS(YEAR(td.print_time), MONTH(td.print_time), 1)")

    label_col = {
        "day":   "CAST(td.print_time AS DATE) AS period",
        "week":  "DATEADD(day, -(DATEPART(weekday, td.print_time) - 1), CAST(td.print_time AS DATE)) AS period",
        "month": "DATEFROMPARTS(YEAR(td.print_time), MONTH(td.print_time), 1) AS period",
    }.get(group_by, "DATEFROMPARTS(YEAR(td.print_time), MONTH(td.print_time), 1) AS period")

    where_extra = ""
    params_extra: list = []
    if printer_id:
        where_extra += " AND td.printer_id = ?"
        params_extra.append(printer_id)
    if site_id:
        where_extra += " AND p.network_id = ?"
        params_extra.append(site_id)

    sql = f"""
        SELECT
            {label_col},
            p.name                                                              AS printer_name,
            p.model_name,
            n.name                                                              AS site_name,
            COUNT(DISTINCT td.job_id)                                           AS total_jobs,
            SUM(td.page_count)                                                  AS total_pages,
            SUM(CASE WHEN td.color = 1 THEN td.page_count ELSE 0 END)          AS color_pages,
            SUM(CASE WHEN td.color = 0 THEN td.page_count ELSE 0 END)          AS bw_pages,
            SUM(CASE WHEN td.duplex = 1 THEN td.page_count ELSE 0 END)         AS duplex_pages,
            CAST(SUM(CASE WHEN td.duplex = 1 THEN td.page_count ELSE 0 END) * 100.0
                 / NULLIF(SUM(td.page_count), 0) AS DECIMAL(5,1))              AS duplex_pct
        FROM {_V('tracking_data')} td
        LEFT JOIN {_V('printers')} p ON p.id = td.printer_id AND p.tenant_id = td.tenant_id
        LEFT JOIN {_V('networks')} n ON n.id = p.network_id  AND n.tenant_id = td.tenant_id
        WHERE td.tenant_id = ?
          AND td.print_time >= ?
          AND td.print_time <  DATEADD(day, 1, CAST(? AS DATE))
          AND td.print_job_status = 'PRINT_OK'
          {where_extra}
        GROUP BY {group_expr}, p.name, p.model_name, n.name
        ORDER BY {group_expr}, total_pages DESC
    """
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date)) + tuple(params_extra)
    return query_fetchall(sql, params)


# ─── 8. Gerätewerte / Device Overview ────────────────────────────────────────

def query_device_readings(
    start_date: str,
    end_date: str,
    site_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Drucker-Übersicht: Auslastung + letzte Aktivität pro Gerät.
    Toner-Füllstände sind nicht in der SQL-Datenbank.
    Gibt alle Drucker zurück, auch inaktive (total_pages = 0).
    """
    tenant_id = get_tenant_id()

    where_extra = ""
    params_extra: list = []
    if site_id:
        where_extra += " AND p.network_id = ?"
        params_extra.append(site_id)

    sql = f"""
        SELECT
            p.id                                                                  AS printer_id,
            p.name                                                                AS printer_name,
            p.model_name,
            p.vendor_name,
            p.location,
            n.name                                                                AS site_name,
            COUNT(DISTINCT td.job_id)                                             AS total_jobs,
            ISNULL(SUM(td.page_count), 0)                                         AS total_pages,
            ISNULL(SUM(CASE WHEN td.color = 1 THEN td.page_count ELSE 0 END), 0)  AS color_pages,
            ISNULL(SUM(CASE WHEN td.color = 0 THEN td.page_count ELSE 0 END), 0)  AS bw_pages,
            MAX(td.print_time)                                                    AS last_activity,
            COUNT(DISTINCT CAST(td.print_time AS DATE))                           AS active_days
        FROM {_V('printers')} p
        LEFT JOIN {_V('networks')} n
               ON n.id = p.network_id AND n.tenant_id = p.tenant_id
        LEFT JOIN {_V('tracking_data')} td
               ON td.printer_id = p.id
              AND td.tenant_id  = p.tenant_id
              AND td.print_time >= ?
              AND td.print_time  < DATEADD(day, 1, CAST(? AS DATE))
              AND td.print_job_status = 'PRINT_OK'
        WHERE p.tenant_id = ?
          {where_extra}
        GROUP BY p.id, p.name, p.model_name, p.vendor_name, p.location, n.name
        ORDER BY ISNULL(SUM(td.page_count), 0) DESC
    """
    params = (_fmt_date(start_date), _fmt_date(end_date), tenant_id) + tuple(params_extra)
    return query_fetchall(sql, params)


# ─── 9. Job-Verlauf (paginiert) ───────────────────────────────────────────────

def query_job_history(
    start_date: str,
    end_date: str,
    page: int = 0,
    page_size: int = 100,
    site_id: Optional[str] = None,
    user_email: Optional[str] = None,
    printer_id: Optional[str] = None,
    status_filter: str = "ok",   # ok | failed | all
) -> list[dict[str, Any]]:
    """
    Rohe Job-Liste mit Paginierung (OFFSET/FETCH NEXT).
    status_filter: 'ok' = nur PRINT_OK, 'failed' = Fehler, 'all' = alles
    """
    tenant_id = get_tenant_id()

    status_clause = ""
    if status_filter == "ok":
        status_clause = "AND td.print_job_status = 'PRINT_OK'"
    elif status_filter == "failed":
        status_clause = "AND td.print_job_status <> 'PRINT_OK'"

    where_extra = ""
    params_extra: list = []
    if site_id:
        where_extra += " AND p.network_id = ?"
        params_extra.append(site_id)
    if user_email:
        where_extra += " AND u.email = ?"
        params_extra.append(user_email)
    if printer_id:
        where_extra += " AND td.printer_id = ?"
        params_extra.append(printer_id)

    offset = max(0, int(page)) * max(1, int(page_size))
    fetch  = max(1, min(int(page_size), 1000))

    sql = f"""
        SELECT
            td.job_id,
            td.print_time,
            td.print_job_status                                                 AS status,
            u.email                                                             AS user_email,
            u.name                                                              AS user_name,
            p.name                                                              AS printer_name,
            n.name                                                              AS site_name,
            td.page_count,
            td.color,
            td.duplex,
            j.paper_size
        FROM {_V('tracking_data')} td
        LEFT JOIN {_V('jobs')}     j ON j.id = td.job_id          AND j.tenant_id = td.tenant_id
        LEFT JOIN {_V('users')}    u ON u.id = j.tenant_user_id   AND u.tenant_id = td.tenant_id
        LEFT JOIN {_V('printers')} p ON p.id = td.printer_id      AND p.tenant_id = td.tenant_id
        LEFT JOIN {_V('networks')} n ON n.id = p.network_id       AND n.tenant_id = td.tenant_id
        WHERE td.tenant_id = ?
          AND td.print_time >= ?
          AND td.print_time <  DATEADD(day, 1, CAST(? AS DATE))
          {status_clause}
          {where_extra}
        ORDER BY td.print_time DESC
        OFFSET {offset} ROWS FETCH NEXT {fetch} ROWS ONLY
    """
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date)) + tuple(params_extra)
    return query_fetchall(sql, params)


# ─── 10. Queue-Statistik ──────────────────────────────────────────────────────

def query_queue_stats(
    start_date: str,
    end_date: str,
    site_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Druckauftrags-Verteilung nach Papierformat, Farbe und Duplex-Modus.
    Zeigt Zusammensetzung des Druckvolumens (Papier-Mix, Farbanteil).
    """
    tenant_id = get_tenant_id()

    where_extra = ""
    params_extra: list = []
    if site_id:
        where_extra += " AND p.network_id = ?"
        params_extra.append(site_id)

    sql = f"""
        SELECT
            ISNULL(j.paper_size, 'UNKNOWN')                                     AS paper_size,
            td.color,
            td.duplex,
            COUNT(DISTINCT td.job_id)                                           AS total_jobs,
            SUM(td.page_count)                                                  AS total_pages,
            CAST(SUM(td.page_count) * 100.0
                 / NULLIF(SUM(SUM(td.page_count)) OVER (), 0) AS DECIMAL(5,1)) AS pct_of_total
        FROM {_V('tracking_data')} td
        LEFT JOIN {_V('jobs')}     j ON j.id = td.job_id     AND j.tenant_id = td.tenant_id
        LEFT JOIN {_V('printers')} p ON p.id = td.printer_id AND p.tenant_id = td.tenant_id
        WHERE td.tenant_id = ?
          AND td.print_time >= ?
          AND td.print_time <  DATEADD(day, 1, CAST(? AS DATE))
          AND td.print_job_status = 'PRINT_OK'
          {where_extra}
        GROUP BY j.paper_size, td.color, td.duplex
        ORDER BY total_pages DESC
    """
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date)) + tuple(params_extra)
    return query_fetchall(sql, params)


# ─── 11. User-Detail ──────────────────────────────────────────────────────────

def query_user_detail(
    start_date: str,
    end_date: str,
    user_email: str,
    group_by: str = "month",
) -> list[dict[str, Any]]:
    """
    Detaillierter Druckverlauf eines einzelnen Benutzers über Zeit.
    Inkl. Scan- und Kopier-Jobs.
    """
    tenant_id = get_tenant_id()

    group_expr = {
        "day":   "CAST(td.print_time AS DATE)",
        "week":  "DATEADD(day, -(DATEPART(weekday, td.print_time) - 1), CAST(td.print_time AS DATE))",
        "month": "DATEFROMPARTS(YEAR(td.print_time), MONTH(td.print_time), 1)",
    }.get(group_by, "DATEFROMPARTS(YEAR(td.print_time), MONTH(td.print_time), 1)")

    label_col = {
        "day":   "CAST(td.print_time AS DATE) AS period",
        "week":  "DATEADD(day, -(DATEPART(weekday, td.print_time) - 1), CAST(td.print_time AS DATE)) AS period",
        "month": "DATEFROMPARTS(YEAR(td.print_time), MONTH(td.print_time), 1) AS period",
    }.get(group_by, "DATEFROMPARTS(YEAR(td.print_time), MONTH(td.print_time), 1) AS period")

    sql = f"""
        SELECT
            {label_col},
            u.email,
            u.name,
            u.department,
            COUNT(DISTINCT td.job_id)                                           AS print_jobs,
            SUM(td.page_count)                                                  AS print_pages,
            SUM(CASE WHEN td.color = 1 THEN td.page_count ELSE 0 END)          AS color_pages,
            SUM(CASE WHEN td.color = 0 THEN td.page_count ELSE 0 END)          AS bw_pages,
            SUM(CASE WHEN td.duplex = 1 THEN td.page_count ELSE 0 END)         AS duplex_pages,
            CAST(SUM(CASE WHEN td.color = 1 THEN td.page_count ELSE 0 END) * 100.0
                 / NULLIF(SUM(td.page_count), 0) AS DECIMAL(5,1))              AS color_pct
        FROM {_V('tracking_data')} td
        JOIN  {_V('jobs')}  j ON j.id = td.job_id        AND j.tenant_id = td.tenant_id
        JOIN  {_V('users')} u ON u.id = j.tenant_user_id AND u.tenant_id = td.tenant_id
        WHERE td.tenant_id = ?
          AND td.print_time >= ?
          AND td.print_time <  DATEADD(day, 1, CAST(? AS DATE))
          AND td.print_job_status = 'PRINT_OK'
          AND u.email = ?
        GROUP BY {group_expr}, u.email, u.name, u.department
        ORDER BY {group_expr}
    """
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date), user_email)
    return query_fetchall(sql, params)


# ─── 12. Kopier-Jobs pro User ─────────────────────────────────────────────────

def query_user_copy_detail(
    start_date: str,
    end_date: str,
    user_email: Optional[str] = None,
    group_by: str = "month",
    site_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Kopier-Jobs (jobs_copy + jobs_copy_details) pro Benutzer über Zeit.
    """
    tenant_id = get_tenant_id()

    group_expr = {
        "day":   "CAST(jc.copy_time AS DATE)",
        "week":  "DATEADD(day, -(DATEPART(weekday, jc.copy_time) - 1), CAST(jc.copy_time AS DATE))",
        "month": "DATEFROMPARTS(YEAR(jc.copy_time), MONTH(jc.copy_time), 1)",
    }.get(group_by, "DATEFROMPARTS(YEAR(jc.copy_time), MONTH(jc.copy_time), 1)")

    label_col = {
        "day":   "CAST(jc.copy_time AS DATE) AS period",
        "week":  "DATEADD(day, -(DATEPART(weekday, jc.copy_time) - 1), CAST(jc.copy_time AS DATE)) AS period",
        "month": "DATEFROMPARTS(YEAR(jc.copy_time), MONTH(jc.copy_time), 1) AS period",
    }.get(group_by, "DATEFROMPARTS(YEAR(jc.copy_time), MONTH(jc.copy_time), 1) AS period")

    where_extra = ""
    params_extra: list = []
    if user_email:
        where_extra += " AND u.email = ?"
        params_extra.append(user_email)
    if site_id:
        where_extra += " AND p.network_id = ?"
        params_extra.append(site_id)

    sql = f"""
        SELECT
            {label_col},
            u.email,
            u.name,
            p.name                                                              AS printer_name,
            n.name                                                              AS site_name,
            COUNT(DISTINCT jc.id)                                               AS total_copy_jobs,
            ISNULL(SUM(jcd.page_count), 0)                                      AS total_pages,
            ISNULL(SUM(CASE WHEN jcd.color = 1 THEN jcd.page_count ELSE 0 END), 0) AS color_pages,
            ISNULL(SUM(CASE WHEN jcd.color = 0 THEN jcd.page_count ELSE 0 END), 0) AS bw_pages,
            ISNULL(SUM(CASE WHEN jcd.duplex = 1 THEN jcd.page_count ELSE 0 END), 0) AS duplex_pages
        FROM {_V('jobs_copy')} jc
        LEFT JOIN {_V('jobs_copy_details')} jcd ON jcd.job_id = jc.id
        LEFT JOIN {_V('users')}    u ON u.id = jc.tenant_user_id AND u.tenant_id = jc.tenant_id
        LEFT JOIN {_V('printers')} p ON p.id = jc.printer_id     AND p.tenant_id = jc.tenant_id
        LEFT JOIN {_V('networks')} n ON n.id = p.network_id      AND n.tenant_id = jc.tenant_id
        WHERE jc.tenant_id = ?
          AND jc.copy_time >= ?
          AND jc.copy_time <  DATEADD(day, 1, CAST(? AS DATE))
          {where_extra}
        GROUP BY {group_expr}, u.email, u.name, p.name, n.name
        ORDER BY {group_expr}, total_pages DESC
    """
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date)) + tuple(params_extra)
    return query_fetchall(sql, params)


# ─── 13. Scan-Jobs pro User ───────────────────────────────────────────────────

def query_user_scan_detail(
    start_date: str,
    end_date: str,
    user_email: Optional[str] = None,
    group_by: str = "month",
    site_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Scan-Jobs (jobs_scan) pro Benutzer über Zeit.
    """
    tenant_id = get_tenant_id()

    group_expr = {
        "day":   "CAST(js.scan_time AS DATE)",
        "week":  "DATEADD(day, -(DATEPART(weekday, js.scan_time) - 1), CAST(js.scan_time AS DATE))",
        "month": "DATEFROMPARTS(YEAR(js.scan_time), MONTH(js.scan_time), 1)",
    }.get(group_by, "DATEFROMPARTS(YEAR(js.scan_time), MONTH(js.scan_time), 1)")

    label_col = {
        "day":   "CAST(js.scan_time AS DATE) AS period",
        "week":  "DATEADD(day, -(DATEPART(weekday, js.scan_time) - 1), CAST(js.scan_time AS DATE)) AS period",
        "month": "DATEFROMPARTS(YEAR(js.scan_time), MONTH(js.scan_time), 1) AS period",
    }.get(group_by, "DATEFROMPARTS(YEAR(js.scan_time), MONTH(js.scan_time), 1) AS period")

    where_extra = ""
    params_extra: list = []
    if user_email:
        where_extra += " AND u.email = ?"
        params_extra.append(user_email)
    if site_id:
        where_extra += " AND p.network_id = ?"
        params_extra.append(site_id)

    sql = f"""
        SELECT
            {label_col},
            u.email,
            u.name,
            p.name                                                              AS printer_name,
            n.name                                                              AS site_name,
            COUNT(DISTINCT js.id)                                               AS total_scan_jobs,
            SUM(js.page_count)                                                  AS total_pages,
            SUM(CASE WHEN js.color = 1 THEN js.page_count ELSE 0 END)          AS color_pages,
            SUM(CASE WHEN js.color = 0 THEN js.page_count ELSE 0 END)          AS bw_pages
        FROM {_V('jobs_scan')} js
        LEFT JOIN {_V('users')}    u ON u.id = js.tenant_user_id AND u.tenant_id = js.tenant_id
        LEFT JOIN {_V('printers')} p ON p.id = js.printer_id     AND p.tenant_id = js.tenant_id
        LEFT JOIN {_V('networks')} n ON n.id = p.network_id      AND n.tenant_id = js.tenant_id
        WHERE js.tenant_id = ?
          AND js.scan_time >= ?
          AND js.scan_time <  DATEADD(day, 1, CAST(? AS DATE))
          {where_extra}
        GROUP BY {group_expr}, u.email, u.name, p.name, n.name
        ORDER BY {group_expr}, total_pages DESC
    """
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date)) + tuple(params_extra)
    return query_fetchall(sql, params)


# ─── 14. Workstation-Übersicht ────────────────────────────────────────────────

def query_workstation_overview(
    start_date: str,
    end_date: str,
    site_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Workstation-Statistik. Erfordert dbo.workstations (optional in Printix BI Schema).
    Gibt leere Liste zurück wenn Tabelle nicht vorhanden.
    """
    tenant_id = get_tenant_id()
    from .sql_client import query_fetchone

    try:
        tbl_check = query_fetchone(
            "SELECT COUNT(*) AS cnt FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA IN ('dbo','reporting') AND TABLE_NAME IN ('workstations','v_workstations')"
        )
        if not (tbl_check or {}).get("cnt"):
            return [{"info": "workstations-Tabelle nicht in diesem Schema vorhanden"}]
    except Exception:
        return [{"info": "workstations-Tabelle nicht in diesem Schema vorhanden"}]

    where_extra = ""
    params_extra: list = []
    if site_id:
        where_extra += " AND w.network_id = ?"
        params_extra.append(site_id)

    sql = f"""
        SELECT
            w.id                                                                AS workstation_id,
            w.name                                                              AS workstation_name,
            w.os_type,
            n.name                                                              AS site_name,
            COUNT(DISTINCT j.id)                                                AS total_jobs,
            SUM(j.page_count)                                                   AS total_pages
        FROM {_V('workstations')} w
        LEFT JOIN {_V('networks')} n ON n.id = w.network_id AND n.tenant_id = w.tenant_id
        LEFT JOIN {_V('jobs')} j      ON j.workstation_id = w.id AND j.tenant_id = w.tenant_id
                                     AND j.submit_time >= ?
                                     AND j.submit_time < DATEADD(day, 1, CAST(? AS DATE))
        WHERE w.tenant_id = ?
          {where_extra}
        GROUP BY w.id, w.name, w.os_type, n.name
        ORDER BY total_pages DESC
    """
    params = (_fmt_date(start_date), _fmt_date(end_date), tenant_id) + tuple(params_extra)
    try:
        return query_fetchall(sql, params)
    except Exception as exc:
        return [{"error": str(exc)[:200]}]


# ─── 15. Workstation-Detail ───────────────────────────────────────────────────

def query_workstation_detail(
    start_date: str,
    end_date: str,
    workstation_id: str,
    group_by: str = "month",
) -> list[dict[str, Any]]:
    """
    Druckverlauf einer einzelnen Workstation über Zeit.
    Gibt leere Liste zurück wenn workstations-Tabelle nicht vorhanden.
    """
    tenant_id = get_tenant_id()
    from .sql_client import query_fetchone

    try:
        tbl_check = query_fetchone(
            "SELECT COUNT(*) AS cnt FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA IN ('dbo','reporting') AND TABLE_NAME IN ('workstations','v_workstations')"
        )
        if not (tbl_check or {}).get("cnt"):
            return [{"info": "workstations-Tabelle nicht in diesem Schema vorhanden"}]
    except Exception:
        return [{"info": "workstations-Tabelle nicht in diesem Schema vorhanden"}]

    group_expr = {
        "day":   "CAST(j.submit_time AS DATE)",
        "week":  "DATEADD(day, -(DATEPART(weekday, j.submit_time) - 1), CAST(j.submit_time AS DATE))",
        "month": "DATEFROMPARTS(YEAR(j.submit_time), MONTH(j.submit_time), 1)",
    }.get(group_by, "DATEFROMPARTS(YEAR(j.submit_time), MONTH(j.submit_time), 1)")

    label_col = {
        "day":   "CAST(j.submit_time AS DATE) AS period",
        "week":  "DATEADD(day, -(DATEPART(weekday, j.submit_time) - 1), CAST(j.submit_time AS DATE)) AS period",
        "month": "DATEFROMPARTS(YEAR(j.submit_time), MONTH(j.submit_time), 1) AS period",
    }.get(group_by, "DATEFROMPARTS(YEAR(j.submit_time), MONTH(j.submit_time), 1) AS period")

    sql = f"""
        SELECT
            {label_col},
            COUNT(DISTINCT j.id)                                                AS total_jobs,
            SUM(j.page_count)                                                   AS total_pages,
            SUM(CASE WHEN j.color = 1 THEN j.page_count ELSE 0 END)            AS color_pages,
            SUM(CASE WHEN j.color = 0 THEN j.page_count ELSE 0 END)            AS bw_pages,
            SUM(CASE WHEN j.duplex = 1 THEN j.page_count ELSE 0 END)           AS duplex_pages
        FROM {_V('jobs')} j
        WHERE j.tenant_id = ?
          AND j.workstation_id = ?
          AND j.submit_time >= ?
          AND j.submit_time <  DATEADD(day, 1, CAST(? AS DATE))
        GROUP BY {group_expr}
        ORDER BY {group_expr}
    """
    params = (tenant_id, workstation_id, _fmt_date(start_date), _fmt_date(end_date))
    try:
        return query_fetchall(sql, params)
    except Exception as exc:
        return [{"error": str(exc)[:200]}]


# ─── 16. Tree-Meter / Nachhaltigkeit ──────────────────────────────────────────

def query_tree_meter(
    start_date: str,
    end_date: str,
    sheets_per_tree: int = 8333,
    site_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Nachhaltigkeits-Kennzahlen: eingesparte Blätter durch Duplex,
    umgerechnet in Bäume (Standard: 1 Baum = 8333 A4-Blätter).

    Formel:
      saved_sheets = page_count - CEILING(page_count/2) für Duplex-Jobs
      trees_saved  = saved_sheets / sheets_per_tree
    """
    tenant_id = get_tenant_id()

    where_extra = ""
    params_extra: list = []
    if site_id:
        where_extra += " AND p.network_id = ?"
        params_extra.append(site_id)

    sql = f"""
        SELECT
            SUM(td.page_count)                                                  AS total_pages,
            SUM(CASE WHEN td.duplex = 1
                     THEN CEILING(CAST(td.page_count AS FLOAT) / 2)
                     ELSE td.page_count END)                                    AS total_sheets_used,
            SUM(CASE WHEN td.duplex = 1
                     THEN td.page_count - CEILING(CAST(td.page_count AS FLOAT) / 2)
                     ELSE 0 END)                                                AS saved_sheets_duplex,
            SUM(CASE WHEN td.duplex = 1 THEN td.page_count ELSE 0 END)         AS duplex_pages,
            SUM(CASE WHEN td.duplex = 0 THEN td.page_count ELSE 0 END)         AS simplex_pages,
            CAST(SUM(CASE WHEN td.duplex = 1 THEN td.page_count ELSE 0 END) * 100.0
                 / NULLIF(SUM(td.page_count), 0) AS DECIMAL(5,1))              AS duplex_pct
        FROM {_V('tracking_data')} td
        LEFT JOIN {_V('printers')} p ON p.id = td.printer_id AND p.tenant_id = td.tenant_id
        WHERE td.tenant_id = ?
          AND td.print_time >= ?
          AND td.print_time <  DATEADD(day, 1, CAST(? AS DATE))
          AND td.print_job_status = 'PRINT_OK'
          {where_extra}
    """
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date)) + tuple(params_extra)

    from .sql_client import query_fetchone
    row = query_fetchone(sql, params) or {}

    saved = int(row.get("saved_sheets_duplex") or 0)
    total_sheets = int(row.get("total_sheets_used") or 0)
    trees = round(saved / sheets_per_tree, 4) if sheets_per_tree else 0

    return {
        "start_date":           start_date,
        "end_date":             end_date,
        "total_pages":          int(row.get("total_pages") or 0),
        "total_sheets_used":    total_sheets,
        "saved_sheets_duplex":  saved,
        "trees_saved":          trees,
        "duplex_pages":         int(row.get("duplex_pages") or 0),
        "simplex_pages":        int(row.get("simplex_pages") or 0),
        "duplex_pct":           float(row.get("duplex_pct") or 0),
        "sheets_per_tree":      sheets_per_tree,
    }


# ─── 17. Service Desk / Fehlgeschlagene Jobs ──────────────────────────────────

def query_service_desk(
    start_date: str,
    end_date: str,
    site_id: Optional[str] = None,
    user_email: Optional[str] = None,
    group_by: str = "status",   # status | day | printer | user
) -> list[dict[str, Any]]:
    """
    Fehlgeschlagene und abgebrochene Druckaufträge für Service-Desk-Analysen.
    group_by: 'status' — nach Fehlertyp aggregiert
              'day'    — zeitlicher Verlauf
              'printer'— nach Drucker
              'user'   — nach Benutzer
    """
    tenant_id = get_tenant_id()

    where_extra = ""
    params_extra: list = []
    if site_id:
        where_extra += " AND p.network_id = ?"
        params_extra.append(site_id)
    if user_email:
        where_extra += " AND u.email = ?"
        params_extra.append(user_email)

    select_group = {
        "status":  "td.print_job_status AS group_key, td.print_job_status",
        "day":     "CAST(td.print_time AS DATE) AS group_key, td.print_job_status",
        "printer": "p.name AS group_key, td.print_job_status",
        "user":    "u.email AS group_key, td.print_job_status",
    }.get(group_by, "td.print_job_status AS group_key, td.print_job_status")

    group_by_clause = {
        "status":  "td.print_job_status",
        "day":     "CAST(td.print_time AS DATE), td.print_job_status",
        "printer": "p.name, td.print_job_status",
        "user":    "u.email, td.print_job_status",
    }.get(group_by, "td.print_job_status")

    sql = f"""
        SELECT
            {select_group},
            COUNT(DISTINCT td.job_id)                                           AS total_jobs,
            SUM(td.page_count)                                                  AS total_pages,
            MAX(td.print_time)                                                  AS last_occurrence
        FROM {_V('tracking_data')} td
        LEFT JOIN {_V('jobs')}     j ON j.id = td.job_id          AND j.tenant_id = td.tenant_id
        LEFT JOIN {_V('users')}    u ON u.id = j.tenant_user_id   AND u.tenant_id = td.tenant_id
        LEFT JOIN {_V('printers')} p ON p.id = td.printer_id      AND p.tenant_id = td.tenant_id
        LEFT JOIN {_V('networks')} n ON n.id = p.network_id       AND n.tenant_id = td.tenant_id
        WHERE td.tenant_id = ?
          AND td.print_time >= ?
          AND td.print_time <  DATEADD(day, 1, CAST(? AS DATE))
          AND td.print_job_status <> 'PRINT_OK'
          {where_extra}
        GROUP BY {group_by_clause}
        ORDER BY total_jobs DESC
    """
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date)) + tuple(params_extra)
    return query_fetchall(sql, params)


# ─── Universeller Dispatcher (v3.7.0) ────────────────────────────────────────

def _translate_trend_kwargs(kwargs: dict) -> dict:
    """v3.7.10: Wenn nur start_date/end_date geliefert werden (z.B. aus Preset-Templates),
    berechne period1 = [start_date..end_date] und period2 = vorangehendes gleich langes Fenster.
    Akzeptiert auch explizit gesetzte period1_*/period2_* (durchreichen unverändert)."""
    if "period1_start" in kwargs and "period2_start" in kwargs:
        # Alle 4 period-Parameter vorhanden — nur irrelevante Felder strippen
        allowed = {"period1_start", "period1_end", "period2_start", "period2_end",
                   "cost_per_sheet", "cost_per_mono", "cost_per_color"}
        return {k: v for k, v in kwargs.items() if k in allowed}
    start = kwargs.get("start_date")
    end   = kwargs.get("end_date")
    if not (start and end):
        raise ValueError("trend benötigt entweder period1_*/period2_* oder start_date/end_date")
    from datetime import date, timedelta
    def _parse(d):
        if isinstance(d, date):
            return d
        return date.fromisoformat(str(d)[:10])
    d1s = _parse(start)
    d1e = _parse(end)
    span_days = (d1e - d1s).days + 1
    d2e = d1s - timedelta(days=1)
    d2s = d2e - timedelta(days=span_days - 1)
    translated = {
        "period1_start": d1s.isoformat(),
        "period1_end":   d1e.isoformat(),
        "period2_start": d2s.isoformat(),
        "period2_end":   d2e.isoformat(),
    }
    for k in ("cost_per_sheet", "cost_per_mono", "cost_per_color"):
        if k in kwargs and kwargs[k] is not None:
            translated[k] = kwargs[k]
    return translated


# ─── 18. Sensible Dokumente (v3.8.0) ──────────────────────────────────────────

# Vordefinierte Keyword-Sets — key entspricht i18n-Key `sens_kw_set_<key>`.
# Die Listen enthalten Substring-Matches (CI) auf dem filename/job-name.
# Bewusst kurz gehalten, damit nicht alle Worte "Finanz" etc. auslösen —
# es sind typische, geschäftssensible Begriffe.
SENSITIVE_KEYWORD_SETS: dict[str, list[str]] = {
    "hr": [
        "Gehalt", "Lohn", "Lohnabrechnung", "Gehaltsabrechnung",
        "Kündigung", "Arbeitsvertrag", "Urlaubsantrag", "Abmahnung",
        "Personalakte", "Bewerbung", "Zeugnis",
    ],
    "finance": [
        "Kreditkarte", "Kontoauszug", "Rechnung", "Budget",
        "Bilanz", "Umsatz", "Mahnung", "Zahlungseingang",
        "Steuer", "Kalkulation",
    ],
    "confidential": [
        "Vertraulich", "Geheim", "Confidential", "Secret",
        "NDA", "Intern", "Entwurf", "Draft",
    ],
    "health": [
        "Arztbrief", "Diagnose", "Krankmeldung", "Attest",
        "Medikation", "Befund", "AU-Bescheinigung",
    ],
    "legal": [
        "Vertrag", "Klage", "Mahnbescheid", "Anwalt",
        "Gerichtsurteil", "Vollmacht", "Gutachten",
    ],
    "pii": [
        "Personalausweis", "Reisepass", "Passport",
        "Geburtsurkunde", "Sozialversicherung", "Meldebescheinigung",
    ],
}


def _resolve_sensitive_keywords(
    keyword_sets: Optional[list[str]] = None,
    custom_keywords: Optional[list[str]] = None,
) -> list[str]:
    """
    Baut die finale Keyword-Liste aus (optionalen) Preset-Sets +
    benutzerdefinierten Keywords. Whitespace wird getrimmt, Duplikate
    Case-Insensitive entfernt, Reihenfolge bleibt stabil.
    """
    seen_lower: set[str] = set()
    out: list[str] = []

    def _push(term: str) -> None:
        t = (term or "").strip()
        if not t:
            return
        low = t.lower()
        if low in seen_lower:
            return
        seen_lower.add(low)
        out.append(t)

    for key in (keyword_sets or []):
        for term in SENSITIVE_KEYWORD_SETS.get(key, []):
            _push(term)
    for term in (custom_keywords or []):
        _push(term)
    return out


def query_sensitive_documents(
    start_date: str,
    end_date: str,
    keyword_sets: Optional[list[str]] = None,
    custom_keywords: Optional[list[str]] = None,
    site_id: Optional[str] = None,
    user_email: Optional[str] = None,
    include_scans: bool = True,
    page: int = 0,
    page_size: int = 500,
) -> list[dict[str, Any]]:
    """
    v3.8.0 — Scannt Print- und Scan-Jobs auf sensible Keywords im filename.

    Liefert pro Treffer:
      document_type (print|scan), print_time, user_email, user_name,
      printer_name, site_name, filename, matched_keyword, page_count, color

    Die Keyword-Suche verwendet case-insensitive LIKE '%term%' — jede
    Kombination aus `keyword_sets` (Preset-Keys) und `custom_keywords`
    (freie Liste) wird OR-verknüpft. Fehlt jedes Keyword, werden als
    Fallback alle Preset-Sets verwendet.
    """
    tenant_id = get_tenant_id()

    terms = _resolve_sensitive_keywords(keyword_sets, custom_keywords)
    if not terms:
        # Fallback: wenn nichts angegeben, alle Sets zusammen nehmen
        terms = _resolve_sensitive_keywords(list(SENSITIVE_KEYWORD_SETS.keys()), None)
    # Safety-Cap: max. 40 Terms, sonst wird das SQL-Pattern monströs
    terms = terms[:40]

    # v3.8.0-fix (verstärkt in v3.8.1):
    # Spalten-Alias + Quell-Tabelle dynamisch auflösen.
    #
    # Reporting-Views können in zwei Zuständen existieren:
    #   a) v3.7.x-Definition → KEIN `filename`-Feld (stale)
    #   b) v3.8.0+-Definition → mit `filename`-Alias auf dbo.jobs.name
    #
    # Wenn die View stale ist (oder gar nicht existiert), gehen wir direkt an
    # `dbo.jobs` / `dbo.jobs_scan` ran und verwenden das reale Spalten-Namen
    # (`name` für Print, KEIN filename für Scan → Scan-Zweig deaktiviert).
    _jobs_tbl = _V('jobs')
    _jobs_scan_tbl = _V('jobs_scan')

    # Prüfe ob die View (falls vorhanden) tatsächlich eine filename-Spalte hat.
    from .sql_client import query_fetchone as _qfo
    def _view_has_column(fq_view: str, col: str) -> bool:
        try:
            r = _qfo(
                "SELECT COUNT(*) AS cnt FROM sys.columns "
                "WHERE object_id = OBJECT_ID(?) AND name = ?",
                (fq_view, col),
            )
            return bool((r or {}).get("cnt", 0) > 0)
        except Exception:
            return False

    # Entscheide Print-Quelle
    if _jobs_tbl.startswith("reporting.") and _view_has_column(_jobs_tbl, "filename"):
        _print_src = _jobs_tbl
        _print_filename_expr = "j.filename"
    else:
        # View hat kein filename-Feld (stale View, Schema-Setup nicht gelaufen).
        # Fallback auf dbo.jobs mit `name`-Spalte (Printix-Dokumentenname).
        # Hinweis: Demo-Daten (demo.jobs) fehlen in diesem Pfad — Benutzer
        # sollte "Schema einrichten" auf der Demo-Seite ausführen, damit die
        # reporting.v_jobs-View erstellt wird und beide Quellen vereint.
        _print_src = "dbo.jobs"
        _print_filename_expr = "j.name"

    # Entscheide Scan-Quelle (dbo.jobs_scan hat i.d.R. keinen filename — nur
    # die neue reporting.v_jobs_scan kennt ihn via demo-Migration).
    if include_scans:
        if _jobs_scan_tbl.startswith("reporting.") and _view_has_column(_jobs_scan_tbl, "filename"):
            _scan_src = _jobs_scan_tbl
        else:
            # Scan-View stale — direkt auf demo.jobs_scan mit filename
            _scan_src = "demo.jobs_scan"
    else:
        _scan_src = None

    # Dynamisches WHERE-OR über alle Keyword-LIKE-Klauseln.
    # pymssql/pyodbc: wir verwenden Parameterisierung, um SQL-Injection
    # vollständig zu vermeiden. Jedes term wird zu '%term%' gewrappt.
    like_clauses = []
    like_params: list = []
    for t in terms:
        like_clauses.append("LOWER(q.filename) LIKE LOWER(?)")
        like_params.append(f"%{t}%")
    keyword_where = "(" + " OR ".join(like_clauses) + ")"

    where_extra = ""
    extra_params: list = []
    if site_id:
        where_extra += " AND q.site_id = ?"
        extra_params.append(site_id)
    if user_email:
        where_extra += " AND q.user_email = ?"
        extra_params.append(user_email)

    offset = max(0, int(page)) * max(1, int(page_size))
    fetch  = max(1, min(int(page_size), 2000))

    # Wir fassen Print- und Scan-Quellen in einer Subquery zusammen, damit
    # wir nur einmal filtern und paginieren. Für Print-Jobs kommt filename
    # aus v_jobs (dort als `name`/`filename` aliased); Scan-Jobs brauchen
    # ebenfalls einen `filename`-Alias im View `reporting.v_jobs_scan`.
    scan_union = ""
    if include_scans:
        scan_union = f"""
            UNION ALL
            SELECT
                'scan'                AS document_type,
                js.scan_time          AS event_time,
                u.email               AS user_email,
                u.name                AS user_name,
                p.name                AS printer_name,
                n.name                AS site_name,
                n.id                  AS site_id,
                js.filename           AS filename,
                js.page_count         AS page_count,
                js.color              AS color
            FROM {_scan_src} js
            LEFT JOIN {_V('users')}    u ON u.id = js.tenant_user_id AND u.tenant_id = js.tenant_id
            LEFT JOIN {_V('printers')} p ON p.id = js.printer_id     AND p.tenant_id = js.tenant_id
            LEFT JOIN {_V('networks')} n ON n.id = p.network_id      AND n.tenant_id = js.tenant_id
            WHERE js.tenant_id = ?
              AND js.scan_time >= ?
              AND js.scan_time <  DATEADD(day, 1, CAST(? AS DATE))
              AND js.filename IS NOT NULL
              AND js.filename <> ''
        """

    sql = f"""
        SELECT TOP ({offset + fetch})
               document_type, event_time, user_email, user_name,
               printer_name, site_name, filename, page_count, color
        FROM (
            SELECT * FROM (
                SELECT
                    'print'               AS document_type,
                    j.submit_time         AS event_time,
                    u.email               AS user_email,
                    u.name                AS user_name,
                    p.name                AS printer_name,
                    n.name                AS site_name,
                    n.id                  AS site_id,
                    CAST({_print_filename_expr} AS NVARCHAR(500)) AS filename,
                    j.page_count          AS page_count,
                    j.color               AS color
                FROM {_print_src} j
                LEFT JOIN {_V('users')}    u ON u.id = j.tenant_user_id AND u.tenant_id = j.tenant_id
                LEFT JOIN {_V('printers')} p ON p.id = j.printer_id     AND p.tenant_id = j.tenant_id
                LEFT JOIN {_V('networks')} n ON n.id = p.network_id     AND n.tenant_id = j.tenant_id
                WHERE j.tenant_id = ?
                  AND j.submit_time >= ?
                  AND j.submit_time <  DATEADD(day, 1, CAST(? AS DATE))
                  AND {_print_filename_expr} IS NOT NULL
                  AND {_print_filename_expr} <> ''
                {scan_union}
            ) q
            WHERE {keyword_where}
            {where_extra}
        ) qq
        ORDER BY event_time DESC
    """
    # Params-Reihenfolge:
    # 1) print branch: tenant_id, start, end
    # 2) scan branch:  tenant_id, start, end (nur wenn include_scans)
    # 3) keyword like_params (einmal, auf aggregiertem q)
    # 4) extra filters (site_id, user_email)
    params: list = [tenant_id, _fmt_date(start_date), _fmt_date(end_date)]
    if include_scans:
        params.extend([tenant_id, _fmt_date(start_date), _fmt_date(end_date)])
    params.extend(like_params)
    params.extend(extra_params)

    rows = query_fetchall(sql, tuple(params))

    # Post-processing: matched_keyword pro Zeile annotieren (erster Treffer)
    lowered_terms = [(t.lower(), t) for t in terms]
    for r in rows:
        fn = (r.get("filename") or "").lower()
        matched = ""
        for low, orig in lowered_terms:
            if low in fn:
                matched = orig
                break
        r["matched_keyword"] = matched
    # Letzter Schliff: Paging client-side (TOP offset+fetch liefert N rows,
    # wir liefern die letzten `fetch` ab offset).
    if offset > 0:
        rows = rows[offset:]
    return rows[:fetch]


# ─── 19. Stunde × Wochentag Heatmap (v3.8.1) ──────────────────────────────────
# Aggregiert Druckvolumen nach Stunde (0..23) × Wochentag (1=Sonntag..7=Samstag)
# für die SVG-Heatmap in report_engine. Gibt eine flache Row-Liste zurück;
# fehlende Zellen werden im Engine-Layer mit 0 aufgefüllt.
def query_hour_dow_heatmap(
    start_date: str,
    end_date: str,
    site_id: Optional[str] = None,
    user_email: Optional[str] = None,
    printer_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Nutzungs-Heatmap: Stunde × Wochentag.

    Spalten pro Row:
      hour       — 0..23 (DATEPART hour)
      dow        — 1..7  (1 = Sonntag, 7 = Samstag; SQL Server DATEPART weekday
                          ist ab SET DATEFIRST abhängig, hier normalisiert)
      total_jobs — Anzahl eindeutiger Jobs
      total_pages— Summe Seiten
    """
    tenant_id = get_tenant_id()

    where_extra = ""
    params_extra: list = []
    if site_id:
        where_extra += " AND p.network_id = ?"
        params_extra.append(site_id)
    if user_email:
        where_extra += " AND u.email = ?"
        params_extra.append(user_email)
    if printer_id:
        where_extra += " AND td.printer_id = ?"
        params_extra.append(printer_id)

    # SET DATEFIRST 7 stellt sicher, dass 1=Sonntag .. 7=Samstag
    sql = f"""
        SET DATEFIRST 7;
        SELECT
            DATEPART(hour,    td.print_time) AS hour,
            DATEPART(weekday, td.print_time) AS dow,
            COUNT(DISTINCT td.job_id)        AS total_jobs,
            SUM(td.page_count)               AS total_pages
        FROM {_V('tracking_data')} td
        LEFT JOIN {_V('jobs')}     j ON j.id = td.job_id AND j.tenant_id = td.tenant_id
        LEFT JOIN {_V('users')}    u ON u.id = j.tenant_user_id AND u.tenant_id = td.tenant_id
        LEFT JOIN {_V('printers')} p ON p.id = td.printer_id AND p.tenant_id = td.tenant_id
        WHERE td.tenant_id = ?
          AND td.print_time >= ?
          AND td.print_time <  DATEADD(day, 1, CAST(? AS DATE))
          AND td.print_job_status = 'PRINT_OK'
          {where_extra}
        GROUP BY DATEPART(hour, td.print_time), DATEPART(weekday, td.print_time)
        ORDER BY dow, hour
    """
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date)) + tuple(params_extra)
    return query_fetchall(sql, params)


# ─── v3.9.0: Admin-Audit-Trail (SQLite, kein MSSQL) ──────────────────────────

def query_audit_log(
    start_date=None,
    end_date=None,
    tenant_id: str = "",
    action_prefix: str = "",
    limit: int = 1000,
    **_ignored,
):
    """Liest Admin-Audit-Log-Einträge aus der lokalen SQLite-DB.

    Kein Zugriff auf MSSQL — der Audit-Trail ist applikations-weit und
    in /data/printix_multi.db gespeichert. Der Report-Engine behandelt
    diesen Query-Typ über den generischen Stufe-2-Tabellen-Fallback.
    """
    try:
        # Verzögerter Import um Zirkularitäten zu vermeiden
        from db import query_audit_log_range  # type: ignore
    except Exception:
        # Fallback — db-Modul nicht importierbar
        return []
    rows = query_audit_log_range(
        start_date=start_date,
        end_date=end_date,
        tenant_id=tenant_id or "",
        action_prefix=action_prefix or "",
        limit=int(limit or 1000),
    )
    # Normalisiere Feldnamen → Display-freundlich für den Tabellen-Fallback
    out = []
    for r in rows:
        out.append({
            "timestamp": r.get("timestamp", ""),
            "actor": r.get("actor") or r.get("user_id") or "",
            "action": r.get("action", ""),
            "object_type": r.get("object_type", ""),
            "object_id": r.get("object_id", ""),
            "details": r.get("details", ""),
            "tenant_id": r.get("tenant_id", ""),
        })
    return out


# ─── v3.9.0: Druck außerhalb der Geschäftszeiten ─────────────────────────────

def query_off_hours_print(
    start_date=None,
    end_date=None,
    site_id: str = "",
    user_email: str = "",
    business_start_hour: int = 7,
    business_end_hour: int = 18,
    include_weekends_as_off_hours: bool = True,
    **_ignored,
):
    """Aggregiert Druckaktivität außerhalb der regulären Arbeitszeit.

    Default: Geschäftszeiten Mo–Fr 07:00–18:00. Alles andere gilt als Off-Hours.
    Liefert eine Zeitreihe mit Tages-Summe der Off-Hours-Jobs sowie ein
    Gesamt-Split (in-hours vs off-hours).
    """
    tenant_id = get_tenant_id()
    _jobs_tbl = _V('jobs')

    # Off-hours condition: hour outside business window OR weekend (DOW 1=Sun,7=Sat with DATEFIRST 7)
    weekend_clause = ""
    if include_weekends_as_off_hours:
        weekend_clause = " OR DATEPART(weekday, j.submit_time) IN (1, 7)"
    off_cond = (
        f"(DATEPART(hour, j.submit_time) < {int(business_start_hour)} "
        f"OR DATEPART(hour, j.submit_time) >= {int(business_end_hour)}"
        f"{weekend_clause})"
    )

    join_extra = ""
    where_extra = ""
    params_extra: list = []
    if site_id:
        join_extra += f" INNER JOIN {_V('printers')} p ON p.id = j.printer_id AND p.tenant_id = j.tenant_id"
        where_extra += " AND p.network_id = ?"
        params_extra.append(site_id)
    if user_email:
        join_extra += f" INNER JOIN {_V('users')} u ON u.id = j.tenant_user_id AND u.tenant_id = j.tenant_id"
        where_extra += " AND u.email = ?"
        params_extra.append(user_email)

    sql = f"""
        SET DATEFIRST 7;
        SELECT
            CONVERT(date, j.submit_time)                     AS day,
            SUM(CASE WHEN {off_cond} THEN 1 ELSE 0 END)      AS off_hours_jobs,
            SUM(CASE WHEN {off_cond} THEN 0 ELSE 1 END)      AS in_hours_jobs,
            COUNT(*)                                         AS total_jobs
        FROM {_jobs_tbl} j
        {join_extra}
        WHERE j.tenant_id = ?
          AND j.submit_time >= ?
          AND j.submit_time <  DATEADD(day, 1, CAST(? AS DATE))
          {where_extra}
        GROUP BY CONVERT(date, j.submit_time)
        ORDER BY day
    """
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date)) + tuple(params_extra)
    try:
        return query_fetchall(sql, params)
    except Exception as exc:
        return [{"error": str(exc)[:200]}]


def _filter_kwargs_to_sig(fn, kwargs: dict) -> dict:
    """
    v3.7.11: Filter kwargs to only those accepted by the target function.
    Schützt run_query-Dispatcher vor Stufe-2-Presets, die zusätzliche
    Layout-Keys (group_by, order_by, preset_id, …) in query_params ablegen.
    Unerwünschte Keys werden verworfen statt einen TypeError auszulösen.
    """
    import inspect as _insp
    try:
        sig = _insp.signature(fn)
    except (TypeError, ValueError):
        return kwargs
    params = sig.parameters
    if any(p.kind == _insp.Parameter.VAR_KEYWORD for p in params.values()):
        return kwargs
    allowed = {
        name for name, p in params.items()
        if p.kind in (_insp.Parameter.POSITIONAL_OR_KEYWORD, _insp.Parameter.KEYWORD_ONLY)
    }
    dropped = [k for k in kwargs if k not in allowed]
    if dropped:
        try:
            import logging as _log
            _log.getLogger("reporting.query_tools").debug(
                "run_query: %s() — dropped unsupported kwargs: %s",
                getattr(fn, "__name__", "?"), dropped
            )
        except Exception:
            pass
    return {k: v for k, v in kwargs.items() if k in allowed}


def run_query(query_type: str, tenant_id: str = "", **kwargs):
    """
    Dispatcher für alle Report-Query-Typen (Stufe 1 + 2).
    tenant_id wird ignoriert — der Caller ruft set_config_from_tenant() vorher.

    Stufe-1-Typen (Original):
      print_stats, cost_report, top_users, top_printers, trend, anomalies

    Stufe-2-Typen (neu):
      printer_history, device_readings, job_history, queue_stats,
      user_detail, user_copy_detail, user_scan_detail,
      workstation_overview, workstation_detail,
      tree_meter, service_desk
    """
    # ── Stufe 1 ──────────────────────────────────────────────────────────────
    if query_type == "print_stats":
        return query_print_stats(**_filter_kwargs_to_sig(query_print_stats, kwargs))
    elif query_type == "cost_report":
        return query_cost_report(**_filter_kwargs_to_sig(query_cost_report, kwargs))
    elif query_type == "top_users":
        return query_top_users(**_filter_kwargs_to_sig(query_top_users, kwargs))
    elif query_type == "top_printers":
        return query_top_printers(**_filter_kwargs_to_sig(query_top_printers, kwargs))
    elif query_type == "trend":
        # v3.7.10: start_date/end_date → period1/period2 übersetzen, damit
        # Preset-Templates und Scheduler nicht an "unexpected keyword" scheitern.
        return query_trend(**_filter_kwargs_to_sig(query_trend, _translate_trend_kwargs(kwargs)))
    elif query_type == "anomalies":
        return query_anomalies(**_filter_kwargs_to_sig(query_anomalies, kwargs))
    # ── Stufe 2 ──────────────────────────────────────────────────────────────
    elif query_type == "printer_history":
        return query_printer_history(**_filter_kwargs_to_sig(query_printer_history, kwargs))
    elif query_type == "device_readings":
        return query_device_readings(**_filter_kwargs_to_sig(query_device_readings, kwargs))
    elif query_type == "job_history":
        return query_job_history(**_filter_kwargs_to_sig(query_job_history, kwargs))
    elif query_type == "queue_stats":
        return query_queue_stats(**_filter_kwargs_to_sig(query_queue_stats, kwargs))
    elif query_type == "user_detail":
        return query_user_detail(**_filter_kwargs_to_sig(query_user_detail, kwargs))
    elif query_type == "user_copy_detail":
        return query_user_copy_detail(**_filter_kwargs_to_sig(query_user_copy_detail, kwargs))
    elif query_type == "user_scan_detail":
        return query_user_scan_detail(**_filter_kwargs_to_sig(query_user_scan_detail, kwargs))
    elif query_type == "workstation_overview":
        return query_workstation_overview(**_filter_kwargs_to_sig(query_workstation_overview, kwargs))
    elif query_type == "workstation_detail":
        return query_workstation_detail(**_filter_kwargs_to_sig(query_workstation_detail, kwargs))
    elif query_type == "tree_meter":
        return query_tree_meter(**_filter_kwargs_to_sig(query_tree_meter, kwargs))
    elif query_type == "service_desk":
        return query_service_desk(**_filter_kwargs_to_sig(query_service_desk, kwargs))
    # ── Stufe 2 (v3.8.0) ─────────────────────────────────────────────────────
    elif query_type == "sensitive_documents":
        return query_sensitive_documents(
            **_filter_kwargs_to_sig(query_sensitive_documents, kwargs)
        )
    # ── Stufe 2 (v3.8.1) ─────────────────────────────────────────────────────
    elif query_type == "hour_dow_heatmap":
        return query_hour_dow_heatmap(
            **_filter_kwargs_to_sig(query_hour_dow_heatmap, kwargs)
        )
    # ── Stufe 2 (v3.9.0) ─────────────────────────────────────────────────────
    elif query_type == "audit_log":
        return query_audit_log(
            **_filter_kwargs_to_sig(query_audit_log, kwargs)
        )
    elif query_type == "off_hours_print":
        return query_off_hours_print(
            **_filter_kwargs_to_sig(query_off_hours_print, kwargs)
        )
    elif query_type == "forecast":
        return query_forecast(**_filter_kwargs_to_sig(query_forecast, kwargs))
    else:
        raise ValueError(f"Unbekannter query_type: {query_type!r}")


# ─── Forecast / Prognose (v4.3.3) ───────────────────────────────────────────

def query_forecast(
    start_date: str,
    end_date: str,
    group_by: str = "month",      # day | week | month
    forecast_periods: int = 1,
    cost_per_sheet: float = 0.01,
    cost_per_mono: float  = 0.02,
    cost_per_color: float = 0.08,
) -> dict[str, Any]:
    """
    Historische Druckdaten + lineare Regression für Prognose.

    Gibt historische Datenpunkte und projizierte Werte zurück.
    Reine Python-Implementierung (kein numpy nötig).
    """
    # Historische Daten über query_print_stats holen
    historical = query_print_stats(
        start_date=start_date,
        end_date=end_date,
        group_by=group_by,
    )

    if not historical:
        return {
            "historical": [],
            "forecast": [],
            "slope": 0, "intercept": 0, "r_squared": 0,
            "prediction_text": "",
        }

    # Datenpunkte für Regression: x = Index, y = total_pages
    n = len(historical)
    xs = list(range(n))
    ys = [float(r.get("total_pages") or 0) for r in historical]

    slope, intercept, r_sq = _linear_regression(xs, ys)

    # Prognose-Punkte generieren
    forecasted = []
    for i in range(1, forecast_periods + 1):
        x_new = n - 1 + i
        y_pred = max(slope * x_new + intercept, 0)  # Nicht negativ
        forecasted.append({
            "period_index": x_new,
            "total_pages": round(y_pred),
            "is_forecast": True,
        })

    # Trend-Text
    if forecasted:
        next_val = forecasted[0]["total_pages"]
        last_val = ys[-1] if ys else 0
        if last_val > 0:
            change_pct = round((next_val - last_val) / last_val * 100, 1)
        else:
            change_pct = 0

        if change_pct > 5:
            trend = "up"
        elif change_pct < -5:
            trend = "down"
        else:
            trend = "stable"

        prediction_text = f"~{next_val:,.0f}"
    else:
        trend = "stable"
        prediction_text = ""
        change_pct = 0

    return {
        "historical": historical,
        "forecast": forecasted,
        "slope": round(slope, 2),
        "intercept": round(intercept, 2),
        "r_squared": round(r_sq, 3),
        "trend": trend,
        "change_pct": change_pct,
        "prediction_text": prediction_text,
    }


def _linear_regression(xs: list, ys: list) -> tuple[float, float, float]:
    """
    Einfache lineare Regression (Least Squares).
    Gibt (slope, intercept, r_squared) zurück.
    """
    n = len(xs)
    if n < 2:
        return (0.0, ys[0] if ys else 0.0, 0.0)

    sum_x  = sum(xs)
    sum_y  = sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    sum_x2 = sum(x * x for x in xs)
    sum_y2 = sum(y * y for y in ys)

    denom = n * sum_x2 - sum_x * sum_x
    if denom == 0:
        return (0.0, sum_y / n, 0.0)

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n

    # R² berechnen
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    mean_y = sum_y / n
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    return (slope, intercept, max(r_squared, 0.0))
