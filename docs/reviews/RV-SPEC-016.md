---
id: RV-SPEC-016
version: 0.1.0
status: complete
verdict: pass_with_changes
review_target: PR-123
review_type: spec
reviewer_model: Devin
created: 2026-05-08
---

# RV-SPEC-016: SPEC Review of PR #123 — TKT-033 runtime_check enforcement at systemd boot

## 1. PR Reviewed

- **PR**: #123
- **Title**: TKT-033 — runtime_check enforcement at systemd boot
- **Branch**: `arch/audit-001-runtime-check-enforcement`
- **Head SHA reviewed**: `b9dbb99f932eb9dc95ff207a64fbd22dbf235544`
- **Merge state**: open, mergeable
- **Files changed**: `docs/tickets/TKT-033.md`
- **Change summary**: Adds the AUDIT-001 spec ticket for enforcing `runtime_check.check_runtime()` at systemd boot, structured boot-failure markers, three new runtime invariants, prompt-manifest design, validation requirements, and PR/review gates.

## 2. Review Findings

### 2.1 No high-severity findings — Severity: none

No finding invalidates TKT-033 as written. The spec is correctly scoped to AUDIT-001 boot-time runtime-check enforcement, keeps AUDIT-002/003/004 out of scope, does not touch ADR-014's infrastructure corrections, and contains no real secrets or production credential values.

### 2.2 Prompt-path invariant needs exact runtime key and per-role path mapping — Severity: medium

TKT-033 defines the new prompt invariant using `agent.system_prompt_path` and `docs/prompts/<role>.md`, then gives a manifest example containing `docs/prompts/orchestrator.md` and `docs/prompts/business-planner.md` (`docs/tickets/TKT-033.md:48`, `docs/tickets/TKT-033.md:97`, `docs/tickets/TKT-033.md:100`, `docs/tickets/TKT-033.md:128`). The merged runtime templates expose the rendered value as `system_prompt.path`, not `agent.system_prompt_path` (`etc/runtime-templates/orchestrator/config.yaml.tmpl:38`, `etc/runtime-templates/planner/config.yaml.tmpl:38`), and the canonical prompt inventory names the runtime orchestrator prompt as `docs/prompts/runtime-hermes-orchestrator.md` and the planner prompt as `docs/prompts/business-planner.md` (`AGENTS.md:11`, `AGENTS.md:12`, `CONTRIBUTING.md:23`).

This is not a scope error: AUDIT-001 is supposed to catch prompt-path drift. It is, however, a precision gap before Executor dispatch. Iter-2 should pin the exact YAML key to inspect and the exact expected prompt path for each role, instead of relying on `<role>.md` shorthand or a partially stale example.

- **Checklist impact**: C-6, C-13, E-1.
- **Escalation needed**: false.

### 2.3 Required-context and dependency version pins are incomplete — Severity: medium

The review checklist requires every non-trivial context/dependency reference to be version-pinned. TKT-033 pins some references, but § 3 and § 9 leave several material sources unpinned or only status-pinned: `HERMES-RUNTIME-CONTRACT.md`, `HERMES-SKILL-ALLOWLIST.md`, ADR-005, ADR-011, TKT-020, and TKT-021 (`docs/tickets/TKT-033.md:62`, `docs/tickets/TKT-033.md:72`, `docs/tickets/TKT-033.md:73`, `docs/tickets/TKT-033.md:75`, `docs/tickets/TKT-033.md:76`, `docs/tickets/TKT-033.md:218`). Those artifacts have concrete versions in frontmatter, including HERMES-RUNTIME-CONTRACT v0.2.0, HERMES-SKILL-ALLOWLIST v0.1.1, ADR-005 v0.1.0, ADR-011 v0.1.1, TKT-020 v0.2.0, and TKT-021 v0.1.1 (`docs/architecture/HERMES-RUNTIME-CONTRACT.md:2`, `docs/architecture/HERMES-SKILL-ALLOWLIST.md:2`, `docs/architecture/adr/ADR-005-multi-hermes-runtime-isolation.md:2`, `docs/architecture/adr/ADR-011-routing-layer.md:2`, `docs/tickets/TKT-020.md:2`, `docs/tickets/TKT-021.md:2`).

