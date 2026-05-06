---
id: OPERATIONAL-STATE-STORE
version: 0.2.1
status: active
---

# Operational State Store

## 1. Purpose

This document describes the v0.1 operational state store implemented by TKT-007. It covers the selected storage backend, schema, security constraints, backup/reset behavior, and relationship to repository governance artifacts.

## 2. Storage Backend Selection

The operational state store uses **SQLite** as its backend, consistent with:

- `ARCH-001` Section 8: operational state backend default is SQLite on VPS unless Hermes native persistence is proven sufficient.
- `ADR-002`: smallest operational store that satisfies Hermes integration needs.
- `HERMES-RUNTIME-CONTRACT.md` Section 6: preferred implementation uses the smallest operational store; SQLite is the default.

**Why SQLite over Hermes native persistence for v0.1:**

- Hermes native persistence (memory/session_search and `~/.hermes/memories/`) is designed for conversation continuity and agent recall, not for structured relational queries on project bindings, scheduled timers, or idempotency-key deduplication.
- SQLite provides transactional integrity, schema enforcement, and index-backed lookups needed for idempotency and scheduling.
- The operational store holds data that must survive process restarts and be queryable by the orchestration layer independently of Hermes memory.
- SQLite is stdlib-only in Python, requires no additional server process, and matches the VPS deployment target.

Hermes native persistence may supplement this store for conversation context, but it does not replace the structured operational tables.

## 3. Schema

Five operational tables plus one internal metadata table (v0.2.1: added `work_items` and `escalations` for multi-Hermes IPC per `MULTI-HERMES-CONTRACT.md` § 6 and `ADR-006`). The v0.3.0+ observability tables (`errors`, `llm_calls`, `llm_calls_daily`) ship via `OBSERVABILITY-CONTRACT.md` and are added in a subsequent migration.

### 3.1 project_bindings

| Column | Type | Purpose |
| --- | --- | --- |
| chat_key | TEXT PK | Sanitized Telegram chat reference (not raw private identifiers in committed code) |
| repo_url | TEXT NOT NULL | GitHub repository URL |
| repo_owner_name | TEXT | Repository owner/name (e.g., `example/proj-alpha`) |
| workspace_path | TEXT | Local workspace path on VPS |
| phase | TEXT | Current project phase metadata |
| updated_at | TEXT NOT NULL | ISO 8601 UTC timestamp of last upsert |

### 3.2 scheduled_progress

| Column | Type | Purpose |
| --- | --- | --- |
| project_key | TEXT PK | References chat_key from project_bindings (FOREIGN KEY) |
| last_report_at | TEXT | ISO 8601 timestamp of last progress report sent |
| next_report_at | TEXT | ISO 8601 timestamp of next scheduled report |
| interval_minutes | INTEGER | Report interval in minutes (30-60 per ARCH-001) |
| updated_at | TEXT NOT NULL | ISO 8601 UTC timestamp of last upsert |

Foreign key: `project_key REFERENCES project_bindings(chat_key)`.

### 3.3 hermes_runs

| Column | Type | Purpose |
| --- | --- | --- |
| run_id | TEXT PK | Hermes agent run identifier |
| project_key | TEXT NOT NULL | References chat_key from project_bindings (FOREIGN KEY) |
| role | TEXT | Assigned role (orchestrator, business_planner, architect, executor, reviewer) |
| task_type | TEXT | Task classification |
| status | TEXT NOT NULL | Run status (pending, in_progress, completed, blocked, failed) |
| idempotency_key | TEXT UNIQUE | Retry/idempotency key for deduplication |
| in_flight_meta | TEXT | JSON-serialized in-flight task metadata |
| updated_at | TEXT NOT NULL | ISO 8601 UTC timestamp of last upsert |

Foreign key: `project_key REFERENCES project_bindings(chat_key)`.

Index: `idx_hermes_runs_idempotency` on `idempotency_key`.

### 3.4 _schema_meta

| Column | Type | Purpose |
| --- | --- | --- |
| key | TEXT PK | Metadata key |
| value | TEXT NOT NULL | Metadata value |

Currently stores `schema_version` for future migration tracking.

### 3.5 work_items (added in v0.2.1)

The canonical inter-runtime IPC primitive per `MULTI-HERMES-CONTRACT.md` § 6.2 and `ADR-006`. The Orchestrator runtime writes work items; specialist runtimes (planner, architect, executor, reviewer) claim, complete, or release them. Implementation: TKT-022.

