from __future__ import annotations

import os
import sqlite3
from typing import Any, Optional

from developer_assistant.hermes_plugins.dev_assist_escalation_policy.rules import (
    evaluate_rules,
    paid_llm_provider_outside_catalog,
)
from developer_assistant.hermes_plugins.dev_assist_escalation_policy.concept_classifier import (
    classify_concept_deviation,
    load_anchor,
    ConceptAnchor,
)
from developer_assistant.hermes_plugins.dev_assist_escalation_policy.redaction import redact_action_args
from developer_assistant.hermes_plugins.dev_assist_escalation_policy.advisory_narrative import generate_advisory_narrative

from developer_assistant.escalations import write_escalation
from developer_assistant import state_store

_READONLY_TOOLS = frozenset({
    "read_file", "list_files", "session_search", "memory_add",
    "memory_replace", "memory_remove", "search_files", "grep",
})

_WITHIN_CATALOG_MODELS = frozenset({
    "accounts/fireworks/models/minimax-m2p7",
    "accounts/fireworks/models/kimi-k2p6",
    "accounts/fireworks/models/qwen3p6-plus",
    "accounts/fireworks/models/deepseek-v4-pro",
    "accounts/fireworks/models/glm-5p1",
})

_DB_PATH = os.environ.get("DEV_ASSIST_OPERATIONAL_DB", ":memory:")


def _get_role() -> str:
    return os.environ.get("HERMES_DEVASSIST_ROLE", "unknown")


def _is_read_only(tool_name: str, action_args: dict) -> bool:
    role = _get_role()
    if tool_name in _READONLY_TOOLS:
        return True
    if tool_name.startswith("work_queue.") or tool_name.startswith("memory_"):
        if tool_name in ("memory_add", "memory_replace", "memory_remove"):
            memory_path = action_args.get("path", "")
            if f"runtimes/{role}/" in memory_path:
                return True
    return False


def _is_within_catalog(action_args: dict) -> bool:
    model = action_args.get("model", "")
    return model in _WITHIN_CATALOG_MODELS


def _write_escalation_row(
    trigger_kind: str,
    context: str,
    proposed_action: str,
    conn: sqlite3.Connection,
    narrative: Optional[str] = None,
    originating_work_item_id: Optional[int] = None,
) -> int:
    role = _get_role()
    urgency = "high" if any(x in trigger_kind for x in ("force_push", "drop_table", "secret:", "expose")) else "medium"
    options = ["approve", "deny"]
    return write_escalation(
        conn,
        originating_runtime=role,
        originating_work_item_id=originating_work_item_id,
        trigger_kind=trigger_kind,
        context=context,
        proposed_action=proposed_action,
        options=options,
        recommended_default="deny",
        impact=trigger_kind,
        urgency=urgency,
        durable_artifact_target="docs/questions/",
    )


def pre_tool_call(
    tool_name: str,
    action_args: dict,
    conn: Optional[sqlite3.Connection] = None,
    advisory_dispatcher: Optional[Any] = None,
    originating_work_item_id: Optional[int] = None,
) -> dict:
    if _is_read_only(tool_name, action_args):
        return {"decision": "allow"}

    redacted_args = redact_action_args(action_args)

    try:
        rule_result = evaluate_rules(tool_name, redacted_args)
    except Exception:
        try:
            if conn is None:
                conn = state_store.open_store(_DB_PATH)
            _write_escalation_row(
                "rule_engine_unavailable",
                "Rule engine raised an exception during evaluation",
                f"{tool_name}: {redacted_args}",
                conn,
                originating_work_item_id=originating_work_item_id,
            )
        except Exception:
            pass
        return {"decision": "blocked", "trigger_kind": "rule_engine_unavailable"}

    if rule_result is not None:
        trigger_kind = f"deterministic_rule:{rule_result}"
        try:
            if conn is None:
                conn = state_store.open_store(_DB_PATH)
            narrative = generate_advisory_narrative(
                rule_id=rule_result,
                cite=trigger_kind,
                context=f"Rule {rule_result} matched",
                proposed_action=f"{tool_name}: {redacted_args}",
                dispatcher=advisory_dispatcher,
            )
            _write_escalation_row(
                trigger_kind,
                f"Rule {rule_result} matched",
                f"{tool_name}: {redacted_args}",
                conn,
                narrative=narrative,
                originating_work_item_id=originating_work_item_id,
            )
        except Exception:
            pass
        return {"decision": "blocked", "trigger_kind": trigger_kind}

    if _is_within_catalog(action_args):
        return {"decision": "allow"}

    if tool_name in ("tool_call",) or action_args.get("_llm_call", False):
        outside_result = paid_llm_provider_outside_catalog(tool_name, redacted_args)
        if outside_result is not None:
            trigger_kind = f"deterministic_rule:{outside_result}"
            try:
                if conn is None:
                    conn = state_store.open_store(_DB_PATH)
                _write_escalation_row(
                    trigger_kind,
                    f"LLM provider outside catalog",
                    f"{tool_name}: {redacted_args}",
                    conn,
                    originating_work_item_id=originating_work_item_id,
                )
            except Exception:
                pass
            return {"decision": "blocked", "trigger_kind": trigger_kind}

    try:
        classifier_result = classify_concept_deviation(tool_name, redacted_args)
    except Exception:
        trigger_kind = "classifier_error"
        try:
            if conn is None:
                conn = state_store.open_store(_DB_PATH)
            _write_escalation_row(
                trigger_kind,
                "Classifier raised an exception",
                f"{tool_name}: {redacted_args}",
                conn,
                originating_work_item_id=originating_work_item_id,
            )
        except Exception:
            pass
        return {"decision": "blocked", "trigger_kind": trigger_kind}

    if classifier_result is not None:
        trigger_kind = classifier_result
        try:
            if conn is None:
                conn = state_store.open_store(_DB_PATH)
            rule_id = classifier_result.replace("concept_deviation:", "")
            narrative = generate_advisory_narrative(
                rule_id=rule_id,
                cite=trigger_kind,
                context=f"Concept deviation classifier matched rule {rule_id}",
                proposed_action=f"{tool_name}: {redacted_args}",
                dispatcher=advisory_dispatcher,
            )
            _write_escalation_row(
                trigger_kind,
                f"Concept deviation: {classifier_result}",
                f"{tool_name}: {redacted_args}",
                conn,
                narrative=narrative,
                originating_work_item_id=originating_work_item_id,
            )
        except Exception:
            pass
        return {"decision": "blocked", "trigger_kind": trigger_kind}

    return {"decision": "allow"}


def register(hooks: dict) -> None:
    hooks["pre_tool_call"] = pre_tool_call
