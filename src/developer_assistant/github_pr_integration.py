"""GitHub repository and PR integration layer for v0.1.

This module wires the project-specific GitHub workflow capability from TKT-014
(github_workflow.py) into the runtime/orchestration path required by TKT-008.

It provides:
- Repository create/register through the TKT-014 REST request path
- Branch creation and PR open linked to one ticket
- CI/check status read through the TKT-014 REST request path
- Reviewer artifact reference/attachment under docs/reviews/
- Founder acknowledgement merge gate (enforced even beyond TKT-014's
  build_merge_command gate)
- Telegram status/progress composition that includes repo, PR, CI, review-gate,
  and ticket state without treating Telegram chat history as authoritative

Security constraints:
- Credentials accepted ONLY from PROJECT_GITHUB_PAT via load_credential().
- GITHUB_TOKEN, GH_TOKEN, ~/.git-credentials, token-bearing remotes,
  committed config, and CLI arguments are NOT accepted as fallback.
- Hermes bundled github-pr-workflow, github-issues, and github-auth remain
  blocked for production credential-bearing use.
- Token values are redacted in all rendered text and error messages.
- No autonomous merges; founder acknowledgement required in v0.1.
- Telegram chat history must not become authoritative state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol

from src.developer_assistant.github_workflow import (
    CredentialSourceError,
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
    load_credential,
    redact_token,
)


_REDACTED = "***REDACTED***"


def _redact_url(url: str) -> str:
    """Redact credential-bearing URL patterns, then token patterns."""
    redacted = re.sub(
        r"(https?://)([^@/:]+@)",
        r"\1" + _REDACTED + "@",
        url,
    )
    return redact_token(redacted)


def _redact_value(value: Any) -> Any:
    """Recursively redact token and credential-bearing strings in a value.

    Preserves container shapes (dict, list, tuple) and non-string scalars.
    Returns a sanitized copy; the original object is not mutated.
    """
    if isinstance(value, str):
        return _redact_url(value)
    if isinstance(value, dict):
        return {k: _redact_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    return value


class RESTExecutor(Protocol):
    """Protocol for executing constructed REST requests."""

    def execute(self, request: GitHubRESTRequest, token: str) -> Dict[str, Any]:
        ...


class GitExecutor(Protocol):
    """Protocol for executing constructed git commands."""

    def execute(self, cmd: GitCommand) -> int:
        ...


class _NullRESTExecutor:
    def execute(self, request: GitHubRESTRequest, token: str) -> Dict[str, Any]:
        return {}


class _NullGitExecutor:
    def execute(self, cmd: GitCommand) -> int:
        return 0


@dataclass
class ReviewGateState:
    """Tracks review-gate state linked to a PR and ticket."""

    review_artifact_path: str = ""
    verdict: str = ""
    reviewer: str = ""
    date: str = ""

    def is_valid_artifact_path(self) -> bool:
        if not self.review_artifact_path:
            return False
        return (
            self.review_artifact_path.startswith("docs/reviews/")
            and self.review_artifact_path.endswith(".md")
        )

    def to_status_text(self) -> str:
        if not self.review_artifact_path:
            return "no review"
        verdict_text = self.verdict if self.verdict else "pending"
        return f"{verdict_text} ({self.review_artifact_path})"


@dataclass
class PRCheckState:
    """CI/check status for a PR."""

    check_name: str = ""
    status: str = ""
    conclusion: str = ""

    def to_status_text(self) -> str:
        if self.status == "completed" and self.conclusion:
            return f"{self.check_name}: {self.conclusion}"
        if self.status:
            return f"{self.check_name}: {self.status}"
        return "no checks"


@dataclass
class ProjectGitHubState:
    """Composite GitHub state for a project, used for Telegram composition."""

    repo_owner: str = ""
    repo_name: str = ""
    repo_url: str = ""
    active_branch: str = ""
    active_pr_number: int = 0
    active_pr_url: str = ""
    active_pr_state: str = ""
    linked_ticket: str = ""
    check_state: Optional[PRCheckState] = None
    review_gate: Optional[ReviewGateState] = None
    founder_acknowledged: bool = False

    @property
    def repo_full_name(self) -> str:
        if self.repo_owner and self.repo_name:
            return f"{self.repo_owner}/{self.repo_name}"
        return ""

    def to_russian_status(self) -> str:
        """Render GitHub state as Russian text for Telegram /status."""
        lines: List[str] = []
        if self.repo_full_name:
            lines.append(f"Репозиторий: {redact_token(self.repo_full_name)}")
        if self.repo_url:
            lines.append(f"URL: {redact_token(self.repo_url)}")
        if self.active_branch:
            lines.append(f"Ветка: {self.active_branch}")
        if self.active_pr_number:
            pr_state = self.active_pr_state or "unknown"
            lines.append(f"PR #{self.active_pr_number}: {pr_state}")
        if self.linked_ticket:
            lines.append(f"Тикет: {self.linked_ticket}")
        if self.check_state:
            lines.append(f"CI: {self.check_state.to_status_text()}")
        if self.review_gate:
            lines.append(f"Ревью: {self.review_gate.to_status_text()}")
        merge_gate = "подтверждено основателем" if self.founder_acknowledged else "требуется подтверждение основателя"
        lines.append(f"Мерж-гейт: {merge_gate}")
        return "\n".join(lines)

    def to_progress_text(self) -> str:
        """Render GitHub state as a progress summary for Telegram reports."""
        parts: List[str] = []
        if self.repo_full_name:
            parts.append(f"Репо: {redact_token(self.repo_full_name)}")
        if self.active_pr_number:
            parts.append(f"PR #{self.active_pr_number}")
        if self.check_state:
            parts.append(f"CI: {self.check_state.to_status_text()}")
        if self.review_gate:
            parts.append(f"Ревью: {self.review_gate.to_status_text()}")
        return " | ".join(parts) if parts else "no GitHub state"


class IntegrationError(RuntimeError):
    """Raised when an integration operation fails."""


class MergeGateError(RuntimeError):
    """Raised when a merge is attempted without founder acknowledgement."""


class GitHubPRIntegration:
    """High-level GitHub PR integration layer.

    Wires TKT-014's project-specific GitHub workflow capability into the
    runtime/orchestration path. Uses load_credential() as the single
    credential entry point and composes GitHub state for Telegram founder
    interaction.

    All network calls are injectable through RESTExecutor and GitExecutor
    protocols, enabling fully mocked unit tests without live GitHub access.
    """

    def __init__(
        self,
        rest_executor: RESTExecutor = _NullRESTExecutor(),
        git_executor: GitExecutor = _NullGitExecutor(),
        *,
        _environ: Optional[Dict[str, str]] = None,
    ) -> None:
        self._rest_executor = rest_executor
        self._git_executor = git_executor
        self._environ = _environ
        self._project_states: Dict[str, ProjectGitHubState] = {}
        self._review_gates: Dict[str, ReviewGateState] = {}

    def _load_token(self, remote_url: Optional[str] = None) -> str:
        """Load credential through load_credential() only."""
        kwargs: Dict[str, Any] = {}
        if self._environ is not None:
            kwargs["_environ"] = self._environ
        if remote_url is not None:
            kwargs["remote_url"] = remote_url
        return load_credential(**kwargs)

    def register_repository(
        self,
        project_key: str,
        owner: str,
        name: str,
        *,
        create: bool = False,
        private: bool = True,
    ) -> ProjectGitHubState:
        """Create or register a GitHub repository for a project.

        Args:
            project_key: Project identifier (e.g., sanitized Telegram chat key).
            owner: Repository owner.
            name: Repository name.
            create: If True, create the repo; if False, register existing.
            private: Whether the repo should be private (create mode only).

        Returns:
            Updated ProjectGitHubState for the project.

        Raises:
            IntegrationError: If the REST operation fails.
            CredentialSourceError: If credential source is invalid.
        """
        token = self._load_token()

        if create:
            request = build_repo_create_request(owner, name, private=private)
        else:
            request = build_repo_register_request(owner, name)

        try:
            result = self._rest_executor.execute(request, token)
        except Exception as exc:
            raise IntegrationError(
                f"Repository {'create' if create else 'register'} failed: "
                f"{redact_token(str(exc))}"
            ) from exc

        state = self._ensure_project_state(project_key)
        state.repo_owner = owner
        state.repo_name = name
        repo_url = result.get("html_url", "")
        state.repo_url = _redact_url(repo_url)

        return state

    def create_branch_and_open_pr(
        self,
        project_key: str,
        ticket_id: str,
        branch_name: str,
        *,
        pr_title: str,
        pr_body: str = "",
        base: str = "main",
        cwd: str = ".",
    ) -> ProjectGitHubState:
        """Create a branch and open a PR linked to one ticket.

        Args:
            project_key: Project identifier.
            ticket_id: Ticket ID to link (e.g., TKT-008).
            branch_name: Name of the new branch.
            pr_title: PR title.
            pr_body: PR body text.
            base: Base branch name.
            cwd: Working directory for git commands.

        Returns:
            Updated ProjectGitHubState with branch and PR info.

        Raises:
            IntegrationError: If the operation fails.
            CredentialSourceError: If credential source is invalid.
        """
        state = self._ensure_project_state(project_key)
        if not state.repo_owner or not state.repo_name:
            raise IntegrationError(
                "Repository must be registered before creating a branch/PR"
            )

        token = self._load_token()

        cmd = build_branch_create_command(branch_name, base=base, cwd=cwd)
        try:
            rc = self._git_executor.execute(cmd)
        except Exception as exc:
            raise IntegrationError(
                f"Branch creation failed: {redact_token(str(exc))}"
            ) from exc
        if rc != 0:
            raise IntegrationError(
                f"Branch creation returned non-zero exit code: {rc}"
            )

        full_pr_body = f"Linked ticket: {ticket_id}\n\n{pr_body}" if pr_body else f"Linked ticket: {ticket_id}"
        request = build_pr_open_request(
            state.repo_owner,
            state.repo_name,
            head=branch_name,
            base=base,
            title=pr_title,
            body=full_pr_body,
        )

        try:
            result = self._rest_executor.execute(request, token)
        except Exception as exc:
            raise IntegrationError(
                f"PR open failed: {redact_token(str(exc))}"
            ) from exc

        state.active_branch = branch_name
        state.active_pr_number = result.get("number", 0)
        pr_url = result.get("html_url", "")
        state.active_pr_url = _redact_url(pr_url)
        state.active_pr_state = result.get("state", "open")
        state.linked_ticket = ticket_id
        state.founder_acknowledged = False

        return state

    def read_check_status(
        self,
        project_key: str,
        ref: str,
    ) -> PRCheckState:
        """Read CI/check status for a PR ref.

        Args:
            project_key: Project identifier.
            ref: Git ref (SHA, branch name, or tag).

        Returns:
            PRCheckState with check results.

        Raises:
            IntegrationError: If the REST operation fails.
            CredentialSourceError: If credential source is invalid.
        """
        state = self._ensure_project_state(project_key)
        if not state.repo_owner or not state.repo_name:
            raise IntegrationError(
                "Repository must be registered before reading check status"
            )

        token = self._load_token()

        request = build_check_status_request(
            state.repo_owner, state.repo_name, ref
        )

        try:
            result = self._rest_executor.execute(request, token)
        except Exception as exc:
            raise IntegrationError(
                f"Check status read failed: {redact_token(str(exc))}"
            ) from exc

        check_runs = result.get("check_runs", [])
        if check_runs:
            first = check_runs[0]
            check_state = PRCheckState(
                check_name=first.get("name", ""),
                status=first.get("status", ""),
                conclusion=first.get("conclusion", ""),
            )
        else:
            check_state = PRCheckState()

        state.check_state = check_state
        return check_state

    def read_pr_metadata(
        self,
        project_key: str,
        pr_number: int,
    ) -> Dict[str, Any]:
        """Read PR metadata through the integration path.

        Args:
            project_key: Project identifier.
            pr_number: PR number.

        Returns:
            PR metadata dict (redacted of any tokens).

        Raises:
            IntegrationError: If the REST operation fails.
            CredentialSourceError: If credential source is invalid.
        """
        state = self._ensure_project_state(project_key)
        if not state.repo_owner or not state.repo_name:
            raise IntegrationError(
                "Repository must be registered before reading PR metadata"
            )

        token = self._load_token()

        request = build_pr_metadata_request(
            state.repo_owner, state.repo_name, pr_number
        )

        try:
            result = self._rest_executor.execute(request, token)
        except Exception as exc:
            raise IntegrationError(
                f"PR metadata read failed: {redact_token(str(exc))}"
            ) from exc

        state.active_pr_state = result.get("state", state.active_pr_state)
        return _redact_value(result)

    def attach_review_artifact(
        self,
        project_key: str,
        artifact_path: str,
        *,
        verdict: str = "",
        reviewer: str = "",
        date: str = "",
    ) -> ReviewGateState:
        """Attach or reference a Reviewer artifact under docs/reviews/.

        This records review-gate state by linking a docs/reviews/RV-CODE-*.md
        path to PR/ticket metadata. It does not write the review artifact body.

        Args:
            project_key: Project identifier.
            artifact_path: Path under docs/reviews/ (e.g., docs/reviews/RV-CODE-019.md).
            verdict: Review verdict (pass, pass_with_changes, fail).
            reviewer: Reviewer identifier.
            date: Date of the review.

        Returns:
            ReviewGateState for the project.

        Raises:
            IntegrationError: If the artifact path is invalid.
        """
        gate = ReviewGateState(
            review_artifact_path=artifact_path,
            verdict=verdict,
            reviewer=reviewer,
            date=date,
        )

        if not gate.is_valid_artifact_path():
            raise IntegrationError(
                f"Invalid review artifact path: {artifact_path}. "
                f"Must start with docs/reviews/ and end with .md"
            )

        state = self._ensure_project_state(project_key)
        state.review_gate = gate
        self._review_gates[project_key] = gate
        return gate

    def check_merge_gate(
        self,
        project_key: str,
        *,
        founder_acknowledgement: bool = False,
    ) -> GitCommand:
        """Check the founder acknowledgement merge gate and return a merge
        command if allowed.

        This enforces founder acknowledgement before merge as an integration
        layer gate, even beyond the underlying TKT-014 build_merge_command()
        enforcement.

        Args:
            project_key: Project identifier.
            founder_acknowledgement: Whether the founder has explicitly
                acknowledged this merge.

        Returns:
            GitCommand for merging.

        Raises:
            MergeGateError: If founder acknowledgement is not given.
            IntegrationError: If no branch is available to merge.
        """
        state = self._ensure_project_state(project_key)

        if not state.active_branch:
            raise IntegrationError(
                "No active branch to merge"
            )

        if not founder_acknowledgement:
            raise MergeGateError(
                "Merge blocked: founder acknowledgement required in v0.1. "
                "The integration layer does not allow autonomous merges."
            )

        cmd = build_merge_command(
            founder_acknowledgement=True,
            branch=state.active_branch,
        )

        state.founder_acknowledged = True
        return cmd

    def get_project_state(self, project_key: str) -> ProjectGitHubState:
        """Return the current ProjectGitHubState for a project."""
        return self._ensure_project_state(project_key)

    def update_project_state(
        self,
        project_key: str,
        *,
        repo_owner: Optional[str] = None,
        repo_name: Optional[str] = None,
        repo_url: Optional[str] = None,
        active_branch: Optional[str] = None,
        active_pr_number: Optional[int] = None,
        active_pr_url: Optional[str] = None,
        active_pr_state: Optional[str] = None,
        linked_ticket: Optional[str] = None,
        check_state: Optional[PRCheckState] = None,
        review_gate: Optional[ReviewGateState] = None,
        founder_acknowledged: Optional[bool] = None,
    ) -> ProjectGitHubState:
        """Update ProjectGitHubState fields for a project."""
        state = self._ensure_project_state(project_key)
        if repo_owner is not None:
            state.repo_owner = repo_owner
        if repo_name is not None:
            state.repo_name = repo_name
        if repo_url is not None:
            state.repo_url = _redact_url(repo_url)
        if active_branch is not None:
            state.active_branch = active_branch
        if active_pr_number is not None:
            state.active_pr_number = active_pr_number
        if active_pr_url is not None:
            state.active_pr_url = _redact_url(active_pr_url)
        if active_pr_state is not None:
            state.active_pr_state = active_pr_state
        if linked_ticket is not None:
            state.linked_ticket = linked_ticket
        if check_state is not None:
            state.check_state = check_state
        if review_gate is not None:
            state.review_gate = review_gate
        if founder_acknowledged is not None:
            state.founder_acknowledged = founder_acknowledged
        return state

    def compose_telegram_status(self, project_key: str) -> str:
        """Compose Russian-language Telegram /status text with GitHub state.

        Returns a status string that includes repository, PR, CI, review-gate,
        and ticket state. Repository artifacts remain authoritative; Telegram
        chat history must not become authoritative state.
        """
        state = self._ensure_project_state(project_key)
        return state.to_russian_status()

    def compose_telegram_progress(self, project_key: str) -> str:
        """Compose a short progress summary for Telegram with GitHub state.

        Returns a compact text suitable for progress reports.
        """
        state = self._ensure_project_state(project_key)
        return state.to_progress_text()

    def _ensure_project_state(self, project_key: str) -> ProjectGitHubState:
        if project_key not in self._project_states:
            self._project_states[project_key] = ProjectGitHubState()
        return self._project_states[project_key]


def compose_github_aware_progress_report(
    project_key: str,
    integration: GitHubPRIntegration,
    completed: str,
    current_action: str,
    blocker_state: str,
    decisions_needed: str,
    notable_risks: str,
) -> str:
    """Compose a ProgressReport-compatible Russian text that includes
    GitHub PR/check/review-gate state.

    This function composes GitHub state with the TKT-006 Telegram founder
    interaction logic so /status, progress, and approval-oriented messages
    can reference repository, PR, CI, and review-gate state without treating
    Telegram chat history as authoritative.

    Returns a full Russian-language progress report string.
    """
    github_text = integration.compose_telegram_progress(project_key)
    return (
        f"Завершено: {completed}\n"
        f"Текущее действие: {current_action}\n"
        f"Блокеры: {blocker_state}\n"
        f"Требуются решения: {decisions_needed}\n"
        f"Риски: {notable_risks}\n"
        f"GitHub: {github_text}"
    )
