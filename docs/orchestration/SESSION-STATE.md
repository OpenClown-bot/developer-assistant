---
id: SESSION-STATE
version: 0.2.5
status: active
updated: 2026-05-09
---

# Session State

## Project

- Name: `developer-assistant`
- Summary: AI developer assistant for orchestrating full software delivery projects.
- Repository state: GitHub repository is active; docs-as-code scaffold, approved architecture baseline, PR-Agent, Docs CI, TKT-001 validator baseline, Hermes-aligned role prompts, PR/review templates, Hermes runtime integration contract, Hermes skill/plugin security allowlist, operational state store, Hermes credential-bearing capability source review, state-store hardening, generated-project VPS deployment contract, runtime ticket readiness pass, project-specific GitHub workflow capability, Telegram founder interaction logic layer, TKT-008 readiness promotion/review, TKT-008 GitHub PR integration implementation/review, TKT-015 Hermes Telegram gateway transport binding/review, TKT-016 runtime GitHub executor binding/review, TKT-017 gated live-smoke readiness harness/review, TKT-011 readiness promotion/spec review, TKT-011 iter-1 blocked outcome record, TKT-018 trial-vehicle readiness/spec review, TKT-018 implementation + TKT-011 iter-2, and RV-CODE-023 review are merged to `main`. TKT-019 progress scheduling helper implementation PR #79, RV-CODE-024 review PR #81 merged to `main`. Architecture revision ARCH-001 v0.3.0 PRs #86-#90 (PR-A through PR-E) all merged to `main` after RV-SPEC-010..015 reviews and conflict resolution; 12 new tickets (TKT-020..031), 11 ADRs (ADR-004..013), 10 boundary-surface docs now on main.
- Artifact language: mixed. Conversation in Russian; long-lived repo docs and prompts in English.

## Current Phase

**AUDIT-001 implementation cycle CLOSED (2026-05-09).** TKT-033 (v0.3.0, status `done`, arch_ref `ARCH-001@0.3.0`) is the merged spec **and** merged implementation for AUDIT-001 (runtime_check enforcement at systemd boot). The implementation cycle ran 5 Executor iterations + 4 Reviewer-verify iterations + 1 Architect spec-amendment cycle, all on top of the spec landed 2026-05-08:

- **Spec cycle (2026-05-08)** closed at TKT-033 v0.2.0 ready: PR #123 (Architect spec) + PR #124 (RV-SPEC-016 iter-1 `pass_with_changes`) + PR #126 (RV-SPEC-017 iter-2 verify `pass`) merged in lockstep with the clerical SO PR (TKT-033 frontmatter promote + SESSION-STATE bump v0.2.3).
- **Implementation cycle (2026-05-08 → 2026-05-09)** closed at TKT-033 v0.3.0 done. Executor PR #128 (branch `exe/tkt-033-runtime-check-enforcement`, HEAD `c9f41c0`) merged 2026-05-09 via merge commit `18b73bc`; Reviewer artifact PR #129 (branch `rv/rv-code-033`) closed-as-superseded post-merge. The cycle exposed a spec-vs-runtime mismatch at iter-3 (Hermes v2026.4.30 uses definitions-time filtering, not dispatch-time exception raising), which Path-B-routed to an Architect spec amendment cycle — TKT-033 v0.2.0 → v0.3.0 — landed on `main` via PR #130 (Architect amendment) + RV-SPEC-018 (clerical SO ratify-ack). Post-amendment, Executor iter-4 reimplemented the round-trip as a filter-based assertion at `runtime_check.py:326-410` (`_attempt_hermes_filter_assertion` helper); PR-Agent (DeepSeek V4 Pro) caught a residual role-gating gap in the iter-4 integration that 3 Anthropic-family reviewers + Reviewer-Kimi initially missed (Finding 8.2.1 — AC-3 (i) production check ran unconditionally for orchestrator role, where spec § 1 B(i) scopes it to non-orchestrator roles only). Executor iter-5 closed Finding 8.2.1 via `if role != "orchestrator":` outer guard at `runtime_check.py:572-573` (mirroring existing precedent at `:499-503`) plus AC-3 (ii) config-driven gating guard at `:586-588` (`if "skills" in disabled_toolsets:`) plus 2 paired tests. Reviewer-Kimi iter-4 verify (PR #129 HEAD `1c44fcc`) closed the cross-model independent confirmation layer with verdict `pass` — Kimi K2.6 Moonshot on opencode (non-Anthropic-family reviewer) substantively re-verified Finding 8.2.1 closure, byte-equality of 11-name `RUNTIME_CHECK_INVARIANTS` enum + 10 raise-side classes + helper, and PR-Agent triage (gh REST API auth gap closed via `gh auth login --with-token`).

