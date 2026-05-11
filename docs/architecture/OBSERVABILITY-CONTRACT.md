---
id: OBSERVABILITY-CONTRACT
version: 0.1.2
status: draft
updated: 2026-05-11
---

# Observability Contract

## 1. Purpose

This contract defines what observability v0.1 commits to: per-runtime structured logging, cross-runtime correlation, a `dev-assist-cli` surface, a Telegram `/status` command, a daily Telegram digest, an LLM-call accounting table, an error rollup table, per-runtime localhost-only health endpoints, log retention, and integration with `docs/operations/RECOVERY-PLAYBOOK.md`.

It closes the v0.1 observability gap surfaced by the Founder in `ADDENDUM-001` (2026-05-06): with five systemd-supervised Hermes runtimes coordinating through SQLite, the question *"where do I look when something breaks"* gets a single, clear answer.

In scope for v0.1: everything in §§ 4-13 below. Out of scope for v0.1 (deferred to "Future Possibilities" or v0.2+):

- Prometheus / Grafana / Loki / ELK / Honeycomb / Datadog. None. v0.1 is on-VPS, no paid services, no extra daemons beyond the five Hermes units and `omniroute.service`.
- Distributed tracing (OpenTelemetry exporters, Tempo/Jaeger).
- Alerting webhooks beyond Telegram.
- Multi-host log shipping.

## 2. Source Of Truth

The Founder approved the v0.1 observability shape on 2026-05-06 via `ADDENDUM-001` (recorded in `docs/orchestration/SESSION-STATE.md` § Current Tooling Decisions). This contract is the durable specification; if `ADDENDUM-001` and this contract disagree on operational behavior, this contract is authoritative and the addendum is updated.

The "no paid services" directive (Founder, 2026-05-06): observability tooling MUST run on the same Ubuntu VPS, MUST NOT introduce a paid third-party dependency, and MUST NOT add a daemon beyond the five Hermes units and `omniroute.service` (`MODEL-CATALOG.md` § 5, `ADR-011`). This is recorded as a binding constraint in `ADR-010-observability-shape.md`.

## 3. Roles And Responsibilities

| Role | Responsibility |
| --- | --- |
| Specialist runtimes | Emit JSON-line logs to systemd journal per § 4 (FR-OBS-01) with correlation via `work_item_id` per § 5 (FR-OBS-02). |
| Orchestrator runtime | Owns the Telegram gateway → answers `/status` per § 7 (FR-OBS-04); owns the cron entry that produces the daily digest per § 8 (FR-OBS-05). |
| Each runtime | Exposes a localhost-only health endpoint per § 11 (FR-OBS-08) on its assigned port. |
| `dev-assist-cli` | The Founder's primary on-VPS tool for status/logs/errors/costs per § 6 (FR-OBS-03). |
| Install script (TKT-026) | Configures journald log rotation per § 12 (FR-OBS-09) and ensures `/var/log/dev-assist/` exists with correct ownership. |
| `RECOVERY-PLAYBOOK.md` | Founder-facing runbook integrating CLI / health-endpoint / journalctl evidence into recovery actions per § 13 (FR-OBS-10). |

## 4. FR-OBS-01 — Structured per-runtime logging

Each Hermes runtime emits JSON-line logs to its systemd journal. One log line per event, one event per line. Logs are accessed via `journalctl -u devassist-<role>.service` (the systemd unit naming convention is established in `SELF-DEPLOYMENT-CONTRACT.md` § 5; the `devassist` prefix without hyphen matches the `devassist:devassist` system user/group).

Mandatory fields per log line:

| Field | Type | Notes |
| --- | --- | --- |
| `ts_iso` | string (ISO 8601) | UTC timestamp with millisecond precision (e.g. `2026-05-06T14:23:00.123Z`). |
| `level` | string | One of `debug`, `info`, `warn`, `error`, `fatal`. |
| `runtime_role` | string | One of `orchestrator`, `business-planner`, `architect`, `executor`, `reviewer`. |
| `work_item_id` | string \| null | The work item this log line is part of (see FR-OBS-02). `null` only when the line is not bound to a work item (e.g., daemon startup). |
| `model` | string \| null | The catalog model identifier (`MODEL-CATALOG.md` § 4.1) when this line records an LLM call. `null` otherwise. |
| `tokens_in` | number \| null | Input tokens for an LLM call. `null` otherwise. |
| `tokens_out` | number \| null | Output tokens for an LLM call. `null` otherwise. |
| `latency_ms` | number \| null | Wall-clock latency in milliseconds for an LLM call. `null` otherwise. |
| `event` | string | A short, structured event identifier (e.g. `llm.call.complete`, `work_item.dequeue`, `escalation.raised`, `health.heartbeat`). Conventions in § 4.1. |
| `message` | string | A human-readable description suitable for Telegram or terminal display. |

