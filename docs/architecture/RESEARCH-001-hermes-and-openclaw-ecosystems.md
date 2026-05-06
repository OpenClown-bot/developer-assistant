---
id: RESEARCH-001
version: 0.1.0
status: draft
---

# RESEARCH-001: Hermes Agent And OpenClaw Ecosystems Research Findings

## 1. Purpose

This document records the deep-research findings collected during the Architect pass that produced ARCH-001 v0.3.0. It exists so that:

- Every architectural claim about Hermes Agent or OpenClaw in ARCH-001, the contracts, and the ADRs can be traced back to a cited source rather than to vendor marketing or assumed behavior.
- A future Reviewer (RV-SPEC) and a future Architect refresh can re-validate the findings against the current versions of those products without redoing the discovery from scratch.
- The Founder can see, in one place, what the assistant actually is built on and what it is not built on.

This document is a research record. It does not implement runtime behavior, install software, or commit to a deployment path. The implementation commitments live in `ARCH-001.md`, the contract documents (`SELF-DEPLOYMENT-CONTRACT.md`, `MULTI-HERMES-CONTRACT.md`, `UPSTREAM-ADAPTER-CONTRACT.md`, `ESCALATION-POLICY.md`, `MODEL-CATALOG.md`), the ADRs in this pass (ADR-004 through ADR-009), and the implementation tickets (TKT-020 through TKT-026).

## 2. Scope Of The Research

The Architect prompt for this pass required deep research on:

- **Hermes Agent**: runtime architecture, skill system, plugin system, memory system, tool calling, security model, configuration, deployment.
- **OpenClaw**: agent runtime, skill/plugin model, multi-channel gateway, A2A plugin architecture, deployment.
- **Cross-ecosystem**: A2A protocols, multi-process supervision (systemd, s6, supervisord, Docker Compose), SQLite for agent memory, LLM routing layers.

This document records what was found in each area. It does not record exhaustive plugin catalogs; it records what is structurally relevant to the multi-Hermes runtime, self-deployment, escalation, and upstream-adapter design choices made in this pass.

## 3. Hermes Agent Findings

### 3.1 Identity And Versioning

- **Source**: `https://github.com/NousResearch/hermes-agent` (MIT license).
- **Version pinned for v0.1**: `v2026.4.30` ("Curator" release), commit `73bf3ab1b22314ed9dfecbb59242c03742fe72af`.
- **Documentation**: `https://hermes-agent.nousresearch.com/docs/`.
- **Distribution**: one-line installer that drops a Hermes installation under `~/.hermes/` (per-user) or `/usr/local/lib/hermes-agent/` (root install). Installer auto-installs Python 3.11, Node.js 22, ripgrep, ffmpeg if missing. Git is the only required prerequisite.
- **Configuration root**: a single directory referred to as `HERMES_HOME`. Default is `~/.hermes/`, overridable via the `HERMES_HOME` environment variable. The directory contains `config.yaml`, `.env`, `auth.json`, `SOUL.md`, `memories/`, `skills/`, `cron/`, `sessions/`, `logs/`, and the SQLite session/state database.

Citation: Hermes Agent docs, Installation and Configuration sections, retrieved during this Architect pass; version pin and commit also recorded in `HERMES-SKILL-ALLOWLIST.md` § 3.

### 3.2 Process Model

The single most important structural finding for this design pass:

> **A Hermes installation is one OS-level process per `HERMES_HOME`. Hermes does not natively run multiple isolated specialist runtimes inside one installation.**

What Hermes does provide inside one runtime:

- **`delegate_task`** spawns short-lived child agents (subagents) inside the same parent process. Subagents have their own context window and can be assigned a different model and toolset, but they are not durable runtimes; they finish their delegated task and return.
- **`role` parameter** on subagents permits nested delegation but is bounded by a depth limit and a per-subagent timeout (default 600 seconds).
- **Up to 3 concurrent subagents per parent** by default, configurable.

Consequences for `developer-assistant`:

- Five **specialist** Hermes runtimes (Orchestrator, Business Planner, Architect, Executor, Reviewer) cannot live inside one Hermes process. They require **five separate `HERMES_HOME` directories supervised externally**.
- Per-runtime memory isolation is therefore **filesystem-level**: each runtime has its own `~/.hermes/memories/MEMORY.md`, `USER.md`, sessions database, and skills directory. There is no implicit shared-memory accident path between runtimes through Hermes' own state. Cross-runtime read/write through normal Linux DAC is prevented by systemd sandbox directives (`ProtectHome=`, `ReadWritePaths=`, `BindReadOnlyPaths=`, `PrivateTmp=`) since all five runtimes share a single Linux uid (`devassist`); the isolation guarantee is conditional on correct systemd unit configuration.
- The Founder-facing process is one of the five (the Orchestrator runtime running the Telegram gateway). Specialist runtimes never directly face the Founder.

Citation: Hermes Agent docs § Sessions, § Delegation (delegate_task), § Configuration. Confirmed by inspecting the `~/.hermes/` directory layout described in the docs and the `delegate_task` tool reference.

