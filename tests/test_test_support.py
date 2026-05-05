"""Tests for TKT-018 test-support helpers.

TKT-018@0.1.0 trial vehicle — all tests are offline-only and deterministic.
"""

import unittest

from src.developer_assistant.test_support import (
    assert_sanitized_chat_label,
    assert_sanitized_label,
    assert_sanitized_user_label,
    is_sanitized_label,
)


class TestIsSanitizedLabel(unittest.TestCase):
    """``is_sanitized_label`` predicate tests."""

    def test_accepts_chat_founder(self) -> None:
        self.assertTrue(is_sanitized_label("chat:founder"))

    def test_accepts_user_founder(self) -> None:
        self.assertTrue(is_sanitized_label("user:founder"))

    def test_accepts_chat_project_alpha(self) -> None:
        self.assertTrue(is_sanitized_label("chat:project-alpha"))

    def test_accepts_user_developer_1(self) -> None:
        self.assertTrue(is_sanitized_label("user:developer-1"))

    def test_accepts_project_label(self) -> None:
        self.assertTrue(is_sanitized_label("project:active"))

    def test_accepts_bot_label(self) -> None:
        self.assertTrue(is_sanitized_label("bot:hermes"))

    def test_accepts_gateway_label(self) -> None:
        self.assertTrue(is_sanitized_label("gateway:primary"))

    def test_accepts_single_char_name(self) -> None:
        self.assertTrue(is_sanitized_label("chat:a"))

    def test_rejects_raw_numeric_id(self) -> None:
        self.assertFalse(is_sanitized_label("123456789"))

    def test_rejects_negative_telegram_id(self) -> None:
        self.assertFalse(is_sanitized_label("-1001234567890"))

    def test_rejects_six_digit_id(self) -> None:
        self.assertFalse(is_sanitized_label("123456"))

    def test_rejects_seven_digit_id(self) -> None:
        self.assertFalse(is_sanitized_label("1234567"))

    def test_rejects_long_numeric_id(self) -> None:
        self.assertFalse(is_sanitized_label("99999999999999"))

    def test_rejects_ghp_token_prefix(self) -> None:
        self.assertFalse(is_sanitized_label("ghp_example123"))

    def test_rejects_gho_token_prefix(self) -> None:
        self.assertFalse(is_sanitized_label("gho_example123"))

    def test_rejects_ghu_token_prefix(self) -> None:
        self.assertFalse(is_sanitized_label("ghu_example123"))

    def test_rejects_ghs_token_prefix(self) -> None:
        self.assertFalse(is_sanitized_label("ghs_example123"))

    def test_rejects_ghr_token_prefix(self) -> None:
        self.assertFalse(is_sanitized_label("ghr_example123"))

    def test_rejects_uppercase_ghp(self) -> None:
        self.assertFalse(is_sanitized_label("GHP_example123"))

    def test_rejects_telegram_bot_token_shape(self) -> None:
        self.assertFalse(is_sanitized_label(
            "123456789:AAbbCCddEEffGGhhIIjjKKllMMnnOOppQQrrSS"
        ))

    def test_rejects_telegram_bot_token_minimal(self) -> None:
        self.assertFalse(is_sanitized_label(
            "123456:AAabcdefghijklmnopqrstuvwxyz1234567890"
        ))

    def test_rejects_empty_string(self) -> None:
        self.assertFalse(is_sanitized_label(""))

    def test_rejects_whitespace_only(self) -> None:
        self.assertFalse(is_sanitized_label("   "))

    def test_rejects_leading_whitespace(self) -> None:
        self.assertFalse(is_sanitized_label(" chat:founder"))

    def test_rejects_trailing_whitespace(self) -> None:
        self.assertFalse(is_sanitized_label("chat:founder "))

    def test_rejects_non_string(self) -> None:
        self.assertFalse(is_sanitized_label(42))  # type: ignore[arg-type]

    def test_rejects_none(self) -> None:
        self.assertFalse(is_sanitized_label(None))  # type: ignore[arg-type]

    def test_rejects_missing_prefix(self) -> None:
        self.assertFalse(is_sanitized_label("founder"))

    def test_rejects_uppercase_prefix(self) -> None:
        self.assertFalse(is_sanitized_label("CHAT:founder"))

    def test_rejects_underscore_in_name(self) -> None:
        self.assertFalse(is_sanitized_label("chat:my_user"))

    def test_rejects_hyphen_at_start(self) -> None:
        self.assertFalse(is_sanitized_label("chat:-founder"))


