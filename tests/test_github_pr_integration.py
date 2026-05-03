"""Unit tests for github_pr_integration module (TKT-008).

Covers:
- Credential use through load_credential(); GITHUB_TOKEN/GH_TOKEN not accepted
- Repository create/register request construction through integration path
- Branch creation and PR open linked to one ticket
- Check-status read / PR metadata read through integration path
- Reviewer artifact reference validation or attachment semantics
- Founder acknowledgement merge gate through integration path
- Telegram status/progress composition containing repo, PR, CI/check, ticket,
  and review-gate state
- Secret hygiene: no token values in URLs, command lines, errors, progress
  text, or test fixtures
"""

import unittest
from typing import Any, Dict

from src.developer_assistant.github_pr_integration import (
    GitHubPRIntegration,
    IntegrationError,
    MergeGateError,
    PRCheckState,
    ProjectGitHubState,
    ReviewGateState,
    compose_github_aware_progress_report,
)
from src.developer_assistant.github_workflow import (
    CredentialSourceError,
    GitHubRESTRequest,
    GitCommand,
    MergeBlockedError,
    redact_token,
)


_FAKE_TOKEN = "FAKE_TEST_TOKEN_NOT_REAL_1234567890"
_FAKE_PAT = "FAKE_PAT_NOT_REAL_AAA111222333444555666777888999000"


class _RecordingRESTExecutor:
    """REST executor that records requests and returns configured responses."""

    def __init__(self, responses: Dict[str, Any] = None) -> None:
        self.requests: list[GitHubRESTRequest] = []
        self.tokens_seen: list[str] = []
        self._responses = responses or {}

    def execute(self, request: GitHubRESTRequest, token: str) -> Dict[str, Any]:
        self.requests.append(request)
        self.tokens_seen.append(token)
        key = f"{request.method} {request.url}"
        return self._responses.get(key, {})


class _FailingRESTExecutor:
    """REST executor that always raises."""

    def execute(self, request: GitHubRESTRequest, token: str) -> Dict[str, Any]:
        raise RuntimeError("REST call failed")


class _RecordingGitExecutor:
    """Git executor that records commands and returns configured exit codes."""

    def __init__(self, exit_code: int = 0) -> None:
        self.commands: list[GitCommand] = []
        self._exit_code = exit_code

    def execute(self, cmd: GitCommand) -> int:
        self.commands.append(cmd)
        return self._exit_code


class _FailingGitExecutor:
    """Git executor that always raises."""

    def execute(self, cmd: GitCommand) -> int:
        raise RuntimeError("git command failed")


def _make_env(pat: str = _FAKE_PAT, github_token: str = "", gh_token: str = "") -> Dict[str, str]:
    env: Dict[str, str] = {}
    if pat:
        env["PROJECT_GITHUB_PAT"] = pat
    if github_token:
        env["GITHUB_TOKEN"] = github_token
    if gh_token:
        env["GH_TOKEN"] = gh_token
    return env


_REPO_CREATE_RESPONSE = {
    "POST https://api.github.com/orgs/testowner/repos": {
        "html_url": "https://github.com/testowner/testrepo",
        "full_name": "testowner/testrepo",
    },
}

_REPO_REGISTER_RESPONSE = {
    "GET https://api.github.com/repos/testowner/testrepo": {
        "html_url": "https://github.com/testowner/testrepo",
        "full_name": "testowner/testrepo",
    },
}

_PR_OPEN_RESPONSE = {
    "POST https://api.github.com/repos/testowner/testrepo/pulls": {
        "number": 42,
        "html_url": "https://github.com/testowner/testrepo/pull/42",
        "state": "open",
    },
}

_CHECK_STATUS_RESPONSE = {
    "GET https://api.github.com/repos/testowner/testrepo/commits/abc123/check-runs": {
        "check_runs": [
            {
                "name": "validate-docs",
                "status": "completed",
                "conclusion": "success",
            },
            {
                "name": "PR-Agent",
                "status": "completed",
                "conclusion": "success",
            },
        ],
    },
}

_PR_METADATA_RESPONSE = {
    "GET https://api.github.com/repos/testowner/testrepo/pulls/42": {
        "number": 42,
        "state": "open",
        "title": "Test PR",
        "html_url": "https://github.com/testowner/testrepo/pull/42",
    },
}


