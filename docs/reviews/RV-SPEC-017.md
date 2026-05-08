---
id: RV-SPEC-017
version: 0.1.0
status: complete
review_target: PR-123
target_iter: 2
target_head: 2a125bfca4da6b97877fff9809b7439135921284
target_iter_predecessor_head: b9dbb99f932eb9dc95ff207a64fbd22dbf235544
prior_review: RV-SPEC-016
reviewer_model: Devin
created: 2026-05-08
---

# RV-SPEC-017: Iter-2 Verify Pass of PR #123 — TKT-033 runtime_check enforcement at systemd boot

## 1. PR Meta

- **PR**: #123
- **Branch**: `arch/audit-001-runtime-check-enforcement`
- **Iter-2 head reviewed**: `2a125bfca4da6b97877fff9809b7439135921284`
- **Iter-1 predecessor head**: `b9dbb99f932eb9dc95ff207a64fbd22dbf235544`
- **Prior review**: RV-SPEC-016 (PR #124)
- **Files changed in iter-2 delta**: `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md`
- **Diff shape**: 9 default-context unified diff hunks, 25 insertions, 24 deletions
- **Iter-2 CI checked**: `validate-docs` completed / success; `Run PR Agent on every pull request` completed / success

## 2. Review Findings

### 2.A RV-SPEC-016 Finding 2.2: prompt-path key and per-role manifest mapping — Severity: none (closed)

Iter-2 closes the prompt-path precision gap. The obsolete `agent.system_prompt_path` string is absent from the iter-2 spec body. The invariant now names the actual runtime key, `system_prompt.path`, in component B, the reader contract, row-13 diagnosis, and AC-3 (iii) (`docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:23`, `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:43`, `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:133`, `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:142`).

The manifest example and per-role mapping now point at canonical prompt files, including `docs/prompts/runtime-hermes-orchestrator.md` for the runtime Orchestrator and `docs/prompts/business-planner.md` for Planner (`docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:31`, `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:36`, `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:41`). The mapping explicitly makes `AGENTS.md` the canonical authority and treats `docs/prompts/<role>.md` shorthand as notation resolved through that mapping (`docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:41`, `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:100`).

- **Result**: closed.
- **Escalation needed**: false.

### 2.B RV-SPEC-016 Finding 2.3: required-context and dependency version pins — Severity: none (closed)

Iter-2 adds the missing version pins in § 3 Required Context for HERMES-RUNTIME-CONTRACT v0.2.0, HERMES-SKILL-ALLOWLIST v0.1.1, ADR-005 v0.1.0, TKT-020 v0.2.0, TKT-021 v0.1.1, and TKT-032 v0.1.0 (`docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:107`, `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:110`, `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:115`, `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:117`).

§ 9 Dependencies now carries the same substantive pins for the compound architecture list and the TKT-020/TKT-021 dedicated bullets (`docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:217`, `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:219`). Inline body references touched by the iter-2 pass are also pinned on first relevant occurrence, including TKT-021/TKT-020/TKT-032 in § 1 and § 4, plus HERMES-SKILL-ALLOWLIST in § 8 (`docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:12`, `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:139`, `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:213`).

- **Result**: closed.
- **Escalation needed**: false.

### 2.C RV-SPEC-016 Finding 2.4: AC-4 advisory test-placement wording — Severity: none (closed)

AC-4 now uses the requested Option A wording: tests `MUST` be offline-only and `MUST live in either` `tests/test_runtime_check.py` or `tests/test_self_deployment_scripts.py`, with an explicit Executor-choice clause that both locations are acceptable (`docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:147`).

- **Result**: closed.
- **Escalation needed**: false.

### 2.D SO-added sibling fix: canonical TKT-020 filename — Severity: none (closed)

Iter-2 removes the non-existent `docs/tickets/TKT-020-self-deployment-implementation.md` filename from the spec body. The spec now uses canonical `docs/tickets/TKT-020.md` / `TKT-020.md` references with v0.2.0 pins in § 1, § 3, § 5, and § 9 (`docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:12`, `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:115`, `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:171`, `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:218`).

- **Result**: closed.
- **Escalation needed**: false.

### 2.E New findings introduced by iter-2 — Severity: none

No new low-or-higher findings were introduced by the iter-2 edits. The delta touches only `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md`; no `MULTI-HERMES`, `AGENTS.md`, `CONTRIBUTING.md`, runtime-template, implementation, test, or CI files changed. The 11-symbolic-name enum remains structurally intact and in the same order (`docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:57`, `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:69`). § 5 Allowed Files keeps the expected surface and the explicit not-allowed list (`docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:153`, `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:173`). Docs validation passes on the iter-2 head, and PR #123 CI is green.

- **Result**: no new defects.
- **Escalation needed**: false.

## 3. AC Reassessment

### AC-1 — pass

Unchanged and still binary: the spec records the live diagnosis and requires Executor branch-cut re-verification before implementation proceeds.

### AC-2 — pass

Unchanged and still binary: all five unit templates must invoke the runtime check from `ExecStartPre=`, fail the unit on non-zero exit, and avoid auto-restart on invariant-class aborts.

### AC-3 — pass

Previously partial in RV-SPEC-016; now full. The prompt invariant uses `system_prompt.path`, resolves canonical prompt files through § 1 component C, and keeps both prompt mismatch and missing-manifest hard-fail modes.

### AC-4 — pass

Previously partial in RV-SPEC-016; now full. Test placement is mandatory but flexible between the two named test files, with no advisory `SHOULD` wording left.

### AC-5 — pass

Unchanged and still binary: all eleven invariants must emit the stable marker before raising existing exception types, preserving TKT-021's raise-side contract.

### AC-6 — pass

Unchanged and still binary: branch-cut baseline count discipline is explicit, validation and unittest discover remain required, and pre-existing failures must not be hidden.

### AC-7 — pass

Unchanged and still binary: real tokens, production hostnames, and credential values are forbidden from repo artifacts and test fixtures.

## 4. Security Check

- The iter-2 diff introduces no real `TELEGRAM_BOT_TOKEN`, `GITHUB_TOKEN`, `FIREWORKS_API_KEY`, `OMNIROUTE_API_KEY`, `OPENROUTER_API_KEY`, raw PAT, or production hostname.
- The added prompt-manifest mapping contains file paths and SHA placeholders only, not prompt bodies or credentials.
- The TKT-020 filename correction and version pins do not alter credential handling or merge authority.
- PR #123 iter-2 CI is both-green: `validate-docs` success and PR-Agent success.

## 5. Final Verdict

**pass**

Finding counts: high 0 / medium 0 / low 0 / none 5. Escalation needed: false. Iter-2 substantively closes all four verification items A-D, introduces no new low-or-higher defects, upgrades the formerly partial AC-3 and AC-4 assessments to pass, keeps the no-regression surface intact, and has green validation/PR-Agent status on the reviewed iter-2 head. The spec is ready for SO ratification and promotion toward the AUDIT-001 Executor cycle.
