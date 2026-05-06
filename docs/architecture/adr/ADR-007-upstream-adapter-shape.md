---
id: ADR-007
version: 0.1.0
status: draft
---

# ADR-007: Upstream Adapter Shape — Hermes skill adapter inside the Orchestrator runtime

## Status

Draft, pending Founder approval. Supersedes none. Related: ADR-005 (multi-Hermes runtime isolation), ADR-006 (IPC and state mediation).

## Context

`PRD-001.md` v0.2.1 § 13.3 commits the project to swapping or adding the upstream entry-point (Telegram in v0.1; OpenClaw or another channel in v0.2+) without touching specialist Hermes runtimes, Founder-facing intake logic, or the orchestrator core. `ARCH-001.md` v0.3.0 § 13 sets the architectural shape; `UPSTREAM-ADAPTER-CONTRACT.md` defines the five operations every adapter must implement. This ADR records WHERE the abstraction lives and WHY.

## Decision

Implement the upstream-adapter abstraction **inside the Orchestrator Hermes runtime** as a Hermes skill adapter:

- The bundled `telegram-gateway` skill provides the Telegram-specific I/O.
- Custom `dev-assist-classifier`, `dev-assist-progress-report`, and `dev-assist-escalation-surface` skills translate between Hermes events and the abstraction's five operations.
- An in-process registry inside the Orchestrator runtime tracks installed adapters and routes outbound intents.
- v0.2 OpenClaw is added by registering a new adapter (and its inbound/outbound skills) in the Orchestrator runtime; specialist runtimes are not touched.

The abstraction does NOT live as: a separate gateway process, an OpenClaw plugin/process, or an MCP HTTP server (in v0.1).

## Considered Options

### Option A — Hermes skill adapter inside the Orchestrator runtime (CHOSEN)

How it works: as in the Decision section. The Orchestrator runtime loads `telegram-gateway` plus custom skills that wrap the five operations. The abstraction is a thin layer between the Hermes event loop and the work-queue / escalations tables.

Trade-offs:

- + Reuses Hermes' built-in Telegram support; no custom Telegram client code.
- + No new process; keeps the v0.1 deployment surface to five Hermes runtimes plus systemd.
- + Adapter switching/adding for v0.2 is loading additional skills and adding registry rows, not standing up new infrastructure.
- + The Orchestrator already does the classification and progress-report work; co-locating the adapter here is the natural shape.
- − Tied to Hermes' skill loading lifecycle. Adapter "hot-swap" without restarting the Orchestrator is not native; v0.1 doesn't need hot-swap.
- − An adapter that requires a long-lived inbound HTTP listener (e.g., Slack with webhooks) would need either Hermes' web-server features or a parallel listener. v0.1's Telegram polling avoids inbound; v0.2's OpenClaw adapter is expected to be outbound-initiated as well.

### Option B — Standalone gateway process (separate from any Hermes runtime)

How it works: a sixth process, supervised by systemd, runs an adapter daemon. It receives upstream messages, normalizes them, and writes work items into the SQLite queue or speaks MCP/A2A to the Orchestrator runtime.

Trade-offs:

- + Strong separation: the Orchestrator runtime is purely an LLM-driven coordinator; gateway code lives in a dedicated daemon.
- + Easier to swap upstream channels at the process level (replace one daemon).
- − Adds a sixth process to the v0.1 deployment surface. Six processes for one adapter exceeds the simplicity goal.
- − Duplicates effort: Hermes already has Telegram polling code in the `telegram-gateway` skill. Reimplementing or wrapping it is custom work.
- − The classifier (`dev-assist-classifier`) needs the Orchestrator's LLM context to do its job. A standalone gateway either calls into the Orchestrator (adding cross-process IPC) or runs its own LLM (adding cost and a second prompt to maintain).
- − Operational tooling (systemd unit, log rotation, env management) doubles for one process.

Rejected: separation benefit does not justify the per-process cost at v0.1 scale.

### Option C — OpenClaw plugin in front of Hermes

How it works: deploy an OpenClaw workspace and write an OpenClaw plugin that does the upstream work. The plugin drives the Hermes Orchestrator via MCP/A2A. Telegram is configured inside OpenClaw, not inside Hermes.

Trade-offs:

- + Fits the v0.2+ vision (OpenClaw as upstream).
- + OpenClaw has a multi-channel gateway built-in.
- − v0.1 explicitly defers OpenClaw (`ARCH-001.md` § 3, ADR-001). Adopting it for the v0.1 upstream is a major scope inversion.
- − Adds OpenClaw as a v0.1 hard dependency: another runtime stack to install, supervise, debug. Doubles the security review surface.
- − If OpenClaw is unavailable or buggy, v0.1 has no Telegram surface.
- − The "swap upstream" requirement was specifically motivated by Founder uncertainty about OpenClaw timing; making OpenClaw the v0.1 floor inverts the constraint.