| Column | Type | Purpose |
| --- | --- | --- |
| id | INTEGER PK AUTOINCREMENT | |
| created_at | TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP | ISO 8601 UTC |
| updated_at | TEXT NOT NULL | ISO 8601 UTC |
| target_role | TEXT NOT NULL CHECK | one of `planner`, `architect`, `executor`, `reviewer` |
| kind | TEXT NOT NULL | e.g., `prd_intake`, `architect_pass`, `ticket_implementation`, `ticket_review`, `prd_question_followup` |
| payload_json | TEXT NOT NULL | JSON: `{ project_id, ticket_id?, prompt, context_paths, allowed_files, expected_outputs, deadline_at?, dedup_key }` |
| priority | INTEGER NOT NULL DEFAULT 50 | 0 highest, 100 lowest |
| status | TEXT NOT NULL CHECK | one of `pending`, `claimed`, `completed`, `failed`, `released` |
| claimed_by_runtime | TEXT | NULL until claimed; one of the five role ids |
| claimed_at | TEXT | NULL until claimed |
| claim_lease_until | TEXT | NULL until claimed; rolling lease, default 30 minutes |
| completed_at | TEXT | NULL until completion |
| result_json | TEXT | JSON output structure per `HERMES-RUNTIME-CONTRACT.md` § 5 |
| attempt_count | INTEGER NOT NULL DEFAULT 0 | |
| max_attempts | INTEGER NOT NULL DEFAULT 3 | |
| originating_run_id | TEXT | foreign key into `hermes_runs.run_id` (nullable) |

Indexes:

- `idx_work_items_claim` on `(target_role, status, priority, id)` — drives the claim query.
- `idx_work_items_runtime` on `(claimed_by_runtime, status)` — drives the runtime-internal "what am I working on" query.
- `idx_work_items_lease` partial index on `(claim_lease_until)` where `status = 'claimed'` — drives the lease-reclaim sweep.

Claim semantics, lease semantics, idempotency, and the dedup-key behavior are specified in `MULTI-HERMES-CONTRACT.md` § 6.2.

### 3.6 escalations (added in v0.2.1)

Pending Founder-facing prompts produced by any runtime when the escalation-policy plugin classifies an action as needing approval (`ESCALATION-POLICY.md` § 5, `MULTI-HERMES-CONTRACT.md` § 6.3, `ADR-006`). The Orchestrator polls this table and surfaces pending entries to Telegram.

| Column | Type | Purpose |
| --- | --- | --- |
| id | INTEGER PK AUTOINCREMENT | |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |
| originating_runtime | TEXT NOT NULL CHECK | one of the five role ids |
| originating_work_item_id | INTEGER | nullable foreign key into `work_items.id` |
| trigger_kind | TEXT NOT NULL | `deterministic_rule:<rule_id>` or `llm_classifier:<classifier_id>` |
| context | TEXT NOT NULL | what situation produced the question |
| proposed_action | TEXT NOT NULL | what the runtime is about to do |
| options_json | TEXT NOT NULL | JSON list of decision options |
| recommended_default | TEXT NOT NULL | |
| impact | TEXT NOT NULL | what is affected |
| urgency | TEXT NOT NULL CHECK | one of `low`, `medium`, `high` |
| durable_artifact_target | TEXT NOT NULL | repository path where the decision will be recorded |
| status | TEXT NOT NULL CHECK | one of `pending`, `surfaced`, `approved`, `denied`, `expired` |
| surfaced_at | TEXT | |
| resolved_at | TEXT | |
| founder_response | TEXT | normalized English decision note |
| telegram_message_id | TEXT | the Telegram message id used to surface this escalation, for follow-up edit/reply |

Indexes:

- `idx_escalations_surface` on `(status, urgency, id)` — drives the Orchestrator's "what should I show next" query.
- `idx_escalations_runtime` on `(originating_runtime, status)` — drives the runtime-internal "is my escalation resolved yet" query.
- `idx_escalations_work_item` on `(originating_work_item_id)` — drives correlation joins with `work_items`.

Resolution semantics, expiration sweep, and the 7-day default expiration are specified in `MULTI-HERMES-CONTRACT.md` § 6.3.

## 4. Security Constraints

