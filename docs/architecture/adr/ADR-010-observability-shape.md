---
id: ADR-010
version: 0.1.0
status: draft
---

# ADR-010: Observability Shape — On-VPS only, journald + SQLite + Telegram + cron, no paid services

## Status

Draft, pending Founder approval. Closes the v0.1 observability gap surfaced in `ADDENDUM-001` § 2 (2026-05-06). Related: ADR-002 (operational state store choice — SQLite), ADR-005 (multi-Hermes runtime isolation), `OBSERVABILITY-CONTRACT.md`.

## Context

`ARCH-001.md` v0.3.0 commits to a five-runtime topology where five Hermes specialist runtimes coordinate through a SQLite-mediated work queue (ADR-005, ADR-006). Each runtime is a separate systemd unit, each owns its own memory store, each calls the routing layer (`ADR-011`) for LLM access. The system is autonomous by default per `PRD-001.md` § 13.1.

This shape raises a non-optional operational question: when something breaks, *where does the Founder look?* Without an answer, autonomy is a liability — the Founder cannot diagnose a wedged runtime, a stuck queue, or a model-spend anomaly without the Architect rebuilding context every time.

The Founder issued a directive in `ADDENDUM-001` § 2.1 (2026-05-06): close the gap *in v0.1*, with the explicit constraint that the v0.1 commit is *on-VPS only*: no paid services, no extra daemons beyond the five Hermes units (now six, including `omniroute.service` per `ADR-011`).

The decision space is therefore not "which observability stack" but "which observability *shape* fits the on-VPS-only constraint while answering the Founder's diagnostic questions."

## Decision

Adopt an **on-VPS-only observability shape** built on three primitives that Ubuntu 22.04 already provides plus one application-layer integration:

1. **systemd journald** for structured log capture, in-memory + persistent on-disk storage, retention/rotation, and time-window filtering. Specialist runtimes write JSON-line stdout/stderr; systemd captures and indexes both. No log shipper, no extra log daemon.
2. **SQLite** for two new operational tables (`errors`, `llm_calls`) co-located with the existing `work_items` and `escalations` tables in `/srv/devassist/state/operational.db`. No separate metrics database.
3. **cron** (the system cron, not Hermes' Hermes-skill cron, to keep observability hardened against Hermes failure) for log retention enforcement, daily-digest assembly, and aggregate-table writes. cron is on every Ubuntu install; no daemon to add.
4. **Telegram** as the human-facing surface: the Orchestrator's existing `telegram-gateway` skill handles a `/status` command and the Orchestrator's cron entry (this one runs through Hermes' cron skill, since it must access the Orchestrator's LLM context to format and authenticate) sends a daily digest. Telegram credentials are already a v0.1 hard dependency for upstream routing — no new third-party.

A `dev-assist-cli` binary is the glue: it reads `journalctl --output=json` and SQLite directly, returning JSON or human-formatted output. It does NOT call runtime endpoints, so it works even when runtimes are down.

Per-runtime localhost-only health endpoints (ports 8181..8185, bind `127.0.0.1`) provide a synchronous "is it alive" signal. They are read-only HTTP, no extra daemon.

The full functional surface is `OBSERVABILITY-CONTRACT.md` FR-OBS-01..10. This ADR records WHY this shape (not Prometheus/Grafana/Datadog/Honeycomb/Sentry/Loki/ELK) was chosen.

## Considered Options

### Option A — On-VPS only: journald + SQLite + cron + Telegram + dev-assist-cli (CHOSEN)

How it works: as in the Decision section.

Trade-offs:

- + Zero new daemons beyond `omniroute.service`. Ubuntu's stock systemd, sqlite3, cron, and (Founder's existing) Telegram bot do all the work.
- + No paid third-party. Aligns with `ADDENDUM-001` § 2.1 ("v0.1 is on-VPS, no paid services") and the v0.1 budget envelope (`PRD-001.md` § 13.1).
- + Founder can `ssh` into the VPS and run `journalctl` / `sqlite3 operational.db` / `dev-assist-cli` to debug, with no separate dashboard to learn.
- + Recovery is `systemctl restart devassist-<role>.service` — a one-line action documented in `RECOVERY-PLAYBOOK.md`.
- + Cross-runtime correlation via `work_item_id` works without distributed tracing infrastructure (the field is just propagated through the work queue and into log lines).
- + Observability data survives a runtime crash (journald + SQLite are external to the runtime process).
- − No pre-built dashboards. Mitigated by `dev-assist-cli status --format human` and the daily digest.
- − No real-time alerting beyond Telegram. Mitigated by the Founder being the only operator; alerts beyond Telegram aren't useful at v0.1 scale.
- − Search is `journalctl --grep` and `sqlite3 SELECT` — less ergonomic than Elastic/Loki. Mitigated by `dev-assist-cli logs` with structured filters, plus the typical query pattern at v0.1 (a handful of work items per day) doesn't strain `journalctl`.
- − No long-term time-series for trend analysis. Mitigated by the daily-aggregate `llm_calls_daily` table (`OBSERVABILITY-CONTRACT.md` § 10) which retains per-day per-runtime per-model summaries indefinitely.

