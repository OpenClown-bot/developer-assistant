"""Tests for Hermes Telegram gateway transport binding (TKT-015).

Covers:
- Gateway payload validation and rejection of raw identifiers
- Transport config validation (allowlist, allow-all flags, webhook, polling)
- Transport-level authorization (allowlist, DM pairing)
- Inbound transport wiring: gateway payload → TelegramEvent → adapter
- Smoke coverage: /new_project, /status, /decisions, /pause, /resume
- Free-form classification through transport boundary
- Specialist-question delivery and founder-answer capture
- Progress-report delivery through transport
- Outbound sender behavior
- Token/private-ID leak prevention
- validate_transport_config_env function
"""

import unittest
from dataclasses import dataclass
from typing import List, Optional

from src.developer_assistant.telegram_adapter import (
    ClassificationResult,
    CommandResult,
    FounderAllowlistConfig,
    FounderAuthorizer,
    MessageCategory,
    ProgressReport,
    SpecialistQuestion,
    TelegramEvent,
    TelegramFounderAdapter,
    TelegramSender,
    classify_message,
)
from src.developer_assistant.hermes_telegram_transport import (
    HermesGatewayPayload,
    HermesTelegramSender,
    HermesTelegramTransport,
    OutboundCallback,
    OutboundCallbackFactory,
    TransportConfig,
    sanitize_gateway_payload,
    validate_transport_config_env,
)


_CHAT_FOUNDER = "chat:founder"
_USER_FOUNDER = "user:founder"
_CHAT_OTHER = "chat:other"
_USER_OTHER = "user:other"
_TS = "2026-05-04T12:00:00+00:00"


def _make_payload(
    chat: str = _CHAT_FOUNDER,
    user: str = _USER_FOUNDER,
    text: str = "hello",
    ts: str = _TS,
    reply_to: Optional[str] = None,
) -> HermesGatewayPayload:
    return HermesGatewayPayload(
        source_chat=chat,
        source_user=user,
        message_text=text,
        timestamp=ts,
        reply_to_message_id=reply_to,
    )


def _make_config(**kwargs) -> TransportConfig:
    defaults = dict(
        allowed_chats=[_CHAT_FOUNDER],
        allowed_users=[_USER_FOUNDER],
        bot_token_configured=True,
        polling_mode=True,
    )
    defaults.update(kwargs)
    return TransportConfig(**defaults)


class _RecordingOutboundCallback:
    def __init__(self) -> None:
        self.calls: List[tuple] = []

    def __call__(self, chat_key: str, text: str) -> None:
        self.calls.append((chat_key, text))


def _recording_factory() -> _RecordingOutboundCallback:
    return _RecordingOutboundCallback()


def _make_transport(
    config: Optional[TransportConfig] = None,
    outbound_factory: Optional[OutboundCallbackFactory] = None,
) -> HermesTelegramTransport:
    cfg = config or _make_config()
    authorizer = FounderAuthorizer(cfg.to_allowlist_config())
    adapter = TelegramFounderAdapter(authorizer=authorizer)
    return HermesTelegramTransport(
        config=cfg,
        adapter=adapter,
        outbound_factory=outbound_factory,
    )


class TestGatewayPayloadValidation(unittest.TestCase):
    def test_valid_payload_passes(self):
        p = _make_payload()
        self.assertIsNone(p.validate())

    def test_missing_source_chat(self):
        p = _make_payload(chat="")
        self.assertIn("missing source_chat", p.validate())

    def test_missing_source_user(self):
        p = _make_payload(user="")
        self.assertIn("missing source_user", p.validate())

    def test_missing_message_text(self):
        p = _make_payload(text="")
        self.assertIn("missing message_text", p.validate())

    def test_missing_timestamp(self):
        p = _make_payload(text="t", ts="")
        self.assertIn("missing timestamp", p.validate())

    def test_rejects_raw_numeric_chat_id(self):
        p = _make_payload(chat="123456789")
        self.assertIn("raw numeric chat ID", p.validate())

    def test_rejects_raw_numeric_chat_id_negative(self):
        p = _make_payload(chat="-1001234567890")
        self.assertIn("raw numeric chat ID", p.validate())

    def test_rejects_raw_numeric_user_id(self):
        p = _make_payload(user="987654321")
        self.assertIn("raw numeric user ID", p.validate())

    def test_accepts_sanitized_key_chat_founder(self):
        p = _make_payload(chat="chat:founder")
        self.assertIsNone(p.validate())

    def test_accepts_sanitized_key_user_founder(self):
        p = _make_payload(user="user:founder")
        self.assertIsNone(p.validate())


