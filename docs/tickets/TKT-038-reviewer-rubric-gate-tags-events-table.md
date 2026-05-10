---
id: TKT-038
version: 0.1.0
status: draft
arch_ref: ARCH-002@0.1.0
adr_ref: ADR-016@0.1.0
updated: 2026-05-10
---

# TKT-038: Reviewer Rubric Gate-Tagged Findings + events table

## 1. Scope

Two coupled changes for ARCH-002:

(A) Implement ADR-016 layer-2 gate-tagging: extend the `dev-assist-reviewer-rubric` skill so every Reviewer finding (RV-CODE / RV-SPEC artifact entry) is tagged with one of the named gate categories — `tests_gate`, `lint_gate`, `typecheck_gate`, `docs_gate`, `concept_anchor_gate`, `cross_link_gate`, `cross_model_consistency_gate`. Extend `validate_docs.py` with a forward-only check that asserts gate-tag presence in any *new* RV-CODE / RV-SPEC artifact (pre-existing artifacts are grandfathered).

(B) Implement ARCH-002 § 5.1 (Q-RESEARCH-002-01) answer: add an `events` append-only table to `OPERATIONAL-STATE-STORE.md` v0.3.x for cross-runtime trace use cases. Schema is small (one row per work-item state transition, escalation surface, runtime_check pass/fail, deploy gate trigger). Retention-bounded (cron-driven 90-day rolling delete). Hooks into existing observability (ADR-010) without new infrastructure.

These two changes are coupled because TKT-038 amends both the Reviewer rubric (gate-tag findings) AND the operational store (events table); they are the natural pair downstream of ADR-016. Splitting them into two tickets adds coordination overhead without architectural benefit.


## 2. Non-scope

- Cross-runtime event-replay analytics (e.g., reconstructing a TKT lifecycle from events) — out of v0.1 scope; the table supports it but no CLI is built.
- Event-driven alerting (e.g., Telegram nudge when N events of type X within Y minutes) — out of scope; deferred to ADR-016 layer-1 attempt-exhaustion path.
- Strict (CI-fail) enforcement of gate tags on PR descriptions — Q-ARCH-002-02 Founder decision; soft (warning-only) is the v0.1 default per ADR-018 § Decision Component 2.
- Reviewer rubric prompt refactor for non-gate-tagging concerns — out of scope.


## 3. Required Context

- ADR-016 v0.1.0 § Decision Layer 2 (gate-tagging spec).
- ARCH-002 v0.1.0 § 5.1 (Q-RESEARCH-002-01 events log answer), § 6.6 (Reviewer rubric amendment).
- TKT-036 v0.1.0 (work-queue state transitions feed events).
- TKT-037 v0.1.0 (escalation-surface emissions feed events).
- `MULTI-HERMES-CONTRACT.md` v0.2.1 § 5.5 (Reviewer skill loadout).
- `OPERATIONAL-STATE-STORE.md` v0.2.1 § 3 (existing tables — for events table addition pattern).
- `scripts/validate_docs.py` (current implementation — for forward-only check addition pattern).


## 4. Acceptance Criteria

### Part A — Reviewer rubric gate-tagging

**AC-A1.** `dev-assist-reviewer-rubric` skill extended with gate-tag taxonomy (seven values). The skill's prompt instructs Reviewer-Kimi to tag every finding with exactly one gate.

**AC-A2.** `validate_docs.py` extended: new RV-CODE / RV-SPEC artifacts (created after deployment timestamp) MUST have every finding tagged with a valid gate value. Pre-existing artifacts grandfathered (no retroactive enforcement). Forward-only via "new file" detection (file not present in `git ls-tree main`).

**AC-A3.** `dev-assist-cli status --by-gate` flag aggregates findings per gate over a configurable time window (default last 7 days). Output: table with gate name, finding count, percentage of total, top-3 PR examples.

