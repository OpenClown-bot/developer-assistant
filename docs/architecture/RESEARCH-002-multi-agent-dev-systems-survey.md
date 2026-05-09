---
id: RESEARCH-002
version: 0.1.0
status: draft
---

# RESEARCH-002: Multi-Agent Development-Time Systems Survey

## 1. Purpose

This document records a one-time Researcher cycle over 31 development-time agent systems. The purpose is to give a later Technical Architect a citation-backed map of existing patterns in multi-agent coding tools, orchestrators, parallel runners, and memory-first coding harnesses.

This is a research artifact only. It does not choose an architecture for `developer-assistant`, does not propose implementation changes, and does not modify existing repository contracts. Architectural synthesis belongs to the downstream Architect cycle.

## 2. Scope

The survey covers four groups:

- **Group A: Founder-curated multi-agent coding harnesses** — Claw Code, Roo Code CLI, Kilo Code CLI, Codebuff, Every Code, CodeMachine-CLI, RA.Aid, Dexto, CLAII.
- **Group B: Founder-curated orchestrators/autonomous loops** — claude-flow, gastown, ralph-orchestrator, AgentsMesh, loom, Aeon, Bernstein, kodo, ORCH, OpenCastle, SageCLI.
- **Group C: Founder-curated parallel runners** — cmux, Crystal/Nimbalyst, AgentPipe, CLITrigger.
- **Group D: SO-curated repositories from broader coding-agent ecosystems** — OpenHands, Letta Code, Pi/pi-mono, Goose, gptme, Plandex, SWE-agent.

All 31 repositories appear in Section 5 and Section 10. The access date for this pass is **2026-05-09 UTC**.

## 3. Methodology

The breadth scan used local shallow clones under `/home/ubuntu/research-002-repos/` and repository metadata captured in `metadata.json`. For each repository, the scan prioritized README files, architecture documents, role/agent definitions, orchestration-loop descriptions, persistence mechanisms, parallelism/sandbox mechanisms, and license/maintenance signals.

The deep-dive shortlist was ranked with a transparent heuristic:

1. **Applicability count** against the ten pain points below.
2. **Pattern strength**: whether the mechanism is a concrete architecture, state machine, protocol, or persistent artifact rather than a marketing claim.
3. **Maintenance health**: recent push date, contributor count, and ecosystem maturity.
4. **License caveat**: permissive licenses were lower-friction for research reuse; source-available, proprietary, or unclear licenses were noted as caveats.

Pain point codes used in the comparative table:

| Code | Pain point |
| --- | --- |
| App-1 | Role separation |
| App-2 | Orchestration loop / state machine |
| App-3 | Cross-model or cross-agent review |
| App-4 | Persistent state / durable memory |
| App-5 | Skill allowlist / reusable capabilities |
| App-6 | Parallel execution / work isolation |
| App-7 | Self-deployment or unattended operation |
| App-8 | Founder/human-in-the-loop escalation |
| App-9 | Skill evolution / learning |
| App-10 | Failure modes, recovery, escalation |

## 4. Coverage Limits

This pass was a breadth-first literature review. It did not run scripts from surveyed repositories, install dependencies, execute agents, or benchmark runtime behavior. Claims are therefore limited to what was visible in source files and docs that were actually read.

The top-10 deep dives are still not exhaustive audits. Large systems such as OpenHands, claude-flow, Codebuff, Goose, and Plandex contain substantial code not inspected in full. Where a repository is deprecated, proprietary, or source-available with caveats, that is noted rather than normalized away.

## 5. Comparative Table Of All 31 Repositories