### Option B — Self-hosted Prometheus + Grafana stack on the VPS (REJECTED)

How it works: prometheus-node-exporter on the VPS, runtimes expose `/metrics` with prom-client, Prometheus scrapes, Grafana renders dashboards, alertmanager sends Telegram alerts.

Trade-offs:

- + Industry-standard.
- + Powerful query language, well-known dashboards.
- − Adds three daemons (prometheus, grafana, alertmanager) to a VPS already running six (Hermes × 5 + OmniRoute). Memory budget on a small VPS becomes painful.
- − Disk pressure: Prometheus's TSDB at default retention plus Grafana's render cache plus journald is a lot.
- − Configuration is non-trivial for a single-operator system. The Founder pays the cost of learning Grafana for the diagnostic value of `journalctl --grep work_item_id=...` plus a few `sqlite3` queries.
- − Dashboard maintenance is real: when the runtime emits a new event type, the dashboard doesn't update unless the Architect updates a Grafana JSON.
- − Adds two ports to the firewall surface (Prometheus 9090, Grafana 3000) even if both are bound to localhost.

Rejected: violates the "no extra daemons beyond five Hermes units (now six w/ omniroute)" directive. The Founder is the only operator at v0.1 scale; the toolset is overkill.

### Option C — Hosted Datadog / Honeycomb / Sentry (REJECTED)

How it works: each runtime ships logs / metrics / errors to a hosted SaaS via SDK.

Trade-offs:

