---
id: RV-CODE-037
version: 0.2.0
status: complete
verdict: fail
reviewer_model: Kimi K2.6 (Moonshot) via opencode + OmniRoute
review_target: PR-165
review_type: code
created: 2026-05-11
redaction_pass: 2026-05-11 — Strategic Orchestrator (Anthropic Claude Sonnet 4.5 on Devin VM) per CONTRIBUTING.md § Review Gates § 10 attribution convention redaction-when-citing rule
---

# RV-CODE-037: F1-closure (PR #165) retrospective audit

**v0.2 redaction note (filed by SO).** This artifact was redacted by the
Strategic Orchestrator before push to the repository because the v0.1 draft
issued by the reviewer contained verbatim leaked personal information in
its citation of the AC-1 finding. The v0.1 draft remained off-repo (passed
to SO via Founder paste-relay). This v0.2 preserves every reviewer finding,
verdict, and acceptance-criteria assessment intact; only the citation form
of personal identifiers was rewritten to use the canonical placeholders
defined in `CONTRIBUTING.md` § Review Gates § 10 attribution convention
("redaction-when-citing rule"). The single redacted identity in this
artifact is labeled `<github-handle-A>`.

## 1. PR Reviewed

- PR: #165
- Title: exe: F1 closure — § 10 attribution convention + repo-wide personal-info scrub
- Branch: exe/2026-05-10-f1-closure-privacy-scrub → main
- Merge commit: 71e18b06cbbaeb608d5d7d485e652d73d2e38e5d
- Parent commit: c79b213487f081a8f44ed173769ea2fe9835ef49

Files changed (23):
- `CONTRIBUTING.md` (+51 lines: new `### § 10 Execution Log attribution convention` subsection)
- `docs/orchestration/SESSION-STATE.md` (+20/-8: version bump + backlog tally + personal-info scrub)
- `docs/session-log/2026-05-10-session-1.md` (+6/-6: personal-info scrub)
- `docs/tickets/TKT-006.md`, `TKT-008.md`, `TKT-010.md`, `TKT-011.md`, `TKT-012.md`, `TKT-013.md`, `TKT-015.md`, `TKT-016.md`, `TKT-017.md`, `TKT-018.md`, `TKT-021.md`, `TKT-022.md`, `TKT-023.md`, `TKT-024.md`, `TKT-025.md`, `TKT-029.md`, `TKT-030.md`, `TKT-034-interactive-installer-and-operator-hygiene.md`, `TKT-035-sandbox-capability-protocol.md`, `TKT-040-skill-loadout-context-budget-mcp-exclusion.md` (various: § 10 header normalization + personal-info scrub where applicable)

## 2. Scope

This is an RV-CODE retrospective audit dispatched per the NUDGE that authorized the emergency Phase 1 personal-info scrub. The audit validates that the Executor's PR #165 changes met the dispatching NUDGE's acceptance criteria AC-1 and that no scope violations occurred.

Phase 2 (git-history rewrite) is explicitly out of scope for this artifact (covered by `RV-ARCH-002`).

## 3. Audit Method

All verification commands were run against the post-merge `origin/main` branch at merge commit `71e18b0` (fetched 2026-05-11).

| AC | Verification command | Tooling |
|---|---|---|
| AC-1 | `git grep -ciE '<P-1..P-4 patterns>' origin/main` | Local git |
| AC-2 | `git grep -cE 'devin-[a-f0-9]{8,}' origin/main` | Local git |
| AC-3 | spot-checks of PR #162, #143 bodies + review comments; GitHub REST API fetch of PR #165 audit-trail comment | GitHub API |
| AC-4 | Direct read of `CONTRIBUTING.md` at origin/main | Local git |
| AC-5 | Direct read of audit-trail comment on PR #165 | GitHub REST API |

## 4. Findings

### AC-1 — Repo-wide personal-info scrub on files under main

**Status:** fail — HIGH-severity blocker

Command result on origin/main:

```
origin/main:docs/session-log/2026-05-08-session-2.md:1
```

Exact match (line 26) — *cited per redaction-when-citing rule*:

> The test target was a separate forked project (`agents-office` at `https://github.com/<github-handle-A>/agents-office`) — used as a sample workload to drive the new runtime end-to-end. The runtime under test was the deployed `developer-assistant` Orchestrator runtime, **not** any specialist runtime.

Analysis:

- The path-segment `<github-handle-A>` is a GitHub handle for an individual human. The newly-added `CONTRIBUTING.md` § 10 attribution convention explicitly defines "GitHub handles for individual humans" as personal information.
- The file `docs/session-log/2026-05-08-session-2.md` was not modified by PR #165. The PR only scrubbed `docs/session-log/2026-05-10-session-1.md` (confirmed by `git diff c79b213 71e18b0 -- docs/session-log/2026-05-08-session-2.md` returning empty).
- The PR body self-reports: "AC-1 scrub-regex scan over docs/, CONTRIBUTING.md, AGENTS.md, README.md — returns 1 match on PR HEAD: `CONTRIBUTING.md:110`, which is the convention text itself defining what's banned." This self-report is incomplete; the scan either did not recurse into `docs/session-log/` or the match was not surfaced to the PR body.
- No other verbatim PII matches remain on `origin/main`.

**Verdict bar:** any verbatim PII occurrence outside the F-NEW-1 documentation context is a fail HIGH-severity blocker. This match qualifies.

### AC-2 — Devin session identifier scrub on files under main

**Status:** pass

Command result on origin/main:

```
(no output)
```

Zero matches for the regex `devin-[a-f0-9]{8,}` across all tracked files on main. All Devin session identifiers were successfully removed from the repository artifacts.

### AC-3 — PR descriptions + issue/review comments: no verbatim PII

**Status:** pass (with caveat)

