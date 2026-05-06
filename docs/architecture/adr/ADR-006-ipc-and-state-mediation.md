---
id: ADR-006
version: 0.1.0
status: draft
---

# ADR-006: Inter-Runtime IPC And State Mediation — SQLite-mediated work queue

## Status

Draft, pending Founder approval. Supersedes none. Related: ADR-005 (multi-Hermes runtime isolation), ADR-002 (repository state).

## Context

The five specialist Hermes runtimes (`MULTI-HERMES-CONTRACT.md` § 2) must coordinate work without violating per-runtime memory isolation (`PRD-001.md` § 13.2). The Orchestrator runtime dispatches work to specialists; specialists deliver results back to the Orchestrator; specialists may pause work waiting on a Founder escalation; expired claims must be reclaimable by another runtime.

`ARCH-001.md` v0.3.0 § 11.2 requires a concrete IPC mechanism and `MULTI-HERMES-CONTRACT.md` § 6 sketches the work-queue and escalation tables. This ADR records why those tables (in the existing SQLite operational store) are the IPC mechanism, and why other candidates were rejected.

## Decision

Use the existing SQLite operational store (`OPERATIONAL-STATE-STORE.md` v0.2.0) as the inter-runtime IPC substrate. Add two tables: `work_items` (the work queue) and `escalations` (the Founder-prompt queue). Both tables are accessed by all five runtimes through their per-runtime symlink to `/srv/devassist/state/state.db` and through the shared `dev-assist-work-queue` Hermes plugin.

Inter-runtime "messages" are durable rows in these tables. There is no in-memory message bus, no network IPC, no separate broker process. The lease semantics on `work_items` (`MULTI-HERMES-CONTRACT.md` § 6.2) provide visibility timeout; periodic polling on `cronjob` (every 60 seconds for specialist runtimes; every 5 seconds for the lease-reclaim sweep) provides delivery.

## Considered Options

### Option A — SQLite-mediated work queue in the existing operational store (CHOSEN)

How it works: as in the Decision section. `work_items` and `escalations` are added by the existing migration mechanism (`OPERATIONAL-STATE-STORE.md` § 6). All five runtimes share the same `state.db` via a symlink. The `dev-assist-work-queue` plugin provides `claim`, `complete`, `release`, `write` tools that wrap atomic SQL operations.

Trade-offs:

- + Zero new infrastructure. No broker, no network port, no extra service.
- + ACID semantics on every operation: claim, complete, release, write are all single SQL statements with `RETURNING *`.
- + Durable by construction: work items survive runtime restart, VPS restart, and rollback (the same backup mechanism that protects `state.db` protects the queue).
- + Inspectable by the Founder: `sqlite3 /srv/devassist/state/state.db 'SELECT ...'` from any shell.
- + Backup-aligned: the same `state.db` backup snapshots that `SELF-DEPLOYMENT-CONTRACT.md` § 6.3 takes during upgrade also include the queue.
- + Idempotency-aligned: dedup keys live in `payload_json.dedup_key` and the existing `idempotency_keys` table semantics extend naturally.
- − Polling-based delivery has higher tail latency than push-based delivery. Mitigated: 60-second polling interval is acceptable for a multi-minute workflow (intake → planning → architecture → implementation each take minutes-to-hours, so 60s polling adds <2% to wall clock).
- − SQLite has writer-serialization. With ~5 runtimes writing infrequently this is a non-issue, but a high-frequency workload would saturate. Mitigated: WAL mode + small write rate; not a v0.1 concern.
- − Cross-host distribution requires copying the database, not connecting to a remote endpoint. v0.1 is single-VPS; this is fine.

### Option B — A2A protocol over HTTP (between specialist runtimes)

How it works: each specialist runtime exposes an A2A-compliant HTTP server. The Orchestrator (or any runtime) calls into another runtime's A2A endpoint to dispatch tasks. Discovery is via published Agent Cards.

Trade-offs:

- + Standardized: A2A v1.0.0 is an open protocol with vendor adoption (`https://a2a-protocol.org/`).
- + Fits the v0.2 OpenClaw upstream story naturally; A2A is also what an external OpenClaw peer would speak.
- + Push-based delivery: lower latency than polling.
- − Five HTTP servers on one VPS; each runtime needs a port, TLS, and reverse-proxy routing. Adds operational surface.
- − Inbound HTTP between runtimes on the same VPS is over `localhost`, but every runtime now has an inbound listener — increases attack surface for a benefit of dubious size.
- − Durability: A2A messages are not natively durable. Either the runtime persists them on receipt (so the database is back in the picture as a durable layer) or messages are lost on restart. Adding durable persistence on top of A2A means doing both A2A and a queue table, doubling the surface.
- − Implementation cost: each runtime grows an HTTP server, an A2A handler, an A2A client. Custom code burden grows.
- − v0.2's external A2A boundary (Orchestrator ↔ external OpenClaw) is a separate decision (`UPSTREAM-ADAPTER-CONTRACT.md` § 8); using A2A internally on top of that is symmetric but adds churn.

