---
id: RV-CODE-014
version: 0.2.0
status: complete
verdict: pass_with_changes
---

# RV-CODE-014: Review of PR #32 — TKT-014 Project-Specific GitHub Workflow Capability

> **Note on ID reuse**: `RV-CODE-014` was previously used for the TKT-012/PR #22 review artifact in an earlier iteration of project bookkeeping. This artifact now reviews PR #32 for TKT-014, per the current cycle's assignment.

## 1. PR Reviewed

- **PR**: [#32](https://github.com/OpenClown-bot/developer-assistant/pull/32)
- **Title**: Implement project-specific GitHub workflow capability (TKT-014)
- **Branch**: `tkt-014/project-github-workflow` → `main`
- **Head SHA**: `fbe81d92e8ca95390ae0181be100b3659f5abd45`
- **Changed files**: 3
  - `src/developer_assistant/github_workflow.py` (new, 620 lines)
  - `tests/test_github_workflow.py` (new, 435 lines)
  - `docs/tickets/TKT-014.md` (Section 10 Execution Log only)

## 2. Ticket Reviewed

- **Ticket**: `TKT-014@0.1.0` — Implement Project-Specific GitHub Workflow Capability

## 3. Required Context Reviewed

- `AGENTS.md`
- `CONTRIBUTING.md`
- `docs/prompts/reviewer.md`
- `docs/tickets/TKT-014.md`
- `docs/tickets/TKT-008.md`
- `docs/tickets/TKT-012.md`
- `docs/architecture/ARCH-001.md`
- `docs/architecture/HERMES-RUNTIME-CONTRACT.md`
- `docs/architecture/HERMES-SKILL-ALLOWLIST.md`
- `docs/architecture/OPERATIONAL-STATE-STORE.md`
- `docs/architecture/adr/ADR-001-platform-foundation.md`
- `docs/architecture/adr/ADR-002-repository-state.md`
- `docs/architecture/adr/ADR-003-plugin-supply-chain.md`
- `docs/reviews/RV-SPEC-001.md` (including Finding 1: Env Var Collision Risk)
- PR #32 diff, body, checks, and PR-Agent comments

## 4. CI Status

| Check | Conclusion | Evidence |
|---|---|---|
| `validate-docs` (Docs CI) | **SUCCESS** | Completed on PR HEAD |
| `Run PR Agent on every pull request` | **SUCCESS** | Completed on PR HEAD |
| PR-Agent inline /improve comments | **Present** | 3 findings posted as PR review comment block |

## 5. Scope And Write-Zone Assessment

| File | Expected Scope | Assessment |
|---|---|---|
| `src/developer_assistant/github_workflow.py` | TKT-014 runtime source | **Pass**. New module implementing the project-specific GitHub workflow capability. No Hermes bundled skills enabled. No autonomous merges implemented. |
| `tests/test_github_workflow.py` | TKT-014 tests | **Pass**. 70 new tests covering all acceptance-criteria categories. No live GitHub API calls. No secrets committed. |
| `docs/tickets/TKT-014.md` | Section 10 Execution Log only | **Pass**. Diff is append-only to Execution Log; frontmatter, status, and Sections 1–9 are unchanged. |

No PRD, architecture, ADR, review artifact, prompt, CI workflow, unrelated ticket, or allowlist modifications were made.

## 6. Acceptance Criteria Assessment

| # | Criterion | Status | Evidence |
|---|---|---|---|---|
| 1 | Module exists for repo create/register, branch create, commit/push, PR open/update, check-status read, PR metadata read | **Pass** | `build_repo_create_request`, `build_repo_register_request`, `build_branch_create_command`, `build_commit_push_command`, `build_pr_open_request`, `build_pr_update_request`, `build_check_status_request`, `build_pr_metadata_request` all present. |
| 2 | Uses GitHub REST API + constrained git; no Hermes bundled skills | **Pass** | Module constructs `GitHubRESTRequest` and `GitCommand` dataclasses. No Hermes skill imports. No `github-pr-workflow`, `github-issues`, or `github-auth` usage. |
| 3 | Credentials accepted only from approved runtime source; rejects `~/.git-credentials`, token-in-remote URLs, committed config, CLI args | **Pass** | `load_credential` reads only `PROJECT_GITHUB_PAT`. Separate rejection utilities (`reject_credential_source`, `check_for_git_credentials_file`, `check_for_token_in_remote`) exist for other sources. See Finding 1 for API-design note. |
| 4 | Documents required token scopes | **Pass** | `_REQUIRED_TOKEN_SCOPES` list and PR body both document scopes. `issues:write` correctly noted as not implemented. |
| 5 | Merge operations require founder acknowledgement; disabled by default | **Pass** | `build_merge_command` raises `MergeBlockedError` unless `founder_acknowledgement=True`. Tests assert error messages mention "v0.1" and "founder". |
| 6 | Dangerous git ops blocked (force push, hard reset, branch deletion, token-bearing remotes) | **Pass** | `_BLOCKED_GIT_FLAGS`, `_BLOCKED_PHRASES`, `_validate_branch_name`, and `check_for_token_in_remote` enforce constraints. Tests cover all listed operations. |
| 7 | Tests cover credential-source rejection, token redaction, REST construction, constrained git commands, merge-gate behavior | **Pass** | 70 tests across 7 test classes. 12 credential-source tests, 9 redaction tests, 14 REST tests, 19 git-constraint tests, 6 merge-gate tests, 8 env-var-collision tests, 2 URL-redaction tests. |
| 8 | `python scripts/validate_docs.py` passes | **Pass** | CI and local validation both pass. |
| 9 | `python -m unittest discover -s tests -p "test_*.py" -v` passes | **Pass** | Executor reports 110 tests OK (40 existing + 70 new). CI green. |

## 7. Findings

### Low — Credential Rejection API Is Fragmented

- **Location**: `src/developer_assistant/github_workflow.py:142–212`
- **Description**: `load_credential()` loads the token from `PROJECT_GITHUB_PAT` only, but it does not automatically invoke `check_for_git_credentials_file`, `check_for_token_in_remote`, or `reject_credential_source`. The rejection functions are separate utilities that callers must invoke manually. If a future caller (e.g., TKT-008 runtime adapter) only calls `load_credential()`, the other source validations may be skipped.
- **Impact**: Non-blocking for this ticket. The functions exist and are tested. TKT-008 integration should ensure all relevant validators are called at the appropriate lifecycle points.
- **Recommendation**: Consider a single `validate_runtime_credential_state()` helper that composes all checks, or document the caller responsibility explicitly in module docstrings before TKT-008 integration.

### Low — Symlink Bypass in `check_for_git_credentials_file`

- **Location**: `src/developer_assistant/github_workflow.py:201–212`
- **Description**: The function uses `os.path.abspath()` rather than `os.path.realpath()`. If a symlink chain is involved, the path comparison may fail to match `~/.git-credentials`.
- **Impact**: Edge-case path resolution gap. In typical usage the function is called with the literal `~/.git-credentials` path.
- **Recommendation**: Replace `os.path.abspath(path)` with `os.path.realpath(path)` in a future cleanup.

### Info — Unused `_BLOCKED_GIT_SUBCOMMANDS` Set

- **Location**: `src/developer_assistant/github_workflow.py:59–61`
- **Description**: `_BLOCKED_GIT_SUBCOMMANDS` includes `"push"` with a comment that it is allowed only through the constrained builder, but `validate_git_args()` never checks this set. The flag/phrase blockers already prevent dangerous push variants.
- **Impact**: Dead code / misleading documentation only.
- **Recommendation**: Either enforce the subcommand blocklist in `validate_git_args()`, or remove the unused constant and rely on the constrained builder functions (`build_commit_push_command`) to produce safe push commands.

## 8. Security Notes

### Credential Security

- **Approved source**: `PROJECT_GITHUB_PAT` environment variable only. Distinct from GitHub Actions auto-injected `GITHUB_TOKEN` and `GH_TOKEN`.
- **Token redaction**: `_TOKEN_PATTERNS` covers `ghp_`, `github_pat_`, `gho_`, `ghu_`, `ghs_`, `ghr_` prefixes. `redact_token()` and `_redact_url()` are applied to command output, errors, and URL strings.
- **No committed secrets**: Test fixtures use `FAKE_TEST_TOKEN_NOT_REAL_1234567890` and `FAKE_PAT_NOT_REAL_AAA...`, which do not match real GitHub token prefixes.
- **Rejected sources**: `~/.git-credentials`, token-in-remote URLs, committed config, and CLI arguments are all rejected by dedicated utilities with tests.

### Git Command Safety

- Shell metacharacters (`;`, `&`, `|`, `` ` ``, `$`) are blocked in branch names.
- Force push, hard reset, branch deletion, and force-with-lease are blocked by flag and phrase matchers.
- URL remotes are rejected in favor of named remotes, and token-bearing URLs trigger `CredentialSourceError`.

### GitHub REST Request Safety

- `GitHubRESTRequest` stores headers without `Authorization`. The real token is injected only via `with_auth(token)`, which returns a new dict.
- `repr()` of the dataclass would not leak the token because the Authorization header is never added to the stored headers.
- API version header `X-GitHub-Api-Version: 2022-11-28` is present on all requests.
- No live network calls in tests.

### Merge Gate

- `build_merge_command` defaults to `founder_acknowledgement=False` and raises `MergeBlockedError`.
- Explicit `founder_acknowledgement=True` is required to construct a merge command.
- Behavior aligns with `ARCH-001` §9 and `HERMES-RUNTIME-CONTRACT.md` §9/§11.

## 9. RV-SPEC-001 Env-Var Collision Finding Assessment

**Finding from RV-SPEC-001**: Low — Env Var Collision Risk in TKT-014 Credential Source.

**Status**: **RESOLVED**.

- PR #32 uses the distinct environment variable `PROJECT_GITHUB_PAT` instead of `GITHUB_TOKEN` or `GH_TOKEN`.
- `TestEnvVarCollisionHandling` (8 tests) explicitly proves:
  - `load_credential` returns `PROJECT_GITHUB_PAT` even when `GITHUB_TOKEN` is present.
  - `GITHUB_TOKEN` alone and `GH_TOKEN` alone both raise `CredentialSourceError`.
  - Empty `PROJECT_GITHUB_PAT` with present `GITHUB_TOKEN` still raises.
- PR body documents the env var choice and the rationale (avoiding GitHub Actions auto-injection collision).
- Required fine-grained PAT scopes are documented in PR body and module docstring.

## 10. Test Observations

- Test count matches claim: 70 new tests across 7 classes.
- All tests use mocked or constructed objects; no live HTTP or git subprocess calls to GitHub.
- Edge cases covered: special characters in owner/repo names (via `quote`), partial PR update bodies, empty credential env vars, shell metacharacters in branch names, dry-run execution mode.
- One minor gap noted: no test for `check_for_git_credentials_file` with a symlink path. This is a Low-severity edge case aligned with Finding 2 above.

## 11. Final Verdict

`pass_with_changes`

PR #32 satisfies TKT-014 scope, stays within the allowed write zone, introduces no secrets, correctly resolves the RV-SPEC-001 env-var collision risk, gates merges by founder acknowledgement, blocks dangerous git operations, and provides 70 tests with mocked GitHub interactions. CI is fully green.

The three Low/Info findings (fragmented credential-rejection API, symlink bypass edge case, unused blocked-subcommands set) are non-blocking and can be addressed in a follow-up cleanup or during TKT-008 integration. No iter-2 is required for correctness or security.

## 12. Recommended Next Steps

1. **Executor iter-2 (optional)**: Address the three Low/Info findings above if convenient before merge; otherwise they may be deferred to TKT-008 integration.
2. **Founder acknowledgement**: Required before merge per `ARCH-001` §9.
3. **Ticket Orchestrator audit**: PR #32 is ready for TO audit pass-1 and Strategic Orchestrator ratification.
