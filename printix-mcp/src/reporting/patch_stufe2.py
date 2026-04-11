"""
Patch-Script: Stufe 2 Query Types + Preset-Updates
Führt alle Änderungen für v3.7.0 durch.
"""
import os, sys

BASE = "/addons/printix-mcp-addon/printix-mcp/src/reporting"

# ═══════════════════════════════════════════════════════════════════════════════
# 1. query_tools.py — Syntax-Fix + 11 neue Query-Typen
# ═══════════════════════════════════════════════════════════════════════════════

QT_OLD = '''        },


# ── Universeller Dispatcher (v3.6.4) ─────────────────────────────────────────
def run_query(query_type: str, tenant_id: str = "", **kwargs) -> list:
    """Dispatcher für alle Report-Query-Typen.
    tenant_id wird ignoriert — der Caller ruft set_config_from_tenant() vorher.
    """
    if query_type == "print_stats":
        return query_print_stats(**kwargs)
    elif query_type == "cost_report":
        return query_cost_report(**kwargs)
    elif query_type == "top_users":
        return query_top_users(**kwargs)
    elif query_type == "top_printers":
        return query_top_printers(**kwargs)
    elif query_type == "trend":
        return query_trend(**kwargs)
    elif query_type == "anomalies":
        return query_anomalies(**kwargs)
    else:
        raise ValueError(f"Unbekannter query_type: {query_type!r}")
    }'''

