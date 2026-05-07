"""Tests for developer_assistant.state.observability_store.

Covers: schema migration, record_error, record_llm_call,
aggregate_llm_calls_daily, query helpers, WAL mode, idempotency.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.state_store import open_store, init_schema
from developer_assistant.state.observability_store import (
    aggregate_llm_calls_daily,
    ensure_wal_mode,
    query_errors,
    query_llm_calls,
    query_llm_calls_daily,
    record_error,
    record_llm_call,
)


def _open_observability_db(db_path: str = ":memory:") -> sqlite3.Connection:
    if db_path == ":memory:":
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        init_schema(conn)
        return conn
    conn = open_store(db_path)
    return conn


class TestObservabilityMigration(unittest.TestCase):
    def test_migration_creates_tables(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "test_obs.db")
            conn = _open_observability_db(db_path)
            try:
                cur = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                tables = {r["name"] for r in cur.fetchall()}
                self.assertIn("errors", tables)
                self.assertIn("llm_calls", tables)
                self.assertIn("llm_calls_daily", tables)
            finally:
                conn.close()

    def test_migration_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "test_obs_idem.db")
            conn = _open_observability_db(db_path)
            try:
                cur = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM _schema_meta WHERE key='schema_version'"
                )
                self.assertEqual(cur.fetchone()["cnt"], 1)
                init_schema(conn)
                cur2 = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM _schema_meta WHERE key='schema_version'"
                )
                self.assertEqual(cur2.fetchone()["cnt"], 1)
            finally:
                conn.close()

    def test_schema_version_is_3(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "test_ver.db")
            conn = _open_observability_db(db_path)
            try:
                cur = conn.execute(
                    "SELECT value FROM _schema_meta WHERE key='schema_version'"
                )
                self.assertEqual(cur.fetchone()["value"], "3")
            finally:
                conn.close()

    def test_wal_mode_on_disk(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "test_wal.db")
            conn = _open_observability_db(db_path)
            try:
                cur = conn.execute("PRAGMA journal_mode")
                self.assertEqual(cur.fetchone()[0].lower(), "wal")
            finally:
                conn.close()

    def test_memory_db_not_wal(self) -> None:
        conn = _open_observability_db(":memory:")
        try:
            cur = conn.execute("PRAGMA journal_mode")
            self.assertNotEqual(cur.fetchone()[0].lower(), "wal")
        finally:
            conn.close()


class TestRecordError(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _open_observability_db(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_record_error_writes_row(self) -> None:
        err_id = record_error(
            self.conn,
            role="executor",
            kind="SchemaValidationError",
            message="bad payload",
        )
        self.assertTrue(err_id)
        cur = self.conn.execute("SELECT * FROM errors WHERE err_id = ?", (err_id,))
        row = cur.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["runtime"], "executor")
        self.assertEqual(row["error_class"], "SchemaValidationError")
        self.assertEqual(row["message"], "bad payload")
        self.assertIsNone(row["work_item_id"])
        self.assertEqual(row["context_json"], "{}")

    def test_record_error_with_work_item(self) -> None:
        err_id = record_error(
            self.conn,
            role="architect",
            kind="TimeoutError",
            message="upstream timeout",
            work_item_id="42",
        )
        cur = self.conn.execute("SELECT work_item_id FROM errors WHERE err_id = ?", (err_id,))
        self.assertEqual(cur.fetchone()["work_item_id"], "42")

    def test_record_error_with_stack_and_context(self) -> None:
        err_id = record_error(
            self.conn,
            role="reviewer",
            kind="ValueError",
            message="bad value",
            stack="Traceback...",
            context={"key": "val"},
        )
        cur = self.conn.execute("SELECT context_json FROM errors WHERE err_id = ?", (err_id,))
        ctx = json.loads(cur.fetchone()["context_json"])
        self.assertEqual(ctx["stack"], "Traceback...")
        self.assertEqual(ctx["key"], "val")

    def test_record_error_null_fields(self) -> None:
        err_id = record_error(
            self.conn,
            role="orchestrator",
            kind="TestError",
            message="test",
        )
        cur = self.conn.execute("SELECT * FROM errors WHERE err_id = ?", (err_id,))
        row = cur.fetchone()
        self.assertIsNone(row["work_item_id"])
        self.assertEqual(row["context_json"], "{}")


class TestRecordLLMCall(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _open_observability_db(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_record_llm_call_success(self) -> None:
        call_id = record_llm_call(
            self.conn,
            role="executor",
            model_id="glm-5p1",
            routing_path="omniroute_endpoint",
            tokens_in=1000,
            tokens_out=500,
            latency_ms=1200,
            rate_in_per_1m_usd=0.40,
            rate_out_per_1m_usd=1.60,
            cost_usd=0.0012,
            status="success",
        )
        cur = self.conn.execute("SELECT * FROM llm_calls WHERE call_id = ?", (call_id,))
        row = cur.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["runtime"], "executor")
        self.assertEqual(row["model"], "glm-5p1")
        self.assertEqual(row["routing_path"], "omniroute_endpoint")
        self.assertEqual(row["tokens_in"], 1000)
        self.assertEqual(row["tokens_out"], 500)
        self.assertEqual(row["latency_ms"], 1200)
        self.assertEqual(row["status"], "success")
        self.assertIsNone(row["error_class"])

    def test_record_llm_call_fail(self) -> None:
        call_id = record_llm_call(
            self.conn,
            role="executor",
            model_id="glm-5p1",
            routing_path="omniroute_endpoint",
            tokens_in=100,
            tokens_out=0,
            latency_ms=5000,
            rate_in_per_1m_usd=0.40,
            rate_out_per_1m_usd=1.60,
            cost_usd=0.0,
            status="fail",
            error_class="provider_5xx",
        )
        cur = self.conn.execute("SELECT error_class, status FROM llm_calls WHERE call_id = ?", (call_id,))
        row = cur.fetchone()
        self.assertEqual(row["status"], "fail")
        self.assertEqual(row["error_class"], "provider_5xx")

    def test_cost_usd_math(self) -> None:
        tokens_in = 1000
        tokens_out = 500
        rate_in = 0.40
        rate_out = 1.60
        expected = (tokens_in * rate_in + tokens_out * rate_out) / 1_000_000
        call_id = record_llm_call(
            self.conn,
            role="architect",
            model_id="deepseek-v4-pro",
            routing_path="omniroute_endpoint",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=1000,
            rate_in_per_1m_usd=rate_in,
            rate_out_per_1m_usd=rate_out,
            cost_usd=expected,
            status="success",
        )
        cur = self.conn.execute("SELECT cost_usd FROM llm_calls WHERE call_id = ?", (call_id,))
        self.assertAlmostEqual(cur.fetchone()["cost_usd"], expected, places=8)


class TestAggregateLLMCallsDaily(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _open_observability_db(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_aggregate_creates_daily_rows(self) -> None:
        for i in range(3):
            record_llm_call(
                self.conn,
                role="executor",
                model_id="glm-5p1",
                routing_path="omniroute_endpoint",
                tokens_in=100,
                tokens_out=50,
                latency_ms=1000 + i * 100,
                rate_in_per_1m_usd=0.40,
                rate_out_per_1m_usd=1.60,
                cost_usd=0.00012,
                status="success",
            )
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        count = aggregate_llm_calls_daily(self.conn, today)
        self.assertEqual(count, 1)
        cur = self.conn.execute("SELECT * FROM llm_calls_daily")
        row = cur.fetchone()
        self.assertEqual(row["call_count"], 3)
        self.assertEqual(row["call_count_success"], 3)
        self.assertEqual(row["call_count_fail"], 0)

    def test_aggregate_idempotent(self) -> None:
        record_llm_call(
            self.conn,
            role="executor",
            model_id="glm-5p1",
            routing_path="omniroute_endpoint",
            tokens_in=100,
            tokens_out=50,
            latency_ms=1000,
            rate_in_per_1m_usd=0.40,
            rate_out_per_1m_usd=1.60,
            cost_usd=0.00012,
            status="success",
        )
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        aggregate_llm_calls_daily(self.conn, today)
        aggregate_llm_calls_daily(self.conn, today)
        cur = self.conn.execute("SELECT COUNT(*) AS cnt FROM llm_calls_daily")
        self.assertEqual(cur.fetchone()["cnt"], 1)

    def test_aggregate_p50_p95_with_enough_calls(self) -> None:
        for i in range(10):
            record_llm_call(
                self.conn,
                role="executor",
                model_id="glm-5p1",
                routing_path="omniroute_endpoint",
                tokens_in=100,
                tokens_out=50,
                latency_ms=100 + i * 100,
                rate_in_per_1m_usd=0.40,
                rate_out_per_1m_usd=1.60,
                cost_usd=0.00012,
                status="success",
            )
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        aggregate_llm_calls_daily(self.conn, today)
        cur = self.conn.execute("SELECT * FROM llm_calls_daily")
        row = cur.fetchone()
        self.assertIsNotNone(row["latency_ms_p50"])
        self.assertIsNotNone(row["latency_ms_p95"])

    def test_aggregate_no_p50_p95_with_few_calls(self) -> None:
        for i in range(3):
            record_llm_call(
                self.conn,
                role="executor",
                model_id="glm-5p1",
                routing_path="omniroute_endpoint",
                tokens_in=100,
                tokens_out=50,
                latency_ms=1000,
                rate_in_per_1m_usd=0.40,
                rate_out_per_1m_usd=1.60,
                cost_usd=0.00012,
                status="success",
            )
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        aggregate_llm_calls_daily(self.conn, today)
        cur = self.conn.execute("SELECT latency_ms_p50, latency_ms_p95 FROM llm_calls_daily")
        row = cur.fetchone()
        self.assertIsNone(row["latency_ms_p50"])
        self.assertIsNone(row["latency_ms_p95"])


class TestQueryErrors(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _open_observability_db(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_query_errors_by_since(self) -> None:
        record_error(self.conn, role="executor", kind="E1", message="m1")
        results = query_errors(self.conn, since="2020-01-01T00:00:00")
        self.assertEqual(len(results), 1)

    def test_query_errors_by_runtime(self) -> None:
        record_error(self.conn, role="executor", kind="E1", message="m1")
        record_error(self.conn, role="architect", kind="E2", message="m2")
        results = query_errors(self.conn, since="2020-01-01T00:00:00", runtime_role="executor")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["runtime"], "executor")

    def test_query_errors_by_kind(self) -> None:
        record_error(self.conn, role="executor", kind="E1", message="m1")
        record_error(self.conn, role="executor", kind="E2", message="m2")
        results = query_errors(self.conn, since="2020-01-01T00:00:00", kind="E1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["error_class"], "E1")


class TestQueryLLMCalls(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _open_observability_db(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_query_by_runtime(self) -> None:
        record_llm_call(
            self.conn,
            role="executor",
            model_id="glm-5p1",
            routing_path="omniroute_endpoint",
            tokens_in=100,
            tokens_out=50,
            latency_ms=1000,
            rate_in_per_1m_usd=0.40,
            rate_out_per_1m_usd=1.60,
            cost_usd=0.00012,
            status="success",
        )
        results = query_llm_calls(self.conn, runtime_role="executor")
        self.assertEqual(len(results), 1)
        results2 = query_llm_calls(self.conn, runtime_role="architect")
        self.assertEqual(len(results2), 0)

    def test_query_by_status(self) -> None:
        record_llm_call(
            self.conn,
            role="executor",
            model_id="glm-5p1",
            routing_path="omniroute_endpoint",
            tokens_in=100,
            tokens_out=0,
            latency_ms=5000,
            rate_in_per_1m_usd=0.40,
            rate_out_per_1m_usd=1.60,
            cost_usd=0.0,
            status="fail",
            error_class="timeout",
        )
        results = query_llm_calls(self.conn, status="fail")
        self.assertEqual(len(results), 1)


class TestQueryLLMCallsDaily(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _open_observability_db(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_query_daily(self) -> None:
        record_llm_call(
            self.conn,
            role="executor",
            model_id="glm-5p1",
            routing_path="omniroute_endpoint",
            tokens_in=100,
            tokens_out=50,
            latency_ms=1000,
            rate_in_per_1m_usd=0.40,
            rate_out_per_1m_usd=1.60,
            cost_usd=0.00012,
            status="success",
        )
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        aggregate_llm_calls_daily(self.conn, today)
        results = query_llm_calls_daily(self.conn, runtime_role="executor")
        self.assertEqual(len(results), 1)


if __name__ == "__main__":
    unittest.main()
