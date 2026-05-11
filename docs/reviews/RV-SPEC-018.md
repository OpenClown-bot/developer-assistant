---
id: RV-SPEC-018
version: 0.1.0
status: complete
verdict: pass_with_changes
review_target: PR-170
target_head: 782e110c2f3d9b00470ad77312ffc6f19eee9191
base_head: 3e298c2f3d9b00470ad77312ffc6f19eee9191
review_type: spec
reviewer_model: Kimi K2.6
reviewer_runtime: opencode + OmniRoute
created: 2026-05-11
---

# RV-SPEC-018: SPEC Review of PR #170 — TKT-041 v0.1.0 AUDIT-003 behaviour-level deployment smoke

## 1. PR Meta

- **PR**: #170
- **Branch**: `arch/audit-003-behaviour-level-smoke`
- **Head SHA reviewed**: `782e110c2f3d9b00470ad77312ffc6f19eee9191`
- **Base SHA**: `3e298c2f3d9b00470ad77312ffc6f19eee9191`
- **Merge state**: open, mergeable
- **Files changed in this commit**: `docs/tickets/TKT-032.md` (frontmatter + § 1 supersession note), `docs/tickets/TKT-041-behaviour-level-deployment-smoke.md` (new spec, 329 lines)
- **Diff shape**: 2 files, 343 insertions(+), 2 deletions(-)
- **CI checked**: `validate-docs` — N/A for spec-only PR; no pytest / unittest surface (RV-SPEC, not RV-CODE)

## 2. Review Findings

### 2.1 MODEL-CATALOG.md § 4.3 citation invalid — N2=300s p95 latency anchor missing — Severity: medium

TKT-041 § 4 AC-7 N2 rationale states: "N1 + typical Planner LLM call latency upper bound (≤ 180 s at p95 for `qwen3p6-plus` per `MODEL-CATALOG.md` v0.3.0 § 4.3 latency table — Executor verifies the p95 number at branch-cut; if the table has shifted, the Executor files Q-TKT and adjusts N2)".

**Finding:** `MODEL-CATALOG.md` v0.3.0 § 4.3 is titled "Why these entries" (`docs/architecture/MODEL-CATALOG.md:65`). It contains prose model-capability descriptions (context-window sizes, MoE parameters, role-fit rationale) and a routing-layer verification note. It does **not** contain a latency table, p95 values, or any quantitative timing data (`grep -i 'latency\|p95\|ms\|second\|timing\| SLA' docs/architecture/MODEL-CATALOG.md` returns zero matches).

**Impact:** The Executor cannot "verify the p95 number at branch-cut" against the cited source because the cited source does not contain the number. This creates two problems:
1. The Q-TKT trigger condition («if the table has shifted») is vacuous — the section never had a table to shift.
2. The N2=300s figure becomes an orphan: the arithmetic `90 + 180 + 5 + buffer ≈ 300` is plausible but the 180 s anchor has no traceable provenance in the repo.

**Mitigation already in ticket:** AC-7 correctly mandates "do NOT silently widen the smoke timeouts" and requires a Q-TKT if N1/N2 need re-derivation. The broken citation does not invalidate the N2 value itself, but it does invalidate the verification instruction.

**Fix:** Replace the citation with one of:
- (a) the actual empirical measurement source (e.g., a session-log entry or benchmark artifact that recorded the 180 s p95), or
- (b) a statement that N2 is an Architect-estimated ceiling pending empirical calibration, with a Q-TKT filed to replace the estimate once live measurements are available, or
- (c) a pointer to an external latency table if the p95 was sourced outside the repo (with an ADR citation).

**Checklist impact:** C-4 (verifiable references), C-13 (traceability).
**Escalation needed:** false — sibling Architect amendment.

### 2.2 PR #169 historical accuracy — TKT-034 dependency pin — Severity: none (informational)

TKT-041 § 9 Dependencies states: "AUDIT-002 (TKT-034 v0.3.1) MUST be merged on `main`. Status: merged via PR #169 (2026-05-11)."