### 3.3 Skills System

- **Skills** are markdown-and-script bundles loaded from `~/.hermes/skills/` and from any directories listed in `config.yaml` under `skills.external_dirs`.
- Each skill has a `SKILL.md` manifest with metadata (name, description, platform constraints, fallback toolsets, required env vars).
- **Progressive disclosure**: the agent first calls `skills_list`, then `skill_view` to read a specific skill, then `skill_view` with a path to read referenced files. This avoids loading every skill into the prompt.
- **Conditional activation**: skills can declare `requires_toolsets` or `fallback_for_toolsets` to activate only when certain toolsets are enabled or as a fallback when a primary toolset is missing.
- **Required environment variables**: skills can declare env vars needed at load time (`required_environment_variables`); if missing, the skill is skipped or guided through setup.
- **Agent-managed skills**: the `skill_manage` tool lets the agent create, patch, or delete skills at runtime. v0.1 deployments must keep this **disabled** for production credential-bearing runtimes (per `HERMES-SKILL-ALLOWLIST.md` § 5).
- **Built-in skills bundled with Hermes**: include `telegram-gateway`, `github-pr-workflow`, `github-issues`, `github-auth`, plus many platform integrations.

Consequences for `developer-assistant`:

- Each specialist runtime can load a **different curated set of skills** by writing different `~/.hermes/config.yaml` and a different per-runtime `skills/` directory.
- A single shared skill source can be loaded by all five runtimes via `skills.external_dirs: [/srv/devassist/shared-skills]`. This is the load path used for the project's own custom `dev-assist-*` skills (defined in `MULTI-HERMES-CONTRACT.md` § 5 and TKT-026).
- The bundled `github-*` skills failed source review for production credentials in TKT-012 and remain blocked for production use in `HERMES-SKILL-ALLOWLIST.md` § 4.2-4.4. The project must continue to use its own GitHub workflow capability, not the bundled skills.

Citation: Hermes Agent docs § Skills, § Tools And Toolsets; `HERMES-SKILL-ALLOWLIST.md` § 4.

### 3.4 Tools And Toolsets

- Hermes ships ~68 built-in tools grouped into logical toolsets: `web`, `terminal`, `file`, `browser`, `vision`, `image_gen`, `memory`, `cronjob`, `delegation`, etc.
- **Terminal backends**: `local`, `docker`, `ssh`, `modal`, `daytona`, `vercel_sandbox`, `singularity`. The `docker` backend runs a single persistent container shared across sessions of one runtime, with `--cap-drop ALL`, `--security-opt no-new-privileges`, `--pids-limit 256`, and a size-limited tmpfs by default.
- **Background processes**: `terminal(background=true)` plus the `process` tool support long-running processes inside the terminal sandbox.

Consequences for `developer-assistant`:

- Executor and Reviewer runtimes use the `docker` terminal backend. Other runtimes (Orchestrator, Business Planner, Architect) do not need a terminal sandbox at all and can run with the toolset disabled.
- Paid sandbox backends (`modal`, `daytona`, `vercel_sandbox`) are **not used in v0.1** because they introduce a paid third-party as a hard runtime dependency, which violates the v0.1 budget envelope. They remain a v0.2+ option per "Future Possibilities" in `ARCH-001.md` § 21.

Citation: Hermes Agent docs § Tools, § Terminal Backends; `HERMES-SKILL-ALLOWLIST.md` § 4.6.

### 3.5 Memory System

Hermes' persistent memory is organized as:

- **`~/.hermes/memories/MEMORY.md`** (~2,200 chars): general operational memory, injected as a frozen snapshot at session start.
- **`~/.hermes/memories/USER.md`** (~1,375 chars): user-specific facts, similarly injected.
- **Sessions database** (`~/.hermes/state.db`): SQLite with FTS5 full-text search across all past sessions; queryable via the `session_search` tool.
- **JSONL transcripts** (`~/.hermes/sessions/`): one file per session for full transcript replay.

Memory updates are explicit: the `memory` tool has `add`, `replace`, and `remove` actions. There is no automatic memory write; the agent must decide to update memory.

Consequences for `developer-assistant`:

- **Per-runtime memory isolation is filesystem-level**: each of the five specialist runtimes has its own `MEMORY.md`, `USER.md`, sessions database, and JSONL transcripts because they have different `HERMES_HOME` directories. There is no shared-memory accident path between runtimes through Hermes itself. Cross-runtime read/write through normal Linux DAC (same uid) is prevented by systemd sandbox directives applied per unit (`ProtectHome=`, `ReadWritePaths=`, `BindReadOnlyPaths=`, `PrivateTmp=`); see `MULTI-HERMES-CONTRACT.md` § 7.
- **Operational vs governance state**: Hermes memory is operational state per `HERMES-RUNTIME-CONTRACT.md` § 3 and `OPERATIONAL-STATE-STORE.md` § 8. It must not become the only place where product, architecture, security, merge, or deployment decisions are recorded.
- **Self-learning state**: a runtime's `MEMORY.md`, `USER.md`, sessions database, and any agent-managed skills it created at runtime are part of its self-learning state. Self-deployment rollback and upgrade must preserve these per-runtime per `SELF-DEPLOYMENT-CONTRACT.md` § 7.