| Group | Repo | Stars | Lang | License | PrimaryMech | RoleSep | Parallel | Persist | App-1..10 | Note |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| A | Claw Code | 190863 | Rust | Unknown | CLI agent harness | Low | Low | Sessions | 2,4,10 | Rust `claw` CLI harness with canonical runtime under `rust/`; docs emphasize doctor/parity/container workflows and explicitly warn ACP/Zed daemon support is not shipped yet. `claw-code@b98b9a712e9a:README.md:L31-L47` |
| A | Roo Code CLI | 23961 | TypeScript | Apache-2.0 | Editor agent modes | Medium | Low | Checkpoints/context | 1,4,5 | Roo presents Code, Architect, Ask, Debug, and Custom Modes as the specialization surface. `Roo-Code@ad256349058d:README.md:L56-L74` |
| A | Kilo Code CLI | 19086 | TypeScript | MIT | Agentic IDE/CLI modes | Medium | Low | Not primary | 1,5 | Kilo's explicit multi-mode surface maps Architect, Coder, Debugger, and Custom modes to task types. `kilocode@9d37a1aead09:README.md:L29-L37` |
| A | Codebuff | 4729 | TypeScript | Apache-2.0 | Composable agent runtime | High | Medium | Session state/backend | 1,2,4,5,6,9,10 | Codebuff documents an agent-runtime loop, subagent spawning, programmatic `handleSteps`, shipped agent definitions, context pruning, and registry-backed templates. `codebuff@54df847c6384:docs/architecture.md:L57-L97` |
| A | Every Code | 3742 | Rust | Apache-2.0 | Codex fork with Auto Drive/Review | Medium | Medium | Bounded state maps | 1,2,3,6,10 | Every Code couples Auto Drive orchestration with background Auto Review in separate worktrees and bounded coordinator/TUI state. `code@861c9bab69d7:README.md:L8-L33` |
| A | CodeMachine-CLI | 2475 | TypeScript | Apache-2.0 | Workflow orchestration layer | High | High | Long-running workflow state | 1,2,4,6,8 | CodeMachine defines workflows once, spawns coding engines, passes context, enables agent communication, parallel execution, and hours/days-long persistence. `CodeMachine-CLI@572def63eb80:README.md:L27-L45` |
| A | RA.Aid | 2222 | Python | Apache-2.0 | LangGraph staged coding agent | High | Low | Memory repositories | 1,2,4,8 | RA.Aid exposes a three-stage Research / Planning / Implementation architecture with dedicated agents and multi-step task execution. `RA.Aid@e71bb83dcfdf:README.md:L60-L90` |
| A | Dexto | 617 | TypeScript | Elastic-2.0 / NOASSERTION | General agent harness | Medium | Medium | Sessions/memory | 1,2,4,5,6,8 | Dexto positions itself as an agent harness that provides orchestration, state, tools, recovery, persistent memory, and specialized sub-agents. `dexto@e671fd519283:README.md:L39-L92` |
| A | CLAII | 2 | Python | Unknown | Small CLI agent loop | Low | Low | `.claii_memory.json` | 2,4,5,10 | CLAII documents scoped filesystem tools, sandboxed Python execution, local knowledge base mentions, and per-project compressed memory. `CLAII@89d42311b208:README.md:L13-L53` |
| B | claude-flow | 47766 | TypeScript | MIT | Swarm coordination platform | High | High | AgentDB/vector memory | 1,2,4,5,6,7,9,10 | claude-flow/RuFlo advertises 100+ agents, federation, swarm topologies, background workers, AgentDB/HNSW memory, self-learning patterns, and parallel MCP tool calls. `claude-flow@02eee0bcdc55:README.md:L180-L216` |
| B | gastown | 15047 | Go | MIT | Git/Dolt multi-agent town | Very high | High | Dolt/beads/git | 1,2,3,4,6,7,8,9,10 | Gas Town documents layered roles, worktree-isolated Polecats, persistent identity/work hooks, priming, mail/nudge/peek communication, and crash-surviving molecules. `gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L25-L99` |
| B | ralph-orchestrator | 2841 | Rust | MIT | Hat/event orchestration loop | High | Medium | Memories/tasks | 1,2,3,4,7,8,10 | Ralph uses multi-backend hats, backpressure gates, persistent memories/tasks, and Telegram human interaction that can block or steer loops. `ralph-orchestrator@3eca5177db33:README.md:L134-L168` |
| B | AgentsMesh | 1996 | Go | NOASSERTION | Workforce control/data plane | High | High | DB-backed Pods/Loops | 1,2,4,5,6,7,8,10 | AgentsMesh separates backend control plane, terminal relay, and self-hosted runners; its product model centers Pods, Tickets, Channels, Loops, Autopilot, Skills, MCP servers, and zero-trust PodBinding. `AgentsMesh@93f56e498ebc:README.md:L100-L114`; `AgentsMesh@93f56e498ebc:design/research/product-model.md:L20-L60` |
| B | loom | 1299 | Rust | Proprietary | Modular coding-agent platform | Medium | Medium | Thread/FTS5 | 1,2,4,5,6,10 | Loom is explicitly proprietary/research-only, but its docs expose a 30+ crate architecture with state machine, tool registry, Weaver remote execution, thread persistence, auth, and feature flags. `loom@7ba513204b3c:README.md:L1-L57` |
| B | Aeon | 282 | TypeScript | MIT | Scheduled autonomous agent framework | Medium | Medium | Persistent memory | 2,4,7,9,10 | Aeon emphasizes unattended schedules, self-healing skills, output-quality monitoring, persistent memory, reactive triggers, and GitHub Actions as zero infrastructure. `aeon@5f2df0715aa3:README.md:L25-L44` |
| B | Bernstein | 303 | Python | Apache-2.0 | Deterministic CLI-agent orchestrator | High | High | `.sdd/` WAL/artifacts | 1,2,4,5,6,7,10 | Bernstein documents pluggable sandbox backends, capability negotiation, and artifact sinks that preserve `.sdd/` WAL/audit/runtime state across ephemeral compute. `bernstein@f950c71eddf0:docs/architecture/sandbox.md:L1-L100`; `bernstein@f950c71eddf0:docs/architecture/storage.md:L1-L14` |
| B | kodo | 93 | Python | MIT | AI coding orchestrator tenets | High | Medium | Not central | 1,2,3,6,10 | kodo's tenets explicitly frame orchestration as solving permission waits, decision waits, shallow work, verification gaps, role specialization, parallelism, drift, and over-decomposition. `kodo@9758a0a1d0b1:docs/orchestration-tenets.md:L5-L30` |
| B | ORCH | 52 | TypeScript | MIT | File-backed CLI/TUI orchestrator | High | High | `.orchestry/` YAML/JSONL | 1,2,4,5,6,7,10 | ORCH documents DDD layers, DI containers, validated task transitions, reconcile/dispatch/collect tick loop, adapter processes, atomic file storage, and markdown skill loading. `ORCH@0c0694896b3a:CLAUDE.md:L28-L102` |
| B | OpenCastle | 43 | TypeScript | MIT | Skill/convoy orchestrator | High | High | SQLite WAL | 1,2,3,4,5,6,7,9,10 | OpenCastle combines specialist agents, on-demand skills, workflow templates, quality gates, cost-aware routing, lesson graduation, and a crash-recoverable Convoy Engine. `opencastle@18c6f2cf4e5c:README.md:L108-L122`; `opencastle@18c6f2cf4e5c:README.md:L155-L204` |
| B | SageCLI | 3 | Shell | MIT | Unix-native process/file control plane | Medium | High | Files/tmux state | 1,2,3,6,7,10 | Sage treats agents as processes and messages as files, supporting 8 runtimes, JSON/stdin workflows, tmux, fallback routing, and headless CI usage. `SageCLI@c167712ddb69:README.md:L44-L65`; `SageCLI@c167712ddb69:README.md:L87-L106` |
| C | cmux | 16590 | Swift | NOASSERTION | Desktop terminal workspace | Medium | High | Workspace/session UI | 1,3,6,8 | cmux focuses on managing many native agent terminal splits, Claude Code Teams, browser import, project commands, and socket/CLI automation. `cmux@0e4277ffc109:README.md:L78-L90` |
| C | Crystal | 3049 | TypeScript | MIT | Deprecated multi-session manager | Medium | High | Local-first files | 1,2,6 | Crystal is deprecated in favor of Nimbalyst; the replacement claims code-aware orchestration and git worktree isolation for parallel AI coding sessions. `crystal@1e18e0bc9812:README.md:L12-L48` |
| C | AgentPipe | 124 | Go | MIT | Multi-agent conversation rooms | Medium | Medium | Chat/event logs | 1,3,4,8,10 | AgentPipe emphasizes conversation save/resume, export, automatic chat logging, event storage, metrics, retry, rate limiting, and shared-room CLI agent communication. `agentpipe@f27e126d854e:README.md:L73-L97`; `agentpipe@f27e126d854e:README.md:L139-L145` |
| C | CLITrigger | 4 | TypeScript | MIT | Parallel worktree automation | Medium | Very high | Wiki/planner/session state | 1,2,3,4,6,7,8,10 | CLITrigger's core loop is capture → delegate → review; TODOs run in parallel worktrees with dependency chains, serialized main-branch tasks, wiki injection, planner, and long-lived sessions. `CLITrigger@fd4731bb3e20:README.md:L92-L129` |
| D | OpenHands | 72996 | Python | MIT core; enterprise caveat | Agent SDK + CLI + GUI + Cloud | Medium | High | Repo memory/cloud state | 1,2,4,6,7,8,10 | OpenHands exposes SDK, CLI, local GUI, cloud, enterprise self-hosting, multi-user RBAC, integrations, and repository memory through `.openhands/microagents/repo.md`. `OpenHands@9482ab1a666d:README.md:L32-L83`; `OpenHands@9482ab1a666d:skills/agent_memory.md:L10-L30` |
| D | Letta Code | 2447 | TypeScript | Apache-2.0 | Memory-first coding harness | Medium | Low | Persistent agent memory | 1,4,5,8,9 | Letta Code centers long-lived agents whose memory persists across sessions and models, with `/init`, `/remember`, and `/skill` learning. `letta-code@afac21583850:README.md:L5-L55` |
| D | Pi (pi-mono) | 47149 | TypeScript | MIT | Agent harness monorepo | Low | Low | Session sharing/data | 2,4,9 | Pi contains a coding-agent CLI, runtime with tool calling/state management, unified provider API, and public OSS session-sharing workflow. `pi-mono@e25415dd5f0b:README.md:L19-L57` |
| D | Goose | 44858 | Rust | Apache-2.0 | General native agent | Low | Low | Extensions/config | 5,7,8 | Goose provides desktop, CLI, API, 15+ providers, ACP subscriptions, and 70+ MCP extensions under AAIF/Linux Foundation governance. `goose@ea5802c3806d:README.md:L20-L45` |
| D | gptme | 4295 | Python | MIT | Local-first terminal agent | Medium | Medium | Lessons/plugins/CAS | 1,4,5,7,9 | gptme is local-first, terminal-anywhere, provider-agnostic, and recently added plugin system, context compression, subagent planner mode, lessons, MCP discovery, and background jobs. `gptme@cf85d7d8b2c7:README.md:L58-L71`; `gptme@cf85d7d8b2c7:README.md:L96-L103` |
| D | Plandex | 15344 | Go | MIT | Large-task planning/execution agent | Medium | Low | Diff sandbox/context cache | 2,4,8,10 | Plandex targets large multi-step tasks with 2M effective context, tree-sitter maps, cumulative diff sandbox, configurable autonomy, rollback, and automated debugging. `plandex@e2d772072efa:README.md:L81-L106` |
| D | SWE-agent | 19177 | Python | MIT | Research issue-fixing agent | Low | Medium | YAML config/runs | 2,6,10 | SWE-agent is now superseded by mini-swe-agent for current development, but remains a documented, configurable, research-oriented GitHub issue fixer. `SWE-agent@0f4f3bba990e:README.md:L19-L35` |

