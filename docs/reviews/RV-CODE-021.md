---
id: RV-CODE-021
version: 0.1.0
status: complete
verdict: pass
reviewer_model: kimi-k2.6
created: 2026-05-04
review_target: PR-60
review_type: code
---

# RV-CODE-021: Review of PR #60 — TKT-017 Live Smoke Readiness Harness

## 1. PR Reviewed

- **PR**: [#60](https://github.com/OpenClown-bot/developer-assistant/pull/60)
- **Title**: TKT-017: Implement gated live-smoke readiness harness
- **Branch**: `tkt-017/live-smoke-readiness` → `main`
- **Head SHA**: `d79b1e0`
- **Changed files**: 3
  - `src/developer_assistant/smoke_readiness.py` (new, 466 lines)
  - `tests/test_smoke_readiness.py` (new, 509 lines, 46 test methods)
  - `docs/tickets/TKT-017.md` (Section 10 Execution Log, 39 additions)

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
| validate-docs (head `d79b1e0`) | success | 6s runtime |
| PR-Agent (head `d79b1e0`) | success | Completed; no new findings after iter-2 fix |
| PR-Agent (head `e211d32`) | success | Completed; found draft label issue (resolved in iter-2) |

## 5. Findings

### Finding 1: Resolved — Draft PR label mismatch (PR-Agent, iter-1)

- **Severity**: low (resolved)
- **File**: `src/developer_assistant/smoke_readiness.py:226`
- **Description**: PR-Agent correctly identified that `build_pr_open_request` does not have a `draft` parameter, so the evidence label "(draft)" was misleading. The Executor fixed this in iter-2 by removing the label.
- **Resolution**: Confirmed fixed in `d79b1e0`. Evidence now correctly states the PR URL without "(draft)" suffix. Risk note added to Execution Log documenting that the PR is not a draft and safety relies on "Do not merge" body text and founder acknowledgement gate.

### Finding 2: Observation — Telegram lane does not perform live gateway send

- **Severity**: informational
- **File**: `src/developer_assistant/smoke_readiness.py:234-321`
- **Description**: The Telegram smoke lane validates transport config readiness and performs a sanitized inbound payload construction, but does not send or receive through the live Hermes Telegram gateway. This is consistent with TKT-017 acceptance criteria which requires "verifying live Hermes Telegram gateway readiness through the TKT-015 transport boundary" using "sanitized command names and sanitized chat/user labels." The acceptance criteria do not require a live send/receive cycle; readiness validation is sufficient. A future TKT-011 end-to-end trial would exercise the full live path.
- **Status**: accepted as within scope.

### Finding 3: Observation — GitHub lane branch creation uses SubprocessGitExecutor locally

- **Severity**: informational
- **File**: `src/developer_assistant/smoke_readiness.py:201-210`
- **Description**: The GitHub lane creates a branch using `SubprocessGitExecutor.execute(build_branch_create_command(...))`, which runs `git checkout -b` locally. This requires the executor to be running in a local clone of the target repository. If the smoke is run from a different directory or machine, branch creation would fail. This is consistent with the TKT-014/016 constrained git command design, which operates on a local working directory. The alternative would be to use the GitHub REST API for branch creation (refs/heads), but TKT-014 does not provide a builder for that and TKT-017 non-scope says "do not implement new GitHub workflow behavior beyond a minimal smoke path over existing APIs."
- **Status**: accepted as within scope. Documented as a runtime environment requirement.

## 6. Acceptance Criteria Assessment

| Criterion | Status | Evidence |
|---|---|---|
| Smoke readiness entry point exists, disabled by default unless gate set | PASS | `SMOKE_GITHUB_LIVE` and `SMOKE_TELEGRAM_LIVE` env gates; default off; tested in `TestGateLogic` |
| GitHub smoke uses `PROJECT_GITHUB_PAT` only, rejects `GITHUB_TOKEN`/`GH_TOKEN`/etc | PASS | Uses `load_credential()` from TKT-014 which enforces all credential-source constraints; tested in `TestGitHubSmokeLaneBlocked` |
| GitHub smoke performs minimal live sequence | PASS | Repo register → branch create → PR open → check status → PR metadata → cleanup documentation; all steps tested with mocks |
| GitHub smoke uses TKT-014 constrained `GitCommand` builders and TKT-016 runtime executors | PASS | `build_branch_create_command`, `build_repo_register_request`, `build_pr_open_request`, `build_check_status_request`, `build_pr_metadata_request` + `HttpRESTExecutor`/`SubprocessGitExecutor` |
| Telegram smoke verifies live gateway readiness through TKT-015 boundary | PASS | Uses `validate_transport_config_env` and `sanitize_gateway_payload` from TKT-015; validates config, allowlist, polling preference |
| Telegram smoke enforces TKT-012/015 constraints | PASS | `GATEWAY_ALLOW_ALL_USERS` and `TELEGRAM_ALLOW_ALL_USERS` checked; allowlist/DM pairing required; polling preferred |
| Only sanitized evidence recorded | PASS | `redact_token()` applied to all error text; branch names, sanitized URLs, command names only; tested in `TestNoSecretLeakage` |
| Evidence states pass/blocked/fail per lane | PASS | `SmokeLaneStatus` enum with PASS/BLOCKED/FAIL/SKIPPED; all outcomes tested |
| No secrets, raw IDs, tokens, credentials in artifacts | PASS | Token pattern scan in `TestNoSecretLeakage`; no raw chat IDs in Telegram evidence; env var names only |
| Smoke path does not enable blocked capabilities | PASS | No Hermes bundled skills, no marketplace skills, no project-local plugins, no OpenClaw, no autonomous merge |
| Smoke path does not merge smoke PR | PASS | No merge code in harness; evidence explicitly states "Do not merge"; founder acknowledgement gate documented |
| TKT-011 remains draft | PASS | Execution log confirms; `SmokeReadinessReport.tkt_011_remains_draft = True`; PR body states it |
| `python scripts/validate_docs.py` passes | PASS | Green on CI and local |
| `python -m unittest discover -s tests -p "test_*.py" -v` passes | PASS | 474 tests OK, 1 skipped |

## 7. Security Notes

1. **Secret handling**: All GitHub and Telegram error paths use `redact_token()` from TKT-014. The `TestNoSecretLeakage` class verifies that no `ghp_*`, `github_pat_*`, `gho_*`, `ghs_*`, `ghu_*`, `ghr_*` patterns appear in any evidence or blocker text, including when real token patterns appear in mock exception messages.

2. **Credential source constraints**: The GitHub lane uses `load_credential()` exclusively, which enforces the full TKT-014 credential-source rejection chain: no `~/.git-credentials`, no `GITHUB_TOKEN`/`GH_TOKEN` fallback, no token-bearing remotes. Tested in `test_blocked_when_pat_missing`, `test_blocked_when_git_credentials_exists`, `test_blocked_when_github_token_collision`.

3. **Raw identifier handling**: Telegram lane uses `sanitize_gateway_payload` which maps raw chat/user IDs to sanitized labels (`chat:founder`, `user:founder`). The `HermesGatewayPayload.validate()` method rejects raw numeric IDs. No raw IDs appear in any evidence output. Tested in `test_blocked_evidence_no_raw_ids` and `test_pass_evidence_no_raw_ids`.

4. **Fail-closed for blocked lanes**: When `PROJECT_GITHUB_PAT` is absent → `BLOCKED`. When `TELEGRAM_BOT_TOKEN` is absent → `BLOCKED`. When allow-all modes are set → `BLOCKED`. No bypass path exists.

5. **No autonomous merge**: The harness contains no merge code. Evidence explicitly records `no_autonomous_merge: true` and `founder_ack_required_before_merge: true`.

6. **No unsafe GitHub commands**: All git operations go through `build_branch_create_command()` which uses TKT-014 constrained command validation. No force push, hard reset, branch deletion, or token-bearing remotes.

7. **PR-Agent ticket analysis**: PR-Agent produced a finding about the draft label mismatch, which was resolved. The `require_ticket_analysis_review = true` setting from PR #59 was active. PR-Agent output was specific and actionable (not purely generic), confirming the configuration improvement.

## 8. PR-Agent Assessment

PR-Agent produced one actionable finding in iter-1 (draft label mismatch) which the Executor resolved in iter-2. This is a useful signal — more specific than the generic output seen in some earlier PRs — and confirms that the `require_ticket_analysis_review = true` tuning from PR #59 is producing better review signal. No residual PR-Agent findings on the final head `d79b1e0`.

## 9. Final Verdict

**pass**

The PR satisfies all TKT-017 acceptance criteria. Both smoke lanes are correctly gated, fail-closed when credentials are unavailable, produce only sanitized evidence, and do not enable any blocked capabilities. The PR-Agent finding was resolved. No secrets, raw identifiers, autonomous merge paths, or unsafe GitHub commands were found. TKT-011 remains draft and was not executed. Founder acknowledgement before merge remains required.
