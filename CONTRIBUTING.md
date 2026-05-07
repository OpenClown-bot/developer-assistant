# Contributing

This repository is managed through role-separated LLM delivery. The rules below exist to prevent scope drift, hidden state, and unreviewed changes.

## Roles

| Role | Default model | Runtime | Purpose | Allowed Write Zone |
| --- | --- | --- | --- | --- |
| Strategic Orchestrator | GPT-5.5 high (main) / DeepSeek V4 Pro (fallback) | opencode (Founder's Windows PC) | Session-level conductor: ticket selection, TO delegation, ratification audit pass-2, merge-safe sign-off, founder-facing teaching | `docs/session-log/`, `docs/meta/`, `docs/orchestration/`, `docs/backlog/` (light edits / new entries), ticket frontmatter promotions (`status`, `arch_ref`, `version`, `updated`) + `§10 Execution Log` append-only fills, `docs/questions/` (light edits / new questions), `.github/workflows/`, `.pr_agent.toml`, `CONTRIBUTING.md`, `AGENTS.md`, `README.md`, `docs/prompts/` (when adapting role prompts) |
| Ticket Orchestrator | GPT-5.5 high (main) / GLM 5.1 (fallback) | opencode (Founder's Windows PC) | Per-TKT cycle runner: drafts Executor + Reviewer NUDGE files, runs cross-reviewer audit pass-1, hands back to Strategic Orchestrator | Per-ticket clerical sub-PRs scoped to one TKT, frontmatter promotion of own TKT, BACKLOG entries scoped to own TKT, NUDGE files (Founder-pasted, generally not committed) |
| Runtime Hermes Orchestrator | runtime persona | Hermes Agent (deployed v0.1 product) | Live operator persona inside the deployed product (Telegram-facing, ContextBlock-driven, skill-allowlist-bound) | None in dev-time. Runtime-only. See `docs/prompts/runtime-hermes-orchestrator.md` |
| Business Planner | GPT-5.5 thinking / Claude Opus 4.7 thinking | ChatGPT Plus (web) | Clarifies product intent and MVP scope | `docs/prd/` |
| Architect | GPT-5.5 xhigh / GPT-5.5 thinking / Opus 4.6 thinking | Codex CLI / opencode CLI / Windsurf | Defines system architecture, ADRs, and implementation tickets | `docs/architecture/`, `docs/tickets/` |
| Code Executor | DeepSeek V4 Pro (main) / GLM 5.1 (fallback), Codex GPT-5.5 (specialist) | opencode + OmniRoute | Implements one approved ticket at a time | `src/`, `tests/`, explicitly allowed config files, and ticket Section 10 Execution Log only |
| Reviewer | Kimi K2.6 (main) / Qwen 3.6 Plus (fallback) | opencode + OmniRoute | Reviews PRs against ticket, architecture, ADRs, and CI | `docs/reviews/` |
| CI/Automation (incl. Qodo PR-Agent) | DeepSeek V4 Pro (PR-Agent) | GitHub Actions | Produces deterministic validation output and supplementary reviewer findings | generated reports or explicitly configured output paths |

If a role needs to modify files outside its write zone, it must stop and surface the rule violation instead of silently working around it.

**On the three orchestrator rows.** "Orchestrator" is intentionally split:
- **Strategic Orchestrator** is the dev-time session-level conductor (GPT-5.5 high in an opencode tab on the Founder's PC; DeepSeek V4 Pro as fallback model via opencode + OmniRoute). It is the partner the Ticket Orchestrator hands back to.
- **Ticket Orchestrator** is the dev-time per-TKT cycle runner (GPT-5.5 high in a separate opencode tab; GLM 5.1 as fallback model via opencode + OmniRoute). One TO session per TKT, never reused.
- **Runtime Hermes Orchestrator** is the in-product persona inside the deployed Hermes Agent runtime. It is NOT a dev-time pipeline role; it has no write-zone in this repo's dev-time process. Its prompt lives in `docs/prompts/runtime-hermes-orchestrator.md` to keep it next to the other prompts, but it is loaded by the runtime, not by dev-time agents.

The full SO portable system prompt lives in `docs/meta/strategic-orchestrator.md`. The TO portable system prompt lives in `docs/prompts/ticket-orchestrator.md`. Session-handoff snapshots between SO sessions live in `docs/session-log/` (auto-cold rule fires after every closed TKT cycle).

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

## Recovery Playbook Discipline

If you change a CLI subcommand, systemd unit name, port assignment, SQLite table schema, or install/verify script name, update `docs/operations/RECOVERY-PLAYBOOK.md` in the same PR. The playbook is the authoritative operator surface and CI verifies it does not drift (TKT-030 harness: `tests/test_recovery_playbook_invariants.py`).
