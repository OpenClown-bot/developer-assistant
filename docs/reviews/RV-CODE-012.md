---
id: RV-CODE-012
version: 0.1.0
status: complete
verdict: pass_with_changes
---

# RV-CODE-012: Review of PR #21 - TKT-012: Hermes credential-bearing capability source review

## Findings

### Medium

1. **Role invocation violation: Orchestrator performed Executor work** (`CONTRIBUTING.md:7`-`13`, `CONTRIBUTING.md:16`, PR #21 comment `4361663149`).
   - The PR comment records that the Orchestrator interpreted the founder message `поехали далее` as permission to act as Executor, while the founder later clarified that the intended meaning was to provide a ticket for an Executor handoff.
   - This violates the role-separated delivery model because Orchestrator coordination should not silently become Executor implementation. The expected path was an Executor invocation for TKT-012, not direct Orchestrator execution.
   - The violation is documented in the PR itself, the changed files stayed within the ticket's allowed implementation paths, and the work is now being reviewed by a Reviewer artifact. Because the PR contains documentation/security review updates only, introduces no production code, and does not bypass the review or founder acknowledgement gates, I do not recommend closing the PR solely for this process defect.
   - Required handling before merge: founder must explicitly acknowledge that PR #21 is accepted as a one-time documented process exception. This must not be treated as precedent for Orchestrator-to-Executor role collapse.

### Low

2. **Residual version wording inconsistency remains outside the updated pin fields** (`docs/architecture/HERMES-SKILL-ALLOWLIST.md:214`-`216`).
   - The PR correctly updates the deployment assumption and allowlist entries from nonexistent `v0.12.0` to `v2026.4.30` commit `73bf3ab1b22314ed9dfecbb59242c03742fe72af`.
   - Section 6 still says "Per Hermes v0.12.0, all plugins are opt-in". This does not undermine the source-review conclusions or credential policy, but it should be cleaned up in a follow-up or before merge if the branch is reworked for any other reason.

### Info

3. **CI has a non-blocking platform warning** (`validate-docs` check run `73993366841`).
   - `validate-docs` passed, but GitHub emitted a Node.js 20 deprecation warning for actions in `.github`.
   - This is unrelated to TKT-012 and does not block this PR.

## Process Verdict

The process violation is real and should be recorded as a role-discipline defect. It is acceptable with documentation for this PR only because all of the following are true:

- The PR comment explicitly documents the ambiguous Orchestrator prompt and the founder's corrected interpretation.
- The diff is limited to `docs/architecture/HERMES-SKILL-ALLOWLIST.md` and `docs/tickets/TKT-012.md` Section 10, matching TKT-012 allowed files.
- No production code, runtime config, credentials, prompts, CI workflows, or review artifacts were modified by the Executor work.
- This Reviewer artifact independently evaluates the diff, ticket, architecture, ADRs, CI, and security conclusions.
- The standard review gate and explicit founder acknowledgement gate remain in force.

PR #21 should not be closed or reworked solely because of the role violation. Merge may proceed only after explicit founder acknowledgement of the documented process exception and the `pass_with_changes` verdict.

## PR Reviewed

- **PR**: [#21](https://github.com/OpenClown-bot/developer-assistant/pull/21)
- **Title**: Review Hermes credential-bearing capabilities
- **Branch**: `tkt-012/source-review-hermes-capabilities` -> `main`
- **Head SHA**: `e9172d94341b0bd61a0d66b0328dd66de5ce20a2`
- **Merge state**: `clean`
- **Changed files**: 2

## Files Reviewed

| File | Expected write zone | Assessment |
| --- | --- | --- |
| `docs/architecture/HERMES-SKILL-ALLOWLIST.md` | TKT-012 allowed file | Allowed; source-review results and Hermes pin updated. |
| `docs/tickets/TKT-012.md` | Section 10 Execution Log only | Allowed; diff only replaces the reserved Section 10 text with execution log entries. Frontmatter/status were not changed. |

No files outside the TKT-012 allowed list were changed.

## Ticket Scope Assessment

TKT-012 requires minimum source review of credential-bearing Hermes Telegram and GitHub capabilities, updates to `HERMES-SKILL-ALLOWLIST.md`, documentation of blockers/fallbacks, no secrets, and docs validation.

| Requirement | Status | Evidence |
| --- | --- | --- |
| Review Telegram gateway credential path and record production token status. | Pass | `HERMES-SKILL-ALLOWLIST.md:46`-`60`, `:356`; Telegram gateway is cleared with constraints. |
| Review GitHub PR workflow credential path and record production token status. | Pass | `HERMES-SKILL-ALLOWLIST.md:62`-`76`, `:357`; bundled PR workflow remains blocked. |
| Check obvious credential exfiltration, unsafe credential logging, broad network/file access assumptions, and unauthorized repository access paths. | Pass | Ticket execution log lists reviewed Telegram modules and GitHub skill docs; allowlist records token-handling concerns for bundled GitHub skills. |
| Update allowlist with source review result, reviewer/date, and constraints. | Pass | Entries cite Executor review for TKT-012 on 2026-05-02 and include constraints/blockers. |
| Document blockers and safe fallback for failed capabilities. | Pass | GitHub PR workflow points to project-specific REST API + `git` orchestration or a follow-up hardened capability ticket. |
| Do not introduce or expose real secrets. | Pass | Diff inspection and secret-pattern search found no token values, PATs, API keys, chat IDs, SSH keys, or `.env` files. |
| `python scripts/validate_docs.py` passes. | Pass | GitHub `validate-docs` check succeeded; local validation after this review artifact also passed. |

## Technical Assessment

The technical conclusions are acceptable for the minimum TKT-012 scope:

- **Telegram gateway**: cleared for production `TELEGRAM_BOT_TOKEN` use only with founder allowlisting or DM pairing, no allow-all flags, polling preferred for v0.1, webhook only with `TELEGRAM_WEBHOOK_SECRET`, and no token values in git-tracked config.
- **GitHub PR/issues/auth bundled skills**: correctly remain blocked for production credential-bearing use. The documented reasons are credible: token extraction from `~/.hermes/.env` or `~/.git-credentials`, broad PAT-style guidance, plaintext credential-store guidance, token-in-remote examples, and PR/merge operations that do not encode this repository's founder acknowledgement policy.
- **Hermes pin**: correcting nonexistent `v0.12.0` to `v2026.4.30` commit `73bf3ab1b22314ed9dfecbb59242c03742fe72af` is the right direction and improves reproducibility.
- **Scope caveat**: the PR does not claim a full Hermes security audit. It limits clearance to the minimum reviewed Telegram path and keeps other credential-bearing paths blocked.

## CI And Checks

- **GitHub checks**: `validate-docs` success; `Run PR Agent on every pull request` success.
- **Commit status API**: no legacy statuses; check-runs API is authoritative here.
- **PR-Agent**: advisory comment reports no major issues and no security concerns.
- **Local diff hygiene**: `git diff --check main...HEAD` passed.
- **Local validation after review artifact**: `python scripts/validate_docs.py` passed.

## Secrets Assessment

No secrets were introduced. I checked the diff and searched repository markdown for common token/key patterns including GitHub PAT prefixes, Telegram bot token shape, AWS access key prefix, private key markers, and direct `TOKEN=` assignments. No matches were found.

## Final Verdict

`pass_with_changes`

PR #21 may proceed without closing/rework, but only as a documented one-time process exception and only after explicit founder acknowledgement. The role violation is not acceptable as normal process, but it is acceptable here because the violation is documented, the changed files are within TKT-012 scope, the technical conclusions are conservative, no secrets are introduced, and CI passes.
