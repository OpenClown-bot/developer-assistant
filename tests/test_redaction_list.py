from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.hermes_plugins.dev_assist_escalation_policy.redaction import (
    REDACTION_PATTERNS,
    redact_string,
    redact_action_args,
    REDACTED_VALUE,
)


class TestRedactionIsConstantMapping(unittest.TestCase):
    def test_is_dict(self):
        self.assertIsInstance(REDACTION_PATTERNS, dict)

    def test_not_empty(self):
        self.assertTrue(len(REDACTION_PATTERNS) > 0)


class TestEnvTokenRedaction(unittest.TestCase):
    def test_token_env_var(self):
        text = "MY_API_TOKEN=secret_value_123"
        result = redact_string(text)
        self.assertNotIn("secret_value_123", result)
        self.assertIn(REDACTED_VALUE, result)


class TestEnvApiKeyRedaction(unittest.TestCase):
    def test_api_key_env_var(self):
        text = "OPENAI_API_KEY=sk-abc123def456"
        result = redact_string(text)
        self.assertNotIn("sk-abc123def456", result)


class TestEnvSecretRedaction(unittest.TestCase):
    def test_secret_env_var(self):
        text = "APP_SECRET=mysecretvalue"
        result = redact_string(text)
        self.assertNotIn("mysecretvalue", result)


class TestEnvPasswordRedaction(unittest.TestCase):
    def test_password_env_var(self):
        text = "DB_PASSWORD=supersecret"
        result = redact_string(text)
        self.assertNotIn("supersecret", result)


class TestSkTokenRedaction(unittest.TestCase):
    def test_sk_token(self):
        text = "key=sk-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        result = redact_string(text)
        self.assertNotIn("sk-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", result)


class TestGhpTokenRedaction(unittest.TestCase):
    def test_ghp_token(self):
        text = "GITHUB_TOKEN=ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        result = redact_string(text)
        self.assertNotIn("ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", result)


class TestTelegramBotTokenRedaction(unittest.TestCase):
    def test_telegram_bot_token(self):
        text = "TELEGRAM_BOT_TOKEN=123456789:AABBCCDDEEFFGGHHIIJJKKLLMMNNOOPPQQ"
        result = redact_string(text)
        self.assertNotIn("123456789:AABBCCDDEEFFGGHHIIJJKKLLMMNNOOPPQQ", result)


class TestOpenRouterKeyRedaction(unittest.TestCase):
    def test_openrouter_key(self):
        text = "OPENROUTER_API_KEY=sk-or-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        result = redact_string(text)
        self.assertNotIn("sk-or-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", result)


class TestOmniRouteKeyRedaction(unittest.TestCase):
    def test_omniroute_key(self):
        text = "OMNIROUTE_API_KEY=sk-omni-AAAAAAAAAAAAAAAAAAAA"
        result = redact_string(text)
        self.assertNotIn("sk-omni-AAAAAAAAAAAAAAAAAAAA", result)


class TestRedactActionArgs(unittest.TestCase):
    def test_nested_dict_redaction(self):
        args = {
            "model": "glm-5p1",
            "api_key": "sk-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "nested": {"secret": "sk-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"},
        }
        result = redact_action_args(args)
        self.assertEqual(result["model"], "glm-5p1")
        self.assertNotIn("sk-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", result["api_key"])
        self.assertNotIn("sk-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", result["nested"]["secret"])

    def test_list_values_redacted(self):
        args = {"tokens": ["sk-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "safe_value"]}
        result = redact_action_args(args)
        self.assertNotIn("sk-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", result["tokens"][0])
        self.assertEqual(result["tokens"][1], "safe_value")


class TestSeededSecretsNotInClassifierOutput(unittest.TestCase):
    def test_no_secret_in_classifier_output(self):
        from developer_assistant.hermes_plugins.dev_assist_escalation_policy.concept_classifier import (
            classify_concept_deviation,
            ConceptAnchor,
        )
        anchor = ConceptAnchor({"deviation_rules": [], "project_identity": {}, "in_scope_v0_1": [], "budget_constraints": [], "tech_anchors": [], "risk_boundaries": []})
        result = classify_concept_deviation(
            "shell_command",
            {"command": "api_key=sk-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"},
            anchor=anchor,
        )
        self.assertEqual(result, "concept_deviation:classifier_safety_default")


if __name__ == "__main__":
    unittest.main()