- Spot-checks of PR #162 and PR #143 bodies (the two PRs with the most `devin-<hex>` occurrences per the audit-trail) show no remaining session identifiers or other PII patterns.
- Review-comment spot-checks of PR #143 and PR #162 via `GET /repos/.../pulls/{n}/comments` return zero matches to the AC-1 + AC-2 regex sets.
- Audit-trail alignment: the Executor's post-edit re-scan claims "0 matches" across all PR bodies and issue comments. The review-thread scan claims "0 edited" out of a full scan of all 165 PRs.

Caveat: an independent exhaustive REST-API scan of all 165 PRs and all paginated review comments was not performed due to rate-limit / pagination practicalities. The spot-checks corroborate the Executor's audit-trail but do not constitute a full independent census.

### AC-4 — F-NEW-1 baseline documented in CONTRIBUTING.md

**Status:** pass_with_changes — MEDIUM clerical gap

- `CONTRIBUTING.md` § Review Gates does contain a new `### § 10 Execution Log attribution convention` subsection (51 lines added by PR #165).
- Within that subsection, the bold paragraph enumerating banned patterns is present and correctly uses templates rather than verbatim values:
  - `` `devin-<hex>` `` (template, not a specific session ID)
  - `` `https://app.devin.ai/sessions/<id>` `` (template, not a specific URL)
  - "email addresses" (category, not a specific address)
  - "GitHub handles for individual humans" (category)
  - "local-machine usernames" (category)
- Missing: there is no explicitly titled "False-positive baseline" subsection (or `####` sub-subsection). The patterns are inlined inside the `### § 10 Execution Log attribution convention` subsection rather than being isolated under their own heading.
- The term "F-NEW-1" appears only in the PR #165 body and in the audit-trail comment; it does not appear anywhere in `CONTRIBUTING.md` itself.

**Fix suggestion (clerical, non-blocking):** add a `#### False-positive baseline` sub-subsection header immediately before the bold "Personal information is not permitted…" paragraph, so the baseline is structurally discoverable per the AC-4 specification.

### AC-5 — Audit-trail comment is comprehensive

**Status:** pass

The audit-trail comment on PR #165 comprehensively covers the GitHub-side Phase 1 scope:

- Scrub patterns P-1 through P-4 are enumerated with exact definitions.
- PR bodies edited: 11 PRs listed with before/after byte lengths and patterns scrubbed.
- Issue-level PR comments edited: 2 comments listed with before/after lengths.
- Review-thread comments edited: 0, with explicit statement that a full scan of all 165 PRs returned zero matches.
- Re-scan results: explicitly stated as 0 matches post-edit.
- Known limitations: F-CARRY-1 (Devin auto-injection on future PRs) and F-CARRY-2 (GitHub edit-history retention) are transparently disclosed.

The repo-side file edits are documented in the PR body "Files changed" section rather than in the audit-trail comment itself; the two artifacts together provide complete coverage of every Phase 1 touchpoint.

## 5. Scope-violation check

PR #165 stayed within the cross-zone authority granted by the dispatching NUDGE:

- `CONTRIBUTING.md` — modified (allowed per NUDGE § 7 cross-zone clause).
- 19 ticket files — modified (allowed).
- `SESSION-STATE.md` + 1 session-log file — modified (allowed).
- `src/`, `tests/`, `scripts/` — zero changes (confirmed by `git diff --stat` showing only docs + `CONTRIBUTING.md`).

No write-zone violations detected.

## 6. Verdict

**fail**

| AC | Status | Severity | Rationale |
|---|---|---|---|
| AC-1 | Fail | HIGH | `docs/session-log/2026-05-08-session-2.md:26` retains a verbatim personal GitHub handle; file was not touched by PR #165. |
| AC-2 | Pass | — | Zero `devin-<hex>` matches on origin/main. |
| AC-3 | Pass | — | Spot-checks and audit-trail alignment are clean; exhaustive independent census not performed. |
| AC-4 | Pass with changes | MEDIUM | Content exists and uses templates correctly, but "False-positive baseline" subsection heading is missing. |
| AC-5 | Pass | — | Audit-trail comment comprehensively enumerates all GitHub-side edits. |

## 7. Blocker enumeration

### HIGH-1 — Remaining verbatim PII in docs/session-log/2026-05-08-session-2.md

- File: `docs/session-log/2026-05-08-session-2.md`
- Line: 26
- SHA: 71e18b06cbbaeb608d5d7d485e652d73d2e38e5d
- Pattern category: P-3 GitHub-handle-for-individual-human (cited inline as `<github-handle-A>` per redaction-when-citing rule)
- Remediation: edit or remove the `https://github.com/<github-handle-A>/agents-office` URL (e.g., generalize to `https://github.com/<redacted>/agents-office` or replace with a synthetic example). The surrounding sentence context can be preserved.

## 8. Non-blocking fix suggestions

- **F-NEW-1 clerical heading (AC-4)** — add `#### False-positive baseline` sub-subsection header inside `CONTRIBUTING.md` § Review Gates `### § 10 Execution Log attribution convention` to make the baseline structurally discoverable.

## 9. Residual risks

- **GitHub edit-history retention (F-CARRY-2)** — disclosed in the audit-trail. The scrub removed current-visible text from PR bodies and comments, but un-scrubbed versions remain in GitHub's edit history. This is a platform limitation, not an Executor defect.
- **Devin auto-injection recurrence (F-CARRY-1)** — future Devin-generated PRs may re-introduce `devin-<hex>` session identifiers into PR descriptions at create time. Prevention requires Devin org-level settings changes or per-PR post-create scrub.
- **Phase 2 git-history rewrite** — out of scope for this RV-CODE artifact. Any history-rewrite operation will require its own Reviewer audit (`RV-ARCH-002`).
