---
id: HERMES-SKILL-ALLOWLIST
version: 0.1.0
status: draft
---

# Hermes Skill/Plugin Security Allowlist

## 1. Purpose

This document defines the v0.1 allowlist and enforcement policy for Hermes Agent skills, plugins, and built-in capabilities used by `developer-assistant`. It satisfies ADR-003 supply-chain controls and the security requirements in ARCH-001 and HERMES-RUNTIME-CONTRACT.md.

The allowlist is deny-by-default: no skill, plugin, or capability is enabled unless it appears in Section 4 with all required fields documented. Everything else is blocked or deferred.

## 2. Enforcement Boundary

The following rules govern all Hermes skills, plugins, and capabilities in the v0.1 deployment:

| Rule | Enforcement |
| --- | --- |
| Only allowlisted skills/plugins may be loaded | Entries must appear in Section 4 |
| Marketplace auto-installation is disabled | `hermes skills install` from hub sources is blocked in production config |
| Unreviewed project-local plugins are disabled | `HERMES_ENABLE_PROJECT_PLUGINS` must remain `false` |
| Community/optional skills/plugins must not receive credentials until source-reviewed | Source review result must be `passed` before credential-bearing use |
| All enabled entries must be pinned to version or commit | No floating `@main` or `@latest` references |
| Credential-bearing capabilities must use least-privilege scoped credentials | See Section 7 |
| Dangerous operations require founder approval | See Section 8 |

## 3. Runtime Deployment Assumptions

| Assumption | Detail |
| --- | --- |
| Hermes Agent version | `v2026.4.30` tag, commit `73bf3ab1b22314ed9dfecbb59242c03742fe72af`; pinned at deployment time |
| Source URL | `https://github.com/NousResearch/hermes-agent` |
| Deployment target | User-owned VPS |
| Terminal backend | `docker` (sandboxed) for production; `local` allowed only during development |
| Gateway mode | Telegram gateway as primary messaging interface |
| Approval mode | `manual` (not `smart` or `off`) for v0.1 |
| YOLO mode | Never enabled in production |
| Project-local plugins | Disabled (`HERMES_ENABLE_PROJECT_PLUGINS` unset or `false`) |
| External skill directories | Not configured in v0.1 |
| Skills Hub auto-update | Disabled in v0.1; `hermes skills update` requires manual review |

## 4. Enabled Skill/Plugin Allowlist

### 4.1 Telegram Gateway Capability

| Field | Value |
| --- | --- |
| Name | `telegram-gateway` |
| Source URL | `https://github.com/NousResearch/hermes-agent` (built-in gateway module) |
| Version/commit | `v2026.4.30`, commit `73bf3ab1b22314ed9dfecbb59242c03742fe72af` |
| Purpose in v0.1 | Receive and send Telegram messages; authenticate founder via allowlist or DM pairing; route commands and free-form input to Orchestrator |
| Maintenance category | built-in |
| Required credentials | `TELEGRAM_BOT_TOKEN` (Telegram bot token from @BotFather) |
| Permission scope | Send and receive messages in chats where the bot is a member; no admin rights required; scoped to single bot identity |
| Source review result | passed with constraints — reviewed by Executor for TKT-012 on 2026-05-02 against Hermes tag `v2026.4.30`, commit `73bf3ab1b22314ed9dfecbb59242c03742fe72af`. The review covered `gateway/config.py`, `gateway/platforms/telegram.py`, `gateway/platforms/telegram_network.py`, `gateway/run.py`, `gateway/status.py`, and Telegram setup docs. `TELEGRAM_BOT_TOKEN` may be used in production only with `TELEGRAM_ALLOWED_USERS` or DM pairing configured, `GATEWAY_ALLOW_ALL_USERS` and `TELEGRAM_ALLOW_ALL_USERS` unset/false, polling mode preferred for v0.1, webhook mode only with `TELEGRAM_WEBHOOK_SECRET`, and no token value written to config tracked by git. |
| Sandbox mode | Not sandboxed; runs as part of the Hermes gateway process |
| Dangerous operations | Can send messages to any chat the bot has access to; can receive message content including potential prompt injection |
| Rollback procedure | (1) Stop Hermes gateway service (`hermes gateway stop`); (2) Revoke Telegram bot token via @BotFather; (3) Remove `TELEGRAM_BOT_TOKEN` from `~/.hermes/.env`; (4) Restore last known-good `config.yaml` from backup; (5) Restart gateway after remediation |