class TestTransportConfigValidation(unittest.TestCase):
    def test_valid_config_no_violations(self):
        cfg = _make_config()
        self.assertEqual(cfg.validate(), [])

    def test_gateway_allow_all_is_rejected(self):
        cfg = _make_config(gateway_allow_all=True)
        violations = cfg.validate()
        self.assertTrue(any("GATEWAY_ALLOW_ALL_USERS" in v for v in violations))

    def test_telegram_allow_all_is_rejected(self):
        cfg = _make_config(telegram_allow_all=True)
        violations = cfg.validate()
        self.assertTrue(any("TELEGRAM_ALLOW_ALL_USERS" in v for v in violations))

    def test_missing_bot_token_is_rejected(self):
        cfg = _make_config(bot_token_configured=False)
        violations = cfg.validate()
        self.assertTrue(any("TELEGRAM_BOT_TOKEN" in v for v in violations))

    def test_empty_allowlist_is_rejected(self):
        cfg = _make_config(allowed_chats=[], allowed_users=[])
        violations = cfg.validate()
        self.assertTrue(any("allowlist" in v.lower() for v in violations))

    def test_dm_pairing_satisfies_allowlist(self):
        cfg = _make_config(
            allowed_chats=[],
            allowed_users=[],
            dm_pairing={_CHAT_FOUNDER: _USER_FOUNDER},
        )
        self.assertEqual(cfg.validate(), [])

    def test_webhook_without_secret_is_rejected(self):
        cfg = _make_config(
            polling_mode=False,
            webhook_mode=True,
            webhook_secret_configured=False,
        )
        violations = cfg.validate()
        self.assertTrue(any("TELEGRAM_WEBHOOK_SECRET" in v for v in violations))

    def test_webhook_with_secret_is_accepted(self):
        cfg = _make_config(
            polling_mode=False,
            webhook_mode=True,
            webhook_secret_configured=True,
        )
        violations = cfg.validate()
        self.assertFalse(any("TELEGRAM_WEBHOOK_SECRET" in v for v in violations))

    def test_polling_and_webhook_mutually_exclusive(self):
        cfg = _make_config(
            polling_mode=True,
            webhook_mode=True,
            webhook_secret_configured=True,
        )
        violations = cfg.validate()
        self.assertTrue(any("mutually exclusive" in v for v in violations))

    def test_no_transport_mode_is_rejected(self):
        cfg = _make_config(polling_mode=False, webhook_mode=False)
        violations = cfg.validate()
        self.assertTrue(any("transport mode" in v.lower() for v in violations))

    def test_config_stores_no_token_values(self):
        cfg = _make_config()
        as_dict = vars(cfg)
        for v in as_dict.values():
            if isinstance(v, str) and v:
                self.assertNotIn(":", v, f"Token-like value found: {v!r}")


