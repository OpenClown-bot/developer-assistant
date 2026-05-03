---
id: TKT-NEW-006-F
version: 0.1.0
status: backlog
source_tkt: TKT-006
created: 2026-05-03
---

# TKT-NEW-006-F: Define Pending Specialist Question Queue Policy

## Context

TKT-006 prevents silent overwrites by allowing only one pending specialist question per chat. A second question raises until the founder resolves the first.

## Proposed Scope

- Decide whether v0.1 should keep a single pending question, queue multiple questions, or reject additional questions with a structured runtime blocker.
- If queueing is adopted, define ordering, cancellation, and `/decisions` presentation behavior.
- Add tests for multiple pending questions and founder answers resolving the intended question.

## Priority

Low to medium. Single-slot behavior is acceptable for one-founder v0.1 but should be explicit before heavier orchestration.
