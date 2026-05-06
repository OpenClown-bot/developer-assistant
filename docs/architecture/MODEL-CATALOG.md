---
id: MODEL-CATALOG
version: 0.1.0
status: draft
---

# Model Catalog

## 1. Purpose

This document is the Founder-pre-approved catalog of LLM models the assistant may use in v0.1. It satisfies `PRD-001.md` § 13.1 (autonomy default) and `ARCH-001.md` v0.3.0 § 16 by carving out a clear "within-catalog model picks proceed without escalation; catalog changes escalate" boundary.

The catalog is durable: every entry has been seen and approved by the Founder. Changing the catalog is a Founder decision per `ESCALATION-POLICY.md` § 4.6 (`paid:llm_provider_outside_catalog`) and § 9.

## 2. Scope

This catalog covers:

- The **main model** every specialist runtime uses for ordinary work.
- The ordered **fallback chain** every specialist runtime uses when its main model is unreachable, rate-limited, or returns an error.
- The **auxiliary classifier model** used by the `dev-assist-escalation-policy` plugin (`ESCALATION-POLICY.md` § 5.2).

Out of scope for this catalog:

- Image-generation, vision, or speech models. v0.1 runtimes do not load `vision`, `image_gen`, or speech skills.
- Embedding models. v0.1 does not run a vector store; embeddings are deferred to "Future Possibilities" (`ARCH-001.md` § 21).
- Local / on-VPS LLM hosting. v0.1 reaches all models through OmniRoute (primary) and OpenRouter (backup), not through local llama.cpp / Ollama.

## 3. Source Of Truth

The Founder pre-approved a role-model assignment on 2026-05-05; this is the assignment recorded in `docs/orchestration/SESSION-STATE.md` § Current Tooling Decisions. v0.1 adopts that assignment and adds the auxiliary classifier entry needed by `ESCALATION-POLICY.md`.

If `SESSION-STATE.md` and this catalog disagree, **this catalog is authoritative for runtime behavior** and `SESSION-STATE.md` should be updated to match. Both files reference each other to make divergence visible.

## 4. Catalog (v0.1)

### 4.1 Per-role assignment

| Role | Main model | Fallback 1 | Fallback 2 | Fallback 3 |
| --- | --- | --- | --- | --- |
| Orchestrator | `gpt-5.1` | `claude-sonnet-4.5` | `gemini-2.5-pro` | `deepseek-v3.5` |
| Business Planner | `claude-sonnet-4.5` | `gpt-5.1` | `gemini-2.5-pro` | `deepseek-v3.5` |
| Architect | `claude-opus-4.5` | `gpt-5.1` | `claude-sonnet-4.5` | `deepseek-v3.5` |
| Executor | `claude-sonnet-4.5` | `gpt-5.1` | `gemini-2.5-pro` | `deepseek-v3.5` |
| Reviewer | `claude-sonnet-4.5` | `gpt-5.1` | `claude-opus-4.5` | `gemini-2.5-pro` |

The fallback chain is consumed in order by Hermes' built-in retry plus the per-runtime `agent.fallback_models` config. When a model in the chain fails (network error, rate limit, content filter, schema-invalid response), the runtime advances to the next entry. If the entire chain is exhausted, the work item attempt fails per `MULTI-HERMES-CONTRACT.md` § 9.2.

### 4.2 Auxiliary classifier (escalation policy)

| Use | Model |
| --- | --- |
| Default classifier | `gpt-5.1-mini` |
| Permitted alternative | `claude-haiku-4.5` |
| Permitted alternative | `gemini-2.5-flash` |

Per `ESCALATION-POLICY.md` § 5.3 the classifier has a hard latency budget of 10 seconds and a hard per-classification cost ceiling of <0.001 USD. The default is chosen to comfortably meet both. Alternatives must also meet both; the catalog enumerates only models that have been validated.

The classifier model must be different from the runtime's main model where possible to keep the classification audit independent of the model that produced the candidate action. v0.1 enforces this with a config-level check in `dev-assist-escalation-policy`'s bootstrap.

### 4.3 Why these entries

- `gpt-5.1` (OpenAI) — strong general-purpose reasoning; broad tool-call support; default Orchestrator pick because Telegram classification benefits from breadth.
- `claude-sonnet-4.5` (Anthropic) — strong code generation and structured output; default Business Planner / Executor / Reviewer pick.
- `claude-opus-4.5` (Anthropic) — Architect's primary because architecture writing benefits from longer reasoning and more careful trade-off analysis; cost is higher, used only by Architect.
- `gemini-2.5-pro` (Google) — pluralism in fallback; large context window if the conversation grows long.
- `deepseek-v3.5` — last-resort fallback; cost-efficient; used only when all three primary providers are unavailable simultaneously.
- `gpt-5.1-mini` / `claude-haiku-4.5` / `gemini-2.5-flash` — small/fast tier; used only as auxiliary classifiers, not for production reasoning, to keep escalation-policy cost negligible.

The names above are placeholder identifiers for the model class; the exact OmniRoute / OpenRouter slug for each is resolved at runtime by the routing layer (§ 5).

