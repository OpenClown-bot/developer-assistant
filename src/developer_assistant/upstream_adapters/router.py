"""Outbound routing helper per UPSTREAM-ADAPTER-CONTRACT.md §6.

Given a founder_id and an outbound intent, resolves the adapter via
the bindings table, looks up the session, and dispatches to
outbound_message or outbound_approval_prompt on the resolved adapter.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Optional

from developer_assistant.founder_identity import lookup_founder_by_upstream_identity
from developer_assistant.upstream_adapters.base import (
    ApprovalPromptInput,
    ApprovalPromptResult,
    OutboundMessageInput,
    OutboundMessageResult,
)
from developer_assistant.upstream_adapters.registry import AdapterRegistry
from developer_assistant.upstream_sessions import list_sessions

logger = logging.getLogger(__name__)


class NoBindingError(Exception):
    """Raised when no adapter binding exists for the given founder_id."""

    def __init__(self, founder_id: str) -> None:
        self.founder_id = founder_id
        super().__init__(
            f"No adapter binding found for founder_id={founder_id!r}"
        )


class NoSessionError(Exception):
    """Raised when no active session exists for the resolved adapter."""

    def __init__(self, founder_id: str, adapter_id: str) -> None:
        self.founder_id = founder_id
        self.adapter_id = adapter_id
        super().__init__(
            f"No session found for founder_id={founder_id!r} "
            f"on adapter={adapter_id!r}"
        )


@dataclass
class OutboundIntent:
    """Describes what the router should send to the founder.

    kind='message' -> dispatches to outbound_message
    kind='approval_prompt' -> dispatches to outbound_approval_prompt
    """

    kind: str
    message_text: str
    purpose: str = "general_message"
    escalation_id: Optional[int] = None
    originating_runtime: str = ""
    proposed_action: str = ""
    trigger_kind: str = ""
    recommended_default: str = ""
    impact: str = ""
    urgency: str = "low"
    response_modes: Optional[list[str]] = None
    parent_message_id_upstream: Optional[str] = None


class Router:
    """Routes outbound messages and approval prompts to the correct adapter.

    Resolves adapter via the founder_identity_bindings table,
    looks up the session, and dispatches.
    """

    def __init__(
        self,
        registry: AdapterRegistry,
        conn: sqlite3.Connection,
        default_adapter_id: str = "telegram",
    ) -> None:
        self._registry = registry
        self._conn = conn
        self._default_adapter_id = default_adapter_id

    def _resolve_adapter_id(self, founder_id: str) -> str:
        """Resolve adapter_id for a founder by checking bindings.

        Falls back to default_adapter_id if no binding found but at
        least one binding exists for the founder on any adapter.
        """
        cur = self._conn.execute(
            "SELECT adapter_id FROM founder_identity_bindings "
            "WHERE founder_id = ? AND revoked_at IS NULL "
            "ORDER BY bound_at DESC LIMIT 1",
            (founder_id,),
        )
        row = cur.fetchone()
        if row is not None:
            return row["adapter_id"]
        raise NoBindingError(founder_id)

    def _resolve_session_id(
        self, founder_id: str, adapter_id: str
    ) -> str:
        """Find an active session for the founder on the given adapter."""
        sessions = list_sessions(
            self._conn, founder_id=founder_id, paused=False
        )
        for s in sessions:
            if s["adapter_id"] == adapter_id:
                return s["session_id"]
        all_sessions = list_sessions(self._conn, founder_id=founder_id)
        for s in all_sessions:
            if s["adapter_id"] == adapter_id:
                return s["session_id"]
        raise NoSessionError(founder_id, adapter_id)

    def send_outbound_to_founder(
        self, founder_id: str, intent: OutboundIntent
    ) -> OutboundMessageResult | ApprovalPromptResult:
        """Resolve adapter and session, then dispatch to the right operation.

        Raises:
            NoBindingError: if no adapter binding exists for founder_id.
            NoSessionError: if no session exists for the resolved adapter.
        """
        adapter_id = self._resolve_adapter_id(founder_id)
        adapter = self._registry.get(adapter_id)
        session_id = self._resolve_session_id(founder_id, adapter_id)

        if intent.kind == "approval_prompt":
            prompt_inp = ApprovalPromptInput(
                escalation_id=intent.escalation_id or 0,
                adapter_id=adapter_id,
                founder_id=founder_id,
                session_id=session_id,
                prompt_text=intent.message_text,
                originating_runtime=intent.originating_runtime,
                proposed_action=intent.proposed_action,
                trigger_kind=intent.trigger_kind,
                recommended_default=intent.recommended_default,
                impact=intent.impact,
                urgency=intent.urgency,
                response_modes=intent.response_modes or [],
            )
            return adapter.outbound_approval_prompt(prompt_inp)

        msg_inp = OutboundMessageInput(
            adapter_id=adapter_id,
            founder_id=founder_id,
            session_id=session_id,
            message_text=intent.message_text,
            purpose=intent.purpose,
            parent_message_id_upstream=intent.parent_message_id_upstream,
        )
        return adapter.outbound_message(msg_inp)
