---
id: ARCH-002
version: 0.1.0
status: draft
arch_ref: ARCH-001@0.3.0
audit_ref: RESEARCH-002@0.1.0
updated: 2026-05-10
---

# ARCH-002: Multi-Agent Synthesis (RESEARCH-002 downstream)

## 1. Purpose And Position

This document is the architectural synthesis cycle downstream of `RESEARCH-002-multi-agent-dev-systems-survey.md`. It maps the Researcher's 31-repository breadth scan against the project's ten pain points (RESEARCH-002 § 3, App-1..10), answers the Researcher's six open architectural questions (RESEARCH-002 § 9, Q-RESEARCH-002-01..06), proposes targeted amendments to existing contracts, drafts new ADRs (status: proposed) and tickets (status: draft) for downstream Executor cycles, and surfaces residual decisions for the Founder (Q-ARCH-002-NN).

ARCH-002 is a sibling document to `ARCH-001.md` v0.3.0, not a replacement. The choice is deliberate: ARCH-001 is cohesive (407 lines, 14 ADRs, 13 boundary contracts, all five surveyed-architecturally-adjacent decisions named), and the survey did not surface a structural gap that demands an ARCH-001 v0.4.0 rewrite. Where the survey produces concrete deltas, this document references the existing contract clause being amended (`MULTI-HERMES-CONTRACT.md § <n>:L<a>-L<b>`) and states the proposed change inline; the actual contract files remain authoritative until the new ADRs are promoted to `accepted` and the contract amendments land via downstream Executor cycles.

## 2. Founder Mandate

The Founder authorized this synthesis cycle on 2026-05-10 with the following directive (verbatim Russian, NUDGE § 4.4):

> «даже если изменения будут очень серьезными и многое перепишут — принимаем»

Translation for downstream agents: *"even if changes are very serious and rewrite much — we accept"*. This is permission to state strong opinions, name preferences, and explicitly reject patterns that don't fit the project, with rationale. Per NUDGE § 12.1 the Researcher kept neutral cataloging tone; this synthesis takes the opposite posture — the Researcher mapped the option space, the Architect picks within it.

Per NUDGE § 12.2 the failure mode to guard against is over-engineering. The survey shortlist (RESEARCH-002 § 8) is tempting — Gas Town's hook system is elegant, AgentsMesh's PodBinding zero-trust model is rich, OpenCastle's Convoy Engine is concise, Bernstein's sandbox capability protocol is portable. This synthesis adopts a small bounded set (four ADRs, six tickets) and explicitly defers the rest. A focused synthesis is better than a kitchen-sink amendment.

## 3. Pain-Point Gap Analysis

For each of the ten Researcher pain-point codes (RESEARCH-002 § 3), this section states (a) where our project stands today, (b) which surveyed repos handle the pain well per Researcher's evidence, and (c) what to adopt, adapt, or explicitly NOT adopt with rationale.

### 3.1 App-1 — Role separation

**Current state.** Five specialist Hermes runtimes (`MULTI-HERMES-CONTRACT.md` v0.2.1 § 2:L17-L31), each with its own `HERMES_HOME`, `MEMORY.md`, `USER.md`, sessions database, and systemd unit. Filesystem-level memory isolation enforced by systemd sandbox directives (`ARCH-001.md` v0.3.0 § 11.1:L211). Role write zones enforced by `CONTRIBUTING.md` § Roles plus the `dev-assist-write-zone-enforcer` skill (`MULTI-HERMES-CONTRACT.md` § 5.4:L156). Three orchestrator roles (Strategic, Ticket, Runtime) are kept *intentionally* separate per `AGENTS.md`. This is among the strongest implementations in the survey set.

**Surveyed repos handling this well.** Gas Town defines a four-layer role hierarchy with persistent identity ledger (`gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L25-L53`). ORCH validates state-machine transitions per role (`ORCH@0c0694896b3a:CLAUDE.md:L49-L52`). Codebuff names sixteen+ specialist agents with explicit template-vs-programmatic distinction (`codebuff@54df847c6384:docs/architecture.md:L83-L97`, `codebuff@54df847c6384:docs/architecture.md:L224-L231`). RA.Aid uses a three-stage Research/Planning/Implementation split (`RA.Aid@e71bb83dcfdf:README.md:L60-L90`).

**Adopt / Adapt / Reject.**

- **Adopt:** Gas Town's *role-bound work-routing* heuristic — "if work is on an agent's hook, the agent must run it" (`gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L64-L82`). Our SQLite work-queue claim model already implements the structural shape (`MULTI-HERMES-CONTRACT.md` § 6.2:L194-L218); adopt the *vocabulary* "role-bound work item" and codify that no work item is ever runtime-agnostic in the queue. Amendment in § 6.1 below.
- **Adapt:** Gas Town's persistent role-identity ledger separated from session transcripts is structurally what we already do (`MEMORY.md` plus `state.db` per runtime), but we don't capture *closed-bead* completions as a durable per-role capability log. Convert this into the freshness-ledger primitive proposed for Q-RESEARCH-002-06 (§ 5.6, ADR-018).
- **Reject:** Codebuff's "shipped agents" registry model (`codebuff@54df847c6384:docs/architecture.md:L70-L81`). Our `HERMES-SKILL-ALLOWLIST.md` v0.1.2 § 2 is deny-by-default; a registry-backed template surface is incompatible with that posture and would require ADR-003 superseding work that v0.1 does not budget for.

### 3.2 App-2 — Orchestration loop / state machine

**Current state.** SQLite-mediated work-queue (`ARCH-001.md` § 11.2:L213-L218, `MULTI-HERMES-CONTRACT.md` § 6.2). Claim/complete/release semantics with rolling 30-minute lease and 60-second polling; lease-reclaim sweep at 5-second cadence (ADR-006 § Decision). State transitions per work item are: `pending → claimed → completed | failed | released`. A separate `escalations` queue surfaces Founder prompts. Three orchestrator-of-tickets roles (SO, TO, Hermes runtime orchestrator) sit above the queue with their own state — SESSION-STATE.md tracks current phase as a human-readable narrative.

**Surveyed repos handling this well.** ORCH defines a validated task lifecycle `todo → in_progress → review → done | failed | cancelled` with explicit retrying and failed branches (`ORCH@0c0694896b3a:CLAUDE.md:L49-L52`) and a three-phase tick loop *Reconcile → Dispatch → Collect* with state mutation serialized behind a promise-chain mutex (`ORCH@0c0694896b3a:CLAUDE.md:L53-L61`). OpenCastle's Convoy Engine is a deterministic crash-recoverable orchestrator with YAML task graphs and SQLite WAL persistence (`opencastle@18c6f2cf4e5c:README.md:L155-L204`). Bernstein has a deterministic CLI-agent orchestrator with `.sdd/` WAL plus artifact sinks (`bernstein@f950c71eddf0:docs/architecture/storage.md:L1-L14`). RA.Aid stages Research/Planning/Implementation with multi-step task execution (`RA.Aid@e71bb83dcfdf:README.md:L60-L90`).

**Adopt / Adapt / Reject.**

- **Adopt:** ORCH's three-phase tick-loop *vocabulary* (Reconcile → Dispatch → Collect) for the `dev-assist-work-queue` plugin's polling cadence. Today the plugin polls `pending` rows and claims them; making the three phases explicit names what already happens and gives operators clearer log markers. Amendment in § 6.1 below.
- **Adopt:** ORCH's terminal-states triple — `done`, `failed`, `cancelled` — to extend our current `completed | failed | released` set. Specifically: a work item the Orchestrator decides to abandon (e.g., ticket no longer relevant after a Founder pivot) needs a `cancelled` terminal state distinct from `failed` (which implies retry exhaustion). Amendment in § 6.1.
- **Defer:** OpenCastle Convoy YAML workflow definitions for declared multi-ticket batches (`opencastle@18c6f2cf4e5c:README.md:L155-L190`). The pattern is elegant for known-multi-ticket sequences (e.g., the historical TKT-020-026 chain), but our SO already produces these sequences as plain SESSION-STATE narrative + per-ticket `work_items` rows; introducing a YAML schema and convoy-interpreter logic is a new surface for marginal v0.1 value. **Trigger to revisit:** first explicit batch of ≥5 dependent tickets that the SO would otherwise track only in prose. Recorded in § Future Possibilities.
- **Reject:** Bernstein's full WAL + audit ledger replacement of our SQLite operational store. We have ADR-002 + ADR-006 already; a WAL replacement adds storage primitives without solving a problem we have. Bernstein's *sandbox* abstraction is adopted separately (§ 3.6, ADR-015), but its storage layer is not.

### 3.3 App-3 — Cross-model or cross-agent review

**Current state.** Three independent review surfaces per PR. (1) GitHub Actions CI runs `validate-docs` plus configured tests/lint (`ARCH-001.md` § 17:L296-L304). (2) Qodo PR-Agent (DeepSeek V4 Pro main, Qwen3.6-Plus fallback per ADR-012) auto-reviews every PR. (3) Reviewer Hermes runtime (Kimi K2.6 main, Moonshot family — non-Anthropic, non-DeepSeek per `AGENTS.md` cross-model independent review doctrine) writes a verdict artifact under `docs/reviews/`. The cross-model defense-in-depth — Anthropic-family agents producing artifacts, DeepSeek-family PR-Agent reviewing, Moonshot-family Reviewer verifying — is among the strongest in the surveyed set.

**Surveyed repos handling this well.** OpenCastle names quality gates as part of the product: fast review after every step, panel majority vote for high-stakes changes, lint/test/build checks (`opencastle@18c6f2cf4e5c:README.md:L114-L122`). kodo frames orchestration as solving verification gaps (`kodo@9758a0a1d0b1:docs/orchestration-tenets.md:L11-L13`). Every Code runs Auto Review in parallel with Auto Drive in separate worktrees (`code@861c9bab69d7:README.md:L29-L33`). Ralph's backpressure gates reject incomplete work for tests, lint, and typecheck (`ralph-orchestrator@3eca5177db33:README.md:L136-L142`). CLITrigger pairs parallel worktree execution with holistic diff/log review (`CLITrigger@fd4731bb3e20:README.md:L92-L103`).

**Adopt / Adapt / Reject.**

- **Adopt:** Ralph's *backpressure-gate* vocabulary (`ralph-orchestrator@3eca5177db33:README.md:L136-L142`). Currently `ARCH-001.md` § 17 names "validate-docs and Run PR Agent on every pull request" as required CI checks, and the Reviewer prompt names verdict types — but the connection between gate failures and work-queue back-pressure is implicit. Make it explicit: the work-queue dispatcher MUST NOT promote a `ticket_review` work item to `completed` while any required CI check is `conclusion: failure`. ADR-016 promotes this to architectural rule rather than Reviewer-prompt convention.
- **Adopt:** OpenCastle's "panel majority vote for high-stakes changes" *as the existing Anthropic+DeepSeek+Moonshot triangle* (`AGENTS.md` cross-model independent review doctrine), without adding a new vote-aggregation surface. The triangle already exists; ADR-016 records it as architectural commitment rather than informal practice.
- **Reject:** OpenCastle's panel-majority-vote *implementation* (`opencastle@18c6f2cf4e5c:README.md:L116`) as a per-decision automated mechanism. v0.1 keeps the Founder as the merge gate (`ARCH-001.md` § 9:L168-L171); a panel-vote auto-merge surface conflicts with `PRD-001.md` § 4 ("Guarantee that generated implementation is correct without CI, review, and explicit user approval" is a non-goal — i.e., explicit user approval IS required).

