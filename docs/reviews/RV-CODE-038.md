---
id: RV-CODE-038
version: 0.1.0
status: complete
verdict: pass_with_changes
ticket: TKT-041@0.1.1
branch: rv/rv-code-038-tkt-041-audit-003-smoke-impl
reviewer_model: Kimi K2.6 (Moonshot) via opencode + OmniRoute
reviewer_role: cross-family witness vs Executor Anthropic Claude Sonnet 4.5
predecessor_review: RV-SPEC-018 (iter-1 spec review) + RV-SPEC-019 (iter-2 verify)
target_pr: "#174"
target_head: a7cce85
target_tkt_branch: exe/tkt-041-audit-003-behaviour-smoke
base_commit: 9482edb
date: 2026-05-12
---

# RV-CODE-038: TKT-041 v0.1.1 AUDIT-003 iter-1 review (cross-family witness — Moonshot Kimi K2.6)

## Verdict: pass_with_changes

All substantive acceptance criteria are satisfied. The implementation matches
`OBSERVABILITY-CONTRACT.md` v0.1.1, `SELF-DEPLOYMENT-CONTRACT.md` § smoke-mode,
and `MULTI-HERMES-CONTRACT.md` § role loadouts. The +50 net-passing test delta
confirms zero regression. One test-portability finding (F-PORT-1) requires a
one-line fix per call-site in two new test files before the suite is green on
Windows developer hosts.

---

## Findings

### F-PORT-1 — `pathlib.Path.write_text` newline translation breaks SHA256 assertions on Windows (Medium)

**Location:**
- `tests/test_behaviour_smoke.py` — `TestAC4PromptShaCrossCheck.setUp` and
  `test_smoke_prompt_sha_mismatch_emits_role_diagnostic`
- `tests/test_observability_manager_smoke.py` —
  `TestHealthExtendedFieldsAsyncRoundtrip.test_prompt_sha256_recomputed_post_tamper`

**Observation:**
These tests compute an expected SHA-256 from a Python `bytes` literal
(e.g. `b"# Planner role prompt (smoke fixture)\n"`) and compare it to the
SHA-256 of a file written with `Path.write_text(..., encoding="utf-8")`. On
Windows, `write_text` defaults to `newline=None`, which translates `\n` to
`\r\n` (`os.linesep`). The on-disk bytes therefore differ from the literal,
causing an assertion failure that is **not** a product-code defect.

**Impact:**
- 2 of 50 new tests fail on Windows (the reviewer host).
- 0 impact on Linux CI or production runtime.
- Does not mask any other failure class.

**Remediation:**
Add `newline=""` to every `Path.write_text(..., encoding="utf-8")` call in
the two test files that is paired with a byte-literal SHA expectation. Example:

```python
Path(p).write_text(body, encoding="utf-8", newline="")
```

Alternatively, compute the expected SHA from `Path(p).read_bytes()` after
writing, rather than from the pre-write string literal.

**Severity rationale:** Medium — not a merge blocker on Linux CI, but the
project's primary development host is Windows and durable tests must be
platform-portable. The fix is trivial and test-only.

---

## Scope Compliance Assessment

`git diff --stat 9482edb..a7cce85` shows 22 files, all within TKT-041 § 5
Allowed Files or derived artefacts:

- `src/developer_assistant/smoke_inject.py` (NEW)
- `src/developer_assistant/observability/health_endpoint.py` (+/-)
- `src/developer_assistant/observability/observability_manager.py` (+/-)
- `src/developer_assistant/cli/dev_assist_cli.py` (+/-)
- `scripts/install-self.sh` (+/-: smoke-mode flag rendering)
- `scripts/verify-self.sh` (+/-: smoke-mode verification invariants)
- `scripts/templates/dev-assist-smoke.sh` (NEW: operator harness)
- `tests/test_behaviour_smoke.py` (NEW)
- `tests/test_smoke_inject_endpoint.py` (NEW)
- `tests/test_dev_assist_cli_smoke.py` (NEW)
- `tests/test_observability_manager_smoke.py` (NEW)
- `tests/fixtures/smoke-mode/*` (6 new fixture files)
- `docs/tickets/TKT-041-behaviour-level-deployment-smoke.md` (+/-: § 10 Execution Log)
- `docs/questions/Q-TKT-041-01.md` through `Q-TKT-041-04.md` (4 NEW question files)

No frozen-surface files were touched. Scope compliance passes.

---

## Architecture / Contract Compliance Assessment

