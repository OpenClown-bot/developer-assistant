---
id: RV-SPEC-004
version: 0.1.0
status: final
review_target: PR-51
review_type: spec
verdict: pass
reviewer_model: kimi-k2.6
created: 2026-05-04
---

# RV-SPEC-004: Review of PR #51 — TKT-016 Readiness

## 1. PR Reviewed

- **PR**: [#51](https://github.com/OpenClown-bot/developer-assistant/pull/51)
- **Title**: Promote TKT-016 runtime GitHub executor binding
- **Branch**: `arch/tkt-016-runtime-github-executors` → `main`
- **Head SHA**: `8c48bdb6f1dba70e5634d1fc64e46f179493fe72`
- **Changed files**: 1
  - `docs/tickets/TKT-016.md` (new, 131 lines)

## 2. Ticket Reviewed

- **Ticket**: `docs/tickets/TKT-016.md` @ `0.1.0`
- **Source backlog**: `TKT-NEW-008-D`
- **Status at review time**: `ready`
- **Scope**: Implement concrete runtime bindings for TKT-008 `RESTExecutor` and `GitExecutor` protocols to real HTTP and constrained `git` execution, using TKT-014 request/command builders and credential path.

## 3. Architecture / ADR References

- **Architecture**: `docs/architecture/ARCH-001.md` @ `0.2.0`
- **Relevant contracts**:
  - `docs/architecture/HERMES-RUNTIME-CONTRACT.md` @ `0.2.0`
  - `docs/architecture/HERMES-SKILL-ALLOWLIST.md` @ `0.1.0`
  - `docs/architecture/OPERATIONAL-STATE-STORE.md` @ `0.2.0`
- **Relevant ADRs**:
  - `ADR-001-platform-foundation.md` @ `0.2.0`
  - `ADR-002-repository-state.md` @ `0.2.0`
  - `ADR-003-plugin-supply-chain.md` @ `0.2.0`
- **Dependencies reviewed**:
  - `TKT-008.md` @ `0.3.0` (done)
  - `TKT-014.md` @ `0.1.0` (done)
  - `TKT-012` (done, source-review gate)
  - `TKT-015.md` @ `0.1.0` (done)
  - `TKT-011.md` @ `0.1.0` (draft, correctly not implemented)
  - `TKT-NEW-008-A.md` @ `0.1.0` (backlog, correctly excluded)
  - `TKT-NEW-008-B.md` @ `0.1.0` (backlog, optional gated path only)
  - `TKT-NEW-008-C.md` @ `0.1.0` (backlog, correctly excluded)
  - `TKT-NEW-008-D.md` @ `0.1.0` (backlog, promoted into this ticket)

## 4. CI Status

| Check | Conclusion |
| --- | --- |
| Docs validation (`python scripts/validate_docs.py`) | **pass** |
| PR-Agent (`Run PR Agent on every pull request`) | **pass** — no security concerns, no major issues |

## 5. Findings (ordered by severity)

No blocking, security-class, or non-blocking findings require changes. The following are informational observations and praise.

### Info — `TKT-006` not listed in Required Context

- **Location**: `docs/tickets/TKT-016.md` §3 Required Context
- **Description**: TKT-006 (Telegram founder interaction logic layer) is not listed as required reading. TKT-016's §2 correctly states it must not rework Telegram transport, and TKT-008 (which is listed) already composes with TKT-006. TKT-015 (listed) provides the transport boundary context. An Executor could safely implement TKT-016 without reading TKT-006 directly, since the TKT-008 integration layer handles Telegram composition.
- **Impact**: None. Not a scope gap or contradiction.
- **Recommendation**: Optional — add `docs/tickets/TKT-006.md` to Required Context if a future revision wants maximum completeness, but omission is acceptable.

### Praise — Non-scope exclusions are comprehensive and precise

- **Location**: `docs/tickets/TKT-016.md` §2 Non-scope
- **Description**: The non-scope section correctly and exhaustively excludes every item specified in the review bootstrap: Hermes bundled `github-pr-workflow`, `github-issues`, `github-auth`; `GITHUB_TOKEN` / `GH_TOKEN` fallback; autonomous merge; founder/ticket/CI/Reviewer gate bypass; TKT-NEW-008-A idempotency; TKT-NEW-008-B full live smoke harness (except optional gated path); TKT-NEW-008-C persistence; Telegram transport rework; full TKT-011 trial; VPS deployment, OpenClaw, marketplace/community skills, project-local plugins, GitHub App provisioning, and credential rotation.

### Praise — TKT-012 / HERMES-SKILL-ALLOWLIST constraints are preserved with testable enforcement

- **Location**: `docs/tickets/TKT-016.md` §2, §4 AC 1, §4 AC 7, §6, §7
- **Description**: The ticket blocks Hermes bundled GitHub skills in non-scope, requires `PROJECT_GITHUB_PAT` as the sole credential path in acceptance criteria, mandates tests rejecting `GITHUB_TOKEN`, `GH_TOKEN`, `~/.git-credentials`, token-bearing remotes, committed config, and CLI arguments, and requires the PR body to state explicitly that Hermes bundled skills remain blocked. This is a complete, layered constraint preservation.

### Praise — TKT-014 constrained git and credential-source controls are preserved

- **Location**: `docs/tickets/TKT-016.md` §4 AC 5–7, §6
- **Description**: The `GitExecutor` acceptance criteria require subprocess execution without shell, without raw command strings, and with continued blocking of force push, `--force-with-lease`, hard reset, branch deletion, token-bearing remotes, and shell metacharacters. These are exactly the TKT-014 constraints. Test requirements cover command-validation enforcement and subprocess shell avoidance.

### Praise — TKT-008 founder acknowledgement, redaction, PR/review/CI gates are preserved

- **Location**: `docs/tickets/TKT-016.md` §2, §4 AC 4, §4 AC 8
- **Description**: Non-scope blocks autonomous merge and gate bypass. AC 4 requires REST error/metadata redaction through existing helpers before logs/Telegram text/errors. AC 8 requires the adapter inject into TKT-008 without bypassing founder merge acknowledgement. This preserves the full TKT-008 gate and redaction contract.

### Praise — DeepSeek V4 Pro default is correctly documented and consistent with tooling decisions

- **Location**: `docs/tickets/TKT-016.md` §9 Dependencies
- **Description**: The ticket states "the upcoming Executor default is DeepSeek V4 Pro for comparison against prior GLM 5.1. No GPT-5.5 XHigh or other specialist model is requested for this ticket." This matches `docs/orchestration/SESSION-STATE.md` § Current Tooling Decisions and `CONTRIBUTING.md` § Roles.

## 6. Acceptance Criteria Assessment

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Concrete `RESTExecutor` using `PROJECT_GITHUB_PAT` through `load_credential()` or TKT-008 entry point | **Pass** | AC text is explicit and testable; references TKT-014 builders and TKT-008 integration layer |
| 2 | Authorization injected only at send time, never stored in durable objects/logs/errors/progress | **Pass** | Testable via inspection of request object lifecycle and log capture |
| 3 | REST supports repo create/register, PR open/update, check-status read, PR metadata read, merge-gate path | **Pass** | Maps directly to TKT-014 builder coverage already reviewed in RV-CODE-014 |
| 4 | REST errors, URLs, headers, metadata, exceptions sanitized with existing redaction helpers | **Pass** | Requires token-redaction helpers from TKT-014/TKT-008; testable with mock HTTP errors |
| 5 | Concrete `GitExecutor` via subprocess without shell, without raw command strings | **Pass** | Explicit and testable; aligns with TKT-014 `GitCommand` list-based args |
| 6 | Git executor continues blocking dangerous operations and shell metacharacter hazards | **Pass** | References TKT-014 validation directly; testable with invalid command injection |
| 7 | Git stdout/stderr, command rendering, return-code errors sanitized before storage/display | **Pass** | Testable via mock subprocess and log capture |
| 8 | Adapter injectable into TKT-008 without replacing API or bypassing founder merge ack | **Pass** | Architectural constraint, testable via integration test with TKT-008 mocks |
| 9 | Runtime configuration explicit and non-secret | **Pass** | Documented env var names without values; no committed secrets |
| 10 | Unit tests cover REST execution, REST failure redaction, git execution, git failure redaction, command validation, shell avoidance, credential rejection, no Hermes bundled skills | **Pass** | Comprehensive and specific test checklist |
| 11 | Integration tests use mocked HTTP/subprocess by default; optional live smoke path is gated, sanitized, and non-mandatory | **Pass** | Aligns with TKT-NEW-008-B scope without overcommitting |
| 12 | `python scripts/validate_docs.py` passes | **Pass** | Verified on PR HEAD |
| 13 | `python -m unittest discover -s tests -p "test_*.py" -v` passes | **Pass** | Self-referential, verifiable at implementation time |

## 7. Scope And Write-Zone Assessment

| File | Expected Scope | Assessment |
| --- | --- | --- |
| `docs/tickets/TKT-016.md` | Ticket creation/promotion from backlog | **Pass**. New ticket file only. No source code, no test files, no architecture modifications, no prompt changes, no CI changes. Frontmatter and all 10 sections are present. |

No PRD, architecture, ADR, review artifact, prompt, CI workflow, unrelated ticket, or allowlist modifications were made.

## 8. Security / Process Notes

- **Credential source**: `PROJECT_GITHUB_PAT` only. `GITHUB_TOKEN`, `GH_TOKEN`, `~/.git-credentials`, token-bearing remotes, committed config, and CLI arguments are all rejected by explicit AC and test requirements.
- **Token redaction**: Required in AC 4 and AC 7 for REST errors/metadata and git stdout/stderr/command rendering. Aligns with TKT-014 `_redact_url()`, `redact_token()`, and TKT-008 `_redact_value()`.
- **No committed secrets**: Ticket is a docs-only PR. No secrets were introduced.
- **Merge gate**: Non-scope blocks autonomous merge. AC 8 preserves founder acknowledgement.
- **Hermes bundled skills blocked**: Non-scope and PR requirements explicitly require stating this.
- **Telegram authority**: TKT-015 transport is preserved, not reworked. TKT-008 Telegram composition remains unchanged.
- **Reviewer artifact validation**: TKT-008 `attach_review_artifact` path validation (`docs/reviews/` prefix, `.md` suffix) is unaffected.

## 9. Contradictions Check

| Document / Artifact | Contradiction Found |
| --- | --- |
| `ARCH-001` @ `0.2.0` | None |
| `HERMES-RUNTIME-CONTRACT.md` @ `0.2.0` | None |
| `HERMES-SKILL-ALLOWLIST.md` @ `0.1.0` | None |
| `OPERATIONAL-STATE-STORE.md` @ `0.2.0` | None — persistence explicitly excluded as follow-up |
| `ADR-001` @ `0.2.0` | None |
| `ADR-002` @ `0.2.0` | None |
| `ADR-003` @ `0.2.0` | None — no marketplace/unreviewed plugins introduced |
| `TKT-008` @ `0.3.0` | None — protocols preserved, gates preserved |
| `TKT-014` @ `0.1.0` | None — builders and constraints reused directly |
| `TKT-015` @ `0.1.0` | None — transport preserved, not reworked |
| `TKT-011` @ `0.1.0` | None — correctly remains draft and out of scope |
| `TKT-NEW-008-A` | None — correctly excluded |
| `TKT-NEW-008-B` | None — optional gated path only, correctly scoped |
| `TKT-NEW-008-C` | None — correctly excluded |
| `RV-CODE-008` | None — redaction and gate requirements preserved |
| `RV-CODE-014` | None — credential-source and git-constraint requirements preserved |
| `RV-CODE-019` | None — Telegram transport context preserved |
| `CONTRIBUTING.md` | None — ticket lifecycle states, write zones, and review gates respected |
| `AGENTS.md` | None — role discipline and required context rules respected |

## 10. Verdict

**`pass`**

PR #51 correctly creates `docs/tickets/TKT-016.md` as a ready executable ticket. The scope is atomic and implementable: bind TKT-008 `RESTExecutor` and `GitExecutor` protocols to real HTTP and constrained `git` execution using the reviewed TKT-014 request/command builders and `PROJECT_GITHUB_PAT` credential path. Non-scope comprehensively excludes every deferred or prohibited item specified in the review bootstrap. TKT-012 / HERMES-SKILL-ALLOWLIST GitHub credential constraints are complete and precise. TKT-014 constrained git command and credential-source controls are preserved. TKT-008 founder acknowledgement, redaction, PR/review/CI gate, and integration contracts are preserved. Required Context and Allowed Files are sufficient and not overbroad. Acceptance criteria are specific and testable. The ticket correctly uses DeepSeek V4 Pro as the default Executor and does not require a specialist model. No contradictions were found against any referenced architecture, ADR, ticket, or review artifact.

PR #51 is merge-safe from the Reviewer perspective.
