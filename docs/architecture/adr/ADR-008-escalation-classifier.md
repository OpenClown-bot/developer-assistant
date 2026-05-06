---
id: ADR-008
version: 0.1.0
status: draft
---

# ADR-008: Escalation Classifier — deterministic rules + LLM classifier

## Status

Draft, pending Founder approval. Supersedes none. Related: ADR-002 (repository state), ADR-006 (IPC), ADR-009 (model assignment).

## Context

`PRD-001.md` v0.2.1 § 13.1 defines the escalation rule:

> The assistant escalates to the Founder only when a candidate decision either (a) strongly deviates from the original concept captured at intake, or (b) risks breaking already-committed scope or operational state.

The PRD intentionally does not commit to a classifier mechanism; the Architect must produce one. `ESCALATION-POLICY.md` operationalizes the mechanism. This ADR records why the chosen mechanism is **deterministic rules first, LLM classifier second**, and why the alternatives were rejected.

## Decision

Operationalize the escalation rule with two layers:

1. **Deterministic rule set** (`ESCALATION-POLICY.md` § 4): a curated set of patterns covering force-push, hard reset, file deletion under governance directories, schema-destructive SQL, credential rotation, public endpoint exposure, paid third-party introduction, write-zone violations, PRD/ADR status changes, and similar concrete risks. Match → escalate, no LLM consultation.
2. **LLM classifier** (`ESCALATION-POLICY.md` § 5): when no deterministic rule matches and the action is not trivially read-only, an auxiliary LLM classifies whether the action deviates from the intake concept or risks breaking committed scope. Verdict ASK_FOUNDER → escalate.

Both layers run inside the `dev-assist-escalation-policy` Hermes plugin, registered on the `pre_tool_call` hook in every specialist runtime. Fail-closed defaults apply when the rule engine errors or the classifier is unreachable.

## Considered Options

### Option A — Deterministic rules + LLM classifier (CHOSEN)

How it works: as in the Decision section. The deterministic layer catches the obvious-and-bounded categories; the LLM layer catches the novel-and-judgment-based cases.

Trade-offs:

- + Coverage: deterministic rules guarantee catch on the named categories; LLM extends to fuzzy cases.
- + Cost-bounded: deterministic match short-circuits; LLM is invoked only when no rule matches.
- + Auditable: every escalation records `trigger_kind` (which rule, or `llm_classifier`) so the Founder can review classifier behavior.
- + Tunable: adding/removing rules is small; refining the LLM prompt is small.
- − Two layers to maintain.
- − LLM classifier introduces a runtime cost (~$0.001 per classification, expected <100/hour during active work; total budget impact small but non-zero).
- − LLM classifier introduces latency (~1-3 seconds typical, up to 10s timeout) on tool calls that don't match any deterministic rule. Mitigated by a per-runtime cache for repeated identical actions within 5 minutes.

### Option B — Deterministic rules only (no LLM)

How it works: the rule set is the entire policy. Anything not matched proceeds.

Trade-offs:

- + Lowest cost (no LLM call per tool call).
- + Lowest latency.
- + Fully auditable; no probabilistic component.
- − Catches only what is enumerated. The PRD § 13.1 first limb ("strongly deviates from the original concept") is hard to express deterministically because "the concept" is fuzzy.
- − Every novel category requires a human (Architect) to update the rule set. Each rule lag = a window where novel scope drift goes through unchecked.
- − Encourages either over-broad rules (false positives, excessive escalation noise) or over-narrow rules (misses real scope drift).

Rejected: insufficient for the first limb of PRD § 13.1.

### Option C — LLM classifier only (no deterministic rules)

How it works: every non-trivial tool call is classified by an LLM.

Trade-offs:

- + Single layer; conceptually clean.
- + Adapts to novel categories without human rule updates.
- − Cost and latency: every tool call pays the LLM cost. With Hermes' high tool-call frequency this is not bounded.
- − Reliability: the LLM may classify a force-push as PROCEED on a bad day. Force-push is a clear-cut case the Architect would never want to leave to a probabilistic model.
- − Auditability: every escalation says "the LLM said so"; rules-based escalation says "rule X.Y matched on input Z" — much easier to debug.
- − If the LLM provider has an outage, fail-closed on every tool call would block all work. Mitigated only by adding a fallback layer, which is what Option A already does.

Rejected: probabilistic-only is the wrong shape for high-stakes deterministic categories.

### Option D — Static type-system enforcement (compile-time)

