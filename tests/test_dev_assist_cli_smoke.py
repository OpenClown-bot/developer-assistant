"""TKT-041 v0.1.1 AUDIT-003 — unit tests for dev-assist-cli smoke subcommands.

Covers:
  * `smoke inject-message` refuses when marker absent (exit 2 + structured JSON)
  * `smoke inject-message` round-trip against a local inject server
  * `smoke test-tool` exit-code matrix: 0 dispatched / 3 refused / 1 unexpected
  * `smoke wait` polls work_items.status, emits planner_claim_timeout /
    planner_result_timeout diagnostics on timeout
"""

from __future__ import annotations

import io
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.cli import dev_assist_cli
from developer_assistant.smoke_inject import (
    make_inject_server,
    make_test_tool_server,
    serve_in_thread,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_004 = REPO_ROOT / "db" / "migrations" / "004_work_queue_and_escalations.sql"


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _init_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(MIGRATION_004.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


def _run_cli(argv: list[str]) -> tuple[int, dict]:
    """Run dev_assist_cli.main with captured stdout, returning (exit, json)."""
    buf = io.StringIO()
    real_stdout = sys.stdout
    sys.stdout = buf
    try:
        rc = dev_assist_cli.main(argv)
    finally:
        sys.stdout = real_stdout
    raw = buf.getvalue().strip()
    parsed: dict = {}
    if raw:
        try:
            parsed = json.loads(raw.splitlines()[-1])
        except json.JSONDecodeError:
            parsed = {"raw": raw}
    return rc, parsed


class TestSmokeRefusalWhenMarkerAbsent(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.marker = os.path.join(self._tmp.name, "absent.flag")
        self.db = os.path.join(self._tmp.name, "op.db")
        _init_db(self.db)

    def test_inject_message_refuses(self):
        rc, payload = _run_cli([
            "--db-path", self.db, "smoke", "--marker-file", self.marker,
            "inject-message", "--text", "x",
        ])
        self.assertEqual(rc, 2)
        self.assertEqual(payload["status"], "refused")
        self.assertEqual(payload["error"], "smoke_mode_not_enabled")

    def test_test_tool_refuses(self):
        rc, payload = _run_cli([
            "--db-path", self.db, "smoke", "--marker-file", self.marker,
            "test-tool", "--runtime", "planner", "--tool", "delegate_task",
        ])
        self.assertEqual(rc, 2)
        self.assertEqual(payload["error"], "smoke_mode_not_enabled")

    def test_wait_refuses(self):
        rc, payload = _run_cli([
            "--db-path", self.db, "smoke", "--marker-file", self.marker,
            "wait", "--work-item-id", "1", "--until", "claimed", "--timeout-s", "1",
        ])
        self.assertEqual(rc, 2)
        self.assertEqual(payload["error"], "smoke_mode_not_enabled")


class TestSmokeInjectMessageRoundtrip(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.marker = os.path.join(self._tmp.name, "smoke.flag")
        Path(self.marker).write_text("smoke_mode_active=true\n", encoding="utf-8")
        self.db = os.path.join(self._tmp.name, "op.db")
        _init_db(self.db)
        self.port = _free_port()
        self.server = make_inject_server(
            bind_host="127.0.0.1", bind_port=self.port,
            marker_file_path=self.marker, operational_db_path=self.db,
        )
        serve_in_thread(self.server)
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)

    def test_injects_and_returns_work_item_id(self):
        rc, payload = _run_cli([
            "--db-path", self.db, "smoke", "--marker-file", self.marker,
            "inject-message", "--text", "smoke-fixture-message-cafef00d",
            "--inject-port", str(self.port),
        ])
        self.assertEqual(rc, 0)
        self.assertGreater(int(payload["work_item_id"]), 0)


class TestSmokeTestToolExitMatrix(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.marker = os.path.join(self._tmp.name, "smoke.flag")
        Path(self.marker).write_text("smoke_mode_active=true\n", encoding="utf-8")
        self.db = os.path.join(self._tmp.name, "op.db")
        _init_db(self.db)
        self.port = _free_port()
        self.server = make_test_tool_server(
            "planner", bind_host="127.0.0.1", bind_port=self.port,
            marker_file_path=self.marker,
        )
        serve_in_thread(self.server)
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)

    def test_negative_delegate_task_exit_3(self):
        rc, payload = _run_cli([
            "--db-path", self.db, "smoke", "--marker-file", self.marker,
            "test-tool", "--runtime", "planner", "--tool", "delegate_task",
            "--test-tool-host", "127.0.0.1",
        ])
        # delegate_task is refused on planner; the CLI must hit the SAME
        # port as our planner stub; we override via test-tool-host but not
        # port. Since ROLE_PORTS["planner"]==8282 the test stub here is at
        # self.port. Re-route by monkey-patching _SMOKE_ROLE_PORTS.
        # The test above will incorrectly hit 8282 unless we patch.
        # We re-run with the patched mapping.
        from developer_assistant.cli import dev_assist_cli as _cli
        orig = dict(_cli._SMOKE_ROLE_PORTS)
        _cli._SMOKE_ROLE_PORTS["planner"] = self.port
        try:
            rc, payload = _run_cli([
                "--db-path", self.db, "smoke", "--marker-file", self.marker,
                "test-tool", "--runtime", "planner", "--tool", "delegate_task",
                "--test-tool-host", "127.0.0.1",
            ])
        finally:
            _cli._SMOKE_ROLE_PORTS.clear()
            _cli._SMOKE_ROLE_PORTS.update(orig)
        self.assertEqual(rc, 3)
        self.assertEqual(payload["status"], "refused")
        self.assertEqual(payload["error"], "tool_not_in_assembled_list")

    def test_positive_dispatch_exit_0(self):
        from developer_assistant.cli import dev_assist_cli as _cli
        orig = dict(_cli._SMOKE_ROLE_PORTS)
        _cli._SMOKE_ROLE_PORTS["planner"] = self.port
        try:
            rc, payload = _run_cli([
                "--db-path", self.db, "smoke", "--marker-file", self.marker,
                "test-tool", "--runtime", "planner",
                "--tool", "dev-assist-work-queue-poll",
                "--test-tool-host", "127.0.0.1",
            ])
        finally:
            _cli._SMOKE_ROLE_PORTS.clear()
            _cli._SMOKE_ROLE_PORTS.update(orig)
        self.assertEqual(rc, 0)
        self.assertEqual(payload["status"], "dispatched")


class TestSmokeWaitDiagnostics(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.marker = os.path.join(self._tmp.name, "smoke.flag")
        Path(self.marker).write_text("smoke_mode_active=true\n", encoding="utf-8")
        self.db = os.path.join(self._tmp.name, "op.db")
        _init_db(self.db)
        conn = sqlite3.connect(self.db)
        try:
            cur = conn.execute(
                """INSERT INTO work_items
                       (created_at, updated_at, target_role, kind, payload_json,
                        priority, status, attempt_count, max_attempts)
                   VALUES
                       ('2026-05-11T00:00:00.000Z','2026-05-11T00:00:00.000Z',
                        'planner','smoke_inject','{}',50,'pending',0,3)""",
            )
            self.work_item_id = int(cur.lastrowid or 0)
            conn.commit()
        finally:
            conn.close()

    def test_claim_timeout_emits_planner_claim_timeout(self):
        rc, payload = _run_cli([
            "--db-path", self.db, "smoke", "--marker-file", self.marker,
            "wait", "--work-item-id", str(self.work_item_id),
            "--until", "claimed", "--timeout-s", "1",
            "--poll-interval-s", "0.2",
        ])
        self.assertEqual(rc, 1)
        self.assertEqual(payload["status"], "timeout")
        self.assertEqual(payload["error"], "planner_claim_timeout")

    def test_result_timeout_emits_planner_result_timeout(self):
        rc, payload = _run_cli([
            "--db-path", self.db, "smoke", "--marker-file", self.marker,
            "wait", "--work-item-id", str(self.work_item_id),
            "--until", "completed", "--timeout-s", "1",
            "--poll-interval-s", "0.2",
        ])
        self.assertEqual(rc, 1)
        self.assertEqual(payload["error"], "planner_result_timeout")

    def test_claim_observed_when_status_updates(self):
        # Simulate the planner claiming the row after 200ms.
        def _claim_later():
            time.sleep(0.3)
            conn = sqlite3.connect(self.db)
            try:
                conn.execute(
                    "UPDATE work_items SET status='claimed', "
                    "claimed_at='2026-05-11T00:00:01.000Z' WHERE id = ?",
                    (self.work_item_id,),
                )
                conn.commit()
            finally:
                conn.close()
        threading.Thread(target=_claim_later, daemon=True).start()
        rc, payload = _run_cli([
            "--db-path", self.db, "smoke", "--marker-file", self.marker,
            "wait", "--work-item-id", str(self.work_item_id),
            "--until", "claimed", "--timeout-s", "5",
            "--poll-interval-s", "0.2",
        ])
        self.assertEqual(rc, 0)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["work_item_status"], "claimed")


if __name__ == "__main__":
    unittest.main()
