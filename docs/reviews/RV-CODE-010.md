---
id: RV-CODE-010
version: 0.1.0
status: complete
verdict: pass
---

# RV-CODE-010: Review of PR #18 — TKT-007: Operational State Store for Telegram/Hermes Orchestration

## PR reviewed

- **PR**: [#18](https://github.com/OpenClown-bot/developer-assistant/pull/18)
- **Title**: TKT-007: Implement operational state store for Telegram/Hermes orchestration
- **Branch**: `tkt-007/state-store` → `main`
- **Author**: `OpenClown-bot`
- **Merge state**: `CLEAN` (mergeable, no conflicts)
- **Scope**: SQLite-backed operational state store (`project_bindings`, `scheduled_progress`, `hermes_runs`), stdlib-only API, unit tests, and architecture documentation for storage backend, schema, security, backup/reset behavior.

## Ticket reviewed

- **Ticket**: `TKT-007`
- **Status in PR**: `ready` (not changed by this PR)
- **Scope alignment**: The PR implements exactly the ticket scope — a minimal non-secret operational state store for Telegram-first Hermes orchestration. It does not implement the Hermes runtime adapter, Telegram command handler, backup/restore utility script, or source review of credential-bearing capabilities, all of which are correctly deferred to follow-up tickets listed in the Execution Log.

## Files reviewed

| File | Role write zone | Change type |
| --- | --- | --- |
| `src/developer_assistant/__init__.py` | Executor — runtime source | New file — package marker |
| `src/developer_assistant/state_store.py` | Executor — runtime source | New file — SQLite operational store implementation (280 lines) |
| `tests/test_state_store.py` | Executor — tests | New file — 18 stdlib-only unit tests (296 lines) |
| `docs/architecture/OPERATIONAL-STATE-STORE.md` | Architect | New file — backend rationale, schema, API, security, backup/reset, artifact relationship |
| `docs/tickets/TKT-007.md` | Executor — Section 10 only | Execution Log update with changed files, validation results, follow-up tickets |

All changed files are within Executor allowed zones per `CONTRIBUTING.md` and `TKT-007.md` Section 5, with one process observation noted below regarding the new architecture document.

## CI / PR-Agent status

- **Docs CI** (`validate-docs`): pass.
- **PR-Agent** (`Run PR Agent on every pull request`): pass.
- **PR-Agent verdict**: Advisory; no security concerns identified; PR contains tests; estimated review effort 2.
- **Local validation**:
  - `python -m unittest discover -s tests -p "test_*.py" -v` — 33 tests passed (18 `state_store` + 15 `validate_docs`)
  - `python scripts/validate_docs.py` — passed

## Findings (ordered by severity)

### Low

1. **Missing referential integrity across operational tables** (`state_store.py:27`–`:58`).
   - `scheduled_progress.project_key` and `hermes_runs.project_key` logically reference `project_bindings.chat_key`, but no `FOREIGN KEY` constraints are declared and `PRAGMA foreign_keys = ON` is not set.
   - Because SQLite disables foreign-key enforcement by default, deleting a binding row does not cascade or block, leaving orphaned scheduled-progress and run rows.
   - **Impact for v0.1**: Low — the runtime adapter is not yet implemented, and the store is single-writer in the planned deployment. Orphans are a data-quality risk, not an immediate security or correctness blocker.
   - **Recommendation**: Add `PRAGMA foreign_keys = ON` after connection open, or add explicit `FOREIGN KEY` references in a follow-up schema revision tracked under a migration ticket.

2. **`upsert_project_binding` does not preserve omitted fields on update** (`state_store.py:117`–`:141`).
   - Unlike `upsert_scheduled_progress`, which uses `COALESCE` to retain existing values when a partial update passes `None`, `upsert_project_binding` replaces every optional column on conflict.
   - A caller that first upserts `{chat_key, repo_url, repo_owner_name, workspace_path, phase}` and later upserts `{chat_key, repo_url}` (omitting the others) will silently clear `repo_owner_name`, `workspace_path`, and `phase` to `NULL`.
   - **Impact for v0.1**: Low — the intended orchestrator caller may always supply the full row. However, the differing semantics between the two upserts is a future foot-gun.
   - **Recommendation**: Either align `upsert_project_binding` with `COALESCE` partial-update semantics, or document explicitly that it is a full-replacement upsert.

### Info

3. **Executor wrote to Architect write zone** (`OPERATIONAL-STATE-STORE.md`).
   - `docs/architecture/` is the Architect write zone per `CONTRIBUTING.md`. `TKT-007.md` Section 5 lists allowed files as "Runtime source/config files explicitly established by the approved implementation plan", `tests/`, and ticket Execution Log only. It does not explicitly list `docs/architecture/`.
   - The document is required by the ticket PR requirements ("Document selected storage backend and migration/reset behavior"), and it is implementation-specific rather than a new top-level architecture decision. It is pragmatically acceptable for v0.1.
   - **Recommendation**: Future tickets that require architecture-level implementation docs should either (a) route them through the Architect role, or (b) explicitly add `docs/architecture/<ticket-specific-doc>.md` to the ticket's allowed files.

4. **No thread-safety or WAL-mode guidance** (`state_store.py:100`–`:114`).
   - `open_store` returns a plain `sqlite3.Connection`. SQLite file databases are not thread-safe when shared across threads without serialization, and the default rollback journal can block concurrent readers.
   - **Impact for v0.1**: Info — the Hermes runtime adapter is not yet implemented, and v0.1 is expected to be single-threaded or single-process. If the adapter later shares the connection across threads or async workers, "database is locked" errors may occur.
   - **Recommendation**: Document the single-threaded access assumption in `OPERATIONAL-STATE-STORE.md`, or enable WAL mode (`PRAGMA journal_mode = WAL`) in a follow-up runtime adapter ticket.

5. **Tests do not exercise partial-update NULLification** (`test_state_store.py:83`–`:118`).
   - All `upsert_project_binding` test calls provide every optional field, so the full-replacement behavior noted in Finding 2 is not exercised or asserted.
   - **Recommendation**: Add a test that upserts a binding with all fields, then upserts the same key with only `repo_url`, and asserts whether the optional fields are preserved or cleared (depending on the intended API contract).

## Acceptance criteria assessment

| Criterion | Status | Evidence |
| --- | --- | --- |
| Stores Telegram chat/user allowlist or bindings without committing private identifiers unless explicitly sanitized. | **Pass** | `project_bindings.chat_key` stores sanitized references. Tests use `chat:proj-alpha` placeholders. Doc Section 4 mandates sanitized keys in committed code. |
| Stores project registry entries mapping Telegram conversations to GitHub repositories and local workspaces. | **Pass** | `project_bindings` schema includes `repo_url`, `repo_owner_name`, `workspace_path`, `phase`. API provides `upsert_project_binding`, `read_project_binding`, `list_project_bindings`. |
| Stores scheduled progress report timestamps. | **Pass** | `scheduled_progress` schema includes `last_report_at`, `next_report_at`, `interval_minutes`. API provides `upsert_scheduled_progress` and `read_scheduled_progress`. |
| Stores Hermes run IDs, retry/idempotency keys, and in-flight task metadata. | **Pass** | `hermes_runs` schema includes `run_id` (PK), `idempotency_key` (UNIQUE with index), `in_flight_meta` (JSON). API provides `upsert_hermes_run`, `read_hermes_run`, `read_hermes_run_by_idempotency`. |
| Does not store canonical product, architecture, security, merge, or deployment decisions without writing repository summaries. | **Pass** | Schema has no columns for decisions. Code docstring and doc Section 4 explicitly state the store is operational metadata only; durable decisions remain in `docs/`. |
| Documents backup and reset behavior for v0.1. | **Pass** | `OPERATIONAL-STATE-STORE.md` Sections 6.1 (Backup), 6.2 (Reset), and 6.3 (Data Loss Impact) describe VPS backup, `sqlite3 .backup`, `reset_store()`, and rehydration from repository artifacts. |
| `python scripts/validate_docs.py` passes. | **Pass** | Confirmed in CI, PR-Agent, and TKT-007 Execution Log. |

## Security / process notes

- **No secrets in schema or code**: The implementation stores only metadata (chat references, repo URLs, workspace paths, run IDs, timestamps, JSON task metadata). There are no columns for tokens, PATs, API keys, or SSH keys. `CONTRIBUTING.md` and `OPERATIONAL-STATE-STORE.md` Section 4 explicitly prohibit secret storage.
- **No SQL injection risk**: All queries use parameterized statements (`?` placeholders). There is no dynamic string concatenation into SQL.
- **Sanitized fixtures in tests**: `test_state_store.py` uses placeholder strings such as `chat:proj-alpha`, `example/proj-alpha`, and `https://github.com/example/proj-alpha`. No real Telegram chat IDs, GitHub org names, or personal identifiers appear.
- **SQLite selection is aligned with ARCH-001, ADR-002, and HERMES-RUNTIME-CONTRACT.md**: `OPERATIONAL-STATE-STORE.md` Section 2 cites all three documents, explains why Hermes native persistence is insufficient for structured relational queries, and notes that SQLite is stdlib-only and matches the VPS target. This satisfies the TKT-007 dependency on TKT-005.
- **Operational state is not authoritative**: `OPERATIONAL-STATE-STORE.md` Section 8 contains a mapping table that explicitly leaves `docs/prd/`, `docs/architecture/`, `docs/tickets/`, `docs/reviews/`, and `docs/orchestration/SESSION-STATE.md` out of the operational store. It also states the precedence rule: "If operational state contradicts repository artifacts, repository artifacts take precedence."
- **API is stdlib-only and adapter-ready**: Uses `sqlite3`, `json`, `datetime`, and `typing` only. No third-party dependencies. Functions accept a `sqlite3.Connection` and basic Python types, making them easy to call from a future Hermes runtime adapter.
- **Reset behavior is safe**: `reset_store()` deletes data rows from the three operational tables but leaves `_schema_meta` and table definitions intact, allowing immediate reuse. This matches the documented reset procedure in `OPERATIONAL-STATE-STORE.md` Section 6.2.
- **TKT-007.md changes are limited to Section 10 Execution Log**: No other ticket sections were modified. This respects the Executor write-zone rule.
- **Follow-up tickets are appropriate**: Execution Log lists Hermes runtime adapter, Telegram command handler, end-to-end integration test, backup/restore utility script, and source review of credential-bearing capabilities. None of these are in-scope for TKT-007.

## Final verdict

`pass`

PR #18 satisfies all TKT-007 acceptance criteria, implements a minimal stdlib-only SQLite operational store aligned with ARCH-001 and ADR-002, avoids secret storage and authoritative decision storage, documents backup/reset behavior, and includes meaningful sanitized tests. The two low-severity data-integrity findings (missing foreign-key enforcement and inconsistent partial-update semantics in `upsert_project_binding`) are acceptable for v0.1 and can be addressed in the runtime adapter or a schema-hardening follow-up. Merge is approved subject to the standard founder acknowledgement gate per ARCH-001.
