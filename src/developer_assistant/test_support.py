"""Minimal offline test-support helpers for sanitized Telegram label assertions.

TKT-018@0.1.0 trial vehicle — offline-only, deterministic, no live services.

Provides helpers that make test assertions about sanitized labels like
`chat:founder` and `user:founder` easier to read, and reject raw numeric
identifiers and secret-looking values that must never appear in committed
artifacts.
"""

from __future__ import annotations

import re
from typing import Pattern

_SANITIZED_LABEL_RE: Pattern[str] = re.compile(
    r"^(chat|user|project|bot|gateway):[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"
)

_RAW_TELEGRAM_ID_RE: Pattern[str] = re.compile(r"^-?\d{6,}$")

_TELEGRAM_BOT_TOKEN_RE: Pattern[str] = re.compile(
    r"^\d{6,10}:AA[A-Za-z0-9_-]{30,40}$"
)

_GITHUB_TOKEN_PREFIXES: tuple[str, ...] = (
    "ghp_", "gho_", "ghu_", "ghs_", "ghr_",
)


def _looks_like_token_prefix(value: str) -> bool:
    lowered = value.lower()
    return any(lowered.startswith(prefix) for prefix in _GITHUB_TOKEN_PREFIXES)


def _looks_like_telegram_bot_token(value: str) -> bool:
    return bool(_TELEGRAM_BOT_TOKEN_RE.match(value))


def _looks_like_raw_telegram_id(value: str) -> bool:
    return bool(_RAW_TELEGRAM_ID_RE.match(value))


def is_sanitized_label(value: str) -> bool:
    """Return True if *value* is an acceptable sanitized label.

    Accepts labels matching ``prefix:name`` where *name* is lowercase
    alphanumeric with optional hyphen separators (e.g. ``chat:founder``,
    ``user:developer-1``, ``project:alpha``).

    Rejects raw numeric identifiers, GitHub token prefixes, and
    Telegram bot-token-shaped strings.
    """
    if not isinstance(value, str):
        return False

    stripped = value.strip()
    if not stripped or stripped != value:
        return False

    if _looks_like_raw_telegram_id(value):
        return False
    if _looks_like_token_prefix(value):
        return False
    if _looks_like_telegram_bot_token(value):
        return False

    return bool(_SANITIZED_LABEL_RE.match(value))


def assert_sanitized_label(label: str) -> None:
    """Assert that *label* is a valid sanitized label.

    Raises:
        AssertionError: if the label is rejected.
    """
    if not isinstance(label, str):
        raise AssertionError(
            f"Expected a string label, got {type(label).__name__}: {label!r}"
        )

    if not label:
        raise AssertionError("Label must not be empty.")

    stripped = label.strip()
    if stripped != label:
        raise AssertionError(
            f"Label must not have leading/trailing whitespace: {label!r}"
        )

    if _looks_like_raw_telegram_id(label):
        raise AssertionError(
            f"Label looks like a raw numeric Telegram ID and must not be "
            f"committed: {label!r}"
        )

    if _looks_like_token_prefix(label):
        raise AssertionError(
            f"Label starts with a GitHub token prefix and must not be "
            f"committed: {label!r}"
        )

    if _looks_like_telegram_bot_token(label):
        raise AssertionError(
            f"Label looks like a Telegram bot token and must not be "
            f"committed: {label!r}"
        )

    if not _SANITIZED_LABEL_RE.match(label):
        raise AssertionError(
            f"Label must match pattern 'prefix:name' (e.g. chat:founder), "
            f"got: {label!r}"
        )


def assert_sanitized_chat_label(label: str) -> None:
    """Assert that *label* is a valid sanitized chat label (``chat:...``)."""
    assert_sanitized_label(label)
    if not label.startswith("chat:"):
        raise AssertionError(
            f"Expected a chat: label, got: {label!r}"
        )


def assert_sanitized_user_label(label: str) -> None:
    """Assert that *label* is a valid sanitized user label (``user:...``)."""
    assert_sanitized_label(label)
    if not label.startswith("user:"):
        raise AssertionError(
            f"Expected a user: label, got: {label!r}"
        )