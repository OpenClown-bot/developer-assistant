"""Tests for the upstream Telegram adapter (TKT-024).

Tests target src.developer_assistant.upstream_adapters.telegram.
Do NOT modify or remove existing TKT-006 test classes in
tests/test_telegram_adapter.py.

Covers:
- Bound identity inbound: resolves founder_id + creates session, returns
  normalized dataclass
- Unbound identity inbound: no session created, no raise, dropped_inbound
  log event
- Outbound via mock: calls mock dispatcher with expected payload
- Approval prompt format: Russian text with all 7 required fields
"""

from __future__ import annotations

import logging
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.founder_identity import bind_founder_identity
from developer_assistant.state_store import open_store
from developer_assistant.upstream_adapters.base import (
    ApprovalPromptInput,
    BindFounderIdentityInput,
    DroppedInboundResult,
    GetOrCreateSessionInput,
    InboundMessageInput,
    InboundMessageResult,
    OutboundMessageInput,
)
from developer_assistant.upstream_adapters.telegram import (
    TelegramAdapter,
    format_approval_prompt_ru,
)
from developer_assistant.upstream_sessions import list_sessions


@dataclass
class _MockDispatchCall:
    skill_name: str
    action: str
    payload: Dict[str, Any]


class _MockHermesDispatcher:
    def __init__(self) -> None:
        self.calls: List[_MockDispatchCall] = []
        self._next_msg_id = 100

    def __call__(
        self, skill_name: str, action: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        self.calls.append(
            _MockDispatchCall(
                skill_name=skill_name, action=action, payload=payload
            )
        )
        msg_id = f"mock-msg-{self._next_msg_id}"
        self._next_msg_id += 1
        return {"message_id": msg_id}


def _make_adapter(
    conn, dispatcher=None
) -> TelegramAdapter:
    return TelegramAdapter(conn=conn, dispatcher=dispatcher or _MockHermesDispatcher())


def _bind_founder(conn, user_id: str = "tg-user-1", founder_id: str = "founder-1") -> None:
    bind_founder_identity(
        conn,
        founder_id=founder_id,
        adapter_id="telegram",
        upstream_user_id=user_id,
    )


class TestUpstreamTelegramAdapterInbound(unittest.TestCase):
    """TKT-024: Telegram adapter inbound tests."""

    def test_bound_identity_inbound_resolves_founder(self):
        conn = open_store(":memory:")
        adapter = _make_adapter(conn)
        _bind_founder(conn, user_id="tg-user-1", founder_id="founder-1")
        inp = InboundMessageInput(
            adapter_id="telegram",
            upstream_user_id="tg-user-1",
            upstream_chat_id="chat:proj-alpha",
            message_text="Привет!",
            message_id="msg-1",
            received_at="2026-05-07T12:00:00Z",
        )
        result = adapter.inbound_message(inp)
        self.assertIsInstance(result, InboundMessageResult)
        assert isinstance(result, InboundMessageResult)
        self.assertEqual(result.founder_id, "founder-1")
        self.assertEqual(result.adapter_id, "telegram")
        self.assertEqual(result.message_text, "Привет!")
        self.assertEqual(result.message_id_upstream, "msg-1")

    def test_bound_identity_inbound_creates_session(self):
        conn = open_store(":memory:")
        adapter = _make_adapter(conn)
        _bind_founder(conn, user_id="tg-user-1", founder_id="founder-1")
        inp = InboundMessageInput(
            adapter_id="telegram",
            upstream_user_id="tg-user-1",
            upstream_chat_id="chat:proj-alpha",
            message_text="hello",
            message_id="msg-2",
            received_at="2026-05-07T12:00:00Z",
        )
        result = adapter.inbound_message(inp)
        self.assertIsInstance(result, InboundMessageResult)
        assert isinstance(result, InboundMessageResult)
        self.assertEqual(result.session_id, "tg-chat:proj-alpha")
        sessions = list_sessions(conn, founder_id="founder-1")
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["adapter_id"], "telegram")

    def test_bound_identity_inbound_normalizes_dataclass(self):
        conn = open_store(":memory:")
        adapter = _make_adapter(conn)
        _bind_founder(conn)
        inp = InboundMessageInput(
            adapter_id="telegram",
            upstream_user_id="tg-user-1",
            upstream_chat_id="chat:proj-alpha",
            message_text="test",
            message_id="msg-3",
            received_at="2026-05-07T12:00:00Z",
            reply_to_message_id="msg-prev",
        )
        result = adapter.inbound_message(inp)
        self.assertIsInstance(result, InboundMessageResult)
        assert isinstance(result, InboundMessageResult)
        self.assertEqual(result.reply_to_message_id_upstream, "msg-prev")
        self.assertEqual(result.received_at, "2026-05-07T12:00:00Z")

    def test_unbound_identity_inbound_drops_message(self):
        conn = open_store(":memory:")
        adapter = _make_adapter(conn)
        inp = InboundMessageInput(
            adapter_id="telegram",
            upstream_user_id="tg-unbound-user",
            upstream_chat_id="chat:unknown",
            message_text="hello",
            message_id="msg-4",
            received_at="2026-05-07T12:00:00Z",
        )
        result = adapter.inbound_message(inp)
        self.assertIsInstance(result, DroppedInboundResult)
        assert isinstance(result, DroppedInboundResult)
        self.assertTrue(result.dropped)
        self.assertEqual(result.reason, "no_identity_binding")

    def test_unbound_identity_no_session_created(self):
        conn = open_store(":memory:")
        adapter = _make_adapter(conn)
        inp = InboundMessageInput(
            adapter_id="telegram",
            upstream_user_id="tg-unbound-user",
            upstream_chat_id="chat:unknown",
            message_text="hello",
            message_id="msg-5",
            received_at="2026-05-07T12:00:00Z",
        )
        adapter.inbound_message(inp)
        sessions = list_sessions(conn)
        self.assertEqual(len(sessions), 0)

    def test_unbound_identity_no_raise(self):
        conn = open_store(":memory:")
        adapter = _make_adapter(conn)
        inp = InboundMessageInput(
            adapter_id="telegram",
            upstream_user_id="tg-unbound-user",
            upstream_chat_id="chat:unknown",
            message_text="hello",
            message_id="msg-6",
            received_at="2026-05-07T12:00:00Z",
        )
        try:
            result = adapter.inbound_message(inp)
        except Exception:
            self.fail("inbound_message for unbound user must not raise")
        self.assertIsInstance(result, DroppedInboundResult)

    def test_unbound_identity_dropped_inbound_log(self):
        conn = open_store(":memory:")
        adapter = _make_adapter(conn)
        inp = InboundMessageInput(
            adapter_id="telegram",
            upstream_user_id="tg-unbound-user",
            upstream_chat_id="chat:unknown",
            message_text="hello",
            message_id="msg-7",
            received_at="2026-05-07T12:00:00Z",
        )
        with self.assertLogs("developer_assistant.upstream_adapters.telegram", level="INFO") as cm:
            adapter.inbound_message(inp)
        logged = " ".join(cm.output)
        self.assertIn("dropped_inbound", logged)

    def test_no_secrets_in_inbound_results(self):
        conn = open_store(":memory:")
        adapter = _make_adapter(conn)
        _bind_founder(conn)
        inp = InboundMessageInput(
            adapter_id="telegram",
            upstream_user_id="tg-user-1",
            upstream_chat_id="chat:proj-alpha",
            message_text="test",
            message_id="msg-8",
            received_at="2026-05-07T12:00:00Z",
        )
        result = adapter.inbound_message(inp)
        result_dict = result.__dict__
        for val in result_dict.values():
            if isinstance(val, str):
                self.assertNotIn("bot_token", val.lower())
                self.assertNotIn("telegram_token", val.lower())


