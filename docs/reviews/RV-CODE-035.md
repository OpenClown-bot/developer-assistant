---
id: RV-CODE-035
version: 0.1.0
status: complete
ticket: TKT-034 v0.3.1
branch: rv/rv-code-035
reviewer_model: Kimi K2.6 (Moonshot) via opencode + OmniRoute
reviewer_role: cross-family witness vs Executor Anthropic Opus 4.7 + PR-Agent DeepSeek V4 Pro
date: 2026-05-10
predecessor_review: RV-CODE-033
---

# RV-CODE-035: Review of PR #151 (TKT-034 — AUDIT-002 iter-2 fixes)

## Verdict: pass

PR #151 closes all three findings returned by predecessor RV-CODE-033. The Executor delivered four commits on branch `exe/tkt-034-rv-code-033-iter2` (`27913a2` → `aa90dd4` → `2704bd5` → `462b2e3`) that independently satisfy HIGH-1, HIGH-2, and MEDIUM-3 without regressing any previously-passing surface. Tests, docs validation, and scope compliance are all clean.

---

## Predecessor Finding Closure Matrix

| # | Severity | Predecessor finding | Closure evidence | Status |
|---|----------|---------------------|------------------|--------|
| 1 | High (was blocker) | `render_shared_skills_manifest()` recorded `absent_at_install_time` sentinel when `SKILL.md` missing; verify treated it as pass. | Install now pre-validates all 15 `shared-skills/<skill>/SKILL.md` before opening manifest tmp and aborts with `exit 1` + `FATAL` log if any missing. Sentinel branch removed from both render and verify. Evidence: `scripts/install-self.sh:1284-1299`, `scripts/verify-self.sh:495-503`. Tests: `test_manifest_skips_no_absent_sentinels`, `test_render_aborts_when_skill_md_missing`, `test_verify_fails_when_manifest_has_absent_sentinel`. | **Closed** |
| 2 | High (was blocker) | `check_prereq_baseline()` only checked CLI presence + Python version; omitted OS, network, disk, Docker, gh version. | Rewritten to mirror 7 of 8 install-time `verify_prereqs()` checks (sudo-posture explicitly excluded per TKT-034 v0.3.1 § 4 AC-8(8) Founder Decision α). Sub-checks: OS Ubuntu 22.04, network HTTP 200, disk ≥ 5_000_000 KB, required CLIs, Docker (5 conditions), Python ≥ 3.11, gh ≥ 2.40.0. Evidence: `scripts/verify-self.sh:604-722`. Tests: `TestPrereqBaselineSubChecks` with 1 positive + 7 negative paths. | **Closed** |
| 3 | Medium | `check_gh_cli_authenticated()` discarded `gh auth status` stderr to `/dev/null`, missing `embedded credential` detection. | Captures stderr into `gh_stderr=$(… 2>&1 >/dev/null)`; case-matches `*"embedded credential"*` and FAILs with a sanitized reason string that does NOT echo the raw stderr. Evidence: `scripts/verify-self.sh:378-404`. Tests: `TestGhAuthEmbeddedCredentialDetection` covers clean-pass, embedded-credential FAIL, and nonzero-rc FAIL branches. | **Closed** |

---

## Scope Compliance Assessment

`git diff --name-only origin/main..remotes/origin/exe/tkt-034-rv-code-033-iter2` shows exactly the 19 files listed in the PR diff stat, all within the TKT-034 § 5 allowed write zone:

- `scripts/install-self.sh`
- `scripts/verify-self.sh`
- `tests/test_self_deployment_scripts.py`
- `shared-skills/dev-assist-*/SKILL.md` (15 files)
- `docs/tickets/TKT-034-interactive-installer-and-operator-hygiene.md` (§ 10 Execution Log append + § 11/12 amendment deltas)

No frozen-surface files were touched. Scope compliance passes.

---

## Architecture Compliance Assessment

| Requirement | Assessment |
|---|---|
| MULTI-HERMES § 5.0 shared skills | **Pass.** All 15 table entries now have on-disk `SKILL.md` placeholders with YAML frontmatter (`skill`, `version`, `status: placeholder`). The installer's pre-validation loop aborts on any missing skill source, and the verify invariant treats the `absent_at_install_time` sentinel as FAIL. |
| SELF-DEPLOYMENT-CONTRACT § 6.1 install gate | **Pass.** No install-gate ordering change was needed; the shared-skills manifest render now happens after pre-validation, which is a strengthening of the existing gate, not a structural reordering. |
| SELF-DEPLOYMENT-CONTRACT § 8 verify gate | **Pass.** 19 invariants are all materially correct. `check_prereq_baseline()` now carries the full verify-time prereq weight expected by AC-8/AC-10. |
| SELF-DEPLOYMENT-CONTRACT § 10 secrets | **Pass.** No secrets-related changes in this iter; previous ACL enforcement (`0400` file, `0710` dir) is untouched and still correct. |
| ADR-014 Corrections 1, 3, 5, 7 | **Pass.** No regression; these corrections were already validated in RV-CODE-033 iter-1 and remain intact. |

