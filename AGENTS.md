# Agent Operating Guide

This file is the shared operating contract for all LLM agents working in `developer-assistant`.

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
