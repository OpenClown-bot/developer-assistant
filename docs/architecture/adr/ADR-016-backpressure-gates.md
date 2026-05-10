---
id: ADR-016
version: 0.1.0
status: proposed
---

# ADR-016: Backpressure Gates As Orchestration Primitive — Ralph adoption

## Status

**Proposed**, pending Founder approval as part of the ARCH-002 synthesis cycle. Supersedes none; coordinates with ADR-006 (IPC), ADR-010 (observability), `MULTI-HERMES-CONTRACT.md` v0.2.1 § 6.2 (work_items state machine), `ARCH-001.md` v0.3.0 § 17 (CI). Implements RESEARCH-002 § 9 Q-RESEARCH-002-03 (verification gates split) and ARCH-002 § 5.3.

## Context

Today the verification gates that determine whether a PR is acceptable run *outside* the work-queue claim/complete cycle. `ARCH-001.md` v0.3.0 § 17 names two CI-required checks (validate-docs, Run PR Agent) plus the Reviewer-Kimi rubric encoded in `dev-assist-reviewer-rubric`. The work-queue's `result_json` column is opaque JSON; the queue does not enforce gate state when promoting a `ticket_implementation` or `ticket_review` work item to `completed`.

This means a buggy or compromised Executor runtime that emits `complete` despite a failing CI run could mark a work item `completed`, and the queue would believe it. Fail-closed defaults exist at the escalation-policy layer (`ESCALATION-POLICY.md` § 3) but not at the work-queue-state-transition layer.

RESEARCH-002 surfaces a clear convergence: Ralph promotes test/lint/typecheck rejection from CI-aspirational to orchestration-structural via "backpressure gates" (`ralph-orchestrator@3eca5177db33:README.md:L136-L142`). kodo states explicitly that orchestrators should structurally enforce verification (`kodo@9758a0a1d0b1:docs/orchestration-tenets.md:L11-L13`). OpenCastle names "fast review after every step + lint/test/build checks" as part of the product, not a post-hoc checklist (`opencastle@18c6f2cf4e5c:README.md:L114-L122`).

## Decision

Promote backpressure gates from CI-only to a two-layer split, both layers enforced structurally:

### Layer 1 — Orchestrator-loop gates (NEW, structural)

The work-queue dispatcher and `complete`-write path enforce four gates:

- **G-DISPATCH-1.** The dispatcher MUST NOT dispatch a `ticket_implementation` work item for a ticket whose `status` (frontmatter) is anything other than `ready`. (Currently informal practice; promoted to structural rule.)
- **G-DISPATCH-2.** The dispatcher MUST NOT dispatch a `ticket_review` work item for a PR whose `validate-docs` CI check is `conclusion: failure`. (Currently no such check; new rule.)
- **G-COMPLETE-1.** The `complete`-write path on `work_items` MUST refuse to promote a work_item to `completed` while the tied PR has any required CI check at `conclusion: failure`. (Currently no such check; new rule. The check is an outer constraint atop the existing `claim_lease_until` enforcement.)
- **G-COMPLETE-2.** When a work_item exceeds `max_attempts` for `failed` reasons unrelated to a Founder decision, the Orchestrator MUST emit a `nudge`-modality escalation per ADR-017 with `trigger_kind='attempt_exhaustion'`, and set the work_item to `failed` (terminal). (Currently informal practice; promoted to structural rule.)

### Layer 2 — CI / Reviewer-PR gates (existing, retained)

Unchanged from `ARCH-001.md` § 17 plus `dev-assist-reviewer-rubric`: validate-docs, Run PR Agent, Reviewer-Kimi rubric. ADR-016 amends only that the Reviewer rubric tags every finding with one of the named gate categories: `tests_gate`, `lint_gate`, `typecheck_gate`, `docs_gate`, `concept_anchor_gate`, `cross_link_gate`, `cross_model_consistency_gate`. This makes gate-failure-rate observable per category in `dev-assist-cli status` aggregates.

## Considered Options

### Option A — Two-layer split with named gates (CHOSEN)

How it works: as in the Decision section. Orchestrator-loop layer enforces state-transition validity; CI/Reviewer layer enforces artifact correctness.