## 6. Top-10 Deep Dives

### 6.1 Rank 1 — Gas Town

Gas Town is the strongest structural analogue for a role-separated dev-time organization. It defines a four-layer role hierarchy: Boot, Deacon, Dogs, Mayor, Witness, Refinery, Polecats, and Crew. The role text is stored as Go templates and injected into Claude Code sessions by `gt prime`; role detection can also derive from the current working directory. `gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L25-L44`

The identity model is notable because it separates transient sessions from persistent role/work identity. The survey describes Role Beads, Agent Beads, and Hooks, with every completion, handoff, and closed bead becoming part of a permanent capability ledger in Dolt. `gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L45-L53`

Its startup priming sequence is explicit and operational: `gt prime` checks slung work, detects autonomous mode, outputs molecule context, restores prior checkpoints, injects beads workflow context, and injects pending mail. That is a concrete context-rehydration pattern for crash recovery and session continuation. `gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L54-L63`

Gas Town's scheduling principle is also concrete: if work is on an agent's hook, the agent must run it. Work persists across session crashes via Git-backed state, and the pull-based hook model avoids a single central scheduler. `gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L64-L82`

For coordination, Gas Town names specific primitives: persisted Mail, direct-session Nudge, and noninterrupting Peek. Its workflow stack distinguishes Formula, Protomolecule, Molecule, and Wisp, which gives the later Architect a vocabulary for template-vs-instance-vs-ephemeral work. `gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L83-L99`

