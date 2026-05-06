---
id: ARCH-001
version: 0.3.0
status: draft
---

# ARCH-001: Telegram-First Multi-Hermes Self-Deployable v0.1 Architecture

## 1. Context

`developer-assistant` is a docs-as-code project for building an AI developer assistant that can orchestrate software delivery through separated roles, durable repository artifacts, pull requests, CI, and review gates.

ARCH-001 v0.2.0 selected the Hermes-first hybrid foundation, Telegram as the primary founder interface, and a split state model (repository artifacts authoritative for governance, SQLite operational store for runtime state). That selection remains in force.

ARCH-001 v0.3.0 absorbs the three new product mandates introduced by `PRD-001.md` v0.2.1:

- **Self-deployment of the assistant itself onto the Founder's VPS** as a v0.1 prerequisite, not an optional follow-up (`PRD-001.md` § 12).
- **High-autonomy operation with exception-based escalation** to the Founder only when a candidate decision deviates from the original concept OR risks breaking already-committed scope or operational state (`PRD-001.md` § 13.1).
- **Multi-Hermes team composition**: each specialist role runs as its own full Hermes runtime with its own memory and self-learning state, while the Founder addresses one entity through one upstream adapter (`PRD-001.md` § 13.2). The upstream entry-point is abstracted so OpenClaw can be added in v0.2 as a parallel adapter (`PRD-001.md` § 13.3).

This revision keeps the v0.2.0 foundation intact and extends it with the multi-Hermes runtime architecture, the per-role skills/plugins layout, the upstream-adapter abstraction, the self-deployment architecture, the operationalized escalation policy, the Founder-pre-approved model catalog, and the research record that grounds these decisions. Detailed contracts for each area are split into separate documents that this spec references.

## 2. v0.1 Scope

v0.1 must prove an end-to-end Founder-driven project orchestration loop through Telegram, on a Founder-owned VPS, with the assistant deployed by the Founder using one command:

1. Telegram founder intake through the Orchestrator Hermes runtime.
2. Multi-Hermes orchestration: one specialist runtime per role (Business Planner, Architect, Executor, Reviewer) coordinated by the Orchestrator runtime through the SQLite work queue.
3. Repository docs-as-code governance for PRD, architecture, ADRs, tickets, questions, reviews, CI results, and handoff state.
4. GitHub repository creation and PR-based delivery under a least-privilege assistant token.
5. CI validation, Reviewer LLM artifacts, and explicit founder approval gates for sensitive actions and final merge/deployment decisions.
6. Progress reports in Russian after ticket completion and during long-running work.
7. A documented one-command VPS deployment contract for **generated projects** (`docs/architecture/GENERATED-PROJECT-DEPLOYMENT-CONTRACT.md`), without automatic live deployment in v0.1.
8. A one-command **self-deployment** contract for the assistant itself (`docs/architecture/SELF-DEPLOYMENT-CONTRACT.md`), with health verification, rollback, and explicit Founder approval gates for `start` and `upgrade`.
9. An **escalation policy** (`docs/architecture/ESCALATION-POLICY.md`) that operationalizes the PRD § 13.1 trigger pair as deterministic rules plus an LLM classifier, enforced as a Hermes plugin shared by every specialist runtime.
10. A **Founder-pre-approved model catalog** (`docs/architecture/MODEL-CATALOG.md`) such that within-catalog model picks proceed autonomously and only catalog changes escalate.

## 3. Deferred Scope

The following remain out of v0.1 unless later approved by the Founder:

- Public SaaS or hostile multi-tenant operation.
- OpenClaw as the primary runtime, default gateway, or part of v0.1's upstream adapter set. v0.2+ adds OpenClaw as an upstream adapter alongside Telegram per `UPSTREAM-ADAPTER-CONTRACT.md` § 4.
- Rich web dashboard beyond optional read-only status.
- **Ungated** fully autonomous production deployment (no Founder approval at `start` or `upgrade`). The PRD-mandated **gated** self-deployment with three approval gates (`install`, `start`, `upgrade`) is **in scope** for v0.1 per `SELF-DEPLOYMENT-CONTRACT.md` § 6 and `PRD-001.md` § 12; only the ungated, fully autonomous variant remains deferred.
- Unreviewed marketplace plugin or skill installation.
- Autonomous merge policy that bypasses user acknowledgement.
- Paid sandbox terminal backends (`modal`, `daytona`, `vercel_sandbox`) and other paid third-party hard dependencies. v0.1 budget covers one Founder-owned VPS plus already-approved LLM API spend (OmniRoute / OpenRouter / direct providers); anything else escalates per `ESCALATION-POLICY.md` § 4.
- Cross-runtime IPC over a network message bus (Redis, NATS, RabbitMQ, A2A-over-HTTP between specialist runtimes). v0.1 mediates inter-runtime work through the SQLite operational store on the same host (ADR-006).

## 4. Architecture Principles

- Telegram is the v0.1 upstream adapter; OpenClaw is intended to slot in as a v0.2+ parallel adapter without changing specialist runtimes.
- Hermes Agent is the runtime foundation. Each specialist role runs as a separate Hermes installation with its own `HERMES_HOME`, memory, and self-learning state.
- Repository artifacts remain the governance source of truth.
- Hermes memory, Telegram chat history, and operational databases are operational state, not authoritative product or engineering decisions.
- Per-runtime memory isolation is **filesystem-level**: each runtime has a distinct `HERMES_HOME` directory, enforced by systemd sandbox directives (`ProtectHome=`, `ReadWritePaths=`, `BindReadOnlyPaths=`, `PrivateTmp=`). All five runtimes share a single Linux uid (`devassist`); a hostile intra-runtime actor is out of the v0.1 single-Founder threat model. Isolation is conditional on correct systemd unit configuration; no custom memory broker is introduced.
- Cross-runtime work is dispatched through a SQLite-mediated work queue that lives in the same operational store the v0.2 of `OPERATIONAL-STATE-STORE.md` already adopts.
- The escalation policy is enforced as a shared Hermes plugin loaded into every specialist runtime, not as a runtime-local instruction the LLM might forget.
- Self-deployment is a Founder-visible product surface (one-command install, one-command verify, one-command rollback, three approval gates), with implementation kept simple, observable, and dependency-light.
- GitHub PRs are the unit of implementation delivery.
- Secrets never live in repository artifacts.
- Hermes skills/plugins are accepted only through an allowlist, pinning, source review, scoped credentials, sandboxing, and rollback procedures (per ADR-003).
- Within the Founder-pre-approved model catalog, specialist runtimes pick models autonomously; catalog changes escalate.

