"""Progress report scheduling persistence helper.

Determines whether a progress report is due and records that a report
was sent, using the existing ``scheduled_progress`` table in the
SQLite operational state store.

This module consumes ``read_scheduled_progress`` and
``upsert_scheduled_progress`` from ``state_store``; it does not
execute raw SQL or modify ``state_store.py``.

All ``project_key`` values must follow the sanitized convention
(e.g. ``chat:proj-alpha``). No secrets, raw Telegram identifiers,
or credential values appear in this module.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from developer_assistant.state_store import (
    read_scheduled_progress,
    upsert_scheduled_progress,
)

_DEFAULT_INTERVAL_MINUTES = 60


def is_report_due(db, project_key: str, now_iso: str) -> bool:
    """Return ``True`` when a progress report is due for *project_key*.

    A report is due when:

    - No ``scheduled_progress`` row exists yet (first report is due), or
    - ``next_report_at`` is not null and ``now_iso >= next_report_at``.

    Returns ``False`` when the row exists but ``next_report_at`` is null
    or ``now_iso < next_report_at``.
    """
    row = read_scheduled_progress(db, project_key)
    if row is None:
        return True
    next_report_at: Optional[str] = row.get("next_report_at")
    if next_report_at is None:
        return False
    return now_iso >= next_report_at


def mark_report_sent(db, project_key: str, now_iso: str) -> None:
    """Record that a progress report was sent for *project_key*.

    Sets ``last_report_at`` to *now_iso* and computes
    ``next_report_at`` as *now_iso* + ``interval_minutes``.
    If the stored ``interval_minutes`` is null, the default of 60
    minutes per ARCH-001 Section 7 is used.
    """
    row = read_scheduled_progress(db, project_key)
    interval: int = _DEFAULT_INTERVAL_MINUTES
    if row is not None and row.get("interval_minutes") is not None:
        interval = row["interval_minutes"]

    now_dt = datetime.fromisoformat(now_iso)
    next_dt = now_dt + timedelta(minutes=interval)
    next_report_at = next_dt.isoformat()

    upsert_scheduled_progress(
        db,
        project_key=project_key,
        last_report_at=now_iso,
        next_report_at=next_report_at,
        interval_minutes=interval,
    )
