"""Tests for developer_assistant.observability.observability_manager.

Covers: lifecycle (start/stop), work_item_id context propagation,
record_llm_call/record_error proxy, catalog parser integration.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.state_store import open_store, init_schema
from developer_assistant.observability.observability_manager import ObservabilityManager


class StubCatalogParser:
    def get_role_assignment(self, role: str) -> Any:
        return MagicMock(main="test-model", fallbacks=[])

    def get_rate_for_model(self, model_id: str) -> tuple[float, float]:
        rates = {
            "glm-5p1": (0.40, 1.60),
            "deepseek-v4-pro": (0.50, 2.19),
        }
        return rates.get(model_id, (0.0, 0.0))


class TestObservabilityManagerLifecycle(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._td.name, "obs_mgr.db")
        conn = open_store(self._db_path)
        conn.close()
        self._parser = StubCatalogParser()

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_start_and_stop(self) -> None:
        mgr = ObservabilityManager(
            runtime_role="executor",
            operational_db_path=self._db_path,
            health_endpoint_port=0,
            catalog_parser=self._parser,
        )
        mgr._health_port = 0
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(mgr.start())
            loop.run_until_complete(mgr.stop())
        finally:
            loop.close()

    def test_stop_idempotent(self) -> None:
        mgr = ObservabilityManager(
            runtime_role="executor",
            operational_db_path=self._db_path,
            health_endpoint_port=0,
            catalog_parser=self._parser,
        )
        mgr._health_port = 0
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(mgr.start())
            loop.run_until_complete(mgr.stop())
            loop.run_until_complete(mgr.stop())
        finally:
            loop.close()


class TestObservabilityManagerContextPropagation(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._td.name, "obs_ctx.db")
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

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_set_work_item_context(self) -> None:
        self._mgr.set_work_item_context("42")
        self.assertEqual(self._mgr._work_item_id, "42")

    def test_clear_work_item_context(self) -> None:
        self._mgr.set_work_item_context("42")
        self._mgr.clear_work_item_context()
        self.assertIsNone(self._mgr._work_item_id)


class TestObservabilityManagerRecordCalls(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._td.name, "obs_rec.db")
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
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._mgr.start())
        finally:
            loop.close()

    def tearDown(self) -> None:
        if self._mgr._db is not None:
            self._mgr._db.close()
        self._td.cleanup()

    def test_record_llm_call(self) -> None:
        self._mgr.record_llm_call(
            model_id="glm-5p1",
            routing_path="omniroute_endpoint",
            tokens_in=1000,
            tokens_out=500,
            latency_ms=1200,
            cost_usd=0.0012,
            status="success",
        )
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute("SELECT * FROM llm_calls")
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["runtime"], "executor")
            self.assertEqual(row["model"], "glm-5p1")
            self.assertEqual(row["rate_in_per_1m_usd"], 0.40)
            self.assertEqual(row["rate_out_per_1m_usd"], 1.60)
        finally:
            conn.close()

    def test_record_error(self) -> None:
        self._mgr.record_error(
            kind="TestError",
            message="something went wrong",
            stack="traceback line",
        )
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute("SELECT * FROM errors")
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["runtime"], "executor")
            self.assertEqual(row["error_class"], "TestError")
        finally:
            conn.close()

    def test_work_item_id_propagated_to_llm_call(self) -> None:
        self._mgr.set_work_item_context("99")
        self._mgr.record_llm_call(
            model_id="glm-5p1",
            routing_path="omniroute_endpoint",
            tokens_in=100,
            tokens_out=50,
            latency_ms=500,
            cost_usd=0.00012,
            status="success",
        )
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute("SELECT work_item_id FROM llm_calls")
            self.assertEqual(cur.fetchone()["work_item_id"], "99")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