class TestUpstreamTelegramAdapterOutbound(unittest.TestCase):
    """TKT-024: Telegram adapter outbound tests."""

    def test_outbound_calls_mock_dispatcher(self):
        conn = open_store(":memory:")
        mock = _MockHermesDispatcher()
        adapter = _make_adapter(conn, dispatcher=mock)
        _bind_founder(conn)
        adapter.inbound_message(InboundMessageInput(
            adapter_id="telegram",
            upstream_user_id="tg-user-1",
            upstream_chat_id="chat:proj-alpha",
            message_text="hello",
            message_id="msg-1",
            received_at="2026-05-07T12:00:00Z",
        ))
        out_inp = OutboundMessageInput(
            adapter_id="telegram",
            founder_id="founder-1",
            session_id="tg-chat:proj-alpha",
            message_text="Привет, основатель!",
            purpose="general_message",
        )
        result = adapter.outbound_message(out_inp)
        self.assertEqual(len(mock.calls), 1)
        call = mock.calls[0]
        self.assertEqual(call.skill_name, "telegram-gateway")
        self.assertEqual(call.action, "send_message")
        self.assertEqual(call.payload["chat_id"], "chat:proj-alpha")
        self.assertIn("Привет, основатель!", call.payload["text"])
        self.assertNotEqual(result.message_id_upstream, "")

    def test_outbound_returns_upstream_message_id(self):
        conn = open_store(":memory:")
        mock = _MockHermesDispatcher()
        adapter = _make_adapter(conn, dispatcher=mock)
        _bind_founder(conn)
        adapter.inbound_message(InboundMessageInput(
            adapter_id="telegram",
            upstream_user_id="tg-user-1",
            upstream_chat_id="chat:proj-alpha",
            message_text="hi",
            message_id="msg-1",
            received_at="2026-05-07T12:00:00Z",
        ))
        out_inp = OutboundMessageInput(
            adapter_id="telegram",
            founder_id="founder-1",
            session_id="tg-chat:proj-alpha",
            message_text="test",
        )
        result = adapter.outbound_message(out_inp)
        self.assertTrue(result.message_id_upstream.startswith("mock-msg-"))

    def test_outbound_missing_session_raises(self):
        conn = open_store(":memory:")
        mock = _MockHermesDispatcher()
        adapter = _make_adapter(conn, dispatcher=mock)
        out_inp = OutboundMessageInput(
            adapter_id="telegram",
            founder_id="founder-1",
            session_id="tg-nonexistent",
            message_text="test",
        )
        with self.assertRaises(ValueError):
            adapter.outbound_message(out_inp)

    def test_outbound_no_secrets_in_payload(self):
        conn = open_store(":memory:")
        mock = _MockHermesDispatcher()
        adapter = _make_adapter(conn, dispatcher=mock)
        _bind_founder(conn)
        adapter.inbound_message(InboundMessageInput(
            adapter_id="telegram",
            upstream_user_id="tg-user-1",
            upstream_chat_id="chat:proj-alpha",
            message_text="hi",
            message_id="msg-1",
            received_at="2026-05-07T12:00:00Z",
        ))
        adapter.outbound_message(OutboundMessageInput(
            adapter_id="telegram",
            founder_id="founder-1",
            session_id="tg-chat:proj-alpha",
            message_text="test",
        ))
        for call in mock.calls:
            for val in call.payload.values():
                if isinstance(val, str):
                    self.assertNotIn("bot_token", val.lower())


