"""Work-queue helpers for operational state store.

Implements the inter-runtime IPC primitive per
MULTI-HERMES-CONTRACT.md § 6.2 and OPERATIONAL-STATE-STORE.md v0.2.1 § 3.5.

All functions take a sqlite3.Connection.
All timestamps in UTC.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_lease_until() -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()


def write_work_item(
    conn: sqlite3.Connection,
    *,
    target_role: str,
    kind: str,
    payload: dict[str, Any],
    priority: int = 50,
    dedup_key: Optional[str] = None,
    max_attempts: int = 3,
    originating_run_id: Optional[str] = None,
) -> int:
    """Insert a new pending work item.

    If dedup_key is provided and a row already exists with the same dedup_key
    in status pending/claimed/failed, returns -1 without inserting.

    Returns the new row id.
    """
    if dedup_key:
        cur = conn.execute(
            "SELECT id FROM work_items "
            "WHERE dedup_key = ? AND status IN ('pending','claimed','failed')",
            (dedup_key,),
        )
        existing = cur.fetchone()
        if existing is not None:
            return -1

    payload_json = json.dumps(payload)
    now = _now_iso()
    cur = conn.execute(
        """INSERT INTO work_items
               (created_at, updated_at, target_role, kind, dedup_key, payload_json,
                priority, status, attempt_count, max_attempts, originating_run_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?)""",
        (now, now, target_role, kind, dedup_key, payload_json,
         priority, max_attempts, originating_run_id),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def claim_work_item(
    conn: sqlite3.Connection,
    *,
    runtime_id: str,
    target_role: str,
) -> Optional[Mapping[str, Any]]:
    """Atomically claim the highest-priority pending item for target_role.

    Updates status to 'claimed', sets claimed_by_runtime, claimed_at, and a
    30-minute rolling lease. Returns the row dict, or None if nothing is
    pending.

    Idempotent: if the runtime already holds the lease, returns the row
    without error.
    """
    now = _now_iso()
    lease_until = _default_lease_until()
    cur = conn.execute(
        """UPDATE work_items
           SET status = 'claimed',
               claimed_by_runtime = ?,
               claimed_at = ?,
               claim_lease_until = ?,
               updated_at = ?
           WHERE id = (
               SELECT id FROM work_items
               WHERE target_role = ? AND status = 'pending'
               ORDER BY priority, id LIMIT 1
           )
           RETURNING *""",
        (runtime_id, now, lease_until, now, target_role),
    )
    row = cur.fetchone()
    conn.commit()
    if row is None:
        return None
    return dict(row)


def complete_work_item(
    conn: sqlite3.Connection,
    *,
    item_id: int,
    result: dict[str, Any],
) -> Optional[Mapping[str, Any]]:
    """Mark a claimed work item as completed with a result dict.

    Returns the updated row dict, or None if the row was not found or not
    currently claimed.
    """
    now = _now_iso()
    result_json = json.dumps(result)
    cur = conn.execute(
        """UPDATE work_items
           SET status = 'completed',
               completed_at = ?,
               result_json = ?,
               claim_lease_until = NULL,
               updated_at = ?
           WHERE id = ? AND status = 'claimed'
           RETURNING *""",
        (now, result_json, now, item_id),
    )
    row = cur.fetchone()
    conn.commit()
    if row is None:
        return None
    return dict(row)


def release_work_item(
    conn: sqlite3.Connection,
    *,
    item_id: int,
) -> Optional[Mapping[str, Any]]:
    """Release a claimed work item back to pending state.

    Returns the updated row dict, or None if the row was not found.
    """
    now = _now_iso()
    cur = conn.execute(
        """UPDATE work_items
           SET status = 'pending',
               claimed_by_runtime = NULL,
               claimed_at = NULL,
               claim_lease_until = NULL,
               updated_at = ?
           WHERE id = ?
           RETURNING *""",
        (now, item_id),
    )
    row = cur.fetchone()
    conn.commit()
    if row is None:
        return None
    return dict(row)


def read_work_items_by_role(
    conn: sqlite3.Connection,
    target_role: str,
    statuses: Optional[list[str]] = None,
) -> list[Mapping[str, Any]]:
    """Return all work items for target_role, optionally filtered by statuses."""
    if statuses is None:
        statuses = ["pending", "claimed", "completed", "failed", "released"]
    placeholders = ",".join("?" * len(statuses))
    cur = conn.execute(
        f"""SELECT * FROM work_items
            WHERE target_role = ? AND status IN ({placeholders})
            ORDER BY priority, id""",
        [target_role] + statuses,
    )
    return [dict(r) for r in cur.fetchall()]


def reclaim_expired_leases(conn: sqlite3.Connection) -> int:
    """Reset all claimed items whose lease has expired back to pending.

    Returns the count of reclaimed items.
    """
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        """UPDATE work_items
           SET status = 'pending',
               claimed_by_runtime = NULL,
               claimed_at = NULL,
               claim_lease_until = NULL,
               updated_at = ?
           WHERE status = 'claimed' AND claim_lease_until < ?
           RETURNING id""",
        (now, now),
    )
    rows = cur.fetchall()
    conn.commit()
    return len(rows)