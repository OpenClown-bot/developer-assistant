"""Tests for developer_assistant.escalations.

Uses stdlib unittest and in-memory sqlite. No real tokens, PATs,
production hostnames, or bash subprocesses.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant import state_store
from developer_assistant.escalations import (
    expire_old_escalations,
    mark_escalation_surfaced,
    read_pending_escalations,
    resolve_escalation,
    write_escalation,
)


class TestWriteEscalation(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_insert_returns_id(self) -> None:
        esc_id = write_escalation(
            self.conn,
            originating_runtime="executor",
            trigger_kind="deterministic_rule:deploy:merge_pr",
            context="About to call GitHub merge API on PR #42.",
            proposed_action="Merge PR #42 to main",
            options=["approve", "deny"],
            recommended_default="deny",
            impact="PR #42 will be merged into main branch",
            urgency="high",
            durable_artifact_target="docs/tickets/TKT-042.md",
        )
        self.assertIsInstance(esc_id, int)
        self.assertGreater(esc_id, 0)

    def test_insert_defaults_to_pending_status(self) -> None:
        esc_id = write_escalation(
            self.conn,
            originating_runtime="architect",
            trigger_kind="llm_classifier",
            context="Concept deviation detected.",
            proposed_action="Switch from Hermes to LangChain.",
            options=["approve", "deny"],
            recommended_default="deny",
            impact="Tech stack pivot",
            urgency="medium",
            durable_artifact_target="docs/questions/q-001.md",
        )
        rows = read_pending_escalations(self.conn)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], esc_id)
        self.assertEqual(rows[0]["status"], "pending")
        self.assertEqual(rows[0]["originating_runtime"], "architect")

    def test_related_work_item(self) -> None:
        from developer_assistant.work_queue import write_work_item, claim_work_item
        item_id = write_work_item(
            self.conn,
            target_role="executor",
            kind="ticket_implementation",
            payload={"ticket_id": "TKT-030"},
        )
        esc_id = write_escalation(
            self.conn,
            originating_runtime="executor",
            originating_work_item_id=item_id,
            trigger_kind="deterministic_rule:deploy:merge_pr",
            context="About to merge.",
            proposed_action="Merge PR",
            options=["approve", "deny"],
            recommended_default="deny",
            impact="PR merged",
            urgency="high",
            durable_artifact_target="docs/tickets/TKT-030.md",
        )
        row = read_pending_escalations(self.conn)[0]
        self.assertEqual(row["originating_work_item_id"], item_id)


class TestReadPendingEscalations(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def _write(self, urgency: str, status: str = "pending") -> None:
        esc_id = write_escalation(
            self.conn,
            originating_runtime="executor",
            trigger_kind="test",
            context="test",
            proposed_action="test",
            options=["approve", "deny"],
            recommended_default="deny",
            impact="test",
            urgency=urgency,
            durable_artifact_target="docs/tickets/TKT-999.md",
        )
        if status != "pending":
            resolve_escalation(
                self.conn,
                escalation_id=esc_id,
                verdict=status,
                founder_response="test",
            )

    def test_ordered_by_urgency_then_id(self) -> None:
        self._write("low")
        self._write("high")
        self._write("medium")
        rows = read_pending_escalations(self.conn)
        self.assertEqual([r["urgency"] for r in rows], ["high", "medium", "low"])

    def test_resolved_not_returned(self) -> None:
        self._write("high", status="approved")
        self._write("medium", status="denied")
        rows = read_pending_escalations(self.conn)
        self.assertEqual(len(rows), 0)

    def test_limit_respected(self) -> None:
        for _ in range(5):
            self._write("high")
        rows = read_pending_escalations(self.conn, limit=3)
        self.assertEqual(len(rows), 3)


class TestMarkEscalationSurfaced(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_surfaced_updates_status_and_telegram_id(self) -> None:
        esc_id = write_escalation(
            self.conn,
            originating_runtime="executor",
            trigger_kind="test",
            context="test",
            proposed_action="test",
            options=["approve", "deny"],
            recommended_default="deny",
            impact="test",
            urgency="high",
            durable_artifact_target="docs/tickets/TKT-999.md",
        )
        row = mark_escalation_surfaced(
            self.conn,
            escalation_id=esc_id,
            telegram_message_id="msg-12345",
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "surfaced")
        self.assertIsNotNone(row["surfaced_at"])
        self.assertEqual(row["telegram_message_id"], "msg-12345")

    def test_surfaced_nonexistent_returns_none(self) -> None:
        row = mark_escalation_surfaced(self.conn, escalation_id=9999, telegram_message_id="x")
        self.assertIsNone(row)

    def test_already_surfaced_returns_none(self) -> None:
        esc_id = write_escalation(
            self.conn,
            originating_runtime="executor",
            trigger_kind="test",
            context="test",
            proposed_action="test",
            options=["approve", "deny"],
            recommended_default="deny",
            impact="test",
            urgency="high",
            durable_artifact_target="docs/tickets/TKT-999.md",
        )
        mark_escalation_surfaced(self.conn, escalation_id=esc_id)
        row = mark_escalation_surfaced(self.conn, escalation_id=esc_id)
        self.assertIsNone(row)


class TestResolveEscalation(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_approve_updates_status_and_response(self) -> None:
        esc_id = write_escalation(
            self.conn,
            originating_runtime="executor",
            trigger_kind="test",
            context="test",
            proposed_action="test",
            options=["approve", "deny"],
            recommended_default="deny",
            impact="test",
            urgency="high",
            durable_artifact_target="docs/tickets/TKT-999.md",
        )
        row = resolve_escalation(
            self.conn,
            escalation_id=esc_id,
            verdict="approved",
            founder_response="Approved - proceed.",
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "approved")
        self.assertIsNotNone(row["resolved_at"])
        self.assertEqual(row["founder_response"], "Approved - proceed.")

    def test_deny_updates_status(self) -> None:
        esc_id = write_escalation(
            self.conn,
            originating_runtime="architect",
            trigger_kind="test",
            context="test",
            proposed_action="test",
            options=["approve", "deny"],
            recommended_default="approve",
            impact="test",
            urgency="low",
            durable_artifact_target="docs/tickets/TKT-999.md",
        )
        row = resolve_escalation(
            self.conn,
            escalation_id=esc_id,
            verdict="denied",
            founder_response="Denied - use alternative approach.",
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "denied")

    def test_invalid_verdict_raises(self) -> None:
        with self.assertRaises(ValueError):
            resolve_escalation(
                self.conn,
                escalation_id=1,
                verdict="invalid",
                founder_response="test",
            )

    def test_resolve_surfaced_esc(self) -> None:
        esc_id = write_escalation(
            self.conn,
            originating_runtime="executor",
            trigger_kind="test",
            context="test",
            proposed_action="test",
            options=["approve", "deny"],
            recommended_default="deny",
            impact="test",
            urgency="high",
            durable_artifact_target="docs/tickets/TKT-999.md",
        )
        mark_escalation_surfaced(self.conn, escalation_id=esc_id)
        row = resolve_escalation(
            self.conn,
            escalation_id=esc_id,
            verdict="approved",
            founder_response="OK",
        )
        self.assertIsNotNone(row)

    def test_resolve_nonexistent_returns_none(self) -> None:
        row = resolve_escalation(
            self.conn,
            escalation_id=9999,
            verdict="approved",
            founder_response="test",
        )
        self.assertIsNone(row)


class TestExpireOldEscalations(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = state_store.open_store(":memory:")

    def tearDown(self) -> None:
        self.conn.close()

    def test_expire_old_pending_returns_count(self) -> None:
        esc_id = write_escalation(
            self.conn,
            originating_runtime="executor",
            trigger_kind="test",
            context="test",
            proposed_action="test",
            options=["approve", "deny"],
            recommended_default="deny",
            impact="test",
            urgency="high",
            durable_artifact_target="docs/tickets/TKT-999.md",
        )
        self.conn.execute(
            "UPDATE escalations SET created_at = '2020-01-01T00:00:00+00:00' WHERE id = ?",
            (esc_id,),
        )
        self.conn.commit()
        count = expire_old_escalations(self.conn)
        self.assertEqual(count, 1)
        rows = read_pending_escalations(self.conn, statuses=["expired"])
        self.assertEqual(len(rows), 1)

    def test_expire_none_returns_zero(self) -> None:
        write_escalation(
            self.conn,
            originating_runtime="executor",
            trigger_kind="test",
            context="test",
            proposed_action="test",
            options=["approve", "deny"],
            recommended_default="deny",
            impact="test",
            urgency="high",
            durable_artifact_target="docs/tickets/TKT-999.md",
        )
        count = expire_old_escalations(self.conn)
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()