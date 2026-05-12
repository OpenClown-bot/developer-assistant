---
id: RV-CODE-039
version: 0.1.0
status: complete
verdict: pass
ticket: TKT-041@0.1.1
branch: rv/rv-code-039-tkt-041-audit-003-smoke-iter-2-3-verify
branch_head: 6d0780e
reviewer_model: Kimi K2.6 (Moonshot) via opencode + OmniRoute
reviewer_role: cross-family witness — lightweight iter-2/iter-3 verify
predecessor_review: RV-CODE-038
target_pr: "#177"
target_head_at_review_time: baeb179 (per Reviewer's local clone state; see SO addendum below)
target_head_on_origin: 2344db7 (HEAD of exe/tkt-041-iter-2-f-port-1-ac-7 at SO-pass-2 ratify time)
base_commit: 5de9b50
date: 2026-05-12
---

# RV-CODE-039: TKT-041 v0.1.1 AUDIT-003 iter-2 + iter-3 verify (lightweight cross-family witness — Moonshot Kimi K2.6)

## Verdict: pass

## Hand-back summary

**Review artifact path:** `docs/reviews/RV-CODE-039.md`
**Branch:** `rv/rv-code-039-tkt-041-audit-003-smoke-iter-2-3-verify`
**Branch HEAD SHA:** `6d0780e`
**Final verdict:** `pass`

## Findings summary

| Finding | Severity | Status | Notes |
|---|---|---|---|
| F-PORT-1 (`Path.write_text` newline translation breaks SHA-256 on Windows) | Medium | CLOSED | 3 `newline=""` additions verified; 20 smoke tests pass on Linux. |
| AC-7 empirical N2 calibration | — | DEFERRED | No VPS access; Q-TKT-041-01 § 7 blocker note filed. Not a new regression. |
| Iter-3 commits absent (`3908b8d`, `2344db7`) | — | NOTED | Expected AC-7 measurement fill + RCA do not exist on the PR branch. |

Zero new Medium or Higher findings introduced by the iter-2 delta.

## AC-7 satisfaction judgement

**Not satisfied in substance, correctly deferred.**

`Q-TKT-041-01.md` § 3 measurement tables remain TBD in every cell. No empirical smoke runs were conducted on a VPS. The expected iter-3 commits (`3908b8d` for measurement fill, `2344db7` for RCA) are absent from `exe/tkt-041-iter-2-f-port-1-ac-7`; only the iter-2 commit `baeb179` exists.

However, AC-7 was already recorded as informational / deferred in predecessor review RV-CODE-038 with the same external blocker (test VPS provisioning). The iter-2 delta does not regress this disposition, nor does it close it. The PR correctly documents the blocker rather than fabricating data.

## Follow-up Q-TKT recommendations for SO routing

1. **Provision test VPS** (Hetzner CX32 / CPX31, Ubuntu 22.04 LTS, 4 vCPU / 8 GB / 80 GB) or dispatch an Executor runtime with SSH credentials to complete AC-7 empirical N2 calibration (≥ 3 smoke runs, fill `Q-TKT-041-01` § 3 tables). **Urgency: High** — blocks AC-7 closure.

2. **Verify `llm_calls` row creation on first real Planner smoke run.** `OBSERVABILITY-CONTRACT.md` v0.1.2 § 10 (FR-OBS-07) mandates that *every* LLM call writes a row to `llm_calls`. If the empirical calibration run shows zero `llm_calls` rows for the Planner work item, file a Q-TKT against `llm_client_instrumentation.py` / `ObservabilityManager.record_llm_call()` wiring as a potential contract violation. **Urgency: Medium.**

3. **Route install-script latent defects** to an AUDIT-002-successor or TKT-020 patch: Ubuntu version assertion, `system_prompt.path` validation at render time, `ExecStartPre state.db` initialization, and smoke-inject systemd unit template. These were surfaced as manual VPS remediations in `TKT-041 § 10 iter-2` but are outside the AUDIT-003 scope. **Urgency: Medium.**

4. **Update PR #177 body** to note that the iter-3 RCA bonus (`2344db7`) and AC-7 measurement fill (`3908b8d`) were not delivered on this branch. **Urgency: Low** (clerical).

## Merge recommendation

Ratify iter-2 F-PORT-1 closure and merge to main. The sole RV-CODE-038 finding is resolved. AC-7 deferral is unchanged and cleanly documented. The absent iter-3 deliverables can land in a fast-follow PR once the SO provisions VPS access.

---

## SO addendum (added during clerical-land — not part of Kimi's original artifact)

This addendum is **not** part of the Reviewer's substantive review. It is appended by the SO during clerical-land to document a Reviewer-side discrepancy that the SO must surface for correct downstream interpretation. The Reviewer's findings, verdict, and recommendations above are preserved byte-equal to the hand-back content (as paste-relayed by Founder; see § Reconstruction note below).

### Stale-clone discrepancy (Reviewer error, not Founder error)

The Reviewer's claim that "iter-3 commits (`3908b8d`, `2344db7`) are absent from the PR branch" is **factually incorrect against `origin/exe/tkt-041-iter-2-f-port-1-ac-7` at the time of the Reviewer's hand-back**. The branch HEAD on origin at hand-back time was `2344db7` (the second iter-3 commit), with both iter-3 commits as ancestors:

```
2344db7  exe: TKT-041 iter-3 — OmniRoute Qwen 3.6 Plus jitter root-cause analysis  ← HEAD
3908b8d  exe: TKT-041 iter-3 — AC-7 empirical N2 calibration on VPS + Q-TKT-041-01 resolution
baeb179  exe: TKT-041 v0.1.1 iter-2 — F-PORT-1 closure + AC-7 empirical N2 fill
5de9b50  so: clerical land — RV-CODE-038 (#176)  ← base
```

`git merge-base --is-ancestor 3908b8d origin/exe/tkt-041-iter-2-f-port-1-ac-7` returns true. `Q-TKT-041-01.md` on the origin HEAD has filled measurement tables (median total round-trip 460 300 ms, p95 792 000 ms, 3 raw runs entered), an iter-3 § 8 "VPS calibration results" section, and a § Root-cause analysis subsection.

The most likely root cause is that the Reviewer's local clone did not run `git fetch origin` after the initial clone, or the clone happened against a stale mirror that did not yet contain the iter-3 push (`3908b8d` was pushed at 2026-05-12 17:51 UTC; `2344db7` at 18:15 UTC; the Reviewer dispatch followed shortly after). The Reviewer did not re-verify with `git fetch` before final read.

### Consequences

- **Findings table row 3 ("Iter-3 commits absent")** is incorrect as stated. The SO supersedes this row: iter-3 commits ARE on the branch at hand-back time. SO does not delete or rewrite the Reviewer's text (byte-equality preserved); SO supersedes it explicitly here.

- **Q-TKT recommendation #1 ("Provision test VPS … to complete AC-7")** is partially superseded. The VPS *was* provisioned (Hetzner CX32 Ubuntu 22.04, per `TKT-041 § 10 iter-3` entry by the Executor on commit `3908b8d`). What remains valid in this recommendation:
  - The empirical N2 calibration *was* performed but produced only 2 of 3 successful runs (Run 3 hit `claim_timeout > 300 s`).
  - The `llm_calls.latency_ms` column is `TBD` in the raw runs table because Hermes does not currently write to the `llm_calls` table (see Q-TKT rec #2 below — this is the *correct* recommendation that survives unchanged).
  - The harness ran in degraded mode (Orchestrator unit could not start because Telegram gateway rejected the fixture token; smoke-inject endpoint on port 8186 bypassed the gateway via direct `operational.db` write).

- **Q-TKT recommendation #4 ("Update PR #177 body to note that iter-3 RCA bonus and AC-7 measurement fill were not delivered on this branch")** is fully superseded. Both *were* delivered on this branch. The PR body itself, however, was written at iter-2 hand-back and does not yet reflect the iter-3 deliverables — that part of the clerical observation is correct. SO will route a `git_pr action=update` to refresh PR #177's body after AC-7 cross-family witness completes (see RV-CODE-040 below).

- **Merge recommendation ("Ratify iter-2 F-PORT-1 closure and merge to main; iter-3 deliverables can land in a fast-follow PR once the SO provisions VPS access")** is partially superseded. The iter-3 deliverables are *already on this PR branch*, not on a future fast-follow. Therefore the merge of PR #177 must happen *after* a cross-family Reviewer witness on the iter-3 deliverables, not before, to preserve the AGENTS.md cross-family Reviewer-on-Executor witness invariant for every commit landing on `main`. PR-Agent (DeepSeek V4 Pro) reviewed `3908b8d` and gave a positive verdict ("🎫 Fully compliant, 🧪 PR contains tests, 🔒 No security concerns, ⚡ No major issues detected"), but PR-Agent is defined as an *optional second reviewer* (AGENTS.md), not a substitute for the primary cross-family witness.

### Forward path chosen by SO

**Path A** — minimal extra cycle, maximum process discipline:

1. **This clerical-land PR** (you are reading it) lands RV-CODE-039 byte-equal onto `main` with this SO addendum.

2. **RV-CODE-040 corrective NUDGE** dispatches the Reviewer (Kimi K2.6 Moonshot, fresh tab) to perform an iter-3 verify-only review with explicit `git fetch origin` + 3-commit-check abort condition. RV-CODE-040 scope:
   - AC-7 measurement quality judgement (2/3 successful runs, `llm_calls.latency_ms` gap, degraded harness mode)
   - RCA scope compliance (`2344db7` contained to Executor write-zone? N2 = 900 s recommendation overstep?)
   - `llm_calls` empty-table contract violation assessment against `OBSERVABILITY-CONTRACT.md` v0.1.2 § 10 (FR-OBS-07)
   - Five install-script defects observation set (TTY non-interactive, Ubuntu version detection, runtime config skills mismatch, `system_prompt.path` rendering, ExecStartPre state.db, missing smoke-inject systemd unit) — surface as Q-TKT routing recommendation

3. **After RV-CODE-040 pass:** final clerical-land PR bundling RV-CODE-040.md + TKT-041 § 10 SO closure entries + frontmatter `ready → done` + SESSION-STATE bump → MERGE-SAFE NOW sign-off on PR #177 (+ this RV-CODE-039 clerical-land if not yet merged).

### Lesson codification (auto-cold session-log targets)

1. **Reviewer git-fetch-before-review convention.** The reviewer prompt (`docs/prompts/reviewer.md`) should require an explicit `git fetch origin && git log origin/<target-tkt-branch> -5` step in the REPO BOOTSTRAP section, with abort-if-fewer-than-expected-commits as a stop condition. Will be proposed as a follow-up reviewer.md amendment in the closure clerical-PR.

2. **SO addendum pattern** is precedent. When a Reviewer artifact contains factual errors against origin state that SO discovers in pass-2 ratify, SO does *not* edit the Reviewer's substantive text; SO appends an explicit SO addendum block (this one) preserving byte-equality of the original. This pattern joins F-CARRY-2 (whitelisted identity bypass) and Path B (paste-relay extraction) as established SO clerical-land precedents.

### Reconstruction note

The substantive Reviewer content above (Findings summary, AC-7 satisfaction judgement, Q-TKT recommendations, Merge recommendation, hand-back metadata) was extracted from a Founder paste-relay (three screenshots of the Kimi opencode hand-back panel). Tables were re-pipe-formatted by SO (the screenshots show rendered HTML/dark-mode panel output; markdown pipes are not visible in the rendered form). Body prose is byte-equal to the visible screenshot text. Frontmatter YAML and the mechanical PR/Ticket/CI header section were composed by SO using the public origin state (commits, branch SHAs, PR numbers) and the standard `docs/prompts/reviewer.md` § Output template. If the Reviewer's local artifact on `rv/rv-code-039-tkt-041-audit-003-smoke-iter-2-3-verify` (HEAD `6d0780e`) contains additional sections not visible in the screenshots, those sections will be appended in a follow-up commit on `so/audit-003-rv-code-039-land` once the Founder paste-relays them.
