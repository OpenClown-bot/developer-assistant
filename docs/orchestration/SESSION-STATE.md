---
id: SESSION-STATE
version: 0.1.0
status: active
updated: 2026-05-01
---

# Session State

## Project

- Name: `developer-assistant`
- Summary: AI developer assistant for orchestrating full software delivery projects.
- Repository state: GitHub repository is active; docs-as-code scaffold, approved architecture baseline, PR-Agent, Docs CI, TKT-001 validator baseline, Hermes-aligned role prompts, PR/review templates, Hermes runtime integration contract, Hermes skill/plugin security allowlist, and operational state store are merged to `main`.
- Artifact language: mixed. Conversation in Russian; long-lived repo docs and prompts in English.

## Current Phase

TKT-001 through TKT-005, TKT-007, and TKT-009 are complete; the next implementation batch needs Architect preparation.

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

## Current Blockers

- GitHub CLI `gh` is not available in PATH in this environment.
- GitHub repository was renamed from `OpenClown-bot/assistant-developer` to `OpenClown-bot/developer-assistant`.
- Local git remote `origin` points to `https://github.com/OpenClown-bot/developer-assistant.git`.
- Temporary GitHub PAT is configured in the current environment for this session.

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

## Current Tooling Decisions

- Git host: GitHub.
- GitHub repository: `https://github.com/OpenClown-bot/developer-assistant`.
- Local git identity observed: `OpenClown-bot <yourmomsenpai@yandex.ru>`.
- Preferred review stack: GitHub Actions, docs validation, relevant tests/lint/typecheck, `pr-agent`, and separate Reviewer LLM.
- PR-Agent is configured as an advisory automated review layer using Qodo PR-Agent on Qwen 3.6 Plus through OmniRoute.
- Required GitHub Actions secret for PR-Agent: `OMNIROUTE_API_KEY`.
- PR-Agent action is pinned to commit `0e37fc84fcc8207561e64eef8f7f634fb57e8447` in PR #3 to avoid floating `@main` supply-chain risk.
- Available LLMs: Codex GPT-5.5 High/XHigh, GLM 5.1, Kimi 2.6, Qwen 3.6 Plus.
- Planned role-model mapping: Business Planner = Codex GPT-5.5 High; Architect = Codex GPT-5.5 XHigh; Executor = GLM 5.1; Reviewer = Kimi 2.6.
- Token budget: no strict limit for listed models.

## Pending User Decisions

- Whether to install GitHub CLI `gh` or continue with plain `git` plus GitHub REST API for PR operations.
- Whether to create a retroactive ticket for PR-Agent setup/configuration history.

## Next Recommended Action

Open Architect work to prepare the next implementation batch after TKT-007 and TKT-009. Reassess whether TKT-006 (Telegram founder interaction), TKT-008 (GitHub integration), TKT-010 (deployment contract), or follow-up hardening tickets should become ready, accounting for the source-review caveats in `docs/architecture/HERMES-SKILL-ALLOWLIST.md` and low-severity state-store review findings in `docs/reviews/RV-CODE-010.md`.