## 5. System Components

| Component | v0.1 Responsibility | State or Artifacts |
| --- | --- | --- |
| Upstream adapter (Telegram in v0.1) | Receive Founder messages, authenticate, send progress reports and approval prompts | Operational session state outside repository |
| Orchestrator Hermes runtime | Run the upstream adapter, classify free-form messages, write work items to the SQLite queue, deliver progress reports, manage escalation surface | Per-runtime `HERMES_HOME`; SQLite work queue |
| Business Planner Hermes runtime | Produce PRDs and questions; consume work items targeted at role `business_planner` | Per-runtime `HERMES_HOME`; repository artifacts under `docs/prd/`, `docs/questions/` |
| Architect Hermes runtime | Produce architecture specs, ADRs, ticket Sections 1-9; consume work items targeted at role `architect` | Per-runtime `HERMES_HOME`; repository artifacts under `docs/architecture/`, `docs/tickets/` |
| Executor Hermes runtime | Implement tickets one PR at a time inside Docker terminal sandbox; consume work items targeted at role `executor` | Per-runtime `HERMES_HOME` with Docker terminal backend; repository code under ticket-allowed write zones |
| Reviewer Hermes runtime | Produce RV-SPEC and RV-CODE reviews; consume work items targeted at role `reviewer` | Per-runtime `HERMES_HOME`; repository artifacts under `docs/reviews/` |
| Role prompts | Define per-role behavior, required reading, write zones, stop conditions, outputs | `docs/prompts/` |
| Repository state store | Authoritative PRD, architecture, ADRs, tickets, questions, reviews, handoff notes, current durable project state | `docs/` artifacts |
| Operational state store | Telegram chat bindings, project registry, scheduled progress timers, Hermes run IDs, agent-run metadata, idempotency keys, **work_items queue**, **escalations queue** | SQLite database on VPS (`OPERATIONAL-STATE-STORE.md`, `MULTI-HERMES-CONTRACT.md` § 6) |
| GitHub integration | Repository creation, branches, PRs, check observation, CI status, review artifact links | Project-specific GitHub workflow capability + repository artifacts |
| CI and validation | Validate docs, tests, lint/typecheck, static/security checks as configured | GitHub Actions and local commands |
| Self-deployment surface | Install, verify, rollback, upgrade entry points and systemd units; secrets file | `scripts/install-self.sh`, `scripts/verify-self.sh`, `scripts/rollback-self.sh`, `scripts/upgrade-self.sh`, `etc/systemd/system/devassist-*.service`, Founder-supplied `SELF-DEPLOY.env` (`SELF-DEPLOYMENT-CONTRACT.md`) |
| Escalation enforcement | Pre-tool-call hook plugin shared by every runtime; deterministic rules + LLM classifier; escalations queue | `dev-assist-escalation-policy` Hermes plugin (`ESCALATION-POLICY.md`) + `escalations` table |
| Model catalog | Founder-pre-approved set of models per role with main + fallback assignments | `docs/architecture/MODEL-CATALOG.md` |
| Security policy | Constrain plugins, tools, credentials, sandboxes, approvals, rollback | ADRs, architecture docs, runtime config outside repository |

## 6. Platform Foundation

