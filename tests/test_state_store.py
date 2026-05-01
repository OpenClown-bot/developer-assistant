"""Tests for developer_assistant.state_store.

Uses stdlib ``unittest`` and ``tempfile``. All chat_key and project_key
values use sanitized placeholder strings; no real Telegram chat IDs,
user IDs, PATs, API keys, or other private identifiers appear here.
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

from developer_assistant.state_store import (
    init_schema,
    list_project_bindings,
    open_store,
    read_hermes_run,
    read_hermes_run_by_idempotency,
    read_project_binding,
    read_scheduled_progress,
    reset_store,
    upsert_hermes_run,
    upsert_project_binding,
    upsert_scheduled_progress,
)


class TestSchemaInitialization(unittest.TestCase):
    def test_init_creates_tables(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "test.db")
            conn = open_store(db_path)
            try:
                cur = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                tables = {r["name"] for r in cur.fetchall()}
                self.assertIn("project_bindings", tables)
                self.assertIn("scheduled_progress", tables)
                self.assertIn("hermes_runs", tables)
                self.assertIn("_schema_meta", tables)
            finally:
                conn.close()

    def test_init_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "test.db")
            conn = open_store(db_path)
            try:
                init_schema(conn)
                init_schema(conn)
                cur = conn.execute(
                    "SELECT value FROM _schema_meta WHERE key='schema_version'"
                )
                self.assertEqual(cur.fetchone()["value"], "1")
            finally:
                conn.close()

    def test_memory_db(self) -> None:
        conn = open_store(":memory:")
        try:
            cur = conn.execute("SELECT COUNT(*) AS n FROM project_bindings")
            self.assertEqual(cur.fetchone()["n"], 0)
        finally:
            conn.close()


class TestProjectBinding(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_upsert_and_read(self) -> None:
        upsert_project_binding(
            self.conn,
            chat_key="chat:proj-alpha",
            repo_url="https://github.com/example/proj-alpha",
            repo_owner_name="example/proj-alpha",
            workspace_path="/workspaces/proj-alpha",
            phase="implementation",
        )
        row = read_project_binding(self.conn, "chat:proj-alpha")
        self.assertIsNotNone(row)
        self.assertEqual(row["repo_url"], "https://github.com/example/proj-alpha")
        self.assertEqual(row["repo_owner_name"], "example/proj-alpha")
        self.assertEqual(row["workspace_path"], "/workspaces/proj-alpha")
        self.assertEqual(row["phase"], "implementation")
        self.assertIsNotNone(row["updated_at"])

    def test_read_missing_returns_none(self) -> None:
        self.assertIsNone(read_project_binding(self.conn, "chat:no-such"))

    def test_upsert_updates_existing(self) -> None:
        upsert_project_binding(
            self.conn,
            chat_key="chat:proj-beta",
            repo_url="https://github.com/example/proj-beta",
        )
        upsert_project_binding(
            self.conn,
            chat_key="chat:proj-beta",
            repo_url="https://github.com/example/proj-beta-v2",
            phase="review",
        )
        row = read_project_binding(self.conn, "chat:proj-beta")
        self.assertEqual(row["repo_url"], "https://github.com/example/proj-beta-v2")
        self.assertEqual(row["phase"], "review")

    def test_list_bindings(self) -> None:
        upsert_project_binding(
            self.conn, chat_key="chat:a", repo_url="https://github.com/example/a"
        )
        upsert_project_binding(
            self.conn, chat_key="chat:b", repo_url="https://github.com/example/b"
        )
        rows = list_project_bindings(self.conn)
        keys = [r["chat_key"] for r in rows]
        self.assertEqual(keys, ["chat:a", "chat:b"])


class TestScheduledProgress(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_upsert_and_read(self) -> None:
        upsert_scheduled_progress(
            self.conn,
            project_key="chat:proj-alpha",
            last_report_at="2026-05-01T10:00:00+00:00",
            next_report_at="2026-05-01T11:00:00+00:00",
            interval_minutes=60,
        )
        row = read_scheduled_progress(self.conn, "chat:proj-alpha")
        self.assertIsNotNone(row)
        self.assertEqual(row["last_report_at"], "2026-05-01T10:00:00+00:00")
        self.assertEqual(row["next_report_at"], "2026-05-01T11:00:00+00:00")
        self.assertEqual(row["interval_minutes"], 60)

    def test_read_missing_returns_none(self) -> None:
        self.assertIsNone(read_scheduled_progress(self.conn, "no-such"))

    def test_upsert_preserves_existing_on_null(self) -> None:
        upsert_scheduled_progress(
            self.conn,
            project_key="chat:proj-gamma",
            last_report_at="2026-05-01T09:00:00+00:00",
            next_report_at="2026-05-01T10:00:00+00:00",
            interval_minutes=60,
        )
        upsert_scheduled_progress(
            self.conn,
            project_key="chat:proj-gamma",
            last_report_at="2026-05-01T09:30:00+00:00",
        )
        row = read_scheduled_progress(self.conn, "chat:proj-gamma")
        self.assertEqual(row["last_report_at"], "2026-05-01T09:30:00+00:00")
        self.assertEqual(row["next_report_at"], "2026-05-01T10:00:00+00:00")
        self.assertEqual(row["interval_minutes"], 60)


class TestHermesRun(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_upsert_and_read_by_run_id(self) -> None:
        upsert_hermes_run(
            self.conn,
            run_id="run-001",
            project_key="chat:proj-alpha",
            role="executor",
            task_type="implementation",
            status="in_progress",
            idempotency_key="idem-001",
            in_flight_meta={"ticket": "TKT-007", "branch": "feat/tkt-007"},
        )
        row = read_hermes_run(self.conn, "run-001")
        self.assertIsNotNone(row)
        self.assertEqual(row["run_id"], "run-001")
        self.assertEqual(row["project_key"], "chat:proj-alpha")
        self.assertEqual(row["role"], "executor")
        self.assertEqual(row["status"], "in_progress")
        self.assertEqual(row["idempotency_key"], "idem-001")
        self.assertEqual(row["in_flight_meta"]["ticket"], "TKT-007")

    def test_read_by_idempotency_key(self) -> None:
        upsert_hermes_run(
            self.conn,
            run_id="run-002",
            project_key="chat:proj-beta",
            status="completed",
            idempotency_key="idem-002",
        )
        row = read_hermes_run_by_idempotency(self.conn, "idem-002")
        self.assertIsNotNone(row)
        self.assertEqual(row["run_id"], "run-002")

    def test_read_missing_returns_none(self) -> None:
        self.assertIsNone(read_hermes_run(self.conn, "no-run"))
        self.assertIsNone(read_hermes_run_by_idempotency(self.conn, "no-idem"))

    def test_upsert_updates_existing(self) -> None:
        upsert_hermes_run(
            self.conn,
            run_id="run-003",
            project_key="chat:proj-gamma",
            status="pending",
        )
        upsert_hermes_run(
            self.conn,
            run_id="run-003",
            project_key="chat:proj-gamma",
            status="completed",
        )
        row = read_hermes_run(self.conn, "run-003")
        self.assertEqual(row["status"], "completed")

    def test_in_flight_meta_none_when_absent(self) -> None:
        upsert_hermes_run(
            self.conn,
            run_id="run-004",
            project_key="chat:proj-delta",
            status="pending",
        )
        row = read_hermes_run(self.conn, "run-004")
        self.assertIsNone(row["in_flight_meta"])


class TestResetStore(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_reset_clears_all_data(self) -> None:
        upsert_project_binding(
            self.conn,
            chat_key="chat:proj-a",
            repo_url="https://github.com/example/a",
        )
        upsert_scheduled_progress(
            self.conn,
            project_key="chat:proj-a",
            interval_minutes=30,
        )
        upsert_hermes_run(
            self.conn,
            run_id="run-100",
            project_key="chat:proj-a",
            status="pending",
        )
        reset_store(self.conn)
        self.assertIsNone(read_project_binding(self.conn, "chat:proj-a"))
        self.assertIsNone(read_scheduled_progress(self.conn, "chat:proj-a"))
        self.assertIsNone(read_hermes_run(self.conn, "run-100"))

    def test_reset_preserves_schema(self) -> None:
        reset_store(self.conn)
        cur = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {r["name"] for r in cur.fetchall()}
        self.assertIn("project_bindings", tables)
        self.assertIn("scheduled_progress", tables)
        self.assertIn("hermes_runs", tables)

    def test_reuse_after_reset(self) -> None:
        reset_store(self.conn)
        upsert_project_binding(
            self.conn,
            chat_key="chat:proj-new",
            repo_url="https://github.com/example/new",
        )
        row = read_project_binding(self.conn, "chat:proj-new")
        self.assertIsNotNone(row)
        self.assertEqual(row["repo_url"], "https://github.com/example/new")


if __name__ == "__main__":
    unittest.main()