Rejected for v0.1: solves the Orchestrator-to-external-peer problem (which doesn't exist yet) at the expense of a problem the SQLite queue already solves.

### Option C — Redis or NATS message broker

How it works: install a Redis (pub/sub or streams) or NATS broker on the VPS; runtimes publish/subscribe through it.

Trade-offs:

- + Push-based delivery; near-zero latency.
- + Mature broker code; well-tested at much higher loads than v0.1 needs.
- + NATS has durable streams (JetStream) that satisfy the durability concern.
- − One more service running on the VPS. NATS or Redis must be installed, configured, supervised, monitored, and backed up.
- − Backup story: now there are two state stores (SQLite + broker). Self-deployment rollback must coordinate both.
- − Operational overhead is real for v0.1's single-Founder workload, where there are <10 messages per active hour.
- − Founder cannot inspect a Redis/NATS state with a single SQL query the way SQLite allows.

Rejected: cost-of-broker exceeds benefit at v0.1 scale.

### Option D — MCP HTTP servers between runtimes

How it works: each runtime hosts an MCP HTTP server exposing role-specific tools (e.g., the Architect runtime exposes `produce_architecture(work_payload)`). Other runtimes call those tools.

Trade-offs:

- + Hermes natively supports calling MCP servers (`RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3.11).
- + Composes with the v0.2 OpenClaw story: OpenClaw can call the same MCP servers.
- − MCP is request/response, not queue-based. To make work durable, add a database; we're back to Option A plus extra HTTP overhead.
- − Five HTTP servers, same drawback as Option B.
- − Synchronous request/response model. The Architect's "produce architecture" call could take 10-60 minutes; the Orchestrator's HTTP request would have to either keep a connection open that long or poll a status endpoint, which is queue semantics on top of HTTP.

Rejected: HTTP RPC is the wrong shape for long-running work.

### Option E — Filesystem-based queue (one file per work item)

How it works: each work item is a JSON file in a shared directory; runtimes write/read/move files to claim and complete work.

Trade-offs:

- + Trivially inspectable.
- + No new dependencies.
- − No atomic claim primitive; rename-based atomic claim (`mv item.json claimed/<role>/`) works but requires careful handling of races.
- − No indexing; large queues become O(n) scans.
- − No transactional update of "work item completed" + "follow-up work item created" without filesystem-level locking.
- − Backup story is more complex (every file rather than one database).

Rejected: SQLite already provides everything filesystem-based queue would, with strict atomicity.

### Option F — In-process Python `asyncio.Queue` shared via the broker process

How it works: a Python broker process holds the queue in memory; runtimes connect to it. Variant: shared-memory queue.

Trade-offs:

- − Not durable across broker restart.
- − Adds a new process.
- − v0.1 has no need for in-process latency.

Rejected without further analysis.

## Decision Criteria And Mapping

| Criterion | Option A (SQLite queue) | Option B (A2A) | Option C (Redis/NATS) | Option D (MCP) | Option E (FS queue) |
| --- | --- | --- | --- | --- | --- |
| Durable by default | Yes | No (add DB) | Yes (Streams) | No (add DB) | Yes |
| New service required | No | No | Yes | No | No |
| Network port required | No | Yes (per runtime) | Yes (broker) | Yes (per runtime) | No |
| Atomic claim primitive | Yes (single SQL) | Manual | Yes | Manual | Manual (rename) |
| Inspection ergonomics | Excellent (SQL) | Tooling needed | CLI tools | Tooling needed | Excellent |
| Backup ergonomics | Excellent (single file) | Hard | Adds backup step | Hard | OK (many files) |
| Latency under v0.1 load | 60s polling, OK | Push (lowest) | Push (lowest) | Sync RPC | Polling |
| Complexity vs payoff | Best ratio | Worse | Worse | Worse | Worse |

Option A wins on every axis except tail latency, where the v0.1 load makes the difference irrelevant.

## Consequences

- The two new tables (`work_items`, `escalations`) ship via TKT-022 as a single migration.
- The `dev-assist-work-queue` plugin (TKT-023, sibling to `dev-assist-escalation-policy`) provides the runtime-facing tools.
- Polling intervals are configurable via per-runtime config; default 60 seconds for specialist polling, 5 seconds for the Orchestrator's escalation surface poll, 300 seconds for the lease-reclaim sweep.
- A future `delegate_task` adoption (currently BLOCKED per `HERMES-SKILL-ALLOWLIST.md` § 4.5) would not replace this queue; it would coexist as a fast-path for short-lived in-runtime delegations while the queue remains the durable cross-runtime substrate.
- A future v0.2 OpenClaw upstream (`UPSTREAM-ADAPTER-CONTRACT.md` § 8) would talk to the Orchestrator via MCP/A2A externally, but the internal cross-runtime substrate remains the SQLite queue. The Orchestrator translates between the two boundaries.
- If empirical load grows to a point where SQLite writer-serialization is the bottleneck, this ADR is revisited with measurements and an upgrade ADR proposed.

## Cross-References

- `PRD-001.md` v0.2.1 § 13.2 (multi-Hermes; cross-role flow without leaking memory)
- `ARCH-001.md` v0.3.0 § 11.2
- `MULTI-HERMES-CONTRACT.md` § 6 (table schemas), § 8 (coordination patterns)
- `OPERATIONAL-STATE-STORE.md` v0.2.0 (existing store)
- `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3.10, § 3.11, § 4, § 5.3, § 6.3
- ADR-002 (repository state), ADR-005 (multi-Hermes runtime isolation)
- Implementation: TKT-022 (queue schema + helpers)
