"""Hermes custom skill: dev-assist-classifier.

Orchestrator-only skill that classifies inbound Telegram messages into
one of five kinds and extracts intent payloads.  Calls the Orchestrator
runtime's main LLM through a dependency-injected dispatcher (never
hardcodes a model path or calls provider SDKs directly).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from developer_assistant.hermes_skills import load_locale_yaml

_PACKAGE_DIR = str(Path(__file__).resolve().parent)


@dataclass
class ClassificationResult:
    kind: str
    intent: dict[str, Any] = field(default_factory=dict)
    raw: str = ""


_COMMAND_RE = re.compile(r"^/(start|help|status|projects|pause|resume)\b")

_APPROVE_RE = re.compile(r"^/approve\s+(\d+)")
_DENY_RE = re.compile(r"^/deny\s+(\d+)")

_CLASSIFICATION_KINDS = frozenset([
    "intake",
    "progress_query",
    "command",
    "freeform_chat",
    "escalation_response",
])


class ClassifierSkill:
    """Classifies a Telegram message and extracts an intent payload.

    Loaded only by the Orchestrator runtime (MULTI-HERMES-CONTRACT.md § 5.1).
    """

    runtime_loadout: str = "orchestrator-only"

    def __init__(
        self,
        llm_dispatcher: Callable[[str], str],
        locale: Optional[dict[str, Any]] = None,
        escalation_lookup: Optional[Callable[[str], Optional[int]]] = None,
    ) -> None:
        self._llm = llm_dispatcher
        if locale is None:
            locale = load_locale_yaml(_PACKAGE_DIR)
        self._locale = locale
        self._escalation_lookup = escalation_lookup

    def classify(
        self,
        text: str,
        founder_id: str,
        current_session_state: Optional[dict[str, Any]] = None,
    ) -> ClassificationResult:
        """Classify *text* and return a kind + intent payload.

        Falls back to ``freeform_chat`` when the LLM returns a
        malformed response or the dispatcher raises.
        """
        stripped = text.strip()

        cmd_intent = self._try_match_command(stripped)
        if cmd_intent is not None:
            return ClassificationResult(
                kind="command",
                intent={"command": cmd_intent},
            )

        escalation_intent = self._try_match_escalation_response(stripped)
        if escalation_intent is not None:
            return ClassificationResult(
                kind="escalation_response",
                intent=escalation_intent,
            )

        most_recent_id = self._resolve_most_recent_escalation_id(founder_id)

        try:
            llm_response = self._llm(
                self._build_classification_prompt(stripped, most_recent_id)
            )
            parsed = self._validate_and_parse(llm_response, most_recent_id)
            return parsed
        except Exception:
            return ClassificationResult(
                kind="freeform_chat",
                intent={"text": text},
            )

    def _resolve_most_recent_escalation_id(
        self, founder_id: str
    ) -> Optional[int]:
        """Return the most recent surfaced escalation id for *founder_id*.

        Returns None if no escalation_lookup is configured or if the
        lookup callable returns None.
        """
        if self._escalation_lookup is None:
            return None
        try:
            return self._escalation_lookup(founder_id)
        except Exception:
            return None

    def _build_classification_prompt(
        self, text: str, most_recent_id: Optional[int] = None
    ) -> str:
        labels = self._locale.get("labels", {})
        kind_names = "\n".join(
            f"  - {v}" for v in labels.values()
        )
        prompt = (
            f"Классифицируй следующее сообщение в одно из намерений:\n"
            f"{kind_names}\n\n"
            f"Ответь строго в JSON формате:\n"
            f'{{"kind": "<намерение>", "details": {{}}}}\n\n'
        )
        if most_recent_id is not None:
            prompt += (
                f"Контекст: активна эскалация #{most_recent_id}, ожидающая ответа.\n"
                f"Если это ответ на эскалацию #{most_recent_id}, установи "
                f"kind=ответ_на_эскалацию и details.escalation_id={most_recent_id}.\n\n"
            )
        prompt += f"Сообщение: {text}"
        return prompt

    @staticmethod
    def _try_match_command(text: str) -> Optional[str]:
        m = _COMMAND_RE.match(text)
        if m is not None:
            return m.group(1)
        return None

    @staticmethod
    def _try_match_escalation_response(text: str) -> Optional[dict[str, Any]]:
        approve = _APPROVE_RE.match(text)
        if approve is not None:
            return {
                "action": "approve",
                "escalation_id": int(approve.group(1)),
            }
        deny = _DENY_RE.match(text)
        if deny is not None:
            return {
                "action": "deny",
                "escalation_id": int(deny.group(1)),
            }
        return None

    def _validate_and_parse(
        self, raw: str, most_recent_id: Optional[int] = None
    ) -> ClassificationResult:
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            raise ValueError(
                self._locale["errors"]["malformed_response"]
            )

        kind = data.get("kind", "")
        if kind not in _CLASSIFICATION_KINDS:
            raise ValueError(
                self._locale["errors"]["malformed_response"]
            )

        intent = data.get("details", {})
        if not isinstance(intent, dict):
            intent = {}

        if kind == "escalation_response" and not intent.get("escalation_id"):
            if most_recent_id is not None:
                intent["escalation_id"] = most_recent_id

        return ClassificationResult(kind=kind, intent=intent, raw=raw)