class TestCredentialUseThroughIntegration(unittest.TestCase):
    """Credential use through load_credential() and GITHUB_TOKEN/GH_TOKEN not accepted."""

    def test_load_credential_uses_project_github_pat(self):
        env = _make_env(pat=_FAKE_PAT)
        rest = _RecordingRESTExecutor(_REPO_REGISTER_RESPONSE)
        integ = GitHubPRIntegration(rest_executor=rest, _environ=env)
        state = integ.register_repository("proj:1", "testowner", "testrepo")
        self.assertEqual(state.repo_owner, "testowner")

    def test_github_token_alone_is_rejected(self):
        env = _make_env(pat="", github_token=_FAKE_TOKEN)
        integ = GitHubPRIntegration(_environ=env)
        with self.assertRaises(CredentialSourceError):
            integ.register_repository("proj:1", "testowner", "testrepo")

    def test_gh_token_alone_is_rejected(self):
        env = _make_env(pat="", gh_token=_FAKE_TOKEN)
        integ = GitHubPRIntegration(_environ=env)
        with self.assertRaises(CredentialSourceError):
            integ.register_repository("proj:1", "testowner", "testrepo")

    def test_github_token_not_used_as_fallback_when_pat_present(self):
        env = _make_env(pat=_FAKE_PAT, github_token=_FAKE_TOKEN)
        rest = _RecordingRESTExecutor(_REPO_REGISTER_RESPONSE)
        integ = GitHubPRIntegration(rest_executor=rest, _environ=env)
        state = integ.register_repository("proj:1", "testowner", "testrepo")
        self.assertEqual(rest.tokens_seen[0], _FAKE_PAT)
        self.assertNotEqual(rest.tokens_seen[0], _FAKE_TOKEN)

    def test_missing_pat_raises_even_if_github_token_present(self):
        env = _make_env(pat="", github_token=_FAKE_TOKEN)
        integ = GitHubPRIntegration(_environ=env)
        with self.assertRaises(CredentialSourceError):
            integ.register_repository("proj:1", "testowner", "testrepo")

    def test_no_credential_env_raises(self):
        env: Dict[str, str] = {}
        integ = GitHubPRIntegration(_environ=env)
        with self.assertRaises(CredentialSourceError):
            integ.register_repository("proj:1", "testowner", "testrepo")


class TestRepositoryCreateRegister(unittest.TestCase):
    """Repository create/register request construction through integration path."""

    def test_register_existing_repository(self):
        rest = _RecordingRESTExecutor(_REPO_REGISTER_RESPONSE)
        integ = GitHubPRIntegration(rest_executor=rest, _environ=_make_env())
        state = integ.register_repository("proj:1", "testowner", "testrepo")
        self.assertEqual(state.repo_owner, "testowner")
        self.assertEqual(state.repo_name, "testrepo")
        self.assertEqual(len(rest.requests), 1)
        req = rest.requests[0]
        self.assertEqual(req.method, "GET")

    def test_create_new_repository(self):
        rest = _RecordingRESTExecutor(_REPO_CREATE_RESPONSE)
        integ = GitHubPRIntegration(rest_executor=rest, _environ=_make_env())
        state = integ.register_repository(
            "proj:1", "testowner", "testrepo", create=True, private=True
        )
        self.assertEqual(state.repo_owner, "testowner")
        self.assertEqual(state.repo_name, "testrepo")
        req = rest.requests[0]
        self.assertEqual(req.method, "POST")
        self.assertIsNotNone(req.body)

    def test_create_repo_default_private(self):
        rest = _RecordingRESTExecutor(_REPO_CREATE_RESPONSE)
        integ = GitHubPRIntegration(rest_executor=rest, _environ=_make_env())
        integ.register_repository("proj:1", "testowner", "testrepo", create=True)
        req = rest.requests[0]
        self.assertTrue(req.body.get("private", False))

    def test_create_repo_public(self):
        rest = _RecordingRESTExecutor(_REPO_CREATE_RESPONSE)
        integ = GitHubPRIntegration(rest_executor=rest, _environ=_make_env())
        integ.register_repository(
            "proj:1", "testowner", "testrepo", create=True, private=False
        )
        req = rest.requests[0]
        self.assertFalse(req.body.get("private", True))

    def test_register_failure_raises_integration_error(self):
        rest = _FailingRESTExecutor()
        integ = GitHubPRIntegration(rest_executor=rest, _environ=_make_env())
        with self.assertRaises(IntegrationError):
            integ.register_repository("proj:1", "testowner", "testrepo")

    def test_repo_url_is_redacted(self):
        responses = {
            "GET https://api.github.com/repos/testowner/testrepo": {
                "html_url": "https://ghp_1234567890abcdefghijklmnop@github.com/testowner/testrepo",
            },
        }
        rest = _RecordingRESTExecutor(responses)
        integ = GitHubPRIntegration(rest_executor=rest, _environ=_make_env())
        state = integ.register_repository("proj:1", "testowner", "testrepo")
        self.assertNotIn("ghp_", state.repo_url)
        self.assertIn("***REDACTED***", state.repo_url)

    def test_project_state_persists_after_register(self):
        rest = _RecordingRESTExecutor(_REPO_REGISTER_RESPONSE)
        integ = GitHubPRIntegration(rest_executor=rest, _environ=_make_env())
        integ.register_repository("proj:1", "testowner", "testrepo")
        state = integ.get_project_state("proj:1")
        self.assertEqual(state.repo_full_name, "testowner/testrepo")