### 4.2 GitHub Repository/PR Capability

| Field | Value |
| --- | --- |
| Name | `github-pr-workflow` |
| Source URL | `https://github.com/NousResearch/hermes-agent` (bundled skill: `skills/github/github-pr-workflow/`) |
| Version/commit | `v2026.4.30`, commit `73bf3ab1b22314ed9dfecbb59242c03742fe72af` |
| Purpose in v0.1 | Branch creation, commit, PR open/update, CI status observation, PR merge (founder-approved only) |
| Maintenance category | built-in (bundled skill) |
| Required credentials | `GITHUB_TOKEN` or `GH_TOKEN` — GitHub PAT or GitHub App token |
| Permission scope | Repository-scoped: `contents:write`, `pull_requests:write`, `checks:read`, `statuses:write`, `actions:read` on `OpenClown-bot/developer-assistant` only; no org-wide or user-wide permissions |
| Source review result | failed for production credential-bearing use — reviewed by Executor for TKT-012 on 2026-05-02 against Hermes tag `v2026.4.30`, commit `73bf3ab1b22314ed9dfecbb59242c03742fe72af`. The reviewed `skills/github/github-pr-workflow/SKILL.md` is instruction-only, but its fallback workflow reads tokens from `~/.hermes/.env` and `~/.git-credentials`, encourages broad PAT-style setup through the related auth skill, and includes merge/push guidance that does not encode this repository's founder-acknowledgement policy. Keep blocked for production `GITHUB_TOKEN`/`GH_TOKEN` use. Safe fallback: use this repository's reviewed REST API + `git` orchestration wrapper with least-privilege token handling, or create a follow-up ticket to author a project-specific GitHub workflow capability. |
| Sandbox mode | Terminal commands execute in Docker backend sandbox when configured; skill instructions run in the LLM context, not as executable code |
| Dangerous operations | Repository write access; branch creation; PR creation; merge operations (founder approval required in v0.1); force push (prohibited by policy) |
| Rollback procedure | (1) Disable the `github-pr-workflow` skill via `hermes config set agent.disabled_toolsets` or skill disable; (2) Revoke the scoped GitHub PAT or rotate the GitHub App token; (3) Stop Hermes service; (4) Restore last known-good `config.yaml`; (5) Resume from repository state — git history is authoritative |

### 4.3 GitHub Issues Capability

| Field | Value |
| --- | --- |
| Name | `github-issues` |
| Source URL | `https://github.com/NousResearch/hermes-agent` (bundled skill: `skills/github/github-issues/`) |
| Version/commit | `v2026.4.30`, commit `73bf3ab1b22314ed9dfecbb59242c03742fe72af` |
| Purpose in v0.1 | Create, label, assign, and triage GitHub issues linked to tickets |
| Maintenance category | built-in (bundled skill) |
| Required credentials | `GITHUB_TOKEN` or `GH_TOKEN` — same token as github-pr-workflow |
| Permission scope | Repository-scoped: `issues:write` on `OpenClown-bot/developer-assistant` only |
| Source review result | failed for production credential-bearing use — reviewed by Executor for TKT-012 on 2026-05-02 against Hermes tag `v2026.4.30`, commit `73bf3ab1b22314ed9dfecbb59242c03742fe72af`. Same token-handling concern as `github-pr-workflow`; keep blocked until a project-specific GitHub capability or hardened upstream workflow is reviewed. |
| Sandbox mode | Same as github-pr-workflow |
| Dangerous operations | Issue creation and modification; no code write access through this skill alone |
| Rollback procedure | Same as github-pr-workflow |

### 4.4 GitHub Auth Capability

