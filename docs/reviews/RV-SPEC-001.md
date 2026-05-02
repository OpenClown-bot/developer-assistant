---
id: RV-SPEC-001
version: 0.1.0
status: complete
verdict: pass_with_changes
---

# RV-SPEC-001: Review of PR #29 — Runtime ticket readiness after source review

## 1. PR Reviewed

- **PR**: [#29](https://github.com/OpenClown-bot/developer-assistant/pull/29)
- **Title**: Prepare runtime integration tickets after source review
- **Branch**: `arch/runtime-ticket-readiness-tkt006-tkt008` → `main`
- **Head SHA**: `0c863f937c8132d399a096695c8cee2dc8c858e5`
- **Merge state**: `CLEAN`
- **Files changed**: 4
  - `docs/architecture/HERMES-RUNTIME-CONTRACT.md`
  - `docs/tickets/TKT-006.md`
  - `docs/tickets/TKT-008.md`
  - `docs/tickets/TKT-014.md` (new)

## 2. Ticket/Spec Artifacts Reviewed

| Artifact | Version at PR head | Status at PR head | Assessment |
|---|---|---|---|
| `docs/tickets/TKT-006.md` | 0.3.0 | `ready` | Correctly promoted from draft after TKT-012 and TKT-013 completion. |
| `docs/tickets/TKT-008.md` | 0.2.0 | `draft` | Correctly kept draft; depends on new TKT-014. |
| `docs/tickets/TKT-011.md` | 0.1.0 | `draft` | Unchanged; correctly remains draft until TKT-006 and TKT-008 are done. |
| `docs/tickets/TKT-014.md` | 0.1.0 | `ready` | New preparatory ticket; scope is precise and dependencies are satisfied. |
| `docs/architecture/HERMES-RUNTIME-CONTRACT.md` | 0.2.0 | `draft` | Updated to reflect GitHub fallback and SQLite state-store decisions. |
| `docs/architecture/HERMES-SKILL-ALLOWLIST.md` | 0.1.0 | `draft` | Unchanged in this PR; already captures TKT-012 source-review outcomes. |
| `docs/architecture/OPERATIONAL-STATE-STORE.md` | 0.2.0 | `active` | Unchanged in this PR; referenced correctly by updated tickets. |
| `docs/orchestration/SESSION-STATE.md` | 0.1.0 | `active` | Unchanged; pending user decision about TKT-006/TKT-008 promotion is resolved by this PR. |

## 3. CI Status

| Check | Conclusion | Evidence |
|---|---|---|
| `validate-docs` (Docs CI) | **SUCCESS** | Completed 2026-05-02T18:17:14Z |
| `Run PR Agent on every pull request` | **SUCCESS** | Completed 2026-05-02T18:19:05Z |
| Local `python3 scripts/validate_docs.py` | **pass** | Run on review branch `rv/spec-001-runtime-ticket-readiness` |

## 4. Findings

### Low — Env Var Collision Risk in TKT-014 Credential Source

- **Location**: `docs/tickets/TKT-014.md:43`
- **Description**: Acceptance criterion #3 permits `GITHUB_TOKEN` or `GH_TOKEN` environment variables as approved credential sources. PR-Agent flagged that GitHub Actions auto-injects a repository-scoped `GITHUB_TOKEN` into CI jobs. If the wrapper reads `GITHUB_TOKEN` without explicit override or scope checks, unit tests running in CI could inadvertently use the default Actions token instead of a fine-grained PAT, causing permission failures or bypassing the least-privilege requirement.
- **Impact**: Non-blocking for production runtime (Hermes runs on a VPS, not in GitHub Actions), but relevant for CI test fidelity and local development safety.
- **Recommendation**: Capture this as a TKT-014 implementation risk/acceptance detail. The Executor should either (a) use a distinct variable name such as `PROJECT_GITHUB_PAT` for the runtime, (b) add an explicit token-scope verification check before API calls, or (c) document that test fixtures must mock or explicitly set the token to avoid CI collision. This refinement can be applied during TKT-014 implementation; the ticket specification does not need to be rewritten before merge.

### Info — HERMES-RUNTIME-CONTRACT Version Bump Justification

- **Location**: `docs/architecture/HERMES-RUNTIME-CONTRACT.md:3`
- **Description**: Version bumped from `0.1.0` to `0.2.0` without a new ADR.
- **Assessment**: Appropriate. The changes are clarifications that reflect already-approved architecture decisions (ADR-001, ADR-002, ADR-003) and completed implementation tickets (TKT-012, TKT-013). No new architectural decision is introduced; the contract is catching up with implementation reality.

### Info — TKT-014 Allowed Files Includes Conditional Architecture Doc

- **Location**: `docs/tickets/TKT-014.md:58`
- **Description**: Section 5 allows `docs/architecture/HERMES-SKILL-ALLOWLIST.md` "only if the implemented capability needs to be recorded as an allowlisted project-specific capability."
- **Assessment**: Acceptable. The condition prevents unconditional Architect-zone writes by an Executor. If the Executor determines the new wrapper should be listed in the allowlist, they must still justify the write. The Ticket Orchestrator or Strategic Orchestrator can enforce this at review time.

## 5. Acceptance/Readiness Assessment

### TKT-006 — Telegram Founder Interaction

| Criterion for Readiness | Status | Evidence |
|---|---|---|
| All stated dependencies complete | **Pass** | TKT-005, TKT-009, TKT-007, TKT-012, TKT-013 are `done`. |
| Source review clears production credential use | **Pass** | TKT-012 cleared `telegram-gateway` with constraints recorded in `HERMES-SKILL-ALLOWLIST.md` Section 4.1. |
| State store hardened for bindings/schedules | **Pass** | TKT-013 enforced FKs, partial-update upserts, and WAL guidance in `OPERATIONAL-STATE-STORE.md`. |
| No new unresolved blockers in scope | **Pass** | Scope aligns with ARCH-001 Section 7 and HERMES-RUNTIME-CONTRACT Section 8. |

**Assessment**: TKT-006 is correctly promoted to `ready`. An Executor may begin implementation under the documented Telegram allowlist constraints.

### TKT-008 — GitHub Repository and PR Integration

| Criterion for Readiness | Status | Evidence |
|---|---|---|
| Dependencies for promotion satisfied | **Fail (by design)** | TKT-014 is not done; TKT-008 explicitly states it is "not ready until a project-specific GitHub workflow capability exists." |
| Hermes bundled skills blocked | **Pass** | TKT-012 rejected `github-pr-workflow`, `github-issues`, and `github-auth`; TKT-008 non-scope and risks reflect this. |
| Architecture fallback documented | **Pass** | HERMES-RUNTIME-CONTRACT Section 9 and TKT-008 scope reference the project-specific REST API + `git` wrapper fallback. |

**Assessment**: TKT-008 correctly remains `draft`. Promotion to `ready` must wait until TKT-014 is merged and verified.

### TKT-014 — Project-Specific GitHub Workflow Capability

| Criterion for Readiness | Status | Evidence |
|---|---|---|
| Dependencies complete | **Pass** | TKT-009 and TKT-012 are `done`. |
| Scope is minimal and precise | **Pass** | Six operations (repo create/register, branch, commit/push, PR open/update, check read, PR metadata read). No full end-to-end TKT-008 flow. |
| Security constraints explicit | **Pass** | Rejects `~/.git-credentials`, token-in-remote, committed config, CLI args; blocks force push, hard reset, branch deletion; requires founder acknowledgement for merge. |
| Test expectations concrete | **Pass** | AC #7 lists five test categories: credential-source rejection, token redaction, mocked REST, constrained git commands, merge-gate behavior. |
| Aligns with ADR-003 | **Pass** | Replaces blocked Hermes bundled skills with a reviewed, scoped, project-specific capability. |

**Assessment**: TKT-014 is correctly created as `ready`. It is the right preparatory ticket and its scope is sufficiently precise for an Executor.

## 6. Security / Process Notes

- **Write zone compliance**: **Confirmed**. All 4 changed files fall within the Architect write zone (`docs/architecture/`, `docs/tickets/`). No source code, CI, prompts, or orchestration files were modified.
- **Secrets exposure**: **None**. No secret values, chat IDs, PATs, or private identifiers appear in the diff. Only secret *names* (`TELEGRAM_BOT_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`) are referenced, which is required for architecture documentation.
- **Token handling**: TKT-014 mandates env-var-only credential sourcing and prohibits plaintext stores. The env-var collision risk noted in Finding 1 is a CI/test concern, not a production secret leak.
- **GitHub credential source**: TKT-014 maintains the fine-grained PAT baseline and defers GitHub App. It explicitly avoids the Hermes bundled `github-auth` skill rejected by TKT-012.
- **Founder acknowledgement before merge**: Preserved in TKT-008 AC #4 and TKT-014 AC #5. HERMES-RUNTIME-CONTRACT Section 9 restates that founder acknowledgement is required before merge in v0.1.
- **Telegram allowlist constraints**: Preserved in TKT-006 AC #8 and unchanged in `HERMES-SKILL-ALLOWLIST.md` Section 4.1.

## 7. Final Verdict

**`pass_with_changes`**

PR #29 correctly promotes TKT-006 to `ready`, keeps TKT-008 in `draft`, and introduces TKT-014 as the precise preparatory ticket required after TKT-012 rejected Hermes bundled GitHub skills. The HERMES-RUNTIME-CONTRACT 0.2.0 update accurately reflects the GitHub fallback and SQLite state-store decisions without overreaching. All write zones, version bumps, and dependencies are correct. CI is green.

The only deferred refinement is documenting the `GITHUB_TOKEN` / GitHub Actions auto-injection collision risk as a TKT-014 implementation detail (Finding 1). This does not block merge.

## 8. Residual Risks

1. **TKT-014 implementation risk**: A custom GitHub wrapper can still mishandle tokens or construct dangerous git commands if the Executor does not fully implement the credential-source rejection, token redaction, and command-constraint tests listed in AC #7.
2. **TKT-006 Telegram runtime risk**: Production `TELEGRAM_BOT_TOKEN` use is cleared only for the reviewed gateway path. The Executor must not broaden token exposure or enable allow-all Telegram access.
3. **TKT-011 trial timing**: TKT-011 must remain `draft` until both TKT-006 and TKT-008 are complete, or until the Founder explicitly approves a narrower dry run.
4. **Env var collision in CI**: As noted in Finding 1, tests for TKT-014 that run in GitHub Actions may accidentally bind to the auto-injected `GITHUB_TOKEN`. The Executor should explicitly mock or override the credential environment in tests.

## 9. Founder Approval Status

- **Founder approval required**: Yes
- **Founder approval status**: Pending

The Architect is proposing ticket-state changes (TKT-006 → ready, TKT-014 → ready) that commit the project to the next Executor sequence. Per ARCH-001 Section 9 and HERMES-RUNTIME-CONTRACT Section 9, founder acknowledgement is required before merge for scope-affecting decisions.
