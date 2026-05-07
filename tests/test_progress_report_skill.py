"""Tests for dev-assist-progress-report Hermes custom skill.

Covers: report due → dispatched → mark_report_sent; not due → skipped;
GitHub unreachable → skip + log; first-time-due → dispatched;
multiple projects → independent dispatch.  All tests are offline —
PR fetcher and router dispatch are dependency-injected fakes.
"""

from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.hermes_skills.dev_assist_progress_report.skill import (
    ProgressReportSkill,
    TickResult,
)
from developer_assistant.state_store import init_schema, open_store


def _make_pr_fetcher(responses: dict[str, list[dict[str, str]]]):
    def fetch(owner: str, repo_url: str) -> list[dict[str, str]]:
        return responses.get(repo_url, [])
    return fetch


def _make_raising_pr_fetcher(error: Exception):
    def fetch(owner: str, repo_url: str) -> list[dict[str, str]]:
        raise error
    return fetch


def _make_router_dispatch():
    """Router fake that returns a synthetic message id."""
    calls: list[tuple[str, str]] = []

    def dispatch(text: str, project_key: str) -> str:
        calls.append((text, project_key))
        return f"msg-{len(calls)}"

    return dispatch, calls


def _insert_binding(db: sqlite3.Connection, chat_key: str, **kwargs):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        """INSERT OR REPLACE INTO project_bindings
           (chat_key, repo_url, repo_owner_name, workspace_path, phase, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            chat_key,
            kwargs.get("repo_url", "https://github.com/org/repo"),
            kwargs.get("repo_owner_name", "org"),
            kwargs.get("workspace_path", None),
            kwargs.get("phase", "active"),
            now,
        ),
    )
    db.commit()


class ProgressReportDueAndDispatchedTests(unittest.TestCase):
    def setUp(self):
        self.db = open_store(":memory:")
        init_schema(self.db)
        _insert_binding(self.db, "chat:proj-alpha", repo_url="https://github.com/org/alpha")

        self.dispatch, self.dispatch_calls = _make_router_dispatch()
        self.skill = ProgressReportSkill(
            db=self.db,
            pr_fetcher=_make_pr_fetcher({
                "https://github.com/org/alpha": [
                    {"title": "Add login", "status": "open"},
                    {"title": "Fix auth", "status": "merged"},
                ],
            }),
            router_dispatch=self.dispatch,
        )

    def tearDown(self):
        self.db.close()

    def test_report_due_dispatched_and_marked_sent(self):
        from datetime import datetime, timezone, timedelta
        now = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        result = self.skill.tick(now)
        self.assertEqual(result.reports_sent, 1)
        self.assertEqual(result.projects_checked, 1)
        self.assertEqual(result.projects_skipped, 0)
        self.assertEqual(len(self.dispatch_calls), 1)
        report_text = self.dispatch_calls[0][0]
        self.assertIn("github.com/org/alpha", report_text)
        self.assertIn("Add login", report_text)
        self.assertIn("Fix auth", report_text)


class ProgressReportNotDueTests(unittest.TestCase):
    def setUp(self):
        self.db = open_store(":memory:")
        init_schema(self.db)
        _insert_binding(self.db, "chat:proj-alpha", repo_url="https://github.com/org/alpha")

        self.dispatch, self.dispatch_calls = _make_router_dispatch()
        self.skill = ProgressReportSkill(
            db=self.db,
            pr_fetcher=_make_pr_fetcher({}),
            router_dispatch=self.dispatch,
        )

    def tearDown(self):
        self.db.close()

    def test_report_not_due_skipped(self):
        self.skill.tick("2026-01-01T00:00:00")
        self.dispatch_calls.clear()
        result = self.skill.tick("2026-01-01T00:29:00")
        self.assertEqual(result.reports_sent, 0)
        self.assertEqual(result.projects_skipped, 1)
        self.assertEqual(len(self.dispatch_calls), 0)


class ProgressReportGitHubUnreachableTests(unittest.TestCase):
    def setUp(self):
        self.db = open_store(":memory:")
        init_schema(self.db)
        _insert_binding(self.db, "chat:proj-beta", repo_url="https://github.com/org/beta")

        self.dispatch, self.dispatch_calls = _make_router_dispatch()
        self.skill = ProgressReportSkill(
            db=self.db,
            pr_fetcher=_make_raising_pr_fetcher(RuntimeError("timeout")),
            router_dispatch=self.dispatch,
        )

    def tearDown(self):
        self.db.close()

    def test_github_unreachable_skipped_without_partial_report(self):
        from datetime import datetime, timezone, timedelta
        now = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        result = self.skill.tick(now)
        self.assertEqual(result.reports_sent, 0)
        self.assertEqual(len(self.dispatch_calls), 0)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("proj-beta", result.errors[0])


class ProgressReportMultipleProjectsTests(unittest.TestCase):
    def setUp(self):
        self.db = open_store(":memory:")
        init_schema(self.db)
        _insert_binding(self.db, "chat:proj-alpha", repo_url="https://github.com/org/alpha")
        _insert_binding(self.db, "chat:proj-beta", repo_url="https://github.com/org/beta")

        self.dispatch, self.dispatch_calls = _make_router_dispatch()
        self.skill = ProgressReportSkill(
            db=self.db,
            pr_fetcher=_make_pr_fetcher({
                "https://github.com/org/alpha": [
                    {"title": "PR A", "status": "open"},
                ],
                "https://github.com/org/beta": [
                    {"title": "PR B", "status": "draft"},
                ],
            }),
            router_dispatch=self.dispatch,
        )

    def tearDown(self):
        self.db.close()

    def test_multiple_projects_independent_dispatch(self):
        from datetime import datetime, timezone, timedelta
        now = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        result = self.skill.tick(now)
        self.assertEqual(result.reports_sent, 2)
        self.assertEqual(result.projects_checked, 2)
        self.assertEqual(len(self.dispatch_calls), 2)


class ProgressReportFirstTimeDueTests(unittest.TestCase):
    def setUp(self):
        self.db = open_store(":memory:")
        init_schema(self.db)
        _insert_binding(self.db, "chat:proj-new", repo_url="https://github.com/org/newproj")

        self.dispatch, self.dispatch_calls = _make_router_dispatch()
        self.skill = ProgressReportSkill(
            db=self.db,
            pr_fetcher=_make_pr_fetcher({
                "https://github.com/org/newproj": [],
            }),
            router_dispatch=self.dispatch,
        )

    def tearDown(self):
        self.db.close()

    def test_first_time_due_dispatched(self):
        result = self.skill.tick("2026-06-15T12:00:00")
        self.assertEqual(result.reports_sent, 1)
        self.assertEqual(len(self.dispatch_calls), 1)


class ProgressReportRuntimeLoadoutTests(unittest.TestCase):
    def setUp(self):
        self.db = open_store(":memory:")
        init_schema(self.db)

    def tearDown(self):
        self.db.close()

    def test_runtime_loadout_is_orchestrator_only(self):
        dispatch, calls = _make_router_dispatch()
        skill = ProgressReportSkill(
            db=self.db,
            pr_fetcher=_make_pr_fetcher({}),
            router_dispatch=dispatch,
        )
        self.assertEqual(skill.runtime_loadout, "orchestrator-only")


class TickResultTests(unittest.TestCase):
    def test_defaults(self):
        result = TickResult()
        self.assertEqual(result.projects_checked, 0)
        self.assertEqual(result.reports_sent, 0)
        self.assertEqual(result.projects_skipped, 0)
        self.assertEqual(result.errors, [])


if __name__ == "__main__":
    unittest.main()