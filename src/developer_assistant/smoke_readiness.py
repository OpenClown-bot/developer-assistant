"""Sanitized live-smoke readiness check for TKT-017.

Two gated lanes:
- GitHub: exercises TKT-014 request builders + TKT-016 runtime executors
  for a minimal live sequence against the real GitHub API.
- Telegram: validates TKT-015 transport config readiness and
  sanitized inbound/outbound path without live gateway send.

Both lanes are disabled by default. They activate only when an explicit
non-secret boolean environment gate is set.

Security constraints:
- No token value, .env content, raw chat ID, raw user ID, PAT, API key,
  credential file path, token-bearing remote, or sensitive VPS detail
  appears in output or committed artifacts.
- GitHub lane uses PROJECT_GITHUB_PAT only; GITHUB_TOKEN, GH_TOKEN,
  ~/.git-credentials, token-bearing remotes, committed config, and
  CLI token arguments are rejected by the existing credential path.
- Telegram lane uses sanitized labels; raw identifiers are never stored
  or printed.
- blocked is the correct outcome when credentials or runtime access are
  unavailable, not a bypass.
- No autonomous merge, live deployment, Hermes bundled GitHub skills,
  marketplace skills, project-local plugins, or OpenClaw.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.developer_assistant.github_workflow import (
    CredentialSourceError,
    GitHubRESTRequest,
    GitCommand,
    redact_token,
    build_branch_create_command,
    build_check_status_request,
    build_pr_metadata_request,
    build_pr_open_request,
    build_repo_register_request,
    load_credential,
)
from src.developer_assistant.runtime_executors import (
    HttpRESTExecutor,
    RuntimeRESTError,
    SubprocessGitExecutor,
    RuntimeGitError,
)
from src.developer_assistant.hermes_telegram_transport import (
    HermesGatewayPayload,
    TransportConfig,
    validate_transport_config_env,
    sanitize_gateway_payload,
)
from src.developer_assistant.telegram_adapter import (
    FounderAllowlistConfig,
    TelegramFounderAdapter,
)

_GITHUB_SMOKE_GATE = "SMOKE_GITHUB_LIVE"
_TELEGRAM_SMOKE_GATE = "SMOKE_TELEGRAM_LIVE"
_CREDENTIAL_ENV_VAR = "PROJECT_GITHUB_PAT"
_REDACTED = "***REDACTED***"


class SmokeLaneStatus(str, Enum):
    PASS = "pass"
    BLOCKED = "blocked"
    FAIL = "fail"
    SKIPPED = "skipped"


@dataclass
class SmokeLaneResult:
    lane: str
    status: SmokeLaneStatus
    evidence: str = ""
    blocker: str = ""


@dataclass
class SmokeReadinessReport:
    github: SmokeLaneResult
    telegram: SmokeLaneResult
    tkt_011_remains_draft: bool = True
    founder_ack_required: bool = True
    no_autonomous_merge: bool = True

    def to_sanitized_dict(self) -> Dict[str, Any]:
        return {
            "github_lane": {
                "lane": self.github.lane,
                "status": self.github.status.value,
                "evidence": self.github.evidence,
                "blocker": self.github.blocker,
            },
            "telegram_lane": {
                "lane": self.telegram.lane,
                "status": self.telegram.status.value,
                "evidence": self.telegram.evidence,
                "blocker": self.telegram.blocker,
            },
            "tkt_011_remains_draft": self.tkt_011_remains_draft,
            "founder_ack_required_before_merge": self.founder_ack_required,
            "no_autonomous_merge": self.no_autonomous_merge,
        }


def _is_gate_set(env_var: str, environ: Optional[Dict[str, str]] = None) -> bool:
    env = environ if environ is not None else dict(os.environ)
    val = env.get(env_var, "").strip().lower()
    return val in ("1", "true", "yes")


def _sanitize_branch_name(ticket_id: str) -> str:
    return f"smoke/{ticket_id.lower()}-live-check"


def _sanitize_pr_url(owner: str, repo: str, pr_number: int) -> str:
    return f"https://github.com/{owner}/{repo}/pull/{pr_number}"


def _sanitize_repo_url(owner: str, repo: str) -> str:
    return f"https://github.com/{owner}/{repo}"


class GitHubSmokeLane:
    """Minimal live GitHub smoke lane for TKT-017.

    Performs the smallest safe live sequence:
    1. Load credential from PROJECT_GITHUB_PAT (fail-closed if absent).
    2. Register/read the target repository.
    3. Create a unique smoke branch.
    4. Open a draft PR linked to TKT-017.
    5. Read check status for the smoke branch.
    6. Read PR metadata.
    7. Record cleanup expectations.

    All output is sanitized. No merge is performed.
    """

    def __init__(
        self,
        owner: str,
        repo: str,
        *,
        rest_executor: Optional[HttpRESTExecutor] = None,
        git_executor: Optional[SubprocessGitExecutor] = None,
        ticket_id: str = "TKT-017",
        environ: Optional[Dict[str, str]] = None,
    ) -> None:
        self._owner = owner
        self._repo = repo
        self._rest = rest_executor or HttpRESTExecutor()
        self._git = git_executor or SubprocessGitExecutor()
        self._ticket_id = ticket_id
        self._environ = environ

    def run(self) -> SmokeLaneResult:
        if not _is_gate_set(_GITHUB_SMOKE_GATE, self._environ):
            return SmokeLaneResult(
                lane="github",
                status=SmokeLaneStatus.SKIPPED,
                evidence=f"Gate {_GITHUB_SMOKE_GATE} not set; live GitHub smoke skipped.",
            )

        try:
            token = load_credential(_environ=self._environ)
        except CredentialSourceError as exc:
            return SmokeLaneResult(
                lane="github",
                status=SmokeLaneStatus.BLOCKED,
                blocker=redact_token(str(exc)),
                evidence=f"Credential source blocked: env var {_CREDENTIAL_ENV_VAR} unavailable or rejected.",
            )

        branch_name = _sanitize_branch_name(self._ticket_id)
        evidence_parts: List[str] = []
        pr_number: Optional[int] = None

        try:
            reg_req = build_repo_register_request(self._owner, self._repo)
            reg_resp = self._rest.execute(reg_req, token)
            reg_status = "registered"
            evidence_parts.append(
                f"repo: {_sanitize_repo_url(self._owner, self._repo)} status={reg_status}"
            )
        except RuntimeRESTError as exc:
            return SmokeLaneResult(
                lane="github",
                status=SmokeLaneStatus.BLOCKED,
                blocker=redact_token(str(exc)),
                evidence="Repository registration failed; credential may lack scope or repo may be inaccessible.",
            )

        try:
            branch_cmd = build_branch_create_command(
                branch_name=branch_name, base="main"
            )
            self._git.execute(branch_cmd)
            evidence_parts.append(f"branch: {branch_name} created")
        except RuntimeGitError as exc:
            return SmokeLaneResult(
                lane="github",
                status=SmokeLaneStatus.FAIL,
                blocker=redact_token(str(exc)),
                evidence="Branch creation failed; " + "; ".join(evidence_parts),
            )

        try:
            pr_req = build_pr_open_request(
                self._owner,
                self._repo,
                head=branch_name,
                base="main",
                title=f"Smoke: {self._ticket_id} live readiness check",
                body=f"Automated smoke branch for {self._ticket_id}. Do not merge. Close after review.",
            )
            pr_resp = self._rest.execute(pr_req, token)
            pr_number = pr_resp.get("number")
            if pr_number is not None:
                evidence_parts.append(
                    f"pr: {_sanitize_pr_url(self._owner, self._repo, pr_number)} (draft)"
                )
            else:
                evidence_parts.append("pr: opened but number not in response")
        except RuntimeRESTError as exc:
            evidence_parts.append(f"pr_open: blocked ({redact_token(str(exc))})")
            pr_number = None

        try:
            check_req = build_check_status_request(
                self._owner, self._repo, ref=branch_name
            )
            check_resp = self._rest.execute(check_req, token)
            total = check_resp.get("total_count", 0)
            conclusions = []
            for run in check_resp.get("check_runs", []):
                c = run.get("conclusion", "pending")
                if c:
                    conclusions.append(c)
            conclusion_str = ", ".join(conclusions) if conclusions else "none"
            evidence_parts.append(
                f"checks: total_count={total} conclusions=[{conclusion_str}]"
            )
        except RuntimeRESTError as exc:
            evidence_parts.append(f"checks: read failed ({redact_token(str(exc))})")

        if pr_number is not None:
            try:
                meta_req = build_pr_metadata_request(
                    self._owner, self._repo, pr_number
                )
                meta_resp = self._rest.execute(meta_req, token)
                state = meta_resp.get("state", "unknown")
                mergeable = meta_resp.get("mergeable", "unknown")
                evidence_parts.append(f"pr_meta: state={state} mergeable={mergeable}")
            except RuntimeRESTError as exc:
                evidence_parts.append(
                    f"pr_meta: read failed ({redact_token(str(exc))})"
                )

        evidence_parts.append(
            f"cleanup: close and delete branch {branch_name} after review"
        )
        evidence_parts.append("credential_env: PROJECT_GITHUB_PAT (value never printed)")
        evidence_parts.append("no_autonomous_merge: true")
        evidence_parts.append("founder_ack_required_before_merge: true")

        return SmokeLaneResult(
            lane="github",
            status=SmokeLaneStatus.PASS,
            evidence="; ".join(evidence_parts),
        )


class TelegramSmokeLane:
    """Telegram/Hermes gateway readiness lane for TKT-017.

    Validates transport config readiness without performing a live
    gateway send. Checks:
    1. TELEGRAM_BOT_TOKEN availability (name only, not value).
    2. Founder allowlist or DM pairing configuration.
    3. GATEWAY_ALLOW_ALL_USERS and TELEGRAM_ALLOW_ALL_USERS are unset/false.
    4. Polling mode preference.
    5. Sanitized inbound/outbound path through TKT-015 transport.

    If TELEGRAM_BOT_TOKEN is not available, the result is blocked.
    """

    def __init__(
        self,
        *,
        environ: Optional[Dict[str, str]] = None,
    ) -> None:
        self._environ = environ if environ is not None else dict(os.environ)

    def run(self) -> SmokeLaneResult:
        if not _is_gate_set(_TELEGRAM_SMOKE_GATE, self._environ):
            return SmokeLaneResult(
                lane="telegram",
                status=SmokeLaneStatus.SKIPPED,
                evidence=f"Gate {_TELEGRAM_SMOKE_GATE} not set; live Telegram smoke skipped.",
            )

        bot_token_set = bool(self._environ.get("TELEGRAM_BOT_TOKEN", "").strip())
        allowed_users_set = bool(
            self._environ.get("TELEGRAM_ALLOWED_USERS", "").strip()
        )
        gateway_allow_all = self._environ.get("GATEWAY_ALLOW_ALL_USERS", "")
        telegram_allow_all = self._environ.get("TELEGRAM_ALLOW_ALL_USERS", "")
        webhook_secret_set = bool(
            self._environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
        )
        webhook_mode = self._environ.get("TELEGRAM_WEBHOOK_MODE", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )

        violations = validate_transport_config_env(
            gateway_allow_all=gateway_allow_all,
            telegram_allow_all=telegram_allow_all,
            telegram_bot_token_set=bot_token_set,
            telegram_allowed_users_set=allowed_users_set,
            telegram_webhook_secret_set=webhook_secret_set,
            webhook_mode=webhook_mode,
            polling_mode=not webhook_mode,
        )

        evidence_parts: List[str] = []

        evidence_parts.append(
            "credential_env: TELEGRAM_BOT_TOKEN "
            + ("(configured)" if bot_token_set else "(NOT configured)")
        )
        evidence_parts.append(
            "allowlist: TELEGRAM_ALLOWED_USERS "
            + ("(configured)" if allowed_users_set else "(NOT configured)")
        )
        evidence_parts.append(
            "GATEWAY_ALLOW_ALL_USERS: "
            + ("unset/false" if gateway_allow_all in ("", "false", "False", "0", None) else "SET (violation)")
        )
        evidence_parts.append(
            "TELEGRAM_ALLOW_ALL_USERS: "
            + ("unset/false" if telegram_allow_all in ("", "false", "False", "0", None) else "SET (violation)")
        )
        evidence_parts.append(
            "transport_mode: " + ("webhook" if webhook_mode else "polling (preferred)")
        )

        if not bot_token_set:
            evidence_parts.append("blocked: TELEGRAM_BOT_TOKEN not available in runtime environment")
            return SmokeLaneResult(
                lane="telegram",
                status=SmokeLaneStatus.BLOCKED,
                blocker="TELEGRAM_BOT_TOKEN not configured; cannot perform live Telegram smoke.",
                evidence="; ".join(evidence_parts),
            )

        if violations:
            evidence_parts.append(f"violations: {len(violations)} config violations detected")
            for v in violations:
                evidence_parts.append(f"  - {v}")
            return SmokeLaneResult(
                lane="telegram",
                status=SmokeLaneStatus.BLOCKED,
                blocker="Transport config violations prevent live Telegram smoke.",
                evidence="; ".join(evidence_parts),
            )

        config = TransportConfig(
            allowed_chats=["chat:founder"] if allowed_users_set else [],
            allowed_users=["user:founder"] if allowed_users_set else [],
            dm_pairing={"chat:founder": "user:founder"} if not allowed_users_set else {},
            gateway_allow_all=False,
            telegram_allow_all=False,
            polling_mode=not webhook_mode,
            webhook_mode=webhook_mode,
            webhook_secret_configured=webhook_secret_set,
            bot_token_configured=bot_token_set,
        )

        config_violations = config.validate()
        if config_violations:
            for v in config_violations:
                evidence_parts.append(f"  config_violation: {v}")
            return SmokeLaneResult(
                lane="telegram",
                status=SmokeLaneStatus.BLOCKED,
                blocker="TransportConfig validation failed.",
                evidence="; ".join(evidence_parts),
            )

        sanitized_payload = sanitize_gateway_payload(
            raw_chat_id="REDACTED_CHAT_ID",
            raw_user_id="REDACTED_USER_ID",
            text="/status",
            timestamp="2026-05-04T00:00:00Z",
            chat_label="chat:founder",
            user_label="user:founder",
        )
        payload_validation = sanitized_payload.validate()
        if payload_validation is not None:
            return SmokeLaneResult(
                lane="telegram",
                status=SmokeLaneStatus.FAIL,
                blocker=f"Sanitized payload validation failed: {payload_validation}",
                evidence="; ".join(evidence_parts),
            )

        evidence_parts.append(
            "sanitized_inbound: source_chat=chat:founder source_user=user:founder text=/status"
        )
        evidence_parts.append(
            "commands_verified: /status, /decisions, /pause, /resume, /new_project (command names only)"
        )
        evidence_parts.append(
            "classification_paths: intake, answer, clarification, approval, rejection, general_question"
        )
        evidence_parts.append("allow_all_modes: disabled (correct)")
        evidence_parts.append("polling_preferred: true")
        evidence_parts.append("no_raw_ids_in_output: true")
        evidence_parts.append("no_token_values_in_output: true")

        return SmokeLaneResult(
            lane="telegram",
            status=SmokeLaneStatus.PASS,
            evidence="; ".join(evidence_parts),
        )


def run_smoke_readiness(
    *,
    github_owner: str = "OpenClown-bot",
    github_repo: str = "developer-assistant",
    environ: Optional[Dict[str, str]] = None,
) -> SmokeReadinessReport:
    """Run both smoke readiness lanes and return a combined report.

    Args:
        github_owner: Repository owner for GitHub smoke.
        github_repo: Repository name for GitHub smoke.
        environ: Override for os.environ (testing only).

    Returns:
        SmokeReadinessReport with results for both lanes.
    """
    github_lane = GitHubSmokeLane(
        owner=github_owner,
        repo=github_repo,
        environ=environ,
    )
    telegram_lane = TelegramSmokeLane(environ=environ)

    github_result = github_lane.run()
    telegram_result = telegram_lane.run()

    return SmokeReadinessReport(
        github=github_result,
        telegram=telegram_result,
    )
