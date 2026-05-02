"""Tests for the project-specific GitHub workflow capability (TKT-014).

Covers:
- Credential-source rejection (composed into load_credential)
- Token redaction in logs/errors
- Mocked GitHub REST request construction
- Constrained git command construction
- Merge-gate behavior
- Env var collision handling (RV-SPEC-001)
- Symlink bypass prevention in git credentials check
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "src")
)

from developer_assistant.github_workflow import (
    CredentialSourceError,
    DangerousOperationError,
    GitHubRESTRequest,
    GitCommand,
    MergeBlockedError,
    build_branch_create_command,
    build_check_status_request,
    build_commit_push_command,
    build_merge_command,
    build_pr_metadata_request,
    build_pr_open_request,
    build_pr_update_request,
    build_repo_create_request,
    build_repo_register_request,
    check_for_git_credentials_file,
    check_for_token_in_remote,
    execute_git_command,
    load_credential,
    redact_token,
    reject_credential_source,
    validate_git_args,
    _CREDENTIAL_ENV_VAR,
    _REDACTED,
)

_FAKE_TOKEN = "FAKE_TEST_TOKEN_NOT_REAL_1234567890"
_FAKE_PAT = "FAKE_PAT_NOT_REAL_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_FAKE_REMOTE_URL_WITH_TOKEN = "https://FAKE_TOKEN_NOT_REAL@github.com/owner/repo.git"


def _safe_credential_env(**extra):
    env = {_CREDENTIAL_ENV_VAR: _FAKE_TOKEN}
    env.update(extra)
    return env


class TestCredentialSourceRejection(unittest.TestCase):

    def test_reject_git_credentials_file(self):
        with self.assertRaises(CredentialSourceError):
            reject_credential_source("~/.git-credentials")

    def test_reject_git_credentials_relative(self):
        with self.assertRaises(CredentialSourceError):
            reject_credential_source(".git-credentials")

    def test_reject_token_in_remote_url(self):
        with self.assertRaises(CredentialSourceError):
            reject_credential_source("token-in-remote URL")

    def test_reject_committed_config(self):
        with self.assertRaises(CredentialSourceError):
            reject_credential_source("committed config token")

    def test_reject_cli_argument(self):
        with self.assertRaises(CredentialSourceError):
            reject_credential_source("cli argument --token")

    def test_reject_cli_flag(self):
        with self.assertRaises(CredentialSourceError):
            reject_credential_source("-t mytoken")

    def test_check_git_credentials_path_matches(self):
        home = os.path.expanduser("~")
        cred_path = os.path.join(home, ".git-credentials")
        with self.assertRaises(CredentialSourceError):
            check_for_git_credentials_file(cred_path)

    def test_check_git_credentials_path_does_not_match(self):
        check_for_git_credentials_file("/tmp/some-other-file")

    def test_check_for_token_in_remote_with_embedded_token(self):
        with self.assertRaises(CredentialSourceError):
            check_for_token_in_remote(
                "https://ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA@github.com/owner/repo.git"
            )

    def test_check_for_token_in_remote_clean_url(self):
        check_for_token_in_remote("https://github.com/owner/repo.git")

    def test_check_for_token_in_remote_with_any_embedded_creds(self):
        with self.assertRaises(CredentialSourceError):
            check_for_token_in_remote("https://user:pass@github.com/owner/repo.git")

    def test_reject_config_file_token(self):
        with self.assertRaises(CredentialSourceError):
            reject_credential_source("config file token in settings.json")


class TestLoadCredentialComposedValidation(unittest.TestCase):

    def test_load_credential_rejects_git_credentials_file_existence(self):
        def fake_realpath(p):
            return p
        with patch("os.path.exists", return_value=True):
            with self.assertRaises(CredentialSourceError) as ctx:
                load_credential(
                    _environ=_safe_credential_env(),
                    _realpath=fake_realpath,
                )
            self.assertIn("~/.git-credentials", str(ctx.exception))

    def test_load_credential_rejects_token_in_remote_url(self):
        with patch("os.path.exists", return_value=False):
            with self.assertRaises(CredentialSourceError):
                load_credential(
                    _environ=_safe_credential_env(),
                    remote_url="https://ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA@github.com/owner/repo.git",
                )

    def test_load_credential_rejects_github_token_only(self):
        with patch("os.path.exists", return_value=False):
            with self.assertRaises(CredentialSourceError) as ctx:
                load_credential(
                    _environ={"GITHUB_TOKEN": "ci-auto-injected-value"},
                )
            self.assertIn("GITHUB_TOKEN", str(ctx.exception))

    def test_load_credential_allows_project_pat_with_github_token_present(self):
        with patch("os.path.exists", return_value=False):
            token = load_credential(
                _environ=_safe_credential_env(GITHUB_TOKEN="ci-auto-injected-value"),
            )
            self.assertEqual(token, _FAKE_TOKEN)

    def test_load_credential_rejects_when_github_token_present_but_pat_empty(self):
        with patch("os.path.exists", return_value=False):
            with self.assertRaises(CredentialSourceError) as ctx:
                load_credential(
                    _environ={
                        _CREDENTIAL_ENV_VAR: "",
                        "GITHUB_TOKEN": "ci-auto-injected-value",
                    },
                )
            self.assertIn("GITHUB_TOKEN", str(ctx.exception))

    def test_load_credential_rejects_missing_env_var(self):
        with patch("os.path.exists", return_value=False):
            with self.assertRaises(CredentialSourceError) as ctx:
                load_credential(_environ={})
            self.assertIn(_CREDENTIAL_ENV_VAR, str(ctx.exception))

    def test_load_credential_rejects_github_token_without_pat(self):
        with patch("os.path.exists", return_value=False):
            with self.assertRaises(CredentialSourceError) as ctx:
                load_credential(
                    _environ={"GITHUB_TOKEN": "ci-value"},
                )
            self.assertIn("GITHUB_TOKEN", str(ctx.exception))

    def test_load_credential_rejects_gh_token_without_pat(self):
        with patch("os.path.exists", return_value=False):
            with self.assertRaises(CredentialSourceError):
                load_credential(_environ={"GH_TOKEN": "ci-value"})

    def test_load_credential_succeeds_with_clean_remote_url(self):
        with patch("os.path.exists", return_value=False):
            token = load_credential(
                _environ=_safe_credential_env(),
                remote_url="https://github.com/owner/repo.git",
            )
            self.assertEqual(token, _FAKE_TOKEN)

    def test_load_credential_error_no_token_value_leaked(self):
        with patch("os.path.exists", return_value=False):
            with self.assertRaises(CredentialSourceError) as ctx:
                load_credential(_environ={})
            self.assertNotIn(_FAKE_TOKEN, str(ctx.exception))
            self.assertNotIn("ghp_", str(ctx.exception))

    def test_load_credential_structurally_cannot_read_config_files(self):
        with patch("os.path.exists", return_value=False):
            token = load_credential(_environ=_safe_credential_env())
            self.assertEqual(token, _FAKE_TOKEN)

    def test_load_credential_structurally_cannot_accept_cli_args(self):
        with patch("os.path.exists", return_value=False):
            token = load_credential(_environ=_safe_credential_env())
            self.assertEqual(token, _FAKE_TOKEN)


class TestRealpathSymlinkBypass(unittest.TestCase):

    def test_check_git_credentials_uses_realpath_direct(self):
        home = os.path.expanduser("~")
        cred_path = os.path.realpath(os.path.join(home, ".git-credentials"))
        with self.assertRaises(CredentialSourceError):
            check_for_git_credentials_file(cred_path)

    def test_check_git_credentials_symlink_resolves_to_same(self):
        home = os.path.expanduser("~")
        direct = os.path.join(home, ".git-credentials")
        resolved = os.path.realpath(direct)
        if direct == resolved:
            self.skipTest("No symlink difference on this platform for this path")
        with self.assertRaises(CredentialSourceError):
            check_for_git_credentials_file(direct)

    def test_check_git_credentials_mocked_symlink_bypass(self):
        home = os.path.expanduser("~")
        cred_real = os.path.realpath(os.path.join(home, ".git-credentials"))
        symlink_path = "/tmp/fake_link_to_git_creds"
        with patch("os.path.realpath") as mock_realpath, \
             patch("os.path.abspath", side_effect=lambda p: p):
            mock_realpath.side_effect = lambda p: cred_real if p == symlink_path else p
            with self.assertRaises(CredentialSourceError):
                check_for_git_credentials_file(symlink_path)

    def test_check_git_credentials_different_path_passes(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=True) as f:
            check_for_git_credentials_file(f.name)


class TestTokenRedaction(unittest.TestCase):

    def test_redact_ghp_token(self):
        text = "token is ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        result = redact_token(text)
        self.assertNotIn("ghp_", result)
        self.assertIn(_REDACTED, result)

    def test_redact_github_pat(self):
        text = "token is github_pat_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA_1234"
        result = redact_token(text)
        self.assertNotIn("github_pat_", result)
        self.assertIn(_REDACTED, result)

    def test_redact_gho_token(self):
        text = "token is gho_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        result = redact_token(text)
        self.assertNotIn("gho_", result)

    def test_redact_ghs_token(self):
        text = "token is ghs_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        result = redact_token(text)
        self.assertNotIn("ghs_", result)

    def test_no_redaction_when_no_token(self):
        text = "normal log message without secrets"
        self.assertEqual(redact_token(text), text)

    def test_git_command_redacts_in_cmdline(self):
        cmd = GitCommand(args=["push", "origin", "main"], cwd=".")
        cmdline = cmd.to_cmdline()
        self.assertNotIn("ghp_", cmdline)

    def test_execute_git_command_redacts_output(self):
        cmd = GitCommand(args=["status"], cwd=".")
        result = execute_git_command(cmd, dry_run=True)
        self.assertNotIn("ghp_", result.stdout)

    def test_load_credential_returns_real_token_for_caller(self):
        with patch("os.path.exists", return_value=False):
            token = load_credential(_environ=_safe_credential_env())
            self.assertEqual(token, _FAKE_TOKEN)

    def test_load_credential_error_message_no_token_value(self):
        with patch("os.path.exists", return_value=False):
            with self.assertRaises(CredentialSourceError) as ctx:
                load_credential(_environ={})
            self.assertNotIn(_FAKE_TOKEN, str(ctx.exception))
            self.assertNotIn("ghp_", str(ctx.exception))


class TestRESTRequestConstruction(unittest.TestCase):

    def test_repo_create_request(self):
        req = build_repo_create_request("my-org", "my-repo", description="test repo")
        self.assertEqual(req.method, "POST")
        self.assertIn("/orgs/my-org/repos", req.url)
        self.assertEqual(req.body["name"], "my-repo")
        self.assertEqual(req.body["description"], "test repo")
        self.assertTrue(req.body["private"])
        self.assertIn("Accept", req.headers)
        self.assertNotIn("Authorization", req.headers)

    def test_repo_create_request_url_has_no_token(self):
        req = build_repo_create_request("org", "repo")
        self.assertNotIn("token", req.url.lower())
        self.assertNotIn("ghp_", req.url)

    def test_repo_register_request(self):
        req = build_repo_register_request("owner", "repo")
        self.assertEqual(req.method, "GET")
        self.assertIn("/repos/owner/repo", req.url)
        self.assertIsNone(req.body)

    def test_repo_register_request_url_has_no_token(self):
        req = build_repo_register_request("owner", "repo")
        self.assertNotIn("token", req.url.lower())

    def test_pr_open_request(self):
        req = build_pr_open_request(
            "owner", "repo",
            head="feature-branch", base="main",
            title="My PR", body="PR body",
        )
        self.assertEqual(req.method, "POST")
        self.assertIn("/repos/owner/repo/pulls", req.url)
        self.assertEqual(req.body["head"], "feature-branch")
        self.assertEqual(req.body["base"], "main")
        self.assertEqual(req.body["title"], "My PR")
        self.assertEqual(req.body["body"], "PR body")

    def test_pr_open_request_url_has_no_token(self):
        req = build_pr_open_request("owner", "repo", head="h", base="b", title="t")
        self.assertNotIn("ghp_", req.url)
        self.assertNotIn("token", req.url.lower())

    def test_pr_update_request(self):
        req = build_pr_update_request(
            "owner", "repo", 42,
            title="Updated", state="closed",
        )
        self.assertEqual(req.method, "PATCH")
        self.assertIn("/repos/owner/repo/pulls/42", req.url)
        self.assertEqual(req.body["title"], "Updated")
        self.assertEqual(req.body["state"], "closed")

    def test_pr_update_request_partial(self):
        req = build_pr_update_request("owner", "repo", 7, body="new body")
        self.assertIn("body", req.body)
        self.assertNotIn("title", req.body)
        self.assertNotIn("state", req.body)

    def test_check_status_request(self):
        req = build_check_status_request("owner", "repo", "abc123")
        self.assertEqual(req.method, "GET")
        self.assertIn("/commits/abc123/check-runs", req.url)

    def test_check_status_request_url_has_no_token(self):
        req = build_check_status_request("owner", "repo", "abc123")
        self.assertNotIn("ghp_", req.url)

    def test_pr_metadata_request(self):
        req = build_pr_metadata_request("owner", "repo", 99)
        self.assertEqual(req.method, "GET")
        self.assertIn("/repos/owner/repo/pulls/99", req.url)
        self.assertIsNone(req.body)

    def test_pr_metadata_request_url_has_no_token(self):
        req = build_pr_metadata_request("owner", "repo", 99)
        self.assertNotIn("ghp_", req.url)
        self.assertNotIn("token", req.url.lower())

    def test_with_auth_adds_bearer(self):
        req = build_repo_register_request("owner", "repo")
        headers = req.with_auth(_FAKE_TOKEN)
        self.assertIn("Authorization", headers)
        self.assertEqual(headers["Authorization"], f"Bearer {_FAKE_TOKEN}")
        self.assertNotIn("Authorization", req.headers)

    def test_request_headers_contain_api_version(self):
        req = build_repo_create_request("org", "repo")
        self.assertIn("X-GitHub-Api-Version", req.headers)

    def test_repo_create_with_special_chars_in_owner(self):
        req = build_repo_create_request("my-org", "repo")
        self.assertNotIn(" ", req.url)


class TestConstrainedGitCommandConstruction(unittest.TestCase):

    def test_branch_create_command(self):
        cmd = build_branch_create_command("feature-x", base="main")
        self.assertEqual(cmd.args, ["checkout", "-b", "feature-x", "main"])

    def test_branch_create_default_base(self):
        cmd = build_branch_create_command("feature-x")
        self.assertIn("main", cmd.args)

    def test_branch_create_rejects_dangerous_name(self):
        with self.assertRaises(DangerousOperationError):
            build_branch_create_command("feature; rm -rf /")

    def test_branch_create_rejects_shell_metacharacters(self):
        with self.assertRaises(DangerousOperationError):
            build_branch_create_command("feature`cmd`")

    def test_branch_create_rejects_dollar_sign(self):
        with self.assertRaises(DangerousOperationError):
            build_branch_create_command("feature$VAR")

    def test_branch_create_rejects_ampersand(self):
        with self.assertRaises(DangerousOperationError):
            build_branch_create_command("feature&&cmd")

    def test_commit_push_command(self):
        cmd = build_commit_push_command(
            "test commit", remote="origin", branch="main"
        )
        self.assertEqual(cmd.args, ["push", "origin", "main"])

    def test_commit_push_omits_force(self):
        cmd = build_commit_push_command("msg", remote="origin", branch="main")
        for arg in cmd.args:
            self.assertNotIn(arg, ["--force", "-f", "--force-with-lease"])

    def test_commit_push_rejects_url_remote(self):
        with self.assertRaises(DangerousOperationError):
            build_commit_push_command("msg", remote="https://github.com/owner/repo.git")

    def test_commit_push_rejects_token_in_remote_url(self):
        with self.assertRaises(CredentialSourceError):
            check_for_token_in_remote(
                "https://ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA@github.com/owner/repo.git"
            )

    def test_validate_git_args_blocks_force_push(self):
        with self.assertRaises(DangerousOperationError):
            validate_git_args(["push", "--force", "origin", "main"])

    def test_validate_git_args_blocks_force_flag(self):
        with self.assertRaises(DangerousOperationError):
            validate_git_args(["push", "-f", "origin", "main"])

    def test_validate_git_args_blocks_hard_reset(self):
        with self.assertRaises(DangerousOperationError):
            validate_git_args(["reset", "--hard", "HEAD~1"])

    def test_validate_git_args_blocks_branch_delete(self):
        with self.assertRaises(DangerousOperationError):
            validate_git_args(["branch", "-D", "feature"])

    def test_validate_git_args_blocks_force_with_lease(self):
        with self.assertRaises(DangerousOperationError):
            validate_git_args(["push", "--force-with-lease", "origin", "main"])

    def test_validate_git_args_allows_safe_push(self):
        result = validate_git_args(["push", "origin", "main"])
        self.assertEqual(result, ["push", "origin", "main"])

    def test_validate_git_args_allows_checkout(self):
        result = validate_git_args(["checkout", "-b", "feature"])
        self.assertEqual(result, ["checkout", "-b", "feature"])

    def test_execute_git_command_dry_run(self):
        cmd = GitCommand(args=["status"], cwd=".")
        result = execute_git_command(cmd, dry_run=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("dry-run", result.stdout)

    def test_execute_git_command_validates_args(self):
        cmd = GitCommand(args=["push", "--force", "origin", "main"], cwd=".")
        with self.assertRaises(DangerousOperationError):
            execute_git_command(cmd, dry_run=True)

    def test_validate_git_args_blocks_generic_force_push_phrase(self):
        with self.assertRaises(DangerousOperationError):
            validate_git_args(["push", "origin", "main", "force push"])

    def test_validate_git_args_blocks_hard_reset_phrase(self):
        with self.assertRaises(DangerousOperationError):
            validate_git_args(["reset", "hard reset"])


class TestMergeGateBehavior(unittest.TestCase):

    def test_merge_disabled_by_default(self):
        with self.assertRaises(MergeBlockedError):
            build_merge_command(branch="feature-x")

    def test_merge_requires_founder_acknowledgement(self):
        with self.assertRaises(MergeBlockedError):
            build_merge_command(founder_acknowledgement=False, branch="feature-x")

    def test_merge_succeeds_with_founder_acknowledgement(self):
        cmd = build_merge_command(
            founder_acknowledgement=True, branch="feature-x"
        )
        self.assertEqual(cmd.args, ["merge", "feature-x"])

    def test_merge_error_message_mentions_v01(self):
        with self.assertRaises(MergeBlockedError) as ctx:
            build_merge_command(branch="feature-x")
        self.assertIn("v0.1", str(ctx.exception))

    def test_merge_error_message_mentions_founder(self):
        with self.assertRaises(MergeBlockedError) as ctx:
            build_merge_command(branch="feature-x")
        self.assertIn("founder", str(ctx.exception).lower())

    def test_merge_rejects_dangerous_branch_name(self):
        with self.assertRaises(DangerousOperationError):
            build_merge_command(
                founder_acknowledgement=True, branch="feature; rm -rf /"
            )


class TestEnvVarCollisionHandling(unittest.TestCase):

    def test_project_github_pat_is_used_not_github_token(self):
        with patch("os.path.exists", return_value=False):
            environ = _safe_credential_env(GITHUB_TOKEN="ci-auto-injected-token-value")
            token = load_credential(_environ=environ)
            self.assertEqual(token, _FAKE_TOKEN)

    def test_github_token_alone_is_not_consumed(self):
        with patch("os.path.exists", return_value=False):
            with self.assertRaises(CredentialSourceError):
                load_credential(_environ={"GITHUB_TOKEN": "ci-auto-injected-token-value"})

    def test_gh_token_alone_is_not_consumed(self):
        with patch("os.path.exists", return_value=False):
            with self.assertRaises(CredentialSourceError):
                load_credential(_environ={"GH_TOKEN": "ci-auto-injected-token-value"})

    def test_empty_project_github_pat_raises_even_if_github_token_present(self):
        with patch("os.path.exists", return_value=False):
            with self.assertRaises(CredentialSourceError):
                load_credential(
                    _environ={
                        _CREDENTIAL_ENV_VAR: "",
                        "GITHUB_TOKEN": "ci-auto-injected-token-value",
                    },
                )

    def test_credential_env_var_is_project_github_pat(self):
        self.assertEqual(_CREDENTIAL_ENV_VAR, "PROJECT_GITHUB_PAT")

    def test_load_credential_ignores_ci_auto_token(self):
        with patch("os.path.exists", return_value=False):
            environ = _safe_credential_env(
                GITHUB_TOKEN="ghs_CI_ACTIONS_AUTO_TOKEN_0000000000000000000",
            )
            token = load_credential(_environ=environ)
            self.assertEqual(token, _FAKE_TOKEN)

    def test_no_credential_env_raises_clear_error(self):
        with patch("os.path.exists", return_value=False):
            with self.assertRaises(CredentialSourceError) as ctx:
                load_credential(_environ={})
            self.assertIn(_CREDENTIAL_ENV_VAR, str(ctx.exception))

    def test_ci_github_token_not_silently_used_as_fallback(self):
        with patch("os.path.exists", return_value=False):
            with self.assertRaises(CredentialSourceError) as ctx:
                load_credential(
                    _environ={"GITHUB_TOKEN": "ghs_CI_ACTIONS_AUTO_TOKEN_0000000000000000000"},
                )
            self.assertIn("GITHUB_TOKEN", str(ctx.exception))
            self.assertIn("CI auto-injected", str(ctx.exception))


class TestRedactedRemoteURLs(unittest.TestCase):

    def test_token_bearing_url_redacted(self):
        url = "https://ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA@github.com/owner/repo.git"
        with self.assertRaises(CredentialSourceError):
            check_for_token_in_remote(url)

    def test_git_command_does_not_contain_token(self):
        cmd = build_commit_push_command("msg", remote="origin", branch="main")
        cmdline = cmd.to_cmdline()
        self.assertNotIn("ghp_", cmdline)
        self.assertNotIn("github_pat_", cmdline)


class TestBlockedSubcommandsRemoved(unittest.TestCase):

    def test_dangerous_push_flags_still_blocked(self):
        with self.assertRaises(DangerousOperationError):
            validate_git_args(["push", "--force", "origin", "main"])

    def test_safe_push_still_allowed(self):
        result = validate_git_args(["push", "origin", "main"])
        self.assertEqual(result, ["push", "origin", "main"])

    def test_constrained_push_builder_works(self):
        cmd = build_commit_push_command("msg", remote="origin", branch="main")
        self.assertEqual(cmd.args, ["push", "origin", "main"])


if __name__ == "__main__":
    unittest.main()
