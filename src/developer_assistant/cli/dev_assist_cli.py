"""dev-assist-cli — operator CLI for the developer-assistant observability surface.

Reads recent log entries from systemd journald, the operational state store
at /srv/devassist/state/operational.db, and localhost-only health endpoints.
Does NOT call any specialist runtime; works even when all runtimes are down.

Stdlib only: argparse, sqlite3, subprocess, json, datetime.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from developer_assistant.observability.status_query import (
    _HEALTH_PORTS,
    open_db_readonly,
    query_status,
    render_status_human,
)
from developer_assistant.smoke_inject import (
    DEFAULT_MARKER_FILE_PATH,
    DEFAULT_OPERATIONAL_DB_PATH,
    INJECT_PORT,
    ROLE_PORTS as _SMOKE_ROLE_PORTS,
    is_smoke_mode_active,
)
from developer_assistant.state.observability_store import (
    query_errors,
    query_llm_calls,
    query_llm_calls_daily,
)

_DEFAULT_DB_PATH = "/srv/devassist/state/operational.db"
_ROLE_ORDER = ["orchestrator", "planner", "architect", "executor", "reviewer"]


def parse_duration(value: str) -> str:
    """Parse a duration string or ISO date into an ISO 8601 UTC timestamp."""
    now = datetime.now(timezone.utc)
    original = value

    if value == "today":
        return now.strftime("%Y-%m-%dT00:00:00.000Z")

    try:
        return datetime.fromisoformat(value).isoformat()
    except ValueError:
        pass

    unit = value[-1].lower()
    if unit in ("h", "m", "d"):
        try:
            num = int(value[:-1])
        except ValueError:
            raise SystemExit(f"ERROR: invalid duration: {original}")
        if unit == "h":
            dt = now - timedelta(hours=num)
        elif unit == "m":
            dt = now - timedelta(minutes=num)
        else:
            dt = now - timedelta(days=num)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000") + "Z"

    raise SystemExit(f"ERROR: invalid duration format: {original}")


def _get_work_item_id(parent_id: int, conn: sqlite3.Connection) -> list[int]:
    """Find work items whose payload_json references the given parent work item id."""
    child_rows = conn.execute(
        "SELECT id, payload_json FROM work_items"
    ).fetchall()
    children = []
    for row in child_rows:
        try:
            payload = json.loads(row["payload_json"])
            if payload.get("parent_work_item_id") == parent_id:
                children.append(row["id"])
        except (json.JSONDecodeError, KeyError):
            continue
    return children


def cmd_status(args: argparse.Namespace) -> int:
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"operational.db unreachable: file not found: {db_path}", file=sys.stderr)
        return 1

    try:
        output = query_status(db_path=db_path)
    except sqlite3.DatabaseError as e:
        print(f"operational.db unreachable: {e}", file=sys.stderr)
        return 1

    if getattr(args, "format", "json") == "human":
        print(render_status_human(output))
    else:
        print(json.dumps(output, indent=2))
    return 0


def _human_tokens(n: int) -> str:
    if n >= 1000000:
        return f"{n / 1000000:.1f}M"
    if n >= 1000:
        return f"{n // 1000}K"
    return str(n)


def cmd_logs(args: argparse.Namespace) -> int:
    work_item_id = args.work_item
    fixture_path = os.environ.get("DEV_ASSIST_CLI_JOURNAL_FIXTURE")

    if fixture_path:
        lines = _read_journal_fixture(fixture_path)
    else:
        since_str = parse_duration(args.since) if args.since else "today"
        log_role = getattr(args, "role", None)
        cmd = [
            "journalctl",
            "--output=json", "--no-pager",
            "--since", since_str,
        ]
        if log_role:
            cmd.extend(["-u", f"devassist-{log_role}.service"])
        else:
            cmd.extend([
                "-u", "devassist-orchestrator.service",
                "-u", "devassist-planner.service",
                "-u", "devassist-architect.service",
                "-u", "devassist-executor.service",
                "-u", "devassist-reviewer.service",
            ])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                if "No journal files" in result.stderr or "No entries" in result.stderr:
                    lines = []
                else:
                    lines = []
                    if result.stdout.strip():
                        lines = [l for l in result.stdout.strip().split("\n") if l]
            else:
                lines = [l for l in result.stdout.strip().split("\n") if l]
        except FileNotFoundError:
            print("journalctl unavailable", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"journalctl error: {e}", file=sys.stderr)
            return 1

    filtered = []
    if work_item_id is not None:
        for line in lines:
            try:
                entry = json.loads(line)
                msg = json.loads(entry.get("MESSAGE", "{}"))
                if msg.get("work_item_id") == work_item_id or str(msg.get("work_item_id")) == str(work_item_id):
                    filtered.append(entry)
            except (json.JSONDecodeError, AttributeError):
                continue
    else:
        filtered = lines

    if args.recursive and work_item_id is not None:
        db_path = args.db_path
        if os.path.exists(db_path):
            try:
                conn = open_db_readonly(db_path)
                try:
                    queue = [int(work_item_id)]
                    seen = set(queue)
                    while queue:
                        pid = queue.pop(0)
                        exists = conn.execute(
                            "SELECT 1 FROM work_items WHERE id = ?", (pid,)
                        ).fetchone()
                        if not exists:
                            print(
                                f"parent_work_item_id {pid} referenced but not found in work_items",
                                file=sys.stderr,
                            )
                        children = _get_work_item_id(pid, conn)
                        for child_id in children:
                            if child_id not in seen:
                                seen.add(child_id)
                                queue.append(child_id)
                    all_ids = seen
                finally:
                    conn.close()
            except Exception:
                print("unable to resolve parent_work_item_id chain from operational.db", file=sys.stderr)
                all_ids = {int(work_item_id)}
        else:
            print("operational.db not found — cannot resolve recursive chain", file=sys.stderr)
            all_ids = {int(work_item_id)}

        filtered = []
        for line in lines:
            try:
                entry = json.loads(line)
                msg = json.loads(entry.get("MESSAGE", "{}"))
                wid = msg.get("work_item_id")
                if wid is not None and str(wid) in {str(i) for i in all_ids}:
                    filtered.append(entry)
            except (json.JSONDecodeError, AttributeError):
                continue

    sorted_lines = sorted(filtered, key=lambda e: e.get("__REALTIME_TIMESTAMP", "0"))

    for entry in sorted_lines:
        print(json.dumps(entry))

    return 0


def _read_journal_fixture(path: str) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def cmd_errors(args: argparse.Namespace) -> int:
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"operational.db unreachable: file not found: {db_path}", file=sys.stderr)
        return 1

    try:
        conn = open_db_readonly(db_path)
    except sqlite3.DatabaseError as e:
        print(f"operational.db unreachable: {e}", file=sys.stderr)
        return 1

    try:
        since = parse_duration(args.since)
        role = getattr(args, "role", None)
        rows = query_errors(conn, since=since, runtime_role=role)
    finally:
        conn.close()

    if getattr(args, "format", "json") == "human":
        if rows:
            headers = ["ts", "runtime", "error_class", "message", "work_item_id"]
            widths = [26, 14, 20, 40, 12]
            print("  ".join(f"{h:<{w}}" for h, w in zip(headers, widths)))
            print("  ".join("-" * w for w in widths))
            for r in rows:
                vals = [
                    str(r.get("ts", ""))[:25],
                    str(r.get("runtime", ""))[:13],
                    str(r.get("error_class", ""))[:19],
                    str(r.get("message", ""))[:39],
                    str(r.get("work_item_id", ""))[:11],
                ]
                print("  ".join(f"{v:<{w}}" for v, w in zip(vals, widths)))
        else:
            print("No errors found for the given time window.")
    else:
        print(json.dumps(rows, indent=2))
    return 0


def cmd_costs(args: argparse.Namespace) -> int:
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"operational.db unreachable: file not found: {db_path}", file=sys.stderr)
        return 1

    try:
        conn = open_db_readonly(db_path)
    except sqlite3.DatabaseError as e:
        print(f"operational.db unreachable: {e}", file=sys.stderr)
        return 1

    try:
        since_iso = parse_duration(args.since)
        role = getattr(args, "role", None)
        model_filter = getattr(args, "model", None)

        now = datetime.now(timezone.utc)
        since_dt = datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
        cutoff_iso = (now - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00.000Z")
        cutoff_day = (now - timedelta(days=7)).strftime("%Y-%m-%d")

        tables_used = []

        rows: list[dict] = []
        if since_iso >= cutoff_iso:
            tables_used.append("llm_calls")
            rows = query_llm_calls(
                conn, since=since_iso,
                runtime_role=role, model=model_filter,
            )
        else:
            tables_used = ["llm_calls", "llm_calls_daily"]
            recent = query_llm_calls(
                conn, since=cutoff_iso,
                runtime_role=role, model=model_filter,
            )
            for r in recent:
                rows.append({
                    "runtime": r.get("runtime"),
                    "model": r.get("model"),
                    "tokens_in": r.get("tokens_in", 0),
                    "tokens_out": r.get("tokens_out", 0),
                    "cost_usd": r.get("cost_usd", 0),
                })
            daily_rows = query_llm_calls_daily(
                conn, since=since_iso.split("T")[0],
                until=cutoff_day,
                runtime_role=role, model=model_filter,
            )
            for r in daily_rows:
                rows.append({
                    "runtime": r.get("runtime"),
                    "model": r.get("model"),
                    "tokens_in": r.get("tokens_in_total", 0),
                    "tokens_out": r.get("tokens_out_total", 0),
                    "cost_usd": r.get("cost_usd_total", 0),
                    "call_count": r.get("call_count", 1),
                })
    finally:
        conn.close()

    aggregated: dict[tuple[str, str], dict] = {}
    for row in rows:
        runtime = row.get("runtime", "")
        model = row.get("model", "")
        key = (runtime, model)
        if key not in aggregated:
            aggregated[key] = {
                "role": runtime,
                "model": model,
                "calls": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "estimated_usd": 0.0,
            }
        aggregated[key]["calls"] += row.get("call_count", 1)
        aggregated[key]["tokens_in"] += int(row.get("tokens_in", 0))
        aggregated[key]["tokens_out"] += int(row.get("tokens_out", 0))
        aggregated[key]["estimated_usd"] += float(row.get("cost_usd", 0))

    by_role_model = list(aggregated.values())
    totals = {
        "tokens_in": sum(a["tokens_in"] for a in by_role_model),
        "tokens_out": sum(a["tokens_out"] for a in by_role_model),
        "estimated_usd": sum(a["estimated_usd"] for a in by_role_model),
    }

    output = {
        "since_iso": since_iso,
        "tables_queried": tables_used,
        "totals": totals,
        "by_role_model": by_role_model,
    }

    if getattr(args, "format", "json") == "human":
        print(f"Since: {since_iso}")
        print(f"Tables queried: {', '.join(tables_used)}")
        print()
        print(f"Total: {_human_tokens(totals['tokens_in'])} in / {_human_tokens(totals['tokens_out'])} out / ${totals['estimated_usd']:.4f}")
        print()
        if by_role_model:
            headers = ["role", "model", "calls", "tokens_in", "tokens_out", "est_usd"]
            widths = [14, 22, 7, 14, 14, 10]
            print("  ".join(f"{h:<{w}}" for h, w in zip(headers, widths)))
            print("  ".join("-" * w for w in widths))
            for b in by_role_model:
                vals = [
                    b["role"][:13],
                    b["model"][:21],
                    str(b["calls"]),
                    _human_tokens(b["tokens_in"]),
                    _human_tokens(b["tokens_out"]),
                    f"${b['estimated_usd']:.4f}",
                ]
                print("  ".join(f"{v:<{w}}" for v, w in zip(vals, widths)))
        else:
            print("No cost data for this window.")
    else:
        print(json.dumps(output, indent=2))
    return 0


def cmd_escalations(args: argparse.Namespace) -> int:
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"operational.db unreachable: file not found: {db_path}", file=sys.stderr)
        return 1

    try:
        conn = open_db_readonly(db_path)
    except sqlite3.DatabaseError as e:
        print(f"operational.db unreachable: {e}", file=sys.stderr)
        return 1

    try:
        since = parse_duration(args.since)
        cur = conn.execute("""
            SELECT id, created_at, updated_at, originating_runtime,
                   originating_work_item_id, trigger_kind, context, proposed_action,
                   options_json, recommended_default, impact, urgency,
                   durable_artifact_target, status, surfaced_at, resolved_at,
                   founder_response, telegram_message_id
            FROM escalations
            WHERE created_at >= ?
            ORDER BY created_at DESC
        """, (since,))
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    if getattr(args, "format", "json") == "human":
        if rows:
            headers = ["id", "created_at", "runtime", "trigger", "status", "urgency"]
            widths = [5, 26, 14, 25, 10, 8]
            print("  ".join(f"{h:<{w}}" for h, w in zip(headers, widths)))
            print("  ".join("-" * w for w in widths))
            for r in rows:
                vals = [
                    str(r.get("id", "")),
                    str(r.get("created_at", ""))[:25],
                    str(r.get("originating_runtime", ""))[:13],
                    str(r.get("trigger_kind", ""))[:24],
                    str(r.get("status", "")),
                    str(r.get("urgency", "")),
                ]
                print("  ".join(f"{v:<{w}}" for v, w in zip(vals, widths)))
        else:
            print("No escalations found for the given time window.")
    else:
        print(json.dumps(rows, indent=2))
    return 0



def _smoke_print_refusal() -> int:
    """Emit the structured smoke-mode-not-enabled refusal and return exit 2."""
    payload = {
        "status": "refused",
        "error": "smoke_mode_not_enabled",
        "hint": (
            "smoke-mode marker file is absent; this CLI subcommand only "
            "operates on a smoke-mode install. See TKT-041 \u00a7 1.4 (1)."
        ),
    }
    print(json.dumps(payload, sort_keys=True))
    return 2


def _smoke_http_post(
    host: str,
    port: int,
    path: str,
    body: dict[str, object],
    timeout_s: int,
) -> tuple[int, dict[str, object]]:
    """POST JSON body to a localhost-only smoke endpoint. Returns (status, body).

    Uses stdlib urllib so the CLI has zero non-stdlib dependencies (matches
    the existing ``dev-assist-cli`` discipline at the top of this module).
    """
    import urllib.error
    import urllib.request

    if host not in ("127.0.0.1", "::1", "localhost"):
        raise ValueError(
            f"smoke CLI refuses non-localhost host: {host!r}",
        )
    url = f"http://{host}:{port}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return exc.code, parsed


def cmd_smoke_inject_message(args: argparse.Namespace) -> int:
    """smoke inject-message → POST to Orchestrator inject endpoint."""
    if not is_smoke_mode_active(args.marker_file):
        return _smoke_print_refusal()
    body = {
        "text": args.text,
        "from_user_id": args.from_user_id,
    }
    try:
        status, payload = _smoke_http_post(
            args.inject_host, args.inject_port,
            "/smoke/inject-message", body, args.timeout_s,
        )
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(payload, sort_keys=True))
    return 0 if status == 200 else 1


def cmd_smoke_test_tool(args: argparse.Namespace) -> int:
    """smoke test-tool → POST to per-runtime test-tool endpoint (AC-3)."""
    if not is_smoke_mode_active(args.marker_file):
        return _smoke_print_refusal()
    port = _SMOKE_ROLE_PORTS[args.runtime]
    body = {"tool": args.tool}
    try:
        status, payload = _smoke_http_post(
            args.test_tool_host, port,
            "/smoke/test-tool", body, args.timeout_s,
        )
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(payload, sort_keys=True))
    if status != 200:
        return 1
    # Exit code reflects dispatch result: 0 = dispatched (positive), 3 =
    # refused (negative AC-3 i/ii expected outcome), 1 = unexpected.
    result_status = payload.get("status") if isinstance(payload, dict) else None
    if result_status == "dispatched":
        return 0
    if result_status == "refused":
        return 3
    return 1


def cmd_smoke_wait(args: argparse.Namespace) -> int:
    """smoke wait → poll operational.db.work_items until target state."""
    if not is_smoke_mode_active(args.marker_file):
        return _smoke_print_refusal()
    import time as _time

    target = args.until
    db_path = args.db_path or _DEFAULT_DB_PATH
    deadline = _time.time() + args.timeout_s
    last_status: str | None = None
    last_claimed_at: str | None = None
    last_completed_at: str | None = None
    last_result: str | None = None

    while _time.time() < deadline:
        try:
            conn = sqlite3.connect(db_path)
            try:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT status, claimed_at, completed_at, result_json "
                    "FROM work_items WHERE id = ?",
                    (args.work_item_id,),
                ).fetchone()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
            return 1

        if row is None:
            print(json.dumps({
                "status": "error", "error": "work_item_not_found",
                "work_item_id": args.work_item_id,
            }, sort_keys=True))
            return 1

        last_status = row["status"]
        last_claimed_at = row["claimed_at"]
        last_completed_at = row["completed_at"]
        last_result = row["result_json"]

        if target == "claimed" and last_status in ("claimed", "completed", "failed"):
            print(json.dumps({
                "status": "ok", "target": target,
                "work_item_id": args.work_item_id,
                "work_item_status": last_status,
                "claimed_at": last_claimed_at,
            }, sort_keys=True))
            return 0
        if target == "completed" and last_status in ("completed", "failed"):
            print(json.dumps({
                "status": "ok", "target": target,
                "work_item_id": args.work_item_id,
                "work_item_status": last_status,
                "completed_at": last_completed_at,
                "result_json": last_result,
            }, sort_keys=True))
            return 0 if last_status == "completed" else 1

        _time.sleep(args.poll_interval_s)

    # Timeout → emit the structured diagnostic per AC-6.
    diagnostic = (
        "planner_claim_timeout" if target == "claimed" else "planner_result_timeout"
    )
    print(json.dumps({
        "status": "timeout", "error": diagnostic,
        "work_item_id": args.work_item_id,
        "work_item_status": last_status,
    }, sort_keys=True))
    return 1


def cmd_smoke(args: argparse.Namespace) -> int:
    if args.smoke_command == "inject-message":
        return cmd_smoke_inject_message(args)
    if args.smoke_command == "test-tool":
        return cmd_smoke_test_tool(args)
    if args.smoke_command == "wait":
        return cmd_smoke_wait(args)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dev-assist-cli",
        description="Operator CLI for the developer-assistant observability surface.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  dev-assist-cli status
  dev-assist-cli status --format human
  dev-assist-cli logs --work-item 1
  dev-assist-cli logs --work-item 1 --recursive --since 1h
  dev-assist-cli errors --since 1h
  dev-assist-cli errors --since 1h --role executor --format human
  dev-assist-cli costs --since today
  dev-assist-cli costs --since 7d --role executor --format human
  dev-assist-cli escalations --since 24h
  dev-assist-cli escalations --since today --format human
""",
    )
    parser.add_argument(
        "--db-path",
        default=os.environ.get("DEV_ASSIST_DB_PATH", _DEFAULT_DB_PATH),
        help=f"Path to operational.db (default: {_DEFAULT_DB_PATH}; env: DEV_ASSIST_DB_PATH)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="Per-runtime system state summary")
    p_status.add_argument("--format", choices=["json", "human"], default="json")

    p_logs = sub.add_parser("logs", help="Fetch journald logs for a work item or role")
    p_logs.add_argument("--work-item", default=None, help="Work item ID to filter by")
    p_logs.add_argument("--role", default=None, choices=list(_HEALTH_PORTS.keys()), help="Filter to a single runtime")
    p_logs.add_argument("--recursive", action="store_true", help="Follow parent_work_item_id chain")
    p_logs.add_argument("--since", default="today", help="Time window (e.g. 1h, 30m, today)")

    p_errors = sub.add_parser("errors", help="Recent rows from the errors table")
    p_errors.add_argument("--since", required=True, help="Time window (e.g. 1h, 30m, today, 2026-05-06)")
    p_errors.add_argument("--role", help="Filter by runtime role")
    p_errors.add_argument("--format", choices=["json", "human"], default="json")

    p_costs = sub.add_parser("costs", help="Aggregated LLM cost data")
    p_costs.add_argument("--since", required=True, help="Time window (e.g. today, 7d, 1h)")
    p_costs.add_argument("--role", help="Filter by runtime role")
    p_costs.add_argument("--model", help="Filter by model identifier")
    p_costs.add_argument("--format", choices=["json", "human"], default="json")

    p_escalations = sub.add_parser("escalations", help="Recent rows from the escalations table")
    p_escalations.add_argument("--since", required=True, help="Time window (e.g. 24h, today, 1h)")
    p_escalations.add_argument("--format", choices=["json", "human"], default="json")

    p_smoke = sub.add_parser(
        "smoke",
        help="TKT-041 AUDIT-003 deployment smoke subcommand group (smoke-mode only)",
    )
    p_smoke.add_argument(
        "--marker-file",
        default=os.environ.get("DEVASSIST_SMOKE_MODE_MARKER_PATH", DEFAULT_MARKER_FILE_PATH),
        help=f"Smoke-mode marker file path (default: {DEFAULT_MARKER_FILE_PATH})",
    )
    smoke_sub = p_smoke.add_subparsers(dest="smoke_command", required=True)

    p_inject = smoke_sub.add_parser(
        "inject-message",
        help="Inject synthetic Telegram message into Orchestrator gateway dispatcher",
    )
    p_inject.add_argument("--text", required=True, help="Synthetic message text")
    p_inject.add_argument(
        "--from-user-id",
        type=int,
        default=999999999,
        help="Synthetic Telegram from_user.id (default: 999999999)",
    )
    p_inject.add_argument(
        "--timeout-s",
        type=int,
        default=5,
        help="HTTP request timeout in seconds (default: 5)",
    )
    p_inject.add_argument(
        "--inject-host",
        default="127.0.0.1",
        help="Inject admin port host (default: 127.0.0.1; localhost-only)",
    )
    p_inject.add_argument(
        "--inject-port",
        type=int,
        default=INJECT_PORT,
        help=f"Inject admin port (default: {INJECT_PORT})",
    )

    p_test_tool = smoke_sub.add_parser(
        "test-tool",
        help="Dispatch synthetic tool-call to runtime test-tool endpoint (AC-3)",
    )
    p_test_tool.add_argument(
        "--runtime",
        required=True,
        choices=sorted(_SMOKE_ROLE_PORTS.keys()),
        help="Target runtime role",
    )
    p_test_tool.add_argument(
        "--tool",
        required=True,
        help="Tool name to dispatch (e.g. delegate_task, skill_manage, dev-assist-work-queue-poll)",
    )
    p_test_tool.add_argument(
        "--timeout-s", type=int, default=5,
    )
    p_test_tool.add_argument(
        "--test-tool-host", default="127.0.0.1",
    )

    p_wait = smoke_sub.add_parser(
        "wait",
        help="Poll operational.db until a work_item reaches the desired state",
    )
    p_wait.add_argument("--work-item-id", type=int, required=True)
    p_wait.add_argument(
        "--until",
        required=True,
        choices=["claimed", "completed"],
        help="Target state: claimed (AC-6 N1) or completed (AC-6 N2)",
    )
    p_wait.add_argument("--timeout-s", type=int, required=True)
    p_wait.add_argument(
        "--poll-interval-s",
        type=float,
        default=1.0,
        help="Poll interval in seconds (default: 1.0)",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    if args.command == "status":
        return cmd_status(args)
    elif args.command == "logs":
        return cmd_logs(args)
    elif args.command == "errors":
        return cmd_errors(args)
    elif args.command == "costs":
        return cmd_costs(args)
    elif args.command == "escalations":
        return cmd_escalations(args)
    elif args.command == "smoke":
        return cmd_smoke(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())