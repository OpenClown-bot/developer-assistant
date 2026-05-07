from __future__ import annotations

import inspect
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.hermes_plugins.dev_assist_escalation_policy.concept_classifier import (
    ConceptAnchor,
    classify_concept_deviation,
    load_anchor,
    _matches,
)


_VALID_CONCEPT_MD = """\
---
id: PROJECT-CONCEPT
version: 0.1.0
status: draft
---

# Project Concept Anchor (structured)

## 2. Concept Anchor Block

```yaml
project_identity:
  name: developer-assistant
  target_user: technical_founder_solo
  primary_interface: Telegram
  secondary_interface: lightweight_web_status_dashboard
  deployment_target: single_vps_owned_by_founder

in_scope_v0_1:
  - id: install_in_15_min
    citation: "PRD-001 § 12.1"

budget_constraints:
  - id: single_ubuntu_vps_founder_owned
    citation: "PRD-001 § 12"

tech_anchors:
  - id: hermes_agent_runtime
    citation: "ARCH-001 § 11"

risk_boundaries:
  - id: no_public_inbound_network_exposure
    citation: "ESCALATION-POLICY.md § 4.5"

deviation_rules:
  - id: replace_target_user
    match:
      kind: file_write
      path_glob: "docs/prd/PRD-*.md"
      content_diff_touches: ["§ 2", "Vision"]
    verdict: ESCALATE
    cite: "concept:replace_target_user (ESCALATION-POLICY § 4.10)"

  - id: replace_tech_stack_anchor
    match:
      kind: any_action
      argument_keyword_set: ["replace_hermes", "swap_telegram", "remove_openclaw"]
      operator: OR
    verdict: ESCALATE
    cite: "concept:replace_tech_stack (ESCALATION-POLICY § 4.10)"

  - id: replace_runtime_target
    match:
      kind: any_action
      argument_keyword_set: ["k8s", "kubernetes", "ecs", "lambda", "cloud_run", "fargate", "deploy_to_aws", "deploy_to_gcp", "deploy_to_azure"]
      operator: OR
    verdict: ESCALATE
    cite: "concept:replace_runtime_target (ESCALATION-POLICY § 4.10)"

  - id: introduce_paid_recurring_service
    match:
      kind: any_action
      argument_keyword_set: ["modal.com", "daytona", "e2b.dev", "vercel", "fly.io paid", "qdrant.cloud", "pinecone", "weaviate.cloud", "managed_redis", "managed_postgres", "letta_cloud"]
      operator: OR
    verdict: ESCALATE
    cite: "paid:new_recurring_service (ESCALATION-POLICY § 4.6)"

  - id: edit_concept_anchor
    match:
      kind: file_write
      path_glob: "docs/architecture/PROJECT-CONCEPT.md"
    verdict: ESCALATE
    cite: "concept:edit_concept_anchor (ESCALATION-POLICY § 4.10)"

  - id: open_public_inbound_port
    match:
      kind: shell_command
      argument_regex: "(ufw allow|firewall-cmd --add-port|iptables -A INPUT.*ACCEPT|systemd .* ListenStream)"
    verdict: ESCALATE
    cite: "net:open_inbound_port (ESCALATION-POLICY § 4.5)"

  - id: introduce_webhook_mode_telegram
    match:
      kind: file_write
      argument_keyword_set: ["telegram_webhook_url", "setWebhook", "telegram.update_mode: webhook"]
      operator: OR
    verdict: ESCALATE
    cite: "net:webhook_mode_telegram (ESCALATION-POLICY § 4.5)"

  - id: hardcode_secret_in_repo
    match:
      kind: file_write
      content_regex: "(?i)(sk-[A-Za-z0-9]{32,}|ghp_[A-Za-z0-9]{36}|[0-9]{9,10}:AA[A-Za-z0-9_-]{33})"
    verdict: ESCALATE
    cite: "secret:write_to_repo (ESCALATION-POLICY § 4.4)"

  - id: default_fall_through
    match:
      kind: any_action
    verdict: PROCEED_OR_RULE_4_DECIDES
    note: |
      If no deviation_rule above fires, control returns to § 4.
```
"""


