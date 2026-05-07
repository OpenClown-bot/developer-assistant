"""Tests for developer_assistant.model_catalog.

Uses stdlib unittest. All values use placeholder strings;
no real tokens, PATs, or production hostnames appear in tests.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.model_catalog import (
    CatalogParseError,
    CatalogViolation,
    ProbeResult,
    RoleAssignment,
    UnknownRole,
    _parse_catalog_table,
    get_role_assignment,
    verify_runtime_config,
)
import developer_assistant.model_catalog as model_catalog


_ORCHESTRATOR_MAIN = "accounts/fireworks/models/minimax-m2p7"
_ORCHESTRATOR_FALLBACKS = [
    "accounts/fireworks/models/kimi-k2p6",
    "accounts/fireworks/models/qwen3p6-plus",
    "accounts/fireworks/models/deepseek-v4-pro",
]
_PLANNER_MAIN = "accounts/fireworks/models/qwen3p6-plus"
_PLANNER_FALLBACKS = [
    "accounts/fireworks/models/kimi-k2p6",
    "accounts/fireworks/models/minimax-m2p7",
    "accounts/fireworks/models/deepseek-v4-pro",
]
_ARCHITECT_MAIN = "accounts/fireworks/models/deepseek-v4-pro"
_ARCHITECT_FALLBACKS = [
    "accounts/fireworks/models/kimi-k2p6",
    "accounts/fireworks/models/glm-5p1",
    "accounts/fireworks/models/qwen3p6-plus",
]
_EXECUTOR_MAIN = "accounts/fireworks/models/glm-5p1"
_EXECUTOR_FALLBACKS = [
    "accounts/fireworks/models/deepseek-v4-pro",
    "accounts/fireworks/models/kimi-k2p6",
    "accounts/fireworks/models/qwen3p6-plus",
]
_REVIEWER_MAIN = "accounts/fireworks/models/kimi-k2p6"
_REVIEWER_FALLBACKS = [
    "accounts/fireworks/models/deepseek-v4-pro",
    "accounts/fireworks/models/glm-5p1",
    "accounts/fireworks/models/qwen3p6-plus",
]


_GOOD_CATALOG_MD = (
    "# Model Catalog\n"
    "## 4. Catalog (v0.1)\n"
    "### 4.1 Per-role assignment\n"
    "\n"
    "| Role | Main model | Fallback 1 | Fallback 2 | Fallback 3 |\n"
    "| --- | --- | --- | --- | --- |\n"
    "| Orchestrator | `accounts/fireworks/models/minimax-m2p7` | `accounts/fireworks/models/kimi-k2p6` | `accounts/fireworks/models/qwen3p6-plus` | `accounts/fireworks/models/deepseek-v4-pro` |\n"
    "| Business Planner | `accounts/fireworks/models/qwen3p6-plus` | `accounts/fireworks/models/kimi-k2p6` | `accounts/fireworks/models/minimax-m2p7` | `accounts/fireworks/models/deepseek-v4-pro` |\n"
    "| Architect | `accounts/fireworks/models/deepseek-v4-pro` | `accounts/fireworks/models/kimi-k2p6` | `accounts/fireworks/models/glm-5p1` | `accounts/fireworks/models/qwen3p6-plus` |\n"
    "| Executor | `accounts/fireworks/models/glm-5p1` | `accounts/fireworks/models/deepseek-v4-pro` | `accounts/fireworks/models/kimi-k2p6` | `accounts/fireworks/models/qwen3p6-plus` |\n"
    "| Reviewer | `accounts/fireworks/models/kimi-k2p6` | `accounts/fireworks/models/deepseek-v4-pro` | `accounts/fireworks/models/glm-5p1` | `accounts/fireworks/models/qwen3p6-plus` |\n"
    "\n"
    "### 4.2 No separate auxiliary classifier\n"
)


class TestParseCorrectness(unittest.TestCase):
    def test_orchestrator_assignment(self) -> None:
        r = get_role_assignment("orchestrator")
        self.assertEqual(r.main, _ORCHESTRATOR_MAIN)
        self.assertEqual(r.fallbacks, _ORCHESTRATOR_FALLBACKS)

    def test_planner_assignment(self) -> None:
        r = get_role_assignment("planner")
        self.assertEqual(r.main, _PLANNER_MAIN)
        self.assertEqual(r.fallbacks, _PLANNER_FALLBACKS)

    def test_architect_assignment(self) -> None:
        r = get_role_assignment("architect")
        self.assertEqual(r.main, _ARCHITECT_MAIN)
        self.assertEqual(r.fallbacks, _ARCHITECT_FALLBACKS)

    def test_executor_assignment(self) -> None:
        r = get_role_assignment("executor")
        self.assertEqual(r.main, _EXECUTOR_MAIN)
        self.assertEqual(r.fallbacks, _EXECUTOR_FALLBACKS)

    def test_reviewer_assignment(self) -> None:
        r = get_role_assignment("reviewer")
        self.assertEqual(r.main, _REVIEWER_MAIN)
        self.assertEqual(r.fallbacks, _REVIEWER_FALLBACKS)

    def test_all_five_roles_populated(self) -> None:
        for role in ["orchestrator", "planner", "architect", "executor", "reviewer"]:
            with self.subTest(role=role):
                r = get_role_assignment(role)
                self.assertIsInstance(r, RoleAssignment)
                self.assertTrue(r.main.startswith("accounts/fireworks/models/"))
                self.assertEqual(len(r.fallbacks), 3)
                for fb in r.fallbacks:
                    self.assertTrue(fb.startswith("accounts/fireworks/models/"))


class TestMalformedCatalogDetection(unittest.TestCase):
    def test_missing_section_41(self) -> None:
        md = "# Model Catalog\nSome text without the table.\n"
        with self.assertRaises(CatalogParseError):
            _parse_catalog_table(md)

    def test_missing_table(self) -> None:
        md = "# Model Catalog\n### 4.1 Per-role assignment\n\nNo table here.\n\n### 4.2 Next\n"
        with self.assertRaises(CatalogParseError):
            _parse_catalog_table(md)

    def test_wrong_column_count(self) -> None:
        md = (
            "### 4.1 Per-role assignment\n"
            "| Role | Main model |\n"
            "| --- | --- |\n"
            "| Orchestrator | `something` |\n"
            "\n### 4.2 Next\n"
        )
        with self.assertRaises(CatalogParseError):
            _parse_catalog_table(md)

    def test_v010_auxiliary_classifier_table_present(self) -> None:
        md = (
            _GOOD_CATALOG_MD
            + "### 4.3 Auxiliary classifier\n"
            "| Classifier | Model |\n"
            "| --- | --- |\n"
            "| Concept deviation | `something` |\n"
        )
        with self.assertRaises(CatalogParseError):
            _parse_catalog_table(md)


class TestGetRoleAssignmentHappyPath(unittest.TestCase):
    def test_each_role_returns_roleassignment(self) -> None:
        for role in ["orchestrator", "planner", "architect", "executor", "reviewer"]:
            with self.subTest(role=role):
                r = get_role_assignment(role)
                self.assertIsInstance(r, RoleAssignment)


class TestGetRoleAssignmentUnknownRole(unittest.TestCase):
    def test_nonexistent_role_raises_unknownrole(self) -> None:
        with self.assertRaises(UnknownRole) as ctx:
            get_role_assignment("nonexistent_role")
        msg = str(ctx.exception)
        for valid in ["orchestrator", "planner", "architect", "executor", "reviewer"]:
            self.assertIn(valid, msg)


class TestVerifyRuntimeConfigHappyPath(unittest.TestCase):
    def test_orchestrator_config_passes(self) -> None:
        config = {
            "agent": {
                "model": _ORCHESTRATOR_MAIN,
                "fallback_models": list(_ORCHESTRATOR_FALLBACKS),
            }
        }
        verify_runtime_config("orchestrator", config)

    def test_all_roles_pass(self) -> None:
        assignments = {
            "orchestrator": (_ORCHESTRATOR_MAIN, _ORCHESTRATOR_FALLBACKS),
            "planner": (_PLANNER_MAIN, _PLANNER_FALLBACKS),
            "architect": (_ARCHITECT_MAIN, _ARCHITECT_FALLBACKS),
            "executor": (_EXECUTOR_MAIN, _EXECUTOR_FALLBACKS),
            "reviewer": (_REVIEWER_MAIN, _REVIEWER_FALLBACKS),
        }
        for role, (main, fbs) in assignments.items():
            with self.subTest(role=role):
                config = {"agent": {"model": main, "fallback_models": list(fbs)}}
                verify_runtime_config(role, config)


class TestVerifyRuntimeConfigViolations(unittest.TestCase):
    def test_wrong_main_model(self) -> None:
        config = {
            "agent": {
                "model": "wrong-model",
                "fallback_models": list(_ORCHESTRATOR_FALLBACKS),
            }
        }
        with self.assertRaises(CatalogViolation):
            verify_runtime_config("orchestrator", config)

    def test_extra_fallback_not_in_catalog(self) -> None:
        config = {
            "agent": {
                "model": _ORCHESTRATOR_MAIN,
                "fallback_models": list(_ORCHESTRATOR_FALLBACKS) + ["extra-model"],
            }
        }
        with self.assertRaises(CatalogViolation):
            verify_runtime_config("orchestrator", config)

    def test_reordered_fallback(self) -> None:
        reordered = [_ORCHESTRATOR_FALLBACKS[1], _ORCHESTRATOR_FALLBACKS[0], _ORCHESTRATOR_FALLBACKS[2]]
        config = {
            "agent": {
                "model": _ORCHESTRATOR_MAIN,
                "fallback_models": reordered,
            }
        }
        with self.assertRaises(CatalogViolation):
            verify_runtime_config("orchestrator", config)

    def test_strict_prefix_allowed(self) -> None:
        config = {
            "agent": {
                "model": _ARCHITECT_MAIN,
                "fallback_models": [_ARCHITECT_FALLBACKS[0]],
            }
        }
        verify_runtime_config("architect", config)

    def test_shorter_chain_prefix_allowed(self) -> None:
        config = {
            "agent": {
                "model": _ORCHESTRATOR_MAIN,
                "fallback_models": _ORCHESTRATOR_FALLBACKS[:2],
            }
        }
        verify_runtime_config("orchestrator", config)

    def test_empty_fallbacks_allowed(self) -> None:
        config = {
            "agent": {
                "model": _ORCHESTRATOR_MAIN,
                "fallback_models": [],
            }
        }
        verify_runtime_config("orchestrator", config)


class TestNoAuxiliaryClassifierSet(unittest.TestCase):
    def test_get_auxiliary_classifier_set_not_in_public_api(self) -> None:
        self.assertNotIn("get_auxiliary_classifier_set", dir(model_catalog))


if __name__ == "__main__":
    unittest.main()