- + Best dashboards, alerting, search.
- + No on-VPS storage burden.
- − Paid third-party. `ADDENDUM-001` § 2.1 explicitly rejects this for v0.1.
- − Adds a per-call dependency on an external SDK; if Datadog is down, observability is degraded but observability of the degradation is also degraded (the runtime can't tell the Founder "I can't reach Datadog" if the channel for telling the Founder is via Datadog).
- − Data exfiltration: log lines may carry user data, work-item content, model outputs. Storing in a SaaS adds a privacy attack surface.

Rejected: violates `ADDENDUM-001` § 2.1's "no paid services" constraint.

### Option D — Self-hosted Loki + Grafana for logs only (REJECTED)

How it works: runtimes write JSON-line logs as today; Promtail ships to Loki; Grafana renders.

Trade-offs:

- + Better search than `journalctl --grep`.
- + Structured-log-native.
- − Adds Loki + Promtail + Grafana = three daemons.
- − Same disk-pressure / memory-pressure / config-overhead concerns as Option B at half the value (logs only, not metrics).

Rejected: "extra daemons" and "configuration overhead" concerns dominate.

### Option E — OpenTelemetry Collector + a hosted backend (REJECTED)

How it works: runtimes emit OTel spans/metrics/logs to a local collector, which exports to a hosted backend (e.g., Honeycomb, Tempo, etc.).

Trade-offs:

- + Modern, distributed-tracing-native.
- − Distributed tracing for a five-runtime system that already correlates via `work_item_id` is overkill at v0.1 scale.
- − Hosted backend = paid service.
- − Local collector = extra daemon.

Rejected: violates both constraints.

### Option F — Per-runtime stdout to log files, custom rotation (REJECTED)

How it works: runtimes write to `/var/log/dev-assist/<role>.log`, logrotate rotates daily.

Trade-offs:

- + Familiar Unix shape.
- − systemd already does this with extra metadata indexed (priority, transport, unit, etc.). Reinventing this discards systemd's existing capabilities.
- − Loses the systemd-native `journalctl --since` / `--unit` / `--grep` filters; replacement is `grep` over flat files.
- − Cross-runtime correlation requires merging files manually; journald merges automatically when querying multiple `--unit` flags.

Rejected: weaker than journald with no compensating advantage.

### Option G — Custom dashboard web app on the VPS (REJECTED)

How it works: a small Flask/FastAPI app on the VPS reads from journald + SQLite and renders a single-page dashboard.

Trade-offs:

- + Pretty.
- − Yet another daemon.
- − Yet another auth surface (the dashboard needs to be locked down to the Founder).
- − Replicates `dev-assist-cli status` with worse latency (HTTP vs CLI) and a permanent maintenance burden.

Rejected: `dev-assist-cli status` covers the use case at zero daemon cost.

## Decision Criteria And Mapping

| Criterion | A (on-VPS, CHOSEN) | B (Prom+Grafana) | C (Datadog/Honeycomb) | D (Loki) | E (OTel hosted) | F (flat files) | G (custom dashboard) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Paid third-party | None | None | Yes | None | Yes | None | None |
| Extra daemons beyond Hermes×5+OmniRoute | 0 | 3 | 0 (or 1 collector) | 3 | 1+ | 0 | 1 |
| Cross-runtime correlation | Yes (work_item_id) | Yes (with config) | Yes | Yes | Yes (native) | Manual | Yes |
| Survives runtime crash | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Founder ergonomics | dev-assist-cli + Telegram | Grafana | Web dashboard | Grafana | Web dashboard | grep | Web dashboard |
| Compatible with `ADDENDUM-001` § 2.1 | Yes | No (extra daemons) | No (paid) | No (extra daemons) | No (paid + extra daemons) | No (loses journald) | No (extra daemon) |
| Compatible with PRD § 13.1 (autonomy + budget) | Yes | At risk | At risk | At risk | At risk | Yes | Yes |
| Implementation cost | Low | Medium-high | Medium | Medium | Medium-high | Low (but lossy) | Medium |
| Learning cost for Founder | Low (CLI + Telegram) | High (Grafana) | Medium-high (vendor SaaS) | High | High | Low | Medium |
| Long-term trend retention | Aggregated (llm_calls_daily) | Native | Native | Logs only | Native | Manual | Custom |

Option A wins by carrying every constraint, especially the binding `ADDENDUM-001` § 2.1 "no paid services + no extra daemons" rule. Trend-retention and ergonomics gaps are mitigated rather than fully eliminated, and `OBSERVABILITY-CONTRACT.md` § 14 captures escape hatches for v0.2+.

## Consequences

- **`OBSERVABILITY-CONTRACT.md`** is the operational specification; this ADR is the rationale.
- **`SELF-DEPLOYMENT-CONTRACT.md` § 5** picks up new responsibilities: install logrotate config, configure journald (`SystemMaxUse=1G`, `MaxRetentionSec=30d`, `MaxFileSec=1d`), bind ports 8181..8185 to `127.0.0.1` only, install `dev-assist-cli` to `/opt/dev-assist/bin/`, install the system-cron entries for retention and aggregate writes, install the Hermes-cron entry for the daily digest.
- **`OPERATIONAL-STATE-STORE.md` § 3** picks up two new tables: `errors`, `llm_calls`, plus the `llm_calls_daily` aggregate.
- **`MULTI-HERMES-CONTRACT.md` § 6.2 / § 7.3** pick up the `work_item_id` propagation discipline (every dequeue sets logger context; sub-tasks inherit; new work items get fresh ids).
- **`ESCALATION-POLICY.md` § 4.6** does NOT change; this ADR is about observability, not escalation rules. But escalation events written to `escalations` are now also visible via `dev-assist-cli` and the daily digest.
- **`RECOVERY-PLAYBOOK.md`** (new) is the Founder-facing runbook integrating the CLI, the health endpoints, and the journalctl/SQLite tooling into recovery actions.
- **No `metrics`-style exporter is added in v0.1.** Specialist runtimes do NOT expose Prometheus `/metrics`. If a v0.2 decision adds Prometheus, this ADR is superseded.
- **No third-party SDK is imported into specialist runtimes for observability.** No `sentry-sdk`, no `datadog`, no `honeycomb-beeline`, no `prom-client`. The runtime's only logging dependency is whatever Hermes Agent's built-in logger uses.
- **Escape hatches for v0.2+** (recorded in `ARCH-001.md` § 21 "Future Possibilities"): the JSON-line log format is structured enough that a future Loki / Honeycomb / Datadog ingestion is purely additive — emit the same lines, plus ship them to the new backend. The `errors` and `llm_calls` SQLite schemas can be dumped to Parquet for OLAP analysis without changes to runtime code.

## Cross-References

- `PRD-001.md` v0.2.1 § 13.1 (autonomy + budget envelope)
- `ADDENDUM-001` § 2.1 (Founder directive: on-VPS only, no paid services, no extra daemons)
- `ARCH-001.md` v0.3.0 § 23 (observability summary), § 21 (future possibilities)
- `OBSERVABILITY-CONTRACT.md` (operational specification of FR-OBS-01..10)
- `OPERATIONAL-STATE-STORE.md` § 3 (`errors` + `llm_calls` schemas)
- `SELF-DEPLOYMENT-CONTRACT.md` § 5.2 (systemd units), § 5.3 (`dev-assist-cli`), § 7 (firewall for 8181..8185)
- `MULTI-HERMES-CONTRACT.md` § 6.2 (`work_items` table), § 7.3 (dequeue path), § 9.4 (heartbeat cadence)
- `ESCALATION-POLICY.md` (no behavior change; observability surface gains visibility)
- `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 5.4 (on-VPS observability prior art), § 6.7 (Hermes logger conventions)
- `docs/operations/RECOVERY-PLAYBOOK.md` (FR-OBS-10 integration target)
- ADR-002 (SQLite as operational store)
- ADR-005, ADR-006 (multi-Hermes + IPC; this ADR rides on top)
- ADR-011 (routing layer; `routing_path` enum source for `llm_calls`)
- Implementation: TKT-027..031 (CLI, structured logging, daily digest, recovery playbook, errors+llm_calls+health)
