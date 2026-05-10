---
id: TKT-NEW-devin-secret-ui-byte-caching
version: 0.1.0
status: backlog
source_tkt: TKT-035
created: 2026-05-10
---

# TKT-NEW: Devin secret-update UI suspected byte-caching of stale PAT

## Context

Surfaceable platform observation from the TKT-035 implementation cycle (Executor DeepSeek V4 Pro on Founder VPS + Reviewer Moonshot Kimi K2.6 on Founder PC) — **NOT a project code issue**.

Both the Executor and the Reviewer sessions, when invoking `gh auth status` / `git push` against `OpenClown-bot/developer-assistant`, hit `HTTP 401 Bad credentials` with the `GITHUB_TOKEN_DEVELOPER_ASSISTANT` env-injected secret. The Executor reported the secret carried a **32-character non-PAT token** with sha256 prefix `22dc386e` and that three round-trips through the Devin secret-update UI saved the byte-identical value each time. Push only succeeded after the Founder pasted a fresh `github_pat_…` directly in chat as a temporary override.

The same symptom recurred two cycle-steps later on the Reviewer session: `gh auth status` reported both the env `GITHUB_TOKEN` and the keyring token as invalid; Reviewer could not push `rv/code-036-tkt-035`. Founder again pasted a fresh temporary PAT, Reviewer self-pushed, Founder deleted the temp token from the environment.

This is the **second** recurrence in two consecutive TKT cycles (TKT-034 iter-2 Architect mini-cycle Q-AMEND-2 in 2026-05-09 logs documented a similar `HTTP 401` symptom against the same secret in a fresh Devin session, but at that time the repo-scoped fallback at `/run/repo_secrets/<repo>/env.secrets` carrying a 40-char `ghp_…` succeeded and the workaround did not require operator intervention).

## Suspected root cause

Devin secret-injection layer appears to byte-cache a stale value in some session-bootstrap path:
- The Founder updates the secret in the Devin settings UI → expected-current value (a fresh `github_pat_…`).
- The Devin VM bootstrap loads `GITHUB_TOKEN_DEVELOPER_ASSISTANT` env var → observed-actual value (a stale 32-char non-PAT token).
- Three save round-trips through the UI did not flush the cache.
- Manual paste-in-chat as session-level override is the only known mitigation.

This is consistent with either (a) a write-through cache miss in the secret store, or (b) the snapshot baking layer pinning a stale value that survives UI updates until the snapshot is rebuilt.

## Proposed scope

- **Bisect the secret-injection path** in Devin's session-bootstrap layer to identify whether the staleness is at the VM-snapshot level or at the runtime env-injection level.
- **Operator-side mitigation:** document a "if 401: paste fresh PAT in chat" runbook step in the runtime-specialist NUDGE convention (already de-facto practiced; should be formalized in `docs/prompts/executor.md` and `docs/prompts/reviewer.md` § Auth bootstrap).
- **Platform-side ask:** raise with Devin platform engineering to investigate whether secret-update UI changes are flushing through to the bootstrap-time env injection.

## Priority

Medium. Not blocking any cycle (manual mitigation works), but recurring (two consecutive cycles) and operator-time-costly (each occurrence costs one extra Founder paste-relay round-trip per pipeline-session-restart).

## References

- `docs/orchestration/SESSION-STATE.md` § Current Phase → AUDIT-002 spec-amendment closure paragraph (Q-AMEND-2 mention, 2026-05-09)
- `docs/orchestration/SESSION-STATE.md` § Current Phase → TKT-035 implementation cycle CLOSED paragraph (F-PA2-4 surfaceable, 2026-05-10)
- TKT-035 Executor hand-back message body (2026-05-10) — Executor self-flagged the observation
