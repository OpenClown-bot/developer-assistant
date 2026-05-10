---
id: SANDBOX-CONTRACT
version: 0.1.0
status: draft
arch_ref: ARCH-002@0.1.0
adr_ref: ADR-015@0.1.0
updated: 2026-05-10
---

# Sandbox Capability Protocol — Boundary Contract

## 1. Purpose

This contract is the authoritative boundary specification between the Executor specialist runtime's Hermes `terminal` toolset and the concrete sandbox backend that runs build/test/lint/git commands on behalf of an in-flight work item. It is the dev-time companion to `MULTI-HERMES-CONTRACT.md` § 5.4 (Executor toolset baseline) and operationalizes the architectural shape decided in ADR-015 (Bernstein-style typed sandbox-capability protocol).

The contract exists so that v0.2+ backend additions (worktree, Modal, E2B) can land non-breakingly: the specialist runtime configuration stays the same shape, the work-queue dispatcher stays the same shape, and only the chosen `SandboxBackend` implementation switches. The protocol is intentionally thin (one enum, two abstract base classes, one helper function); the abstraction's cost is roughly one indirection, mitigated by the verbatim error-propagation guarantee in § 3.

This document does not include implementation source; the v0.1 module layout is `src/sandbox/protocol.py` (interfaces) plus `src/sandbox/docker.py` (concrete `DockerSandbox`). It also does not redefine concepts authoritative in upstream contracts: per-runtime memory isolation is in `MULTI-HERMES-CONTRACT.md` § 7, work-item lifecycle in § 6.2, escalation surfacing in § 6.3.

## 2. Backend interface

A sandbox backend is an instance of the `SandboxBackend` abstract base class. It declares its supported capabilities (§ 4) and exposes the create / resume / destroy session lifecycle. The interface is:

| Member | Type | Purpose |
| --- | --- | --- |
| `name` | `str` (property) | Stable backend identifier, e.g. `"docker"`. Used by log attribution and by the `dev-assist-escalation-surface` skill when surfacing a capability mismatch. |
| `capabilities` | `frozenset[SandboxCapability]` (property) | The capability subset this backend declares it supports. Compared by `negotiate_capabilities` (§ 5) against the work item's required-capability set. |
| `create(work_item_id: str) -> Session` | method | Create a fresh session bound to `work_item_id`. The work item id is recorded as a backend-side label (e.g. Docker container label) so external operators can correlate sessions to work items. |
| `resume(session_id: str) -> Session` | method | Re-attach to an existing session by opaque id. Used by the lease-reclaim sweep on lease expiration recovery (`MULTI-HERMES-CONTRACT.md` § 6.2). |
| `destroy(session_id: str) -> None` | method | Destroy a session by opaque id. Idempotent — calling on a missing session is a no-op, not an error. |

`SandboxBackend` is an ABC: instantiating it directly raises `TypeError`. Concrete implementations must override every abstract member; partial implementations remain abstract per Python's ABC machinery and `tests/test_sandbox.py` enforces this.

## 3. Session interface

A session represents an active sandbox bound to one work item. It is produced by `SandboxBackend.create` or re-attached by `SandboxBackend.resume`. The interface is:

| Member | Type | Purpose |
| --- | --- | --- |
| `session_id` | `str` (property) | Opaque session identifier (e.g. Docker container id). The caller treats it as a string token; the backend manages identity. |
| `read(path) -> bytes` | method | Read file contents from inside the sandbox. Bytes (not str-decoded) so binary build output passes through faithfully. |
| `write(path, content) -> None` | method | Write file contents into the sandbox. |
| `exec(cmd, env=None, timeout=None) -> ExecResult` | method | Execute `cmd` (a sequence of strings) inside the sandbox. Returns an `ExecResult` carrying `exit_code: int`, `stdout: bytes`, `stderr: bytes`. |
| `ls(path) -> Sequence[str]` | method | List directory entries under `path`. Errors propagate as `RuntimeError` carrying the underlying stderr verbatim. |
| `snapshot() -> str` | method | Capability-gated. Implementations whose backend does not declare `SandboxCapability.SNAPSHOT` raise `CapabilityNotAvailable`. |
| `shutdown() -> None` | method | Tear down the session. Idempotent. |

**Verbatim error propagation (load-bearing).** `Session.exec` MUST propagate non-zero exit codes, stderr content, and timeout exceptions from the underlying backend transport unchanged. The abstraction layer is forbidden from masking, rewriting, or swallowing backend errors that the Executor previously saw directly. This is the primary risk-mitigation guarantee from TKT-035 § 7. `tests/test_sandbox.py::DockerSandboxErrorPropagationTests` enforces this for `DockerSandbox`; future backends MUST add equivalent tests.

## 4. Capability enum

The `SandboxCapability` enum has exactly six values, frozen for v0.1 per ADR-015 § Decision point 1. Additions require an ADR amendment.