### 3.4 App-4 — Persistent state / durable memory

**Current state.** Repository artifacts (`docs/`) are authoritative for governance state; SQLite operational store at `/srv/devassist/state/operational.db` carries operational state (project bindings, scheduled progress timers, work_items, escalations, hermes_runs, idempotency_keys); per-runtime `MEMORY.md` and `state.db` hold runtime self-learning state, isolated by filesystem (`ARCH-001.md` § 8:L133-L154). ADR-002 names this split. The shape is clean by design.

**Surveyed repos handling this well.** ORCH stores all state in `.orchestry/`, with YAML for tasks/agents/goals/teams, JSON+JSONL events, atomic writes, tail reads (`ORCH@0c0694896b3a:CLAUDE.md:L69-L81`). Bernstein persists `.sdd/` WAL, audit logs, runtime state, outputs, cost ledger, metrics, with artifact sinks for S3/GCS/Azure/R2 (`bernstein@f950c71eddf0:docs/architecture/storage.md:L1-L14`). Gas Town uses Dolt+beads+git for persistent identity/work hooks (`gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L45-L53`). Letta Code persists agent memory across sessions and models with `/init`, `/remember`, `/skill` commands (`letta-code@afac21583850:README.md:L25-L55`). OpenHands stores reusable repository knowledge in `.openhands/microagents/repo.md` with explicit confirmation gates before saving (`OpenHands@9482ab1a666d:skills/agent_memory.md:L10-L30`).

**Adopt / Adapt / Reject.**

- **Adopt:** OpenHands' confirmation-gated repo-memory pattern (`OpenHands@9482ab1a666d:skills/agent_memory.md:L23-L30`) as the *governance* model for any future automated `MEMORY.md` writes. Today the runtimes can write to their own `MEMORY.md` without artifact-level governance; OpenHands' "ask user, list exact items, save only approved subsets" pattern is the right shape if/when we begin auto-graduating runtime self-learning into durable artifacts. **Defer the implementation** to Future Possibilities — v0.1 keeps `MEMORY.md` as private per-runtime state with no auto-graduation pathway.
- **Adopt:** Bernstein's *artifact-sink* vocabulary as a deferred future extension point for backup destinations beyond local filesystem (`bernstein@f950c71eddf0:docs/architecture/storage.md:L1-L14`). Today `SELF-DEPLOYMENT-CONTRACT.md` § 7 names operational.db backup as a single local-filesystem snapshot; Bernstein's sink abstraction is the right vocabulary if v0.2+ adds remote backup destinations. Recorded in § Future Possibilities, not adopted as v0.1 work.
- **Reject:** Letta Code's persistent-agent memory model (`letta-code@afac21583850:README.md:L25-L39`). Letta's design centers a single agent whose memory persists *across models*, sessions, and even providers — directly conflicting with `PRD-001.md` § 13.2's strict per-runtime memory isolation mandate. The conflict is structural, not reconcilable by adaptation.
- **Reject:** ORCH's full file-backed state model (`ORCH@0c0694896b3a:CLAUDE.md:L69-L81`) as a replacement for our SQLite operational store. We chose SQLite in ADR-002 + ADR-006 for ACID semantics on claim/complete/release operations and 60s+ polling intervals; ORCH's tail-read / atomic-write model is correct for ORCH's interactive cadence but unnecessary for our serialized-low-frequency cadence.

### 3.5 App-5 — Skill allowlist / reusable capabilities

**Current state.** Deny-by-default allowlist in `HERMES-SKILL-ALLOWLIST.md` v0.1.2 § 2 with required-fields contract (Name, Source URL, Version/commit, Purpose, Required credentials, Permission scope, Source review status, Sandbox mode, Dangerous operations, Rollback procedure) per § 4. Fifteen custom `dev-assist-*` skills enumerated in `MULTI-HERMES-CONTRACT.md` § 5 Custom skill allowlist. Two custom plugins (`dev-assist-escalation-policy`, `dev-assist-work-queue`) loaded into all five runtimes per § 5.6. Marketplace auto-installation blocked; `HERMES_ENABLE_PROJECT_PLUGINS=false` at runtime config. Hermes built-in skills filtered by toolset enable/disable lists per ADR-014 amendments.

**Surveyed repos handling this well.** ORCH's skill loader is a simple allowlist-like mechanism: Markdown skills loaded from `skills/library/`, library names constrained, MCP names skipped, contents cached, dispatch-time injection per agent's `skills` field (`ORCH@0c0694896b3a:CLAUDE.md:L86-L93`). OpenCastle's on-demand skill loading auto-selects during init based on stack to keep context lean (`opencastle@18c6f2cf4e5c:README.md:L110-L114`). Codebuff publishes templates to a registry with Zod schemas, tool-call validation, shared session state (`codebuff@54df847c6384:docs/architecture.md:L70-L81`). Letta Code's `/skill` command can ask the agent to learn a reusable module from current trajectory (`letta-code@afac21583850:README.md:L50-L55`).

**Adopt / Adapt / Reject.**

- **Adopt:** ORCH's MCP-name *exclusion* from the skill loader path (`ORCH@0c0694896b3a:CLAUDE.md:L86-L93`). We currently say MCP HTTP servers are out of scope (`ARCH-001.md` § 21:L363) but we don't have an explicit exclusion in the skill-loading code path. Add an exclusion pattern: skill names matching `mcp:*` or `mcp/*` are rejected at load time. Trivial defensive measure aligned with the existing deny-by-default posture. Amendment in § 6.3.
- **Adopt:** OpenCastle's *context-budget* framing — "loaded only as needed; designed to keep context windows lean" (`opencastle@18c6f2cf4e5c:README.md:L110-L114`). Currently each runtime loads its full per-role skill set on startup. While our skill set is small (5-7 skills per role) and fits in context, the *vocabulary* of "context-budget" gives operators a concrete metric to track when adding skills. Amendment in § 6.3 — add a single "context budget" line per role to `MULTI-HERMES-CONTRACT.md` § 5 stating the prompt+skills+plugin context cap.
- **Reject:** Codebuff's registry-backed publishing model (`codebuff@54df847c6384:docs/architecture.md:L70-L81`). Same rationale as App-1 reject: incompatible with deny-by-default allowlist; no v0.1 budget for ADR-003 supersession.
- **Reject:** Letta Code's `/skill` learn-from-trajectory command (`letta-code@afac21583850:README.md:L50-L55`). v0.1's `HERMES-SKILL-ALLOWLIST.md` § 2 requires source review before any new skill receives credentials; agent-authored runtime-graduated skills would either bypass that gate or require a heavyweight runtime-review cycle that v0.1 does not budget.

### 3.6 App-6 — Parallel execution / work isolation

**Current state.** Single-worktree single-Founder threat model. The Executor runtime uses Hermes' `terminal` skill with Docker backend (`MULTI-HERMES-CONTRACT.md` § 5.4:L155), which sandboxes shell commands but does not partition the source-of-truth git working tree. Five Hermes runtimes share the `devassist` Linux uid; isolation is filesystem-level via systemd sandbox directives (ADR-005 § Decision). Parallel ticket execution is not a v0.1 feature — the work queue serializes per role (`MULTI-HERMES-CONTRACT.md` § 6.2 claim semantics).

**Surveyed repos handling this well.** Bernstein decomposes agent isolation into a formal sandbox protocol with backend (worktree, Docker, E2B, Modal) and session (read/write/exec/ls/snapshot/shutdown) responsibilities, plus capability negotiation (`FILE_RW`, `EXEC`, `NETWORK`, `GPU`, `SNAPSHOT`, `PERSISTENT_VOLUMES`) (`bernstein@f950c71eddf0:docs/architecture/sandbox.md:L21-L91`). Gas Town uses worktrees for ephemeral Polecats, full clones for persistent Crew (`gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L41-L44`). OpenCastle gives one git worktree per worker with dependency-order merge-back (`opencastle@18c6f2cf4e5c:README.md:L192-L195`). CLITrigger gives each TODO its own worktree with simultaneous Claude/Gemini/Codex execution and serialized main-branch tasks (`CLITrigger@fd4731bb3e20:README.md:L125-L127`). AgentsMesh's Pod model binds Runner+Agent+Repository with PTY+sandbox state and a lifecycle through `running → paused/disconnected/orphaned → completed/terminated/error` (`AgentsMesh@93f56e498ebc:design/research/product-model.md:L20-L25`).

**Adopt / Adapt / Reject.**

- **Adopt (high priority):** Bernstein's *typed sandbox-capability protocol* (`bernstein@f950c71eddf0:docs/architecture/sandbox.md:L21-L91`) as a thin abstraction layer above Hermes' Docker terminal backend. Today our `MULTI-HERMES-CONTRACT.md` § 5.4 names "Docker" as the Executor backend with no abstraction. Bernstein's vocabulary — capability set `{FILE_RW, EXEC, NETWORK, GPU, SNAPSHOT, PERSISTENT_VOLUMES}` plus session interface — gives v0.2+ a clean path to Modal/E2B/microVM backends if a generated project's build cannot fit local Docker (`ARCH-001.md` § 21 Future Possibilities already names paid sandbox backends as a future trigger). The abstraction is small enough that v0.1 ships a single concrete `DockerSandbox` implementation with capabilities `{FILE_RW, EXEC, NETWORK}` and the others raise `CapabilityNotAvailable`; v0.2+ adds `ModalSandbox`/`E2BSandbox` without changing specialist runtimes. ADR-015 records the choice.
- **Adopt:** Gas Town's *worktree-vs-clone* distinction (`gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L41-L44`) as deferred vocabulary for the post-v0.1 parallel-execution feature. Currently we operate single-worktree; when (not if) the Founder asks for parallel-ticket execution, this distinction becomes load-bearing. Recorded in § Future Possibilities.
- **Defer:** OpenCastle's worktree-per-worker + dependency-order merge-back (`opencastle@18c6f2cf4e5c:README.md:L192-L195`). Same deferral as App-2 Convoy YAML — pattern is correct, but the trigger condition (multi-ticket parallel batch) does not exist in v0.1. Recorded in § Future Possibilities.
- **Reject:** AgentsMesh's full Pod product model with PodBinding zero-trust permissions (`AgentsMesh@93f56e498ebc:design/research/product-model.md:L56-L89`). The Pod abstraction is appropriate for AgentsMesh's multi-tenant data plane; v0.1 explicitly excludes multi-tenant per `PRD-001.md` § 4. The PodBinding permissions model is rich but solves a problem we don't have. Recorded as a v0.2+ "if multi-tenant becomes a goal" trigger in § Future Possibilities.