- **No secrets**: The schema does not store Telegram bot tokens, GitHub PATs, LLM API keys, SSH keys, or any other secret values. Secret values must remain in environment variables, Hermes-supported secret mechanisms, GitHub Actions secrets, or VPS secret storage.
- **Sanitized chat keys**: The `chat_key` and `project_key` fields should use sanitized references (e.g., `chat:proj-alpha`) rather than raw Telegram chat IDs or user IDs in committed code, tests, and fixtures. Production deployments may store actual chat IDs in the runtime database on the VPS, but those values must not be committed to the repository.
- **Operational metadata only**: This store does not hold canonical product, architecture, security, merge, or deployment decisions. Those remain in repository artifacts under `docs/`.
- **Non-secret credential metadata**: Which secret names must exist in the runtime environment may be recorded (e.g., "TELEGRAM_BOT_TOKEN is required"), but never the secret values themselves.

## 5. API

The implementation module (`src/developer_assistant/state_store.py`) provides:

| Function | Purpose |
| --- | --- |
| `open_store(db_path)` | Open/create SQLite database, initialize schema, return connection |
| `init_schema(db)` | Create all tables and indexes if they do not exist |
| `upsert_project_binding(...)` | Insert or update a project binding row |
| `read_project_binding(db, chat_key)` | Read a single project binding |
| `list_project_bindings(db)` | List all project bindings |
| `upsert_scheduled_progress(...)` | Insert or update a scheduled progress row |
| `read_scheduled_progress(db, project_key)` | Read a single scheduled progress row |
| `upsert_hermes_run(...)` | Insert or update a Hermes run metadata row |
| `read_hermes_run(db, run_id)` | Read a Hermes run by run ID |
| `read_hermes_run_by_idempotency(db, idempotency_key)` | Read a Hermes run by idempotency key |
| `reset_store(db)` | Delete all operational data rows, preserving schema |

All functions are stdlib-only (sqlite3, json, datetime). No third-party dependencies.

### 5.1 Foreign Key Enforcement

`open_store` executes `PRAGMA foreign_keys = ON` on every connection. This means:

- Inserting a `scheduled_progress` or `hermes_runs` row with a `project_key` that does not exist in `project_bindings.chat_key` raises `sqlite3.IntegrityError`.
- Deleting a `project_bindings` row that is referenced by child rows raises `sqlite3.IntegrityError` unless the child rows are deleted first.
- `reset_store` already deletes child tables before the parent table, so it works correctly under FK enforcement.

### 5.2 Upsert Semantics

All upsert functions use **partial-update** semantics: omitted optional fields (passed as `None`) are preserved from the existing row using `COALESCE`. To explicitly clear an optional field, the caller must pass a non-`None` value (e.g., an empty string for text fields). This applies to:

- `upsert_project_binding`: `repo_owner_name`, `workspace_path`, `phase` are preserved on conflict when `None`.
- `upsert_scheduled_progress`: `last_report_at`, `next_report_at`, `interval_minutes` are preserved on conflict when `None`.
- `upsert_hermes_run`: `idempotency_key` is preserved on conflict when `None` (to prevent accidental clearing of a deduplication key). Other fields (`role`, `task_type`, `status`, `in_flight_meta`, `project_key`) are full-replacement on conflict.
- v0.2.1: `claim_work_item`, `complete_work_item`, `release_work_item`, `write_work_item`, `surface_escalation`, `resolve_escalation` are atomic single-statement operations (`UPDATE ... RETURNING *`) implemented in TKT-022 helpers; they do not follow upsert semantics.

## 6. Backup and Reset Behavior (v0.1)

### 6.1 Backup

The SQLite database is a single file on the VPS. Backup strategy for v0.1:

1. The SQLite database file should be included in the VPS filesystem backup schedule.
2. For a consistent offline backup, stop the Hermes service before copying the file, or use `sqlite3` to make a backup:
   ```
   sqlite3 /path/to/state.db ".backup /path/to/state.db.bak"
   ```
3. Backup frequency should match VPS backup intervals. Daily is recommended for v0.1.

### 6.2 Reset

To reset operational state (e.g., after corruption or for a clean start):

1. Stop the Hermes service to prevent in-flight writes.
2. Back up the database file if any data should be preserved:
   ```
   cp /path/to/state.db /path/to/state.db.pre-reset
   ```
