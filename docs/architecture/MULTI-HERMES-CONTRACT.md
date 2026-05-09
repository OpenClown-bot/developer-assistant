---
id: MULTI-HERMES-CONTRACT
version: 0.2.1
status: draft
amendments: ADR-014 (live deployment corrections from TKT-032, 2026-05-08)
updated: 2026-05-09
---

# Multi-Hermes Runtime Contract

## 1. Purpose

This document defines the v0.1 contract for running `developer-assistant` as a team of five specialist Hermes runtimes on one Ubuntu 22.04 VPS. It satisfies `PRD-001.md` § 13.2 (multi-Hermes team composition) and operationalizes the architectural shape defined in `ARCH-001.md` v0.3.0 § 11.

The contract is a boundary specification: it states what each runtime is, what config and state it owns, what skills and plugins it loads, and how runtimes coordinate work without violating memory isolation. It does not include scripts, plugin source code, or systemd unit text (those are implementation details for TKT-021 through TKT-025).

## 2. Why Five Runtimes And Not One

`PRD-001.md` § 13.2 mandates that each specialist role runs as its own full Hermes runtime with its own memory and self-learning state. The research record (`RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3.2) established that one Hermes installation is one OS-level process: there is no native mechanism for running multiple specialist runtimes inside a single Hermes installation with isolated memory.

Therefore the multi-Hermes mandate is implemented as **five separate Hermes installations** under `/srv/devassist/runtimes/<role>/.hermes/`, supervised by systemd (ADR-005). Each installation has its own `MEMORY.md`, `USER.md`, sessions database, cron jobs, skills directory, and config — **filesystem-level** isolation enforced by distinct `HERMES_HOME` paths plus the systemd sandbox directives in `SELF-DEPLOYMENT-CONTRACT.md` § 5.2 (`ProtectHome=`, `ReadOnlyPaths=`, `ReadWritePaths=`, `BindReadOnlyPaths=`, `PrivateTmp=`). All five runtimes share the `devassist` Linux uid; the isolation is conditional on correct systemd unit configuration. v0.1's single-Founder threat model accepts the shared-uid limitation.

The five roles map 1:1 to the existing role prompts under `docs/prompts/`:

| Runtime role id | Runtime directory | Role prompt | Founder-facing? |
| --- | --- | --- | --- |
| `orchestrator` | `runtimes/orchestrator/.hermes/` | `docs/prompts/orchestrator.md` | Yes (the only one) |
| `planner` | `runtimes/planner/.hermes/` | `docs/prompts/business_planner.md` | No |
| `architect` | `runtimes/architect/.hermes/` | `docs/prompts/architect.md` | No |
| `executor` | `runtimes/executor/.hermes/` | `docs/prompts/executor.md` | No |
| `reviewer` | `runtimes/reviewer/.hermes/` | `docs/prompts/reviewer.md` | No |

## 3. Per-Runtime Identity

Each runtime is uniquely identified by the value of the `HERMES_DEVASSIST_ROLE` environment variable, set by the systemd unit (`SELF-DEPLOYMENT-CONTRACT.md` § 5.2). Plugins and shared skills read this variable to specialize behavior without requiring per-role plugin packages.

Allowed values: `orchestrator`, `planner`, `architect`, `executor`, `reviewer`. Any other value is rejected by the work-queue plugin's bootstrap check; the runtime exits with non-zero status.

## 4. Per-Runtime Config Layout

**Amended per ADR-014 Correction 2 (2026-05-08):** Hermes Agent v2026.4.30 uses a `model:` top-level section in `config.yaml`, not the legacy `agent.model` / `agent.fallback_models` keys. The config layout below reflects the verified-live format.

Each `runtimes/<role>/.hermes/config.yaml` carries:

- `agent.system_prompt_path`: pointer to the role's prompt file inside the project repo (e.g., `/srv/devassist/repo/docs/prompts/architect.md`).
- `model.default`: the runtime's main model (per `MODEL-CATALOG.md`). This replaces the legacy `agent.model`.
- `model.fallback_models`: ordered list of fallbacks (per `MODEL-CATALOG.md`). This replaces the legacy `agent.fallback_models`.
- `model.provider`: `custom` for all runtimes using OmniRoute (required for Hermes to honor `model.api_key` and `model.base_url`).
- `model.api_key`: the OmniRoute auth key. Set to `${FIREWORKS_API_KEY}` (rendered by the install script's `render_runtime_configs()`). ADR-014 Correction 3.
- `model.base_url`: the OmniRoute endpoint. Set to the value of `OMNIROUTE_BASE_URL` env var (rendered at install time). ADR-014 Corrections 1 and 8.
- `agent.toolsets`: enabled toolsets from § 5 below.
- `skills.external_dirs`: includes `/srv/devassist/shared-skills/` for all five runtimes.
- `plugins.enabled`: includes `dev-assist-escalation-policy` and `dev-assist-work-queue` for all five runtimes.
- `plugins.disabled`: `skill_manage` (agent-managed runtime skill creation; v0.1 production keeps it off).
- `approvals.mode`: `manual` for all five runtimes (`HERMES-SKILL-ALLOWLIST.md` § 3).
- `gateway.enabled`: `true` only for the Orchestrator runtime; `false` for the other four.
- `terminal.backend`: `docker` for Executor and Reviewer; not loaded for the other three.
- `cron.enabled`: `true` for all five runtimes.
- `memory.path`: `/srv/devassist/runtimes/<role>/.hermes/memories/` (default Hermes layout).
- `sessions.path`: `/srv/devassist/runtimes/<role>/.hermes/sessions/`.
- `operational_db.path`: `/srv/devassist/runtimes/<role>/.hermes/operational.db` (the symlink target points to `/srv/devassist/state/operational.db`, the **shared** operational store).

Example `model:` section for the Architect runtime:

```yaml
model:
  default: "accounts/fireworks/models/deepseek-v4-pro"
  fallback_models:
    - "accounts/fireworks/models/kimi-k2p6"
    - "accounts/fireworks/models/glm-5p1"
    - "accounts/fireworks/models/qwen3p6-plus"
  provider: custom
  api_key: "${FIREWORKS_API_KEY}"
  base_url: "https://omniroute.infinitycore.space:8443/v1"
```

The `api_key` and `base_url` values are rendered by the install script from `SELF-DEPLOY.env` at install time. The `{{key}}` template placeholders are substituted by `render_runtime_configs()` — they are NOT Hermes-native `${VAR}` expansion (which would double-expand and break escaping). ADR-014 Correction 8.

The per-runtime Hermes native sessions index lives at `/srv/devassist/runtimes/<role>/.hermes/state.db` and is **not** shared and **not** a symlink — each runtime owns its own sessions index. The `state.db`/`operational.db` filename split eliminates the upstream Hermes default-layout collision flagged in RV-SPEC-010 CRIT-1.

The `ExecStart` for each runtime is specified in `SELF-DEPLOYMENT-CONTRACT.md` § 5.2.1: only the Orchestrator runs `hermes gateway run`; the other four runtimes run `hermes run` (no gateway, no inbound listener).

Per-runtime `.env` is the symlink to `/srv/devassist/secrets/SELF-DEPLOY.env`. Per-runtime `auth.json` and `SOUL.md` are unique to each runtime and not shared.

## 5. Skills Loadout Per Role

The per-role loadout below is the authoritative list of Hermes built-in skills, custom `dev-assist-*` skills, and Hermes plugins that may be loaded by each runtime. Anything outside this list is denied at config-validation time (`HERMES-SKILL-ALLOWLIST.md` § 4 deny-by-default policy).

### 5.0 Custom dev-assist-* skill allowlist (extends `HERMES-SKILL-ALLOWLIST.md` § 4)

The 15 custom skills referenced below are project-local skills built and reviewed inside this repository (write zone: `docs/architecture/shared-skills/` for SKILL.md authorship; the runtime tree under `/srv/devassist/shared-skills/` is the install destination). Per `HERMES-SKILL-ALLOWLIST.md` § 6 ("Project-Local Plugin Policy"), `HERMES_ENABLE_PROJECT_PLUGINS` remains `false`; these custom skills are **skills**, not plugins, and ship as content inside `/srv/devassist/shared-skills/` referenced by `skills.external_dirs`.

Each custom skill must satisfy the standard allowlist fields (Name, Source URL, Version/commit, Purpose, Required credentials, Permission scope, Source review result, Sandbox mode, Dangerous operations, Rollback procedure). Until `HERMES-SKILL-ALLOWLIST.md` is updated to include each of these (TKT-021 follow-up), this contract serves as the authoritative stub:

| Custom skill name | Loaded by | Source location | Version pin | Purpose | Source review status |
| --- | --- | --- | --- | --- | --- |
| `dev-assist-classifier` | Orchestrator | `shared-skills/dev-assist-classifier/` in this repo | git commit at release tag | Classify Telegram messages as: founder-approval response, new project intake, status query, or escalation reply | unreviewed (TKT-025 produces; TKT-021 reviews) |
| `dev-assist-progress-report` | Orchestrator | `shared-skills/dev-assist-progress-report/` | git commit | Compose 30-60 minute progress reports from `work_items` and `escalations` rows; deliver via Telegram | unreviewed |
| `dev-assist-escalation-surface` | Orchestrator | `shared-skills/dev-assist-escalation-surface/` | git commit | Read pending `escalations` rows, format Russian Telegram message with Founder approval prompt, mark surfaced | unreviewed |
| `dev-assist-work-queue-write` | Orchestrator | `shared-skills/dev-assist-work-queue-write/` | git commit | Insert rows into `work_items` table on the Orchestrator only | unreviewed |
| `dev-assist-work-queue-poll` | Planner, Architect, Executor, Reviewer | `shared-skills/dev-assist-work-queue-poll/` | git commit | Claim/complete/release `work_items` rows for the runtime's role | unreviewed |
| `dev-assist-prd-writer` | Planner | `shared-skills/dev-assist-prd-writer/` | git commit | Compose PRD artifacts in `docs/prd/` | unreviewed |
| `dev-assist-questions-writer` | Planner | `shared-skills/dev-assist-questions-writer/` | git commit | Compose question artifacts in `docs/questions/` | unreviewed |
| `dev-assist-arch-writer` | Architect | `shared-skills/dev-assist-arch-writer/` | git commit | Compose ARCH-001 and contracts in `docs/architecture/` | unreviewed |
| `dev-assist-adr-writer` | Architect | `shared-skills/dev-assist-adr-writer/` | git commit | Compose ADR artifacts in `docs/architecture/adr/` | unreviewed |
| `dev-assist-tickets-writer` | Architect | `shared-skills/dev-assist-tickets-writer/` | git commit | Compose ticket Sections 1-9 in `docs/tickets/` | unreviewed |
| `dev-assist-executor-discipline` | Executor | `shared-skills/dev-assist-executor-discipline/` | git commit | Encodes Executor role rules: one ticket per PR, no scope creep, all CI green | unreviewed |
| `dev-assist-write-zone-enforcer` | Executor | `shared-skills/dev-assist-write-zone-enforcer/` | git commit | Pre-write hook denying file writes outside the ticket's allowed write zones | unreviewed |
| `dev-assist-github-workflow` | Executor | `shared-skills/dev-assist-github-workflow/` | git commit | Wraps the project's reviewed REST API + git orchestration code (`HERMES-RUNTIME-CONTRACT.md` § 9) | unreviewed |
| `dev-assist-reviewer-rubric` | Reviewer | `shared-skills/dev-assist-reviewer-rubric/` | git commit | Encodes RV-SPEC and RV-CODE rubric; emits one of `pass`, `pass_with_changes`, `pass_with_recommendations`, `fail` | unreviewed |
| `dev-assist-review-writer` | Reviewer | `shared-skills/dev-assist-review-writer/` | git commit | Compose review artifacts in `docs/reviews/` | unreviewed |

Version pins resolve to a specific git commit at `releases/<release-id>/` activation time (`SELF-DEPLOYMENT-CONTRACT.md` § 4). Source review (§ review-status column) is a TKT-021 acceptance criterion: each skill's `SKILL.md` plus any associated config must be reviewed against `HERMES-SKILL-ALLOWLIST.md` § 4 fields before the runtime is allowed to start in production.

The two custom Hermes plugins (`dev-assist-escalation-policy`, `dev-assist-work-queue`) are listed in § 5.6.

### 5.0.1 Per-Role Loadout Tables

The full per-role loadout. Each runtime's `config.yaml` enables only the listed Hermes built-in skills/toolsets and loads the listed custom skills via `skills.external_dirs`. Plugins are listed separately in § 5.6.

### 5.1 Orchestrator runtime

| Category | Loaded |
| --- | --- |
| Hermes built-in skills | `telegram-gateway`, `cronjob`, `memory` |
| Custom dev-assist skills | `dev-assist-classifier`, `dev-assist-progress-report`, `dev-assist-escalation-surface`, `dev-assist-work-queue-write` |
| Hermes built-in skills NOT loaded | `terminal` (no shell access from Orchestrator), bundled `github-*` (BLOCKED per `HERMES-SKILL-ALLOWLIST.md` § 4.2-4.4), `delegate_task` (BLOCKED per § 4.5), `web`, `browser`, `vision`, `image_gen` |

Purpose: the Orchestrator runtime is the only one that talks to the Founder. It receives Telegram messages, classifies them with `dev-assist-classifier`, writes follow-up work to the SQLite queue with `dev-assist-work-queue-write`, surfaces pending escalations with `dev-assist-escalation-surface`, and delivers progress reports with `dev-assist-progress-report` driven by `cronjob`.

### 5.2 Business Planner runtime

| Category | Loaded |
| --- | --- |
| Hermes built-in skills | `cronjob`, `memory` |
| Custom dev-assist skills | `dev-assist-prd-writer`, `dev-assist-questions-writer`, `dev-assist-work-queue-poll` |
| NOT loaded | `telegram-gateway`, `terminal`, bundled `github-*`, `delegate_task`, `web`, `browser` |

Purpose: produces PRDs (write zone: `docs/prd/`) and questions (write zone: `docs/questions/`). Polls the work queue for items targeting role `planner`.

### 5.3 Architect runtime

| Category | Loaded |
| --- | --- |
| Hermes built-in skills | `cronjob`, `memory` |
| Custom dev-assist skills | `dev-assist-arch-writer`, `dev-assist-adr-writer`, `dev-assist-tickets-writer`, `dev-assist-work-queue-poll` |
| NOT loaded | `telegram-gateway`, `terminal`, bundled `github-*`, `delegate_task`, `web`, `browser` |

Purpose: produces architecture specs (write zone: `docs/architecture/`), ADRs (write zone: `docs/architecture/adr/`), and ticket Sections 1-9 (write zone: `docs/tickets/`). Polls the work queue for items targeting role `architect`.

### 5.4 Executor runtime

| Category | Loaded |
| --- | --- |
| Hermes built-in skills | `terminal` (Docker backend), `cronjob`, `memory` |
| Custom dev-assist skills | `dev-assist-executor-discipline`, `dev-assist-write-zone-enforcer`, `dev-assist-github-workflow`, `dev-assist-work-queue-poll` |
| NOT loaded | `telegram-gateway`, bundled `github-pr-workflow` / `github-issues` / `github-auth` (BLOCKED per `HERMES-SKILL-ALLOWLIST.md` § 4.2-4.4), `delegate_task` (BLOCKED), `web`, `browser` |

Purpose: implements one ticket per PR. The `dev-assist-write-zone-enforcer` skill checks the ticket's allowed write zones before any file write. The `dev-assist-github-workflow` skill wraps the project's reviewed REST API + git orchestration code for branch creation, commit, PR open/update, and merge prompting (`HERMES-RUNTIME-CONTRACT.md` § 9 Constraints). The Docker terminal backend gives the runtime a sandboxed shell for build/test commands without granting host access.

### 5.5 Reviewer runtime

| Category | Loaded |
| --- | --- |
| Hermes built-in skills | `terminal` (Docker backend; read-only mounts of the project repo), `cronjob`, `memory` |
| Custom dev-assist skills | `dev-assist-reviewer-rubric`, `dev-assist-review-writer`, `dev-assist-work-queue-poll` |
| NOT loaded | `telegram-gateway`, bundled `github-*`, `delegate_task`, `web`, `browser` |

Purpose: produces RV-SPEC and RV-CODE reviews (write zone: `docs/reviews/`). Reads the diff, applies the rubric encoded in `dev-assist-reviewer-rubric`, and emits one of the verdicts (`pass`, `pass_with_changes`, `pass_with_recommendations`, `fail`) via `dev-assist-review-writer`. The Docker terminal backend has read-only mounts so the Reviewer can run static checks without modifying the codebase.

### 5.6 Plugins (loaded by all five runtimes)

| Plugin | Purpose | Behavior gating |
| --- | --- | --- |
| `dev-assist-escalation-policy` | Pre-tool-call hook enforcing `ESCALATION-POLICY.md` (deterministic rules + LLM classifier) | Reads `HERMES_DEVASSIST_ROLE` to specialize log labels; deterministic rule set is universal; LLM classifier is invoked from any runtime |
| `dev-assist-work-queue` | Tools for `claim`, `complete`, `release`, `write` against `work_items` and `escalations`; integrated with `cronjob` for periodic polling | Reads `HERMES_DEVASSIST_ROLE` to scope `claim` and `release` queries; `write` is allowed on the Orchestrator only |

Both plugins are Python packages installed once into each runtime's pip environment. The `pyproject.toml` of each plugin declares the Hermes plugin entry-point (`hermes_agent.plugins`) so Hermes auto-discovers them at runtime startup.

## 6. SQLite Operational Store Schema (Multi-Hermes Additions)

This section sketches the two new tables required by the multi-Hermes IPC layer (ADR-006). **The authoritative schema definition is `OPERATIONAL-STATE-STORE.md` v0.2.1 § 3.5 (work_items) and § 3.6 (escalations).** This section is kept for narrative continuity (claim/lease semantics, resolution semantics) but the column/type/constraint detail is now owned by OPERATIONAL-STATE-STORE so a single document is the schema source of truth. The migration ticket is TKT-022.

### 6.1 Existing Tables (Unchanged)

The v0.2.0 schema in `OPERATIONAL-STATE-STORE.md` (project_bindings, scheduled_progress, hermes_runs, _schema_meta) remains intact. The two new tables are added by the v0.2.1 migration.

### 6.2 New Table: `work_items`

The canonical inter-runtime IPC primitive. The Orchestrator writes work items; specialist runtimes claim, complete, or release them. Authoritative column definitions are in `OPERATIONAL-STATE-STORE.md` v0.2.1 § 3.5; the table below restates them for narrative locality:

Columns:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | |
| `created_at` | TEXT NOT NULL | ISO 8601 UTC, default `CURRENT_TIMESTAMP` |
| `updated_at` | TEXT NOT NULL | ISO 8601 UTC |
| `target_role` | TEXT NOT NULL | one of `planner`, `architect`, `executor`, `reviewer` |
| `kind` | TEXT NOT NULL | e.g., `prd_intake`, `architect_pass`, `ticket_implementation`, `ticket_review`, `prd_question_followup` |
| `payload_json` | TEXT NOT NULL | JSON: `{ project_id, ticket_id?, prompt, context_paths, allowed_files, expected_outputs, deadline_at? }` |
| `priority` | INTEGER NOT NULL DEFAULT 50 | 0 highest, 100 lowest |
| `status` | TEXT NOT NULL CHECK | `pending`, `claimed`, `completed`, `failed`, `released` |
| `claimed_by_runtime` | TEXT | NULL until claimed; one of the five role ids |
| `claimed_at` | TEXT | NULL until claimed |
| `claim_lease_until` | TEXT | NULL until claimed; rolling lease, default 30 minutes |
| `completed_at` | TEXT | NULL until completion |
| `result_json` | TEXT | JSON output structure per `HERMES-RUNTIME-CONTRACT.md` § 5 |
| `attempt_count` | INTEGER NOT NULL DEFAULT 0 | |
| `max_attempts` | INTEGER NOT NULL DEFAULT 3 | |
| `originating_run_id` | TEXT | foreign key into `hermes_runs.id` |

Indexes:

- `(target_role, status, priority, id)` — drives the claim query.
- `(claimed_by_runtime, status)` — drives the runtime-internal "what am I working on" query.
- `(claim_lease_until)` partial index where `status = 'claimed'` — drives the lease-reclaim sweep.

Claim semantics:

- A runtime issues `UPDATE work_items SET status='claimed', claimed_by_runtime=?, claimed_at=CURRENT_TIMESTAMP, claim_lease_until=datetime('now', '+30 minutes'), attempt_count=attempt_count+1 WHERE id = (SELECT id FROM work_items WHERE target_role=? AND status='pending' ORDER BY priority, id LIMIT 1) RETURNING *;`.
- If `attempt_count` exceeds `max_attempts` after a failed run, the runtime sets status to `failed` and writes an `escalation` row.
- A periodic sweep (every 5 minutes via the Orchestrator's cron) scans for `status='claimed' AND claim_lease_until < CURRENT_TIMESTAMP`, sets those items back to `pending`, and decrements the lease holder's claim count for forensic accounting.

Idempotency: each work item carries a deterministic dedup key in `payload_json.dedup_key` (e.g., `ticket-implementation:TKT-020`). The work-queue plugin refuses to insert a duplicate row with the same dedup key while a previous row with that key is in `pending`, `claimed`, or `failed` status.

### 6.3 New Table: `escalations`

Pending Founder-facing prompts produced by any runtime when the escalation-policy plugin classifies an action as needing approval. The Orchestrator polls this table and surfaces pending entries to Telegram. Authoritative column definitions are in `OPERATIONAL-STATE-STORE.md` v0.2.1 § 3.6; the table below restates them for narrative locality:

Columns:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | |
| `created_at` | TEXT NOT NULL | |
| `updated_at` | TEXT NOT NULL | |
| `originating_runtime` | TEXT NOT NULL | one of the five role ids |
| `originating_work_item_id` | INTEGER | nullable foreign key into `work_items.id` |
| `trigger_kind` | TEXT NOT NULL | `deterministic_rule:<rule_id>` or `llm_classifier` |
| `context` | TEXT NOT NULL | what situation produced the question |
| `proposed_action` | TEXT NOT NULL | what the runtime is about to do |
| `options_json` | TEXT NOT NULL | JSON list of decision options |
| `recommended_default` | TEXT NOT NULL | |
| `impact` | TEXT NOT NULL | what is affected |
| `urgency` | TEXT NOT NULL CHECK | `low`, `medium`, `high` |
| `durable_artifact_target` | TEXT NOT NULL | repository path where the decision will be recorded |
| `status` | TEXT NOT NULL CHECK | `pending`, `surfaced`, `approved`, `denied`, `expired` |
| `surfaced_at` | TEXT | |
| `resolved_at` | TEXT | |
| `founder_response` | TEXT | normalized English decision note |
| `telegram_message_id` | TEXT | the Telegram message id used to surface this escalation, for follow-up edit/reply |

Indexes:

- `(status, urgency, id)` — drives the Orchestrator's "what should I show next" query.
- `(originating_runtime, status)` — drives the runtime-internal "is my escalation resolved yet" query.

Resolution semantics:

- The Orchestrator's `dev-assist-escalation-surface` skill polls for `status='pending'` entries, sends them to Telegram, and updates `status='surfaced'` plus `surfaced_at`.
- The Orchestrator's `dev-assist-classifier` skill matches incoming Telegram messages against `surfaced` escalations (including via the `/approve <id>` and `/deny <id>` commands).
- On approval/denial, the Orchestrator writes the founder response, sets status to `approved`/`denied`, and (separately) writes the durable artifact at `durable_artifact_target`.
- Originating runtimes block on their escalation by polling for `status IN ('approved','denied')` against the `id` they own.

Expiration: an escalation that remains `pending` or `surfaced` for longer than 7 days (configurable) gets `status='expired'` by the Orchestrator's daily sweep cron job. The originating work item is set to `failed`, and a new escalation is raised informing the Founder of the expiration.

### 6.4 Schema Migration Discipline

Schema additions in this contract land via the existing `OPERATIONAL-STATE-STORE.md` § 6 migration mechanism: a new SQL migration file in `db/migrations/` with a monotonically increasing version number, applied idempotently by the install script during preflight. Rollback of a multi-Hermes upgrade preserves data in `work_items` and `escalations` (both are backed up alongside `operational.db`, the shared operational store).

## 7. Memory And Self-Learning State

Each runtime's memory is **filesystem-level isolated** by distinct `HERMES_HOME` paths plus the systemd sandbox directives in `SELF-DEPLOYMENT-CONTRACT.md` § 5.2:

- `runtimes/<role>/.hermes/memories/MEMORY.md`: operational memory for that role only. The Orchestrator's MEMORY.md is **not** loaded by any other runtime; the Architect's MEMORY.md is **not** loaded by any other runtime; etc.
- `runtimes/<role>/.hermes/memories/USER.md`: per-runtime user model (the runtime's understanding of the Founder's preferences in that role's domain).
- `runtimes/<role>/.hermes/sessions/<id>.jsonl`: full session transcripts. Used only by `session_search` queries that the runtime itself issues.
- `runtimes/<role>/.hermes/state.db`: a Hermes-managed SQLite file holding the per-runtime FTS5 sessions index. **Per-runtime**, not shared, not a symlink. Distinct from the shared operational store at `/srv/devassist/state/operational.db` (the filename split is the CRIT-1 fix from RV-SPEC-010).
- `runtimes/<role>/.hermes/operational.db`: a symlink to `/srv/devassist/state/operational.db`. This is the **shared** store containing `work_items`, `escalations`, project registry, scheduled progress timers, in-flight Hermes run metadata, and (per `OPERATIONAL-STATE-STORE.md` v0.3.0+) the observability tables.

The PRD § 13.2 prohibition on cross-role memory leakage is enforced by:

- The systemd unit's `ProtectHome=true`, `ReadOnlyPaths=/srv/devassist`, and `ReadWritePaths=/srv/devassist/runtimes/<role> /srv/devassist/state /srv/devassist/logs` (`SELF-DEPLOYMENT-CONTRACT.md` § 5.2). The `ReadOnlyPaths`/`ReadWritePaths` pair denies write access to other runtimes' directories at the kernel level even though all five runtimes share the `devassist` uid.
- `BindReadOnlyPaths=/srv/devassist/repo /srv/devassist/shared-skills /srv/devassist/shared-plugins /srv/devassist/releases` providing read-only-by-binding for the shared assets.
- Per-unit `PrivateTmp=true` isolating `/tmp` between runtimes.

The per-unit access restriction is the primary defense; the shared uid is acceptable in v0.1 because the threat model is one trusted Founder/operator, not a hostile multi-tenant environment. A hostile intra-runtime actor (a runtime that is itself prompt-injected and chooses to attack another runtime) is out of scope; v0.2+ may revisit by giving each runtime its own uid.

## 8. Cross-Runtime Coordination Patterns

### 8.1 Orchestrator → specialist work dispatch

1. Orchestrator receives a Telegram message classified as e.g. "founder approves the architecture, dispatch TKT-020 to Executor".
2. Orchestrator invokes `dev-assist-work-queue-write` with `target_role='executor'`, `kind='ticket_implementation'`, payload referencing `TKT-020`.
3. Plugin inserts a row into `work_items` with `status='pending'`.
4. The Executor runtime's `dev-assist-work-queue-poll` skill (driven by `cronjob` every 60 seconds) issues the claim query, picks up the row, runs the implementation, and marks it `completed` with a `result_json` summarizing files changed and validation commands.
5. The Orchestrator's polling loop sees the `completed` row and routes a follow-up `kind='ticket_review'` work item to the Reviewer runtime.

### 8.2 Specialist → Orchestrator escalation

1. The Architect runtime is about to introduce a new paid third-party (e.g., a hosted vector store). The `dev-assist-escalation-policy` plugin's deterministic rule "introduce paid third-party as hard dependency" matches at the `pre_tool_call` hook.
2. The plugin inserts a row into `escalations` with `originating_runtime='architect'`, `originating_work_item_id=<current>`, `trigger_kind='deterministic_rule:paid_third_party'`, etc.
3. The plugin returns a special "blocked" response to the Hermes tool-call dispatcher; the runtime suspends the work item by `release`-ing it back to `pending` state until the escalation resolves.
4. The Orchestrator's `dev-assist-escalation-surface` skill picks up the new escalation, formulates a Russian Telegram message, and waits for the Founder.
5. Founder approves via `/approve <id>` or denies via `/deny <id>`.
6. Originating Architect runtime sees `status='approved'`, re-claims the work item, and proceeds (or sees `status='denied'` and writes a `blocker` artifact instead).

### 8.3 Specialist → durable artifact write

Each specialist runtime is the canonical writer for its allowed write zones (per `CONTRIBUTING.md` role write zones and per the role prompt). The runtime's custom `dev-assist-<role>-writer` skill is the standard mechanism. Cross-zone writes are blocked by the `dev-assist-write-zone-enforcer` skill on the Executor runtime; on the other runtimes, the role prompt's write-zone constraint plus the Hermes approval mode is the gate.

### 8.4 Specialist → specialist (NOT a v0.1 pattern)

There is no direct specialist-to-specialist messaging in v0.1. All cross-role flow is mediated by the Orchestrator, who decides what work item to write next based on the previous one's result. This avoids cycles, keeps the dispatch logic in one place, and makes the audit trail (the sequence of `work_items` rows) trivially reconstructible.

## 9. Failure Semantics

### 9.1 Runtime crash

systemd's `Restart=on-failure` brings the unit back. `StartLimitBurst=5` over `StartLimitIntervalSec=300` prevents thrashing. The lease-reclaim sweep (§ 6.2) returns any work items that were `claimed` by the dead runtime back to `pending` after the lease expires.

### 9.2 LLM provider outage

The runtime's main model becomes unreachable. Hermes' built-in retry plus the per-runtime `agent.fallback_models` config (`MODEL-CATALOG.md` § 4) tries the next model in the chain. If the entire chain is exhausted, the work item attempt fails, `attempt_count` increments, and the item returns to `pending` (or escalates if `attempt_count >= max_attempts`).

### 9.3 Operational state store unavailable

`operational.db` is on local disk; the only realistic outage is filesystem corruption. The escalation-policy plugin's bootstrap check fails fast on startup if the schema version mismatches, preventing a runtime from running against a state store it does not understand. If `operational.db` is unreadable mid-runtime, the runtime exits with a clear error; the Founder runs `rollback-self.sh` to restore the last backup.

### 9.4 Escalation backlog

If the `escalations` table accumulates many `pending` rows, the Orchestrator's surface skill iterates them in `(status, urgency, id)` order. The Founder sees them one at a time in Telegram. The 7-day expiration (§ 6.3) prevents indefinite accumulation.

## 10. Observability

| Signal | Where it lives | How it is read |
| --- | --- | --- |
| Per-runtime stdout/stderr | `journalctl -u devassist-<role>.service` | Founder runs ad-hoc; CI references in TKT-020 verify scripts |
| Per-runtime application logs | `runtimes/<role>/.hermes/logs/` | rotated daily; preserved through rollback to `/srv/devassist/logs/post-rollback/` |
| Work-queue state | `operational.db` `work_items` table | `sqlite3 /srv/devassist/state/operational.db 'SELECT * FROM work_items WHERE status IN (...)'` |
| Escalation state | `operational.db` `escalations` table | same |
| Aggregate runtime status | `systemctl status devassist.target` | shows all five units in one view |
| Hermes session transcripts | `runtimes/<role>/.hermes/sessions/*.jsonl` | runtime-internal `session_search` only |

The Orchestrator runtime additionally surfaces `/status` to Telegram (per `ARCH-001.md` § 7), which queries the work-queue and project-registry tables and produces a Founder-facing status summary.

## 11. Capacity And Resource Planning

The five runtimes share one VPS. Empirical capacity is an open research item (`RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 7). Initial sizing assumption (verified before TKT-011 dispatches):

- Each runtime is one Python 3.11 process plus its Docker terminal sandbox container (Executor and Reviewer only).
- Memory: ~250-500 MB per Python process + ~200 MB per Docker container × 2 = ~1.5-3 GB total under steady state, with headroom for one active LLM streaming response per runtime. (Estimate flagged unverified in `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 5.2.1; TKT-020 dry-run captures empirical numbers.)
- CPU: bursty during LLM tool calls; idle most of the time. One vCPU with 2-4 GB RAM is the lower bound for the trial; 2 vCPU with 4-8 GB is recommended.
- Disk: `operational.db` grows slowly (sub-MB per work item); per-runtime `state.db` (Hermes native sessions index) grows with the session count; `sessions/` JSONL grows ~100 KB per session. Rotate `sessions/` to `~/.hermes/sessions-archive/` after 90 days (TKT-021 follow-up).

If the trial measures any runtime regularly hitting the memory ceiling, the Architect appends an updated sizing note here and a corresponding ADR addendum proposes paid-sandbox or split-host options (those go to "Future Possibilities" in `ARCH-001.md` § 21 because they're paid-third-party-dependent).

## 12. Security Considerations Specific To Multi-Hermes

The `HERMES-SKILL-ALLOWLIST.md` controls remain in force for every runtime. Multi-Hermes-specific additions:

- **No unit may load skills outside its loadout in § 5.** TKT-021 includes a startup check that diff-compares the loaded skills against the per-role expected set from `MULTI-HERMES-CONTRACT.md` § 5; mismatch is a fatal-startup error.
- **No unit may write to another unit's runtime directory.** Per § 7, the systemd `ReadWritePaths=` restriction enforces this at OS level.
- **The `dev-assist-work-queue` plugin's `write` operation is allowed only on the Orchestrator.** Specialist runtimes have only `claim`, `complete`, `release`. The plugin enforces this by reading `HERMES_DEVASSIST_ROLE` and refusing `write` from non-Orchestrator runtimes.
- **Telegram bot token reachability is config-level, not env-level.** All five units load the same `EnvironmentFile=/srv/devassist/secrets/SELF-DEPLOY.env` so `TELEGRAM_BOT_TOKEN` is technically present in every runtime's environment. The secret-segregation guarantee comes from skill loadout: only the Orchestrator's `config.yaml` enables `gateway.enabled: true` and loads the `telegram-gateway` skill (§ 4, § 5.1). Specialist runtimes have no skill that knows how to consume `TELEGRAM_BOT_TOKEN` and cannot reach the Telegram API even though the env var is in their environment. TKT-021 enforces this with a config-level check that asserts the `telegram-gateway` skill is **not** in the loaded set for non-Orchestrator runtimes; mismatch is a fatal-startup error. Defense-in-depth at the network layer is provided by the deterministic escalation rule blocking arbitrary outbound HTTP from non-Orchestrator runtimes (`ESCALATION-POLICY.md` § 4). See `SELF-DEPLOYMENT-CONTRACT.md` § 10.1 for the full secret-segregation pattern.

## 13. Cross-References

- `PRD-001.md` v0.2.1 § 13.2 (multi-Hermes mandate)
- `PRD-001.md` v0.2.1 § 7 (NFR: per-runtime state isolation)
- `ARCH-001.md` v0.3.0 § 11, § 12
- `SELF-DEPLOYMENT-CONTRACT.md` (filesystem layout, systemd units)
- `OPERATIONAL-STATE-STORE.md` v0.2.0 (existing schema)
- `HERMES-SKILL-ALLOWLIST.md` v0.1.0
- `HERMES-RUNTIME-CONTRACT.md` v0.2.0
- `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3, § 6
- `docs/architecture/adr/ADR-005-multi-hermes-runtime-isolation.md`
- `docs/architecture/adr/ADR-006-ipc-and-state-mediation.md`
- Implementation: TKT-021 (runtime layout), TKT-022 (queue schema), TKT-023 (escalation plugin), TKT-025 (custom skills)
