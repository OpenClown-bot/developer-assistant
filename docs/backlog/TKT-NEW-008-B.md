---
id: TKT-NEW-008-B
version: 0.1.0
status: backlog
source_tkt: TKT-008
created: 2026-05-04
---

# TKT-NEW-008-B: Add Sanitized Live GitHub Smoke Test

## Context

TKT-008 used mocked REST and git executors. That satisfied the ticket scope, but no live GitHub smoke test has verified repository registration, branch creation, PR opening, check-status reading, and PR metadata reading against real GitHub API behavior.

## Proposed Scope

- Add an optional smoke-test path that runs only when an explicit non-secret environment gate is set.
- Use `PROJECT_GITHUB_PAT` only, never `GITHUB_TOKEN`, `GH_TOKEN`, `~/.git-credentials`, token-bearing remotes, committed config, or CLI arguments.
- Print sanitized repository/PR URLs and never print token values or raw credentials.
- Document manual cleanup expectations for any branch or PR created by the smoke test.

## Priority

Medium before first production GitHub automation trial.
