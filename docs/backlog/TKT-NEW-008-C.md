---
id: TKT-NEW-008-C
version: 0.1.0
status: backlog
source_tkt: TKT-008
created: 2026-05-04
---

# TKT-NEW-008-C: Persist GitHub Integration Project State

## Context

TKT-008 stores `ProjectGitHubState` in memory. This is acceptable for the logic-layer integration but a runtime process restart loses active repository, PR, CI, review-gate, and merge-gate state.

## Proposed Scope

- Persist GitHub integration state through the SQLite operational state store from TKT-007 or another approved runtime persistence mechanism.
- Keep repository artifacts authoritative for tickets, reviews, merge decisions, and durable engineering state.
- Store only operational metadata; do not store secrets or canonical product/architecture/review decisions.
- Add tests for restore/resume behavior after process restart.

## Priority

High before long-running Hermes runtime operation relies on GitHub state continuity.