### 6.2 Rank 2 — ORCH

ORCH is a compact example of a file-backed orchestrator with a clear DDD layering model: Domain, Application, Infrastructure, and CLI/TUI. It avoids framework magic and makes dependency direction explicit. `ORCH@0c0694896b3a:CLAUDE.md:L28-L39`

The DI split is concrete. `LightContainer` serves read-only commands, while the full `Container` adds orchestrator, adapters, process manager, and LiquidJS for active run/tui/doctor commands. This separation is relevant to tooling that must distinguish inspection from mutation. `ORCH@0c0694896b3a:CLAUDE.md:L41-L48`

The task lifecycle is a validated state machine: `todo → in_progress → review → done`, with retrying and failed branches and terminal states for done, failed, and cancelled. `ORCH@0c0694896b3a:CLAUDE.md:L49-L52`

The tick loop uses three phases per cycle: Reconcile to inspect PIDs/stalls/zombies, Dispatch to claim idle agents and launch adapter processes, and Collect to process completed runs, update stats, and transition tasks. State mutation is serialized behind a promise-chain mutex. `ORCH@0c0694896b3a:CLAUDE.md:L53-L61`

ORCH stores all state in `.orchestry/`, using YAML for tasks/agents/goals/teams, JSON metadata plus append-only JSONL events for runs, a single `state.json`, and JSON context/messages. The docs call out atomic writes, tail reads for OOM protection, and parallel file reads. `ORCH@0c0694896b3a:CLAUDE.md:L69-L81`

The skill loader is a simple allowlist-like mechanism: Markdown skills are loaded from `skills/library/`, library skill names are constrained, MCP skill names are skipped, contents are cached, and skills are injected at dispatch based on each agent's `skills` field. `ORCH@0c0694896b3a:CLAUDE.md:L86-L93`

### 6.3 Rank 3 — Bernstein

Bernstein is relevant because it decomposes agent isolation into a formal sandbox protocol. Its docs state that every spawned agent is isolated so concurrent agents cannot stomp on each other's files, processes, or secrets, and that the backend choice is pluggable rather than hard-coded. `bernstein@f950c71eddf0:docs/architecture/sandbox.md:L1-L20`

The sandbox protocol is a typed interface with backend and session responsibilities. A backend can create, resume, and destroy sessions; a session exposes read, write, exec, ls, snapshot, and shutdown. This is a portable vocabulary for comparing worktree, Docker, E2B, Modal, or future backends. `bernstein@f950c71eddf0:docs/architecture/sandbox.md:L21-L66`

Capability negotiation is explicit. Bernstein enumerates `FILE_RW`, `EXEC`, `NETWORK`, `GPU`, `SNAPSHOT`, and `PERSISTENT_VOLUMES`, and schedulers reject manifests requiring capabilities the selected backend lacks. `bernstein@f950c71eddf0:docs/architecture/sandbox.md:L67-L91`

Its first-party backend matrix is useful because it treats worktrees, Docker, E2B, and Modal as different points on the same abstraction, with latency, cost, and isolation trade-offs called out. `bernstein@f950c71eddf0:docs/architecture/sandbox.md:L93-L110`

Persistence is similarly abstracted. Bernstein persists `.sdd/` working state, WAL, HMAC audit logs, runtime state, outputs, cost ledger, and metrics, then decouples that from the local filesystem through artifact sinks for S3, GCS, Azure Blob, R2, or custom plugins. `bernstein@f950c71eddf0:docs/architecture/storage.md:L1-L14`

The buffered durability design is concrete: durable writes first commit locally with fsync semantics, then queue asynchronous remote mirrors with bounded back-pressure and graceful shutdown. Reads prefer remote for crash recovery and fall back local. `bernstein@f950c71eddf0:docs/architecture/storage.md:L63-L96`

### 6.4 Rank 4 — AgentsMesh

AgentsMesh is the clearest "AI workforce platform" model among the surveyed repos. It separates the control plane from the data plane: backend orchestration commands travel through gRPC with mTLS, while terminal I/O streams through a Relay cluster. `AgentsMesh@93f56e498ebc:README.md:L100-L114`

Its entity model has three layers. The infrastructure layer defines Runner and Pod; the work-collaboration layer defines Ticket, Channel, Repository, and PodBinding; the automation layer defines Loop, LoopRun, and AutopilotController. `AgentsMesh@93f56e498ebc:design/research/product-model.md:L20-L36`

The Pod concept is especially concrete: a Pod is immutable once created, binds a Runner, Agent, and Repository, owns PTY terminal and sandbox state, and follows a lifecycle from initialization through running, paused/disconnected/orphaned, completed/terminated/error. `AgentsMesh@93f56e498ebc:design/research/product-model.md:L20-L25`

