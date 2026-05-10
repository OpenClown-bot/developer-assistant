---
id: ADR-018
version: 0.1.0
status: proposed
---

# ADR-018: Anti-Drift Concept-Anchor Freshness Ledger

## Status

**Proposed**, pending Founder approval as part of the ARCH-002 synthesis cycle. Supersedes none; coordinates with ADR-008 (deterministic escalation classifier), ADR-002 (repository state), `PROJECT-CONCEPT.md` v0.1.0 § 2 (concept anchor block), `MULTI-HERMES-CONTRACT.md` v0.2.1 § 5.5 (Reviewer skill loadout), `scripts/validate_docs.py` (CI gate). Implements RESEARCH-002 § 9 Q-RESEARCH-002-06 (anti-drift mechanism) and ARCH-002 § 5.6.

## Context

The project has *four* artifact-producing LLM roles (Business Planner, Architect, Executor, Reviewer) plus three orchestrator roles, with the Strategic Orchestrator producing additional governance state in `docs/orchestration/SESSION-STATE.md` and `docs/session-log/`. This is unusual breadth among the surveyed repos and creates a structural risk: **inter-artifact semantic drift on factual concept-anchor claims**.

Three current mechanisms partially address drift:

1. **`PROJECT-CONCEPT.md` § 2 structured concept anchor** — drift in the concept-replacement sense (target user swap, tech-stack swap, deployment-target swap) is caught by `ESCALATION-POLICY.md` § 4 + § 5 classifier.
2. **Cross-link / frontmatter / status-flow validation in `validate_docs.py`** — drift in the references-vs-reality sense is caught at the validate-docs CI gate.
3. **Cross-model independent review** doctrine in `AGENTS.md` — same-model echo-chamber drift mitigated by the Anthropic + DeepSeek + Moonshot review triangle.

What none of these mechanisms catches is **inter-artifact factual divergence on long-lived concept-anchor claims**. Examples:

- ARCH-001 § 11.1 says "memory isolation is filesystem-level". If a future Reviewer rubric edit later judges code against an implicit "memory broker" mental model, the artifacts disagree without triggering any rule.
- PRD-001 § 13.2 says "five Hermes runtimes". If Architect later writes ARCH-003 with seven runtimes (e.g., adding a Tester role per Founder ask), an existing TKT or ADR that still cites "five runtimes" goes stale without triggering any rule.
- MODEL-CATALOG § 5 says "OmniRoute primary + OpenRouter backup". If a future ADR adds a third routing layer, contracts that still cite the two-layer assumption are silently stale.

RESEARCH-002 surfaces CLITrigger's wiki-injection pattern (`CLITrigger@fd4731bb3e20:README.md:L107-L115`) as the closest survey analogue: selective token-budgeted injection of canonical knowledge at dispatch time. OpenHands' confirmation-gated repo-memory pattern (`OpenHands@9482ab1a666d:skills/agent_memory.md:L10-L30`) is the right governance shape. kodo names "drift / heresy" as a top failure mode (`kodo@9758a0a1d0b1:docs/orchestration-tenets.md:L21-L30`).

## Decision

Add a **concept-anchor freshness ledger** as a new structured artifact, coupled with a validate_docs.py extension and a Reviewer-rubric context-injection branch. The ledger lists, for each long-lived contract document, the *concept-anchor IDs it asserts*; validate_docs.py checks anchor membership and forward consistency; the Reviewer skill injects relevant anchors at dispatch time.

### Component 1 — `docs/architecture/CONCEPT-ANCHOR-FRESHNESS.md` (new artifact)

Architect write zone. A small structured table mapping each long-lived contract document to the concept-anchor IDs it asserts. Schema:

```markdown
| Contract document | Asserted anchor IDs | Last reviewed |
| --- | --- | --- |
| ARCH-001 v0.3.0 | multi_hermes_runtime_topology, hermes_agent_runtime, sqlite_state_store, linux_vps_systemd, omniroute_routing_primary, deterministic_escalation_policy, founder_pre_approved_model_catalog | 2026-05-10 |
| MULTI-HERMES-CONTRACT v0.2.1 | multi_hermes_runtime_topology, sqlite_state_store, deterministic_escalation_policy | 2026-05-10 |
| ... | ... | ... |
```

Anchor IDs match keys in `PROJECT-CONCEPT.md` § 2 (e.g., `tech_anchors[].id`, `risk_boundaries[].id`, `deviation_rules[].id`) or are explicit synonym aliases declared in a small alias table at the top of CONCEPT-ANCHOR-FRESHNESS.md.

### Component 2 — `validate_docs.py` extension (two new checks)

- **Check 1 (anchor membership):** every asserted anchor ID in the ledger maps to a current entry in `PROJECT-CONCEPT.md` § 2 OR to an entry in the alias table. Mismatches → CI fail with line-precise error message.
- **Check 2 (forward consistency, soft):** when a contract document is changed in a PR (file modified in PR diff), its asserted anchors must be listed in the PR body under a `## Concept Anchors Asserted` section. Mismatches → CI **warning** (annotation only; merge allowed). Per Q-ARCH-002-02 the strict-vs-soft choice is Founder-decision; ADR-018 adopts soft as v0.1 default.

### Component 3 — Reviewer-rubric context injection (CLITrigger pattern)

