#!/usr/bin/env python3
"""
Printix MCP Server — Tool-Smoketest.

Runs every MCP tool the Printix MCP server advertises via `tools/list`, with
risk-aware defaults (read-only only), chained ID discovery, and a
markdown + JSON report.

Usage
-----
    export PRINTIX_MCP_URL=https://mcp.printix.cloud/mcp
    export PRINTIX_MCP_TOKEN=<tenant bearer token>

    python3 mcp_smoketest.py                       # read-only (default)
    python3 mcp_smoketest.py --include-write       # + write-safe tools
    python3 mcp_smoketest.py --include-destructive # + destructive tools
    python3 mcp_smoketest.py --only printix_status,printix_whoami
    python3 mcp_smoketest.py --report out.md --json out.json --verbose

Exit code: 0 if all selected tools PASS or SKIP, 1 if any FAIL.

Notes
-----
* Speaks the Streamable-HTTP transport the FastMCP server exposes on `/mcp`.
* Each tool call is wrapped in a 60s timeout.
* The runner lists the server's advertised tools first; any new tool that is
  not in `TOOL_CLASSES` is reported as "unclassified — not tested".
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

import requests


# ────────────────────────────────────────────────────────────────────────────
#  Tool classification
#
#  Class:
#    R  = read-only, always run
#    W  = write-safe (no destructive side effect), run with --include-write
#    D  = destructive, only run with --include-destructive
#    S  = skip (needs live data or produces real-world side effects)
#
#  Args is a dict of parameter name → value spec. Values can be:
#    * a literal (str/int/bool/list)
#    * a "$placeholder" string resolved from the discovery cache
# ────────────────────────────────────────────────────────────────────────────

TOOL_CLASSES: dict[str, dict] = {
    # ── Status & Info ─────────────────────────────────────────────────────
    "printix_status":                {"class": "R", "args": {}},
    "printix_whoami":                {"class": "R", "args": {}},

    # ── Printers & Queues ─────────────────────────────────────────────────
    "printix_list_printers":         {"class": "R", "args": {"size": 2}},
    "printix_get_printer":           {"class": "R", "args": {"printer_id": "$printer_id", "queue_id": "$queue_id"}},

    # ── Print Jobs ────────────────────────────────────────────────────────
    "printix_list_jobs":              {"class": "R", "args": {"size": 2}},
    "printix_get_job":                {"class": "R", "args": {"job_id": "$job_id"}, "needs": ["job_id"]},
    "printix_submit_job":             {"class": "D"},
    "printix_complete_upload":        {"class": "D"},
    "printix_delete_job":             {"class": "D"},
    "printix_change_job_owner":       {"class": "S", "reason": "needs a live job + second user"},

    # ── Card Management (Printix Cloud) ──────────────────────────────────
    "printix_list_cards":             {"class": "R", "args": {"user_id": "$user_id"}, "needs": ["user_id"]},
    "printix_search_card":            {"class": "R", "args": {"card_id": "$card_id"}, "needs": ["card_id"]},
    "printix_register_card":          {"class": "D"},
    "printix_delete_card":            {"class": "D"},

    # ── Card Management (Local DB) ───────────────────────────────────────
    "printix_list_card_profiles":     {"class": "R", "args": {}},
    "printix_get_card_profile":       {"class": "R", "args": {"profile_id": "$card_profile_id"}, "needs": ["card_profile_id"]},
    "printix_search_card_mappings":   {"class": "R", "args": {"search": ""}},
    "printix_get_card_details":       {"class": "R", "args": {"card_id": "$card_id"}, "needs": ["card_id"]},
    "printix_decode_card_value":      {"class": "R", "args": {"card_value": "MDEyMzQ1Njc4OUFC"}},
    "printix_transform_card_value":   {"class": "R", "args": {"card_value": "MDEyMzQ1Njc4OUFC", "profile_id": "$card_profile_id"}, "needs": ["card_profile_id"]},
    "printix_get_user_card_context":  {"class": "R", "args": {"user_id": "$user_id"}, "needs": ["user_id"]},

    # ── Users ─────────────────────────────────────────────────────────────
    "printix_list_users":             {"class": "R", "args": {"page_size": 2}},
    "printix_get_user":               {"class": "R", "args": {"user_id": "$user_id"}, "needs": ["user_id"]},
    "printix_create_user":            {"class": "D"},
    "printix_delete_user":            {"class": "D"},
    "printix_generate_id_code":       {"class": "S", "reason": "issues real code, visible in audit"},

    # ── Groups ────────────────────────────────────────────────────────────
    "printix_list_groups":            {"class": "R", "args": {"size": 2}},
    "printix_get_group":              {"class": "R", "args": {"group_id": "$group_id"}, "needs": ["group_id"]},
    "printix_create_group":           {"class": "D"},
    "printix_delete_group":           {"class": "D"},

    # ── Workstations ─────────────────────────────────────────────────────
    "printix_list_workstations":      {"class": "R", "args": {"page_size": 2}},
    "printix_get_workstation":        {"class": "R", "args": {"workstation_id": "$workstation_id"}, "needs": ["workstation_id"]},

    # ── Sites & Networks ─────────────────────────────────────────────────
    "printix_list_sites":             {"class": "R", "args": {"size": 2}},
    "printix_get_site":               {"class": "R", "args": {"site_id": "$site_id"}, "needs": ["site_id"]},
    "printix_create_site":            {"class": "D"},
    "printix_update_site":            {"class": "D"},
    "printix_delete_site":            {"class": "D"},
    "printix_list_networks":          {"class": "R", "args": {"size": 2}},
    "printix_get_network":            {"class": "R", "args": {"network_id": "$network_id"}, "needs": ["network_id"]},
    "printix_create_network":         {"class": "D"},
    "printix_update_network":         {"class": "D"},
    "printix_delete_network":         {"class": "D"},

    # ── SNMP ──────────────────────────────────────────────────────────────
    "printix_list_snmp_configs":      {"class": "R", "args": {"size": 2}},
    "printix_get_snmp_config":        {"class": "R", "args": {"config_id": "$snmp_id"}, "needs": ["snmp_id"]},
    "printix_create_snmp_config":     {"class": "D"},
    "printix_delete_snmp_config":     {"class": "D"},

    # ── Reporting — Queries ──────────────────────────────────────────────
    "printix_reporting_status":       {"class": "R", "args": {}},
    "printix_query_print_stats":      {"class": "R", "args": {"days": 7, "group_by": "user"}},
    "printix_query_cost_report":      {"class": "R", "args": {"days": 7}},
    "printix_query_top_users":        {"class": "R", "args": {"top_n": 5}},
    "printix_query_top_printers":     {"class": "R", "args": {"top_n": 5}},
    "printix_query_anomalies":        {"class": "R", "args": {"days": 7}},
    "printix_query_trend":            {"class": "R", "args": {"days": 7, "group_by": "day"}},
    "printix_query_any":              {"class": "S", "reason": "free-form spec; needs a validated template"},

    # ── Reporting — Templates & Schedules ────────────────────────────────
    "printix_save_report_template":   {"class": "D"},
    "printix_list_report_templates":  {"class": "R", "args": {}},
    "printix_get_report_template":    {"class": "R", "args": {"report_id": "$report_id"}, "needs": ["report_id"]},
    "printix_delete_report_template": {"class": "D"},
    "printix_run_report_now":         {"class": "W", "args": {"report_id": "$report_id"}, "needs": ["report_id"]},
    "printix_send_test_email":        {"class": "W", "args": {"recipient": os.getenv("PRINTIX_TEST_EMAIL", "")}, "needs_env": ["PRINTIX_TEST_EMAIL"]},
    "printix_schedule_report":        {"class": "D"},
    "printix_list_schedules":         {"class": "R", "args": {}},
    "printix_delete_schedule":        {"class": "D"},
    "printix_update_schedule":        {"class": "D"},

    # ── Reporting — Design & Preview ─────────────────────────────────────
    "printix_list_design_options":    {"class": "R", "args": {}},
    "printix_preview_report":         {"class": "W", "args": {"report_id": "$report_id"}, "needs": ["report_id"]},

    # ── Demo Data ────────────────────────────────────────────────────────
    "printix_demo_setup_schema":      {"class": "W", "args": {}},
    "printix_demo_generate":          {"class": "D"},
    "printix_demo_rollback":          {"class": "D"},
    "printix_demo_status":            {"class": "R", "args": {}},

    # ── Audit Log & Feature Requests ─────────────────────────────────────
    "printix_query_audit_log":        {"class": "R", "args": {"limit": 5}},
    "printix_list_feature_requests":  {"class": "R", "args": {"limit": 5}},
    "printix_get_feature_request":    {"class": "R", "args": {"ticket_id": "$ticket_id"}, "needs": ["ticket_id"]},

    # ── Backup ────────────────────────────────────────────────────────────
    "printix_list_backups":           {"class": "R", "args": {}},
    "printix_create_backup":          {"class": "W", "args": {}},

    # ── Capture ──────────────────────────────────────────────────────────
    "printix_list_capture_profiles":  {"class": "R", "args": {}},
    "printix_capture_status":         {"class": "R", "args": {}},

    # ── Site/Network aggregations ────────────────────────────────────────
    "printix_site_summary":           {"class": "R", "args": {"site_id": "$site_id"}, "needs": ["site_id"]},
    "printix_network_printers":       {"class": "R", "args": {"network_id": "$network_id"}, "needs": ["network_id"]},
    "printix_get_queue_context":      {"class": "R", "args": {"queue_id": "$queue_id", "printer_id": "$printer_id"}, "needs": ["queue_id", "printer_id"]},
    "printix_get_network_context":    {"class": "R", "args": {"network_id": "$network_id"}, "needs": ["network_id"]},
    "printix_get_snmp_context":       {"class": "R", "args": {"config_id": "$snmp_id"}, "needs": ["snmp_id"]},

    # ── Cross-Source Insights ────────────────────────────────────────────
    "printix_find_user":              {"class": "R", "args": {"query": "a"}},
    "printix_user_360":               {"class": "R", "args": {"query": "$user_email"}, "needs": ["user_email"]},
    "printix_printer_health_report":  {"class": "R", "args": {}},
    "printix_tenant_summary":         {"class": "R", "args": {}},
    "printix_diagnose_user":          {"class": "R", "args": {"email": "$user_email"}, "needs": ["user_email"]},

    # ── Card Management — Tenant-Wide ────────────────────────────────────
    "printix_list_cards_by_tenant":   {"class": "R", "args": {"status": "all"}},
    "printix_find_orphaned_mappings": {"class": "R", "args": {}},
    "printix_bulk_import_cards":      {"class": "D"},
    "printix_suggest_profile":        {"class": "R", "args": {"sample_uid": "MDEyMzQ1Njc4OUFC"}},
    "printix_card_audit":             {"class": "R", "args": {"user_email": "$user_email"}, "needs": ["user_email"]},

    # ── Print Jobs & Reporting — High-Level ──────────────────────────────
    "printix_top_printers":           {"class": "R", "args": {"days": 7, "limit": 5}},
    "printix_top_users":              {"class": "R", "args": {"days": 7, "limit": 5}},
    "printix_jobs_stuck":             {"class": "R", "args": {"minutes": 60}},
    "printix_print_trends":           {"class": "R", "args": {"group_by": "day", "days": 7}},
    "printix_cost_by_department":     {"class": "R", "args": {"days": 7}},
    "printix_compare_periods":        {"class": "R", "args": {"days_a": 7, "days_b": 7}},

    # ── Access & Governance ──────────────────────────────────────────────
    "printix_list_admins":            {"class": "R", "args": {}},
    "printix_permission_matrix":      {"class": "R", "args": {}},
    "printix_inactive_users":         {"class": "R", "args": {"days": 90}},
    "printix_sso_status":             {"class": "R", "args": {"email": "$user_email"}, "needs": ["user_email"]},

    # ── Agent Workflow Helpers ───────────────────────────────────────────
    "printix_explain_error":          {"class": "R", "args": {"code_or_message": "401 Unauthorized"}},
    "printix_suggest_next_action":    {"class": "R", "args": {"context": "user cannot print"}},
    "printix_send_to_user":           {"class": "D"},
    "printix_onboard_user":           {"class": "D"},
    "printix_offboard_user":          {"class": "D"},

    # ── Quality of Life ──────────────────────────────────────────────────
    "printix_quick_print":            {"class": "D"},
    "printix_resolve_printer":        {"class": "R", "args": {"name_or_location": "a"}},
    "printix_natural_query":          {"class": "R", "args": {"question": "How many jobs this week?"}},
}


# ────────────────────────────────────────────────────────────────────────────
#  Minimal MCP-over-Streamable-HTTP client
# ────────────────────────────────────────────────────────────────────────────

class MCPClient:
    """Synchronous MCP client over the Streamable-HTTP transport.

    Minimal: initialize → list → call. Parses both plain-JSON and SSE-framed
    responses. Keeps a session id across calls.
    """

    def __init__(self, url: str, token: str, timeout: int = 60, verbose: bool = False):
        self.url = url
        self.token = token
        self.timeout = timeout
        self.verbose = verbose
        self.session_id: Optional[str] = None
        self._rpc_id = 0

    def _next_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    def _headers(self) -> dict:
        h = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            # Streamable HTTP spec: client must accept both JSON and SSE
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    def _post(self, payload: dict) -> Optional[dict]:
        r = requests.post(self.url, headers=self._headers(),
                          data=json.dumps(payload), timeout=self.timeout)
        if self.verbose:
            print(f"  → POST {payload.get('method')} → {r.status_code}")
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:400]}")

        # Capture session id from response header (set on initialize)
        sid = r.headers.get("Mcp-Session-Id") or r.headers.get("mcp-session-id")
        if sid and not self.session_id:
            self.session_id = sid

        ctype = r.headers.get("content-type", "")
        body = r.text
        if not body.strip():
            return None

        # SSE-framed response? -> parse event `data:` lines, last one wins for JSON-RPC responses
        if "text/event-stream" in ctype or body.lstrip().startswith("event:") or body.lstrip().startswith("data:"):
            last_obj: Optional[dict] = None
            for line in body.splitlines():
                line = line.rstrip("\r")
                if line.startswith("data:"):
                    chunk = line[5:].strip()
                    if not chunk or chunk == "[DONE]":
                        continue
                    try:
                        obj = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue
                    # A JSON-RPC response has "id"; notifications don't.
                    if "id" in obj:
                        last_obj = obj
            return last_obj

        # Plain JSON
        try:
            return json.loads(body)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response: {e}; body[:400]={body[:400]}")

    def initialize(self) -> dict:
        resp = self._post({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "printix-mcp-smoketest", "version": "1.0"},
            },
        })
        if not resp or "result" not in resp:
            raise RuntimeError(f"initialize failed: {resp}")
        # Fire the required notifications/initialized (no response expected)
        try:
            self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        except Exception:
            pass
        return resp["result"]

    def list_tools(self) -> list[dict]:
        tools: list[dict] = []
        cursor: Optional[str] = None
        while True:
            params: dict = {}
            if cursor:
                params["cursor"] = cursor
            resp = self._post({
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/list",
                "params": params,
            })
            if not resp or "result" not in resp:
                raise RuntimeError(f"tools/list failed: {resp}")
            tools.extend(resp["result"].get("tools", []))
            cursor = resp["result"].get("nextCursor")
            if not cursor:
                break
        return tools

    def call_tool(self, name: str, arguments: dict) -> tuple[bool, Any, Optional[str]]:
        """Returns (is_error, payload, raw_text). is_error reflects MCP protocol + server-level errors."""
        resp = self._post({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        if not resp:
            return True, None, "empty response"
        if "error" in resp:
            return True, resp["error"], json.dumps(resp["error"])[:500]
        result = resp.get("result", {})
        # MCP: isError:true + content:[{type:text,text:...}]
        is_error = bool(result.get("isError"))
        content = result.get("content", [])
        text = ""
        for item in content:
            if item.get("type") == "text":
                text += item.get("text", "")
        # Try to decode JSON body (Printix tools return JSON-encoded strings)
        payload: Any
        try:
            payload = json.loads(text) if text else None
        except json.JSONDecodeError:
            payload = text
        # Printix convention: {"error": true, ...} is a tool-level error even if isError=false
        if isinstance(payload, dict) and payload.get("error") is True:
            is_error = True
        return is_error, payload, text[:500]


# ────────────────────────────────────────────────────────────────────────────
#  Discovery phase — pull first ID of each resource type
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class DiscoveryCache:
    """First-available IDs discovered from list_* calls."""
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    printer_id: Optional[str] = None
    queue_id: Optional[str] = None
    group_id: Optional[str] = None
    workstation_id: Optional[str] = None
    site_id: Optional[str] = None
    network_id: Optional[str] = None
    snmp_id: Optional[str] = None
    card_id: Optional[str] = None
    card_profile_id: Optional[str] = None
    job_id: Optional[str] = None
    report_id: Optional[str] = None
    ticket_id: Optional[str] = None

    def has(self, name: str) -> bool:
        return getattr(self, name, None) not in (None, "", [])

    def get(self, name: str) -> Any:
        return getattr(self, name, None)


def _first_id(payload: Any, *keys: str) -> Optional[str]:
    """Dig into a nested list/dict and return the first value of any of `keys`."""
    if payload is None:
        return None
    # Unwrap common envelopes
    candidates: list[Any] = []
    if isinstance(payload, dict):
        for env_key in ("printers", "users", "groups", "workstations", "sites",
                        "networks", "configs", "jobs", "cards", "profiles",
                        "templates", "tickets", "items", "results", "data"):
            if env_key in payload and isinstance(payload[env_key], list):
                candidates.extend(payload[env_key])
        # Also allow the dict itself to be the entity (for get_* responses)
        candidates.append(payload)
    elif isinstance(payload, list):
        candidates.extend(payload)
    for entity in candidates:
        if not isinstance(entity, dict):
            continue
        for key in keys:
            val = entity.get(key)
            if val:
                return val
    return None


def run_discovery(client: MCPClient, verbose: bool = False) -> DiscoveryCache:
    cache = DiscoveryCache()

    def probe(tool: str, args: dict, extractors: list[tuple[str, tuple[str, ...]]]):
        try:
            is_err, payload, raw = client.call_tool(tool, args)
            if is_err:
                if verbose:
                    print(f"  [discovery] {tool} returned error: {raw}")
                return
            for attr, keys in extractors:
                if not cache.has(attr):
                    val = _first_id(payload, *keys)
                    if val:
                        setattr(cache, attr, val)
                        if verbose:
                            print(f"  [discovery] {attr} = {val}")
        except Exception as e:
            if verbose:
                print(f"  [discovery] {tool} exception: {e}")

    probe("printix_list_users", {"page_size": 2}, [
        ("user_id",    ("id", "userId", "user_id")),
        ("user_email", ("email",)),
    ])
    probe("printix_list_printers", {"size": 2}, [
        ("printer_id", ("id", "printerId", "printer_id")),
        ("queue_id",   ("queueId", "queue_id")),
    ])
    probe("printix_list_groups",       {"size": 2},       [("group_id",       ("id", "groupId", "group_id"))])
    probe("printix_list_workstations", {"page_size": 2},  [("workstation_id", ("id", "workstationId", "workstation_id"))])
    probe("printix_list_sites",        {"size": 2},       [("site_id",        ("id", "siteId", "site_id"))])
    probe("printix_list_networks",     {"size": 2},       [("network_id",     ("id", "networkId", "network_id"))])
    probe("printix_list_snmp_configs", {"size": 2},       [("snmp_id",        ("id", "configId", "snmp_id"))])
    probe("printix_list_jobs",         {"size": 2},       [("job_id",         ("id", "jobId", "job_id"))])
    probe("printix_list_cards_by_tenant", {"status": "all"}, [
        ("card_id", ("id", "cardId", "card_id")),
    ])
    probe("printix_list_card_profiles",     {},           [("card_profile_id", ("id", "profile_id"))])
    probe("printix_list_report_templates",  {},           [("report_id",       ("id", "report_id"))])
    probe("printix_list_feature_requests",  {"limit": 2}, [("ticket_id",       ("id", "ticket_id"))])

    return cache


# ────────────────────────────────────────────────────────────────────────────
#  Test orchestration
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class ToolResult:
    name: str
    klass: str
    status: str            # "PASS" | "FAIL" | "SKIP"
    duration_ms: int = 0
    reason: str = ""
    args: dict = field(default_factory=dict)
    preview: str = ""      # short excerpt of response

    def to_dict(self) -> dict:
        return asdict(self)


def _resolve_args(spec_args: dict, cache: DiscoveryCache) -> tuple[dict, list[str]]:
    """Replace $placeholder strings with cache values. Returns (args, missing)."""
    resolved: dict = {}
    missing: list[str] = []
    for k, v in spec_args.items():
        if isinstance(v, str) and v.startswith("$"):
            attr = v[1:]
            val = cache.get(attr)
            if val in (None, ""):
                missing.append(attr)
            else:
                resolved[k] = val
        else:
            resolved[k] = v
    return resolved, missing


def _preview(payload: Any, n: int = 160) -> str:
    try:
        s = json.dumps(payload, ensure_ascii=False)
    except Exception:
        s = str(payload)
    s = re.sub(r"\s+", " ", s)
    return s[:n] + ("…" if len(s) > n else "")


def run_tests(
    client: MCPClient,
    advertised: list[str],
    include_write: bool,
    include_destructive: bool,
    only: Optional[set[str]],
    cache: DiscoveryCache,
    verbose: bool,
) -> list[ToolResult]:
    results: list[ToolResult] = []

    # Iterate in a stable order: advertised first (so we preserve server order), then extras in TOOL_CLASSES
    seen: set[str] = set()
    ordered = list(advertised) + [t for t in TOOL_CLASSES if t not in advertised]

    for tool in ordered:
        if tool in seen:
            continue
        seen.add(tool)

        if only and tool not in only:
            continue

        spec = TOOL_CLASSES.get(tool)
        if spec is None:
            # Unclassified tool advertised by server
            results.append(ToolResult(
                name=tool, klass="?", status="SKIP",
                reason="unclassified — add to TOOL_CLASSES",
            ))
            continue

        klass = spec.get("class", "?")

        # Filter by class selection
        if klass == "S":
            results.append(ToolResult(name=tool, klass=klass, status="SKIP",
                                      reason=spec.get("reason", "not runnable in smoketest")))
            continue
        if klass == "W" and not include_write:
            results.append(ToolResult(name=tool, klass=klass, status="SKIP",
                                      reason="write-safe (use --include-write)"))
            continue
        if klass == "D" and not include_destructive:
            results.append(ToolResult(name=tool, klass=klass, status="SKIP",
                                      reason="destructive (use --include-destructive)"))
            continue
        if klass not in {"R", "W", "D"}:
            results.append(ToolResult(name=tool, klass=klass, status="SKIP",
                                      reason=f"unknown class {klass!r}"))
            continue

        # Destructive tools need explicit per-tool arg sets — we don't run them blind
        if klass == "D" and not spec.get("args"):
            results.append(ToolResult(name=tool, klass=klass, status="SKIP",
                                      reason="destructive and no safe args defined"))
            continue

        # Resolve placeholder args from the discovery cache
        raw_args = spec.get("args", {}) or {}
        args, missing = _resolve_args(raw_args, cache)
        needs = spec.get("needs", [])
        if missing or any(not cache.has(n) for n in needs):
            unresolved = set(missing) | {n for n in needs if not cache.has(n)}
            results.append(ToolResult(
                name=tool, klass=klass, status="SKIP",
                reason=f"missing discovered IDs: {', '.join(sorted(unresolved))}",
                args=raw_args,
            ))
            continue
        # Env-variable needs (e.g. PRINTIX_TEST_EMAIL for send_test_email)
        for env in spec.get("needs_env", []) or []:
            if not os.getenv(env):
                results.append(ToolResult(
                    name=tool, klass=klass, status="SKIP",
                    reason=f"env var {env} not set",
                    args=raw_args,
                ))
                break
        else:
            # Actually call the tool
            t0 = time.monotonic()
            try:
                is_err, payload, raw = client.call_tool(tool, args)
                dt = int((time.monotonic() - t0) * 1000)
                if is_err:
                    results.append(ToolResult(
                        name=tool, klass=klass, status="FAIL",
                        duration_ms=dt, reason=_preview(payload) or raw or "error",
                        args=args, preview=_preview(payload),
                    ))
                else:
                    results.append(ToolResult(
                        name=tool, klass=klass, status="PASS",
                        duration_ms=dt, args=args, preview=_preview(payload),
                    ))
                if verbose:
                    print(f"  {tool:<40s} {'FAIL' if is_err else 'PASS'}  {dt:>5d}ms  {_preview(payload, 80)}")
            except Exception as e:
                dt = int((time.monotonic() - t0) * 1000)
                results.append(ToolResult(
                    name=tool, klass=klass, status="FAIL",
                    duration_ms=dt, reason=f"exception: {e}", args=args,
                ))

    return results


# ────────────────────────────────────────────────────────────────────────────
#  Reporting
# ────────────────────────────────────────────────────────────────────────────

def render_markdown(
    url: str, version: Optional[str],
    advertised: list[str], results: list[ToolResult],
    cache: DiscoveryCache,
    include_write: bool, include_destructive: bool,
) -> str:
    total = len(results)
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    skipped = sum(1 for r in results if r.status == "SKIP")
    unclassified = [r.name for r in results if r.klass == "?"]

    lines: list[str] = []
    lines.append(f"# Printix MCP — Tool Smoketest Report")
    lines.append("")
    lines.append(f"- **Endpoint:** `{url}`")
    if version:
        lines.append(f"- **Server version:** `{version}`")
    lines.append(f"- **Tools advertised:** {len(advertised)}")
    lines.append(f"- **Tools classified:** {len(TOOL_CLASSES)}")
    lines.append(f"- **Tools executed:** {total} ({passed} PASS · {failed} FAIL · {skipped} SKIP)")
    lines.append(f"- **Flags:** `--include-write={include_write}` · `--include-destructive={include_destructive}`")
    lines.append("")
    lines.append("## Discovery Cache")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    for k in cache.__dataclass_fields__:
        v = cache.get(k)
        lines.append(f"| `{k}` | `{v}` |" if v else f"| `{k}` | _not found_ |")
    lines.append("")

    if unclassified:
        lines.append("## ⚠️ Unclassified tools (server advertises but smoketest does not know)")
        for n in unclassified:
            lines.append(f"- `{n}`")
        lines.append("")

    lines.append("## Results")
    lines.append("")
    lines.append("| Tool | Class | Status | Duration | Details |")
    lines.append("|---|---|---|---|---|")
    icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}
    for r in results:
        detail = r.reason or r.preview or ""
        detail = detail.replace("|", "\\|")
        dur = f"{r.duration_ms} ms" if r.duration_ms else "—"
        lines.append(f"| `{r.name}` | {r.klass} | {icon.get(r.status, '?')} {r.status} | {dur} | {detail[:120]} |")
    lines.append("")

    if failed:
        lines.append("## Failures (detail)")
        lines.append("")
        for r in results:
            if r.status == "FAIL":
                lines.append(f"### `{r.name}`")
                lines.append(f"- args: `{json.dumps(r.args)}`")
                lines.append(f"- reason: {r.reason}")
                if r.preview and r.preview != r.reason:
                    lines.append(f"- preview: `{r.preview}`")
                lines.append("")

    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────────────
#  Main
# ────────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Printix MCP tool smoketest")
    ap.add_argument("--url", default=os.getenv("PRINTIX_MCP_URL", "https://mcp.printix.cloud/mcp"),
                    help="MCP endpoint (default: $PRINTIX_MCP_URL or https://mcp.printix.cloud/mcp)")
    ap.add_argument("--token", default=os.getenv("PRINTIX_MCP_TOKEN"),
                    help="Bearer token (default: $PRINTIX_MCP_TOKEN)")
    ap.add_argument("--include-write", action="store_true", help="Also run write-safe tools")
    ap.add_argument("--include-destructive", action="store_true", help="Also run destructive tools (DANGER)")
    ap.add_argument("--only", default="", help="Comma-separated subset of tool names to run")
    ap.add_argument("--report", default="", help="Write markdown report to this path")
    ap.add_argument("--json", dest="json_out", default="", help="Write JSON report to this path")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    if not args.token:
        print("ERROR: no bearer token. Set $PRINTIX_MCP_TOKEN or pass --token.", file=sys.stderr)
        return 2

    only = {t.strip() for t in args.only.split(",") if t.strip()} or None

    print(f"Printix MCP smoketest → {args.url}")
    client = MCPClient(args.url, args.token, verbose=args.verbose)

    try:
        info = client.initialize()
    except Exception as e:
        print(f"ERROR: initialize failed: {e}", file=sys.stderr)
        return 2

    server_info = info.get("serverInfo", {}) if isinstance(info, dict) else {}
    server_version = server_info.get("version") or info.get("protocolVersion")
    print(f"  server: {server_info.get('name', '?')} v{server_version}")

    try:
        advertised = [t["name"] for t in client.list_tools()]
    except Exception as e:
        print(f"ERROR: tools/list failed: {e}", file=sys.stderr)
        return 2
    print(f"  advertised tools: {len(advertised)}")

    print("  running discovery...")
    cache = run_discovery(client, verbose=args.verbose)

    print("  executing tools...")
    results = run_tests(client, advertised, args.include_write, args.include_destructive,
                        only, cache, verbose=args.verbose)

    # Summary to stdout
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    skipped = sum(1 for r in results if r.status == "SKIP")
    print(f"\nResult: {passed} PASS · {failed} FAIL · {skipped} SKIP  (of {len(results)})")

    if failed:
        print("\nFailures:")
        for r in results:
            if r.status == "FAIL":
                print(f"  - {r.name}: {r.reason}")

    if args.report:
        md = render_markdown(args.url, str(server_version) if server_version else None,
                             advertised, results, cache,
                             args.include_write, args.include_destructive)
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"\nMarkdown report: {args.report}")

    if args.json_out:
        doc = {
            "endpoint": args.url,
            "server_version": str(server_version) if server_version else None,
            "advertised_tools": advertised,
            "include_write": args.include_write,
            "include_destructive": args.include_destructive,
            "discovery": asdict(cache),
            "results": [r.to_dict() for r in results],
        }
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2)
        print(f"JSON report: {args.json_out}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