This does not change the intended implementation, but it weakens spec reproducibility. Iter-2 should pin these references explicitly.

- **Checklist impact**: C-4, C-17.
- **Escalation needed**: false.

### 2.4 AC-4 test placement uses advisory wording — Severity: low

AC-4 says the new tests "SHOULD live either" in `tests/test_runtime_check.py` or another focused unittest file (`docs/tickets/TKT-033.md:105`). The rest of AC-4 is binary and enforceable, so this is not blocking; replacing the advisory placement language with a required location or explicitly stating either location is acceptable would make the AC cleaner for RV-CODE review.

- **Checklist impact**: C-5.
- **Escalation needed**: false.

### 2.5 Passing checklist summary — Severity: none

All other internal, external, and hard-rule checks pass: frontmatter and draft status are correct; scope/non-scope stay within AUDIT-001; AC-1..AC-8 are largely binary-decidable; marker grammar and the 11-name invariant enum are defined; manifest missing/unreadable is a hard failure; allowed files cover the expected runtime-check, install, unit-template, verify, and test surfaces; PR requirements preserve the two-PR pipeline and Founder acknowledgement; risks cover schema drift, marker compatibility, and manifest-renderer regression; execution log is empty; PR #123 only changes `docs/tickets/TKT-033.md`, which is inside the Architect write zone; the prose is English; and no real secrets or production hostnames were introduced.

## 3. AC Assessment

### AC-1 — pass

The AC requires an executable wrapper around `runtime_check.check_runtime()` and names the role, config path, operational DB path, and environment inputs needed for offline review.

### AC-2 — pass

The AC requires all five systemd unit templates to run the check from `ExecStartPre=`, emit `RUNTIME_CHECK_FAILED:<role>:<invariant_name>`, and avoid masking invariant failures with `Restart=always`.

### AC-3 — partial

The delegate-task and skill-manage invariants are testable and tied to marker names, but the prompt-path invariant needs the exact runtime config key and per-role prompt path mapping clarified before Executor dispatch.

### AC-4 — partial

The required negative regression cases are present, but the advisory test-placement wording and the AC-3 prompt-path ambiguity make this only partially ready for RV-CODE use.

### AC-5 — pass

The AC preserves existing exception classes while allowing a structured base exception/interface for marker emission, so it avoids unnecessary test churn.

### AC-6 — pass

The AC uses a baseline-at-cut formulation for the full unittest suite and requires no regression relative to the Executor's branch baseline.

### AC-7 — pass

The AC requires an explicit secrets/production-hostname audit covering the new unit files, marker output, manifest, tests, and docs.

### AC-8 — pass

The AC preserves the two-PR pipeline, requires RV-SPEC before Executor dispatch, RV-CODE before merge-safe signoff, and Founder acknowledgement before merge.

## 4. Security Notes

- **Secrets audit**: No real `TELEGRAM_BOT_TOKEN`, `GITHUB_TOKEN`, `FIREWORKS_API_KEY`, `OMNIROUTE_API_KEY`, raw PAT, or production hostname appears in TKT-033.
- **Boot-failure markers**: The marker grammar carries role and invariant identifiers only; it does not require secret values in journald.
- **Prompt manifest**: The manifest stores SHA-256 digests and file paths, not prompt bodies or secrets. The fail-closed behavior is appropriate, but it increases boot sensitivity to renderer bugs; TKT-033 correctly records that risk.
- **Architectural exposure**: No new credential surface, merge path, or autonomous runtime capability is authorized by the spec.

## 5. Final Verdict

**pass_with_changes**

TKT-033 is directionally correct and faithful to AUDIT-001, with no high-severity blocker or Founder-decision escalation. Two medium-severity precision gaps should be fixed before Executor dispatch: pin the prompt-path invariant to the actual runtime config key and canonical per-role prompt paths, and version-pin the remaining non-trivial context/dependency references. After those iter-2 changes, the spec should be ready for SO ratification and AUDIT-001 Executor dispatch.
