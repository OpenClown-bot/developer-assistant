---
id: ADR-009
version: 0.1.0
status: draft
---

# ADR-009: Model Assignment And Fallback — Founder-pre-approved catalog with main + fallback chains

## Status

Draft, pending Founder approval. Supersedes none. Related: ADR-008 (escalation classifier).

## Context

`PRD-001.md` v0.2.1 § 13.1 sets autonomy as the default and escalation as the exception. Per-call model selection is one of the most frequent runtime decisions; if every model pick required a Founder approval, autonomy is dead. If no model picks ever require Founder approval, the v0.1 budget envelope can be exceeded silently.

`ARCH-001.md` v0.3.0 § 16 defines a Founder-pre-approved catalog as the boundary: within-catalog picks are autonomous; catalog changes escalate. `MODEL-CATALOG.md` enumerates the v0.1 catalog. This ADR records WHY the catalog shape was chosen and WHY the routing layer is OmniRoute / OpenRouter rather than direct provider SDKs.

## Decision

Adopt a **Founder-pre-approved model catalog** with three structural choices:

1. **Per-role assignment**: each specialist runtime has one main model and an ordered fallback chain (Fallback 1 → 2 → 3). The main model is what the runtime starts each work item with; the fallback chain handles upstream errors, rate limits, and content-filter refusals.
2. **Auxiliary classifier set**: the `dev-assist-escalation-policy` plugin uses one of a separate small set of models (`MODEL-CATALOG.md` § 4.2) for the LLM classifier, distinct from the main models so the classification audit is independent.
3. **Routing layer is OmniRoute (primary) + OpenRouter (backup)**: specialist runtimes never call provider SDKs directly. The routing layer resolves catalog identifiers to current provider slugs and handles retry/rate-limit/region-failover.

Within-catalog picks (Hermes' built-in retry advancing through the fallback chain; the auxiliary classifier choosing among permitted alternatives; the routing layer falling over from OmniRoute to OpenRouter) proceed autonomously. Catalog changes (adding a model, changing a role's main, reordering a fallback chain, changing the routing layer) escalate per `ESCALATION-POLICY.md` § 4.6 (`paid:llm_provider_outside_catalog`).

## Considered Options

For convenience, "model assignment" decision and "routing layer" decision are evaluated together because they interact.

### Option A — Per-role catalog with fallback chains, OmniRoute + OpenRouter routing (CHOSEN)

How it works: as in the Decision section.

Trade-offs:

- + Founder approval is captured durably (in this artifact); per-call decisions don't pay Founder time.
- + Fallback chains absorb provider outages without escalation noise.
- + Separating auxiliary classifier from main models keeps the policy audit independent.
- + Routing layer abstracts provider API drift.
- + No paid third-party broker beyond OmniRoute / OpenRouter (already-approved spend).
- − Catalog refresh cadence requires Founder action (default: refresh on Founder request per `ARCH-001.md` § 22). Mitigated: refreshes are infrequent.
- − Catalog identifiers are placeholders that the routing layer resolves; if both routing providers don't recognize an identifier, the runtime falls back automatically and the verify script's connectivity check surfaces the issue on the next run.

### Option B — Open-ended model selection (no catalog)

How it works: each runtime picks any model the routing layer can reach. No fixed list.

Trade-offs:

- + Maximum flexibility.
- − No budget guard. A runtime could pick a high-cost model out of habit and the v0.1 envelope blows.
- − No audit trail of "why this model." Founder loses a key knob.
- − The `paid:llm_provider_outside_catalog` deterministic rule disappears; the only safety net is the LLM classifier, which is itself probabilistic.

Rejected: bypasses the budget guard.

### Option C — Single model assignment per role (no fallback chain)

How it works: each role has exactly one model. On error, the runtime fails.

Trade-offs:

- + Simplest to describe.
- − A single provider outage takes down the entire runtime.
- − Rate-limit handling has nowhere to go.
- − Content-filter refusal has nowhere to go.

Rejected: insufficient resilience.

### Option D — Catalog with no role assignment (any role can use any catalog entry)

How it works: catalog enumerates allowed models; each runtime picks per-call from the whole catalog.

Trade-offs:

- + More flexible.
- − Loses the per-role tuning rationale (`MODEL-CATALOG.md` § 4.3): the Architect benefits from `claude-opus-4.5`'s longer reasoning; the Reviewer benefits from `claude-sonnet-4.5`'s code review depth. A per-call free-for-all may pick worse models for a role's needs.
- − Cost varies wildly per call without a meaningful guardrail; the budget envelope is fuzzier.

