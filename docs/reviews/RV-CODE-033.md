---
id: RV-CODE-033
version: 0.2.0
status: review_pending
ticket_ref: TKT-033@0.2.0
pr_ref: OpenClown-bot/developer-assistant#128
head_sha: c1949f3b28ddbf94d175a6554b75bedc72907418
verdict: pass_with_changes
iter_history:
  - iteration: 1
    head_sha: a022a3f9ba3cc10ed456d1b16f572f92f153b8d2
    verdict: pass_with_changes
  - iteration: 2
    head_sha: c1949f3b28ddbf94d175a6554b75bedc72907418
    verdict: pass_with_changes
---

# RV-CODE-033: Review of PR #128 — TKT-033 runtime_check enforcement at systemd boot

## 1. Verdict

**pass_with_changes** — the implementation satisfies the boot-enforcement, prompt-manifest, marker, baseline, scope, and secrets portions of TKT-033, but AC-3's `delegate_task_callable` / `skill_manage_callable` production path is still config-level rather than an actual Hermes call-attempt gating check; Executor iter-2 is needed before merge-safe signoff.

## 2. Findings

1. **delegate_task / skill_manage runtime-call invariants are config-level in production, not actual round-trip call attempts**
   - **severity:** medium
   - **ac_anchor:** AC-3, AC-4
   - **spec_anchor:** `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:20-23`; `src/developer_assistant/runtime_check.py:334-354`; `src/developer_assistant/runtime_check.py:494-506`; `tests/test_runtime_check.py:655-711`
   - **observation:** `_default_delegate_task_caller()` and `_default_skill_manage_caller()` return "gated" from `_config_asserts_skill_gating(config_path, ...)`, so the production `check_runtime()` path verifies only rendered config assertions (`skills.<name>.enabled=false` or `plugins.disabled`) unless a test injects a callable. The tests exercise callable failure through injected lambdas and default pass through the config-level helper.
   - **expected:** TKT-033 component B requires an attempted invocation of `delegate_task` / `skill_manage` to fail at runtime, "not just" be absent or disabled in config, with a round-trip actual call attempt that receives the Hermes gating error.
   - **suggestion:** Replace the production default callers with a safe Hermes capability invocation seam that actually attempts the disabled operation and asserts the expected gating error, or explicitly bounce the design back to Architect/SO if a pre-start `ExecStartPre` process cannot perform that round trip. Add offline tests that mock that production invocation seam, rather than proving only config parsing.
   - **disposition:** must-fix

2. **Fallback selection for injected callers uses truthiness instead of an explicit `None` guard**
   - **severity:** low
   - **ac_anchor:** AC-3
   - **spec_anchor:** `src/developer_assistant/runtime_check.py:494-504`
   - **observation:** `delegate_caller = delegate_task_caller or _default_delegate_task_caller` and `skill_caller = skill_manage_caller or _default_skill_manage_caller` silently fall back when a supplied callable-like object is falsy.
   - **expected:** Injection seams should distinguish "not supplied" from "supplied but falsy" explicitly.
   - **suggestion:** Use `delegate_task_caller if delegate_task_caller is not None else _default_delegate_task_caller` and the analogous `skill_manage_caller` expression.
   - **disposition:** nice-to-have

3. **Execution-log modified-file count is clerically wrong**
   - **severity:** nit
   - **ac_anchor:** AC-8
   - **spec_anchor:** `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:317-329`
   - **observation:** The heading says "11 allowed; 9 actually touched", but the numbered list identifies 10 touched files plus `scripts/verify-self.sh` as not touched.
   - **expected:** The heading should match the reviewed diff: 10 of 11 allowed paths were actually touched.
   - **suggestion:** Change the heading to "11 allowed; 10 actually touched" in the Executor branch or a follow-up clerical SO PR.
   - **disposition:** nice-to-have

**AC-6 environmental variance note:** On this Reviewer VM, the mandatory single-VM re-run produced `Ran 1084` on main and `Ran 1112` on the Executor head, with the same 13 FAIL/ERROR lines and zero added FAIL/ERROR rows. These absolute counts differ from Executor and SO runs, but the required relative invariant holds: `1112 - 1084 = 28`, and the sorted FAIL/ERROR diff has no added lines.

