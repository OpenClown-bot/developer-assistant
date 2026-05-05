---
id: TKT-NEW-019-A
version: 0.1.0
status: backlog
source_tkt: TKT-019
created: 2026-05-06
---

# TKT-NEW-019-A: Align Ticket Filename Contracts With Implementation

## Context

RV-CODE-024 finding 4.1 (non-blocking): TKT-019 §5 Allowed Files specified `progress_scheduler.py`, but the implementation delivered `progress_scheduling.py`. Functionally identical, but the mismatch signals weak contract discipline between ticket scope and PR delivery.

## Proposed Scope

- Before TKT-011 live trial, add a pre-flight check or convention that ticket §5 Allowed Files filenames must match the actual PR filenames.
- Consider a `validate_docs.py` rule that cross-references ticket allowed-files paths against the actual module names when a PR is open, or add an SO/TO checklist item.

## Priority

Low. No correctness impact. Recommended before TKT-011 live trial to avoid confusion in automated orchestration.
