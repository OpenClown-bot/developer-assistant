"""Tests for developer_assistant.progress_scheduler.

Uses stdlib ``unittest``. All ``project_key`` values use sanitized
placeholder strings such as ``chat:proj-alpha``; no real Telegram chat
IDs, user IDs, PATs, API keys, or other private identifiers appear
here.

Tests are offline-only and deterministic. No live Telegram, GitHub,
VPS, network access, credentials, external services, or
environment-specific private config is required.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "src")
)

from developer_assistant.progress_scheduler import (
    is_report_due,
    mark_report_sent,
)
from developer_assistant.state_store import (
    init_schema,
    open_store,
    upsert_project_binding,
    upsert_scheduled_progress,
)


def _open_test_db() -> sqlite3.Connection:
    conn = open_store(":memory:")
    upsert_project_binding(
        conn,
        chat_key="chat:proj-alpha",
        repo_url="https://github.com/example/proj-alpha",
    )
    upsert_project_binding(
        conn,
        chat_key="chat:proj-beta",
        repo_url="https://github.com/example/proj-beta",
    )
    return conn


class TestIsReportDue(unittest.TestCase):
    def test_due_when_no_row_exists(self) -> None:
        db = _open_test_db()
        self.assertTrue(is_report_due(db, "chat:proj-alpha", "2026-05-06T10:00:00+00:00"))

    def test_due_when_overdue(self) -> None:
        db = _open_test_db()
        upsert_scheduled_progress(
            db,
            project_key="chat:proj-alpha",
            next_report_at="2026-05-06T09:00:00+00:00",
        )
        self.assertTrue(is_report_due(db, "chat:proj-alpha", "2026-05-06T10:00:00+00:00"))

    def test_due_when_next_report_at_equals_now(self) -> None:
        db = _open_test_db()
        upsert_scheduled_progress(
            db,
            project_key="chat:proj-alpha",
            next_report_at="2026-05-06T10:00:00+00:00",
        )
        self.assertTrue(is_report_due(db, "chat:proj-alpha", "2026-05-06T10:00:00+00:00"))

    def test_not_due_when_not_yet_time(self) -> None:
        db = _open_test_db()
        upsert_scheduled_progress(
            db,
            project_key="chat:proj-alpha",
            next_report_at="2026-05-06T11:00:00+00:00",
        )
        self.assertFalse(is_report_due(db, "chat:proj-alpha", "2026-05-06T10:00:00+00:00"))

    def test_not_due_when_next_report_at_is_null(self) -> None:
        db = _open_test_db()
        upsert_scheduled_progress(
            db,
            project_key="chat:proj-alpha",
            last_report_at="2026-05-06T10:00:00+00:00",
            next_report_at=None,
        )
        self.assertFalse(is_report_due(db, "chat:proj-alpha", "2026-05-06T12:00:00+00:00"))

    def test_due_for_different_project_keys_independently(self) -> None:
        db = _open_test_db()
        upsert_scheduled_progress(
            db,
            project_key="chat:proj-alpha",
            next_report_at="2026-05-06T09:00:00+00:00",
        )
        self.assertTrue(is_report_due(db, "chat:proj-alpha", "2026-05-06T10:00:00+00:00"))
        self.assertTrue(is_report_due(db, "chat:proj-beta", "2026-05-06T10:00:00+00:00"))


class TestMarkReportSent(unittest.TestCase):
    def test_updates_last_report_at(self) -> None:
        db = _open_test_db()
        mark_report_sent(db, "chat:proj-alpha", "2026-05-06T10:00:00+00:00")
        row = db.execute(
            "SELECT last_report_at FROM scheduled_progress WHERE project_key = ?",
            ("chat:proj-alpha",),
        ).fetchone()
        self.assertEqual(row["last_report_at"], "2026-05-06T10:00:00+00:00")

    def test_computes_next_report_at_with_default_interval(self) -> None:
        db = _open_test_db()
        mark_report_sent(db, "chat:proj-alpha", "2026-05-06T10:00:00+00:00")
        row = db.execute(
            "SELECT next_report_at, interval_minutes FROM scheduled_progress WHERE project_key = ?",
            ("chat:proj-alpha",),
        ).fetchone()
        self.assertEqual(row["next_report_at"], "2026-05-06T11:00:00+00:00")
        self.assertEqual(row["interval_minutes"], 60)

    def test_computes_next_report_at_with_custom_interval(self) -> None:
        db = _open_test_db()
        upsert_scheduled_progress(
            db,
            project_key="chat:proj-alpha",
            interval_minutes=30,
        )
        mark_report_sent(db, "chat:proj-alpha", "2026-05-06T10:00:00+00:00")
        row = db.execute(
            "SELECT next_report_at, interval_minutes FROM scheduled_progress WHERE project_key = ?",
            ("chat:proj-alpha",),
        ).fetchone()
        self.assertEqual(row["next_report_at"], "2026-05-06T10:30:00+00:00")
        self.assertEqual(row["interval_minutes"], 30)

    def test_defaults_interval_to_60_when_stored_null(self) -> None:
        db = _open_test_db()
        upsert_scheduled_progress(
            db,
            project_key="chat:proj-alpha",
            last_report_at="2026-05-06T08:00:00+00:00",
        )
        mark_report_sent(db, "chat:proj-alpha", "2026-05-06T10:00:00+00:00")
        row = db.execute(
            "SELECT next_report_at, interval_minutes FROM scheduled_progress WHERE project_key = ?",
            ("chat:proj-alpha",),
        ).fetchone()
        self.assertEqual(row["next_report_at"], "2026-05-06T11:00:00+00:00")
        self.assertEqual(row["interval_minutes"], 60)

    def test_round_trip_mark_then_check_due(self) -> None:
        db = _open_test_db()
        mark_report_sent(db, "chat:proj-alpha", "2026-05-06T10:00:00+00:00")
        self.assertFalse(is_report_due(db, "chat:proj-alpha", "2026-05-06T10:30:00+00:00"))
        self.assertTrue(is_report_due(db, "chat:proj-alpha", "2026-05-06T11:00:00+00:00"))

    def test_no_project_binding_does_not_crash_is_report_due(self) -> None:
        db = _open_test_db()
        result = is_report_due(db, "chat:nonexistent", "2026-05-06T10:00:00+00:00")
        self.assertTrue(result)

    def test_no_project_binding_does_not_crash_mark_report_sent(self) -> None:
        db = _open_test_db()
        from developer_assistant.state_store import upsert_project_binding
        upsert_project_binding(
            db,
            chat_key="chat:proj-gamma",
            repo_url="https://github.com/example/proj-gamma",
        )
        mark_report_sent(db, "chat:proj-gamma", "2026-05-06T10:00:00+00:00")
        row = db.execute(
            "SELECT last_report_at FROM scheduled_progress WHERE project_key = ?",
            ("chat:proj-gamma",),
        ).fetchone()
        self.assertEqual(row["last_report_at"], "2026-05-06T10:00:00+00:00")

    def test_repeated_mark_report_sent_advances_next_report_at(self) -> None:
        db = _open_test_db()
        mark_report_sent(db, "chat:proj-alpha", "2026-05-06T10:00:00+00:00")
        mark_report_sent(db, "chat:proj-alpha", "2026-05-06T11:00:00+00:00")
        row = db.execute(
            "SELECT last_report_at, next_report_at FROM scheduled_progress WHERE project_key = ?",
            ("chat:proj-alpha",),
        ).fetchone()
        self.assertEqual(row["last_report_at"], "2026-05-06T11:00:00+00:00")
        self.assertEqual(row["next_report_at"], "2026-05-06T12:00:00+00:00")

    def test_utc_timestamp_comparison(self) -> None:
        db = _open_test_db()
        mark_report_sent(db, "chat:proj-alpha", "2026-05-06T10:00:00+00:00")
        self.assertFalse(is_report_due(db, "chat:proj-alpha", "2026-05-06T10:59:59+00:00"))
        self.assertTrue(is_report_due(db, "chat:proj-alpha", "2026-05-06T11:00:00+00:00"))


if __name__ == "__main__":
    unittest.main()
