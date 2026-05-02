"""Tests for Telegram founder interaction adapter (TKT-006).

Covers:
- Command routing for /new_project, /status, /decisions, /pause, /resume
- Allowlist/authorization behavior
- Free-form message classification
- Specialist-agent question formatting/routing
- Durable decision capture
- Progress report scheduling
- Secret/raw identifier hygiene
"""

import unittest
from dataclasses import dataclass
from typing import List

from src.developer_assistant.telegram_adapter import (
    ClassificationResult,
    CommandName,
    CommandResult,
    FounderAllowlistConfig,
    FounderAuthorizer,
    MessageCategory,
    ProgressReport,
    SpecialistQuestion,
    TelegramEvent,
    TelegramFounderAdapter,
    _MIN_REPORT_INTERVAL_MINUTES,
    _MAX_REPORT_INTERVAL_MINUTES,
    classify_message,
    validate_telegram_config_env,
)


@dataclass
class _RecordedWrite:
    path: str
    content: str


class _RecordingArtifactWriter:
    def __init__(self) -> None:
        self.writes: List[_RecordedWrite] = []

    def write(self, artifact_path: str, content: str) -> None:
        self.writes.append(_RecordedWrite(path=artifact_path, content=content))


class _RecordingTelegramSender:
    def __init__(self) -> None:
        self.sent: List[tuple] = []

    def send(self, chat_key: str, text: str) -> None:
        self.sent.append((chat_key, text))


def _make_event(chat_key: str = "chat:founder", user_key: str = "user:founder", text: str = "", timestamp: str = "2026-05-03T12:00:00+00:00") -> TelegramEvent:
    return TelegramEvent(chat_key=chat_key, user_key=user_key, text=text, timestamp=timestamp)


def _make_authorizer(chat_keys=None, user_keys=None, gateway_allow_all=False, telegram_allow_all=False) -> FounderAuthorizer:
    if chat_keys is None:
        chat_keys = ["chat:founder"]
    if user_keys is None:
        user_keys = ["user:founder"]
    return FounderAuthorizer(FounderAllowlistConfig(
        allowed_chat_keys=chat_keys,
        allowed_user_keys=user_keys,
        gateway_allow_all=gateway_allow_all,
        telegram_allow_all=telegram_allow_all,
    ))


def _make_adapter(authorizer=None, writer=None, sender=None) -> TelegramFounderAdapter:
    if authorizer is None:
        authorizer = _make_authorizer()
    if writer is None:
        writer = _RecordingArtifactWriter()
    if sender is None:
        sender = _RecordingTelegramSender()
    return TelegramFounderAdapter(authorizer=authorizer, artifact_writer=writer, telegram_sender=sender)


class TestCommandRouting(unittest.TestCase):
    def test_new_project(self):
        adapter = _make_adapter()
        result = adapter.handle_event(_make_event(text="/new_project"))
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertEqual(result.command, CommandName.NEW_PROJECT)
        self.assertEqual(result.status, "started")
        self.assertIn("нового проекта", result.message_ru.lower())

    def test_status(self):
        adapter = _make_adapter()
        adapter.handle_event(_make_event(text="/new_project"))
        result = adapter.handle_event(_make_event(text="/status"))
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertEqual(result.command, CommandName.STATUS)
        self.assertEqual(result.status, "ok")

    def test_decisions_no_pending(self):
        adapter = _make_adapter()
        result = adapter.handle_event(_make_event(text="/decisions"))
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertEqual(result.command, CommandName.DECISIONS)
        self.assertEqual(result.status, "ok")

    def test_decisions_with_pending_question(self):
        sender = _RecordingTelegramSender()
        adapter = _make_adapter(sender=sender)
        q = SpecialistQuestion(
            context="Need to choose stack",
            options=["Python", "Node.js"],
            recommendation="Python",
            impact="Affects all implementation",
            urgency="high",
        )
        adapter.route_specialist_question("chat:founder", q)
        result = adapter.handle_event(_make_event(text="/decisions"))
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertEqual(result.command, CommandName.DECISIONS)
        self.assertEqual(result.status, "pending")
        self.assertIn("открытый вопрос", result.message_ru.lower())

    def test_pause(self):
        adapter = _make_adapter()
        result = adapter.handle_event(_make_event(text="/pause"))
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertEqual(result.command, CommandName.PAUSE)
        self.assertEqual(result.status, "paused")

    def test_resume(self):
        adapter = _make_adapter()
        adapter.handle_event(_make_event(text="/pause"))
        result = adapter.handle_event(_make_event(text="/resume"))
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertEqual(result.command, CommandName.RESUME)
        self.assertEqual(result.status, "resumed")

    def test_command_with_bot_name_suffix(self):
        adapter = _make_adapter()
        result = adapter.handle_event(_make_event(text="/status@mybot"))
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertEqual(result.command, CommandName.STATUS)

    def test_unknown_text_not_command(self):
        adapter = _make_adapter()
        result = adapter.handle_event(_make_event(text="Hello, how are you?"))
        self.assertIsInstance(result, ClassificationResult)


