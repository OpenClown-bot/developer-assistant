"""Telegram upstream adapter per UPSTREAM-ADAPTER-CONTRACT.md §4 + §7.

Extends UpstreamAdapter. Consumes founder_identity and upstream_sessions
helpers (TKT-022). Calls Hermes telegram-gateway skill via an injectable
tool dispatcher (mockable in tests).
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import replace
from typing import Any, Callable, Dict, Optional, Protocol, runtime_checkable

from developer_assistant.founder_identity import (
    bind_founder_identity,
    lookup_founder_by_upstream_identity,
)
from developer_assistant.upstream_adapters.base import (
    ApprovalPromptInput,
    ApprovalPromptResult,
    BindFounderIdentityInput,
    BindFounderIdentityResult,
    DroppedInboundResult,
    GetOrCreateSessionInput,
    GetOrCreateSessionResult,
    InboundMessageInput,
    InboundMessageResult,
    OutboundMessageInput,
    OutboundMessageResult,
    UpstreamAdapter,
)
from developer_assistant.upstream_sessions import (
    get_or_create_session as _get_or_create_session,
    read_session,
)

logger = logging.getLogger(__name__)

_ADAPTER_ID = "telegram"


def _session_id_for_chat(upstream_chat_id: str) -> str:
    return f"tg-{upstream_chat_id}"


_URGENCY_RU = {
    "low": "низкая",
    "medium": "средняя",
    "high": "высокая",
}


def format_approval_prompt_ru(inp: ApprovalPromptInput) -> str:
    """Format a Russian-localized approval prompt per ESCALATION-POLICY.md §7.

    Must include all seven required fields:
    1. originating runtime
    2. proposed action
    3. trigger kind
    4. recommended default
    5. impact
    6. urgency
    7. escalation id
    """
    urgency_ru = _URGENCY_RU.get(inp.urgency, inp.urgency)
    lines = [
        f"Исходная среда выполнения: {inp.originating_runtime}",
        f"Предлагаемое действие: {inp.proposed_action}",
        f"Тип триггера: {inp.trigger_kind}",
        f"Рекомендуемое значение по умолчанию: {inp.recommended_default}",
        f"Влияние: {inp.impact}",
        f"Срочность: {urgency_ru}",
        f"Идентификатор эскалации: {inp.escalation_id}",
    ]
    if inp.prompt_text:
        lines.append("")
        lines.append(inp.prompt_text)
    return "\n".join(lines)


@runtime_checkable
class HermesToolDispatcher(Protocol):
    """Protocol for calling Hermes skills. Mockable in tests."""

    def __call__(
        self, skill_name: str, action: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        ...


def _default_dispatcher(
    skill_name: str, action: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    logger.warning(
        "default_dispatcher_called",
        extra={"skill_name": skill_name, "action": action},
    )
    return {"message_id": "mock-msg-id"}


class TelegramAdapter(UpstreamAdapter):
    """Telegram upstream adapter for v0.1.

    Uses the Hermes telegram-gateway skill for outbound delivery
    and TKT-022 helpers for identity and session management.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        dispatcher: Optional[HermesToolDispatcher] = None,
    ) -> None:
        self._conn = conn
        self._dispatcher: HermesToolDispatcher = dispatcher or _default_dispatcher

    @property
    def adapter_id(self) -> str:
        return _ADAPTER_ID

    def inbound_message(
        self, inp: InboundMessageInput
    ) -> InboundMessageResult | DroppedInboundResult:
        founder_id = lookup_founder_by_upstream_identity(
            self._conn,
            adapter_id=_ADAPTER_ID,
            upstream_user_id=inp.upstream_user_id,
        )
        if founder_id is None:
            logger.info(
                "dropped_inbound",
                extra={
                    "adapter_id": _ADAPTER_ID,
                    "upstream_user_id": inp.upstream_user_id,
                    "reason": "no_identity_binding",
                },
            )
            return DroppedInboundResult(
                adapter_id=_ADAPTER_ID,
                upstream_user_id=inp.upstream_user_id,
                reason="no_identity_binding",
            )

        session_id = _session_id_for_chat(inp.upstream_chat_id)
        session_row = _get_or_create_session(
            self._conn,
            session_id=session_id,
            adapter_id=_ADAPTER_ID,
            founder_id=founder_id,
            upstream_chat_id=inp.upstream_chat_id,
        )

        return InboundMessageResult(
            adapter_id=_ADAPTER_ID,
            founder_id=founder_id,
            session_id=session_id,
            message_text=inp.message_text,
            message_id_upstream=inp.message_id,
            reply_to_message_id_upstream=inp.reply_to_message_id,
            received_at=inp.received_at,
        )

    def outbound_message(
        self, inp: OutboundMessageInput
    ) -> OutboundMessageResult:
        session = read_session(self._conn, inp.session_id)
        if session is None:
            raise ValueError(f"Session not found: {inp.session_id!r}")

        chat_id = session["upstream_chat_id"]
        result = self._dispatcher(
            skill_name="telegram-gateway",
            action="send_message",
            payload={
                "chat_id": chat_id,
                "text": inp.message_text,
                "parse_mode": "Markdown",
            },
        )
        message_id = result.get("message_id", "")
        return OutboundMessageResult(message_id_upstream=message_id)

    def outbound_approval_prompt(
        self, inp: ApprovalPromptInput
    ) -> ApprovalPromptResult:
        russian_text = format_approval_prompt_ru(inp)
        outbound_inp = OutboundMessageInput(
            adapter_id=inp.adapter_id,
            founder_id=inp.founder_id,
            session_id=inp.session_id,
            message_text=russian_text,
            purpose="decision_response",
        )
        msg_result = self.outbound_message(outbound_inp)
        return ApprovalPromptResult(
            message_id_upstream=msg_result.message_id_upstream
        )

    def bind_founder_identity(
        self, inp: BindFounderIdentityInput
    ) -> BindFounderIdentityResult:
        row_id = bind_founder_identity(
            self._conn,
            founder_id=inp.founder_id,
            adapter_id=inp.adapter_id,
            upstream_user_id=inp.upstream_user_id,
            display_name=inp.display_name,
        )
        return BindFounderIdentityResult(binding_id=row_id)

    def get_or_create_session(
        self, inp: GetOrCreateSessionInput
    ) -> GetOrCreateSessionResult:
        session_row = _get_or_create_session(
            self._conn,
            session_id=inp.session_id,
            adapter_id=inp.adapter_id,
            founder_id=inp.founder_id,
            upstream_chat_id=inp.upstream_chat_id,
        )
        return GetOrCreateSessionResult(
            session_id=session_row["session_id"],
            adapter_id=session_row["adapter_id"],
            founder_id=session_row["founder_id"],
            upstream_chat_id=session_row["upstream_chat_id"],
            created_at=session_row["created_at"],
            last_message_at=session_row["last_message_at"],
            paused=bool(session_row["paused"]),
            current_project_id=session_row.get("current_project_id"),
        )