Citation: Hermes Agent docs § Memory, § Sessions; `HERMES-RUNTIME-CONTRACT.md` § 3; `OPERATIONAL-STATE-STORE.md` § 8.

### 3.6 Cron And Scheduled Jobs

- The `cronjob` tool supports `create`, `edit`, `pause`, `resume`, `run`, `remove`, `list` actions.
- Jobs persist under `~/.hermes/cron/` and tick every 60 seconds.
- Jobs can be skill-backed or no-agent script-only.
- **Delivery options** include `origin` (the Hermes session that scheduled it), `local` (output to logs only), `telegram`, `discord`, `slack`, `email`, etc. Output can be wrapped with `[SILENT]` markers to suppress delivery while still writing logs.

Consequences for `developer-assistant`:

- The Orchestrator runtime owns the **30-60 minute progress report cron** per `PRD-001.md` § 5 Journey 6 and `ARCH-001.md` § 7. It runs as a cron job inside the Orchestrator's `~/.hermes/cron/` directory and delivers to Telegram.
- Each specialist runtime can own its own cron job for runtime-internal maintenance (e.g., a polling tick for the work queue described in `MULTI-HERMES-CONTRACT.md` § 6) without coordination through a global scheduler.
- **Cron approval mode**: cron jobs must run under `approvals.mode: manual` (or its equivalent post-headless gate) so that scheduled tool calls do not bypass interactive approval. This is captured in `HERMES-SKILL-ALLOWLIST.md` § 4.7 as a hardening requirement for v0.1.

Citation: Hermes Agent docs § Cron, § Approvals; `HERMES-SKILL-ALLOWLIST.md` § 4.7.

### 3.7 Telegram Gateway

- Built-in gateway covers 15+ messaging platforms (Telegram, Discord, Slack, WhatsApp, Signal, Matrix, Mattermost, Email, SMS, etc.).
- **Per-chat session store**: each chat (or user, depending on configuration) gets its own continuing session. Commands like `/new`, `/model`, `/retry`, `/compress`, `/title`, `/resume`, `/background` modify session behavior from inside the chat.
- **Authentication options** for Telegram: `TELEGRAM_ALLOWED_USERS` allowlist, DM pairing, optional webhook secret, polling vs webhook mode.
- **Bot identity**: one Telegram bot per Hermes runtime, identified by the `TELEGRAM_BOT_TOKEN`.

Consequences for `developer-assistant`:

- **Only the Orchestrator runtime carries the `telegram-gateway` skill**. The other four runtimes do not face Telegram; the Founder addresses one bot identity, period.
- **Polling mode in v0.1**: webhook mode requires public-internet exposure of the VPS, which raises the security-and-firewall surface. Polling mode keeps the VPS outbound-only. Webhook mode is reconsidered after v0.1 stabilizes.
- **Allowlist enforced**: `TELEGRAM_ALLOWED_USERS` must be set; `GATEWAY_ALLOW_ALL_USERS` and `TELEGRAM_ALLOW_ALL_USERS` must remain unset/false. This is recorded in `HERMES-SKILL-ALLOWLIST.md` § 4.1.

Citation: Hermes Agent docs § Messaging Gateway, § Telegram Setup; `HERMES-SKILL-ALLOWLIST.md` § 4.1.

### 3.8 Plugin System

- Plugins are **Python packages** discovered through `pip` entry-points (the standard Python plugin registration mechanism).
- Plugins can register **hooks** at well-defined extension points: `pre_gateway_dispatch`, `pre_tool_call`, `post_tool_call`, `pre_session_start`, `post_session_end`, etc.
- **Project-local plugins**: opt-in via `HERMES_ENABLE_PROJECT_PLUGINS=true` reading from a `.hermes/plugins/` directory in the active workspace. v0.1 keeps this **disabled** per `HERMES-SKILL-ALLOWLIST.md` § 3.
- **Marketplace auto-installation**: explicitly disabled per ADR-003.

Consequences for `developer-assistant`:

- The **escalation-policy enforcement plugin** (`dev-assist-escalation-policy`) is a Hermes plugin distributed as a Python package, installed via pip into each runtime's environment, and registered as an entry-point. It registers a `pre_tool_call` hook that runs the deterministic and LLM-classified checks in `ESCALATION-POLICY.md`.
- The **work-queue polling plugin** (`dev-assist-work-queue`) is a similar Python plugin that exposes tools the runtime calls each loop iteration to claim, complete, or release work items in the SQLite operational store.
- The same plugin package can be installed into all five runtimes; runtime-specific behavior is gated by checking the runtime's role assignment, which is read from a per-runtime config value (e.g., `HERMES_DEVASSIST_ROLE`).

Citation: Hermes Agent docs § Plugins, § Configuration; `HERMES-SKILL-ALLOWLIST.md` § 3, § 4.

