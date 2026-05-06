---
id: TKT-NEW-to-rationale-doctrine-collision
version: 0.1.0
status: backlog
source: Founder model-assignment update 2026-05-05
created: 2026-05-05
---

# TKT-NEW-to-rationale-doctrine-collision: Architect refresh of TO + SO uncorrelation rationale after 2026-05-05 fallback assignments

## Context

On 2026-05-05 the Founder set the following dev-time pipeline model assignments for `developer-assistant`:

| Role | Main | Fallback |
|---|---|---|
| Strategic Orchestrator | GPT-5.5 high | DeepSeek V4 Pro via opencode + OmniRoute |
| Ticket Orchestrator | GPT-5.5 high | GLM 5.1 via opencode + OmniRoute |
| Executor | DeepSeek V4 Pro | GLM 5.1 (Codex GPT-5.5 as specialist) |
| Reviewer | Kimi K2.6 | Qwen 3.6 Plus via opencode + OmniRoute |

These assignments were applied as clerical model-line edits in:

- `AGENTS.md` Roles table.
- `CONTRIBUTING.md` Roles table + supporting paragraph.
- `docs/meta/strategic-orchestrator.md` § 1 Identity & role + § 2 Project context + § 5 Roles & write zones inline table + § Delegating to Ticket Orchestrator.
- `docs/prompts/ticket-orchestrator.md` § Mission bullet 5 + 6 + § Project context + § Environment Note + § Responsibilities bullet 2.
- `docs/prompts/executor.md` § Environment Note.
- `docs/prompts/reviewer.md` § Environment Note.
- `docs/orchestration/SESSION-STATE.md` § Current Tooling Decisions.

The clerical PR did NOT rewrite the substantive *Why GPT-5.5 thinking (uncorrelated reasoning)* rationale section in `docs/prompts/ticket-orchestrator.md` because that section is doctrine-scope (Architect-owned), not a one-line model swap. Instead the clerical PR added a `<!-- DOCTRINE-COLLISION (2026-05-05) -->` HTML comment marker above that rationale section.

## The collision

The `Why GPT-5.5 thinking (uncorrelated reasoning)` rationale section argues:

> The Reviewer (Kimi K2.6), default Executor (GLM 5.1), and PR-Agent (DeepSeek V4 Pro) are separate model/runtime roles. The TO role's primary job at hand-back time is the **first cross-reviewer audit pass** ... Choosing GPT-5.5 for TO keeps the audit independent from Kimi, GLM, and the PR-Agent model.

The Founder's 2026-05-05 fallback assignments contradict this argument in two ways:

1. **TO + GLM-5.1 fallback × Executor + GLM-5.1 fallback.** When both the TO primary (GPT-5.5 high) and Executor primary (DeepSeek V4 Pro) fall over to GLM 5.1, the TO would be auditing same-family Executor output — exactly the rubber-stamp risk the rationale was written to avoid.
2. **SO + DeepSeek V4 Pro fallback × Executor + DeepSeek V4 Pro main.** When the SO primary (GPT-5.5 high) falls over to DeepSeek V4 Pro, the SO ratification audit pass-2 would be auditing same-family Executor output. The same correlation problem applies; the SO ratification step is the second of the two-phase audit (TO pass-1 + SO pass-2), so loss of independence at the SO layer is even more load-bearing than at the TO layer.

## Why this is not a TKT yet

The fallback paths are by definition rare. As of 2026-05-05, neither the TO nor the SO has run on a fallback model in any closed cycle. The collision is real but its operational impact has not yet manifested. Architect should refresh the rationale before the first time either fallback is actually invoked, OR the Founder can choose different uncorrelated fallbacks.

## What Architect must produce

A revised `Why GPT-5.5 thinking (uncorrelated reasoning)` rationale block in `docs/prompts/ticket-orchestrator.md` that is internally consistent with the Founder-set fallback choices. Three resolution paths:

**(a) Defend the new fallbacks.** Argue fallback frequency is low enough that correlation cost is bounded, and that the load-bearing Reviewer (Kimi K2.6 → Qwen 3.6 Plus) remains an independent reasoner per audit even if SO+Executor both run on DeepSeek V4 Pro or TO+Executor both run on GLM 5.1. This requires updating the `docs/meta/strategic-orchestrator.md` § Identity & role paragraph that currently says fallback is "a temporary session, not a doctrine reset" — that framing is consistent with (a) and would NOT need to change.

**(b) Propose different uncorrelated fallbacks.** For example: SO fallback = Claude Opus 4.7 thinking (different family from GPT-5.5 / DeepSeek / GLM / Kimi / Qwen). TO fallback = Qwen 3.6 Plus (same as Reviewer fallback, but Reviewer would not be active at the TO audit phase — TO audits Reviewer output, so a Qwen-3.6-Plus TO auditing a Kimi-K2.6 Reviewer output is uncorrelated; and a Qwen-3.6-Plus TO auditing a Qwen-3.6-Plus Reviewer output is correlated, requiring a tertiary fallback). Founder ratifies the change in a follow-up clerical PR.

**(c) Argue fallbacks should not exist at all.** If GPT-5.5 high on opencode is unavailable, TO and SO are paused and the work is held for direct Founder + supervisory handling rather than dropping into a correlated fallback. This is the strictest interpretation of the original rationale and matches how the production pipeline already handles Architect / Reviewer outages (manual intervention, not silent fallback).

The Architect refresh must also update the parallel mention in `docs/meta/strategic-orchestrator.md` § 1 Identity & role (currently says "DeepSeek V4 Pro via opencode + OmniRoute" as the SO fallback) and `docs/orchestration/SESSION-STATE.md` § Current Tooling Decisions if the resolution conclusion changes either fallback assignment.

## Acceptance criteria for the eventual TKT

- `docs/prompts/ticket-orchestrator.md` § *Why GPT-5.5 thinking* rationale block is internally consistent with the chosen fallback model assignments.
- The `<!-- DOCTRINE-COLLISION (2026-05-05) -->` HTML comment marker is removed once the rationale is internally consistent.
- `docs/meta/strategic-orchestrator.md` § 1 Identity & role reads coherently with the rewritten rationale.
- `docs/orchestration/SESSION-STATE.md` § Current Tooling Decisions reflects the final fallback choices.
- A new ADR is filed if the conclusion is (b) or (c) above (the model / fallback policy itself is being changed in light of the doctrine review).

## Reviewer

Kimi K2.6 RV-SPEC review on the rewritten rationale, with explicit pushback if the rewrite is not internally consistent.

## Notes

- This entry mirrors the `BACKLOG-012 / TKT-NEW-architect-refresh-to-rationale-after-deepseek-fallback` entry in the sister repo `OpenClown-bot/openclown-assistant` (see that repo's `docs/backlog/role-doctrine-followups.md`). The two entries are intentionally separated by repo because they describe different rationale collisions: openclown-assistant introduced DeepSeek V4 Pro as TO fallback (collision with the openclown-assistant rationale); developer-assistant introduced GLM 5.1 as TO fallback + DeepSeek V4 Pro as SO fallback (collisions with the developer-assistant rationale).