class TestUpstreamTelegramAdapterApprovalPrompt(unittest.TestCase):
    """TKT-024: Telegram adapter approval prompt tests."""

    def test_approval_prompt_format_russian_all_seven_fields(self):
        inp = ApprovalPromptInput(
            escalation_id=42,
            adapter_id="telegram",
            founder_id="founder-1",
            session_id="tg-chat:proj-alpha",
            prompt_text="Необходимо ваше одобрение",
            originating_runtime="executor",
            proposed_action="deploy to production",
            trigger_kind="deterministic_rule:deploy:start_units_unprompted",
            recommended_default="deny",
            impact="Production deployment of generated project",
            urgency="high",
        )
        text = format_approval_prompt_ru(inp)
        self.assertIn("Исходная среда выполнения", text)
        self.assertIn("executor", text)
        self.assertIn("Предлагаемое действие", text)
        self.assertIn("deploy to production", text)
        self.assertIn("Тип триггера", text)
        self.assertIn("deterministic_rule:deploy:start_units_unprompted", text)
        self.assertIn("Рекомендуемое значение по умолчанию", text)
        self.assertIn("deny", text)
        self.assertIn("Влияние", text)
        self.assertIn("Production deployment", text)
        self.assertIn("Срочность", text)
        self.assertIn("высокая", text)
        self.assertIn("Идентификатор эскалации", text)
        self.assertIn("42", text)

    def test_approval_prompt_urgency_low(self):
        inp = ApprovalPromptInput(
            escalation_id=1,
            adapter_id="telegram",
            founder_id="founder-1",
            session_id="tg-chat:x",
            prompt_text="",
            urgency="low",
        )
        text = format_approval_prompt_ru(inp)
        self.assertIn("низкая", text)

    def test_approval_prompt_urgency_medium(self):
        inp = ApprovalPromptInput(
            escalation_id=1,
            adapter_id="telegram",
            founder_id="founder-1",
            session_id="tg-chat:x",
            prompt_text="",
            urgency="medium",
        )
        text = format_approval_prompt_ru(inp)
        self.assertIn("средняя", text)

    def test_approval_prompt_includes_prompt_text(self):
        inp = ApprovalPromptInput(
            escalation_id=1,
            adapter_id="telegram",
            founder_id="founder-1",
            session_id="tg-chat:x",
            prompt_text="Подробное описание ситуации",
            urgency="low",
        )
        text = format_approval_prompt_ru(inp)
        self.assertIn("Подробное описание ситуации", text)

    def test_approval_prompt_dispatches_via_outbound(self):
        conn = open_store(":memory:")
        mock = _MockHermesDispatcher()
        adapter = _make_adapter(conn, dispatcher=mock)
        _bind_founder(conn)
        adapter.inbound_message(InboundMessageInput(
            adapter_id="telegram",
            upstream_user_id="tg-user-1",
            upstream_chat_id="chat:proj-alpha",
            message_text="hi",
            message_id="msg-1",
            received_at="2026-05-07T12:00:00Z",
        ))
        inp = ApprovalPromptInput(
            escalation_id=99,
            adapter_id="telegram",
            founder_id="founder-1",
            session_id="tg-chat:proj-alpha",
            prompt_text="Approve this",
            originating_runtime="executor",
            proposed_action="deploy",
            trigger_kind="rule:deploy",
            recommended_default="deny",
            impact="Production",
            urgency="high",
        )
        result = adapter.outbound_approval_prompt(inp)
        self.assertEqual(len(mock.calls), 1)
        sent_text = mock.calls[0].payload["text"]
        self.assertIn("Идентификатор эскалации", sent_text)
        self.assertIn("99", sent_text)
        self.assertNotEqual(result.message_id_upstream, "")