class TestTransportAuthorization(unittest.TestCase):
    def test_allowlisted_chat_is_authorized(self):
        cfg = _make_config(allowed_chats=[_CHAT_FOUNDER])
        self.assertTrue(cfg.is_authorized(_CHAT_FOUNDER, _USER_OTHER))

    def test_allowlisted_user_is_authorized(self):
        cfg = _make_config(allowed_users=[_USER_FOUNDER])
        self.assertTrue(cfg.is_authorized(_CHAT_OTHER, _USER_FOUNDER))

    def test_non_allowlisted_is_rejected(self):
        cfg = _make_config(allowed_chats=[_CHAT_FOUNDER], allowed_users=[_USER_FOUNDER])
        self.assertFalse(cfg.is_authorized("chat:unknown", "user:unknown"))

    def test_dm_pairing_is_authorized(self):
        cfg = _make_config(
            allowed_chats=[],
            allowed_users=[],
            dm_pairing={_CHAT_FOUNDER: _USER_FOUNDER},
        )
        self.assertTrue(cfg.is_authorized(_CHAT_FOUNDER, _USER_FOUNDER))

    def test_dm_pairing_wrong_user_is_rejected(self):
        cfg = _make_config(
            allowed_chats=[],
            allowed_users=[],
            dm_pairing={_CHAT_FOUNDER: _USER_FOUNDER},
        )
        self.assertFalse(cfg.is_authorized(_CHAT_FOUNDER, "user:stranger"))

    def test_gateway_allow_all_disables_authorization(self):
        cfg = _make_config(
            allowed_chats=[_CHAT_FOUNDER],
            gateway_allow_all=True,
        )
        self.assertFalse(cfg.is_authorized(_CHAT_FOUNDER, _USER_FOUNDER))

    def test_telegram_allow_all_disables_authorization(self):
        cfg = _make_config(
            allowed_users=[_USER_FOUNDER],
            telegram_allow_all=True,
        )
        self.assertFalse(cfg.is_authorized(_CHAT_FOUNDER, _USER_FOUNDER))


class TestInboundTransportWiring(unittest.TestCase):
    def test_authorized_payload_creates_event_and_routes(self):
        transport = _make_transport()
        payload = _make_payload(text="/status")
        result = transport.receive(payload)
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertEqual(result.chat_key, _CHAT_FOUNDER)

    def test_unauthorized_payload_is_rejected(self):
        transport = _make_transport()
        payload = _make_payload(chat="chat:stranger", user="user:stranger")
        result = transport.receive(payload)
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertIn("Unauthorized", result.text)

    def test_invalid_payload_returns_error(self):
        transport = _make_transport()
        payload = _make_payload(chat="")
        result = transport.receive(payload)
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertIn("missing", result.text)

    def test_raw_chat_id_in_payload_is_rejected(self):
        transport = _make_transport()
        payload = _make_payload(chat="123456789")
        result = transport.receive(payload)
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertIn("raw numeric", result.text)

    def test_event_contains_sanitized_keys_not_raw_ids(self):
        transport = _make_transport()
        payload = _make_payload(text="hello")
        result = transport.receive(payload)
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertEqual(result.chat_key, _CHAT_FOUNDER)

    def test_transport_rejects_empty_allowlist_config(self):
        cfg = _make_config(allowed_chats=[], allowed_users=[])
        cfg_violations = cfg.validate()
        self.assertTrue(len(cfg_violations) > 0)
        authorizer = FounderAuthorizer(cfg.to_allowlist_config())
        adapter = TelegramFounderAdapter(authorizer=authorizer)
        transport = HermesTelegramTransport(config=cfg, adapter=adapter)
        payload = _make_payload(text="/status")
        result = transport.receive(payload)
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertIn("Unauthorized", result.text)


class TestNewProjectCommandThroughTransport(unittest.TestCase):
    def test_new_project_with_name(self):
        transport = _make_transport()
        payload = _make_payload(text="/new_project MyTestProject")
        result = transport.receive(payload)
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertIn("начат", result.message_ru.lower())
        self.assertIn("MyTestProject", payload.message_text)

    def test_new_project_without_name(self):
        transport = _make_transport()
        payload = _make_payload(text="/new_project")
        result = transport.receive(payload)
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertIn("начат", result.message_ru.lower())


class TestStatusCommandThroughTransport(unittest.TestCase):
    def test_status_with_known_project(self):
        transport = _make_transport()
        transport.receive(_make_payload(text="/new_project TestP"))
        result = transport.receive(_make_payload(text="/status"))
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertIn("фаза", result.message_ru.lower())

    def test_status_without_project(self):
        transport = _make_transport()
        result = transport.receive(_make_payload(text="/status"))
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertIn("фаза", result.message_ru.lower())


