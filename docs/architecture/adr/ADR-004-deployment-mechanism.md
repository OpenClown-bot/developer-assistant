---
id: ADR-004
version: 0.1.0
status: draft
---

# ADR-004: Self-Deployment Mechanism — systemd + idempotent bash bootstrap

## Status

Draft, pending Founder approval. Supersedes none.

## Context

`PRD-001.md` v0.2.1 § 12 mandates that the assistant deploy itself onto a Founder-owned Ubuntu 22.04 LTS VPS through one command, with health verification, rollback, and three approval gates (`install`, `start`, `upgrade`). `ARCH-001.md` v0.3.0 § 14 sets the architectural shape; this ADR records the mechanism choice.

The mechanism must:

- Supervise five separate Hermes runtimes (`MULTI-HERMES-CONTRACT.md` § 2) each with auto-restart on failure.
- Be idempotent: re-runnable on an already-installed VPS without duplicating runtime processes or corrupting the operational state store (`PRD-001.md` § 9).
- Avoid paid third-party hard dependencies for v0.1 (`PRD-001.md` § 13.1; `ESCALATION-POLICY.md` § 4.6).
- Be inspectable and rollbackable by the Founder using standard Linux tooling.
- Keep the runtime sandbox surface (Docker terminal backend for Executor and Reviewer) intact.
- Preserve per-runtime memory and self-learning state across rollback and upgrade (`PRD-001.md` § 13.2).

## Decision

Deploy `developer-assistant` using **systemd** as the runtime supervisor, driven by an **idempotent bash bootstrap script** (`scripts/install-self.sh`) that lays down the filesystem layout, installs Hermes Agent once, configures five per-runtime `HERMES_HOME` directories, renders systemd unit files, runs preflight checks, and stops without starting any runtime. Three sibling scripts (`verify-self.sh`, `rollback-self.sh`, `upgrade-self.sh`) cover health verification, rollback, and upgrade.

The Executor and Reviewer runtimes use Docker for their `terminal` skill backend (sandboxed shell), but the supervisor of the runtimes themselves is systemd, not Docker Compose. Docker is a tool the runtimes call into; it is not the supervisor.

## Considered Options

### Option A — systemd + idempotent bash bootstrap (CHOSEN)

How it works: one bash script writes the filesystem layout, installs Hermes Agent at `/usr/local/lib/hermes-agent/` (idempotent: skips if already pinned), creates per-runtime `HERMES_HOME` directories, renders six systemd unit files (one umbrella `devassist.target` plus five `devassist-<role>.service`), runs `systemctl daemon-reload`, runs preflight checks via `verify-self.sh`, and exits without starting anything. Founder runs `systemctl start devassist.target` to start. Hermes' Docker terminal backend is configured per-runtime for Executor and Reviewer.

Trade-offs:

- + No new abstraction beyond what Ubuntu 22.04 already ships. systemd is universally available, well-understood, and Founder-inspectable via `systemctl`/`journalctl`.
- + Per-runtime resource limits, restart policies, and sandbox flags are first-class systemd primitives (`MemoryMax=`, `Restart=on-failure`, `NoNewPrivileges=`, `ProtectHome=`, `ProtectSystem=`, etc.).
- + Idempotent: re-run the install script and it skips already-applied steps (Hermes already at pinned version, layout already created, units already up-to-date by hash).
- + Rollback-friendly: stopping a unit is `systemctl stop`; restoring state is restoring `state.db` from a backup; restoring config is flipping a `releases/current` symlink.
- + No paid third-party dependency.
- + Consistent with Ubuntu's expected operating model: a system administrator can use `systemctl status devassist.target` and immediately understand the system.
- − Tied to systemd-using Linux. Not portable to FreeBSD, Alpine without OpenRC, or non-Linux platforms. v0.1 does not target these.
- − Requires writing per-runtime systemd units; the install script must render them. Mitigated: only ~30 lines per unit and they share a template.
- − If a future runtime needs to be added, the install script and a unit file must both be updated. Mitigated: that's the natural shape of the change anyway.

### Option B — Docker Compose

How it works: a single `docker-compose.yml` defines six services (one per runtime + an optional supervisor). Each service is a container running one Hermes runtime. `docker compose up` starts everything. State volumes mount `/srv/devassist/runtimes/<role>/.hermes/` per service.

Trade-offs:

- + Process isolation between runtimes is tighter (separate container namespaces, separate cgroups).
- + Familiar to many developers; "docker compose up" is a recognizable verb.
- + Easier to define resource limits per service in one file.
- − Requires Docker-in-Docker for the Executor and Reviewer runtimes' `terminal` skill backend, OR exposing the host Docker socket to those containers. Both options are operationally awkward and have security implications.
- − Adds Docker as a hard supervisor dependency on the VPS (Docker is already a hard dependency for the terminal sandbox; using it as supervisor doubles down).
- − Hermes Agent reads `HERMES_HOME` and writes there continuously. Mounting `HERMES_HOME` as a Docker volume means lots of writes through the Docker storage driver, which is fine but adds a layer of debugging when something goes wrong.
- − systemd-style resource controls (`MemoryMax=`, `OOMScoreAdjust=`) require Docker-specific equivalents in `docker-compose.yml`; the Founder must be familiar with Docker semantics rather than systemd semantics.
- − Less Founder-friendly for inspection: `docker compose logs <service>` works but requires `docker` privilege; `journalctl` does not.
- − More moving parts: Docker daemon health, the compose stack, the network bridge, etc. all add failure modes.