| Field | Value |
| --- | --- |
| Name | `github-auth` |
| Source URL | `https://github.com/NousResearch/hermes-agent` (bundled skill: `skills/github/github-auth/`) |
| Version/commit | `v2026.4.30`, commit `73bf3ab1b22314ed9dfecbb59242c03742fe72af` |
| Purpose in v0.1 | Set up GitHub authentication (HTTPS token, SSH key, or `gh` CLI login) during initial Hermes configuration |
| Maintenance category | built-in (bundled skill) |
| Required credentials | None at skill-load time; guides the user to configure `GITHUB_TOKEN` |
| Permission scope | Configuration guidance only; does not perform API operations |
| Source review result | failed for production credential setup — reviewed by Executor for TKT-012 on 2026-05-02 against Hermes tag `v2026.4.30`, commit `73bf3ab1b22314ed9dfecbb59242c03742fe72af`. `skills/github/github-auth/SKILL.md` includes guidance for classic PAT `repo` scope, plaintext `credential.helper store`, token embedding in remote URLs, and extracting tokens from `~/.git-credentials`. Do not use it to provision production credentials for `developer-assistant`; use least-privilege GitHub App or fine-grained PAT procedures documented by this repository instead. |
| Sandbox mode | Not applicable (configuration guidance only) |
| Dangerous operations | May guide credential entry; no direct API calls |
| Rollback procedure | Remove stored GitHub credentials from `~/.hermes/.env`; revoke PAT if compromised |

### 4.5 Coding-Agent Delegation Capability

| Field | Value |
| --- | --- |
| Name | `delegate_task` (Hermes built-in tool) |
| Source URL | `https://github.com/NousResearch/hermes-agent` (core agent tool) |
| Version/commit | `v2026.4.30`, commit `73bf3ab1b22314ed9dfecbb59242c03742fe72af` |
| Purpose in v0.1 | Spawn isolated subagents for parallel or specialized workstreams (Executor, Reviewer roles); delegates coding tasks to subagents using the same model or a different provider |
| Maintenance category | built-in |
| Required credentials | LLM provider API key (same as main agent or auxiliary model key) |
| Permission scope | Inherits the toolsets and permissions of the parent agent session; subagent shares the Docker container by default |
| Source review result | not reviewed — core Hermes tool. **Blocked for credential-bearing production delegation until runtime adapter confirms subagent isolation is adequate.** Development/testing with non-sensitive repositories is acceptable. |
| Sandbox mode | Subagents share the Docker container sandbox with the parent agent unless per-task environment overrides are registered |
| Dangerous operations | Can execute terminal commands; can read and write files in the shared workspace; can access the same credentials as the parent |
| Rollback procedure | (1) Stop the subagent via `/stop` or interrupt; (2) Stop Hermes service; (3) Revoke any credentials the subagent had access to; (4) Restore workspace from git state; (5) Restart Hermes |

### 4.6 Sandboxed Shell/Runtime Execution Capability

| Field | Value |
| --- | --- |
| Name | `terminal` (Hermes built-in tool, Docker backend) |
| Source URL | `https://github.com/NousResearch/hermes-agent` (core tool) |
| Version/commit | `v2026.4.30`, commit `73bf3ab1b22314ed9dfecbb59242c03742fe72af` |
| Purpose in v0.1 | Execute shell commands, scripts, and build/test workflows inside an isolated Docker container with security hardening |
| Maintenance category | built-in |
| Required credentials | None directly; Docker backend may receive forwarded env vars via `docker_forward_env` |
| Permission scope | Container-isolated: `--cap-drop ALL`, `--security-opt no-new-privileges`, `--pids-limit 256`, size-limited tmpfs; no host filesystem access unless bind-mounted |
| Source review result | not reviewed — core Hermes tool. Docker security flags are documented and match Docker security best practices. **Docker backend reduces risk significantly compared to `local` backend.** |
| Sandbox mode | Full Docker container isolation (namespaces, capabilities dropped, PID limits, no-new-privileges) |
| Dangerous operations | Shell command execution within the container; `docker_forward_env` entries become visible inside the container; container root can install packages |
| Rollback procedure | (1) Stop Hermes service; (2) Remove Docker container (`docker rm -f <container>`); (3) Remove forwarded env vars from `docker_forward_env` config; (4) Restart Hermes with clean container |

### 4.7 Cron/Scheduler Capability

