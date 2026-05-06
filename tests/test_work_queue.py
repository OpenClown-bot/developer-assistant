"""Tests for developer_assistant.work_queue.

Uses stdlib unittest and in-memory sqlite. No real tokens, PATs,
production hostnames, or bash subprocesses.
"""

from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant import state_store
from developer_assistant.work_queue import (
    claim_work_item,
    complete_work_item,
    read_work_items_by_role,
    reclaim_expired_leases,
    release_work_item,
    write_work_item,
)


class TestWriteWorkItem(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_insert_returns_id(self) -> None:
        item_id = write_work_item(
            self.conn,
            target_role="executor",
            kind="ticket_implementation",
            payload={"ticket_id": "TKT-020", "branch": "ticket/tkt-020"},
        )
        self.assertIsInstance(item_id, int)
        self.assertGreater(item_id, 0)

    def test_insert_creates_pending_status(self) -> None:
        item_id = write_work_item(
            self.conn,
            target_role="architect",
            kind="architect_pass",
            payload={"project_id": "proj-alpha"},
            priority=10,
        )
        rows = read_work_items_by_role(self.conn, "architect")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], item_id)
        self.assertEqual(rows[0]["status"], "pending")
        self.assertEqual(rows[0]["target_role"], "architect")
        self.assertEqual(rows[0]["priority"], 10)

    def test_dedup_key_prevents_duplicate(self) -> None:
        id1 = write_work_item(
            self.conn,
            target_role="executor",
            kind="ticket_implementation",
            payload={"ticket_id": "TKT-020"},
            dedup_key="ticket-implementation:TKT-020",
        )
        id2 = write_work_item(
            self.conn,
            target_role="executor",
            kind="ticket_implementation",
            payload={"ticket_id": "TKT-020"},
            dedup_key="ticket-implementation:TKT-020",
        )
        self.assertGreater(id1, 0)
        self.assertEqual(id2, -1)
        rows = read_work_items_by_role(self.conn, "executor")
        self.assertEqual(len(rows), 1)

    def test_originating_run_id(self) -> None:
        state_store.upsert_project_binding(
            self.conn,
            chat_key="chat:proj-alpha",
            repo_url="https://github.com/test/test",
        )
        state_store.upsert_hermes_run(
            self.conn,
            run_id="run-001",
            project_key="chat:proj-alpha",
            status="in_progress",
        )
        item_id = write_work_item(
            self.conn,
            target_role="executor",
            kind="ticket_implementation",
            payload={"ticket_id": "TKT-020"},
            originating_run_id="run-001",
        )
        row = read_work_items_by_role(self.conn, "executor")[0]
        self.assertEqual(row["originating_run_id"], "run-001")


