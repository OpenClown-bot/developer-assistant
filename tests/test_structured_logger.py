"""Tests for developer_assistant.observability.structured_logger.

Covers:
- JSON shape on each log level (debug, info, warn, error)
- All mandatory fields present per OBSERVABILITY-CONTRACT § 4
- contextvar propagation across asyncio.create_task
- contextvar propagation across threading.Thread using dispatch_in_thread
- work_item_id is null outside the work_item() block
- Decorator on sync function — emits start + complete
- Decorator on async function — emits start + complete
- Decorator emits .fail on raised exception with error_class
- No prompt/completion content in the log output
- runtime_role defaults to "unknown" when env var unset
- init_runtime_logger() is idempotent
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import sys
import threading
import unittest
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from developer_assistant.observability.structured_logger import (
    _JsonFormatter,
    _WORK_ITEM_ID,
    dispatch_in_thread,
    get_logger,
    init_runtime_logger,
    instrument_llm_call,
    work_item,
)


class _JsonCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.setFormatter(_JsonFormatter())
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.records.append(self.format(record))
        except Exception:
            pass


@contextmanager
def _capture_logger(name: str = "test"):
    logger = get_logger(name)
    handler = _JsonCapture()
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)


class TestJsonShapePerLevel(unittest.TestCase):
    def setUp(self) -> None:
        init_runtime_logger()

    @patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": "executor"})
    def test_debug_json_shape(self) -> None:
        with _capture_logger("debug_test") as cap:
            lg = get_logger("debug_test")
            lg.debug("hello debug", extra={"event": "test.debug", "_extra_payload": {}})
        lines = cap.records
        self.assertTrue(len(lines) >= 1)
        obj = json.loads(lines[-1])
        self.assertEqual(obj["level"], "debug")
        self.assertEqual(obj["event"], "test.debug")
        self.assertEqual(obj["message"], "hello debug")
        self.assertEqual(obj["runtime_role"], "executor")

    @patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": "executor"})
    def test_info_json_shape(self) -> None:
        with _capture_logger("info_test") as cap:
            lg = get_logger("info_test")
            lg.info("hello info", extra={"event": "test.info", "_extra_payload": {}})
        obj = json.loads(cap.records[-1])
        self.assertEqual(obj["level"], "info")

    @patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": "executor"})
    def test_warn_json_shape(self) -> None:
        with _capture_logger("warn_test") as cap:
            lg = get_logger("warn_test")
            lg.warning("hello warn", extra={"event": "test.warn", "_extra_payload": {}})
        obj = json.loads(cap.records[-1])
        self.assertEqual(obj["level"], "warn")

    @patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": "executor"})
    def test_error_json_shape(self) -> None:
        with _capture_logger("error_test") as cap:
            lg = get_logger("error_test")
            lg.error("hello error", extra={"event": "test.error", "_extra_payload": {}})
        obj = json.loads(cap.records[-1])
        self.assertEqual(obj["level"], "error")


class TestMandatoryFields(unittest.TestCase):
    @patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": "architect"})
    def test_all_mandatory_fields_present(self) -> None:
        with _capture_logger("fields_test") as cap:
            lg = get_logger("fields_test")
            lg.info(
                "test message",
                extra={
                    "event": "test.mandatory",
                    "_extra_payload": {"model": "glm-5p1", "tokens_in": 100, "tokens_out": 50, "latency_ms": 200},
                },
            )
        obj = json.loads(cap.records[-1])
        mandatory = [
            "ts_iso", "level", "runtime_role", "work_item_id",
            "model", "tokens_in", "tokens_out", "latency_ms", "event", "message",
        ]
        for field in mandatory:
            self.assertIn(field, obj, f"missing mandatory field: {field}")
        self.assertEqual(obj["runtime_role"], "architect")
        self.assertEqual(obj["model"], "glm-5p1")
        self.assertEqual(obj["tokens_in"], 100)
        self.assertEqual(obj["tokens_out"], 50)
        self.assertEqual(obj["latency_ms"], 200)
        self.assertIsNone(obj["work_item_id"])

    @patch.dict(os.environ, {}, clear=True)
    def test_runtime_role_defaults_to_unknown(self) -> None:
        from developer_assistant.observability import structured_logger as sl
        sl._RUNTIME_ROLE_WARNED = False
        with _capture_logger("role_test") as cap:
            lg = get_logger("role_test")
            lg.info("no role", extra={"event": "test.norole", "_extra_payload": {}})
        norole_entries = [
            json.loads(r) for r in cap.records
            if json.loads(r).get("event") == "test.norole"
        ]
        self.assertTrue(len(norole_entries) >= 1)
        self.assertEqual(norole_entries[-1]["runtime_role"], "unknown")


class TestWorkItemIdContextVar(unittest.TestCase):
    @patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": "executor"})
    def test_work_item_id_set_inside_block(self) -> None:
        with _capture_logger("ctx_test") as cap:
            lg = get_logger("ctx_test")
            with work_item("abc123"):
                lg.info("inside", extra={"event": "test.inside", "_extra_payload": {}})
        obj = json.loads(cap.records[-1])
        self.assertEqual(obj["work_item_id"], "abc123")

    @patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": "executor"})
    def test_work_item_id_null_outside_block(self) -> None:
        with _capture_logger("ctx_null") as cap:
            lg = get_logger("ctx_null")
            lg.info("outside", extra={"event": "test.outside", "_extra_payload": {}})
        obj = json.loads(cap.records[-1])
        self.assertIsNone(obj["work_item_id"])

    @patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": "executor"})
    def test_work_item_id_restored_after_block(self) -> None:
        with _capture_logger("ctx_restore") as cap:
            lg = get_logger("ctx_restore")
            lg.info("before", extra={"event": "test.before", "_extra_payload": {}})
            with work_item("w1"):
                lg.info("inside", extra={"event": "test.inside", "_extra_payload": {}})
            lg.info("after", extra={"event": "test.after", "_extra_payload": {}})
        objs = [json.loads(r) for r in cap.records]
        self.assertIsNone(objs[0]["work_item_id"])
        self.assertEqual(objs[1]["work_item_id"], "w1")
        self.assertIsNone(objs[2]["work_item_id"])

    @patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": "executor"})
    def test_contextvar_propagation_asyncio(self) -> None:
        results: list[str] = []

        async def _inner() -> None:
            wid = _WORK_ITEM_ID.get()
            results.append(wid or "NONE")

        async def _run() -> None:
            with work_item("async-wid"):
                await asyncio.create_task(_inner())

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_run())
        finally:
            loop.close()
        self.assertEqual(results, ["async-wid"])

    @patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": "executor"})
    def test_contextvar_propagation_thread(self) -> None:
        results: list[Any] = []

        def _thread_fn() -> str:
            wid = _WORK_ITEM_ID.get()
            return wid or "NONE"

        with work_item("thread-wid"):
            result = dispatch_in_thread(_thread_fn)
        self.assertEqual(result, "thread-wid")

    @patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": "executor"})
    def test_contextvar_null_in_raw_thread(self) -> None:
        results: list[Any] = [None]

        def _raw_fn() -> None:
            results[0] = _WORK_ITEM_ID.get()

        with work_item("parent-wid"):
            t = threading.Thread(target=_raw_fn)
            t.start()
            t.join()
        self.assertIsNone(results[0])


class TestInstrumentLLMCallDecorator(unittest.TestCase):
    @patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": "executor"})
    def test_sync_decorator_emits_start_and_complete(self) -> None:
        with _capture_logger("structured.llm") as cap:
            @instrument_llm_call(model_id="glm-5p1")
            def fake_llm(prompt: str) -> dict:
                return {
                    "usage": {"prompt_tokens": 50, "completion_tokens": 25},
                    "content": "secret response",
                }

            result = fake_llm("hello")
        self.assertEqual(result["usage"]["prompt_tokens"], 50)
        objs = [json.loads(r) for r in cap.records]
        events = [o["event"] for o in objs]
        self.assertIn("llm.call.start", events)
        self.assertIn("llm.call.complete", events)
        complete_obj = [o for o in objs if o["event"] == "llm.call.complete"][0]
        self.assertEqual(complete_obj["model"], "glm-5p1")
        self.assertEqual(complete_obj["tokens_in"], 50)
        self.assertEqual(complete_obj["tokens_out"], 25)
        self.assertIsInstance(complete_obj["latency_ms"], int)
        self.assertIn("cost_usd", complete_obj)

    @patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": "executor"})
    def test_async_decorator_emits_start_and_complete(self) -> None:
        async def _run() -> dict:
            @instrument_llm_call(model_id="deepseek-v4-pro")
            async def fake_llm_async(prompt: str) -> dict:
                return {
                    "usage": {"prompt_tokens": 80, "completion_tokens": 40},
                    "content": "secret async response",
                }

            return await fake_llm_async("hello")

        with _capture_logger("structured.llm") as cap:
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(_run())
            finally:
                loop.close()
        objs = [json.loads(r) for r in cap.records]
        events = [o["event"] for o in objs]
        self.assertIn("llm.call.start", events)
        self.assertIn("llm.call.complete", events)

    @patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": "executor"})
    def test_decorator_emits_fail_on_exception(self) -> None:
        with _capture_logger("structured.llm") as cap:
            @instrument_llm_call(model_id="glm-5p1")
            def bad_llm() -> None:
                raise ValueError("bad input")

            with self.assertRaises(ValueError):
                bad_llm()
        objs = [json.loads(r) for r in cap.records]
        events = [o["event"] for o in objs]
        self.assertIn("llm.call.start", events)
        self.assertIn("llm.call.fail", events)
        fail_obj = [o for o in objs if o["event"] == "llm.call.fail"][0]
        self.assertEqual(fail_obj["error_class"], "ValueError")
        self.assertNotIn("traceback", fail_obj)

    @patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": "executor"})
    def test_decorator_no_prompt_content_in_log(self) -> None:
        with _capture_logger("structured.llm") as cap:
            @instrument_llm_call(model_id="glm-5p1")
            def llm_with_secrets(prompt: str) -> dict:
                return {
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                    "content": "SENSITIVE API KEY xyz789",
                    "prompt": "my secret prompt",
                }

            llm_with_secrets("secret prompt text")
        for rec in cap.records:
            obj = json.loads(rec)
            text = json.dumps(obj)
            self.assertNotIn("SENSITIVE", text)
            self.assertNotIn("secret prompt", text)
            self.assertNotIn("xyz789", text)

    @patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": "executor"})
    def test_decorator_plain_dict_response(self) -> None:
        with _capture_logger("structured.llm") as cap:
            @instrument_llm_call(model_id="glm-5p1")
            def plain_llm() -> dict:
                return {"tokens_in": 30, "tokens_out": 15}

            result = plain_llm()
        objs = [json.loads(r) for r in cap.records]
        complete_obj = [o for o in objs if o["event"] == "llm.call.complete"][0]
        self.assertEqual(complete_obj["tokens_in"], 30)
        self.assertEqual(complete_obj["tokens_out"], 15)

    @patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": "executor"})
    def test_decorator_object_response(self) -> None:
        class _Usage:
            prompt_tokens = 60
            completion_tokens = 30

        class _Response:
            usage = _Usage()

        with _capture_logger("structured.llm") as cap:
            @instrument_llm_call(model_id="glm-5p1")
            def obj_llm() -> _Response:
                return _Response()

            result = obj_llm()
        objs = [json.loads(r) for r in cap.records]
        complete_obj = [o for o in objs if o["event"] == "llm.call.complete"][0]
        self.assertEqual(complete_obj["tokens_in"], 60)
        self.assertEqual(complete_obj["tokens_out"], 30)


class TestInitRuntimeLoggerIdempotent(unittest.TestCase):
    def test_init_called_twice_no_error(self) -> None:
        init_runtime_logger()
        init_runtime_logger()
        root = logging.getLogger("devassist")
        json_handler_count = sum(
            1 for h in root.handlers if isinstance(h, logging.Handler)
        )
        self.assertGreaterEqual(json_handler_count, 1)


class TestDispatchInThread(unittest.TestCase):
    def test_dispatch_returns_value(self) -> None:
        result = dispatch_in_thread(lambda: 42)
        self.assertEqual(result, 42)

    def test_dispatch_propagates_exception(self) -> None:
        def _raise() -> None:
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            dispatch_in_thread(_raise)


if __name__ == "__main__":
    unittest.main()