| Field | Value |
| --- | --- |
| Name | `cronjob` (Hermes built-in tool) |
| Source URL | `https://github.com/NousResearch/hermes-agent` (core tool) |
| Version/commit | `v2026.4.30`, commit `73bf3ab1b22314ed9dfecbb59242c03742fe72af` |
| Purpose in v0.1 | Schedule periodic progress reports, health checks, and maintenance tasks; deliver scheduled output to Telegram |
| Maintenance category | built-in |
| Required credentials | No dedicated credentials; inherits gateway and LLM provider credentials from the Hermes session |
| Permission scope | Can execute any tool available to the agent; scheduled tasks run with the same permissions as the parent session |
| Source review result | not reviewed — core Hermes tool. **Cron jobs in headless mode bypass interactive approval; manual approval mode must be enforced.** |
| Sandbox mode | Cron jobs run in the same environment as the parent agent session |
| Dangerous operations | Unattended execution of any tool the agent has access to; can execute terminal commands without interactive approval if approval mode is not `manual` |
| Rollback procedure | (1) Pause or remove the cron job via `cronjob` tool action `remove`; (2) Stop Hermes service; (3) Review and clean `~/.hermes/cron/` for persisted jobs; (4) Restart with `approvals.mode: manual` confirmed |

### 4.8 Memory/State Capability

| Field | Value |
| --- | --- |
| Name | `memory` + `session_search` (Hermes built-in tools) |
| Source URL | `https://github.com/NousResearch/hermes-agent` (core tools) |
| Version/commit | `v2026.4.30`, commit `73bf3ab1b22314ed9dfecbb59242c03742fe72af` |
| Purpose in v0.1 | Persistent operational memory across sessions; cross-session recall for conversation continuity; not authoritative for product/architecture decisions |
| Maintenance category | built-in |
| Required credentials | None; LLM provider key used for session search summarization |
| Permission scope | Read/write to `~/.hermes/memories/` (MEMORY.md, USER.md); FTS5 search index across past sessions |
| Source review result | not reviewed — core Hermes feature. **Memory is operational state, not authoritative governance state per HERMES-RUNTIME-CONTRACT.md Section 3.** Low risk if repository artifacts remain the source of truth. |
| Sandbox mode | Not sandboxed; part of the Hermes core process |
| Dangerous operations | Can store and recall information that may influence agent behavior; memory content may contain prompt injection if not properly sanitized |
| Rollback procedure | (1) Clear memory via `memory` tool or delete `~/.hermes/memories/` files; (2) Restart Hermes session; (3) Repository artifacts remain authoritative — re-read required context paths |

## 5. Deferred Or Prohibited Skills/Plugins

The following capabilities are explicitly deferred or prohibited in v0.1:

| Capability | Status | Reason |
| --- | --- | --- |
| Marketplace/Hub auto-installation | Prohibited | ADR-003: marketplace auto-installation not allowed; manual install with security scan required for any future addition |
| Project-local plugins (`.hermes/plugins/`) | Prohibited | `HERMES_ENABLE_PROJECT_PLUGINS` remains `false`; unreviewed project-local plugins are disabled by default per ADR-003 |
| Community skills from Skills Hub | Deferred | Source review not completed; no community skill may receive credentials until reviewed and explicitly added to this allowlist |
| Claude Code delegation skill (`claude-code`) | Deferred | Requires Anthropic API key; not needed for v0.1 which uses GLM 5.1 / Codex models via configured providers |
| OpenAI Codex delegation skill (`codex`) | Deferred | Requires OpenAI API key; v0.1 uses configured OmniRoute providers, not direct Codex CLI |
| OpenCode delegation skill (`opencode`) | Deferred | Requires separate setup; not evaluated for v0.1 |
| Webhook subscriptions plugin | Deferred | Not required for v0.1; introduces external endpoint exposure risk |
| MCP server integrations | Deferred | Requires per-server review; not needed for v0.1 baseline |
| Voice mode | Deferred | Not required for v0.1 text-based Telegram interaction |
| Browser automation tools | Deferred | Not required for v0.1; introduces attack surface |
| Image generation / media tools | Deferred | Not required for v0.1 |
| Home Assistant integration | Prohibited | Not applicable to v0.1 scope |
| OpenClaw plugins | Prohibited | Per ADR-003: not part of v0.1; any future adoption requires separate ADR |
| Any `optional-skills/` from Hermes repo | Deferred | Optional official skills are not auto-enabled; each requires individual review before inclusion |
| External skill directories | Prohibited | Not configured in v0.1; `skills.external_dirs` remains unset |

## 6. Marketplace And Project-Local Plugin Policy

### Marketplace Auto-Installation

