---
id: ADR-009
version: 0.1.1
status: draft
---

# ADR-009: Model Assignment And Fallback — Founder-pre-approved catalog with main + fallback chains

## Status

Draft, pending Founder approval. Supersedes none. Related: ADR-008 v0.1.1 (escalation classifier), ADR-011 (routing layer; lands in PR-E).

v0.1.1 (RV-SPEC-012 F2 fix + cross-PR consistency with ADDENDUM-001): replaces the placeholder catalog identifiers with the real OmniRoute Fireworks-backend identifiers from `MODEL-CATALOG.md` v0.1.1 § 4.1; drops the "separate auxiliary classifier set" branch of the Decision (the v0.1 escalation classifier is now deterministic per ADR-008 v0.1.1, so no auxiliary classifier model entry is needed); aligns the routing-layer narrative with ADDENDUM-001's Option B mandate (OmniRoute primary with Fireworks as configured backend; OpenRouter backup; no direct-Fireworks SDK).

## Context

`PRD-001.md` v0.2.1 § 13.1 sets autonomy as the default and escalation as the exception. Per-call model selection is one of the most frequent runtime decisions; if every model pick required a Founder approval, autonomy is dead. If no model picks ever require Founder approval, the v0.1 budget envelope can be exceeded silently.

`ARCH-001.md` v0.3.0 § 16 defines a Founder-pre-approved catalog as the boundary: within-catalog picks are autonomous; catalog changes escalate. `MODEL-CATALOG.md` enumerates the v0.1 catalog. This ADR records WHY the catalog shape was chosen and WHY the routing layer is OmniRoute / OpenRouter rather than direct provider SDKs.

## Decision

Adopt a **Founder-pre-approved model catalog** with three structural choices:

1. **Per-role assignment, capability-only ordering**: each specialist runtime has one main model and an ordered fallback chain (Fallback 1 → 2 → 3). The main model is what the runtime starts each work item with; the fallback chain handles upstream errors, rate limits, and content-filter refusals. Per ADDENDUM-001 (2026-05-06), the chain is ordered by capability fit alone, ignoring per-token price.
2. **No separate auxiliary classifier model in v0.1**: the v0.1 escalation policy is deterministic (`ESCALATION-POLICY.md` v0.1.1 § 5; ADR-008 v0.1.1) and runs no LLM call inside the decision path. The optional advisory-narrative call in `ESCALATION-POLICY.md` v0.1.1 § 5.5 reuses the runtime's catalog main model from § 4.1, so no separate "auxiliary classifier" model entry is required.
3. **Routing layer is OmniRoute primary with Fireworks as configured backend, OpenRouter backup** (ADDENDUM-001 patch, Option B): specialist runtimes never import a Fireworks SDK and never call `api.fireworks.ai` directly. OmniRoute resolves the Fireworks-native paths in `MODEL-CATALOG.md` § 4.1 (`accounts/fireworks/models/<slug>`) to the Fireworks backend; OpenRouter is the fallback routing layer when OmniRoute is unreachable. The routing-layer choice itself is recorded in ADR-011 (PR-E).

Within-catalog picks (Hermes' built-in retry advancing through the fallback chain; the routing layer falling over from OmniRoute to OpenRouter) proceed autonomously. Catalog changes (adding a model, changing a role's main, reordering a fallback chain, changing the routing layer, switching the Fireworks backend to a different provider) escalate per `ESCALATION-POLICY.md` § 4.6 (`paid:llm_provider_outside_catalog`).

### Verification gate

The catalog identifiers in `MODEL-CATALOG.md` § 4.1 are real OmniRoute paths against the Fireworks backend, NOT placeholders. The TKT-026 install verify script issues a 1-token completion against `http://127.0.0.1:<omniroute_port>/v1/chat/completions` for each of the five identifiers at install / upgrade time; failure to resolve raises `paid:third_party_external_service_not_yet_supported` (`ESCALATION-POLICY.md` § 4.6) with no silent fallback to direct-Fireworks (binding precondition recorded in ADR-011).

## Considered Options

For convenience, "model assignment" decision and "routing layer" decision are evaluated together because they interact.

### Option A — Per-role catalog with fallback chains, OmniRoute primary + OpenRouter backup (CHOSEN, v0.1.1)

How it works: as in the Decision section.

Trade-offs:

