---
id: ADR-017
version: 0.1.0
status: proposed
---

# ADR-017: Escalation Modalities — Gas Town Mail/Nudge/Peek split

## Status

**Proposed**, pending Founder approval as part of the ARCH-002 synthesis cycle. Supersedes none; coordinates with ADR-008 (escalation classifier deterministic), ADR-006 (IPC), `MULTI-HERMES-CONTRACT.md` v0.2.1 § 6.3 (escalations table), `ESCALATION-POLICY.md` v0.1.1 § 4 (deterministic rules) + § 5 (concept-deviation classifier). Implements RESEARCH-002 § 9 Q-RESEARCH-002-04 (human escalation modeling) and ARCH-002 § 5.4.

## Context

The current `escalations` table (`MULTI-HERMES-CONTRACT.md` v0.2.1 § 6.3, schema authoritative in `OPERATIONAL-STATE-STORE.md` v0.2.1 § 3.6) is single-shape. Every row is treated as immediate-blocking by `dev-assist-escalation-surface`: when the Orchestrator polls the queue and finds a row, it sends a Telegram message and waits.

In practice the project already needs three distinct urgency levels:

1. **Specialist runtime is blocked, decision required before continuing** — e.g., `ESCALATION-POLICY.md` § 4 rule match (force-push, paid third-party introduction, write-zone violation), or § 5 concept-deviation match. Originating runtime SHOULD pause its current work_item rather than continue speculatively.
2. **Reviewer-Kimi flagged a medium-priority finding that doesn't block merge** — e.g., a documentation hygiene observation. Founder should see it eventually but no work pauses.
3. **Specialist runtime emitted an informational note** — e.g., a structural observation like "tests took 4× longer than baseline this run". Founder may browse on demand; no Telegram push.

Today's queue conflates all three: every escalation produces a Telegram push and is treated as blocking. Founder fatigue plus runtime-pause mistakes become structural risks.

RESEARCH-002 surfaces a clear convergence on three modalities: Gas Town's Mail (durable, deferred), Nudge (immediate, blocking), Peek (read-only inspection) (`gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L83-L99`). Ralph's `human.interact` blocking event implements the strongest mode (`ralph-orchestrator@3eca5177db33:README.md:L144-L168`). AgentsMesh Channels frame multi-pod multi-human grouping (`AgentsMesh@93f56e498ebc:design/research/product-model.md:L26-L30`) — over-engineered for v0.1's single-Founder shape but confirms the modality-split direction.

## Decision

Split the single-shape escalation queue into three modalities. Add a `modality` column to the `escalations` table with `CHECK (modality IN ('nudge','mail','peek'))`. Each modality has distinct surface behaviour, runtime-pause behaviour, and persistence semantics.

### Modality 1 — `nudge` (immediate, blocking)

- **Surface:** priority Telegram message via `dev-assist-escalation-surface`, formatted with Russian narrative per `ESCALATION-POLICY.md` § 5.5 advisory call (LLM-generated outside decision path).
- **Runtime behaviour:** originating runtime's current `work_items` row is set to `paused_on_founder` (new status value per ARCH-002 § 6.1). Runtime does not claim new work.
- **Resume behaviour:** when Founder responds, Orchestrator captures the response into the originating work_item's resolution path (durable artifact + escalation table `responded_at`/`response_text`/`resolution_artifact_path`). Originating runtime's work_item transitions back to `claimed`.
- **Default for:** every existing escalation trigger pre-ADR-017 (backward-compatible default).
- **Maps to:** Gas Town Nudge + Ralph `human.interact`.

### Modality 2 — `mail` (durable, deferred)

- **Surface:** entry in the daily Telegram digest (cron-driven, sent once per day) and in `dev-assist-cli status` / web-status surface. Russian narrative inline.
- **Runtime behaviour:** originating runtime continues its work; current `work_items` row stays `claimed`.
- **Persistence:** same as nudge — durable artifact written when Founder acknowledges/responds; `responded_at`/`response_text` columns may stay NULL longer.
- **Used for:** Reviewer recommendations that don't block merge, low-priority observations from specialist runtimes, gate-failure mail per ADR-016 G-COMPLETE-2 except the attempt-exhaustion case.
- **Maps to:** Gas Town Mail.

### Modality 3 — `peek` (read-only inspection)

- **Surface:** entry in `dev-assist-cli status` and web-status surface only. No Telegram push, no daily-digest entry.
- **Runtime behaviour:** originating runtime continues its work; current `work_items` row unaffected.
- **Persistence:** the row exists in `escalations` table for traceability; `responded_at`/`response_text` may stay NULL indefinitely (Founder can ignore peeks).
- **Used for:** structural observations, progress-style commentary, anti-drift freshness-ledger annotations per ADR-018.
- **Maps to:** Gas Town Peek.

### Mapping rules from existing triggers to new modalities

