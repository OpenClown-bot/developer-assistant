---
id: SESSION-STATE
version: 0.1.1
status: active
updated: 2026-05-06
---

# Session State

## Project

- Name: `developer-assistant`
- Summary: AI developer assistant for orchestrating full software delivery projects.
- Repository state: GitHub repository is active; docs-as-code scaffold, approved architecture baseline, PR-Agent, Docs CI, TKT-001 validator baseline, Hermes-aligned role prompts, PR/review templates, Hermes runtime integration contract, Hermes skill/plugin security allowlist, operational state store, Hermes credential-bearing capability source review, state-store hardening, generated-project VPS deployment contract, runtime ticket readiness pass, project-specific GitHub workflow capability, Telegram founder interaction logic layer, TKT-008 readiness promotion/review, TKT-008 GitHub PR integration implementation/review, TKT-015 Hermes Telegram gateway transport binding/review, TKT-016 runtime GitHub executor binding/review, TKT-017 gated live-smoke readiness harness/review, TKT-011 readiness promotion/spec review, TKT-011 iter-1 blocked outcome record, TKT-018 trial-vehicle readiness/spec review, TKT-018 implementation + TKT-011 iter-2, and RV-CODE-023 review are merged to `main`. TKT-019 progress scheduling helper implementation PR #79, RV-CODE-024 review PR #81 merged to `main`.
- Artifact language: mixed. Conversation in Russian; long-lived repo docs and prompts in English.

## Current Phase

TKT-001 through TKT-010 and TKT-012 through TKT-017 are complete. Runtime readiness pass PR #29 is merged and reviewed by RV-SPEC-001. `TKT-008` implementation PR #41 and review PR #42 are merged. `TKT-015` implementation PR #47 and review PR #48 are merged. `TKT-016` implementation PR #53 and review PR #54 are merged. `TKT-017` implementation PR #60 and review PR #61 are merged. `TKT-011` remains ready after PR #64 and SPEC review PR #65; iter-2 (part of PR #72) reaffirmed blocked readiness — PROJECT_GITHUB_PAT and TELEGRAM_BOT_TOKEN unavailable; full Telegram-to-PR trial not yet executed. `TKT-018` is now done after implementation PR #72 and CODE review PR #74 / RV-CODE-023; it served as the trial vehicle. `TKT-011` iter-3 completed: first time BOTH readiness lanes (GitHub + Telegram) passed. `TKT-019` is done after implementation PR #79 and CODE review PR #81 / RV-CODE-024 (pass_with_recommendations, 2 minor non-blocking findings filed as TKT-NEW-019-A and TKT-NEW-019-B).

## Process Variant

Lightweight PRD -> Architecture Specification -> Tickets -> PR implementation -> CI -> automated PR review -> Reviewer LLM -> user-approved merge.

## Current Active PRs

- PR #73 (Devin): carry-over practices audit + pipeline model assignments + self-deployment Architect-pass directive. Not reviewed through project pipeline.

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
- `TKT-008`: done in PR #41; reviewed in PR #42 / `RV-CODE-008.md` with verdict `pass`.
- `TKT-011`: ready in PR #64; reviewed in PR #65 / `RV-SPEC-006.md` with verdict `pass`; iter-1 blocked in PR #67 because no ready implementation ticket existed as trial target; first Telegram-to-PR orchestration trial remains pending.
- `TKT-014`: done in PR #32; reviewed in PR #33.
- `TKT-015`: done in PR #47; reviewed in PR #48 / `RV-CODE-019.md` with verdict `pass`.
- `TKT-016`: done in PR #53; reviewed in PR #54 / `RV-CODE-020.md` with verdict `pass`.
- `TKT-017`: done in PR #60; reviewed in PR #61 / `RV-CODE-021.md` with verdict `pass`.
- `TKT-018`: done in PR #72; reviewed in PR #74 / `RV-CODE-023.md` with verdict `pass`; served as TKT-011 iter-2 trial vehicle.
- `TKT-019`: done in PR #79; reviewed in PR #81 / `RV-CODE-024.md` with verdict `pass_with_recommendations`; progress scheduling persistence helper, TKT-011 iter-3 trial vehicle.

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
- ~~Lightweight web interface is deferred until Telegram works.~~ Superseded 2026-05-06 by ADR-013 (`docs/architecture/adr/ADR-013-web-interface.md`): `PRD-001.md` v0.2.1 § 6 is met in v0.1 by a read-only `dev-assist-cli serve-web` HTTP surface on `127.0.0.1:8180`, with Founder access via SSH tunnel. No new daemon, no new framework, no auth at the application layer; lifecycle as the eighth systemd unit `devassist-web.service` (`SELF-DEPLOYMENT-CONTRACT.md` v0.2.0 § 5.4).
- Merge policy for v0.1: always ask founder after CI and Reviewer pass.
- Generated project VPS deployment contract: one-command `make deploy` or equivalent; final live execution requires founder approval.
- Hermes Telegram gateway source review passed with constraints for production `TELEGRAM_BOT_TOKEN` use.
- Hermes bundled GitHub credential-bearing skills reviewed in TKT-012 are not cleared for production `GITHUB_TOKEN` or `GH_TOKEN` use; use project-specific REST API plus `git` orchestration instead.
- Operational state store hardening is complete: SQLite foreign keys are enforced, project binding upserts preserve omitted optional fields, and WAL/single-thread guidance is documented.
- Runtime readiness pass: `TKT-006` provides the Telegram founder interaction logic layer, `TKT-014` provides the reviewed project-specific GitHub REST API plus constrained `git` workflow capability, `TKT-008` provides the high-level GitHub PR integration logic layer, `TKT-015` binds the Telegram adapter to a Hermes Telegram gateway transport boundary with mocked smoke coverage and security checks, `TKT-016` binds GitHub executor protocols to real runtime HTTP/git execution with mocked coverage and token-redaction checks, and `TKT-017` adds a gated live-smoke readiness harness that fails closed without explicit gates/credentials. `TKT-018` is the separate ready implementation ticket selected as the next `TKT-011` trial vehicle; TKT-017 existence alone is not live readiness, and both GitHub and Telegram readiness lanes must pass before the full trial runs.