class TestBranchCreateAndPROpen(unittest.TestCase):
    """Branch creation and PR open linked to one ticket."""

    def _setup_registered(self) -> tuple[GitHubPRIntegration, _RecordingRESTExecutor, _RecordingGitExecutor]:
        rest = _RecordingRESTExecutor({**_REPO_REGISTER_RESPONSE, **_PR_OPEN_RESPONSE})
        git = _RecordingGitExecutor()
        integ = GitHubPRIntegration(
            rest_executor=rest, git_executor=git, _environ=_make_env()
        )
        integ.register_repository("proj:1", "testowner", "testrepo")
        rest.requests.clear()
        return integ, rest, git

    def test_create_branch_and_open_pr(self):
        integ, rest, git = self._setup_registered()
        state = integ.create_branch_and_open_pr(
            "proj:1", "TKT-008", "tkt-008/feature",
            pr_title="Implement feature",
        )
        self.assertEqual(state.active_branch, "tkt-008/feature")
        self.assertEqual(state.active_pr_number, 42)
        self.assertEqual(state.active_pr_state, "open")
        self.assertEqual(state.linked_ticket, "TKT-008")
        self.assertFalse(state.founder_acknowledged)

    def test_pr_body_includes_ticket_link(self):
        integ, rest, git = self._setup_registered()
        integ.create_branch_and_open_pr(
            "proj:1", "TKT-008", "tkt-008/feature",
            pr_title="Feature", pr_body="Extra body text",
        )
        pr_req = [r for r in rest.requests if r.method == "POST"][0]
        body = pr_req.body or {}
        self.assertIn("TKT-008", body.get("body", ""))

    def test_pr_body_default_is_ticket_only(self):
        integ, rest, git = self._setup_registered()
        integ.create_branch_and_open_pr(
            "proj:1", "TKT-008", "tkt-008/feature",
            pr_title="Feature",
        )
        pr_req = [r for r in rest.requests if r.method == "POST"][0]
        body = pr_req.body or {}
        self.assertEqual(body.get("body"), "Linked ticket: TKT-008")

    def test_branch_create_command_constructed(self):
        integ, rest, git = self._setup_registered()
        integ.create_branch_and_open_pr(
            "proj:1", "TKT-008", "tkt-008/feature",
            pr_title="Feature", base="main",
        )
        self.assertTrue(len(git.commands) >= 1)
        branch_cmd = git.commands[0]
        self.assertIn("checkout", branch_cmd.args)
        self.assertIn("-b", branch_cmd.args)
        self.assertIn("tkt-008/feature", branch_cmd.args)

    def test_requires_registered_repo(self):
        git = _RecordingGitExecutor()
        integ = GitHubPRIntegration(git_executor=git, _environ=_make_env())
        with self.assertRaises(IntegrationError):
            integ.create_branch_and_open_pr(
                "proj:1", "TKT-008", "tkt-008/feature",
                pr_title="Feature",
            )

    def test_branch_create_failure_raises(self):
        rest = _RecordingRESTExecutor({**_REPO_REGISTER_RESPONSE, **_PR_OPEN_RESPONSE})
        git = _FailingGitExecutor()
        integ = GitHubPRIntegration(
            rest_executor=rest, git_executor=git, _environ=_make_env()
        )
        integ.register_repository("proj:1", "testowner", "testrepo")
        with self.assertRaises(IntegrationError):
            integ.create_branch_and_open_pr(
                "proj:1", "TKT-008", "tkt-008/feature",
                pr_title="Feature",
            )

    def test_branch_create_nonzero_exit_raises(self):
        rest = _RecordingRESTExecutor({**_REPO_REGISTER_RESPONSE, **_PR_OPEN_RESPONSE})
        git = _RecordingGitExecutor(exit_code=1)
        integ = GitHubPRIntegration(
            rest_executor=rest, git_executor=git, _environ=_make_env()
        )
        integ.register_repository("proj:1", "testowner", "testrepo")
        with self.assertRaises(IntegrationError):
            integ.create_branch_and_open_pr(
                "proj:1", "TKT-008", "tkt-008/feature",
                pr_title="Feature",
            )

    def test_pr_open_failure_raises(self):
        rest_ok = _RecordingRESTExecutor(_REPO_REGISTER_RESPONSE)
        rest_fail = _FailingRESTExecutor()

        class _SwitchingRESTExecutor:
            def __init__(self):
                self.calls = 0
                self._ok = rest_ok
                self._fail = rest_fail

            def execute(self, request, token):
                self.calls += 1
                if self.calls <= 1:
                    return self._ok.execute(request, token)
                return self._fail.execute(request, token)

        git = _RecordingGitExecutor()
        integ = GitHubPRIntegration(
            rest_executor=_SwitchingRESTExecutor(), git_executor=git, _environ=_make_env()
        )
        integ.register_repository("proj:1", "testowner", "testrepo")
        with self.assertRaises(IntegrationError):
            integ.create_branch_and_open_pr(
                "proj:1", "TKT-008", "tkt-008/feature",
                pr_title="Feature",
            )