`ESCALATION-POLICY.md` § 4 deterministic-rule matches → `nudge` (default backward-compatible).
`ESCALATION-POLICY.md` § 5 concept-deviation classifier `verdict: ESCALATE` → `nudge`.
`ESCALATION-POLICY.md` § 5 concept-deviation classifier `verdict: AMEND_OR_ESCALATE` (new variant introduced for low-priority deviations that the Architect could resolve) → `mail`.
ADR-016 G-COMPLETE-2 attempt-exhaustion → `nudge`.
ADR-016 layer-2 Reviewer-rubric findings tagged `*_recommendations` (non-blocking) → `mail`.
ADR-018 freshness-ledger drift → `mail`.
Operational observations (e.g., `verify_self_invariant_fail` per ARCH-002 § 6.4 named failure modes) → `mail`.

## Considered Options

### Option A — Three-modality split per Gas Town (CHOSEN)

How it works: as in the Decision section.

Trade-offs:

- **+** Lightweight implementation: one schema column + one new value in `work_items.status` enum + three branches in the existing `dev-assist-escalation-surface` skill.
- **+** Aligns with surveyed convergence (Gas Town + Ralph + implicit AgentsMesh Channels grouping).
- **+** Reduces Founder fatigue: peeks don't push, mails batch into daily digest, only nudges interrupt.
- **+** Reduces speculative-work risk: nudges pause the originating runtime, preventing it from continuing past a decision boundary.
- **−** Operational complexity: classifier authors must pick the right modality. Mitigated by mapping-rule defaults (every `ESCALATION-POLICY.md` § 4 match defaults to nudge unless rule explicitly tags otherwise).

### Option B — Two-modality split (nudge + mail only)

How it works: drop the peek modality; informational notes go into runtime journald only.

Trade-offs:

- **+** Smaller surface; one less branch in the surface formatter.
- **−** Loses the freshness-ledger annotation pathway (ADR-018 emits peeks to track concept-anchor health without alerting). The ledger would need its own surface, duplicating effort.

Rejected: ADR-018 forward-references peek modality; bundling the two ADRs is more cohesive.

### Option C — Status quo (single-shape queue)

How it works: keep current queue; rely on Founder filtering out non-urgent Telegram messages.

Trade-offs:

- **+** Zero implementation cost.
- **−** Founder fatigue is a known Operations risk per `OBSERVABILITY-CONTRACT.md` (Founder is the only operator).
- **−** Speculative-work risk persists.

Rejected: surveyed convergence is too clear to ignore.

### Option D — AgentsMesh-style N:M Channels

How it works: fully model multi-pod multi-human communication groups (`AgentsMesh@93f56e498ebc:design/research/product-model.md:L26-L30`).

Trade-offs:

- **−** v0.1 has one Founder + N specialist runtimes; N:M abstraction is unnecessary.
- **−** Larger schema and surface; over-engineering risk per NUDGE § 12.2.

Rejected; recorded in ARCH-002 § 10 Future Possibilities for v0.2+ if a second human is ever added.

## Consequences

- **Implementation cost.** TKT-037 implements: schema migration adding `modality` column with default `'nudge'`; new value `paused_on_founder` in `work_items.status` enum; three-branch surface formatter in `dev-assist-escalation-surface` skill; daily-digest cron task. Estimated ~150-200 lines of new code + ~80 lines of tests + ~50 lines of skill update.
- **Schema migration.** Additive only: `ALTER TABLE escalations ADD COLUMN modality TEXT NOT NULL DEFAULT 'nudge' CHECK (modality IN ('nudge','mail','peek'))` plus enum extension on `work_items.status`. Backward-compatible: all existing rows are `nudge`.
- **Backward compatibility.** Pre-ADR-017 escalation rows automatically receive `modality='nudge'`, matching current behaviour. New rules in `ESCALATION-POLICY.md` after ADR-017 ratify can specify modality explicitly.
- **Failure modes.** New entries in OBSERVABILITY-CONTRACT § Named Failure Modes: `escalation_modality_invalid` (write attempt with bad modality value — schema CHECK rejects), `paused_on_founder_stuck` (work_item in `paused_on_founder` for > 24h without Founder response — surfaces as mail-digest reminder).
- **`ESCALATION-POLICY.md` v0.1.2 amendment.** Each rule in § 4 and the classifier verdicts in § 5 gain a `modality` field (defaulting to `nudge` for backward compatibility). § 5 introduces the new `AMEND_OR_ESCALATE` verdict variant for `mail`-modality deviations.
- **Founder UX.** Daily Telegram digest at a fixed local time (default 09:00 Founder TZ) with all `mail` entries since previous digest. Web-status surface and `dev-assist-cli status` show all three modalities with filter flags.

## References

- RESEARCH-002 § 6.1 (Gas Town deep dive), § 6.8 (Ralph deep dive), § 7.4 (human-in-loop theme).
- ARCH-002 § 3.8 (App-8), § 5.4 (Q-RESEARCH-002-04), § 6.2 (amendment).
- `gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L83-L99` (Mail/Nudge/Peek source).
- `ralph-orchestrator@3eca5177db33:README.md:L144-L168` (human.interact blocking source).
- ADR-008 (deterministic classifier), ADR-006 (IPC), `MULTI-HERMES-CONTRACT.md` § 6.3, `ESCALATION-POLICY.md` § 4 + § 5.
- TKT-037 (implementation ticket).