## 3. AC matrix

| AC | Result | Evidence |
|---|---|---|
| AC-1 | pass | Re-verified the four branch-cut observations on main `c97ed39`: five configs render; `check_runtime()` exists with the seven TKT-021 invariant raise paths; no unit has `ExecStartPre=runtime_check`; all five units use `Restart=always` without `RestartPreventExitStatus=`. |
| AC-2 | pass | All five Executor-head service templates contain `ExecStartPre=/usr/bin/python3 -m developer_assistant.runtime_check`, `Environment=PYTHONPATH=/srv/devassist/repo/src`, `Restart=always`, and `RestartPreventExitStatus=78`. |
| AC-3 | partial | Prompt-manifest missing/unreadable and SHA mismatch hard-fail, and manifest rendering is folded into `render_runtime_configs()` before unit rendering; however `delegate_task_callable` / `skill_manage_callable` production defaults are config-level, not actual Hermes call attempts. |
| AC-4 | partial | The branch adds 22 `test_runtime_check.py` tests and 6 `test_self_deployment_scripts.py` tests, including marker checks, manifest tests, and unit-template parsing over all roles; the tests do not cover a true production Hermes round-trip for the two callable invariants. |
| AC-5 | pass | `RUNTIME_CHECK_INVARIANTS` is a public frozenset with the canonical 11 names; all 11 named invariant raise paths emit `RUNTIME_CHECK_FAILED:<role>:<invariant_name>` immediately before preserving the existing exception classes. |
| AC-6 | pass | Reviewer re-run on one VM: main `Ran 1084`, Executor `Ran 1112`; delta is exactly 28 tests; sorted FAIL/ERROR lists have zero added lines. |
| AC-7 | pass | Regex scan over the modified runtime-check, install, template, test, and ticket files found zero real token, PAT, API-key, or production-hostname matches. |
| AC-8 | pass | This RV-CODE artifact is the second PR in the two-PR pipeline; no merge path is enabled and Founder acknowledgement remains required. |

## 4. PR-Agent triage

| PR-Agent item | Reviewer verdict | Disposition |
|---|---|---|
| Possible Issue: `delegate_task_caller or _default_delegate_task_caller` and analogous skill fallback | accept as low-severity robustness finding | Recorded as Finding 2; not independently merge-blocking, but can be fixed during iter-2. |
| Scope Discipline: PR #128 allegedly follows the scope of "ticket #127" | reject as false-positive | PR-Agent matched the previous clerical PR number rather than TKT-033. Actual PR #128 scope is 10 modified files, all within TKT-033 § 5 allowed files. |

## 5. Hard rules check

- [x] Reviewer write-zone respected: this PR adds only `docs/reviews/RV-CODE-033.md`.
- [x] Implementation PR branch `exe/tkt-033-runtime-check-enforcement` was read only; no push or edit was made to it.
- [x] No code in `src/`, `tests/`, `scripts/`, `docs/architecture/`, `docs/architecture/adr/`, `docs/tickets/§§1-9`, `docs/prompts/`, or `docs/prd/` was modified by the Reviewer.
- [x] No merge was performed or enabled.
- [x] No force-push to `main` was performed.
- [x] No git hooks were skipped; no `--no-verify` / `--no-gpg-sign` was used.
- [x] No commit was amended.
- [x] No git command was run with `sudo`; git config was not changed.
- [x] No `git add .` was used; staging is limited to this review artifact.
- [x] No file containing a real secret was committed.
- [x] Executor PR #128 checks were inspected and were both `completed / success` before this verdict.
- [x] Cross-account GitHub auth was bootstrapped via `GH_TOKEN` and verified against `OpenClown-bot/developer-assistant`.

## 6. Recommendation

Iter-2 needed; gaps listed above. The implementation is close, and AC-1/2/5/6/7/8 plus the prompt-manifest portion of AC-3 are review-pass, but PR #128 is not merge-safe until the two callable invariants perform an actual Hermes gating round trip (or the spec is explicitly revised by the proper role) and the iter-2 delta is re-reviewed.

## 7. Iter-2 verification

### 7.1 Iter-2 verdict

