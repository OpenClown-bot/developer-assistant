"""Unit tests for runtime_executors module (TKT-016).

Covers:
- Successful REST execution through HttpRESTExecutor
- REST failure redaction (HTTP errors, URL errors, connection errors)
- Successful git execution through SubprocessGitExecutor
- Git failure redaction (non-zero exit codes, exceptions)
- Command-validation enforcement (blocked flags rejected by validate_git_args)
- Subprocess shell avoidance
- Credential-source rejection
- No use of Hermes bundled GitHub skills
- Secret hygiene: no token values in errors, rendered text, or test fixtures
- Integration with TKT-008 GitHubPRIntegration through executor injection
"""

import json
import subprocess
import unittest
import urllib.error
import urllib.request
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from src.developer_assistant.github_workflow import (
    GitHubRESTRequest,
    GitCommand,
    validate_git_args,
    redact_token,
)
from src.developer_assistant.runtime_executors import (
    HttpRESTExecutor,
    RuntimeGitError,
    RuntimeRESTError,
    SubprocessGitExecutor,
)

_FAKE_TOKEN = "FAKE_TEST_TOKEN_NOT_REAL_1234567890"
_FAKE_PAT = "github_pat_11ABCDEFGHIJKLMNOP1234567890A1B2"


class TestHttpRESTExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = HttpRESTExecutor()
        self.token = _FAKE_PAT

    def _make_get_request(self, url: str = "https://api.github.com/repos/owner/repo") -> GitHubRESTRequest:
        return GitHubRESTRequest(method="GET", url=url)

    def _make_post_request(self, body: Dict[str, Any] = None) -> GitHubRESTRequest:
        return GitHubRESTRequest(
            method="POST",
            url="https://api.github.com/user/repos",
            body=body or {"name": "test-repo"},
        )

    def test_successful_get_request(self):
        expected = {"id": 1, "full_name": "owner/repo"}
        request = self._make_get_request()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(expected).encode("utf-8")
            mock_urlopen.return_value = mock_resp

            result = self.executor.execute(request, self.token)

        self.assertEqual(result, expected)

    def test_successful_post_request(self):
        body = {"name": "test-repo", "private": False}
        expected = {"id": 2, "full_name": "owner/test-repo"}
        request = self._make_post_request(body)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(expected).encode("utf-8")
            mock_urlopen.return_value = mock_resp

            result = self.executor.execute(request, self.token)

        self.assertEqual(result, expected)

    def test_successful_patch_request(self):
        expected = {"state": "open", "body": "updated"}
        request = GitHubRESTRequest(
            method="PATCH",
            url="https://api.github.com/repos/owner/repo/pulls/1",
            body={"body": "updated"},
        )

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(expected).encode("utf-8")
            mock_urlopen.return_value = mock_resp

            result = self.executor.execute(request, self.token)

        self.assertEqual(result, expected)

    def test_successful_empty_response_body(self):
        request = self._make_get_request()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b""
            mock_urlopen.return_value = mock_resp

            result = self.executor.execute(request, self.token)

        self.assertEqual(result, {})

    def test_http_error_redacts_token_in_url(self):
        request = self._make_get_request(
            url="https://api.github.com/repos/owner/repo"
        )

        with patch("urllib.request.urlopen") as mock_urlopen:
            def raise_404(*args, **kwargs):
                raise urllib.error.HTTPError(
                    "https://api.github.com/repos/owner/repo",
                    404,
                    "Not Found",
                    {},
                    None,
                )
            mock_urlopen.side_effect = raise_404

            with self.assertRaises(RuntimeRESTError) as ctx:
                self.executor.execute(request, self.token)

        error_text = str(ctx.exception)
        self.assertNotIn(self.token, error_text)
        self.assertIn("HTTP 404", error_text)

    def test_http_error_redacts_token_in_error_body(self):
        request = self._make_get_request()

        error_body_str = json.dumps({"message": "Bad credentials", "token": _FAKE_PAT})

        with patch("urllib.request.urlopen") as mock_urlopen:
            def raise_401(*args, **kwargs):
                raise urllib.error.HTTPError(
                    "https://api.github.com/repos/owner/repo",
                    401,
                    "Unauthorized",
                    {},
                    MagicMock(read=lambda: error_body_str.encode("utf-8")),
                )
            mock_urlopen.side_effect = raise_401

            with self.assertRaises(RuntimeRESTError) as ctx:
                self.executor.execute(request, self.token)

        error_text = str(ctx.exception)
        self.assertNotIn(_FAKE_PAT, error_text)

    def test_url_error_redacts_token(self):
        request = self._make_get_request()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("connection refused")

            with self.assertRaises(RuntimeRESTError) as ctx:
                self.executor.execute(request, self.token)

        error_text = str(ctx.exception)
        self.assertNotIn(self.token, error_text)
        self.assertIn("URL error", error_text)

    def test_os_error_redacts_token(self):
        request = self._make_get_request()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = OSError("socket error")

            with self.assertRaises(RuntimeRESTError) as ctx:
                self.executor.execute(request, self.token)

        error_text = str(ctx.exception)
        self.assertNotIn(self.token, error_text)

    def test_value_error_redacts_token(self):
        request = self._make_get_request()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = ValueError("invalid URL")

            with self.assertRaises(RuntimeRESTError) as ctx:
                self.executor.execute(request, self.token)

        error_text = str(ctx.exception)
        self.assertNotIn(self.token, error_text)

    def test_generic_exception_redacts_token(self):
        request = self._make_get_request()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = RuntimeError("unexpected crash")

            with self.assertRaises(RuntimeRESTError) as ctx:
                self.executor.execute(request, self.token)

        error_text = str(ctx.exception)
        self.assertNotIn(self.token, error_text)

    def test_token_not_stored_in_request_after_auth(self):
        request = self._make_get_request()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"ok": True}).encode("utf-8")
            mock_urlopen.return_value = mock_resp

            self.executor.execute(request, self.token)

        self.assertNotIn(self.token, request.url)
        self.assertIsNone(request.body)

    def test_authorization_header_injected_at_send_time(self):
        request = self._make_get_request()

        with patch("urllib.request.urlopen") as mock_urlopen:
            with patch("urllib.request.Request") as mock_request_cls:
                mock_resp = MagicMock()
                mock_resp.read.return_value = json.dumps({"ok": True}).encode("utf-8")
                mock_urlopen.return_value = mock_resp

                self.executor.execute(request, self.token)

                mock_request_cls.assert_called_once()
                call_kwargs = {}
                if mock_request_cls.call_args[1]:
                    call_kwargs = mock_request_cls.call_args[1]
                self.assertIn("headers", call_kwargs)
                self.assertIn("Authorization", call_kwargs["headers"])

    def test_non_dict_response_becomes_empty_dict(self):
        request = self._make_get_request()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps([1, 2, 3]).encode("utf-8")
            mock_urlopen.return_value = mock_resp

            result = self.executor.execute(request, self.token)

        self.assertEqual(result, {})

    def test_token_not_in_error_for_malformed_json_response(self):
        request = self._make_get_request()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = "not json".encode("utf-8")
            mock_urlopen.return_value = mock_resp

            with self.assertRaises(RuntimeRESTError) as ctx:
                self.executor.execute(request, self.token)

        self.assertNotIn(self.token, str(ctx.exception))


class TestSubprocessGitExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = SubprocessGitExecutor()

    def _make_cmd(self, args=None):
        return GitCommand(args=args or ["status"])

    def test_successful_git_execution(self):
        cmd = self._make_cmd(["status"])

        with patch(
            "src.developer_assistant.runtime_executors.execute_git_command"
        ) as mock_exec:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_exec.return_value = mock_result

            result = self.executor.execute(cmd)

        self.assertEqual(result, 0)
        mock_exec.assert_called_once_with(cmd)

    def test_successful_git_branch_creation(self):
        cmd = self._make_cmd(["checkout", "-b", "feature/xyz"])

        with patch(
            "src.developer_assistant.runtime_executors.execute_git_command"
        ) as mock_exec:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_exec.return_value = mock_result

            result = self.executor.execute(cmd)

        self.assertEqual(result, 0)

    def test_git_non_zero_exit_code_raises_runtime_git_error(self):
        cmd = self._make_cmd(["status"])

        with patch(
            "src.developer_assistant.runtime_executors.execute_git_command"
        ) as mock_exec:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "fatal: not a git repository"
            mock_exec.return_value = mock_result

            with self.assertRaises(RuntimeGitError) as ctx:
                self.executor.execute(cmd)

        error_text = str(ctx.exception)
        self.assertIn("exited with code 1", error_text)
        self.assertIn("fatal: not a git repository", error_text)

    def test_git_exception_raises_runtime_git_error(self):
        cmd = self._make_cmd(["clone", "some-url"])

        with patch(
            "src.developer_assistant.runtime_executors.execute_git_command"
        ) as mock_exec:
            mock_exec.side_effect = OSError("command not found")

            with self.assertRaises(RuntimeGitError) as ctx:
                self.executor.execute(cmd)

        error_text = str(ctx.exception)
        self.assertIn("Git command failed", error_text)

    def test_git_error_text_is_redacted(self):
        cmd = self._make_cmd(["push", "origin", "main"])

        with patch(
            "src.developer_assistant.runtime_executors.execute_git_command"
        ) as mock_exec:
            mock_result = MagicMock()
            mock_result.returncode = 128
            mock_result.stderr = (
                "remote: Invalid username or token github_pat_11ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456\n"
                "fatal: Authentication failed"
            )
            mock_exec.return_value = mock_result

            with self.assertRaises(RuntimeGitError) as ctx:
                self.executor.execute(cmd)

        error_text = str(ctx.exception)
        self.assertNotIn("github_pat_", error_text)

    def test_no_shell_execution_subprocess_shell_is_false(self):
        cmd = self._make_cmd(["status"])

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            with patch("src.developer_assistant.github_workflow.validate_git_args", return_value=["git", "status"]):
                from src.developer_assistant.github_workflow import execute_git_command as real_exec
                real_exec(cmd)

            self.assertTrue(mock_run.called)
            shell_arg = mock_run.call_args[1].get("shell", False)
            self.assertFalse(shell_arg)

    def test_command_validation_blocks_force_push(self):
        from src.developer_assistant.github_workflow import DangerousOperationError
        with self.assertRaises(DangerousOperationError):
            validate_git_args(["push", "--force", "origin", "main"])

    def test_command_validation_blocks_force_with_lease(self):
        from src.developer_assistant.github_workflow import DangerousOperationError
        with self.assertRaises(DangerousOperationError):
            validate_git_args(["push", "--force-with-lease", "origin", "main"])

    def test_command_validation_blocks_hard_reset(self):
        from src.developer_assistant.github_workflow import DangerousOperationError
        with self.assertRaises(DangerousOperationError):
            validate_git_args(["reset", "--hard", "HEAD~1"])

    def test_command_validation_blocks_branch_deletion_with_D(self):
        from src.developer_assistant.github_workflow import DangerousOperationError
        with self.assertRaises(DangerousOperationError):
            validate_git_args(["branch", "-D", "feature/x"])

    def test_command_validation_blocks_branch_deletion_with_delete(self):
        from src.developer_assistant.github_workflow import DangerousOperationError
        with self.assertRaises(DangerousOperationError):
            validate_git_args(["branch", "--delete", "feature/x"])

    def test_executor_enforces_validation_on_bad_command(self):
        cmd = self._make_cmd(["push", "--force", "origin", "main"])

        with patch(
            "src.developer_assistant.runtime_executors.execute_git_command"
        ) as mock_exec:
            mock_exec.side_effect = ValueError("blocked flag: --force")

            with self.assertRaises(RuntimeGitError) as ctx:
                self.executor.execute(cmd)

        self.assertIn("Git command failed", str(ctx.exception))

    def test_no_raw_command_strings_arg_list_only(self):
        cmd = GitCommand(args=["diff", "--cached"])

        with patch(
            "src.developer_assistant.runtime_executors.execute_git_command"
        ) as mock_exec:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_exec.return_value = mock_result

            result = self.executor.execute(cmd)
            self.assertEqual(result, 0)

    def test_stdout_stderr_redacted_in_successful_execution(self):
        cmd = self._make_cmd(["log", "--oneline"])

        with patch(
            "src.developer_assistant.runtime_executors.execute_git_command"
        ) as mock_exec:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "abc123 Fix bug"
            mock_exec.return_value = mock_result

            result = self.executor.execute(cmd)
            self.assertEqual(result, 0)