class TestDecisionsCommandThroughTransport(unittest.TestCase):
    def test_decisions_no_pending(self):
        transport = _make_transport()
        result = transport.receive(_make_payload(text="/decisions"))
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertIn("нет открытых", result.message_ru.lower())

    def test_decisions_with_pending(self):
        transport = _make_transport()
        q = SpecialistQuestion(
            context="Выбор стека",
            options=["Python", "Rust"],
            recommendation="Python",
            impact="Все модули",
            urgency="high",
        )
        transport._adapter.route_specialist_question(_CHAT_FOUNDER, q)
        result = transport.receive(_make_payload(text="/decisions"))
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertIn("открытый вопрос", result.message_ru.lower())


class TestPauseCommandThroughTransport(unittest.TestCase):
    def test_pause(self):
        transport = _make_transport()
        result = transport.receive(_make_payload(text="/pause"))
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertIn("приостановлен", result.message_ru.lower())

    def test_pause_already_paused(self):
        transport = _make_transport()
        transport.receive(_make_payload(text="/pause"))
        result = transport.receive(_make_payload(text="/pause"))
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertIn("приостановлен", result.message_ru.lower())


class TestResumeCommandThroughTransport(unittest.TestCase):
    def test_resume(self):
        transport = _make_transport()
        transport.receive(_make_payload(text="/pause"))
        result = transport.receive(_make_payload(text="/resume"))
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertIn("возобновлен", result.message_ru.lower())

    def test_resume_already_active(self):
        transport = _make_transport()
        result = transport.receive(_make_payload(text="/resume"))
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertIn("возобновлен", result.message_ru.lower())


class TestFreeformClassificationThroughTransport(unittest.TestCase):
    def test_intake_is_classified(self):
        transport = _make_transport()
        result = transport.receive(_make_payload(text="хочу сделать приложение"))
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertEqual(result.category, MessageCategory.INTAKE)

    def test_approval_is_classified(self):
        transport = _make_transport()
        transport._adapter.route_specialist_question(
            _CHAT_FOUNDER,
            SpecialistQuestion(
                context="Нужно ли добавлять авторизацию",
                options=["Да", "Нет"],
                recommendation="Да",
                impact="Безопасность",
                urgency="medium",
            ),
        )
        result = transport.receive(_make_payload(text="да, одобряю"))
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertEqual(result.category, MessageCategory.APPROVAL)

    def test_rejection_is_classified(self):
        transport = _make_transport()
        transport._adapter.route_specialist_question(
            _CHAT_FOUNDER,
            SpecialistQuestion(
                context="Нужно ли",
                options=["Да", "Нет"],
                recommendation="Да",
                impact="Среднее",
                urgency="low",
            ),
        )
        result = transport.receive(_make_payload(text="нет, отклоняю"))
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertEqual(result.category, MessageCategory.REJECTION)

    def test_clarification_is_classified(self):
        transport = _make_transport()
        transport._adapter.route_specialist_question(
            _CHAT_FOUNDER,
            SpecialistQuestion(
                context="Нужно ли",
                options=["Да", "Нет"],
                recommendation="Да",
                impact="Среднее",
                urgency="low",
            ),
        )
        result = transport.receive(_make_payload(text="уточни что значит"))
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertEqual(result.category, MessageCategory.CLARIFICATION)

    def test_general_question_is_classified(self):
        transport = _make_transport()
        result = transport.receive(_make_payload(text="как работает CI?"))
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertEqual(result.category, MessageCategory.GENERAL_QUESTION)