QT_NEW = '''        },
    }


# ─── 7. Drucker-Historie ──────────────────────────────────────────────────────

def query_printer_history(
    start_date: str,
    end_date: str,
    printer_id = None,
    group_by: str = "month",
    site_id = None,
):
    """Per-Drucker Druckvolumen über Zeit."""
    from typing import Any, Optional
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
    params_extra = []
    if printer_id:
        where_extra += " AND td.printer_id = ?"
        params_extra.append(printer_id)
    if site_id:
        where_extra += " AND p.network_id = ?"
        params_extra.append(site_id)
    sql = f"""
        SELECT {label_col},
            p.name AS printer_name, p.model_name, n.name AS site_name,
            COUNT(DISTINCT td.job_id) AS total_jobs, SUM(td.page_count) AS total_pages,
            SUM(CASE WHEN td.color=1 THEN td.page_count ELSE 0 END) AS color_pages,
            SUM(CASE WHEN td.color=0 THEN td.page_count ELSE 0 END) AS bw_pages,
            SUM(CASE WHEN td.duplex=1 THEN td.page_count ELSE 0 END) AS duplex_pages,
            CAST(SUM(CASE WHEN td.duplex=1 THEN td.page_count ELSE 0 END)*100.0/NULLIF(SUM(td.page_count),0) AS DECIMAL(5,1)) AS duplex_pct
        FROM {_V('tracking_data')} td
        LEFT JOIN {_V('printers')} p ON p.id=td.printer_id AND p.tenant_id=td.tenant_id
        LEFT JOIN {_V('networks')} n ON n.id=p.network_id AND n.tenant_id=td.tenant_id
        WHERE td.tenant_id=? AND td.print_time>=? AND td.print_time<DATEADD(day,1,CAST(? AS DATE))
          AND td.print_job_status=\'PRINT_OK\' {where_extra}
        GROUP BY {group_expr}, p.name, p.model_name, n.name
        ORDER BY {group_expr}, total_pages DESC"""
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date)) + tuple(params_extra)
    return query_fetchall(sql, params)


def query_device_readings(start_date: str, end_date: str, site_id=None):
    """Drucker-Übersicht: Auslastung + letzte Aktivität."""
    tenant_id = get_tenant_id()
    where_extra = ""
    params_extra = []
    if site_id:
        where_extra += " AND p.network_id = ?"
        params_extra.append(site_id)
    sql = f"""
        SELECT p.id AS printer_id, p.name AS printer_name, p.model_name, p.vendor_name, p.location,
            n.name AS site_name,
            COUNT(DISTINCT td.job_id) AS total_jobs,
            ISNULL(SUM(td.page_count),0) AS total_pages,
            ISNULL(SUM(CASE WHEN td.color=1 THEN td.page_count ELSE 0 END),0) AS color_pages,
            ISNULL(SUM(CASE WHEN td.color=0 THEN td.page_count ELSE 0 END),0) AS bw_pages,
            MAX(td.print_time) AS last_activity,
            COUNT(DISTINCT CAST(td.print_time AS DATE)) AS active_days
        FROM {_V('printers')} p
        LEFT JOIN {_V('networks')} n ON n.id=p.network_id AND n.tenant_id=p.tenant_id
        LEFT JOIN {_V('tracking_data')} td ON td.printer_id=p.id AND td.tenant_id=p.tenant_id
              AND td.print_time>=? AND td.print_time<DATEADD(day,1,CAST(? AS DATE))
              AND td.print_job_status=\'PRINT_OK\'
        WHERE p.tenant_id=? {where_extra}
        GROUP BY p.id, p.name, p.model_name, p.vendor_name, p.location, n.name
        ORDER BY ISNULL(SUM(td.page_count),0) DESC"""
    params = (_fmt_date(start_date), _fmt_date(end_date), tenant_id) + tuple(params_extra)
    return query_fetchall(sql, params)


def query_job_history(start_date: str, end_date: str, page: int=0, page_size: int=100,
                      site_id=None, user_email=None, printer_id=None, status_filter: str="ok"):
    """Rohe Job-Liste mit Paginierung."""
    tenant_id = get_tenant_id()
    status_clause = ""
    if status_filter == "ok":
        status_clause = "AND td.print_job_status = \'PRINT_OK\'"
    elif status_filter == "failed":
        status_clause = "AND td.print_job_status <> \'PRINT_OK\'"
    where_extra = ""
    params_extra = []
    if site_id:
        where_extra += " AND p.network_id=?"; params_extra.append(site_id)
    if user_email:
        where_extra += " AND u.email=?"; params_extra.append(user_email)
    if printer_id:
        where_extra += " AND td.printer_id=?"; params_extra.append(printer_id)
    offset = max(0, int(page)) * max(1, int(page_size))
    fetch  = max(1, min(int(page_size), 1000))
    sql = f"""
        SELECT td.job_id, td.print_time, td.print_job_status AS status,
            u.email AS user_email, u.name AS user_name,
            p.name AS printer_name, n.name AS site_name,
            td.page_count, td.color, td.duplex, j.paper_size
        FROM {_V('tracking_data')} td
        LEFT JOIN {_V('jobs')} j ON j.id=td.job_id AND j.tenant_id=td.tenant_id
        LEFT JOIN {_V('users')} u ON u.id=j.tenant_user_id AND u.tenant_id=td.tenant_id
        LEFT JOIN {_V('printers')} p ON p.id=td.printer_id AND p.tenant_id=td.tenant_id
        LEFT JOIN {_V('networks')} n ON n.id=p.network_id AND n.tenant_id=td.tenant_id
        WHERE td.tenant_id=? AND td.print_time>=? AND td.print_time<DATEADD(day,1,CAST(? AS DATE))
          {status_clause} {where_extra}
        ORDER BY td.print_time DESC
        OFFSET {offset} ROWS FETCH NEXT {fetch} ROWS ONLY"""
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date)) + tuple(params_extra)
    return query_fetchall(sql, params)


def query_queue_stats(start_date: str, end_date: str, site_id=None):
    """Druckauftrags-Verteilung nach Papierformat, Farbe und Duplex."""
    tenant_id = get_tenant_id()
    where_extra = ""
    params_extra = []
    if site_id:
        where_extra += " AND p.network_id=?"; params_extra.append(site_id)
    sql = f"""
        SELECT ISNULL(j.paper_size,\'UNKNOWN\') AS paper_size, td.color, td.duplex,
            COUNT(DISTINCT td.job_id) AS total_jobs, SUM(td.page_count) AS total_pages,
            CAST(SUM(td.page_count)*100.0/NULLIF(SUM(SUM(td.page_count)) OVER (),0) AS DECIMAL(5,1)) AS pct_of_total
        FROM {_V('tracking_data')} td
        LEFT JOIN {_V('jobs')} j ON j.id=td.job_id AND j.tenant_id=td.tenant_id
        LEFT JOIN {_V('printers')} p ON p.id=td.printer_id AND p.tenant_id=td.tenant_id
        WHERE td.tenant_id=? AND td.print_time>=? AND td.print_time<DATEADD(day,1,CAST(? AS DATE))
          AND td.print_job_status=\'PRINT_OK\' {where_extra}
        GROUP BY j.paper_size, td.color, td.duplex
        ORDER BY total_pages DESC"""
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date)) + tuple(params_extra)
    return query_fetchall(sql, params)


def query_user_detail(start_date: str, end_date: str, user_email: str, group_by: str="month"):
    """Detaillierter Druckverlauf eines einzelnen Benutzers."""
    tenant_id = get_tenant_id()
    group_expr = {
        "day": "CAST(td.print_time AS DATE)",
        "week": "DATEADD(day, -(DATEPART(weekday, td.print_time) - 1), CAST(td.print_time AS DATE))",
        "month": "DATEFROMPARTS(YEAR(td.print_time), MONTH(td.print_time), 1)",
    }.get(group_by, "DATEFROMPARTS(YEAR(td.print_time), MONTH(td.print_time), 1)")
    label_col = {
        "day": "CAST(td.print_time AS DATE) AS period",
        "week": "DATEADD(day, -(DATEPART(weekday, td.print_time) - 1), CAST(td.print_time AS DATE)) AS period",
        "month": "DATEFROMPARTS(YEAR(td.print_time), MONTH(td.print_time), 1) AS period",
    }.get(group_by, "DATEFROMPARTS(YEAR(td.print_time), MONTH(td.print_time), 1) AS period")
    sql = f"""
        SELECT {label_col}, u.email, u.name, u.department,
            COUNT(DISTINCT td.job_id) AS print_jobs, SUM(td.page_count) AS print_pages,
            SUM(CASE WHEN td.color=1 THEN td.page_count ELSE 0 END) AS color_pages,
            SUM(CASE WHEN td.color=0 THEN td.page_count ELSE 0 END) AS bw_pages,
            SUM(CASE WHEN td.duplex=1 THEN td.page_count ELSE 0 END) AS duplex_pages,
            CAST(SUM(CASE WHEN td.color=1 THEN td.page_count ELSE 0 END)*100.0/NULLIF(SUM(td.page_count),0) AS DECIMAL(5,1)) AS color_pct
        FROM {_V('tracking_data')} td
        JOIN {_V('jobs')} j ON j.id=td.job_id AND j.tenant_id=td.tenant_id
        JOIN {_V('users')} u ON u.id=j.tenant_user_id AND u.tenant_id=td.tenant_id
        WHERE td.tenant_id=? AND td.print_time>=? AND td.print_time<DATEADD(day,1,CAST(? AS DATE))
          AND td.print_job_status=\'PRINT_OK\' AND u.email=?
        GROUP BY {group_expr}, u.email, u.name, u.department
        ORDER BY {group_expr}"""
    return query_fetchall(sql, (tenant_id, _fmt_date(start_date), _fmt_date(end_date), user_email))


def query_user_copy_detail(start_date: str, end_date: str, user_email=None, group_by: str="month", site_id=None):
    """Kopier-Jobs pro Benutzer."""
    tenant_id = get_tenant_id()
    group_expr = {
        "day": "CAST(jc.copy_time AS DATE)",
        "week": "DATEADD(day, -(DATEPART(weekday, jc.copy_time) - 1), CAST(jc.copy_time AS DATE))",
        "month": "DATEFROMPARTS(YEAR(jc.copy_time), MONTH(jc.copy_time), 1)",
    }.get(group_by, "DATEFROMPARTS(YEAR(jc.copy_time), MONTH(jc.copy_time), 1)")
    label_col = {
        "day": "CAST(jc.copy_time AS DATE) AS period",
        "week": "DATEADD(day, -(DATEPART(weekday, jc.copy_time) - 1), CAST(jc.copy_time AS DATE)) AS period",
        "month": "DATEFROMPARTS(YEAR(jc.copy_time), MONTH(jc.copy_time), 1) AS period",
    }.get(group_by, "DATEFROMPARTS(YEAR(jc.copy_time), MONTH(jc.copy_time), 1) AS period")
    where_extra = ""
    params_extra = []
    if user_email:
        where_extra += " AND u.email=?"; params_extra.append(user_email)
    if site_id:
        where_extra += " AND p.network_id=?"; params_extra.append(site_id)
    sql = f"""
        SELECT {label_col}, u.email, u.name, p.name AS printer_name, n.name AS site_name,
            COUNT(DISTINCT jc.id) AS total_copy_jobs,
            ISNULL(SUM(jcd.page_count),0) AS total_pages,
            ISNULL(SUM(CASE WHEN jcd.color=1 THEN jcd.page_count ELSE 0 END),0) AS color_pages,
            ISNULL(SUM(CASE WHEN jcd.color=0 THEN jcd.page_count ELSE 0 END),0) AS bw_pages,
            ISNULL(SUM(CASE WHEN jcd.duplex=1 THEN jcd.page_count ELSE 0 END),0) AS duplex_pages
        FROM {_V('jobs_copy')} jc
        LEFT JOIN {_V('jobs_copy_details')} jcd ON jcd.job_id=jc.id
        LEFT JOIN {_V('users')} u ON u.id=jc.tenant_user_id AND u.tenant_id=jc.tenant_id
        LEFT JOIN {_V('printers')} p ON p.id=jc.printer_id AND p.tenant_id=jc.tenant_id
        LEFT JOIN {_V('networks')} n ON n.id=p.network_id AND n.tenant_id=jc.tenant_id
        WHERE jc.tenant_id=? AND jc.copy_time>=? AND jc.copy_time<DATEADD(day,1,CAST(? AS DATE))
          {where_extra}
        GROUP BY {group_expr}, u.email, u.name, p.name, n.name
        ORDER BY {group_expr}, total_pages DESC"""
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date)) + tuple(params_extra)
    return query_fetchall(sql, params)


def query_user_scan_detail(start_date: str, end_date: str, user_email=None, group_by: str="month", site_id=None):
    """Scan-Jobs pro Benutzer."""
    tenant_id = get_tenant_id()
    group_expr = {
        "day": "CAST(js.scan_time AS DATE)",
        "week": "DATEADD(day, -(DATEPART(weekday, js.scan_time) - 1), CAST(js.scan_time AS DATE))",
        "month": "DATEFROMPARTS(YEAR(js.scan_time), MONTH(js.scan_time), 1)",
    }.get(group_by, "DATEFROMPARTS(YEAR(js.scan_time), MONTH(js.scan_time), 1)")
    label_col = {
        "day": "CAST(js.scan_time AS DATE) AS period",
        "week": "DATEADD(day, -(DATEPART(weekday, js.scan_time) - 1), CAST(js.scan_time AS DATE)) AS period",
        "month": "DATEFROMPARTS(YEAR(js.scan_time), MONTH(js.scan_time), 1) AS period",
    }.get(group_by, "DATEFROMPARTS(YEAR(js.scan_time), MONTH(js.scan_time), 1) AS period")
    where_extra = ""
    params_extra = []
    if user_email:
        where_extra += " AND u.email=?"; params_extra.append(user_email)
    if site_id:
        where_extra += " AND p.network_id=?"; params_extra.append(site_id)
    sql = f"""
        SELECT {label_col}, u.email, u.name, p.name AS printer_name, n.name AS site_name,
            COUNT(DISTINCT js.id) AS total_scan_jobs, SUM(js.page_count) AS total_pages,
            SUM(CASE WHEN js.color=1 THEN js.page_count ELSE 0 END) AS color_pages,
            SUM(CASE WHEN js.color=0 THEN js.page_count ELSE 0 END) AS bw_pages
        FROM {_V('jobs_scan')} js
        LEFT JOIN {_V('users')} u ON u.id=js.tenant_user_id AND u.tenant_id=js.tenant_id
        LEFT JOIN {_V('printers')} p ON p.id=js.printer_id AND p.tenant_id=js.tenant_id
        LEFT JOIN {_V('networks')} n ON n.id=p.network_id AND n.tenant_id=js.tenant_id
        WHERE js.tenant_id=? AND js.scan_time>=? AND js.scan_time<DATEADD(day,1,CAST(? AS DATE))
          {where_extra}
        GROUP BY {group_expr}, u.email, u.name, p.name, n.name
        ORDER BY {group_expr}, total_pages DESC"""
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date)) + tuple(params_extra)
    return query_fetchall(sql, params)


def query_workstation_overview(start_date: str, end_date: str, site_id=None):
    """Workstation-Übersicht. Gibt Hinweis falls Tabelle fehlt."""
    tenant_id = get_tenant_id()
    from .sql_client import query_fetchone
    try:
        tbl = query_fetchone("SELECT COUNT(*) AS cnt FROM INFORMATION_SCHEMA.TABLES "
                             "WHERE TABLE_SCHEMA IN (\'dbo\',\'reporting\') AND TABLE_NAME IN (\'workstations\',\'v_workstations\')")
        if not (tbl or {}).get("cnt"):
            return [{"info": "workstations-Tabelle nicht in diesem Schema vorhanden"}]
    except Exception:
        return [{"info": "workstations-Tabelle nicht in diesem Schema vorhanden"}]
    where_extra = ""
    params_extra = []
    if site_id:
        where_extra += " AND w.network_id=?"; params_extra.append(site_id)
    sql = f"""
        SELECT w.id AS workstation_id, w.name AS workstation_name, w.os_type,
            n.name AS site_name,
            COUNT(DISTINCT j.id) AS total_jobs, SUM(j.page_count) AS total_pages
        FROM {_V(\'workstations\')} w
        LEFT JOIN {_V(\'networks\')} n ON n.id=w.network_id AND n.tenant_id=w.tenant_id
        LEFT JOIN {_V(\'jobs\')} j ON j.workstation_id=w.id AND j.tenant_id=w.tenant_id
                                 AND j.submit_time>=? AND j.submit_time<DATEADD(day,1,CAST(? AS DATE))
        WHERE w.tenant_id=? {where_extra}
        GROUP BY w.id, w.name, w.os_type, n.name
        ORDER BY total_pages DESC"""
    params = (_fmt_date(start_date), _fmt_date(end_date), tenant_id) + tuple(params_extra)
    try:
        return query_fetchall(sql, params)
    except Exception as exc:
        return [{"error": str(exc)[:200]}]


def query_workstation_detail(start_date: str, end_date: str, workstation_id: str, group_by: str="month"):
    """Druckverlauf einer einzelnen Workstation."""
    tenant_id = get_tenant_id()
    from .sql_client import query_fetchone
    try:
        tbl = query_fetchone("SELECT COUNT(*) AS cnt FROM INFORMATION_SCHEMA.TABLES "
                             "WHERE TABLE_SCHEMA IN (\'dbo\',\'reporting\') AND TABLE_NAME IN (\'workstations\',\'v_workstations\')")
        if not (tbl or {}).get("cnt"):
            return [{"info": "workstations-Tabelle nicht in diesem Schema vorhanden"}]
    except Exception:
        return [{"info": "workstations-Tabelle nicht in diesem Schema vorhanden"}]
    group_expr = {
        "day": "CAST(j.submit_time AS DATE)",
        "week": "DATEADD(day, -(DATEPART(weekday, j.submit_time) - 1), CAST(j.submit_time AS DATE))",
        "month": "DATEFROMPARTS(YEAR(j.submit_time), MONTH(j.submit_time), 1)",
    }.get(group_by, "DATEFROMPARTS(YEAR(j.submit_time), MONTH(j.submit_time), 1)")
    label_col = {
        "day": "CAST(j.submit_time AS DATE) AS period",
        "week": "DATEADD(day, -(DATEPART(weekday, j.submit_time) - 1), CAST(j.submit_time AS DATE)) AS period",
        "month": "DATEFROMPARTS(YEAR(j.submit_time), MONTH(j.submit_time), 1) AS period",
    }.get(group_by, "DATEFROMPARTS(YEAR(j.submit_time), MONTH(j.submit_time), 1) AS period")
    sql = f"""
        SELECT {label_col},
            COUNT(DISTINCT j.id) AS total_jobs, SUM(j.page_count) AS total_pages,
            SUM(CASE WHEN j.color=1 THEN j.page_count ELSE 0 END) AS color_pages,
            SUM(CASE WHEN j.color=0 THEN j.page_count ELSE 0 END) AS bw_pages,
            SUM(CASE WHEN j.duplex=1 THEN j.page_count ELSE 0 END) AS duplex_pages
        FROM {_V(\'jobs\')} j
        WHERE j.tenant_id=? AND j.workstation_id=? AND j.submit_time>=?
          AND j.submit_time<DATEADD(day,1,CAST(? AS DATE))
        GROUP BY {group_expr} ORDER BY {group_expr}"""
    try:
        return query_fetchall(sql, (tenant_id, workstation_id, _fmt_date(start_date), _fmt_date(end_date)))
    except Exception as exc:
        return [{"error": str(exc)[:200]}]


def query_tree_meter(start_date: str, end_date: str, sheets_per_tree: int=8333, site_id=None):
    """Nachhaltigkeits-Kennzahlen: eingesparte Blätter durch Duplex."""
    tenant_id = get_tenant_id()
    where_extra = ""
    params_extra = []
    if site_id:
        where_extra += " AND p.network_id=?"; params_extra.append(site_id)
    sql = f"""
        SELECT SUM(td.page_count) AS total_pages,
            SUM(CASE WHEN td.duplex=1 THEN CEILING(CAST(td.page_count AS FLOAT)/2) ELSE td.page_count END) AS total_sheets_used,
            SUM(CASE WHEN td.duplex=1 THEN td.page_count-CEILING(CAST(td.page_count AS FLOAT)/2) ELSE 0 END) AS saved_sheets_duplex,
            SUM(CASE WHEN td.duplex=1 THEN td.page_count ELSE 0 END) AS duplex_pages,
            SUM(CASE WHEN td.duplex=0 THEN td.page_count ELSE 0 END) AS simplex_pages,
            CAST(SUM(CASE WHEN td.duplex=1 THEN td.page_count ELSE 0 END)*100.0/NULLIF(SUM(td.page_count),0) AS DECIMAL(5,1)) AS duplex_pct
        FROM {_V(\'tracking_data\')} td
        LEFT JOIN {_V(\'printers\')} p ON p.id=td.printer_id AND p.tenant_id=td.tenant_id
        WHERE td.tenant_id=? AND td.print_time>=? AND td.print_time<DATEADD(day,1,CAST(? AS DATE))
          AND td.print_job_status=\'PRINT_OK\' {where_extra}"""
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date)) + tuple(params_extra)
    from .sql_client import query_fetchone
    row = query_fetchone(sql, params) or {}
    saved = int(row.get("saved_sheets_duplex") or 0)
    return {
        "start_date": start_date, "end_date": end_date,
        "total_pages": int(row.get("total_pages") or 0),
        "total_sheets_used": int(row.get("total_sheets_used") or 0),
        "saved_sheets_duplex": saved,
        "trees_saved": round(saved / sheets_per_tree, 4) if sheets_per_tree else 0,
        "duplex_pages": int(row.get("duplex_pages") or 0),
        "simplex_pages": int(row.get("simplex_pages") or 0),
        "duplex_pct": float(row.get("duplex_pct") or 0),
        "sheets_per_tree": sheets_per_tree,
    }


def query_service_desk(start_date: str, end_date: str, site_id=None, user_email=None, group_by: str="status"):
    """Fehlgeschlagene und abgebrochene Druckjobs."""
    tenant_id = get_tenant_id()
    where_extra = ""
    params_extra = []
    if site_id:
        where_extra += " AND p.network_id=?"; params_extra.append(site_id)
    if user_email:
        where_extra += " AND u.email=?"; params_extra.append(user_email)
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
        SELECT {select_group},
            COUNT(DISTINCT td.job_id) AS total_jobs, SUM(td.page_count) AS total_pages,
            MAX(td.print_time) AS last_occurrence
        FROM {_V(\'tracking_data\')} td
        LEFT JOIN {_V(\'jobs\')} j ON j.id=td.job_id AND j.tenant_id=td.tenant_id
        LEFT JOIN {_V(\'users\')} u ON u.id=j.tenant_user_id AND u.tenant_id=td.tenant_id
        LEFT JOIN {_V(\'printers\')} p ON p.id=td.printer_id AND p.tenant_id=td.tenant_id
        LEFT JOIN {_V(\'networks\')} n ON n.id=p.network_id AND n.tenant_id=td.tenant_id
        WHERE td.tenant_id=? AND td.print_time>=? AND td.print_time<DATEADD(day,1,CAST(? AS DATE))
          AND td.print_job_status<>\'PRINT_OK\' {where_extra}
        GROUP BY {group_by_clause} ORDER BY total_jobs DESC"""
    params = (tenant_id, _fmt_date(start_date), _fmt_date(end_date)) + tuple(params_extra)
    return query_fetchall(sql, params)


# ─── Universeller Dispatcher (v3.7.0) ────────────────────────────────────────

def run_query(query_type: str, tenant_id: str = "", **kwargs):
    """Dispatcher Stufe 1+2."""
    if query_type == "print_stats":      return query_print_stats(**kwargs)
    elif query_type == "cost_report":    return query_cost_report(**kwargs)
    elif query_type == "top_users":      return query_top_users(**kwargs)
    elif query_type == "top_printers":   return query_top_printers(**kwargs)
    elif query_type == "trend":          return query_trend(**kwargs)
    elif query_type == "anomalies":      return query_anomalies(**kwargs)
    elif query_type == "printer_history":   return query_printer_history(**kwargs)
    elif query_type == "device_readings":   return query_device_readings(**kwargs)
    elif query_type == "job_history":       return query_job_history(**kwargs)
    elif query_type == "queue_stats":       return query_queue_stats(**kwargs)
    elif query_type == "user_detail":       return query_user_detail(**kwargs)
    elif query_type == "user_copy_detail":  return query_user_copy_detail(**kwargs)
    elif query_type == "user_scan_detail":  return query_user_scan_detail(**kwargs)
    elif query_type == "workstation_overview": return query_workstation_overview(**kwargs)
    elif query_type == "workstation_detail":   return query_workstation_detail(**kwargs)
    elif query_type == "tree_meter":        return query_tree_meter(**kwargs)
    elif query_type == "service_desk":      return query_service_desk(**kwargs)
    else:
        raise ValueError(f"Unbekannter query_type: {query_type!r}")'''

# ═══════════════════════════════════════════════════════════════════════════════
# Patch ausführen
# ═══════════════════════════════════════════════════════════════════════════════

qt_path = os.path.join(BASE, "query_tools.py")
content = open(qt_path).read()
if QT_OLD in content:
    content = content.replace(QT_OLD, QT_NEW, 1)
    open(qt_path, "w").write(content)
    print(f"✅ query_tools.py gepatcht: {qt_path}")
elif "run_query" in content and "query_printer_history" in content:
    print(f"ℹ️  query_tools.py bereits aktuell: {qt_path}")
else:
    print(f"❌ Kein Match in query_tools.py — manuell prüfen")

print("Fertig.")