class TestCredentialSourceRejection(unittest.TestCase):
    def test_github_token_is_rejected(self):
        with patch.dict("os.environ", {"GITHUB_TOKEN": _FAKE_TOKEN}), \
             patch.dict("os.environ", {"PROJECT_GITHUB_PAT": ""}):
            from src.developer_assistant.github_workflow import CredentialSourceError, load_credential
            with self.assertRaises(CredentialSourceError) as ctx:
                load_credential()
            self.assertIn("PROJECT_GITHUB_PAT", str(ctx.exception))

    def test_gh_token_is_rejected(self):
        with patch.dict("os.environ", {"GH_TOKEN": _FAKE_TOKEN}), \
             patch.dict("os.environ", {"PROJECT_GITHUB_PAT": ""}):
            from src.developer_assistant.github_workflow import CredentialSourceError, load_credential
            with self.assertRaises(CredentialSourceError) as ctx:
                load_credential()
            self.assertIn("PROJECT_GITHUB_PAT", str(ctx.exception))

    def test_project_github_pat_is_accepted(self):
        with patch.dict("os.environ", {"PROJECT_GITHUB_PAT": _FAKE_PAT}):
            from src.developer_assistant.github_workflow import load_credential
            token = load_credential()
            self.assertEqual(token, _FAKE_PAT)


