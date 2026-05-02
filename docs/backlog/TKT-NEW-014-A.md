---
id: TKT-NEW-014-A
version: 0.1.0
status: backlog
source_tkt: TKT-014
created: 2026-05-02
---

# TKT-NEW-014-A: Clarify GH_TOKEN Collision Error Handling

## Context

PR-Agent on TKT-014 Executor PR #32 noted that `load_credential()` documents `GITHUB_TOKEN` and `GH_TOKEN` fallback rejection, but only emits the special CI-collision message for `GITHUB_TOKEN` when `PROJECT_GITHUB_PAT` is absent.

The security property is preserved: `GH_TOKEN` is not consumed, and `load_credential()` still raises when `PROJECT_GITHUB_PAT` is missing. This follow-up is for operator clarity and documentation/code alignment.

## Proposed Scope

- Consider adding an explicit `GH_TOKEN` branch to the CI-collision warning path in `load_credential()`.
- Add or update tests so `GH_TOKEN` alone raises a message that clearly states CI auto-injected GitHub tokens are not accepted.
- Keep `PROJECT_GITHUB_PAT` as the only approved v0.1 credential environment variable unless a later architecture decision changes it.

## Priority

Low. Defer until TKT-008 integration or a GitHub workflow cleanup pass.
