# Contributing

This repository is managed through role-separated LLM delivery. The rules below exist to prevent scope drift, hidden state, and unreviewed changes.

## Roles

| Role | Purpose | Allowed Write Zone |
| --- | --- | --- |
| Orchestrator | Coordinates process, state, handoffs, questions, and role prompts | `docs/orchestration/`, `docs/questions/`, coordination sections in docs |
| Business Planner | Clarifies product intent and MVP scope | `docs/prd/` |
| Architect | Defines system architecture, ADRs, and implementation tickets | `docs/architecture/`, `docs/tickets/` |
| Executor | Implements one approved ticket at a time | `src/`, `tests/`, explicitly allowed config files, and ticket Section 10 Execution Log only |
| Reviewer | Reviews PRs against ticket, architecture, ADRs, and CI | `docs/reviews/` |
| CI/Automation | Produces deterministic validation output | generated reports or explicitly configured output paths |

If a role needs to modify files outside its write zone, it must stop and surface the rule violation instead of silently working around it.

## Ticket Lifecycle

Tickets move through these states:

```text
draft -> ready -> in_progress -> in_review -> done
```

- `draft`: not ready for implementation.
- `ready`: approved for Executor.
- `in_progress`: Executor is working.
- `in_review`: PR is open and awaiting review.
- `done`: merged and verified.

Do not skip statuses unless the reason is documented in the ticket or orchestration state.

## PR Contract

Every meaningful implementation change must go through a PR. A PR must include:

- Linked ticket.
- Summary of changes.
- Acceptance criteria checklist status.
- Tests run.
- Known limitations.
- Risk notes, when relevant.

Executors must not expand scope beyond the ticket. If the implementation reveals missing scope, create or request a follow-up ticket.

## Review Gates

Before merge, every implementation PR requires:

1. Automated checks.
2. Reviewer LLM verdict in `docs/reviews/`.
3. Explicit user acknowledgement.

Allowed Reviewer verdicts:

- `pass`
- `pass_with_changes`
- `fail`

## CI Baseline

Minimum validation:

- `python scripts/validate_docs.py`
- Relevant tests when code exists.
- Lint/typecheck when configured.
- Static/security checks when configured.

## Versioning

Core artifacts use YAML frontmatter with semantic versions:

```yaml
---
id: ARCH-001
version: 0.1.0
status: draft
---
```

Architecture-changing version bumps require an ADR.

## Secrets

Never commit secrets, including GitHub PATs, LLM API keys, VPS SSH keys, `.env` files, private repository credentials, or service tokens.
