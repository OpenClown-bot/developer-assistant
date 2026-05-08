"""Reusable status-query function shared by dev-assist-cli and Telegram /status.

Extracts the status-query logic that was inlined in dev_assist_cli.py:cmd_status
into a single source-of-truth function that both the CLI and the Telegram
/status handler consume.

Stdlib only: sqlite3, json, urllib.request, datetime.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from developer_assistant.state.observability_store import (
    query_llm_calls,
)

_DEFAULT_DB_PATH = "/srv/devassist/state/operational.db"
_HEALTH_PORTS = {
    "orchestrator": 8181,
    "planner": 8182,
    "architect": 8183,
    "executor": 8184,
    "reviewer": 8185,
}
_ROLE_ORDER = ["orchestrator", "planner", "architect", "executor", "reviewer"]


def open_db_readonly(db_path: str) -> sqlite3.Connection:
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro&nolock=1", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn


def _check_health_endpoint(port: int, timeout: int = 5) -> dict:
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/health",
            headers={"User-Agent": "dev-assist-cli/0.1"},
        )
        resp = urllib.request.urlopen(req, timeout=timeout)
        body = json.loads(resp.read().decode())
        return {"ok": True, "status_code": resp.status, "body": body}
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _check_systemctl_unit(unit_name: str) -> str:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", unit_name],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def _human_tokens(n: int) -> str:
    if n >= 1000000:
        return f"{n / 1000000:.1f}M"
    if n >= 1000:
        return f"{n // 1000}K"
    return str(n)


def query_status(
    db_path: str = _DEFAULT_DB_PATH,
    health_ports: Optional[dict[str, int]] = None,
    role_order: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Single source-of-truth status query.

    Returns a dict with keys: ts_iso, runtimes, queue,
    recent_escalations, today_token_totals.
    Raises sqlite3.DatabaseError if the DB is unreachable.
    """
    if health_ports is None:
        health_ports = dict(_HEALTH_PORTS)
    if role_order is None:
        role_order = list(_ROLE_ORDER)

    conn = open_db_readonly(db_path)
    try:
        conn.execute("PRAGMA quick_check")
    except sqlite3.DatabaseError:
        conn.close()
        raise

    try:
        runtimes = []
        for role in role_order:
            if role == "omniroute":
                systemctl_state = _check_systemctl_unit("omniroute.service")
                if systemctl_state == "active":
                    state = "running"
                elif systemctl_state == "inactive":
                    state = "down"
                else:
                    state = "unknown"
                runtimes.append({
                    "role": role,
                    "state": state,
                    "health_endpoint": "systemctl:omniroute.service",
                    "health_endpoint_status": systemctl_state,
                })
                continue

            port = health_ports.get(role, 0)
            health = _check_health_endpoint(port)

            systemctl_state = _check_systemctl_unit(f"devassist-{role}.service")

            if health["ok"] and systemctl_state == "active":
                body = health.get("body", {})
                uptime_s = body.get("uptime_s")
                current_model = body.get("current_model")
                current_work_item_id = body.get("current_work_item_id")
                heartbeat_age_s = body.get("heartbeat_age_s", 0)

                now = datetime.now(timezone.utc)
                recent_err = conn.execute(
                    "SELECT 1 FROM errors WHERE runtime = ? AND ts >= ? LIMIT 1",
                    (role, (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S.000Z")),
                ).fetchone()
                last_err_row = conn.execute(
                    "SELECT ts as ts_iso, error_class FROM errors "
                    "WHERE runtime = ? AND ts >= ? ORDER BY ts DESC LIMIT 1",
                    (role, (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S.000Z")),
                ).fetchone()
                last_error = dict(last_err_row) if last_err_row else None

                heartbeat_degraded = heartbeat_age_s and heartbeat_age_s > 60
                error_degraded = recent_err is not None
                if heartbeat_degraded or error_degraded:
                    state = "degraded"
                else:
                    state = "running"
                last_error_val = last_error
            elif systemctl_state == "active":
                state = "degraded"
                last_error_val = None
            elif systemctl_state == "inactive":
                state = "down"
                last_error_val = None
            else:
                state = "unknown"
                last_error_val = None

            runtimes.append({
                "role": role,
                "state": state,
                "uptime_s": health.get("body", {}).get("uptime_s") if health["ok"] else None,
                "last_error": last_error_val,
                "current_model": health.get("body", {}).get("current_model") if health["ok"] else None,
                "current_work_item_id": health.get("body", {}).get("current_work_item_id") if health["ok"] else None,
                "heartbeat_age_s": health.get("body", {}).get("heartbeat_age_s") if health["ok"] else None,
                "health_endpoint": f"http://127.0.0.1:{port}/health",
                "health_endpoint_status": health.get("status_code") if health["ok"] else "unreachable",
            })

        queue = conn.execute("""
            SELECT status, COUNT(*) as cnt FROM work_items
            GROUP BY status
        """).fetchall()
        queue_counts = {
            "pending": 0,
            "in_progress": 0,
            "escalated": 0,
            "failed": 0,
        }
        for row in queue:
            if row["status"] == "pending":
                queue_counts["pending"] = row["cnt"]
            elif row["status"] in ("claimed",):
                queue_counts["in_progress"] = row["cnt"]
            elif row["status"] == "failed":
                queue_counts["failed"] = row["cnt"]

        esc_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM escalations WHERE status IN ('pending', 'surfaced')"
        ).fetchone()
        queue_counts["escalated"] = esc_count["cnt"] if esc_count else 0

        esc_rows = conn.execute("""
            SELECT created_at as ts_iso, trigger_kind as rule, status as disposition
            FROM escalations
            WHERE status IN ('pending', 'surfaced')
            ORDER BY created_at DESC
            LIMIT 10
        """).fetchall()
        recent_escalations = [dict(r) for r in esc_rows]

        now = datetime.now(timezone.utc)
        today_start = now.strftime("%Y-%m-%dT00:00:00.000Z")
        today_calls = query_llm_calls(conn, since=today_start)

        token_totals: dict[tuple[str, str], dict[str, Any]] = {}
        for call in today_calls:
            runtime = call.get("runtime", "")
            model = call.get("model", "")
            key = (runtime, model)
            if key not in token_totals:
                token_totals[key] = {
                    "role": runtime,
                    "model": model,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "estimated_usd": 0.0,
                }
            token_totals[key]["tokens_in"] += int(call.get("tokens_in", 0))
            token_totals[key]["tokens_out"] += int(call.get("tokens_out", 0))
            token_totals[key]["estimated_usd"] += float(call.get("cost_usd", 0))

        today_token_totals = list(token_totals.values())

        output = {
            "ts_iso": now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z",
            "runtimes": runtimes,
            "queue": queue_counts,
            "recent_escalations": recent_escalations,
            "today_token_totals": today_token_totals,
        }
    finally:
        conn.close()

    return output


def render_status_human(output: dict[str, Any]) -> str:
    """Render status dict as human-readable text (same format as dev-assist-cli --format human).

    Returns the rendered string; caller decides what to do with it
    (print to stdout, send via Telegram, etc.).
    """
    lines: list[str] = []
    lines.append(f"Dev Assistant — status as of {output['ts_iso']}")
    lines.append("")
    lines.append("Runtimes:")
    for rt in output["runtimes"]:
        role = rt["role"]
        state = rt["state"]
        extra = ""
        if rt.get("current_work_item_id"):
            extra += f" (work_item {rt['current_work_item_id']})"
        if rt.get("current_model"):
            extra += f" (model {rt['current_model']})"
        if rt.get("uptime_s"):
            extra += f" (uptime {rt['uptime_s']}s)"
        hp = rt.get("health_endpoint_status", "?")
        lines.append(f"  {role:<20s} {state:<10s} health={hp}{extra}")

    q = output["queue"]
    lines.append(f"\nQueue: {q['pending']} pending, {q['in_progress']} in progress, {q['escalated']} escalated, {q['failed']} failed")

    if output["today_token_totals"]:
        lines.append("\nToday (UTC):")
        for t in output["today_token_totals"]:
            tin = _human_tokens(t["tokens_in"])
            tout = _human_tokens(t["tokens_out"])
            usd = t["estimated_usd"]
            lines.append(f"  {t['role']:<12s} {t['model']:<20s} {tin} in / {tout} out   ~${usd:.2f}")

    escs = output["recent_escalations"]
    if escs:
        lines.append(f"\nLast {len(escs)} escalations:")
        for e in escs:
            lines.append(f"  {e['ts_iso']}  {e['rule']} ({e['disposition']})")

    return "\n".join(lines)
