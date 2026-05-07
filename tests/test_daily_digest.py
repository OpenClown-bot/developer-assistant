"""Tests for developer_assistant.observability.daily_digest.

Covers: empty-window digest, populated-window digest, section ordering,
filename determinism, idempotent write, delivery failure, graceful
degradation when tables are absent.

All offline: fixture DB, fake Telegram client. No real network or keys.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.observability.daily_digest import (
    DigestDeliveryError,
    deliver_digest_via_telegram,
    render_digest,
    write_digest,
)
from developer_assistant.observability.telegram_utils import paginate_text


def _build_populated_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    _init_schema(conn)
    _seed_work_items(conn)
    _seed_escalations(conn)
    _seed_errors(conn)
    _seed_llm_calls(conn)

    conn.commit()
    conn.close()


def _build_empty_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    _init_schema(conn)
    conn.commit()
    conn.close()


def _build_partial_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS _schema_meta (
        key TEXT PRIMARY KEY, value TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS work_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL,
        target_role TEXT NOT NULL,
        kind TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        priority INTEGER NOT NULL DEFAULT 50,
        status TEXT NOT NULL,
        claimed_by_runtime TEXT,
        claimed_at TEXT,
        claim_lease_until TEXT,
        completed_at TEXT,
        result_json TEXT,
        attempt_count INTEGER NOT NULL DEFAULT 0,
        max_attempts INTEGER NOT NULL DEFAULT 3,
        originating_run_id TEXT
    )""")
    conn.commit()
    conn.close()


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS _schema_meta (
        key TEXT PRIMARY KEY, value TEXT NOT NULL
    )""")

    conn.execute("""CREATE TABLE IF NOT EXISTS work_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL,
        target_role TEXT NOT NULL,
        kind TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        priority INTEGER NOT NULL DEFAULT 50,
        status TEXT NOT NULL,
        claimed_by_runtime TEXT,
        claimed_at TEXT,
        claim_lease_until TEXT,
        completed_at TEXT,
        result_json TEXT,
        attempt_count INTEGER NOT NULL DEFAULT 0,
        max_attempts INTEGER NOT NULL DEFAULT 3,
        originating_run_id TEXT
    )""")

    conn.execute("""CREATE TABLE IF NOT EXISTS escalations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        originating_runtime TEXT NOT NULL,
        originating_work_item_id INTEGER,
        trigger_kind TEXT NOT NULL,
        context TEXT NOT NULL,
        proposed_action TEXT NOT NULL,
        options_json TEXT NOT NULL,
        recommended_default TEXT NOT NULL,
        impact TEXT NOT NULL,
        urgency TEXT NOT NULL,
        durable_artifact_target TEXT NOT NULL,
        status TEXT NOT NULL,
        surfaced_at TEXT,
        resolved_at TEXT,
        founder_response TEXT,
        telegram_message_id TEXT
    )""")

    conn.execute("""CREATE TABLE IF NOT EXISTS errors (
        err_id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        runtime TEXT NOT NULL,
        work_item_id TEXT,
        error_class TEXT NOT NULL,
        message TEXT NOT NULL,
        context_json TEXT NOT NULL DEFAULT '{}'
    )""")

    conn.execute("""CREATE TABLE IF NOT EXISTS llm_calls (
        call_id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        runtime TEXT NOT NULL,
        work_item_id TEXT,
        model TEXT NOT NULL,
        routing_path TEXT NOT NULL,
        tokens_in INTEGER NOT NULL,
        tokens_out INTEGER NOT NULL,
        latency_ms INTEGER NOT NULL,
        rate_in_per_1m_usd REAL NOT NULL,
        rate_out_per_1m_usd REAL NOT NULL,
        cost_usd REAL NOT NULL,
        status TEXT NOT NULL,
        error_class TEXT
    )""")

    conn.execute("""INSERT OR REPLACE INTO _schema_meta (key, value) VALUES ('schema_version', '3')""")


def _hours_ago(h: float) -> str:
    dt = datetime.now(timezone.utc) - timedelta(hours=h)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _seed_work_items(conn: sqlite3.Connection) -> None:
    now = _hours_ago(0)
    window_start = (datetime.now(timezone.utc) - timedelta(hours=25)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    conn.execute("""INSERT INTO work_items
        (created_at, updated_at, target_role, kind, payload_json, priority, status, completed_at)
        VALUES (?, ?, 'executor', 'ticket_implementation', '{}', 50, 'completed', ?)""",
        (window_start, now, now))
    conn.execute("""INSERT INTO work_items
        (created_at, updated_at, target_role, kind, payload_json, priority, status, completed_at)
        VALUES (?, ?, 'architect', 'architect_pass', '{}', 50, 'completed', ?)""",
        (window_start, now, now))


def _seed_escalations(conn: sqlite3.Connection) -> None:
    ts = _hours_ago(12)
    conn.execute("""INSERT INTO escalations
        (created_at, updated_at, originating_runtime, originating_work_item_id,
         trigger_kind, context, proposed_action, options_json, recommended_default,
         impact, urgency, durable_artifact_target, status)
        VALUES (?, ?, 'executor', 1, 'cost_rule', 'budget exceeded',
                'Halt execution', '["approve","deny"]', 'deny',
                'Cost', 'high', 'docs/adr/adr-011.md', 'pending')""",
        (ts, ts))


def _seed_errors(conn: sqlite3.Connection) -> None:
    conn.execute("""INSERT INTO errors
        (err_id, ts, runtime, work_item_id, error_class, message, context_json)
        VALUES (?, ?, 'executor', '1', 'LLMTimeout', 'Timeout calling model', '{}')""",
        ("err_digest_001", _hours_ago(6)))
    conn.execute("""INSERT INTO errors
        (err_id, ts, runtime, work_item_id, error_class, message, context_json)
        VALUES (?, ?, 'architect', '2', 'NetworkError', 'Connection reset', '{}')""",
        ("err_digest_002", _hours_ago(3)))


def _seed_llm_calls(conn: sqlite3.Connection) -> None:
    ts = _hours_ago(4)
    conn.execute("""INSERT INTO llm_calls
        (call_id, ts, runtime, work_item_id, model, routing_path,
         tokens_in, tokens_out, latency_ms, rate_in_per_1m_usd, rate_out_per_1m_usd,
         cost_usd, status)
        VALUES (?, ?, 'executor', '1', 'deepseek-v4-pro', 'omniroute_endpoint',
         5000, 2000, 500, 0.5, 1.5, 0.15, 'success')""",
        ("call_digest_001", ts))
    conn.execute("""INSERT INTO llm_calls
        (call_id, ts, runtime, work_item_id, model, routing_path,
         tokens_in, tokens_out, latency_ms, rate_in_per_1m_usd, rate_out_per_1m_usd,
         cost_usd, status)
        VALUES (?, ?, 'reviewer', '2', 'kimi-k2.6', 'openrouter_endpoint',
         2000, 800, 300, 0.3, 1.0, 0.08, 'success')""",
        ("call_digest_002", ts))


class _FakeTelegramClient:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_message(self, chat_key: str, text: str) -> None:
        self.sent.append((chat_key, text))


class _FailingTelegramClient:
    def send_message(self, chat_key: str, text: str) -> None:
        raise RuntimeError("Telegram API error: 429 Too Many Requests")


class TestRenderDigestEmptyWindow(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "operational.db")
        _build_empty_db(self.db_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("developer_assistant.observability.daily_digest._count_runtimes_up_down", return_value=(0, 5))
    def test_empty_window_renders_no_crash(self, mock_count):
        window_start = datetime.now(timezone.utc) - timedelta(hours=24)
        window_end = datetime.now(timezone.utc)
        result = render_digest(window_start, window_end, db_path=self.db_path)
        self.assertIn("Daily Digest", result)
        self.assertIn("No data available", result)

    @patch("developer_assistant.observability.daily_digest._count_runtimes_up_down", return_value=(0, 5))
    def test_empty_window_has_all_sections(self, mock_count):
        window_start = datetime.now(timezone.utc) - timedelta(hours=24)
        window_end = datetime.now(timezone.utc)
        result = render_digest(window_start, window_end, db_path=self.db_path)
        self.assertIn("Work Items Completed", result)
        self.assertIn("Errors", result)
        self.assertIn("Escalations", result)
        self.assertIn("LLM Cost", result)


class TestRenderDigestPopulatedWindow(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "operational.db")
        _build_populated_db(self.db_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("developer_assistant.observability.daily_digest._count_runtimes_up_down", return_value=(3, 2))
    def test_populated_window_renders_data(self, mock_count):
        window_start = datetime.now(timezone.utc) - timedelta(hours=25)
        window_end = datetime.now(timezone.utc)
        result = render_digest(window_start, window_end, db_path=self.db_path)
        self.assertIn("executor", result)
        self.assertTrue("LLMTimeout" in result or "NetworkError" in result)
        self.assertIn("deepseek-v4-pro", result)
        self.assertIn("cost_rule", result)

    @patch("developer_assistant.observability.daily_digest._count_runtimes_up_down", return_value=(3, 2))
    def test_populated_window_has_tables(self, mock_count):
        window_start = datetime.now(timezone.utc) - timedelta(hours=25)
        window_end = datetime.now(timezone.utc)
        result = render_digest(window_start, window_end, db_path=self.db_path)
        self.assertIn("| Runtime | Count |", result)
        self.assertIn("| Role | Model |", result)


class TestSectionOrdering(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "operational.db")
        _build_populated_db(self.db_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("developer_assistant.observability.daily_digest._count_runtimes_up_down", return_value=(3, 2))
    def test_section_order_is_stable(self, mock_count):
        window_start = datetime.now(timezone.utc) - timedelta(hours=25)
        window_end = datetime.now(timezone.utc)
        result = render_digest(window_start, window_end, db_path=self.db_path)

        wi_pos = result.index("Work Items Completed")
        err_pos = result.index("Errors")
        esc_pos = result.index("Escalations")
        llm_pos = result.index("LLM Cost")

        self.assertLess(wi_pos, err_pos)
        self.assertLess(err_pos, esc_pos)
        self.assertLess(esc_pos, llm_pos)

    @patch("developer_assistant.observability.daily_digest._count_runtimes_up_down", return_value=(3, 2))
    def test_recovery_link_present_when_errors(self, mock_count):
        window_start = datetime.now(timezone.utc) - timedelta(hours=25)
        window_end = datetime.now(timezone.utc)
        result = render_digest(window_start, window_end, db_path=self.db_path)
        self.assertIn("RECOVERY-PLAYBOOK.md", result)

    @patch("developer_assistant.observability.daily_digest._count_runtimes_up_down", return_value=(5, 0))
    def test_recovery_link_absent_when_no_errors(self, mock_count):
        tmpdir2 = tempfile.mkdtemp()
        try:
            db_path2 = os.path.join(tmpdir2, "operational.db")
            _build_empty_db(db_path2)
            window_start = datetime.now(timezone.utc) - timedelta(hours=24)
            window_end = datetime.now(timezone.utc)
            result = render_digest(window_start, window_end, db_path=db_path2)
            self.assertNotIn("RECOVERY-PLAYBOOK.md", result)
        finally:
            import shutil
            shutil.rmtree(tmpdir2, ignore_errors=True)


class TestWriteDigestFilenameDeterminism(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.dest_dir = os.path.join(self.tmpdir, "dest")
        self.db_path = os.path.join(self.tmpdir, "operational.db")
        _build_empty_db(self.db_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("developer_assistant.observability.daily_digest._count_runtimes_up_down", return_value=(0, 5))
    def test_filename_is_deterministic(self, mock_count):
        window_start = datetime(2026, 5, 6, 0, 0, 0)
        window_end = datetime(2026, 5, 7, 0, 0, 0)
        path = write_digest(window_start, window_end, dest_dir=self.dest_dir, db_path=self.db_path)
        self.assertEqual(path.name, "daily-digest-20260506.md")

    @patch("developer_assistant.observability.daily_digest._count_runtimes_up_down", return_value=(0, 5))
    def test_idempotent_write_overwrites(self, mock_count):
        window_start = datetime(2026, 5, 6, 0, 0, 0)
        window_end = datetime(2026, 5, 7, 0, 0, 0)
        path1 = write_digest(window_start, window_end, dest_dir=self.dest_dir, db_path=self.db_path)
        content1 = path1.read_text(encoding="utf-8")
        path2 = write_digest(window_start, window_end, dest_dir=self.dest_dir, db_path=self.db_path)
        content2 = path2.read_text(encoding="utf-8")
        self.assertEqual(path1, path2)
        self.assertEqual(content1, content2)


class TestDeliverDigestViaTelegram(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.dest_dir = os.path.join(self.tmpdir, "dest")
        self.db_path = os.path.join(self.tmpdir, "operational.db")
        _build_empty_db(self.db_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("developer_assistant.observability.daily_digest._count_runtimes_up_down", return_value=(0, 5))
    def test_delivery_success_sends_message(self, mock_count):
        window_start = datetime(2026, 5, 6, 0, 0, 0)
        window_end = datetime(2026, 5, 7, 0, 0, 0)
        path = write_digest(window_start, window_end, dest_dir=self.dest_dir, db_path=self.db_path)

        fake = _FakeTelegramClient()
        deliver_digest_via_telegram(path, telegram_client=fake, chat_key="chat:founder")
        self.assertEqual(len(fake.sent), 1)
        self.assertEqual(fake.sent[0][0], "chat:founder")
        self.assertIn("Daily Digest", fake.sent[0][1])

    @patch("developer_assistant.observability.daily_digest._count_runtimes_up_down", return_value=(0, 5))
    def test_delivery_failure_raises_and_preserves_file(self, mock_count):
        window_start = datetime(2026, 5, 6, 0, 0, 0)
        window_end = datetime(2026, 5, 7, 0, 0, 0)
        path = write_digest(window_start, window_end, dest_dir=self.dest_dir, db_path=self.db_path)
        self.assertTrue(path.exists())

        failing = _FailingTelegramClient()
        with self.assertRaises(DigestDeliveryError):
            deliver_digest_via_telegram(path, telegram_client=failing, chat_key="chat:founder")

        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 0)


class TestPagination(unittest.TestCase):
    @patch("developer_assistant.observability.daily_digest._count_runtimes_up_down", return_value=(0, 5))
    def test_long_digest_is_paginated(self, mock_count):
        fake = _FakeTelegramClient()
        long_text = "line\n" * 5000
        parts = paginate_text(long_text, max_len=4096)
        self.assertGreater(len(parts), 1)
        for i, part in enumerate(parts, 1):
            self.assertTrue(part.startswith(f"(part {i}/"))


class TestGracefulDegradationMissingTables(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "operational.db")
        _build_partial_db(self.db_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("developer_assistant.observability.daily_digest._count_runtimes_up_down", return_value=(0, 5))
    def test_missing_tables_no_crash(self, mock_count):
        window_start = datetime.now(timezone.utc) - timedelta(hours=24)
        window_end = datetime.now(timezone.utc)
        result = render_digest(window_start, window_end, db_path=self.db_path)
        self.assertIn("Daily Digest", result)
        self.assertIn("No data available", result)


if __name__ == "__main__":
    unittest.main()