How it works: encode the policy as type constraints in the runtime's code; tool calls that would violate are rejected at compile time.

Trade-offs:

- + Strongest guarantee: violation is impossible.
- − The runtime is an LLM-driven agent; "compile-time" doesn't really apply to runtime tool argument synthesis. Tool arguments are LLM output strings.
- − A static analyzer over LLM output is itself a runtime check, which collapses to Option A or B.

Rejected: category error.

### Option E — RAG over PRD/ADRs (retrieve-augmented classification)

How it works: every tool call is classified by an LLM that has the PRD/ADRs retrieved into its context. The retrieval grounds the classifier in the current scope.

Trade-offs:

- + Higher quality classifications (the LLM has the actual scope text to reason against).
- − Higher latency (retrieval + LLM call) and higher cost.
- − Embedding model required; v0.1 is `MODEL-CATALOG.md` § 2 explicit about not running embeddings yet.
- − Adds a dependency (vector store) the v0.1 budget envelope rejects (`ESCALATION-POLICY.md` § 4.6 paid:* rules).

Rejected for v0.1; revisited for v0.2 if the LLM classifier in Option A turns out to need more context than the static-text injection currently uses.

### Option F — Human-in-the-loop on every tool call

How it works: every tool call goes to the Founder for approval (essentially Hermes' approval mode set to the strictest level for everything).

Trade-offs:

- + Maximum safety.
- − Defeats the purpose of high autonomy. Founder is woken up every few minutes.
- − Fails the PRD § 13.1 mandate.

Rejected outright.

## Decision Criteria And Mapping

| Criterion | Option A (rules + LLM) | Option B (rules only) | Option C (LLM only) | Option D (types) | Option E (RAG) | Option F (HITL all) |
| --- | --- | --- | --- | --- | --- | --- |
| Catches deterministic categories | Yes | Yes | Probabilistic | N/A | Probabilistic | Yes |
| Catches concept drift | Yes | No | Yes | N/A | Yes | Yes |
| Cost-bounded | Yes | Yes | No | N/A | No | N/A (Founder time) |
| Latency-bounded | Yes (cache) | Yes | No | N/A | No | No (Founder lag) |
| Auditable | Yes | Yes | Weak | N/A | Weak | Yes |
| Compatible with v0.1 budget | Yes | Yes | Yes | N/A | No | N/A |
| Compatible with PRD § 13.1 | Yes | Partial | Partial | N/A | Yes | Yes (but defeats autonomy) |
| Implementation cost | Medium | Low | Low | N/A | High | Trivial |

Option A wins on every relevant axis; Option B is a worse partial; Option C is a reliability regression on the deterministic categories.

## Consequences

- Implementation in TKT-023 produces the `dev-assist-escalation-policy` plugin with both layers and the `pre_tool_call` hook integration.
- The deterministic rule set is enumerated in `ESCALATION-POLICY.md` § 4 and is the authoritative source. Rule changes go through the Architect → RV-SPEC → Founder loop.
- The LLM classifier model is one of the Founder-pre-approved auxiliary classifiers (`MODEL-CATALOG.md` § 4.2). Default: `gpt-5.1-mini`. Changing the default escalates per `ESCALATION-POLICY.md` § 9.
- The classifier prompt is hard-coded in the plugin source, NOT editable by any runtime's MEMORY.md. This prevents a runtime from quietly weakening its own escalation policy via memory drift.
- The classifier runs on a redacted version of the action's arguments to avoid sending secret values to the auxiliary LLM provider.
- Every escalation is durable in the `escalations` table; aggregate audit queries (`ESCALATION-POLICY.md` § 8) inform tuning.
- Fail-closed defaults: if the rule engine errors or the classifier times out, ESCALATE rather than PROCEED.

## Cross-References

- `PRD-001.md` v0.2.1 § 13.1 (escalation rule)
- `ARCH-001.md` v0.3.0 § 15
- `ESCALATION-POLICY.md` (full policy)
- `MULTI-HERMES-CONTRACT.md` § 5.6, § 8.2 (plugin loadout, escalation flow)
- `MODEL-CATALOG.md` § 4.2 (auxiliary classifier set)
- `HERMES-RUNTIME-CONTRACT.md` v0.2.0 § 5 founder_questions
- `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3.8, § 3.9, § 6.4
- ADR-002 (repository state), ADR-006 (IPC), ADR-009 (model assignment)
- Implementation: TKT-023
