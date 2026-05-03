---
id: TKT-NEW-006-C
version: 0.1.0
status: backlog
source_tkt: TKT-006
created: 2026-05-03
---

# TKT-NEW-006-C: Harden Progress Timestamp Parsing

## Context

PR-Agent on TKT-006 PR #35 noted that invalid timestamp parsing in `is_report_due()` returns `True`, which could trigger repeated progress reports until valid timestamps are supplied.

## Proposed Scope

- Decide fail-closed behavior for invalid timestamps, likely returning `False` and surfacing a warning/status for the runtime layer.
- Add tests for malformed ISO timestamps, naive/aware mismatches, and recovery after a valid timestamp arrives.
- Avoid spamming founder Telegram chats on bad operational state.

## Priority

Low to medium. Address before live scheduled reporting is enabled.
