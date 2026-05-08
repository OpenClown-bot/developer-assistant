---
id: MODEL-CATALOG
version: 0.3.0
status: draft
amendments: ADR-014 (live deployment corrections from TKT-032, 2026-05-08)
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

The Founder pre-approved a role-model assignment on 2026-05-05 (recorded in `docs/orchestration/SESSION-STATE.md` § Current Tooling Decisions). On 2026-05-06 the Founder issued ADDENDUM-001 (relayed via Business Planner) which (a) replaced the placeholder identifiers with five Fireworks-hosted models reachable through OmniRoute, (b) waived per-token cost optimization within the catalog, and (c) made the routing layer mandate explicit. This catalog adopts the ADDENDUM-001 set; the cost-posture rewrite that ADDENDUM-001 also mandates lands in v0.2.0 (PR-E).

Reconciliation between the 2026-05-05 seven-role list and the v0.1 five-runtime architecture (`MULTI-HERMES-CONTRACT.md`):

- **Strategic Orchestrator** and **Ticket Orchestrator** in the 2026-05-05 list are two operational modes of the same `orchestrator` Hermes runtime; the catalog assigns one main model to that runtime.
- **PR-Agent** in the 2026-05-05 list is a CI workflow (`.github/workflows/pr_agent.yml`), not a Hermes runtime; its model is configured separately in the workflow file and is OUT OF SCOPE for this catalog. The workflow already pins `openai/fireworks/accounts/fireworks/models/deepseek-v4-pro` (litellm format), which is the same Fireworks model identifier this catalog uses for the `architect` runtime, so the two surfaces are consistent.

If `SESSION-STATE.md` and this catalog disagree, **this catalog is authoritative for runtime behavior** and `SESSION-STATE.md` should be updated to match. Both files reference each other to make divergence visible.

## 4. Catalog (v0.1)

### 4.1 Per-role assignment