**AC-A4.** `tests/test_reviewer_rubric_gate_tags.py` covers: gate-tag enum validity; validate_docs forward-only check passes for grandfathered artifacts; validate_docs fails for new artifact missing tags; CLI aggregation produces correct counts.

### Part B — events table

**AC-B1.** Schema added to `OPERATIONAL-STATE-STORE.md` v0.3.x: `events(id INTEGER PRIMARY KEY, ts INTEGER NOT NULL, source_runtime TEXT, source_table TEXT, source_id INTEGER, kind TEXT, payload_json TEXT)`. Index on `(ts)` for retention sweep, `(kind)` for query by event type.

**AC-B2.** Event emitters wired into:
- work-queue dispatcher and complete-write paths (one event per state transition);
- escalation-surface (one event per nudge/mail/peek emission);
- runtime_check_invariants enforcement (one event per pass/fail per role);
- self-deployment scripts (install / verify / rollback / upgrade gate triggers — one event each).

**AC-B3.** Retention sweep: cron task at daily cadence deletes rows where `ts < now() - 90 days`. Deletion is via direct DELETE; no soft-delete column needed. Test covering the 90-day boundary.

**AC-B4.** `dev-assist-cli events` new command lists recent events with filters: `--source <runtime>`, `--kind <event_type>`, `--since <duration>`, `--limit <N>`. Output: tabular by default, `--json` flag for machine-readable.

**AC-B5.** `OPERATIONAL-STATE-STORE.md` v0.3.x documents the events table with full schema and retention policy. Migration recorded.

**AC-B6.** `tests/test_events_table.py` covers: schema migration; emission paths from each source; retention sweep; CLI filter combinations; tabular and JSON output.

### Part C — OBSERVABILITY-CONTRACT § Named Failure Modes (folded from ARCH-002 § 6.4)

**AC-C1.** `OBSERVABILITY-CONTRACT.md` extended with a new § "Named Failure Modes" enumerating: `lease_expiry`, `attempt_exhaustion`, `escalation_engine_error`, `concept_anchor_malformed`, `runtime_check_fail`, `model_unreachable`, `secret_missing`, `verify_self_invariant_fail`, `drift`, `over_decomposition`, `role_ood`, plus the new failure modes introduced by ARCH-002: `sandbox_capability_unavailable` (ADR-015), `gate_failure_dispatch` / `gate_failure_complete` (ADR-016), `escalation_modality_invalid` / `paused_on_founder_stuck` (ADR-017), `concept_anchor_unlisted` / `concept_anchor_orphan` / `concept_anchor_alias_collision` (ADR-018), `github_check_api_unreachable` (TKT-036). Each entry has detection signal, recovery path, and escalation modality fields per ARCH-002 § 6.4 table.

**AC-C2.** `dev-assist-cli status` learns to filter / aggregate by failure-mode label (`--by-failure-mode` flag).

### Cross-cutting

**AC-X1.** `python3 scripts/validate_docs.py` passes.

**AC-X2.** No regression on existing `dev-assist-cli status` output (Part A is additive `--by-gate` flag, Part C is additive `--by-failure-mode` flag).


## 5. Allowed Files

### Part A
- `docs/architecture/shared-skills/dev-assist-reviewer-rubric/SKILL.md` (extend)
- `scripts/validate_docs.py` (extend with forward-only check)
- `src/cli/status.py` (extend with `--by-gate` flag)
- `tests/test_reviewer_rubric_gate_tags.py` (NEW)