Rejected: per-role assignment encodes the Founder's pricing/quality choices durably.

### Option E — Direct provider SDKs (no routing layer)

How it works: each runtime imports OpenAI/Anthropic/Google SDKs directly.

Trade-offs:

- + One less hop.
- + Provider-specific features available natively.
- − Provider-API-shape changes require code changes in five runtimes.
- − Per-call rate-limit and retry logic must be implemented per runtime.
- − Region failover must be implemented per runtime.
- − Catalog identifier abstraction is lost; switching `gpt-5.1` to a successor model means everywhere.

Rejected: routing layer's benefits exceed its cost.

### Option F — OmniRoute only (no OpenRouter backup)

How it works: only OmniRoute is the routing layer. If OmniRoute is down, the system is down.

Trade-offs:

- + Simpler.
- − Single point of failure.
- − OmniRoute's outage history is short; assuming low rate is reasonable but not zero.

Rejected: minimal incremental cost to add OpenRouter as a backup; large incremental resilience benefit.

### Option G — Hermes' built-in model routing only (no external routing layer)

How it works: Hermes Agent's per-runtime `agent.model` and `agent.fallback_models` are the only routing layer. Each entry is a provider:model identifier.

Trade-offs:

- + No external routing layer.
- − Hermes still needs provider credentials per provider it speaks. Multiplies the secret surface in `SELF-DEPLOY.env`.
- − Provider API shape changes require Hermes runtime updates.
- − Composes poorly with the catalog identifier abstraction.

Rejected: routing layer indirection is the right level for the catalog identifier abstraction.

## Decision Criteria And Mapping

| Criterion | Option A (catalog + chains + routing) | Option B (open-ended) | Option C (single per role) | Option D (catalog no role) | Option E (direct SDKs) | Option F (OmniRoute only) | Option G (Hermes only) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Budget guard | Yes (catalog) | No | Yes | Yes (catalog) | Per-runtime code | Yes | Yes |
| Resilience | Yes (chain + 2 routers) | Depends | No | Yes | Per-runtime code | Single router | Single router |
| Audit captures choices | Yes | Weak | Yes | Partial | Weak | Yes | Yes |
| API drift mitigation | Yes (routing layer) | Routing-dep | Yes (routing layer) | Yes (routing layer) | No | Yes | No |
| Multi-provider feasible | Yes | Yes | Yes | Yes | Heavy | Yes | Heavy |
| Compatible with v0.1 budget | Yes | At risk | Yes | Yes | Yes | Yes | Yes |
| Compatible with PRD § 13.1 | Yes (autonomy + bounded) | No (no bound) | Yes | Yes | Yes | Yes | Yes |
| Implementation cost | Low (config only) | Low | Low | Low | Medium | Low | Low |

Option A wins by carrying every concern.

## Consequences

- The catalog (`MODEL-CATALOG.md`) is the durable record of Founder approval. Changes to that document escalate via `ESCALATION-POLICY.md` § 9.
- Specialist runtimes' `agent.model` and `agent.fallback_models` are populated from the catalog by the install script (TKT-021).
- The `dev-assist-escalation-policy` plugin reads the catalog's auxiliary classifier set via the same mechanism (TKT-023).
- TKT-026 implements a small enforcement helper that the install script invokes to verify each runtime's `agent.model` matches the catalog at startup; mismatch fails the verify check.
- Adding a new model requires editing the catalog, opening a PR, RV-SPEC, Founder approval. Rolling out is then a config-only change applied by re-running the install script.
- Routing-layer outage handling: OmniRoute → OpenRouter falls automatically; both unreachable raises an escalation (`paid:llm_provider_outside_catalog` does NOT fire because the destination is in catalog; instead the `attempt_count` exhausts and the work-item failure path fires).
- Empirical cost-monitoring is out of scope for this ADR; if the trial reveals divergence from expectation, a follow-up ADR addendum proposes adjustment.

## Cross-References

- `PRD-001.md` v0.2.1 § 13.1 (autonomy + escalation)
- `ARCH-001.md` v0.3.0 § 16
- `MODEL-CATALOG.md` (enumerated catalog)
- `ESCALATION-POLICY.md` § 4.6 (`paid:llm_provider_outside_catalog`), § 9 (tuning)
- `MULTI-HERMES-CONTRACT.md` § 4 (per-runtime config), § 9.2 (fallback chain on outage)
- `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 5.4, § 6.7
- `docs/orchestration/SESSION-STATE.md` § Current Tooling Decisions (Founder approval timestamp)
- ADR-008 (escalation classifier)
- Implementation: TKT-026 (catalog enforcement helper)
