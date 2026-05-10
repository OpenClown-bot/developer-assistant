---
id: RV-CODE-036
version: 0.1.0
status: complete
verdict: pass_with_changes
ticket: TKT-035@0.1.0
branch: rv/code-036-tkt-035
reviewer_model: Kimi K2.6 (Moonshot) via opencode + OmniRoute
reviewer_role: cross-family witness vs Executor DeepSeek V4 Pro + PR-Agent DeepSeek V4 Pro
predecessor_review: none
target_pr: "#155"
target_head: b653dbc
target_tkt_branch: tkt/035-sandbox-capability-protocol
date: 2026-05-10
---

# RV-CODE-036: TKT-035 iter-1 review (cross-family witness — Moonshot Kimi K2.6)

## Verdict: pass_with_changes

One clerical finding (F1) requires a ticket § 10 amendment before merge. All eight acceptance criteria are substantively satisfied. Implementation matches ADR-015 § Decision points 1–6, SANDBOX-CONTRACT.md v0.1.0 is well-formed, and the +36 net-passing test delta confirms zero regression.

---

## Findings

### F1 — Clerical: Execution Log SHA mismatch (Medium)

**Location:** `docs/tickets/TKT-035-sandbox-capability-protocol.md` § 10 Execution Log iter-1 entry.

**Observation:** The Execution Log records `Implementation HEAD SHA: a3d5308` for the single implementation commit, but the actual commit on branch `tkt/035-sandbox-capability-protocol` is `4fea58c` (`git log origin/main..origin/tkt/035-sandbox-capability-protocol --oneline` shows `4fea58c` followed by `b653dbc`).

**Impact:** None on code correctness or architecture compliance; this is a post-rebase clerical drift where the pre-rebase SHA was captured before the final push.

**Remediation:** Executor amends § 10 iter-1 entry to state `Implementation HEAD SHA: 4fea58c`.

**Severity rationale:** Medium — not a merge blocker, but durable artifacts must match the git graph for forensic auditability. Closure can happen in the same PR (a second commit on the tkt-branch) or as a fast-follow clerical PR.

---

## Scope Compliance Assessment

`git diff --stat origin/main..origin/tkt/035-sandbox-capability-protocol` shows exactly seven files, all within TKT-035 § 5 Allowed Files:

- `src/sandbox/__init__.py` (NEW)
- `src/sandbox/protocol.py` (NEW)
- `src/sandbox/docker.py` (NEW)
- `tests/test_sandbox.py` (NEW)
- `docs/architecture/SANDBOX-CONTRACT.md` (NEW)
- `docs/architecture/MULTI-HERMES-CONTRACT.md` (one-line amendment in § 5.4)
- `docs/tickets/TKT-035-sandbox-capability-protocol.md` (§ 10 Execution Log)

No frozen-surface files were touched. Scope compliance passes.

---

## Architecture Compliance Assessment

| Requirement | Assessment |
|---|---|
| ADR-015 § Decision point 1 — Capability enum | **Pass.** `SandboxCapability` has exactly six values in the mandated order: `FILE_RW`, `EXEC`, `NETWORK`, `GPU`, `SNAPSHOT`, `PERSISTENT_VOLUMES`. |
| ADR-015 § Decision point 2 — Session + Backend ABC | **Pass.** `Session` declares `session_id`, `read`, `write`, `exec`, `ls`, `snapshot`, `shutdown`. `SandboxBackend` declares `name`, `capabilities`, `create`, `resume`, `destroy`. Both are ABCs with `@abstractmethod` enforcement. |
| ADR-015 § Decision point 3 — Negotiation | **Pass.** `negotiate_capabilities(work_item, backend) -> Result` is a pure function (no I/O, no global state). Dispatcher-level `mail`-modality escalation is referenced in docstrings; actual dispatcher wiring is out of TKT-035 scope. |
| ADR-015 § Decision point 4 — DockerSandbox capabilities | **Pass.** `DOCKER_CAPABILITIES == {FILE_RW, EXEC, NETWORK}` exactly. `snapshot` raises `CapabilityNotAvailable`. |
| ADR-015 § Decision point 5 — v0.2+ extension path | **Pass.** `WorktreeSandbox`, `ModalSandbox`, `E2BSandbox` are deferred; SANDBOX-CONTRACT.md § 7 records triggers and capability sets. |
| ADR-015 § Decision point 6 — Boundary contract | **Pass.** `SANDBOX-CONTRACT.md` v0.1.0 authored with correct frontmatter and all seven required sections. |
| MULTI-HERMES-CONTRACT.md § 5.4 cross-reference | **Pass.** Exactly one substantive new line added: "Executor terminal-backend protocol authoritative in `SANDBOX-CONTRACT.md` v0.1.0." No other diff in the file. |
| TKT-035 § 8 hard rule — no subprocess in `src/sandbox/` | **Pass.** `src/sandbox/docker.py` dispatches exclusively through the `docker` Python SDK (`docker.from_env()`, `containers.run`, `containers.get`, `container.exec_run`, `container.put_archive`, `container.get_archive`). `subprocess` is not imported in any `src/sandbox/` file. |

---

## Acceptance Criteria Assessment