### 3.9 Security Posture

- **Approval modes**: `manual`, `smart`, `off`, plus a "headless" mode for cron jobs. v0.1 requires `manual` (per `HERMES-SKILL-ALLOWLIST.md` § 3) and never `off` (no YOLO mode in production).
- **Project-local plugins disabled** by default in v0.1.
- **Marketplace auto-installation disabled** by default in v0.1.
- **Per-tool credential scoping**: each tool can declare which env vars it needs; tools that do not need a credential do not see it.

Consequences for `developer-assistant`:

- The escalation-policy plugin pre-empts dangerous commands at the `pre_tool_call` hook layer, before they reach the Hermes-level approval prompt. The Hermes approval prompt remains as a **second** safety net, not the only one.
- Sandboxed terminal (Docker backend) is required for Executor and Reviewer; the `local` terminal backend is allowed only during development on a non-production runtime.

Citation: Hermes Agent docs § Security; `HERMES-SKILL-ALLOWLIST.md` § 2, § 3.

### 3.10 What Hermes Does NOT Do

These are limitations relevant to the design pass that the Architect must absorb rather than wish away:

- **No native multi-runtime supervision**. One Hermes installation is one process. Five specialist runtimes need five installations and an external supervisor.
- **No native A2A protocol**. Hermes runtimes can talk to each other through tool calls only when they are on the same machine and both expose tools the caller can reach (e.g., via MCP HTTP server, see § 3.11). No first-class agent-to-agent message bus.
- **No native escalation classifier**. Hermes has approval modes and tool-call hooks, but the rule "deviates from concept OR risks breaking state" must be implemented in the project's plugin layer, not assumed.
- **No native multi-tenant isolation**. v0.1 is single-Founder; multi-tenant scoping is out of scope per `PRD-001.md` § 4.
- **`delegate_task` is intra-process**. It does not let one Hermes runtime delegate to another Hermes runtime. Cross-runtime work is mediated by the SQLite work queue described in `MULTI-HERMES-CONTRACT.md` § 6.

Citation: Inspection of Hermes Agent docs and source structure during this Architect pass; the absence of these features is the structural finding.

### 3.11 MCP Integration

- Hermes supports **Model Context Protocol** (MCP) servers as tool sources, both stdio (local subprocess) and HTTP.
- Tools from MCP servers are exposed under `mcp_<server_name>_<tool_name>`.
- MCP servers can be filtered (`include`/`exclude`) per server.
- A Hermes runtime can be both an MCP **client** (consuming tools from external servers) and, when wrapped, an MCP **provider** (exposing its own tools).

Consequences for `developer-assistant`:

- **MCP is the v0.2+ interop surface** for letting one specialist Hermes runtime expose a narrow toolset to a future external upstream (e.g., OpenClaw). v0.1 does **not** rely on MCP between runtimes, because the SQLite work queue is simpler, more observable, and avoids running per-runtime HTTP servers.
- The escalation-policy plugin can later be expressed as an MCP-backed classifier if cross-runtime classifier sharing is needed; v0.1 keeps it in-process per ADR-008.

Citation: Hermes Agent docs § MCP Integration.

## 4. OpenClaw Findings

### 4.1 Identity And Position

- **Source**: `https://github.com/openclaw/openclaw`.
- **Documentation**: `https://docs.openclaw.ai/`.
- **What it is**: a multi-channel agent gateway with an embedded Pi agent runtime, multi-agent routing, workspace-based configuration, plugin system, and skill loading from multiple sources.
- **What it is not (for v0.1)**: a runtime that replaces Hermes. ADR-001 selected Hermes-first for v0.1; ADR-003 prohibits OpenClaw plugins in v0.1. OpenClaw enters the picture only as a **future upstream entry-point** alongside Telegram (see `UPSTREAM-ADAPTER-CONTRACT.md` § 4 and `PRD-001.md` § 13.3).

Citation: OpenClaw docs § Tools / Skills, § Tools / Plugin, § Plugins / Community; freecodecamp's "OpenClaw A2A Plugin Architecture Guide" retrieved during this pass.

### 4.2 Skill And Plugin Model

- OpenClaw skills are similar in spirit to Hermes skills (markdown manifest + scripts) but the manifest schema differs.
- OpenClaw plugins are loaded **in-process** with the gateway, which makes the supply-chain risk equivalent to or higher than Hermes. ADR-003 § Decision keeps OpenClaw plugins out of v0.1 for this reason.
- OpenClaw provides a documented A2A (Agent-to-Agent) plugin architecture pattern: an OpenClaw instance can call out to other agents (potentially Hermes) by treating them as A2A-protocol-speaking peers.

Consequences for `developer-assistant`:

- v0.1 does **not** load OpenClaw skills or plugins. The OpenClaw bridge in v0.2+ is implemented on the OpenClaw side as a thin adapter that talks to the developer-assistant Orchestrator runtime over a defined adapter protocol (see `UPSTREAM-ADAPTER-CONTRACT.md` § 5). The OpenClaw side's plugin trust posture is the OpenClaw operator's responsibility, not this project's.