Hermes Agent v2026.4.30 (commit `73bf3ab1b22314ed9dfecbb59242c03742fe72af`) is the v0.1 runtime foundation. Per the research record (`RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3.2), one Hermes installation is one OS-level process. The PRD § 13.2 multi-Hermes mandate is therefore implemented as **five separate Hermes installations** under `/srv/devassist/runtimes/<role>/.hermes/`, each supervised by its own systemd unit (ADR-004, `SELF-DEPLOYMENT-CONTRACT.md` § 5).

Each Hermes runtime owns:

- Telegram gateway operation **only on the Orchestrator runtime**.
- Long-running server/VPS operation under systemd (auto-restart on failure; manual start after install per Section 12.5 of the PRD).
- Scheduled progress reports owned by the Orchestrator runtime via Hermes' `cronjob` tool.
- Sandboxed execution for the Executor and Reviewer runtimes via the Docker terminal backend.
- The escalation-policy enforcement plugin (loaded into all five runtimes).
- A shared external skill directory (`/srv/devassist/shared-skills/`) so that custom `dev-assist-*` skills are written once and loaded by every runtime that needs them.

`developer-assistant` still owns the governance model. Repository artifacts are authoritative for product, architecture, tickets, reviews, and durable decisions. Hermes is the runtime that executes and routes work, not the canonical record.

The implementation remains a Hermes-first hybrid: use Hermes capabilities where they reduce custom runtime work, and add only the minimal project-specific glue needed to enforce repository governance, prompts, tickets, CI, review gates, Telegram decision capture, project registry behavior, and the new escalation enforcement.

## 7. Telegram Founder Interaction

Telegram interaction is the v0.1 upstream adapter. From the Founder's view, exactly one bot identity exists; the multi-Hermes layout is invisible. The Telegram adapter lives **only on the Orchestrator runtime** (`UPSTREAM-ADAPTER-CONTRACT.md` § 4).

Hybrid command/free-form chat model:

- `/new_project` starts guided intake and creates or selects a project workspace after required approvals.
- `/status` returns current phase, active ticket, active PR, blockers, and pending decisions.
- `/decisions` lists open decisions requiring founder input.
- `/pause` and `/resume` control autonomous work for the current project.
- `/approve <id>` and `/deny <id>` resolve open escalation prompts (see § 11 below and `ESCALATION-POLICY.md` § 7).
- Free-form founder messages are routed to the Orchestrator runtime for classification as intake, answer, clarification, approval, rejection, or general question.

Question routing:

- Specialist runtimes emit founder questions with context, decision options, recommended default, impact, and urgency, written into the `escalations` table by the runtime that produced them.
- The Orchestrator runtime polls the `escalations` table, sends pending questions in Russian via Telegram, captures Founder responses, normalizes them into English durable decision notes, and writes the decision to the artifact target the question declared (`PRD`, `docs/questions/`, ADR, or ticket).

Progress reports:

- Sent after each ticket changes phase or a PR/review gate completes.
- Sent on a 30-to-60-minute interval during long-running work via the Orchestrator's `cronjob`.
- Reports include completed work, current action, blocker state, decisions needed, and notable risks; deep technical detail only on Founder request.

Decision capture:

- Telegram chat history is not enough for durable decisions.
- Decisions affecting product scope, architecture, security, credentials, merge policy, deployment, external services, or cost must be summarized into repository artifacts before being treated as final.
- Operational acknowledgements may remain in operational state when they do not affect durable engineering behavior.

## 8. State Model

Repository artifacts remain authoritative for durable engineering state (unchanged from v0.2.0):

- `docs/prd/` for product requirements.
- `docs/architecture/` and `docs/architecture/adr/` for system decisions.
- `docs/tickets/` for implementation contracts and status.
- `docs/questions/` for unresolved or resolved founder questions.
- `docs/reviews/` for Reviewer LLM artifacts.
- `docs/orchestration/SESSION-STATE.md` for human-readable phase, blockers, active tickets, active PRs, and next action.

External operational state (SQLite, per `OPERATIONAL-STATE-STORE.md` § 2) holds:

- Telegram user/chat allowlist and project chat binding.
- Project registry mapping Telegram conversations to GitHub repositories and local workspaces.
- Scheduled progress update timers and last-report timestamps.
- Hermes agent-run IDs, retry/idempotency keys, and in-flight task metadata.
- Non-secret credential metadata (which secret names must exist).
- **`work_items` queue** (new in v0.3.0): the canonical inter-runtime IPC primitive (`MULTI-HERMES-CONTRACT.md` § 6.2).
- **`escalations` queue** (new in v0.3.0): pending Founder-facing prompts produced by any runtime, surfaced to Telegram by the Orchestrator (`ESCALATION-POLICY.md` § 7, `MULTI-HERMES-CONTRACT.md` § 6.3).

External state must not store canonical product or architecture decisions without writing a durable repository summary. Secrets must live in environment variables (the Founder's `SELF-DEPLOY.env`), Hermes-supported secret mechanisms, GitHub Actions secrets, or VPS secret storage, never in repository artifacts.

## 9. GitHub And Review Flow

The Executor runtime uses GitHub through least-privilege credentials and repository-scoped permissions (unchanged from v0.2.0).

Implementation flow:

1. Founder approves architecture and a ticket sequence.
2. A ticket is moved to `ready` only when no unresolved blocker remains for that ticket.
3. The Orchestrator runtime writes a `work_item` for role `executor` and ticket id.
4. The Executor runtime claims the work item, works on one ticket in a branch, opens a PR linked to the ticket.
5. CI runs docs validation and relevant project checks.
6. `pr-agent` or equivalent automated review may provide supplemental feedback.
7. The Orchestrator writes a follow-up `work_item` for role `reviewer`; the Reviewer runtime writes an artifact under `docs/reviews/` using the allowed verdicts (`pass`, `pass_with_changes`, `pass_with_recommendations`, `fail`).
8. Founder acknowledgement is required before merge in v0.1.

Autonomous merges are not the default for v0.1. Merge policy is reconsidered after at least one successful Telegram-to-PR-to-review-to-merge cycle (TKT-011).

## 10. Security Model

v0.1 assumes one trusted founder/operator and assistant-owned or founder-approved repositories. It does not support hostile multi-tenant operation.

Accepted risks (unchanged from v0.2.0):

- Hermes Agent is a large runtime with broad tool, memory, gateway, and plugin capabilities.
- Skills/plugins can execute code, alter behavior, and access credentials if allowed.
- Telegram, GitHub, LLM providers, VPS runtime, and coding sandboxes form a broad trust boundary.

Required mitigations (extended in v0.3.0):

- Use a Telegram allowlist and explicit Founder chat pairing.
- Use least-privilege GitHub tokens scoped to required repositories and operations.
- Scope LLM, GitHub, Telegram, and VPS credentials separately; do not share a broad all-purpose token.
- Use Docker terminal backend for Executor and Reviewer; never `local` backend in production.
- Disable unreviewed project-local plugins (`HERMES_ENABLE_PROJECT_PLUGINS=false`) and marketplace auto-installation.
- Maintain an allowlist of enabled Hermes skills/plugins (`HERMES-SKILL-ALLOWLIST.md`) with source, version/commit, purpose, required credentials, review result, and rollback method.
- Pin Hermes runtime and all enabled skills/plugins to versions or commits.
- Source-review any optional/community skill before it receives credentials or write access.
- **Run the escalation-policy plugin in every runtime** so dangerous tool calls and out-of-concept actions are pre-empted before reaching Hermes' approval prompt.
- Keep a rollback path: stop the affected systemd unit, revoke credentials, restore last known-good runtime config, restore the operational state store from backup, and continue from repository state.
- Do not commit `.env`, PATs, API keys, SSH keys, Telegram tokens, or VPS credentials.
- Self-deployment secrets live only in `/srv/devassist/secrets/SELF-DEPLOY.env` (mode 0600, owner `devassist:devassist`); never written to logs, journalctl output, PR artifacts, or review artifacts.

## 11. Multi-Hermes Runtime Architecture

v0.1 runs five specialist Hermes runtimes on one Founder-owned VPS, supervised by systemd, communicating through the SQLite work queue. The detailed contract is `MULTI-HERMES-CONTRACT.md`; this section captures the architectural shape.

### 11.1 Per-Runtime Layout

Each runtime is a separate Hermes installation under `/srv/devassist/runtimes/<role>/.hermes/`, where `<role>` is one of `orchestrator`, `planner`, `architect`, `executor`, `reviewer`. Each runtime has:

- Its own `config.yaml`, `.env`, `auth.json`, `SOUL.md`, `memories/MEMORY.md`, `memories/USER.md`, `sessions/`, `state.db` (Hermes native sessions database, per `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3.5), `cron/`, `logs/`, and `skills/` directory.
- A symlink `operational.db -> /srv/devassist/state/operational.db` pointing at the **shared operational store** (distinct from the per-runtime `state.db`); never overwritten by Hermes itself, owned by the project's IPC layer (`MULTI-HERMES-CONTRACT.md` § 6, `OPERATIONAL-STATE-STORE.md`).
- Its own systemd unit (`devassist-<role>.service`), supervised by the umbrella `devassist.target`.
- A per-runtime `HERMES_DEVASSIST_ROLE` env var so the shared escalation-policy and work-queue plugins can specialize behavior without per-runtime plugin packages.

