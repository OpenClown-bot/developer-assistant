"""Tests for developer_assistant.observability.llm_client_instrumentation.

Covers: wrapper records expected llm_call row on success against a stub
OmniRoute HTTP server, records status=fail on transport error,
records status=fail with error_class=provider_5xx on upstream HTTP 5xx,
rate-snapshot lookup, cost_usd math.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.state_store import open_store
from developer_assistant.observability.llm_client_instrumentation import (
    InstrumentedLLMClient,
    LLMCallError,
)
from developer_assistant.observability.observability_manager import ObservabilityManager


class StubCatalogParser:
    def get_role_assignment(self, role: str) -> Any:
        from unittest.mock import MagicMock
        return MagicMock(main="glm-5p1", fallbacks=[])

    def get_rate_for_model(self, model_id: str) -> tuple[float, float]:
        rates = {
            "glm-5p1": (0.40, 1.60),
            "deepseek-v4-pro": (0.50, 2.19),
        }
        return rates.get(model_id, (0.0, 0.0))


async def _start_stub_server(
    responses: list[tuple[int, dict]],
) -> tuple[asyncio.AbstractServer, int]:
    queue = list(responses)

    async def handler(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        await reader.read(65536)
        if queue:
            status_code, body_dict = queue.pop(0)
        else:
            status_code, body_dict = 200, {}
        body = json.dumps(body_dict).encode("utf-8")
        reason = "OK" if status_code == 200 else "Error"
        writer.write(
            f"HTTP/1.1 {status_code} {reason}\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Content-Type: application/json\r\n"
            f"Connection: close\r\n\r\n".encode()
        )
        writer.write(body)
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, port


class TestInstrumentationSuccess(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._td.name, "instr.db")
        conn = open_store(self._db_path)
        conn.close()
        self._parser = StubCatalogParser()
        self._mgr = ObservabilityManager(
            runtime_role="executor",
            operational_db_path=self._db_path,
            health_endpoint_port=0,
            catalog_parser=self._parser,
        )
        self._mgr._health_port = 0
        self._loop = asyncio.new_event_loop()
        self._loop.run_until_complete(self._mgr.start())

    def tearDown(self) -> None:
        if self._mgr._db is not None:
            self._mgr._db.close()
        self._loop.close()
        self._td.cleanup()

    def test_success_records_llm_call(self) -> None:
        response_body = {
            "id": "chatcmpl-123",
            "model": "glm-5p1",
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            "choices": [],
        }
        server, port = self._loop.run_until_complete(
            _start_stub_server([(200, response_body)])
        )
        try:
            client = InstrumentedLLMClient(
                manager=self._mgr,
                omniroute_base_url=f"http://127.0.0.1:{port}",
            )
            result = self._loop.run_until_complete(
                client.chat_completion(
                    model="glm-5p1",
                    messages=[{"role": "user", "content": "test"}],
                )
            )
            self.assertIn("usage", result)
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            try:
                cur = conn.execute("SELECT * FROM llm_calls")
                row = cur.fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row["model"], "glm-5p1")
                self.assertEqual(row["tokens_in"], 100)
                self.assertEqual(row["tokens_out"], 50)
                self.assertEqual(row["status"], "success")
                self.assertEqual(row["runtime"], "executor")
                self.assertAlmostEqual(
                    row["cost_usd"],
                    (100 * 0.40 + 50 * 1.60) / 1_000_000,
                    places=8,
                )
            finally:
                conn.close()
        finally:
            server.close()
            self._loop.run_until_complete(server.wait_closed())

    def test_provider_5xx_records_fail(self) -> None:
        response_body = {"error": {"message": "internal error", "type": "server_error"}}
        server, port = self._loop.run_until_complete(
            _start_stub_server([(500, response_body)])
        )
        try:
            client = InstrumentedLLMClient(
                manager=self._mgr,
                omniroute_base_url=f"http://127.0.0.1:{port}",
            )
            with self.assertRaises(LLMCallError):
                self._loop.run_until_complete(
                    client.chat_completion(
                        model="glm-5p1",
                        messages=[{"role": "user", "content": "test"}],
                    )
                )
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            try:
                cur = conn.execute("SELECT * FROM llm_calls")
                row = cur.fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row["status"], "fail")
                self.assertEqual(row["error_class"], "provider_5xx")
            finally:
                conn.close()
        finally:
            server.close()
            self._loop.run_until_complete(server.wait_closed())

    def test_transport_error_records_fail(self) -> None:
        client = InstrumentedLLMClient(
            manager=self._mgr,
            omniroute_base_url="http://127.0.0.1:1",
            timeout_seconds=2.0,
        )
        with self.assertRaises(LLMCallError):
            self._loop.run_until_complete(
                client.chat_completion(
                    model="glm-5p1",
                    messages=[{"role": "user", "content": "test"}],
                )
            )
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute("SELECT status, error_class FROM llm_calls")
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["status"], "fail")
            self.assertIn(row["error_class"], ("transport", "timeout", "ConnectError"))
        finally:
            conn.close()

    def test_cost_usd_math_known_rates(self) -> None:
        tokens_in = 142000
        tokens_out = 38000
        rate_in = 0.40
        rate_out = 1.60
        expected_cost = (tokens_in * rate_in + tokens_out * rate_out) / 1_000_000
        response_body = {
            "id": "chatcmpl-456",
            "model": "glm-5p1",
            "usage": {"prompt_tokens": tokens_in, "completion_tokens": tokens_out},
            "choices": [],
        }
        server, port = self._loop.run_until_complete(
            _start_stub_server([(200, response_body)])
        )
        try:
            client = InstrumentedLLMClient(
                manager=self._mgr,
                omniroute_base_url=f"http://127.0.0.1:{port}",
            )
            self._loop.run_until_complete(
                client.chat_completion(
                    model="glm-5p1",
                    messages=[{"role": "user", "content": "test"}],
                )
            )
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            try:
                cur = conn.execute("SELECT cost_usd FROM llm_calls")
                row = cur.fetchone()
                self.assertAlmostEqual(row["cost_usd"], expected_cost, places=6)
            finally:
                conn.close()
        finally:
            server.close()
            self._loop.run_until_complete(server.wait_closed())


if __name__ == "__main__":
    unittest.main()
