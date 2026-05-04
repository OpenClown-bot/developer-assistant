"""Hermes Telegram gateway transport binding for TKT-006 adapter.

Wires the TKT-006 Telegram founder interaction adapter to live Hermes
Telegram gateway transport for one trusted founder and one active project.

Inbound: converts Hermes Telegram gateway payloads into TelegramEvent
with sanitized chat/user keys. Enforces founder allowlist or DM pairing
before adapter handling.

Outbound: binds TelegramSender.send() to a Hermes Telegram gateway
transport abstraction that preserves Russian founder-facing text.

Security: no tokens, raw chat IDs, or raw user IDs in committed artifacts,
fixtures, logs, or errors. GATEWAY_ALLOW_ALL_USERS and TELEGRAM_ALLOW_ALL_USERS
remain unset/false. Polling is preferred for v0.1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .telegram_adapter import (
    ClassificationResult,
    CommandResult,
    FounderAllowlistConfig,
    FounderAuthorizer,
    TelegramEvent,
    TelegramFounderAdapter,
    TelegramSender,
)


@dataclass
class HermesGatewayPayload:
    """Sanitized inbound payload from Hermes Telegram gateway.

    Raw chat IDs and user IDs are never stored here. The transport layer
    maps real identifiers to sanitized keys before constructing this payload.
    """

    source_chat: str
    source_user: str
    message_text: str
    timestamp: str
    reply_to_message_id: Optional[str] = None

    def validate(self) -> Optional[str]:
        if not self.source_chat:
            return "missing source_chat"
        if not self.source_user:
            return "missing source_user"
        if not self.message_text:
            return "missing message_text"
        if not self.timestamp:
            return "missing timestamp"
        chat_str = str(self.source_chat)
        if chat_str.isdigit() or (chat_str.startswith("-") and chat_str[1:].isdigit()):
            return "source_chat appears to be a raw numeric chat ID"
        user_str = str(self.source_user)
        if user_str.isdigit():
            return "source_user appears to be a raw numeric user ID"
        return None


@dataclass
class TransportConfig:
    allowed_chats: List[str] = field(default_factory=list)
    allowed_users: List[str] = field(default_factory=list)
    dm_pairing: Dict[str, str] = field(default_factory=dict)
    gateway_allow_all: bool = False
    telegram_allow_all: bool = False
    polling_mode: bool = True
    webhook_mode: bool = False
    webhook_secret_configured: bool = False
    bot_token_configured: bool = False

    def validate(self) -> List[str]:
        violations: List[str] = []

        if self.gateway_allow_all:
            violations.append("GATEWAY_ALLOW_ALL_USERS must not be enabled")
        if self.telegram_allow_all:
            violations.append("TELEGRAM_ALLOW_ALL_USERS must not be enabled")
        if not self.allowed_chats and not self.allowed_users and not self.dm_pairing:
            violations.append(
                "allowlist must contain at least one chat, user, or DM pairing"
            )
        if not self.bot_token_configured:
            violations.append("TELEGRAM_BOT_TOKEN must be configured")
        if self.webhook_mode and not self.webhook_secret_configured:
            violations.append(
                "TELEGRAM_WEBHOOK_SECRET must be configured in webhook mode"
            )
        if self.webhook_mode and self.polling_mode:
            violations.append("polling and webhook modes are mutually exclusive")
        if not self.polling_mode and not self.webhook_mode:
            violations.append("at least one transport mode (polling or webhook) must be enabled")

        return violations

    def to_allowlist_config(self) -> FounderAllowlistConfig:
        return FounderAllowlistConfig(
            allowed_chat_keys=list(self.allowed_chats),
            allowed_user_keys=list(self.allowed_users),
            gateway_allow_all=False,
            telegram_allow_all=False,
        )

    def is_authorized(self, chat_key: str, user_key: str) -> bool:
        if self.gateway_allow_all or self.telegram_allow_all:
            return False
        if chat_key in self.allowed_chats:
            return True
        if user_key in self.allowed_users:
            return True
        paired_user = self.dm_pairing.get(chat_key)
        if paired_user is not None and paired_user == user_key:
            return True
        return False


OutboundCallback = Callable[[str, str], None]


class HermesTelegramSender:
    """Implements TelegramSender, delivers through transport callback.

    The callback is the transport boundary abstraction: in a live deployment
    it calls the Hermes Telegram gateway API; in tests it records calls.
    """

    def __init__(self, callback: OutboundCallback) -> None:
        self._callback = callback

    def send(self, chat_key: str, text: str) -> None:
        if self._callback is not None:
            self._callback(chat_key, text)


OutboundCallbackFactory = Callable[[], OutboundCallback]


class HermesTelegramTransport:
    """Wires TKT-006 adapter to Hermes Telegram gateway transport.

    One instance per deployment. Provides:
    - Inbound: gateway payload → TelegramEvent → adapter
    - Outbound: adapter → TelegramSender → gateway transport
    - Config validation for all security constraints
    """

    def __init__(
        self,
        config: TransportConfig,
        adapter: TelegramFounderAdapter,
        outbound_factory: Optional[OutboundCallbackFactory] = None,
    ) -> None:
        self._config = config
        self._adapter = adapter
        self._outbound_factory = outbound_factory
        self._outbound_sender: TelegramSender

    def config_violations(self) -> List[str]:
        return self._config.validate()

    def receive(self, payload: HermesGatewayPayload) -> Optional[CommandResult | ClassificationResult]:
        validation_error = payload.validate()
        if validation_error is not None:
            return ClassificationResult(
                category="general_question",
                chat_key=payload.source_chat,
                text=validation_error,
                durable_decision=False,
                artifact_target=None,
            )

        if not self._config.is_authorized(payload.source_chat, payload.source_user):
            return ClassificationResult(
                category="general_question",
                chat_key=payload.source_chat,
                text="Unauthorized: chat/user not in allowlist",
                durable_decision=False,
                artifact_target=None,
            )

        event = TelegramEvent(
            chat_key=payload.source_chat,
            user_key=payload.source_user,
            text=payload.message_text,
            timestamp=payload.timestamp,
            reply_to=payload.reply_to_message_id,
        )

        return self._adapter.handle_event(event)

    def deliver(
        self,
        result: CommandResult | ClassificationResult,
        callback: Optional[OutboundCallback] = None,
    ) -> None:
        text = result.message_ru if isinstance(result, CommandResult) else result.text
        cb = callback
        if cb is None and self._outbound_factory is not None:
            cb = self._outbound_factory()
        if cb is not None:
            cb(result.chat_key, text)

    def create_sender(self) -> TelegramSender:
        if self._outbound_factory is not None:
            return HermesTelegramSender(self._outbound_factory())
        return HermesTelegramSender(lambda chat_key, text: None)

    def deliver_as_sender(
        self,
        result: CommandResult | ClassificationResult,
    ) -> None:
        if self._outbound_factory is not None:
            cb = self._outbound_factory()
            text = result.message_ru if isinstance(result, CommandResult) else result.text
            cb(result.chat_key, text)


def validate_transport_config_env(
    *,
    gateway_allow_all: Optional[str] = None,
    telegram_allow_all: Optional[str] = None,
    telegram_bot_token_set: bool = False,
    telegram_allowed_users_set: bool = False,
    telegram_webhook_secret_set: bool = False,
    webhook_mode: bool = False,
    polling_mode: bool = True,
) -> List[str]:
    violations: List[str] = []

    if gateway_allow_all not in (None, "", "false", "False", "0"):
        violations.append("GATEWAY_ALLOW_ALL_USERS must be unset or false")
    if telegram_allow_all not in (None, "", "false", "False", "0"):
        violations.append("TELEGRAM_ALLOW_ALL_USERS must be unset or false")
    if not telegram_allowed_users_set and not webhook_mode:
        violations.append("TELEGRAM_ALLOWED_USERS must be set (or DM pairing configured)")
    if not telegram_bot_token_set:
        violations.append("TELEGRAM_BOT_TOKEN must be set in runtime environment")
    if webhook_mode and not telegram_webhook_secret_set:
        violations.append("TELEGRAM_WEBHOOK_SECRET must be set when using webhook mode")
    if webhook_mode and polling_mode:
        violations.append("polling and webhook modes are mutually exclusive")

    return violations


def sanitize_gateway_payload(
    raw_chat_id: str,
    raw_user_id: str,
    text: str,
    timestamp: str,
    chat_label: str = "chat:founder",
    user_label: str = "user:founder",
    reply_to: Optional[str] = None,
) -> HermesGatewayPayload:
    return HermesGatewayPayload(
        source_chat=chat_label,
        source_user=user_label,
        message_text=text.strip(),
        timestamp=timestamp,
        reply_to_message_id=reply_to,
    )