class TestAllowlistAuthorization(unittest.TestCase):
    def test_allowed_chat(self):
        authorizer = _make_authorizer(chat_keys=["chat:founder"])
        self.assertTrue(authorizer.is_allowed("chat:founder", "user:unknown"))

    def test_allowed_user(self):
        authorizer = _make_authorizer(user_keys=["user:founder"])
        self.assertTrue(authorizer.is_allowed("chat:unknown", "user:founder"))

    def test_rejected_chat_and_user(self):
        authorizer = _make_authorizer(chat_keys=["chat:founder"], user_keys=["user:founder"])
        self.assertFalse(authorizer.is_allowed("chat:stranger", "user:stranger"))

    def test_gateway_allow_all_denied(self):
        authorizer = _make_authorizer(chat_keys=["chat:founder"], gateway_allow_all=True)
        self.assertFalse(authorizer.is_allowed("chat:founder", "user:founder"))

    def test_telegram_allow_all_denied(self):
        authorizer = _make_authorizer(chat_keys=["chat:founder"], telegram_allow_all=True)
        self.assertFalse(authorizer.is_allowed("chat:founder", "user:founder"))

    def test_unauthorized_event_returns_rejection(self):
        authorizer = _make_authorizer(chat_keys=["chat:founder"])
        adapter = TelegramFounderAdapter(authorizer=authorizer)
        result = adapter.handle_event(_make_event(chat_key="chat:stranger", user_key="user:stranger", text="/status"))
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertEqual(result.category, MessageCategory.REJECTION)

    def test_validate_config_ok(self):
        authorizer = _make_authorizer()
        self.assertIsNone(authorizer.validate_config())

    def test_validate_config_gateway_allow_all(self):
        authorizer = _make_authorizer(gateway_allow_all=True)
        self.assertIsNotNone(authorizer.validate_config())

    def test_validate_config_telegram_allow_all(self):
        authorizer = _make_authorizer(telegram_allow_all=True)
        self.assertIsNotNone(authorizer.validate_config())

    def test_validate_config_empty_allowlist(self):
        authorizer = FounderAuthorizer(FounderAllowlistConfig())
        self.assertIsNotNone(authorizer.validate_config())


class TestFreeFormClassification(unittest.TestCase):
    def test_intake_default(self):
        self.assertEqual(classify_message("I want to build a new app"), MessageCategory.INTAKE)

    def test_approval_ru(self):
        self.assertEqual(classify_message("Одобряю этот план"), MessageCategory.APPROVAL)

    def test_approval_en(self):
        self.assertEqual(classify_message("I approve this architecture"), MessageCategory.APPROVAL)

    def test_rejection_ru(self):
        self.assertEqual(classify_message("Отклоняю предложение"), MessageCategory.REJECTION)

    def test_rejection_en(self):
        self.assertEqual(classify_message("I reject this proposal"), MessageCategory.REJECTION)

    def test_clarification_ru(self):
        self.assertEqual(classify_message("Уточни, что значит этот термин"), MessageCategory.CLARIFICATION)

    def test_clarification_en(self):
        self.assertEqual(classify_message("Can you clarify what this means?"), MessageCategory.CLARIFICATION)

    def test_general_question_ru(self):
        self.assertEqual(classify_message("Как будет работать деплой?"), MessageCategory.GENERAL_QUESTION)

    def test_general_question_en(self):
        self.assertEqual(classify_message("How will the deployment work?"), MessageCategory.GENERAL_QUESTION)

    def test_pending_question_answer(self):
        self.assertEqual(classify_message("Use Python for backend", pending_question=True), MessageCategory.ANSWER)

    def test_pending_question_approval(self):
        self.assertEqual(classify_message("Approve the merge", pending_question=True), MessageCategory.APPROVAL)

    def test_pending_question_rejection(self):
        self.assertEqual(classify_message("Reject the change", pending_question=True), MessageCategory.REJECTION)

    def test_pending_question_clarification(self):
        self.assertEqual(classify_message("Clarify the impact", pending_question=True), MessageCategory.CLARIFICATION)

    def test_pending_question_answer_default(self):
        self.assertEqual(classify_message("I think we should use SQLite", pending_question=True), MessageCategory.ANSWER)

    def test_classification_exactly_one(self):
        categories = set(MessageCategory)
        result = classify_message("одобряю")
        self.assertIn(result, categories)

    def test_all_categories_covered(self):
        expected = {"intake", "answer", "clarification", "approval", "rejection", "general_question"}
        self.assertEqual(set(c.value for c in MessageCategory), expected)


