---
id: RV-SPEC-005
version: 0.1.0
status: complete
verdict: pass
reviewer_model: kimi-k2.6
created: 2026-05-04
review_target: PR-57
review_type: spec
---

# RV-SPEC-005: Review of PR #57 — TKT-017 Live Smoke Readiness

## 1. PR Reviewed

- **PR**: [#57](https://github.com/OpenClown-bot/developer-assistant/pull/57)
- **Title**: Add TKT-017 live smoke readiness ticket
- **Branch**: `arch/tkt-017-live-smoke-readiness` → `main`
- **Head SHA**: `741fe79`
- **Changed files**: 1
  - `docs/tickets/TKT-017.md` (new, 140 lines)

## 2. Ticket Reviewed

- **Ticket**: `docs/tickets/TKT-017.md` @ `0.1.0`
- **Source backlog**: `TKT-NEW-008-B`
- **Status at review time**: `ready`
- **Scope**: Sanitized live-smoke readiness check covering two lanes — Telegram/Hermes gateway smoke (TKT-015 boundary) and GitHub REST/`git` smoke (TKT-008/TKT-014/TKT-016 boundary) — to produce evidence that unblocks a later `TKT-011` end-to-end trial.

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
  - `TKT-006.md` @ `0.1.0` (done)
  - `TKT-008.md` @ `0.3.0` (done)
  - `TKT-011.md` @ `0.1.0` (draft, correctly not executed)
  - `TKT-014.md` @ `0.1.0` (done)
  - `TKT-015.md` @ `0.1.0` (done)
  - `TKT-016.md` @ `0.1.0` (done)
  - `TKT-NEW-008-A.md` @ `0.1.0` (backlog, correctly excluded)
  - `TKT-NEW-008-B.md` @ `0.1.0` (backlog, promoted into this ticket)
  - `TKT-NEW-008-C.md` @ `0.1.0` (backlog, correctly excluded)
  - `RV-CODE-008.md`, `RV-CODE-014.md`, `RV-CODE-019.md`, `RV-CODE-020.md`, `RV-SPEC-004.md`

## 4. CI Status

| Check | Conclusion |
| --- | --- |
| Docs validation (`python scripts/validate_docs.py`) | **pass** |
| PR-Agent (`Run PR Agent on every pull request`) | **pass** — no security concerns, no major issues |

## 5. Findings (ordered by severity)

No blocking, security-class, or non-blocking findings require changes. The following are informational observations.

### Info — Required Context list is large (23 files)

- **Location**: `docs/tickets/TKT-017.md` §3 Required Context
- **Description**: The Required Context list includes 23 files spanning architecture, ADRs, tickets, backlog, and review artifacts. This is correct for a cross-cutting readiness ticket that touches Telegram transport, GitHub integration, credential paths, and runtime contracts, but it creates a significant Executor reading burden.
- **Impact**: Low. The list is accurate and necessary; no files should be removed.
- **Recommendation**: None required. The Executor must read all listed files before implementation.

### Info — Ticket covers two independent smoke lanes in one implementation

- **Location**: `docs/tickets/TKT-017.md` §1 Scope
- **Description**: The ticket combines Telegram smoke and GitHub smoke into a single ticket. If only one lane has live credentials available, the other lane will record `blocked` per AC 8. This is acceptable because the ticket is a readiness gate, not a feature delivery, and AC 8 requires per-lane `pass`/`blocked`/`fail` reporting.
- **Impact**: None.
- **Recommendation**: None required. The Executor should report each lane independently.

### Praise — TKT-011 execution prevention is layered and fail-closed

- **Location**: `docs/tickets/TKT-017.md` §2, §4 AC 12–13, §7 PR Requirements, §9 Dependencies
- **Description**: The ticket prevents accidental TKT-011 execution through four independent layers: (1) Non-scope item #1 explicitly prohibits TKT-011 execution; (2) AC 12 requires evidence to state TKT-011 status is unchanged; (3) AC 13 requires blockers to be recorded before any TKT-011 attempt; (4) PR Requirements item 7 mandates stating TKT-011 remains draft; (5) Dependencies explicitly state TKT-011 must not be executed until a later Orchestrator/Architect step decides readiness. This is a comprehensive fail-closed design.

### Praise — Security constraints are exhaustive and map directly to prior review hardening

- **Location**: `docs/tickets/TKT-017.md` §2, §4 AC 2/4/9/10/11, §6, §7, §8
- **Description**: The ticket preserves every security constraint established by TKT-012, TKT-014, TKT-015, and TKT-016: `PROJECT_GITHUB_PAT` only (AC 2); TKT-014 constrained `GitCommand` builders and TKT-016 runtime executors (AC 4); no token values, raw chat IDs, raw user IDs, `.env`, credential files, token-bearing remotes in artifacts/logs/tests/exceptions (AC 9); no Hermes bundled GitHub skills, marketplace skills, project-local plugins, OpenClaw, autonomous merge (AC 10); smoke PR must not merge (AC 11); manual diff inspection before review for secrets (§6); env var names documented without values (§7). The fail-closed `blocked` outcome when credentials are unavailable (AC 8) prevents bypass.

### Praise — Live evidence requirements are concrete and testable

- **Location**: `docs/tickets/TKT-017.md` §4 AC 3/5/6/7/8
- **Description**: GitHub smoke specifies the exact minimal sequence (repo registration or current repo, unique smoke branch, constrained git transport, PR open/draft, check-status read, PR metadata read, cleanup). Telegram smoke specifies exact commands and free-form classification. Evidence format is explicitly defined (sanitized labels, URLs, outcomes, timestamps). Per-lane pass/block/fail reporting is mandatory. This is specific enough for Executor handoff.

### Praise — TKT-NEW-008-A and TKT-NEW-008-C correctly remain separate

- **Location**: `docs/tickets/TKT-017.md` §2, §9 Dependencies
- **Description**: Non-scope explicitly excludes idempotent retry behavior (TKT-NEW-008-A) and GitHub state persistence (TKT-NEW-008-C). Dependencies restate both as separate follow-ups with correct priority rationale. The ticket does not absorb scope that belongs to backlog items.

## 6. Acceptance Criteria Assessment

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Smoke entry point or documented manual procedure exists for GitHub live smoke, disabled by default | **Pass** | Explicitly testable; gated by non-secret env flag |
| 2 | GitHub smoke uses `PROJECT_GITHUB_PAT` only, rejects prohibited credential paths | **Pass** | Maps to TKT-014/TKT-016 credential-source hardening |
| 3 | GitHub smoke performs smallest safe live sequence with cleanup expectations | **Pass** | Exact sequence defined in AC text |
| 4 | GitHub smoke uses TKT-014/TKT-016 builders/executors, no raw shell or dangerous git | **Pass** | Directly references reviewed constraints |
| 5 | Telegram smoke verifies live Hermes gateway readiness through TKT-015 boundary | **Pass** | Commands and classification path specified |
| 6 | Telegram smoke enforces TKT-012/TKT-015 constraints | **Pass** | Allowlist, polling, webhook secret, approved token storage |
| 7 | Smoke records only sanitized evidence | **Pass** | Explicit evidence format list |
| 8 | Evidence states `pass`/`blocked`/`fail` per lane; `blocked` when credentials/runtime unavailable | **Pass** | Fail-closed design |
| 9 | No secrets or raw private identifiers in artifacts, logs, tests, exceptions, evidence | **Pass** | Comprehensive prohibition list |
| 10 | No Hermes bundled skills, marketplace skills, plugins, OpenClaw, autonomous merge, live deployment | **Pass** | Matches HERMES-SKILL-ALLOWLIST |
| 11 | Smoke PR is not merged automatically | **Pass** | Explicit AC and PR requirement |
| 12 | If smoke passes, evidence states TKT-011 may be considered separately; ticket does not change TKT-011 status | **Pass** | Prevents scope creep into orchestration |
| 13 | If smoke blocks/fails, evidence records blocker before any TKT-011 attempt | **Pass** | Fail-closed |
| 14 | `python scripts/validate_docs.py` passes | **Pass** | Verified on PR HEAD |
| 15 | `python -m unittest discover -s tests -p "test_*.py" -v` passes if code changed | **Pass** | Self-referential, verifiable at implementation time |

## 7. Scope and Write-Zone Assessment

| File | Expected Scope | Assessment |
| --- | --- | --- |
| `docs/tickets/TKT-017.md` | Ticket creation/promotion from backlog | **Pass**. New ticket file only. No source code, no test files, no architecture modifications, no prompt changes, no CI changes, no backlog metadata edits. Frontmatter and all 10 sections are present. |

No PRD, architecture body, ADR, review artifact, prompt, CI workflow, unrelated ticket, or backlog modifications were made.

## 8. Security / Process Notes

- **Credential source**: `PROJECT_GITHUB_PAT` only. `GITHUB_TOKEN`, `GH_TOKEN`, `~/.git-credentials`, token-bearing remotes, committed config, and CLI arguments are all rejected by explicit AC, non-scope, and PR requirements.
- **Token redaction**: Required in AC 7 and AC 9 for all output channels. Aligns with TKT-014 `_redact_url()`, `redact_token()`, and TKT-008 `_redact_value()`.
- **No committed secrets**: Ticket is a docs-only PR. No secrets were introduced.
- **Raw identifier protection**: AC 9 and non-scope explicitly prohibit raw Telegram chat IDs, raw Telegram user IDs, and private runtime config in all repository artifacts.
- **Merge gate**: AC 11 and non-scope block autonomous merge. PR Requirements item 6 preserves founder acknowledgement.
- **Hermes bundled skills blocked**: AC 10, non-scope, and PR Requirements explicitly require stating this.
- **Telegram authority**: TKT-015 transport constraints are preserved in AC 6. TKT-012 gateway review constraints are preserved.
- **TKT-011 isolation**: The ticket is a readiness gate, not an execution path. TKT-011 remains draft and is explicitly excluded from implementation.

## 9. Contradictions Check

| Document / Artifact | Contradiction Found |
| --- | --- |
| `ARCH-001` @ `0.2.0` | None |
| `HERMES-RUNTIME-CONTRACT.md` @ `0.2.0` | None — runtime boundary, validation, and reporting contracts preserved |
| `HERMES-SKILL-ALLOWLIST.md` @ `0.1.0` | None — bundled skills remain blocked, marketplace auto-install prohibited, project-local plugins disabled |
| `OPERATIONAL-STATE-STORE.md` @ `0.2.0` | None — persistence explicitly excluded as TKT-NEW-008-C follow-up |
| `ADR-001` @ `0.2.0` | None |
| `ADR-002` @ `0.2.0` | None |
| `ADR-003` @ `0.2.0` | None — no marketplace/unreviewed plugins introduced |
| `TKT-006` @ `0.1.0` | None — Telegram interaction logic preserved |
| `TKT-008` @ `0.3.0` | None — integration layer and redaction contracts preserved |
| `TKT-011` @ `0.1.0` | None — correctly remains draft and excluded from execution |
| `TKT-014` @ `0.1.0` | None — credential path and constrained git builders reused directly |
| `TKT-015` @ `0.1.0` | None — transport boundary constraints preserved, not reworked |
| `TKT-016` @ `0.1.0` | None — runtime executor binding reused for smoke evidence |
| `TKT-NEW-008-A` | None — correctly excluded |
| `TKT-NEW-008-B` | None — promoted into this ticket appropriately |
| `TKT-NEW-008-C` | None — correctly excluded |
| `RV-CODE-008` | None — redaction and gate requirements preserved |
| `RV-CODE-014` | None — credential-source and git-constraint requirements preserved |
| `RV-CODE-019` | None — Telegram transport context preserved |
| `RV-CODE-020` | None — runtime executor binding and token-redaction preserved |
| `RV-SPEC-004` | None — prior readiness review pattern consistent |
| `CONTRIBUTING.md` | None — ticket lifecycle states, write zones, and review gates respected |
| `AGENTS.md` | None — role discipline and required context rules respected |

## 10. Verdict

**`pass`**

PR #57 correctly creates `docs/tickets/TKT-017.md` as a ready executable readiness ticket. The scope is atomic and implementable: run sanitized live-smoke evidence for the Telegram/Hermes gateway boundary and the GitHub REST/`git` runtime boundary before any `TKT-011` execution attempt.

The ticket is safe before `TKT-011` because:
- It explicitly excludes TKT-011 execution in non-scope, ACs, PR requirements, and dependencies.
- It is fail-closed: unavailable credentials or runtime environment produce `blocked`, not bypass.
- It does not change TKT-011 status regardless of smoke outcome.

Security constraints are complete and layered, preventing secret leakage, raw identifier exposure, unsafe credential paths, token-bearing remotes, and autonomous merge. Acceptance criteria, non-scope, allowed files, validation requirements, PR requirements, and risks are specific enough for Executor handoff. The Architect stayed inside the `docs/tickets/` write-zone with no production code, tests, or review body edits. `TKT-NEW-008-A` and `TKT-NEW-008-C` are correctly left as separate follow-ups.

PR #57 is merge-safe from the Reviewer perspective.