Memory isolation is **filesystem-level**: each runtime's `HERMES_HOME` is a distinct path, and systemd sandbox directives (`ProtectHome=`, `ReadWritePaths=`, `BindReadOnlyPaths=`, `PrivateTmp=`) prevent cross-runtime read/write through normal DAC. Because all five runtimes share the `devassist` uid, the isolation is **conditional on correct systemd unit configuration**; a hostile intra-runtime actor is out of the v0.1 single-Founder threat model. The PRD § 13.2 strict isolation requirement is satisfied by the Hermes layout plus systemd sandboxing, not by a custom memory broker (`RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 6.2).

### 11.2 Inter-Runtime IPC

Inter-runtime work is dispatched through a `work_items` table in the existing SQLite operational store (`OPERATIONAL-STATE-STORE.md`, extended schema in `MULTI-HERMES-CONTRACT.md` § 6.2). The Orchestrator writes work items; specialist runtimes claim, complete, or release them.

ADR-006 records the IPC choice; the alternatives considered (A2A-over-HTTP between runtimes, Redis/NATS message bus, Hermes MCP HTTP servers) are documented and rejected for v0.1.

### 11.3 Shared Skills And Plugins

Custom skills and the escalation-policy plugin live in shared locations:

- **Skills**: `/srv/devassist/shared-skills/` is added to each runtime's `skills.external_dirs` config. Custom `dev-assist-*` skills (writers, work-queue pollers, escalation surfacers) are written once and loaded by every runtime that needs them. Per-role specialization is via `requires_toolsets` / `fallback_for_toolsets` in each skill's manifest.
- **Plugins**: `/srv/devassist/shared-plugins/` holds Python plugin packages installed via pip into the Hermes virtualenvs. The `dev-assist-escalation-policy` plugin is loaded into all five runtimes; the `dev-assist-work-queue` plugin is loaded into all five runtimes; both gate behavior on `HERMES_DEVASSIST_ROLE`.

The set of skills enabled per runtime is in `MULTI-HERMES-CONTRACT.md` § 5.

### 11.4 Self-Learning State Preservation

Each runtime's `MEMORY.md`, `USER.md`, and sessions database (`~/.hermes/state.db`) are part of its self-learning state. Self-deployment rollback and upgrade preserve these per runtime, alongside the shared **operational store** (`/srv/devassist/state/operational.db`, see `SELF-DEPLOYMENT-CONTRACT.md` § 7).

## 12. Skills And Plugins Per Role

Detailed loadout in `MULTI-HERMES-CONTRACT.md` § 5; summary table:

| Role | Hermes built-in skills enabled | Custom dev-assist skills loaded | Plugins loaded |
| --- | --- | --- | --- |
| Orchestrator | `telegram-gateway`, `cronjob`, `memory` | `dev-assist-classifier`, `dev-assist-progress-report`, `dev-assist-escalation-surface`, `dev-assist-work-queue-write` | `dev-assist-escalation-policy`, `dev-assist-work-queue` |
| Business Planner | `cronjob`, `memory` | `dev-assist-prd-writer`, `dev-assist-questions-writer`, `dev-assist-work-queue-poll` | `dev-assist-escalation-policy`, `dev-assist-work-queue` |
| Architect | `cronjob`, `memory` | `dev-assist-arch-writer`, `dev-assist-adr-writer`, `dev-assist-tickets-writer`, `dev-assist-work-queue-poll` | `dev-assist-escalation-policy`, `dev-assist-work-queue` |
| Executor | `terminal` (Docker backend), `cronjob`, `memory` | `dev-assist-executor-discipline`, `dev-assist-write-zone-enforcer`, `dev-assist-github-workflow`, `dev-assist-work-queue-poll` | `dev-assist-escalation-policy`, `dev-assist-work-queue` |
| Reviewer | `terminal` (Docker backend, read-only mounts), `cronjob`, `memory` | `dev-assist-reviewer-rubric`, `dev-assist-review-writer`, `dev-assist-work-queue-poll` | `dev-assist-escalation-policy`, `dev-assist-work-queue` |

