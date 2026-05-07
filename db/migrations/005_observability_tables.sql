-- Migration: 005_observability_tables
-- Adds errors, llm_calls, llm_calls_daily tables for v0.1 observability
-- per OBSERVABILITY-CONTRACT.md v0.1.1 §§ 9-10 and
-- OPERATIONAL-STATE-STORE.md v0.3.0 §§ 3.7-3.9.
-- Idempotent: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.
-- No data migration: all three tables start empty.

-- errors: per-runtime error rollup (FR-OBS-06)
-- Ref: OPERATIONAL-STATE-STORE.md v0.3.0 § 3.7, OBSERVABILITY-CONTRACT.md v0.1.1 § 9
CREATE TABLE IF NOT EXISTS errors (
    err_id        TEXT PRIMARY KEY,
    ts            TEXT NOT NULL,
    runtime       TEXT NOT NULL CHECK (runtime IN ('orchestrator', 'business-planner', 'architect', 'executor', 'reviewer', 'omniroute')),
    work_item_id  TEXT,
    error_class   TEXT NOT NULL,
    message       TEXT NOT NULL,
    context_json  TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_errors_ts ON errors (ts);
CREATE INDEX IF NOT EXISTS idx_errors_runtime_ts ON errors (runtime, ts);
CREATE INDEX IF NOT EXISTS idx_errors_work_item ON errors (work_item_id);

-- llm_calls: per-call LLM cost/latency/token accounting (FR-OBS-07)
-- Ref: OPERATIONAL-STATE-STORE.md v0.3.0 § 3.8, OBSERVABILITY-CONTRACT.md v0.1.1 § 10
CREATE TABLE IF NOT EXISTS llm_calls (
    call_id            TEXT PRIMARY KEY,
    ts                 TEXT NOT NULL,
    runtime            TEXT NOT NULL CHECK (runtime IN ('orchestrator', 'business-planner', 'architect', 'executor', 'reviewer')),
    work_item_id       TEXT,
    model              TEXT NOT NULL,
    routing_path       TEXT NOT NULL CHECK (routing_path IN ('omniroute_endpoint', 'openrouter_endpoint')),
    tokens_in          INTEGER NOT NULL,
    tokens_out         INTEGER NOT NULL,
    latency_ms         INTEGER NOT NULL,
    rate_in_per_1m_usd REAL NOT NULL,
    rate_out_per_1m_usd REAL NOT NULL,
    cost_usd           REAL NOT NULL,
    status             TEXT NOT NULL CHECK (status IN ('success', 'fail')),
    error_class        TEXT
);

CREATE INDEX IF NOT EXISTS idx_llm_calls_ts ON llm_calls (ts);
CREATE INDEX IF NOT EXISTS idx_llm_calls_runtime_model_ts ON llm_calls (runtime, model, ts);
CREATE INDEX IF NOT EXISTS idx_llm_calls_work_item ON llm_calls (work_item_id);

-- llm_calls_daily: daily aggregated cost summary (FR-OBS-07 daily rollup)
-- Ref: OPERATIONAL-STATE-STORE.md v0.3.0 § 3.9, OBSERVABILITY-CONTRACT.md v0.1.1 § 12.2
CREATE TABLE IF NOT EXISTS llm_calls_daily (
    day               TEXT NOT NULL,
    runtime           TEXT NOT NULL CHECK (runtime IN ('orchestrator', 'business-planner', 'architect', 'executor', 'reviewer')),
    model             TEXT NOT NULL,
    routing_path      TEXT NOT NULL CHECK (routing_path IN ('omniroute_endpoint', 'openrouter_endpoint')),
    call_count        INTEGER NOT NULL,
    call_count_success INTEGER NOT NULL,
    call_count_fail   INTEGER NOT NULL,
    tokens_in_total   INTEGER NOT NULL,
    tokens_out_total  INTEGER NOT NULL,
    cost_usd_total    REAL NOT NULL,
    latency_ms_p50    INTEGER,
    latency_ms_p95    INTEGER,
    PRIMARY KEY (day, runtime, model, routing_path)
);

CREATE INDEX IF NOT EXISTS idx_llm_calls_daily_day ON llm_calls_daily (day);

-- Bump schema version to 3
INSERT OR REPLACE INTO _schema_meta (key, value) VALUES ('schema_version', '3');