class TestSpecialistQuestionFormatting(unittest.TestCase):
    def test_fields_present(self):
        q = SpecialistQuestion(
            context="Choosing database",
            options=["SQLite", "PostgreSQL"],
            recommendation="SQLite",
            impact="Affects persistence layer",
            urgency="low",
        )
        text = q.to_russian_text()
        self.assertIn("Контекст", text)
        self.assertIn("Варианты", text)
        self.assertIn("Рекомендация", text)
        self.assertIn("Влияние", text)
        self.assertIn("Срочность", text)
        self.assertIn("низкая", text)

    def test_urgency_validation(self):
        with self.assertRaises(ValueError):
            SpecialistQuestion(
                context="test", options=["a"], recommendation="a",
                impact="none", urgency="critical",
            )

    def test_urgency_medium(self):
        q = SpecialistQuestion(
            context="test", options=["a"], recommendation="a",
            impact="none", urgency="medium",
        )
        self.assertIn("средняя", q.to_russian_text())

    def test_urgency_high(self):
        q = SpecialistQuestion(
            context="test", options=["a"], recommendation="a",
            impact="none", urgency="high",
        )
        self.assertIn("высокая", q.to_russian_text())

    def test_routing_sends_to_telegram(self):
        sender = _RecordingTelegramSender()
        adapter = _make_adapter(sender=sender)
        q = SpecialistQuestion(
            context="Stack choice",
            options=["Python", "Go"],
            recommendation="Python",
            impact="Core implementation language",
            urgency="medium",
        )
        text = adapter.route_specialist_question("chat:founder", q)
        self.assertTrue(len(sender.sent) > 0)
        sent_chat, sent_text = sender.sent[0]
        self.assertEqual(sent_chat, "chat:founder")
        self.assertIn("Stack choice", sent_text)

    def test_routing_stores_pending_question(self):
        sender = _RecordingTelegramSender()
        adapter = _make_adapter(sender=sender)
        q = SpecialistQuestion(
            context="test", options=["a"], recommendation="a",
            impact="none", urgency="low",
        )
        adapter.route_specialist_question("chat:founder", q)
        result = adapter.handle_event(_make_event(text="/decisions"))
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertEqual(result.status, "pending")