Rejected: incompatible with v0.1 scope.

### Option D — MCP HTTP server inside the Orchestrator runtime exposing intake tools

How it works: the Orchestrator runtime exposes an MCP server. Telegram is handled by some external listener (cron-driven script, separate small daemon, or OpenClaw) that calls the Orchestrator's MCP `intake_message` tool.

Trade-offs:

- + Cleaner abstraction: the Orchestrator's interface is "MCP tools"; whoever calls them is irrelevant.
- + v0.2 OpenClaw can call the same MCP tools.
- − Pushes the Telegram listener to an external process anyway (Option B in disguise) OR keeps it in-runtime via the `telegram-gateway` skill (Option A in disguise). The MCP layer is gain on the v0.2 boundary, not on the v0.1 internal layout.
- − Inbound HTTP on the VPS adds a network port. The escalation policy `net:open_inbound_port` rule (`ESCALATION-POLICY.md` § 4.5) applies; opening the port requires Founder approval.
- − v0.1 Telegram-only does not need MCP.

Rejected for v0.1; relevant for v0.2 (`UPSTREAM-ADAPTER-CONTRACT.md` § 8 forward-looking notes).

### Option E — A2A-compliant HTTP server on the Orchestrator runtime

How it works: similar to Option D but using A2A protocol instead of MCP. The Orchestrator publishes an Agent Card describing its capabilities; external peers (OpenClaw, future agents) call in via A2A.

Trade-offs:

- + Open standard; future-proof for multi-agent ecosystem.
- + Same long-running task semantics A2A provides natively.
- − Same drawbacks as Option D for v0.1: inbound port, no v0.1 caller, listener still needs to be implemented.

Rejected for v0.1; A2A remains a "Future Possibility" in `ARCH-001.md` § 21 for the v0.2+ external boundary.

### Option F — Per-specialist-runtime adapters (each runtime knows about Telegram)

How it works: each of the five runtimes loads its own copy of the upstream adapter. Each can talk to the Founder directly.

Trade-offs:

- − Violates the PRD § 13.3 "one entity, one upstream surface" requirement. The Founder would see five bots.
- − Massive duplication. Five Telegram bot tokens, or all five sharing one (and competing for `getUpdates` polling, which is racy).
- − Memory isolation between runtimes is preserved but the user experience is broken.

Rejected outright.

## Decision Criteria And Mapping

| Criterion | Option A (Orchestrator skill) | Option B (separate daemon) | Option C (OpenClaw v0.1) | Option D (MCP) | Option E (A2A) | Option F (per-specialist) |
| --- | --- | --- | --- | --- | --- | --- |
| Single Founder-facing entity | Yes | Yes | Yes | Yes | Yes | No |
| v0.1 process count delta | 0 | +1 | +1 (or more) | +0 to +1 | +0 to +1 | 0 |
| New code to write | Low | Medium | High | Medium | Medium | Medium-High |
| Compatible with PRD § 13.3 | Yes | Yes | Inverts scope | Yes | Yes | No |
| Compatible with v0.1 scope | Yes | Yes | No | Partial | Partial | No |
| Future-proof for OpenClaw v0.2 | Yes (add skill) | Yes (add daemon) | Already there | Yes (caller switch) | Yes | No |
| Inbound port required | No | Maybe | Yes | Yes | Yes | No |

Option A is the only option that satisfies the v0.1 scope, preserves the single Founder entity, and stays compatible with the v0.2 OpenClaw addition.

## Consequences

- The Orchestrator runtime's loadout (`MULTI-HERMES-CONTRACT.md` § 5.1) bears all upstream-adapter responsibilities.
- The Telegram bot token is loaded only into the Orchestrator runtime's environment.
- v0.2's OpenClaw adapter is added by writing one more set of inbound/outbound/approval-surface skills and registering them in the Orchestrator's adapter registry. Specialist runtimes are not touched.
- The v0.2 routing policy (simultaneous Telegram + OpenClaw vs switchable) is a separate decision per `PRD-001.md` § 10 Q18 and is not committed by this ADR.
- If a future upstream channel requires inbound HTTP (e.g., Slack webhooks), Option D / Option E becomes relevant; this ADR does not preclude it but does not commit to it.

## Cross-References

- `PRD-001.md` v0.2.1 § 13.3 (upstream composability mandate)
- `ARCH-001.md` v0.3.0 § 13
- `UPSTREAM-ADAPTER-CONTRACT.md` (full contract)
- `MULTI-HERMES-CONTRACT.md` § 5.1, § 12 (Orchestrator-only Telegram token)
- `HERMES-SKILL-ALLOWLIST.md` v0.1.0 § 4.1 (Telegram gateway allowlist entry)
- `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3.7, § 3.11, § 4, § 6.5
- ADR-001 (platform foundation), ADR-005 (multi-Hermes), ADR-006 (IPC)
- Implementation: TKT-024 (upstream-adapter scaffolding)