PR #169 commit `3e298c2` message reads: `docs: F1 closure ratification — TKT-034 § 10 + SESSION-STATE + session-log wrapper finding (#169)`. This is a post-implementation clerical closure PR (F1 ratification + execution-log back-fill + session-log update), not the implementation PR that landed TKT-034 v0.3.1's code, tests, and scripts. The actual implementation merged earlier via PR #135 (iter-1) and PR #137 (iter-2), per `docs/tickets/TKT-034-interactive-installer-and-operator-hygiene.md` § 10.

**Impact:** None on the merge-safe gate — TKT-034 v0.3.1 IS on `main`. The PR number is a historical-attribution convenience, not a load-bearing dependency predicate.
**Fix:** Optional — change "merged via PR #169" to "merged via PR #135 + #137; closure ratified via PR #169" for forensic accuracy.
**Escalation needed:** false.

### 2.3 TKT-040 cross-family Reviewer mandate citation accuracy — Severity: none (informational)

TKT-041 § 7 PR Requirements states: "Cross-family Reviewer-LLM (Kimi K2.6 Moonshot on opencode + OmniRoute) is MANDATORY per the AUDIT-001 / TKT-040 precedent."

TKT-040 (`docs/tickets/TKT-040-skill-loadout-context-budget-mcp-exclusion.md`) is a skill-loadout documentation amendment + MCP-exclusion defensive check. Its scope does not mention Reviewer mandate, cross-family audit, or PR-Agent integration. The actual precedent for cross-family Reviewer-LLM enforcement is in `AGENTS.md` (multi-LLM pipeline role table) and `CONTRIBUTING.md` § Review Gates (`Reviewer: Kimi K2.6 (main) / Qwen 3.6 Plus (fallback)`), reinforced by TKT-033 § 7 (AUDIT-001) and the `docs/meta/strategic-orchestrator.md` § 10 cross-reviewer audit pattern.

**Impact:** None — the requirement itself is valid and rooted in stronger documents. TKT-040 is a weak citation for it.
**Fix:** Optional — cite `AGENTS.md`, `CONTRIBUTING.md` § Review Gates, or `docs/meta/strategic-orchestrator.md` § 10 instead of / in addition to TKT-040.
**Escalation needed:** false.

### 2.4 Sibling-out boundary and Allowed Files constrainedness — Severity: none

TKT-041 § 5 Allowed Files follows the AUDIT-001 / AUDIT-002 precedent pattern exactly:
- `src/`, `scripts/`, `tests/`, and ticket-local `§ 10 Execution Log` fills are in-zone.
- All architecture documents (`MULTI-HERMES-CONTRACT.md`, `HERMES-SKILL-ALLOWLIST.md`, `SELF-DEPLOYMENT-CONTRACT.md`, `OBSERVABILITY-CONTRACT.md`, `MODEL-CATALOG.md`), ADRs, `SESSION-STATE.md`, `docs/prompts/<role>.md`, and merged sibling tickets are explicitly listed as **NOT** in-zone.
- The `OBSERVABILITY-CONTRACT.md` § 11 amendment and the proposed 12th `runtime_check` invariant are correctly routed to sibling/Q-TKT paths, not folded in.

No scope-creep surface is visible in the commit.

### 2.5 Security envelope completeness for v0.1 — Severity: none

§ 1.4 security envelope (7 invariants) is sufficient for a v0.1 smoke-mode posture:
1. Marker-file gate (`0400` ACL + TTY confirmation) — strong.
2. Localhost-only bind (`127.0.0.1:8186`, `8281..8285`) — correct.
3. Smoke-fixture token regex (`^smoke-fixture-token-[a-z0-9]{8}$`) — prevents real BotFather tokens.
4. Telegram outbound dry-run — defense-in-depth; fallback to Q-TKT if Hermes lacks the override.
5. Polling disabled — prevents real-chat consumption.
6. Mutual exclusion with production install — verified by `verify-self.sh` extension.
7. Reviewer artifact required for any envelope change — frozen-contract posture.

Residual risks are honestly documented in § 8 (localhost-exposure on compromised `devassist` user, classifier non-determinism, N1/N2 derivation drift, OBSERVABILITY-CONTRACT.md amendment lag window). Each has an acceptable v0.1 mitigation or Q-TKT escape hatch.

### 2.6 TKT-032 supersession coverage completeness — Severity: none

