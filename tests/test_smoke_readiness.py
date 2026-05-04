"""Unit tests for smoke_readiness.py (TKT-017).

All tests are offline: no live GitHub API calls, no live Telegram gateway
connections, no secrets, no raw chat/user IDs.

The tests exercise:
- Gate default-off behavior
- Credential-source rejection / blocked outcome
- Sanitized evidence formatting
- Transport config validation (blocked when misconfigured)
- Full mock pass path for both lanes
- SmokeReadinessReport serialization
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.developer_assistant.smoke_readiness import (
    GitHubSmokeLane,
    TelegramSmokeLane,
    SmokeLaneStatus,
    SmokeLaneResult,
    SmokeReadinessReport,
    _is_gate_set,
    _sanitize_branch_name,
    _sanitize_pr_url,
    _sanitize_repo_url,
    run_smoke_readiness,
)


class TestGateLogic(unittest.TestCase):
    def test_gate_unset_defaults_to_off(self):
        self.assertFalse(_is_gate_set("SMOKE_GITHUB_LIVE", {}))

    def test_gate_empty_string_is_off(self):
        self.assertFalse(_is_gate_set("SMOKE_GITHUB_LIVE", {"SMOKE_GITHUB_LIVE": ""}))

    def test_gate_false_string_is_off(self):
        self.assertFalse(_is_gate_set("SMOKE_GITHUB_LIVE", {"SMOKE_GITHUB_LIVE": "false"}))

    def test_gate_zero_is_off(self):
        self.assertFalse(_is_gate_set("SMOKE_GITHUB_LIVE", {"SMOKE_GITHUB_LIVE": "0"}))

    def test_gate_one_is_on(self):
        self.assertTrue(_is_gate_set("SMOKE_GITHUB_LIVE", {"SMOKE_GITHUB_LIVE": "1"}))

    def test_gate_true_is_on(self):
        self.assertTrue(_is_gate_set("SMOKE_GITHUB_LIVE", {"SMOKE_GITHUB_LIVE": "true"}))

    def test_gate_yes_is_on(self):
        self.assertTrue(_is_gate_set("SMOKE_GITHUB_LIVE", {"SMOKE_GITHUB_LIVE": "yes"}))

    def test_gate_case_insensitive(self):
        self.assertTrue(_is_gate_set("SMOKE_GITHUB_LIVE", {"SMOKE_GITHUB_LIVE": "TRUE"}))

    def test_gate_wrong_env_var_is_off(self):
        self.assertFalse(_is_gate_set("OTHER_VAR", {"SMOKE_GITHUB_LIVE": "1"}))


class TestSanitizationHelpers(unittest.TestCase):
    def test_sanitize_branch_name(self):
        self.assertEqual(_sanitize_branch_name("TKT-017"), "smoke/tkt-017-live-check")

    def test_sanitize_branch_name_with_suffix(self):
        name = _sanitize_branch_name("TKT-017", suffix="a1b2c3d4")
        self.assertEqual(name, "smoke/tkt-017-live-check-a1b2c3d4")

    def test_sanitize_branch_name_prefix_preserved_with_suffix(self):
        name = _sanitize_branch_name("TKT-017", suffix="ff00ff00")
        self.assertTrue(name.startswith("smoke/tkt-017-live-check-"))

    def test_sanitize_pr_url(self):
        url = _sanitize_pr_url("owner", "repo", 42)
        self.assertEqual(url, "https://github.com/owner/repo/pull/42")
        self.assertNotIn("ghp_", url)

    def test_sanitize_repo_url(self):
        url = _sanitize_repo_url("owner", "repo")
        self.assertEqual(url, "https://github.com/owner/repo")


class TestGitHubSmokeLaneSkipped(unittest.TestCase):
    def test_skipped_when_gate_not_set(self):
        lane = GitHubSmokeLane("owner", "repo", environ={})
        result = lane.run()
        self.assertEqual(result.status, SmokeLaneStatus.SKIPPED)
        self.assertIn("not set", result.evidence)
        self.assertEqual(result.lane, "github")


class TestGitHubSmokeLaneBlocked(unittest.TestCase):
    def _base_env(self, **overrides):
        env = {"SMOKE_GITHUB_LIVE": "1"}
        env.update(overrides)
        return env

    def test_blocked_when_pat_missing(self):
        lane = GitHubSmokeLane(
            "owner", "repo",
            environ=self._base_env(),
        )
        result = lane.run()
        self.assertEqual(result.status, SmokeLaneStatus.BLOCKED)
        self.assertIn("PROJECT_GITHUB_PAT", result.evidence)
        self.assertNotIn("ghp_", result.evidence)
        self.assertNotIn("github_pat_", result.evidence)

    def test_blocked_when_git_credentials_exists(self):
        env = self._base_env(PROJECT_GITHUB_PAT="ghp_" + "a" * 36)
        with patch("src.developer_assistant.github_workflow.os.path.exists", return_value=True):
            lane = GitHubSmokeLane("owner", "repo", environ=env)
            result = lane.run()
            self.assertEqual(result.status, SmokeLaneStatus.BLOCKED)

    def test_blocked_when_github_token_collision(self):
        env = self._base_env(GITHUB_TOKEN="ghs_" + "b" * 36)
        lane = GitHubSmokeLane("owner", "repo", environ=env)
        result = lane.run()
        self.assertEqual(result.status, SmokeLaneStatus.BLOCKED)
        self.assertNotIn("ghs_", result.evidence)


class TestGitHubSmokeLanePass(unittest.TestCase):
    def _pass_env(self, **overrides):
        env = {
            "SMOKE_GITHUB_LIVE": "1",
            "PROJECT_GITHUB_PAT": "ghp_" + "a" * 36,
        }
        env.update(overrides)
        return env

    def test_pass_with_mocked_executors(self):
        rest_mock = MagicMock()
        rest_mock.execute.side_effect = [
            {"full_name": "owner/repo", "private": True},
            {"number": 99, "html_url": "https://github.com/owner/repo/pull/99"},
            {"total_count": 1, "check_runs": [{"conclusion": "success"}]},
            {"state": "open", "mergeable": True},
        ]
        git_mock = MagicMock()
        git_mock.execute.return_value = 0

        lane = GitHubSmokeLane(
            "owner", "repo",
            rest_executor=rest_mock,
            git_executor=git_mock,
            environ=self._pass_env(),
        )
        result = lane.run()
        self.assertEqual(result.status, SmokeLaneStatus.PASS)
        self.assertIn("repo:", result.evidence)
        self.assertIn("branch:", result.evidence)
        self.assertIn("pr:", result.evidence)
        self.assertIn("checks:", result.evidence)
        self.assertIn("cleanup:", result.evidence)
        self.assertIn("PROJECT_GITHUB_PAT", result.evidence)
        self.assertNotIn("ghp_", result.evidence)

    def test_pass_records_sanitized_pr_url(self):
        rest_mock = MagicMock()
        rest_mock.execute.side_effect = [
            {"full_name": "owner/repo"},
            {"number": 42},
            {"total_count": 0, "check_runs": []},
            {"state": "open", "mergeable": None},
        ]
        git_mock = MagicMock()
        git_mock.execute.return_value = 0

        lane = GitHubSmokeLane(
            "owner", "repo",
            rest_executor=rest_mock,
            git_executor=git_mock,
            environ=self._pass_env(),
        )
        result = lane.run()
        self.assertEqual(result.status, SmokeLaneStatus.PASS)
        self.assertIn("pull/42", result.evidence)

    def test_blocked_on_pr_open_failure(self):
        from src.developer_assistant.runtime_executors import RuntimeRESTError

        rest_mock = MagicMock()
        rest_mock.execute.side_effect = [
            {"full_name": "owner/repo"},
            RuntimeRESTError("HTTP 422 for https://api.github.com/repos/owner/repo/pulls: ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"),
        ]
        git_mock = MagicMock()
        git_mock.execute.return_value = 0

        lane = GitHubSmokeLane(
            "owner", "repo",
            rest_executor=rest_mock,
            git_executor=git_mock,
            environ=self._pass_env(),
        )
        result = lane.run()
        self.assertEqual(result.status, SmokeLaneStatus.BLOCKED)
        self.assertNotIn("ghp_", result.evidence)
        self.assertNotIn("ghp_", result.blocker)
        self.assertIn("PR open failed", result.evidence)

    def test_fail_on_branch_creation_error(self):
        from src.developer_assistant.runtime_executors import RuntimeGitError

        rest_mock = MagicMock()
        rest_mock.execute.return_value = {"full_name": "owner/repo"}
        git_mock = MagicMock()
        git_mock.execute.side_effect = RuntimeGitError("git checkout failed with ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")

        lane = GitHubSmokeLane(
            "owner", "repo",
            rest_executor=rest_mock,
            git_executor=git_mock,
            environ=self._pass_env(),
        )
        result = lane.run()
        self.assertEqual(result.status, SmokeLaneStatus.FAIL)
        self.assertNotIn("ghp_", result.evidence)
        self.assertNotIn("ghp_", result.blocker)

    def test_blocked_on_repo_register_failure(self):
        from src.developer_assistant.runtime_executors import RuntimeRESTError

        rest_mock = MagicMock()
        rest_mock.execute.side_effect = RuntimeRESTError(
            "HTTP 403 for https://api.github.com/repos/owner/repo: token ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        )

        lane = GitHubSmokeLane(
            "owner", "repo",
            rest_executor=rest_mock,
            environ=self._pass_env(),
        )
        result = lane.run()
        self.assertEqual(result.status, SmokeLaneStatus.BLOCKED)
        self.assertNotIn("ghp_", result.evidence)
        self.assertNotIn("ghp_", result.blocker)

    def test_no_autonomous_merge_in_evidence(self):
        rest_mock = MagicMock()
        rest_mock.execute.side_effect = [
            {"full_name": "owner/repo"},
            {"number": 1},
            {"total_count": 0, "check_runs": []},
            {"state": "open", "mergeable": True},
        ]
        git_mock = MagicMock()
        git_mock.execute.return_value = 0

        lane = GitHubSmokeLane(
            "owner", "repo",
            rest_executor=rest_mock,
            git_executor=git_mock,
            environ=self._pass_env(),
        )
        result = lane.run()
        self.assertIn("no_autonomous_merge: true", result.evidence)
        self.assertIn("founder_ack_required_before_merge: true", result.evidence)


class TestTelegramSmokeLaneSkipped(unittest.TestCase):
    def test_skipped_when_gate_not_set(self):
        lane = TelegramSmokeLane(environ={})
        result = lane.run()
        self.assertEqual(result.status, SmokeLaneStatus.SKIPPED)
        self.assertIn("not set", result.evidence)
        self.assertEqual(result.lane, "telegram")


class TestTelegramSmokeLaneBlocked(unittest.TestCase):
    def _base_env(self, **overrides):
        env = {"SMOKE_TELEGRAM_LIVE": "1"}
        env.update(overrides)
        return env

    def test_blocked_when_bot_token_missing(self):
        lane = TelegramSmokeLane(environ=self._base_env())
        result = lane.run()
        self.assertEqual(result.status, SmokeLaneStatus.BLOCKED)
        self.assertIn("TELEGRAM_BOT_TOKEN", result.evidence)
        self.assertIn("NOT configured", result.evidence)

    def test_blocked_when_allow_all_enabled(self):
        env = self._base_env(
            TELEGRAM_BOT_TOKEN="redacted-token-value",
            GATEWAY_ALLOW_ALL_USERS="true",
            TELEGRAM_ALLOWED_USERS="user:founder",
        )
        lane = TelegramSmokeLane(environ=env)
        result = lane.run()
        self.assertEqual(result.status, SmokeLaneStatus.BLOCKED)
        self.assertIn("violation", result.evidence.lower())

    def test_blocked_when_telegram_allow_all_enabled(self):
        env = self._base_env(
            TELEGRAM_BOT_TOKEN="redacted-token-value",
            TELEGRAM_ALLOW_ALL_USERS="true",
            TELEGRAM_ALLOWED_USERS="user:founder",
        )
        lane = TelegramSmokeLane(environ=env)
        result = lane.run()
        self.assertEqual(result.status, SmokeLaneStatus.BLOCKED)

    def test_blocked_when_no_allowlist_or_dm_pairing(self):
        env = self._base_env(
            TELEGRAM_BOT_TOKEN="redacted-token-value",
        )
        lane = TelegramSmokeLane(environ=env)
        result = lane.run()
        self.assertIn("BLOCKED", result.status.value.upper())

    def test_blocked_evidence_no_raw_ids(self):
        lane = TelegramSmokeLane(environ=self._base_env())
        result = lane.run()
        import re
        raw_id_pattern = re.compile(r"\b\d{5,}\b")
        self.assertIsNone(raw_id_pattern.search(result.evidence))


class TestTelegramSmokeLanePass(unittest.TestCase):
    def _pass_env(self, **overrides):
        env = {
            "SMOKE_TELEGRAM_LIVE": "1",
            "TELEGRAM_BOT_TOKEN": "redacted-bot-token",
            "TELEGRAM_ALLOWED_USERS": "user:founder",
        }
        env.update(overrides)
        return env

    @staticmethod
    def _successful_proof():
        def _proof(payload):
            assert isinstance(payload, dict)
            return {"success": True, "evidence": "live gateway proof OK"}
        return _proof

    def test_pass_with_minimal_config(self):
        lane = TelegramSmokeLane(
            environ=self._pass_env(),
            live_gateway_proof=self._successful_proof(),
        )
        result = lane.run()
        self.assertEqual(result.status, SmokeLaneStatus.PASS)
        self.assertIn("chat:founder", result.evidence)
        self.assertIn("user:founder", result.evidence)
        self.assertIn("/status", result.evidence)

    def test_pass_evidence_no_raw_ids(self):
        lane = TelegramSmokeLane(
            environ=self._pass_env(),
            live_gateway_proof=self._successful_proof(),
        )
        result = lane.run()
        import re
        raw_id_pattern = re.compile(r"\b\d{5,}\b")
        self.assertIsNone(raw_id_pattern.search(result.evidence))

    def test_pass_evidence_no_token_values(self):
        lane = TelegramSmokeLane(
            environ=self._pass_env(),
            live_gateway_proof=self._successful_proof(),
        )
        result = lane.run()
        self.assertNotIn("redacted-bot-token", result.evidence)
        self.assertNotIn("123456:", result.evidence)

    def test_pass_mentions_commands(self):
        lane = TelegramSmokeLane(
            environ=self._pass_env(),
            live_gateway_proof=self._successful_proof(),
        )
        result = lane.run()
        for cmd in ["/status", "/decisions", "/pause", "/resume", "/new_project"]:
            self.assertIn(cmd, result.evidence)

    def test_pass_mentions_classification_paths(self):
        lane = TelegramSmokeLane(
            environ=self._pass_env(),
            live_gateway_proof=self._successful_proof(),
        )
        result = lane.run()
        for cat in ["intake", "answer", "clarification", "approval", "rejection", "general_question"]:
            self.assertIn(cat, result.evidence)

    def test_pass_polling_preferred(self):
        lane = TelegramSmokeLane(
            environ=self._pass_env(),
            live_gateway_proof=self._successful_proof(),
        )
        result = lane.run()
        self.assertIn("polling", result.evidence)

    def test_pass_allow_all_disabled(self):
        lane = TelegramSmokeLane(
            environ=self._pass_env(),
            live_gateway_proof=self._successful_proof(),
        )
        result = lane.run()
        self.assertIn("disabled", result.evidence)


class TestTelegramSmokeLaneWebhook(unittest.TestCase):
    def _webhook_env(self, **overrides):
        env = {
            "SMOKE_TELEGRAM_LIVE": "1",
            "TELEGRAM_BOT_TOKEN": "redacted-bot-token",
            "TELEGRAM_ALLOWED_USERS": "user:founder",
            "TELEGRAM_WEBHOOK_MODE": "true",
            "TELEGRAM_WEBHOOK_SECRET": "redacted-secret",
        }
        env.update(overrides)
        return env

    def test_webhook_mode_with_secret_passes(self):
        lane = TelegramSmokeLane(environ=self._webhook_env())
        result = lane.run()
        self.assertIn("webhook", result.evidence)

    def test_webhook_mode_without_secret_blocked(self):
        env = self._webhook_env(TELEGRAM_WEBHOOK_SECRET="")
        lane = TelegramSmokeLane(environ=env)
        result = lane.run()
        self.assertEqual(result.status, SmokeLaneStatus.BLOCKED)


class TestGitHubBranchUniqueness(unittest.TestCase):
    def test_different_instances_generate_different_branches(self):
        lane_a = GitHubSmokeLane("owner", "repo")
        lane_b = GitHubSmokeLane("owner", "repo")
        self.assertNotEqual(lane_a._branch_suffix, lane_b._branch_suffix)

    def test_branch_suffix_injectable(self):
        lane = GitHubSmokeLane("owner", "repo", branch_suffix="ff00ff00")
        self.assertEqual(lane._branch_suffix, "ff00ff00")

    def test_branch_name_includes_injected_suffix(self):
        from src.developer_assistant.smoke_readiness import _sanitize_branch_name
        name = _sanitize_branch_name("TKT-017", suffix="a1b2c3d4")
        self.assertTrue(name.startswith("smoke/tkt-017-live-check-"))
        self.assertEqual(name, "smoke/tkt-017-live-check-a1b2c3d4")

    def test_branch_name_prefix_clear_for_cleanup(self):
        from src.developer_assistant.smoke_readiness import _sanitize_branch_name
        name = _sanitize_branch_name("TKT-017", suffix="abcdef12")
        self.assertTrue(name.startswith("smoke/tkt-017-"))

    def test_branch_suffix_no_secret_in_branch_name(self):
        from src.developer_assistant.smoke_readiness import _sanitize_branch_name, _generate_branch_suffix
        suffix = _generate_branch_suffix()
        self.assertIsInstance(suffix, str)
        self.assertGreater(len(suffix), 0)
        name = _sanitize_branch_name("TKT-017", suffix=suffix)
        self.assertNotIn("ghp_", name)
        self.assertNotIn("token", name)
        self.assertNotIn("pat", name)
        self.assertNotIn("@", name)
        self.assertNotIn(":", name)


class TestTelegramLiveGatewayProof(unittest.TestCase):
    def _live_env(self, **overrides):
        env = {
            "SMOKE_TELEGRAM_LIVE": "1",
            "TELEGRAM_BOT_TOKEN": "redacted-bot-token",
            "TELEGRAM_ALLOWED_USERS": "user:founder",
        }
        env.update(overrides)
        return env

    def test_config_only_without_proof_returns_blocked(self):
        lane = TelegramSmokeLane(environ=self._live_env())
        result = lane.run()
        self.assertEqual(result.status, SmokeLaneStatus.BLOCKED)
        self.assertIn("live_gateway_proof: not provided", result.evidence)

    def test_live_proof_success_returns_pass(self):
        def _success_proof(payload):
            self.assertIn("commands", payload)
            self.assertIn("chat_label", payload)
            self.assertNotIn("token", str(payload).lower())
            self.assertNotIn("ghp_", str(payload))
            return {"success": True, "evidence": "gateway ok"}
        lane = TelegramSmokeLane(
            environ=self._live_env(),
            live_gateway_proof=_success_proof,
        )
        result = lane.run()
        self.assertEqual(result.status, SmokeLaneStatus.PASS)
        self.assertIn("live_gateway_proof: gateway ok", result.evidence)

    def test_live_proof_failure_returns_blocked(self):
        def _fail_proof(payload):
            return {"success": False, "error": "Gateway timeout"}
        lane = TelegramSmokeLane(
            environ=self._live_env(),
            live_gateway_proof=_fail_proof,
        )
        result = lane.run()
        self.assertEqual(result.status, SmokeLaneStatus.BLOCKED)
        self.assertIn("live_gateway_proof: failed", result.evidence)
        self.assertIn("Gateway timeout", result.blocker)

    def test_live_proof_exception_returns_fail(self):
        def _exc_proof(payload):
            raise ConnectionError("Connection refused at 127.0.0.1:8080")
        lane = TelegramSmokeLane(
            environ=self._live_env(),
            live_gateway_proof=_exc_proof,
        )
        result = lane.run()
        self.assertEqual(result.status, SmokeLaneStatus.FAIL)
        self.assertIn("Connection refused at 127.0.0.1:8080", result.evidence)

    def test_live_proof_failure_no_secret_leak(self):
        def _fail_proof(payload):
            return {"success": False, "error": "Failed with ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}
        lane = TelegramSmokeLane(
            environ=self._live_env(),
            live_gateway_proof=_fail_proof,
        )
        result = lane.run()
        self.assertNotIn("ghp_", result.evidence)
        self.assertNotIn("ghp_", result.blocker)

    def test_live_proof_exception_no_secret_leak(self):
        def _exc_proof(payload):
            raise RuntimeError("Token was ghp_" + "A" * 36)
        lane = TelegramSmokeLane(
            environ=self._live_env(),
            live_gateway_proof=_exc_proof,
        )
        result = lane.run()
        self.assertNotIn("ghp_", result.evidence)
        self.assertNotIn("ghp_", result.blocker)

    def test_live_proof_receives_only_sanitized_input(self):
        received = []

        def _capture_proof(payload):
            received.append(payload)
            return {"success": True, "evidence": "ok"}

        lane = TelegramSmokeLane(
            environ=self._live_env(),
            live_gateway_proof=_capture_proof,
        )
        lane.run()
        self.assertEqual(len(received), 1)
        payload = received[0]
        self.assertIsInstance(payload, dict)
        self.assertNotIn("redacted-bot-token", str(payload))
        self.assertNotIn("user:founder", payload.get("chat_label", ""))
        self.assertIn("chat:founder", payload.get("chat_label", ""))
        self.assertNotIn("ghp_", str(payload))


class TestSmokeReadinessReport(unittest.TestCase):
    def test_to_sanitized_dict_structure(self):
        report = SmokeReadinessReport(
            github=SmokeLaneResult(
                lane="github",
                status=SmokeLaneStatus.SKIPPED,
                evidence="gate not set",
            ),
            telegram=SmokeLaneResult(
                lane="telegram",
                status=SmokeLaneStatus.SKIPPED,
                evidence="gate not set",
            ),
        )
        d = report.to_sanitized_dict()
        self.assertIn("github_lane", d)
        self.assertIn("telegram_lane", d)
        self.assertTrue(d["tkt_011_remains_draft"])
        self.assertTrue(d["founder_ack_required_before_merge"])
        self.assertTrue(d["no_autonomous_merge"])

    def test_blocked_report_has_blocker(self):
        report = SmokeReadinessReport(
            github=SmokeLaneResult(
                lane="github",
                status=SmokeLaneStatus.BLOCKED,
                blocker="PROJECT_GITHUB_PAT not available",
            ),
            telegram=SmokeLaneResult(
                lane="telegram",
                status=SmokeLaneStatus.BLOCKED,
                blocker="TELEGRAM_BOT_TOKEN not configured",
            ),
        )
        d = report.to_sanitized_dict()
        self.assertEqual(d["github_lane"]["status"], "blocked")
        self.assertEqual(d["telegram_lane"]["status"], "blocked")
        self.assertIn("PROJECT_GITHUB_PAT", d["github_lane"]["blocker"])
        self.assertIn("TELEGRAM_BOT_TOKEN", d["telegram_lane"]["blocker"])


class TestRunSmokeReadiness(unittest.TestCase):
    def test_both_skipped_by_default(self):
        report = run_smoke_readiness(environ={})
        self.assertEqual(report.github.status, SmokeLaneStatus.SKIPPED)
        self.assertEqual(report.telegram.status, SmokeLaneStatus.SKIPPED)
        self.assertTrue(report.tkt_011_remains_draft)
        self.assertTrue(report.founder_ack_required)

    def test_github_blocked_pat_missing(self):
        env = {"SMOKE_GITHUB_LIVE": "1"}
        report = run_smoke_readiness(environ=env)
        self.assertEqual(report.github.status, SmokeLaneStatus.BLOCKED)

    def test_telegram_blocked_no_token(self):
        env = {"SMOKE_TELEGRAM_LIVE": "1"}
        report = run_smoke_readiness(environ=env)
        self.assertEqual(report.telegram.status, SmokeLaneStatus.BLOCKED)


class TestNoSecretLeakage(unittest.TestCase):
    """Verify that no test or result contains token patterns."""

    _TOKEN_PATTERN = __import__("re").compile(
        r"ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,}[A-Za-z0-9]|gho_[A-Za-z0-9]{36}|ghu_[A-Za-z0-9]{36}|ghs_[A-Za-z0-9]{36}|ghr_[A-Za-z0-9]{36}"
    )

    def test_github_blocked_no_token_leak(self):
        lane = GitHubSmokeLane("owner", "repo", environ={"SMOKE_GITHUB_LIVE": "1"})
        result = lane.run()
        self.assertIsNone(self._TOKEN_PATTERN.search(result.evidence))
        self.assertIsNone(self._TOKEN_PATTERN.search(result.blocker))

    def test_telegram_blocked_no_token_leak(self):
        lane = TelegramSmokeLane(environ={"SMOKE_TELEGRAM_LIVE": "1"})
        result = lane.run()
        self.assertIsNone(self._TOKEN_PATTERN.search(result.evidence))
        self.assertIsNone(self._TOKEN_PATTERN.search(result.blocker))

    def test_github_mocked_pass_no_token_leak(self):
        rest_mock = MagicMock()
        rest_mock.execute.side_effect = [
            {"full_name": "owner/repo"},
            {"number": 1},
            {"total_count": 0, "check_runs": []},
            {"state": "open", "mergeable": True},
        ]
        git_mock = MagicMock()
        git_mock.execute.return_value = 0
        env = {
            "SMOKE_GITHUB_LIVE": "1",
            "PROJECT_GITHUB_PAT": "ghp_" + "a" * 36,
        }
        lane = GitHubSmokeLane(
            "owner", "repo",
            rest_executor=rest_mock,
            git_executor=git_mock,
            environ=env,
        )
        result = lane.run()
        self.assertIsNone(self._TOKEN_PATTERN.search(result.evidence))
        self.assertIsNone(self._TOKEN_PATTERN.search(result.blocker))

    def test_telegram_pass_no_token_leak(self):
        env = {
            "SMOKE_TELEGRAM_LIVE": "1",
            "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "TELEGRAM_ALLOWED_USERS": "user:founder",
        }
        lane = TelegramSmokeLane(environ=env)
        result = lane.run()
        self.assertNotIn("123456:ABC-DEF", result.evidence)
        self.assertNotIn("123456:ABC-DEF", result.blocker)


if __name__ == "__main__":
    unittest.main()
