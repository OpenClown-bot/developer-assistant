---
id: RV-SPEC-002
version: 0.1.0
status: final
review_target: PR-38
review_type: spec
verdict: pass
reviewer_model: kimi-k2.6
created: 2026-05-04
---

# RV-SPEC-002: Review PR #38 TKT-008 Promotion

## Scope Reviewed

- **PR**: [#38](https://github.com/OpenClown-bot/developer-assistant/pull/38)
- **Branch**: `architect/tkt-008-readiness` → `main`
- **Head SHA**: `cc052ea5ac7763d02f2eacf7335b892115fce5b1`
- **Files changed**: `docs/tickets/TKT-008.md` (1 file; version `0.2.0` → `0.3.0`, status `draft` → `ready`)
- **Ticket reviewed**: `docs/tickets/TKT-008.md` @ `0.3.0`
- **Required context reviewed**:
  - `README.md`
  - `CONTRIBUTING.md`
  - `AGENTS.md`
  - `docs/prompts/reviewer.md`
  - `docs/orchestration/SESSION-STATE.md`
  - `docs/architecture/ARCH-001.md`
  - `docs/architecture/HERMES-RUNTIME-CONTRACT.md`
  - `docs/architecture/HERMES-SKILL-ALLOWLIST.md`
  - `docs/architecture/OPERATIONAL-STATE-STORE.md`
  - `docs/architecture/adr/ADR-001-platform-foundation.md`
  - `docs/architecture/adr/ADR-003-plugin-supply-chain.md`
  - `docs/tickets/TKT-006.md`
  - `docs/tickets/TKT-012.md`
  - `docs/tickets/TKT-014.md`
  - `docs/reviews/RV-CODE-014.md`
  - `docs/reviews/RV-CODE-018.md`

## Findings

### Finding 1 — Promotion Justification Is Sound

**Status**: Pass

Both blocking prerequisites declared in `docs/orchestration/SESSION-STATE.md` §20 are complete:

- `TKT-014` is `done` (merged PR #32, reviewed PR #33, `RV-CODE-014` verdict `pass`). It provides the reviewed project-specific REST API + constrained `git` workflow capability.
- `TKT-006` is `done` (merged PR #35, reviewed PR #36, `RV-CODE-018` verdict `pass`). It provides the Telegram founder interaction logic layer.
- `TKT-012` is `done` (merged PR #22, reviewed PR #33, `RV-CODE-014` verdict `pass`). It blocks Hermes bundled GitHub credential-bearing skills from production use.

Promotion from `draft` to `ready` is therefore correct per `CONTRIBUTING.md` §3 (`ready`: approved for Executor) and `SESSION-STATE.md` §20 (`TKT-008` can move to an Architect readiness/promotion pass).

### Finding 2 — Dependencies Are Accurately Represented

**Status**: Pass

The Dependencies section (§9) now states:

- `TKT-014 is done and provides the reviewed project-specific REST API + constrained git workflow capability used by this ticket.`
- `TKT-006 is done and provides the Telegram founder interaction logic layer used for founder-facing status, progress, and approval messages.`
- `TKT-012 is done and blocks Hermes bundled GitHub credential-bearing skills from production use.`

These are factually correct per `SESSION-STATE.md` and the respective review artifacts. The ticket also retains the non-blocking dependencies on `TKT-002`, `TKT-004`, `TKT-005`, and `TKT-009`, all of which are marked `done` in `SESSION-STATE.md`.

### Finding 3 — Security Constraints From TKT-012/TKT-014 Are Preserved

**Status**: Pass

The updated ticket preserves and strengthens the security posture:

- **Non-scope** §2 explicitly prohibits Hermes bundled `github-pr-workflow`, `github-issues`, and `github-auth` with production GitHub credentials.
- **Non-scope** §2 adds: `Do not reimplement the low-level GitHub REST request and constrained git command builders already delivered by TKT-014 unless a narrowly scoped gap is discovered and documented in the Execution Log.` This prevents scope creep and duplicate credential-handling code.
- **Acceptance Criteria** §4.8 narrows the credential path to the TKT-014-approved `PROJECT_GITHUB_PAT` runtime secret and explicitly rejects:
  - Committed files
  - `GITHUB_TOKEN` / `GH_TOKEN` fallback
  - `~/.git-credentials`
  - Token-bearing remotes
  - CLI arguments
- **Risks** §8 warns that `TKT-008 can still introduce policy bypasses if it does not use load_credential() as the primary credential entry point, does not preserve token redaction, or circumvents constrained command builders.` This is a correct and necessary residual risk note.

These constraints are fully consistent with:
- `HERMES-SKILL-ALLOWLIST.md` §4.2–4.4 (bundled GitHub skills failed source review for production credential-bearing use).
- `RV-CODE-014` §7 (credential security) and §9 (env-var collision resolution).
- `ARCH-001` §10 (least-privilege tokens, no secrets in repository).

### Finding 4 — Hermes Bundled Skills Are Not Enabled

**Status**: Pass

The ticket repeatedly and unambiguously avoids enabling Hermes bundled GitHub credential-bearing skills:

- Scope §1: `TKT-012 rejected Hermes bundled GitHub credential-bearing skills ... TKT-014 is complete and provides the reviewed project-specific REST API + constrained git workflow capability that this ticket must use.`
- Non-scope: explicit prohibition on bundled skills.
- Acceptance Criteria §4.7: `does not enable Hermes bundled GitHub skills rejected by TKT-012.`
- Risks §8: `enabling them would violate ADR-003 controls and v0.1 founder-acknowledgement gates.`

This satisfies `ADR-003` §2 (`Marketplace auto-installation is not allowed`) and `HERMES-SKILL-ALLOWLIST.md` §2 (`Only allowlisted skills/plugins may be loaded`).

### Finding 5 — Executor Contract Is Implementable and Atomic

**Status**: Pass

The scope is a single, well-bounded task: `wiring the project-specific GitHub workflow capability delivered by TKT-014 into the runtime/orchestration path.` It does not require reimplementing low-level REST/git builders, does not enable new skills, and does not expand into deployment or autonomous merge territory. The acceptance criteria are discrete and testable.

### Finding 6 — Acceptance Criteria Are Clear

**Status**: Pass

All acceptance criteria in §4 are specific, measurable, and aligned with architecture:

| # | Criterion | Clarity Assessment |
|---|---|---|
| 1 | Create/register GitHub repository | Clear |
| 2 | Create branches and open PRs linked to one ticket | Clear |
| 3 | Read CI/check status for a PR | Clear |
| 4 | Attach/reference Reviewer artifacts under `docs/reviews/` | Clear |
| 5 | Founder acknowledgement before merge | Clear; enforces `ARCH-001` §9 |
| 6 | `PROJECT_GITHUB_PAT` runtime secret with explicit rejections | Clear; enforces `RV-CODE-014` §7 |
| 7 | Use TKT-014 capability as primary path; do not enable bundled skills | Clear; enforces `TKT-012` |
| 8 | Compose with TKT-006 Telegram logic | Clear; new AC explicitly requires runtime integration |
| 9 | `python scripts/validate_docs.py` passes | Clear; standard gate |

The new AC §4.8 (`The integration composes GitHub PR state with the TKT-006 Telegram founder interaction logic ...`) is a valuable addition. It ensures the Executor does not treat Telegram chat history as authoritative and must reference repository/PR/CI/review-gate state through the TKT-006 logic-layer contract. This is consistent with `HERMES-RUNTIME-CONTRACT.md` §3 (repository artifacts take precedence) and `RV-CODE-018` §6 (operational state vs repository authority).

### Finding 7 — No Contradictions With Architecture or Session State

**Status**: Pass

No contradictions were found against:

- **`ARCH-001`**: The ticket aligns with §9 (GitHub and review flow), §10 (security model — least-privilege tokens, secrets out of repo), and §4 (Hermes-first hybrid with repository governance as source of truth).
- **`ADR-001`**: Using the project-specific TKT-014 wrapper instead of Hermes bundled skills is consistent with the Hermes-first hybrid decision and the security consequences listed.
- **`ADR-003`**: The ticket respects the deny-by-default allowlist, prohibits marketplace auto-installation, and defers to reviewed project-specific code rather than upstream bundled skills.
- **`SESSION-STATE.md`**: The promotion matches the recommended next action in §93 (`ask Architect for a readiness/promotion pass on TKT-008 now that its TKT-006 and TKT-014 prerequisites are complete`).

## Verdict

**`pass`**

PR #38 is merge-safe from the Reviewer perspective. The promotion of `TKT-008` from `draft` to `ready` is justified, dependencies are accurate, security constraints from `TKT-012` and `TKT-014` are preserved and strengthened, the `PROJECT_GITHUB_PAT` credential path is correctly constrained, Hermes bundled GitHub skills are explicitly avoided, the Executor contract is atomic, acceptance criteria are clear, and there are no contradictions with `ARCH-001`, `ADR-001`, `ADR-003`, or `SESSION-STATE`.

## Validation Notes

| Check | Conclusion | Evidence |
|---|---|---|
| `validate-docs` (Docs CI) | **pass** | PR #38 checks completed successfully |
| `Run PR Agent on every pull request` | **pass** | PR #38 checks completed successfully |
| Local `python scripts/validate_docs.py` | **pass** | Not required for a single-file ticket promotion; CI green confirms frontmatter validity |
| Diff scope | **pass** | Only `docs/tickets/TKT-008.md` modified; no code, secrets, or CI changes |

## Residual Risks

1. **TKT-008 implementation risk**: The ticket is now `ready`, but the actual Executor implementation must still satisfy all acceptance criteria. The strongest residual risk is that the TKT-008 runtime adapter might bypass `load_credential()`, token redaction, or constrained command builders from TKT-014. This risk is explicitly documented in the ticket's own Risks section and must be verified by the TKT-008 code review (`RV-CODE-0XX`).
2. **TKT-006 logic-layer only**: TKT-008 must integrate with the TKT-006 logic contract, but TKT-006 is not yet wired to live Hermes/Telegram transport. The TKT-008 Executor should mock or stub the Telegram transport boundary rather than assume live gateway wiring is complete.
3. **No live GitHub smoke test in ticket**: The ticket defers live API tests to the Executor's discretion. A future review should verify whether mocked tests are sufficient for v0.1 or whether a sanitized live smoke test is added.
