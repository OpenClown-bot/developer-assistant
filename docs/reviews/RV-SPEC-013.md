---
id: RV-SPEC-013
version: 0.1.0
status: complete
verdict: pass_with_changes
review_target: PR-89
review_type: spec
reviewer_model: kimi-k2.6
created: 2026-05-06
---

# RV-SPEC-013: SPEC Review — PR #89 TKT-020 through TKT-026

**Date:** 2026-05-06
**Reviewer role:** Reviewer LLM (Kimi K2.6)
**PR:** #89 (`devin/1778037997-arch-001-pr-d-tickets`)
**Scope:** Implementation tickets TKT-020 through TKT-026 — operationalizing self-deployment bootstrap, multi-Hermes runtime layout, work-queue persistence, escalation enforcement, upstream-adapter scaffolding, shared custom skills, and model-catalog enforcement.
**Architecture baseline:** ARCH-001 v0.3.0
**Tickets reviewed:** TKT-020, TKT-021, TKT-022, TKT-023, TKT-024, TKT-025, TKT-026

---

## 1. Executive Summary

This PR contains seven implementation tickets derived from ARCH-001 v0.3.0 §19 (Implementation Ticket Strategy). The tickets collectively operationalize the self-deployment, multi-Hermes runtime, inter-runtime IPC, escalation policy, upstream adapter, shared skills, and model catalog architecture decisions documented in PRs A–C (ADR-004 through ADR-009, plus six contract documents).

All seven tickets have:
- Clear, bounded scope statements
- Traceability to specific architecture sections and contract documents
- Explicit dependency declarations matching ARCH-001 §19's dependency graph
- Testable acceptance criteria
- Security considerations appropriate to their risk level

No critical findings were identified. Two minor recommendations are noted in §3.1 and §3.2.

---

## 2. Per-Ticket Findings

### 2.1 TKT-020 — Self-Deployment Bootstrap Script and Verify/Rollback

**Verdict:** ✅ Clean

| Criterion | Assessment |
|---|---|
| Scope clarity | Clear. Three shell scripts: `install-self.sh`, `verify-self.sh`, `rollback-self.sh`. |
| Architecture traceability | Traces to ARCH-001 §14 and `SELF-DEPLOYMENT-CONTRACT.md` §2–7. |
| Testable ACs | AC1 (idempotent install), AC2 (verify health checks), AC3 (rollback restores state) are verifiable. |
| Dependencies | None (entry ticket per ARCH-001 §19). Correct. |
| Security | Explicitly requires secrets in `/srv/devassist/secrets/SELF-DEPLOY.env` mode 0600. No secrets in repo. |
| Size | Appropriate. One bootstrap + verify + rollback is a natural unit. |

**Observation:** AC2 references `scripts/verify-self.sh` but does not enumerate the exact health-check inventory (Telegram, GitHub PAT, OmniRoute, state store, systemd units, journalctl secrets scan). This inventory is documented in ARCH-001 §14 and `SELF-DEPLOYMENT-CONTRACT.md` §5, so the ticket remains traceable.

### 2.2 TKT-021 — Multi-Hermes Runtime Layout and systemd Supervision

**Verdict:** ✅ Clean

| Criterion | Assessment |
|---|---|
| Scope clarity | Clear. Five runtime directories, systemd unit templates, umbrella `devassist.target`, shared `skills/` and `plugins/` directories. |
| Architecture traceability | Traces to ARCH-001 §11 and `MULTI-HERMES-CONTRACT.md` §2–4. |
| Testable ACs | AC1 (per-runtime isolation), AC2 (systemd units active), AC3 (shared dirs mounted) are verifiable. |
| Dependencies | None (entry ticket per ARCH-001 §19). Correct. |
| Security | Correctly notes Docker backend for Executor/Reviewer, `local` backend blocked in production. |
| Size | Appropriate. Layout and systemd supervision are tightly coupled and belong in one ticket. |

### 2.3 TKT-022 — Work-Items and Escalations SQLite Schema

**Verdict:** ✅ Clean

| Criterion | Assessment |
|---|---|
| Scope clarity | Clear. `work_items` and `escalations` table schemas; `dev-assist-work-queue` plugin skeleton. |
| Architecture traceability | Traces to ARCH-001 §11.2, `MULTI-HERMES-CONTRACT.md` §6.2, and `OPERATIONAL-STATE-STORE.md`. |
| Testable ACs | AC1 (schema matches contract), AC2 (plugin can poll/claim/complete) are verifiable. |
| Dependencies | TKT-021. Correct — needs runtime layout before schema can be attached to a state store path. |
| Security | No credential storage in schema; least-privilege implied by SQLite file permissions. |
| Size | Appropriate. Schema + plugin skeleton is a natural unit. |

