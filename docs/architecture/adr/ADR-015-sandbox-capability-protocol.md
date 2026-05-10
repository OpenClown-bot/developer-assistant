---
id: ADR-015
version: 0.1.0
status: proposed
---

# ADR-015: Sandbox Capability Protocol — Bernstein-style typed abstraction

## Status

**Proposed**, pending Founder approval as part of the ARCH-002 synthesis cycle. Supersedes none; coordinates with ADR-005 (multi-Hermes runtime isolation), ADR-014 § Correction 5 (Docker terminal backend in production), and `MULTI-HERMES-CONTRACT.md` v0.2.1 § 5.4 Executor toolset. Implements RESEARCH-002 § 9 Q-RESEARCH-002-02 (minimum isolation boundary) and ARCH-002 § 5.2.

## Context

`MULTI-HERMES-CONTRACT.md` v0.2.1 § 5.4 names the Executor's command-execution backend as Hermes' built-in `terminal` toolset, configured to run inside a Docker container per ADR-014 § Correction 5. The contract names *one* backend with no abstraction layer.

ARCH-001 v0.3.0 § 21 already names "paid sandbox backends (Modal, E2B, Daytona)" as a future possibility for the case where a generated project's build cannot fit local Docker. Today, picking up that future possibility would require touching every place `MULTI-HERMES-CONTRACT.md` § 5.4 / `OBSERVABILITY-CONTRACT.md` / Reviewer rubric assumes Docker concretely.

The RESEARCH-002 survey identifies Bernstein as the strongest existing implementation of a typed sandbox-capability protocol that abstracts over backends (worktree, Docker, E2B, Modal) without committing to any single one (`bernstein@f950c71eddf0:docs/architecture/sandbox.md:L21-L91`). Five further surveyed repos converge on the same structural shape — Gas Town worktrees-vs-clones (`gastown@18b1f4170c5f:docs/research/w-gc-004-agent-framework-survey.md:L41-L44`), CLITrigger worktree-per-TODO (`CLITrigger@fd4731bb3e20:README.md:L125-L127`), OpenCastle worktree-per-worker (`opencastle@18c6f2cf4e5c:README.md:L192-L195`), AgentsMesh Pod (`AgentsMesh@93f56e498ebc:design/research/product-model.md:L20-L25`), Codebuff agent-runtime (`codebuff@54df847c6384:docs/architecture.md:L57-L97`).

## Decision

Adopt Bernstein's typed sandbox-capability vocabulary as a **thin abstraction layer** between the Executor specialist runtime and the concrete Docker backend, with the following properties:

1. **Capability set.** A finite enum `SandboxCapability ∈ {FILE_RW, EXEC, NETWORK, GPU, SNAPSHOT, PERSISTENT_VOLUMES}`. Each backend declares which capabilities it supports.
2. **Session interface.** A backend exposes `create(work_item_id) → Session`, `resume(session_id) → Session`, `destroy(session_id)`. A `Session` exposes `read(path)`, `write(path, content)`, `exec(cmd, env, timeout)`, `ls(path)`, `snapshot()` (capability-gated), `shutdown()`.
3. **Capability negotiation at dispatch.** The work-queue dispatcher compares the work-item's required capabilities (declared in the ticket frontmatter) against the active backend's declared capabilities; if any required capability is missing, the dispatcher refuses to dispatch and emits a `mail`-modality escalation per ADR-017.
4. **v0.1 single concrete implementation.** Ship `DockerSandbox` (capabilities: `{FILE_RW, EXEC, NETWORK}`) as the only concrete backend in v0.1. `GPU`, `SNAPSHOT`, `PERSISTENT_VOLUMES` raise `CapabilityNotAvailable` if requested.
5. **v0.2+ extension path.** Future ADRs add `WorktreeSandbox` (for parallel-ticket execution), `ModalSandbox` and `E2BSandbox` (for builds-too-large-for-local-Docker). No specialist runtime needs to change when those backends are added — the abstraction sits between Hermes' `terminal` toolset and the chosen backend.
6. **Boundary contract.** A new artifact `docs/architecture/SANDBOX-CONTRACT.md` (Architect write zone) authored by TKT-035 makes the protocol authoritative; `MULTI-HERMES-CONTRACT.md` § 5.4 amendment cross-references it.