class TestCheckStatusRead(unittest.TestCase):
    """Check-status read / PR metadata read through integration path."""

    def _setup_registered(self) -> tuple[GitHubPRIntegration, _RecordingRESTExecutor]:
        rest = _RecordingRESTExecutor({
            **_REPO_REGISTER_RESPONSE,
            **_CHECK_STATUS_RESPONSE,
            **_PR_METADATA_RESPONSE,
        })
        integ = GitHubPRIntegration(rest_executor=rest, _environ=_make_env())
        integ.register_repository("proj:1", "testowner", "testrepo")
        rest.requests.clear()
        return integ, rest

    def test_read_check_status(self):
        integ, rest = self._setup_registered()
        check = integ.read_check_status("proj:1", "abc123")
        self.assertEqual(check.check_name, "validate-docs")
        self.assertEqual(check.status, "completed")
        self.assertEqual(check.conclusion, "success")

    def test_check_status_updates_project_state(self):
        integ, _ = self._setup_registered()
        integ.read_check_status("proj:1", "abc123")
        state = integ.get_project_state("proj:1")
        self.assertIsNotNone(state.check_state)
        self.assertEqual(state.check_state.conclusion, "success")

    def test_check_status_no_runs(self):
        responses = {
            **_REPO_REGISTER_RESPONSE,
            "GET https://api.github.com/repos/testowner/testrepo/commits/abc123/check-runs": {
                "check_runs": [],
            },
        }
        rest = _RecordingRESTExecutor(responses)
        integ = GitHubPRIntegration(rest_executor=rest, _environ=_make_env())
        integ.register_repository("proj:1", "testowner", "testrepo")
        check = integ.read_check_status("proj:1", "abc123")
        self.assertEqual(check.check_name, "")
        self.assertEqual(check.status, "")

    def test_read_pr_metadata(self):
        integ, rest = self._setup_registered()
        meta = integ.read_pr_metadata("proj:1", 42)
        self.assertEqual(meta.get("number"), 42)
        self.assertEqual(meta.get("state"), "open")

    def test_pr_metadata_updates_state(self):
        integ, _ = self._setup_registered()
        integ.read_pr_metadata("proj:1", 42)
        state = integ.get_project_state("proj:1")
        self.assertEqual(state.active_pr_state, "open")

    def test_requires_registered_repo_for_check(self):
        integ = GitHubPRIntegration(_environ=_make_env())
        with self.assertRaises(IntegrationError):
            integ.read_check_status("proj:1", "abc123")

    def test_requires_registered_repo_for_pr_metadata(self):
        integ = GitHubPRIntegration(_environ=_make_env())
        with self.assertRaises(IntegrationError):
            integ.read_pr_metadata("proj:1", 42)