AgentsMesh explicitly models multi-agent collaboration through Channels, PodBindings, and Mesh. Channels are N:M communication groups, PodBinding is the permissioned relation where one Pod can observe or control another, and Mesh is a runtime-derived graph of active Pods, bindings, channels, and runners rather than a persisted entity. `AgentsMesh@93f56e498ebc:design/research/product-model.md:L26-L49`

The zero-trust section is valuable because it names security expectations and their limits. Pods default to no inter-Pod access; PodBinding must grant read/write, credentials are injected at Pod start rather than stored in database records, and runners are independent. The same document also records discovered permission gaps, such as missing Pod privacy and API-key scope enforcement. `AgentsMesh@93f56e498ebc:design/research/product-model.md:L56-L89`

### 6.5 Rank 5 — OpenCastle

OpenCastle is a concise example of a packaged multi-agent development system. Its visible product surface includes specialist agents for development, UI/UX, database, security, testing, review, and more. `opencastle@18c6f2cf4e5c:README.md:L108-L112`

Its context-management pattern is on-demand skills: skills are loaded only as needed, auto-selected during init based on stack, and designed to keep context windows lean. `opencastle@18c6f2cf4e5c:README.md:L110-L114`

OpenCastle also names quality gates as part of the product rather than a post-hoc checklist: fast review after every step, panel majority vote for high-stakes changes, and lint/test/build checks. It also advertises cost-aware model-tier routing and lesson graduation into permanent instructions. `opencastle@18c6f2cf4e5c:README.md:L114-L122`

The Convoy Engine is a deterministic, crash-recoverable orchestrator: tasks live in YAML, can run overnight, and can resume after crashes. The example convoy shows task IDs, agent assignment, prompts, file scopes, dependencies, and gate commands. `opencastle@18c6f2cf4e5c:README.md:L155-L190`

OpenCastle documents the concrete runtime guarantees of Convoy: SQLite WAL crash safety, one git worktree per worker, dependency-order merge-back, auto-started real-time dashboard, and multiple supported coding runtimes in one convoy. `opencastle@18c6f2cf4e5c:README.md:L192-L204`

### 6.6 Rank 6 — Codebuff

Codebuff provides a strong harness-level view of agent execution. Its `packages/agent-runtime/` is described as the core agent loop driving LLM inference, tool execution, and multi-step reasoning, with an explicit entry point path through `main-prompt.ts` and `run-agent-step.ts`. `codebuff@54df847c6384:docs/architecture.md:L57-L63`

The same architecture document records key runtime responsibilities: manage agent templates, system prompts, tool definitions, subagent spawning, programmatic `handleSteps` generators, AI SDK streams, tool-call routing, token counting, cache debugging, and cost tracking. `codebuff@54df847c6384:docs/architecture.md:L61-L68`

Codebuff's shared `common/` package is relevant because tool contracts are centralized: Zod schemas, tool names, tool-call validation, shared `SessionState`, `AgentOutput`, and DI contracts live in a package with no dependencies. `codebuff@54df847c6384:docs/architecture.md:L70-L81`

The agent catalog is role-rich. The repository ships base agents, editor, file-explorer, thinker, reviewer, researcher, general agents, terminal executor (`basher`), and context pruner. `codebuff@54df847c6384:docs/architecture.md:L83-L97`

The template system distinguishes prompt agents from programmatic agents. Prompt agents combine system prompt, tool list, and spawnable subagents, while programmatic agents run `handleSteps` generator functions in a sandbox; templates can live in shipped `agents/` or local `.agents/`, and can be published to a registry. `codebuff@54df847c6384:docs/architecture.md:L224-L231`

### 6.7 Rank 7 — CLITrigger

CLITrigger is the clearest pure parallel-runner example. Its core loop is capture → delegate → review: a planner, TODOs, and schedules feed overnight or sidelined AI execution, followed by holistic review across diffs and logs. `CLITrigger@fd4731bb3e20:README.md:L92-L103`

The knowledge mechanism is explicit. CLITrigger has a per-project wiki modeled as a knowledge graph with nodes and typed edges, selective injection modes, one-shot LLM retrieval for relevant entries, token estimates, and export to `.clitrigger/wiki/<entity>/<slug>.md` so the wiki can live in Git or Obsidian. `CLITrigger@fd4731bb3e20:README.md:L107-L115`

Its planner is separate from TODOs and supports lightweight capture, images, tags, markdown import/export, and conversion of planner items into TODOs or schedules. `CLITrigger@fd4731bb3e20:README.md:L117-L123`

Parallel execution is worktree-centered. Each TODO can get its own git worktree; Claude, Gemini, and Codex CLIs execute simultaneously; dependency chains trigger follow-up tasks and branch merges; main-branch tasks are serialized to avoid conflicts. `CLITrigger@fd4731bb3e20:README.md:L125-L127`

CLITrigger also treats long-lived interactive sessions as first-class entities with docking, xterm.js rendering, exact PTY viewport sizing, per-session wiki injection, pre-flight banners, and persisted window geometry. `CLITrigger@fd4731bb3e20:README.md:L128-L134`

### 6.8 Rank 8 — Ralph Orchestrator

Ralph is a concise implementation of continuous iteration as an orchestration discipline. Its README says it implements the Ralph Wiggum technique: autonomous task completion through continuous iteration. `ralph-orchestrator@3eca5177db33:README.md:L134-L142`