## 5. Routing Layer

All model calls go through OmniRoute (primary) or OpenRouter (backup). Specialist runtimes never call provider SDKs directly. Rationale:

- Decouples runtime config from provider API shape changes.
- Centralizes per-call rate-limit and retry behavior.
- Lets the Founder swap providers under a single contract without touching specialist runtimes.
- Keeps the v0.1 budget envelope inside the already-approved LLM API spend.

OmniRoute is the default. OpenRouter is the backup; the routing layer falls back to it if OmniRoute is unreachable. Both are configured via env vars in `SELF-DEPLOY.env`:

- `OMNIROUTE_API_KEY` — required.
- `OPENROUTER_API_KEY` — required (backup).

If neither is reachable, runtimes fail fast per `MULTI-HERMES-CONTRACT.md` § 9.2.

## 6. Within-Catalog Picks Are Autonomous

Per `ESCALATION-POLICY.md` § 4.6 (`paid:llm_provider_outside_catalog`), a runtime may use any model listed in this catalog without escalating. Specifically:

- A runtime may switch from its main model to its declared fallback during a single conversation (Hermes' retry chain does this automatically).
- A runtime may use the auxiliary classifier model under any condition the escalation-policy plugin requires.
- A runtime may NOT call a model not in this catalog. Doing so triggers `paid:llm_provider_outside_catalog` and escalates.

## 7. Catalog Changes Escalate

Changing the catalog is a Founder-approved decision. The deterministic rule `paid:llm_provider_outside_catalog` catches calls that bypass the catalog at runtime; an *intentional* catalog change is performed by editing this file, which:

1. The Architect proposes via PR.
2. RV-SPEC reviews.
3. Founder approves (the same loop as any architecture artifact).

The PR's title MUST include `MODEL-CATALOG` so it is visible to the Founder as a budget-touching change.

Specifically the following changes escalate:

- Adding a new model entry.
- Removing an existing entry.
- Changing a role's main model.
- Reordering a role's fallback chain.
- Changing the auxiliary classifier set.
- Changing the routing layer (e.g., adding a third routing provider, removing OmniRoute).

The following do NOT escalate (within-catalog operational behavior):

- A runtime advancing through its declared fallback chain because of an upstream outage.
- The auxiliary classifier choosing a different permitted alternative because the default is unreachable (within the listed alternatives in § 4.2).
- Per-call retry, rate-limit handling, content-filter handling.

## 8. Cost Posture

v0.1 does not commit to a specific monthly LLM spend. The Founder pre-approved the catalog above with the expectation that:

- Routine operation (Orchestrator + Business Planner + Architect + Executor + Reviewer producing one PRD + one architecture pass + one ticket per work cycle) fits inside the already-approved LLM API budget.
- The auxiliary classifier's contribution to spend is bounded by `ESCALATION-POLICY.md` § 5.3 (<0.001 USD per classification, expected <100 classifications per active hour, expected ~1-2 active hours per day during the trial).
- Architect runs use `claude-opus-4.5` selectively; the model is more expensive per token but the runtime is invoked rarely and produces high-leverage output.

If empirical cost during the trial diverges meaningfully from this expectation, the Architect adds a cost note to this file's next version and the Founder decides whether to adjust the catalog.

## 9. Known-Caveat List

- **Model identifier drift**: provider model names change (e.g., from `gpt-5.1` → `gpt-5.1-2026-05`). The routing layer (OmniRoute / OpenRouter) resolves the catalog name to the current provider slug. If a slug is deprecated by the provider and the routing layer cannot resolve it, the runtime advances to the next fallback and the verify script's connectivity check fails on the next run, surfacing the issue.
- **Provider regional availability**: some providers may be unavailable in the Founder's VPS region. The routing layer handles this by attempting alternative regions or falling back; if all regions fail for a provider, that fallback chain entry is skipped on subsequent attempts within the same minute.
- **Content filtering**: a model may refuse to produce a particular output (e.g., security-sensitive code). The runtime advances to the next fallback. If the entire chain refuses, the work item attempt fails and an escalation is raised.

## 10. Catalog Refresh Cadence

Per `ARCH-001.md` § 22 item 6 the default cadence is "refresh on Founder request." The Architect does NOT autonomously refresh the catalog when a new provider model is announced; refreshes are Founder-approved.

If the trial reveals that a model in the catalog has been deprecated by its provider in a way the routing layer cannot recover from, the Architect proposes a refresh PR. The PR is reviewed by RV-SPEC, then approved by the Founder.

## 11. Cross-References

- `PRD-001.md` v0.2.1 § 13.1 (autonomy default)
- `ARCH-001.md` v0.3.0 § 16
- `ESCALATION-POLICY.md` § 4.6 (`paid:llm_provider_outside_catalog`), § 5 (LLM classifier), § 9 (tuning process)
- `docs/orchestration/SESSION-STATE.md` § Current Tooling Decisions (Founder approval timestamp)
- `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 5.4, § 6.7
- `docs/architecture/adr/ADR-009-model-assignment-and-fallback.md`
- Implementation: TKT-026 (model-catalog enforcement helper)