Marketplace auto-installation is **disabled** in v0.1. The Hermes Skills Hub (`hermes skills install`) offers installation from multiple sources including official optional skills, skills.sh, well-known endpoints, GitHub repos, ClawHub, LobeHub, and direct URLs. In v0.1:

- No skill may be installed from any Hub source without explicit founder approval.
- Any installed skill must be added to this allowlist (Section 4) with all required fields before it can be used in production.
- The Hermes security scanner (`hermes skills inspect`) should be run before any installation, but scanner results are not a substitute for source review per ADR-003.

### Project-Local Plugins

Project-local plugins under `.hermes/plugins/` are **disabled** by default in Hermes. In v0.1:

- `HERMES_ENABLE_PROJECT_PLUGINS` must remain unset or `false`.
- No project-local plugin may be enabled even in development without being added to this allowlist.
- User plugins under `~/.hermes/plugins/` require explicit opt-in via `plugins.enabled` in `config.yaml` and must appear in this allowlist.

### Plugin Opt-In Requirement

Per Hermes `v2026.4.30`, all plugins are opt-in: discovered but not enabled by default. Every enabled plugin must be listed in `plugins.enabled` in `config.yaml`. This allowlist is the governance document that justifies each entry.

## 7. Credential Scope Requirements

### 7.1 Telegram Bot Token

| Property | Requirement |
| --- | --- |
| Token source | Bot token from @BotFather |
| Scope | Single bot identity; no admin privileges; messages restricted to chats where the bot is a member |
| Allowlist enforcement | `TELEGRAM_ALLOWED_USERS` must list only the founder's Telegram user ID; no `GATEWAY_ALLOW_ALL_USERS` |
| DM pairing | Permitted as an alternative to hardcoded allowlist; pairing data stored in `~/.hermes/pairing/` with `chmod 0600` |
| Storage | `~/.hermes/.env` with `chmod 600`; never committed to repository |
| Rotation | Revoke old token via @BotFather; generate new token; update `~/.hermes/.env`; restart gateway |

### 7.2 GitHub Token

| Property | Requirement |
| --- | --- |
| Token type | Fine-grained personal access token (PAT) or GitHub App installation token |
| Scope | Repository-scoped to `OpenClown-bot/developer-assistant` only |
| Permissions | `contents:write`, `pull_requests:write`, `issues:write`, `checks:read`, `statuses:write`, `actions:read` — minimal set for PR lifecycle |
| Prohibited permissions | No `admin:org`, no `user`, no `delete_repo`, no `workflow:write` unless explicitly needed for a future ticket |
| Storage | `~/.hermes/.env` as `GITHUB_TOKEN` or `GH_TOKEN` with `chmod 600`; never committed to repository |
| Rotation | Revoke old token via GitHub Settings > Developer settings; generate new scoped token; update `~/.hermes/.env`; restart Hermes |
| Separation | GitHub token must be separate from LLM provider keys, Telegram bot token, and VPS credentials |

### 7.3 LLM Provider Keys

| Property | Requirement |
| --- | --- |
| Scope | LLM API access only; must not be shared with GitHub or Telegram integrations |
| Storage | `~/.hermes/.env`; never committed to repository |
| Passthrough | Not forwarded into Docker containers via `docker_forward_env` unless a specific skill requires it and is allowlisted |
| Separation | Separate from GitHub token, Telegram bot token, and VPS credentials |

### 7.4 VPS Credentials

| Property | Requirement |
| --- | --- |
| Scope | SSH access to deployment VPS only; not shared with Hermes agent runtime |
| Storage | `~/.ssh/` on the operator's local machine or approved secret storage; never in `~/.hermes/.env` or repository |
| Prohibition | VPS SSH keys must not appear in `docker_forward_env`, `env_passthrough`, or any Hermes configuration |
| Separation | Completely separate from GitHub, Telegram, and LLM credentials |

### 7.5 Credential Isolation Summary

| Credential | Shared with | Isolation |
| --- | --- | --- |
| Telegram bot token | Telegram gateway only | Not forwarded to Docker; not in `env_passthrough` |
| GitHub PAT | GitHub skills/tools only | Forwarded to Docker via `docker_forward_env: ["GITHUB_TOKEN"]` if needed for terminal commands inside container |
| LLM provider key | LLM API calls only | Not forwarded to Docker; not in `env_passthrough` |
| VPS SSH key | Operator only | Never in Hermes configuration |

