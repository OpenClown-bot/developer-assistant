"""Tests for dev-assist-escalation-surface Hermes custom skill.

Covers: 0 pending → 0 returned; 3 pending → 3 surfaced; router error
→ escalation stays pending, retry next tick; expire_old advances past
cutoff.  All tests are offline — router dispatch is a dependency-injected
fake.
"""

from __future__ import annotations

import sqlite3
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.escalations import (
    read_pending_escalations,
    write_escalation,
)
from developer_assistant.hermes_skills.dev_assist_escalation_surface.skill import (
    EscalationSurfaceSkill,
)
from developer_assistant.state_store import init_schema, open_store


def _make_router_dispatch():
    calls: list[tuple[str, str]] = []

    def dispatch(text: str, key: str) -> str:
        calls.append((text, key))
        return f"msg-{len(calls)}"

    return dispatch, calls


def _make_failing_router_dispatch():
    def dispatch(text: str, key: str) -> str:
        raise RuntimeError("network error")

    return dispatch


class EscalationSurfaceZeroPendingTests(unittest.TestCase):
    def setUp(self):
        self.db = open_store(":memory:")
        init_schema(self.db)
        self.dispatch, self.calls = _make_router_dispatch()
        self.skill = EscalationSurfaceSkill(
            db=self.db,
            router_dispatch=self.dispatch,
        )

    def tearDown(self):
        self.db.close()

    def test_zero_pending_returns_zero(self):
        result = self.skill.surface_pending("2026-06-01T00:00:00")
        self.assertEqual(result, 0)
        self.assertEqual(len(self.calls), 0)


class EscalationSurfaceThreePendingTests(unittest.TestCase):
    def setUp(self):
        self.db = open_store(":memory:")
        init_schema(self.db)
        self.dispatch, self.calls = _make_router_dispatch()
        self.skill = EscalationSurfaceSkill(
            db=self.db,
            router_dispatch=self.dispatch,
        )

        for i in range(1, 4):
            write_escalation(
                self.db,
                originating_runtime="executor",
                trigger_kind="paid:pr_workflow_merge",
                context=f"Context for escalation {i}",
                proposed_action=f"Merge PR #{i}",
                options=["Approve", "Deny"],
                recommended_default="Approve",
                impact=f"Adds feature module #{i}",
                urgency="medium",
                durable_artifact_target=f"docs/decisions/DEC-{i}.md",
            )

    def tearDown(self):
        self.db.close()

    def test_three_pending_three_surfaced(self):
        result = self.skill.surface_pending("2026-06-01T00:00:00")
        self.assertEqual(result, 3)
        self.assertEqual(len(self.calls), 3)

    def test_surfaced_escalations_not_re_surfaced(self):
        self.skill.surface_pending("2026-06-01T00:00:00")
        self.calls.clear()
        result = self.skill.surface_pending("2026-06-01T00:01:00")
        self.assertEqual(result, 0)
        self.assertEqual(len(self.calls), 0)

    def test_surface_format_includes_all_fields(self):
        self.skill.surface_pending("2026-06-01T00:00:00")
        text = self.calls[0][0]
        self.assertIn("Требуется решение основателя", text)
        self.assertIn("executor", text)
        self.assertIn("Merge PR #1", text)
        self.assertIn("medium", text)


class EscalationSurfaceRouterErrorTests(unittest.TestCase):
    def setUp(self):
        self.db = open_store(":memory:")
        init_schema(self.db)
        self.skill = EscalationSurfaceSkill(
            db=self.db,
            router_dispatch=_make_failing_router_dispatch(),
        )

        write_escalation(
            self.db,
            originating_runtime="executor",
            trigger_kind="paid:pr_workflow_merge",
            context="Should stay pending",
            proposed_action="Merge PR",
            options=["Approve", "Deny"],
            recommended_default="Approve",
            impact="Feature",
            urgency="high",
            durable_artifact_target="docs/decisions/DEC-RETRY.md",
        )

    def tearDown(self):
        self.db.close()

    def test_router_error_escalation_stays_pending(self):
        result = self.skill.surface_pending("2026-06-01T00:00:00")
        self.assertEqual(result, 0)

        pending = read_pending_escalations(self.db, statuses=["pending"])
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["status"], "pending")


class EscalationExpireOldTests(unittest.TestCase):
    def setUp(self):
        self.db = open_store(":memory:")
        init_schema(self.db)
        self.dispatch, self.calls = _make_router_dispatch()
        self.skill = EscalationSurfaceSkill(
            db=self.db,
            router_dispatch=self.dispatch,
        )

        write_escalation(
            self.db,
            originating_runtime="executor",
            trigger_kind="paid:concept_deviation",
            context="Old escalation",
            proposed_action="Rethink approach",
            options=["Keep", "Scrap"],
            recommended_default="Keep",
            impact="Architecture",
            urgency="low",
            durable_artifact_target="docs/decisions/DEC-OLD.md",
        )

    def tearDown(self):
        self.db.close()

    def test_expire_old_advances_past_cutoff(self):
        self.db.execute(
            "UPDATE escalations SET created_at = ? WHERE status = 'pending'",
            ((datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),),
        )
        self.db.commit()

        expired = self.skill.expire_old("2026-06-01T00:00:00")
        self.assertEqual(expired, 1)

        pending = read_pending_escalations(self.db, statuses=["pending"])
        self.assertEqual(len(pending), 0)


class EscalationSurfaceRuntimeLoadoutTests(unittest.TestCase):
    def setUp(self):
        self.db = open_store(":memory:")
        init_schema(self.db)
        self.dispatch, self.calls = _make_router_dispatch()

    def tearDown(self):
        self.db.close()

    def test_runtime_loadout_is_orchestrator_only(self):
        skill = EscalationSurfaceSkill(
            db=self.db,
            router_dispatch=self.dispatch,
        )
        self.assertEqual(skill.runtime_loadout, "orchestrator-only")


if __name__ == "__main__":
    unittest.main()