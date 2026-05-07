"""Tests for developer_assistant.skills.telegram_gateway_status_handler.

Covers: allowlist accept/reject, pagination at 4096 chars,
content equivalence with dev-assist-cli status --format human,
behavior when operational.db is unreachable.

All offline: fake sender, fake allowlist, fixture DB. No real Telegram.
"""

from __future__ import annotations

import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.skills.telegram_gateway_status_handler import (
    handle_status_command,
)
from developer_assistant.observability.status_query import (
    query_status,
    render_status_human,
)
from developer_assistant.observability.telegram_utils import paginate_text


class _FakeSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, chat_key: str, text: str) -> None:
        self.sent.append((chat_key, text))


class _FakeAllowlist:
    def __init__(self, allowed_keys: set[tuple[str, str]] | None = None) -> None:
        self.allowed = allowed_keys if allowed_keys is not None else {("chat:founder", "user:founder")}

    def is_allowed(self, chat_key: str, user_key: str) -> bool:
        return (chat_key, user_key) in self.allowed


def _build_fixture_db(db_path: str) -> None:
    from tests.fixtures.dev_assist_cli.make_fixture_db import build_fixture_db
    build_fixture_db(db_path)


_MOCK_HEALTH = {
    "ok": True, "status_code": 200,
    "body": {
        "role": "executor", "state": "running", "uptime_s": 86400,
        "current_model": "glm-5.1", "current_work_item_id": "1",
        "heartbeat_age_s": 12,
    }
}


class TestAllowlistAccept(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "operational.db")
        _build_fixture_db(self.db_path)
        self.sender = _FakeSender()
        self.allowlist = _FakeAllowlist()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_allowed_user_receives_status(self):
        with patch("developer_assistant.observability.status_query._check_health_endpoint", return_value=_MOCK_HEALTH), \
             patch("developer_assistant.observability.status_query._check_systemctl_unit", return_value="active"):
            result = handle_status_command(
                "chat:founder", "user:founder",
                self.sender, self.allowlist, db_path=self.db_path,
            )

        self.assertTrue(result)
        self.assertGreater(len(self.sender.sent), 0)
        self.assertEqual(self.sender.sent[0][0], "chat:founder")
        self.assertIn("Runtimes:", self.sender.sent[0][1])


class TestAllowlistReject(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "operational.db")
        _build_fixture_db(self.db_path)
        self.sender = _FakeSender()
        self.allowlist = _FakeAllowlist()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_non_allowed_user_gets_generic_rejection(self):
        result = handle_status_command(
            "chat:unknown", "user:stranger",
            self.sender, self.allowlist, db_path=self.db_path,
        )

        self.assertFalse(result)
        self.assertEqual(len(self.sender.sent), 1)
        self.assertIn("not available", self.sender.sent[0][1])

    def test_rejection_does_not_leak_status_info(self):
        handle_status_command(
            "chat:unknown", "user:stranger",
            self.sender, self.allowlist, db_path=self.db_path,
        )
        msg = self.sender.sent[0][1]
        self.assertNotIn("Runtimes:", msg)
        self.assertNotIn("Queue:", msg)


class TestPaginationAt4096(unittest.TestCase):
    def test_short_text_no_pagination(self):
        parts = paginate_text("short text\n", max_len=4096)
        self.assertEqual(len(parts), 1)
        self.assertFalse(parts[0].startswith("(part"))

    def test_long_text_is_paginated(self):
        long_text = "line of text\n" * 500
        parts = paginate_text(long_text, max_len=4096)
        self.assertGreater(len(parts), 1)
        for i, part in enumerate(parts, 1):
            self.assertTrue(part.startswith(f"(part {i}/"))
            self.assertLessEqual(len(part), 4096 + 20)

    def test_pagination_splits_at_line_boundaries(self):
        long_text = "a" * 4090 + "\n" + "b" * 4090
        parts = paginate_text(long_text, max_len=4096)
        self.assertGreater(len(parts), 1)
        for part in parts:
            lines = part.split("\n")
            for line in lines:
                if line.startswith("(part"):
                    continue
                if line:
                    self.assertLessEqual(len(line), 4096)

    def test_pagination_part_count_consistent(self):
        long_text = "line\n" * 5000
        parts = paginate_text(long_text, max_len=4096)
        total = len(parts)
        for i, part in enumerate(parts, 1):
            self.assertTrue(part.startswith(f"(part {i}/{total})"))


class TestContentEquivalenceWithCLI(unittest.TestCase):
    """Both CLI and Telegram /status handler go through status_query.query_status()
    and status_query.render_status_human(). This test verifies they produce
    identical output by calling both paths with the same mocked deps."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "operational.db")
        _build_fixture_db(self.db_path)
        self.sender = _FakeSender()
        self.allowlist = _FakeAllowlist()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_telegram_status_matches_cli_human_format(self):
        frozen_now = datetime(2026, 5, 7, 12, 0, 0, 123000, tzinfo=timezone.utc)
        with patch("developer_assistant.observability.status_query._check_health_endpoint", return_value=_MOCK_HEALTH), \
             patch("developer_assistant.observability.status_query._check_systemctl_unit", return_value="active"), \
             patch("developer_assistant.observability.status_query.datetime") as mock_dt:
            mock_dt.now.return_value = frozen_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            status_dict = query_status(db_path=self.db_path)
            cli_text = render_status_human(status_dict)

            handle_status_command(
                "chat:founder", "user:founder",
                self.sender, self.allowlist, db_path=self.db_path,
            )

        telegram_text = self.sender.sent[0][1]
        self.assertEqual(telegram_text, cli_text)


class TestDbUnreachable(unittest.TestCase):
    def setUp(self):
        self.sender = _FakeSender()
        self.allowlist = _FakeAllowlist()

    def test_unreachable_db_sends_error_message(self):
        result = handle_status_command(
            "chat:founder", "user:founder",
            self.sender, self.allowlist, db_path="/nonexistent/path/operational.db",
        )

        self.assertTrue(result)
        self.assertGreater(len(self.sender.sent), 0)
        self.assertIn("failed", self.sender.sent[0][1].lower())


if __name__ == "__main__":
    unittest.main()
