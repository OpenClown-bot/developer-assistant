---
id: TKT-NEW-008-D
version: 0.1.0
status: completed
source_tkt: TKT-008
created: 2026-05-04
completed_by_tkt: TKT-016
completed_at: 2026-05-04
---

# TKT-NEW-008-D: Bind GitHub Executors To Real Runtime HTTP And Git

## Context

TKT-008 introduced injectable `RESTExecutor` and `GitExecutor` protocols and tested them with mocks. A future runtime adapter must bind those protocols to real HTTP and subprocess execution without weakening token redaction or constrained git-command enforcement.

## Proposed Scope

- Implement concrete HTTP execution for TKT-014 `GitHubRESTRequest` objects.
- Implement concrete git execution for TKT-014 `GitCommand` objects.
- Preserve token redaction in logs, errors, Telegram progress text, and exceptions.
- Preserve constrained command enforcement and continue blocking force push, hard reset, branch deletion, token-bearing remotes, and shell metacharacter hazards.
- Add integration tests with mocked subprocess/HTTP boundaries and optional sanitized live smoke coverage if approved.

## Priority

High before live Hermes GitHub automation uses the TKT-008 integration layer.

## Resolution

Implemented by `TKT-016` in PR #53 and reviewed by `RV-CODE-020` in PR #54. The backlog item is consumed; retry/idempotency, sanitized live GitHub smoke coverage, and GitHub integration state persistence remain separate follow-ups under `TKT-NEW-008-A`, `TKT-NEW-008-B`, and `TKT-NEW-008-C`.