class TestUpstreamTelegramAdapterBindAndSession(unittest.TestCase):
    """TKT-024: Telegram adapter bind_founder_identity and get_or_create_session."""

    def test_bind_founder_identity(self):
        conn = open_store(":memory:")
        adapter = _make_adapter(conn)
        inp = BindFounderIdentityInput(
            founder_id="founder-1",
            adapter_id="telegram",
            upstream_user_id="tg-user-1",
            display_name="Founder",
        )
        result = adapter.bind_founder_identity(inp)
        self.assertIsInstance(result.binding_id, int)
        self.assertGreater(result.binding_id, 0)

    def test_get_or_create_session(self):
        conn = open_store(":memory:")
        adapter = _make_adapter(conn)
        inp = GetOrCreateSessionInput(
            session_id="tg-chat:proj-alpha",
            adapter_id="telegram",
            founder_id="founder-1",
            upstream_chat_id="chat:proj-alpha",
        )
        result = adapter.get_or_create_session(inp)
        self.assertEqual(result.session_id, "tg-chat:proj-alpha")
        self.assertEqual(result.adapter_id, "telegram")
        self.assertEqual(result.founder_id, "founder-1")
        self.assertEqual(result.upstream_chat_id, "chat:proj-alpha")
        self.assertFalse(result.paused)


if __name__ == "__main__":
    unittest.main()