## 8. Sandboxing And Dangerous Operation Controls

### 8.1 Sandbox Configuration

| Setting | Value | Rationale |
| --- | --- | --- |
| `terminal.backend` | `docker` | Production gateway must use container isolation |
| `terminal.docker_image` | Pinned image (e.g., `nikolaik/python-nodejs:python3.11-nodejs20@sha256:<pin>`) | Pin to specific digest for reproducibility |
| `terminal.container_persistent` | `true` | Preserve workspace across sessions for development continuity |
| `terminal.container_cpu` | `1` | Limit compute resources |
| `terminal.container_memory` | `5120` (MB) | Limit memory usage |
| `terminal.container_disk` | `51200` (MB) | Limit disk usage |
| `terminal.docker_forward_env` | `["GITHUB_TOKEN"]` only | Minimal credential forwarding |
| `approvals.mode` | `manual` | All dangerous commands require interactive approval |
| `approvals.timeout` | `60` (seconds) | Fail-closed on timeout |
| `security.tirith_enabled` | `true` | Enable pre-execution security scanning |
| `security.tirith_fail_open` | `false` | Block commands when tirith is unavailable in production |

### 8.2 Dangerous Operation Approval Rules

The following operations require explicit founder approval before execution, aligned with HERMES-RUNTIME-CONTRACT.md Section 11 and ADR-003:

| Category | Operations | Approval Method |
| --- | --- | --- |
| Credential changes | Creation, rotation, revocation, scope changes for any token or key | Telegram approval from founder |
| Public endpoint exposure | Opening ports, deploying to public URLs, configuring webhooks | Telegram approval from founder |
| Spending money | Paid API calls beyond normal LLM usage, cloud resource allocation, paid skill subscriptions | Telegram approval from founder |
| Deployment actions | VPS deployment, live execution of generated projects, `make deploy` | Telegram approval from founder |
| Irreversible Git operations | Force push, hard reset, branch deletion, `rm -rf` in repository context | Telegram approval from founder; Hermes hardline blocklist prevents catastrophic variants |
| Merge operations | Any merge to `main` or protected branch | Telegram approval from founder required in v0.1 per ARCH-001 |

Hermes built-in dangerous command approval handles shell-level dangerous patterns (recursive delete, pipe-to-shell, system config modification, etc.). The approval rules above extend to semantic operations that may not trigger pattern-based approval but are policy-level dangerous for `developer-assistant`.

### 8.3 Hermes Hardline Blocklist

The Hermes hardline blocklist (always-on floor) prevents catastrophic commands regardless of approval mode or YOLO mode:

- `rm -rf /` and variants
- Fork bombs
- `mkfs` on mounted root
- `dd` to physical disk
- Piping untrusted URLs to `sh` at rootfs

This blocklist is built into Hermes and cannot be overridden. It provides an additional safety layer beyond the policy-level approval rules.

## 9. Rollback Procedure

When a skill, plugin, or capability causes harm or behaves unexpectedly, follow these steps in order:

1. **Disable the skill/plugin.**
   - For skills: remove from slash command availability or disable via `agent.disabled_toolsets` in `config.yaml`
   - For plugins: remove from `plugins.enabled` in `config.yaml` or add to `plugins.disabled`
   - For built-in tools: disable via `agent.disabled_toolsets` in `config.yaml`

2. **Revoke scoped credentials.**
   - Telegram: revoke bot token via @BotFather
   - GitHub: revoke PAT via GitHub Settings or rotate GitHub App token
   - LLM: rotate API key with the provider
   - VPS: never in Hermes; rotate SSH key independently if compromised

3. **Stop the Hermes service.**
   - `hermes gateway stop`
   - Or kill the process if unresponsive

4. **Restore last known-good runtime config.**
   - Restore `~/.hermes/config.yaml` from backup
   - Restore `~/.hermes/.env` from backup (secrets only; verify no corruption)
   - Remove any Docker containers: `docker rm -f <container>`
   - Remove installed skills that caused the issue: `hermes skills uninstall <name>`

5. **Resume from repository state.**
   - Repository artifacts in `docs/` remain authoritative per HERMES-RUNTIME-CONTRACT.md Section 3
   - Re-read required context paths from the repository
   - Resume work from the last known-good ticket state
   - Git history is the source of truth for code state

