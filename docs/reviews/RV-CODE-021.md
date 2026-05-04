---
id: RV-CODE-021
version: 0.2.0
status: complete
verdict: pass
reviewer_model: kimi-k2.6
created: 2026-05-04
updated: 2026-05-04
review_target: PR-60
review_type: code
---

# RV-CODE-021: Review of PR #60 — TKT-017 Live Smoke Readiness Harness (Iter-3 Final)

## 1. PR Reviewed

- **PR**: [#60](https://github.com/OpenClown-bot/developer-assistant/pull/60)
- **Title**: TKT-017: Implement gated live-smoke readiness harness
- **Branch**: `tkt-017/live-smoke-readiness` → `main`
- **Head SHA**: `559b544ac0bc83c263877af0fa385525de856b3c`
- **Changed files**: 3
  - `src/developer_assistant/smoke_readiness.py` (new, 529 lines)
  - `tests/test_smoke_readiness.py` (new, 677 lines, 59 test methods)
  - `docs/tickets/TKT-017.md` (Section 10 Execution Log, iter-1/iter-2/iter-3 additions)

## 2. Ticket Reviewed

- **Ticket**: `docs/tickets/TKT-017.md` @ `0.1.0`
- **Status at review time**: `ready`
- **Source backlog**: `TKT-NEW-008-B`
- **Scope alignment**: The PR stays entirely within TKT-017 scope. It implements a gated live-smoke readiness harness with two lanes (GitHub, Telegram) using existing TKT-014/016/015 APIs. It does not execute TKT-011, does not implement idempotent retry behavior from TKT-NEW-008-A, does not implement state persistence from TKT-NEW-008-C, does not enable Hermes bundled skills, does not enable autonomous merge, and does not open public endpoints or change credential scopes.

## 3. Architecture / ADR References

- **Architecture**: `docs/architecture/ARCH-001.md` @ `0.2.0`
- **Relevant contracts**:
  - `docs/architecture/HERMES-RUNTIME-CONTRACT.md` @ `0.2.0`
  - `docs/architecture/HERMES-SKILL-ALLOWLIST.md` @ `0.1.0`
  - `docs/architecture/OPERATIONAL-STATE-STORE.md` @ `0.2.0`
- **Relevant ADRs**:
  - `ADR-001-platform-foundation.md` @ `0.2.0`
  - `ADR-002-repository-state.md` @ `0.2.0`
  - `ADR-003-plugin-supply-chain.md` @ `0.2.0`
- **Dependencies reviewed**:
  - `TKT-006.md` @ `0.1.0` (done)
  - `TKT-008.md` @ `0.3.0` (done)
  - `TKT-011.md` @ `0.1.0` (draft, correctly not executed)
  - `TKT-014.md` @ `0.1.0` (done)
  - `TKT-015.md` @ `0.1.0` (done)
  - `TKT-016.md` @ `0.1.0` (done)
  - `TKT-NEW-008-A.md` @ `0.1.0` (backlog, correctly excluded)
  - `TKT-NEW-008-B.md` @ `0.1.0` (backlog, source of TKT-017)
  - `TKT-NEW-008-C.md` @ `0.1.0` (backlog, correctly excluded)

## 4. CI Status

| Check | Conclusion | Evidence |
|---|---|---|
| validate-docs (head `559b544`) | success | 6s runtime |
| PR-Agent (head `559b544`) | success | Completed; no findings |
| PR-Agent (head `d79b1e0`) | success | Completed; no new findings after iter-2 fix |
| PR-Agent (head `e211d32`) | success | Completed; found draft label issue (resolved in iter-2) |
| Local unittest (head `559b544`) | success | 488 tests OK, 1 skipped |
| Local docs validation (head `559b544`) | success | Passed |

## 5. SO Blocker Resolution (Iter-3)

The Strategic Orchestrator identified four blockers on earlier iterations. This section confirms each is resolved in the final head `559b544`.

### Blocker 1: GitHub smoke branch name was deterministic instead of unique — RESOLVED

- **File**: `src/developer_assistant/smoke_readiness.py:129-130`, `src/developer_assistant/smoke_readiness.py:162-173`
- **Evidence**:
  - `_generate_branch_suffix()` returns `uuid.uuid4().hex[:8]` (8-character lowercase hex).
  - `GitHubSmokeLane.__init__` accepts an injectable `branch_suffix` parameter.
  - Default branch suffix is generated per-instance; two instances always produce different suffixes.
  - Branch name format: `smoke/tkt-017-live-check-<suffix>`.
- **Test coverage**: `TestGitHubBranchUniqueness` (5 tests):
  - `test_different_instances_generate_different_branches` confirms suffix uniqueness.
  - `test_branch_suffix_injectable` confirms testability.
  - `test_branch_suffix_no_secret_in_branch_name` confirms no token patterns in generated names.
- **Reviewer confirmation**: PASS.

### Blocker 2: GitHub smoke lane could return PASS when PR open failed — RESOLVED

- **File**: `src/developer_assistant/smoke_readiness.py:243-249`
- **Evidence**:
  - `RuntimeRESTError` during PR open now returns `SmokeLaneResult(status=BLOCKED)` immediately.
  - Evidence contains `"PR open failed; "` prefix followed by prior successful steps.
  - Token in exception is redacted via `redact_token()` before being stored in `blocker`.
- **Test coverage**: `TestGitHubSmokeLanePass.test_blocked_on_pr_open_failure`:
  - Asserts `status == BLOCKED`.
  - Asserts no `ghp_` leak in `evidence` or `blocker`.
  - Asserts `"PR open failed"` is present in evidence.
- **Reviewer confirmation**: PASS.

### Blocker 3: Telegram lane could return PASS from config-only checks without live Hermes Telegram gateway proof — RESOLVED

- **File**: `src/developer_assistant/smoke_readiness.py:119`, `src/developer_assistant/smoke_readiness.py:312-317`, `src/developer_assistant/smoke_readiness.py:450-497`
- **Evidence**:
  - `TelegramSmokeLane` now requires an injectable `live_gateway_proof: LiveGatewayProofCallback` for a PASS verdict.
  - Without the callback, config-only readiness returns `BLOCKED` with `live_gateway_proof: not provided` in evidence.
  - The callback receives only sanitized metadata (command names, `chat:founder`, `user:founder`, transport mode).
  - Callback success → `PASS`; callback failure → `BLOCKED`; callback exception → `FAIL`.
  - All callback results are redacted via `redact_token()` before recording.
- **Test coverage**: `TestTelegramLiveGatewayProof` (7 tests):
  - `test_config_only_without_proof_returns_blocked` confirms BLOCKED without callback.
  - `test_live_proof_success_returns_pass` confirms PASS with successful callback.
  - `test_live_proof_failure_returns_blocked` confirms BLOCKED on callback failure.
  - `test_live_proof_exception_returns_fail` confirms FAIL on callback exception.
  - `test_live_proof_failure_no_secret_leak` and `test_live_proof_exception_no_secret_leak` confirm redaction.
  - `test_live_proof_receives_only_sanitized_input` confirms callback input contains no tokens or raw IDs.
- **Reviewer confirmation**: PASS.

### Blocker 4: docs/tickets/TKT-017.md Section 10 line counts were stale — RESOLVED

- **File**: `docs/tickets/TKT-017.md`
- **Evidence**:
  - Iter-1 line counts corrected from `~310/~340` to `466/509`.
  - Iter-3 entry added with accurate counts (`529 lines` for `smoke_readiness.py`, `677 lines` for `test_smoke_readiness.py`, `59 test methods`).
- **Reviewer confirmation**: PASS.

## 6. Findings

### Finding 1: Resolved — Draft PR label mismatch (PR-Agent, iter-1)

- **Severity**: low (resolved)
- **File**: `src/developer_assistant/smoke_readiness.py:226`
- **Description**: PR-Agent correctly identified that `build_pr_open_request` does not have a `draft` parameter, so the evidence label "(draft)" was misleading. The Executor fixed this in iter-2 by removing the label.
- **Resolution**: Confirmed fixed in `d79b1e0`. Evidence now correctly states the PR URL without "(draft)" suffix. Risk note added to Execution Log documenting that the PR is not a draft and safety relies on "Do not merge" body text and founder acknowledgement gate.

### Finding 2: Resolved — Telegram lane now requires live gateway proof for PASS (SO Blocker 3, iter-3)

- **Severity**: medium (resolved in iter-3)
- **File**: `src/developer_assistant/smoke_readiness.py:450-497`
- **Description**: In iter-1/iter-2, the Telegram lane returned PASS after config-only checks, which could give a false impression of live gateway readiness. In iter-3, `TelegramSmokeLane` requires an injectable `live_gateway_proof` callback for PASS. Without it, the result is BLOCKED.
- **Resolution**: Confirmed fixed in `559b544`. The callback design is clean: it receives only sanitized labels, returns a dict with `success`/`evidence`/`error`, and all results are redacted. Test coverage is thorough (7 tests in `TestTelegramLiveGatewayProof`).

### Finding 3: Observation — GitHub lane branch creation uses SubprocessGitExecutor locally

- **Severity**: informational
- **File**: `src/developer_assistant/smoke_readiness.py:212-224`
- **Description**: The GitHub lane creates a branch using `SubprocessGitExecutor.execute(build_branch_create_command(...))`, which runs `git checkout -b` locally. This requires the executor to be running in a local clone of the target repository. If the smoke is run from a different directory or machine, branch creation would fail. This is consistent with the TKT-014/016 constrained git command design, which operates on a local working directory. The alternative would be to use the GitHub REST API for branch creation (refs/heads), but TKT-014 does not provide a builder for that and TKT-017 non-scope says "do not implement new GitHub workflow behavior beyond a minimal smoke path over existing APIs."
- **Status**: accepted as within scope. Documented as a runtime environment requirement.

## 7. Acceptance Criteria Assessment

| Criterion | Status | Evidence |
|---|---|---|
| Smoke readiness entry point exists, disabled by default unless gate set | PASS | `SMOKE_GITHUB_LIVE` and `SMOKE_TELEGRAM_LIVE` env gates; default off; tested in `TestGateLogic` |
| GitHub smoke uses `PROJECT_GITHUB_PAT` only, rejects `GITHUB_TOKEN`/`GH_TOKEN`/etc | PASS | Uses `load_credential()` from TKT-014 which enforces all credential-source constraints; tested in `TestGitHubSmokeLaneBlocked` |
| GitHub smoke performs minimal live sequence | PASS | Repo register → branch create → PR open → check status → PR metadata → cleanup documentation; all steps tested with mocks |
| GitHub smoke uses TKT-014 constrained `GitCommand` builders and TKT-016 runtime executors | PASS | `build_branch_create_command`, `build_repo_register_request`, `build_pr_open_request`, `build_check_status_request`, `build_pr_metadata_request` + `HttpRESTExecutor`/`SubprocessGitExecutor` |
| Telegram smoke verifies live gateway readiness through TKT-015 boundary | PASS | `validate_transport_config_env`, `sanitize_gateway_payload`, and `live_gateway_proof` callback from TKT-015; config validation + proof callback required for PASS |
| Telegram smoke enforces TKT-012/015 constraints | PASS | `GATEWAY_ALLOW_ALL_USERS` and `TELEGRAM_ALLOW_ALL_USERS` checked; allowlist/DM pairing required; polling preferred |
| Only sanitized evidence recorded | PASS | `redact_token()` applied to all error text; branch names, sanitized URLs, command names only; tested in `TestNoSecretLeakage` and `TestTelegramLiveGatewayProof` |
| Evidence states pass/blocked/fail per lane | PASS | `SmokeLaneStatus` enum with PASS/BLOCKED/FAIL/SKIPPED; all outcomes tested |
| No secrets, raw IDs, tokens, credentials in artifacts | PASS | Token pattern scan in `TestNoSecretLeakage`; no raw chat IDs in Telegram evidence; env var names only |
| Smoke path does not enable blocked capabilities | PASS | No Hermes bundled skills, no marketplace skills, no project-local plugins, no OpenClaw, no autonomous merge |
| Smoke path does not merge smoke PR | PASS | No merge code in harness; evidence explicitly states "Do not merge"; founder acknowledgement gate documented |
| TKT-011 remains draft | PASS | Execution log confirms; `SmokeReadinessReport.tkt_011_remains_draft = True`; PR body states it |
| `python scripts/validate_docs.py` passes | PASS | Green on CI and local |
| `python -m unittest discover -s tests -p "test_*.py" -v` passes | PASS | 488 tests OK, 1 skipped |

## 8. Security Notes

1. **Secret handling**: All GitHub and Telegram error paths use `redact_token()` from TKT-014. The `TestNoSecretLeakage` class verifies that no `ghp_*`, `github_pat_*`, `gho_*`, `ghs_*`, `ghu_*`, `ghr_*` patterns appear in any evidence or blocker text, including when real token patterns appear in mock exception messages.

2. **Credential source constraints**: The GitHub lane uses `load_credential()` exclusively, which enforces the full TKT-014 credential-source rejection chain: no `~/.git-credentials`, no `GITHUB_TOKEN`/`GH_TOKEN` fallback, no token-bearing remotes. Tested in `test_blocked_when_pat_missing`, `test_blocked_when_git_credentials_exists`, `test_blocked_when_github_token_collision`.

3. **Raw identifier handling**: Telegram lane uses `sanitize_gateway_payload` which maps raw chat/user IDs to sanitized labels (`chat:founder`, `user:founder`). The `HermesGatewayPayload.validate()` method rejects raw numeric IDs. No raw IDs appear in any evidence output. Tested in `test_blocked_evidence_no_raw_ids` and `test_pass_evidence_no_raw_ids`.

4. **Fail-closed for blocked lanes**: When `PROJECT_GITHUB_PAT` is absent → `BLOCKED`. When `TELEGRAM_BOT_TOKEN` is absent → `BLOCKED`. When allow-all modes are set → `BLOCKED`. When `live_gateway_proof` is absent → `BLOCKED`. When PR open fails → `BLOCKED`. No bypass path exists.

5. **No autonomous merge**: The harness contains no merge code. Evidence explicitly records `no_autonomous_merge: true` and `founder_ack_required_before_merge: true`.

6. **No unsafe GitHub commands**: All git operations go through `build_branch_create_command()` which uses TKT-014 constrained command validation. No force push, hard reset, branch deletion, or token-bearing remotes.

7. **Branch uniqueness prevents collision**: `_generate_branch_suffix()` uses `uuid.uuid4().hex[:8]`, producing unique branch names per run. The prefix `smoke/tkt-017-live-check-` is consistent for cleanup scripts.

8. **PR-Agent ticket analysis**: PR-Agent produced one actionable finding in iter-1 (draft label mismatch) which the Executor resolved in iter-2. No residual PR-Agent findings on the final head `559b544`.

## 9. PR-Agent Assessment

PR-Agent produced one actionable finding in iter-1 (draft label mismatch) which the Executor resolved in iter-2. This is a useful signal — more specific than the generic output seen in some earlier PRs — and confirms that the `require_ticket_analysis_review = true` tuning from PR #59 is producing better review signal. No residual PR-Agent findings on the final head `559b544`.

## 10. Final Verdict

**pass**

The PR satisfies all TKT-017 acceptance criteria. Both smoke lanes are correctly gated, fail-closed when credentials are unavailable, produce only sanitized evidence, and do not enable any blocked capabilities. All four Strategic Orchestrator blockers identified in earlier iterations are fully resolved in commit `559b544ac0bc83c263877af0fa385525de856b3c`:

1. GitHub smoke branch names are now unique via `uuid.uuid4().hex[:8]` suffix.
2. GitHub smoke lane returns `BLOCKED` (not `PASS`) when PR open fails.
3. Telegram smoke lane requires a `live_gateway_proof` callback for `PASS`; config-only readiness returns `BLOCKED`.
4. `docs/tickets/TKT-017.md` Section 10 line counts are accurate and iter-3 is fully documented.

No secrets, raw identifiers, autonomous merge paths, or unsafe GitHub commands were found. TKT-011 remains draft and was not executed. Founder acknowledgement before merge remains required.

**PR #60 head `559b544ac0bc83c263877af0fa385525de856b3c` is approved for merge from the Reviewer perspective.**