class TestReviewArtifactAttachment(unittest.TestCase):
    """Reviewer artifact reference validation or attachment semantics."""

    def test_attach_valid_review_artifact(self):
        integ = GitHubPRIntegration(_environ=_make_env())
        gate = integ.attach_review_artifact(
            "proj:1", "docs/reviews/RV-CODE-019.md",
            verdict="pass", reviewer="kimi-k2.6", date="2026-05-04",
        )
        self.assertEqual(gate.review_artifact_path, "docs/reviews/RV-CODE-019.md")
        self.assertEqual(gate.verdict, "pass")
        self.assertTrue(gate.is_valid_artifact_path())

    def test_attach_review_updates_project_state(self):
        integ = GitHubPRIntegration(_environ=_make_env())
        integ.attach_review_artifact(
            "proj:1", "docs/reviews/RV-CODE-019.md", verdict="pass",
        )
        state = integ.get_project_state("proj:1")
        self.assertIsNotNone(state.review_gate)
        self.assertEqual(state.review_gate.verdict, "pass")

    def test_reject_invalid_artifact_path_not_in_docs_reviews(self):
        integ = GitHubPRIntegration(_environ=_make_env())
        with self.assertRaises(IntegrationError):
            integ.attach_review_artifact("proj:1", "src/reviews/RV-CODE-019.md")

    def test_reject_invalid_artifact_path_no_md_extension(self):
        integ = GitHubPRIntegration(_environ=_make_env())
        with self.assertRaises(IntegrationError):
            integ.attach_review_artifact("proj:1", "docs/reviews/RV-CODE-019.txt")

    def test_reject_empty_artifact_path(self):
        integ = GitHubPRIntegration(_environ=_make_env())
        with self.assertRaises(IntegrationError):
            integ.attach_review_artifact("proj:1", "")

    def test_review_gate_status_text_with_verdict(self):
        gate = ReviewGateState(
            review_artifact_path="docs/reviews/RV-CODE-019.md",
            verdict="pass",
        )
        self.assertIn("pass", gate.to_status_text())
        self.assertIn("RV-CODE-019", gate.to_status_text())

    def test_review_gate_status_text_no_review(self):
        gate = ReviewGateState()
        self.assertEqual(gate.to_status_text(), "no review")

    def test_review_gate_status_text_pending_verdict(self):
        gate = ReviewGateState(
            review_artifact_path="docs/reviews/RV-CODE-020.md",
        )
        self.assertIn("pending", gate.to_status_text())

    def test_is_valid_artifact_path_accepts_correct_format(self):
        gate = ReviewGateState(review_artifact_path="docs/reviews/RV-CODE-019.md")
        self.assertTrue(gate.is_valid_artifact_path())

    def test_is_valid_artifact_path_rejects_wrong_prefix(self):
        gate = ReviewGateState(review_artifact_path="other/reviews/RV-CODE-019.md")
        self.assertFalse(gate.is_valid_artifact_path())

    def test_is_valid_artifact_path_rejects_wrong_suffix(self):
        gate = ReviewGateState(review_artifact_path="docs/reviews/RV-CODE-019.py")
        self.assertFalse(gate.is_valid_artifact_path())

    def test_does_not_write_review_body(self):
        integ = GitHubPRIntegration(_environ=_make_env())
        gate = integ.attach_review_artifact(
            "proj:1", "docs/reviews/RV-CODE-019.md", verdict="pass",
        )
        self.assertFalse(hasattr(gate, "body"))
        self.assertFalse(hasattr(gate, "content"))