Citation: OpenClaw docs § Tools / Plugin, § Plugins / Community; ADR-003.

### 4.3 Multi-Channel Gateway

- OpenClaw can present a unified gateway across multiple messaging channels (Slack, Discord, Telegram, web, etc.), much like Hermes.
- Workspace-based configuration: each OpenClaw workspace can define its own routing policy, agent set, plugin set, and credentials.

Consequences for `developer-assistant`:

- For v0.2+, an OpenClaw workspace can expose `developer-assistant` to the Founder as one of many delegated agents, alongside whatever else the Founder uses OpenClaw for. The Founder addresses OpenClaw, OpenClaw addresses `developer-assistant`'s Orchestrator runtime through the upstream-adapter, the Orchestrator addresses the specialist runtimes through the SQLite queue. The Founder still sees one assistant identity per channel.

Citation: OpenClaw docs § Tools / Skills, § Plugins / Community.

### 4.4 A2A Plugin Architecture

- OpenClaw documents an A2A plugin pattern that follows the open A2A protocol (`https://a2a-protocol.org/`).
- A2A defines: agent discovery (a well-known endpoint that lists capabilities), task negotiation, task delegation, secure information exchange. Notably, A2A **does not require exposing internal state, memory, or tools** of the receiving agent — it exposes only an external task contract.

Consequences for `developer-assistant`:

- A2A is an **interop contract** between this project and external agents (including OpenClaw). It is not the v0.1 cross-runtime IPC mechanism. ADR-006 chose SQLite-mediated IPC for the same-host five-runtime case because A2A would force every runtime to expose an HTTP server and re-implement queueing/idempotency that SQLite already gives us.
- A2A becomes the v0.2+ shape for the **upstream** boundary. The Orchestrator runtime can expose an A2A-compliant endpoint for OpenClaw or any other A2A-speaking peer.

Citation: A2A protocol docs (v1.0.0 released 2026-03-12); freecodecamp's "OpenClaw A2A Plugin Architecture Guide".

### 4.5 OpenClaw Limitations For v0.1

- **In-process plugins** raise supply-chain risk equivalent to or higher than Hermes.
- **Workspace-based config** is a richer surface than v0.1 needs; one Founder, one assistant, one bot identity is the v0.1 simplification.
- **Multi-agent routing inside OpenClaw** is redundant with the multi-Hermes work queue this design adopts; running both routing layers in v0.1 would double the moving parts without changing the user-facing behavior.

Therefore:

- v0.1 does not use OpenClaw at all.
- v0.2+ uses OpenClaw only as an upstream adapter (Founder enters through OpenClaw, OpenClaw forwards to Orchestrator). OpenClaw is not the gateway, runtime, or scheduler for `developer-assistant` itself.

Citation: OpenClaw docs § Plugins / Community; ADR-001 § Decision; ADR-003 § Decision; `PRD-001.md` § 13.3.

## 5. Cross-Ecosystem Findings

### 5.1 A2A Protocol

- A2A is an open agent-to-agent protocol (v1.0.0, 2026-03-12) that defines: agent cards (a well-known JSON descriptor of capabilities), task lifecycle (submit / poll / complete), and secure channel negotiation.
- A2A is meant to interop **between** agents owned by different operators. It is not optimized for tight intra-system IPC between five processes on one host.
- A2A is one of several candidate protocols evaluated in ADR-006 § Options Considered; the chosen mechanism is SQLite-mediated work queue (Option C) for v0.1 with A2A reserved for the v0.2+ upstream boundary.

Citation: `https://a2a-protocol.org/` retrieved during this pass.

### 5.2 Multi-Process Supervision Options

Three supervision patterns evaluated for the five-Hermes case:

- **Option A — Single multi-process container with `s6-overlay`**. One Docker image, multiple processes, init system inside the container. Pro: one image to ship. Con: one image fault zone; restarting one runtime requires careful s6 config.
- **Option B — Docker Compose with one container per runtime**. Five services, one network. Pro: clean isolation, easy `docker compose logs <service>`. Con: requires Docker as a hard dependency on the VPS, larger disk and memory footprint.
- **Option C — systemd units on the host**. Five `*.service` units under one `devassist.target`. Pro: native to Ubuntu 22.04 LTS, no Docker required for runtimes themselves, journalctl logs, simple rollback. Con: requires the install script to be idempotent and Hermes-aware.

ADR-004 selects **Option C (systemd)** for v0.1 because it minimizes new dependencies on a $5/month-class VPS, gives the Founder familiar tooling (`systemctl`, `journalctl`), and aligns with Hermes' own `hermes gateway install --system` documentation.

Citation: systemd unit documentation (`man systemd.service`, `man systemd.target`); s6-overlay documentation; Docker Compose v2 documentation; Hermes Agent docs § Deployment.

### 5.2.1 Installation Time And Steady-State Resource Footprint (Unverified Estimates)

Two numbers are load-bearing for v0.1 feasibility but were **not** measured during this research pass. They are recorded here as **unverified estimates** with explicit validation tasks so an implementation ticket (TKT-020) can replace them with empirical numbers before TKT-011 dispatches.

