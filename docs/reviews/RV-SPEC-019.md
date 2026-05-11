---
id: RV-SPEC-019
version: 0.1.0
status: complete
verdict: pass
review_target: PR-170
target_iter: 2
target_head: 2fea8487d322f4c594926b8230d8c092eec36d15
base_head: 3e298c2f3d9b00470ad77312ffc6f19eee9191
review_type: spec
reviewer_model: Kimi K2.6
reviewer_runtime: opencode + OmniRoute
created: 2026-05-12
---

# RV-SPEC-019: Iter-2 Verify Pass of PR #170 — TKT-041 v0.1.1 AUDIT-003 behaviour-level deployment smoke

## 1. PR Meta

- **PR**: #170
- **Branch**: `arch/audit-003-behaviour-level-smoke`
- **Iter-2 head reviewed**: `2fea8487d322f4c594926b8230d8c092eec36d15`
- **Iter-1 head (already reviewed)**: `782e110c2f3d9b00470ad77312ffc6f19eee9191`
- **Prior review**: RV-SPEC-018 (verdict `pass_with_changes`)
- **Files changed in iter-2 delta**: `docs/tickets/TKT-041-behaviour-level-deployment-smoke.md` only
- **Diff shape**: 5 hunks (frontmatter version + updated; AC-7 N2 rationale rewrite; § 7 PR Requirements cross-family Reviewer mandate citation; § 8 Risks N1/N2 mirror line; § 9 Dependencies PR #169 full-chain correction), 20 insertions(+), 10 deletions(-)
- **Iter-2 CI checked**: validate-docs ✓ / validate-identities ✓ / Run PR Agent ✓ (all green; 3 passed / 0 failed / 0 pending)

## 2. Iter-2 Re-Verify Checklist

### 2.1 Frontmatter (lines 1–11) — RESOLVED

`version: 0.1.0 → 0.1.1`, `updated: 2026-05-11 → 2026-05-12`. `status: ready` unchanged; `id`, `arch_ref`, `audit_ref`, `supersedes` unchanged. No other frontmatter keys modified.

### 2.2 § 4 AC-7 (N1 + N2 rationale) — Finding 2.1 RESOLVED

**Old text (v0.1.0):** Cited "≤ 180 s at p95 for `qwen3p6-plus` per `MODEL-CATALOG.md` v0.3.0 § 4.3 latency table — Executor verifies the p95 number at branch-cut" (`docs/tickets/TKT-041-behaviour-level-deployment-smoke.md:205` in iter-1).

**New text (v0.1.1):** Re-framed as "an Architect-estimated upper bound for a single Planner LLM round-trip on the role's catalog main `qwen3p6-plus` (≈ 180s ceiling — see provenance note below)" (`docs/tickets/TKT-041-behaviour-level-deployment-smoke.md:205` in iter-2).

**Provenance note added** (iter-2 lines 205–215) transparently states:
- The 180s figure is an Architect-set ceiling **pending empirical calibration**, NOT sourced from a quantitative latency table in `MODEL-CATALOG.md` v0.3.0 § 4.3.
- Explicitly notes that § 4.3 contains "model-capability prose — context-window sizes, MoE parameters, role-fit rationale — but no latency, p95, or quantitative timing data", with the verification command (`grep -niE 'latency|p95|ms|second|timing|SLA'`) confirming zero matches — matching RV-SPEC-018 § 2.1 finding.
- Cites three informing anchors: (a) `ESCALATION-POLICY.md` § 5.3 / `MODEL-CATALOG.md` § 4.2 ≤ 10s classifier bound (the only quantitative latency anchor in the repo), (b) AUDIT-001 / TKT-033 v0.3.0 precedent of conservative empirical-pending budgets (TKT-033 § 4 AC-7 + § 8), and (c) order-of-magnitude reasoning about a single Planner LLM call at v0.1 scale on `qwen3p6-plus` through OmniRoute.
- **Q-TKT-041-01 mandated**: Executor at AUDIT-003 iter-1 captures actual median/p95/p99 from ≥ 3 smoke runs and files a Q-TKT; follow-on Architect cycle amends AC-7 with the measured ceiling.
- **Drift triggers preserved**: Q-TKT required for changes to N1 cadence source (`MULTI-HERMES-CONTRACT.md` § 8.1), N2 supporting anchors (`ESCALATION-POLICY.md` § 5.3 / `MODEL-CATALOG.md` § 4.2, `OBSERVABILITY-CONTRACT.md` § 9), matching the v0.1.0 "do NOT silently widen" rule.

**Resolution path matches AUDIT-001 precedent:** TKT-033 v0.3.0 § 4 AC-7 / § 8 uses the same empirical-pending conservative-budget pattern (NUDGE flagged this in the iter-2 scope). The option (b) "empirical-estimate-with-Q-TKT" pattern is consistent with that precedent.

**Result:** RESOLVED. Citation is corrected; the estimate is honestly labeled; empirical-calibration escape hatch is mandated; no silent-timeout-widening risk remains.

### 2.3 § 7 PR Requirements — Finding 2.3 RESOLVED

**Old text (v0.1.0):** "Cross-family Reviewer-LLM (Kimi K2.6 Moonshot on opencode + OmniRoute) is MANDATORY per the AUDIT-001 / TKT-040 precedent."

**New text (v0.1.1):** Cites four stronger precedents instead of TKT-040:
1. `AGENTS.md` multi-LLM pipeline role table — Reviewer = Kimi K2.6 main / Qwen 3.6 Plus fallback on opencode + OmniRoute; PR-Agent = DeepSeek V4 Pro as second reviewer, not replacement.
2. `CONTRIBUTING.md` § Roles + § Review Gates — RV-SPEC / RV-CODE / RV-ARCH naming convention; `pass` / `pass_with_changes` / `fail` verdicts.
3. `docs/meta/strategic-orchestrator.md` § 10 — ratification audit pass-2 against the cross-reviewer artifact.
4. `TKT-033-runtime-check-systemd-boot-enforcement.md` § 7 — AUDIT-001 ticket-level precedent for including Reviewer artifact path + verdict + PR-Agent status in PR body.

**Result:** RESOLVED. TKT-040 citation removed; replacement cites are all load-bearing and accurately map to the mandate.

### 2.4 § 8 Risks mirror line — N1/N2 derivation risk — RESOLVED

**Old text (v0.1.0):** "N1 = 90s and N2 = 300s are derived from current cadence and `MODEL-CATALOG.md` v0.3.0 § 4.3 p95 numbers."

**New text (v0.1.1):** Re-framed as "anchored on current cadence + Architect-estimated LLM-round-trip ceiling pending empirical calibration." Mirrors the AC-7 provenance note. Dual-layer mitigation spelled out: (1) Q-TKT-041-01 empirical-calibration replaces the estimate, (2) separate Q-TKT for drift in any supporting anchor (`MULTI-HERMES-CONTRACT.md` § 8.1, `ESCALATION-POLICY.md` § 5.3 / `MODEL-CATALOG.md` § 4.2, `OBSERVABILITY-CONTRACT.md` § 9). The smoke fails loudly rather than silently passing on a stretched envelope.

**Result:** RESOLVED. Risk narrative is internally consistent with the corrected AC-7.

### 2.5 § 9 Dependencies — Finding 2.2 RESOLVED

**Old text (v0.1.0):** "Status: merged via PR #169 (2026-05-11)."

**New text (v0.1.1):** Full forensic chain: "spec PR #133 (TKT-034 v0.2.0 AUDIT-002 spec landing); amendments PR #139 (v0.2.0 → v0.3.0) + PR #140 (v0.3.0 → v0.3.1 micro-amendment); implementation PR #135 (iter-1) + PR #151 (iter-2 closing RV-CODE-033 findings); reviewers PR #137 (RV-CODE-033 verdict `fail` on iter-1) + PR #152 (RV-CODE-035 verdict `pass` on iter-2); closure ratification PR #169 (F1 closure ratification — TKT-034 § 10 + SESSION-STATE bump v0.3.12 + session-log wrapper finding). Full forensic chain confirmed via `git log --grep='TKT-034\|RV-CODE-033\|RV-CODE-035' main` against HEAD `3e298c2`."

**Result:** RESOLVED. PR #169 is correctly identified as the closure ratification PR, not the implementation merge PR. The full chain is verifiable via git-grep.

### 2.6 Ratified surfaces untouched — VERIFIED

`git diff 782e110..2fea848 -- docs/tickets/TKT-041-behaviour-level-deployment-smoke.md` confirms **zero hunks** at:
- § 1.0, §§ 1.1–1.5, § 1.2, § 1.3, § 1.4 (structural decisions)
- AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-8, AC-9 (predicate bodies)
- § 5 Allowed Files, § 6 Test Strategy
- § 10 Execution Log, § 11 Cross-References

No changes to `docs/tickets/TKT-032.md` (supersession amendment was in the original `782e110` commit, not iter-2). No changes to architecture docs, ADRs, `src/`, `tests/`, `scripts/`, SESSION-STATE, or role prompts.

**Scope-creep verdict:** None. Iter-2 delta is exactly the five hunks enumerated above.

## 3. AC Reassessment

### AC-1 — pass (unchanged from RV-SPEC-018)

### AC-2 — pass (unchanged from RV-SPEC-018)

### AC-3 — pass (unchanged from RV-SPEC-018)

### AC-4 — pass (unchanged from RV-SPEC-018)

### AC-5 — pass (unchanged from RV-SPEC-018)

### AC-6 — pass (unchanged from RV-SPEC-018)

### AC-7 — pass (upgraded from partial)

N1=90s derivation remains fully traceable to `MULTI-HERMES-CONTRACT.md` v0.2.0 § 8.1 step 4. N2=300s 180s LLM-round-trip term is now honestly framed as an Architect-estimated ceiling with a mandated Q-TKT-041-01 empirical-calibration path. The broken `MODEL-CATALOG.md` § 4.3 citation is removed and replaced with a transparent provenance note. No p95 table is claimed to exist where none does. The drift-trigger mechanism (Q-TKT for any supporting-anchor change) prevents silent timeout widening.

### AC-8 — pass (unchanged from RV-SPEC-018)

### AC-9 — pass (unchanged from RV-SPEC-018)

## 4. Security Notes

- **Iter-2 diff introduces no new credentials or PII.** Zero matches for `ghp_`, `fw_`, `sk-`, `bot[0-9]+:`, or 40+ hex token shapes in the 5-hunk delta.
- **No new hostnames or real identifiers.** The only synthetic identity string is still `999999999`.
- **Smoke-mode security envelope unchanged.** § 1.4 invariants were not touched in iter-2; they remain as ratified in RV-SPEC-018 § 2.5.

## 5. Final Verdict

**pass**

Finding counts: high 0 / medium 0 / low 0 / none 0. Escalation needed: false.

All three RV-SPEC-018 findings are resolved with no scope creep into ratified surfaces:
1. **Finding 2.1 (medium → RESOLVED):** AC-7 N2 citation corrected; 180s ceiling is now labeled as Architect-estimate-with-Q-TKT-empirical-calibration; `MODEL-CATALOG.md` § 4.3 mis-citation removed.
2. **Finding 2.2 (none/informational → RESOLVED):** PR #169 misattribution corrected to full forensic chain (spec → amendments → implementation → reviewers → closure).
3. **Finding 2.3 (none/informational → RESOLVED):** TKT-040 weak citation replaced with four stronger, load-bearing precedents (`AGENTS.md`, `CONTRIBUTING.md` § Roles + § Review Gates, `docs/meta/strategic-orchestrator.md` § 10, TKT-033 § 7).

The iter-2 delta is precisely scoped to the three findings plus the § 8 Risks mirror line (AC-7 consistency) and frontmatter version bump. No new low-or-higher defects were introduced. The spec is ready for SO ratification and promotion to `ready` for AUDIT-003 Executor dispatch.