3. Either remove the database file (it will be recreated on next startup) or call `reset_store(db)` to clear all data rows while preserving the schema.
4. Restart the Hermes runtime.
5. Rehydrate durable decisions from repository artifacts: the runtime must re-read `docs/orchestration/SESSION-STATE.md`, `docs/tickets/`, `docs/architecture/`, and other governance documents to rebuild operational context.

### 6.3 Data Loss Impact

Loss of the operational database may interrupt:

- Scheduled progress report timers (must be reconfigured).
- In-flight Hermes run tracking (runs may need to be restarted).
- Telegram-to-project bindings (must be re-established via `/new_project` or manual configuration).

Database loss **must not** lose canonical product, architecture, security, merge, or deployment decisions, which are stored in repository artifacts under `docs/`. The operational store is rebuildable from repository state plus runtime reconfiguration.

## 7. Database Path

The implementation accepts an explicit database path from the caller. It does not hardcode a production path. The recommended production path on the VPS for v0.2.1+ multi-Hermes deployments is:

```
/srv/devassist/state/operational.db
```

This is the **shared operational store** referenced by all five runtime symlinks (`SELF-DEPLOYMENT-CONTRACT.md` § 4, `MULTI-HERMES-CONTRACT.md` § 4). The filename `operational.db` (not `state.db`) was chosen to avoid the upstream Hermes default-layout collision flagged in RV-SPEC-010 CRIT-1: each per-runtime `~/.hermes/state.db` is a Hermes-managed FTS5 sessions index distinct from this shared operational store.

For pre-multi-Hermes (single-runtime) deployments the path is:

```
/opt/developer-assistant/state.db
```

The path should be configured via environment variable or runtime configuration, not committed to the repository.

Tests use `:memory:` for transient in-process databases or `tempfile` for file-based testing.

## 8. Relationship to Repository Artifacts

| Domain | Authoritative Source | Operational Store |
| --- | --- | --- |
| Product requirements | `docs/prd/` | Not stored |
| Architecture decisions | `docs/architecture/`, `docs/architecture/adr/` | Not stored |
| Ticket status | `docs/tickets/` | Not stored |
| Review verdicts | `docs/reviews/` | Not stored |
| Session state and handoffs | `docs/orchestration/SESSION-STATE.md` | Not stored |
| Telegram chat bindings | Not in repository | `project_bindings` table |
| Project registry | Not in repository | `project_bindings` table |
| Scheduled progress timers | Not in repository | `scheduled_progress` table |
| Hermes run metadata | Not in repository | `hermes_runs` table |
| Inter-runtime work queue | Not in repository | `work_items` table (v0.2.1+) |
| Pending Founder escalations | Not in repository | `escalations` table (v0.2.1+) |

If operational state contradicts repository artifacts, repository artifacts take precedence per `HERMES-RUNTIME-CONTRACT.md` Section 3.

## 9. Concurrency and WAL Guidance

The v0.1 operational store assumes **single-threaded, single-process access** to the SQLite database. The Hermes runtime adapter should use the connection from a single thread or serialize access through a single worker.

If the adapter later shares the connection across threads or async workers:

- Enable WAL mode (`PRAGMA journal_mode = WAL`) to allow concurrent readers while a writer holds the lock. This avoids "database is locked" errors under read-heavy workloads.
- Use `sqlite3.connect(..., check_same_thread=False)` only if the calling code serializes all database access.
- Consider moving to a connection pool or async SQLite driver for high-concurrency scenarios beyond v0.1.

For v0.1 deployments, the default rollback journal mode is acceptable because the expected workload is single-writer with infrequent reads.

## 10. Future Considerations

- Schema versioning and migration: the `_schema_meta` table tracks `schema_version` for future migration support. v0.2.1 introduces the first additive migration (`work_items`, `escalations`); v0.3.0 will add the observability tables per `OBSERVABILITY-CONTRACT.md`.
- Hermes native persistence may be evaluated for conversation context in a follow-up ticket, but structured operational queries remain in SQLite.
- Multi-tenant isolation is explicitly out of scope for v0.1.
- A backup/restore utility script may be added in a future ticket.
- v0.2.1 schema migration history:
  - v0.2.0 → v0.2.1: Add `work_items` and `escalations` tables for multi-Hermes IPC. Idempotent `CREATE TABLE IF NOT EXISTS` plus index creation. No data migration needed (both tables start empty).