The `dev-assist-reviewer-rubric` skill (write zone: `docs/architecture/shared-skills/dev-assist-reviewer-rubric/SKILL.md`) extends to read CONCEPT-ANCHOR-FRESHNESS.md at dispatch time, identify the relevant anchors for the PR's changed files, and inject them into the Reviewer LLM's context. This gives Reviewer-Kimi a deterministic concept-anchor reference rather than relying on its trained-in mental model.

### Component 4 — Optional `peek`-modality emit on stale anchors

When the validate_docs `Check 2` warning fires (PR changed contract without listing anchors), the workflow optionally emits a `peek`-modality escalation per ADR-017 to the freshness-ledger digest channel, with `trigger_kind='concept_anchor_unlisted'`. This builds a passive observation log of which contracts get amended without anchor-discipline, surfacing patterns over time. Optional in v0.1; can be disabled via env flag.

## Considered Options

### Option A — Freshness ledger + validate_docs + Reviewer injection (CHOSEN)

How it works: as in the Decision section.

Trade-offs:

- **+** Lightweight: one new ~50-line artifact + ~30 lines of validate_docs.py extension + one branch in Reviewer skill loader.
- **+** Catches *factual concept-anchor divergence*, complementing the existing same-model-echo-chamber mitigation (cross-model review) and concept-replacement mitigation (escalation classifier).
- **+** Aligned with surveyed CLITrigger wiki-injection + OpenHands governance-gate patterns.
- **+** Soft-default check (Q-ARCH-002-02 option B) avoids blocking merges on documentation hygiene.
- **−** Maintenance cost: ledger needs Architect attention when anchors evolve. Mitigated by `Last reviewed` column making staleness visible, and by Reviewer rubric injecting the ledger into review context (so a contract amendment that misuses an anchor is caught at review time).
- **−** Some judgement is required to decide which anchor IDs a contract asserts. Mitigated by starting with a small explicit catalogue in `PROJECT-CONCEPT.md` § 2 (~20 anchor IDs total v0.1) and growing only by Architect-cycle PR.

### Option B — Add full event-log replay (`OPERATIONAL-STATE-STORE` events table)

How it works: complement the ledger with a Bernstein-style append-only event log of every contract change, allowing post-hoc replay analysis.

Trade-offs:

- **+** Stronger forensic capability.
- **−** Conflates two concerns: drift detection (this ADR) and event-log durability (separately addressed by ARCH-002 § 5.1 / TKT-038).

ADR-018 addresses only drift detection; the events table is implemented in TKT-038 as a *separate* mechanism. Both can be used together.

### Option C — Pure Reviewer-prompt injection (no validate_docs check, no ledger artifact)

How it works: hand-craft a long Reviewer prompt that lists anchors inline; rely on Reviewer-Kimi to spot drift.

Trade-offs:

- **+** Zero artifact / schema overhead.
- **−** Same-model-echo-chamber risk: Reviewer-Kimi is one LLM; its judgement on factual anchor consistency is probabilistic.
- **−** Prompt bloat: anchors inline in the rubric grow with the project.
- **−** No CI gate: drift can land without any check.

Rejected: structural enforcement is the point; relying on a single LLM's probabilistic judgement misses the goal.

### Option D — Status quo (no anti-drift mechanism)

Rejected per the Founder mandate to accept structural changes; per kodo's drift-as-named-failure-mode discipline; per the four-LLM-role artifact-production fan-out.

## Consequences

- **Implementation cost.** TKT-039 implements: ledger artifact (~50 lines), validate_docs.py two checks (~30 lines), Reviewer skill context-injection branch (~20 lines), tests for ledger membership/consistency (~50 lines). Cross-cuts Architect write-zone + scripts.
- **Reviewer rubric impact.** Average Reviewer prompt grows by ~200 tokens per dispatch (relevant anchors injected); within OpenCastle-style "context budget" amendment per ARCH-002 § 6.3.
- **Backward compatibility.** Existing contracts can be migrated incrementally; pre-ADR-018 contracts default to "(not yet anchored)" in the ledger and trigger a Mail-digest reminder per `Last reviewed` field. Initial seeding done by TKT-039 across the 13 long-lived contracts known on 2026-05-10.
- **Failure modes.** New entries in OBSERVABILITY-CONTRACT § Named Failure Modes: `concept_anchor_unlisted` (Check 2 warning), `concept_anchor_orphan` (Check 1 fail — anchor referenced but no `PROJECT-CONCEPT.md` § 2 entry), `concept_anchor_alias_collision` (alias table has duplicate ID).
- **Operator UX.** `dev-assist-cli concept-anchors` new command lists ledger entries; `--stale` flag shows contracts whose `Last reviewed` is > 90 days old.

## References

- RESEARCH-002 § 6.7 (CLITrigger deep dive), § 6.10 (OpenHands), § 7.7 (failure-modes theme).
- ARCH-002 § 3.1 (App-1), § 3.4 (App-4), § 5.6 (Q-RESEARCH-002-06 answer), § 6.5 (amendment proposal).
- `CLITrigger@fd4731bb3e20:README.md:L107-L115` (wiki injection source).
- `OpenHands@9482ab1a666d:skills/agent_memory.md:L10-L30` (governance-gate source).
- `kodo@9758a0a1d0b1:docs/orchestration-tenets.md:L21-L30` (drift named failure mode source).
- ADR-002 (repository state), ADR-008 (deterministic classifier), `PROJECT-CONCEPT.md` § 2.
- TKT-039 (implementation ticket).
