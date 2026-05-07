"""Tests for developer_assistant.observability.omniroute_header.

Covers:
- inject_work_item_header with work_item_id set/unset
- build_headers_with_work_item with work_item_id set/unset
"""

from __future__ import annotations

import os
import sys
import unittest
from typing import Any
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from developer_assistant.observability.structured_logger import (
    _WORK_ITEM_ID,
    work_item,
)
from developer_assistant.observability.omniroute_header import (
    build_headers_with_work_item,
    inject_work_item_header,
)


class TestInjectWorkItemHeader(unittest.TestCase):
    def test_header_present_when_work_item_id_set(self) -> None:
        req = MagicMock()
        req.headers = {}
        with work_item("WI-123"):
            inject_work_item_header(req)
        self.assertEqual(req.headers.get("X-DEVASSIST-Work-Item-Id"), "WI-123")

    def test_header_absent_when_work_item_id_none(self) -> None:
        req = MagicMock()
        req.headers = {}
        token = _WORK_ITEM_ID.set(None)
        try:
            inject_work_item_header(req)
        finally:
            _WORK_ITEM_ID.reset(token)
        self.assertNotIn("X-DEVASSIST-Work-Item-Id", req.headers)


class TestBuildHeadersWithWorkItem(unittest.TestCase):
    def test_adds_header_when_work_item_id_set(self) -> None:
        with work_item("WI-456"):
            result = build_headers_with_work_item({"Accept": "application/json"})
        self.assertEqual(result["X-DEVASSIST-Work-Item-Id"], "WI-456")
        self.assertEqual(result["Accept"], "application/json")

    def test_returns_original_dict_when_work_item_id_none(self) -> None:
        token = _WORK_ITEM_ID.set(None)
        try:
            result = build_headers_with_work_item({"Accept": "application/json"})
        finally:
            _WORK_ITEM_ID.reset(token)
        self.assertNotIn("X-DEVASSIST-Work-Item-Id", result)
        self.assertEqual(result["Accept"], "application/json")


if __name__ == "__main__":
    unittest.main()
