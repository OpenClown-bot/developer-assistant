"""Round-trip test: MODEL-CATALOG.md → runtime_layout renderer → verify_runtime_config.

Proves that TKT-021's rendered config.yaml output is consistent with
TKT-026's catalog enforcement for all five roles.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.model_catalog import verify_runtime_config
from developer_assistant.runtime_layout import render_runtime_config


class TestRoundTrip(unittest.TestCase):
    def _extract_agent_config(self, config_yaml: str) -> dict:
        lines = config_yaml.splitlines()
        model_val = None
        fallback_vals: list[str] = []
        in_agent = False
        in_fallbacks = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("agent:"):
                in_agent = True
                in_fallbacks = False
                continue
            if in_agent and stripped.startswith("model:"):
                model_val = stripped.split(":", 1)[1].strip()
                in_fallbacks = False
                continue
            if in_agent and stripped.startswith("fallback_models:"):
                in_fallbacks = True
                continue
            if in_fallbacks and stripped.startswith("- "):
                fallback_vals.append(stripped[2:].strip())
                continue
            if in_agent and stripped and not stripped.startswith("-") and not stripped.startswith("#"):
                in_fallbacks = False
        return {"agent": {"model": model_val, "fallback_models": fallback_vals}}

    def test_round_trip_all_roles(self) -> None:
        for role in ["orchestrator", "planner", "architect", "executor", "reviewer"]:
            with self.subTest(role=role):
                rendered = render_runtime_config(
                    role=role,
                    secrets_env_path="/srv/devassist/secrets/SELF-DEPLOY.env",
                    state_db_path="/srv/devassist/state/operational.db",
                    repo_path="/srv/devassist/repo",
                )
                config_yaml = rendered["config.yaml"]
                config = self._extract_agent_config(config_yaml)
                verify_runtime_config(role, config)


if __name__ == "__main__":
    unittest.main()