class TestDurableDecisionCapture(unittest.TestCase):
    def test_durable_approval_writes_artifact(self):
        writer = _RecordingArtifactWriter()
        adapter = _make_adapter(writer=writer)
        result = adapter.handle_event(_make_event(text="Одобряю архитектуру проекта"))
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertTrue(result.durable_decision)
        self.assertIsNotNone(result.artifact_target)
        self.assertTrue(len(writer.writes) > 0)
        self.assertEqual(writer.writes[0].path, "docs/questions/")

    def test_durable_rejection_writes_artifact(self):
        writer = _RecordingArtifactWriter()
        adapter = _make_adapter(writer=writer)
        result = adapter.handle_event(_make_event(text="Отклоняю change в продакшн"))
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertTrue(result.durable_decision)
        self.assertTrue(len(writer.writes) > 0)

    def test_nondurable_approval_no_artifact_write(self):
        writer = _RecordingArtifactWriter()
        adapter = _make_adapter(writer=writer)
        result = adapter.handle_event(_make_event(text="Approve the typo fix"))
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertFalse(result.durable_decision)
        self.assertEqual(len(writer.writes), 0)

    def test_answer_to_pending_question_clears_it(self):
        writer = _RecordingArtifactWriter()
        sender = _RecordingTelegramSender()
        adapter = _make_adapter(writer=writer, sender=sender)
        q = SpecialistQuestion(
            context="Stack choice", options=["Python", "Go"],
            recommendation="Python", impact="Core language",
            urgency="medium",
        )
        adapter.route_specialist_question("chat:founder", q)
        result = adapter.handle_event(_make_event(text="Use Python for the backend architecture"))
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertEqual(result.category, MessageCategory.ANSWER)
        result2 = adapter.handle_event(_make_event(text="/decisions"))
        self.assertIsInstance(result2, CommandResult)
        assert isinstance(result2, CommandResult)
        self.assertEqual(result2.status, "ok")

    def test_writer_not_called_for_nondurable(self):
        writer = _RecordingArtifactWriter()
        adapter = _make_adapter(writer=writer)
        adapter.handle_event(_make_event(text="Как дела?"))
        self.assertEqual(len(writer.writes), 0)

    def test_artifact_content_includes_chat_key_and_text(self):
        writer = _RecordingArtifactWriter()
        adapter = _make_adapter(writer=writer)
        adapter.handle_event(_make_event(text="Одобряю архитектуру деплоя"))
        self.assertIn("chat:founder", writer.writes[0].content)
        self.assertIn("архитектуру деплоя", writer.writes[0].content)


class TestProgressReportScheduling(unittest.TestCase):
    def _make_report(self) -> ProgressReport:
        return ProgressReport(
            completed="TKT-006 implementation",
            current_action="Writing tests",
            blocker_state="None",
            decisions_needed="Stack choice",
            notable_risks="None",
        )

    def test_milestone_report_always_due(self):
        adapter = _make_adapter()
        self.assertTrue(adapter.is_report_due("chat:founder", "2026-05-03T12:00:00+00:00", is_milestone=True))

    def test_first_report_due_when_no_previous(self):
        adapter = _make_adapter()
        self.assertTrue(adapter.is_report_due("chat:founder", "2026-05-03T12:00:00+00:00"))

    def test_report_not_due_within_interval(self):
        adapter = _make_adapter()
        sender = _RecordingTelegramSender()
        adapter._telegram_sender = sender
        adapter.send_progress_report("chat:founder", self._make_report(), "2026-05-03T12:00:00+00:00")
        self.assertFalse(adapter.is_report_due("chat:founder", "2026-05-03T12:30:00+00:00"))
        self.assertTrue(adapter.is_report_due("chat:founder", "2026-05-03T12:46:00+00:00"))

    def test_report_due_after_interval(self):
        adapter = _make_adapter()
        sender = _RecordingTelegramSender()
        adapter._telegram_sender = sender
        adapter.send_progress_report("chat:founder", self._make_report(), "2026-05-03T12:00:00+00:00")
        self.assertTrue(adapter.is_report_due("chat:founder", "2026-05-03T12:46:00+00:00"))

    def test_send_report_sends_russian_text(self):
        sender = _RecordingTelegramSender()
        adapter = _make_adapter(sender=sender)
        report = self._make_report()
        text = adapter.send_progress_report("chat:founder", report, "2026-05-03T12:00:00+00:00")
        self.assertTrue(len(text) > 0)
        self.assertIn("Завершено", text)
        self.assertTrue(len(sender.sent) > 0)

    def test_send_report_returns_empty_when_not_due(self):
        sender = _RecordingTelegramSender()
        adapter = _make_adapter(sender=sender)
        report = self._make_report()
        adapter.send_progress_report("chat:founder", report, "2026-05-03T12:00:00+00:00")
        text = adapter.send_progress_report("chat:founder", report, "2026-05-03T12:10:00+00:00")
        self.assertEqual(text, "")

    def test_set_report_interval_valid(self):
        adapter = _make_adapter()
        adapter.set_report_interval("chat:founder", 45)
        self.assertEqual(adapter._report_intervals["chat:founder"], 45)

    def test_set_report_interval_too_low(self):
        adapter = _make_adapter()
        with self.assertRaises(ValueError):
            adapter.set_report_interval("chat:founder", 15)

    def test_set_report_interval_too_high(self):
        adapter = _make_adapter()
        with self.assertRaises(ValueError):
            adapter.set_report_interval("chat:founder", 90)

    def test_interval_boundary_30(self):
        adapter = _make_adapter()
        adapter.set_report_interval("chat:founder", 30)
        self.assertEqual(adapter._report_intervals["chat:founder"], 30)

    def test_interval_boundary_60(self):
        adapter = _make_adapter()
        adapter.set_report_interval("chat:founder", 60)
        self.assertEqual(adapter._report_intervals["chat:founder"], 60)

    def test_invalid_interval_clamped_in_is_report_due(self):
        adapter = _make_adapter()
        adapter._report_intervals["chat:founder"] = 10
        sender = _RecordingTelegramSender()
        adapter._telegram_sender = sender
        adapter.send_progress_report("chat:founder", self._make_report(), "2026-05-03T12:00:00+00:00")
        self.assertFalse(adapter.is_report_due("chat:founder", "2026-05-03T12:30:00+00:00"))
        self.assertTrue(adapter.is_report_due("chat:founder", "2026-05-03T12:46:00+00:00"))

    def test_milestone_report_overrides_interval(self):
        adapter = _make_adapter()
        sender = _RecordingTelegramSender()
        adapter._telegram_sender = sender
        adapter.send_progress_report("chat:founder", self._make_report(), "2026-05-03T12:00:00+00:00")
        self.assertTrue(adapter.is_report_due("chat:founder", "2026-05-03T12:05:00+00:00", is_milestone=True))


