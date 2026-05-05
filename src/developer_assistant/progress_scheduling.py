"""Progress report scheduling persistence helpers.

Pure functions that determine whether a progress report is due and record
that a report was sent, using the existing ``scheduled_progress`` table in
the SQLite operational state store.

These are offline, deterministic helpers with no live Telegram, GitHub,
VPS, or external-service wiring.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from developer_assistant.state_store import (
    read_scheduled_progress,
    upsert_scheduled_progress,
)


def is_report_due(
    db: object,
    project_key: str,
    now_iso: str,
) -> bool:
    """Return True when a progress report is due for *project_key*.

    A report is due when:
    - No ``scheduled_progress`` row exists for *project_key*
      (first report is always due), OR
    - ``next_report_at`` is not NULL and *now_iso* >= ``next_report_at``.

    Returns False when ``next_report_at`` is NULL or when
    *now_iso* < ``next_report_at``.
    """
    row = read_scheduled_progress(db, project_key)
    if row is None:
        return True
    next_at = row["next_report_at"]
    if next_at is None:
        return False
    return now_iso >= next_at


def mark_report_sent(
    db: object,
    project_key: str,
    now_iso: str,
) -> None:
    """Record that a progress report was sent for *project_key*.

    - Sets ``last_report_at`` to *now_iso*.
    - Computes ``next_report_at`` as *now_iso* + ``interval_minutes``.
    - If ``interval_minutes`` is NULL in the stored row (or no row exists),
      defaults to 60 minutes per ARCH-001 Section 7.
    - INSERTs a new row when no scheduled_progress row exists for
      *project_key*.
    """
    row = read_scheduled_progress(db, project_key)

    if row is not None and row["interval_minutes"] is not None:
        interval = row["interval_minutes"]
    else:
        interval = 60

    dt = datetime.fromisoformat(now_iso)
    next_dt = dt + timedelta(minutes=interval)
    next_report_at = next_dt.isoformat()

    upsert_scheduled_progress(
        db,
        project_key=project_key,
        last_report_at=now_iso,
        next_report_at=next_report_at,
        interval_minutes=interval,
    )