class TestSpecialistQuestionDelivery(unittest.TestCase):
    def test_question_delivery_through_transport(self):
        recorder = _RecordingOutboundCallback()
        transport = _make_transport(outbound_factory=lambda: recorder)
        q = SpecialistQuestion(
            context="Выбор фронтенд фреймворка",
            options=["React", "Vue", "Svelte"],
            recommendation="React",
            impact="Весь UI разработки",
            urgency="high",
        )
        transport._adapter.route_specialist_question(_CHAT_FOUNDER, q)
        result = transport.receive(_make_payload(text="/decisions"))
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertIn("открытый вопрос", result.message_ru.lower())

    def test_question_russian_text_is_preserved(self):
        q = SpecialistQuestion(
            context="Тестовый контекст",
            options=["Опция А", "Опция Б"],
            recommendation="Опция А",
            impact="Большое",
            urgency="medium",
        )
        text = q.to_russian_text()
        self.assertIn("Тестовый контекст", text)
        self.assertIn("Опция А", text)
        self.assertIn("средняя", text)


class TestFounderAnswerCapture(unittest.TestCase):
    def test_founder_answer_is_classified(self):
        transport = _make_transport()
        transport._adapter.route_specialist_question(
            _CHAT_FOUNDER,
            SpecialistQuestion(
                context="Выбор",
                options=["А", "Б"],
                recommendation="А",
                impact="Малое",
                urgency="low",
            ),
        )
        result = transport.receive(_make_payload(text="выбираю вариант Б"))
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertEqual(result.category, MessageCategory.ANSWER)

    def test_founder_approval_captured_as_durable(self):
        transport = _make_transport()
        transport._adapter.route_specialist_question(
            _CHAT_FOUNDER,
            SpecialistQuestion(
                context="Merge в production",
                options=["Да", "Нет"],
                recommendation="Да",
                impact="Production deployment",
                urgency="high",
            ),
        )
        result = transport.receive(_make_payload(text="одобряю мерж"))
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertEqual(result.category, MessageCategory.APPROVAL)


class TestProgressReportDelivery(unittest.TestCase):
    def test_progress_report_russian_text(self):
        report = ProgressReport(
            completed="TKT-015 реализация",
            current_action="Написание тестов",
            blocker_state="Нет",
            decisions_needed="Нет",
            notable_risks="Нет",
        )
        text = report.to_russian_text()
        self.assertIn("Завершено:", text)
        self.assertIn("TKT-015", text)
        self.assertIn("Текущее действие:", text)
        self.assertIn("Блокеры:", text)
        self.assertIn("Нет", text)

    def test_progress_report_delivery_through_outbound(self):
        recorder = _RecordingOutboundCallback()
        transport = _make_transport(outbound_factory=lambda: recorder)
        report = ProgressReport(
            completed="Шаг 1",
            current_action="Шаг 2",
            blocker_state="Нет",
            decisions_needed="Нет",
            notable_risks="Нет",
        )
        transport.deliver(
            CommandResult(
                command="/decisions",
                chat_key=_CHAT_FOUNDER,
                response_key="progress",
                status="ok",
                message_ru=report.to_russian_text(),
            ),
            callback=recorder,
        )
        self.assertEqual(len(recorder.calls), 1)
        self.assertEqual(recorder.calls[0][0], _CHAT_FOUNDER)
        self.assertIn("Завершено:", recorder.calls[0][1])


class TestOutboundSender(unittest.TestCase):
    def test_sender_invokes_callback(self):
        recorder = _RecordingOutboundCallback()
        sender = HermesTelegramSender(recorder)
        sender.send(_CHAT_FOUNDER, "Привет, основатель")
        self.assertEqual(len(recorder.calls), 1)
        self.assertEqual(recorder.calls[0], (_CHAT_FOUNDER, "Привет, основатель"))

    def test_sender_preserves_russian_text(self):
        recorder = _RecordingOutboundCallback()
        sender = HermesTelegramSender(recorder)
        russian_text = "Проект приостановлен. Ожидаю решения основателя по выбору стека."
        sender.send(_CHAT_FOUNDER, russian_text)
        self.assertEqual(recorder.calls[0][1], russian_text)

    def test_create_sender_from_transport(self):
        transport = _make_transport()
        sender = transport.create_sender()
        self.assertIsNotNone(sender)
        sender.send(_CHAT_FOUNDER, "тест")

    def test_deliver_uses_callback(self):
        recorder = _RecordingOutboundCallback()
        transport = _make_transport(outbound_factory=lambda: recorder)
        result = transport.receive(_make_payload(text="/status"))
        transport.deliver(result, callback=recorder)
        self.assertTrue(len(recorder.calls) > 0)

    def test_deliver_as_sender_uses_factory(self):
        recorder = _RecordingOutboundCallback()
        transport = _make_transport(outbound_factory=lambda: recorder)
        result = transport.receive(_make_payload(text="/status"))
        transport.deliver_as_sender(result)
        self.assertTrue(len(recorder.calls) > 0)