Additional optional fields are permitted (e.g. `error_class`, `error_message`, `stack`, `model_endpoint`, `routing_path`). They MUST NOT collide with the mandatory field names.

### 4.1 Event-name conventions

Event identifiers use dot notation: `<domain>.<noun>.<verb>`. Examples:

- `runtime.startup` — the runtime started.
- `runtime.shutdown.graceful` / `runtime.shutdown.forced` — clean stop / killed.
- `work_item.dequeue` — the runtime picked up a work item.
- `work_item.complete` — the runtime finished a work item successfully.
- `work_item.fail` — the runtime failed a work item; an `error_class` field MUST accompany.
- `llm.call.start` — an LLM call started.
- `llm.call.complete` — an LLM call returned a non-error response. `model`, `tokens_in`, `tokens_out`, `latency_ms` MUST be set.
- `llm.call.error` — an LLM call returned an error. `model`, `latency_ms`, `error_class` MUST be set.
- `llm.call.fallback` — the runtime advanced to the next model in its fallback chain. The new model goes in `model`.
- `escalation.raised` — an escalation was created. The escalation row id goes in an `escalation_id` optional field.
- `escalation.resolved` — an escalation was approved or denied. The disposition goes in an `escalation_disposition` optional field.
- `health.heartbeat` — periodic health beat (default cadence: every 30 seconds; cadence is configurable in `MULTI-HERMES-CONTRACT.md` § 4).

The list above is a starting set; new event names follow the same `<domain>.<noun>.<verb>` convention and are added by Executor sessions as needed.

### 4.2 Implementation note

Hermes Agent's built-in logger emits one line per event by default. The implementation MUST configure the runtime so the line is JSON, not plain text. TKT-028 specifies the implementation. journald's `_TRANSPORT=stdout` flag is not relevant — runtimes write to stdout/stderr; systemd captures both.

## 5. FR-OBS-02 — Cross-runtime correlation via `work_item_id`

Every `work_items.id` written to the work_items table by the Orchestrator (`MULTI-HERMES-CONTRACT.md` § 6.2) propagates to every runtime that picks up that item. Every log line emitted in the context of a work item carries that `work_item_id`. The Founder can run:

```
journalctl -u devassist-orchestrator.service \
           -u devassist-planner.service \
           -u devassist-architect.service \
           -u devassist-executor.service \
           -u devassist-reviewer.service \
           -u devassist-omniroute.service \
           --grep work_item_id=<id>
```

(or the equivalent `dev-assist-cli logs --work-item <id>` aggregator, FR-OBS-03) and see the full lifecycle across all five runtimes.

Propagation requirements:

- Orchestrator generates `work_items.id` (UUID v7 or ULID; see `OPERATIONAL-STATE-STORE.md` § 3) at queue-insertion time.
- When a runtime dequeues a work item (`MULTI-HERMES-CONTRACT.md` § 7.3), it sets the `work_item_id` field on its logger context for the duration of that item.
- All log lines produced inside the dequeue→complete window carry that `work_item_id`.
- When the runtime delegates to a downstream runtime (e.g., Architect → Executor), the downstream runtime inherits the same `work_item_id` (it is the same work item).
- `work_item_id` MUST NOT be re-used across distinct work items.

### 5.1 Sub-task correlation

When a runtime's work item produces sub-tasks (e.g., the Architect produces multiple Executor tickets), each sub-task is its own work item with its own `work_item_id`, AND each sub-task's `work_items` row has a `parent_work_item_id` pointing to the originating work item. Log lines for sub-tasks carry the sub-task's `work_item_id`; the parent relationship is reconstructed by joining the queue.

`dev-assist-cli logs --work-item <id> --recursive` (FR-OBS-03) MAY follow `parent_work_item_id` to surface the full hierarchy; the default behavior surfaces only the direct work item.

## 6. FR-OBS-03 — `dev-assist-cli` observability surface

The existing `dev-assist-cli` (introduced by `SELF-DEPLOYMENT-CONTRACT.md` § 5.3) gains the following subcommands. Each subcommand returns JSON by default; a `--format human` flag pretty-prints for terminal viewing.

### 6.1 `dev-assist-cli status`

Outputs a JSON summary of the system state:

```json
{
  "ts_iso": "2026-05-06T14:23:00.123Z",
  "runtimes": [
    {
      "role": "orchestrator",
      "state": "running",            // running | degraded | down
      "uptime_s": 86400,
      "last_error": {                // null if no error in last 24h
        "ts_iso": "2026-05-06T03:12:00.000Z",
        "error_class": "TelegramAPIError"
      },
      "current_model": "minimax-m2.7",
      "current_work_item_id": "01H...",
      "heartbeat_age_s": 12,
      "health_endpoint": "http://localhost:8181/health",
      "health_endpoint_status": 200
    }
    // ...one per runtime, including 'omniroute' if installed
  ],
  "queue": {
    "pending": 3,
    "in_progress": 2,
    "escalated": 1,
    "failed": 0
  },
  "recent_escalations": [             // last 10
    {
      "ts_iso": "...",
      "rule": "deviates_from_concept",
      "disposition": "pending"
    }
  ],
  "today_token_totals": [             // grouped by role + model
    {
      "role": "executor",
      "model": "glm-5.1",
      "tokens_in": 142000,
      "tokens_out": 38000,
      "estimated_usd": 0.27
    }
  ]
}
```