| Requirement | Assessment |
|---|---|
| `OBSERVABILITY-CONTRACT.md` v0.1.1 § 4.2 — `/health` extended fields | Pass. `health_endpoint.py` exposes `prompt_sha256`, `prompt_path`, `smoke_mode`, and `loaded_skills` when `?internal=1` is present and the smoke-mode marker file exists. Marker-absent requests return `null` for these fields. |
| `SELF-DEPLOYMENT-CONTRACT.md` § smoke-mode install | Pass. `install-self.sh` gains `--smoke-mode` flag rendering and `check_smoke_mode_mutual_exclusion` in `verify-self.sh` enforces that `TELEGRAM_BOT_TOKEN` matches `^smoke-fixture-token-[a-z0-9]{8}$` when the marker is present. |
| `MULTI-HERMES-CONTRACT.md` § 5 role loadouts | Pass. `test_behaviour_smoke.py::TestAC2LoadedSkillsSetEquality` verifies each role's `loaded_skills` set equals the canonical contract table. `hermes_agent` is explicitly absent from all sets. `classifier` is present only on `orchestrator`. |
| `MULTI-HERMES-CONTRACT.md` § 5.5 Reviewer terminal skill | Informational / deferred. Q-TKT-041-04 correctly surfaces a discrepancy: the contract lists `terminal` for Reviewer; TKT-041 § 3.2 omits it. The question is routed to Architect amendment per Executor protocol and is not an audit blocker. |
| ADR-014 § invariants | Pass. AC-3 (delegate-task / skill-manage refusal gating) is implemented in `smoke_inject.py::classify_test_tool_dispatch` and enforced by `dev_assist_cli.py` smoke subcommand routing. |
| ADR-010 observability shape | Pass. The extended-field JSON schema matches the contract shape; keys are sorted for deterministic output. |

---

## Acceptance Criteria Assessment

| AC | Status | Evidence / rationale |
|---|---|---|
| AC-1 — Smoke-mode marker runtime gate | Pass | `tests/test_smoke_inject_endpoint.py::TestSmokeModeActiveGate` (marker present/absent). `tests/test_dev_assist_cli_smoke.py::TestSmokeRefusalWhenMarkerAbsent` (`inject-message`, `test-tool`, `wait` all refuse with exit code 3 and `SMOKE_MODE_NOT_ENABLED` marker). |
| AC-2 — Per-role loaded-skills set equality | Pass | `tests/test_behaviour_smoke.py::TestAC2LoadedSkillsSetEquality` verifies `classifier` only on `orchestrator`, canonical anchors on all roles, and `hermes_agent` absent everywhere. |
| AC-3 — Dispatch refusal / classify test-tool | Pass | `tests/test_behaviour_smoke.py::TestAC3DispatchRefusal`, `tests/test_smoke_inject_endpoint.py::TestClassifyTestToolDispatch`, `TestTestToolHandler`. `delegate_task` refused on all specialists; `skill_manage` refused on every role including orchestrator. In-loadout positive tools dispatch. |
| AC-4 — Prompt SHA cross-check | Pass | `tests/test_behaviour_smoke.py::TestAC4PromptShaCrossCheck` substantively tests manifest ↔ filesystem SHA equality and tamper-detection diagnostic emission. F-PORT-1 causes the `test_manifest_sha_matches_filesystem_sha_when_untampered` assertion to fail on Windows only; the product logic is correct. |
| AC-5 — Classifier → work-item inject | Pass | `tests/test_behaviour_smoke.py::TestAC5ClassifierToWorkItem` and `tests/test_smoke_inject_endpoint.py::TestWriteInjectedWorkItem` verify the smoke-inject endpoint writes a pending planner-targeted work-item with the synthetic payload. |
| AC-6 — Planner round-trip (N1 claim, N2 result) | Pass | `tests/test_behaviour_smoke.py::TestAC6PlannerRoundtrip` and `tests/test_dev_assist_cli_smoke.py::TestSmokeWaitDiagnostics` verify claim observation within N1 and result/timeout diagnostics. N2 default remains 300 s pending empirical calibration. |
| AC-7 — Smoke install from dist | Informational / deferred | Explicitly deferred via Q-TKT-041-01 (BLOCKED on test VPS provisioning). Routed to Strategic Orchestrator per TKT-041 § 6 + nudge § Mandatory deliverables item 3. Not a fail-blocking omission at iter-1 hand-back. |
| AC-8 — Operator-facing smoke runner | Pass | `scripts/templates/dev-assist-smoke.sh` exists, is executable, accepts `--timeout-claim-s`, `--timeout-result-s`, `--cli`, `--marker-file`, `--db-path`, emits structured JSON, exits 0/1/2 per spec. |
| AC-9 — Secret-leak negative grep | Pass | `tests/test_behaviour_smoke.py::TestAC9SmokeArtefactSecretLeakNegative`, `tests/test_smoke_inject_endpoint.py::TestSmokeFixtureTokenRegex`, and `scripts/verify-self.sh::check_smoke_artefact_secret_leak` all assert zero matches for production token shapes (`xoxb-...`, `ghp_...`, `sk-...`) across the smoke fixture tree and source. The only allowed shape is `^smoke-fixture-token-[a-z0-9]{8}$`. |

