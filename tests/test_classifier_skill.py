"""Tests for dev-assist-classifier Hermes custom skill.

Covers each classification kind with representative input, freeform_chat
fallback on ambiguous/malformed responses, schema validation, and
escalation_response parsing.  All tests are offline — the LLM dispatcher
is a dependency-injected fake.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.hermes_skills.dev_assist_classifier.skill import (
    ClassificationResult,
    ClassifierSkill,
)


def _make_dispatcher(responses: list[str]):
    """Return a fake LLM dispatcher that yields pre-canned JSON responses."""

    idx = 0

    def dispatch(prompt: str) -> str:
        nonlocal idx
        if idx >= len(responses):
            return json.dumps({"kind": "freeform_chat", "details": {}})
        result = responses[idx]
        idx += 1
        return result

    return dispatch


def _make_raising_dispatcher(error: Exception):
    def dispatch(prompt: str) -> str:
        raise error

    return dispatch


class ClassifierIntakeTests(unittest.TestCase):
    def setUp(self):
        self.skill = ClassifierSkill(
            llm_dispatcher=_make_dispatcher([
                json.dumps({"kind": "intake", "details": {
                    "project": "test-project", "summary": "Build a CLI tool"
                }}),
            ])
        )

    def test_intake_classification(self):
        result = self.skill.classify(
            "I want to build a CLI tool for task tracking",
            founder_id="founder-1",
        )
        self.assertEqual(result.kind, "intake")
        self.assertEqual(result.intent.get("project"), "test-project")


class ClassifierProgressQueryTests(unittest.TestCase):
    def setUp(self):
        self.skill = ClassifierSkill(
            llm_dispatcher=_make_dispatcher([
                json.dumps({"kind": "progress_query", "details": {
                    "project_key": "chat:proj-alpha"
                }}),
            ])
        )

    def test_progress_query_classification(self):
        result = self.skill.classify(
            "What's the progress on proj-alpha?",
            founder_id="founder-1",
        )
        self.assertEqual(result.kind, "progress_query")
        self.assertEqual(
            result.intent.get("project_key"), "chat:proj-alpha"
        )


class ClassifierCommandTests(unittest.TestCase):
    def setUp(self):
        self.skill = ClassifierSkill(
            llm_dispatcher=_make_dispatcher([])
        )

    def test_start_command(self):
        result = self.skill.classify(
            "/start", founder_id="founder-1"
        )
        self.assertEqual(result.kind, "command")
        self.assertEqual(result.intent["command"], "start")

    def test_help_command(self):
        result = self.skill.classify(
            "/help", founder_id="founder-1"
        )
        self.assertEqual(result.kind, "command")
        self.assertEqual(result.intent["command"], "help")

    def test_status_command(self):
        result = self.skill.classify(
            "/status", founder_id="founder-1"
        )
        self.assertEqual(result.kind, "command")
        self.assertEqual(result.intent["command"], "status")

    def test_projects_command(self):
        result = self.skill.classify(
            "/projects", founder_id="founder-1"
        )
        self.assertEqual(result.kind, "command")
        self.assertEqual(result.intent["command"], "projects")

    def test_pause_command(self):
        result = self.skill.classify(
            "/pause", founder_id="founder-1"
        )
        self.assertEqual(result.kind, "command")
        self.assertEqual(result.intent["command"], "pause")

    def test_resume_command(self):
        result = self.skill.classify(
            "/resume", founder_id="founder-1"
        )
        self.assertEqual(result.kind, "command")
        self.assertEqual(result.intent["command"], "resume")


class ClassifierFreeformChatTests(unittest.TestCase):
    def setUp(self):
        self.skill = ClassifierSkill(
            llm_dispatcher=_make_dispatcher([
                json.dumps({"kind": "freeform_chat", "details": {
                    "text": "Hello how are you"
                }}),
            ])
        )

    def test_freeform_classification(self):
        result = self.skill.classify(
            "Hello how are you?", founder_id="founder-1"
        )
        self.assertEqual(result.kind, "freeform_chat")

    def test_ambiguous_falls_back_to_freeform(self):
        skill = ClassifierSkill(
            llm_dispatcher=_make_dispatcher([
                json.dumps({"kind": "freeform_chat", "details": {}}),
            ])
        )
        result = skill.classify(
            "hmm maybe I want to build something",
            founder_id="founder-1",
        )
        self.assertEqual(result.kind, "freeform_chat")


class ClassifierEscalationResponseTests(unittest.TestCase):
    def test_approve_command_extracts_id(self):
        skill = ClassifierSkill(
            llm_dispatcher=_make_dispatcher([])
        )
        result = skill.classify(
            "/approve 42", founder_id="founder-1"
        )
        self.assertEqual(result.kind, "escalation_response")
        self.assertEqual(result.intent["action"], "approve")
        self.assertEqual(result.intent["escalation_id"], 42)

    def test_deny_command_extracts_id(self):
        skill = ClassifierSkill(
            llm_dispatcher=_make_dispatcher([])
        )
        result = skill.classify(
            "/deny 7", founder_id="founder-1"
        )
        self.assertEqual(result.kind, "escalation_response")
        self.assertEqual(result.intent["action"], "deny")
        self.assertEqual(result.intent["escalation_id"], 7)


class ClassifierSchemaValidationTests(unittest.TestCase):
    def test_malformed_json_falls_back_to_freeform(self):
        skill = ClassifierSkill(
            llm_dispatcher=_make_dispatcher(["not-json-at-all"])
        )
        result = skill.classify(
            "Build a web app", founder_id="founder-1"
        )
        self.assertEqual(result.kind, "freeform_chat")

    def test_invalid_kind_falls_back_to_freeform(self):
        skill = ClassifierSkill(
            llm_dispatcher=_make_dispatcher([
                json.dumps({"kind": "invalid_kind", "details": {}})
            ])
        )
        result = skill.classify(
            "Build a web app", founder_id="founder-1"
        )
        self.assertEqual(result.kind, "freeform_chat")

    def test_missing_kind_falls_back_to_freeform(self):
        skill = ClassifierSkill(
            llm_dispatcher=_make_dispatcher([
                json.dumps({"details": {"project": "x"}})
            ])
        )
        result = skill.classify(
            "Some message", founder_id="founder-1"
        )
        self.assertEqual(result.kind, "freeform_chat")

    def test_non_dict_details_normalized(self):
        skill = ClassifierSkill(
            llm_dispatcher=_make_dispatcher([
                json.dumps({"kind": "intake", "details": "not-a-dict"})
            ])
        )
        result = skill.classify(
            "I need an API", founder_id="founder-1"
        )
        self.assertEqual(result.kind, "intake")
        self.assertEqual(result.intent, {})


class ClassifierDispatcherErrorTests(unittest.TestCase):
    def test_dispatcher_exception_falls_back_to_freeform(self):
        skill = ClassifierSkill(
            llm_dispatcher=_make_raising_dispatcher(RuntimeError("LLM down"))
        )
        result = skill.classify(
            "Build a CLI tool", founder_id="founder-1"
        )
        self.assertEqual(result.kind, "freeform_chat")


class ClassifierFreeTextEscalationResponseTests(unittest.TestCase):
    def setUp(self):
        self.lookup_calls: list[int] = []

    def _make_lookup(self, return_id: Optional[int]) -> object:
        def lookup(founder_id: str) -> Optional[int]:
            self.lookup_calls.append(return_id)
            return return_id
        return lookup

    def test_free_text_reply_injects_escalation_id_from_lookup(self):
        skill = ClassifierSkill(
            llm_dispatcher=_make_dispatcher([
                json.dumps({
                    "kind": "escalation_response",
                    "details": {"text": "Yes, go ahead"},
                }),
            ]),
            escalation_lookup=self._make_lookup(42),
        )
        result = skill.classify(
            "Yes, go ahead", founder_id="founder-1"
        )
        self.assertEqual(result.kind, "escalation_response")
        self.assertEqual(result.intent["escalation_id"], 42)
        self.assertIn("text", result.intent)

    def test_llm_includes_escalation_id_from_prompt_hint(self):
        skill = ClassifierSkill(
            llm_dispatcher=_make_dispatcher([
                json.dumps({
                    "kind": "escalation_response",
                    "details": {"text": "Let's do it", "escalation_id": 42},
                }),
            ]),
            escalation_lookup=self._make_lookup(42),
        )
        result = skill.classify(
            "Let's do it", founder_id="founder-1"
        )
        self.assertEqual(result.kind, "escalation_response")
        self.assertEqual(result.intent["escalation_id"], 42)

    def test_no_surfaced_escalation_escalation_response_without_id(self):
        skill = ClassifierSkill(
            llm_dispatcher=_make_dispatcher([
                json.dumps({
                    "kind": "escalation_response",
                    "details": {"text": "Just do it"},
                }),
            ]),
            escalation_lookup=self._make_lookup(None),
        )
        result = skill.classify(
            "Just do it", founder_id="founder-1"
        )
        self.assertEqual(result.kind, "escalation_response")
        self.assertNotIn("escalation_id", result.intent)

    def test_no_lookup_configured_preserves_original_behavior(self):
        skill = ClassifierSkill(
            llm_dispatcher=_make_dispatcher([
                json.dumps({
                    "kind": "escalation_response",
                    "details": {"text": "Reply text"},
                }),
            ]),
        )
        result = skill.classify(
            "Reply text", founder_id="founder-1"
        )
        self.assertEqual(result.kind, "escalation_response")
        self.assertNotIn("escalation_id", result.intent)

    def test_lookup_exception_falls_back_gracefully(self):
        def broken_lookup(founder_id: str) -> Optional[int]:
            raise RuntimeError("DB down")
        skill = ClassifierSkill(
            llm_dispatcher=_make_dispatcher([
                json.dumps({
                    "kind": "escalation_response",
                    "details": {"text": "OK"},
                }),
            ]),
            escalation_lookup=broken_lookup,
        )
        result = skill.classify(
            "OK", founder_id="founder-1"
        )
        self.assertEqual(result.kind, "escalation_response")
        self.assertNotIn("escalation_id", result.intent)


class ClassifierRuntimeLoadoutTests(unittest.TestCase):
    def test_runtime_loadout_is_orchestrator_only(self):
        skill = ClassifierSkill(
            llm_dispatcher=_make_dispatcher([])
        )
        self.assertEqual(skill.runtime_loadout, "orchestrator-only")


class ClassificationResultTests(unittest.TestCase):
    def test_result_dataclass_defaults(self):
        result = ClassificationResult(kind="intake")
        self.assertEqual(result.kind, "intake")
        self.assertEqual(result.intent, {})


if __name__ == "__main__":
    unittest.main()