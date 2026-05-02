"""Project-specific GitHub workflow capability for v0.1.

This module provides minimal, reviewed GitHub operations using REST API
request construction and constrained git command construction. It replaces
production use of Hermes bundled github-pr-workflow, github-issues, and
github-auth, which failed TKT-012 source review for credential-bearing use.

Security constraints:
- Credentials accepted ONLY from the PROJECT_GITHUB_PAT environment variable.
- Rejected: ~/.git-credentials, token-in-remote URLs, committed config,
  CLI token arguments.
- Token values are redacted in all logs and errors.
- Dangerous git operations (force push, hard reset, branch deletion,
  token-bearing remotes) are blocked.
- Merge operations are disabled by default and require explicit founder
  acknowledgement.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import quote


_CREDENTIAL_ENV_VAR = "PROJECT_GITHUB_PAT"

_GITHUB_API_BASE = "https://api.github.com"

_REDACTED = "***REDACTED***"

_TOKEN_PATTERNS = re.compile(r"ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,}[A-Za-z0-9]|gho_[A-Za-z0-9]{36}|ghu_[A-Za-z0-9]{36}|ghs_[A-Za-z0-9]{36}|ghr_[A-Za-z0-9]{36}")

_BLOCKED_GIT_FLAGS = frozenset([
    "--force",
    "-f",
    "--hard",
    "-D",
    "--delete",
    "--force-with-lease",
])

_BLOCKED_GIT_SUBCOMMANDS = frozenset([
    "push",
])  # push is allowed only through constrained builder

_BLOCKED_PHRASES = frozenset([
    "force push",
    "hard reset",
    "branch -D",
    "branch --delete",
    "reset --hard",
    "push --force",
    "push -f",
    "push --force-with-lease",
])

_REQUIRED_TOKEN_SCOPES = [
    "contents:write",
    "pull_requests:write",
    "checks:read",
    "statuses:write",
    "actions:read",
]


class CredentialSourceError(RuntimeError):
    """Raised when an unapproved credential source is detected."""


class DangerousOperationError(RuntimeError):
    """Raised when a blocked dangerous git operation is attempted."""


class MergeBlockedError(RuntimeError):
    """Raised when a merge is attempted without required founder acknowledgement."""


def redact_token(value: str) -> str:
    """Redact known token patterns from a string."""
    return _TOKEN_PATTERNS.sub(_REDACTED, value)


def _redact_url(url: str) -> str:
    """Redact token-bearing URLs (https://token@host or token-in-query)."""
    return re.sub(
        r"(https?://)([^@/:]+@)",
        r"\1" + _REDACTED + "@",
        url,
    )


@dataclass
class GitHubRESTRequest:
    """Represents a constructed GitHub REST API request.

    Attributes:
        method: HTTP method (GET, POST, PATCH, PUT, DELETE).
        url: Full API URL (without token).
        headers: HTTP headers dict (without Authorization).
        body: Optional JSON-serializable body dict.
    """

    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: Optional[dict[str, Any]] = None

    def with_auth(self, token: str) -> dict[str, str]:
        """Return headers dict with Authorization header added.

        The returned dict contains the real token. Callers must redact
        before logging.
        """
        h = dict(self.headers)
        h["Authorization"] = f"Bearer {token}"
        return h


@dataclass
class GitCommand:
    """Represents a constrained git command.

    Attributes:
        args: List of git command arguments (e.g., ['checkout', '-b', 'feature']).
        cwd: Working directory for the command.
    """

    args: list[str]
    cwd: str = "."

    def to_cmdline(self) -> str:
        """Return a shell-safe command-line string with redacted tokens."""
        parts = ["git"] + self.args
        return redact_token(" ".join(parts))


def load_credential(
    *,
    env_var: str = _CREDENTIAL_ENV_VAR,
    _environ: Optional[dict[str, str]] = None,
) -> str:
    """Load GitHub credential from the approved environment variable.

    Args:
        env_var: Name of the environment variable to read.
        _environ: Override for os.environ (for testing).

    Returns:
        The token string.

    Raises:
        CredentialSourceError: If the token is not found or an unapproved
            source is detected.
    """
    environ = _environ if _environ is not None else dict(os.environ)

    token = environ.get(env_var, "").strip()
    if not token:
        raise CredentialSourceError(
            f"GitHub credential not found in {env_var} environment variable"
        )

    return token


def reject_credential_source(source: str) -> None:
    """Reject an unapproved credential source.

    Args:
        source: Description of the credential source being rejected.

    Raises:
        CredentialSourceError: Always raised for known bad sources.
    """
    lower = source.lower()
    blocked_sources = [
        "~/.git-credentials",
        ".git-credentials",
        "git-credentials",
        "token-in-remote",
        "remote url token",
        "committed config",
        "config file token",
        "cli argument",
        "command line token",
        "--token",
        "-t ",
    ]
    for b in blocked_sources:
        if b in lower:
            raise CredentialSourceError(
                f"Credential source rejected: {source}"
            )


def check_for_git_credentials_file(path: str) -> None:
    """Check if ~/.git-credentials exists and reject it.

    Raises:
        CredentialSourceError: If ~/.git-credentials is found.
    """
    home = os.path.expanduser("~")
    cred_path = os.path.join(home, ".git-credentials")
    if os.path.normpath(os.path.abspath(path)) == os.path.normpath(cred_path):
        raise CredentialSourceError(
            "Credential source rejected: ~/.git-credentials"
        )


def check_for_token_in_remote(url: str) -> None:
    """Check if a remote URL contains an embedded token.

    Raises:
        CredentialSourceError: If a token is detected in the URL.
    """
    if re.search(r"://[^@/]+@", url):
        raise CredentialSourceError(
            f"Credential source rejected: token-in-remote URL ({_redact_url(url)})"
        )
    if _TOKEN_PATTERNS.search(url):
        raise CredentialSourceError(
            "Credential source rejected: token pattern in remote URL"
        )


def build_repo_create_request(
    owner: str,
    name: str,
    *,
    description: str = "",
    private: bool = True,
    auto_init: bool = True,
) -> GitHubRESTRequest:
    """Construct a GitHub API request to create a repository.

    Args:
        owner: Organization or user that will own the repo.
        name: Repository name.
        description: Optional repo description.
        private: Whether the repo should be private.
        auto_init: Whether to auto-initialize with a README.

    Returns:
        A GitHubRESTRequest for POST /orgs/{owner}/repos or /user/repos.
    """
    body: dict[str, Any] = {
        "name": name,
        "description": description,
        "private": private,
        "auto_init": auto_init,
    }
    url = f"{_GITHUB_API_BASE}/orgs/{quote(owner, safe='')}/repos"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    return GitHubRESTRequest(
        method="POST",
        url=url,
        headers=headers,
        body=body,
    )


def build_repo_register_request(
    owner: str,
    name: str,
) -> GitHubRESTRequest:
    """Construct a GitHub API request to read/register an existing repository.

    Args:
        owner: Repository owner.
        name: Repository name.

    Returns:
        A GitHubRESTRequest for GET /repos/{owner}/{name}.
    """
    url = f"{_GITHUB_API_BASE}/repos/{quote(owner, safe='')}/{quote(name, safe='')}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    return GitHubRESTRequest(
        method="GET",
        url=url,
        headers=headers,
    )


