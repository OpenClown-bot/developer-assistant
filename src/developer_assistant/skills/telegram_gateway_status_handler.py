"""/status command handler for the Telegram gateway skill.

Implements OBSERVABILITY-CONTRACT.md v0.1.1 § 7 (FR-OBS-04).

On /status from allowlisted chat ID: calls status_query.query_status(),
renders human-format output, sends as Telegram message(s).
On /status from non-allowlisted sender: logs unauthorized_status_request
event, replies with generic "command not available" message.
Pagination: split at line boundaries when body > 4096 chars;
prefix parts with "(part 1/N)" / "(part 2/N)".
"""

from __future__ import annotations

import logging
from typing import Optional, Protocol

from developer_assistant.observability.status_query import (
    query_status,
    render_status_human,
)
from developer_assistant.observability.telegram_utils import paginate_text

_TELEGRAM_MSG_LIMIT = 4096
_UNAUTHORIZED_REPLY = "This command is not available to you."

_logger: Optional[logging.Logger] = None


def _get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    try:
        from developer_assistant.observability.structured_logger import get_logger
        _logger = get_logger("telegram_gateway_status_handler")
    except ImportError:
        _logger = logging.getLogger("telegram_gateway_status_handler")
    return _logger


class TelegramSender(Protocol):
    def send(self, chat_key: str, text: str) -> None: ...


class AllowlistChecker(Protocol):
    def is_allowed(self, chat_key: str, user_key: str) -> bool: ...


def _paginate(text: str, max_len: int = _TELEGRAM_MSG_LIMIT) -> list[str]:
    return paginate_text(text, max_len)


def handle_status_command(
    chat_key: str,
    user_key: str,
    sender: TelegramSender,
    allowlist: AllowlistChecker,
    db_path: str = "/srv/devassist/state/operational.db",
    health_ports: Optional[dict[str, int]] = None,
    role_order: Optional[list[str]] = None,
) -> bool:
    """Handle a /status command received via Telegram.

    Returns True if the command was handled (allowlisted sender),
    False if the sender was unauthorized.
    """
    if not allowlist.is_allowed(chat_key, user_key):
        _log_unauthorized(chat_key, user_key)
        sender.send(chat_key, _UNAUTHORIZED_REPLY)
        return False

    try:
        status_dict = query_status(
            db_path=db_path,
            health_ports=health_ports,
            role_order=role_order,
        )
    except Exception as e:
        _get_logger().error("status_query failed: %s", e)
        sender.send(chat_key, "Status query failed. See logs for details.")
        return True

    human_text = render_status_human(status_dict)
    parts = _paginate(human_text)

    for part in parts:
        sender.send(chat_key, part)

    return True


def _log_unauthorized(chat_key: str, user_key: str) -> None:
    logger = _get_logger()
    try:
        from developer_assistant.observability.structured_logger import get_logger as _sl_get_logger
        sl_logger = _sl_get_logger("telegram_gateway_status_handler")
        sl_logger.warning(
            "unauthorized_status_request",
            extra={
                "event": "unauthorized_status_request",
                "_extra_payload": {
                    "chat_key": chat_key,
                    "user_key": user_key,
                },
            },
        )
    except ImportError:
        logger.warning(
            "unauthorized_status_request chat_key=%s user_key=%s",
            chat_key, user_key,
        )
