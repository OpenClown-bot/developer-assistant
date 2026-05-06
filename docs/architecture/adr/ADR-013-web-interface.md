---
id: ADR-013
version: 0.1.0
status: draft
---

# ADR-013: Lightweight Web Interface — Read-only Status Surface Served By `dev-assist-cli`

## Status

Draft, pending Founder approval. Closes the `PRD-001.md` v0.2.1 § 6 web-interface gap surfaced as RV-SPEC-014 C-002 against PR-E. Related: ADR-010 (observability shape), ADR-011 (routing layer), `OBSERVABILITY-CONTRACT.md`, `SELF-DEPLOYMENT-CONTRACT.md` v0.2.0.

## Context

`PRD-001.md` v0.2.1 § 6 contains a hard product requirement:

> The system must provide a founder-facing conversational interface through Telegram and a lightweight web interface.

Through PRs A-E the architecture stack covered Telegram (the Orchestrator runtime's `telegram-gateway` skill plus `dev-assist-classifier` and `dev-assist-escalation-surface`), but the **web interface** half of the FR-006 pair was not addressed. The first PR-E pass landed observability (`OBSERVABILITY-CONTRACT.md`, `OPERATIONAL-STATE-STORE.md` v0.3.0, ADR-010, ADR-011, TKT-027..031), but those artifacts only describe the operator CLI (`dev-assist-cli`), the Telegram `/status` digest, and the per-runtime localhost-only `GET /health` endpoints (ports 8181..8185). None of those is a "founder-facing web interface" the Founder can open in a browser.

`PRD-001.md` v0.2.1 § 10 Q2 explicitly leaves the v0.1 web-interface scope **open**:

> What should the lightweight web interface include in v0.1 beyond chat and project status?

`SESSION-STATE.md` § Current Architectural Decisions records: *"Lightweight web interface is deferred until Telegram works."* That deferral was acceptable while the PRD § 6 mandate remained "future-tense"; once the PRD codified it as a v0.1 functional requirement, the architecture has to either commit or escalate. ADDENDUM-001 (Founder, 2026-05-06) did not explicitly waive § 6's web-interface clause; the architect interpreted the addendum as additive (observability + routing) rather than as a § 6 deferral.

This ADR closes the gap by committing to the **smallest surface that satisfies § 6 without expanding the v0.1 budget envelope or violating the `ADDENDUM-001` § 2.1 "no extra daemons / no paid services" constraint** that ADR-010 also carries.

## Decision

Adopt **a single read-only HTTP status surface** served by `dev-assist-cli`, bound to `127.0.0.1:8180` and (optionally) reachable through the VPS firewall on a Founder-allowlisted host. The surface satisfies `PRD-001.md` § 6 by giving the Founder a single browser-loadable page that mirrors the data already exposed by `dev-assist-cli status --format human`, the per-runtime `GET /health` endpoints, and the daily Telegram digest — without introducing a new daemon, new framework, new auth surface, or new database.

Concretely:

1. **One endpoint, one process**: a thin HTTP server inside `dev-assist-cli` (mode: `dev-assist-cli serve-web --port 8180`) using Python's standard-library `http.server` (or `aiohttp` if the runtime already pulls it via Hermes; coordinate with TKT-027). The same binary that powers the operator CLI also serves the web surface; there is no second installable.
2. **Read-only**: the surface issues no writes to `operational.db`, no escalation rows, no work-queue items, and no model calls. It reads journald via `journalctl --output=json` and SQLite directly, exactly as `dev-assist-cli status` does.
3. **Static-by-shape responses**: each request is a fresh server-side render. No JS framework, no client-side state, no WebSocket, no streaming. Auto-refresh is achieved via a stock `<meta http-equiv="refresh" content="30">` tag if and only if the Founder navigates to the auto-refresh path; the default path is single-shot.
4. **Two response formats**: `Accept: text/html` returns an HTML status page; `Accept: application/json` (or `?format=json`) returns the same shape `dev-assist-cli status --format json` returns. The HTML view is cosmetic glue around the JSON response; both views read the same backing function so they cannot diverge.
5. **No auth at the application layer**: authentication is defense-in-depth via the VPS firewall plus localhost binding (see § Port Assignment And Network Posture below). The application does not maintain a session, does not store cookies, does not implement password or token auth, and does not depend on the Telegram bot token. This is the same posture the `dev-assist-cli` already takes for the local operator surface.
6. **Lifecycle is a separate systemd unit**: `devassist-web.service` (added in `SELF-DEPLOYMENT-CONTRACT.md` v0.2.0 § 5.4). The unit runs `/opt/dev-assist/bin/dev-assist-cli serve-web --port 8180` as the `devassist` user, with the same systemd sandboxing template the specialist runtimes use (`NoNewPrivileges=true`, `ProtectSystem=full`, `ProtectHome=true`, `PrivateTmp=true`, `ReadOnlyPaths=/srv/devassist`, `ReadWritePaths=/srv/devassist/logs`).

### What the surface renders

The surface renders the status snapshot already produced by `dev-assist-cli status` (defined in TKT-027): one page, several sections.

| Section | Source | Read pattern |
| --- | --- | --- |
| Phase / blockers / next action | `docs/orchestration/SESSION-STATE.md` parsed at request time | File read (`/srv/devassist/repo/docs/orchestration/SESSION-STATE.md`) |
| Per-runtime health | All five `GET /health` endpoints (8181..8185) called in parallel with a 500 ms timeout each | Localhost HTTP fan-out |
| Queue depth and last activity | `operational.db` `work_items` and `errors` tables | SQLite read |
| Last 10 LLM calls (per runtime) | `operational.db` `llm_calls` table | SQLite read |
| Pending escalations summary | `operational.db` `escalations` table (only count + earliest-pending-timestamp; full content stays Telegram-only) | SQLite read |
| Today's digest | `operational.db` `llm_calls_daily` rolled up for the current UTC day | SQLite read |
| Recent journald lines | `journalctl --output=json --since="-15 minutes" --unit="devassist-*"` (last 50 lines) | Subprocess read |

Pending-escalation **content** is intentionally kept out of the web surface; only the count and oldest pending timestamp appear. Full escalation rows are Telegram-only (`ESCALATION-POLICY.md` § 7) so a Founder loses no governance fidelity by reading the web surface, and an attacker who reaches port 8180 cannot read the full escalation prompts.

### Port Assignment And Network Posture

- **Port 8180** is reserved for `devassist-web.service`. This is one less than the dev-assist-cli health-port range (8181..8185) so the web surface and per-runtime health endpoints sit on the same /24 of the localhost port space, easing firewall and Founder mental-model consistency.
- The unit binds **localhost only** (`127.0.0.1:8180`) by default. Browser access from outside the VPS requires either an SSH tunnel (`ssh -L 8180:127.0.0.1:8180 founder@vps`) or an explicit `ufw` rule the Founder adds after the install step. Neither is automated by the install script.
- This assignment does NOT collide with: OmniRoute on `127.0.0.1:20128` (`ADR-011-routing-layer.md`), Hermes Telegram polling (outbound-only; no listener; `HERMES-SKILL-ALLOWLIST.md` § 4.1), per-runtime health endpoints `127.0.0.1:8181..8185` (`OBSERVABILITY-CONTRACT.md` § 11), SSH on `:22`, the Founder's own services on the VPS.
- Future port allocations stay under `127.0.0.1:8180..8189`; values outside that range trip the deterministic `net:public_endpoint_exposure` rule (`ESCALATION-POLICY.md` § 4.5) and require Founder approval.

## Considered Options

### Option A — Build a new SPA dashboard with a backend API (REJECTED)

How it works: Vite/React frontend, FastAPI backend, a new `dashboard.service` systemd unit, websocket push for live updates.

Trade-offs:

- + Best Founder ergonomics for a v1.0+ product.
- − Two new daemons (frontend dev server + backend API) at v0.1 scale = same disk-pressure / memory-pressure / config-overhead concerns ADR-010 Option B already enumerated.
- − A new auth surface that is non-trivial to lock down for a single-Founder system.
- − Replicates `dev-assist-cli` data with a slow path (HTTP fan-out plus DB query plus React render) where the CLI already does it in one process.
- − Substantial implementation cost competing with the v0.1 trial budget.

Rejected: violates `ADDENDUM-001` § 2.1's "no extra daemons" rule by the same logic that rejected Prometheus + Grafana in ADR-010.

### Option B — Defer the web interface entirely (REJECTED)

How it works: keep `SESSION-STATE.md` § Current Architectural Decisions's *"Lightweight web interface is deferred until Telegram works"* as the official posture; document that PRD § 6 is partially unmet in v0.1.

Trade-offs:

- + Zero implementation cost.
- + Architecture stays simple.
- − Leaves a hard PRD requirement (`PRD-001.md` § 6 "must provide … a lightweight web interface") unaddressed.
- − Forces the Founder to either accept a § 6 waiver or block PR-E on a § 6 fix anyway.

Rejected: § 6 is a `must` requirement; closing the gap with the smallest possible surface (Option C) is cheaper than a § 6 PRD revision.

### Option C — Read-only `dev-assist-cli` HTTP surface (CHOSEN)

How it works: as in the Decision section.

Trade-offs:

- + Smallest possible scope: zero new daemons beyond the systemd unit wrapper around an existing binary; zero new dependencies; zero auth surface; one read-path.
- + Reuses `dev-assist-cli status`'s status-snapshot logic; the HTML view cannot diverge from the CLI / digest because both consume the same backing function.
- + Compatible with `ADDENDUM-001` § 2.1 ("no paid services + no extra daemons beyond the six already approved" — the seventh unit `devassist-web.service` is a thin wrapper, not a new daemon class).
- + Read-only = trivially low security surface; the application has no write paths to compromise.
- + Founder can reach it via a one-line `ssh -L` tunnel without any pre-shared secrets.
- − Browser-side ergonomics are basic (no live updates without a refresh; no fancy charts). Mitigated: the Founder is the only operator at v0.1 scale and already gets daily digests via Telegram.
- − Per-request latency is slightly higher than `dev-assist-cli status` invocation (HTTP overhead + journalctl subprocess fan-out) — a few hundred ms typical. Acceptable.

Chosen: this is the only option that satisfies PRD § 6 *and* `ADDENDUM-001` § 2.1.

### Option D — A fixed HTML file regenerated by cron (REJECTED)

How it works: a cron job runs `dev-assist-cli status --format html > /var/www/devassist/index.html` every 5 minutes; nginx serves the file.

Trade-offs:

- + Web server is stock nginx; no custom server code.
- − Adds nginx as a daemon (already disqualified by `ADDENDUM-001` § 2.1 logic).
- − File has stale data between cron ticks; the Founder cannot get a fresh status without waiting for the next tick.
- − Requires nginx config that hardens to the same security posture Option C achieves with zero config.

Rejected: Option C is strictly simpler.

## Decision Criteria And Mapping

| Criterion | A (SPA dashboard) | B (defer) | C (cli HTTP, CHOSEN) | D (cron-rendered HTML) |
| --- | --- | --- | --- | --- |
| Satisfies `PRD-001.md` § 6 | Yes (overshoots) | No | Yes | Yes (stale) |
| Extra daemons beyond Hermes×5+omniroute+web | 2 | 0 | 0 | 1 (nginx) |
| New auth surface | Yes | None | None | None |
| Compatible with `ADDENDUM-001` § 2.1 | No | Yes | Yes | No |
| Implementation cost | High | None | Low | Medium |
| Read-only | No | n/a | Yes | Yes |
| Founder ergonomics | Best (with cost) | Worst | Acceptable | Acceptable-stale |
| Cross-runtime data | Yes | n/a | Yes | Yes |
| Live data | Yes | n/a | Yes (per request) | No |

Option C is the only column that carries every constraint simultaneously.

## Consequences

- **`ARCH-001.md` v0.3.0 § 24** captures the architectural shape (this ADR is the rationale).
- **`SELF-DEPLOYMENT-CONTRACT.md` v0.2.0 § 5.4** adds `devassist-web.service` to the systemd unit set (now seven units: `devassist.target`, five specialist runtimes, `omniroute.service`, `devassist-web.service`). The install script renders the unit; the start gate covers it; verify checks reachability of `http://127.0.0.1:8180/health`.
- **`SELF-DEPLOYMENT-CONTRACT.md` v0.2.0 § 4** filesystem layout adds `/opt/dev-assist/bin/dev-assist-cli` (laid down by the install script per ADR-010's existing dev-assist-cli responsibility) and `/srv/devassist/web/templates/` for the HTML templates packaged with `dev-assist-cli`.
- **`SELF-DEPLOYMENT-CONTRACT.md` v0.2.0 § 8** adds an eighth verify invariant: `curl -fs http://127.0.0.1:8180/health` returns `200 OK` with body `{"role":"web","ok":true}`. Failure is a non-zero verify exit.
- **`OBSERVABILITY-CONTRACT.md`** is unchanged in shape but gains the web surface as a third Founder-facing observability channel (CLI / Telegram digest / web). FR-OBS-08 (per-runtime health endpoints) is consumed by, not duplicated by, this ADR.
- **`ESCALATION-POLICY.md`** is unchanged in shape; the deterministic rule `net:public_endpoint_exposure` (`ESCALATION-POLICY.md` § 4.5) still fires if a future change tries to bind the web surface to `0.0.0.0` or expose port 8180 externally without Founder approval.
- **No new database, no new schema migration**: the surface reads existing tables (`work_items`, `escalations`, `errors`, `llm_calls`, `llm_calls_daily`) and existing repository artifacts (`SESSION-STATE.md`).
- **No new model calls**: the surface never invokes a model and never records to the `llm_calls` table.
- **TKT-027 (CLI) absorbs the implementation** rather than introducing a new TKT-032: the web surface is a `serve-web` subcommand of the same `dev-assist-cli` binary TKT-027 already specifies. TKT-027's allowed-files list is extended in PR-E (this ADR) to include `src/developer_assistant/cli/web_server.py` and `src/developer_assistant/cli/templates/status.html`. No separate ticket is required because the web surface adds <300 lines of stdlib HTTP code on top of TKT-027's existing data-collection helpers.
- **`SESSION-STATE.md` § Current Architectural Decisions** is updated to record that the web interface is now in scope for v0.1 (no longer "deferred until Telegram works") and that it is read-only.
- **Future possibilities** (recorded in `ARCH-001.md` § 21): if a v0.2 decision adds Founder-facing controls (e.g., a "pause autonomy" toggle), this ADR is superseded; the v0.2 ADR documents the auth model, write path, and CSRF posture for the new write surface. v0.1 commits to read-only.
- **No third-party SDK is imported** by the web surface. The runtime's only dependency is whatever Python stdlib (`http.server`, `sqlite3`, `subprocess`, `jinja2` if available, otherwise `string.Template`) plus the existing `dev-assist-cli` data-collection helpers.

## Cross-References

- `PRD-001.md` v0.2.1 § 6 (functional requirement: lightweight web interface), § 10 Q2 (open scope question; closed by this ADR), § 13.1 (autonomy + escalation envelope)
- `ADDENDUM-001` § 2.1 (Founder directive: on-VPS only, no paid services, no extra daemons — preserved by Option C)
- `ARCH-001.md` v0.3.0 § 23 (observability summary), § 24 (web interface architecture summary)
- `OBSERVABILITY-CONTRACT.md` v0.1.1 (CLI, health endpoints, llm_calls, errors — read by the web surface)
- `SELF-DEPLOYMENT-CONTRACT.md` v0.2.0 § 4 (filesystem layout), § 5.4 (`devassist-web.service` unit), § 8 (verify invariant set)
- `ESCALATION-POLICY.md` v0.1.1 § 4.5 (`net:public_endpoint_exposure` deterministic rule)
- `MULTI-HERMES-CONTRACT.md` (per-runtime health endpoints aggregated by the web surface)
- `OPERATIONAL-STATE-STORE.md` v0.3.0 (tables read by the web surface)
- ADR-010 (observability shape; this ADR rides on top of the dev-assist-cli surface ADR-010 already chose)
- ADR-011 (routing layer; OmniRoute port 20128 listed in port-allocation table)
- `docs/orchestration/SESSION-STATE.md` § Current Architectural Decisions (updated to reflect v0.1 web-interface commitment)
- Implementation: TKT-027 (CLI; the web server is a `serve-web` subcommand)
- RV-SPEC-014 C-002 (the review finding that motivated this ADR)
