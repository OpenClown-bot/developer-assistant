---
id: ADR-001
version: 0.2.0
status: approved
---

# ADR-001: Use a Hermes-First Hybrid Foundation for v0.1

## Context

The project must choose whether v0.1 is founded on Hermes Agent, OpenClaw, a custom runtime, or a hybrid approach. The previous draft selected a custom thin docs-as-code orchestrator and deferred Telegram and Hermes. That decision is not approved.

The current user decisions require Telegram interaction in v0.1, prefer building around Hermes Agent rather than a custom runtime from scratch, and accept some Hermes/OpenClaw platform and plugin risks if clearly documented and mitigated.

Hermes Agent provides the closest fit for v0.1 because it supports server operation, Telegram gateway behavior, scheduled automations, subagent delegation, GitHub/coding-agent skills, sandbox options, and VPS deployment patterns. OpenClaw remains useful as a possible future gateway/control UI, but does not have a stronger immediate fit than Hermes for the requested Hermes-centered product direction.

## Decision

Use Hermes Agent as the v0.1 runtime foundation in a Hermes-first hybrid architecture.

Hermes will own Telegram gateway operation, runtime orchestration, scheduled progress updates, and agent/tool delegation. Repository artifacts will remain the authoritative governance layer for PRD, architecture, ADRs, tickets, questions, reviews, durable decisions, and handoff state.

Do not build a custom runtime from scratch in v0.1 except for minimal glue required to bind Hermes to the repository governance model, GitHub workflow, state persistence, and security policy.

OpenClaw is deferred as a possible later gateway/control UI addition and requires a separate ADR before adoption.

## Consequences

- v0.1 includes Telegram founder interaction instead of deferring it.
- Hermes becomes a required runtime dependency for the first product implementation.
- The project can reuse Hermes gateway, scheduling, delegation, and sandbox capabilities instead of recreating them.
- Repository docs-as-code governance remains portable and inspectable outside Hermes.
- Some operational state must live outside the repository for Telegram session binding, project registry, scheduled updates, and agent-run metadata.
- The project accepts larger runtime and supply-chain risk in exchange for faster Telegram-first delivery.
- Security controls for skill/plugin allowlists, pinning, source review, credential scoping, sandboxing, and rollback are mandatory for v0.1.

## Status Notes

This ADR is draft until the user approves the revised Hermes-first architecture and the initial implementation ticket sequence.