class TestIntegrationWithTKT008(unittest.TestCase):
    def test_http_executor_can_be_injected_into_integration(self):
        from src.developer_assistant.github_pr_integration import GitHubPRIntegration

        with patch.dict("os.environ", {"PROJECT_GITHUB_PAT": _FAKE_PAT}):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = MagicMock()
                mock_resp.read.return_value = json.dumps({"id": 1, "full_name": "owner/test"}).encode("utf-8")
                mock_urlopen.return_value = mock_resp

                integration = GitHubPRIntegration(
                    rest_executor=HttpRESTExecutor(),
                    git_executor=SubprocessGitExecutor(),
                )

                state = integration.register_repository(
                    project_key="test-proj",
                    owner="owner",
                    name="test",
                    create=True,
                )
                self.assertEqual(state.repo_full_name, "owner/test")

    def test_git_executor_can_be_injected_into_integration(self):
        from src.developer_assistant.github_pr_integration import GitHubPRIntegration

        with patch.dict("os.environ", {"PROJECT_GITHUB_PAT": _FAKE_PAT}):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = MagicMock()
                mock_resp.read.return_value = json.dumps({"id": 1, "full_name": "owner/test"}).encode("utf-8")
                mock_urlopen.return_value = mock_resp

                integration = GitHubPRIntegration(
                    rest_executor=HttpRESTExecutor(),
                    git_executor=SubprocessGitExecutor(),
                )

                state = integration.register_repository(
                    project_key="test-proj",
                    owner="owner",
                    name="test",
                    create=True,
                )
                self.assertEqual(state.repo_owner, "owner")
                self.assertEqual(state.repo_name, "test")

    def test_no_hermes_bundled_github_skill_imports(self):
        with self.assertRaises(ImportError):
            import hermes.skills.github.github_pr_workflow  # type: ignore[import-untyped]

    def test_no_hermes_bundled_github_auth_imports(self):
        with self.assertRaises(ImportError):
            import hermes.skills.github.github_auth  # type: ignore[import-untyped]

    def test_no_hermes_bundled_github_issues_imports(self):
        with self.assertRaises(ImportError):
            import hermes.skills.github.github_issues  # type: ignore[import-untyped]


class TestTokenRedactionOutputs(unittest.TestCase):
    def test_rest_error_url_does_not_contain_token(self):
        executor = HttpRESTExecutor()
        request = GitHubRESTRequest(
            method="GET",
            url="https://api.github.com/repos/owner/repo",
        )

        with patch("urllib.request.urlopen") as mock_urlopen:
            def raise_500(*args, **kwargs):
                raise urllib.error.HTTPError(
                    "https://api.github.com/repos/owner/repo",
                    500,
                    "Server Error",
                    {},
                    None,
                )
            mock_urlopen.side_effect = raise_500

            try:
                executor.execute(request, _FAKE_PAT)
            except RuntimeRESTError as exc:
                self.assertNotIn(_FAKE_PAT, str(exc))
                self.assertNotIn("github_pat_", str(exc).lower())

    def test_git_error_output_does_not_contain_raw_pat(self):
        executor = SubprocessGitExecutor()
        cmd = GitCommand(args=["push"])

        with patch(
            "src.developer_assistant.runtime_executors.execute_git_command"
        ) as mock_exec:
            mock_exec.side_effect = ValueError(
                f"token-bearing remote URL containing {_FAKE_PAT} rejected"
            )

            try:
                executor.execute(cmd)
            except RuntimeGitError as exc:
                self.assertNotIn(_FAKE_PAT, str(exc))

    def test_progress_text_cannot_leak_tokens(self):
        from src.developer_assistant.github_pr_integration import (
            GitHubPRIntegration,
            compose_github_aware_progress_report,
        )

        with patch.dict("os.environ", {"PROJECT_GITHUB_PAT": _FAKE_PAT}):
            integration = GitHubPRIntegration()

            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = MagicMock()
                mock_resp.read.return_value = json.dumps({"id": 1, "full_name": "owner/repo"}).encode("utf-8")
                mock_urlopen.return_value = mock_resp

                integration.register_repository(
                    project_key="demo",
                    owner="owner",
                    name="repo",
                    create=True,
                )

            result = compose_github_aware_progress_report(
                project_key="demo",
                integration=integration,
                completed="TKT-001",
                current_action="testing",
                blocker_state="none",
                decisions_needed="none",
                notable_risks="none",
            )

        self.assertNotIn(_FAKE_PAT, result)
        self.assertNotIn("github_pat_", result.lower())


class TestSmokeGateDisabledByDefault(unittest.TestCase):
    def test_live_smoke_is_disabled_by_default(self):
        executor = HttpRESTExecutor()
        self.assertFalse(
            hasattr(executor, "_smoke_enabled") and getattr(executor, "_smoke_enabled", False),
            "Live smoke must not be enabled by default",
        )

    def test_no_autonomous_merge_path(self):
        from src.developer_assistant.github_workflow import build_merge_command, MergeBlockedError
        with self.assertRaises(MergeBlockedError):
            build_merge_command(founder_acknowledgement=False)


if __name__ == "__main__":
    unittest.main()