"""dev-assist-cli — operator CLI for the developer-assistant observability surface.

Reads recent log entries from systemd journald, the operational state store
at /srv/devassist/state/operational.db, and localhost-only health endpoints.
Does NOT call any specialist runtime; works even when all runtimes are down.

Stdlib only: argparse, sqlite3, subprocess, json, urllib.request, datetime.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from developer_assistant.state.observability_store import (
    query_errors,
    query_llm_calls,
    query_llm_calls_daily,
)

_DEFAULT_DB_PATH = "/srv/devassist/state/operational.db"
_HEALTH_PORTS = {
    "orchestrator": 8181,
    "planner": 8182,
    "architect": 8183,
    "executor": 8184,
    "reviewer": 8185,
}
_ROLE_ORDER = ["orchestrator", "planner", "architect", "executor", "reviewer", "omniroute"]


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


def open_db_readonly(db_path: str) -> sqlite3.Connection:
    """Open the operational DB read-only. Falls back gracefully on Windows."""
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
            headers={"User-Agent": "dev-assist-cli/0.1"}
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
        conn = open_db_readonly(db_path)
        try:
            conn.execute("PRAGMA quick_check")
        except sqlite3.DatabaseError as e:
            print(f"operational.db unreachable: {e}", file=sys.stderr)
            return 1
    except sqlite3.DatabaseError as e:
        print(f"operational.db unreachable: {e}", file=sys.stderr)
        return 1

    try:
        runtimes = []
        for role in _ROLE_ORDER:
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

            port = _HEALTH_PORTS[role]
            health = _check_health_endpoint(port)

            systemctl_state = _check_systemctl_unit(f"devassist-{role}.service")

            if health["ok"] and systemctl_state == "active":
                body = health.get("body", {})
                uptime_s = body.get("uptime_s")
                current_model = body.get("current_model")
                current_work_item_id = body.get("current_work_item_id")
                heartbeat_age_s = body.get("heartbeat_age_s", 0)

                if heartbeat_age_s and heartbeat_age_s > 300:
                    state = "degraded"
                else:
                    state = "running"
            elif systemctl_state == "active":
                state = "degraded"
            elif systemctl_state == "inactive":
                state = "down"
            else:
                state = "unknown"

            runtimes.append({
                "role": role,
                "state": state,
                "uptime_s": health.get("body", {}).get("uptime_s") if health["ok"] else None,
                "last_error": None,
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

        token_totals: dict[tuple[str, str], dict[str, float]] = {}
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

    if getattr(args, "format", "json") == "human":
        _print_status_human(output)
    else:
        print(json.dumps(output, indent=2))
    return 0


def _print_status_human(output: dict) -> None:
    print(f"Dev Assistant — status as of {output['ts_iso']}")
    print()
    print("Runtimes:")
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
        print(f"  {role:<20s} {state:<10s} health={hp}{extra}")

    q = output["queue"]
    print(f"\nQueue: {q['pending']} pending, {q['in_progress']} in progress, {q['escalated']} escalated, {q['failed']} failed")

    if output["today_token_totals"]:
        print("\nToday (UTC):")
        for t in output["today_token_totals"]:
            tin = _human_tokens(t["tokens_in"])
            tout = _human_tokens(t["tokens_out"])
            usd = t["estimated_usd"]
            print(f"  {t['role']:<12s} {t['model']:<20s} {tin} in / {tout} out   ~${usd:.2f}")

    escs = output["recent_escalations"]
    if escs:
        print(f"\nLast {len(escs)} escalations:")
        for e in escs:
            print(f"  {e['ts_iso']}  {e['rule']} ({e['disposition']})")


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
        cmd = [
            "journalctl",
            "--output=json", "--no-pager",
            "--since", since_str,
            "-u", "devassist-orchestrator.service",
            "-u", "devassist-planner.service",
            "-u", "devassist-architect.service",
            "-u", "devassist-executor.service",
            "-u", "devassist-reviewer.service",
        ]
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
    for line in lines:
        try:
            entry = json.loads(line)
            msg = json.loads(entry.get("MESSAGE", "{}"))
            if msg.get("work_item_id") == work_item_id or str(msg.get("work_item_id")) == str(work_item_id):
                filtered.append(entry)
        except (json.JSONDecodeError, AttributeError):
            continue

    if args.recursive:
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
        aggregated[key]["calls"] += 1
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

    p_logs = sub.add_parser("logs", help="Fetch journald logs for a work item")
    p_logs.add_argument("--work-item", required=True, help="Work item ID to filter by")
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

    return 0


if __name__ == "__main__":
    sys.exit(main())