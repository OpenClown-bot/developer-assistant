"""Escalation helpers for operational state store.

Implements pending Founder-facing prompts per
MULTI-HERMES-CONTRACT.md § 6.3, ESCALATION-POLICY.md § 6,
and OPERATIONAL-STATE-STORE.md v0.2.1 § 3.6.

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


def write_escalation(
    conn: sqlite3.Connection,
    *,
    originating_runtime: str,
    originating_work_item_id: Optional[int] = None,
    trigger_kind: str,
    context: str,
    proposed_action: str,
    options: list[str],
    recommended_default: str,
    impact: str,
    urgency: str,
    durable_artifact_target: str,
) -> int:
    """Insert a new pending escalation.

    Returns the new row id.
    """
    now = _now_iso()
    options_json = json.dumps(options)
    cur = conn.execute(
        """INSERT INTO escalations
               (created_at, updated_at, originating_runtime, originating_work_item_id,
                trigger_kind, context, proposed_action, options_json,
                recommended_default, impact, urgency, durable_artifact_target, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
        (now, now, originating_runtime, originating_work_item_id,
         trigger_kind, context, proposed_action, options_json,
         recommended_default, impact, urgency, durable_artifact_target),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def read_pending_escalations(
    conn: sqlite3.Connection,
    statuses: Optional[list[str]] = None,
    limit: int = 10,
) -> list[Mapping[str, Any]]:
    """Return escalations in pending/surfaced state, ordered by urgency then id.

    Surfaced escalations are subject to a 5-minute re-surface cooldown:
    items surfaced less than 5 minutes ago are excluded so the Founder
    is not re-prompted immediately.
    """
    if statuses is None:
        statuses = ["pending", "surfaced"]
    placeholders = ",".join("?" * len(statuses))
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    cur = conn.execute(
        f"""SELECT * FROM escalations
            WHERE status IN ({placeholders})
              AND (surfaced_at IS NULL OR surfaced_at < ?)
            ORDER BY
                CASE urgency
                    WHEN 'high'   THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low'    THEN 3
                END,
                id
            LIMIT ?""",
        statuses + [cutoff, limit],
    )
    return [dict(r) for r in cur.fetchall()]


def mark_escalation_surfaced(
    conn: sqlite3.Connection,
    *,
    escalation_id: int,
    telegram_message_id: Optional[str] = None,
) -> Optional[Mapping[str, Any]]:
    """Mark an escalation as surfaced and record the Telegram message id.

    Returns the updated row dict, or None if not found.
    """
    now = _now_iso()
    cur = conn.execute(
        """UPDATE escalations
           SET status = 'surfaced',
               surfaced_at = ?,
               telegram_message_id = COALESCE(?, telegram_message_id),
               updated_at = ?
           WHERE id = ? AND status = 'pending'
           RETURNING *""",
        (now, telegram_message_id, now, escalation_id),
    )
    row = cur.fetchone()
    conn.commit()
    if row is None:
        return None
    return dict(row)


def resolve_escalation(
    conn: sqlite3.Connection,
    *,
    escalation_id: int,
    verdict: str,
    founder_response: str,
) -> Optional[Mapping[str, Any]]:
    """Resolve an escalation as approved or denied.

    Returns the updated row dict, or None if not found.
    """
    if verdict not in ("approved", "denied"):
        raise ValueError(f"verdict must be 'approved' or 'denied', got {verdict!r}")
    now = _now_iso()
    cur = conn.execute(
        """UPDATE escalations
           SET status = ?,
               resolved_at = ?,
               founder_response = ?,
               updated_at = ?
           WHERE id = ? AND status IN ('pending', 'surfaced')
           RETURNING *""",
        (verdict, now, founder_response, now, escalation_id),
    )
    row = cur.fetchone()
    conn.commit()
    if row is None:
        return None
    return dict(row)


def expire_old_escalations(
    conn: sqlite3.Connection,
    max_age_days: int = 7,
) -> int:
    """Expire escalations older than max_age_days that remain pending or surfaced.

    Returns the count of expired rows.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
    cur = conn.execute(
        """UPDATE escalations
           SET status = 'expired',
               updated_at = ?
           WHERE status IN ('pending', 'surfaced') AND created_at < ?
           RETURNING id""",
        (_now_iso(), cutoff),
    )
    rows = cur.fetchall()
    conn.commit()
    return len(rows)