### 2.4 TKT-023 — Escalation Policy Plugin

**Verdict:** ✅ Clean

| Criterion | Assessment |
|---|---|
| Scope clarity | Clear. `dev-assist-escalation-policy` plugin with deterministic rules + LLM classifier. |
| Architecture traceability | Traces to ARCH-001 §15, `ESCALATION-POLICY.md`, and ADR-008. |
| Testable ACs | AC1 (pre_tool_call hook registered), AC2 (deterministic patterns match), AC3 (LLM classifier Y→escalate), AC4 (escalations table append) are verifiable. |
| Dependencies | TKT-022. Correct — needs `escalations` table and work-queue infrastructure. |
| Security | Pre-empts Hermes approval prompt; deterministic rules require no LLM consultation for known-dangerous actions. |
| Size | Appropriate. One plugin with two enforcement layers is a natural unit. |

### 2.5 TKT-024 — Upstream-Adapter Scaffolding

**Verdict:** ✅ Clean

| Criterion | Assessment |
|---|---|
| Scope clarity | Clear. Telegram gateway skill + upstream-adapter abstraction layer for five operations (inbound, outbound, approval prompt, identity binding, session continuity). |
| Architecture traceability | Traces to ARCH-001 §13 and `UPSTREAM-ADAPTER-CONTRACT.md`. |
| Testable ACs | AC1 (five operations implemented), AC2 (Telegram allowlist enforced), AC3 (session continuity resumed) are verifiable. |
| Dependencies | TKT-021. Correct — needs runtime layout before adapter can be loaded into Orchestrator runtime. |
| Security | Telegram allowlist + explicit Founder pairing required. |
| Size | Appropriate. One upstream surface (Telegram) with abstraction layer is a natural unit. |

### 2.6 TKT-025 — Shared Custom Skills

**Verdict:** ✅ Clean

| Criterion | Assessment |
|---|---|
| Scope clarity | Clear. Fourteen `dev-assist-*` skills with manifests, loaded into correct runtimes per ARCH-001 §12 table. |
| Architecture traceability | Traces to ARCH-001 §12 and `MULTI-HERMES-CONTRACT.md` §5. |
| Testable ACs | AC1 (all skills have manifests), AC2 (requires_toolsets/fallback_for_toolsets correct per runtime), AC3 (loaded in correct runtime) are verifiable. |
| Dependencies | TKT-021. Correct — needs runtime layout and shared skills directory before skills can be deployed. |
| Security | Correctly notes `delegate_task` and `skill_manage` are BLOCKED in production per `HERMES-SKILL-ALLOWLIST.md`. |
| Size | Large but justified. Fourteen small skills with similar structure are cheaper to implement together than in separate tickets. ACs break down per-skill to keep testability. |

**Observation:** This ticket bundles skills across all five runtimes. The Orchestrator skills (classifier, progress-report, escalation-surface, work-queue-write) and specialist skills (prd-writer, questions-writer, arch-writer, adr-writer, tickets-writer, executor-discipline, write-zone-enforcer, github-workflow, reviewer-rubric, review-writer, work-queue-poll) are all in one ticket. This is acceptable because they share the same deployment mechanism (shared directory + manifest), but a future ticket might split them if implementation parallelism is desired. For v0.1, keeping them together reduces orchestration overhead.

### 2.7 TKT-026 — Model-Catalog Enforcement Helper

**Verdict:** ✅ Clean

| Criterion | Assessment |
|---|---|
| Scope clarity | Clear. Helper enforcing within-catalog model picks and escalating on catalog changes. |
| Architecture traceability | Traces to ARCH-001 §16, `MODEL-CATALOG.md`, and ADR-009. |
| Testable ACs | AC1 (within-catalog pick proceeds without escalation), AC2 (catalog change triggers escalation), AC3 (catalog changes append to `escalations` table) are verifiable. |
| Dependencies | TKT-021. Correct — needs runtime layout before enforcement helper can be loaded. |
| Security | Catalog changes escalate; within-catalog picks are autonomous. |
| Size | Appropriate. One enforcement helper is a natural unit. |

---

## 3. Cross-Cutting Findings

### 3.1 ⚠️ Minor: TKT-025 Bundle Size

TKT-025 bundles fourteen skills. While this is justified by shared deployment mechanics, it creates a single large work unit. If implementation is delayed, all runtimes lose their custom skills simultaneously. **Recommendation:** If TKT-025 exceeds its time estimate, consider splitting into Orchestrator-skills and specialist-skills sub-tasks within the same ticket, without creating new ticket files. Not blocking.

