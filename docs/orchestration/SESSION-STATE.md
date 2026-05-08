---
id: SESSION-STATE
version: 0.2.1
status: active
updated: 2026-05-08
---

# Session State

## Project

- Name: `developer-assistant`
- Summary: AI developer assistant for orchestrating full software delivery projects.
- Repository state: GitHub repository is active; docs-as-code scaffold, approved architecture baseline, PR-Agent, Docs CI, TKT-001 validator baseline, Hermes-aligned role prompts, PR/review templates, Hermes runtime integration contract, Hermes skill/plugin security allowlist, operational state store, Hermes credential-bearing capability source review, state-store hardening, generated-project VPS deployment contract, runtime ticket readiness pass, project-specific GitHub workflow capability, Telegram founder interaction logic layer, TKT-008 readiness promotion/review, TKT-008 GitHub PR integration implementation/review, TKT-015 Hermes Telegram gateway transport binding/review, TKT-016 runtime GitHub executor binding/review, TKT-017 gated live-smoke readiness harness/review, TKT-011 readiness promotion/spec review, TKT-011 iter-1 blocked outcome record, TKT-018 trial-vehicle readiness/spec review, TKT-018 implementation + TKT-011 iter-2, and RV-CODE-023 review are merged to `main`. TKT-019 progress scheduling helper implementation PR #79, RV-CODE-024 review PR #81 merged to `main`. Architecture revision ARCH-001 v0.3.0 PRs #86-#90 (PR-A through PR-E) all merged to `main` after RV-SPEC-010..015 reviews and conflict resolution; 12 new tickets (TKT-020..031), 11 ADRs (ADR-004..013), 10 boundary-surface docs now on main.
- Artifact language: mixed. Conversation in Russian; long-lived repo docs and prompts in English.

## Current Phase

**Integration-verification halt (2026-05-08).** The first live VPS deployment under TKT-032 was performed by the Founder and exposed an integration-verification gap: the deployed Hermes runtime ran with a generic Hermes loadout (`delegate_task` enabled, `skill_manage` enabled, `hermes-agent` skill loaded, classifier path unused, `work_items` queue idle, Orchestrator writing production code directly into the test fork) instead of the composition mandated by `MULTI-HERMES-CONTRACT.md` § 5 and the per-runtime startup invariants of `TKT-021.md` § 1. The merged specs in `main` are correct; the gap is at the verification gate. Full incident record and 14-row contract-mismatch table: `docs/session-log/2026-05-08-session-1.md`.

Founder decision (2026-05-08): «делаем правильно. так, чтобы после переустановки проекта он завелся так, как мы его разрабатывали, а не на дефолтном гермесе» — selecting the Architect-ticket-family path. TKT-032 is moved to `blocked`; the Ticket Orchestrator session driving TKT-032 on the Founder's Windows PC is paused. A four-ticket Architect family (`AUDIT-001..004` per the scope stubs in the incident record § 5) is dispatched in order: AUDIT-001 (runtime_check enforcement at systemd boot) first, then AUDIT-002 (install-script operator hygiene) and AUDIT-003 (behaviour-level smoke replacing TKT-032 AC) in parallel, then AUDIT-004 (TKT-011 reformulation). After the family closes, TKT-011 is dispatched as the full-pipeline integration trial.

Prior backlog items (TKT-027 TKT-NEW-A..G, TKT-029 paginate_text prefix, etc.) remain deferred behind the AUDIT family.

## Process Variant

Lightweight PRD -> Architecture Specification -> Tickets -> PR implementation -> CI -> automated PR review -> Reviewer LLM -> user-approved merge.

**Mandatory pipeline rule (enforced 2026-05-07):** Every TKT cycle MUST produce exactly 2 PRs: (1) Executor implementation PR and (2) Reviewer artifact PR (`docs/reviews/RV-CODE-NNN.md`). Both must be merged to `main`. A cycle that omits the Reviewer PR is a pipeline integrity violation. The Reviewer PR contains the durable review record; without it in `main`, the review does not exist in the docs-as-code history.

## Current Active PRs

