# developer-assistant

`developer-assistant` is a docs-as-code project for building an AI developer assistant that can orchestrate software delivery through separated LLM roles, durable repository artifacts, pull requests, validation, and review gates.

The project is currently in bootstrap. The first product goal is not to build a fully autonomous programmer. The first useful v0.1 is a reliable project orchestration layer: PRD, architecture, tickets, execution prompts, review prompts, and durable session state.

## Current Phase

Bootstrap and lightweight product planning.

## Delivery Model

This repository uses a lightweight docs-as-code pipeline:

1. Business Planner produces a lightweight PRD in `docs/prd/`.
2. Architect produces an architecture specification in `docs/architecture/` and ADRs when needed.
3. Architect breaks approved architecture into implementation tickets in `docs/tickets/`.
4. Executor agents implement individual tickets in separate branches and PRs.
5. Reviewer agents validate PRs against the ticket, architecture, ADRs, tests, and repository rules.
6. The user explicitly approves merge after CI and review gates pass.

## Key Constraints

- No direct pushes to `main` for meaningful changes.
- Every implementation PR must link a ticket.
- CI must validate docs, tests, lint/typecheck when available.
- Reviewer LLM review is mandatory for implementation PRs.
- Secrets must never be committed to the repository.
- Durable project state lives in repository files, not in chat memory.

## Important Directories

- `docs/prd/` - product requirements.
- `docs/architecture/` - architecture specs and ADRs.
- `docs/tickets/` - implementation contracts.
- `docs/reviews/` - code and spec review artifacts.
- `docs/backlog/` - deferred findings and technical debt.
- `docs/prompts/` - role prompts for separate LLM sessions.
- `docs/questions/` - unresolved product, architecture, and process questions.
- `docs/orchestration/` - durable session state and handoffs.
- `scripts/` - repository validation scripts.

## Reference

The process is inspired by `OpenClown-bot/openclown-assistant`, adapted for this repository rather than copied directly.
