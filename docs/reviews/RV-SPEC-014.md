---
id: RV-SPEC-014
version: 0.1.0
status: draft
reviewer_role: Reviewer
pr_number: 90
verdict: fail
---

# RV-SPEC-014: Architect Pass — Self-Deployment, Multi-Hermes Runtime, Observability, Upstream Adapter, Escalation Policy, Model Catalog

## 1. PR Reviewed

- **PR**: #90 (Architect pass for TKT-020 through TKT-031)
- **Scope**: Complete v0.1 architecture specification covering self-deployment (`SELF-DEPLOYMENT-CONTRACT.md` v0.2.0), multi-Hermes runtime isolation (`MULTI-HERMES-CONTRACT.md` v0.1.0, ADR-005, ADR-006), upstream-adapter abstraction (`UPSTREAM-ADAPTER-CONTRACT.md` v0.1.0, ADR-007), escalation policy (`ESCALATION-POLICY.md` v0.1.0, ADR-008), model catalog (`MODEL-CATALOG.md` v0.2.0, ADR-009, ADR-011), observability (`OBSERVABILITY-CONTRACT.md` v0.1.0, ADR-010, `RECOVERY-PLAYBOOK.md` v0.1.0), and implementation tickets TKT-020 through TKT-031.
- **Lines changed**: ~5,838 additions across 31 files.
- **Doc validation**: `python scripts/validate_docs.py` — **passed**.

## 2. Spec Reviewed

- `docs/architecture/ARCH-001.md` v0.3.0
- `docs/architecture/SELF-DEPLOYMENT-CONTRACT.md` v0.2.0
- `docs/architecture/MULTI-HERMES-CONTRACT.md` v0.1.0
- `docs/architecture/UPSTREAM-ADAPTER-CONTRACT.md` v0.1.0
- `docs/architecture/ESCALATION-POLICY.md` v0.1.0
- `docs/architecture/MODEL-CATALOG.md` v0.2.0
- `docs/architecture/OBSERVABILITY-CONTRACT.md` v0.1.0
- `docs/architecture/OPERATIONAL-STATE-STORE.md` v0.3.0
- `docs/architecture/RESEARCH-001-hermes-and-openclaw-ecosystems.md` v0.1.0
- `docs/architecture/adr/ADR-004-deployment-mechanism.md` v0.1.0
- `docs/architecture/adr/ADR-005-multi-hermes-runtime-isolation.md` v0.1.0
- `docs/architecture/adr/ADR-006-ipc-and-state-mediation.md` v0.1.0
- `docs/architecture/adr/ADR-007-upstream-adapter-shape.md` v0.1.0
- `docs/architecture/adr/ADR-008-escalation-classifier.md` v0.1.0
- `docs/architecture/adr/ADR-009-model-assignment-and-fallback.md` v0.2.0
- `docs/architecture/adr/ADR-010-observability-shape.md` v0.1.0
- `docs/architecture/adr/ADR-011-routing-layer.md` v0.1.0
- `docs/operations/RECOVERY-PLAYBOOK.md` v0.1.0
- `docs/orchestration/SESSION-STATE.md` v0.2.0
- `docs/tickets/TKT-020.md` through `docs/tickets/TKT-031.md`

## 3. Architecture / ADR / PRD References

- **Baseline architecture (main)**: `ARCH-001.md` v0.2.0, `OPERATIONAL-STATE-STORE.md` v0.2.0, `SELF-DEPLOYMENT-CONTRACT.md` v0.1.0, `SESSION-STATE.md` v0.1.0.
- **PRD cross-check**: `PRD-001.md` v0.2.1 § 6 (Functional Requirements), § 9 (Success Criteria), § 12 (Self-Deployment Operational Target), § 13 (Operating Mode, Team Composition, and Upstream Composability).
- **Merge-stack context**: This is the last PR in the merge stack; implementation PRs A/B/C/D are anticipated but not yet available for direct cross-check.

## 4. Review Findings (Severity-Ordered)

### C-001 — CRITICAL: OmniRoute Port Number Contradiction Between ADR-011 / MODEL-CATALOG.md and SELF-DEPLOYMENT-CONTRACT.md

**Finding**: The architecture contains a direct, unambiguous contradiction in the OmniRoute localhost port:

- `ADR-011-routing-layer.md` § Decision, item 1: specialist runtimes point to **`http://localhost:20128/v1`**.
- `MODEL-CATALOG.md` § 5.1: OmniRoute listens on **`localhost:20128/v1`**.
- `SELF-DEPLOYMENT-CONTRACT.md` § 5.3: the `omniroute.service` unit binds **`127.0.0.1:18080`** (`ExecStart=/usr/local/bin/omniroute serve --bind 127.0.0.1:18080 ...`).
- `SELF-DEPLOYMENT-CONTRACT.md` § 8 (Health Verification Invariants): the verify script checks **`http://127.0.0.1:18080/health`** and issues completions through **`http://127.0.0.1:18080/v1/chat/completions`**.

