from __future__ import annotations

import re

REDACTION_PATTERNS: dict[str, str] = {
    "ENV_TOKEN": r"(?i)^.*_TOKEN\s*=\s*(.+)$",
    "ENV_API_KEY": r"(?i)^.*_API_KEY\s*=\s*(.+)$",
    "ENV_SECRET": r"(?i)^.*_SECRET\s*=\s*(.+)$",
    "ENV_PASSWORD": r"(?i)^.*_PASSWORD\s*=\s*(.+)$",
    "SK_TOKEN": r"sk-[A-Za-z0-9]{20,}",
    "GHP_TOKEN": r"ghp_[A-Za-z0-9]{36}",
    "TELEGRAM_BOT_TOKEN": r"[0-9]{8,10}:AA[A-Za-z0-9_-]{33}",
    "OPENROUTER_KEY": r"sk-or-[A-Za-z0-9\-]{30,}",
    "OMNIROUTE_KEY": r"sk-omni-[A-Za-z0-9\-]{20,}",
}

REDACTED_VALUE = "<REDACTED>"

_compiled_patterns: dict[str, re.Pattern[str]] = {
    name: re.compile(pat) for name, pat in REDACTION_PATTERNS.items()
}


def redact_string(text: str) -> str:
    result = text
    for _name, pat in _compiled_patterns.items():
        result = pat.sub(REDACTED_VALUE, result)
    return result


def redact_action_args(args: dict) -> dict:
    redacted: dict = {}
    for key, value in args.items():
        if isinstance(value, str):
            redacted[key] = redact_string(value)
        elif isinstance(value, dict):
            redacted[key] = redact_action_args(value)
        elif isinstance(value, list):
            redacted[key] = [
                redact_string(v) if isinstance(v, str) else v for v in value
            ]
        else:
            redacted[key] = value
    return redacted
