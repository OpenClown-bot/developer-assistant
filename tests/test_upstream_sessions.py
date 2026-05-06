"""Tests for developer_assistant.upstream_sessions.

Uses stdlib unittest and in-memory sqlite. No real tokens, PATs,
production hostnames, or bash subprocesses.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant import state_store
from developer_assistant import upstream_sessions as sessions


class TestGetOrCreateSession(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_create_returns_row(self) -> None:
        row = sessions.get_or_create_session(
            self.conn,
            session_id="tg-123456789",
            adapter_id="telegram",
            founder_id="founder-001",
            upstream_chat_id="123456789",
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["session_id"], "tg-123456789")
        self.assertEqual(row["adapter_id"], "telegram")
        self.assertEqual(row["founder_id"], "founder-001")
        self.assertEqual(row["paused"], 0)
        self.assertIsNone(row["current_project_id"])

    def test_get_existing_updates_last_message_at(self) -> None:
        row1 = sessions.get_or_create_session(
            self.conn,
            session_id="tg-123456789",
            adapter_id="telegram",
            founder_id="founder-001",
            upstream_chat_id="123456789",
        )
        row2 = sessions.get_or_create_session(
            self.conn,
            session_id="tg-123456789",
            adapter_id="telegram",
            founder_id="founder-001",
            upstream_chat_id="123456789",
        )
        self.assertEqual(row1["id"], row2["id"])
        self.assertGreaterEqual(row2["last_message_at"], row1["last_message_at"])

    def test_upsert_updates_upstream_chat_id(self) -> None:
        sessions.get_or_create_session(
            self.conn,
            session_id="tg-123456789",
            adapter_id="telegram",
            founder_id="founder-001",
            upstream_chat_id="123456789",
        )
        row = sessions.get_or_create_session(
            self.conn,
            session_id="tg-123456789",
            adapter_id="telegram",
            founder_id="founder-001",
            upstream_chat_id="987654321",
        )
        self.assertEqual(row["upstream_chat_id"], "987654321")


class TestUpdateSessionLastMessage(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_touch_updates_timestamp(self) -> None:
        sessions.get_or_create_session(
            self.conn,
            session_id="tg-123456789",
            adapter_id="telegram",
            founder_id="founder-001",
            upstream_chat_id="123456789",
        )
        row = sessions.update_session_last_message(
            self.conn,
            session_id="tg-123456789",
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["session_id"], "tg-123456789")

    def test_nonexistent_returns_none(self) -> None:
        row = sessions.update_session_last_message(
            self.conn,
            session_id="tg-no-such",
        )
        self.assertIsNone(row)


class TestSetSessionPaused(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_pause_true(self) -> None:
        sessions.get_or_create_session(
            self.conn,
            session_id="tg-123456789",
            adapter_id="telegram",
            founder_id="founder-001",
            upstream_chat_id="123456789",
        )
        row = sessions.set_session_paused(
            self.conn,
            session_id="tg-123456789",
            paused=True,
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["paused"], 1)

    def test_pause_false_clears(self) -> None:
        sessions.get_or_create_session(
            self.conn,
            session_id="tg-123456789",
            adapter_id="telegram",
            founder_id="founder-001",
            upstream_chat_id="123456789",
        )
        sessions.set_session_paused(self.conn, session_id="tg-123456789", paused=True)
        row = sessions.set_session_paused(self.conn, session_id="tg-123456789", paused=False)
        self.assertIsNotNone(row)
        self.assertEqual(row["paused"], 0)

    def test_nonexistent_returns_none(self) -> None:
        row = sessions.set_session_paused(
            self.conn,
            session_id="tg-no-such",
            paused=True,
        )
        self.assertIsNone(row)


class TestSetSessionCurrentProject(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_set_project_id(self) -> None:
        sessions.get_or_create_session(
            self.conn,
            session_id="tg-123456789",
            adapter_id="telegram",
            founder_id="founder-001",
            upstream_chat_id="123456789",
        )
        row = sessions.set_session_current_project(
            self.conn,
            session_id="tg-123456789",
            project_id=42,
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["current_project_id"], 42)

    def test_clear_project_id(self) -> None:
        sessions.get_or_create_session(
            self.conn,
            session_id="tg-123456789",
            adapter_id="telegram",
            founder_id="founder-001",
            upstream_chat_id="123456789",
        )
        sessions.set_session_current_project(
            self.conn,
            session_id="tg-123456789",
            project_id=42,
        )
        row = sessions.set_session_current_project(
            self.conn,
            session_id="tg-123456789",
            project_id=None,
        )
        self.assertIsNotNone(row)
        self.assertIsNone(row["current_project_id"])

    def test_nonexistent_returns_none(self) -> None:
        row = sessions.set_session_current_project(
            self.conn,
            session_id="tg-no-such",
            project_id=1,
        )
        self.assertIsNone(row)


class TestReadSession(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_found(self) -> None:
        sessions.get_or_create_session(
            self.conn,
            session_id="tg-123456789",
            adapter_id="telegram",
            founder_id="founder-001",
            upstream_chat_id="123456789",
        )
        row = sessions.read_session(self.conn, "tg-123456789")
        self.assertIsNotNone(row)
        self.assertEqual(row["session_id"], "tg-123456789")

    def test_not_found(self) -> None:
        row = sessions.read_session(self.conn, "tg-no-such")
        self.assertIsNone(row)


class TestListSessions(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_list_all(self) -> None:
        sessions.get_or_create_session(
            self.conn,
            session_id="tg-111",
            adapter_id="telegram",
            founder_id="founder-001",
            upstream_chat_id="111",
        )
        sessions.get_or_create_session(
            self.conn,
            session_id="tg-222",
            adapter_id="telegram",
            founder_id="founder-001",
            upstream_chat_id="222",
        )
        rows = sessions.list_sessions(self.conn)
        self.assertEqual(len(rows), 2)

    def test_filter_by_founder_id(self) -> None:
        sessions.get_or_create_session(
            self.conn,
            session_id="tg-111",
            adapter_id="telegram",
            founder_id="founder-001",
            upstream_chat_id="111",
        )
        sessions.get_or_create_session(
            self.conn,
            session_id="tg-222",
            adapter_id="telegram",
            founder_id="founder-002",
            upstream_chat_id="222",
        )
        rows = sessions.list_sessions(self.conn, founder_id="founder-001")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["founder_id"], "founder-001")

    def test_filter_by_paused(self) -> None:
        sessions.get_or_create_session(
            self.conn,
            session_id="tg-111",
            adapter_id="telegram",
            founder_id="founder-001",
            upstream_chat_id="111",
        )
        sessions.get_or_create_session(
            self.conn,
            session_id="tg-222",
            adapter_id="telegram",
            founder_id="founder-001",
            upstream_chat_id="222",
        )
        sessions.set_session_paused(self.conn, session_id="tg-222", paused=True)
        rows = sessions.list_sessions(self.conn, paused=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["session_id"], "tg-222")


if __name__ == "__main__":
    unittest.main()