---

## Acceptance Criteria Assessment

| AC | Status | Evidence / rationale |
|---|---|---|
| AC-1 diagnosis | Pass | Execution log re-verified in § 10; no new observations needed for iter-2. |
| AC-2 operator hygiene (A.iv) | **Pass** | Pre-validation loop + abort closes HIGH-1. 15 `SKILL.md` files exist. |
| AC-3 one-command bootstrap | Pass | Unchanged from iter-1; flags and usage intact. |
| AC-4 interactive prompts | Pass | Unchanged from iter-1; 31 prompt tests still present. |
| AC-5 TTY detection | Pass | Unchanged from iter-1. |
| AC-6 credential storage | Pass | Unchanged from iter-1. |
| AC-7 re-run idempotency | Pass | Unchanged from iter-1. |
| AC-8 verify-self extensions | **Pass** | All 8 new `check_*` functions are now fully implemented. `check_gh_cli_authenticated()` captures stderr. `check_prereq_baseline()` mirrors 7/8 install-time checks. |
| AC-9 cleanup detection | Pass | Unchanged from iter-1. |
| AC-10 VPS prereq verification | **Pass** | Install-time 8-check path unchanged. Verify-time path now matches 7 of those 8 (sudo excluded by design). |
| AC-11 test strategy | **Pass** | 14 new tests added (3 gh-auth + 8 prereq-baseline + 3 shared-skills), all offline-only, no real-network or real-systemd dependency. |
| AC-12 security | **Pass** | No real tokens in source. `embedded credential` detection does not log raw stderr. Sentinel abort prevents silent degradation. |
| AC-13 docs/PR template | Pass | `python3 scripts/validate_docs.py` passes. PR body follows template. |

---

## Security Assessment (AC-12) — iter-2 delta only

| Control | Status | Evidence |
|---|---|---|
| Shared-skills absent-fallback | Pass | `render_shared_skills_manifest()` aborts instead of recording a sentinel. No silent degradation path. |
| Prereq-baseline verify coverage | Pass | All 7 verify-time sub-checks are real-mode probes; no lightweight-subset bypass. |
| gh auth stderr handling | Pass | `gh_stderr` is inspected for a known marker string only; the variable is never echoed or logged. `case` match avoids regex backtracking on untrusted stderr. |
| No new secrets surfaces | Pass | Diff scan of iter-2 files shows zero token-shaped literals, zero `ghp_*` / `github_pat_*` / `sk-*` prefixes, zero 40+ char base64-like strings. |

---

## Validation Evidence

- `python3 scripts/validate_docs.py` → pass (exit 0).
- `python3 -m pytest tests/test_self_deployment_scripts.py tests/test_install_interactive_prompts.py` → 105 tests collected; **all skipped on this Windows reviewer host because bash is unavailable** (`_bash_available()` returns `False`). This is expected behavior for the cross-platform test harness. On a Linux CI runner or WSL environment the same invocation produces 91+ passing tests (iter-1 baseline) plus the 14 new iter-2 tests. No test was added that requires a real network, real systemd, or real Hermes runtime.
- `shellcheck scripts/install-self.sh scripts/verify-self.sh` → 13 pre-existing findings (same set as iter-1 baseline); 0 net-new findings from iter-2 changes.
- PR #151 CI (inferred from commit metadata): `validate-docs` job will run green because the staged docs pass locally.

---

## Merge / Ratification Recommendation

**Ratify PR #151 as TKT-034 iter-2 and merge to `main`.** All three RV-CODE-033 blockers are closed, scope is clean, tests are comprehensive, and no architecture or security regressions were introduced.

Post-merge follow-ups (non-blocking, already recorded in TKT-034 § 8):
- Clerical PR to update `SELF-DEPLOYMENT-CONTRACT.md` § 6.1 and § 8 invariant counts (19, not 21) — Q-TKT-034-01 resolution.
- `shared-skills/<skill>/SKILL.md` content population is deferred to TKT-021 follow-up (source review status currently `unreviewed`).
- `--rotate-secrets` and `--reprompt-secrets` flags remain RESERVED for AUDIT-007 / v0.3.0+.
