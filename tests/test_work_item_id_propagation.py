"""Tests for work_item_id propagation across simulated runtime pipeline.

Covers:
- Synthetic four-step pipeline (Orchestrator-create → Architect-claim →
  Executor-claim → Reviewer-claim) where a single work_item_id appears
  in all four log streams.
- Parent-child case: parent work_item_id and child work_item_id are
  distinct; child's log lines carry child id; parent is recoverable
  via the parent_id field (modeled as a log extra).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import unittest
from typing import Any
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from developer_assistant.observability.structured_logger import (
    _JsonFormatter,
    get_logger,
    init_runtime_logger,
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


class TestFourStepPipeline(unittest.TestCase):
    @patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": "executor"})
    def test_single_work_item_across_four_runtimes(self) -> None:
        init_runtime_logger()
        wid = "WI-PIPELINE-001"
        all_log_lines: list[dict[str, Any]] = []

        roles = ["orchestrator", "architect", "executor", "reviewer"]
        for role in roles:
            handler = _JsonCapture()
            handler.setLevel(logging.DEBUG)
            logger = get_logger(f"pipeline.{role}")
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
            try:
                with work_item(wid):
                    with patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": role}):
                        logger.info(
                            f"{role} processing work item",
                            extra={
                                "event": "work_item.process",
                                "_extra_payload": {
                                    "runtime_role": role,
                                },
                            },
                        )
            finally:
                logger.removeHandler(handler)
            for rec in handler.records:
                obj = json.loads(rec)
                obj["_simulated_role"] = role
                all_log_lines.append(obj)

        self.assertEqual(len(all_log_lines), 4)
        for entry in all_log_lines:
            self.assertEqual(
                entry.get("work_item_id"), wid,
                f"work_item_id mismatch for role {entry['_simulated_role']}"
            )

    @patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": "executor"})
    def test_parent_child_distinct_work_item_ids(self) -> None:
        init_runtime_logger()
        parent_wid = "WI-PARENT-001"
        child_wid = "WI-CHILD-001"

        handler = _JsonCapture()
        handler.setLevel(logging.DEBUG)
        logger = get_logger("pipeline.parent_child")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            with work_item(parent_wid):
                logger.info(
                    "parent work",
                    extra={
                        "event": "work_item.process",
                        "_extra_payload": {
                            "parent_work_item_id": None,
                        },
                    },
                )
                with work_item(child_wid):
                    logger.info(
                        "child work",
                        extra={
                            "event": "work_item.process",
                            "_extra_payload": {
                                "parent_work_item_id": parent_wid,
                            },
                        },
                    )
                logger.info(
                    "parent resumed",
                    extra={
                        "event": "work_item.process",
                        "_extra_payload": {},
                    },
                )
        finally:
            logger.removeHandler(handler)

        objs = [json.loads(r) for r in handler.records]
        self.assertEqual(len(objs), 3)

        self.assertEqual(objs[0]["work_item_id"], parent_wid)

        self.assertEqual(objs[1]["work_item_id"], child_wid)
        self.assertEqual(objs[1].get("parent_work_item_id"), parent_wid)

        self.assertEqual(objs[2]["work_item_id"], parent_wid)

    @patch.dict(os.environ, {"DEVASSIST_RUNTIME_ROLE": "executor"})
    def test_nested_work_items_correct_scope(self) -> None:
        init_runtime_logger()

        handler = _JsonCapture()
        handler.setLevel(logging.DEBUG)
        logger = get_logger("pipeline.nested")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            logger.info(
                "no work item",
                extra={"event": "test.no_wid", "_extra_payload": {}},
            )
            with work_item("outer"):
                logger.info(
                    "outer scope",
                    extra={"event": "test.outer", "_extra_payload": {}},
                )
                with work_item("inner"):
                    logger.info(
                        "inner scope",
                        extra={"event": "test.inner", "_extra_payload": {}},
                    )
                logger.info(
                    "back to outer",
                    extra={"event": "test.outer_back", "_extra_payload": {}},
                )
            logger.info(
                "no work item again",
                extra={"event": "test.no_wid2", "_extra_payload": {}},
            )
        finally:
            logger.removeHandler(handler)

        objs = [json.loads(r) for r in handler.records]
        self.assertIsNone(objs[0]["work_item_id"])
        self.assertEqual(objs[1]["work_item_id"], "outer")
        self.assertEqual(objs[2]["work_item_id"], "inner")
        self.assertEqual(objs[3]["work_item_id"], "outer")
        self.assertIsNone(objs[4]["work_item_id"])


if __name__ == "__main__":
    unittest.main()
