"""Tests for the upstream outbound Router (TKT-024).

Covers:
- Router resolves adapter via bindings and dispatches to outbound
- Router fails clearly when no binding exists for founder
- Router fails clearly when no session exists
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.founder_identity import bind_founder_identity
from developer_assistant.state_store import open_store
from developer_assistant.upstream_adapters.base import (
    ApprovalPromptResult,
    OutboundMessageResult,
)
from developer_assistant.upstream_adapters.registry import AdapterRegistry
from developer_assistant.upstream_adapters.router import (
    NoBindingError,
    NoSessionError,
    OutboundIntent,
    Router,
)
from developer_assistant.upstream_adapters.telegram import TelegramAdapter


@dataclass
class _MockDispatchCall:
    skill_name: str
    action: str
    payload: Dict[str, Any]


class _MockHermesDispatcher:
    def __init__(self) -> None:
        self.calls: List[_MockDispatchCall] = []
        self._next_msg_id = 200

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


def _make_router(conn=None, dispatcher=None) -> tuple:
    if conn is None:
        conn = open_store(":memory:")
    mock = dispatcher or _MockHermesDispatcher()
    adapter = TelegramAdapter(conn=conn, dispatcher=mock)
    registry = AdapterRegistry()
    registry.register("telegram", adapter)
    router = Router(registry=registry, conn=conn)
    return router, mock


class TestRouterResolvesAdapter(unittest.TestCase):
    """TKT-024: Router resolves adapter via bindings and dispatches."""

    def test_send_message_resolves_and_dispatches(self):
        conn = open_store(":memory:")
        router, mock = _make_router(conn=conn)
        bind_founder_identity(
            conn,
            founder_id="founder-1",
            adapter_id="telegram",
            upstream_user_id="tg-user-1",
        )
        from developer_assistant.upstream_adapters.base import InboundMessageInput
        adapter = router._registry.get("telegram")
        adapter.inbound_message(InboundMessageInput(
            adapter_id="telegram",
            upstream_user_id="tg-user-1",
            upstream_chat_id="chat:proj-alpha",
            message_text="hi",
            message_id="msg-1",
            received_at="2026-05-07T12:00:00Z",
        ))
        intent = OutboundIntent(
            kind="message",
            message_text="Привет!",
            purpose="general_message",
        )
        result = router.send_outbound_to_founder("founder-1", intent)
        self.assertIsInstance(result, OutboundMessageResult)
        assert isinstance(result, OutboundMessageResult)
        self.assertTrue(result.message_id_upstream.startswith("mock-msg-"))
        self.assertEqual(len(mock.calls), 1)
        self.assertEqual(mock.calls[0].skill_name, "telegram-gateway")

    def test_send_approval_resolves_and_dispatches(self):
        conn = open_store(":memory:")
        router, mock = _make_router(conn=conn)
        bind_founder_identity(
            conn,
            founder_id="founder-1",
            adapter_id="telegram",
            upstream_user_id="tg-user-1",
        )
        from developer_assistant.upstream_adapters.base import InboundMessageInput
        adapter = router._registry.get("telegram")
        adapter.inbound_message(InboundMessageInput(
            adapter_id="telegram",
            upstream_user_id="tg-user-1",
            upstream_chat_id="chat:proj-alpha",
            message_text="hi",
            message_id="msg-1",
            received_at="2026-05-07T12:00:00Z",
        ))
        intent = OutboundIntent(
            kind="approval_prompt",
            message_text="Approve deployment?",
            escalation_id=42,
            originating_runtime="executor",
            proposed_action="deploy to production",
            trigger_kind="deterministic_rule:deploy:start_units_unprompted",
            recommended_default="deny",
            impact="Production deployment",
            urgency="high",
        )
        result = router.send_outbound_to_founder("founder-1", intent)
        self.assertIsInstance(result, ApprovalPromptResult)
        assert isinstance(result, ApprovalPromptResult)
        self.assertTrue(result.message_id_upstream.startswith("mock-msg-"))
        sent_text = mock.calls[0].payload["text"]
        self.assertIn("Идентификатор эскалации", sent_text)
        self.assertIn("42", sent_text)


class TestRouterNoBinding(unittest.TestCase):
    """TKT-024: Router fails clearly when no binding exists."""

    def test_no_binding_raises_informative_error(self):
        conn = open_store(":memory:")
        router, _ = _make_router(conn=conn)
        intent = OutboundIntent(kind="message", message_text="test")
        with self.assertRaises(NoBindingError) as ctx:
            router.send_outbound_to_founder("founder-unknown", intent)
        self.assertEqual(ctx.exception.founder_id, "founder-unknown")
        self.assertIn("founder-unknown", str(ctx.exception))

    def test_no_binding_error_has_founder_id(self):
        conn = open_store(":memory:")
        router, _ = _make_router(conn=conn)
        intent = OutboundIntent(kind="message", message_text="test")
        with self.assertRaises(NoBindingError) as ctx:
            router.send_outbound_to_founder("no-such-founder", intent)
        err = ctx.exception
        self.assertEqual(err.founder_id, "no-such-founder")


class TestRouterNoSession(unittest.TestCase):
    """TKT-024: Router fails clearly when no session exists."""

    def test_no_session_raises_informative_error(self):
        conn = open_store(":memory:")
        router, _ = _make_router(conn=conn)
        bind_founder_identity(
            conn,
            founder_id="founder-1",
            adapter_id="telegram",
            upstream_user_id="tg-user-1",
        )
        intent = OutboundIntent(kind="message", message_text="test")
        with self.assertRaises(NoSessionError) as ctx:
            router.send_outbound_to_founder("founder-1", intent)
        self.assertEqual(ctx.exception.founder_id, "founder-1")
        self.assertEqual(ctx.exception.adapter_id, "telegram")
        self.assertIn("founder-1", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