**Hermes Agent installation time on a clean Ubuntu 22.04 LTS VPS** (relevant to `PRD-001.md` § 12 15-minute bound):

- Estimate: **~5 minutes (300 seconds)** for the one-line installer cold-cache (~400 MB Python-package fetch over residential-grade outbound bandwidth on a 2 vCPU / 4 GB RAM VPS), based on the Hermes Agent installer's documented "large initial fetch + venv setup + first-time pip resolve" steps.
- Citation: Hermes Agent docs § Installation describe the installer behavior; no time figure is published in the upstream docs at retrieval time. The 300 s estimate is the Architect's worst-case derivation, not a measured value.
- Validation task: TKT-020 § Acceptance Criteria includes a dry-run on a fresh Ubuntu 22.04 LTS VPS that records the actual install time and updates `ADR-004 § Timing Feasibility` if the measured value diverges by >25% from the 300 s estimate.
- Mitigation if measured >480 s (8 minutes): pre-stage the Hermes installer tarball into the project's `vendor/` directory at architect-pass time and replace the live one-line install with a local-file install. This eliminates the ~400 MB outbound fetch from the budget.

**Steady-state per-Hermes-runtime memory footprint** (relevant to whether five runtimes fit in 4 GB RAM with headroom for Docker terminal sandboxes):

- Estimate: **~300-600 MB resident per Hermes runtime** under steady state (one Python process per `HERMES_HOME`, with skills loaded but no active session). Total for five runtimes: **~1.5-3 GB**.
- Citation: Hermes Agent docs do not publish a per-process memory figure; the 300-600 MB range is the Architect's projection from typical Python-LLM-client process sizes (Hermes uses a Python runtime with ~50-80 MB minimum baseline plus skill payload).
- Validation task: TKT-020 § Acceptance Criteria includes capturing `systemd-cgls --memory devassist.target` output post-startup and recording it as evidence in the install verification report.
- Mitigation if measured total >3 GB on the target VPS profile: (a) consolidate Business Planner + Architect runtimes into one (they have similar idle profiles), or (b) require a 6+ GB RAM VPS as the v0.1 minimum, or (c) defer Reviewer runtime by inlining Reviewer work into Architect runtime until v0.2.

These two estimates are flagged as **assumptions, not findings**, in this research record. ADR-004 § Timing Feasibility consumes them and `MULTI-HERMES-CONTRACT.md` § 11 records the steady-state footprint figure traceably back here.

### 5.3 SQLite As An IPC Substrate

- SQLite is stdlib in Python; no extra server process.
- SQLite supports WAL mode (`PRAGMA journal_mode=WAL`) for concurrent readers while a writer holds the lock.
- A simple `work_items` table with a status column and a per-row `claimed_by` field plus `UPDATE ... WHERE status='pending' LIMIT 1` (with `RETURNING` on SQLite ≥ 3.35) gives an at-most-once dispatch primitive without a separate queue server.

Consequences for `developer-assistant`:

- v0.1 uses SQLite (the same `state.db` already adopted by `OPERATIONAL-STATE-STORE.md`) as the work queue. Two new tables (`work_items` and `escalations`) are added in this pass and described in `MULTI-HERMES-CONTRACT.md` § 6.
- Heavier alternatives (Redis, NATS, RabbitMQ) are deferred until the SQLite path proves insufficient. ADR-006 records this trade-off.

Citation: SQLite docs § WAL, § RETURNING; `OPERATIONAL-STATE-STORE.md` § 9.

### 5.4 Model Routing And Catalog

- The Founder set role-model assignments on 2026-05-05; see `docs/orchestration/SESSION-STATE.md` § Current Tooling Decisions and `docs/backlog/TKT-NEW-to-rationale-doctrine-collision.md`.
- Models are reached through OmniRoute (and OpenRouter as a backup), not through direct provider SDKs. This decouples runtime config from any single provider's API shape.
- Within the Founder-pre-approved catalog (see `MODEL-CATALOG.md`), specialist runtimes pick the model best suited to their role without escalation. Additions to the catalog escalate per `ESCALATION-POLICY.md` § 4.

Citation: `docs/orchestration/SESSION-STATE.md`; `docs/backlog/TKT-NEW-to-rationale-doctrine-collision.md`; `MODEL-CATALOG.md` § 3.

### 5.5 LLM Sandbox Backends Cost Posture

The Hermes terminal tool supports paid sandbox backends (`modal`, `daytona`, `vercel_sandbox`). These are explicitly **not** adopted in v0.1 because they introduce a paid third-party as a hard runtime dependency, which violates the v0.1 budget envelope (one Founder-owned VPS plus already-approved LLM API spend; no other recurring paid services). The local `docker` backend is the v0.1 choice for Executor and Reviewer.

Paid sandboxes remain a v0.2+ option in ARCH-001 § 21 "Future Possibilities" once a concrete benefit is identified and the Founder explicitly approves the line item.

