"""Generate a synthetic operational.db for dev_assist_cli tests.

Creates an in-memory DB copy written to disk with all observability tables
pre-populated with deterministic test data.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone, timedelta

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "db", "migrations")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _hours_ago(h: float) -> str:
    dt = datetime.now(timezone.utc) - timedelta(hours=h)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _days_ago(d: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=d)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _minutes_ago(m: float) -> str:
    dt = datetime.now(timezone.utc) - timedelta(minutes=m)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _day_ago(d: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=d)
    return dt.strftime("%Y-%m-%d")


def build_fixture_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    _init_schema(conn)
    _seed_work_items(conn)
    _seed_escalations(conn)
    _seed_errors(conn)
    _seed_llm_calls(conn)
    _seed_llm_calls_daily(conn)

    conn.commit()
    conn.close()


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS _schema_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""")

    # work_items
    conn.execute("""CREATE TABLE IF NOT EXISTS work_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL,
        target_role TEXT NOT NULL CHECK (target_role IN ('planner','architect','executor','reviewer')),
        kind TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        priority INTEGER NOT NULL DEFAULT 50,
        status TEXT NOT NULL CHECK (status IN ('pending','claimed','completed','failed','released')),
        claimed_by_runtime TEXT,
        claimed_at TEXT,
        claim_lease_until TEXT,
        completed_at TEXT,
        result_json TEXT,
        attempt_count INTEGER NOT NULL DEFAULT 0,
        max_attempts INTEGER NOT NULL DEFAULT 3,
        originating_run_id TEXT
    )""")

    # escalations
    conn.execute("""CREATE TABLE IF NOT EXISTS escalations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        originating_runtime TEXT NOT NULL CHECK (originating_runtime IN ('orchestrator','business-planner','architect','executor','reviewer')),
        originating_work_item_id INTEGER,
        trigger_kind TEXT NOT NULL,
        context TEXT NOT NULL,
        proposed_action TEXT NOT NULL,
        options_json TEXT NOT NULL,
        recommended_default TEXT NOT NULL,
        impact TEXT NOT NULL,
        urgency TEXT NOT NULL CHECK (urgency IN ('low','medium','high')),
        durable_artifact_target TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('pending','surfaced','approved','denied','expired')),
        surfaced_at TEXT,
        resolved_at TEXT,
        founder_response TEXT,
        telegram_message_id TEXT
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_escalations_surface ON escalations (status, urgency, id)""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_escalations_runtime ON escalations (originating_runtime, status)""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_escalations_work_item ON escalations (originating_work_item_id)""")

    # errors
    conn.execute("""CREATE TABLE IF NOT EXISTS errors (
        err_id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        runtime TEXT NOT NULL CHECK (runtime IN ('orchestrator','business-planner','architect','executor','reviewer','omniroute')),
        work_item_id TEXT,
        error_class TEXT NOT NULL,
        message TEXT NOT NULL,
        context_json TEXT NOT NULL DEFAULT '{}'
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_errors_ts ON errors (ts)""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_errors_runtime_ts ON errors (runtime, ts)""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_errors_work_item ON errors (work_item_id)""")

    # llm_calls
    conn.execute("""CREATE TABLE IF NOT EXISTS llm_calls (
        call_id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        runtime TEXT NOT NULL CHECK (runtime IN ('orchestrator','business-planner','architect','executor','reviewer')),
        work_item_id TEXT,
        model TEXT NOT NULL,
        routing_path TEXT NOT NULL CHECK (routing_path IN ('omniroute_endpoint','openrouter_endpoint')),
        tokens_in INTEGER NOT NULL,
        tokens_out INTEGER NOT NULL,
        latency_ms INTEGER NOT NULL,
        rate_in_per_1m_usd REAL NOT NULL,
        rate_out_per_1m_usd REAL NOT NULL,
        cost_usd REAL NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('success','fail')),
        error_class TEXT
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_llm_calls_ts ON llm_calls (ts)""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_llm_calls_runtime_model_ts ON llm_calls (runtime, model, ts)""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_llm_calls_work_item ON llm_calls (work_item_id)""")

    # llm_calls_daily
    conn.execute("""CREATE TABLE IF NOT EXISTS llm_calls_daily (
        day TEXT NOT NULL,
        runtime TEXT NOT NULL CHECK (runtime IN ('orchestrator','business-planner','architect','executor','reviewer')),
        model TEXT NOT NULL,
        routing_path TEXT NOT NULL CHECK (routing_path IN ('omniroute_endpoint','openrouter_endpoint')),
        call_count INTEGER NOT NULL,
        call_count_success INTEGER NOT NULL,
        call_count_fail INTEGER NOT NULL,
        tokens_in_total INTEGER NOT NULL,
        tokens_out_total INTEGER NOT NULL,
        cost_usd_total REAL NOT NULL,
        latency_ms_p50 INTEGER,
        latency_ms_p95 INTEGER,
        PRIMARY KEY (day, runtime, model, routing_path)
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_llm_calls_daily_day ON llm_calls_daily (day)""")

    conn.execute("""INSERT OR REPLACE INTO _schema_meta (key, value) VALUES ('schema_version', '3')""")


