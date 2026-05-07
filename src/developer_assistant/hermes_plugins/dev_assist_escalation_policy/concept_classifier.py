from __future__ import annotations

import os
import re
import signal
import fnmatch
from pathlib import Path
from typing import Any, Optional

import yaml

from developer_assistant.hermes_plugins.dev_assist_escalation_policy.redaction import redact_string, REDACTED_VALUE

_MINIMUM_ANCHOR_VERSION = "0.1.0"

_DEFAULT_CONCEPT_PATH = (
    "/srv/devassist/repo/docs/architecture/PROJECT-CONCEPT.md"
)

_env_path = os.environ.get("DEV_ASSIST_PROJECT_CONCEPT_PATH", _DEFAULT_CONCEPT_PATH)


class ConceptAnchor:
    def __init__(self, raw: dict) -> None:
        self.project_identity: dict = raw.get("project_identity", {})
        self.in_scope_v0_1: list[dict] = raw.get("in_scope_v0_1", [])
        self.budget_constraints: list[dict] = raw.get("budget_constraints", [])
        self.tech_anchors: list[dict] = raw.get("tech_anchors", [])
        self.risk_boundaries: list[dict] = raw.get("risk_boundaries", [])
        self.deviation_rules: list[dict] = raw.get("deviation_rules", [])


_anchor: Optional[ConceptAnchor] = None


def _parse_yaml_block(text: str) -> dict:
    in_block = False
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```yaml"):
            in_block = True
            continue
        if in_block and stripped.startswith("```"):
            break
        if in_block:
            lines.append(line)
    if not lines:
        raise ValueError("No YAML block found in PROJECT-CONCEPT.md")
    return yaml.safe_load("\n".join(lines))


def _check_version(frontmatter_text: str) -> None:
    m = re.search(r"^version:\s*(.+)$", frontmatter_text, re.MULTILINE)
    if not m:
        raise ValueError("Missing version in PROJECT-CONCEPT.md frontmatter")
    version = m.group(1).strip().strip("'\"")
    if version < _MINIMUM_ANCHOR_VERSION:
        raise ValueError(
            f"PROJECT-CONCEPT.md version {version} < minimum {_MINIMUM_ANCHOR_VERSION}"
        )


def load_anchor(path: Optional[str] = None) -> ConceptAnchor:
    global _anchor
    p = path or _env_path
    text = Path(p).read_text(encoding="utf-8")
    fm_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if fm_match:
        _check_version(fm_match.group(1))
    raw = _parse_yaml_block(text)
    anchor = ConceptAnchor(raw)
    _anchor = anchor
    return anchor


def _sighup_handler(signum: int, frame: Any) -> None:
    try:
        load_anchor()
    except Exception:
        pass


try:
    signal.signal(signal.SIGHUP, _sighup_handler)
except (AttributeError, OSError):
    pass


def _matches(action_kind: str, action_args: dict, match_spec: dict) -> bool:
    kind_match = match_spec.get("kind", "any_action")
    if kind_match != "any_action" and action_kind != kind_match:
        return False

    path_glob = match_spec.get("path_glob")
    if path_glob:
        path = action_args.get("path", "")
        if not fnmatch.fnmatch(path, path_glob):
            return False

    kw_set = match_spec.get("argument_keyword_set")
    if kw_set:
        operator = match_spec.get("operator", "OR")
        arg_str = " ".join(str(v) for v in action_args.values() if isinstance(v, str))
        arg_str = redact_string(arg_str)
        matches_found = [kw in arg_str for kw in kw_set]
        if operator == "OR":
            if not any(matches_found):
                return False
        else:
            if not all(matches_found):
                return False

    arg_regex = match_spec.get("argument_regex")
    if arg_regex:
        arg_str = " ".join(str(v) for v in action_args.values() if isinstance(v, str))
        arg_str = redact_string(arg_str)
        if not re.search(arg_regex, arg_str):
            return False

    content_regex = match_spec.get("content_regex")
    if content_regex:
        content = action_args.get("content", "")
        if not re.search(content_regex, content or ""):
            return False

    diff_touches = match_spec.get("content_diff_touches")
    if diff_touches:
        content = action_args.get("content", "")
        old_content = action_args.get("old_content", "")
        if not content:
            return False
        if old_content:
            added = set(content.splitlines()) - set(old_content.splitlines())
            added_text = "\n".join(added)
        else:
            added_text = content
        if not any(anchor in added_text for anchor in diff_touches):
            return False

    return True


def classify_concept_deviation(
    action_kind: str,
    action_args: dict,
    anchor: Optional[ConceptAnchor] = None,
) -> Optional[str]:
    if anchor is None:
        anchor = _anchor
    if anchor is None:
        return "concept:anchor_unavailable"
    try:
        for rule in anchor.deviation_rules:
            match_spec = rule.get("match", {})
            if _matches(action_kind, action_args, match_spec):
                verdict = rule.get("verdict", "")
                if verdict == "ESCALATE":
                    return f"concept_deviation:{rule['id']}"
                elif verdict == "PROCEED_OR_RULE_4_DECIDES":
                    from developer_assistant.hermes_plugins.dev_assist_escalation_policy.rules import evaluate_rules
                    rule_result = evaluate_rules(action_kind, action_args)
                    if rule_result is not None:
                        return rule_result
                    return None
                else:
                    return None
        return "concept_deviation:classifier_safety_default"
    except Exception:
        return "concept_deviation:classifier_error"


try:
    load_anchor()
except Exception:
    pass