## Current Tooling Decisions

- Git host: GitHub.
- GitHub repository: `https://github.com/OpenClown-bot/developer-assistant`.
- Local git identity observed: `OpenClown-bot <yourmomsenpai@yandex.ru>`.
- Preferred review stack: GitHub Actions, docs validation, relevant tests/lint/typecheck, `pr-agent`, and separate Reviewer LLM.
- PR-Agent is configured as an advisory automated review layer using Qodo PR-Agent on DeepSeek V4 Pro through OmniRoute.
- Required GitHub Actions secret for PR-Agent: `OMNIROUTE_API_KEY`.
- PR-Agent action is pinned to commit `0e37fc84fcc8207561e64eef8f7f634fb57e8447` in PR #3 to avoid floating `@main` supply-chain risk.
- Available LLMs: Codex GPT-5.5 High/XHigh, GPT-5.3 Codex, DeepSeek V4 Pro, GLM 5.1, Kimi 2.6, Qwen 3.6 Plus.
- **Founder-set role-model mapping (2026-05-05):**
  - Business Planner = Codex GPT-5.5 High.
  - Architect = Codex GPT-5.5 XHigh.
  - Strategic Orchestrator = GPT-5.5 high (main) / DeepSeek V4 Pro (fallback) on opencode (Founder's Windows PC). Supersedes the prior implicit "Devin = orchestrator" assumption — Devin is now a tool the Strategic Orchestrator may invoke, not the orchestrator itself.
  - Ticket Orchestrator = GPT-5.5 high (main) / GLM 5.1 (fallback) on opencode (Founder's Windows PC). Supersedes the prior "GPT-5.5 thinking" baseline. One fresh TO session per TKT, never reused.
  - Executor = DeepSeek V4 Pro (main) / GLM 5.1 (fallback) / Codex GPT-5.5 (specialist) on opencode + OmniRoute. Supersedes the prior "GLM 5.1 default, Qwen 3.6 Plus parallel" baseline.
  - Reviewer = Kimi K2.6 (main) / Qwen 3.6 Plus (fallback) on opencode + OmniRoute. Supersedes the prior "Kimi K2.6" only baseline.
  - PR-Agent = DeepSeek V4 Pro through OmniRoute on GitHub Actions (unchanged).
- Doctrine collisions introduced by the 2026-05-05 model-mapping change are filed in `docs/backlog/` as `TKT-NEW-to-rationale-doctrine-collision.md` (TO/SO uncorrelation rationale vs new GLM-5.1 / DeepSeek V4 Pro fallback positions). Architect-refresh required before either fallback is exercised in a closed cycle.
- Runtime Hermes Orchestrator persona is loaded at runtime by the deployed Hermes Agent (`docs/prompts/runtime-hermes-orchestrator.md`); it is NOT one of the dev-time pipeline roles.
- Token budget: no strict limit for listed models.

## Pending User Decisions

- Whether to create a retroactive ticket for PR-Agent setup/configuration history.
- None blocking immediate post-TKT-008 closure planning.

## Next Recommended Action

Recommended next step: Decide fate of PR #73 (Devin, unreviewed by project pipeline). Then reassess TKT-011 iter-3 readiness — TKT-019 is done but live credentials (PROJECT_GITHUB_PAT, TELEGRAM_BOT_TOKEN) remain unavailable. SO may close TKT-011 as blocked/unexecutable for v0.1 if credential path remains unavailable, or promote a new offline-only ticket as the next trial vehicle.