| AC | Status | Evidence / rationale |
|---|---|---|
| AC-1 — Protocol ABC + enum | **Pass** | `tests/test_sandbox.py::CapabilityEnumTests` verifies six values in ADR order. `ProtocolShapeTests` verifies `SandboxBackend` and `Session` are abstract and list the required methods. |
| AC-2 — DockerSandbox concrete | **Pass** | `DOCKER_CAPABILITIES` frozen-set matches `{FILE_RW, EXEC, NETWORK}`. `DockerSession.snapshot()` raises `CapabilityNotAvailable(SandboxCapability.SNAPSHOT, "docker")`. SDK-only dispatch confirmed by source inspection and absence of `subprocess` import. |
| AC-3 — Negotiation pure function | **Pass** | `negotiate_capabilities` is a standalone pure function. `NegotiationTests::test_err_for_each_unsupported_capability` iterates all six capabilities. `test_err_against_empty_backend` iterates all six against an empty backend. Both pass. |
| AC-4 — Test coverage | **Pass** | 36 tests collected, 36 passed, 0 failed. Coverage: protocol shape, enum integrity, happy path (create→exec→shutdown), capability declaration, `CapabilityNotAvailable` on snapshot, negotiation `Err`, verbatim error propagation (non-zero exit, stderr, `TimeoutError`, arbitrary SDK exception, `ls` non-zero exit → `RuntimeError`). |
| AC-5 — SANDBOX-CONTRACT.md | **Pass** | Frontmatter: `status: draft`, `arch_ref: ARCH-002@0.1.0`, `adr_ref: ADR-015@0.1.0`, `updated: 2026-05-10`. Seven sections: Purpose, Backend interface, Session interface, Capability enum, Negotiation algorithm, v0.1 backend matrix, Future backends. |
| AC-6 — MULTI-HERMES-CONTRACT.md § 5.4 | **Pass** | Diff shows exactly one substantive new line cross-referencing SANDBOX-CONTRACT.md v0.1.0. |
| AC-7 — `validate_docs.py` | **Pass** | `python3 scripts/validate_docs.py` on tkt HEAD `b653dbc` returns `Docs validation passed.` (exit 0). |
| AC-8 — Non-regression | **Pass** | tkt branch: 1127 passed / 7 failed / 112 skipped. origin/main baseline: 1091 passed / 7 failed / 112 skipped. Net delta: **+36 passed**, zero new failures, zero new skips. The 7 pre-existing failures are environment-dependent (`test_runtime_check.py`, `test_runtime_layout_catalog_round_trip.py`) and outside the TKT-035 write zone. |

---

## Security Assessment

| Control | Status | Evidence |
|---|---|---|
| No secrets in new files | Pass | Source scan of all seven new/modified files shows zero token-shaped literals, zero `ghp_*` / `github_pat_*` / `sk-*` prefixes, zero 40+ char base64-like strings. |
| No `.env` or credential files | Pass | None added. |
| Docker dispatch pathway | Pass | All Docker operations route through the typed `docker` Python SDK (`_docker_module() -> docker.from_env()`), not raw `subprocess.run("docker ...")`. This eliminates shell-injection risk in the abstraction layer. |
| Test isolation | Pass | `tests/test_sandbox.py` uses `unittest.mock.MagicMock` for the Docker client. No real containers are created, no real PATs or hostnames are referenced, no network I/O occurs. |
| Error propagation hygiene | Pass | `ExecResult` carries `stdout: bytes` and `stderr: bytes` without decoding, preventing encoding-related information leakage or corruption of binary build artifacts. |

---

## Validation Evidence

- `python3 scripts/validate_docs.py` → **Docs validation passed.** (exit 0, run on tkt HEAD `b653dbc`).
- `python -m pytest tests/test_sandbox.py -v` → **36 passed, 0 failed, 0 skipped** in 0.12 s.
- `python -m pytest tests/ --tb=no -q` (tkt branch `b653dbc`) → **1127 passed, 7 failed, 112 skipped, 84 subtests passed** in 17.70 s.
- `python -m pytest tests/ --tb=no -q` (origin/main `ceb8b2b6`) → **1091 passed, 7 failed, 112 skipped, 84 subtests passed** in 17.64 s.
- Net delta: **+36 passing tests**, zero new failures, zero new skips — the exact count of new `test_sandbox.py` cases.
- Pre-existing 7 failures are identical on both branches and concentrated in `tests/test_runtime_check.py` + `tests/test_runtime_layout_catalog_round_trip.py`; these require `/srv/devassist/` install layout not present on this Windows reviewer host and are outside TKT-035 scope.

---

## CI / PR-Agent Status

- GitHub Actions CI for PR #155: not directly inspectable via `gh` CLI in this environment (unauthenticated). Local validation indicates `validate_docs` and pytest will be green for the new files. The SO ratify pass-2 will gate PR-Agent settle.
- PR-Agent auto-review (DeepSeek V4 Pro via OmniRoute): pending. Not waited for per NUDGE § Hand-back protocol.

---

## Merge / Ratification Recommendation

**Ratify PR #155 as TKT-035 iter-1 and merge to `main` after F1 is closed.**

F1 is clerical-only: the Executor amends `docs/tickets/TKT-035-sandbox-capability-protocol.md` § 10 iter-1 entry to record the correct implementation SHA (`4fea58c` instead of `a3d5308`). This can be done as an additional commit on the existing tkt-branch before merge, or as a fast-follow clerical PR — the Reviewer has no preference.

No architecture deviations, no security regressions, no scope violations, and all substantive acceptance criteria are satisfied. The abstraction layer is thin, well-tested, and correctly future-proofs the v0.2+ backend extension path per ADR-015.