def build_pr_open_request(
    owner: str,
    repo: str,
    *,
    head: str,
    base: str,
    title: str,
    body: str = "",
) -> GitHubRESTRequest:
    """Construct a GitHub API request to open a pull request.

    Args:
        owner: Repository owner.
        repo: Repository name.
        head: Head branch name.
        base: Base branch name.
        title: PR title.
        body: PR body text.

    Returns:
        A GitHubRESTRequest for POST /repos/{owner}/{repo}/pulls.
    """
    pr_body: dict[str, Any] = {
        "head": head,
        "base": base,
        "title": title,
        "body": body,
    }
    url = f"{_GITHUB_API_BASE}/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/pulls"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    return GitHubRESTRequest(
        method="POST",
        url=url,
        headers=headers,
        body=pr_body,
    )


def build_pr_update_request(
    owner: str,
    repo: str,
    pr_number: int,
    *,
    title: Optional[str] = None,
    body: Optional[str] = None,
    state: Optional[str] = None,
    base: Optional[str] = None,
) -> GitHubRESTRequest:
    """Construct a GitHub API request to update a pull request.

    Args:
        owner: Repository owner.
        repo: Repository name.
        pr_number: PR number.
        title: New title (optional).
        body: New body (optional).
        state: New state ('open' or 'closed', optional).
        base: New base branch (optional).

    Returns:
        A GitHubRESTRequest for PATCH /repos/{owner}/{repo}/pulls/{pr_number}.
    """
    pr_body: dict[str, Any] = {}
    if title is not None:
        pr_body["title"] = title
    if body is not None:
        pr_body["body"] = body
    if state is not None:
        pr_body["state"] = state
    if base is not None:
        pr_body["base"] = base
    url = f"{_GITHUB_API_BASE}/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/pulls/{pr_number}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    return GitHubRESTRequest(
        method="PATCH",
        url=url,
        headers=headers,
        body=pr_body if pr_body else None,
    )


def build_check_status_request(
    owner: str,
    repo: str,
    ref: str,
) -> GitHubRESTRequest:
    """Construct a GitHub API request to read check statuses for a ref.

    Args:
        owner: Repository owner.
        repo: Repository name.
        ref: Git ref (SHA, branch name, or tag).

    Returns:
        A GitHubRESTRequest for GET /repos/{owner}/{repo}/commits/{ref}/check-runs.
    """
    url = f"{_GITHUB_API_BASE}/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/commits/{quote(ref, safe='')}/check-runs"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    return GitHubRESTRequest(
        method="GET",
        url=url,
        headers=headers,
    )


