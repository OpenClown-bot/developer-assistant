---
id: TKT-NEW-008-A
version: 0.1.0
status: backlog
source_tkt: TKT-008
created: 2026-05-04
---

# TKT-NEW-008-A: Add Idempotent Branch And PR Creation

## Context

TKT-008 delivered the GitHub PR integration logic layer. Reviewer and PR-Agent both noted that `create_branch_and_open_pr` is not retry-idempotent: if branch creation succeeds but PR opening fails, a retry can attempt duplicate branch or PR creation.

## Proposed Scope

- Add explicit branch/PR idempotency checks before live runtime retry behavior depends on this path.
- Define whether the integration should reuse an existing branch/PR for the same ticket or fail with a clear operator-visible error.
- Preserve the TKT-014 constrained git command builders and `PROJECT_GITHUB_PAT` credential path.
- Add unit tests for retry-after-partial-failure behavior.

## Priority

High before unattended live runtime retries.
