"""Tests for developer_assistant.observability.health_endpoint.

Covers: JSON shape, localhost-only binding, queue_depth, error detection,
non-localhost refusal.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.state_store import open_store
from developer_assistant.observability.health_endpoint import HealthEndpoint


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _fetch_health(port: int) -> dict:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
    await writer.drain()
    response = b""
    while True:
        chunk = await reader.read(4096)
        if not chunk:
            break
        response += chunk
    writer.close()
    body_start = response.find(b"\r\n\r\n")
    body = response[body_start + 4:] if body_start >= 0 else b""
    return json.loads(body)


class TestHealthEndpointJsonShape(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._td.name, "health.db")
        conn = open_store(self._db_path)
        conn.close()
        self._port = _find_free_port()
        self._ep = HealthEndpoint("executor", self._port, self._db_path)
        self._loop = asyncio.new_event_loop()
        self._loop.run_until_complete(self._ep.start())

    def tearDown(self) -> None:
        self._loop.run_until_complete(self._ep.stop())
        self._loop.close()
        self._td.cleanup()

    def test_health_returns_json(self) -> None:
        result = self._loop.run_until_complete(_fetch_health(self._port))
        self.assertEqual(result["role"], "executor")
        self.assertIn("state", result)
        self.assertIn("uptime_s", result)
        self.assertIn("current_work_item_id", result)
        self.assertIn("current_model", result)
        self.assertIn("version", result)
        self.assertIn("build_commit", result)
        self.assertIn("ts_iso", result)
        self.assertIn("heartbeat_age_s", result)

    def test_health_initial_state_running(self) -> None:
        result = self._loop.run_until_complete(_fetch_health(self._port))
        self.assertEqual(result["state"], "running")

    def test_orchestrator_has_queue_stats(self) -> None:
        td2 = tempfile.TemporaryDirectory()
        db2 = os.path.join(td2.name, "orch_health.db")
        conn = open_store(db2)
        conn.close()
        port2 = _find_free_port()
        ep2 = HealthEndpoint("orchestrator", port2, db2)
        loop2 = asyncio.new_event_loop()
        loop2.run_until_complete(ep2.start())
        try:
            result = loop2.run_until_complete(_fetch_health(port2))
            self.assertIn("queue_stats", result)
            self.assertIn("pending", result["queue_stats"])
            self.assertIn("in_progress", result["queue_stats"])
            self.assertIn("escalated", result["queue_stats"])
            self.assertIn("failed", result["queue_stats"])
        finally:
            loop2.run_until_complete(ep2.stop())
            loop2.close()
            td2.cleanup()


class TestHealthEndpointNonLocalhost(unittest.TestCase):
    def test_non_localhost_refused(self) -> None:
        td = tempfile.TemporaryDirectory()
        db_path = os.path.join(td.name, "refuse.db")
        conn = open_store(db_path)
        conn.close()
        port = _find_free_port()
        ep = HealthEndpoint("executor", port, db_path)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(ep.start())
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                try:
                    s.connect(("0.0.0.0", port))
                    self.fail("Connection from 0.0.0.0 should have been refused")
                except (ConnectionRefusedError, OSError, socket.timeout):
                    pass
        finally:
            loop.run_until_complete(ep.stop())
            loop.close()
            td.cleanup()


class TestHealthEndpointDegradedOnError(unittest.TestCase):
    def test_degraded_on_recent_error(self) -> None:
        td = tempfile.TemporaryDirectory()
        db_path = os.path.join(td.name, "degraded.db")
        conn = open_store(db_path)
        conn.execute(
            "INSERT INTO errors (err_id, ts, runtime, error_class, message, context_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("test1", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "executor", "E", "m", "{}"),
        )
        conn.commit()
        conn.close()
        port = _find_free_port()
        ep = HealthEndpoint("executor", port, db_path)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(ep.start())
        try:
            result = loop.run_until_complete(_fetch_health(port))
            self.assertEqual(result["state"], "degraded")
        finally:
            loop.run_until_complete(ep.stop())
            loop.close()
            td.cleanup()

    def test_degraded_on_db_unreachable(self) -> None:
        port = _find_free_port()
        ep = HealthEndpoint("executor", port, "/nonexistent/path/operational.db")
        loop = asyncio.new_event_loop()
        loop.run_until_complete(ep.start())
        try:
            result = loop.run_until_complete(_fetch_health(port))
            self.assertEqual(result["state"], "degraded")
        finally:
            loop.run_until_complete(ep.stop())
            loop.close()


if __name__ == "__main__":
    unittest.main()
