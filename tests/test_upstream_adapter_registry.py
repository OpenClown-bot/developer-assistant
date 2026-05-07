"""Tests for the upstream-adapter registry (TKT-024).

Covers:
- Registry duplicate rejection
- Registry lookup missing -> structured error
- Registry iteration order
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.upstream_adapters.base import (
    DroppedInboundResult,
    InboundMessageInput,
    InboundMessageResult,
    UpstreamAdapter,
)
from developer_assistant.upstream_adapters.registry import (
    AdapterNotFoundError,
    AdapterRegistry,
    DuplicateAdapterError,
)


class _StubAdapter(UpstreamAdapter):
    def inbound_message(self, inp):
        return DroppedInboundResult(
            adapter_id=inp.adapter_id,
            upstream_user_id=inp.upstream_user_id,
            reason="stub",
        )

    def outbound_message(self, inp):
        from developer_assistant.upstream_adapters.base import OutboundMessageResult
        return OutboundMessageResult(message_id_upstream="stub-out")

    def outbound_approval_prompt(self, inp):
        from developer_assistant.upstream_adapters.base import ApprovalPromptResult
        return ApprovalPromptResult(message_id_upstream="stub-approval")

    def bind_founder_identity(self, inp):
        from developer_assistant.upstream_adapters.base import BindFounderIdentityResult
        return BindFounderIdentityResult(binding_id=1)

    def get_or_create_session(self, inp):
        from developer_assistant.upstream_adapters.base import GetOrCreateSessionResult
        return GetOrCreateSessionResult(
            session_id=inp.session_id,
            adapter_id=inp.adapter_id,
            founder_id=inp.founder_id,
            upstream_chat_id=inp.upstream_chat_id,
            created_at="2026-05-07T00:00:00Z",
            last_message_at="2026-05-07T00:00:00Z",
            paused=False,
        )


class TestRegistryDuplicateRejection(unittest.TestCase):
    def test_register_rejects_duplicate(self):
        registry = AdapterRegistry()
        a1 = _StubAdapter()
        registry.register("telegram", a1)
        with self.assertRaises(DuplicateAdapterError) as ctx:
            registry.register("telegram", _StubAdapter())
        self.assertEqual(ctx.exception.adapter_id, "telegram")

    def test_different_ids_allowed(self):
        registry = AdapterRegistry()
        registry.register("telegram", _StubAdapter())
        registry.register("openclaw", _StubAdapter())
        self.assertTrue(registry.has("telegram"))
        self.assertTrue(registry.has("openclaw"))


class TestRegistryLookup(unittest.TestCase):
    def test_get_returns_registered_impl(self):
        registry = AdapterRegistry()
        a = _StubAdapter()
        registry.register("telegram", a)
        result = registry.get("telegram")
        self.assertIs(result, a)

    def test_get_missing_raises_structured_error(self):
        registry = AdapterRegistry()
        with self.assertRaises(AdapterNotFoundError) as ctx:
            registry.get("nonexistent")
        self.assertEqual(ctx.exception.adapter_id, "nonexistent")
        self.assertIn("nonexistent", str(ctx.exception))

    def test_has_returns_false_for_unregistered(self):
        registry = AdapterRegistry()
        self.assertFalse(registry.has("missing"))


class TestRegistryIterationOrder(unittest.TestCase):
    def test_iter_adapters_returns_registration_order(self):
        registry = AdapterRegistry()
        a1 = _StubAdapter()
        a2 = _StubAdapter()
        a3 = _StubAdapter()
        registry.register("telegram", a1)
        registry.register("openclaw", a2)
        registry.register("a2a", a3)
        ids = [aid for aid, _ in registry.iter_adapters()]
        self.assertEqual(ids, ["telegram", "openclaw", "a2a"])

    def test_iter_adapters_empty_registry(self):
        registry = AdapterRegistry()
        ids = list(registry.iter_adapters())
        self.assertEqual(ids, [])


if __name__ == "__main__":
    unittest.main()
