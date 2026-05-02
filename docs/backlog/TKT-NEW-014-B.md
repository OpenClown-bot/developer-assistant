---
id: TKT-NEW-014-B
version: 0.1.0
status: backlog
source_tkt: TKT-014
created: 2026-05-02
---

# TKT-NEW-014-B: Decide Credential Helper Public API Shape

## Context

PR-Agent on TKT-014 Executor PR #32 noted that `reject_credential_source()` and `check_for_git_credentials_file()` are defined and tested public utilities but are not all invoked by `load_credential()`.

Reviewer PR #33 clarified that `load_credential()` remains the primary credential entry point and enforces the required TKT-014 safety properties inline. Separate helper calls are appropriate only when a future lifecycle has an explicit reason to inspect a credential source independently of token loading.

## Proposed Scope

- During TKT-008 integration, decide whether these helpers should remain public utilities, be composed behind a new validation helper, or be made private/removed.
- Preserve the TKT-014 security properties: no `~/.git-credentials`, no token-bearing remotes, no committed config or CLI token source, and `PROJECT_GITHUB_PAT` as the only approved runtime credential env var.
- Update tests and docs to match the chosen API shape.

## Priority

Low. Evaluate when TKT-008 wires the GitHub workflow module into runtime orchestration.
