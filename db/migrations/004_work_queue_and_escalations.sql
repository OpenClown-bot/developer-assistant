-- Migration: 004_work_queue_and_escalations
-- Adds work_items, escalations, founder_identity_bindings, upstream_sessions
-- for multi-Hermes IPC per MULTI-HERMES-CONTRACT.md § 6 and UPSTREAM-ADAPTER-CONTRACT.md § 4-5.
-- Idempotent: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.
-- No data migration: all four tables start empty.

PRAGMA journal_mode = WAL;

-- work_items: canonical inter-runtime IPC primitive
-- Ref: OPERATIONAL-STATE-STORE.md v0.2.1 § 3.5, MULTI-HERMES-CONTRACT.md § 6.2
CREATE TABLE IF NOT EXISTS work_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL,
    target_role TEXT NOT NULL CHECK (target_role IN ('planner', 'architect', 'executor', 'reviewer')),
    kind TEXT NOT NULL,
    dedup_key TEXT UNIQUE,
    payload_json TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 50 CHECK (priority >= 0 AND priority <= 100),
    status TEXT NOT NULL CHECK (status IN ('pending', 'claimed', 'completed', 'failed', 'released')),
    claimed_by_runtime TEXT,
    claimed_at TEXT,
    claim_lease_until TEXT,
    completed_at TEXT,
    result_json TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    originating_run_id TEXT REFERENCES hermes_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_work_items_claim
    ON work_items (target_role, status, priority, id);

CREATE INDEX IF NOT EXISTS idx_work_items_runtime
    ON work_items (claimed_by_runtime, status);

CREATE INDEX IF NOT EXISTS idx_work_items_lease
    ON work_items (claim_lease_until)
    WHERE status = 'claimed';

-- escalations: pending Founder-facing prompts
-- Ref: OPERATIONAL-STATE-STORE.md v0.2.1 § 3.6, MULTI-HERMES-CONTRACT.md § 6.3, ESCALATION-POLICY.md § 6
CREATE TABLE IF NOT EXISTS escalations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    originating_runtime TEXT NOT NULL CHECK (originating_runtime IN ('orchestrator', 'planner', 'architect', 'executor', 'reviewer')),
    originating_work_item_id INTEGER REFERENCES work_items(id),
    trigger_kind TEXT NOT NULL,
    context TEXT NOT NULL,
    proposed_action TEXT NOT NULL,
    options_json TEXT NOT NULL,
    recommended_default TEXT NOT NULL,
    impact TEXT NOT NULL,
    urgency TEXT NOT NULL CHECK (urgency IN ('low', 'medium', 'high')),
    durable_artifact_target TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'surfaced', 'approved', 'denied', 'expired')),
    surfaced_at TEXT,
    resolved_at TEXT,
    founder_response TEXT,
    telegram_message_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_escalations_surface
    ON escalations (status, urgency, id);

CREATE INDEX IF NOT EXISTS idx_escalations_runtime
    ON escalations (originating_runtime, status);

CREATE INDEX IF NOT EXISTS idx_escalations_work_item
    ON escalations (originating_work_item_id);

-- founder_identity_bindings: maps upstream identity to internal founder id
-- Ref: UPSTREAM-ADAPTER-CONTRACT.md § 4.4
CREATE TABLE IF NOT EXISTS founder_identity_bindings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    founder_id TEXT NOT NULL,
    adapter_id TEXT NOT NULL,
    upstream_user_id TEXT NOT NULL,
    display_name TEXT,
    bound_at TEXT NOT NULL,
    revoked_at TEXT,
    UNIQUE (adapter_id, upstream_user_id)
);

CREATE INDEX IF NOT EXISTS idx_founder_binding_adapter
    ON founder_identity_bindings (adapter_id, upstream_user_id);

CREATE INDEX IF NOT EXISTS idx_founder_binding_founder
    ON founder_identity_bindings (founder_id);

-- upstream_sessions: per-adapter session continuity
-- Ref: UPSTREAM-ADAPTER-CONTRACT.md § 4.5
CREATE TABLE IF NOT EXISTS upstream_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE,
    adapter_id TEXT NOT NULL,
    founder_id TEXT NOT NULL,
    upstream_chat_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_message_at TEXT NOT NULL,
    paused INTEGER NOT NULL DEFAULT 0,
    current_project_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_session_adapter_founder
    ON upstream_sessions (adapter_id, founder_id);

CREATE INDEX IF NOT EXISTS idx_session_upstream_chat
    ON upstream_sessions (adapter_id, upstream_chat_id);

-- Bump schema version to 2
CREATE TABLE IF NOT EXISTS _schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR REPLACE INTO _schema_meta (key, value) VALUES ('schema_version', '2');