---
id: TKT-NEW-019-B
version: 0.1.0
status: backlog
source_tkt: TKT-019
created: 2026-05-06
---

# TKT-NEW-019-B: Add Explicit Datetime Parsing In is_report_due

## Context

RV-CODE-024 finding 4.2 (non-blocking): `is_report_due()` uses lexicographic string comparison (`now_iso >= next_report_at`). ISO 8601 strings sort correctly lexicographically in offline v0.1 scope, but edge-case ambiguities (timezone offsets, fractional seconds, mixed formatting) could arise when runtime wiring adds live timestamp sources.

## Proposed Scope

- Replace string comparison in `is_report_due` with explicit `datetime` parsing before live runtime wiring (TKT-NEW-006-B).
- Ensure UTC normalization and consistent formatting.
- Preserve the current offline-safe behavior as a fallback if parsing fails.

## Priority

Low. Safe for offline v0.1. Required before TKT-NEW-006-B runtime wiring introduces live timestamp sources.