The bundled Hermes `github-pr-workflow`, `github-issues`, and `github-auth` skills remain BLOCKED for production credentials (`HERMES-SKILL-ALLOWLIST.md` § 4.2-4.4). The Executor runtime uses a project-specific `dev-assist-github-workflow` skill that wraps the project's reviewed REST API + git orchestration code (per `HERMES-RUNTIME-CONTRACT.md` § 9 Constraints).

`delegate_task` is **not loaded** in v0.1 production runtimes (`HERMES-SKILL-ALLOWLIST.md` § 4.5 keeps it BLOCKED for credential-bearing production until subagent isolation is confirmed). Cross-role work flows through the SQLite work queue, not through `delegate_task`.

`skill_manage` (agent-managed runtime skill creation) is disabled in v0.1 production. Open research item in `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 7.

## 13. Upstream Entry-Point Abstraction

Detailed contract in `UPSTREAM-ADAPTER-CONTRACT.md`; summary:

- v0.1 ships exactly one upstream adapter: **Telegram**, implemented inside the Orchestrator runtime as the `telegram-gateway` skill plus the `dev-assist-classifier` and `dev-assist-escalation-surface` custom skills.
- The abstraction defines five operations: **inbound** (deliver Founder message to Orchestrator), **outbound** (send Orchestrator message to Founder), **approval prompt** (deliver an `escalations` row to Founder and capture a yes/no/answer response), **identity binding** (map upstream identity to internal Founder identity), **session continuity** (resume an ongoing session).
- v0.2+ adds OpenClaw (or any A2A-compliant peer) as a parallel upstream adapter inside the Orchestrator runtime. Specialist runtimes are not modified.
- Whether v0.2 simultaneously runs Telegram and OpenClaw, or switches between them, is open in `PRD-001.md` § 10 Q18; ADR-007 records the chosen abstraction shape, not the v0.2 routing policy.

## 14. Self-Deployment Architecture

Detailed contract in `SELF-DEPLOYMENT-CONTRACT.md`; summary of the architectural shape:

- **Mechanism (ADR-004)**: idempotent bash bootstrap script (`scripts/install-self.sh`) that lays down filesystem layout, installs Hermes once at `/usr/local/lib/hermes-agent/`, creates five per-runtime `HERMES_HOME` directories under `/srv/devassist/runtimes/<role>/.hermes/`, renders systemd unit templates, writes the umbrella `devassist.target`, and runs preflight health checks. systemd supervises the runtimes; Docker is used only inside the Executor and Reviewer terminal sandboxes.
- **Approval gates**: `install` runs without approval; `start` requires explicit Founder approval (the install script leaves all units in `inactive` state); `upgrade` requires explicit Founder approval AND a state-store backup taken before the upgrade begins (`SELF-DEPLOYMENT-CONTRACT.md` § 6).
- **Health check (`scripts/verify-self.sh`)**: connectivity-only invariant set per `PRD-001.md` § 10 Q12 recommendation: Telegram reachable, GitHub PAT valid, OmniRoute reachable, state store writable and at expected schema version, each systemd unit `active (running)`, no secrets in `journalctl` output. Returns non-zero on failure with a human-readable summary.
- **Rollback (`scripts/rollback-self.sh`)**: stop all units, restore the last `operational.db` backup snapshot (the shared operational store at `/srv/devassist/state/operational.db`), restore last known-good runtime config tarball, restart units. Operational data needed to resume project bindings, scheduled progress timers, and in-flight Hermes run metadata is preserved. Per-runtime `state.db` (Hermes native sessions database) is preserved per runtime under each `HERMES_HOME`.
- **Repeatability**: the install script is safe to re-run on an already-installed VPS without duplicating runtime processes or corrupting the operational state store (PRD § 9 success criterion).
- **Secrets**: a single `/srv/devassist/secrets/SELF-DEPLOY.env` (mode 0600, owner `devassist:devassist`) is the only place secret values exist on disk; the install script reads it and renders systemd `EnvironmentFile=` directives that point at it. Secrets never enter committed config, repository artifacts, logs, PR artifacts, review artifacts, or shell history.

## 15. Escalation Policy Architecture

Detailed contract in `ESCALATION-POLICY.md` v0.1.1; summary:

- The PRD § 13.1 trigger pair ("deviates from concept" OR "risks breaking already-committed scope or operational state") is operationalized as two **fully deterministic** enforcement layers, both running inside the `dev-assist-escalation-policy` Hermes plugin loaded into every specialist runtime:
  - **Deterministic rule set** (`ESCALATION-POLICY.md` v0.1.1 § 4): a curated pattern list (force-push, hard reset, file deletion under governance directories, schema-destructive SQL, credential rotation, public endpoint exposure, paid third-party introduction, write-zone violations, PRD/ADR status flips, concept-anchor edits, etc.). Match → escalate, no further checks.
  - **Deterministic concept-deviation classifier** (`ESCALATION-POLICY.md` v0.1.1 § 5): when no § 4 rule matches and the action is not read-only or within-catalog, the classifier compares the candidate action against a structured project-concept anchor (`PROJECT-CONCEPT.md` § 2) using a fully-specified pure-function predicate set. Same input always yields the same verdict; **no LLM call inside the decision path** (RV-SPEC-012 F3 fix).
- Both layers run at the Hermes `pre_tool_call` hook, so they pre-empt the Hermes-level approval prompt rather than relying on it.
- An escalation appends a row to the SQLite `escalations` table; the Orchestrator runtime polls the table and surfaces pending escalations to Telegram.
- The Founder's response is captured back into the originating runtime's work item and into the durable artifact target the escalation declared (PRD, `docs/questions/`, ADR, or ticket).
- The plugin MAY invoke the runtime's catalog main model from `MODEL-CATALOG.md` v0.1.1 § 4.1 to generate a Russian-language advisory narrative on the escalation surface (`ESCALATION-POLICY.md` v0.1.1 § 5.5). This narrative is **NOT in the decision path** — the deterministic classifier has already returned `ESCALATE` before the call is made; the call is best-effort with a deterministic English fallback narrative on timeout/failure.
- ADR-008 v0.1.1 records the classifier-mechanism choice (deterministic rules + structured concept anchor; no LLM in the decision) and the v0.1.1 history (Option B — the v0.1.0 "deterministic + LLM classifier" design — was rejected by RV-SPEC-012 F3).

## 16. Model Catalog Architecture

Detailed catalog in `MODEL-CATALOG.md` v0.1.1; summary:

- The Founder pre-approved a role-model assignment on 2026-05-05 and refined it on 2026-05-06 via ADDENDUM-001, which (a) replaced the placeholder identifiers with five Fireworks-hosted models reachable through OmniRoute, (b) waived per-token cost optimization within the catalog, and (c) made the routing-layer mandate explicit (Option B). The v0.1.1 catalog encodes this set; the cost-posture rewrite ADDENDUM-001 also requires lands as v0.2.0 in PR-E.
- **Per-role assignment, capability-only ordering** (`MODEL-CATALOG.md` v0.1.1 § 4.1): identifiers are real OmniRoute Fireworks-native paths (`accounts/fireworks/models/<slug>`), NOT placeholders. Runtimes: `orchestrator` → `minimax-m2p7`; `business-planner` → `qwen3p6-plus`; `architect` → `deepseek-v4-pro`; `executor` → `glm-5p1`; `reviewer` → `kimi-k2p6`. Each role has a 4-entry chain (main + 3 fallbacks) ordered by capability fit alone.
- **No separate auxiliary classifier model in v0.1**: the v0.1.1 escalation classifier is deterministic (`ESCALATION-POLICY.md` v0.1.1 § 5; ADR-008 v0.1.1) with no LLM in the decision; the optional advisory narrative (§ 5.5) reuses the runtime's catalog main model.
- **Within-catalog model picks proceed without escalation**. Catalog changes (adding a new model, changing a role's main, changing a role's fallback, changing the routing layer, switching the Fireworks backend) escalate per `ESCALATION-POLICY.md` v0.1.1 § 4.6.
- Models are reached through OmniRoute (primary, with Fireworks as configured backend) and OpenRouter (backup); specialist runtimes never import a Fireworks SDK or hit `api.fireworks.ai` directly. This decouples runtime config from any single provider's API shape and keeps the v0.1 budget envelope inside the already-approved LLM API spend. **Verification gate**: the TKT-026 install verify script issues a 1-token completion against `http://127.0.0.1:<omniroute_port>/v1/chat/completions` for each catalog identifier at install/upgrade; failure raises `paid:third_party_external_service_not_yet_supported` with no silent fallback to direct-Fireworks (binding precondition recorded in ADR-011, lands in PR-E). OmniRoute-supports-Fireworks gate verified 2026-05-06 via OmniRoute issue [#265](https://github.com/diegosouzapw/OmniRoute/issues/265) (closed; mainteiner confirmed: "send the Fireworks path as model ID and OmniRoute auto-resolves it").
- ADR-009 v0.1.1 records the catalog-as-architecture-document choice (with real OmniRoute Fireworks identifiers; no auxiliary classifier model in v0.1; ADDENDUM-001 cost-posture override applied).