§ 1.5 cross-reference table audits all 11 TKT-032 v0.1.0 § 4 AC bullets against AUDIT-001/002/003 replacement coverage. Verified: zero bullets lack replacement. The process-aliveness layer (install script runs, env file exists, `verify-self.sh` exits 0, runtime status shows running/degraded, at least one `/health` returns 200) is subsumed by AUDIT-001 + AUDIT-002. The behaviour layer (all five `/health` endpoints return structured payload, classifier → work_items → Planner claim → result → observability round-trip) is new in AUDIT-003. Supersession is sound.

### 2.7 AC determinism and offline-testability — Severity: none

AC-2 (skill-loadout probe), AC-3 (negative test for `delegate_task` / `skill_manage` + symmetry sanity), AC-4 (prompt SHA + path round-trip), AC-5 (synthetic-message → classifier → `work_items`), and AC-6 (Planner claim + result + observability) are all genuinely deterministic and offline-testable per the five pillars. The spec correctly mandates fixture-based stubbing of Hermes runtime surfaces rather than live LLM / Telegram / systemd invocation. AC-8 baseline discipline and AC-9 secret/PII grep are direct continuations of AUDIT-001/002 precedent.

## 3. AC Assessment

### AC-1 (diagnosis) — pass

§ 3.1 records seven live-state observations at HEAD `3e298c2`. Each is a binary, verifiable predicate (e.g., "`loaded_skills` field does not currently appear in OBSERVABILITY-CONTRACT.md § 11", "`dev-assist-cli` does not expose a `smoke` subcommand"). The implementer is correctly instructed to re-verify at branch-cut and file Q-TKT if any observation has shifted. This matches the AUDIT-001 AC-1 pattern (TKT-033 § 3.1).

### AC-2 (behaviour-level skill-loadout probe) — pass

Set-equality assertion against § 3.2 per-role table; `hermes-agent` absent; `dev-assist-classifier` present in Orchestrator set. Implementation path (`observability_manager.py` backward-compatible extension) is well-scoped. The contract-parsing mandate («test parses `MULTI-HERMES-CONTRACT.md` § 5.1–5.5 at test time») mirrors AUDIT-002 AC-2 (d) and prevents fixture drift.

### AC-3 (active negative test: `delegate_task` + `skill_manage`) — pass

Three sub-criteria cover the full surface: (i) `delegate_task` dispatch refusal on non-orchestrator roles, (ii) `skill_manage` dispatch refusal on all five roles, (iii) symmetry sanity for in-loadout tools. The localhost admin-port probe surface (`127.0.0.1:8281..8285`) is smoke-mode-gated. The refusal-class probe is pragmatically left as "closest equivalent error class" with Executor documentation in iter-1, acknowledging Hermes v2026.4.30's lack of a typed gating-error layer (already established in TKT-033 v0.3.0 § 8 Amendment notes).

### AC-4 (prompt SHA + path round-trip) — pass

Three sub-criteria: (i) `/health` fields added, (ii) SHA-256 compared against install-time manifest, (iii) `prompt_path` canonical cross-check. All are backward-compatible additions. The manifest reader path (`/srv/devassist/state/prompt-manifest.json`) is the same artifact introduced by TKT-033 v0.3.0 component C, so AUDIT-003 does not introduce a new manifest schema.

### AC-5 (synthetic-message → classifier → `work_items`) — pass

Inject path (`127.0.0.1:8186`), correlation-id persistence, classifier-label non-emptiness + membership in canonical 5-class set, and `target_role='planner'` are all deterministic. The synthetic text is designed to be ambiguous (so the smoke tests classifier persistence, not classifier accuracy), and the spec correctly routes non-Planner classification to Q-TKT rotation rather than smoke regression.

### AC-6 (Planner claim + result + observability round-trip) — pass

Six sub-criteria cover claim timeout (`planner_claim_timeout`), health best-effort observation (`planner_health_no_currentwork`), result timeout (`planner_result_timeout`), `llm_calls` correlation (including the important `planner_no_llm_call` failure mode when `status='failed'` but no LLM call was recorded), `errors` correlation on failure path, and queue-stats consistency. The N1=90s and N2=300s budgets are given with explicit derivation chains.

### AC-7 (N1 + N2 rationale) — partial

