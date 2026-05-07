"""Observability store: typed helpers for errors, llm_calls, llm_calls_daily.

Implements OPERATIONAL-STATE-STORE.md v0.3.0 §§ 3.7-3.9 and
OBSERVABILITY-CONTRACT.md v0.1.1 §§ 9-10.

All functions take a sqlite3.Connection. All timestamps are ISO 8601 UTC.
WAL mode and synchronous=NORMAL are enforced on first connection via
ensure_wal_mode().
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_ulid() -> str:
    return uuid.uuid4().hex


def ensure_wal_mode(db: sqlite3.Connection) -> None:
    cur = db.execute("PRAGMA journal_mode")
    mode = cur.fetchone()[0]
    if mode.lower() != "wal":
        db.execute("PRAGMA journal_mode = WAL")
    db.execute("PRAGMA synchronous = NORMAL")


def record_error(
    db: sqlite3.Connection,
    *,
    role: str,
    kind: str,
    message: str,
    work_item_id: Optional[str] = None,
    stack: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> str:
    err_id = _new_ulid()
    ts = _now_iso()
    merged_context: dict[str, Any] = {}
    if context:
        merged_context.update(context)
    if stack:
        merged_context["stack"] = stack
    context_json = json.dumps(merged_context, sort_keys=True)
    db.execute(
        """INSERT INTO errors (err_id, ts, runtime, work_item_id, error_class, message, context_json)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (err_id, ts, role, work_item_id, kind, message, context_json),
    )
    db.commit()
    return err_id


def record_llm_call(
    db: sqlite3.Connection,
    *,
    role: str,
    work_item_id: Optional[str] = None,
    model_id: str = "",
    routing_path: str = "omniroute_endpoint",
    tokens_in: int = 0,
    tokens_out: int = 0,
    latency_ms: int = 0,
    rate_in_per_1m_usd: float = 0.0,
    rate_out_per_1m_usd: float = 0.0,
    cost_usd: float = 0.0,
    status: str = "success",
    error_class: Optional[str] = None,
) -> str:
    call_id = _new_ulid()
    ts = _now_iso()
    db.execute(
        """INSERT INTO llm_calls
           (call_id, ts, runtime, work_item_id, model, routing_path,
            tokens_in, tokens_out, latency_ms, rate_in_per_1m_usd,
            rate_out_per_1m_usd, cost_usd, status, error_class)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (call_id, ts, role, work_item_id, model_id, routing_path,
         tokens_in, tokens_out, latency_ms, rate_in_per_1m_usd,
         rate_out_per_1m_usd, cost_usd, status, error_class),
    )
    db.commit()
    return call_id


def aggregate_llm_calls_daily(
    db: sqlite3.Connection,
    target_date: str,
) -> int:
    cur = db.execute(
        """SELECT
             runtime, model, routing_path,
             COUNT(*) AS call_count,
             SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS call_count_success,
             SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END) AS call_count_fail,
             SUM(tokens_in) AS tokens_in_total,
             SUM(tokens_out) AS tokens_out_total,
             SUM(cost_usd) AS cost_usd_total
           FROM llm_calls
           WHERE ts >= ? AND ts < ?
           GROUP BY runtime, model, routing_path""",
        (f"{target_date}T00:00:00", f"{target_date}T23:59:59.999999"),
    )
    rows = cur.fetchall()

    latency_rows: dict[tuple[str, str, str], list[int]] = {}
    lcur = db.execute(
        """SELECT runtime, model, routing_path, latency_ms
           FROM llm_calls
           WHERE ts >= ? AND ts < ?""",
        (f"{target_date}T00:00:00", f"{target_date}T23:59:59.999999"),
    )
    for lrow in lcur.fetchall():
        key = (lrow[0], lrow[1], lrow[2])
        latency_rows.setdefault(key, []).append(lrow[3])

    inserted = 0
    for row in rows:
        runtime, model, routing_path = row[0], row[1], row[2]
        call_count = row[3]
        call_count_success = row[4]
        call_count_fail = row[5]
        tokens_in_total = row[6]
        tokens_out_total = row[7]
        cost_usd_total = row[8]

        p50: Optional[int] = None
        p95: Optional[int] = None
        if call_count >= 5:
            latencies = sorted(latency_rows.get((runtime, model, routing_path), []))
            if latencies:
                p50_idx = int(len(latencies) * 0.5)
                p95_idx = int(len(latencies) * 0.95)
                p50 = latencies[min(p50_idx, len(latencies) - 1)]
                p95 = latencies[min(p95_idx, len(latencies) - 1)]

        db.execute(
            """INSERT OR REPLACE INTO llm_calls_daily
               (day, runtime, model, routing_path, call_count,
                call_count_success, call_count_fail, tokens_in_total,
                tokens_out_total, cost_usd_total, latency_ms_p50, latency_ms_p95)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (target_date, runtime, model, routing_path, call_count,
             call_count_success, call_count_fail, tokens_in_total,
             tokens_out_total, cost_usd_total, p50, p95),
        )
        inserted += 1

    db.commit()
    return inserted


def query_errors(
    db: sqlite3.Connection,
    *,
    since: str,
    until: Optional[str] = None,
    runtime_role: Optional[str] = None,
    kind: Optional[str] = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM errors WHERE ts >= ?"
    params: list[Any] = [since]
    if until is not None:
        sql += " AND ts < ?"
        params.append(until)
    if runtime_role is not None:
        sql += " AND runtime = ?"
        params.append(runtime_role)
    if kind is not None:
        sql += " AND error_class = ?"
        params.append(kind)
    sql += " ORDER BY ts DESC"
    cur = db.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def query_llm_calls(
    db: sqlite3.Connection,
    *,
    since: Optional[str] = None,
    until: Optional[str] = None,
    runtime_role: Optional[str] = None,
    model: Optional[str] = None,
    routing_path: Optional[str] = None,
    status: Optional[str] = None,
    work_item_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM llm_calls WHERE 1=1"
    params: list[Any] = []
    if since is not None:
        sql += " AND ts >= ?"
        params.append(since)
    if until is not None:
        sql += " AND ts < ?"
        params.append(until)
    if runtime_role is not None:
        sql += " AND runtime = ?"
        params.append(runtime_role)
    if model is not None:
        sql += " AND model = ?"
        params.append(model)
    if routing_path is not None:
        sql += " AND routing_path = ?"
        params.append(routing_path)
    if status is not None:
        sql += " AND status = ?"
        params.append(status)
    if work_item_id is not None:
        sql += " AND work_item_id = ?"
        params.append(work_item_id)
    sql += " ORDER BY ts DESC"
    cur = db.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def query_llm_calls_daily(
    db: sqlite3.Connection,
    *,
    since: Optional[str] = None,
    until: Optional[str] = None,
    runtime_role: Optional[str] = None,
    model: Optional[str] = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM llm_calls_daily WHERE 1=1"
    params: list[Any] = []
    if since is not None:
        sql += " AND day >= ?"
        params.append(since)
    if until is not None:
        sql += " AND day < ?"
        params.append(until)
    if runtime_role is not None:
        sql += " AND runtime = ?"
        params.append(runtime_role)
    if model is not None:
        sql += " AND model = ?"
        params.append(model)
    sql += " ORDER BY day DESC, runtime, model"
    cur = db.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]