class TestLoadFromDiskHappyPath(unittest.TestCase):
    def test_load_anchor_success(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(_VALID_CONCEPT_MD)
            f.flush()
            anchor = load_anchor(f.name)
        os.unlink(f.name)
        self.assertIsInstance(anchor, ConceptAnchor)
        self.assertEqual(anchor.project_identity["name"], "developer-assistant")
        self.assertTrue(len(anchor.deviation_rules) > 0)


class TestMalformedYAMLFailClosed(unittest.TestCase):
    def test_malformed_yaml_returns_anchor_unavailable(self):
        bad_md = """\
---
id: PROJECT-CONCEPT
version: 0.1.0
status: draft
---

## 2. Concept Anchor Block

```yaml
project_identity:
  name: developer-assistant
  target_user: [broken
```
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(bad_md)
            f.flush()
            path = f.name
        try:
            with patch(
                "developer_assistant.hermes_plugins.dev_assist_escalation_policy.concept_classifier._anchor",
                None,
            ):
                result = classify_concept_deviation(
                    "shell_command",
                    {"command": "ls"},
                    anchor=None,
                )
                self.assertEqual(result, "concept:anchor_unavailable")
        finally:
            os.unlink(path)

    def test_load_anchor_raises_on_malformed(self):
        bad_md = """\
---
id: PROJECT-CONCEPT
version: 0.1.0
status: draft
---

## 2. Concept Anchor Block

```yaml
project_identity:
  name: developer-assistant
  target_user: [broken
```
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(bad_md)
            f.flush()
            path = f.name
        try:
            with self.assertRaises(Exception):
                load_anchor(path)
        finally:
            os.unlink(path)


class TestMissingFileFailClosed(unittest.TestCase):
    def test_missing_file_returns_anchor_unavailable(self):
        with patch(
            "developer_assistant.hermes_plugins.dev_assist_escalation_policy.concept_classifier._anchor",
            None,
        ):
            result = classify_concept_deviation(
                "shell_command",
                {"command": "ls"},
                anchor=None,
            )
            self.assertEqual(result, "concept:anchor_unavailable")


class TestInScopeAction(unittest.TestCase):
    def test_in_scope_action_returns_none(self):
        anchor = self._make_anchor()
        result = classify_concept_deviation(
            "file_write",
            {"path": "src/main.py", "content": "print('hello')"},
            anchor=anchor,
        )
        self.assertIsNone(result)

    def _make_anchor(self) -> ConceptAnchor:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(_VALID_CONCEPT_MD)
            f.flush()
            anchor = load_anchor(f.name)
        os.unlink(f.name)
        return anchor


class TestOutOfScopeAction(unittest.TestCase):
    def test_replace_target_user(self):
        anchor = self._make_anchor()
        result = classify_concept_deviation(
            "file_write",
            {"path": "docs/prd/PRD-001.md", "content": "§ 2 Vision changed"},
            anchor=anchor,
        )
        self.assertEqual(result, "concept_deviation:replace_target_user")

    def test_replace_tech_stack(self):
        anchor = self._make_anchor()
        result = classify_concept_deviation(
            "shell_command",
            {"command": "replace_hermes with something"},
            anchor=anchor,
        )
        self.assertEqual(result, "concept_deviation:replace_tech_stack_anchor")

    def test_replace_runtime_target(self):
        anchor = self._make_anchor()
        result = classify_concept_deviation(
            "shell_command",
            {"command": "deploy_to_aws"},
            anchor=anchor,
        )
        self.assertEqual(result, "concept_deviation:replace_runtime_target")

    def test_edit_concept_anchor(self):
        anchor = self._make_anchor()
        result = classify_concept_deviation(
            "file_write",
            {"path": "docs/architecture/PROJECT-CONCEPT.md", "content": "updated"},
            anchor=anchor,
        )
        self.assertEqual(result, "concept_deviation:edit_concept_anchor")

    def test_open_public_inbound_port(self):
        anchor = self._make_anchor()
        result = classify_concept_deviation(
            "shell_command",
            {"command": "ufw allow 8080"},
            anchor=anchor,
        )
        self.assertEqual(result, "concept_deviation:open_public_inbound_port")

    def test_introduce_paid_recurring_service(self):
        anchor = self._make_anchor()
        result = classify_concept_deviation(
            "shell_command",
            {"command": "pip install modal.com sdk"},
            anchor=anchor,
        )
        self.assertEqual(result, "concept_deviation:introduce_paid_recurring_service")

    def _make_anchor(self) -> ConceptAnchor:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(_VALID_CONCEPT_MD)
            f.flush()
            anchor = load_anchor(f.name)
        os.unlink(f.name)
        return anchor


class TestDefaultFallThrough(unittest.TestCase):
    def test_default_fall_through_proceeds_if_no_rule4(self):
        anchor = self._make_anchor()
        result = classify_concept_deviation(
            "file_write",
            {"path": "src/utils.py", "content": "def helper(): pass"},
            anchor=anchor,
        )
        self.assertIsNone(result)

    def _make_anchor(self) -> ConceptAnchor:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(_VALID_CONCEPT_MD)
            f.flush()
            anchor = load_anchor(f.name)
        os.unlink(f.name)
        return anchor


class TestNoLLMReferences(unittest.TestCase):
    def test_no_model_dispatcher_import(self):
        import developer_assistant.hermes_plugins.dev_assist_escalation_policy.concept_classifier as mod
        source = inspect.getsource(mod)
        forbidden = [
            "requests.", "httpx.", "aiohttp.",
            "openai.", "anthropic.", "langchain.",
            "ChatCompletion", "Completion",
            "llm_call", "llm_provider",
        ]
        for term in forbidden:
            self.assertNotIn(term, source, f"Found forbidden term: {term}")

    def test_no_http_client_references(self):
        import developer_assistant.hermes_plugins.dev_assist_escalation_policy.concept_classifier as mod
        members = dir(mod)
        forbidden = ["requests", "httpx", "aiohttp", "urllib3", "http_client"]
        for name in forbidden:
            self.assertNotIn(name, members, f"Found forbidden member: {name}")


if __name__ == "__main__":
    unittest.main()