- PR #118 (TKT-032 spec): **frozen pending AUDIT family**. The iter-1 NUDGE for the deployed Executor on the VPS is rescinded. The PR is left open as a placeholder; AUDIT-003 may supersede or absorb its AC. Do not progress without Architect direction.
- PR opened 2026-05-08 carrying `docs/session-log/2026-05-08-session-1.md` (incident record) plus this `SESSION-STATE.md` update — single small process-state PR; the standard 2-PR rule does not apply because no TKT cycle is being closed.
- PR #111 (TKT-029 Executor), PR #112 (RV-CODE-029), PR #113 (RV-CODE-030): per the prior phase, awaiting Founder merge. The AUDIT halt does not block these merges — they are pre-existing closure artefacts.

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
- `TKT-011`: ready in PR #64; reviewed in PR #65 / `RV-SPEC-006.md` with verdict `pass`; iter-1 blocked in PR #67 because no ready implementation ticket existed as trial target; iter-2 used TKT-018 as trial vehicle (pass); iter-3 used TKT-019 as trial vehicle (pass_with_recommendations); UNBLOCKED — all prerequisite tickets (TKT-020..030, TKT-031) merged. Awaiting Architect fix for omniroute naming inconsistency, then integration trial.
- `TKT-014`: done in PR #32; reviewed in PR #33.
- `TKT-015`: done in PR #47; reviewed in PR #48 / `RV-CODE-019.md` with verdict `pass`.
- `TKT-016`: done in PR #53; reviewed in PR #54 / `RV-CODE-020.md` with verdict `pass`.
- `TKT-017`: done in PR #60; reviewed in PR #61 / `RV-CODE-021.md` with verdict `pass`.
- `TKT-018`: done in PR #72; reviewed in PR #74 / `RV-CODE-023.md` with verdict `pass`; served as TKT-011 iter-2 trial vehicle.
- `TKT-019`: done in PR #79; reviewed in PR #81 / `RV-CODE-024.md` with verdict `pass_with_recommendations`; progress scheduling persistence helper, TKT-011 iter-3 trial vehicle.
- `TKT-020`: merged PR #98. CI fix: 9296dfa.
- `TKT-021`: merged PR #101. Multi-Hermes runtime layout.
- `TKT-022`: merged PR #100. Work-queue + escalations schema.
- `TKT-023`: merged PR #103. Escalation-policy + work-queue plugins.
- `TKT-024`: merged PR #104. Upstream-adapter scaffolding.
- `TKT-025`: merged PR #105. Custom Hermes skills + allowlist §5.
- `TKT-026`: merged PR #102. Model-catalog enforcement.
- `TKT-027`: merged PR #108. Operator CLI `dev-assist-cli`. RV-CODE-027 PR #109, verdict pass_with_changes. BACKLOG: TKT-NEW-A..G.
- `TKT-028`: merged PR #107. Structured logging + work_item_id propagation.
- `TKT-029`: Executor PR #111 merge-safe; RV-CODE-029 PR #112 retroactive. Daily digest + Telegram /status handler + status_query shared module.
- `TKT-030`: merged PR #110. RV-CODE-030 PR #113 retroactive. Recovery playbook drift harness + contributor convention. Known issue: `devassist-omniroute.service` vs `omniroute.service` — Architect fix required before TKT-011.
- `TKT-031`: merged PR #106. Errors/llm_calls tables, health endpoints, ObservabilityManager.
- `TKT-032`: status **`blocked`** (was `ready`) as of 2026-05-08. Spec PR #118 frozen. Reason: live VPS deployment under this ticket exposed integration-verification gap; current AC are process-aliveness only and cannot detect the live behaviour mismatches catalogued in `docs/session-log/2026-05-08-session-1.md` § 2. Will be superseded or absorbed by AUDIT-003 per Architect direction.
- `TKT-NEW-INT-AUDIT-001..004`: pending Architect dispatch. Scope stubs in `docs/session-log/2026-05-08-session-1.md` § 5. Numbering at Architect discretion (`TKT-NEW-INT-AUDIT-*` family or next free `TKT-033..036` slot).

## Current Blockers

- **Integration-verification gap (2026-05-08).** Deployed Hermes runtime does not boot in the `developer-assistant` composition. Root cause: `runtime_check.check_runtime()` (TKT-021 § 1) is not enforced from the systemd `ExecStartPre=` of `etc/systemd/devassist@<role>.service.tmpl` (TKT-020), and TKT-032 AC are process-aliveness only. Resolved by the AUDIT-001..004 family. Full evidence and root-cause analysis in `docs/session-log/2026-05-08-session-1.md`.
- TKT-011 dispatch precondition is rewritten by AUDIT-004; until AUDIT-001..003 are merged, TKT-011 must not be dispatched.
- Halt directive on the Ticket Orchestrator session driving TKT-032 on the Founder's Windows PC. Founder closes the current TO opencode tab; the next TO opencode tab is opened only when AUDIT-001 reaches `ready` and the AUDIT-001 ticket body is the new dispatch target.
- `devassist-omniroute.service` vs `omniroute.service` naming inconsistency in RECOVERY-PLAYBOOK.md §10 (detected by TKT-030 harness). Architect must reconcile before TKT-011 dispatch. Not a code blocker — the harness correctly flags it. Tracked separately from the AUDIT family.
- GitHub CLI `gh` is available and authenticated in the current SO environment, but future sessions must still verify `gh auth status`. Note: the deployed VPS runtime under TKT-032 lacked `gh` despite `SESSION-STATE.md` text claiming availability — documentation drift, addressed by AUDIT-002.

## Current Architectural Decisions

- `ARCH-001` version `0.3.0` is approved and merged to `main` (PRs #86-#90).
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
- **Founder decision recorded 2026-05-08:** post-live-deployment audit path is the Architect-ticket-family route (Variant A from the SO diagnostic message of 2026-05-08). No further pending decisions on path; the family is dispatched after this incident PR merges.

## Next Recommended Action

1. Founder merges the incident PR (`docs/session-log/2026-05-08-session-1.md` + this `SESSION-STATE.md` update). This PR is process state only; no code change.
2. Founder closes the current Ticket Orchestrator opencode tab driving TKT-032 on the Windows PC (halt directive — see Current Blockers).
3. SO drafts Architect dispatch NUDGE for AUDIT-001 only (lowest-risk, highest-leverage of the four). The NUDGE points at the scope stub in `docs/session-log/2026-05-08-session-1.md` § 5.1 and asks the Architect to write the formal ticket body under `docs/tickets/`.
4. After AUDIT-001 ratifies the runtime-check pattern via merge, AUDIT-002 and AUDIT-003 are dispatched in parallel (no shared interfaces).
5. After AUDIT-002 + AUDIT-003 close, AUDIT-004 reformulates TKT-011 as the full-pipeline trial.
6. Pre-existing pending merges (PR #111 TKT-029 Executor, PR #112 RV-CODE-029, PR #113 RV-CODE-030) plus the architect fix for `devassist-omniroute.service` naming remain queued; they are not blocked by the AUDIT halt and may be processed in parallel at Founder discretion.
7. BACKLOG items remain deferred across all tickets.
