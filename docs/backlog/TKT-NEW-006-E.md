---
id: TKT-NEW-006-E
version: 0.1.0
status: backlog
source_tkt: TKT-006
created: 2026-05-03
---

# TKT-NEW-006-E: Improve Founder Message Classification

## Context

TKT-006 classifies free-form founder messages with deterministic regex/keyword heuristics. This is sufficient for a logic-layer baseline but can misclassify ambiguous, sarcastic, or mixed-intent messages.

## Proposed Scope

- Evaluate an LLM-assisted or hybrid classifier for ambiguous cases.
- Preserve the explicit categories required by TKT-006: intake, answer, clarification, approval, rejection, and general question.
- Add tests for mixed Russian/English messages, ambiguous approvals/rejections, and pending-question context.
- Ensure durable decisions still write to repository artifacts before being treated as final.

## Priority

Medium. Useful before broad live Telegram use.