class TestFounderAcknowledgementMergeGate(unittest.TestCase):
    """Founder acknowledgement merge gate through integration path."""

    def _setup_with_branch(self) -> GitHubPRIntegration:
        rest = _RecordingRESTExecutor({**_REPO_REGISTER_RESPONSE, **_PR_OPEN_RESPONSE})
        git = _RecordingGitExecutor()
        integ = GitHubPRIntegration(
            rest_executor=rest, git_executor=git, _environ=_make_env()
        )
        integ.register_repository("proj:1", "testowner", "testrepo")
        integ.create_branch_and_open_pr(
            "proj:1", "TKT-008", "tkt-008/feature", pr_title="Feature",
        )
        return integ

    def test_merge_blocked_without_founder_acknowledgement(self):
        integ = self._setup_with_branch()
        with self.assertRaises(MergeGateError):
            integ.check_merge_gate("proj:1")

    def test_merge_blocked_error_mentions_founder(self):
        integ = self._setup_with_branch()
        try:
            integ.check_merge_gate("proj:1")
        except MergeGateError as e:
            self.assertIn("founder", str(e).lower())

    def test_merge_blocked_error_mentions_v01(self):
        integ = self._setup_with_branch()
        try:
            integ.check_merge_gate("proj:1")
        except MergeGateError as e:
            self.assertIn("v0.1", str(e))

    def test_merge_succeeds_with_founder_acknowledgement(self):
        integ = self._setup_with_branch()
        cmd = integ.check_merge_gate("proj:1", founder_acknowledgement=True)
        self.assertIsInstance(cmd, GitCommand)
        self.assertIn("merge", cmd.args)

    def test_founder_acknowledgement_updates_state(self):
        integ = self._setup_with_branch()
        integ.check_merge_gate("proj:1", founder_acknowledgement=True)
        state = integ.get_project_state("proj:1")
        self.assertTrue(state.founder_acknowledged)

    def test_no_active_branch_raises(self):
        integ = GitHubPRIntegration(_environ=_make_env())
        with self.assertRaises(IntegrationError):
            integ.check_merge_gate("proj:1", founder_acknowledgement=True)

    def test_double_gate_enforcement(self):
        """Integration layer gate fires even if underlying builder would also block."""
        integ = self._setup_with_branch()
        with self.assertRaises(MergeGateError):
            integ.check_merge_gate("proj:1", founder_acknowledgement=False)

    def test_merge_gate_does_not_allow_autonomous_merge(self):
        """Default (no acknowledgement) must always block."""
        integ = self._setup_with_branch()
        with self.assertRaises(MergeGateError):
            integ.check_merge_gate("proj:1")


class TestTelegramComposition(unittest.TestCase):
    """Telegram status/progress composition with repo, PR, CI, ticket, review-gate."""

    def _setup_full(self) -> GitHubPRIntegration:
        rest = _RecordingRESTExecutor({
            **_REPO_REGISTER_RESPONSE,
            **_PR_OPEN_RESPONSE,
            **_CHECK_STATUS_RESPONSE,
        })
        git = _RecordingGitExecutor()
        integ = GitHubPRIntegration(
            rest_executor=rest, git_executor=git, _environ=_make_env()
        )
        integ.register_repository("proj:1", "testowner", "testrepo")
        integ.create_branch_and_open_pr(
            "proj:1", "TKT-008", "tkt-008/feature", pr_title="Feature",
        )
        integ.read_check_status("proj:1", "abc123")
        integ.attach_review_artifact(
            "proj:1", "docs/reviews/RV-CODE-019.md",
            verdict="pass", reviewer="kimi-k2.6",
        )
        return integ

    def test_status_contains_repo(self):
        integ = self._setup_full()
        text = integ.compose_telegram_status("proj:1")
        self.assertIn("Репозиторий", text)
        self.assertIn("testowner/testrepo", text)

    def test_status_contains_pr(self):
        integ = self._setup_full()
        text = integ.compose_telegram_status("proj:1")
        self.assertIn("PR #42", text)

    def test_status_contains_ci(self):
        integ = self._setup_full()
        text = integ.compose_telegram_status("proj:1")
        self.assertIn("CI:", text)

    def test_status_contains_ticket(self):
        integ = self._setup_full()
        text = integ.compose_telegram_status("proj:1")
        self.assertIn("Тикет", text)
        self.assertIn("TKT-008", text)

    def test_status_contains_review_gate(self):
        integ = self._setup_full()
        text = integ.compose_telegram_status("proj:1")
        self.assertIn("Ревью", text)
        self.assertIn("pass", text)

    def test_status_contains_merge_gate(self):
        integ = self._setup_full()
        text = integ.compose_telegram_status("proj:1")
        self.assertIn("Мерж-гейт", text)
        self.assertIn("подтверждение основателя", text)

    def test_status_after_founder_ack_shows_confirmed(self):
        integ = self._setup_full()
        integ.check_merge_gate("proj:1", founder_acknowledgement=True)
        text = integ.compose_telegram_status("proj:1")
        self.assertIn("подтверждено основателем", text)

    def test_progress_contains_github_state(self):
        integ = self._setup_full()
        text = integ.compose_telegram_progress("proj:1")
        self.assertIn("testowner/testrepo", text)
        self.assertIn("PR #42", text)

    def test_empty_project_status(self):
        integ = GitHubPRIntegration(_environ=_make_env())
        text = integ.compose_telegram_status("proj:2")
        self.assertIn("Мерж-гейт", text)

    def test_compose_github_aware_progress_report(self):
        integ = self._setup_full()
        text = compose_github_aware_progress_report(
            "proj:1", integ,
            completed="реализован интеграционный слой",
            current_action="запуск тестов",
            blocker_state="нет",
            decisions_needed="подтверждение мержа",
            notable_risks="нет",
        )
        self.assertIn("Завершено", text)
        self.assertIn("реализован интеграционный слой", text)
        self.assertIn("GitHub:", text)
        self.assertIn("testowner/testrepo", text)

    def test_telegram_chat_history_not_authoritative(self):
        """Status is derived from ProjectGitHubState, not from chat history."""
        integ = self._setup_full()
        state = integ.get_project_state("proj:1")
        self.assertEqual(state.linked_ticket, "TKT-008")
        self.assertEqual(state.active_pr_number, 42)
        text = integ.compose_telegram_status("proj:1")
        self.assertIn("TKT-008", text)


