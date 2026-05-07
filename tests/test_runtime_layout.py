"""Tests for developer_assistant.runtime_layout.

Uses stdlib ``unittest`` and ``tempfile``. All values use placeholder strings;
no real tokens, PATs, or production hostnames appear in tests.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.runtime_layout import (
    _ALLOWED_ROLES,
    get_role_model_assignment,
    get_role_skills,
    render_runtime_config,
)

_EXPECTED_SCHEMA_VERSION = "3"


class TestAllowedRoles(unittest.TestCase):
    def test_allowed_roles_contains_five(self) -> None:
        self.assertEqual(len(_ALLOWED_ROLES), 5)
        for role in ["orchestrator", "planner", "architect", "executor", "reviewer"]:
            self.assertIn(role, _ALLOWED_ROLES)


class TestRenderRuntimeConfig(unittest.TestCase):
    def setUp(self) -> None:
        self.maxDiff = 8000
        self.repo_path = "/srv/devassist/repo"
        self.secrets_path = "/srv/devassist/secrets/SELF-DEPLOY.env"
        self.state_db_path = "/srv/devassist/state/operational.db"

    def test_render_unknown_role_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            render_runtime_config(
                role="unknown",
                secrets_env_path=self.secrets_path,
                state_db_path=self.state_db_path,
                repo_path=self.repo_path,
            )
        self.assertIn("unknown", str(ctx.exception))
        self.assertIn("orchestrator", str(ctx.exception))

    def test_render_returns_three_files(self) -> None:
        for role in _ALLOWED_ROLES:
            with self.subTest(role=role):
                result = render_runtime_config(
                    role=role,
                    secrets_env_path=self.secrets_path,
                    state_db_path=self.state_db_path,
                    repo_path=self.repo_path,
                )
                self.assertEqual(set(result.keys()), {"config.yaml", "auth.json", "SOUL.md"})

    def test_orchestrator_has_telegram_gateway(self) -> None:
        result = render_runtime_config(
            role="orchestrator",
            secrets_env_path=self.secrets_path,
            state_db_path=self.state_db_path,
            repo_path=self.repo_path,
        )
        cfg = result["config.yaml"]
        self.assertIn("telegram-gateway", cfg)
        self.assertIn("gateway:", cfg)
        self.assertTrue(any(
            line.strip() == "enabled: true" and i > 0 and "gateway" in cfg[:cfg.index(line)]
            for i, line in enumerate(cfg.splitlines())
        ))
        self.assertNotIn("terminal:", cfg)

    def test_planner_no_telegram_gateway(self) -> None:
        result = render_runtime_config(
            role="planner",
            secrets_env_path=self.secrets_path,
            state_db_path=self.state_db_path,
            repo_path=self.repo_path,
        )
        cfg = result["config.yaml"]
        self.assertNotIn("telegram-gateway", cfg)
        self.assertIn("enabled: false", cfg)

    def test_architect_no_telegram_gateway(self) -> None:
        result = render_runtime_config(
            role="architect",
            secrets_env_path=self.secrets_path,
            state_db_path=self.state_db_path,
            repo_path=self.repo_path,
        )
        self.assertNotIn("telegram-gateway", result["config.yaml"])
        self.assertNotIn("terminal:", result["config.yaml"])

    def test_executor_has_docker_terminal(self) -> None:
        result = render_runtime_config(
            role="executor",
            secrets_env_path=self.secrets_path,
            state_db_path=self.state_db_path,
            repo_path=self.repo_path,
        )
        cfg = result["config.yaml"]
        self.assertNotIn("telegram-gateway", cfg)
        self.assertIn("terminal:", cfg)
        self.assertIn("backend: docker", cfg)

    def test_reviewer_has_docker_terminal(self) -> None:
        result = render_runtime_config(
            role="reviewer",
            secrets_env_path=self.secrets_path,
            state_db_path=self.state_db_path,
            repo_path=self.repo_path,
        )
        cfg = result["config.yaml"]
        self.assertNotIn("telegram-gateway", cfg)
        self.assertIn("terminal:", cfg)
        self.assertIn("backend: docker", cfg)

    def test_architect_model_is_deepseek_v4_pro(self) -> None:
        result = render_runtime_config(
            role="architect",
            secrets_env_path=self.secrets_path,
            state_db_path=self.state_db_path,
            repo_path=self.repo_path,
        )
        self.assertIn("accounts/fireworks/models/deepseek-v4-pro", result["config.yaml"])

    def test_orchestrator_model_is_minimax_m2p7(self) -> None:
        result = render_runtime_config(
            role="orchestrator",
            secrets_env_path=self.secrets_path,
            state_db_path=self.state_db_path,
            repo_path=self.repo_path,
        )
        self.assertIn("accounts/fireworks/models/minimax-m2p7", result["config.yaml"])

    def test_planner_model_is_qwen3p6_plus(self) -> None:
        result = render_runtime_config(
            role="planner",
            secrets_env_path=self.secrets_path,
            state_db_path=self.state_db_path,
            repo_path=self.repo_path,
        )
        self.assertIn("accounts/fireworks/models/qwen3p6-plus", result["config.yaml"])

    def test_executor_model_is_glm_5p1(self) -> None:
        result = render_runtime_config(
            role="executor",
            secrets_env_path=self.secrets_path,
            state_db_path=self.state_db_path,
            repo_path=self.repo_path,
        )
        self.assertIn("accounts/fireworks/models/glm-5p1", result["config.yaml"])

    def test_reviewer_model_is_kimi_k2p6(self) -> None:
        result = render_runtime_config(
            role="reviewer",
            secrets_env_path=self.secrets_path,
            state_db_path=self.state_db_path,
            repo_path=self.repo_path,
        )
        self.assertIn("accounts/fireworks/models/kimi-k2p6", result["config.yaml"])

    def test_orchestrator_gateway_enabled_true(self) -> None:
        result = render_runtime_config(
            role="orchestrator",
            secrets_env_path=self.secrets_path,
            state_db_path=self.state_db_path,
            repo_path=self.repo_path,
        )
        lines = result["config.yaml"].splitlines()
        in_gateway = False
        found_true = False
        for line in lines:
            stripped = line.strip()
            if stripped == "gateway:":
                in_gateway = True
            elif in_gateway and stripped.startswith("enabled:"):
                if "true" in stripped:
                    found_true = True
                in_gateway = False
        self.assertTrue(found_true, "gateway.enabled should be true for orchestrator")

    def test_non_orchestrator_gateway_enabled_false(self) -> None:
        for role in ["planner", "architect", "executor", "reviewer"]:
            with self.subTest(role=role):
                result = render_runtime_config(
                    role=role,
                    secrets_env_path=self.secrets_path,
                    state_db_path=self.state_db_path,
                    repo_path=self.repo_path,
                )
                lines = result["config.yaml"].splitlines()
                in_gateway = False
                found_false = False
                for line in lines:
                    stripped = line.strip()
                    if stripped == "gateway:":
                        in_gateway = True
                    elif in_gateway and stripped.startswith("enabled:"):
                        if "false" in stripped:
                            found_false = True
                        in_gateway = False
                self.assertTrue(found_false, "gateway.enabled should be false for {r}".format(r=role))

    def test_all_roles_have_skill_manage_disabled(self) -> None:
        for role in _ALLOWED_ROLES:
            with self.subTest(role=role):
                result = render_runtime_config(
                    role=role,
                    secrets_env_path=self.secrets_path,
                    state_db_path=self.state_db_path,
                    repo_path=self.repo_path,
                )
                self.assertIn("skill_manage", result["config.yaml"])

    def test_all_roles_have_delegate_task_disabled(self) -> None:
        for role in _ALLOWED_ROLES:
            with self.subTest(role=role):
                result = render_runtime_config(
                    role=role,
                    secrets_env_path=self.secrets_path,
                    state_db_path=self.state_db_path,
                    repo_path=self.repo_path,
                )
                self.assertIn("delegate_task", result["config.yaml"])

    def test_all_roles_have_approvals_manual(self) -> None:
        for role in _ALLOWED_ROLES:
            with self.subTest(role=role):
                result = render_runtime_config(
                    role=role,
                    secrets_env_path=self.secrets_path,
                    state_db_path=self.state_db_path,
                    repo_path=self.repo_path,
                )
                self.assertIn("mode: manual", result["config.yaml"])

    def test_all_roles_have_shared_skills_dir(self) -> None:
        for role in _ALLOWED_ROLES:
            with self.subTest(role=role):
                result = render_runtime_config(
                    role=role,
                    secrets_env_path=self.secrets_path,
                    state_db_path=self.state_db_path,
                    repo_path=self.repo_path,
                )
                self.assertIn("/srv/devassist/shared-skills/", result["config.yaml"])

    def test_all_roles_have_operational_db_path(self) -> None:
        for role in _ALLOWED_ROLES:
            with self.subTest(role=role):
                result = render_runtime_config(
                    role=role,
                    secrets_env_path=self.secrets_path,
                    state_db_path=self.state_db_path,
                    repo_path=self.repo_path,
                )
                self.assertIn("operational_db:", result["config.yaml"])
                self.assertIn("operational.db", result["config.yaml"])

    def test_omnioute_base_url_in_all_configs(self) -> None:
        for role in _ALLOWED_ROLES:
            with self.subTest(role=role):
                result = render_runtime_config(
                    role=role,
                    secrets_env_path=self.secrets_path,
                    state_db_path=self.state_db_path,
                    repo_path=self.repo_path,
                )
                self.assertIn("http://127.0.0.1:20128/v1", result["config.yaml"])

    def test_all_roles_have_escalation_policy_plugin(self) -> None:
        for role in _ALLOWED_ROLES:
            with self.subTest(role=role):
                result = render_runtime_config(
                    role=role,
                    secrets_env_path=self.secrets_path,
                    state_db_path=self.state_db_path,
                    repo_path=self.repo_path,
                )
                self.assertIn("dev-assist-escalation-policy", result["config.yaml"])

    def test_all_roles_have_work_queue_plugin(self) -> None:
        for role in _ALLOWED_ROLES:
            with self.subTest(role=role):
                result = render_runtime_config(
                    role=role,
                    secrets_env_path=self.secrets_path,
                    state_db_path=self.state_db_path,
                    repo_path=self.repo_path,
                )
                self.assertIn("dev-assist-work-queue", result["config.yaml"])

    def test_configs_are_pairwise_unequal(self) -> None:
        rendered = {}
        for role in _ALLOWED_ROLES:
            result = render_runtime_config(
                role=role,
                secrets_env_path=self.secrets_path,
                state_db_path=self.state_db_path,
                repo_path=self.repo_path,
            )
            rendered[role] = result["config.yaml"]

        pairs = [(r1, r2) for r1 in _ALLOWED_ROLES for r2 in _ALLOWED_ROLES if r1 < r2]
        for r1, r2 in pairs:
            with self.subTest(p1=r1, p2=r2):
                self.assertNotEqual(
                    rendered[r1], rendered[r2],
                    "{r1} and {r2} configs should differ".format(r1=r1, r2=r2),
                )

    def test_cli_invocation_against_temp_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out_dir = os.path.join(td, "out")
            role = "orchestrator"
            result = render_runtime_config(
                role=role,
                secrets_env_path=self.secrets_path,
                state_db_path=self.state_db_path,
                repo_path=self.repo_path,
            )
            os.makedirs(out_dir)
            for filename, content in result.items():
                dest = os.path.join(out_dir, filename)
                with open(dest, "w", encoding="utf-8") as fh:
                    fh.write(content)

            for fname in ["config.yaml", "auth.json", "SOUL.md"]:
                path = os.path.join(out_dir, fname)
                self.assertTrue(os.path.exists(path), "{f} should be written".format(f=fname))
                with open(path, encoding="utf-8") as fh:
                    content = fh.read()
                self.assertGreater(len(content), 0, "{f} should not be empty".format(f=fname))


class TestGetRoleModelAssignment(unittest.TestCase):
    def test_orchestrator_main_model(self) -> None:
        main, fallbacks = get_role_model_assignment("orchestrator")
        self.assertEqual(main, "accounts/fireworks/models/minimax-m2p7")
        self.assertEqual(len(fallbacks), 3)

    def test_architect_main_model(self) -> None:
        main, _ = get_role_model_assignment("architect")
        self.assertEqual(main, "accounts/fireworks/models/deepseek-v4-pro")

    def test_unknown_role_raises(self) -> None:
        with self.assertRaises(ValueError):
            get_role_model_assignment("invalid")


class TestGetRoleSkills(unittest.TestCase):
    def test_orchestrator_has_telegram_gateway(self) -> None:
        built_in, custom = get_role_skills("orchestrator")
        self.assertIn("telegram-gateway", built_in)

    def test_executor_has_terminal(self) -> None:
        built_in, custom = get_role_skills("executor")
        self.assertIn("terminal", built_in)

    def test_planner_no_telegram(self) -> None:
        built_in, custom = get_role_skills("planner")
        self.assertNotIn("telegram-gateway", built_in)

    def test_all_have_cronjob_and_memory(self) -> None:
        for role in _ALLOWED_ROLES:
            with self.subTest(role=role):
                built_in, _ = get_role_skills(role)
                self.assertIn("cronjob", built_in)
                self.assertIn("memory", built_in)


if __name__ == "__main__":
    unittest.main()