class TestClaimWorkItem(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_claim_returns_row(self) -> None:
        item_id = write_work_item(
            self.conn,
            target_role="executor",
            kind="ticket_implementation",
            payload={"ticket_id": "TKT-021"},
        )
        row = claim_work_item(self.conn, runtime_id="executor-01", target_role="executor")
        self.assertIsNotNone(row)
        self.assertEqual(row["id"], item_id)
        self.assertEqual(row["status"], "claimed")
        self.assertEqual(row["claimed_by_runtime"], "executor-01")
        self.assertIsNotNone(row["claimed_at"])
        self.assertIsNotNone(row["claim_lease_until"])

    def test_claim_returns_none_when_empty(self) -> None:
        row = claim_work_item(self.conn, runtime_id="executor-01", target_role="planner")
        self.assertIsNone(row)

    def test_claim_highest_priority_first(self) -> None:
        id_low = write_work_item(
            self.conn,
            target_role="architect",
            kind="architect_pass",
            payload={},
            priority=80,
        )
        id_high = write_work_item(
            self.conn,
            target_role="architect",
            kind="architect_pass",
            payload={},
            priority=5,
        )
        row = claim_work_item(self.conn, runtime_id="architect-01", target_role="architect")
        self.assertEqual(row["id"], id_high)

    def test_claimed_item_not_claimable_by_another(self) -> None:
        write_work_item(
            self.conn,
            target_role="reviewer",
            kind="ticket_review",
            payload={},
        )
        claim_work_item(self.conn, runtime_id="reviewer-01", target_role="reviewer")
        row2 = claim_work_item(self.conn, runtime_id="reviewer-02", target_role="reviewer")
        self.assertIsNone(row2)

    def test_completed_item_not_claimable(self) -> None:
        item_id = write_work_item(
            self.conn,
            target_role="planner",
            kind="prd_intake",
            payload={},
        )
        claim_work_item(self.conn, runtime_id="planner-01", target_role="planner")
        complete_work_item(self.conn, item_id=item_id, result={})
        row = claim_work_item(self.conn, runtime_id="planner-02", target_role="planner")
        self.assertIsNone(row)


class TestCompleteWorkItem(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_complete_returns_updated_row(self) -> None:
        item_id = write_work_item(
            self.conn,
            target_role="executor",
            kind="ticket_implementation",
            payload={},
        )
        claim_work_item(self.conn, runtime_id="executor-01", target_role="executor")
        row = complete_work_item(self.conn, item_id=item_id, result={"files_changed": ["a.py"]})
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "completed")
        self.assertIsNotNone(row["completed_at"])
        self.assertIsNone(row["claim_lease_until"])
        self.assertIsNotNone(row["result_json"])

    def test_complete_nonexistent_returns_none(self) -> None:
        row = complete_work_item(self.conn, item_id=9999, result={})
        self.assertIsNone(row)

    def test_complete_unclaimed_returns_none(self) -> None:
        item_id = write_work_item(
            self.conn,
            target_role="executor",
            kind="ticket_implementation",
            payload={},
        )
        row = complete_work_item(self.conn, item_id=item_id, result={})
        self.assertIsNone(row)


class TestReleaseWorkItem(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_release_returns_pending_row(self) -> None:
        item_id = write_work_item(
            self.conn,
            target_role="executor",
            kind="ticket_implementation",
            payload={},
        )
        claim_work_item(self.conn, runtime_id="executor-01", target_role="executor")
        row = release_work_item(self.conn, item_id=item_id)
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "pending")
        self.assertIsNone(row["claimed_by_runtime"])

    def test_release_nonexistent_returns_none(self) -> None:
        row = release_work_item(self.conn, item_id=9999)
        self.assertIsNone(row)

    def test_released_item_claimable_again(self) -> None:
        item_id = write_work_item(
            self.conn,
            target_role="planner",
            kind="prd_intake",
            payload={},
        )
        claim_work_item(self.conn, runtime_id="planner-01", target_role="planner")
        release_work_item(self.conn, item_id=item_id)
        row = claim_work_item(self.conn, runtime_id="planner-02", target_role="planner")
        self.assertIsNotNone(row)
        self.assertEqual(row["id"], item_id)


class TestReclaimExpiredLeases(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_reclaim_returns_count(self) -> None:
        write_work_item(self.conn, target_role="executor", kind="test", payload={})
        claim_work_item(self.conn, runtime_id="executor-01", target_role="executor")
        self.conn.execute(
            "UPDATE work_items SET claim_lease_until = '2020-01-01T00:00:00+00:00' WHERE status = 'claimed'"
        )
        self.conn.commit()
        count = reclaim_expired_leases(self.conn)
        self.assertEqual(count, 1)
        rows = read_work_items_by_role(self.conn, "executor", statuses=["pending"])
        self.assertEqual(len(rows), 1)

    def test_reclaim_none_expired_returns_zero(self) -> None:
        write_work_item(self.conn, target_role="executor", kind="test", payload={})
        claim_work_item(self.conn, runtime_id="executor-01", target_role="executor")
        count = reclaim_expired_leases(self.conn)
        self.assertEqual(count, 0)


class TestReadWorkItemsByRole(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_filter_by_statuses(self) -> None:
        write_work_item(self.conn, target_role="executor", kind="test", payload={})
        claim_work_item(self.conn, runtime_id="executor-01", target_role="executor")
        rows = read_work_items_by_role(self.conn, "executor", statuses=["claimed"])
        self.assertEqual(len(rows), 1)
        rows = read_work_items_by_role(self.conn, "executor", statuses=["pending"])
        self.assertEqual(len(rows), 0)

    def test_empty_role(self) -> None:
        rows = read_work_items_by_role(self.conn, "planner")
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()