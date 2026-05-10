---
id: NEXT-2-HOURS
version: 0.1.1
status: superseded
updated: 2026-05-10
---

# Next 2 Hours

> **Superseded 2026-05-10.** This document is a bootstrap-time scaffold from the empty-repo era. Its goals (write PRD-001, write ARCH-001, dispatch first Architect session) are all complete — PRD-001 is at v0.2.1, ARCH-001 is at v0.3.0, ARCH-002 is at v0.1.0, and TKT-020/021/022/023/025/030/032/033/034/035/040 are all merged on `main` as of 2026-05-10. Step 3 ("Start a Business Planner session") and Step 5 ("Start an Architect session after PRD approval") no longer reflect the project state.
>
> **Authoritative replacement:** `docs/orchestration/SESSION-STATE.md` is now the live state tracker. For the active SO pipeline, see `docs/meta/strategic-orchestrator.md`. For the role pipeline, see `docs/prompts/<role>.md`. For per-cycle handoffs, see `docs/session-log/<date>-session-N.md`.
>
> Body preserved below for historical reference.

This guide explains what to do next and why.

## Goal

Move `developer-assistant` from an empty repository to a product-planning-ready docs-as-code project.

## Step 1: Review The Bootstrap Scaffold

Read:

- `README.md`
- `CONTRIBUTING.md`
- `AGENTS.md`
- `docs/orchestration/SESSION-STATE.md`

Why: these files define the operating contract. Without them, separate LLM sessions will invent their own process and drift.

## Step 2: Run Docs Validation

Command:

```bash
python scripts/validate_docs.py
```

Why: validation gives a deterministic signal that the repository has the minimum process structure before additional agents depend on it.

## Step 3: Start A Business Planner Session

Open a separate OpenCode session and paste the prompt from:

```text
docs/prompts/business-planner.md
```

Why: the Business Planner owns product scope. The Orchestrator should not silently invent product requirements, and the Architect should not design before product intent is documented.

## Step 4: Review The PRD Draft With The User

The Business Planner should create:

```text
docs/prd/PRD-001.md
```

Review it with the user before architecture starts.

Why: the PRD is the product contract. If the MVP is vague, architecture and tickets will become vague too.

## Step 5: Start An Architect Session After PRD Approval

Open another OpenCode session and paste:

```text
docs/prompts/architect.md
```

Why: the Architect must evaluate Hermes Agent and OpenClaw before choosing a foundation. This prevents prematurely locking into a framework because it sounds promising.

## Step 6: Do Not Implement Yet

No Executor should write production code until tickets exist and at least one ticket is `ready`.

Why: tickets are the implementation contract. They prevent scope creep and allow Reviewers to judge whether a PR did exactly what was requested.

## Recommended First Business Planner Invocation

Use `docs/prompts/business-planner.md` as-is. The expected first output is:

```text
docs/prd/PRD-001.md
```

If the Business Planner has unresolved questions, it should also update:

```text
docs/questions/
```
