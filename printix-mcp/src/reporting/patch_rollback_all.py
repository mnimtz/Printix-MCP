#!/usr/bin/env python3
"""Patch: add rollback_demo_all() to demo_generator.py"""
import sys

path = "/addons/printix-mcp-addon/printix-mcp/src/reporting/demo_generator.py"
content = open(path).read()

if 'def rollback_demo_all' in content:
    print("rollback_demo_all already exists — nothing to do")
    sys.exit(0)

ANCHOR = '        "status":         "ok",\n    }\n\n\ndef get_demo_status'

NEW_FUNC = '''        "status":         "ok",
    }


def rollback_demo_all(tenant_id: str) -> dict:
    """
    Löscht ALLE Demo-Daten für den Tenant (alle Tags/Sessions).
    Nützlich wenn man ohne bestehende Sessions alles bereinigen möchte.
    """
    from .sql_client import execute_write, query_fetchall

    try:
        sessions = query_fetchall(
            "SELECT session_id, demo_tag FROM demo.demo_sessions WHERE tenant_id=?",
            (tenant_id,),
        )
    except Exception as e:
        return {"deleted": {}, "sessions_found": 0, "total_deleted": 0, "status": "ok",
                "message": f"Keine Demo-Tabellen gefunden ({e})"}

    tables_ordered = [
        "demo.jobs_copy_details",
        "demo.jobs_copy",
        "demo.jobs_scan",
        "demo.tracking_data",
        "demo.jobs",
        "demo.printers",
        "demo.users",
        "demo.networks",
        "demo.demo_sessions",
    ]
    deleted: dict = {}
    for tbl in tables_ordered:
        if tbl == "demo.demo_sessions":
            try:
                n = execute_write("DELETE FROM demo.demo_sessions WHERE tenant_id=?", (tenant_id,))
                deleted[tbl] = deleted.get(tbl, 0) + n
            except Exception as e:
                import logging; logging.getLogger(__name__).warning("Rollback-All %s: %s", tbl, e)
        else:
            col = "demo_session_id"
            try:
                n = execute_write(
                    f"DELETE FROM {tbl} WHERE {col} IN "
                    "(SELECT session_id FROM demo.demo_sessions WHERE tenant_id=?)",
                    (tenant_id,),
                )
                deleted[tbl] = deleted.get(tbl, 0) + n
            except Exception as e:
                import logging; logging.getLogger(__name__).warning("Rollback-All %s: %s", tbl, e)

    total = sum(deleted.values())
    import logging; logging.getLogger(__name__).info(
        "Rollback-All: %d Zeilen gelöscht für tenant_id=%s", total, tenant_id)
    return {
        "deleted":        deleted,
        "sessions_found": len(sessions),
        "total_deleted":  total,
        "status":         "ok",
    }


def get_demo_status'''

if ANCHOR not in content:
    print(f"ERROR: anchor not found! Occurrences of 'def get_demo_status': {content.count('def get_demo_status')}")
    sys.exit(1)

new_content = content.replace(ANCHOR, NEW_FUNC, 1)
open(path, 'w').write(new_content)
print(f"Done! {len(content)} → {len(new_content)} chars")
print("Verify:", "def rollback_demo_all" in new_content)
