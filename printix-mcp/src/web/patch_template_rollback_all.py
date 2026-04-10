#!/usr/bin/env python3
"""Patch tenant_demo.html: add global 'Alle Demo-Daten löschen' button."""
import sys

path = "/addons/printix-mcp-addon/printix-mcp/src/web/templates/tenant_demo.html"
content = open(path).read()

if '/tenant/demo/rollback-all' in content:
    print("rollback-all button already present — nothing to do")
    sys.exit(0)

ANCHOR = '''    <div style="margin-top:24px;">
      <a href="/dashboard" class="btn btn-secondary">← {{ _('nav_dashboard') }}</a>
    </div>'''

NEW_BLOCK = '''    <div style="margin-top:24px; display:flex; gap:12px; align-items:center; flex-wrap:wrap;">
      <a href="/dashboard" class="btn btn-secondary">← {{ _('nav_dashboard') }}</a>
      <form method="post" action="/tenant/demo/rollback-all" style="margin:0;"
            onsubmit="return confirm('{{ _(\\'demo_confirm_rollback_all\\') }}')">
        <button type="submit" class="btn btn-danger btn-sm" style="padding:6px 14px;">
          🗑️ {{ _('demo_btn_rollback_all') }}
        </button>
      </form>
    </div>'''

if ANCHOR not in content:
    print("ERROR: anchor not found!")
    sys.exit(1)

new_content = content.replace(ANCHOR, NEW_BLOCK, 1)
open(path, 'w').write(new_content)
print(f"Done! {len(content)} → {len(new_content)} chars")
print("Verify:", '/tenant/demo/rollback-all' in new_content)