## 17. CI And Validation

The v0.1 CI baseline runs:

- `python scripts/validate_docs.py`.
- Project tests when production code exists.
- Lint/typecheck when configured by implementation tickets.
- Static/security checks selected by architecture or security tickets.
- `pr-agent` review on every pull request (configured per `.pr_agent.toml`).

Required CI checks for `main` and PR branches: `validate-docs` and `Run PR Agent on every pull request`. Both must reach `conclusion: success` before declaring a PR ready for Founder merge.

Docs validation should check frontmatter, required ticket sections, ADR structure, and gradually add cross-link and status validation.

## 18. Generated Project Contract

Generated projects are distinct from the assistant itself. Their contract is `docs/architecture/GENERATED-PROJECT-DEPLOYMENT-CONTRACT.md` (v0.1.0 active) and remains unchanged by this revision. Generated projects must include:

- `README.md` with purpose, status, and local run instructions.
- `CONTRIBUTING.md` with role/write-zone rules.
- `AGENTS.md` for agent operating rules.
- `docs/prd/`, `docs/architecture/`, `docs/tickets/`, `docs/reviews/`, `docs/questions/`, `docs/orchestration/`.
- CI workflow running docs validation and relevant application checks.
- PR and review templates.
- Handoff notes and known risks.
- A documented one-command VPS deployment entry point, such as `make deploy` or an equivalent script, with final live execution requiring founder approval.

The assistant's own self-deployment is governed by `SELF-DEPLOYMENT-CONTRACT.md` and is **not** the same surface as the generated-project deployment contract.

## 19. Implementation Ticket Strategy

This pass produces TKT-020 through TKT-026 (seven tickets) covering self-deployment bootstrap, multi-Hermes runtime layout, work-queue persistence, escalation enforcement, upstream-adapter scaffolding, shared custom skills, and model-catalog enforcement helper. The tickets remain `draft` until the Founder approves this revised architecture and Reviewer LLM passes (or pass_with_changes) RV-SPEC review.

These tickets must be implemented and merged before TKT-011 (the first end-to-end Telegram-to-PR orchestration trial) is dispatched, because TKT-011 requires a deployed Hermes runtime to begin from. Sequencing constraint: this ARCH-001 v0.3.0 pass → RV-SPEC review → Founder merge → TKT-020-026 dispatch and merge → TKT-011 dispatch.

Parallelization within TKT-020-026: tickets are mostly independent and can be worked in parallel where the Orchestrator-of-tickets allows. The dependency graph is:

```
TKT-020 (self-deployment bootstrap)  ─┐
TKT-021 (multi-Hermes layout)        ─┼─►  TKT-011 (Telegram-to-PR trial)
TKT-022 (work_items + escalations)   ─┤
TKT-023 (escalation plugin)          ─┤
TKT-024 (upstream-adapter scaffolding)┤
TKT-025 (shared custom skills)       ─┤
TKT-026 (model-catalog helper)       ─┘
```

TKT-020 and TKT-021 are the entry tickets (no upstream dependencies in this set). TKT-022 depends on TKT-021. TKT-023 depends on TKT-022. TKT-024 depends on TKT-021. TKT-025 depends on TKT-021. TKT-026 depends on TKT-021. All seven must merge before TKT-011 is dispatched.

## 20. Research Findings Summary

The full research record is `RESEARCH-001-hermes-and-openclaw-ecosystems.md`. The structurally-load-bearing findings used by this revision:

- A Hermes installation is one OS-level process; multiple specialist runtimes require multiple installations supervised externally (RESEARCH-001 § 3.2).
- Per-runtime memory isolation is physical (separate `~/.hermes/` directories), not implemented through a custom broker (§ 3.5, § 6.2).
- Cross-runtime IPC is best mediated by the existing SQLite operational store rather than by introducing A2A-over-HTTP, Redis, or NATS for v0.1 (§ 3.10, § 5.3, § 6.3).
- Escalation enforcement belongs in a Hermes plugin layer, pre-empting Hermes' own approval prompt (§ 3.8, § 3.9, § 6.4).
- Telegram stays on the Orchestrator runtime only; the upstream-adapter abstraction lives above the specialist runtimes so OpenClaw can be added without changing them (§ 3.7, § 4.3, § 6.5).
- systemd is the v0.1 supervisor of choice for a $5/month-class VPS; Docker Compose and s6-overlay remain documented alternatives (§ 5.2, § 6.6).
- Within the Founder-pre-approved catalog, model picks are autonomous; catalog changes escalate (§ 5.4, § 6.7).
- No paid third-party hard dependencies in v0.1 (§ 5.5, § 6.8).

## 21. Future Possibilities

These are explicitly NOT v0.1 commitments. They are recorded so the design space is visible without committing the v0.1 budget envelope to them.

- **Paid sandbox terminal backends** (`modal`, `daytona`, `vercel_sandbox`) for Executor work needing larger or specialized environments. Trigger: a generated project whose build cannot fit the local Docker backend.
- **OpenClaw upstream adapter**: v0.2+ alongside Telegram per `PRD-001.md` § 13.3. Trigger: Founder begins using OpenClaw as a general assistant and wants to delegate project-creation tasks from there.
- **A2A protocol** (`https://a2a-protocol.org/`) as the upstream surface for any external agent (OpenClaw included) calling into `developer-assistant`'s Orchestrator runtime. Trigger: a second external upstream beyond OpenClaw enters the picture.
- **Cross-runtime MCP servers** for tighter intra-system tool sharing (e.g., letting the Reviewer runtime call a tool exposed by the Architect runtime). Trigger: the SQLite work queue proves insufficient for a class of cross-runtime work that requires synchronous response.
- **Vector store for skill memory** (sqlite-vec, pgvector, or hosted) for richer per-runtime self-learning. Trigger: `MEMORY.md` capacity ceiling becomes a measured constraint, not a speculative one.
- **Auto-start on VPS reboot** (currently manual per `PRD-001.md` § 10 Q13 default). Trigger: first stable trial completes and the Founder approves weakening the explicit-start gate.
- **Webhook mode for Telegram gateway** (currently polling per `HERMES-SKILL-ALLOWLIST.md` § 4.1). Trigger: Founder approves opening an inbound port on the VPS.
- **Multi-tenant isolation**: explicitly out of v0.1 scope per `PRD-001.md` § 4. Trigger: the assistant graduates beyond one Founder.

## 22. Remaining User Decisions

The following decisions are open but do not block approval of this architecture:

1. Exact Telegram command set and whether free-form chat is allowed beyond the hybrid model in § 7.
2. ~~Whether the lightweight web interface is deferred, read-only, or still required in v0.1 after Telegram is working.~~ Closed by ADR-013 (`docs/architecture/adr/ADR-013-web-interface.md`): read-only `dev-assist-cli serve-web` HTTP surface on `127.0.0.1:8180`. See § 24.
3. Whether the v0.2 upstream-adapter layout supports simultaneous Telegram + OpenClaw or one-at-a-time switchable per `PRD-001.md` § 10 Q18 (architecture supports both; the routing policy is a v0.2 product decision).
4. Auto-start on reboot vs manual-start per `PRD-001.md` § 10 Q13 (default: manual).
5. Webhook vs polling mode for Telegram gateway per `HERMES-SKILL-ALLOWLIST.md` § 4.1 (default: polling).
6. Catalog-refresh cadence for `MODEL-CATALOG.md` (default: refresh on Founder request).
7. Whether `skill_manage` (agent-managed runtime skill creation) is enabled under supervisory-only review in a future iteration (default: disabled in v0.1 production).

## 23. Observability Summary

Detailed contracts in `OBSERVABILITY-CONTRACT.md` v0.1.1 and `OPERATIONAL-STATE-STORE.md` v0.3.0; rationale in ADR-010 (observability shape). This section ties the pieces together so a reader of ARCH-001 alone understands the observability story without opening five sub-documents.

