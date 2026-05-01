---
id: RV-CODE-009
version: 0.1.0
status: complete
verdict: pass
---

# RV-CODE-009: Review of PR #16 — TKT-009: Hermes skill/plugin security allowlist

## PR reviewed

- **PR**: [#16](https://github.com/OpenClown-bot/developer-assistant/pull/16)
- **Title**: TKT-009: Hermes skill/plugin security allowlist
- **Branch**: `tkt-009/skill-allowlist` → `main`
- **Author**: `OpenClown-bot`
- **Merge state**: `CLEAN`
- **Scope**: New architecture policy document `HERMES-SKILL-ALLOWLIST.md` and TKT-009 Execution Log update.

## Ticket reviewed

- **Ticket**: `TKT-009`
- **Status in PR**: `ready` (not changed by this PR)
- **Scope alignment**: The PR implements exactly the ticket scope — a v0.1 allowlist and enforcement approach as a documented architecture/security policy. It does not implement runtime behavior, config generation, or source review, which are all correctly deferred.

## Files reviewed

| File | Role write zone | Change type |
| --- | --- | --- |
| `docs/architecture/HERMES-SKILL-ALLOWLIST.md` | Architect | New file — v0.1 allowlist and enforcement policy |
| `docs/tickets/TKT-009.md` | Executor — Section 10 only | Added Execution Log with changed files, validation, deferred items, and follow-ups |

Both files are within allowed Executor zones per `CONTRIBUTING.md` and `TKT-009.md` Section 5. No production code, prompts, templates, scripts, tests, workflows, or review artifacts were modified.

## CI / PR-Agent status

- **Docs CI** (`validate-docs`): pass (6s).
- **PR-Agent** (`Run PR Agent on every pull request`): pass (1m50s).
- **PR-Agent verdict**: Advisory; no security concerns in the diff; two focus areas flagged for reviewer attention (subagent isolation ambiguity and persistent container vs rollback tension).
- **Local validation**: `python scripts/validate_docs.py` passes.

## Findings (ordered by severity)

### Info

1. **Persistent container vs rollback tension** (`HERMES-SKILL-ALLOWLIST.md:279` and `:337`).
   - Section 8.1 sets `terminal.container_persistent: true` to preserve workspace across sessions.
   - Section 9 Step 4 prescribes `docker rm -f <container>` during rollback, which destroys the persistent workspace.
   - This is a documentation inconsistency, not a security vulnerability, because Step 5 explicitly directs recovery from git history and repository state. However, the procedure should clarify whether uncommitted container state is intentionally sacrificed during incident response, or whether the container should be stopped (not removed) when forensic continuity is desired.
   - **Recommendation**: In a follow-up edit or as part of the rollback testing ticket, clarify the container removal step — e.g., "Stop and remove the container (uncommitted workspace state will be lost; recover from git history)."

2. **Subagent isolation ambiguity flagged by PR-Agent** (`HERMES-SKILL-ALLOWLIST.md:120`–`:122`).
   - Section 4.5 notes that `delegate_task` subagents share the Docker container sandbox with the parent by default, while Section 4.6 describes "full Docker container isolation."
   - The document correctly mitigates this by explicitly marking `delegate_task` as **blocked for credential-bearing production use until runtime adapter confirms subagent isolation is adequate**.
   - This is an accepted v0.1 risk and is appropriately documented. No action required before merge.

3. **Source review result lacks reviewer/date** (ADR-003 required field).
   - Every allowlist entry lists "Source review result: not reviewed" but does not include a reviewer name or date because no review has been performed.
   - This is honest and correct. Adding fabricated reviewer/date metadata would be worse than omitting it. The document includes a Section 10 review status table and an explicit caveat that no credential-bearing skill should be used in production until the result is updated to `passed`. The follow-up ticket "Source review of credential-bearing capabilities" will populate this field.

4. **No fake certainty in source review** (`HERMES-SKILL-ALLOWLIST.md:372`–`:374`).
   - The "Important Caveat" paragraph explicitly states that no credential-bearing skill should be used in production until source review is completed. This satisfies the requirement to avoid false source-review certainty.

## Acceptance criteria assessment

| Criterion | Status | Evidence |
| --- | --- | --- |
| An allowlist artifact or runtime config lists every enabled Hermes skill/plugin. | **Pass** | Section 4 documents 8 enabled capabilities; Section 5 documents 14 deferred/prohibited capabilities. |
| Each entry includes name, source URL, version/commit, purpose, maintenance category, required credentials, permission scope, source review result, sandbox mode, dangerous operations, and rollback procedure. | **Pass** | All 8 entries in Section 4 include every required field mapped from ADR-003. |
| Marketplace auto-installation and unreviewed project-local plugins are disabled or documented as unavailable. | **Pass** | Section 2, Section 5, and Section 6 explicitly disable both. `HERMES_ENABLE_PROJECT_PLUGINS` must remain `false`; `hermes skills install` from hub sources is blocked. |
| Credential-bearing skills/plugins use least-privilege credentials. | **Pass** | Section 7 defines scoped credentials for Telegram (single bot, no admin), GitHub (repo-scoped PAT), LLM (API-only), and VPS (operator-only, never in Hermes). |
| Rollback steps are tested or documented for disabling a skill/plugin and revoking credentials. | **Pass** | Section 9 documents a 5-step rollback procedure covering disable, revoke, stop, restore config, and resume from repository state. Testing is explicitly deferred to a follow-up ticket. |
| `python scripts/validate_docs.py` passes. | **Pass** | Confirmed in CI and TKT-009 Execution Log. |

## Security / process notes

- **Deny-by-default is explicit and aligned with ADR-003**: Section 1 states "no skill, plugin, or capability is enabled unless it appears in Section 4." Section 2 enforcement rules map directly to ADR-003 required controls.
- **Credential-bearing capabilities are blocked for production use**: `telegram-gateway`, `github-pr-workflow`, `github-issues`, and `delegate_task` all carry bold warnings that they are blocked until source review passes. This is the correct conservative posture for v0.1.
- **Least-privilege scopes are clearly defined**: Telegram bot token is scoped to a single identity without admin rights; GitHub PAT is repository-scoped to `OpenClown-bot/developer-assistant` only with an explicit prohibited-permissions list; LLM keys are isolated from GitHub/Telegram; VPS SSH keys are completely excluded from Hermes configuration.
- **Marketplace and project-local plugins are prohibited**: Section 5 and Section 6 leave no ambiguity — auto-installation and `.hermes/plugins/` are disabled in v0.1.
- **Sandbox and dangerous-operation rules align with HERMES-RUNTIME-CONTRACT.md Section 11**: Section 8.2 approval categories (credential changes, public endpoint exposure, spending, deployment, irreversible git, merge operations) match the contract exactly. `approvals.mode: manual`, `tirith_enabled: true`, and `tirith_fail_open: false` are all specified.
- **No secrets committed**: Diff inspection confirms no tokens, keys, chat IDs, PATs, `.env` files, or credentials appear in repository artifacts.
- **Follow-up tickets are appropriate and non-scope-creeping**: All 7 follow-up items (runtime config generation, source review, enforcement tests, Docker image pinning, subagent isolation verification, rollback testing, operational state store selection) are logically deferred from a policy-only ticket.
- **TKT-009.md changes are limited to Section 10 Execution Log**: The diff shows only the Execution Log section was appended; no other ticket sections were modified. This respects the Executor write-zone rule.

## Final verdict

`pass`

PR #16 satisfies all TKT-009 acceptance criteria, aligns with ADR-003 and `HERMES-RUNTIME-CONTRACT.md` Section 11, maintains deny-by-default posture, blocks credential-bearing capabilities pending source review, documents least-privilege credential scoping, prohibits marketplace and project-local plugins, and avoids committing any secrets. The one minor documentation tension between `container_persistent: true` and `docker rm -f` in rollback is noted as an info-level finding that can be clarified in a follow-up edit or during rollback testing. Merge is approved subject to the standard founder acknowledgement gate per ARCH-001.