`state` semantics:

- `running`: the runtime's systemd unit is `active`, the heartbeat age is below the threshold (default 60s), the health endpoint returns 200.
- `degraded`: the unit is `active` but at least one of (heartbeat age > threshold, health endpoint not 200, last error in the last 5 minutes) holds.
- `down`: the unit is not `active`, OR no heartbeat in the last 5 minutes.

### 6.2 `dev-assist-cli logs --since <duration> [--role <role>] [--work-item <id>] [--recursive]`

Aggregator that calls journalctl under the hood with appropriate filters. `<duration>` follows journalctl's `--since` syntax (e.g., `1h`, `1 hour ago`, `today`). `--role` filters to a single runtime; omitting includes all five. `--work-item` filters to a specific `work_item_id`. `--recursive` follows `parent_work_item_id` (§ 5.1).

Output is the JSON-line log stream (one line per event), suitable for piping to `jq`.

### 6.3 `dev-assist-cli errors --since <duration> [--role <role>]`

Pulls from the `errors` SQLite table (FR-OBS-06) with timestamps, runtime, work-item id, error class, message. Output is JSON array (or pretty-printed table with `--format human`).

### 6.4 `dev-assist-cli costs --since <duration> [--role <role>] [--model <model>]`

Pulls from the `llm_calls` SQLite table (FR-OBS-07) with per-runtime, per-model token counts and estimated USD. Output is JSON (or pretty-printed table with `--format human`):

```json
{
  "since_iso": "2026-05-05T00:00:00Z",
  "totals": {
    "tokens_in": 1234567,
    "tokens_out": 234567,
    "estimated_usd": 1.42
  },
  "by_role_model": [
    {
      "role": "executor",
      "model": "glm-5.1",
      "calls": 142,
      "tokens_in": 800000,
      "tokens_out": 150000,
      "estimated_usd": 0.92
    }
  ]
}
```

`estimated_usd` is computed using the per-model rates in `MODEL-CATALOG.md` § 4.3 (or whatever rate snapshot was active at call time, stored in the `llm_calls` row per FR-OBS-07).

### 6.5 Implementation note

`dev-assist-cli` is a thin Python (or shell) script under `/opt/dev-assist/bin/dev-assist-cli`, installed by the install script (TKT-026). It reads from journald (`journalctl --output=json`) and SQLite (`/srv/devassist/state/operational.db`) directly; it does NOT call any specialist-runtime endpoint, so it works even when runtimes are down.

## 7. FR-OBS-04 — Telegram `/status` command

The Orchestrator's `telegram-gateway` skill recognizes a `/status` slash-command and returns a human-readable summary equivalent to `dev-assist-cli status --format human`, formatted for Telegram.

Format:

```
Dev Assistant — status as of 2026-05-06 14:23 UTC

Runtimes:
  orchestrator        running  (uptime 24h, model minimax-m2.7)
  business-planner    running  (idle)
  architect           running  (work_item 01H..., model deepseek-v4-pro)
  executor            degraded (last error 3m ago: SchemaValidationError)
  reviewer            running  (idle)
  omniroute           running  (uptime 24h)

Queue: 3 pending, 2 in progress, 1 escalated, 0 failed

Today (UTC):
  executor   glm-5.1         142K in / 38K out   ~$0.27
  architect  deepseek-v4-pro 23K in / 8K out     ~$0.07
  reviewer   kimi-k2.6       12K in / 2K out     ~$0.02

Last 3 escalations:
  14:00  deviates_from_concept (pending)
  10:30  paid:llm_provider_outside_catalog (denied)
  09:15  scope_breaking_change (approved)
```

Multi-message responses are acceptable when the body exceeds Telegram's 4096-char limit. The Orchestrator splits at semantic boundaries (section breaks, table-row boundaries) rather than mid-line.

The command is restricted to the Founder's chat ID (the same chat ID that v0.1 already uses for Founder communication per `MULTI-HERMES-CONTRACT.md` and `UPSTREAM-ADAPTER-CONTRACT.md`). Other senders get a polite "this command is not available to you" response.

## 8. FR-OBS-05 — Daily digest

A new Hermes cron entry (Orchestrator runtime, since it owns the Telegram gateway) runs at 08:00 in the VPS timezone. It produces a Markdown digest of the previous 24 hours.

Content:

| Section | Source |
| --- | --- |
| Header (date + VPS uptime) | `uptime`, ISO date |
| Work items processed | `work_items` rows where `state = 'complete'` and `completed_at >= 24h ago` |
| Escalations raised + disposition | `escalations` rows where `created_at >= 24h ago` |
| Errors logged | `errors` table (FR-OBS-06) where `ts >= 24h ago` |
| Model usage breakdown | `llm_calls` table (FR-OBS-07) grouped by `runtime`, `model`, with summed tokens + estimated USD |
| New auto-generated skills | Hermes' built-in skill management (last 24h of skill creation events) |
| Anomalies | Queue stuck > 30 min; runtime crashed (state went to `down`); classifier drift (ratio of escalations rated `deviation` vs `safe` shifted > 20% from prior day) |

Delivery:

- Written to `/var/log/dev-assist/daily-digest-{YYYYMMDD}.md`.
- Sent to the Founder's Telegram chat as a single message (or multi-part if it exceeds 4096 chars).
- Rotated weekly to `/var/log/dev-assist/archive/{YYYY}-W{NN}/daily-digest-{YYYYMMDD}.md.gz`.

If a daily digest run fails (e.g., Telegram unreachable), the Markdown file is still written to disk. The next successful run retries unsent days from the archive.

## 9. FR-OBS-06 — `errors` SQLite table

A new SQLite table `errors` is added to `/srv/devassist/state/operational.db`:

```sql
CREATE TABLE errors (
    err_id        TEXT PRIMARY KEY,            -- ULID
    ts            TEXT NOT NULL,               -- ISO 8601 UTC
    runtime       TEXT NOT NULL,               -- one of: orchestrator, business-planner, architect, executor, reviewer
    work_item_id  TEXT,                        -- FK to work_items.id, NULL when error not bound to a work item
    error_class   TEXT NOT NULL,               -- e.g. 'TelegramAPIError', 'SchemaValidationError'
    message       TEXT NOT NULL,               -- short human-readable
    context_json  TEXT NOT NULL DEFAULT '{}',  -- arbitrary JSON for stack trace, request details, etc.
    FOREIGN KEY (work_item_id) REFERENCES work_items(id)
);
CREATE INDEX errors_ts_idx ON errors (ts);
CREATE INDEX errors_runtime_ts_idx ON errors (runtime, ts);
CREATE INDEX errors_work_item_idx ON errors (work_item_id);
```

Population: every log line at `level >= 'error'` writes a row. Implementation may batch-write to avoid contention; the maximum write delay is 5 seconds. The schema is owned by `OPERATIONAL-STATE-STORE.md` § 3.