Citation: Hermes Agent docs § Terminal Backends; ARCH-001.md § 21; `PRD-001.md` § 13.1 (paid third-party action escalates).

## 6. Synthesis Insights Used By This Pass

The following insights from the research above are the reason the design choices in this pass take the shape they do. Each insight maps to one or more design choices.

### 6.1 Five Specialist Runtimes Require Five Hermes Installations

- Source: § 3.2.
- Used in: `MULTI-HERMES-CONTRACT.md` § 4 (per-runtime layout), `SELF-DEPLOYMENT-CONTRACT.md` § 4 (filesystem layout), ADR-005 § Decision.
- Resource footprint estimate: **~1.5-3 GB total resident memory** for five idle Hermes runtimes on the target VPS, flagged as unverified in § 5.2.1; validated empirically during TKT-020 dry-run.

### 6.2 Memory Isolation Between Runtimes Is Filesystem-Level (Conditional On Correct Sandboxing)

- Source: § 3.5.
- Used in: `MULTI-HERMES-CONTRACT.md` § 7 (memory and self-learning state), ADR-005 § Consequences. The PRD's strict per-role isolation (§ 13.2 and § 7 NFR) is satisfied by the natural Hermes filesystem layout (separate `HERMES_HOME`) plus systemd sandbox directives (`ProtectHome=`, `ReadWritePaths=`, `BindReadOnlyPaths=`, `PrivateTmp=`), not by a custom memory broker. The five runtimes share a single Linux uid (`devassist`); the isolation guarantee is conditional on correct systemd unit configuration. v0.1's single-Founder threat model accepts the shared-uid limitation.

### 6.3 Cross-Runtime IPC Is Best Mediated By The Repository And The SQLite Store

- Source: § 3.10, § 5.3.
- Used in: `MULTI-HERMES-CONTRACT.md` § 6 (work-items schema), ADR-006 § Decision. Avoiding A2A and HTTP-between-runtimes for v0.1 cuts moving parts and aligns with the existing `OPERATIONAL-STATE-STORE.md`.

### 6.4 Escalation Enforcement Belongs In A Hermes Plugin Layer

- Source: § 3.8, § 3.9, § 3.10.
- Used in: `ESCALATION-POLICY.md` § 5 (deterministic rules), § 6 (LLM classifier), ADR-008 § Decision. Hermes' approval modes are the second safety net; the project's escalation-policy plugin is the first.

### 6.5 Telegram Stays On The Orchestrator Only; Adapter Boundary Lives Above The Specialist Runtimes

- Source: § 3.7, § 4.3.
- Used in: `UPSTREAM-ADAPTER-CONTRACT.md` § 4-5, ADR-007 § Decision. v0.1 ships only the Telegram adapter inside the Orchestrator runtime; v0.2+ adds OpenClaw or another A2A-speaking adapter without touching specialist runtimes.

### 6.6 systemd Wins For v0.1 Self-Deployment

- Source: § 5.2.
- Used in: `SELF-DEPLOYMENT-CONTRACT.md` § 5 (units), ADR-004 § Decision. Docker Compose and s6-overlay remain documented alternatives for later evaluation.

### 6.7 Founder-Pre-Approved Model Catalog Removes Per-Decision Escalation Friction

- Source: § 5.4.
- Used in: `MODEL-CATALOG.md`, ADR-009 § Decision. Within-catalog model picks are autonomous; catalog changes escalate.

### 6.8 No Paid Third-Party Hard Dependencies In v0.1

- Source: § 5.5; `PRD-001.md` § 13.1.
- Used in: ADR-004 § Decision (no `modal`/`daytona`/`vercel_sandbox` backend), ADR-006 § Decision (no managed Postgres / managed vector store), ADR-008 § Decision (LLM classifier reuses already-approved OmniRoute spend), `MODEL-CATALOG.md` § 3.

## 7. Open Research Items

These remain open and are intentionally not closed in this pass. They are not blockers for ARCH-001 v0.3.0 but should be re-examined when revisiting the design or before related implementation tickets enter `ready` status.

1. **Hermes runtime memory ceiling under concurrent specialist load**: empirical question; needs measurement on the target VPS once self-deployment is exercised. Owner: Executor of TKT-020; deliverable: a note appended to `MULTI-HERMES-CONTRACT.md` § 11.
2. **OpenClaw upstream adapter**: not in v0.1 scope; v0.2+ ticket required. Owner: future Architect pass; trigger: Founder request to begin OpenClaw-side integration.
3. **Per-runtime self-learning skill creation policy**: `skill_manage` is disabled in v0.1 production; whether and when to allow runtime-created skills under supervisory-only review is a v0.2+ governance question. Owner: future Architect pass.
4. **Model catalog refresh cadence**: how often to re-examine the catalog against newly available models is a Founder decision; the Architect refresh discussed in `docs/backlog/TKT-NEW-to-rationale-doctrine-collision.md` is the closest existing doctrine touchpoint.

## 8. Bibliography