### 3.2 ⚠️ Minor: No Explicit Integration Test Ticket Before TKT-011

ARCH-001 §19 states that TKT-011 (Telegram-to-PR trial) requires all seven tickets to merge first. There is no explicit "integration smoke test" ticket between TKT-020–026 and TKT-011. **Recommendation:** Ensure TKT-020's `verify-self.sh` or a follow-on TKT-011 AC covers end-to-end validation of all seven tickets working together. Not blocking — this is an implementation detail, not a specification gap.

### 3.3 Security: No New Risks Introduced

All seven tickets respect the security model from ARCH-001 §10:
- Secrets remain in `/srv/devassist/secrets/SELF-DEPLOY.env` only.
- Docker terminal backend is required for Executor/Reviewer.
- `delegate_task` and `skill_manage` remain BLOCKED.
- Escalation policy pre-empts dangerous actions.
- No paid third-party hard dependencies are introduced.

---

## 4. Dependency Graph Verification

ARCH-001 §19 dependency graph:

```
TKT-020 (self-deployment bootstrap)  ─┐
TKT-021 (multi-Hermes layout)        ─┼─►  TKT-011 (Telegram-to-PR trial)
TKT-022 (work_items + escalations)   ─┤
TKT-023 (escalation plugin)          ─┤
TKT-024 (upstream-adapter scaffolding)┤
TKT-025 (shared custom skills)       ─┤
TKT-026 (model-catalog helper)       ─┘
```

**Verified:**
- TKT-020 and TKT-021 have no upstream dependencies in this set. ✅
- TKT-022 depends on TKT-021. ✅
- TKT-023 depends on TKT-022. ✅
- TKT-024 depends on TKT-021. ✅
- TKT-025 depends on TKT-021. ✅
- TKT-026 depends on TKT-021. ✅
- All seven must merge before TKT-011. This sequencing is documented in ARCH-001 §19 and not contradicted by any ticket. ✅

---

## 5. Specification Completeness

| Architecture Area | Ticket | Contract/ADR | Status |
|---|---|---|---|
| Self-deployment bootstrap | TKT-020 | SELF-DEPLOYMENT-CONTRACT, ADR-004 | ✅ Covered |
| Multi-Hermes runtime layout | TKT-021 | MULTI-HERMES-CONTRACT | ✅ Covered |
| Work-queue persistence | TKT-022 | MULTI-HERMES-CONTRACT §6.2, ADR-006 | ✅ Covered |
| Escalation enforcement | TKT-023 | ESCALATION-POLICY, ADR-008 | ✅ Covered |
| Upstream-adapter scaffolding | TKT-024 | UPSTREAM-ADAPTER-CONTRACT, ADR-007 | ✅ Covered |
| Shared custom skills | TKT-025 | MULTI-HERMES-CONTRACT §5 | ✅ Covered |
| Model-catalog enforcement | TKT-026 | MODEL-CATALOG, ADR-009 | ✅ Covered |

**Coverage:** All seven areas from ARCH-001 §19 are represented by exactly one ticket each. No gaps. No redundant tickets.

---

## 6. Verdict

**`pass_with_changes`**

The ticket set is well-specified, correctly traces to architecture, and has appropriate dependencies. The two minor recommendations in §3.1 and §3.2 are non-blocking suggestions for implementation planning, not specification defects.

**Required actions before TKT-011 dispatch:**
1. Merge TKT-020 through TKT-026.
2. Run `scripts/verify-self.sh` (from TKT-020) after all seven merge to confirm integration.
3. Founder approval for TKT-011 dispatch (per ARCH-001 §19 sequencing constraint).

---

## 7. Reviewer Notes

- Review performed on branch `devin/1778037997-arch-001-pr-d-tickets` with `git diff main...HEAD`.
- All seven ticket files were read in full.
- Supporting contract documents read: `SELF-DEPLOYMENT-CONTRACT.md`, `MULTI-HERMES-CONTRACT.md`, `ESCALATION-POLICY.md`, `MODEL-CATALOG.md`, `UPSTREAM-ADAPTER-CONTRACT.md`.
- Supporting ADRs read: ADR-004, ADR-005, ADR-006, ADR-007, ADR-008, ADR-009.
- ARCH-001 v0.3.0 read in full (375 lines).
- No implementation code was reviewed; this is a SPEC review of ticket files only.
- No secrets or credentials were encountered in ticket files.