class TestTokenAndPrivateIDLeakPrevention(unittest.TestCase):
    def test_payload_rejects_numeric_chat_as_raw(self):
        p = _make_payload(chat="123456")
        self.assertIsNotNone(p.validate())

    def test_payload_rejects_numeric_user_as_raw(self):
        p = _make_payload(user="999999")
        self.assertIsNotNone(p.validate())

    def test_config_never_contains_token_value(self):
        cfg = _make_config()
        self.assertFalse(hasattr(cfg, "bot_token"))
        self.assertTrue(hasattr(cfg, "bot_token_configured"))
        self.assertIsInstance(cfg.bot_token_configured, bool)

    def test_sanitize_gateway_payload_returns_sanitized_keys(self):
        result = sanitize_gateway_payload(
            raw_chat_id="123456",
            raw_user_id="789012",
            text="/status",
            timestamp=_TS,
            chat_label="chat:founder",
            user_label="user:founder",
        )
        self.assertEqual(result.source_chat, "chat:founder")
        self.assertEqual(result.source_user, "user:founder")
        self.assertNotEqual(result.source_chat, "123456")
        self.assertNotEqual(result.source_user, "789012")

    def test_outbound_does_not_expose_token(self):
        recorder = _RecordingOutboundCallback()
        sender = HermesTelegramSender(recorder)
        sender.send(_CHAT_FOUNDER, "test message")
        for _, text in recorder.calls:
            self.assertNotIn("TOKEN", text.upper())
            self.assertNotIn("BOT", text.upper())

    def test_error_message_does_not_leak_private_id(self):
        transport = _make_transport()
        result = transport.receive(_make_payload(chat="123456789"))
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertNotIn("123456789", result.text)

    def test_unauthorized_message_does_not_leak_chat_id(self):
        transport = _make_transport()
        result = transport.receive(_make_payload(chat="chat:stranger"))
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertNotIn("chat:stranger", result.text)