The feature set maps directly to process-control pain points: multi-backend support, a hat system for specialized personas, backpressure gates that reject incomplete work, and persistent memories/tasks for learning and tracking. `ralph-orchestrator@3eca5177db33:README.md:L136-L142`

Backpressure is the most important named mechanism. The README describes gates that reject incomplete work for tests, lint, and typecheck, making verification structural rather than aspirational. `ralph-orchestrator@3eca5177db33:README.md:L138-L142`

The human-in-the-loop channel is also concrete. RObot uses Telegram; agents can emit `human.interact` events and block until answered, while humans can send proactive guidance at any time. `ralph-orchestrator@3eca5177db33:README.md:L144-L168`

Ralph's parallel-loop routing gives a useful escalation pattern: messages can route by reply-to, `@loop-id`, or default to primary, and commands such as `/status`, `/tasks`, and `/restart` expose real-time loop visibility. `ralph-orchestrator@3eca5177db33:README.md:L165-L170`

### 6.9 Rank 9 — Letta Code

Letta Code is the strongest memory-first coding harness in the set. Its README explicitly contrasts independent sessions with a persisted agent whose memory is portable across Claude, GPT, Gemini, GLM, Kimi, and other models. `letta-code@afac21583850:README.md:L5-L10`

The design philosophy is long-lived agents. Letta ties sessions to a persisted agent that learns, with `/clear` starting a new thread while memory persists. `letta-code@afac21583850:README.md:L25-L39`

The user-facing memory commands are simple and relevant to a Founder-in-the-loop workflow: `/init` initializes the memory system and `/remember` gives active guidance about what should be retained. `letta-code@afac21583850:README.md:L40-L49`

The skill system is explicitly connected to learning. Skills are reusable modules in a `.skills` directory, and `/skill` can ask the agent to learn a skill from the current trajectory. `letta-code@afac21583850:README.md:L50-L55`

At implementation level, the surveyed memory module loads starter memory blocks from embedded MDX prompts, separates global labels such as `persona` and `human`, marks some blocks read-only, and caches loaded blocks. `letta-code@afac21583850:src/agent/memory.ts:L10-L19`; `letta-code@afac21583850:src/agent/memory.ts:L83-L135`

### 6.10 Rank 10 — OpenHands

OpenHands is important less as a direct role-separated orchestrator and more as a mature agent platform with multiple distribution surfaces. The README separates SDK, CLI, local GUI, Cloud, and Enterprise. `OpenHands@9482ab1a666d:README.md:L32-L69`

The SDK is described as a composable Python library that powers the other surfaces and can scale from local agents to thousands of cloud agents. `OpenHands@9482ab1a666d:README.md:L34-L40`

The Cloud and Enterprise sections are relevant to deployment and governance: Cloud adds Slack/Jira/Linear integrations, multi-user support, RBAC, permissions, and collaboration features; Enterprise is self-hostable in a VPC via Kubernetes but has source-available licensing constraints. `OpenHands@9482ab1a666d:README.md:L53-L72`

The repo-memory skill is a concrete, docs-as-code-adjacent persistence pattern. It stores reusable repository knowledge in `.openhands/microagents/repo.md`, automatically includes it in context, and limits it to general knowledge such as repo structure, commands, style, workflows, and best practices. `OpenHands@9482ab1a666d:skills/agent_memory.md:L10-L22`

The same skill includes governance: before adding memory, the agent must ask user confirmation, list exact items, save only approved subsets, integrate with existing knowledge, and clearly note partial exploration limits. `OpenHands@9482ab1a666d:skills/agent_memory.md:L23-L30`

## 7. Cross-Cutting Themes

### 7.1 Work isolation usually means git worktrees first

Gas Town uses worktrees for ephemeral Polecats and full clones for persistent Crew. `gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L41-L44` Bernstein treats worktree as the default sandbox backend while abstracting Docker/E2B/Modal behind the same protocol. `bernstein@f950c71eddf0:docs/architecture/sandbox.md:L93-L100` OpenCastle and CLITrigger also center per-worker or per-TODO worktrees. `opencastle@18c6f2cf4e5c:README.md:L192-L195`; `CLITrigger@fd4731bb3e20:README.md:L125-L127`

### 7.2 Durable orchestration state is more varied than "memory"

ORCH uses `.orchestry/` files and JSONL events. `ORCH@0c0694896b3a:CLAUDE.md:L69-L81` Bernstein uses `.sdd/` WAL, audit logs, cost ledger, and artifact sinks. `bernstein@f950c71eddf0:docs/architecture/storage.md:L1-L14` Gas Town uses Dolt/beads/git-backed work identity and hooks. `gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L45-L53` Letta Code persists agent memory across sessions and models. `letta-code@afac21583850:README.md:L25-L39`

### 7.3 Verification is increasingly an orchestration primitive

kodo states that orchestrators should structurally enforce verification and push back on shallow work. `kodo@9758a0a1d0b1:docs/orchestration-tenets.md:L11-L13` Ralph implements backpressure gates for tests, lint, and typecheck. `ralph-orchestrator@3eca5177db33:README.md:L136-L142` OpenCastle names fast review, panel votes, and lint/test/build gates. `opencastle@18c6f2cf4e5c:README.md:L114-L118`

### 7.4 Human-in-the-loop is explicit in stronger orchestrators