**pass_with_changes** — Executor iter-2 closes Finding 2 and Finding 3, and it replaces the iter-1 config-introspection helper with an attempted import/call path. However, the new AC-3 helper still does not prove the spec-required Hermes gating error: it accepts module absence as "gated", accepts missing entry points as "gated", catches every `BaseException` as "gated", and calls a guessed `config_path=` signature that is not the documented upstream Hermes tool API for either `delegate_task` or `skill_manage`. AC-3 and AC-4 therefore remain **partial**, and PR #128 still needs Executor iter-3 before merge-safe signoff.

### 7.2 Iter-2 findings

1. **Broad-catch round-trip conflates absence, signature errors, and actual Hermes gating**
   - **severity:** medium
   - **ac_anchor:** AC-3, AC-4
   - **spec_anchor:** `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md:20-23`; `src/developer_assistant/runtime_check.py:304-349`; `tests/test_runtime_check.py:723-849`
   - **observation:** `_attempt_hermes_skill_round_trip()` returns `"gated"` when `importlib.import_module("hermes.skills.<name>")` raises `ImportError`, when the imported module has no recognised entry point, when `Skill()` construction fails, or when the resolved callable raises any `BaseException`. The new tests explicitly codify absence and missing-entry-point as successful gating branches.
   - **expected:** TKT-033 component B requires an attempted invocation to fail at runtime, "not just" be absent from the loaded skill list, and requires asserting that Hermes returns the gating error. That is narrower than "anything raised or missing means gated".
   - **suggestion:** Resolve the real Hermes tool registry/handler and assert a specific disabled-tool/gating response or exception. Treat import failure, missing entry point, constructor failure, and argument-shape `TypeError` as runtime-check inconclusive/failing, not as AC-3 pass.
   - **disposition:** must-fix

2. **The production call shape appears guessed and is not the upstream Hermes tool API**
   - **severity:** medium
   - **ac_anchor:** AC-3, AC-4
   - **spec_anchor:** `src/developer_assistant/runtime_check.py:345-348`; upstream `tools/delegate_tool.py` and `tools/skill_manager_tool.py` API evidence
   - **observation:** The helper dispatches `invoke(config_path=config_path)`. The current upstream Hermes source exposes `delegate_task(goal=None, context=None, toolsets=None, tasks=None, max_iterations=None, acp_command=None, acp_args=None, role=None, parent_agent=None)`, registered through `registry.register(name="delegate_task", handler=lambda args, **kw: delegate_task(..., parent_agent=kw.get("parent_agent")))`. It exposes `skill_manage(action, name, content=None, category=None, file_path=None, file_content=None, old_string=None, new_string=None, replace_all=False, absorbed_into=None)`, registered through `registry.register(name="skill_manage", handler=lambda args, **kw: skill_manage(...))`. Neither signature accepts `config_path=`.
   - **expected:** The round trip must exercise the same runtime path that would execute the tool and observe the disabled/gating response. A signature mismatch caught as `BaseException` is not evidence that Hermes enforced the disabled skill; it is a practical no-op false pass.
   - **suggestion:** Call through the Hermes registry with realistic tool arguments and the runtime's disabled-tool configuration, or add an adapter with documented signature evidence from the pinned Hermes version. Add tests where a fake real-shape handler raises the specific gating error and where a wrong keyword `TypeError` fails the check.
   - **disposition:** must-fix

3. **Finding 2 closure verified**
   - **severity:** none
   - **ac_anchor:** AC-3
   - **observation:** `check_runtime()` now selects injected `delegate_task_caller` and `skill_manage_caller` with explicit `is not None` guards, and `TestCallerInjectionFallback` covers falsy-but-callable injection for both seams.
   - **disposition:** closed

4. **Finding 3 closure verified**
   - **severity:** none
   - **ac_anchor:** AC-8
   - **observation:** The iter-1 execution-log heading was corrected from "9 actually touched" to "10 actually touched"; the numbered list remains consistent.
   - **disposition:** closed

### 7.3 Iter-2 AC matrix delta

