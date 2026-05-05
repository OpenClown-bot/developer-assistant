"""Tests for developer_assistant.progress_scheduling.

Offline tests using in-memory SQLite databases.
All ``project_key`` / ``chat_key`` values are sanitized labels.
No live Telegram, GitHub, VPS, or external-service access.
"""

from __future__ import annotations

import sqlite3
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.progress_scheduling import (
    is_report_due,
    mark_report_sent,
)
from developer_assistant.state_store import (
    open_store,
    read_scheduled_progress,
    reset_store,
    upsert_project_binding,
)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


_PROJECT_KEY = "chat:proj-alpha"


class IsReportDueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = open_store(":memory:")
        upsert_project_binding(
            self.conn,
            chat_key=_PROJECT_KEY,
            repo_url="https://github.com/example/proj-alpha",
        )

    def tearDown(self) -> None:
        self.conn.close()

    def test_true_when_no_row_exists_first_report_due(self) -> None:
        self.assertTrue(is_report_due(self.conn, _PROJECT_KEY, "2026-05-01T10:00:00+00:00"))

    def test_true_when_now_iso_gte_next_report_at(self) -> None:
        now = datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc)
        next_at = now + timedelta(minutes=30)
        self.conn.execute(
            "INSERT INTO scheduled_progress (project_key, last_report_at, next_report_at, interval_minutes, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (_PROJECT_KEY, _iso(now), _iso(next_at), 30, _iso(now)),
        )
        self.conn.commit()

        self.assertTrue(is_report_due(self.conn, _PROJECT_KEY, _iso(next_at)))

    def test_false_when_now_iso_lt_next_report_at(self) -> None:
        now = datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc)
        next_at = now + timedelta(minutes=30)
        self.conn.execute(
            "INSERT INTO scheduled_progress (project_key, last_report_at, next_report_at, interval_minutes, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (_PROJECT_KEY, _iso(now), _iso(next_at), 30, _iso(now)),
        )
        self.conn.commit()

        just_before = next_at - timedelta(seconds=1)
        self.assertFalse(is_report_due(self.conn, _PROJECT_KEY, _iso(just_before)))

    def test_false_when_next_report_at_is_null(self) -> None:
        now = datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc)
        self.conn.execute(
            "INSERT INTO scheduled_progress (project_key, last_report_at, next_report_at, interval_minutes, updated_at) "
            "VALUES (?, ?, NULL, ?, ?)",
            (_PROJECT_KEY, _iso(now), 30, _iso(now)),
        )
        self.conn.commit()

        self.assertFalse(is_report_due(self.conn, _PROJECT_KEY, _iso(now)))


class MarkReportSentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = open_store(":memory:")
        upsert_project_binding(
            self.conn,
            chat_key=_PROJECT_KEY,
            repo_url="https://github.com/example/proj-alpha",
        )

    def tearDown(self) -> None:
        self.conn.close()

    def test_inserts_new_row_when_no_row_exists(self) -> None:
        now = _iso(datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc))
        mark_report_sent(self.conn, _PROJECT_KEY, now)

        row = read_scheduled_progress(self.conn, _PROJECT_KEY)
        self.assertIsNotNone(row)
        self.assertEqual(row["last_report_at"], now)
        self.assertEqual(row["interval_minutes"], 60)

    def test_updates_last_report_at_and_computes_next_report_at(self) -> None:
        now_dt = datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = _iso(now_dt)
        expected_next = _iso(now_dt + timedelta(minutes=30))

        self.conn.execute(
            "INSERT INTO scheduled_progress (project_key, last_report_at, next_report_at, interval_minutes, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (_PROJECT_KEY, _iso(now_dt - timedelta(minutes=30)), _iso(now_dt), 30, _iso(now_dt)),
        )
        self.conn.commit()

        mark_report_sent(self.conn, _PROJECT_KEY, now)

        row = read_scheduled_progress(self.conn, _PROJECT_KEY)
        self.assertEqual(row["last_report_at"], now)
        self.assertEqual(row["next_report_at"], expected_next)
        self.assertEqual(row["interval_minutes"], 30)

    def test_default_60_minutes_when_interval_minutes_is_null(self) -> None:
        now_dt = datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = _iso(now_dt)
        expected_next = _iso(now_dt + timedelta(minutes=60))

        self.conn.execute(
            "INSERT INTO scheduled_progress (project_key, last_report_at, next_report_at, interval_minutes, updated_at) "
            "VALUES (?, ?, ?, NULL, ?)",
            (_PROJECT_KEY, _iso(now_dt - timedelta(minutes=60)), _iso(now_dt), _iso(now_dt)),
        )
        self.conn.commit()

        mark_report_sent(self.conn, _PROJECT_KEY, now)

        row = read_scheduled_progress(self.conn, _PROJECT_KEY)
        self.assertEqual(row["last_report_at"], now)
        self.assertEqual(row["next_report_at"], expected_next)
        self.assertEqual(row["interval_minutes"], 60)

    def test_uses_stored_interval_minutes_when_present(self) -> None:
        now_dt = datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = _iso(now_dt)
        expected_next = _iso(now_dt + timedelta(minutes=45))

        self.conn.execute(
            "INSERT INTO scheduled_progress (project_key, last_report_at, next_report_at, interval_minutes, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (_PROJECT_KEY, _iso(now_dt - timedelta(minutes=45)), _iso(now_dt), 45, _iso(now_dt)),
        )
        self.conn.commit()

        mark_report_sent(self.conn, _PROJECT_KEY, now)

        row = read_scheduled_progress(self.conn, _PROJECT_KEY)
        self.assertEqual(row["interval_minutes"], 45)
        self.assertEqual(row["next_report_at"], expected_next)

    def test_default_60_minutes_on_insert_when_no_row_exists(self) -> None:
        now_dt = datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = _iso(now_dt)
        expected_next = _iso(now_dt + timedelta(minutes=60))

        mark_report_sent(self.conn, _PROJECT_KEY, now)

        row = read_scheduled_progress(self.conn, _PROJECT_KEY)
        self.assertEqual(row["interval_minutes"], 60)
        self.assertEqual(row["next_report_at"], expected_next)

    def test_equal_timestamp_means_due(self) -> None:
        now_dt = datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = _iso(now_dt)

        self.conn.execute(
            "INSERT INTO scheduled_progress (project_key, last_report_at, next_report_at, interval_minutes, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (_PROJECT_KEY, _iso(now_dt - timedelta(minutes=30)), now, 30, _iso(now_dt)),
        )
        self.conn.commit()

        self.assertTrue(is_report_due(self.conn, _PROJECT_KEY, now))


if __name__ == "__main__":
    unittest.main()