Ralph routes agent questions and proactive guidance through Telegram, with blocking `human.interact` events. `ralph-orchestrator@3eca5177db33:README.md:L144-L168` Gas Town separates persisted Mail, immediate Nudge, and noninterrupting Peek. `gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L83-L87` AgentsMesh models human users and Pods in shared Channels. `AgentsMesh@93f56e498ebc:design/research/product-model.md:L26-L30`

### 7.5 Skill systems range from static markdown to learned trajectories

ORCH loads Markdown skills with name validation and dispatch-time injection. `ORCH@0c0694896b3a:CLAUDE.md:L86-L93` OpenCastle auto-selects on-demand skills to keep context lean. `opencastle@18c6f2cf4e5c:README.md:L110-L114` Letta Code exposes `/skill` to learn reusable modules from current trajectory. `letta-code@afac21583850:README.md:L50-L55`

### 7.6 Parallelism creates review and merge burden

CLITrigger explicitly pairs parallel worktree execution with holistic diff/log review. `CLITrigger@fd4731bb3e20:README.md:L92-L103` OpenCastle merges isolated workers back in dependency order. `opencastle@18c6f2cf4e5c:README.md:L192-L195` Every Code runs Auto Review in parallel with Auto Drive so quality checks do not block the command flow. `code@861c9bab69d7:README.md:L29-L33`

### 7.7 Stronger systems name their failure modes

kodo names micromanagement, drift/heresy, over-decomposition, role-OOD effects, and token/latency overhead. `kodo@9758a0a1d0b1:docs/orchestration-tenets.md:L21-L30` AgentsMesh records permission gaps in its own product model. `AgentsMesh@93f56e498ebc:design/research/product-model.md:L82-L89` Bernstein turns ephemeral compute loss into a storage-sink problem. `bernstein@f950c71eddf0:docs/architecture/storage.md:L3-L14`

## 8. Shortlist For Downstream Architect Attention

This shortlist is not an adoption recommendation. It is a map of repositories whose patterns appear most relevant for a later Architect to inspect more deeply.

| Repo | Why it belongs on the Architect's reading list | Pain points | Caveats |
| --- | --- | --- | --- |
| Gas Town | Strongest role/identity/hook/priming model for durable multi-agent operations. | 1,2,4,6,7,8,10 | Large, opinionated system; some docs are internal research notes. |
| ORCH | Compact DDD + state-machine + tick-loop + file-backed orchestrator. | 1,2,4,5,6,7,10 | Small project and low star count. |
| Bernstein | Best sandbox/storage abstraction for work isolation and crash recovery. | 2,4,6,7,10 | Some features documented as phased rollout. |
| AgentsMesh | Rich product model for Pods, Tickets, Channels, Loops, Runner, Relay, and PodBinding permissions. | 1,2,4,5,6,7,8,10 | License is unclear/NOASSERTION; product model records open permission gaps. |
| OpenCastle | Concise YAML convoy, quality gates, worktree isolation, model routing, and lesson graduation. | 1,2,3,4,5,6,7,9,10 | Smaller/newer repo; docs are higher level than ORCH/Bernstein. |
| Codebuff | Detailed composable harness internals: agent-runtime loop, templates, subagents, tool schemas. | 1,2,4,5,6,9,10 | SaaS/backend coupling and registry assumptions may not map directly. |
| CLITrigger | Clear capture/delegate/review loop for parallel worktree execution with wiki context injection. | 1,2,3,4,6,7,8,10 | Very low star count; requires UI maturity review. |
| Ralph | Backpressure and Telegram RObot are useful patterns for verification and human escalation. | 1,2,3,4,7,8,10 | Hat terminology may need translation into this repo's role model. |
| Letta Code | Strongest persistent-memory and skill-learning semantics. | 1,4,5,8,9 | Agent-memory model is not itself a full dev-time orchestrator. |
| OpenHands | Mature platform/deployment and governed repo-memory pattern. | 1,2,4,6,7,8,10 | Enterprise licensing caveat; large system requires targeted follow-up. |

## 9. Open Architectural Questions

- **Q-RESEARCH-002-01:** Should durable state be represented primarily as docs-as-code Markdown, as append-only event logs, as issue/bead records, or as a hybrid? Gas Town, ORCH, Bernstein, and OpenHands each imply different answers.
- **Q-RESEARCH-002-02:** What is the minimum isolation boundary for parallel dev-time agents: separate branch, git worktree, full clone, container, microVM, or self-hosted runner Pod?
- **Q-RESEARCH-002-03:** Which verification gates belong inside the orchestrator loop itself, and which belong only to CI/Reviewer PR gates?
- **Q-RESEARCH-002-04:** How should human escalation be modeled: blocking questions, persisted mail, direct session nudges, PR comments, Telegram/Slack messages, or docs-backed decision records?
- **Q-RESEARCH-002-05:** How should reusable skills evolve safely: static allowlisted Markdown, repo-local skills, marketplace/registry skills, or learned skills that require review before becoming permanent?
- **Q-RESEARCH-002-06:** What anti-drift mechanism is required when multiple LLM roles can produce durable project artifacts independently?

## 10. Bibliography And Maintenance Snapshot