### Option C — Single-container Hermes installation with s6-overlay

How it works: one Docker container, one filesystem, with s6-overlay (or supervisord) running five separate `hermes gateway run` processes, one per role. Memory isolation is via separate `HERMES_HOME` directories inside the container.

Trade-offs:

- + Smallest deployment surface from the Founder's view: one container.
- + Simpler upgrade story: pull a new image, restart the container.
- − Memory isolation is weaker: all five processes share the container's filesystem and Linux uid; per-runtime sandboxing through systemd primitives is unavailable.
- − Per-process restart inside s6/supervisord is supported but per-process resource limits are less mature than systemd's.
- − The Docker terminal sandbox for Executor and Reviewer would need Docker-in-Docker inside this single container; nesting overhead is real.
- − The Hermes installation is replicated five times inside the container (per `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3.2 finding that one Hermes process means one install). The disk savings are negligible; the operational complexity is added without benefit.
- − Founder cannot use `systemctl` to inspect individual roles; must use `s6-svstat` or equivalent.

### Option D — Kubernetes

How it works: a small k3s or k0s cluster on the VPS, with five Deployments and an umbrella service.

Trade-offs:

- − Massive overhead for one VPS. The control-plane resources alone consume ~500 MB RAM, leaving less for the runtimes.
- − Docker-in-Docker for the terminal sandbox becomes containerd-in-Kubernetes-pod, which is even more awkward.
- − Founder must operate Kubernetes to debug.
- − No upside that systemd does not already provide on a single VPS.

Rejected outright.

### Option E — Nix-based deployment

How it works: a Nix flake describes the entire VPS state; `nix-rebuild switch` brings the VPS to that state.

Trade-offs:

- + Strongest determinism and rollback story (Nix generations).
- − Founder must learn Nix.
- − Nix on Ubuntu requires either NixOS (different distro) or non-trivial Nix-on-Ubuntu setup.
- − Build times can be long.
- − Hermes Agent is not yet packaged as a Nix derivation; would require maintaining one.

Rejected: the operational complexity exceeds the determinism benefit at v0.1 scale.

## Decision Criteria And Mapping

| Criterion | Option A (systemd + bash) | Option B (Docker Compose) | Option C (s6/single-container) | Option D (Kubernetes) | Option E (Nix) |
| --- | --- | --- | --- | --- | --- |
| Idempotent re-install | Yes (script-level) | Yes (compose) | Yes (image rebuild) | Yes (apply) | Yes (Nix) |
| Per-runtime memory isolation | Strong (systemd Protect*) | Strongest (containers) | Weakest (shared FS) | Strong (pods) | Strong |
| Founder inspectability | systemctl, journalctl | docker, docker compose | s6-svstat | kubectl | nix log |
| Tooling already on Ubuntu 22.04 | Yes | Yes (apt install docker.io) | No | No | No |
| Docker-in-Docker for terminal sandbox | No (host docker) | Yes (DinD or socket mount) | Yes (DinD) | Yes (DinD) | Depends |
| Paid third-party dependency | No | No | No | No | No |
| Operational complexity | Low | Medium | Medium-Low | Very High | High (learning curve) |
| Rollback ergonomics | Excellent (script) | Good (compose down/up) | Good (image swap) | Good (deployment rollback) | Excellent (Nix generation) |

Option A scores best on the operational-complexity / Founder-inspectability axes while matching the others on isolation, idempotence, and rollback.

## Consequences

- Implementation in TKT-020 produces four shell scripts and six systemd unit files.
- The terminal sandbox for Executor and Reviewer uses the host Docker socket via the `docker` group; the runtimes' systemd units carry `SupplementaryGroups=docker`.
- Adding a sixth runtime in v0.2+ requires editing the install script (one line for the new role) and adding a new systemd unit file. The change is small.
- If the VPS does not run systemd (e.g., a future Alpine deployment), this ADR is revisited.
- The decision does not preclude wrapping the v0.1 deployment in Docker Compose later if a packaging benefit emerges (e.g., a one-shot demo deployment); systemd remains the v0.1 primary mechanism.

## Cross-References

- `PRD-001.md` v0.2.1 § 9, § 12, § 12.5
- `ARCH-001.md` v0.3.0 § 14
- `SELF-DEPLOYMENT-CONTRACT.md` (full contract)
- `MULTI-HERMES-CONTRACT.md` (per-runtime layout)
- `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3.2, § 5.2, § 6.6
- ADR-001 (platform foundation)
- Implementation: TKT-020