| Source | Used For |
| --- | --- |
| `https://github.com/NousResearch/hermes-agent` (v2026.4.30, commit `73bf3ab1b22314ed9dfecbb59242c03742fe72af`) | § 3 Hermes findings; allowlist version pin |
| `https://hermes-agent.nousresearch.com/docs/` (Installation, Configuration, Sessions, Messaging, Skills, Tools, Memory, Cron, Delegation, MCP, Plugins, Security) | § 3 all subsections |
| `https://github.com/openclaw/openclaw` | § 4 OpenClaw findings |
| `https://docs.openclaw.ai/` (Tools / Skills, Tools / Plugin, Plugins / Community) | § 4 OpenClaw findings |
| `https://www.freecodecamp.org/news/openclaw-a2a-plugin-architecture-guide/` | § 4.4 A2A pattern |
| `https://a2a-protocol.org/` (v1.0.0, 2026-03-12) | § 4.4, § 5.1 |
| `man systemd.service`, `man systemd.target` (Ubuntu 22.04 LTS) | § 5.2 supervisor option C |
| s6-overlay docs | § 5.2 supervisor option A |
| Docker Compose v2 docs | § 5.2 supervisor option B |
| SQLite docs § WAL, § RETURNING | § 5.3 |
| `docs/orchestration/SESSION-STATE.md` (current) | § 5.4 |
| `docs/backlog/TKT-NEW-to-rationale-doctrine-collision.md` | § 5.4 |
| `docs/backlog/TKT-NEW-self-deployment-architect-pass.md` | scope motivation |
| `docs/prd/PRD-001.md` v0.2.1 § 12-13 | scope motivation |
| `docs/architecture/ARCH-001.md` v0.2.0 (baseline) | revision input |
| `docs/architecture/HERMES-RUNTIME-CONTRACT.md` v0.2.0 | § 3 Hermes findings, boundary preservation |
| `docs/architecture/HERMES-SKILL-ALLOWLIST.md` v0.1.0 | § 3.3, § 3.7, § 3.9 |
| `docs/architecture/OPERATIONAL-STATE-STORE.md` v0.2.0 | § 5.3 |
| `docs/architecture/GENERATED-PROJECT-DEPLOYMENT-CONTRACT.md` v0.1.0 | distinction from self-deployment |
| `docs/architecture/adr/ADR-001-platform-foundation.md` v0.2.0 | Hermes-first baseline |
| `docs/architecture/adr/ADR-002-repository-state.md` v0.2.0 | split state model |
| `docs/architecture/adr/ADR-003-plugin-supply-chain.md` v0.2.0 | OpenClaw v0.1 deferral |
| `docs/reviews/RV-CODE-024.md` | review-language conventions for tickets |
| `docs/session-log/2026-05-06-session-1.md` | latest authoritative project state |
| `https://github.com/diegosouzapw/OmniRoute` (v3.7.x README, `providerRegistry.ts`) | § 5.4, § 6.7 (routing-layer findings); ADR-011 verification gate |
| `https://github.com/diegosouzapw/OmniRoute/issues/265` (closed 2026-03-10; mainteiner: "send the Fireworks path as model ID and OmniRoute auto-resolves it") | § 5.4 OmniRoute-supports-Fireworks binding precondition; ADR-011, ADR-009 v0.1.1, MODEL-CATALOG.md v0.2.0 § 4.2 |
| `https://api.fireworks.ai/inference/v1` (OpenAI-compatible chat-completions endpoint; OmniRoute upstream) | § 5.4; ADR-011 Decision step 3 |
| `https://fireworks.ai/models/fireworks/deepseek-v3p1` (Fireworks `accounts/fireworks/models/deepseek-v4-pro` → architect role) | § 5.4 catalog grounding; ADR-009 v0.1.1; MODEL-CATALOG.md v0.2.0 § 4.1 |
| `https://fireworks.ai/models/fireworks/qwen3-235b-a22b-instruct-2507` (Fireworks `accounts/fireworks/models/qwen3p6-plus` → planner role) | § 5.4 catalog grounding; ADR-009 v0.1.1; MODEL-CATALOG.md v0.2.0 § 4.1 |
| `https://fireworks.ai/models/fireworks/glm-4p5` (Fireworks `accounts/fireworks/models/glm-5p1` → executor role) | § 5.4 catalog grounding; ADR-009 v0.1.1; MODEL-CATALOG.md v0.2.0 § 4.1 |
| `https://fireworks.ai/models/fireworks/kimi-k2-instruct` (Fireworks `accounts/fireworks/models/kimi-k2p6` → reviewer role) | § 5.4 catalog grounding; ADR-009 v0.1.1; MODEL-CATALOG.md v0.2.0 § 4.1 |
| `https://fireworks.ai/models/fireworks/minimax-m2` (Fireworks `accounts/fireworks/models/minimax-m2p7` → orchestrator role) | § 5.4 catalog grounding; ADR-009 v0.1.1; MODEL-CATALOG.md v0.2.0 § 4.1 |
| `https://openrouter.ai/api/v1` (OpenRouter chat-completions endpoint; backup routing layer) | § 5.4; ADR-011 Decision step 4 |
