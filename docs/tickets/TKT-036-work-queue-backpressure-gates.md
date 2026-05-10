---
id: TKT-036
version: 0.1.0
status: draft
arch_ref: ARCH-002@0.1.0
adr_ref: ADR-016@0.1.0
updated: 2026-05-10
---

# TKT-036: Work-Queue Backpressure Gates — orchestrator-loop verification

## 1. Scope

Implement ADR-016 layer-1 (orchestrator-loop) backpressure gates G-DISPATCH-1, G-DISPATCH-2, G-COMPLETE-1, G-COMPLETE-2 in the `dev-assist-work-queue` plugin. This ticket promotes verification gates from CI-only to work-queue-state-transition-level enforcement. Layer-2 (CI / Reviewer-PR) gates are unchanged by this ticket; their gate-tagging is implemented in TKT-038.

The work also extends the `work_items.status` enum with two new values — `cancelled` (terminal, runtime aborts work item) and `paused_on_founder` (non-terminal, runtime is blocked waiting for nudge response per ADR-017). The `cancelled` status is independent of ADR-017; `paused_on_founder` requires TKT-037 to be merged for the modality-split surface logic to work, but the column itself can land in TKT-036 with TKT-037 layering on top.


## 2. Non-scope

- Layer-2 gate-tagging in Reviewer rubric — TKT-038.
- Surface logic for `paused_on_founder` (Telegram + work-item resume) — TKT-037.
- Daily digest of mail-modality escalations — TKT-037.
- `dev-assist-cli status --by-gate` flag — TKT-038 (depends on Reviewer rubric tagging).
- Concept-anchor freshness ledger drift gates — TKT-039.


## 3. Required Context

- ADR-016 v0.1.0 § Decision (final spec).
- ADR-017 v0.1.0 § Decision (for `paused_on_founder` status enum extension).
- ARCH-002 v0.1.0 § 3.3 (App-3), § 3.10 (App-10), § 5.3 (Q-RESEARCH-002-03), § 6.1 (amendment).
- `MULTI-HERMES-CONTRACT.md` v0.2.1 § 6.2 (work_items state machine baseline).
- `OPERATIONAL-STATE-STORE.md` v0.2.1 § 3.5 (work_items table baseline).
- `ARCH-001.md` v0.3.0 § 17 (CI baseline).
- TKT-022 v0.x (work_items table base — reference for migration tooling).


## 4. Acceptance Criteria

**AC-1 (G-DISPATCH-1).** Work-queue dispatcher refuses to dispatch `target_kind='ticket_implementation'` for a ticket whose frontmatter `status` is anything other than `ready`. Failure path: log structured error, do NOT promote work_item to `claimed`, leave `pending`. Test covering each non-ready status (`draft`, `in_progress`, `done`, etc.) confirms refusal.

**AC-2 (G-DISPATCH-2).** Work-queue dispatcher refuses to dispatch `target_kind='ticket_review'` for a PR whose `validate-docs` GitHub Check run is `conclusion: failure`. The check is performed via GitHub Check API (read-only). Failure path: log structured error, leave `pending`. Test covering the failure case via mocked Check API response.

**AC-3 (G-COMPLETE-1).** The `complete`-write SQL on `work_items` MUST NOT promote a work_item to `completed` while the tied PR has any required CI check at `conclusion: failure`. Implemented as a SQLite trigger or as a Python pre-write check (Architect chooses; recommend Python-side for testability). Test covering the failure case.

**AC-4 (G-COMPLETE-2).** When `attempt_count >= max_attempts` and the most recent attempt's status is `failed`, the Orchestrator MUST emit a `nudge`-modality escalation (per ADR-017) with `trigger_kind='attempt_exhaustion'` and set the work_item to `failed` (terminal). Test covering attempt-exhaustion path.

**AC-5 (`cancelled` status).** Schema migration adds `'cancelled'` to `work_items.status` CHECK constraint. New transition: `claimed → cancelled` (via explicit `cancel(work_item_id, reason)` API). Test covering cancellation path.

**AC-6 (`paused_on_founder` status).** Schema migration adds `'paused_on_founder'` to `work_items.status` CHECK constraint. The column accepts the new value; transition logic (claimed → paused_on_founder → claimed) is gated to work even before TKT-037 implements the surface logic — TKT-036's tests cover the schema-level transitions only; surface behavior tested in TKT-037.

