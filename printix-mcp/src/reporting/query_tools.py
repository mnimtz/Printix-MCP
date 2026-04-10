"""
Query Tools — Printix BI Datenabfragen
=======================================
Alle Abfragen gegen dbo-Schema der printix_bi_data_2_1 Datenbank.

Tabellenstruktur (aus PowerBI-Template extrahiert):
  dbo.tracking_data  — Druckaufträge (page_count, color, duplex, print_time, printer_id, job_id, tenant_id)
  dbo.jobs           — Jobs (id, tenant_id, color, duplex, page_count, paper_size, printer_id, submit_time, tenant_user_id)
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

import math
from datetime import date, datetime
from typing import Any, Optional

from .sql_client import query_fetchall, get_tenant_id


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

    group_expr = {
        "day":     "CAST(td.print_time AS DATE)",
        "week":    "DATEADD(day, -(DATEPART(weekday, td.print_time) - 1), CAST(td.print_time AS DATE))",
        "month":   "DATEFROMPARTS(YEAR(td.print_time), MONTH(td.print_time), 1)",
        "user":    "u.email",
        "printer": "p.name",
        "site":    "n.name",
    }.get(group_by, "CAST(td.print_time AS DATE)")

    label_col = {
        "day":     "CAST(td.print_time AS DATE) AS period",
        "week":    "DATEADD(day, -(DATEPART(weekday, td.print_time) - 1), CAST(td.print_time AS DATE)) AS period",
        "month":   "DATEFROMPARTS(YEAR(td.print_time), MONTH(td.print_time), 1) AS period",
        "user":    "u.email AS period",
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
    return query_fetchall(sql, params)


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
    return query_fetchall(sql, params)


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
    return query_fetchall(sql, params)


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
    return query_fetchall(sql, params)


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
