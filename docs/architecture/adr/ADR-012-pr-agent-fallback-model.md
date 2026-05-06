---
id: ADR-012
version: 0.1.0
status: accepted
---

# ADR-012: PR-Agent Fallback Model — Fireworks-hosted Qwen3.6-Plus

## Status

Accepted. This is a straightforward config fix; no Founder approval gate required.

## Context

PR-Agent (Qodo PR-Agent, running as GitHub Action) uses DeepSeek V4 Pro as its primary review model, routed through OmniRoute → Fireworks per `ADR-011`. When DeepSeek V4 Pro is unavailable (API errors, timeouts, rate limits), PR-Agent falls back to the model listed in `fallback_models` in `.pr_agent.toml`.

The current effective fallback is `o4-mini` (OpenAI o4-mini), which comes from PR-Agent's built-in default in `pr_processing.py:retry_with_fallback_models`. This default is wrong for two reasons:

1. **Architecture violation**: `ADR-011` (routing layer) mandates all LLM calls go through OmniRoute → Fireworks. `o4-mini` routes directly to OpenAI, bypassing our routing layer and observability stack.
2. **Operational mismatch**: `o4-mini` is a reasoning model with high latency (30–90 s typical). When DeepSeek is down, we need a *fast* fallback, not another slow one. PR-Agent's `ai_timeout` is 180 s — if both primary and fallback are slow, the run dies.

DeepSeek V4 Pro has been unreliable recently (Fireworks API errors, timeouts). The fallback must actually work, be quick, and stay within the Fireworks-only boundary.

## Decision

Set PR-Agent's `fallback_models` to a single Fireworks-hosted model: **Qwen3.6-Plus** (`fireworks/qwen3p6-plus`), formatted for LiteLLM as:

```
openai/fireworks/accounts/fireworks/models/qwen3p6-plus
```

This is added to `.pr_agent.toml` under `[config]` as a one-entry `fallback_models` list, which overrides PR-Agent's built-in `o4-mini` default.

### Why Qwen3.6-Plus

- **Fireworks-hosted**: Confirmed in catalog. Routes through OmniRoute → Fireworks, satisfying `ADR-011`.
- **Code-optimized**: Arena Code score 1465 (rank 13 of 73). Strong enough for PR review, description, and code suggestions.
- **Fast**: Non-thinking, reasonably-sized model. Typical latency is well under the 180 s timeout, leaving headroom after a primary failure.
- **Cost-efficient**: $0.33/$1.95 per 1M tokens (input/output). The cheapest *strong* option in the catalog; fallback is infrequent but cheap when it fires.
- **Already in catalog**: Assigned as Business Planner main in `MODEL-CATALOG.md` v0.2.0. No catalog expansion needed.

We intentionally do **not** use a two-deep fallback chain. PR-Agent's own retry logic handles transient errors; if the primary (DeepSeek V4 Pro) fails and the single fallback (Qwen3.6-Plus) also fails, the issue is almost certainly an OmniRoute/Fireworks-wide outage, and a second fallback would likely fail too while burning extra timeout budget.

## Considered Options

### Option A — Qwen3.6-Plus (CHOSEN)

Trade-offs:
- + Already in catalog (`MODEL-CATALOG.md` v0.2.0 § 4.1). No catalog change, no Founder approval needed.
- + Strong code score (1465) with low price ($0.33/$1.95). Best quality-per-dollar among in-catalog options.
- + Non-thinking, fast enough for a 180 s timeout window even after primary latency.
- + 1M context window is overkill for PR-Agent diffs (rarely >30K) but harmless.
- − Slightly more expensive than MiniMax-M2.7 or DeepSeek-V3.2 on output. Mitigated: fallback is infrequent; the quality gap to those cheaper models is larger than the cost gap.

### Option B — GLM-5.1

Trade-offs:
- + Highest code score in catalog (1532). Better code quality than Qwen3.6-Plus.
- + Already in catalog as Executor main.
- − Most expensive option ($1.40/$4.40). For a fallback that may fire dozens of times during a Fireworks incident, cost adds up.
- − Larger model = slightly higher latency than Qwen3.6-Plus. When primary already failed, speed matters more than marginal quality.

Rejected: excellent model, but overkill for a fallback slot where speed and cost dominate.

### Option C — MiniMax-M2.7