def _seed_work_items(conn: sqlite3.Connection) -> None:
    now = _now_iso()
    # Parent work item (id=1)
    conn.execute("""INSERT INTO work_items
        (created_at, updated_at, target_role, kind, payload_json, priority, status, claimed_by_runtime, claimed_at)
        VALUES (?, ?, 'executor', 'ticket_implementation', ?, 50, 'claimed', 'executor', ?)""",
        (now, now, json.dumps({"ticket_id": "TKT-027", "prompt": "build CLI"}), now))

    # Child work item (id=2) — references parent=1 in payload_json
    child_payload = json.dumps({"ticket_id": "TKT-028", "prompt": "structured logging", "parent_work_item_id": 1})
    conn.execute("""INSERT INTO work_items
        (created_at, updated_at, target_role, kind, payload_json, priority, status, claimed_by_runtime, claimed_at)
        VALUES (?, ?, 'architect', 'ticket_implementation', ?, 50, 'claimed', 'architect', ?)""",
        (now, now, child_payload, now))

    # Grandchild work item (id=3) — references parent=2
    gc_payload = json.dumps({"ticket_id": "TKT-029", "prompt": "telegram status", "parent_work_item_id": 2})
    conn.execute("""INSERT INTO work_items
        (created_at, updated_at, target_role, kind, payload_json, priority, status, claimed_by_runtime, claimed_at)
        VALUES (?, ?, 'planner', 'ticket_implementation', ?, 50, 'claimed', 'planner', ?)""",
        (now, now, gc_payload, now))

    # Pending items
    conn.execute("""INSERT INTO work_items
        (created_at, updated_at, target_role, kind, payload_json, priority, status)
        VALUES (?, ?, 'planner', 'prd_intake', '{}', 50, 'pending')""", (now, now))
    conn.execute("""INSERT INTO work_items
        (created_at, updated_at, target_role, kind, payload_json, priority, status)
        VALUES (?, ?, 'reviewer', 'ticket_review', '{}', 50, 'pending')""", (now, now))
    conn.execute("""INSERT INTO work_items
        (created_at, updated_at, target_role, kind, payload_json, priority, status)
        VALUES (?, ?, 'executor', 'ticket_implementation', '{}', 60, 'pending')""", (now, now))

    # Completed
    conn.execute("""INSERT INTO work_items
        (created_at, updated_at, target_role, kind, payload_json, priority, status, completed_at)
        VALUES (?, ?, 'executor', 'ticket_implementation', '{}', 50, 'completed', ?)""",
        (now, now, now))

    # Failed
    conn.execute("""INSERT INTO work_items
        (created_at, updated_at, target_role, kind, payload_json, priority, status)
        VALUES (?, ?, 'architect', 'architect_pass', '{}', 50, 'failed')""", (now, now))

    # Orphan work item — references non-existent parent_work_item_id
    orphan_payload = json.dumps({"ticket_id": "TKT-099", "description": "orphan test", "parent_work_item_id": 9999})
    conn.execute("""INSERT INTO work_items
        (created_at, updated_at, target_role, kind, payload_json, priority, status)
        VALUES (?, ?, 'executor', 'ticket_implementation', ?, 50, 'pending')""",
        (now, now, orphan_payload))