All identifiers are real OmniRoute model paths in the Fireworks-native form `accounts/fireworks/models/<slug>`. OmniRoute auto-resolves these paths to the Fireworks backend per its provider registry (OmniRoute issue [#265](https://github.com/diegosouzapw/OmniRoute/issues/265), closed 2026-03-10, maintainer confirmed: "send the Fireworks path as model ID and OmniRoute auto-resolves it"). Specialist runtimes pass these strings as `model.default` in their per-runtime Hermes `config.yaml` under the `model:` section (ADR-014 Correction 2). The legacy `agent.model` / `agent.fallback_models` keys are not used. The fallback chain is capability-only — ordered by suitability for the role's task, NOT by per-token price (per ADDENDUM-001 cost-posture override).

**Operational note (ADR-014 Correction 4):** During the TKT-032 live deployment, the short-form model ID `deepseek-v3p2` was verified to resolve on the deployed OmniRoute instance, while the `accounts/fireworks/models/deepseek-v4-pro` format was not confirmed. The deployed OmniRoute may use a different alias convention than the Fireworks-native slug format. Until a systematic verification against the deployed OmniRoute's `/v1/models` endpoint confirms that the `accounts/fireworks/models/<slug>` format works, the install script uses the short-form identifiers that are known to resolve. The catalog below retains the Fireworks-native format as the canonical identifier; operational deployment may substitute the short-form alias as documented in the install script's `MODEL_IDENTIFIERS` configuration.

| Role | Main model | Fallback 1 | Fallback 2 | Fallback 3 |
| --- | --- | --- | --- | --- |
| Orchestrator | `accounts/fireworks/models/minimax-m2p7` | `accounts/fireworks/models/kimi-k2p6` | `accounts/fireworks/models/qwen3p6-plus` | `accounts/fireworks/models/deepseek-v4-pro` |
| Business Planner | `accounts/fireworks/models/qwen3p6-plus` | `accounts/fireworks/models/kimi-k2p6` | `accounts/fireworks/models/minimax-m2p7` | `accounts/fireworks/models/deepseek-v4-pro` |
| Architect | `accounts/fireworks/models/deepseek-v4-pro` | `accounts/fireworks/models/kimi-k2p6` | `accounts/fireworks/models/glm-5p1` | `accounts/fireworks/models/qwen3p6-plus` |
| Executor | `accounts/fireworks/models/glm-5p1` | `accounts/fireworks/models/deepseek-v4-pro` | `accounts/fireworks/models/kimi-k2p6` | `accounts/fireworks/models/qwen3p6-plus` |
| Reviewer | `accounts/fireworks/models/kimi-k2p6` | `accounts/fireworks/models/deepseek-v4-pro` | `accounts/fireworks/models/glm-5p1` | `accounts/fireworks/models/qwen3p6-plus` |

The fallback chain is consumed in order by Hermes' built-in retry. When a model in the chain fails (network error, rate limit, content filter, schema-invalid response), the runtime advances to the next entry. If the entire chain is exhausted, the work item attempt fails per `MULTI-HERMES-CONTRACT.md` § 9.2. Fallback models are configured under `model.fallback_models` in the `model:` section of Hermes `config.yaml` (ADR-014 Correction 2).

### 4.2 No separate auxiliary classifier model in v0.1

The v0.1 escalation policy is **deterministic** (`ESCALATION-POLICY.md` v0.1.1 § 5 + `PROJECT-CONCEPT.md` § 2): the concept-deviation decision is a pure function of the candidate action and the structured concept anchor, with no LLM call in the decision path. There is therefore no "auxiliary classifier model" entry to enumerate here.

`dev-assist-escalation-policy` is permitted to invoke the runtime's own main model from § 4.1 to generate a *human-readable narrative* for the Founder (e.g., a Russian-language summary of why a specific escalation row was raised). That narrative is advisory text on the escalation surface, NOT an input to the escalate/proceed decision. Cost and latency for this advisory call are bounded by `ESCALATION-POLICY.md` § 5.3 (≤ 10 s, ≤ 0.001 USD per call), and the model used is the runtime's catalog main, so no new catalog entry is needed.

### 4.3 Why these entries

- `accounts/fireworks/models/deepseek-v4-pro` — DeepSeek-V4-Pro, 1.05 M context, 1.6 T MoE, function-calling. Architect main: deepest reasoning depth in the catalog; long context for cross-artifact synthesis. Universal fallback (last-resort) for every role because it is the strongest single model.
- `accounts/fireworks/models/kimi-k2p6` — Kimi K2.6, 262 K context, 1 T MoE, function-calling, vision. Reviewer main: the Reviewer reads large diffs and benefits from the longest non-DeepSeek context window; strong code-review aptitude per public lmarena ratings (2026-05-01 snapshot).
- `accounts/fireworks/models/minimax-m2p7` — MiniMax M2.7, 196 K context, 228.7 B MoE, function-calling. Orchestrator main: dispatch + classification benefit from breadth and low latency; the Orchestrator does not need the deepest reasoning tier for routine inbound-message routing.
- `accounts/fireworks/models/glm-5p1` — GLM 5.1, 202 K context, 754 B MoE, function-calling. Executor main: top-3 on Code Arena (AIWire 2026-04-12); strong code generation and structured edit output.
- `accounts/fireworks/models/qwen3p6-plus` — Qwen 3.6 Plus, 131 K context, MoE, function-calling, vision. Business Planner main: structured PRD-style writing aptitude; lmarena top-tier on text + code arenas (2026-05-01 snapshot).

All five identifiers are real OmniRoute paths verified to resolve against the Fireworks backend (OmniRoute v3.7.x provider registry, issue #265). They are NOT placeholders. The TKT-026 model-catalog enforcement helper exercises each identifier at install time by issuing a 1-token completion against `http://127.0.0.1:<omniroute_port>/v1/chat/completions`; failure to resolve is a fatal verify-script error per `SELF-DEPLOYMENT-CONTRACT.md` § 8.

## 5. Routing Layer

All model calls go through OmniRoute (primary) with Fireworks as its configured backend. Specialist runtimes never import a Fireworks SDK and never call `api.fireworks.ai` directly. OpenRouter is configured as the backup routing layer for use when OmniRoute itself is unreachable. Rationale (`ADR-011`):

- Decouples runtime config from provider API shape changes.
- Centralizes per-call rate-limit and retry behavior.
- Lets the Founder swap backends under a single contract without touching specialist runtimes.
- Eliminates a Fireworks-specific SDK dependency in five places (one Hermes runtime per role).

**Verification gate** (binding precondition for v0.1 install): OmniRoute MUST resolve all five identifiers in § 4.1 to the Fireworks backend. Verified 2026-05-06 via OmniRoute issue #265 (closed). The TKT-026 install verify script re-runs this gate at every install/upgrade. On failure, the installer escalates with `paid:third_party_external_service_not_yet_supported` (`ESCALATION-POLICY.md` § 4.6) — there is NO silent fallback to direct-Fireworks SDK.

### 5.1 Endpoints and ports

**Amended per ADR-014 Correction 1 (2026-05-08):** OmniRoute is currently deployed on a remote host. The install script renders the OmniRoute base URL into each runtime's `config.yaml` via the `OMNIROUTE_BASE_URL` env var. The current deployment uses `https://omniroute.infinitycore.space:8443/v1`. The `model.base_url` field in the `model:` config section (not `agent.api_base`) is set to this value by the install script's `render_runtime_configs()` function (ADR-014 Corrections 2 and 8). When OmniRoute is deployed locally in the future, `OMNIROUTE_BASE_URL` defaults to `http://127.0.0.1:20128` per `SELF-DEPLOYMENT-CONTRACT.md` § 5.3.

### 5.2 Credentials

**Amended per ADR-014 Correction 3 (2026-05-08):** Configured via env vars in `SELF-DEPLOY.env`:

- `FIREWORKS_API_KEY` — required. Used by specialist runtimes as the `model.api_key` value in Hermes `config.yaml` to authenticate to OmniRoute. When OmniRoute is remote (current deployment), this is the sole auth key. When OmniRoute is local (future option), this key is configured into OmniRoute's state DB as the upstream Fireworks credential, and a separate `OMNIROUTE_API_KEY` may be used for runtime-to-OmniRoute auth.
- `OMNIROUTE_BASE_URL` — required. The full base URL of the OmniRoute endpoint (e.g., `https://omniroute.infinitycore.space:8443/v1`). Set as `model.base_url` in Hermes config.
- `OPENROUTER_API_KEY` — required (backup routing layer, activated when OmniRoute is unreachable).

If neither OmniRoute nor OpenRouter is reachable, runtimes fail fast per `MULTI-HERMES-CONTRACT.md` § 9.2.

## 6. Within-Catalog Picks Are Autonomous

Per `ESCALATION-POLICY.md` § 4.6 (`paid:llm_provider_outside_catalog`), a runtime may use any model listed in this catalog without escalating. Specifically:

- A runtime may switch from its main model to its declared fallback during a single conversation (Hermes' retry chain does this automatically).
- A runtime may invoke its catalog main model from `dev-assist-escalation-policy` to generate Russian-language narrative for the escalation surface (per § 4.2; advisory text only, never used as input to the deterministic decision).
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
- Changing the routing layer (e.g., adding a third routing provider, removing OmniRoute, switching the Fireworks backend to a different provider).

The following do NOT escalate (within-catalog operational behavior):

- A runtime advancing through its declared fallback chain because of an upstream outage.
- The auxiliary classifier choosing a different permitted alternative because the default is unreachable (within the listed alternatives in § 4.2).
- Per-call retry, rate-limit handling, content-filter handling.

## 8. Cost Posture

The Founder has approved any spend within this catalog. Per-runtime / per-day USD ceilings are out of scope for v0.1.

Per ADDENDUM-001 (Founder, 2026-05-06): *"We are not saving on these models, so do not try to squeeze on token cost."* This wholesale supersedes the v0.1.0 catalog's "fits inside already-approved LLM API budget" framing and the "Architect adds a cost note if empirical spend diverges" clause. Specifically:

- **Within-catalog model selection**: pick each role's main model by capability fit alone. The fallback chain in § 4.1 is ordered by capability-degradation tolerance, not by cost ascent. A pricier-but-more-capable Fallback-N is preferred over a cheaper-but-less-capable Fallback-N.
- **No per-token internal optimization**: runtimes do not minimize prompt size beyond what hygiene requires (no aggressive context compression, no token-count gating that could trade quality for token savings).
- **No per-day / per-runtime spend cap**: there is no automatic budget circuit breaker. The deterministic escalation rule `paid:llm_provider_outside_catalog` (`ESCALATION-POLICY.md` § 4.6) is the only cost gate that escalates, and it only fires when a runtime tries to call a model that is NOT in this catalog at all.
- **Observability remains mandatory**: every LLM call writes a row to the `llm_calls` table per `OBSERVABILITY-CONTRACT.md` v0.1.1 FR-OBS-07; the daily Telegram digest reports per-runtime per-model spend (FR-OBS-05). Cost tracking is the v0.1 commitment; cost optimization is not.

The auxiliary classifier ceilings in `ESCALATION-POLICY.md` § 5.3 (≤ 10s latency, ≤ 0.001 USD per classification) remain in force. Those ceilings are about classifier independence and policy hygiene (not Founder savings), so the no-cost-optimization directive does not relax them.

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
- `ESCALATION-POLICY.md` v0.1.1 § 4.6 (`paid:llm_provider_outside_catalog`), § 5 (deterministic concept-deviation classifier), § 9 (tuning process)
- `PROJECT-CONCEPT.md` v0.1.0 § 2 (concept anchor block consumed by the deterministic classifier)
- `docs/orchestration/SESSION-STATE.md` § Current Tooling Decisions (Founder approval timestamp)
- `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 5.4, § 6.7
- `docs/architecture/adr/ADR-009-model-assignment-and-fallback.md` v0.1.1 (model assignment + routing)
- `docs/architecture/adr/ADR-011-routing-layer.md` (OmniRoute primary with Fireworks backend; lands in PR-E)
- ADDENDUM-001 (Founder, 2026-05-06) — Fireworks model identifiers, cost-posture override, routing-layer mandate (Option B). The cost-posture rewrite this addendum requires lands as v0.2.0 in PR-E.
- Implementation: TKT-026 (model-catalog enforcement helper)
- External: OmniRoute issue [#265](https://github.com/diegosouzapw/OmniRoute/issues/265) (Fireworks-as-backend verification, 2026-03-10)
