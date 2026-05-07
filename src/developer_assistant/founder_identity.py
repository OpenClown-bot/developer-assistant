"""Founder identity binding helpers for operational state store.

Implements upstream identity mapping per
UPSTREAM-ADAPTER-CONTRACT.md § 4.4.

All functions take a sqlite3.Connection.
All timestamps in UTC.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Mapping, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def bind_founder_identity(
    conn: sqlite3.Connection,
    *,
    founder_id: str,
    adapter_id: str,
    upstream_user_id: str,
    display_name: Optional[str] = None,
) -> int:
    """Insert a new founder identity binding, or do nothing if one exists.

    Returns the row id.
    """
    now = _now_iso()
    cur = conn.execute(
        """INSERT OR IGNORE INTO founder_identity_bindings
               (created_at, founder_id, adapter_id, upstream_user_id, display_name, bound_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (now, founder_id, adapter_id, upstream_user_id, display_name, now),
    )
    conn.commit()
    if cur.lastrowid is not None and cur.lastrowid != 0:
        return cur.lastrowid  # type: ignore[return-value]
    cur2 = conn.execute(
        "SELECT id FROM founder_identity_bindings "
        "WHERE adapter_id = ? AND upstream_user_id = ?",
        (adapter_id, upstream_user_id),
    )
    row = cur2.fetchone()
    return row["id"]  # type: ignore[return-value]


def lookup_founder_by_upstream_identity(
    conn: sqlite3.Connection,
    *,
    adapter_id: str,
    upstream_user_id: str,
) -> Optional[str]:
    """Look up the founder_id for a given adapter + upstream identity.

    Returns the founder_id string, or None if not found or revoked.
    """
    cur = conn.execute(
        "SELECT founder_id FROM founder_identity_bindings "
        "WHERE adapter_id = ? AND upstream_user_id = ? AND revoked_at IS NULL",
        (adapter_id, upstream_user_id),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return row["founder_id"]


def revoke_founder_binding(
    conn: sqlite3.Connection,
    *,
    adapter_id: str,
    upstream_user_id: str,
) -> bool:
    """Revoke a founder identity binding by setting revoked_at.

    Returns True if a row was revoked, False if no active binding existed.
    """
    now = _now_iso()
    cur = conn.execute(
        """UPDATE founder_identity_bindings
           SET revoked_at = ?
           WHERE adapter_id = ? AND upstream_user_id = ? AND revoked_at IS NULL
           RETURNING id""",
        (now, adapter_id, upstream_user_id),
    )
    rows = cur.fetchall()
    conn.commit()
    return len(rows) > 0


def list_founder_bindings(
    conn: sqlite3.Connection,
    founder_id: Optional[str] = None,
) -> list[Mapping[str, Any]]:
    """List all (or filtered) founder identity bindings."""
    if founder_id is None:
        cur = conn.execute("SELECT * FROM founder_identity_bindings ORDER BY bound_at DESC")
    else:
        cur = conn.execute(
            "SELECT * FROM founder_identity_bindings WHERE founder_id = ? ORDER BY bound_at DESC",
            (founder_id,),
        )
    return [dict(r) for r in cur.fetchall()]