- + Founder approval is captured durably (in this artifact); per-call decisions don't pay Founder time.
- + Fallback chains absorb provider outages without escalation noise.
- + Capability-only chain ordering (ADDENDUM-001) maximizes task fit; the v0.1 cost-posture override drops per-token-price ranking from the choice space.
- + Routing layer abstracts provider API drift.
- + No paid third-party broker beyond OmniRoute / OpenRouter (already-approved spend; binding precondition that OmniRoute supports the Fireworks backend for all five catalog models, verified 2026-05-06 via OmniRoute issue [#265](https://github.com/diegosouzapw/OmniRoute/issues/265) and re-verified at every install by TKT-026).
- − Catalog refresh cadence requires Founder action (default: refresh on Founder request per `ARCH-001.md` § 22). Mitigated: refreshes are infrequent.
- − OmniRoute is single-source for the Fireworks backend; if OmniRoute drops Fireworks support (e.g., upstream removes the alias), `paid:third_party_external_service_not_yet_supported` fires and the system pauses until the routing layer is restored or OpenRouter is re-validated for the same models. Mitigated: TKT-026 install verify catches drift early.

### Option B — Open-ended model selection (no catalog)

How it works: each runtime picks any model the routing layer can reach. No fixed list.

Trade-offs:

- + Maximum flexibility.
- − No budget guard. A runtime could pick a high-cost model out of habit and the v0.1 envelope blows.
- − No audit trail of "why this model." Founder loses a key knob.
- − The `paid:llm_provider_outside_catalog` deterministic rule disappears; with the v0.1.1 deterministic escalation classifier (ADR-008 v0.1.1), there is no probabilistic safety net at all.

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
- − Loses the per-role tuning rationale (`MODEL-CATALOG.md` v0.1.1 § 4.3): the Architect benefits from `accounts/fireworks/models/deepseek-v4-pro`'s deepest reasoning; the Reviewer benefits from `accounts/fireworks/models/kimi-k2p6`'s long context for diff review; the Executor benefits from `accounts/fireworks/models/glm-5p1`'s top-3 Code Arena ranking. A per-call free-for-all may pick worse models for a role's needs.
- − Cost is no longer a concern within the catalog (ADDENDUM-001 cost-posture override), but task-fit still matters; per-role assignment preserves the capability-tuning intent.

Rejected: per-role assignment encodes the Founder's quality choices durably.

### Option E — Direct provider SDKs (no routing layer)

How it works: each runtime imports the Fireworks SDK directly (and OpenAI/Anthropic SDKs if the catalog grows).

Trade-offs:

- + One less hop.
- + Provider-specific features available natively.
- − Provider-API-shape changes require code changes in five runtimes.
- − Per-call rate-limit and retry logic must be implemented per runtime.
- − Region failover must be implemented per runtime.
- − Catalog identifier abstraction is lost; replacing `accounts/fireworks/models/deepseek-v4-pro` with a successor means edits everywhere.
- − Explicitly forbidden by ADDENDUM-001 routing-layer mandate (Option B): no specialist runtime imports a Fireworks SDK or hits `api.fireworks.ai` directly.

Rejected: routing layer's benefits exceed its cost; ADDENDUM-001 mandates the indirection.

### Option F — OmniRoute only (no OpenRouter backup)

How it works: only OmniRoute is the routing layer. If OmniRoute is down, the system is down.

Trade-offs:

- + Simpler.
- − Single point of failure.
- − OmniRoute's outage history is short; assuming low rate is reasonable but not zero.
- − If OmniRoute drops Fireworks support upstream, the entire catalog is unreachable; OpenRouter as backup gives the system a chance to keep running on a degraded subset (ADR-011 enumerates the OpenRouter-side validation cadence).

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

- The catalog (`MODEL-CATALOG.md` v0.1.1) is the durable record of Founder approval. Changes to that document escalate via `ESCALATION-POLICY.md` v0.1.1 § 9.
- Specialist runtimes' `agent.model` and `agent.fallback_models` are populated from the catalog by the install script (TKT-021). The model identifier strings passed verbatim into Hermes config are the OmniRoute Fireworks-native paths (`accounts/fireworks/models/<slug>`).
- TKT-026 implements an enforcement helper that the install script invokes to verify each runtime's `agent.model` matches the catalog at startup AND that OmniRoute resolves each catalog identifier with a 1-token completion against `http://127.0.0.1:<omniroute_port>/v1/chat/completions`; either mismatch fails the verify check.
- Adding a new model requires editing the catalog, opening a PR, RV-SPEC, Founder approval. Rolling out is then a config-only change applied by re-running the install script.
- Routing-layer outage handling: OmniRoute unreachable → OpenRouter takes over (ADR-011 enumerates the failover criteria and the `OPENROUTER_FALLBACK_OK_FOR_FIREWORKS_MODELS` precondition). Both unreachable raises an escalation; `paid:llm_provider_outside_catalog` does NOT fire because the destination is in catalog; instead the `attempt_count` exhausts and the work-item failure path fires.
- The `dev-assist-escalation-policy` plugin does NOT consume any auxiliary-classifier entry from the catalog. The deterministic classifier in `ESCALATION-POLICY.md` v0.1.1 § 5 has no LLM dependency; the optional advisory-narrative call in § 5.5 reuses the runtime's catalog main model.
- ADDENDUM-001 cost-posture override applies: per-token cost optimization within the catalog is waived in v0.1; the only cost gate is the deterministic rule `paid:llm_provider_outside_catalog`. Empirical cost-monitoring lives in `OBSERVABILITY-CONTRACT.md` (PR-E).

## Cross-References

- `PRD-001.md` v0.2.1 § 13.1 (autonomy + escalation)
- `ARCH-001.md` v0.3.0 § 16
- `MODEL-CATALOG.md` v0.1.1 (enumerated catalog with real OmniRoute Fireworks paths)
- `ESCALATION-POLICY.md` v0.1.1 § 4.6 (`paid:llm_provider_outside_catalog`), § 5 (deterministic concept-deviation classifier), § 9 (tuning)
- `MULTI-HERMES-CONTRACT.md` § 4 (per-runtime config), § 9.2 (fallback chain on outage)
- `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 5.4, § 6.7
- `docs/orchestration/SESSION-STATE.md` § Current Tooling Decisions (Founder approval timestamp)
- ADDENDUM-001 (Founder, 2026-05-06; routing-layer Option B, cost-posture override, Fireworks identifier set)
- ADR-008 v0.1.1 (escalation classifier — deterministic, no auxiliary classifier model)
- ADR-011 (routing layer — OmniRoute primary with Fireworks backend, OpenRouter backup; lands in PR-E)
- RV-SPEC-012 F2 (the review finding that motivated v0.1.1 of this ADR)
- External: OmniRoute issue [#265](https://github.com/diegosouzapw/OmniRoute/issues/265) (Fireworks-as-backend verification, 2026-03-10)
- Implementation: TKT-026 (catalog enforcement helper)
