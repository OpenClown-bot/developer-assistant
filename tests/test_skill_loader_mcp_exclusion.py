"""Unit + integration tests for TKT-040 AC-5 (MCP skill exclusion).

Covers the 4 explicit cases enumerated in AC-5 plus the three
non-match guards from TKT-040 § 6 Test Strategy:

AC-5 (rejection cases):
  - skill named ``mcp:foo`` rejected (prefix ``mcp:``)
  - skill named ``mcp/bar/SKILL.md`` rejected (prefix ``mcp/``)
  - skill at path ``shared-skills/mcp/baz/SKILL.md`` rejected
    (path-segment ``/mcp/``)

AC-5 (non-match cases — substring must not be greedy):
  - skill named ``dev-assist-mcp-not-actually`` accepted

§ 6 Test Strategy (additional non-match guards):
  - skill named ``dev-assist-mcp-bridge`` accepted
    (TKT-040 § 7 risk-mitigation case — future v0.2+ name)
  - skill named ``dev-assist-classifier`` accepted (control)
  - skill named ``mcphelper`` accepted (no separator after ``mcp``)

Integration:
  - registering the work-queue plugin populates
    ``hooks["skill_loader"]`` with the helpers, and feeding a
    mixed batch through ``filter`` keeps only the non-MCP skills
    while emitting a structured rejection log entry per
    ``OBSERVABILITY-CONTRACT.md`` § 4.
"""

from __future__ import annotations

import logging
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.hermes_plugins.dev_assist_work_queue import register
from developer_assistant.hermes_plugins.dev_assist_work_queue.skill_loader import (
    filter_skills,
    is_mcp_excluded,
)


class TestIsMcpExcludedRejectionCases(unittest.TestCase):
    """AC-5 rejection cases: pattern must reject these skill descriptors."""

    def test_name_with_mcp_colon_prefix_rejected(self):
        # AC-5 case 1: skill named "mcp:foo" rejected (prefix "mcp:").
        self.assertTrue(is_mcp_excluded("mcp:foo"))

    def test_name_with_mcp_slash_prefix_rejected(self):
        # AC-5 case 2: skill named "mcp/bar/SKILL.md" rejected (prefix "mcp/").
        self.assertTrue(is_mcp_excluded("mcp/bar/SKILL.md"))

    def test_path_under_mcp_segment_rejected(self):
        # AC-5 case 3: skill at path "shared-skills/mcp/baz/SKILL.md" rejected
        # (path-segment "/mcp/" — substring "mcp" alone would not match).
        self.assertTrue(
            is_mcp_excluded(
                "dev-assist-classifier",
                "shared-skills/mcp/baz/SKILL.md",
            )
        )

    def test_runtime_install_path_under_mcp_segment_rejected(self):
        # The runtime tree under /srv/devassist/shared-skills/mcp/ is the
        # canonical install destination per MULTI-HERMES-CONTRACT.md § 5.0.1.
        self.assertTrue(
            is_mcp_excluded(
                "any-name",
                "/srv/devassist/shared-skills/mcp/foo/SKILL.md",
            )
        )


class TestIsMcpExcludedAcceptanceCases(unittest.TestCase):
    """AC-5 + § 6 non-match cases: pattern must NOT be greedy on substring."""

    def test_substring_mcp_inside_name_accepted_not_actually(self):
        # AC-5 case 4: substring match must NOT be greedy.
        # "dev-assist-mcp-not-actually" must be accepted because
        # "mcp" appears as a sub-token but not as an "mcp:" or "mcp/" prefix.
        self.assertFalse(is_mcp_excluded("dev-assist-mcp-not-actually"))

    def test_dev_assist_mcp_bridge_accepted_risk_mitigation(self):
        # TKT-040 § 7 risk note: a future v0.2+ "dev-assist-mcp-bridge" skill
        # must NOT be falsely rejected. This is the TKT-040 § 8 Hard Rule 4
        # canonical guard case.
        self.assertFalse(is_mcp_excluded("dev-assist-mcp-bridge"))

    def test_dev_assist_classifier_accepted_control(self):
        # § 6 Test Strategy control case: the canonical loaded Orchestrator
        # custom skill must remain accepted with no path argument.
        self.assertFalse(is_mcp_excluded("dev-assist-classifier"))

    def test_mcphelper_accepted_no_separator_after_mcp(self):
        # § 6 Test Strategy: "mcphelper" — no separator after "mcp" — must
        # NOT match the prefix patterns. Substring "mcp" alone is not a match.
        self.assertFalse(is_mcp_excluded("mcphelper"))

    def test_path_with_substring_mcp_in_segment_name_accepted(self):
        # Path-segment matcher must check the literal "/mcp/" boundary, not
        # any segment that merely contains "mcp" as a substring.
        self.assertFalse(
            is_mcp_excluded(
                "dev-assist-classifier",
                "shared-skills/dev-assist-mcp-bridge/SKILL.md",
            )
        )

    def test_empty_name_and_path_accepted(self):
        # Defensive: an empty name with no path is not an MCP skill and
        # must not be falsely flagged as excluded.
        self.assertFalse(is_mcp_excluded(""))
        self.assertFalse(is_mcp_excluded("", None))