The v0.1 commitment is **on-VPS only** observability per ADDENDUM-001 § 2.1 (Founder, 2026-05-06): no paid services, no extra daemons beyond the seven systemd units already approved (`devassist.target`, five specialist runtimes, `omniroute.service`, plus `devassist-web.service` per ADR-013). Three primitives carry the load — systemd journald (structured logs with retention), SQLite (three observability tables co-located with `work_items` and `escalations` in the shared `operational.db`), and cron (system-cron for log retention / aggregate writes; Hermes-cron for the daily Telegram digest because that one needs the Orchestrator's LLM context).

The five Hermes specialist runtimes are instrumented at the **client side** (RV-SPEC-014 M-001 fix): every LLM call goes through a thin Python wrapper around the OmniRoute / OpenRouter HTTP client (`src/developer_assistant/observability/llm_client_instrumentation.py`) that records one row per call to the `llm_calls` table — `runtime_role`, `work_item_id`, `model_id`, `routing_path`, `tokens_in`, `tokens_out`, `latency_ms`, `cost_usd`, `status`, `error_class`. Cost is computed from `MODEL-CATALOG.md` v0.2.0 § 4.1 rate snapshots via the catalog parser from TKT-026. The wrapper is owned by an `ObservabilityManager` class (RV-SPEC-014 M-003 fix; `OBSERVABILITY-CONTRACT.md` v0.1.1 § 14) instantiated once per runtime at startup; the class also owns the per-runtime localhost-only `GET /health` endpoint (`127.0.0.1:8181..8185`) and the structured-logging context (work-item-id propagation through the work queue).

Errors land in the `errors` table via `ObservabilityManager.record_error(...)`; the `llm_calls_daily` aggregate table is rolled up by a system-cron job once per UTC day for the Telegram digest path. journald keeps structured stdout/stderr from each unit per FR-OBS-09a (`/etc/systemd/journald.conf.d/dev-assist.conf` with `SystemMaxUse=1G`, `MaxRetentionSec=30d`); the SQLite tables are pruned per FR-OBS-09b by the same cron set, with FR-OBS-09c covering the install-time verification that the retention config landed.

An **OmniRoute server-side middleware** (`src/developer_assistant/observability/omniroute_middleware.py`) is the SECONDARY / OPTIONAL observability path per RV-SPEC-014 M-001. The middleware is only implemented if the OmniRoute v3.7.x extension API is verified by reading the OmniRoute source code; the verified API version is recorded in ADR-011's Consequences section. If verified, the middleware adds parallel rows from OmniRoute's perspective (useful as a cross-check). If not verified, this module is omitted entirely from v0.1 and the client-side instrumentation is the single source of truth for `llm_calls`. The decision is recorded in TKT-031's § 10 Execution Log.

Founder-facing surfaces are three: (1) the operator CLI `dev-assist-cli` (TKT-027) reads journald and `operational.db` directly and works even when runtimes are down; (2) the daily Telegram digest sent by the Orchestrator's Hermes-cron entry summarizes per-runtime per-model spend (FR-OBS-05); (3) the read-only web surface `dev-assist-cli serve-web` on `127.0.0.1:8180` (ADR-013) renders the same data as the CLI in browser-loadable form. All three consume the same backing functions; they cannot diverge. Cross-runtime correlation is via `work_item_id` propagated through the work queue and into log lines — no distributed-tracing infrastructure is added. `RECOVERY-PLAYBOOK.md` (PR-E) is the operator-facing runbook integrating CLI, health endpoints, and journalctl/SQLite tooling into recovery actions.

Implementation tickets: TKT-027 (CLI + web subcommand), TKT-028 (structured logger + work-item-id header injector), TKT-029 (daily digest renderer + Telegram `/status`), TKT-030 (recovery-playbook discipline harness), TKT-031 (errors + llm_calls + llm_calls_daily tables, client-side LLM instrumentation, ObservabilityManager, per-runtime health endpoints).

## 24. Web Interface Architecture

Detailed rationale in ADR-013 (`docs/architecture/adr/ADR-013-web-interface.md`); summary:

`PRD-001.md` v0.2.1 § 6 mandates a "lightweight web interface" alongside Telegram. v0.1 satisfies this with the **smallest surface that meets the requirement without violating ADDENDUM-001 § 2.1** (no extra daemons / no paid services): a single read-only HTTP status page served by `dev-assist-cli serve-web` on `127.0.0.1:8180`. Browser access from outside the VPS is via SSH tunnel (`ssh -L 8180:127.0.0.1:8180 founder@vps`) or a Founder-added `ufw` rule; no auth at the application layer, no session, no cookies, no write paths.

The same `dev-assist-cli` binary that powers the operator CLI also serves the web surface. Each request is a fresh server-side render reading journald via `journalctl --output=json` and the existing `operational.db` tables (`work_items`, `escalations`, `errors`, `llm_calls`, `llm_calls_daily`). Two response formats: `Accept: text/html` returns the HTML page; `Accept: application/json` returns the same shape `dev-assist-cli status --format json` returns. Both views call the same backing function so they cannot diverge. No JS framework, no WebSocket, no streaming; auto-refresh is a stock `<meta http-equiv="refresh" content="30">` tag on an opt-in path.

Pending-escalation **content** is intentionally Telegram-only (`ESCALATION-POLICY.md` § 7); the web surface shows only the count and oldest pending timestamp. This means an attacker who reaches port 8180 sees no escalation prompt content, and the Founder loses no governance fidelity by reading the web surface (the full Founder-approval loop stays on Telegram). Port 8180 sits one below the per-runtime health-port range 8181..8185 so the firewall and Founder mental model stay coherent; allocations outside `127.0.0.1:8180..8189` trip `net:public_endpoint_exposure` (`ESCALATION-POLICY.md` § 4.5) and require Founder approval.

Lifecycle is a separate systemd unit `devassist-web.service` (`SELF-DEPLOYMENT-CONTRACT.md` v0.2.0 § 5.4) running `/opt/dev-assist/bin/dev-assist-cli serve-web --port 8180` as the `devassist` user with the same sandbox directives the specialist runtimes use. The verify script's invariant set (`SELF-DEPLOYMENT-CONTRACT.md` v0.2.0 § 8) probes `http://127.0.0.1:8180/health` on every install/upgrade. Implementation lives inside TKT-027 (CLI) — no separate ticket is created because the web surface adds <300 lines of stdlib HTTP code on top of TKT-027's existing data-collection helpers.
