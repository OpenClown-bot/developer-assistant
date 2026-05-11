---
id: TKT-035
version: 0.1.1
status: done
arch_ref: ARCH-002@0.1.0
adr_ref: ADR-015@0.1.0
updated: 2026-05-10
---

# TKT-035: Sandbox Capability Protocol v0.1 — DockerSandbox concrete implementation

## 1. Scope

Implement ADR-015 (Sandbox Capability Protocol) as a thin Python abstraction layer between Hermes' `terminal` toolset and the concrete Docker backend. This ticket ships the protocol interfaces plus a single concrete `DockerSandbox` backend; v0.2+ backends (`WorktreeSandbox`, `ModalSandbox`, `E2BSandbox`) are explicitly deferred. The Executor specialist runtime's runtime-visible behaviour does not change in v0.1 — this ticket is purely the abstraction layer.

The work also authors a new boundary contract `docs/architecture/SANDBOX-CONTRACT.md` (Architect-zone authorship within this Executor ticket is permitted because the contract's content is fully specified by ADR-015; the Architect cycle has signed off via ADR-018 ratify). `MULTI-HERMES-CONTRACT.md` § 5.4 receives a one-line cross-reference amendment to point at SANDBOX-CONTRACT.md for the Executor's terminal-backend definition.


## 2. Non-scope

- WorktreeSandbox implementation — Future Possibility per ARCH-002 § 10, triggered by parallel-ticket execution.
- ModalSandbox / E2BSandbox implementations — Future Possibility per ARCH-002 § 10, triggered by build-too-large-for-Docker.
- GPU / SNAPSHOT / PERSISTENT_VOLUMES capability *implementations* — only the enum values exist; raising `CapabilityNotAvailable` is sufficient for v0.1.
- Capability matrix for backends beyond DockerSandbox — covered by future ADRs.
- Performance benchmarks of the abstraction layer overhead — assumed negligible for v0.1; revisit if observability shows >5% latency increase.


## 3. Required Context

- ADR-015 v0.1.0 § Decision (final spec).
- ARCH-002 v0.1.0 § 3.6 (App-6 isolation), § 5.2 (Q-RESEARCH-002-02), § 6.1 (amendment).
- `MULTI-HERMES-CONTRACT.md` v0.2.1 § 5.4 (Executor terminal toolset baseline).
- `bernstein@f950c71eddf0:docs/architecture/sandbox.md:L21-L91` (reference implementation; not for direct copy — for vocabulary alignment).
- ADR-014 § Correction 5 (current Docker-backed terminal in production).


## 4. Acceptance Criteria

**AC-1.** `src/sandbox/protocol.py` defines a `SandboxBackend` abstract base class plus `Session` abstract base class plus `SandboxCapability` enum exactly matching ADR-015 § Decision point 1 and 2. The capability enum has exactly six values: `FILE_RW`, `EXEC`, `NETWORK`, `GPU`, `SNAPSHOT`, `PERSISTENT_VOLUMES`.

**AC-2.** `src/sandbox/docker.py` implements `DockerSandbox(SandboxBackend)` with declared capabilities `{FILE_RW, EXEC, NETWORK}`. Methods `create`, `resume`, `destroy` plus `Session` methods `read`, `write`, `exec`, `ls`, `shutdown` are functional. `snapshot` raises `CapabilityNotAvailable`.

**AC-3.** Capability negotiation: a new helper `negotiate_capabilities(work_item, backend) -> Result` returns `Ok` if all required capabilities are declared, else `Err(missing_capability)`. Tested with a unit test covering all six capabilities.

**AC-4.** `tests/test_sandbox.py` covers: protocol shape (interfaces enforce abstract methods), DockerSandbox happy path (create-exec-shutdown), DockerSandbox capability declaration (only `{FILE_RW, EXEC, NETWORK}`), `CapabilityNotAvailable` raised on unsupported requests, negotiation helper returning `Err` for missing caps. All tests pass under `pytest`.

**AC-5.** `docs/architecture/SANDBOX-CONTRACT.md` v0.1.0 (status: draft, arch_ref: ARCH-002@0.1.0, adr_ref: ADR-015@0.1.0) authored with sections: § 1 Purpose, § 2 Backend interface, § 3 Session interface, § 4 Capability enum, § 5 Negotiation algorithm, § 6 v0.1 backend matrix (DockerSandbox only), § 7 Future backends (worktree, Modal, E2B per ARCH-002 § 10).

**AC-6.** `MULTI-HERMES-CONTRACT.md` § 5.4 amended with one-line cross-reference: "Executor terminal-backend protocol authoritative in `SANDBOX-CONTRACT.md` v0.1.0."

**AC-7.** `python3 scripts/validate_docs.py` passes (frontmatter, cross-link to ADR-015, status flow).

**AC-8.** No runtime-visible behavioural change for the Executor specialist runtime pre/post deployment (verified by re-running the existing TKT-008 / TKT-016 GitHub-executor smoke pattern locally; this AC is a non-regression observation, not a new test).


## 5. Allowed Files

- `src/sandbox/__init__.py` (NEW)
- `src/sandbox/protocol.py` (NEW)
- `src/sandbox/docker.py` (NEW)
- `tests/test_sandbox.py` (NEW)
- `docs/architecture/SANDBOX-CONTRACT.md` (NEW; Architect-zone authorship within this Executor ticket is justified by ADR-015 § Decision point 6 explicit pointer to TKT-035 as authoring vehicle)
- `docs/architecture/MULTI-HERMES-CONTRACT.md` (one-line amendment in § 5.4 only)
- `pyproject.toml` (only if a new test fixture or runtime dep is required; if so, must be added to ADR-014-style amendment)


## 6. Test Strategy

Test pyramid for this ticket:

- **Unit (`tests/test_sandbox.py`):** protocol shape (abstract base classes enforce method presence), `SandboxCapability` enum integrity, capability-negotiation helper happy/error paths, `DockerSandbox` capability declaration, `CapabilityNotAvailable` raised on unsupported requests.
- **Integration:** `DockerSandbox` round-trip — `create → write → exec → read → shutdown` against a real local Docker daemon (CI runner has docker-in-docker available per ARCH-001 § 17 baseline; if not, gate this layer behind an env flag).
- **Non-regression:** the existing TKT-008/TKT-016 GitHub-executor smoke pattern is re-run locally; no behavioural change observed.


## 7. Risk Notes

Primary risk: the abstraction layer adds one indirection between the Executor's Hermes terminal toolset and the Docker backend. If the indirection is implemented sloppily, it could mask Docker errors that the Executor previously saw directly. Mitigation: error-passthrough tests at the protocol layer; unit-test that `DockerSandbox.exec` propagates non-zero exit codes, stderr content, and timeout exceptions verbatim. Secondary risk: CI runner Docker-in-Docker availability — if absent, fall back to mocked Docker SDK for AC-2 happy-path test.


## 8. Spec Amendment Notes

Hard rules for this ticket (governance constraints inherited from ARCH-002 + the source ADR; Executor MUST observe):


- Do NOT touch any other file under `src/` or `tests/` unless it was on the Allowed Files list.
- Do NOT modify ADR-015 (contracts at `proposed` status are amended via Architect cycles, not Executor cycles; if ADR-015 needs amendment, raise a Q-TKT and stop).
- Do NOT bypass the Hermes terminal toolset — `DockerSandbox.exec` calls Docker via the existing `docker` Python SDK pathway used by Hermes, not via raw `subprocess.run("docker exec ...")`.
- Do NOT add new external pip dependencies without an accompanying ADR amendment per NUDGE § 5.4 (the Docker SDK is already a v0.1 dependency).
- The Executor specialist runtime's terminal-toolset configuration MUST NOT change shape in v0.1 — DockerSandbox is registered as the backend transparently.


## 9. Cross-references

- ADR-015 v0.1.0 (Sandbox Capability Protocol).
- ARCH-002 v0.1.0 § 3.6, § 5.2, § 6.1.
- RESEARCH-002 § 6.3 (Bernstein), § 7.1 (work isolation).
- `bernstein@f950c71eddf0:docs/architecture/sandbox.md:L21-L91`.
- `MULTI-HERMES-CONTRACT.md` v0.2.1 § 5.4.
- ADR-005 (multi-Hermes runtime isolation), ADR-014 § Correction 5.


## 10. Execution Log

### iter-1 — 2026-05-10 — Code Executor

- **Branch:** `tkt/035-sandbox-capability-protocol` cut from `origin/main` HEAD `ceb8b2b6`.
- **Implementation HEAD SHA:** `a3d5308` (single commit `tkt-035: Sandbox Capability Protocol v0.1 — DockerSandbox concrete implementation`).
- **AC-7 docs validation:** `python3 scripts/validate_docs.py` → `Docs validation passed.`
- **AC-4 pytest counts:**
  - `tests/test_sandbox.py` (new, this ticket): **36 passed, 0 failed, 0 skipped, 0 subtests** (`pytest tests/test_sandbox.py`).
  - Full suite (`pytest tests/`): **1187 passed, 62 failed, 2 skipped** — the 62 failures are pre-existing on `origin/main` HEAD `ceb8b2b6` (verified with `git stash -u && pytest tests/` returning 1151 passed / 62 failed / 2 skipped against the same baseline — the +36 net-passing count exactly matches the new `tests/test_sandbox.py` cases). Failures are concentrated in `tests/test_self_deployment_scripts.py` and a handful of `runtime_check` / `runtime_layout_catalog_round_trip` subFAILED rows; all require a real install layout under `/srv/devassist/...` that this Executor environment does not provision and that this ticket does not modify (AC-8 non-regression observation: scripts under `scripts/install-self.sh`, `scripts/verify-self.sh`, and the systemd unit templates are untouched).
- **Mocked-Docker policy:** the AC-4 happy-path / error-propagation tests use a `unittest.mock.MagicMock` docker client because the Executor environment has no docker-in-docker; matches the § 7 risk-mitigation fallback wording.
- **Hard-rule observance (ticket § 8):**
  - No writes outside § 5 Allowed Files (verified via `git diff --stat` post-commit; touched files are `src/sandbox/{__init__,protocol,docker}.py`, `tests/test_sandbox.py`, `docs/architecture/SANDBOX-CONTRACT.md`, and a single-line amendment to `docs/architecture/MULTI-HERMES-CONTRACT.md` § 5.4).
  - ADR-015 not modified.
  - `DockerSandbox` dispatches all Docker operations through the `docker` Python SDK (`docker.from_env()` lazy-imported in `sandbox.docker._docker_module()`, `containers.run`, `containers.get`, `container.exec_run`, `container.put_archive`, `container.get_archive`); `subprocess` is not imported anywhere in the new module tree.
  - No new pip dependencies added; `pyproject.toml` not amended (the `docker` SDK is the v0.1 dep already named by `MULTI-HERMES-CONTRACT.md` § 5.4 / ADR-014 § Correction 5; mocked SDK in tests means the Executor environment doesn't need it installed).
  - Executor specialist runtime's `terminal.backend: docker` shape in `MULTI-HERMES-CONTRACT.md` § 4 / § 5.4 unchanged — DockerSandbox is registered transparently.
- **Known limitations:**
  - `DockerSession.exec` accepts a `timeout` parameter for forward-compat but the docker SDK 7.x `container.exec_run` does not honor a per-call timeout natively; transport-level timeout exceptions are propagated verbatim per § 7. A future iteration can wire a wall-clock timeout via `asyncio` or a subprocess-style watchdog if a ticket consumer requires deterministic per-call cutoffs.
  - `DockerSession.read` returns the bytes of the first regular-file member of the SDK's `get_archive` tar stream; it is not a directory-recursive read. Documented in § 3 of `SANDBOX-CONTRACT.md`.
  - Capability negotiation iterates the work item's required-capability `frozenset` and returns the first missing capability — `frozenset` iteration order is hash-stable but not insertion-ordered, so the precise `Err.missing_capability` value may vary across capability sets of size > 1. Tests assert correctness (any missing cap is returned) rather than ordering; sufficient for AC-3.
- **Surfaceable flags raised this cycle:** none beyond the carry-over flags F1 / F4 named in the iter-1 NUDGE (out of scope per the NUDGE).

### Closure amendment — 2026-05-10 — Strategic Orchestrator

Filed as part of the TKT-035 closure-PR (`so/closure-tkt-035-*`) by SO (Anthropic Claude). This subsection closes Reviewer finding `RV-CODE-036` F1 (Medium clerical) append-only per SO write-zone discipline; the iter-1 entry above is preserved verbatim for forensic auditability.

- **F1 closure (Execution Log SHA correction).** The iter-1 entry records `Implementation HEAD SHA: a3d5308`, which is the pre-rebase SHA captured before the Executor's final push to `tkt/035-sandbox-capability-protocol`. The authoritative implementation commit on the merged tkt-branch is `4fea58c` (verified via `git log origin/main..origin/tkt/035-sandbox-capability-protocol --oneline` against tkt HEAD `b653dbc` before merge; `b653dbc` is the subsequent `append § 10 Execution Log entry` commit). For all forensic audit purposes, treat **`4fea58c`** as the authoritative implementation SHA for iter-1; the `a3d5308` reference above is historical pre-rebase noise. Reviewer F1 finding (`RV-CODE-036` § Findings F1) is closed by this documentary correction per RV-CODE-036 § F1 remediation option `fast-follow clerical PR`.
- **SO ratify pass-2 attestation (PR #155 + PR #156).** Substantive verification on iter-1 HEAD `b653dbc` (PR #155) and review HEAD `b63f5d1` (PR #156) completed by SO: direct code-read on all 5 new files (`src/sandbox/{__init__,protocol,docker}.py`, `tests/test_sandbox.py`, `docs/architecture/SANDBOX-CONTRACT.md`) + AC-6 git-diff inspection on `MULTI-HERMES-CONTRACT.md` § 5.4 (exactly one substantive new line) + AC-7 `python3 scripts/validate_docs.py` → `Docs validation passed.` + AC-2 hard-rule `subprocess`-not-imported check across `src/sandbox/` + AC-4 targeted `pytest tests/test_sandbox.py` → **36/0/0** (reconciles with Executor + Reviewer reports byte-equal) + AC-8 non-regression delta `+36/0/0` reconciled across three environments (Executor full-suite 1187/62/2; Reviewer full-suite 1127/7/112+84subt; SO targeted-only; all three confirm the load-bearing invariant: zero new failures, zero new skips, +36 net-passing). CI status on `b653dbc`: validate-docs ✓ success + PR-Agent ✓ success (settled `Fully compliant` 8/8 ACs). CI status on `b63f5d1`: validate-docs ✓ success + PR-Agent ✓ success.
- **Cross-family witness chain integrity (AUDIT-002 doctrine).** SO Anthropic (Claude) ↔ Executor DeepSeek V4 Pro (opencode + OmniRoute, Founder VPS) ↔ Reviewer Kimi K2.6 Moonshot (opencode + OmniRoute, Founder PC) ↔ PR-Agent DeepSeek V4 Pro (Qodo on GitHub Actions). Three independent model families. `AGENTS.md` cross-family witness doctrine satisfied.
- **Status promotion.** Frontmatter `status: draft` → `status: done`, `version: 0.1.0` → `0.1.1` (patch bump for the documentary correction + status promote; no spec amendment in this closure). ADR-015 promotion from `proposed` → `accepted` and ARCH-002 § 3.6/5.2 ratify markers are deferred to a separate Architect cycle per SO write-zone discipline (`docs/architecture/adr/` is not in SO write zone).
- **Carry-over surfaceable flags for SO maintenance pass (non-blocking, not actioned here).**
  - F-PA2-2 Pytest baseline reconciliation: handoff cited 12 failures (on-VPS `/srv/devassist/` provisioned), Executor reported 62 (containerized env without `/srv/devassist/`), Reviewer reported 7 (Windows-style env without the larger `test_self_deployment_scripts.py` failure surface). All three environment-dependent; delta-based verification (`+36/0/0`) holds across all three. Folded into `Q-TKT-034-02` long-tail / F2 backlog item.
  - F-PA2-4 Recurring VPS GH auth `HTTP 401`: surfaced twice in this cycle (Executor session needed Founder to paste fresh `github_pat_…` directly; Reviewer session needed a second temp-PAT paste). Suspected Devin secret-update UI byte-caching of a stale 32-char non-PAT token. Platform observation, not project code; tracked for SO maintenance pass.