### Rollback Testing

Rollback steps are documented above but not yet tested in a live Hermes deployment. Follow-up ticket required for end-to-end rollback verification once the runtime adapter is implemented.

## 10. Source Review Notes

### Review Status Summary

| Entry | Source Review Status | Notes |
| --- | --- | --- |
| telegram-gateway | Passed with constraints | Minimal credential-bearing review completed for TKT-012 on 2026-05-02 against `v2026.4.30` commit `73bf3ab1b22314ed9dfecbb59242c03742fe72af`. No obvious token exfiltration path was found in reviewed Telegram gateway code. Production use requires founder allowlisting or pairing, no allow-all flags, and webhook secret if webhook mode is used. |
| github-pr-workflow | Failed for production credential-bearing use | Bundled skill is markdown instructions, not executable code, but it instructs agents to read tokens from `~/.hermes/.env` and `~/.git-credentials` and includes broad PR/merge operations that do not encode this repository's gates. Use project-specific REST API + `git` orchestration instead. |
| github-issues | Failed for production credential-bearing use | Same token-handling concern as github-pr-workflow. Not needed to unblock TKT-008 PR workflow; keep blocked until separately hardened/reviewed. |
| github-auth | Failed for production credential setup | Configuration guidance includes classic PAT broad scopes, plaintext credential-store persistence, token-in-remote examples, and token extraction from `~/.git-credentials`. Do not use for production credential provisioning. |
| delegate_task | Not reviewed | Core Hermes tool; subagent isolation depends on Hermes implementation. Docker container sharing between parent and subagent is a known concurrency risk. |
| terminal (Docker) | Not reviewed | Core Hermes tool; Docker security flags match documented best practices. Container isolation provides a meaningful security boundary. |
| cronjob | Not reviewed | Core Hermes tool; unattended execution risk mitigated by `approvals.mode: manual` |
| memory + session_search | Not reviewed | Core Hermes feature; memory is operational state only, not authoritative per governance contract. Low risk if repository remains source of truth. |

### Review Priorities for Follow-Up

1. **High priority**: project-specific GitHub workflow capability — upstream GitHub skill instructions remain blocked for production credentials
2. **Medium priority**: `delegate_task` isolation model — subagent credential access needs verification
3. **Low priority**: Memory and cron tools — operational state only, lower risk profile

### Important Caveat

Minimal source review has cleared only the Telegram gateway for credential-bearing production use, and only under the constraints documented in Section 4.1. GitHub credential-bearing bundled skills remain blocked; production GitHub automation must use a project-specific reviewed path until a later source-review ticket clears a hardened upstream or custom capability. Development and testing with dedicated, scoped, non-sensitive credentials remains acceptable.

## 11. Validation

The following validation requirements apply to this allowlist:

- `python scripts/validate_docs.py` must pass after any changes to this document or related artifacts.
- No secret values (tokens, keys, passwords, chat IDs) are included in this document or any repository artifact.
- Concrete runtime config syntax validation (YAML schema, `config.yaml` structural checks) is deferred unless a config file is added to the repository.
- The allowlist content should be manually reviewed against ADR-003 required fields to confirm completeness.

## 12. Follow-Up Tickets

The following follow-up tickets are needed:

| Follow-Up | Description |
| --- | --- |
| Concrete Hermes runtime config | Once Hermes Agent package names, versions, and config schema are confirmed at deployment time, create a ticket to generate the actual `~/.hermes/config.yaml` reflecting this allowlist |
| Source review of credential-bearing capabilities | Before any skill/plugin receives production credentials, a source review ticket must be completed and the result recorded in Section 4 |
| Enforcement tests | Once the Hermes runtime adapter is implemented, create a ticket for automated tests verifying: allowlisted skills only are enabled, marketplace install is blocked, project-local plugins are disabled, approval mode is `manual` |
| Docker image pinning | Pin the Docker terminal image to a specific SHA256 digest and document the verification procedure |
| Subagent isolation verification | Verify that `delegate_task` subagents cannot access credentials not forwarded via `docker_forward_env` |
| Rollback procedure testing | End-to-end test of the rollback procedure documented in Section 9 |
| Operational state store selection | Decide between Hermes native persistence and SQLite per HERMES-RUNTIME-CONTRACT.md Section 6 |