N1=90s derivation is fully traceable to `MULTI-HERMES-CONTRACT.md` v0.2.0 § 8.1 step 4 (60-second poll cadence) plus 30 s slack. N2=300s derivation cites an 180 s p95 value from `MODEL-CATALOG.md` v0.3.0 § 4.3, but that section contains no latency table (Finding 2.1). The arithmetic `90 + 180 + 5 + buffer ≈ 300` is sound as an estimate, but the citation is broken. Upgrade to **pass** once the citation is corrected or the p95 anchor is sourced from a valid document/empirical measurement.

### AC-8 (test baseline discipline) — pass

Direct continuation of TKT-033 / TKT-034 precedent: record `<count_before>`, record `<count_after>`, assert `<count_after> >= <count_before>`, delta explained by AC-2..AC-6 + AC-9 additions only. No existing test removal or masking permitted.

### AC-9 (secret-leak + PII grep) — pass

Sub-criteria cover secret-shape grep (Telegram bot token, GitHub PAT, Fireworks API key, OmniRoute API key, OpenRouter API key), PII grep (Founder chat/user ids, usernames, emails, real names, domains), and `verify-self.sh` extension. Smoke-fixture token regex and synthetic user id (`999999999`) are correctly scoped as the only allowed identity strings.

## 4. Security Notes

- **No real credentials in spec.** Zero matches for `ghp_`, `fw_`, `sk-`, `bot[0-9]+:`, or 40+ hex token shapes in the reviewed diff. The only token-like string is the smoke-fixture regex `^smoke-fixture-token-[a-z0-9]{8}$`, which is explicitly a non-real shape.
- **No PII in spec.** No real Telegram chat IDs, GitHub usernames, emails, or hostnames. The synthetic user id `999999999` and message text `smoke-fixture-message-<correlation_id>` are the only identity strings.
- **Smoke-mode isolation.** The localhost-only bind (`127.0.0.1:8186/8281..8285`) + marker-file gate + mutual exclusion with production install provides defense-in-depth. Residual risk (compromised `devassist` user hitting localhost admin ports) is acknowledged in § 8 and mitigated by AUDIT-001's `ExecStartPre=` layer and runtime-isolation `systemd` sandbox.
- **No autonomous merge path enabled.** § 7 PR Requirements explicitly state Founder acknowledgement before merge remains required.

## 5. Final Verdict

**pass_with_changes**

Finding counts: high 0 / medium 1 / low 0 / none 3 (informational).

The TKT-041 v0.1.0 spec is directionally correct, scope-disciplined, and faithful to the AUDIT-003 NUDGE. The behaviour-level smoke contract (AC-2 through AC-6) is well-structured, genuinely offline-testable, and correctly routes all out-of-scope concerns (OBSERVABILITY-CONTRACT.md amendment, 12th runtime_check invariant, cross-specialist smoke, real-network tests) to sibling PRs or Q-TKTs. The TKT-032 supersession is complete with zero coverage gaps.

One medium-severity precision gap should be fixed before Executor dispatch: the `MODEL-CATALOG.md` v0.3.0 § 4.3 citation in AC-7 N2 rationale is broken — the cited section has no latency table or p95 values. The Architect should issue a sibling amendment correcting the citation or providing the actual empirical source for the 180 s upper bound. After that amendment, the spec should be ready for SO ratification and AUDIT-003 Executor dispatch.

## 6. Errata / Sibling Amendment Recommendations

1. **TKT-041 § 4 AC-7 — N2 citation fix.** Sibling Architect mini-PR (or direct amendment if SO ratifies inline): replace "`MODEL-CATALOG.md` v0.3.0 § 4.3 latency table" with the actual provenance of the 180 s p95 value, or rephrase as an empirically-estimated ceiling with a Q-TKT to replace it once live Planner LLM-call latency measurements are available.
2. **TKT-041 § 9 — PR #169 historical accuracy.** Optional cosmetic fix: "merged via PR #135 + #137; closure ratified via PR #169."
3. **TKT-041 § 7 — cross-family Reviewer mandate citation.** Optional cosmetic fix: cite `AGENTS.md` / `CONTRIBUTING.md` § Review Gates / `docs/meta/strategic-orchestrator.md` § 10 instead of TKT-040.

---
*Reviewer hand-back:* Branch `rv/audit-003-spec-review` carries this review file. HEAD SHA at push will be recorded below this line by the pushing agent.