class TestSecretHygiene(unittest.TestCase):
    def test_no_token_in_event(self):
        event = _make_event()
        self.assertNotIn("token", event.chat_key)
        self.assertNotIn("token", event.user_key)

    def test_sanitized_chat_keys_in_fixtures(self):
        self.assertEqual(_make_event().chat_key, "chat:founder")
        self.assertEqual(_make_event().user_key, "user:founder")

    def test_adapter_no_token_storage(self):
        adapter = _make_adapter()
        all_attrs = dir(adapter)
        for attr in all_attrs:
            if attr.startswith("_") and not attr.startswith("__"):
                val = getattr(adapter, attr)
                if isinstance(val, str):
                    self.assertNotIn("bot_token", val.lower())
                    self.assertNotIn("telegram_token", val.lower())

    def test_config_env_no_token_values(self):
        violations = validate_telegram_config_env(
            gateway_allow_all=None,
            telegram_allow_all=None,
            telegram_bot_token_set=True,
            telegram_allowed_users_set=True,
            webhook_mode=False,
        )
        self.assertEqual(len(violations), 0)


class TestTelegramConfigValidation(unittest.TestCase):
    def test_valid_polling_config(self):
        violations = validate_telegram_config_env(
            telegram_bot_token_set=True,
            telegram_allowed_users_set=True,
            webhook_mode=False,
        )
        self.assertEqual(len(violations), 0)

    def test_gateway_allow_all_violation(self):
        violations = validate_telegram_config_env(
            gateway_allow_all="true",
            telegram_bot_token_set=True,
            telegram_allowed_users_set=True,
        )
        self.assertTrue(any("GATEWAY_ALLOW_ALL_USERS" in v for v in violations))

    def test_telegram_allow_all_violation(self):
        violations = validate_telegram_config_env(
            telegram_allow_all="true",
            telegram_bot_token_set=True,
            telegram_allowed_users_set=True,
        )
        self.assertTrue(any("TELEGRAM_ALLOW_ALL_USERS" in v for v in violations))

    def test_missing_allowed_users(self):
        violations = validate_telegram_config_env(
            telegram_bot_token_set=True,
            telegram_allowed_users_set=False,
            webhook_mode=False,
        )
        self.assertTrue(any("TELEGRAM_ALLOWED_USERS" in v for v in violations))

    def test_missing_bot_token(self):
        violations = validate_telegram_config_env(
            telegram_bot_token_set=False,
            telegram_allowed_users_set=True,
        )
        self.assertTrue(any("TELEGRAM_BOT_TOKEN" in v for v in violations))

    def test_webhook_without_secret(self):
        violations = validate_telegram_config_env(
            telegram_bot_token_set=True,
            telegram_allowed_users_set=True,
            webhook_mode=True,
            telegram_webhook_secret_set=False,
        )
        self.assertTrue(any("TELEGRAM_WEBHOOK_SECRET" in v for v in violations))

    def test_webhook_with_secret_ok(self):
        violations = validate_telegram_config_env(
            telegram_bot_token_set=True,
            telegram_allowed_users_set=True,
            webhook_mode=True,
            telegram_webhook_secret_set=True,
        )
        self.assertEqual(len(violations), 0)

    def test_allow_all_false_string_ok(self):
        violations = validate_telegram_config_env(
            gateway_allow_all="false",
            telegram_allow_all="0",
            telegram_bot_token_set=True,
            telegram_allowed_users_set=True,
        )
        self.assertEqual(len(violations), 0)


