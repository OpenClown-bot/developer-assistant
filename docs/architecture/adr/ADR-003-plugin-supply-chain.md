---
id: ADR-003
version: 0.2.0
status: approved
---

# ADR-003: Allow Reviewed Hermes Skills and Plugins with Strict Supply-Chain Controls

## Context

Hermes Agent and OpenClaw both provide useful skills/plugins for GitHub, PR review, coding-agent delegation, deployment, browser use, memory, security, and project management. These capabilities are valuable for a Telegram-first Hermes-centered v0.1.

The same ecosystems create supply-chain and runtime risk. Skills/plugins may execute code, add hooks, alter agent behavior, access credentials, call external services, or expose sensitive repository and founder data. OpenClaw plugins run in-process with the gateway. Hermes plugins are opt-in and project-local plugins can be disabled by default, but enabled plugins still require trust.

The user accepts some platform, plugin, and security risk if it is documented and mitigated.

## Decision

v0.1 may use Hermes built-in skills and a small allowlist of optional skills/plugins only when each entry is documented, pinned, source-reviewed, credential-scoped, sandboxed where practical, and reversible.

Marketplace auto-installation is not allowed. Community or optional skills/plugins must not receive credentials or write access until reviewed and explicitly added to the allowlist.

OpenClaw skills/plugins are not part of v0.1. Any later OpenClaw adoption requires a separate ADR and equivalent or stricter controls.

## Required Allowlist Fields

Each enabled skill/plugin must document:

- Name and source URL.
- Version, package lock entry, or commit hash.
- Purpose in v0.1.
- Whether it is built-in, optional official, or community-maintained.
- Required credentials and permission scope.
- Source review result and reviewer/date.
- Sandbox or isolation mode.
- Dangerous operations it can perform.
- Rollback procedure.

## Required Controls

- Pin Hermes runtime and enabled skills/plugins for v0.1 deployments.
- Disable unreviewed project-local plugins and marketplace auto-installation.
- Use least-privilege credentials per integration.
- Prefer sandboxed execution for generated-code work, shell commands, and repository-modifying tools.
- Require founder approval for dangerous commands, credential changes, spending, public endpoint exposure, and deployment actions.
- Keep secrets out of repository artifacts and logs.
- Maintain rollback by disabling the skill/plugin, revoking scoped credentials, stopping Hermes, restoring last known-good runtime config, and resuming from repository state.

## Consequences

- v0.1 can benefit from Hermes automation without treating the whole plugin ecosystem as trusted.
- Executors must implement a concrete allowlist and runtime policy before enabling credential-bearing automation.
- Security review becomes part of the implementation sequence, not an optional later hardening task.
- Some useful skills/plugins may be deferred if source review or sandboxing is not feasible.