class TestFilterSkills(unittest.TestCase):
    """``filter_skills`` returns the non-excluded subset, preserving order."""

    def test_filter_strips_excluded_and_preserves_order(self):
        skills = [
            {"name": "mcp:alpha"},
            {"name": "dev-assist-classifier"},
            {"name": "mcp/beta"},
            {"name": "mcphelper"},
            {"name": "anything", "path": "/srv/devassist/shared-skills/mcp/x/SKILL.md"},
            {"name": "dev-assist-mcp-bridge"},
        ]
        kept = filter_skills(skills, logger=logging.getLogger("test_filter_skills"))
        kept_names = [d["name"] for d in kept]
        self.assertEqual(
            kept_names,
            ["dev-assist-classifier", "mcphelper", "dev-assist-mcp-bridge"],
        )

    def test_filter_emits_structured_log_for_each_rejection(self):
        # AC-4 + integration: each rejection emits a structured entry with
        # event="skill_loader.mcp_exclusion" so the rejection is visible in
        # journald and the SQLite observability store.
        captured: list[logging.LogRecord] = []

        class _Capture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(record)

        logger = logging.getLogger("test_filter_skills_log_capture")
        logger.setLevel(logging.INFO)
        handler = _Capture()
        logger.addHandler(handler)
        try:
            filter_skills(
                [
                    {"name": "mcp:alpha"},
                    {"name": "dev-assist-classifier"},
                    {"name": "mcp/beta"},
                ],
                logger=logger,
            )
        finally:
            logger.removeHandler(handler)

        events = [getattr(rec, "event", None) for rec in captured]
        self.assertEqual(
            events,
            ["skill_loader.mcp_exclusion", "skill_loader.mcp_exclusion"],
        )
        for rec in captured:
            payload = getattr(rec, "_extra_payload", None)
            self.assertIsNotNone(payload)
            self.assertIn("skill_name", payload)
            self.assertIn("rule", payload)


class TestPluginRegisterIntegratesSkillLoader(unittest.TestCase):
    """``register(hooks)`` exposes the loader extension under ``skill_loader``."""

    def test_register_populates_skill_loader_hook_with_helpers(self):
        # Integration: registering the dev_assist_work_queue plugin must
        # populate hooks["skill_loader"] with the two callables. Mirrors the
        # hook-dict shape used by dev_assist_escalation_policy's
        # hooks["pre_tool_call"] integration.
        hooks: dict = {}
        register(hooks)
        self.assertIn("skill_loader", hooks)
        loader = hooks["skill_loader"]
        self.assertIn("is_excluded", loader)
        self.assertIn("filter", loader)
        self.assertTrue(callable(loader["is_excluded"]))
        self.assertTrue(callable(loader["filter"]))

    def test_register_loader_rejects_mcp_named_fixture_skill(self):
        # Integration: a fixture skill matching the pattern is rejected when
        # piped through the loader hook installed by register().
        hooks: dict = {}
        register(hooks)
        kept = hooks["skill_loader"]["filter"](
            [
                {"name": "mcp:fixture"},
                {"name": "dev-assist-classifier"},
            ],
            logger=logging.getLogger("test_register_loader_rejection_fixture"),
        )
        self.assertEqual([d["name"] for d in kept], ["dev-assist-classifier"])

    def test_register_loader_does_not_reject_dev_assist_mcp_bridge(self):
        # Hard Rule 4 + § 7 risk mitigation: the future "dev-assist-mcp-bridge"
        # name must NOT be falsely rejected when piped through the registered
        # loader hook.
        hooks: dict = {}
        register(hooks)
        kept = hooks["skill_loader"]["filter"](
            [{"name": "dev-assist-mcp-bridge"}],
            logger=logging.getLogger("test_register_loader_no_false_positive"),
        )
        self.assertEqual([d["name"] for d in kept], ["dev-assist-mcp-bridge"])


if __name__ == "__main__":
    unittest.main()