class TestProjectStateManagement(unittest.TestCase):
    def test_update_phase(self):
        adapter = _make_adapter()
        adapter.update_project_state("chat:founder", phase="architecture")
        proj = adapter._projects["chat:founder"]
        self.assertEqual(proj.phase, "architecture")

    def test_update_active_ticket(self):
        adapter = _make_adapter()
        adapter.update_project_state("chat:founder", active_ticket="TKT-007")
        self.assertEqual(adapter._projects["chat:founder"].active_ticket, "TKT-007")

    def test_pause_resume_project_state(self):
        adapter = _make_adapter()
        adapter.handle_event(_make_event(text="/pause"))
        self.assertTrue(adapter._projects["chat:founder"].paused)
        adapter.handle_event(_make_event(text="/resume"))
        self.assertFalse(adapter._projects["chat:founder"].paused)

    def test_status_reflects_project_state(self):
        adapter = _make_adapter()
        adapter.update_project_state(
            "chat:founder",
            phase="implementation",
            active_ticket="TKT-006",
            active_pr="PR-25",
            blockers="Waiting for review",
            pending_decisions="Stack choice",
        )
        result = adapter.handle_event(_make_event(text="/status"))
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertIn("implementation", result.message_ru)
        self.assertIn("TKT-006", result.message_ru)
        self.assertIn("PR-25", result.message_ru)


class TestEdgeCases(unittest.TestCase):
    def test_command_with_extra_spaces(self):
        adapter = _make_adapter()
        result = adapter.handle_event(_make_event(text="  /status  "))
        self.assertIsInstance(result, CommandResult)
        assert isinstance(result, CommandResult)
        self.assertEqual(result.command, CommandName.STATUS)

    def test_non_command_slash(self):
        adapter = _make_adapter()
        result = adapter.handle_event(_make_event(text="/unknown_command"))
        self.assertIsInstance(result, ClassificationResult)

    def test_empty_text(self):
        adapter = _make_adapter()
        result = adapter.handle_event(_make_event(text=""))
        self.assertIsInstance(result, ClassificationResult)
        assert isinstance(result, ClassificationResult)
        self.assertEqual(result.category, MessageCategory.INTAKE)

    def test_multiple_projects_isolated(self):
        authorizer = _make_authorizer(chat_keys=["chat:proj-alpha", "chat:proj-beta"])
        adapter = _make_adapter(authorizer=authorizer)
        adapter.handle_event(_make_event(chat_key="chat:proj-alpha", text="/new_project"))
        adapter.handle_event(_make_event(chat_key="chat:proj-beta", text="/pause"))
        self.assertFalse(adapter._projects["chat:proj-alpha"].paused)
        self.assertTrue(adapter._projects["chat:proj-beta"].paused)

    def test_progress_report_russian_text(self):
        report = ProgressReport(
            completed="TKT-006 done",
            current_action="Running tests",
            blocker_state="None",
            decisions_needed="Merge approval",
            notable_risks="Test flakiness",
        )
        text = report.to_russian_text()
        self.assertIn("Завершено", text)
        self.assertIn("Текущее действие", text)
        self.assertIn("Блокеры", text)
        self.assertIn("Требуются решения", text)
        self.assertIn("Риски", text)

    def test_specialist_question_options_formatting(self):
        q = SpecialistQuestion(
            context="Test",
            options=["Option A", "Option B", "Option C"],
            recommendation="Option A",
            impact="Significant",
            urgency="medium",
        )
        text = q.to_russian_text()
        self.assertIn("- Option A", text)
        self.assertIn("- Option B", text)
        self.assertIn("- Option C", text)


if __name__ == "__main__":
    unittest.main()