Trade-offs:

- **+** Structural defense-in-depth: a buggy Executor cannot mark work `completed` if CI is failing; the queue refuses the write transactionally.
- **+** Gate-tagging at the Reviewer level produces operational signal — `dev-assist-cli status` can show "lint_gate: 12% finding rate" or "concept_anchor_gate: spike in last 24h".
- **+** Aligned with kodo's tenet (`kodo@9758a0a1d0b1:docs/orchestration-tenets.md:L11-L13`) and Ralph's structural rejection.
- **−** Layer 1 requires GitHub Check API integration in the work-queue plugin (read-only). New dependency surface, but `gh-cli` is already on the runtime per TKT-034 § 1.B.viii.
- **−** Tight coupling between work-queue state machine and CI state. If the GitHub API is unreachable, layer-1 gates fail-closed (cannot promote to completed), which is a deliberate choice per `ESCALATION-POLICY.md` § 3 fail-closed-defaults pattern.

### Option B — CI-only gates with informal Executor self-discipline (status quo)

How it works: keep the current shape; rely on Executor prompts plus Reviewer-Kimi to catch failed-gate completions.

Trade-offs:

- **+** Zero implementation cost.
- **−** Same-model echo chamber risk: Executor and Reviewer are both LLM-driven; structural enforcement at the queue level is independent of LLM judgement.
- **−** Survey unanimous on stronger orchestrators having structural verification.

Rejected: per Founder mandate "we accept very serious changes" — this is the right place to take a structural step.

### Option C — Three-layer split (Orchestrator-loop + CI + Founder-gate)

How it works: add a third layer requiring explicit Founder approval before any work item is `completed`.

Trade-offs:

- **−** Conflicts with `PRD-001.md` § 13.1 autonomy mandate (Founder approves merges, not every state transition).
- **−** Latency cost per work item.

Rejected: `PRD-001.md` § 4 non-goal "Guarantee that generated implementation is correct without CI, review, and explicit user approval" already places Founder at the merge gate, not at the queue-state gate. Three-layer split duplicates merge gate.

## Consequences

- **Implementation cost.** TKT-036 implements layer-1 gates in `src/work_queue/`; TKT-038 implements gate-tagging in the `dev-assist-reviewer-rubric` skill plus validate_docs.py forward-only check. Estimated ~200-300 lines of work_queue code + ~50 lines of Reviewer rubric edits + ~30 lines of validate_docs check.
- **Schema migration.** `OPERATIONAL-STATE-STORE.md` schema migration v0.3.x: extend `work_items.status` enum to include `paused_on_founder` (per ADR-017) and `cancelled` (per ARCH-002 § 6.1). Additive; no destructive changes.
- **Backward compatibility.** Existing in-flight work items unaffected; new gates apply forward-only after deployment.
- **Failure modes.** New entries in OBSERVABILITY-CONTRACT § Named Failure Modes: `gate_failure_dispatch` (dispatcher refused), `gate_failure_complete` (complete-write refused). Both surface as mail-modality unless they coincide with attempt_exhaustion (which surfaces as nudge per G-COMPLETE-2).
- **Operator UX.** `dev-assist-cli status` extends with `--by-gate` flag aggregating Reviewer-rubric gate-tag findings per category over a time window.

## References

- RESEARCH-002 § 6.8 (Ralph deep dive), § 7.3 (verification theme).
- ARCH-002 § 3.3 (App-3), § 3.10 (App-10), § 5.3 (Q-RESEARCH-002-03), § 6.1 (amendment), § 6.6 (Reviewer rubric amendment).
- `ralph-orchestrator@3eca5177db33:README.md:L136-L142` (backpressure gates source).
- `kodo@9758a0a1d0b1:docs/orchestration-tenets.md:L11-L13` (verification tenet source).
- `opencastle@18c6f2cf4e5c:README.md:L114-L122` (panel quality gates source).
- ADR-006 (IPC), ADR-010 (observability), `MULTI-HERMES-CONTRACT.md` § 6.2.
- TKT-036 (work-queue gates implementation), TKT-038 (Reviewer rubric gate-tagging).