**Impact**: If the install script renders the systemd unit with port 18080 while every runtime config (per ADR-011 and MODEL-CATALOG) points to 20128, all LLM calls will fail on connection refused. The system will immediately fall through to the OpenRouter backup for every call, or fail entirely if the backup is also unavailable. This breaks the v0.1 "one-command install → verify → start" flow.

**Required action**: Harmonize all references to a single port. Update either the systemd unit template in `SELF-DEPLOYMENT-CONTRACT.md` § 5.3 (and the verify invariants in § 8) to 20128, or update `ADR-011` and `MODEL-CATALOG.md` to 18080. Verify that `MULTI-HERMES-CONTRACT.md` § 4 (per-runtime model client config) and `TKT-026` / `TKT-020` scopes align with the chosen port.

### C-002 — CRITICAL: Missing Lightweight Web Interface Architecture (PRD § 6 Contradiction)

**Finding**: `PRD-001.md` v0.2.1 § 6 Functional Requirements states:

> "The system must provide a founder-facing conversational interface through Telegram **and a lightweight web interface**."

The v0.1 architecture does **not** specify any web interface. `UPSTREAM-ADAPTER-CONTRACT.md` v0.1.0 scopes v0.1 to Telegram only and defers OpenClaw to v0.2+. `ARCH-001.md` v0.3.0 § 21 (Future Possibilities) lists the web interface as an open question: "Whether the lightweight web interface is deferred, read-only, or still required in v0.1 after Telegram is working."

**Impact**: The PRD mandates a web interface for v0.1. The architecture treats it as optional/deferred without explicit Founder approval for the deferral and without documenting the deferral in an ADR. This is a direct PRD contradiction.

**Required action**: Either (a) add an ADR and contract documenting the v0.1 web interface shape (even if minimal/read-only), or (b) update `PRD-001.md` with a Founder-approved deferral to v0.2, or (c) document the web interface as a minimal read-only status dashboard bound to the same localhost ports as the health endpoints. The current silent omission is not acceptable.

### M-001 — MAJOR: TKT-031 Assumes Unverified OmniRoute Middleware Extension Point

**Finding**: `TKT-031.md` § 1 scopes:

> "An OmniRoute middleware `src/developer_assistant/observability/omniroute_middleware.py` that: Hooks into the OmniRoute service's request/response pipeline (per OmniRoute v3.7.x's middleware extension point — see `https://github.com/diegosouzapw/OmniRoute`)."

The architecture cites OmniRoute GitHub Issue #265 for Fireworks alias resolution, but **no evidence in the repo** verifies that OmniRoute v3.7.x exposes a stable middleware extension point suitable for intercepting every request/response to record `llm_calls` rows. If the middleware API does not exist, is unstable, or requires a different OmniRoute version, TKT-031 becomes unimplementable as written.

**Required action**: Replace the unverified middleware assumption with a fallback design: (a) instrument at the *runtime client* side (the Python code that issues the HTTP request to OmniRoute/OpenRouter) if OmniRoute middleware is unavailable, or (b) verify the middleware API exists and document the exact API version/commit in `ADR-011` Consequences before merging.

### M-002 — MAJOR: FR-OBS-09 (Log Retention) Lacks Concrete Testability

**Finding**: `OBSERVABILITY-CONTRACT.md` § 13 FR-OBS-09 states:

> "Log retention: systemd journald retains logs for at least 7 days; `vacuum_logs` cron job drops observability SQLite tables older than 30 days."

While FR-OBS-01 through FR-OBS-08 and FR-OBS-10 have clear unit/integration test paths (JSON formatter, contextvar propagation, CLI fixtures, SQLite schema validation, HTTP endpoint tests, playbook command parsing), FR-OBS-09 spans two system-level concerns:

1. **journald 7-day retention** is a `journald.conf` or `systemd-journald` disk-usage policy, not application code. A unit test cannot verify it without mocking the entire systemd subsystem.
2. **`vacuum_logs` cron job** is mentioned but not scoped to any ticket. None of TKT-027 through TKT-031 mention implementing this job.

**Required action**: Add a ticket (or extend TKT-030) for the `vacuum_logs` cron job implementation. For journald retention, the contract should specify how verification is performed (e.g., an install-script invariant that checks `journalctl --disk-usage` against a threshold, or a CI test that spins up a systemd-enabled container).