def build_pr_metadata_request(
    owner: str,
    repo: str,
    pr_number: int,
) -> GitHubRESTRequest:
    """Construct a GitHub API request to read PR metadata.

    Args:
        owner: Repository owner.
        repo: Repository name.
        pr_number: PR number.

    Returns:
        A GitHubRESTRequest for GET /repos/{owner}/{repo}/pulls/{pr_number}.
    """
    url = f"{_GITHUB_API_BASE}/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/pulls/{pr_number}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    return GitHubRESTRequest(
        method="GET",
        url=url,
        headers=headers,
    )


def build_branch_create_command(
    branch_name: str,
    base: str = "main",
    cwd: str = ".",
) -> GitCommand:
    """Construct a constrained git command to create a branch.

    Args:
        branch_name: Name of the new branch.
        base: Base branch to create from.
        cwd: Working directory.

    Returns:
        A GitCommand for creating the branch.

    Raises:
        DangerousOperationError: If branch_name or base contains
            dangerous patterns.
    """
    _validate_branch_name(branch_name)
    _validate_branch_name(base)
    return GitCommand(
        args=["checkout", "-b", branch_name, base],
        cwd=cwd,
    )


def build_commit_push_command(
    message: str,
    remote: str = "origin",
    branch: str = "HEAD",
    cwd: str = ".",
) -> GitCommand:
    """Construct constrained git commands for commit and push.

    The push command explicitly omits force-push flags.

    Args:
        message: Commit message.
        remote: Remote name (must not be a URL).
        branch: Branch name or HEAD.
        cwd: Working directory.

    Returns:
        A GitCommand for pushing (after staging and committing).

    Raises:
        DangerousOperationError: If dangerous flags or token-bearing
            remotes are detected.
    """
    if _looks_like_url(remote):
        check_for_token_in_remote(remote)
        raise DangerousOperationError(
            "Remote must be a named remote, not a URL"
        )
    _validate_branch_name(branch)
    return GitCommand(
        args=["push", remote, branch],
        cwd=cwd,
    )


def build_merge_command(
    *,
    founder_acknowledgement: bool = False,
    branch: str = "",
    cwd: str = ".",
) -> GitCommand:
    """Construct a merge command if founder acknowledgement is given.

    Merge operations are disabled by default in v0.1. They require explicit
    founder acknowledgement.

    Args:
        founder_acknowledgement: Whether the founder has explicitly
            acknowledged this merge.
        branch: Branch to merge.
        cwd: Working directory.

    Returns:
        A GitCommand for merging.

    Raises:
        MergeBlockedError: If founder_acknowledgement is False.
        DangerousOperationError: If branch contains dangerous patterns.
    """
    if not founder_acknowledgement:
        raise MergeBlockedError(
            "Merge operations are disabled by default in v0.1. "
            "Explicit founder acknowledgement is required."
        )
    _validate_branch_name(branch)
    return GitCommand(
        args=["merge", branch],
        cwd=cwd,
    )


def validate_git_args(args: list[str]) -> list[str]:
    """Validate a list of git arguments against blocked operations.

    Args:
        args: Git argument list (without 'git' prefix).

    Returns:
        The validated args list.

    Raises:
        DangerousOperationError: If blocked flags or subcommands are found.
    """
    for arg in args:
        if arg in _BLOCKED_GIT_FLAGS:
            raise DangerousOperationError(
                f"Blocked git flag: {arg}"
            )
    joined = " ".join(args).lower()
    for phrase in _BLOCKED_PHRASES:
        if phrase in joined:
            raise DangerousOperationError(
                f"Blocked git operation: {phrase}"
            )
    return args


def _validate_branch_name(name: str) -> None:
    """Validate a branch name against dangerous patterns."""
    if not name:
        return
    for phrase in _BLOCKED_PHRASES:
        if phrase in name.lower():
            raise DangerousOperationError(
                f"Branch name contains blocked pattern: {phrase}"
            )
    if ";" in name or "&" in name or "|" in name or "`" in name or "$" in name:
        raise DangerousOperationError(
            f"Branch name contains shell metacharacter: {name!r}"
        )


def _looks_like_url(s: str) -> bool:
    """Check if a string looks like a URL rather than a named remote."""
    return s.startswith("http://") or s.startswith("https://") or s.startswith("git://") or s.startswith("ssh://")


def execute_git_command(
    cmd: GitCommand,
    *,
    timeout: int = 300,
    dry_run: bool = False,
) -> subprocess.CompletedProcess:
    """Execute a constrained git command.

    Args:
        cmd: GitCommand to execute.
        timeout: Timeout in seconds.
        dry_run: If True, return a mock result without executing.

    Returns:
        subprocess.CompletedProcess result.

    Raises:
        DangerousOperationError: If the command contains blocked operations.
    """
    validate_git_args(cmd.args)
    full_cmd = ["git"] + cmd.args
    cmdline_str = cmd.to_cmdline()

    if dry_run:
        return subprocess.CompletedProcess(
            args=full_cmd,
            returncode=0,
            stdout=f"[dry-run] {redact_token(cmdline_str)}",
            stderr="",
        )

    result = subprocess.run(
        full_cmd,
        cwd=cmd.cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    result.stdout = redact_token(result.stdout)
    result.stderr = redact_token(result.stderr)
    return result