Trade-offs:
- + Cheapest in catalog ($0.30/$1.20). Fastest due to smallest size.
- + Already in catalog as Orchestrator main.
- − Lowest code score in catalog (1408). A 200-point drop from DeepSeek V4 Pro is meaningful for code review quality.
- − PR-Agent's `pr_reviewer` is load-bearing for security and scope-discipline checks; a weak fallback increases miss risk.

Rejected: too large a quality sacrifice for the small cost/latency win.

### Option D — DeepSeek-V3.2

Trade-offs:
- + Cheapest non-thinking DeepSeek ($0.25/$0.38). Very fast.
- + Same provider family as primary — may share failure modes (Fireworks-wide DeepSeek outage) but not guaranteed.
- − Not in catalog. Adding it requires catalog expansion, Founder approval, and install-script update per `ADR-009`.
- − Lowest code score among considered options (1332). Large quality drop.

Rejected: catalog expansion overhead + quality drop outweigh the marginal cost savings.

### Option E — Two-deep fallback chain (Qwen3.6-Plus → MiniMax-M2.7)

Trade-offs:
- + Adds a second safety net if the first fallback fails.
- − PR-Agent already retries transient errors internally. A second model call burns timeout budget (180 s total) for minimal gain when the root cause is likely a platform-wide outage.
- − Adds config complexity and makes PR-Agent runs less predictable.

Rejected: single fallback is simpler and sufficient. If Fireworks is down for both DeepSeek and Qwen, MiniMax will almost certainly fail too.

### Option F — Keep o4-mini (built-in default)

Trade-offs:
- + Zero config change.
- − Violates `ADR-011` (bypasses OmniRoute → Fireworks, goes direct to OpenAI).
- − Reasoning model = high latency, compounding timeout risk.
- − Not in catalog, not observed by OmniRoute `llm_calls` table.

Rejected outright: architecture violation + operational mismatch.

## Decision Criteria And Mapping

| Criterion | Option A (Qwen3.6-Plus, CHOSEN) | Option B (GLM-5.1) | Option C (MiniMax) | Option D (DeepSeek-V3.2) | Option E (two-deep) | Option F (o4-mini) |
| --- | --- | --- | --- | --- | --- | --- |
| Fireworks-only / ADR-011 | Yes | Yes | Yes | Yes | Yes | No |
| In catalog (no expansion) | Yes | Yes | Yes | No | Yes | N/A |
| Code score (Arena) | 1465 | 1532 | 1408 | 1332 | 1465/1408 | Unknown |
| Output price ($/M) | $1.95 | $4.40 | $1.20 | $0.38 | $1.95/$1.20 | Unknown |
| Non-thinking / fast | Yes | Yes | Yes | Yes | Yes | No (reasoning) |
| PR-Agent timeout safe | Yes | Yes | Yes | Yes | Marginal | No |
| Config simplicity | High | High | High | High | Medium | N/A |

Option A wins on the quality-price-speed trade-off while staying fully within catalog and architecture boundaries.

## Consequences

- `.pr_agent.toml` gains one line: `fallback_models = ["openai/fireworks/accounts/fireworks/models/qwen3p6-plus"]` under `[config]`.
- When DeepSeek V4 Pro is unreachable, PR-Agent falls back to Qwen3.6-Plus through the same OmniRoute → Fireworks path, preserving observability in the `llm_calls` table (`OBSERVABILITY-CONTRACT.md` FR-OBS-07).
- No catalog change, no install-script change, no workflow change. The only diff is `.pr_agent.toml`.
- If Qwen3.6-Plus also fails (rare — different model family, different Fireworks endpoint), PR-Agent's built-in retry will exhaust its attempts and the run will fail. This is acceptable: a platform-wide Fireworks outage should fail loudly rather than silently degrading review quality.
- Future catalog refreshes may swap the fallback if a better fast+cheap+strong Fireworks model enters the catalog; that would be a config-only change following this same ADR pattern.

## Cross-References

- `MODEL-CATALOG.md` v0.2.0 § 4.1 (Qwen3.6-Plus as Business Planner main)
- ADR-009 (catalog assignment rationale; in-catalog picks proceed autonomously)
- ADR-011 (routing layer — all calls through OmniRoute → Fireworks)
- `OBSERVABILITY-CONTRACT.md` FR-OBS-07 (`llm_calls` table records routing path)
- `.pr_agent.toml` (config patched by this ADR)
- `.github/workflows/pr_agent.yml` (workflow env vars unchanged; `OPENAI.API_BASE` already points to OmniRoute)
