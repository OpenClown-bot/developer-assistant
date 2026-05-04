---
id: TKT-NEW-008-D
version: 0.1.0
status: backlog
source_tkt: TKT-008
created: 2026-05-04
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