class TestAssertSanitizedLabel(unittest.TestCase):
    """``assert_sanitized_label`` tests."""

    def test_passes_for_valid_label(self) -> None:
        assert_sanitized_label("chat:founder")

    def test_passes_for_user_label(self) -> None:
        assert_sanitized_label("user:developer")

    def test_passes_for_project_label(self) -> None:
        assert_sanitized_label("project:alpha")

    def test_raises_for_raw_id(self) -> None:
        with self.assertRaises(AssertionError) as ctx:
            assert_sanitized_label("123456789")
        self.assertIn("raw numeric", ctx.exception.args[0].lower())

    def test_raises_for_token_prefix(self) -> None:
        with self.assertRaises(AssertionError) as ctx:
            assert_sanitized_label("ghp_example")
        self.assertIn("token prefix", ctx.exception.args[0].lower())

    def test_raises_for_bot_token(self) -> None:
        with self.assertRaises(AssertionError) as ctx:
            assert_sanitized_label(
                "123456789:AAbbCCddEEffGGhhIIjjKKllMMnnOOppQQrrSS"
            )
        self.assertIn("bot token", ctx.exception.args[0].lower())

    def test_raises_for_empty(self) -> None:
        with self.assertRaises(AssertionError) as ctx:
            assert_sanitized_label("")
        self.assertIn("empty", ctx.exception.args[0].lower())

    def test_raises_for_non_string(self) -> None:
        with self.assertRaises(AssertionError) as ctx:
            assert_sanitized_label(123)  # type: ignore[arg-type]
        self.assertIn("string", ctx.exception.args[0].lower())

    def test_raises_for_whitespace(self) -> None:
        with self.assertRaises(AssertionError) as ctx:
            assert_sanitized_label(" chat:founder")
        self.assertIn("whitespace", ctx.exception.args[0].lower())

    def test_raises_for_bad_format(self) -> None:
        with self.assertRaises(AssertionError) as ctx:
            assert_sanitized_label("founder")
        self.assertIn("prefix", ctx.exception.args[0].lower())

    def test_failure_message_includes_actual_value(self) -> None:
        with self.assertRaises(AssertionError) as ctx:
            assert_sanitized_label("123456789")
        self.assertIn("123456789", ctx.exception.args[0])


class TestAssertSanitizedChatLabel(unittest.TestCase):
    """``assert_sanitized_chat_label`` tests."""

    def test_passes_for_chat_founder(self) -> None:
        assert_sanitized_chat_label("chat:founder")

    def test_passes_for_chat_project(self) -> None:
        assert_sanitized_chat_label("chat:project")

    def test_raises_for_user_label(self) -> None:
        with self.assertRaises(AssertionError) as ctx:
            assert_sanitized_chat_label("user:founder")
        self.assertIn("chat:", ctx.exception.args[0])

    def test_raises_for_raw_id(self) -> None:
        with self.assertRaises(AssertionError):
            assert_sanitized_chat_label("123456789")

    def test_raises_for_token_prefix(self) -> None:
        with self.assertRaises(AssertionError):
            assert_sanitized_chat_label("ghp_example")


class TestAssertSanitizedUserLabel(unittest.TestCase):
    """``assert_sanitized_user_label`` tests."""

    def test_passes_for_user_founder(self) -> None:
        assert_sanitized_user_label("user:founder")

    def test_passes_for_user_developer(self) -> None:
        assert_sanitized_user_label("user:developer")

    def test_raises_for_chat_label(self) -> None:
        with self.assertRaises(AssertionError) as ctx:
            assert_sanitized_user_label("chat:founder")
        self.assertIn("user:", ctx.exception.args[0])

    def test_raises_for_raw_id(self) -> None:
        with self.assertRaises(AssertionError):
            assert_sanitized_user_label("123456789")

    def test_raises_for_bot_token(self) -> None:
        with self.assertRaises(AssertionError):
            assert_sanitized_user_label(
                "123456789:AAbbCCddEEffGGhhIIjjKKllMMnnOOppQQrrSS"
            )