### 3.7 App-7 — Self-deployment or unattended operation

**Current state.** `SELF-DEPLOYMENT-CONTRACT.md` v0.2.0 specifies install/verify/rollback/upgrade scripts under `scripts/install-self.sh` etc., systemd-supervised five-runtime topology plus `omniroute.service` (ADR-011) plus `devassist-web.service` (ADR-013), with three approval gates (install, start, upgrade) per ADR-004. TKT-034 v0.3.1 adds interactive installer, eight new verify-self.sh invariants, and operator-hygiene scope. AUDIT-001 closed 2026-05-09 with `runtime_check` enforcement at systemd boot. No paid third-party hard dependencies.

**Surveyed repos handling this well.** Aeon emphasizes unattended schedules, self-healing skills, output-quality monitoring, persistent memory, reactive triggers, GitHub Actions as zero infrastructure (`aeon@5f2df0715aa3:README.md:L25-L44`). Bernstein's storage abstraction with artifact sinks plus buffered durability (durable writes commit locally with fsync, then queue async remote mirrors with bounded back-pressure) addresses ephemeral-compute crash recovery (`bernstein@f950c71eddf0:docs/architecture/storage.md:L63-L96`). Gas Town's molecules survive crashes via Git-backed state plus pull-based hooks (`gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L64-L82`). OpenCastle's Convoy Engine guarantees crash safety via SQLite WAL, with auto-started real-time dashboard (`opencastle@18c6f2cf4e5c:README.md:L192-L204`). OpenHands distributes via SDK/CLI/GUI/Cloud/Enterprise with Kubernetes self-hosting (`OpenHands@9482ab1a666d:README.md:L32-L72`).

**Adopt / Adapt / Reject.**

- **Adopt:** Bernstein's *buffered-durability* pattern as a deferred future extension for `operational.db` backups (`bernstein@f950c71eddf0:docs/architecture/storage.md:L63-L96`). Today `SELF-DEPLOYMENT-CONTRACT.md` § 7 backs up operational.db synchronously; Bernstein's "local fsync first, then async remote mirror with bounded back-pressure" is the right vocabulary if v0.2+ adds off-VPS backups. Recorded in § Future Possibilities, not adopted as v0.1 work.
- **Reject:** OpenHands' Kubernetes self-hosting deployment surface (`OpenHands@9482ab1a666d:README.md:L67-L72`). `PROJECT-CONCEPT.md` § 2 risk_boundaries explicitly enumerates k8s/kubernetes/ecs/lambda/cloud_run/fargate as escalation triggers (`replace_runtime_target` rule). Hard reject; not a future-possibility either.
- **Reject:** Aeon's GitHub-Actions-as-zero-infrastructure deployment pattern (`aeon@5f2df0715aa3:README.md:L25-L44`). Our v0.1 deployment target is single Ubuntu VPS owned by Founder per `PRD-001.md` § 12; CI in GitHub Actions is for *project repos*, not the assistant runtime. Pattern doesn't fit.

### 3.8 App-8 — Founder/human-in-the-loop escalation

**Current state.** Single `escalations` queue table (`MULTI-HERMES-CONTRACT.md` § 6.3), polled by Orchestrator runtime, surfaced as Russian Telegram message via `dev-assist-escalation-surface` skill. Trigger logic in `ESCALATION-POLICY.md` v0.1.1: deterministic § 4 rule set + deterministic § 5 concept-deviation classifier (no LLM in decision path per RV-SPEC-012 F3 fix). Founder responds via Telegram; response captured into originating runtime's work item plus durable artifact target. Architecturally clean but **the queue has only one shape** — every escalation is treated as immediate-blocking even when it's purely informational.

**Surveyed repos handling this well.** Gas Town distinguishes three communication modalities: persisted Mail (durable, deferred), direct-session Nudge (immediate, blocking), noninterrupting Peek (read-only inspection) (`gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L83-L99`). Ralph routes Telegram messages with blocking `human.interact` events; agents can emit and block until answered, humans send proactive guidance any time (`ralph-orchestrator@3eca5177db33:README.md:L144-L168`). AgentsMesh Channels are N:M communication groups including humans and Pods (`AgentsMesh@93f56e498ebc:design/research/product-model.md:L26-L30`). AgentPipe centers conversation save/resume, export, automatic chat logging, event storage (`agentpipe@f27e126d854e:README.md:L73-L97`).

**Adopt / Adapt / Reject.**

- **Adopt (high priority):** Gas Town's *three communication modalities* — Mail, Nudge, Peek — as a structured field on the existing `escalations` table (`gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L83-L99`). The current single-shape queue conflates "specialist runtime is blocked, please decide before continuing" with "Architect noticed a residual question, no rush" with "Reviewer surfaces a low-priority recommendation". Adding a `modality` column with values `nudge | mail | peek` lets the Orchestrator surface them differently in Telegram (Nudge → immediate priority message, Mail → daily digest entry, Peek → status-page-only). The work-queue plugin's claim semantics also benefit: a runtime that emitted a `nudge` should mark its current work item `paused-on-founder` rather than continue speculatively. ADR-017 records the choice; amendment to `MULTI-HERMES-CONTRACT.md` § 6.3 schema in § 6.2 below.
- **Adopt:** Ralph's `human.interact` blocking-event vocabulary as the structural primitive that *implements* Gas Town's `nudge` modality (`ralph-orchestrator@3eca5177db33:README.md:L144-L168`). The two surveyed repos converge on the same shape from different vocabularies; we adopt the union — Gas Town's three-mode taxonomy, Ralph's blocking semantics for the strongest mode.
- **Reject:** AgentsMesh Channels as N:M groups including humans (`AgentsMesh@93f56e498ebc:design/research/product-model.md:L26-L30`). v0.1 has one Founder + N specialist runtimes; the N:M group abstraction is unnecessary. Future-possibility-only if we ever add a second human (e.g., a junior engineer the Founder loops in).
- **Reject:** AgentPipe's full conversation export/replay surface (`agentpipe@f27e126d854e:README.md:L73-L97`). Our durable-decision capture pattern (`MULTI-HERMES-CONTRACT.md` § 7 "Decisions affecting product scope... must be summarized into repository artifacts") is structurally stronger than chat-export — it produces governance artifacts rather than transcript dumps.

### 3.9 App-9 — Skill evolution / learning

**Current state.** Disabled in v0.1 production. `HERMES-SKILL-ALLOWLIST.md` § 4.5 keeps `delegate_task` BLOCKED; `skill_manage` (agent-managed runtime skill creation) is disabled because v0.1 production keeps `plugins.disabled: skill_manage` per `MULTI-HERMES-CONTRACT.md` § 4. Static-allowlist-only. The 15 custom `dev-assist-*` skills evolve only through Architect-write-zone edits (`docs/architecture/shared-skills/`) followed by source review per `HERMES-SKILL-ALLOWLIST.md` § 6 ("Project-Local Plugin Policy") and TKT-021 acceptance.

**Surveyed repos handling this well.** Letta Code's `/skill` command learns reusable modules from current trajectory (`letta-code@afac21583850:README.md:L50-L55`). OpenCastle has lesson graduation into permanent instructions (`opencastle@18c6f2cf4e5c:README.md:L114-L122`). claude-flow advertises self-learning patterns and 100+ agents (`claude-flow@02eee0bcdc55:README.md:L180-L216`). gptme adds plugin system, lessons, MCP discovery, background jobs (`gptme@cf85d7d8b2c7:README.md:L96-L103`). Codebuff's agent-runtime supports `handleSteps` programmatic generators with subagent spawning (`codebuff@54df847c6384:docs/architecture.md:L57-L97`).

**Adopt / Adapt / Reject.**