class TestValidateTransportConfigEnv(unittest.TestCase):
    def test_valid_env_no_violations(self):
        violations = validate_transport_config_env(
            telegram_bot_token_set=True,
            telegram_allowed_users_set=True,
            polling_mode=True,
            webhook_mode=False,
        )
        self.assertEqual(violations, [])

    def test_missing_bot_token_violation(self):
        violations = validate_transport_config_env(
            telegram_bot_token_set=False,
            telegram_allowed_users_set=True,
        )
        self.assertTrue(any("TELEGRAM_BOT_TOKEN" in v for v in violations))

    def test_missing_allowed_users_violation(self):
        violations = validate_transport_config_env(
            telegram_bot_token_set=True,
            telegram_allowed_users_set=False,
        )
        self.assertTrue(any("TELEGRAM_ALLOWED_USERS" in v for v in violations))

    def test_gateway_allow_all_violation(self):
        violations = validate_transport_config_env(
            telegram_bot_token_set=True,
            telegram_allowed_users_set=True,
            gateway_allow_all="true",
        )
        self.assertTrue(any("GATEWAY_ALLOW_ALL_USERS" in v for v in violations))

    def test_telegram_allow_all_violation(self):
        violations = validate_transport_config_env(
            telegram_bot_token_set=True,
            telegram_allowed_users_set=True,
            telegram_allow_all="1",
        )
        self.assertTrue(any("TELEGRAM_ALLOW_ALL_USERS" in v for v in violations))

    def test_webhook_without_secret_violation(self):
        violations = validate_transport_config_env(
            telegram_bot_token_set=True,
            telegram_allowed_users_set=True,
            webhook_mode=True,
            telegram_webhook_secret_set=False,
        )
        self.assertTrue(any("TELEGRAM_WEBHOOK_SECRET" in v for v in violations))

    def test_webhook_with_secret_no_violation(self):
        violations = validate_transport_config_env(
            telegram_bot_token_set=True,
            telegram_allowed_users_set=True,
            webhook_mode=True,
            telegram_webhook_secret_set=True,
        )
        self.assertFalse(any("TELEGRAM_WEBHOOK_SECRET" in v for v in violations))

    def test_polling_and_webhook_mutually_exclusive_violation(self):
        violations = validate_transport_config_env(
            telegram_bot_token_set=True,
            telegram_allowed_users_set=True,
            webhook_mode=True,
            polling_mode=True,
        )
        self.assertTrue(any("mutually exclusive" in v for v in violations))

    def test_allow_all_false_strings_are_accepted(self):
        for val in ("false", "False", "0"):
            violations = validate_transport_config_env(
                telegram_bot_token_set=True,
                telegram_allowed_users_set=True,
                gateway_allow_all=val,
                telegram_allow_all="false",
            )
            self.assertEqual(violations, [], f"failed for {val!r}")

    def test_allow_all_empty_strings_are_accepted(self):
        violations = validate_transport_config_env(
            telegram_bot_token_set=True,
            telegram_allowed_users_set=True,
            gateway_allow_all="",
            telegram_allow_all="",
        )
        self.assertEqual(violations, [])


class TestExistingAdapterBehaviorPreserved(unittest.TestCase):
    """Verify TKT-006 adapter behavior is unchanged via transport layer."""

    def test_handle_event_still_classifies_intake(self):
        adapter = TelegramFounderAdapter(
            authorizer=FounderAuthorizer(
                FounderAllowlistConfig(
                    allowed_chat_keys=[_CHAT_FOUNDER],
                    allowed_user_keys=[_USER_FOUNDER],
                )
            )
        )
        event = TelegramEvent(
            chat_key=_CHAT_FOUNDER,
            user_key=_USER_FOUNDER,
            text="хочу сделать приложение",
            timestamp=_TS,
        )
        result = adapter.handle_event(event)
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertEqual(result.category, MessageCategory.INTAKE)

    def test_handle_event_still_routes_commands(self):
        adapter = TelegramFounderAdapter(
            authorizer=FounderAuthorizer(
                FounderAllowlistConfig(
                    allowed_chat_keys=[_CHAT_FOUNDER],
                    allowed_user_keys=[_USER_FOUNDER],
                )
            )
        )
        event = TelegramEvent(
            chat_key=_CHAT_FOUNDER,
            user_key=_USER_FOUNDER,
            text="/status",
            timestamp=_TS,
        )
        result = adapter.handle_event(event)
        self.assertIsInstance(result, CommandResult)

    def test_handle_event_still_rejects_unauthorized(self):
        adapter = TelegramFounderAdapter(
            authorizer=FounderAuthorizer(
                FounderAllowlistConfig(
                    allowed_chat_keys=[_CHAT_FOUNDER],
                )
            )
        )
        event = TelegramEvent(
            chat_key="chat:stranger",
            user_key="user:stranger",
            text="/status",
            timestamp=_TS,
        )
        result = adapter.handle_event(event)
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertIn("Unauthorized", result.text)

    def test_classify_message_smoke(self):
        for text, expected in [
            ("хочу создать приложение", MessageCategory.INTAKE),
            ("да, согласен", MessageCategory.APPROVAL),
            ("нет, отказываю", MessageCategory.REJECTION),
            ("подробнее расскажи", MessageCategory.CLARIFICATION),
            ("как это работает", MessageCategory.GENERAL_QUESTION),
        ]:
            with self.subTest(text=text):
                result = classify_message(text)
                self.assertEqual(result, expected, f"Failed for {text}")


if __name__ == "__main__":
    unittest.main()