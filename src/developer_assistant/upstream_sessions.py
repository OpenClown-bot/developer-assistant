"""Upstream session helpers for operational state store.

Implements per-adapter session continuity per
UPSTREAM-ADAPTER-CONTRACT.md § 4.5.

All functions take a sqlite3.Connection.
All timestamps in UTC.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Mapping, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_or_create_session(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    adapter_id: str,
    founder_id: str,
    upstream_chat_id: str,
) -> Mapping[str, Any]:
    """Return existing session row or insert a new one.

    Always-on UPSERT: updates last_message_at to now on existing row
    (touch to keep session alive).
    """
    now = _now_iso()
    cur = conn.execute(
        """INSERT INTO upstream_sessions
               (session_id, adapter_id, founder_id, upstream_chat_id, created_at, last_message_at, paused)
           VALUES (?, ?, ?, ?, ?, ?, 0)
           ON CONFLICT(session_id) DO UPDATE SET
               last_message_at = excluded.last_message_at,
               upstream_chat_id = excluded.upstream_chat_id
           RETURNING *""",
        (session_id, adapter_id, founder_id, upstream_chat_id, now, now),
    )
    row = cur.fetchone()
    conn.commit()
    return dict(row)


def update_session_last_message(
    conn: sqlite3.Connection,
    *,
    session_id: str,
) -> Optional[Mapping[str, Any]]:
    """Touch last_message_at on an existing session.

    Returns the updated row, or None if session not found.
    """
    now = _now_iso()
    cur = conn.execute(
        """UPDATE upstream_sessions
           SET last_message_at = ?
           WHERE session_id = ?
           RETURNING *""",
        (now, session_id),
    )
    row = cur.fetchone()
    conn.commit()
    if row is None:
        return None
    return dict(row)


def set_session_paused(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    paused: bool,
) -> Optional[Mapping[str, Any]]:
    """Set the paused flag on a session.

    Returns the updated row, or None if session not found.
    """
    cur = conn.execute(
        """UPDATE upstream_sessions
           SET paused = ?
           WHERE session_id = ?
           RETURNING *""",
        (1 if paused else 0, session_id),
    )
    row = cur.fetchone()
    conn.commit()
    if row is None:
        return None
    return dict(row)


def set_session_current_project(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    project_id: Optional[int],
) -> Optional[Mapping[str, Any]]:
    """Set the current project binding on a session.

    Pass project_id=None to clear.
    Returns the updated row, or None if session not found.
    """
    cur = conn.execute(
        """UPDATE upstream_sessions
           SET current_project_id = ?
           WHERE session_id = ?
           RETURNING *""",
        (project_id, session_id),
    )
    row = cur.fetchone()
    conn.commit()
    if row is None:
        return None
    return dict(row)


def read_session(
    conn: sqlite3.Connection,
    session_id: str,
) -> Optional[Mapping[str, Any]]:
    """Read a session by session_id."""
    cur = conn.execute(
        "SELECT * FROM upstream_sessions WHERE session_id = ?",
        (session_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return dict(row)


def list_sessions(
    conn: sqlite3.Connection,
    founder_id: Optional[str] = None,
    paused: Optional[bool] = None,
) -> list[Mapping[str, Any]]:
    """List sessions, optionally filtered by founder_id and/or paused status."""
    conditions = []
    params: list[Any] = []
    if founder_id is not None:
        conditions.append("founder_id = ?")
        params.append(founder_id)
    if paused is not None:
        conditions.append("paused = ?")
        params.append(1 if paused else 0)
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    cur = conn.execute(
        f"SELECT * FROM upstream_sessions WHERE {where_clause} ORDER BY last_message_at DESC",
        params,
    )
    return [dict(r) for r in cur.fetchall()]