Retention: rows older than 30 days are deleted by a daily cron (same cron as FR-OBS-05). Telegram-delivered digest rows are retained on disk indefinitely (they're in `/var/log/dev-assist/archive/`).

## 10. FR-OBS-07 — `llm_calls` SQLite table

A new SQLite table `llm_calls` is added to `/srv/devassist/state/operational.db`:

```sql
CREATE TABLE llm_calls (
    call_id            TEXT PRIMARY KEY,            -- ULID
    ts                 TEXT NOT NULL,               -- ISO 8601 UTC, request start
    runtime            TEXT NOT NULL,               -- one of: orchestrator, business-planner, architect, executor, reviewer
    work_item_id       TEXT,                        -- FK to work_items.id
    model              TEXT NOT NULL,               -- catalog identifier from MODEL-CATALOG.md § 4.1, e.g. 'glm-5.1'
    routing_path       TEXT NOT NULL,               -- one of: 'omniroute_endpoint', 'openrouter_endpoint'
    tokens_in          INTEGER NOT NULL,
    tokens_out         INTEGER NOT NULL,
    latency_ms         INTEGER NOT NULL,
    rate_in_per_1m_usd REAL NOT NULL,               -- snapshot at call time from MODEL-CATALOG.md § 4.3
    rate_out_per_1m_usd REAL NOT NULL,
    cost_usd           REAL NOT NULL,               -- computed: (tokens_in * rate_in + tokens_out * rate_out) / 1e6
    error_class        TEXT,                        -- NULL on success
    FOREIGN KEY (work_item_id) REFERENCES work_items(id)
);
CREATE INDEX llm_calls_ts_idx ON llm_calls (ts);
CREATE INDEX llm_calls_runtime_model_ts_idx ON llm_calls (runtime, model, ts);
CREATE INDEX llm_calls_work_item_idx ON llm_calls (work_item_id);
```

Population: every LLM call (success or error) writes one row when the call concludes. Both successful and errored calls write a row; errored calls have `error_class` set and `tokens_out` may be 0.

The `rate_in_per_1m_usd` and `rate_out_per_1m_usd` snapshot at call time is critical: when the catalog rates change in a future revision, historical cost remains computed against the rate that was in effect, so the daily digest's per-day cost number stays accurate. The install script (TKT-026) embeds the current rates from `MODEL-CATALOG.md` § 4.3 into a static lookup at install time; runtime changes to `MODEL-CATALOG.md` are picked up only on the next install/upgrade run, which is acceptable because catalog changes go through a Founder approval pipeline anyway.

Retention: rows older than 90 days are deleted by a daily cron. Aggregated per-day per-runtime per-model summaries are written to a separate `llm_calls_daily` table before rows are deleted, so historical cost trends survive retention. (`llm_calls_daily` schema is implementation detail of TKT-031; it carries the same dimensions plus a `day` date column.)

The schema is owned by `OPERATIONAL-STATE-STORE.md` § 3.

## 11. FR-OBS-08 — Per-runtime localhost-only health endpoints

Each Hermes runtime exposes an HTTP health endpoint on a unique localhost-only port. The endpoints answer GET requests on `http://127.0.0.1:<port>/health` with JSON.

| Runtime | Port |
| --- | --- |
| Orchestrator | 8181 |
| Business Planner | 8182 |
| Architect | 8183 |
| Executor | 8184 |
| Reviewer | 8185 |

Bind address MUST be `127.0.0.1` (or `::1`). Binding to `0.0.0.0` is forbidden. The VPS firewall rules (`SELF-DEPLOYMENT-CONTRACT.md` § 7) further enforce that ports 8181..8185 are not exposed to the public network.

Response body:

```json
{
  "ts_iso": "2026-05-06T14:23:00.123Z",
  "role": "orchestrator",
  "state": "running",                           // running | degraded | down (down is not actually returned because the endpoint would not respond)
  "uptime_s": 86400,
  "current_work_item_id": "01H...",             // null if idle
  "current_model": "minimax-m2.7",              // null if idle
  "heartbeat_age_s": 12,
  "queue_stats": {                              // only orchestrator returns these
    "pending": 3,
    "in_progress": 2,
    "escalated": 1,
    "failed": 0
  },
  "version": "0.1.0",
  "build_commit": "abcdef0",
  "loaded_skills": [                            // only present when smoke-mode active OR /health?internal=1 (see § 11.1); per-role expected set pinned in MULTI-HERMES-CONTRACT.md § 5.1–5.5
    "telegram-gateway",
    "cronjob",
    "memory",
    "dev-assist-classifier",
    "dev-assist-progress-report",
    "dev-assist-escalation-surface",
    "dev-assist-work-queue-write"
  ],
  "prompt_path": "docs/prompts/runtime-hermes-orchestrator.md",  // only present when smoke-mode active OR /health?internal=1; resolved agent.system_prompt_path relative to /srv/devassist/repo/ per SELF-DEPLOYMENT-CONTRACT.md § 5
  "prompt_sha256": "0123abcd… (64 hex chars) …"  // only present when smoke-mode active OR /health?internal=1; SHA-256 hex of file at prompt_path, computed at request time (NOT cached at boot)
}
```

`current_work_item_id` and `current_model` reflect the state at the time of the GET; they are not authoritative during a transition (the LLM call may complete between the time the runtime read the value and the time the endpoint serialized the response). Consumers MUST treat them as best-effort.

`dev-assist-cli status` (§ 6.1) calls each health endpoint to populate `health_endpoint_status`. If the endpoint does not respond within 5 seconds, the runtime is reported as `down`.

The endpoints are read-only — no POST/PUT/DELETE methods are defined.

### 11.1 Smoke-mode / internal-admin-gated optional fields (v0.1.2 amendment)

Three additional optional fields are added to the `/health` JSON to support the behaviour-level deployment smoke specified by `TKT-041` v0.1.1 § 4 AC-2 + AC-4. The fields are **backward-compatible additions**: existing consumers that ignore them are unaffected, and they are **absent from production-posture `/health` responses by default** — the gate (described below) controls whether they appear.

| Field | Type | Semantics | Source contract |
| --- | --- | --- | --- |
| `loaded_skills` | `list[str]` | The set of skill names currently loaded into the runtime. The per-role expected sets are owned by `MULTI-HERMES-CONTRACT.md` § 5.1–5.5 (each role's authoritative loadout table); this contract does NOT duplicate the per-role values — cite § 5.1–5.5 as the source of truth. | `TKT-041` v0.1.1 § 4 AC-2 (behaviour-level skill-loadout probe). |
| `prompt_path` | `string` | The resolved `agent.system_prompt_path` for the runtime, as a path relative to `/srv/devassist/repo/` (the install root per `SELF-DEPLOYMENT-CONTRACT.md` § 5). The per-role canonical filename under `docs/prompts/` is owned by `MULTI-HERMES-CONTRACT.md` § 5.1–5.5 role table (e.g., `docs/prompts/architect.md` for the architect runtime; `docs/prompts/runtime-hermes-orchestrator.md` for the orchestrator runtime per the ARCH-002 § 12.1 path correction). | `TKT-041` v0.1.1 § 4 AC-4 (i), (iii). |
| `prompt_sha256` | `string` | SHA-256 hex digest of the file content at the resolved `prompt_path`. Computed **at request time on every `/health` GET** — NOT cached at runtime boot. Computing at request time is load-bearing for AC-4's post-boot tamper detection (a boot-cached value would miss a tamper that occurred after the runtime started). | `TKT-041` v0.1.1 § 4 AC-4 (i), (ii). |

**Production-posture gate (default: absent).** Production `/health` responses MUST NOT include `loaded_skills` / `prompt_path` / `prompt_sha256` unless the request is **either** (a) made while the smoke-mode marker file `/srv/devassist/state/smoke-mode.flag` (mode `0400`, owner `devassist:devassist` per `TKT-041` v0.1.1 § 1.4 (1)) is present, **or** (b) authenticated as an internal admin probe via the `?internal=1` query-string parameter on the localhost-only `/health` endpoint. The Executor implementation chooses the exact authentication mechanism for the `?internal=1` path within this constraint (`TKT-041` v0.1.1 § 5 Allowed Files note on `tests/test_observability_manager_smoke.py`).

**Rationale for the gate (per `TKT-041` v0.1.1 § 8 risk bullet 1).** A loaded-skills enumeration on an unrestricted production endpoint would leak architecture details (the per-role skill loadout reveals the project's role-separation topology, which is a defense-in-depth concern even though the contract itself is public). The gate keeps the surface available to the smoke and to internal admin probes while denying it on the default production `/health` posture. Residual risk — a misconfigured firewall combined with a leaked internal-admin token — is mitigated at the VPS firewall layer per `SELF-DEPLOYMENT-CONTRACT.md` § 7.

**Backward compatibility.** Existing `/health` consumers (`dev-assist-cli status` per § 6.1; daily-digest assembly per § 8; the Telegram `/status` command per § 7) ignore unknown fields. Adding three optional fields gated to smoke-mode / internal-admin posture does not change the response shape any existing consumer observes. The on-VPS-only observability shape (`ADR-010-observability-shape.md`) is preserved unchanged — these fields are emitted by the same localhost-only `/health` endpoint and do NOT introduce a new transport, daemon, or surface.

**Cross-references.** `TKT-041` v0.1.1 § 4 AC-2 + AC-4 (source contract for the field additions and the smoke assertions that consume them); `MULTI-HERMES-CONTRACT.md` § 5.1–5.5 (source of truth for the per-role `loaded_skills` expected values and the per-role canonical `prompt_path`); `SELF-DEPLOYMENT-CONTRACT.md` § 5 (install root for resolving `prompt_path`); `ADR-010-observability-shape.md` (on-VPS-only observability shape — unchanged by this amendment).

## 12. FR-OBS-09 — Log retention and rotation (split into testable sub-requirements per RV-SPEC-014 M-002)

Log retention has three independently testable sub-requirements. The split exists because journald retention is a system-level configuration (not application code) and cannot be unit-tested; SQLite-row retention IS application code and must be unit-testable. Treating both under one FR-OBS-09 led to confusion in TKT-031's draft acceptance criteria, which the M-002 finding called out.

### 12.1 FR-OBS-09a — Journald retention configuration (config-file existence)

The install script (TKT-020) writes `/etc/systemd/journald.conf.d/dev-assist.conf` with the following key=value pairs:

| Setting | Value | Rationale |
| --- | --- | --- |
| `Storage=persistent` | persistent | Survive reboot. |
| `SystemMaxUse=` | `1G` | Caps total journald disk use; on a typical VPS this is plenty for ~30 days at v0.1 traffic. |
| `MaxRetentionSec=` | `30d` (`2592000`) | Lines older than 30 days are deleted by journald. |
| `MaxFileSec=` | `1d` (`86400`) | Roll the file daily for easier `journalctl --since` slicing. |
| `Compress=yes` | yes | Default; reduces disk pressure. |

Verifiable by checking the config file contains the expected key=value lines. The install script's verify step (TKT-020) asserts this; no application unit test is needed because the file is system config rendered by a shell script, not application code.

### 12.2 FR-OBS-09b — SQLite-row retention cron job (unit-testable)

A cron job in `/etc/cron.d/dev-assist-observability` (laid down by TKT-020's install script; SQL body owned by TKT-031) runs daily at 03:00 UTC and:

- Deletes rows from `errors` where `ts < now() - 90 days` (or `60 days` per § 9 below; coordinate with the table-level retention statement, which is authoritative).
- Deletes rows from `llm_calls` where `ts < now() - 90 days` AND a corresponding row exists in `llm_calls_daily` for that `(date, runtime_role, model_id)` (i.e., the row's data has been aggregated into the daily summary).

Verifiable by a unit test against a synthetic `operational.db`: insert old rows, run the SQL the cron runs (the SQL is exposed as a function in `observability_store.py`), assert the rows are deleted and the daily-summary rows remain.

### 12.3 FR-OBS-09c — Install-time verification (config-file health-check)

The install verify step (`scripts/verify-self.sh`, TKT-020) asserts that:

- `/etc/systemd/journald.conf.d/dev-assist.conf` exists and contains the expected key=value pairs from § 12.1.
- `/etc/cron.d/dev-assist-observability` exists and contains the expected cron entries from § 12.2.
- `journalctl --disk-usage` returns a number below `SystemMaxUse=` (sanity check that journald has applied the config; not a strict bound, since journald may not have rotated yet immediately after install).

Verifiable by the verify script reading the files and asserting their content. If any check fails, install fails fast with a diagnostic.

### 12.4 Daily-digest archive rotation (system-level)

Daily-digest Markdown files in `/var/log/dev-assist/` are rotated weekly to `/var/log/dev-assist/archive/{YYYY}-W{NN}/` and gzipped; a separate cron deletes archive files older than 1 year. Log rotation uses `logrotate` (a stock Ubuntu package, not an extra daemon).

`errors` and `llm_calls` SQLite-table retention is defined in §§ 9 and 10 above; the cron that enforces them is FR-OBS-09b above.

## 13. FR-OBS-10 — Recovery playbook integration

`docs/operations/RECOVERY-PLAYBOOK.md` (Founder-facing runbook) documents the diagnose-then-act flow when a runtime is wedged, the queue is stuck, or escalations are piling up. It cross-references this contract:

- "Where do I look first?" → `dev-assist-cli status` (FR-OBS-03 § 6.1) and `/status` Telegram command (FR-OBS-04).
- "Why did this work item fail?" → `dev-assist-cli logs --work-item <id> --recursive` (FR-OBS-03 § 6.2).
- "What errors are happening?" → `dev-assist-cli errors --since 1h` (FR-OBS-03 § 6.3) or the daily digest § 8.
- "How much have I spent today?" → `dev-assist-cli costs --since today` (FR-OBS-03 § 6.4) or the daily digest § 8.
- "Why is the executor not responding?" → curl the health endpoint at `http://127.0.0.1:8184/health` (FR-OBS-08 § 11).
- "How do I restart a wedged runtime?" → `systemctl restart devassist-<role>.service` (and the playbook describes the post-restart verification).

The playbook is in the Architect's write zone but its purpose is operational; it must be readable by the Founder without prior architectural context. See `docs/operations/RECOVERY-PLAYBOOK.md`.

## 14. ObservabilityManager class specification (RV-SPEC-014 M-003 fix)

The runtime-side observability code is owned by a single class, `ObservabilityManager`, instantiated once per Hermes runtime at startup. This section specifies its responsibilities, interface, lifecycle, and relationship to the surrounding modules so an Executor can implement it (TKT-031) without architectural guesswork.

### 14.1 Responsibilities

`ObservabilityManager` owns:

- The runtime's logger context — the `work_item_id` propagated through every log line emitted while the runtime is processing a work item (FR-OBS-02).
- The runtime's connection to the operational store — exposes `record_llm_call(...)` and `record_error(...)` calls that proxy to `observability_store.py`.
- The per-runtime localhost-only health-endpoint lifecycle (FR-OBS-08) — start at runtime startup, drain on SIGTERM, release the bound port.
- The structured-logging adapter that ensures every JSON-line log emitted by the runtime carries the mandatory fields in § 4.

`ObservabilityManager` does NOT own:

- The catalog parser (TKT-026).
- The dev-assist-cli (TKT-027) or the daily digest renderer (TKT-029) — those are out-of-process consumers that read directly from journald + `operational.db`.
- The OmniRoute server-side middleware — that's a separate optional module (TKT-031 § 1; SECONDARY observability path).

### 14.2 Public interface

```python
class ObservabilityManager:
    def __init__(
        self,
        runtime_role: str,                 # "orchestrator" | "business-planner" | "architect" | "executor" | "reviewer"
        operational_db_path: str,          # /srv/devassist/state/operational.db
        health_endpoint_port: int,         # 8181..8185 per FR-OBS-08
        catalog_parser: ModelCatalogParser,  # from TKT-026
    ) -> None: ...

    async def start(self) -> None:
        """Bind the health endpoint, open the SQLite connection (WAL mode), register the structured-logging adapter."""

    async def stop(self) -> None:
        """Drain pending writes, close SQLite, release health-endpoint port. Idempotent."""

    def set_work_item_context(self, work_item_id: str | None) -> None:
        """Set the logger-context work_item_id for the current async task. Called at work-item dequeue (TKT-028)."""

    def clear_work_item_context(self) -> None:
        """Clear the logger-context work_item_id. Called at work-item complete/fail."""

    def record_llm_call(
        self,
        model_id: str,
        routing_path: str,                 # "omniroute_endpoint" | "openrouter_endpoint"
        tokens_in: int,
        tokens_out: int,
        latency_ms: int,
        cost_usd: float,
        status: str,                       # "success" | "fail"
        error_class: str | None = None,
    ) -> None:
        """Write a row to llm_calls. work_item_id is read from the current logger context. Synchronous; non-blocking via background flush queue."""

    def record_error(
        self,
        kind: str,                         # canonical error class
        message: str,
        stack: str | None = None,
        context: dict | None = None,
    ) -> None:
        """Write a row to errors. work_item_id and runtime_role are read from instance state."""
```

### 14.3 Lifecycle

`ObservabilityManager` is instantiated by the TKT-028 Hermes plugin at runtime startup, AFTER the catalog parser (TKT-026) is constructed (the manager needs the parser to compute `cost_usd` for `record_llm_call` if the caller did not pre-compute it). The startup sequence:

1. Read `runtime_role` from env var `DEVASSIST_RUNTIME_ROLE`.
2. Read `operational_db_path` from env var `DEVASSIST_OPERATIONAL_DB` (default `/srv/devassist/state/operational.db`).
3. Read `health_endpoint_port` from env var `DEVASSIST_HEALTH_PORT` (set per FR-OBS-08 table).
4. Construct `ModelCatalogParser` from `MODEL-CATALOG.md` (TKT-026).
5. Construct `ObservabilityManager(runtime_role, operational_db_path, health_endpoint_port, catalog_parser)`.
6. `await manager.start()`.

On SIGTERM:

1. The runtime adapter calls `await manager.stop()`.
2. `stop()` drains the background flush queue (max 5s wait), closes SQLite, releases the health-endpoint port.
3. The runtime exits.

### 14.4 Relationship to LLM client instrumentation

The client-side LLM instrumentation (TKT-031 § 1, PRIMARY observability path) is a separate module (`llm_client_instrumentation.py`) that wraps the runtime's HTTP client to OmniRoute / OpenRouter. The wrapper calls `ObservabilityManager.record_llm_call(...)` after each request completes. The wrapper does NOT need to know about the manager's other responsibilities; it sees the manager only through the `record_llm_call` method.

### 14.5 Relationship to the OmniRoute server-side middleware (SECONDARY)

If the OmniRoute v3.7.x extension API is verified per ADR-011's "OmniRoute pinning" Consequences and the verified API contract is recorded, a separate `omniroute_middleware.py` module may be implemented. It runs INSIDE the `omniroute.service` process (not inside the Hermes runtime), so it does NOT use `ObservabilityManager` directly. Instead, it writes its own rows to `operational.db` via `observability_store.py` (which is process-safe under SQLite WAL mode). The two paths (client-side primary, server-side optional) produce parallel rows that can be cross-checked for accounting consistency.

### 14.6 Testability

Per RV-SPEC-014 M-002 split, the manager's responsibilities map cleanly to FR-OBS-09's sub-requirements:

- `record_llm_call` and `record_error` writes ARE testable application code (FR-OBS-09b).
- The health-endpoint lifecycle IS testable (TKT-031 § 4.4).
- Journald retention configuration is NOT this class's concern — it is FR-OBS-09a (system-level config) and FR-OBS-09c (verify step).

## 15. Cross-References

- `PRD-001.md` v0.2.1 § 13.1 (autonomy default — observability is the safety net for autonomy)
- `ARCH-001.md` v0.3.0 § 23 (observability architecture summary)
- `ADDENDUM-001` (Founder, 2026-05-06) — the source requirement
- `MODEL-CATALOG.md` v0.2.0 § 8 (cost posture cross-references FR-OBS-07)
- `ESCALATION-POLICY.md` § 4.6 (escalation events appear in journald + `escalations` table; daily digest summarizes)
- `MULTI-HERMES-CONTRACT.md` § 6.2 (`work_items` table; `work_item_id` propagation source), § 7.3 (dequeue path that sets `work_item_id` context), § 9.4 (backoff cadence informs heartbeat thresholds)
- `OPERATIONAL-STATE-STORE.md` § 3 (schema for `errors`, `llm_calls`)
- `SELF-DEPLOYMENT-CONTRACT.md` § 5.2 (systemd units), § 5.3 (`dev-assist-cli`), § 6 (verify step), § 7 (firewall rules for 8181..8185)
- `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 5.4, § 6.7 (on-VPS observability findings; rejection of paid services)
- `ADR-010-observability-shape.md` (decision: on-VPS only, paid-service alternatives rejected)
- `ADR-011-routing-layer.md` (`routing_path` enum source for `llm_calls`)
- `docs/operations/RECOVERY-PLAYBOOK.md` (FR-OBS-10 integration target)
- `docs/tickets/TKT-041-behaviour-level-deployment-smoke.md` v0.1.1 § 4 AC-2 + AC-4 — source contract for the `loaded_skills` / `prompt_path` / `prompt_sha256` `/health` fields specified in § 11.1 (v0.1.2 amendment)
- Implementation: TKT-027 (CLI), TKT-028 (structured logging + work_item_id propagation), TKT-029 (daily digest + Telegram /status), TKT-030 (recovery playbook execution discipline), TKT-031 (`errors` + `llm_calls` tables + health endpoints)
