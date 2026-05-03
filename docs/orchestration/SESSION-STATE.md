---
id: SESSION-STATE
version: 0.1.0
status: active
updated: 2026-05-02
---

# Session State

## Project

- Name: `developer-assistant`
- Summary: AI developer assistant for orchestrating full software delivery projects.
- Repository state: GitHub repository is active; docs-as-code scaffold, approved architecture baseline, PR-Agent, Docs CI, TKT-001 validator baseline, Hermes-aligned role prompts, PR/review templates, Hermes runtime integration contract, Hermes skill/plugin security allowlist, operational state store, Hermes credential-bearing capability source review, state-store hardening, generated-project VPS deployment contract, runtime ticket readiness pass, project-specific GitHub workflow capability, and Telegram founder interaction logic layer are merged to `main`.
- Artifact language: mixed. Conversation in Russian; long-lived repo docs and prompts in English.

## Current Phase

TKT-001 through TKT-007, TKT-009, TKT-010, TKT-012, TKT-013, and TKT-014 are complete. Runtime readiness pass PR #29 is merged and reviewed by RV-SPEC-001. `TKT-008` and `TKT-011` remain draft.

## Process Variant

Lightweight PRD -> Architecture Specification -> Tickets -> PR implementation -> CI -> automated PR review -> Reviewer LLM -> user-approved merge.

## Current Active PRs

- None.

## Current Active Tickets

- `TKT-001`: done in PR #4.
- `TKT-002`: done; satisfied by existing Docs CI baseline.
- `TKT-003`: done in PR #8.
- `TKT-004`: done in PR #10.
- `TKT-005`: done in PR #13.
- `TKT-009`: done in PR #16.
- `TKT-007`: done in PR #18.
- `TKT-012`: done in PR #22; source-review gate for credential-bearing Hermes Telegram and GitHub capabilities.
- `TKT-013`: done in PR #23; state-store hardening follow-up from RV-CODE-010.
- `TKT-010`: done in PR #26; reviewed in PR #27.
- `TKT-006`: done in PR #35; reviewed in PR #36.
- `TKT-008`: draft; GitHub repository and PR integration. Can now be promoted by Architect because TKT-014 is complete.
- `TKT-011`: draft; first Telegram-to-PR orchestration trial.
- `TKT-014`: done in PR #32; reviewed in PR #33.

## Current Blockers

- GitHub repository was renamed from `OpenClown-bot/assistant-developer` to `OpenClown-bot/developer-assistant`.
- Local git remote `origin` points to `https://github.com/OpenClown-bot/developer-assistant.git`.
- Temporary GitHub PAT is configured in the current environment for this session.
- GitHub CLI `gh` is available and authenticated in the current SO environment, but future sessions must still verify `gh auth status`.

## Current Architectural Decisions

- `ARCH-001` version `0.2.0` is approved by the user as the v0.1 baseline.
- v0.1 is Telegram-first and Hermes-centered using a Hermes-first hybrid foundation.
- Repository docs-as-code governance remains the source of truth for PRD, architecture, ADRs, tickets, reviews, decisions, and handoff state.
- OpenClaw is deferred as a possible later gateway/control UI unless a Hermes blocker is documented.
- Deployment target: user-owned VPS.
- Operational state backend default: SQLite on VPS unless Hermes native persistence is proven sufficient.
- Security-sensitive data exists because the system may handle GitHub PATs, LLM API keys, repository access, and VPS credentials.
- Telegram interaction model: hybrid commands plus free-form classification.
- Lightweight web interface is deferred until Telegram works.
- Merge policy for v0.1: always ask founder after CI and Reviewer pass.
- Generated project VPS deployment contract: one-command `make deploy` or equivalent; final live execution requires founder approval.
- Hermes Telegram gateway source review passed with constraints for production `TELEGRAM_BOT_TOKEN` use.
- Hermes bundled GitHub credential-bearing skills reviewed in TKT-012 are not cleared for production `GITHUB_TOKEN` or `GH_TOKEN` use; use project-specific REST API plus `git` orchestration instead.
- Operational state store hardening is complete: SQLite foreign keys are enforced, project binding upserts preserve omitted optional fields, and WAL/single-thread guidance is documented.
- Runtime readiness pass: `TKT-006` now provides the Telegram founder interaction logic layer, and `TKT-014` provides the reviewed project-specific GitHub REST API plus constrained `git` workflow capability. `TKT-008` can move to an Architect readiness/promotion pass.

## Current Tooling Decisions

- Git host: GitHub.
- GitHub repository: `https://github.com/OpenClown-bot/developer-assistant`.
- Local git identity observed: `OpenClown-bot <yourmomsenpai@yandex.ru>`.
- Preferred review stack: GitHub Actions, docs validation, relevant tests/lint/typecheck, `pr-agent`, and separate Reviewer LLM.
- PR-Agent is configured as an advisory automated review layer using Qodo PR-Agent on GPT-5.3 Codex through OmniRoute.
- Required GitHub Actions secret for PR-Agent: `OMNIROUTE_API_KEY`.
- PR-Agent action is pinned to commit `0e37fc84fcc8207561e64eef8f7f634fb57e8447` in PR #3 to avoid floating `@main` supply-chain risk.
- Available LLMs: Codex GPT-5.5 High/XHigh, GPT-5.3 Codex, GLM 5.1, Kimi 2.6, Qwen 3.6 Plus.
- Planned role-model mapping: Business Planner = Codex GPT-5.5 High; Architect = Codex GPT-5.5 XHigh; Executor = GLM 5.1 (default), Qwen 3.6 Plus (parallel), Codex GPT-5.5 (specialist); Reviewer = Kimi 2.6.
- Strategic Orchestrator runtime: GPT-5.5 high on opencode (Founder's Windows PC). Replaces the prior implicit "Devin = orchestrator" assumption — Devin is now a tool the Strategic Orchestrator may invoke, not the orchestrator itself.
- Ticket Orchestrator runtime: GPT-5.5 thinking on opencode (Founder's Windows PC). One fresh TO session per TKT, never reused.
- Runtime Hermes Orchestrator persona is loaded at runtime by the deployed Hermes Agent (`docs/prompts/runtime-hermes-orchestrator.md`); it is NOT one of the dev-time pipeline roles.
- Token budget: no strict limit for listed models.

## Pending User Decisions

- Whether to create a retroactive ticket for PR-Agent setup/configuration history.
- Whether to run an Architect readiness/promotion pass for `TKT-008` now that TKT-006 and TKT-014 are complete, or prioritize one of the live-runtime follow-ups from TKT-006.

## Next Recommended Action

Recommended next step: ask Architect for a readiness/promotion pass on `TKT-008` now that its TKT-006 and TKT-014 prerequisites are complete. If the next priority is live Telegram operation before GitHub orchestration, select the highest-priority TKT-006 follow-up (`TKT-NEW-006-A` or `TKT-NEW-006-D`) instead.
