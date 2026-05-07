from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant import state_store
from developer_assistant.hermes_plugins.dev_assist_work_queue.tools import (
    work_queue_claim,
    work_queue_complete,
    work_queue_release,
    work_queue_write,
)


class TestClaimOnEmptyQueue(unittest.TestCase):
    def setUp(self):
        self.conn = state_store.open_store(":memory:")

    def tearDown(self):
        self.conn.close()

    @patch.dict(os.environ, {"HERMES_DEVASSIST_ROLE": "executor"})
    def test_claim_returns_null(self):
        result = work_queue_claim("executor", conn=self.conn)
        self.assertEqual(result["status"], "ok")
        self.assertIsNone(result["work_item"])


class TestClaimWithRoleMismatch(unittest.TestCase):
    def setUp(self):
        self.conn = state_store.open_store(":memory:")

    def tearDown(self):
        self.conn.close()

    @patch.dict(os.environ, {"HERMES_DEVASSIST_ROLE": "executor"})
    def test_claim_role_mismatch_fails(self):
        result = work_queue_claim("planner", conn=self.conn)
        self.assertEqual(result["status"], "error")
        self.assertIn("mismatch", result["error"].lower())


class TestCompleteWorkItem(unittest.TestCase):
    def setUp(self):
        self.conn = state_store.open_store(":memory:")

    def tearDown(self):
        self.conn.close()

    @patch.dict(os.environ, {"HERMES_DEVASSIST_ROLE": "executor"})
    def test_complete_moves_to_completed(self):
        write_result = work_queue_write(
            target_role="executor",
            kind="ticket_implementation",
            payload={"ticket": "TKT-023"},
            conn=self.conn,
        )
        item_id = write_result["id"]
        work_queue_claim("executor", conn=self.conn)
        result = work_queue_complete(item_id, {"status": "done"}, conn=self.conn)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["work_item"]["status"], "completed")


class TestReleaseWorkItem(unittest.TestCase):
    def setUp(self):
        self.conn = state_store.open_store(":memory:")

    def tearDown(self):
        self.conn.close()

    @patch.dict(os.environ, {"HERMES_DEVASSIST_ROLE": "executor"})
    def test_release_returns_to_pending(self):
        write_result = work_queue_write(
            target_role="executor",
            kind="ticket_implementation",
            payload={"ticket": "TKT-023"},
            conn=self.conn,
        )
        item_id = write_result["id"]
        work_queue_claim("executor", conn=self.conn)
        result = work_queue_release(item_id, conn=self.conn)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["work_item"]["status"], "pending")


class TestReleaseWithIncrementAttempts(unittest.TestCase):
    def setUp(self):
        self.conn = state_store.open_store(":memory:")

    def tearDown(self):
        self.conn.close()

    @patch.dict(os.environ, {"HERMES_DEVASSIST_ROLE": "executor"})
    def test_release_increments_attempt_count(self):
        write_result = work_queue_write(
            target_role="executor",
            kind="ticket_implementation",
            payload={"ticket": "TKT-023"},
            conn=self.conn,
        )
        item_id = write_result["id"]
        work_queue_claim("executor", conn=self.conn)
        result = work_queue_release(item_id, increment_attempts=True, conn=self.conn)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["work_item"]["attempt_count"], 1)


class TestWriteInsertsAndReturnsId(unittest.TestCase):
    def setUp(self):
        self.conn = state_store.open_store(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_write_inserts(self):
        result = work_queue_write(
            target_role="executor",
            kind="ticket_implementation",
            payload={"ticket": "TKT-023"},
            conn=self.conn,
        )
        self.assertEqual(result["status"], "ok")
        self.assertIsInstance(result["id"], int)


class TestWriteWithDuplicateDedupKey(unittest.TestCase):
    def setUp(self):
        self.conn = state_store.open_store(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_duplicate_dedup_key_returns_existing_id(self):
        r1 = work_queue_write(
            target_role="executor",
            kind="ticket_implementation",
            payload={"ticket": "TKT-023"},
            dedup_key="TKT-023:impl",
            conn=self.conn,
        )
        r2 = work_queue_write(
            target_role="executor",
            kind="ticket_implementation",
            payload={"ticket": "TKT-023"},
            dedup_key="TKT-023:impl",
            conn=self.conn,
        )
        self.assertEqual(r1["id"], r2["id"])


class TestWriteInvalidTargetRole(unittest.TestCase):
    def setUp(self):
        self.conn = state_store.open_store(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_invalid_target_role_rejected(self):
        result = work_queue_write(
            target_role="invalid_role",
            kind="test",
            payload={},
            conn=self.conn,
        )
        self.assertEqual(result["status"], "error")


class TestWriteAllowsOrchestratorRole(unittest.TestCase):
    def setUp(self):
        self.conn = state_store.open_store(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_orchestrator_accepted_by_plugin_validation(self):
        result = work_queue_write(
            target_role="orchestrator",
            kind="test",
            payload={},
            conn=self.conn,
        )
        self.assertNotIn("Invalid target_role", result.get("error", ""))


if __name__ == "__main__":
    unittest.main()