The TKT-032 cycle PRs (#119 Executor, #121 Architect ADR-014, #122 SO integration-composition audit) merged to `main` 2026-05-08; the cycle's RV-CODE-032 review (PR #120, branch `rv/rv-code-032`, merge commit `55882f4`) merged to `main` 2026-05-09 after a 1-line SO clerical fix to add the missing `status: complete` frontmatter key (matches RV-CODE-027 convention; review content untouched). AUDIT-001 implementation cycle now CLOSED 2026-05-09; AUDIT-002 (install-script operator hygiene) is the next dispatch — fresh Architect Devin session, NUDGE composition pending.

The live test that triggered this audit cycle exposed a second-layer gap that ADR-014 was not scoped to address: once the bot booted (after the eight infrastructure corrections), it was responding **as a generic Hermes Agent**, not as a `developer-assistant` Orchestrator runtime. `delegate_task` was enabled, `skill_manage` was enabled, `hermes-agent` skill was loaded, the classifier path was unused, `work_items` queue stayed idle, and the Orchestrator wrote production code directly into the test fork — fourteen documented contract violations against `MULTI-HERMES-CONTRACT.md` § 5 and the per-runtime startup invariants of `TKT-021.md` § 1. The merged specs in `main` are correct; the gap is at the runtime-composition verification gate. Full audit record and 14-row table: `docs/session-log/2026-05-08-session-2.md`. The Architect's parallel session-log covering ADR-014's eight infrastructure corrections is `docs/session-log/2026-05-08-session-1.md`.

Founder decision (2026-05-08): «делаем правильно. так, чтобы после переустановки проекта он завелся так, как мы его разрабатывали, а не на дефолтном гермесе» — selecting the Architect-ticket-family path. TKT-032 the *ticket* is moved to `blocked` (its AC are process-aliveness only and cannot detect the 14 behavioural mismatches). A four-ticket Architect family (`AUDIT-001..004` per the scope stubs in `docs/session-log/2026-05-08-session-2.md` § 5) is dispatched in order: AUDIT-001 (runtime_check enforcement at systemd boot — TKT-033, **spec closed 2026-05-08**) first, then AUDIT-002 (install-script operator hygiene) and AUDIT-003 (behaviour-level smoke replacing TKT-032 AC) in parallel, then AUDIT-004 (TKT-011 reformulation). Each AUDIT-NNN gets a fresh Architect Devin session, fresh Executor Devin session, and fresh Reviewer Devin session per cycle. After the family closes, TKT-011 is dispatched as the full-pipeline integration trial.

Prior backlog items (TKT-027 TKT-NEW-A..G, TKT-029 paginate_text prefix, etc.) remain deferred behind the AUDIT family.

## Process Variant

Lightweight PRD -> Architecture Specification -> Tickets -> PR implementation -> CI -> automated PR review -> Reviewer LLM -> user-approved merge.

**Mandatory pipeline rule (enforced 2026-05-07):** Every TKT cycle MUST produce exactly 2 PRs: (1) Executor implementation PR and (2) Reviewer artifact PR (`docs/reviews/RV-CODE-NNN.md`). Both must be merged to `main`. A cycle that omits the Reviewer PR is a pipeline integrity violation. The Reviewer PR contains the durable review record; without it in `main`, the review does not exist in the docs-as-code history.

## Current Active PRs

- **PR #120** (`rv/rv-code-032`, Reviewer): RV-CODE-032 review of PR #119 with verdict `pass-with-notes` (7 findings, 0 blockers). OPEN. CI failing on `validate-docs` (frontmatter issue in `docs/reviews/RV-CODE-032.md`). Base branch is `exe/tkt-032-vps-smoke-test` (stale post-#119-merge); needs retarget to `main`. Awaiting Reviewer fix to frontmatter and base retarget, then Founder merge. Pipeline debt; does NOT block AUDIT-002 dispatch in itself but MUST be cleared before AUDIT-002 dispatch so the audit history stays coherent.

PR #123 (`arch/audit-001-runtime-check-enforcement`, Architect TKT-033 spec), PR #124 (`rv/rv-spec-016`, Reviewer iter-1 review artifact), PR #126 (`rv/rv-spec-017`, Reviewer iter-2 verify-pass artifact) merged to `main` 2026-05-08 — AUDIT-001 spec cycle CLOSED. PR #130 (`arch/tkt-033-iter-3-spec-amend`, Architect TKT-033 v0.2.0 → v0.3.0 amendment) merged to `main` 2026-05-09 (HEAD `78d1e42`) — spec-vs-runtime mismatch resolved. PR #128 (`exe/tkt-033-runtime-check-enforcement`, Executor TKT-033 implementation, HEAD `c9f41c0`) merged to `main` 2026-05-09 via merge commit `18b73bc` — AUDIT-001 implementation cycle CLOSED. PR #129 (`rv/rv-code-033`, Reviewer artifact, HEAD `1c44fcc` carrying RV-CODE-033 v0.4.0 with iter-1/2/3 + iter-3-revision + iter-4 entries) closed-as-superseded post-PR-#128-merge alongside this clerical SO PR (TKT-033 frontmatter `ready` → `done` + this SESSION-STATE bump v0.2.3 → v0.2.4).

All TKT-032 cycle PRs (#119 Executor, #121 Architect ADR-014, #122 SO integration-composition audit) merged to `main` as of 2026-05-08. All prior pending merges (PR #111 TKT-029 Executor, PR #112 RV-CODE-029, PR #113 RV-CODE-030, PR #114–#118 closure / fix / spec PRs) merged to `main`.

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
- `TKT-029`: merged PR #111 (Executor). RV-CODE-029 merged PR #112. Daily digest + Telegram /status handler + status_query shared module.
- `TKT-030`: merged PR #110. RV-CODE-030 merged PR #113. Recovery playbook drift harness + contributor convention. TKT-030-FIX-001 (`devassist-omniroute.service` → `omniroute.service` reconciliation) merged PRs #115/#116/#117.
- `TKT-031`: merged PR #106. Errors/llm_calls tables, health endpoints, ObservabilityManager.
- `TKT-032`: spec merged PR #118. Cycle PRs #119 (Executor, merged), #120 (Reviewer, OPEN — see Current Active PRs), #121 (Architect ADR-014, merged). Status **`blocked`** as of 2026-05-08. Reason ticket is `blocked` rather than `done`: current AC are process-aliveness only and cannot detect the live behaviour mismatches catalogued in `docs/session-log/2026-05-08-session-2.md` § 2. Will be superseded or absorbed by AUDIT-003 per AUDIT-family plan.
- `TKT-033`: AUDIT-001 spec **and** implementation — runtime_check enforcement at systemd boot. Status `done`, version `0.3.0`, arch_ref `ARCH-001@0.3.0`. **Spec cycle:** PR #123 (Architect spec) + PR #124 (RV-SPEC-016 iter-1 `pass_with_changes`) + PR #126 (RV-SPEC-017 iter-2 verify `pass`) all merged 2026-05-08 → TKT-033 v0.2.0 ready. **Spec amendment cycle:** PR #130 (Architect TKT-033 v0.2.0 → v0.3.0 — definitions-time filter alignment per Hermes v2026.4.30) merged 2026-05-09 (HEAD `78d1e42`) — Path-B-routed from Executor iter-3 escalation. **Implementation cycle:** PR #128 (Executor, branch `exe/tkt-033-runtime-check-enforcement`, HEAD `c9f41c0`) merged 2026-05-09 via merge commit `18b73bc`. PR #129 (Reviewer artifact `rv/rv-code-033`, HEAD `1c44fcc` carrying RV-CODE-033 v0.4.0) closed-as-superseded post-merge. **Iteration count:** 5 Executor iters (iter-1/2/3 escalation/4/5) + 4 Reviewer-verify iters (iter-1/2/3/3-revision/4) + 1 Architect amendment cycle. **PR-Agent (DeepSeek V4 Pro) caught Finding 8.2.1** at iter-4 HEAD that 3 Anthropic-family reviewers + Reviewer-Kimi initially missed: AC-3 (i) production check ran unconditionally for orchestrator role, where spec § 1 B(i) scopes to non-orchestrator roles only. **Iter-5** closed Finding 8.2.1 via `if role != "orchestrator":` outer guard at `runtime_check.py:572-573` (mirroring existing precedent at `:499-503`) + AC-3 (ii) config-driven gating guard at `:586-588` (`if "skills" in disabled_toolsets:`) + 2 paired tests. **Reviewer-Kimi iter-4 verify** (Kimi K2.6 Moonshot on opencode, non-Anthropic-family reviewer) substantively re-verified Finding 8.2.1 closure with verdict `pass` — cross-model independent confirmation closed.
- `TKT-NEW-INT-AUDIT-002..004`: AUDIT-002 (install-script operator hygiene), AUDIT-003 (behaviour-level smoke replacing TKT-032 AC), AUDIT-004 (TKT-011 reformulation). All three pending Architect dispatch — each gets a fresh Architect Devin session AFTER the previous AUDIT closes (AUDIT-002 dispatched after AUDIT-001 ratify+merge; AUDIT-003 dispatched in parallel with AUDIT-002 since they have no shared interfaces; AUDIT-004 dispatched after AUDIT-002 + AUDIT-003 close). Scope stubs in `docs/session-log/2026-05-08-session-2.md` § 5. Numbering at Architect discretion (next free `TKT-034..036` slot most likely).

## Current Blockers

- **Integration-composition gap (2026-05-08).** Deployed Hermes runtime boots after ADR-014's eight infrastructure corrections, but boots in a generic Hermes loadout, not in the `developer-assistant` composition. Root cause: `runtime_check.check_runtime()` (TKT-021 § 1) is not enforced from the systemd `ExecStartPre=` of `etc/systemd/devassist@<role>.service.tmpl` (TKT-020), and TKT-032 AC are process-aliveness only. **Partially resolved 2026-05-09 by AUDIT-001 implementation merge** (PR #128 — TKT-033 v0.3.0 done): `ExecStartPre=` enforcement at the systemd unit layer + 11-name `RUNTIME_CHECK_INVARIANTS` enum (delegate_task_callable / skill_manage_callable + 8 prior + prompt-manifest pair) + filter-based round-trip + role-gated and config-driven guards now landed. **Full resolution requires AUDIT-002 (install-script operator hygiene), AUDIT-003 (behaviour-level smoke replacing TKT-032 AC), and AUDIT-004 (TKT-011 reformulation) close.** Full evidence and root-cause analysis in `docs/session-log/2026-05-08-session-2.md`.
- TKT-011 dispatch precondition is rewritten by AUDIT-004; until AUDIT-001..003 are merged, TKT-011 must not be dispatched.
- PR #120 `validate-docs` failure on `docs/reviews/RV-CODE-032.md` frontmatter (Reviewer must fix). Not blocking the SO's audit PR #122; blocking PR #120's path to merge.
- `FIREWORKS_API_KEY` must be rotated before production use — it was exposed in chat during TKT-032 live debugging (per ADR-014 / PR #121 security note). Founder action.
- GitHub CLI `gh` is available and authenticated in the current SO environment, but future sessions must still verify `gh auth status`. Note: the deployed VPS runtime under TKT-032 lacked `gh` despite `SESSION-STATE.md` text previously claiming availability — documentation drift, addressed by AUDIT-002.

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
- **Founder decision recorded 2026-05-08:** post-live-deployment audit path is the Architect-ticket-family route (Variant A from the SO diagnostic message of 2026-05-08). No further pending decisions on path; AUDIT-001 is currently at spec stage (PR #123, RV-SPEC-016 in flight).

## Next Recommended Action

1. Reviewer fixes `docs/reviews/RV-CODE-032.md` frontmatter and retargets PR #120 base to `main`; Founder merges PR #120. Pipeline debt cleared. MUST be cleared before AUDIT-002 dispatch so the audit history stays coherent.
2. SO dispatches AUDIT-002 (install-script operator hygiene) — fresh Architect Devin session — after PR #120 clears. Standard 3-cycle: spec → implementation → reviewer-artifact.
3. After AUDIT-002 spec ratifies, AUDIT-003 (behaviour-level smoke replacing TKT-032 AC) is dispatched in parallel with AUDIT-002 (no shared interfaces). After AUDIT-002 + AUDIT-003 close, AUDIT-004 reformulates TKT-011 as the full-pipeline trial.
4. Founder rotates `FIREWORKS_API_KEY` before any production use (per ADR-014 / PR #121 security note).
5. BACKLOG items remain deferred across all tickets.