## Considered Options

### Option A — Bernstein-style typed protocol (CHOSEN)

How it works: as in the Decision section. Capability enum + session interface + dispatcher negotiation + single v0.1 backend.

Trade-offs:

- **+** Future-proofing without speculative implementation: the protocol is small (~50 lines of Python interfaces), one concrete backend ships v0.1, additions are non-breaking.
- **+** Capability negotiation makes "this ticket needs GPU" or "this ticket needs snapshot rollback" explicit at dispatch time rather than failing mid-execution.
- **+** Aligns the project with the surveyed convergence; future contributors can recognize the pattern.
- **+** No new pip dependency: pure-Python interface plus existing Docker-Python integration.
- **−** One additional indirection between the Executor runtime and the sandbox; debugging requires understanding the protocol layer. Mitigated by `SANDBOX-CONTRACT.md` documentation and by keeping the layer thin.

### Option B — Status quo (Docker hard-coded in MULTI-HERMES-CONTRACT § 5.4)

How it works: keep the Docker backend named directly in the contract; revisit when v0.2+ needs Modal/E2B.

Trade-offs:

- **+** Zero implementation cost in v0.1.
- **−** Every v0.2+ backend addition requires touching MULTI-HERMES-CONTRACT, the Executor prompt, the Reviewer rubric, OBSERVABILITY-CONTRACT.
- **−** Capability mismatch (e.g., a ticket assumes GPU access that local Docker doesn't have) fails opaquely at runtime instead of being caught at dispatch.

Rejected: ARCH-001 § 21 explicitly names the v0.2+ trigger condition; preparing the abstraction layer is cheaper than retroactively introducing it under deadline pressure.

### Option C — Adopt Bernstein's full storage-sink abstraction simultaneously

How it works: take both the sandbox protocol AND the artifact-sink storage abstraction (`bernstein@f950c71eddf0:docs/architecture/storage.md:L1-L14`) in the same ADR.

Trade-offs:

- **−** Conflates two concerns: sandbox isolation (this ADR) and durable-state mirror destinations (a future v0.2+ concern with no v0.1 trigger).
- **−** Larger surface; over-engineering risk per NUDGE § 12.2.

Rejected: ARCH-002 § 3.4 / § 3.7 records the storage-sink abstraction as Future Possibility with explicit trigger.

## Consequences

- **Implementation cost.** TKT-035 implements `SANDBOX-CONTRACT.md` + `src/sandbox/protocol.py` (interfaces) + `src/sandbox/docker.py` (DockerSandbox concrete) + `tests/test_sandbox.py`. Estimated ~250-400 lines of new code + ~150 lines of tests.
- **Contract amendments.** `MULTI-HERMES-CONTRACT.md` § 5.4 cross-references SANDBOX-CONTRACT.md; the Executor's `terminal` toolset configuration becomes "DockerSandbox-backed terminal" rather than "Docker-backed terminal".
- **Backward compatibility.** No runtime-visible behaviour change in v0.1 — DockerSandbox is functionally identical to the current Docker-backed terminal. The abstraction is purely additive.
- **Forward compatibility.** v0.2+ ADRs adding new backends (worktree, Modal, E2B) reference this ADR's protocol and add to the capability matrix. ADR-015 may bump to v0.2.0 when first new backend is added.
- **Failure modes.** New `failure_mode` entry in OBSERVABILITY-CONTRACT § Named Failure Modes: `sandbox_capability_unavailable` — dispatcher rejected work item due to missing capability; recovery: ticket frontmatter must be amended OR a backend supporting the capability must be added; escalation modality: mail.

## References

- RESEARCH-002 § 6.3 (Bernstein deep dive).
- ARCH-002 § 3.6 (App-6 isolation), § 5.2 (Q-RESEARCH-002-02), § 6.1 (amendment proposal).
- `bernstein@f950c71eddf0:docs/architecture/sandbox.md:L21-L91` (sandbox protocol source).
- ADR-005 (multi-Hermes runtime isolation), ADR-014 § Correction 5 (Docker backend in production).
- TKT-035 (implementation ticket, status: draft).
