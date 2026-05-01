---
id: ADR-002
version: 0.2.0
status: draft
---

# ADR-002: Use Repository Artifacts for Governance and External Store for Operational Runtime State

## Context

The system needs durable state so new agent sessions can resume without hidden chat memory. The previous draft selected repository artifacts as the only v0.1 state store.

Telegram-first Hermes orchestration changes this constraint. Telegram chat binding, project registry, scheduled progress reports, Hermes run metadata, retries, and in-flight task state require operational persistence outside repository files. At the same time, product and engineering decisions must remain reviewable in repository artifacts.

## Decision

Use a split state model for v0.1.

Repository artifacts are authoritative for governance state: PRD, architecture, ADRs, tickets, questions, reviews, session summaries, blockers, decisions, and handoff notes.

An external operational state store is required for Telegram/Hermes runtime state: chat/user allowlists, Telegram-to-project bindings, project registry, scheduled progress timestamps, Hermes run IDs, retry/idempotency keys, and in-flight agent metadata.

The preferred implementation should use the smallest operational store that satisfies Hermes integration needs, such as Hermes native persistence if sufficient or a local SQLite database on the VPS. The final choice is an implementation decision that must be documented before the runtime ticket is marked ready.

## Consequences

- Telegram-first v0.1 can survive process restarts and resume scheduled updates.
- Repository docs remain the durable source of truth for decisions and engineering state.
- Operational state can contain metadata but must not become the only place where product, architecture, security, merge, or deployment decisions are recorded.
- Secrets remain outside both repository artifacts and ordinary operational tables unless an approved secret mechanism is used.
- Validation must focus on repository artifacts, while runtime tests must cover operational state behavior.
