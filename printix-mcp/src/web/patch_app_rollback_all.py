#!/usr/bin/env python3
"""Patch: add /tenant/demo/rollback-all route to app.py"""
import sys

path = "/addons/printix-mcp-addon/printix-mcp/src/web/app.py"
content = open(path).read()

if '/tenant/demo/rollback-all' in content:
    print("rollback-all route already exists — nothing to do")
    sys.exit(0)

ANCHOR = '''    # ── Reports-Register (v3.0.0) ─────────────────────────────────────────────'''

NEW_ROUTE = '''    @app.post("/tenant/demo/rollback-all", response_class=HTMLResponse)
    async def tenant_demo_rollback_all(request: Request):
        """Löscht ALLE Demo-Daten des Tenants – auch ohne bestehende Sessions."""
        user = require_login(request)
        if user is None:
            return RedirectResponse("/login", status_code=302)
        try:
            from db import get_tenant_full_by_user_id
            tenant = get_tenant_full_by_user_id(user["id"])
            if not tenant or not tenant.get("sql_server"):
                return RedirectResponse("/tenant/demo?flash=error&flash_msg=no_sql", status_code=302)
            import sys as _sys, os as _os
            src_dir = _os.path.dirname(_os.path.dirname(__file__))
            if src_dir not in _sys.path:
                _sys.path.insert(0, src_dir)
            from reporting.sql_client import set_config_from_tenant
            set_config_from_tenant(tenant)
            from reporting.demo_generator import rollback_demo_all
            result = rollback_demo_all(tenant["printix_tenant_id"])
            logger.info("Demo-Rollback-All: %d Zeilen gelöscht", result.get("total_deleted", 0))
            return RedirectResponse("/tenant/demo?flash=rollback_ok", status_code=302)
        except Exception as e:
            logger.error("tenant_demo_rollback_all error: %s", e)
            return RedirectResponse(f"/tenant/demo?flash=error&flash_msg={str(e)[:120]}", status_code=302)

    # ── Reports-Register (v3.0.0) ─────────────────────────────────────────────'''

if ANCHOR not in content:
    print("ERROR: anchor not found!")
    sys.exit(1)

new_content = content.replace(ANCHOR, NEW_ROUTE, 1)
open(path, 'w').write(new_content)
print(f"Done! {len(content)} → {len(new_content)} chars")
print("Verify:", '/tenant/demo/rollback-all' in new_content)