| Capability | Meaning |
| --- | --- |
| `FILE_RW` | Backend supports `Session.read` and `Session.write` against arbitrary paths inside the sandbox. |
| `EXEC` | Backend supports `Session.exec` with arbitrary commands. |
| `NETWORK` | Backend supports outbound network access from inside the sandbox (e.g. `pip install`, `git fetch`). |
| `GPU` | Backend supports GPU passthrough. Not declared by any v0.1 backend. |
| `SNAPSHOT` | Backend supports `Session.snapshot` returning a snapshot id usable for rollback. Not declared by any v0.1 backend. |
| `PERSISTENT_VOLUMES` | Backend supports volumes that survive `Session.shutdown` for cross-session continuity. Not declared by any v0.1 backend. |

Capabilities are declarative metadata about the backend's *abilities*, not toggles. A backend that declares `NETWORK` always exposes network access; capability negotiation (§ 5) is purely an admit/reject gate at dispatch time.

## 5. Negotiation algorithm

Capability negotiation is a pure function:

```
negotiate_capabilities(work_item, backend) -> Result
```

where `Result = Ok | Err(missing_capability)`.

Algorithm:

1. Read `work_item.required_capabilities` (the set of `SandboxCapability` values declared in the ticket frontmatter).
2. Read `backend.capabilities` (the set declared by the active backend).
3. For each required capability in iteration order:
   - If the capability is not in the backend's declared set, return `Err(missing_capability=<that capability>)`.
4. If all required capabilities are declared, return `Ok()`.

Per ADR-015 § Decision point 3 the work-queue dispatcher MUST refuse to dispatch the work item on `Err`. The dispatcher emits a `mail`-modality escalation per ADR-017 (since capability mismatch is a non-blocking informational signal — the operator either amends the ticket frontmatter or activates a backend supporting the capability). The corresponding observability failure mode is `sandbox_capability_unavailable` per ADR-015 § Consequences.

The function is pure (no I/O, no global state) so it is safe to call from any runtime, exercise transparently in unit tests, and short-circuit at any point in the dispatcher's loop without side-effect concerns.

## 6. v0.1 backend matrix

Exactly one concrete backend ships in v0.1.

| Backend | Module | Declared capabilities | Default image | Trigger to deprecate |
| --- | --- | --- | --- | --- |
| `DockerSandbox` | `src/sandbox/docker.py` | `{FILE_RW, EXEC, NETWORK}` | `python:3.12-slim` | None — DockerSandbox is the v0.1 baseline matching the deployed Hermes `terminal` Docker backend (ADR-014 § Correction 5). |

`DockerSandbox` dispatches all Docker operations through the `docker` Python SDK (`docker.from_env()`, `containers.run`, `containers.get`, `container.exec_run`, `container.put_archive`, `container.get_archive`). Per TKT-035 § 8 hard rule the implementation never falls back to `subprocess.run("docker exec ...")`. The SDK is the same one Hermes' built-in `terminal` toolset uses, so deploying `DockerSandbox` introduces no new pip dependency.

`DockerSandbox.snapshot` raises `CapabilityNotAvailable` because `SNAPSHOT` is not declared. Likewise any callsite invoking GPU- or persistent-volume-gated session methods on `DockerSandbox` would raise `CapabilityNotAvailable`; v0.1 has no such session methods (only `snapshot` is capability-gated in v0.1), so the negotiation gate at dispatch is the primary enforcement surface.

## 7. Future backends

The following backends are explicitly out of v0.1 scope. They are recorded here so the protocol shape remains stable when they land.

| Backend | Trigger condition | Likely capabilities | Reference |
| --- | --- | --- | --- |
| `WorktreeSandbox` | First explicit batch of parallel-ticket execution per `ARCH-002` § 10 Future Possibilities. Each work item gets its own git worktree to prevent cross-ticket interference. | `{FILE_RW, EXEC, PERSISTENT_VOLUMES}` (worktree state survives session teardown). | Gas Town worktree-vs-clone distinction; OpenCastle worktree-per-worker (`ARCH-002` § 3.6 Adopt list, deferred). |
| `ModalSandbox` | Generated project's build cannot fit local Docker (RAM, CPU, or time budget) — the Future Possibility named in `ARCH-001` § 21. | `{FILE_RW, EXEC, NETWORK, GPU}` (Modal natively supports GPU and large CPU/RAM). | RESEARCH-002 Bernstein survey § 6.3. |
| `E2BSandbox` | Same trigger as `ModalSandbox` plus operator preference for E2B's microVM-per-session model over Modal's container-per-call. | `{FILE_RW, EXEC, NETWORK, SNAPSHOT}` (E2B natively supports microVM snapshots). | RESEARCH-002 Bernstein survey § 6.3. |

When a new backend is added, the implementing ADR amends the v0.1 backend matrix in § 6 of this contract (or bumps the contract to v0.2.0 if the addition is large enough to warrant a version bump under `CONTRIBUTING.md` § Versioning rules), names the trigger condition, lists the declared capability set, and adds a corresponding row in the `MULTI-HERMES-CONTRACT.md` § 5.4 Executor toolset table. The work-queue dispatcher does not need to change shape — capability negotiation already routes the work item to the right backend.