| Group | Repo | Upstream | SHA | License | Maintenance snapshot |
| --- | --- | --- | --- | --- | --- |
| A | Claw Code | `ultraworkers/claw-code` | `b98b9a712e9a` | Unknown | 190863 stars; 4 contributors; pushed 2026-05-09; not archived. |
| A | Roo Code CLI | `RooCodeInc/Roo-Code` | `ad256349058d` | Apache-2.0 | 23961 stars; 287 contributors; pushed 2026-05-09; not archived. |
| A | Kilo Code CLI | `Kilo-Org/kilocode` | `9d37a1aead09` | MIT | 19086 stars; 421 contributors; pushed 2026-05-09; not archived. |
| A | Codebuff | `CodebuffAI/codebuff` | `54df847c6384` | Apache-2.0 | 4729 stars; 28 contributors; pushed 2026-05-09; not archived. |
| A | Every Code | `just-every/code` | `861c9bab69d7` | Apache-2.0 | 3742 stars; 448 contributors; pushed 2026-05-08; not archived. |
| A | CodeMachine-CLI | `moazbuilds/CodeMachine-CLI` | `572def63eb80` | Apache-2.0 | 2475 stars; 7 contributors; pushed 2026-02-25; not archived. |
| A | RA.Aid | `ai-christianson/RA.Aid` | `e71bb83dcfdf` | Apache-2.0 | 2222 stars; 23 contributors; pushed 2026-01-30; not archived. |
| A | Dexto | `truffle-ai/dexto` | `e671fd519283` | NOASSERTION / Elastic-2.0 badge | 617 stars; 11 contributors; pushed 2026-05-09; not archived. |
| A | CLAII | `agencyswarm/CLAII` | `89d42311b208` | Unknown | 2 stars; 2 contributors; pushed 2025-11-17; not archived. |
| B | claude-flow | `ruvnet/ruflo` | `02eee0bcdc55` | MIT | 47766 stars; 20 contributors; pushed 2026-05-09; not archived. |
| B | gastown | `gastownhall/gastown` | `18b1f4170c5f` | MIT | 15047 stars; 238 contributors; pushed 2026-05-09; not archived. |
| B | ralph-orchestrator | `mikeyobrien/ralph-orchestrator` | `3eca5177db33` | MIT | 2841 stars; 32 contributors; pushed 2026-05-08; not archived. |
| B | AgentsMesh | `AgentsMesh/AgentsMesh` | `93f56e498ebc` | NOASSERTION | 1996 stars; 10 contributors; pushed 2026-05-09; not archived. |
| B | loom | `ghuntley/loom` | `7ba513204b3c` | Proprietary | 1299 stars; 1 contributor; pushed 2026-04-10; not archived; README says research-only. |
| B | Aeon | `aaronjmars/aeon` | `5f2df0715aa3` | MIT | 282 stars; 5 contributors; pushed 2026-05-09; not archived. |
| B | Bernstein | `sipyourdrink-ltd/bernstein` | `f950c71eddf0` | Apache-2.0 | 303 stars; 18 contributors; pushed 2026-05-09; not archived. |
| B | kodo | `ikamensh/kodo` | `9758a0a1d0b1` | MIT | 93 stars; 4 contributors; pushed 2026-05-06; not archived. |
| B | ORCH | `oxgeneral/ORCH` | `0c0694896b3a` | MIT | 52 stars; 2 contributors; pushed 2026-04-17; not archived. |
| B | OpenCastle | `monkilabs/opencastle` | `18c6f2cf4e5c` | MIT | 43 stars; 4 contributors; pushed 2026-04-20; not archived. |
| B | sage (SageCLI) | `youwangd/SageCLI` | `c167712ddb69` | MIT | 3 stars; 1 contributor; pushed 2026-04-27; not archived. |
| C | cmux | `manaflow-ai/cmux` | `0e4277ffc109` | NOASSERTION | 16590 stars; 82 contributors; pushed 2026-05-09; not archived. |
| C | Crystal | `stravu/crystal` | `1e18e0bc9812` | MIT | 3049 stars; 15 contributors; pushed 2026-02-26; not archived, but README says deprecated in February 2026. |
| C | AgentPipe | `kevinelliott/agentpipe` | `f27e126d854e` | MIT | 124 stars; 4 contributors; pushed 2026-03-30; not archived. |
| C | CLITrigger | `HyperAITeam/CLITrigger` | `fd4731bb3e20` | MIT | 4 stars; 4 contributors; pushed 2026-05-07; not archived. |
| D | OpenHands | `OpenHands/OpenHands` | `9482ab1a666d` | MIT core; enterprise source-available caveat | 72996 stars; 463 contributors; pushed 2026-05-09; not archived. |
| D | Letta Code | `letta-ai/letta-code` | `afac21583850` | Apache-2.0 | 2447 stars; 26 contributors; pushed 2026-05-09; not archived. |
| D | Pi (pi-mono) | `earendil-works/pi` | `e25415dd5f0b` | MIT | 47149 stars; 196 contributors; pushed 2026-05-09; not archived. |
| D | Goose | `aaif-goose/goose` | `ea5802c3806d` | Apache-2.0 | 44858 stars; 441 contributors; pushed 2026-05-09; not archived. |
| D | gptme | `gptme/gptme` | `cf85d7d8b2c7` | MIT | 4295 stars; 31 contributors; pushed 2026-05-09; not archived. |
| D | Plandex | `plandex-ai/plandex` | `e2d772072efa` | MIT | 15344 stars; 22 contributors; pushed 2025-10-03; not archived. |
| D | SWE-agent | `SWE-agent/SWE-agent` | `0f4f3bba990e` | MIT | 19177 stars; 92 contributors; pushed 2026-04-27; not archived; README recommends mini-swe-agent for current use. |