| AC | Iter-1 | Iter-2 | Evidence |
|---|---:|---:|---|
| AC-1 | pass | pass | Delta from `a022a3f..c1949f3` touches only `runtime_check.py`, `test_runtime_check.py`, and the TKT-033 ticket execution log; no branch-cut observations changed. |
| AC-2 | pass | pass | `git diff a022a3f..c1949f3 -- scripts/templates/` is empty; service-template enforcement remains at iter-1 pass state. |
| AC-3 | partial | partial | The default callers now attempt an import/call, but the helper accepts absence and all exceptions as gated and does not assert the Hermes gating error or a verified real call signature. |
| AC-4 | partial | partial | The 8 new tests are offline-safe and cover helper branches plus falsy injection. They do not cover a Hermes-specific gating exception class/response, and the success-path fakes accept `**kwargs`, masking the `config_path=` signature risk. |
| AC-5 | pass | pass | The canonical 11 invariant names and abort exit code 78 remain present; the iter-2 diff does not alter the legacy TKT-021 raise-side exception paths. |
| AC-6 | pass | pass | Reconstructed same-VM baseline because `/tmp/rv_iter1_post_fail_error_list.txt` was absent: `a022a3f` ran 1112 tests with 13 FAIL/ERROR lines; `c1949f3` ran 1120 tests with the same 13 FAIL/ERROR lines; sorted diff is empty. |
| AC-7 | pass | pass | Secret/hostname regex scan across the iter-2 modified file contents found zero matches. |
| AC-8 | pass | pass | Two-PR pipeline preserved: PR #128 remains the Executor PR; this update is a new commit on existing RV-CODE PR #129, with no merge or implementation-branch push by Reviewer. |

### 7.4 SO-surfaced flags triage

| Flag | Reviewer triage | Rationale |
|---|---|---|
| Flag-1 — spec-text deviation | iter-3 bounce | Accepted. ImportError/no-entry-point/constructor failure are absence or adapter failures, not proof that an attempted runtime invocation returned Hermes' gating error. Catching `BaseException` also treats unrelated defects as successful gating. |
| Flag-2 — practical no-op risk | iter-3 bounce | Accepted. Upstream Hermes evidence points to `tools.delegate_tool.delegate_task(...)` and `tools.skill_manager_tool.skill_manage(...)` registered through `tools.registry`, not to `hermes.skills.<name>.invoke(config_path=...)`; `config_path=` is not in either visible handler signature. |
| Flag-3 — env-config baseline shift | verified | The Reviewer VM reproduced the iter-2 baseline shape: `a022a3f` = 1112 tests, `c1949f3` = 1120 tests, with zero sorted FAIL/ERROR diff. The missing `/tmp` iter-1 list was reconstructed from the pinned iter-1 commit on the same VM. |
| Flag-4 — Findings 2 and 3 closure | verified | Finding 2 is fixed with `is not None` guards and regression coverage; Finding 3's execution-log count is corrected. |

### 7.5 Iter-2 hard rules check

- [x] Reviewer write-zone respected: this iter-2 commit modifies only `docs/reviews/RV-CODE-033.md`.
- [x] Implementation PR branch `exe/tkt-033-runtime-check-enforcement` was read only; no push or edit was made to it.
- [x] No code in `src/`, `tests/`, `scripts/`, `docs/architecture/`, `docs/architecture/adr/`, `docs/tickets/§§1-9`, `docs/prompts/`, or `docs/prd/` was modified by the Reviewer.
- [x] No merge was performed.
- [x] No force-push to `main` or `rv/rv-code-033` was performed.
- [x] No git hooks were skipped; no `--no-verify` / `--no-gpg-sign` was used.
- [x] No commit was amended; iter-1 commit `7b236420c5d17a20752a382869801c8707e074ee` is preserved.
- [x] No git command was run with `sudo`; git config was not changed.
- [x] No `git add .` was used; staging is limited to this review artifact.
- [x] No file containing a real secret was committed.

### 7.6 Iter-2 recommendation

Dispatch Executor iter-3 as an in-session continuation. Required fix: make `delegate_task_callable` and `skill_manage_callable` fail/pass on the real Hermes disabled-tool gating response, not on import absence, missing entry points, broad exception catch, or guessed keyword mismatch. Until then, PR #128 remains **pass_with_changes** rather than merge-safe.
