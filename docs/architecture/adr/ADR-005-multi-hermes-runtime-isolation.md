---
id: ADR-005
version: 0.1.0
status: draft
---

# ADR-005: Multi-Hermes Runtime Isolation — five separate Hermes installations

## Status

Draft, pending Founder approval. Supersedes none. Related: ADR-004 (deployment mechanism), ADR-006 (IPC and state mediation).

## Context

`PRD-001.md` v0.2.1 § 13.2 mandates that each specialist role (Orchestrator, Business Planner, Architect, Executor, Reviewer) runs as its own full Hermes runtime with its own memory and self-learning state, while the Founder addresses one entity through one upstream adapter. The product mandate is precise: per-role memory and self-learning state must be strictly isolated, and the Founder-facing surface stays singular.

Research (`RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3.2) established that one Hermes Agent installation is one OS-level process. There is no documented mechanism to run multiple specialist runtimes inside a single Hermes installation with isolated memory: `HERMES_HOME` is per-process, `MEMORY.md` is per-process, and the sessions database is per-process.

Therefore the multi-Hermes mandate must be operationalized through some kind of multi-installation structure. This ADR records which structure.

## Decision

Run **five separate Hermes installations** under `/srv/devassist/runtimes/<role>/.hermes/`, supervised individually by systemd as five `devassist-<role>.service` units (the supervisor mechanism is in ADR-004). Per-runtime memory isolation is **filesystem-level**: each runtime has a distinct `HERMES_HOME` path containing its own `MEMORY.md`, `USER.md`, sessions database (`state.db`), and `cron/` job files. Cross-runtime read/write is prevented by systemd sandbox directives (`ProtectHome=`, `ReadWritePaths=`, `BindReadOnlyPaths=`, `PrivateTmp=`) since all five runtimes share a single Linux uid (`devassist`); a hostile intra-runtime actor is out of the v0.1 single-Founder threat model.

A single shared SQLite **operational store** at `/srv/devassist/state/operational.db` (renamed from the placeholder `state.db` to disambiguate from the per-runtime Hermes native sessions database also called `state.db`) is symlinked into each runtime's `HERMES_HOME` so that the multi-Hermes IPC layer (ADR-006) can use one database for cross-runtime work coordination without violating memory isolation. The exact symlink command rendered by `scripts/install-self.sh` for each runtime is:

```
ln -sfn /srv/devassist/state/operational.db \
  /srv/devassist/runtimes/<role>/.hermes/operational.db
```

The symlink name `operational.db` is intentionally distinct from Hermes' own per-runtime `state.db`; both files coexist in the same directory without collision. The shared store contains operational state (work items, escalations, project bindings, scheduled progress timers) — never per-runtime memory or session transcripts.

A single Hermes Python distribution is installed once at `/usr/local/lib/hermes-agent/`; the five runtimes share the same binary but each has its own `HERMES_HOME`. This avoids five copies of the same code.

## Considered Options

### Option A — Five separate Hermes installations supervised by systemd (CHOSEN)

How it works: as described in the Decision section. Each runtime runs as its own systemd-supervised process with its own `HERMES_HOME`. Custom skills and the escalation-policy plugin live in shared paths added to each runtime's `skills.external_dirs` and pip environment.

Trade-offs:

- + Filesystem-level memory isolation by construction (separate `HERMES_HOME` paths plus systemd `ProtectHome=`/`ReadWritePaths=`/`BindReadOnlyPaths=`/`PrivateTmp=`). No custom memory broker. Conditional on correct systemd unit configuration; v0.1's single-Founder threat model accepts the shared-uid limitation.
- + Clean per-process supervision (systemd handles each runtime's lifecycle, restart, resource limits independently).
- + Clean shutdown / start of one runtime without disturbing the others.
- + Per-runtime logs are naturally separated in `journalctl -u devassist-<role>.service`.
- + Aligns directly with `PRD-001.md` § 13.2's "full Hermes runtime per role" wording.
- − Five processes consume more memory than one. Mitigated: each runtime is one Python process; total ~1.5-3 GB under steady state per `MULTI-HERMES-CONTRACT.md` § 11.
- − The five runtimes share a uid (`devassist`); strict OS-level isolation between them depends on systemd's `ProtectHome=`, `ReadWritePaths=`, `BindReadOnlyPaths=`, and `PrivateTmp=` rather than separate uids. If a systemd unit is misconfigured, bypassed, or if a runtime escapes its sandbox, it can read or write another runtime's `MEMORY.md`, `USER.md`, or sessions database via normal DAC. Mitigated: v0.1's threat model is one trusted Founder/operator, not hostile multi-tenant; `BindReadOnlyPaths=` is part of the unit template (not a TKT-021 implementation note) so the isolation promise is part of the deployment contract.
- − Five sets of credentials, five env files, five logs. Mitigated: install script renders all of them from one template; one shared `.env` symlinked into all five runtimes.

### Option B — Single Hermes installation with custom multi-runtime broker

How it works: write a custom Python broker that wraps the Hermes runtime and presents five virtual "agents" backed by separate `MEMORY.md` files and separate session databases, all in one OS process. The role determines which set of files Hermes reads at any given moment.

Trade-offs:

- + Smaller resource footprint (one Python process).
- − Fundamentally fights Hermes' design: `HERMES_HOME` is global per-process, the cron scheduler is global per-process, the gateway listener is global per-process. Forcing five identities into one process means deeply patching Hermes or building a wrapper that swaps state in/out per request.
- − Crash in one role takes down the others.
- − Per-role resource limits (memory, restart count) are unavailable.
- − The gateway listener (Telegram polling) cannot be "owned" by one role; it must be shared. Sharing makes the role boundary blurry.
- − Heavy custom code burden the project must maintain forever; first significant deviation from upstream Hermes.
- − Memory isolation is logical, not physical; a bug in the wrapper leaks one role's MEMORY.md into another.

Rejected: the cost of fighting Hermes' shape exceeds the benefit of saving four Python processes' worth of memory.

### Option C — Single Hermes installation with multiple `HERMES_HOME` switching via env var

How it works: launch one Hermes process for each role-specific operation, each time setting `HERMES_HOME` to a different path. Runtimes are not long-lived; they are per-task ephemeral.

Trade-offs:

- + Simpler: no supervisor, no IPC, just a process per task.
- − Loses every advantage of long-lived runtimes: warm caches, persistent cron jobs, persistent gateway listener, conversational continuity inside the runtime's own session memory.
- − Telegram polling cannot be ephemeral; the gateway must be persistent. So the Orchestrator must be long-lived even if specialists are ephemeral, which collapses to a hybrid that's worse than Option A in every respect.
- − Cron scheduling for the 30-60 minute progress reports relies on a long-lived process. Ephemeral processes cannot host cron.

Rejected: incompatible with the gateway and cron requirements.

### Option D — Five Hermes installations as five Docker containers

How it works: same shape as Option A but each runtime is a Docker container instead of a systemd service.

Trade-offs:

- + Stronger isolation between runtimes (separate uid in each container, separate mount namespaces).
- + The shared uid concern in Option A's last drawback is fully addressed.
- − Docker becomes the supervisor (or Compose); ADR-004 already considered and rejected this path. Docker-in-Docker overhead for the Executor/Reviewer terminal sandbox is the dominant downside.
- − See ADR-004 Option B for full trade-off analysis.

Rejected: subsumed by ADR-004.

### Option E — Five Hermes installations on five separate VPSes

How it works: one VPS per runtime; cross-runtime IPC over a network protocol (REST, A2A, MCP-over-HTTP).

Trade-offs:

- + Strongest possible isolation (separate hosts).
- + Each runtime can scale independently.
- − Five VPSes = 5× cost. v0.1 budget is one VPS.
- − Network IPC is a paid third-party concern (TLS, public endpoints, message broker if used).
- − Operational complexity grows linearly with VPS count.
- − No advantage at v0.1 scale; the Founder is one person and the runtimes communicate only with each other and the GitHub API.

Rejected: out of v0.1 budget envelope.

### Option F — Hermes "subagents" via `delegate_task` skill

How it works: one root Hermes runtime; specialist work happens via the bundled `delegate_task` skill spawning subagents. Each subagent has a separate context window but shares the parent runtime's process.

Trade-offs:

- + Ships in Hermes; no custom multi-installation work needed.
- − `HERMES-SKILL-ALLOWLIST.md` § 4.5 keeps `delegate_task` BLOCKED for v0.1 production due to credential isolation concerns. Approving it would itself be a Founder-approved scope change.
- − Subagents share the parent runtime's `MEMORY.md`. PRD § 13.2's strict isolation requirement is not satisfied.
- − Cron, gateway listener, and approval flows are still single-rooted; only the conversation context branches.
- − The subagent abstraction is documented as "isolation by ephemeral context", not "isolation of long-term memory." It does not satisfy the product mandate.

Rejected: incompatible with PRD § 13.2's "own memory and self-learning state" requirement.

## Decision Criteria And Mapping

| Criterion | Option A (systemd × 5) | Option B (broker) | Option C (ephemeral) | Option D (Docker × 5) | Option E (VPS × 5) | Option F (subagents) |
| --- | --- | --- | --- | --- | --- | --- |
| Per-role memory isolation strict | Strong (filesystem) | Weak (logical) | Strong | Strongest | Strongest | None |
| Long-lived gateway, cron | Yes | Yes (rooted in single process) | No | Yes | Yes | Yes |
| One-process resource cost | High (5×) | Low (1×) | Low (per-task) | High (5×) + Docker | Highest | Low |
| Custom maintenance burden | Low | High | Medium | Medium | Medium | Lowest |
| Compatible with allowlist | Yes | Yes | Yes | Yes | Yes | No (`delegate_task` blocked) |
| Compatible with v0.1 budget | Yes | Yes | Yes | Yes | No | Yes |
| Aligns with PRD § 13.2 wording | Yes | Partial (logical) | Yes | Yes | Yes | No |

Option A is the only option that simultaneously satisfies the PRD § 13.2 requirement, the v0.1 budget, the allowlist constraints, and the operational simplicity goal.

## Consequences

- Five `HERMES_HOME` directories, five systemd units, one shared **operational store** at `/srv/devassist/state/operational.db` (symlinked into each runtime's `HERMES_HOME` as `operational.db`, distinct from each runtime's native `state.db`). The install script (TKT-020) renders all five from templates.
- Memory isolation is satisfied by filesystem layout plus systemd `ProtectHome=` / `ReadWritePaths=` / `BindReadOnlyPaths=` / `PrivateTmp=`. The shared uid is acceptable in v0.1's single-Founder threat model; the isolation promise is conditional on correct systemd unit configuration.
- The Hermes binary install is shared (`/usr/local/lib/hermes-agent/`), so a Hermes upgrade affects all five runtimes simultaneously. This is desired: keeping the version pin uniform avoids cross-runtime version drift.
- Custom skills and plugins live in shared paths (`/srv/devassist/shared-skills/`, `/srv/devassist/shared-plugins/`), loaded by all five runtimes.
- Telegram gateway runs only on the Orchestrator runtime. Specialist runtimes do not load the `telegram-gateway` skill.
- Adding a sixth runtime later is a small, well-shaped change (one new `HERMES_HOME`, one new systemd unit, one new role id).

## Cross-References

- `PRD-001.md` v0.2.1 § 13.2 (multi-Hermes mandate)
- `ARCH-001.md` v0.3.0 § 11 (architecture summary)
- `MULTI-HERMES-CONTRACT.md` (full contract)
- `SELF-DEPLOYMENT-CONTRACT.md` § 4 (filesystem layout)
- `HERMES-SKILL-ALLOWLIST.md` v0.1.0 § 4.5 (delegate_task blocked rationale)
- `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3.2, § 3.5, § 6.2
- ADR-001 (platform foundation), ADR-004 (deployment mechanism), ADR-006 (IPC)
- Implementation: TKT-021