def _seed_escalations(conn: sqlite3.Connection) -> None:
    now = _now_iso()
    for i in range(12):
        age_hours = i * 2
        esc = (
            _hours_ago(age_hours),
            _hours_ago(age_hours),
            "executor",
            1,
            "deterministic_rule:paid_service",
            "LLM provider outside catalog requested",
            "Block the request",
            json.dumps(["approve", "deny"]),
            "deny",
            "Cost budget",
            "high" if i < 3 else "medium",
            "docs/adr/adr-011.md",
            "pending" if i < 5 else "surfaced" if i < 8 else "approved",
            _hours_ago(age_hours) if i >= 5 else None,
            _hours_ago(age_hours - 1) if i >= 8 else None,
            "Approved" if i >= 8 else None,
            f"msg_{i}" if i >= 5 else None,
        )
        conn.execute("""INSERT INTO escalations
            (created_at, updated_at, originating_runtime, originating_work_item_id,
             trigger_kind, context, proposed_action, options_json, recommended_default,
             impact, urgency, durable_artifact_target, status, surfaced_at, resolved_at,
             founder_response, telegram_message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", esc)


def _seed_errors(conn: sqlite3.Connection) -> None:
    roles = ["orchestrator", "business-planner", "architect", "executor", "reviewer"]
    for i, role in enumerate(roles):
        conn.execute("""INSERT INTO errors
            (err_id, ts, runtime, work_item_id, error_class, message, context_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (f"err_{i:03d}", _hours_ago(i * 0.5), role, "1", f"TestError{i}", f"Test message {i}", '{"stack":"trace"}'))
    # An older error > 24h
    conn.execute("""INSERT INTO errors
        (err_id, ts, runtime, work_item_id, error_class, message, context_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("err_old", _days_ago(2), "executor", "1", "OldError", "Old message", "{}"))
    # A recent error within last 5 minutes (for degraded-on-recent-error test)
    conn.execute("""INSERT INTO errors
        (err_id, ts, runtime, work_item_id, error_class, message, context_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("err_recent", _minutes_ago(2), "executor", "1", "RecentError", "Recent error for degraded test", "{}"))
    # An error within last 24h but older than 5 min (for last_error test)
    conn.execute("""INSERT INTO errors
        (err_id, ts, runtime, work_item_id, error_class, message, context_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("err_24h", _hours_ago(6), "executor", "1", "ErrorIn24h", "Error within last 24h", "{}"))


def _seed_llm_calls(conn: sqlite3.Connection) -> None:
    today = _today()
    # Today's calls
    data = [
        ("executor", "glm-5.1", "omniroute_endpoint", 1000, 500, 0.05),
        ("executor", "deepseek-v4-pro", "omniroute_endpoint", 5000, 2000, 0.15),
        ("architect", "deepseek-v4-pro", "omniroute_endpoint", 3000, 1000, 0.10),
        ("reviewer", "kimi-k2.6", "openrouter_endpoint", 2000, 800, 0.08),
        ("orchestrator", "minimax-m2.7", "omniroute_endpoint", 800, 300, 0.03),
    ]
    for idx, (role, model, rp, tin, tout, cost) in enumerate(data):
        conn.execute("""INSERT INTO llm_calls
            (call_id, ts, runtime, work_item_id, model, routing_path,
             tokens_in, tokens_out, latency_ms, rate_in_per_1m_usd, rate_out_per_1m_usd,
             cost_usd, status, error_class)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (f"call_{idx:03d}", f"{today}T10:00:00.000Z", role, "1", model, rp,
             tin, tout, 500, 0.5, 1.5, cost, "success", None))

    # Calls at 5-6 days ago (recent portion of the 7-day boundary, for split-merge testing)
    for d in (5, 6):
        day = _day_ago(d)
        conn.execute("""INSERT INTO llm_calls
            (call_id, ts, runtime, work_item_id, model, routing_path,
             tokens_in, tokens_out, latency_ms, rate_in_per_1m_usd, rate_out_per_1m_usd,
             cost_usd, status, error_class)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (f"call_rec_{d}", f"{day}T12:00:00.000Z", "architect", "1", "deepseek-v4-pro",
             "omniroute_endpoint", 2000, 800, 300, 0.5, 1.5, 0.07, "success", None))

    # Old calls for daily rollup
    for d in range(8, 15):
        day = _day_ago(d)
        conn.execute("""INSERT INTO llm_calls
            (call_id, ts, runtime, work_item_id, model, routing_path,
             tokens_in, tokens_out, latency_ms, rate_in_per_1m_usd, rate_out_per_1m_usd,
             cost_usd, status, error_class)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (f"call_old_{d}", f"{day}T10:00:00.000Z", "executor", "1", "deepseek-v4-pro", "omniroute_endpoint",
             5000, 2000, 500, 0.5, 1.5, 0.15, "success", None))


def _seed_llm_calls_daily(conn: sqlite3.Connection) -> None:
    for d in range(8, 15):
        day = _day_ago(d)
        conn.execute("""INSERT OR REPLACE INTO llm_calls_daily
            (day, runtime, model, routing_path, call_count, call_count_success, call_count_fail,
             tokens_in_total, tokens_out_total, cost_usd_total)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (day, "executor", "deepseek-v4-pro", "omniroute_endpoint", 1, 1, 0, 5000, 2000, 0.15))


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <db_path>", file=sys.stderr)
        sys.exit(1)
    build_fixture_db(sys.argv[1])