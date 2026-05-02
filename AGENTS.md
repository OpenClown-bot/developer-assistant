# Agent Operating Guide

This file is the shared operating contract for all LLM agents working in `developer-assistant`.

This repository is managed by a **multi-LLM pipeline** with strict role separation. If you are an AI agent, identify your role from the prompt you received and load the matching file:

| Role | Prompt file | Default model | Runtime |
|---|---|---|---|
| Strategic Orchestrator | `docs/meta/strategic-orchestrator.md` | GPT-5.5 high | opencode (Founder's Windows PC) |
| Ticket Orchestrator | `docs/prompts/ticket-orchestrator.md` | GPT-5.5 thinking | opencode (Founder's Windows PC) |
| Runtime Hermes Orchestrator | `docs/prompts/runtime-hermes-orchestrator.md` | runtime persona | Hermes Agent (deployed v0.1 product) — NOT a dev-time pipeline role |
| Business Planner | `docs/prompts/business-planner.md` | GPT-5.5 thinking / Claude Opus 4.7 thinking | ChatGPT Plus (web) |
| Technical Architect | `docs/prompts/architect.md` | GPT-5.5 xhigh / GPT-5.5 thinking / Opus 4.6 thinking | Codex CLI / opencode CLI / Windsurf |
| Code Executor | `docs/prompts/executor.md` | GLM 5.1 (default), Qwen 3.6 Plus (parallel), Codex GPT-5.5 (specialist) | opencode + OmniRoute |
| Reviewer | `docs/prompts/reviewer.md` | Kimi K2.6 | opencode + OmniRoute |

**Qodo PR-Agent** (Qwen 3.6 Plus through OmniRoute) auto-reviews every PR; it is a **second** reviewer alongside Kimi, not a replacement. See `.pr_agent.toml` and `.github/workflows/pr_agent.yml` for its configuration.

The **three orchestrator roles** are intentionally separate, despite sharing the word "Orchestrator":
- **Strategic Orchestrator** is the dev-time *session-level* conductor (one role across the lifetime of the project, many sessions stitched together via `docs/session-log/`).
- **Ticket Orchestrator** is the dev-time *per-TKT* cycle runner (one fresh session per ticket, never reused).
- **Runtime Hermes Orchestrator** is the *in-product runtime persona* (loaded by the deployed Hermes Agent, not by dev-time agents). It has no write-zone in this repo's dev-time process.

If you are running as the Strategic Orchestrator, load `docs/meta/strategic-orchestrator.md` first, then check `docs/session-log/` for the latest snapshot. If you are running as the Ticket Orchestrator, load `docs/prompts/ticket-orchestrator.md` first, then read your assigned TKT's bootstrap message in full.

Follow the role file **exactly**. Do not cross role boundaries. See `CONTRIBUTING.md` for the full process rules.

Before making any change:

1. Read `README.md` and `CONTRIBUTING.md`.
2. Confirm your write-zone in `CONTRIBUTING.md` § Roles. Touching files outside it WILL be rejected by Reviewer.
3. Read the role-specific reference knowledge listed in your prompt file.
4. Run `python3 scripts/validate_docs.py` before pushing. CI runs the same check on every PR.

## Project Mission

Build an AI developer assistant that can orchestrate real software projects through separated roles, durable docs-as-code state, ticket-based implementation, pull requests, CI, and review gates.

## Default Language Policy

- User-facing conversation: Russian by default.
- Long-lived repository artifacts: English by default.
- Role prompts: English.
- User decisions may be summarized in English artifacts when needed for future agents.

English repository artifacts are preferred because external tooling, PR review systems, and most coding agents handle English technical instructions more reliably.

## Current Platform Candidates

The architecture phase must evaluate these candidates before choosing a foundation:

- Hermes Agent: `https://github.com/nousresearch/hermes-agent`
- Hermes Agent docs: `https://hermes-agent.nousresearch.com/docs`
- OpenClaw: `https://github.com/openclaw/openclaw`
- OpenClaw docs: `https://docs.openclaw.ai/start/getting-started`

The project should treat these as candidates, not pre-approved decisions.

## Role Discipline

Agents must follow `CONTRIBUTING.md` write zones. Do not write production code unless acting as an Executor for an approved ticket.

## Required Context For Executors

An Executor must read before implementing:

- The assigned ticket in `docs/tickets/`.
- The active architecture spec in `docs/architecture/`.
- Relevant ADRs in `docs/architecture/adr/`.
- `CONTRIBUTING.md`.
- `AGENTS.md`.

## Required Context For Reviewers

A Reviewer must read before reviewing:

- The PR diff.
- The assigned ticket.
- The active architecture spec.
- Relevant ADRs.
- CI results.
- `CONTRIBUTING.md`.

## Security Defaults

- Do not print or persist secrets.
- Do not commit `.env` or credential files.
- Prefer least-privilege GitHub tokens.
- Treat repository access, VPS access, and LLM keys as security-sensitive.