class TestSecretHygiene(unittest.TestCase):
    """Secret hygiene: no token values in URLs, command lines, errors, progress text."""

    def test_no_token_in_status_text(self):
        rest = _RecordingRESTExecutor({
            **_REPO_REGISTER_RESPONSE,
            **_PR_OPEN_RESPONSE,
        })
        git = _RecordingGitExecutor()
        integ = GitHubPRIntegration(
            rest_executor=rest, git_executor=git, _environ=_make_env()
        )
        integ.register_repository("proj:1", "testowner", "testrepo")
        integ.create_branch_and_open_pr(
            "proj:1", "TKT-008", "tkt-008/feature", pr_title="Feature",
        )
        text = integ.compose_telegram_status("proj:1")
        self.assertNotIn(_FAKE_PAT, text)
        self.assertNotIn(_FAKE_TOKEN, text)

    def test_no_token_in_progress_text(self):
        rest = _RecordingRESTExecutor({
            **_REPO_REGISTER_RESPONSE,
            **_PR_OPEN_RESPONSE,
        })
        git = _RecordingGitExecutor()
        integ = GitHubPRIntegration(
            rest_executor=rest, git_executor=git, _environ=_make_env()
        )
        integ.register_repository("proj:1", "testowner", "testrepo")
        integ.create_branch_and_open_pr(
            "proj:1", "TKT-008", "tkt-008/feature", pr_title="Feature",
        )
        text = integ.compose_telegram_progress("proj:1")
        self.assertNotIn(_FAKE_PAT, text)
        self.assertNotIn(_FAKE_TOKEN, text)

    def test_no_token_in_integration_error_message(self):
        rest = _FailingRESTExecutor()
        integ = GitHubPRIntegration(rest_executor=rest, _environ=_make_env())
        try:
            integ.register_repository("proj:1", "testowner", "testrepo")
        except IntegrationError as e:
            self.assertNotIn(_FAKE_PAT, str(e))
            self.assertNotIn(_FAKE_TOKEN, str(e))

    def test_no_token_in_compose_progress_report(self):
        rest = _RecordingRESTExecutor({
            **_REPO_REGISTER_RESPONSE,
            **_PR_OPEN_RESPONSE,
        })
        git = _RecordingGitExecutor()
        integ = GitHubPRIntegration(
            rest_executor=rest, git_executor=git, _environ=_make_env()
        )
        integ.register_repository("proj:1", "testowner", "testrepo")
        text = compose_github_aware_progress_report(
            "proj:1", integ, "done", "running", "none", "none", "none",
        )
        self.assertNotIn(_FAKE_PAT, text)
        self.assertNotIn(_FAKE_TOKEN, text)

    def test_token_redacted_in_repo_url(self):
        token_url = "https://ghp_abcdefghijklmnopqrstuvwx@github.com/testowner/testrepo"
        responses = {
            "GET https://api.github.com/repos/testowner/testrepo": {
                "html_url": token_url,
            },
        }
        rest = _RecordingRESTExecutor(responses)
        integ = GitHubPRIntegration(rest_executor=rest, _environ=_make_env())
        state = integ.register_repository("proj:1", "testowner", "testrepo")
        self.assertNotIn("ghp_", state.repo_url)
        text = integ.compose_telegram_status("proj:1")
        self.assertNotIn("ghp_", text)

    def test_no_real_token_patterns_in_test_fixtures(self):
        """Test fixtures must not contain real token prefixes."""
        import re
        real_pattern = re.compile(r"ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,}")
        self.assertIsNone(real_pattern.search(_FAKE_TOKEN))
        self.assertIsNone(real_pattern.search(_FAKE_PAT))

    def test_no_token_in_pr_url(self):
        token_pr_url = "https://github_pat_ABCDEFGHIJKLMNOPQRSTUVWXYZ@github.com/testowner/testrepo/pull/42"
        responses = {
            **_REPO_REGISTER_RESPONSE,
            "POST https://api.github.com/repos/testowner/testrepo/pulls": {
                "number": 42,
                "html_url": token_pr_url,
                "state": "open",
            },
        }
        rest = _RecordingRESTExecutor(responses)
        git = _RecordingGitExecutor()
        integ = GitHubPRIntegration(
            rest_executor=rest, git_executor=git, _environ=_make_env()
        )
        integ.register_repository("proj:1", "testowner", "testrepo")
        integ.create_branch_and_open_pr(
            "proj:1", "TKT-008", "tkt-008/feature", pr_title="Feature",
        )
        state = integ.get_project_state("proj:1")
        self.assertNotIn("github_pat_", state.active_pr_url)
        text = integ.compose_telegram_status("proj:1")
        self.assertNotIn("github_pat_", text)


