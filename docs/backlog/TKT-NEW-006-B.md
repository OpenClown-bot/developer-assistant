---
id: TKT-NEW-006-B
version: 0.1.0
status: backlog
source_tkt: TKT-006
created: 2026-05-03
---

# TKT-NEW-006-B: Persist Progress Scheduling In SQLite

## Context

TKT-006 progress report scheduling stores last-report timestamps and intervals in memory. Process restarts lose scheduling state, while `OPERATIONAL-STATE-STORE.md` already defines the `scheduled_progress` table.

## Proposed Scope

- Store progress interval, last report timestamp, and next report timestamp in SQLite `scheduled_progress` rows.
- Preserve TKT-013 foreign-key enforcement and partial-update semantics.
- Use sanitized chat/project keys in tests and fixtures.
- Keep repository artifacts authoritative; the operational store must not hold durable product or architecture decisions.

## Priority

Medium. Required before reliable long-running runtime operation.

## Partial Resolution

Persistence-facing helper subset delivered by `TKT-019` in PR #79: `is_report_due` and `mark_report_sent` in `src/developer_assistant/progress_scheduling.py`. Runtime wiring into the TKT-006 Telegram adapter and live scheduling loop remains deferred.