### Part B
- `src/events/emitter.py` (NEW)
- `src/work_queue/dispatcher.py` (extend with event emission — minimal additive; coordinated with TKT-036's modifications via merge order)
- `src/work_queue/complete.py` (extend)
- `src/escalation/surface.py` (extend — coordinated with TKT-037)
- `src/runtime_check/runtime_check.py` (extend with event emission)
- `scripts/install-self.sh`, `scripts/verify-self.sh`, `scripts/rollback-self.sh`, `scripts/upgrade-self.sh` (extend with event emission)
- `src/cli/events.py` (NEW)
- `tests/test_events_table.py` (NEW)
- `docs/architecture/OPERATIONAL-STATE-STORE.md` (§ 3.x amendment with events table)
- `docs/architecture/migrations/op-store-v0.3.x.md` (extend with events table migration)

### Part C
- `docs/architecture/OBSERVABILITY-CONTRACT.md` (new § Named Failure Modes per ARCH-002 § 6.4)
- `src/cli/status.py` (extend with `--by-failure-mode` flag — same file as Part A's `--by-gate` extension)


## 6. Test Strategy

Test pyramid for this ticket:

- **Unit (`tests/test_reviewer_rubric_gate_tags.py`):** gate-tag enum validity; validate_docs forward-only check passes for grandfathered artifacts; validate_docs fails for new artifact missing tags; CLI aggregation produces correct counts per gate over a time window.
- **Unit (`tests/test_events_table.py`):** schema migration; each emitter source (work-queue, escalation, runtime_check, install/verify/rollback/upgrade) writes a correctly-shaped row; retention sweep deletes rows older than 90 days; CLI filter combinations (`--source`, `--kind`, `--since`, `--limit`) return expected subsets; tabular and JSON output formats.
- **Forward-only enforcement:** new RV-CODE artifact lacking gate tags → CI fail; pre-existing RV-CODE artifact (in `git ls-tree main`) lacking gate tags → CI pass.
- **Cross-cutting:** named-failure-modes catalogue added to OBSERVABILITY-CONTRACT renders in `dev-assist-cli status --by-failure-mode` aggregation.


## 7. Risk Notes

Primary risk: the events table grows unboundedly without retention sweep. Mitigation: retention sweep runs daily and is tested at the 90-day boundary; if the sweep cron fails, an `events_retention_overdue` peek-modality escalation is emitted at 91 days. Secondary risk: gate-tag classification by Reviewer-Kimi may be inconsistent (probabilistic LLM output). Mitigation: validate_docs enforces presence of *some* valid gate tag per finding; classification accuracy is a soft observability metric, not a hard gate. Tertiary risk: events table writes from multiple emitters could become a contention point on SQLite. Mitigation: writes are append-only with auto-incrementing PK; SQLite's WAL mode (per OPERATIONAL-STATE-STORE.md baseline) handles concurrent writes well below v0.1 expected event volume.


## 8. Spec Amendment Notes

Hard rules for this ticket (governance constraints inherited from ARCH-002 + the source ADR; Executor MUST observe):


- Do NOT modify ADR-016 — Architect-cycle authoritative.
- Do NOT modify ADR-018 / TKT-039 territory (concept-anchor freshness ledger) — TKT-039's write zone.
- The events table is *append-only* in all source emitters (only retention-sweep performs DELETE; no UPDATE).
- The events table is *operational-side state*, NEVER authoritative for governance decisions per `HERMES-RUNTIME-CONTRACT.md` § 3 ("If Hermes memory or operational state contradicts repository artifacts, repository artifacts take precedence").
- Forward-only check on RV-CODE / RV-SPEC artifacts MUST NOT retroactively fail pre-existing PRs/artifacts.


## 9. Cross-references

- ADR-016 v0.1.0 § Decision Layer 2.
- ARCH-002 v0.1.0 § 5.1 (events table answer), § 5.3 (verification gates), § 6.6 (Reviewer rubric amendment).
- RESEARCH-002 § 6.2 (ORCH events.jsonl), § 6.3 (Bernstein WAL), § 7.2 (durable state varied).
- `MULTI-HERMES-CONTRACT.md` v0.2.1 § 5.5.
- `OPERATIONAL-STATE-STORE.md` v0.2.1 § 3.
- `HERMES-RUNTIME-CONTRACT.md` § 3.


## 10. Execution Log

(Reserved for Executor cycle.)