class TestHermesBundledSkillsBlocked(unittest.TestCase):
    """Integration does not enable Hermes bundled GitHub skills."""

    def test_no_hermes_skill_imports(self):
        """The integration module does not import or use Hermes bundled skills."""
        import src.developer_assistant.github_pr_integration as mod
        import inspect
        source = inspect.getsource(mod)
        lower = source.lower()
        for skill in ("github-pr-workflow", "github-issues", "github-auth"):
            self.assertNotIn(f"import {skill}", source)
            self.assertNotIn(f"from {skill}", source)
        self.assertNotIn("hermes", lower.replace(
            "hermes bundled github-pr-workflow, github-issues, and github-auth remain", ""
        ).replace(
            "hermes agent", ""
        ).replace(
            "hermes runtime", ""
        ).replace(
            "hermes-orchestrated", ""
        ).replace(
            "hermes run", ""
        ))

    def test_uses_project_specific_github_workflow(self):
        """The integration module imports from github_workflow.py."""
        import src.developer_assistant.github_pr_integration as mod
        import inspect
        source = inspect.getsource(mod)
        self.assertIn("github_workflow", source)
        self.assertIn("load_credential", source)


class TestProjectGitHubStateDataclass(unittest.TestCase):
    """ProjectGitHubState dataclass behavior."""

    def test_repo_full_name(self):
        state = ProjectGitHubState(repo_owner="owner", repo_name="repo")
        self.assertEqual(state.repo_full_name, "owner/repo")

    def test_repo_full_name_empty(self):
        state = ProjectGitHubState()
        self.assertEqual(state.repo_full_name, "")

    def test_pr_check_state_completed_with_conclusion(self):
        check = PRCheckState(check_name="ci", status="completed", conclusion="success")
        self.assertEqual(check.to_status_text(), "ci: success")

    def test_pr_check_state_in_progress(self):
        check = PRCheckState(check_name="ci", status="in_progress")
        self.assertEqual(check.to_status_text(), "ci: in_progress")

    def test_pr_check_state_empty(self):
        check = PRCheckState()
        self.assertEqual(check.to_status_text(), "no checks")

    def test_update_project_state(self):
        integ = GitHubPRIntegration(_environ=_make_env())
        integ.update_project_state(
            "proj:1",
            repo_owner="owner",
            repo_name="repo",
            active_branch="feature",
            linked_ticket="TKT-008",
        )
        state = integ.get_project_state("proj:1")
        self.assertEqual(state.repo_owner, "owner")
        self.assertEqual(state.active_branch, "feature")

    def test_update_project_state_partial(self):
        integ = GitHubPRIntegration(_environ=_make_env())
        integ.update_project_state("proj:1", repo_owner="owner")
        integ.update_project_state("proj:1", repo_name="repo")
        state = integ.get_project_state("proj:1")
        self.assertEqual(state.repo_owner, "owner")
        self.assertEqual(state.repo_name, "repo")


if __name__ == "__main__":
    unittest.main()
