"""Telegram founder interaction adapter for Hermes Agent.

This module implements the minimal Telegram founder interaction path for v0.1:
one trusted founder, one active project, through the Hermes Agent runtime.

It provides:
- Founder allowlist/authorization for Telegram chats
- Command routing for /new_project, /status, /decisions, /pause, /resume
- Free-form message classification (intake, answer, clarification, approval,
  rejection, general_question)
- Specialist-agent question formatting and routing
- Durable decision capture through an injectable artifact writer
- Progress report scheduling with milestone and 30-60 minute interval support

Security: no Telegram tokens, raw chat IDs, or raw user IDs are stored in
committed code or config. All identifiers use sanitized keys (e.g. chat:founder).
Production credential use requires TELEGRAM_ALLOWED_USERS or DM pairing,
GATEWAY_ALLOW_ALL_USERS and TELEGRAM_ALLOW_ALL_USERS must be unset/false.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol


class MessageCategory(str, Enum):
    INTAKE = "intake"
    ANSWER = "answer"
    CLARIFICATION = "clarification"
    APPROVAL = "approval"
    REJECTION = "rejection"
    GENERAL_QUESTION = "general_question"


class CommandName(str, Enum):
    NEW_PROJECT = "/new_project"
    STATUS = "/status"
    DECISIONS = "/decisions"
    PAUSE = "/pause"
    RESUME = "/resume"


@dataclass
class TelegramEvent:
    chat_key: str
    user_key: str
    text: str
    timestamp: str
    reply_to: Optional[str] = None


@dataclass
class SpecialistQuestion:
    context: str
    options: List[str]
    recommendation: str
    impact: str
    urgency: str

    def __post_init__(self) -> None:
        if self.urgency not in ("low", "medium", "high"):
            raise ValueError(f"urgency must be low/medium/high, got {self.urgency!r}")

    def to_russian_text(self) -> str:
        urgency_ru = {"low": "низкая", "medium": "средняя", "high": "высокая"}
        options_text = "\n".join(f"  - {o}" for o in self.options)
        return (
            f"Контекст: {self.context}\n"
            f"Варианты:\n{options_text}\n"
            f"Рекомендация: {self.recommendation}\n"
            f"Влияние: {self.impact}\n"
            f"Срочность: {urgency_ru.get(self.urgency, self.urgency)}"
        )


@dataclass
class ProgressReport:
    completed: str
    current_action: str
    blocker_state: str
    decisions_needed: str
    notable_risks: str

    def to_russian_text(self) -> str:
        return (
            f"Завершено: {self.completed}\n"
            f"Текущее действие: {self.current_action}\n"
            f"Блокеры: {self.blocker_state}\n"
            f"Требуются решения: {self.decisions_needed}\n"
            f"Риски: {self.notable_risks}"
        )


@dataclass
class CommandResult:
    command: CommandName
    chat_key: str
    response_key: str
    status: str
    message_ru: str
    artifact_intent: Optional[str] = None


@dataclass
class ClassificationResult:
    category: MessageCategory
    chat_key: str
    text: str
    durable_decision: bool
    artifact_target: Optional[str] = None


class ArtifactWriter(Protocol):
    def write(self, artifact_path: str, content: str) -> None: ...


class TelegramSender(Protocol):
    def send(self, chat_key: str, text: str) -> None: ...


class _NullArtifactWriter:
    def write(self, artifact_path: str, content: str) -> None:
        pass

class _NullTelegramSender:
    def send(self, chat_key: str, text: str) -> None:
        pass


_APPROVAL_PATTERNS = [
    re.compile(r"\b(одобр|соглас|одобряю|согласен|утвержд|подтвержд|approve|approved|confirmed|yes|да|ок|ok|хорошо|давай|go ahead)\b", re.IGNORECASE),
]

_REJECTION_PATTERNS = [
    re.compile(r"\b(отверг|отклон|не соглас|отказываю|reject|rejected|denied|no|нет|отмена|cancel|stop|не надо)", re.IGNORECASE),
]

_CLARIFICATION_PATTERNS = [
    re.compile(r"\b(уточн|поясн|разъясн|что значит|что имеется|explain|clarify|what do you mean|what does|подробнее)\b", re.IGNORECASE),
]

_QUESTION_PATTERNS = [
    re.compile(r"\b(как|почему|зачем|когда|сколько|где|какой|какая|какие|можно ли|стоит ли|how|why|when|how much|where|which|should|can we|is it)\b", re.IGNORECASE),
]

_DURABLE_DECISION_KEYWORDS = [
    "архитектур", "безопасност", "деплой", "депло", "deploy", "deployment",
    "мерж", "merge", "продакшн", "production", "бюджет", "budget", "cost",
    "стоимость", "credential", "токен", "token", "scope", "доступ",
    "архитектура", "architecture", "scope change", "расширение",
]


def _classify_approval(text: str) -> bool:
    for p in _APPROVAL_PATTERNS:
        if p.search(text):
            return True
    return False


def _classify_rejection(text: str) -> bool:
    for p in _REJECTION_PATTERNS:
        if p.search(text):
            return True
    return False


def _classify_clarification(text: str) -> bool:
    for p in _CLARIFICATION_PATTERNS:
        if p.search(text):
            return True
    return False


def _classify_question(text: str) -> bool:
    for p in _QUESTION_PATTERNS:
        if p.search(text):
            return True
    return False


def _is_durable_decision(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _DURABLE_DECISION_KEYWORDS)


def classify_message(text: str, pending_question: bool = False) -> MessageCategory:
    """Classify a free-form founder message into exactly one category."""
    if pending_question:
        if _classify_approval(text):
            return MessageCategory.APPROVAL
        if _classify_rejection(text):
            return MessageCategory.REJECTION
        if _classify_clarification(text):
            return MessageCategory.CLARIFICATION
        return MessageCategory.ANSWER

    if _classify_approval(text):
        return MessageCategory.APPROVAL
    if _classify_rejection(text):
        return MessageCategory.REJECTION
    if _classify_clarification(text):
        return MessageCategory.CLARIFICATION
    if _classify_question(text):
        return MessageCategory.GENERAL_QUESTION

    return MessageCategory.INTAKE


@dataclass
class FounderAllowlistConfig:
    allowed_chat_keys: List[str] = field(default_factory=list)
    allowed_user_keys: List[str] = field(default_factory=list)
    gateway_allow_all: bool = False
    telegram_allow_all: bool = False


class FounderAuthorizer:
    def __init__(self, config: FounderAllowlistConfig) -> None:
        self._config = config

    def is_allowed(self, chat_key: str, user_key: str) -> bool:
        if self._config.gateway_allow_all or self._config.telegram_allow_all:
            return False
        chat_ok = chat_key in self._config.allowed_chat_keys
        user_ok = user_key in self._config.allowed_user_keys
        return chat_ok or user_ok

    def validate_config(self) -> Optional[str]:
        if self._config.gateway_allow_all:
            return "GATEWAY_ALLOW_ALL_USERS must not be enabled"
        if self._config.telegram_allow_all:
            return "TELEGRAM_ALLOW_ALL_USERS must not be enabled"
        if not self._config.allowed_chat_keys and not self._config.allowed_user_keys:
            return "allowlist must contain at least one chat or user key"
        return None


_MIN_REPORT_INTERVAL_MINUTES = 30
_MAX_REPORT_INTERVAL_MINUTES = 60


@dataclass
class ProjectState:
    paused: bool = False
    phase: str = ""
    active_ticket: str = ""
    active_pr: str = ""
    blockers: str = ""
    pending_decisions: str = ""


class TelegramFounderAdapter:
    def __init__(
        self,
        authorizer: FounderAuthorizer,
        artifact_writer: ArtifactWriter = _NullArtifactWriter(),
        telegram_sender: TelegramSender = _NullTelegramSender(),
    ) -> None:
        self._authorizer = authorizer
        self._artifact_writer = artifact_writer
        self._telegram_sender = telegram_sender
        self._projects: Dict[str, ProjectState] = {}
        self._pending_questions: Dict[str, SpecialistQuestion] = {}
        self._report_intervals: Dict[str, int] = {}
        self._last_report_ts: Dict[str, Optional[str]] = {}

    def handle_event(self, event: TelegramEvent) -> Optional[CommandResult | ClassificationResult]:
        if not self._authorizer.is_allowed(event.chat_key, event.user_key):
            return ClassificationResult(
                category=MessageCategory.REJECTION,
                chat_key=event.chat_key,
                text="Unauthorized",
                durable_decision=False,
                artifact_target=None,
            )

        cmd = self._parse_command(event.text)
        if cmd is not None:
            return self._dispatch_command(cmd, event)

        return self._handle_freeform(event)

    def _parse_command(self, text: str) -> Optional[CommandName]:
        stripped = text.strip()
        for cn in CommandName:
            if stripped.startswith(cn.value) and (
                len(stripped) == len(cn.value) or stripped[len(cn.value)] in (" ", "@")
            ):
                return cn
        return None

    def _dispatch_command(self, cmd: CommandName, event: TelegramEvent) -> CommandResult:
        if cmd == CommandName.NEW_PROJECT:
            return self._cmd_new_project(event)
        elif cmd == CommandName.STATUS:
            return self._cmd_status(event)
        elif cmd == CommandName.DECISIONS:
            return self._cmd_decisions(event)
        elif cmd == CommandName.PAUSE:
            return self._cmd_pause(event)
        elif cmd == CommandName.RESUME:
            return self._cmd_resume(event)
        else:
            return CommandResult(
                command=cmd,
                chat_key=event.chat_key,
                response_key=event.chat_key,
                status="unknown",
                message_ru="Неизвестная команда",
            )

    def _ensure_project(self, chat_key: str) -> ProjectState:
        if chat_key not in self._projects:
            self._projects[chat_key] = ProjectState()
        return self._projects[chat_key]

    def _cmd_new_project(self, event: TelegramEvent) -> CommandResult:
        proj = self._ensure_project(event.chat_key)
        proj.paused = False
        proj.phase = "intake"
        self._report_intervals[event.chat_key] = 45
        return CommandResult(
            command=CommandName.NEW_PROJECT,
            chat_key=event.chat_key,
            response_key=event.chat_key,
            status="started",
            message_ru="Начат процесс создания нового проекта. Опишите проект.",
            artifact_intent="docs/prd/",
        )

    def _cmd_status(self, event: TelegramEvent) -> CommandResult:
        proj = self._ensure_project(event.chat_key)
        return CommandResult(
            command=CommandName.STATUS,
            chat_key=event.chat_key,
            response_key=event.chat_key,
            status="ok",
            message_ru=(
                f"Фаза: {proj.phase or 'не задана'}\n"
                f"Активный тикет: {proj.active_ticket or 'нет'}\n"
                f"Активный PR: {proj.active_pr or 'нет'}\n"
                f"Блокеры: {proj.blockers or 'нет'}\n"
                f"Решения: {proj.pending_decisions or 'нет'}\n"
                f"Пауза: {'да' if proj.paused else 'нет'}"
            ),
        )

    def _cmd_decisions(self, event: TelegramEvent) -> CommandResult:
        proj = self._ensure_project(event.chat_key)
        if self._pending_questions.get(event.chat_key):
            q = self._pending_questions[event.chat_key]
            return CommandResult(
                command=CommandName.DECISIONS,
                chat_key=event.chat_key,
                response_key=event.chat_key,
                status="pending",
                message_ru=f"Открытый вопрос:\n{q.to_russian_text()}",
            )
        decisions = proj.pending_decisions or "Нет открытых решений"
        return CommandResult(
            command=CommandName.DECISIONS,
            chat_key=event.chat_key,
            response_key=event.chat_key,
            status="ok",
            message_ru=f"Открытые решения: {decisions}",
        )

    def _cmd_pause(self, event: TelegramEvent) -> CommandResult:
        proj = self._ensure_project(event.chat_key)
        proj.paused = True
        return CommandResult(
            command=CommandName.PAUSE,
            chat_key=event.chat_key,
            response_key=event.chat_key,
            status="paused",
            message_ru="Работа по проекту приостановлена.",
        )

    def _cmd_resume(self, event: TelegramEvent) -> CommandResult:
        proj = self._ensure_project(event.chat_key)
        proj.paused = False
        return CommandResult(
            command=CommandName.RESUME,
            chat_key=event.chat_key,
            response_key=event.chat_key,
            status="resumed",
            message_ru="Работа по проекту возобновлена.",
        )

    def _handle_freeform(self, event: TelegramEvent) -> ClassificationResult:
        has_pending = event.chat_key in self._pending_questions
        category = classify_message(event.text, pending_question=has_pending)
        durable = _is_durable_decision(event.text)
        artifact_target = None
        if durable and category in (MessageCategory.APPROVAL, MessageCategory.REJECTION, MessageCategory.ANSWER):
            artifact_target = "docs/questions/"
        elif durable:
            artifact_target = "docs/questions/"

        if category == MessageCategory.APPROVAL and durable and artifact_target:
            self._artifact_writer.write(
                artifact_target,
                f"Decision from {event.chat_key}: {event.text}",
            )

        if has_pending and category in (MessageCategory.APPROVAL, MessageCategory.REJECTION, MessageCategory.ANSWER, MessageCategory.CLARIFICATION):
            del self._pending_questions[event.chat_key]

        return ClassificationResult(
            category=category,
            chat_key=event.chat_key,
            text=event.text,
            durable_decision=durable,
            artifact_target=artifact_target,
        )

    def route_specialist_question(
        self, chat_key: str, question: SpecialistQuestion
    ) -> str:
        self._pending_questions[chat_key] = question
        text = question.to_russian_text()
        self._telegram_sender.send(chat_key, text)
        return text

    def is_report_due(self, chat_key: str, current_ts: str, is_milestone: bool = False) -> bool:
        if is_milestone:
            return True
        interval = self._report_intervals.get(chat_key, 45)
        if interval < _MIN_REPORT_INTERVAL_MINUTES or interval > _MAX_REPORT_INTERVAL_MINUTES:
            interval = 45
        last_ts = self._last_report_ts.get(chat_key)
        if last_ts is None:
            return True
        from datetime import datetime, timezone
        try:
            last_dt = datetime.fromisoformat(last_ts)
            curr_dt = datetime.fromisoformat(current_ts)
        except (ValueError, TypeError):
            return True
        delta_minutes = (curr_dt - last_dt).total_seconds() / 60.0
        return delta_minutes >= interval

    def send_progress_report(
        self, chat_key: str, report: ProgressReport, current_ts: str, is_milestone: bool = False
    ) -> str:
        if not self.is_report_due(chat_key, current_ts, is_milestone):
            return ""
        text = report.to_russian_text()
        self._telegram_sender.send(chat_key, text)
        self._last_report_ts[chat_key] = current_ts
        return text

    def set_report_interval(self, chat_key: str, minutes: int) -> None:
        if minutes < _MIN_REPORT_INTERVAL_MINUTES or minutes > _MAX_REPORT_INTERVAL_MINUTES:
            raise ValueError(
                f"Report interval must be {_MIN_REPORT_INTERVAL_MINUTES}-{_MAX_REPORT_INTERVAL_MINUTES} minutes, got {minutes}"
            )
        self._report_intervals[chat_key] = minutes

    def update_project_state(
        self,
        chat_key: str,
        *,
        paused: Optional[bool] = None,
        phase: Optional[str] = None,
        active_ticket: Optional[str] = None,
        active_pr: Optional[str] = None,
        blockers: Optional[str] = None,
        pending_decisions: Optional[str] = None,
    ) -> None:
        proj = self._ensure_project(chat_key)
        if paused is not None:
            proj.paused = paused
        if phase is not None:
            proj.phase = phase
        if active_ticket is not None:
            proj.active_ticket = active_ticket
        if active_pr is not None:
            proj.active_pr = active_pr
        if blockers is not None:
            proj.blockers = blockers
        if pending_decisions is not None:
            proj.pending_decisions = pending_decisions


def validate_telegram_config_env(
    *,
    gateway_allow_all: Optional[str] = None,
    telegram_allow_all: Optional[str] = None,
    telegram_bot_token_set: bool = False,
    telegram_allowed_users_set: bool = False,
    telegram_webhook_secret_set: bool = False,
    webhook_mode: bool = False,
) -> List[str]:
    """Validate Telegram security configuration from environment indicators.

    Returns a list of violations (empty if valid). This function checks
    environment variable *presence* indicators, never values.
    """
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

    return violations
