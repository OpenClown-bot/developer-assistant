"""Abstract base class for upstream adapters per UPSTREAM-ADAPTER-CONTRACT.md v0.1.0 §4.

Defines five operations with typed dataclass inputs/outputs.
No untyped dicts in public signatures.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class InboundMessageInput:
    adapter_id: str
    upstream_user_id: str
    upstream_chat_id: str
    message_text: str
    message_id: str
    received_at: str
    reply_to_message_id: Optional[str] = None
    attachments: list[str] = field(default_factory=list)


@dataclass
class InboundMessageResult:
    adapter_id: str
    founder_id: str
    session_id: str
    message_text: str
    message_id_upstream: str
    received_at: str
    reply_to_message_id_upstream: Optional[str] = None


@dataclass
class DroppedInboundResult:
    adapter_id: str
    upstream_user_id: str
    reason: str
    dropped: bool = True


@dataclass
class OutboundMessageInput:
    adapter_id: str
    founder_id: str
    session_id: str
    message_text: str
    purpose: str = "general_message"
    parent_message_id_upstream: Optional[str] = None


@dataclass
class OutboundMessageResult:
    message_id_upstream: str


@dataclass
class ApprovalPromptInput:
    escalation_id: int
    adapter_id: str
    founder_id: str
    session_id: str
    prompt_text: str
    originating_runtime: str = ""
    proposed_action: str = ""
    trigger_kind: str = ""
    recommended_default: str = ""
    impact: str = ""
    urgency: str = "low"
    response_modes: list[str] = field(
        default_factory=lambda: ["slash_command", "inline_buttons", "free_text"]
    )


@dataclass
class ApprovalPromptResult:
    message_id_upstream: str


@dataclass
class BindFounderIdentityInput:
    founder_id: str
    adapter_id: str
    upstream_user_id: str
    display_name: Optional[str] = None


@dataclass
class BindFounderIdentityResult:
    binding_id: int


@dataclass
class GetOrCreateSessionInput:
    session_id: str
    adapter_id: str
    founder_id: str
    upstream_chat_id: str


@dataclass
class GetOrCreateSessionResult:
    session_id: str
    adapter_id: str
    founder_id: str
    upstream_chat_id: str
    created_at: str
    last_message_at: str
    paused: bool
    current_project_id: Optional[int] = None


class UpstreamAdapter(ABC):
    """Abstract base for all upstream adapters.

    Each adapter must implement exactly five operations
    per UPSTREAM-ADAPTER-CONTRACT.md §4.
    """

    @abstractmethod
    def inbound_message(
        self, inp: InboundMessageInput
    ) -> InboundMessageResult | DroppedInboundResult:
        ...

    @abstractmethod
    def outbound_message(
        self, inp: OutboundMessageInput
    ) -> OutboundMessageResult:
        ...

    @abstractmethod
    def outbound_approval_prompt(
        self, inp: ApprovalPromptInput
    ) -> ApprovalPromptResult:
        ...

    @abstractmethod
    def bind_founder_identity(
        self, inp: BindFounderIdentityInput
    ) -> BindFounderIdentityResult:
        ...

    @abstractmethod
    def get_or_create_session(
        self, inp: GetOrCreateSessionInput
    ) -> GetOrCreateSessionResult:
        ...