**AC-7.** `MULTI-HERMES-CONTRACT.md` § 6.2 amended with new status enum values and new transitions. `OPERATIONAL-STATE-STORE.md` v0.3.x schema migration documented.

**AC-8.** GitHub Check API integration is read-only and uses the existing PAT (`GITHUB_TOKEN_DEVELOPER_ASSISTANT` per ARCH-001 § 17 / TKT-008 / TKT-016). Caching: per-PR check status cached for 30 seconds to avoid GitHub rate limits.

**AC-9.** When the GitHub Check API is unreachable (network failure, rate-limit exhaustion), gates G-DISPATCH-2 and G-COMPLETE-1 fail-closed: refuse to dispatch / refuse to promote, emit a `mail`-modality escalation per ADR-017 with `trigger_kind='github_check_api_unreachable'`. Test covering the unreachable-API path with mocked HTTP errors.

**AC-10.** `python3 scripts/validate_docs.py` passes.


## 5. Allowed Files

- `src/work_queue/dispatcher.py` (extend)
- `src/work_queue/complete.py` (extend or NEW depending on existing organization)
- `src/work_queue/github_checks.py` (NEW — GitHub Check API client wrapper, read-only)
- `tests/test_work_queue_gates.py` (NEW)
- `docs/architecture/MULTI-HERMES-CONTRACT.md` (§ 6.2 amendment only)
- `docs/architecture/OPERATIONAL-STATE-STORE.md` (§ 3.5 amendment only)
- `docs/architecture/migrations/op-store-v0.3.x.md` (NEW migration record)


## 6. Test Strategy

Test pyramid for this ticket:

- **Unit (`tests/test_work_queue_gates.py`):** each gate (G-DISPATCH-1, G-DISPATCH-2, G-COMPLETE-1, G-COMPLETE-2) tested with happy and refusal paths. GitHub Check API client tested with mocked HTTP responses (success, failure, network error, rate-limit).
- **Schema migration:** v0.2.x → v0.3.x migration tested for additivity (no DROP, existing rows preserved); `cancelled` and `paused_on_founder` enum extension tested for forward-only compatibility.
- **Integration:** end-to-end gate sequence — create work_item, attempt dispatch with not-ready ticket (refuse), promote ticket to ready, dispatch (succeed), simulate CI failure, attempt complete (refuse), simulate CI success, complete (succeed).
- **Failure injection:** GitHub Check API unreachable → fail-closed paths (refuse + emit mail-modality escalation) tested.


## 7. Risk Notes

Primary risk: tight coupling between work-queue state machine and GitHub Check API state. If GitHub is rate-limited or experiencing an outage, gates G-DISPATCH-2 and G-COMPLETE-1 fail-closed (refuse to dispatch / refuse to promote). Mitigation: 30-second cache on Check API responses; mail-modality escalation on `github_check_api_unreachable` so Founder is informed without runtime hard-locking. Secondary risk: schema migration runs against an in-flight production database (post-AUDIT-002 deployment); migration must be idempotent and rollback-safe via `scripts/rollback-self.sh` per ADR-004.


## 8. Spec Amendment Notes

Hard rules for this ticket (governance constraints inherited from ARCH-002 + the source ADR; Executor MUST observe):


- Do NOT modify `MULTI-HERMES-CONTRACT.md` § 6.3 (escalations table) — that's TKT-037's write zone.
- Do NOT touch the `dev-assist-escalation-surface` skill — that's TKT-037's write zone.
- Do NOT modify ADR-016, ADR-017 — Architect-cycle authoritative.
- Schema migration must be additive (no DROP / no destructive ALTER).
- GitHub Check API client must be read-only — no `gh pr edit`, no `gh pr review`, no merge. Only Check API read.
- All gate-failure paths emit structured journald entries with named failure-mode labels per ARCH-002 § 6.4.


## 9. Cross-references

- ADR-016 v0.1.0 (Backpressure gates).
- ADR-017 v0.1.0 (Escalation modalities — for `paused_on_founder` and mail-modality emission).
- ARCH-002 v0.1.0 § 3.3, § 3.10, § 5.3, § 6.1.
- RESEARCH-002 § 6.8 (Ralph), § 7.3 (verification).
- `MULTI-HERMES-CONTRACT.md` v0.2.1 § 6.2.
- `OPERATIONAL-STATE-STORE.md` v0.2.1 § 3.5.
- `ARCH-001.md` v0.3.0 § 17.


## 10. Execution Log

(Reserved for Executor cycle.)