### M-003 — MAJOR: RECOVERY-PLAYBOOK.md § 8.3 Asks Non-Engineer Founder to Edit an Architecture Document

**Finding**: `RECOVERY-PLAYBOOK.md` § 8.3 (VPS Resource Exhaustion → Memory) instructs:

> "The 1.5-3 GB steady-state estimate in `MULTI-HERMES-CONTRACT.md` § 11 should be re-evaluated against actual measurements; **append the measurement to that section**."

This playbook is explicitly marketed as readable by a non-engineer Founder with no architectural context. Asking the Founder to "append the measurement to that section" of an architecture contract document violates the audience contract and is unlikely to be followed.

**Required action**: Change the instruction to: log the measurement to `/var/log/dev-assist/resource-measurements.log` (or similar) and surface it in the daily digest. Remove the instruction to edit a repository artifact.

### N-001 — MINOR: TKT-020 Does Not Explicitly Invoke TKT-026's Model-Catalog Enforcement CLI

**Finding**: `SELF-DEPLOYMENT-CONTRACT.md` § 6 states that the install script's verify step must check OmniRoute supports each catalog model. `TKT-026.md` scopes a CLI (`model_catalog_cli.py`) that performs this verification. `TKT-020.md` scopes the install/verify scripts but does **not** mention invoking TKT-026's CLI. The integration between the two tickets is implied but not explicit.

**Required action**: Add a cross-reference in `TKT-020.md` § 1 or § 2 stating that `scripts/verify-self.sh` invokes `src/developer_assistant/cli/model_catalog_cli.py` (from TKT-026) as its OmniRoute model-probe step.

### N-002 — MINOR: ADR-011 Considered Options List Option B Before Option A

**Finding**: In `ADR-011-routing-layer.md` § Considered Options, the chosen Option B appears **before** the rejected Option A. While not functionally harmful, it violates the conventional reading flow and makes quick scanning slightly confusing.

**Required action**: Re-order the options so Option A appears first, or add a note explaining why B is listed first (e.g., "B is the chosen option; A is listed below for completeness").

### N-003 — MINOR: ESCALATION-POLICY.md § 5.4 "Redaction List" Not Explicitly Scoped in TKT-023

**Finding**: `ESCALATION-POLICY.md` § 5.4 defines a redaction list for the LLM classifier prompt (e.g., scrubbing `GITHUB_TOKEN`, `TELEGRAM_BOT_TOKEN`). `TKT-023.md` § 1 mentions implementing "the hard-coded prompt, the redaction list, and the latency/cost guards," but does not break out the redaction list as an explicit implementation item with its own acceptance criteria.

**Required action**: Add one bullet to TKT-023 § 1 confirming the redaction list is a constant mapping in the plugin source, tested by a unit test that asserts no secret env-var values appear in the classifier prompt string.

## 5. Per-Ticket Assessment (TKT-020 through TKT-031)

| Ticket | Verdict | Rationale |
| --- | --- | --- |
| **TKT-020** | `pass_with_changes` | Scope is clear (install/verify/rollback/upgrade scripts + systemd units). Minor: should explicitly reference TKT-026 CLI for model-probe invariant. |
| **TKT-021** | `pass` | Per-runtime layout, config rendering, and role-gating are well-scoped. Dependencies on MULTI-HERMES-CONTRACT.md and MODEL-CATALOG.md are clear. |
| **TKT-022** | `pass` | Schema extensions for `work_items`, `escalations`, `founder_identity_bindings`, `upstream_sessions` are precise and map 1:1 to the contracts. |
| **TKT-023** | `pass_with_changes` | Escalation-policy and work-queue plugin scopes are correct. Minor: redaction list needs explicit testable bullet. |
| **TKT-024** | `pass` | Upstream-adapter scaffolding (registry, base contract, Telegram binding, outbound router) is well-bounded and defers OpenClaw to v0.2. |
| **TKT-025** | `pass` | Three custom skills (`classifier`, `progress-report`, `escalation-surface`) align with MULTI-HERMES-CONTRACT.md § 5.1 and UPSTREAM-ADAPTER-CONTRACT.md § 9. |
| **TKT-026** | `pass` | Model-catalog enforcement helper is a clean, testable scope. CLI for install preflight is correctly bounded. |
| **TKT-027** | `pass` | `dev-assist-cli` subcommands map exactly to OBSERVABILITY-CONTRACT.md § 6. Read-only SQLite access and localhost health probes are safe. |
| **TKT-028** | `pass` | Structured logger + `work_item_id` contextvar propagation is a standard, testable pattern. Hermes plugin adapter hook is referenced correctly. |
| **TKT-029** | `pass` | Daily digest + Telegram `/status` command scope matches OBSERVABILITY-CONTRACT.md FR-OBS-04/05. Cron definition is correctly placed. |
| **TKT-030** | `pass` | Recovery-playbook execution discipline (parsing fenced blocks, CI invariant) is a strong, verifiable scope. |
| **TKT-031** | `pass_with_recommendations` | Data-store and health-endpoint scopes are clear. **Substantive concern**: OmniRoute middleware assumption (M-001) must be resolved before implementation begins. |