---

## Q-TKT Routing Verification

| Question | Routed to | Anchor AC / topic | Status |
|---|---|---|---|
| Q-TKT-041-01 | Strategic Orchestrator | AC-7 empirical N2 calibration | open — BLOCKED on test VPS provisioning |
| Q-TKT-041-02 | Strategic Orchestrator | AUDIT-001-successor: 12th `runtime_check` invariant `smoke_fixture_token_mismatch` | open — routed for successor cycle |
| Q-TKT-041-03 | Strategic Orchestrator | Hermes `gateway.telegram.dry_run` override availability | open — SO ratification needed |
| Q-TKT-041-04 | Strategic Orchestrator (→ Architect) | Reviewer terminal skill discrepancy | open — Architect amendment needed |

All four questions are correctly filed, correctly routed, and do not block
iter-1 code-level audit closure.

---

## Security Assessment

| Control | Status | Evidence |
|---|---|---|
| No secrets in new files | Pass | Source scan of all 22 changed files shows zero live tokens. `tests/fixtures/smoke-mode/smoke_fixture_token.txt` contains exactly `smoke-fixture-token-a1b2c3d4`, which matches the canonical allowed shape. |
| No `.env` or credential files | Pass | None added. |
| Smoke-mode / production mutual exclusion | Pass | `scripts/verify-self.sh::check_smoke_mode_mutual_exclusion` refuses to continue if the smoke marker coexists with a production-shaped `TELEGRAM_BOT_TOKEN`. `install-self.sh --smoke-mode` renders the fixture token. |
| Secret-shape grep in test assertions | Pass | Regex literals (`ghp_[A-Za-z0-9]{36,}`, `^[0-9]+:[A-Za-z0-9_-]{35,}$`, etc.) appear only in test / documentation context, never as live values. |
| Test isolation | Pass | All 50 new tests use local SQLite (`:memory:` or temp files), `unittest.mock`, and `127.0.0.1`-bound HTTP servers. No real PATs, no real Telegram API calls, no network egress. |

---

## Validation Evidence

- **Test collection (exe branch `a7cce85`):** 1291 tests collected.
- **New smoke tests only** (`tests/test_behaviour_smoke.py`, `test_smoke_inject_endpoint.py`, `test_dev_assist_cli_smoke.py`, `test_observability_manager_smoke.py`): 50 collected; 48 passed, 2 failed (F-PORT-1 Windows newline translation).
- **Full suite (exe branch `a7cce85`):** 1175 passed, 112 skipped, 9 failed, 112 subtests passed in ~20.4 s.
- **Pre-existing failure parity (main@9482edb):** The 7 non-smoke failures (`tests/test_runtime_check.py` + `tests/test_runtime_layout_catalog_round_trip.py`) are identical on base and head, confirming zero regression.
- **Net delta:** approximately +50 passing tests, zero new failures attributable to product code, zero new skips.
- `scripts/validate_docs.py`: `Docs validation passed.` (exit 0, run on review branch after reading exe branch files.)

---

## CI / PR-Agent Status

- **GitHub Actions CI for PR #174:** not directly inspectable via `gh` CLI in this environment (unauthenticated). Local validation indicates pytest will be green for the new files on Linux CI; F-PORT-1 is Windows-only.
- **PR-Agent auto-review** (DeepSeek V4 Pro via OmniRoute): pending. Not waited for per NUDGE § Hand-back protocol.

---

## Merge / Ratification Recommendation

**Ratify PR #174 as TKT-041 v0.1.1 iter-1 and merge to `main` after F-PORT-1 is closed.**

F-PORT-1 is test-only and trivial: add `newline=""` to the `Path.write_text` call sites in `tests/test_behaviour_smoke.py` and `tests/test_observability_manager_smoke.py` (three call sites total). This can be done as an additional commit on the existing `exe/tkt-041-audit-003-behaviour-smoke` branch before merge, or as a fast-follow clerical PR — the Reviewer has no preference.

No architecture deviations, no security regressions, no scope violations, and all substantive acceptance criteria are satisfied. The smoke-mode harness is well-isolated, correctly refuses to run without the marker, and preserves the production-secret negative-grep invariant. Q-TKT-041-01 through -04 are correctly filed and routed for post-merge resolution.
