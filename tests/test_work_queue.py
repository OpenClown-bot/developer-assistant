"""Tests for developer_assistant.work_queue.

Uses stdlib unittest and in-memory sqlite. No real tokens, PATs,
production hostnames, or bash subprocesses.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import threading
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
        self.assertEqual(id2, id1)
        rows = read_work_items_by_role(self.conn, "executor")
        self.assertEqual(len(rows), 1)

    def test_no_dedup_key_allows_duplicate_rows(self) -> None:
        id1 = write_work_item(
            self.conn,
            target_role="executor",
            kind="ticket_implementation",
            payload={"ticket_id": "TKT-020"},
        )
        id2 = write_work_item(
            self.conn,
            target_role="executor",
            kind="ticket_implementation",
            payload={"ticket_id": "TKT-020"},
        )
        self.assertNotEqual(id1, id2)
        rows = read_work_items_by_role(self.conn, "executor")
        self.assertEqual(len(rows), 2)

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

    def test_lease_minutes_custom(self) -> None:
        write_work_item(
            self.conn,
            target_role="executor",
            kind="test",
            payload={},
        )
        row = claim_work_item(
            self.conn,
            runtime_id="executor-01",
            target_role="executor",
            lease_minutes=60,
        )
        self.assertIsNotNone(row)


class TestClaimWorkItemConcurrency(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_concurrent.db")
        self.conn = state_store.open_store(self.db_path)
        write_work_item(
            self.conn,
            target_role="executor",
            kind="ticket_implementation",
            payload={"ticket_id": "TKT-020"},
        )

    def tearDown(self) -> None:
        self.conn.close()
        os.unlink(self.db_path)
        os.rmdir(self.tmpdir)

    def test_only_one_thread_claims(self) -> None:
        results: list[object] = [None, None]
        barrier = threading.Barrier(2, timeout=5)

        def claim(idx: int, runtime_id: str) -> None:
            conn2 = state_store.open_store(self.db_path)
            barrier.wait()
            row = claim_work_item(conn2, runtime_id=runtime_id, target_role="executor")
            results[idx] = row
            conn2.close()

        t1 = threading.Thread(target=claim, args=(0, "executor-01"))
        t2 = threading.Thread(target=claim, args=(1, "executor-02"))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        claimed = [r for r in results if r is not None]
        nones = [r for r in results if r is None]
        self.assertEqual(len(claimed), 1)
        self.assertEqual(len(nones), 1)


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

    def test_release_increment_attempts_stays_pending(self) -> None:
        item_id = write_work_item(
            self.conn,
            target_role="executor",
            kind="test",
            payload={},
            max_attempts=3,
        )
        claim_work_item(self.conn, runtime_id="executor-01", target_role="executor")
        row = release_work_item(self.conn, item_id=item_id, increment_attempts=True)
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["attempt_count"], 1)

    def test_release_increment_attempts_reaches_failed(self) -> None:
        item_id = write_work_item(
            self.conn,
            target_role="executor",
            kind="test",
            payload={},
            max_attempts=1,
        )
        claim_work_item(self.conn, runtime_id="executor-01", target_role="executor")
        row = release_work_item(self.conn, item_id=item_id, increment_attempts=True)
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["attempt_count"], 1)


class TestDedupKeyLifecycle(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_dedup_key_rejected_while_claimed(self) -> None:
        id1 = write_work_item(
            self.conn,
            target_role="executor",
            kind="test",
            payload={},
            dedup_key="dk-001",
        )
        claim_work_item(self.conn, runtime_id="executor-01", target_role="executor")
        id2 = write_work_item(
            self.conn,
            target_role="executor",
            kind="test",
            payload={},
            dedup_key="dk-001",
        )
        self.assertEqual(id2, id1)

    def test_dedup_key_rejected_while_failed(self) -> None:
        id1 = write_work_item(
            self.conn,
            target_role="executor",
            kind="test",
            payload={},
            dedup_key="dk-002",
            max_attempts=1,
        )
        claim_work_item(self.conn, runtime_id="executor-01", target_role="executor")
        release_work_item(self.conn, item_id=id1, increment_attempts=True)
        id2 = write_work_item(
            self.conn,
            target_role="executor",
            kind="test",
            payload={},
            dedup_key="dk-002",
        )
        self.assertEqual(id2, id1)

    def test_dedup_key_allowed_after_completed(self) -> None:
        id1 = write_work_item(
            self.conn,
            target_role="executor",
            kind="test",
            payload={},
            dedup_key="dk-003",
        )
        claim_work_item(self.conn, runtime_id="executor-01", target_role="executor")
        complete_work_item(self.conn, item_id=id1, result={})
        id2 = write_work_item(
            self.conn,
            target_role="executor",
            kind="test",
            payload={},
            dedup_key="dk-003",
        )
        self.assertNotEqual(id2, id1)
        self.assertGreater(id2, 0)
        rows = read_work_items_by_role(self.conn, "executor")
        self.assertEqual(len(rows), 2)


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