## 6. Cross-File Consistency Notes

- **Work-items schema**: `MULTI-HERMES-CONTRACT.md` § 6.2, `OPERATIONAL-STATE-STORE.md` § 3.3, and `TKT-022.md` all agree on table shape, column types, and index definitions. ✅
- **Escalation policy → tickets**: `ESCALATION-POLICY.md` § 4 deterministic rules and § 5 LLM classifier are both explicitly referenced in `TKT-023.md`. ✅
- **Model catalog → ADR-009/ADR-011**: `MODEL-CATALOG.md` § 4 role assignments match ADR-009 Decision and ADR-011 Consequences. ✅
- **Observability contract → tickets**: FR-OBS-01..08 are each covered by TKT-027..031 with traceable mappings. FR-OBS-10 maps to TKT-030. FR-OBS-09 is the only gap (M-002). ⚠️
- **Self-deployment → PRD § 12**: Three approval gates (install / start / upgrade + backup) match PRD-001.md § 12.5 exactly. ✅
- **Multi-Hermes → PRD § 13.2**: Five separate runtimes with isolated memory, single Founder-facing entity through Telegram — consistent across MULTI-HERMES-CONTRACT.md, ADR-005, and ARCH-001.md § 11. ✅
- **Upstream adapter → PRD § 13.3**: Abstraction lives inside Orchestrator runtime, v0.1 Telegram-only, v0.2+ OpenClaw slot — consistent across UPSTREAM-ADAPTER-CONTRACT.md, ADR-007, and ARCH-001.md § 13. ✅
- **Port contradiction**: `ADR-011` + `MODEL-CATALOG.md` (20128) vs `SELF-DEPLOYMENT-CONTRACT.md` (18080) — **inconsistent** (C-001). ❌
- **Web interface**: PRD § 6 requires it; architecture omits it — **inconsistent** (C-002). ❌

## 7. Security Notes

- **No secrets in repository files**: Enforced by schema design (OPERATIONAL-STATE-STORE.md § 4), SELF-DEPLOYMENT-CONTRACT.md § 10, and ESCALATION-POLICY.md `secret:*` rules. ✅
- **Secret scrubbing in journald**: Mentioned in SELF-DEPLOYMENT-CONTRACT.md § 10 as a verify invariant. ✅
- **Systemd sandboxing**: `NoNewPrivileges=true`, `ProtectSystem=full`, `ProtectHome=true`, `PrivateTmp=true` on all runtime units. ✅
- **Health endpoints bound to localhost only**: `127.0.0.1` (or `::1`) explicitly forbidden from `0.0.0.0`. VPS firewall rules referenced in SELF-DEPLOYMENT-CONTRACT.md § 7. ✅
- **Escalation-policy coverage**: `secret:*`, `net:*`, `gov:*`, `git:*`, `state:*`, `paid:*`, `deploy:*`, `plugin:*`, `scope:*`, `concept:*` rules cover the major risk categories. ✅
- **LLM-call cost snapshot**: `llm_calls` table snapshots `rate_in_per_1m_usd` and `rate_out_per_1m_usd` at call time, preventing historical cost drift if catalog rates change. ✅

## 8. Final Verdict

**`fail`**

The architecture pass is comprehensive, well-structured, and demonstrates deep research grounding (`RESEARCH-001`). Most tickets are clearly scoped and traceable to their parent contracts. ADRs contain robust option analysis (≥ 3 options each). Security posture and cross-file consistency are generally strong.

However, two **CRITICAL** findings prevent a `pass` or `pass_with_recommendations` verdict:

1. **C-001 (OmniRoute port contradiction)**: A direct, unambiguous port-number mismatch (18080 vs 20128) between the routing-layer ADR / model catalog and the self-deployment contract / systemd unit template. This would break all v0.1 LLM connectivity on first install.
2. **C-002 (Missing web interface)**: A direct contradiction with `PRD-001.md` v0.2.1 § 6, which mandates a lightweight web interface for v0.1. The architecture silently omits it without Founder-approved deferral or ADR justification.

These must be resolved before the Founder approves the architecture and before any implementation tickets (TKT-020..031) are dispatched to the Executor.

Once C-001 and C-002 are fixed and M-001 through M-003 are addressed, the pass should be re-reviewed (RV-SPEC-014-r1) before merge.