- **Reject:** All forms of automated skill evolution / learning for v0.1. Per `HERMES-SKILL-ALLOWLIST.md` § 2, every enabled skill requires source review *before* receiving credentials or write access. Agent-graduated skills either bypass that gate or require a runtime-review cycle that v0.1 does not budget. Letta `/skill`, OpenCastle lesson graduation, claude-flow self-learning, gptme lessons all reject for the same reason.
- **Defer to Future Possibilities:** OpenCastle's *lesson-graduation* concept is the right shape *for v0.2+ if* Founder approves opening the runtime → durable-artifact pathway with mandatory Reviewer-LLM cross-check before promotion. Recorded in § Future Possibilities.
- **Note for downstream cycles:** the `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 7 already names `skill_manage` as an open research item; this synthesis does not change that, just confirms that the survey provided no new evidence to relax the v0.1 prohibition.

### 3.10 App-10 — Failure modes / recovery / escalation

**Current state.** Lease-reclaim sweep on stuck `claimed` work items (5-second cron per ADR-006 § Decision). Per-attempt counter with `max_attempts` default 3 (`MULTI-HERMES-CONTRACT.md` § 6.2). Rollback via `scripts/rollback-self.sh` per ADR-004 + `SELF-DEPLOYMENT-CONTRACT.md` § 6. Escalation policy fail-closed defaults — rule-engine error → escalate, malformed `PROJECT-CONCEPT.md` → escalate (`ESCALATION-POLICY.md` v0.1.1 § 3:L52-L58). Observability via journald + SQLite + cron + Telegram + `dev-assist-cli` per ADR-010 + `OBSERVABILITY-CONTRACT.md`. Strong by v0.1 standards but failure-mode names are scattered across artifacts rather than catalogued centrally.

**Surveyed repos handling this well.** kodo names micromanagement, drift/heresy, over-decomposition, role-OOD effects, token/latency overhead as named failure modes (`kodo@9758a0a1d0b1:docs/orchestration-tenets.md:L21-L30`). AgentsMesh records permission gaps in its own product model (`AgentsMesh@93f56e498ebc:design/research/product-model.md:L82-L89`). Bernstein turns ephemeral-compute loss into a storage-sink problem (`bernstein@f950c71eddf0:docs/architecture/storage.md:L3-L14`). Plandex provides cumulative diff sandbox, configurable autonomy, rollback, automated debugging (`plandex@e2d772072efa:README.md:L81-L106`). Ralph's backpressure gates structurally reject incomplete work (`ralph-orchestrator@3eca5177db33:README.md:L138-L142`).

**Adopt / Adapt / Reject.**

- **Adopt:** kodo's *named-failure-modes* discipline (`kodo@9758a0a1d0b1:docs/orchestration-tenets.md:L21-L30`). Today our failure modes are scattered across `OBSERVABILITY-CONTRACT.md`, `MULTI-HERMES-CONTRACT.md` claim lease semantics, `ESCALATION-POLICY.md` fail-closed paths. Add a single § "Named Failure Modes" to `OBSERVABILITY-CONTRACT.md` enumerating: `lease_expiry`, `attempt_exhaustion`, `escalation_engine_error`, `runtime_check_fail`, `concept_anchor_malformed`, `model_unreachable`, `secret_missing`, `verify_self_invariant_fail`, plus the kodo-style cross-cutting names: `drift`, `over_decomposition`, `role_ood`. Each gets a recovery path. Amendment in § 6.4. Lightweight (catalogue, not new infrastructure).
- **Adopt:** Bernstein's *ephemeral-compute-loss-as-storage-problem* framing as the v0.2+ extension trigger (`bernstein@f950c71eddf0:docs/architecture/storage.md:L3-L14`). v0.1 single-VPS shape doesn't have the ephemeral-compute problem (the VPS is durable); v0.2 if/when Modal/E2B sandbox backends ship will. Recorded in § Future Possibilities.
- **Reject:** Plandex's automated-debugging surface (`plandex@e2d772072efa:README.md:L81-L106`). Plandex's debugging loop calls back into its own LLM provider; v0.1's deterministic escalation policy already routes failures through structured channels (escalation queue → Founder; PR-Agent → Reviewer → Founder). Adding an inner debugging loop between Executor and Reviewer-Kimi conflicts with the cross-model independent review doctrine.

## 4. Cross-Cutting Theme Synthesis

This section maps each of the seven cross-cutting themes from RESEARCH-002 § 7 to concrete architectural decisions for ARCH-002.

| Theme (RESEARCH-002 § 7.N) | Decision in ARCH-002 |
| --- | --- |
| § 7.1 Work isolation usually means git worktrees first | **Defer.** Single-worktree single-Founder threat model is correct for v0.1. Worktree-based isolation is § Future Possibilities triggered by parallel-ticket execution. ADR-015 sandbox-capability protocol prepares the abstraction layer above worktree-vs-Docker-vs-Modal distinction. |
| § 7.2 Durable orchestration state is more varied than "memory" | **Already split.** ADR-002 (governance vs operational) plus ADR-006 (SQLite IPC) match the surveyed pattern. No change. |
| § 7.3 Verification is increasingly an orchestration primitive | **Adopt.** ADR-016 promotes Ralph-style backpressure gates from CI-only to work-queue-level; Reviewer rubric updated to use the vocabulary. |
| § 7.4 Human-in-the-loop is explicit in stronger orchestrators | **Adopt.** ADR-017 splits escalation into three modalities (Mail/Nudge/Peek) per Gas Town. |
| § 7.5 Skill systems range from static markdown to learned trajectories | **Stay static.** Deny-by-default allowlist (`HERMES-SKILL-ALLOWLIST.md` § 2) keeps v0.1 at the static-markdown end. Lesson-graduation deferred. |
| § 7.6 Parallelism creates review and merge burden | **Already mitigated.** Single-worktree v0.1 has no parallelism burden. The cross-model review triangle (`AGENTS.md` cross-model independent review doctrine) addresses the review-burden half preemptively. |
| § 7.7 Stronger systems name their failure modes | **Adopt.** Amendment to `OBSERVABILITY-CONTRACT.md` adding § Named Failure Modes per kodo's discipline. |

## 5. Q-RESEARCH-002 Answers

### 5.1 Q-RESEARCH-002-01 — Durable state representation

> Should durable state be represented primarily as docs-as-code Markdown, as append-only event logs, as issue/bead records, or as a hybrid? Gas Town, ORCH, Bernstein, and OpenHands each imply different answers.

The architecture has already answered this in ADR-002 v0.2.0 § Decision: split-state model with **Markdown docs-as-code authoritative for governance** and **SQLite operational store for runtime metadata**. This is the *hybrid* answer — Gas Town/Dolt-style identity ledgers, ORCH `.orchestry/` YAML+JSONL events, and Bernstein `.sdd/` WAL are all variants of "operational state outside repository", which we operationalize as a single SQLite file under `OPERATIONAL-STATE-STORE.md` v0.2.1.

What the survey *does* refine is which kinds of state belong in which half. Gas Town's persistent role-identity ledger is a "closed beads" durable artifact — closer to an append-only event log than to a current-state row. ORCH's `runs/<run_id>/events.jsonl` (`ORCH@0c0694896b3a:CLAUDE.md:L73-L75`) is an *event log* of what each runtime did during a run, not a current-state snapshot. Our SQLite operational store today carries primarily current-state rows (`work_items` with status, `escalations` with surfaced-at, `hermes_runs` with metadata). For future-cycle traceability — "show me every runtime action across the last week" — the absence of an event-log primitive is a small gap.

The synthesis answer: **stay primarily docs-as-code-plus-SQLite-current-state**, but **add an `events` append-only table to OPERATIONAL-STATE-STORE.md v0.3.0** for the cross-runtime trace use case. Implementation deferred to TKT-038 (§ 8); the schema is small (one row per work-item state transition, escalation surface, runtime_check pass/fail, deploy gate trigger), retention-bounded (cron-driven 90-day rolling delete, similar to journald rotation), and fits the existing observability shape (ADR-010) without new infrastructure. Bernstein's WAL is not adopted because we don't have a WAL-class durability requirement — current-state rows are sufficient for crash recovery, and the new event log is for *traceability* not durability.

This answer is consistent with the existing Architect's preference for Markdown governance documents — the new event table is operational-side state, never authoritative for governance decisions, and the rule "If Hermes memory or operational state contradicts repository artifacts, repository artifacts take precedence" (`HERMES-RUNTIME-CONTRACT.md` § 3:L36) extends naturally.

### 5.2 Q-RESEARCH-002-02 — Minimum isolation boundary for parallel agents

> What is the minimum isolation boundary for parallel dev-time agents: separate branch, git worktree, full clone, container, microVM, or self-hosted runner Pod?

This question is **conditionally not v0.1 scope**. The work-queue claim model (`MULTI-HERMES-CONTRACT.md` § 6.2) serializes per role: only one Executor runtime is claiming `target_role=executor` at a time, only one Reviewer is claiming `target_role=reviewer`. Parallel dev-time agents in the survey sense — multiple Executors or multiple Reviewers running concurrently — is a v0.2+ feature triggered by Founder asking for parallel-ticket execution.

When the trigger fires, the survey's answer is clear: **git worktree is the right minimum boundary** for *sequential-claiming* parallel agents on the same repo, **Docker container is the right minimum for command-execution sandboxing within a single agent**, and **microVMs / self-hosted runner Pods are over-engineering** unless multi-tenant becomes a goal (which `PRD-001.md` § 4 explicitly excludes). Bernstein's typed sandbox-capability protocol (`bernstein@f950c71eddf0:docs/architecture/sandbox.md:L21-L91`) gives the right vocabulary to span the worktree/Docker/Modal/E2B/microVM space without committing to one backend; this is what ADR-015 adopts.

The five surveyed evidence points converge: Gas Town worktrees-for-Polecats vs full-clones-for-Crew (`gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L41-L44`), CLITrigger worktree-per-TODO (`CLITrigger@fd4731bb3e20:README.md:L125-L127`), OpenCastle worktree-per-worker (`opencastle@18c6f2cf4e5c:README.md:L192-L195`), Bernstein worktree as default sandbox backend (`bernstein@f950c71eddf0:docs/architecture/sandbox.md:L93-L100`), Codebuff agent-runtime managing many subagents (`codebuff@54df847c6384:docs/architecture.md:L57-L97`). All five name worktree as the parallel-execution primitive; nobody centers microVMs or k8s runner Pods for the dev-time orchestration use case.

The synthesis answer for v0.1: **Docker container for command execution (already the case), no parallel agents at orchestration level**. For v0.2+: **Bernstein-style typed-protocol abstraction that ships with `DockerSandbox` v0.1 implementation; v0.2+ adds `WorktreeSandbox` (for parallel-ticket execution) and `ModalSandbox`/`E2BSandbox` (for builds-too-large-for-local-Docker triggers)**. ADR-015 captures this; TKT-035 (§ 8) implements the v0.1 abstraction layer with single concrete backend.

### 5.3 Q-RESEARCH-002-03 — Verification gates: orchestrator vs CI/Reviewer

> Which verification gates belong inside the orchestrator loop itself, and which belong only to CI/Reviewer PR gates?

Today the gates split is **CI-and-Reviewer-side**, with the work-queue claim/complete cycle agnostic to gate state (`MULTI-HERMES-CONTRACT.md` § 6.2 — `result_json` is opaque JSON; the queue does not enforce gates). This is one rung weaker than the survey's strong-orchestrator pattern.

Ralph names the answer: **structural backpressure gates** at the orchestration level for tests/lint/typecheck (`ralph-orchestrator@3eca5177db33:README.md:L136-L142`). The work-queue dispatcher should refuse to promote `ticket_review` to `completed` if the tied PR has any required CI check at `conclusion: failure`; the work-queue should refuse to dispatch a new `ticket_implementation` work item if the prior ticket's PR is still un-merged. OpenCastle's "fast review after every step + lint/test/build checks" (`opencastle@18c6f2cf4e5c:README.md:L114-L122`) and kodo's "structurally enforce verification" (`kodo@9758a0a1d0b1:docs/orchestration-tenets.md:L11-L13`) point in the same direction.

The synthesis answer is a **two-layer split** documented in ADR-016:

- **Orchestrator-loop gates (new, structural):** (a) the dispatcher MUST NOT dispatch a `ticket_implementation` for a ticket whose `status` is anything other than `ready`. (b) The dispatcher MUST NOT dispatch a `ticket_review` work item for a PR whose `validate-docs` CI check is `conclusion: success`. (c) The dispatcher MUST NOT promote any work item to `completed` while its tied PR has any required CI check at `conclusion: failure`. (d) The Orchestrator MUST surface a `nudge`-modality escalation (per ADR-017) when a work item exceeds `max_attempts` for `failed` reasons unrelated to a Founder decision.
- **CI/Reviewer-PR gates (existing):** validate-docs (frontmatter, ticket sections, cross-link integrity) + Run PR Agent on every pull request (`ARCH-001.md` § 17:L296-L304), plus Reviewer-Kimi rubric (`docs/prompts/reviewer.md` rubric encoded in `dev-assist-reviewer-rubric` skill).

The two layers are complementary: CI/Reviewer gates check *artifact correctness*; orchestrator-loop gates check *work-queue state-transition validity*. Ralph implements both layers; we currently implement only the second. ADR-016 promotes the first layer to architectural rule.

This is a meaningful change: today a buggy Executor runtime that emits `complete` despite a failing CI run could mark a work item `completed` and the queue would believe it. After ADR-016 adoption, the queue rejects the `complete` write transactionally if the PR's required CI checks are not green. Implementation deferred to TKT-036 (§ 8).

### 5.4 Q-RESEARCH-002-04 — Human escalation modeling

> How should human escalation be modeled: blocking questions, persisted mail, direct session nudges, PR comments, Telegram/Slack messages, or docs-backed decision records?

The survey converges on a *modality split*. Gas Town's three-mode taxonomy — Mail (durable, deferred), Nudge (immediate, blocking), Peek (read-only inspection) (`gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L83-L99`) — is the most articulated. Ralph's `human.interact` blocking event (`ralph-orchestrator@3eca5177db33:README.md:L144-L168`) maps to Gas Town's Nudge. Telegram gateway as the *transport* is what we already use; the missing piece is the *modality split inside* the existing escalation queue.

Today our `escalations` table is single-shape — every row is treated as immediate-blocking by the current `dev-assist-escalation-surface` skill. In practice we already have the three Gas Town modalities implicitly:
- Reviewer flagging "C-002 medium-priority recommendation that doesn't block merge" → would be Mail.
- Specialist runtime hitting `paid:llm_provider_outside_catalog` and needing Founder unstuck before any work continues → Nudge.
- SO daily-progress-report-style "here's what happened in the last 30 minutes" → Peek.

The synthesis answer adopts Gas Town's three-mode taxonomy as a structured `modality` column on the existing `escalations` table:

- **`nudge`** (immediate, blocking): Founder must answer before originating runtime continues. Surfaced as priority Telegram message with `/approve <id>` / `/deny <id>` / free-form-answer prompt. Originating runtime's current work_item is set to `paused-on-founder` status (new value in the work_items.status enum). Maps to current `ESCALATION-POLICY.md` § 4 deterministic rule matches and § 5 concept-deviation matches.
- **`mail`** (durable, deferred): runtime continues; the escalation appears in the daily Telegram digest and the `dev-assist-cli status` / web-status surface, but does not block. Maps to recommendation-style review comments and low-priority observations.
- **`peek`** (read-only inspection): runtime emits an informational note that the Founder can browse via web-status surface or `/status` Telegram command; no Telegram push. Maps to progress observations and structural commentary that does not require a decision.

Repository artifacts remain the durable end-state for any decision affecting product scope, architecture, or security (`MULTI-HERMES-CONTRACT.md` § 7 unchanged). Telegram is the synchronous transport for `nudge`; daily digest for `mail`; web-status for `peek`. PR comments are *not* a separate modality — they are the existing Reviewer / PR-Agent surface, complementary to the escalation queue.

ADR-017 records the choice; amendment to `MULTI-HERMES-CONTRACT.md` § 6.3 schema in § 6.2 below; TKT-037 implements (§ 8). Implementation cost is low: one new column, one new value in `work_items.status` enum, three branches in the existing `dev-assist-escalation-surface` skill's surface-formatter.

### 5.5 Q-RESEARCH-002-05 — Skill evolution safety

> How should reusable skills evolve safely: static allowlisted Markdown, repo-local skills, marketplace/registry skills, or learned skills that require review before becoming permanent?

Static allowlisted Markdown. Hard. The deny-by-default allowlist (`HERMES-SKILL-ALLOWLIST.md` v0.1.2 § 2) is the correct posture for v0.1's threat model: one Founder, one VPS, no multi-tenant, no public agent-marketplace ingest. Every entry must document Source URL, Version/commit, Purpose, Required credentials, Permission scope, Source review status, Sandbox mode, Dangerous operations, Rollback procedure (§ 4). This is a heavyweight gate and *appropriately* so.

The survey did not provide evidence to relax the policy. Letta Code's `/skill` learn-from-trajectory (`letta-code@afac21583850:README.md:L50-L55`), OpenCastle's lesson-graduation (`opencastle@18c6f2cf4e5c:README.md:L114-L122`), claude-flow's self-learning patterns (`claude-flow@02eee0bcdc55:README.md:L180-L216`), and gptme's lessons (`gptme@cf85d7d8b2c7:README.md:L96-L103`) all describe pathways from runtime-trajectory → durable skill, but none describe a *security review gate* that would satisfy `HERMES-SKILL-ALLOWLIST.md` § 6 "credential-bearing capabilities must use least-privilege scoped credentials" plus § 8 source-review-passed-before-credentials. Codebuff's registry-backed publishing (`codebuff@54df847c6384:docs/architecture.md:L70-L81`) is even further from our posture — registry ingest is the marketplace pathway we explicitly block via `HERMES_ENABLE_PROJECT_PLUGINS=false`.

The synthesis answer for v0.1: **stay static-markdown-allowlist with Architect-cycle Architect-write-zone authorship plus Reviewer-LLM cross-check before adoption**. The 15 custom `dev-assist-*` skills evolve only through the Architect → Reviewer → Founder approval loop documented in `MULTI-HERMES-CONTRACT.md` § 5.0. No automated evolution.

For v0.2+ the right shape is a **two-stage gate**: (1) runtime emits a *proposed-skill* artifact under `docs/architecture/shared-skills/PROPOSED/<skill-name>.md` with the trajectory that produced it; (2) Architect cycle reviews, hardens, and promotes via standard write-zone amendment. This is documented as a Future Possibility in § 9 — the design space is visible without committing v0.1 budget.

The strong rejection of automated graduation in v0.1 is a deliberate stance against the survey's "skill evolution range" theme (RESEARCH-002 § 7.5). Per NUDGE § 12.1 and the Founder's "we accept very serious changes" mandate, this is the explicit place to name a preference: **for v0.1, runtime self-learning is a private-MEMORY.md feature, not a durable-artifact-graduation feature**. The deny-by-default posture is preserved; learned trajectories never reach `skills.external_dirs` without Architect review.

### 5.6 Q-RESEARCH-002-06 — Anti-drift mechanism for multi-LLM artifact production

> What anti-drift mechanism is required when multiple LLM roles can produce durable project artifacts independently?

This is the highest-leverage question in the set, because the project is unusual among the surveyed repos in having *four* artifact-producing LLM roles (Business Planner, Architect, Executor, Reviewer) plus three orchestrator roles, with the Strategic Orchestrator session-level conductor producing additional governance state in `docs/orchestration/SESSION-STATE.md` and `docs/session-log/`. Anti-drift is non-optional.

Today we have three partial mechanisms:

1. **`PROJECT-CONCEPT.md` § 2 structured concept anchor** (`PROJECT-CONCEPT.md` § 2:L19-L185) — drift in the concept-anchor sense (replacing target user, swapping tech stack, changing deployment target) is caught by the deterministic rule set in `ESCALATION-POLICY.md` § 4 and the concept-deviation classifier in § 5.
2. **Cross-link / frontmatter / status-flow validation** in `scripts/validate_docs.py` (CI-required check) — drift in the references-vs-reality sense is caught at the validate-docs gate.
3. **Cross-model independent review** doctrine in `AGENTS.md` — Anthropic-family Architect / Business Planner artifacts are reviewed by DeepSeek-family PR-Agent and Moonshot-family Reviewer-Kimi. Same-model echo chambers are mitigated structurally.

What none of these mechanisms catches is **inter-artifact semantic drift**: ARCH-001 § 11.1 says "memory isolation is filesystem-level"; if Reviewer-Kimi rubric encoded by `dev-assist-reviewer-rubric` later starts judging code against a "memory broker" mental model, the artifacts disagree without triggering any rule. Or: PRD-001 § 13.2 says "five Hermes runtimes"; if Architect later writes ARCH-003 with seven runtimes (e.g., adding a Tester role per Founder ask), an existing TKT that still cites "five runtimes" goes stale without triggering any rule. CLITrigger's wiki-injection pattern (`CLITrigger@fd4731bb3e20:README.md:L107-L115`) is the closest survey analogue — selective token-budgeted injection of canonical knowledge at dispatch time.

The synthesis answer is a **concept-anchor freshness ledger** — a small structured artifact that lists, for each long-lived contract document, the *concept-anchor entries it asserts* (e.g., MULTI-HERMES-CONTRACT.md asserts `multi_hermes_runtime_topology=five_separate_installations`, `escalation_policy=deterministic_classifier`, `model_routing=omniroute_primary_openrouter_backup`). The ledger is an artifact at `docs/architecture/CONCEPT-ANCHOR-FRESHNESS.md` (Architect write zone), and `scripts/validate_docs.py` extends to assert two invariants:

- **Anchor membership:** every assertion in the ledger maps to a current entry in `PROJECT-CONCEPT.md` § 2 or to an explicit deviation-allowance comment.
- **Forward consistency:** when a contract document is amended, its asserted anchors are listed in the PR description (template enforced); validate_docs.py grep-checks the PR description plus the changed contract for anchor-name continuity.

Per CLITrigger's pattern, the ledger is also the *Reviewer-context-injection* surface — at dispatch time, the `dev-assist-reviewer-rubric` skill reads the ledger and includes the relevant anchors-asserted in its review prompt. This gives Reviewer-Kimi a deterministic concept-anchor reference rather than relying on its trained-in mental model of our project.

ADR-018 records the mechanism choice; amendment to `MULTI-HERMES-CONTRACT.md` § 5 (Reviewer skill loadout) plus a new contract artifact in § 6.5 below; TKT-039 implements (§ 8). Cost is moderate: one new ~50-line ledger artifact, one new validate-docs check, one new context-injection branch in the Reviewer skill. Lower cost than the alternative (regular cross-artifact audits by Architect).

This is a *structural* anti-drift mechanism, not a *behavioral* one — it does not stop a Reviewer from disagreeing with an Architect on a judgment call (which is what cross-model independent review handles), it stops divergence on *factual concept-anchor claims* (memory isolation mechanism, runtime count, routing layer, etc.). The two mechanisms are complementary and both stay in effect.

## 6. Architectural Amendment Proposals

This section enumerates targeted amendments to existing contract documents. Each entry states the file, current-state quote, proposed change, rationale, and citations. Amendments do not land here (status: draft); they land via downstream Executor cycles after the corresponding ADRs are promoted from `proposed` to `accepted`.

### 6.1 `MULTI-HERMES-CONTRACT.md` § 6.2 — work_items state machine

**Current state** (`MULTI-HERMES-CONTRACT.md` v0.2.1 § 6.2:L194-L218):

> `status` | TEXT NOT NULL CHECK | `pending`, `claimed`, `completed`, `failed`, `released`

**Proposed change.** Extend the status enum to add two values: `cancelled` (terminal, runtime decided to abandon — e.g., ticket no longer relevant) and `paused_on_founder` (non-terminal, runtime is blocked waiting for a `nudge`-modality escalation per ADR-017).

**Rationale.** ORCH's terminal-states triple `done | failed | cancelled` (`ORCH@0c0694896b3a:CLAUDE.md:L49-L52`) names a state we currently conflate with `failed`. Gas Town's pull-based scheduling (`gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L64-L82`) implies the originating runtime should mark itself paused rather than continue speculatively. Ralph's `human.interact` blocking events (`ralph-orchestrator@3eca5177db33:README.md:L144-L168`) make the same point. Maps to App-2 + App-8.

**New transitions:** `claimed → cancelled` (runtime aborts), `claimed → paused_on_founder` (nudge escalation emitted), `paused_on_founder → claimed` (Founder responded, runtime resumes), `paused_on_founder → cancelled` (Founder denied / Founder pivot rendered work item irrelevant).

**Implementation:** TKT-036 (§ 8).

### 6.2 `MULTI-HERMES-CONTRACT.md` § 6.3 — escalations table modality column

**Current state** (`MULTI-HERMES-CONTRACT.md` § 6.3 — schema authoritative in `OPERATIONAL-STATE-STORE.md` § 3.6).

The current `escalations` table has columns for `id`, `created_at`, `originating_runtime`, `originating_work_item_id`, `trigger_kind`, `payload_json`, `surfaced_at`, `responded_at`, `response_text`, `resolution_artifact_path`. There is no `modality` column; every escalation is treated as immediate-blocking by `dev-assist-escalation-surface`.

**Proposed change.** Add a `modality` column with `CHECK (modality IN ('nudge','mail','peek'))`, default `nudge` for backward compatibility (escalation rules in `ESCALATION-POLICY.md` § 4 default to nudge per ADR-017). The `dev-assist-escalation-surface` skill branches on modality: `nudge` → priority Telegram message + originating runtime's work_item set to `paused_on_founder`; `mail` → daily digest entry; `peek` → web-status surface only.

**Rationale.** Gas Town's three-mode taxonomy (`gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L83-L99`). Maps to App-8 + Q-RESEARCH-002-04. ADR-017.

**Implementation:** TKT-037 (§ 8). Schema migration is additive (new column with default value); no breaking change. The schema change is owned by `OPERATIONAL-STATE-STORE.md` v0.3.x.

### 6.3 `MULTI-HERMES-CONTRACT.md` § 5 — context budget per role + MCP exclusion

**Current state** (`MULTI-HERMES-CONTRACT.md` § 5 — per-role loadout tables L121-L168). The tables list Hermes built-in skills, custom skills, and explicitly-NOT-loaded skills, but do not state a context budget cap and do not have an explicit MCP-name exclusion at the skill loader.

**Proposed change.** Add (a) a single line per role table stating the prompt+skills+plugins context budget cap (e.g., "Context budget: prompt (~3.5k tokens) + skills loadout (~2k tokens) + plugins (~0.5k tokens) ≈ 6k tokens of static context per dispatch"), and (b) a one-paragraph subsection at § 5.0 stating that skill names matching `mcp:*` or `mcp/*` (or any path under `/srv/devassist/shared-skills/mcp/`) are excluded at load time.

**Rationale.** OpenCastle's "loaded only as needed... designed to keep context windows lean" (`opencastle@18c6f2cf4e5c:README.md:L110-L114`) — context-budget vocabulary. ORCH's MCP-name exclusion (`ORCH@0c0694896b3a:CLAUDE.md:L86-L93`) — defensive boundary aligned with our existing `ARCH-001.md` § 21 exclusion of MCP HTTP servers from v0.1. Maps to App-5.

**Implementation:** TKT-040 (§ 8). Trivial documentation change plus a one-line exclusion in the skill loader's `init` path.

### 6.4 `OBSERVABILITY-CONTRACT.md` — new § Named Failure Modes

**Current state** (`OBSERVABILITY-CONTRACT.md` v0.1.x). The contract names FR-OBS-01..10 functional requirements and the four observability primitives (journald + SQLite + cron + Telegram + dev-assist-cli per ADR-010), but does not catalogue project-level failure modes in one place. They are scattered across `MULTI-HERMES-CONTRACT.md` § 6.2 (lease expiry, attempt exhaustion), `ESCALATION-POLICY.md` § 3 fail-closed defaults (rule_engine_unavailable, classifier_error), `SELF-DEPLOYMENT-CONTRACT.md` § 6 (rollback triggers), TKT-033 § 8 (runtime_check_fail).

**Proposed change.** Add a § "Named Failure Modes" enumerating the cross-cutting failure-mode names with their detection signal, recovery path, and escalation modality:

| Failure mode | Detection | Recovery path | Escalation modality |
| --- | --- | --- | --- |
| `lease_expiry` | cron lease-reclaim sweep at 5s cadence finds `claimed` row past `claim_lease_until` | reset to `pending`, increment `attempt_count` | none unless `attempt_count >= max_attempts` |
| `attempt_exhaustion` | `attempt_count >= max_attempts` with terminal `failed` | mark work item `failed`, emit nudge | nudge |
| `escalation_engine_error` | `dev-assist-escalation-policy` plugin pre_tool_call hook raises | fail-closed: pause runtime, emit nudge with `trigger_kind='classifier_error'` | nudge |
| `concept_anchor_malformed` | `PROJECT-CONCEPT.md` YAML parse fails at runtime startup | fail-closed: refuse to start runtime, log to journald | nudge (operator-visible via `/status`) |
| `runtime_check_fail` | TKT-033 invariant fails at boot | refuse to start runtime, exit non-zero | nudge (operator-visible) |
| `model_unreachable` | OmniRoute returns non-success for all catalog identifiers OR OpenRouter fallback fails | retry per Hermes default; if persistent, emit nudge | nudge |
| `secret_missing` | install-self.sh / verify-self.sh detects missing required env var | refuse to install/start; report which var | nudge |
| `verify_self_invariant_fail` | `scripts/verify-self.sh` returns non-zero | report which invariant; do not auto-rollback | mail (operator-visible via verify output) |
| `drift` | concept-anchor freshness ledger check fails (ADR-018) | mark PR with validation failure; require Architect re-pass | mail |
| `over_decomposition` | (kodo) Architect produces > N tickets for single architectural change without explicit Founder approval | (operational signal only — no automated detection in v0.1) | mail (Architect prompt amendment) |
| `role_ood` | (kodo) runtime emits a tool call outside its prompt's allowed-toolset list | escalation policy § 4 catches; runtime pauses | nudge |

**Rationale.** kodo's named-failure-modes discipline (`kodo@9758a0a1d0b1:docs/orchestration-tenets.md:L21-L30`). Maps to App-10. Centralizing the names lets operators search journald with consistent labels and lets the daily digest aggregate by failure mode. Lightweight (catalogue, not new infrastructure).

**Implementation:** Folded into TKT-038 (events table is the natural pair). The OBSERVABILITY-CONTRACT.md § Named Failure Modes amendment lands as part of TKT-038's documentation footprint.

### 6.5 New artifact: `CONCEPT-ANCHOR-FRESHNESS.md`

**Current state.** No such file. Drift between contract documents and `PROJECT-CONCEPT.md` § 2 anchors is detected only by Architect-cycle audit (ad-hoc) plus cross-link validation in `validate_docs.py` (which checks references, not anchor-claim consistency).

**Proposed change.** Add `docs/architecture/CONCEPT-ANCHOR-FRESHNESS.md` (Architect write zone), with a small structured table mapping each long-lived contract document to the concept-anchor IDs it asserts. Example shape:

```markdown
| Contract document | Asserted anchor IDs |
| --- | --- |
| ARCH-001 v0.3.0 | multi_hermes_runtime_topology, hermes_agent_runtime, sqlite_state_store, linux_vps_systemd, omniroute_routing_primary, deterministic_escalation_policy |
| MULTI-HERMES-CONTRACT v0.2.1 | multi_hermes_runtime_topology, sqlite_state_store, deterministic_escalation_policy |
| ESCALATION-POLICY v0.1.1 | deterministic_escalation_policy |
| MODEL-CATALOG v0.1.1 | omniroute_routing_primary, openrouter_routing_backup, founder_pre_approved_model_catalog |
| ADR-005 v0.1.0 | multi_hermes_runtime_topology, hermes_agent_runtime |
| ADR-006 v0.1.0 | sqlite_state_store, multi_hermes_runtime_topology |
... (extends to all contracts)
```

`scripts/validate_docs.py` extends with two checks: (a) every asserted anchor ID maps to a current entry in `PROJECT-CONCEPT.md` § 2 (in_scope_v0_1, tech_anchors, risk_boundaries, deviation_rules, etc.); (b) PR descriptions for changed contract files must list the asserted anchors of the changed file (template enforced).

**Rationale.** Q-RESEARCH-002-06 anti-drift answer (§ 5.6). CLITrigger's wiki-injection pattern (`CLITrigger@fd4731bb3e20:README.md:L107-L115`). Maps to App-1, App-4. ADR-018.

**Implementation:** TKT-039 (§ 8). New file (Architect write zone) plus validate_docs.py extension plus dev-assist-reviewer-rubric skill update for context injection.

### 6.6 `dev-assist-reviewer-rubric` skill — backpressure-gate vocabulary

**Current state** (`MULTI-HERMES-CONTRACT.md` § 5.5:L161-L169 — Reviewer custom skills loadout). The Reviewer rubric encodes verdict types `pass | pass_with_changes | pass_with_recommendations | fail`, but does not name the gate failures structurally. CI-side gate failures (validate-docs, PR-Agent) are handled by GitHub Actions; the Reviewer's own gate failures are encoded as findings in the review artifact under `docs/reviews/`.

**Proposed change.** Update the `dev-assist-reviewer-rubric` skill (write zone: `docs/architecture/shared-skills/dev-assist-reviewer-rubric/SKILL.md` — Architect-cycle authorship per `MULTI-HERMES-CONTRACT.md` § 5.0) to use the named backpressure-gate vocabulary: each finding is tagged with one of `tests_gate`, `lint_gate`, `typecheck_gate`, `docs_gate`, `concept_anchor_gate`, `cross_link_gate`, `cross_model_consistency_gate`. The Reviewer LLM receives the gate taxonomy in its prompt and must classify every finding by gate.

**Rationale.** Ralph's backpressure gates (`ralph-orchestrator@3eca5177db33:README.md:L136-L142`). Maps to App-3 + Q-RESEARCH-002-03. ADR-016. Operator benefit: gate-tagged findings let `dev-assist-cli status` aggregate "what kinds of gates fail most across PRs" — a basic process-improvement signal currently absent.

**Implementation:** TKT-038 (§ 8). Skill amendment plus minor `validate_docs.py` extension to assert presence of gate tags in any new RV-CODE / RV-SPEC artifact. Backward-compatible (existing artifacts pre-amendment do not require gate tags; the rule is forward-only).

## 7. New ADR Proposals

This synthesis proposes four ADRs at status: `proposed`. Per NUDGE § 12.3, ADRs at `proposed` are NOT yet binding; they become binding only after Founder ratify and Architect promotion to `accepted`. The full ADR text lives in `docs/architecture/adr/`; this section provides an at-a-glance summary.

| ADR | Title | Status | Decision summary | Adopts from | Maps to | Implements |
| --- | --- | --- | --- | --- | --- | --- |
| ADR-015 | Sandbox Capability Protocol — Bernstein-style typed abstraction | proposed | Adopt typed sandbox interface with capability set `{FILE_RW, EXEC, NETWORK, GPU, SNAPSHOT, PERSISTENT_VOLUMES}`. v0.1 ships single `DockerSandbox` with `{FILE_RW, EXEC, NETWORK}`. v0.2+ adds `WorktreeSandbox`/`ModalSandbox`/`E2BSandbox` without changing specialist runtimes. | `bernstein@f950c71eddf0:docs/architecture/sandbox.md:L21-L91` | App-6, App-7, Q-RESEARCH-002-02 | TKT-035 |
| ADR-016 | Backpressure Gates As Orchestration Primitive — Ralph adoption | proposed | Promote tests/lint/typecheck/docs gates from CI-only to work-queue-level. Dispatcher refuses to promote `ticket_review → completed` while required CI checks at `failure`. Reviewer rubric tags findings by gate name. | `ralph-orchestrator@3eca5177db33:README.md:L136-L142`, `kodo@9758a0a1d0b1:docs/orchestration-tenets.md:L11-L13`, `opencastle@18c6f2cf4e5c:README.md:L114-L122` | App-3, App-10, Q-RESEARCH-002-03 | TKT-036, TKT-038 |
| ADR-017 | Escalation Modalities — Gas Town Mail/Nudge/Peek split | proposed | Split single-shape escalation queue into three modalities. Add `modality` column to `escalations` table. Add `paused_on_founder` work-item status. Surface formatter branches by modality. | `gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L83-L99`, `ralph-orchestrator@3eca5177db33:README.md:L144-L168` | App-8, Q-RESEARCH-002-04 | TKT-037 |
| ADR-018 | Anti-Drift Concept-Anchor Freshness Ledger | proposed | Add `CONCEPT-ANCHOR-FRESHNESS.md` mapping each contract to asserted anchors. Extend `validate_docs.py` with two membership/consistency checks. Reviewer rubric injects relevant anchors at dispatch (CLITrigger wiki-injection pattern). | `CLITrigger@fd4731bb3e20:README.md:L107-L115`, `OpenHands@9482ab1a666d:skills/agent_memory.md:L10-L30` | App-1, App-4, Q-RESEARCH-002-06 | TKT-039 |

Per NUDGE § 5.4 no new external dependencies are introduced. ADR-015's sandbox protocol is a Python interface (no new pip package); ADR-016 reuses GitHub Actions check-API and existing SQLite; ADR-017 is one schema column + one enum value; ADR-018 is one Markdown file + one validate_docs check.

## 8. New Ticket Proposals

Six tickets at status: `draft`. They land as separate Executor implementation cycles after the corresponding ADRs are promoted to `accepted` per NUDGE § 12.3. Full ticket bodies live in `docs/tickets/TKT-035..040.md`; this section provides at-a-glance summary plus dependency graph.

| Ticket | Title | Status | Implements | Depends on | Allowed write zones |
| --- | --- | --- | --- | --- | --- |
| TKT-035 | Sandbox Capability Protocol v0.1 — DockerSandbox concrete implementation | draft | ADR-015 | (none) | `src/sandbox/`, `tests/test_sandbox.py`, `docs/architecture/SANDBOX-CONTRACT.md` (NEW Architect-zone authorship in TKT body), `MULTI-HERMES-CONTRACT.md` § 5.4 amendment |
| TKT-036 | Work-Queue Backpressure Gates — orchestrator-loop verification | draft | ADR-016 | TKT-022 (work_items table base) | `src/work_queue/`, `tests/test_work_queue_gates.py`, `MULTI-HERMES-CONTRACT.md` § 6.2 amendment, `OPERATIONAL-STATE-STORE.md` § 3.5 schema migration v0.3.x |
| TKT-037 | Escalation Modality Split — Mail/Nudge/Peek surface formatter | draft | ADR-017 | TKT-023 (escalation plugin base) | `src/escalation/`, `tests/test_escalation_modality.py`, `MULTI-HERMES-CONTRACT.md` § 6.3 amendment, `OPERATIONAL-STATE-STORE.md` § 3.6 schema migration v0.3.x, `dev-assist-escalation-surface` skill amendment |
| TKT-038 | Reviewer Rubric Gate-Tagged Findings + events table | draft | ADR-016 (backpressure tag), Q-RESEARCH-002-01 (events log) | TKT-036 | `dev-assist-reviewer-rubric` skill (Architect-zone), `OPERATIONAL-STATE-STORE.md` § 3.7 NEW events table, `scripts/validate_docs.py` gate-tag forward-only check |
| TKT-039 | Concept-Anchor Freshness Ledger + validate_docs check + Reviewer context injection | draft | ADR-018 | TKT-038 (reviewer rubric base after gate tags) | `docs/architecture/CONCEPT-ANCHOR-FRESHNESS.md` NEW, `scripts/validate_docs.py` two new checks, `dev-assist-reviewer-rubric` skill context-injection branch |
| TKT-040 | Skill Loadout Context Budget Documentation + MCP Exclusion | draft | (no ADR — documentation amendment only) | (none) | `MULTI-HERMES-CONTRACT.md` § 5 amendment, `dev-assist-work-queue` plugin skill loader exclusion-pattern check |

Dependency graph:

```
TKT-035 (ADR-015)  ─────┐
TKT-036 (ADR-016) ────────┐
TKT-037 (ADR-017) ──────────┐
TKT-040 (no ADR)  ────────────┐
TKT-038 (ADR-016 ext) ←─ TKT-036
TKT-039 (ADR-018)     ←─ TKT-038
```

TKT-035, TKT-036, TKT-037, TKT-040 are independent and dispatchable in parallel after ADR ratify. TKT-038 depends on TKT-036 for the work-queue gate base. TKT-039 depends on TKT-038 for the reviewer-rubric base.

Each ticket follows the standard nine-section template (Purpose, Inputs, Outputs, Acceptance Criteria, Allowed Files, Hard Rules, Deferred Items, References, Iteration Log). The full ticket bodies are appended in this PR as `docs/tickets/TKT-035-*.md` ... `docs/tickets/TKT-040-*.md`.

## 9. Open Architectural Questions For Founder (Q-ARCH-002-NN)

Per NUDGE § 4.3 (required-content section "Open architectural questions") and § 12.3 (ADRs at proposed are not yet binding), the following questions remain Founder-decisions. Each has a 1-2 sentence framing, options, and Architect's recommendation.

### Q-ARCH-002-01 — Convoy YAML scope

**Framing.** OpenCastle Convoy YAML (`opencastle@18c6f2cf4e5c:README.md:L155-L204`) is the most-tempting deferred pattern. The trigger condition for adopting it is "first explicit batch of ≥5 dependent tickets that the SO would otherwise track only in prose". Whether to adopt now or defer.

**Options.**
- **A. Defer (recommended).** Keep SQLite work-queue + SESSION-STATE narrative as the multi-ticket coordination surface. Trigger: first batch ≥5 tickets.
- **B. Adopt now.** Add a `convoy.yaml` schema and convoy-interpreter logic to `dev-assist-work-queue` plugin. Adds ~200-300 lines of orchestration primitives.

**Architect's recommendation.** A. Defer. Per Founder's 2026-05-10 ack ("Convoy-YAML на твоё усмотрение"), and per NUDGE § 12.2 over-engineering guard.

### Q-ARCH-002-02 — Anti-drift validate-docs check strictness

**Framing.** ADR-018 + TKT-039 propose extending `validate_docs.py` with two checks (anchor membership + forward consistency). The forward-consistency check requires PR descriptions to list asserted anchors of changed contract files. PR-description format enforcement is mildly invasive.

**Options.**
- **A. Strict.** PR description without listed anchors → CI fail.
- **B. Soft.** PR description without listed anchors → CI warning (annotation only); merge allowed.
- **C. Reviewer-only.** Reviewer-Kimi rubric checks for anchor list; no validate_docs.py enforcement.

**Architect's recommendation.** B. Soft (CI warning). v0.1 should not block merges on documentation hygiene; the warning surface is sufficient pressure to comply, and the strict path can be promoted in v0.2 if compliance is poor.

### Q-ARCH-002-03 — Backpressure-gate scope

**Framing.** ADR-016 + TKT-036 propose four orchestrator-loop gates (a-d in § 5.3 above). Gate (d) — "Orchestrator MUST surface a `nudge`-modality escalation when work item exceeds `max_attempts`" — couples ADR-016 to ADR-017 modality split. Whether to adopt all four gates as one ticket or split into smaller tickets.

**Options.**
- **A. All four in TKT-036 (recommended).** Single coherent backpressure-gate ticket; depends on TKT-037 for modality.
- **B. Split into TKT-036a (gates a-c) + TKT-036b (gate d).** Decouples from TKT-037 timing; TKT-036b waits.

**Architect's recommendation.** A. The four gates are conceptually one mechanism; splitting introduces a partial-implementation window where the Orchestrator can fail-by-attempt without surfacing.

### Q-ARCH-002-04 — Future-Possibility trigger sensitivity

**Framing.** § Future Possibilities (below) names triggers for several deferred patterns: Convoy YAML (≥5 dependent tickets), worktree-based parallel execution (Founder asks for parallel-ticket execution), Bernstein artifact sinks for off-VPS backups (v0.2+), Modal/E2B sandbox backends (build-too-large-for-Docker). These triggers are Architect-defined; the Founder may want different thresholds.

**Options.**
- **A. Accept Architect-defined triggers as written (recommended).**
- **B. Founder defines explicit thresholds.** E.g., "worktree-parallel triggered when N≥3 tickets are blocked-on-each-other for >X hours".

**Architect's recommendation.** A. The Architect-defined triggers are *advisory*; if the Founder hits any of them ad-hoc, the Architect cycle picks up the trigger and proposes the upgrade. Explicit Founder thresholds add governance overhead without obvious benefit.

### Q-ARCH-002-05 — kodo-style "over_decomposition" detection

**Framing.** § 6.4 amendment to OBSERVABILITY-CONTRACT names `over_decomposition` as a kodo-style failure mode. Per the table, it has "no automated detection in v0.1" because the heuristic ("Architect produces >N tickets for single architectural change") is fuzzy. Whether to invest in detection now.

**Options.**
- **A. Document only, no detection (recommended).**
- **B. Add a soft check.** validate_docs warns if a single ARCH-NNN PR drafts >5 TKTs.

**Architect's recommendation.** A. The current ARCH-002 PR drafts 6 TKTs and 4 ADRs, which is Architect-judgement-correct given the synthesis breadth; an automated check would false-positive here. Save it as a Reviewer-rubric concern instead — Reviewer-Kimi judges whether the decomposition is appropriate per architectural-change scope.

### Q-ARCH-002-06 — Skill-graduation v0.2 spec timing

**Framing.** § 5.5 (Q-RESEARCH-002-05 answer) defers automated skill evolution to a hypothetical v0.2+ two-stage gate (proposed-skill artifact under `docs/architecture/shared-skills/PROPOSED/` → Architect cycle promotion). Whether to spec the v0.2 gate now or wait.

**Options.**
- **A. Wait until first runtime self-learning trajectory exists (recommended).** v0.1 keeps `MEMORY.md` private; no skills attempt to graduate.
- **B. Spec the gate now.** Add `SKILL-GRADUATION-CONTRACT.md` v0.1.0 (status: draft) with the two-stage shape and the Architect-cycle review requirements.

**Architect's recommendation.** A. Per § 5.5 strong-rejection stance, runtime self-learning is private-MEMORY.md-only in v0.1. Speculatively spec'ing v0.2 patterns is over-engineering.

## 10. Future Possibilities

Recorded so the design space is visible without committing v0.1 budget. Each entry has a *trigger condition* — what observable event would warrant promoting the future-possibility into a real Architect cycle.

- **Convoy YAML workflow definitions** for declared multi-ticket batches. Trigger: first batch ≥5 dependent tickets that the SO would otherwise track only in prose. Pattern source: `opencastle@18c6f2cf4e5c:README.md:L155-L204`.
- **Worktree-based parallel-ticket execution**, with `WorktreeSandbox` (extending ADR-015 protocol). Trigger: Founder asks for parallel-ticket execution OR a generated-project's CI requires it. Pattern source: `gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L41-L44`, `CLITrigger@fd4731bb3e20:README.md:L125-L127`, `opencastle@18c6f2cf4e5c:README.md:L192-L195`.
- **Modal/E2B sandbox backends** (`ModalSandbox`, `E2BSandbox` extending ADR-015 protocol). Trigger: a generated project whose build cannot fit local Docker backend (`ARCH-001.md` § 21 already names this trigger). Pattern source: `bernstein@f950c71eddf0:docs/architecture/sandbox.md:L93-L100`.
- **Bernstein-style artifact sinks** for off-VPS backups (S3/GCS/Azure/R2). Trigger: Founder asks for off-VPS backup destinations OR v0.2+ multi-VPS topology. Pattern source: `bernstein@f950c71eddf0:docs/architecture/storage.md:L1-L14`.
- **Bernstein-style buffered-durability** for `operational.db` mirror. Trigger: same as artifact sinks. Pattern source: `bernstein@f950c71eddf0:docs/architecture/storage.md:L63-L96`.
- **AgentsMesh Channels** as N:M human+pod communication groups. Trigger: project graduates beyond single Founder. Pattern source: `AgentsMesh@93f56e498ebc:design/research/product-model.md:L26-L30`.
- **AgentsMesh PodBinding zero-trust permissions model**. Trigger: multi-tenant becomes a goal (`PRD-001.md` § 4 explicitly excludes today). Pattern source: `AgentsMesh@93f56e498ebc:design/research/product-model.md:L56-L89`.
- **OpenCastle lesson-graduation pathway** (runtime trajectory → durable skill). Trigger: Founder approves opening runtime → durable-artifact pathway with mandatory Reviewer-LLM cross-check before promotion. Two-stage gate spec deferred per Q-ARCH-002-06. Pattern source: `opencastle@18c6f2cf4e5c:README.md:L114-L122`.
- **OpenHands repo-memory confirmation gate** for any future automated `MEMORY.md` writes. Trigger: same as lesson-graduation. Pattern source: `OpenHands@9482ab1a666d:skills/agent_memory.md:L10-L30`.
- **CLITrigger-style parallel multi-CLI execution** (Claude/Gemini/Codex side-by-side). Trigger: cross-vendor cross-check moves from review-time to execution-time. Pattern source: `CLITrigger@fd4731bb3e20:README.md:L125-L127`.

## 11. Sources Index

This section catalogues every Researcher-cited claim used in this synthesis (anchored by RESEARCH-002 § 10 bibliography SHA-pins) plus citations to existing project contracts.

### 11.1 Surveyed-repo citations (from RESEARCH-002 § 10 bibliography)

| Repo | SHA | Sections cited |
| --- | --- | --- |
| Gas Town | `gastownhall/gastown@18b1f4170c5f` | `docs/research/w-gc-004-agent-framework-survey.md:L25-L99` (full deep-dive), `:L41-L44` (worktree-vs-clone), `:L45-L53` (identity ledger), `:L54-L63` (priming), `:L64-L82` (pull-based hooks), `:L83-L99` (Mail/Nudge/Peek) |
| ORCH | `oxgeneral/ORCH@0c0694896b3a` | `CLAUDE.md:L28-L102` (full deep-dive), `:L41-L48` (DI), `:L49-L52` (state machine), `:L53-L61` (tick loop), `:L69-L81` (storage), `:L86-L93` (skill loader) |
| Bernstein | `sipyourdrink-ltd/bernstein@f950c71eddf0` | `docs/architecture/sandbox.md:L1-L100` (sandbox protocol), `:L21-L66` (typed interface), `:L67-L91` (capability negotiation), `:L93-L110` (backend matrix), `docs/architecture/storage.md:L1-L14` (storage), `:L63-L96` (buffered durability) |
| AgentsMesh | `AgentsMesh/AgentsMesh@93f56e498ebc` | `README.md:L100-L114` (control/data plane), `design/research/product-model.md:L20-L25` (Pod), `:L20-L36` (entity model), `:L26-L49` (Channels/PodBinding/Mesh), `:L56-L89` (zero-trust + permission gaps) |
| OpenCastle | `monkilabs/opencastle@18c6f2cf4e5c` | `README.md:L108-L122` (specialist agents + on-demand skills + quality gates), `:L155-L190` (Convoy example), `:L192-L204` (Convoy runtime guarantees) |
| Codebuff | `CodebuffAI/codebuff@54df847c6384` | `docs/architecture.md:L57-L97` (agent-runtime), `:L70-L81` (common package + registry), `:L83-L97` (agent catalog), `:L224-L231` (template system) |
| CLITrigger | `HyperAITeam/CLITrigger@fd4731bb3e20` | `README.md:L92-L129` (capture/delegate/review loop), `:L107-L115` (wiki injection), `:L117-L123` (planner), `:L125-L127` (worktree), `:L128-L134` (sessions) |
| Ralph | `mikeyobrien/ralph-orchestrator@3eca5177db33` | `README.md:L134-L168` (full deep-dive), `:L136-L142` (backpressure gates), `:L138-L142` (test/lint/typecheck), `:L144-L168` (Telegram RObot), `:L165-L170` (loop routing) |
| Letta Code | `letta-ai/letta-code@afac21583850` | `README.md:L5-L55` (memory-first design), `:L25-L39` (long-lived agents), `:L40-L49` (memory commands), `:L50-L55` (skill learning), `src/agent/memory.ts:L10-L19`, `:L83-L135` |
| OpenHands | `OpenHands/OpenHands@9482ab1a666d` | `README.md:L32-L83` (distribution surfaces), `:L34-L40` (SDK), `:L53-L72` (Cloud/Enterprise), `skills/agent_memory.md:L10-L30` (repo memory + governance) |
| kodo | `ikamensh/kodo@9758a0a1d0b1` | `docs/orchestration-tenets.md:L5-L30` (full tenets), `:L11-L13` (verification), `:L21-L30` (named failure modes) |
| claude-flow | `ruvnet/ruflo@02eee0bcdc55` | `README.md:L180-L216` (federation/swarm/AgentDB) |
| Aeon | `aaronjmars/aeon@5f2df0715aa3` | `README.md:L25-L44` (unattended schedules) |
| RA.Aid | `ai-christianson/RA.Aid@e71bb83dcfdf` | `README.md:L60-L90` (three-stage architecture) |
| AgentPipe | `kevinelliott/agentpipe@f27e126d854e` | `README.md:L73-L97` (conversation save/resume), `:L139-L145` |
| Plandex | `plandex-ai/plandex@e2d772072efa` | `README.md:L81-L106` (large-task planning) |
| Every Code | `just-every/code@861c9bab69d7` | `README.md:L29-L33` (Auto Drive + Auto Review) |
| gptme | `gptme/gptme@cf85d7d8b2c7` | `README.md:L96-L103` (plugin system + lessons) |

Each cited repo above is anchored by RESEARCH-002 § 10 SHA-pins; this synthesis does not introduce new SHAs.

### 11.2 Existing-project-contract citations

| Document | Version | Sections cited |
| --- | --- | --- |
| ARCH-001.md | v0.3.0 | § 8 (state model), § 9 (GitHub flow), § 11.1 (per-runtime layout), § 11.2 (IPC), § 11.3 (shared skills/plugins), § 11.4 (self-learning), § 13 (upstream adapter), § 14 (self-deployment), § 15 (escalation policy), § 16 (model catalog), § 17 (CI), § 21 (future possibilities) |
| MULTI-HERMES-CONTRACT.md | v0.2.1 | § 2 (five runtimes), § 3 (per-runtime identity), § 4 (per-runtime config), § 5 (skills loadout per role), § 5.0 (custom skill allowlist), § 5.0.1-5.6 (per-role tables), § 6.2 (work_items table), § 6.3 (escalations table), § 7 (decision capture) |
| HERMES-RUNTIME-CONTRACT.md | v0.2.0 | § 3 (governance state authority), § 4 (runtime input), § 5 (runtime output), § 9 (constraints) |
| HERMES-SKILL-ALLOWLIST.md | v0.1.2 | § 2 (deny-by-default), § 3 (deployment assumptions), § 4 (allowlist + gating mechanism), § 4.1 (Telegram), § 4.2-4.4 (bundled GitHub blocked), § 4.5 (delegate_task blocked), § 6 (project-local plugin policy), § 8 (credential scoping) |
| ESCALATION-POLICY.md | v0.1.1 | § 1 (purpose), § 2 (where it runs), § 3 (decision tree + fail-closed defaults), § 4 (deterministic rules), § 5 (concept-deviation classifier), § 5.5 (advisory narrative), § 9 (versioning) |
| PROJECT-CONCEPT.md | v0.1.0 | § 1 (purpose), § 2 (concept anchor block), § 3 (classifier algorithm) |
| OPERATIONAL-STATE-STORE.md | v0.2.1 | § 3.5 (work_items), § 3.6 (escalations) |
| OBSERVABILITY-CONTRACT.md | v0.1.x | FR-OBS-01..10 functional requirements |
| MODEL-CATALOG.md | v0.1.1 | § 4.1 (per-role assignments), § 5 (routing layer) |
| UPSTREAM-ADAPTER-CONTRACT.md | v0.1.x | (referenced from ARCH-001 § 13 for v0.2+ OpenClaw posture) |
| SELF-DEPLOYMENT-CONTRACT.md | v0.2.0 | § 5 (systemd units), § 5.2 (sandbox directives), § 6 (rollback), § 7 (operational.db backup) |
| ADR-001..014 | various | full text per `docs/architecture/adr/ADR-NNN-*.md` |
| PRD-001.md | v0.2.1 | § 4 (non-goals), § 6 (functional requirements), § 11 (deferred items), § 12 (self-deployment), § 13.1 (autonomy / escalation), § 13.2 (multi-Hermes mandate), § 13.3 (upstream composability) |
| AGENTS.md | (always-on) | role table, cross-model independent review doctrine, default language policy |
| CONTRIBUTING.md | (always-on) | § Roles (write zones), § Ticket lifecycle |
| RESEARCH-001-hermes-and-openclaw-ecosystems.md | v0.1.x | § 3.2 (one Hermes = one process), § 3.5 (memory model), § 6.2 (memory broker rejection), § 7 (skill_manage open item) |
| RESEARCH-002-multi-agent-dev-systems-survey.md | v0.1.0 | full document — § 3 pain points, § 5 comparative table, § 6 deep dives, § 7 themes, § 8 shortlist, § 9 open questions, § 10 bibliography |
| SESSION-STATE.md | v0.2.8 | (referenced for current-phase context only; not amended by this synthesis) |
