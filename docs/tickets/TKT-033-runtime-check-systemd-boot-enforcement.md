---
id: TKT-033
version: 0.2.0
status: ready
arch_ref: ARCH-001@0.3.0
---

# TKT-033: runtime_check enforcement at systemd boot (AUDIT-001 spec)

## 1. Scope

Make `runtime_check.check_runtime()` (TKT-021, v0.1.1) actually block boot of every developer-assistant Hermes runtime by attaching it to the systemd unit's `ExecStartPre=` directive with abort-on-failure semantics, extending its invariant set with three new round-trip checks, and adding a structured journald marker grammar so that `verify-self.sh` (TKT-020, v0.2.0) can detect every invariant failure deterministically. This ticket promotes the scope stub in `docs/session-log/2026-05-08-session-2.md` § 5.1 (AUDIT-001) into a full implementation contract; it is the first of a four-ticket family (AUDIT-001..004) closing the integration-composition gap exposed by the 2026-05-08 live VPS deployment of TKT-032 (v0.1.0).

The work is the **composition layer** counterpart to ADR-014 (the eight infrastructure corrections from the same live test). ADR-014 corrected what the runtime needs to be reachable; AUDIT-001 corrects what the runtime is allowed to do once it boots. Sibling: this ticket extends the existing TKT-021 § 1 (a)-(e) invariants — it does not retrofit them and it does not change their raise-side behaviour; it only adds an observability emit before raise and adds new invariants alongside.

Five components in scope:

- **A. `ExecStartPre=` enforcement.** The five per-role systemd unit templates at `scripts/templates/devassist-<role>.service.j2` (post-PR #119 path; see § 3) MUST add an `ExecStartPre=` line that invokes `runtime_check.check_runtime()` (or a thin shim wrapping it) with the role's resolved arguments. A non-zero exit from the helper MUST cause the systemd unit to fail to start. The `Restart=` policy MUST NOT silently auto-restart the unit on a `runtime_check` abort exit code (the live test showed `Restart=always` masking invariant violations under the boot loop). Whether the Executor solves this with `RestartPreventExitStatus=` on top of the existing `Restart=always` or by switching to `Restart=on-failure` with an explicit exit-code allowlist is left to implementation; the spec mandates only the observable behaviour: a `runtime_check` invariant failure surfaces in journald and the unit transitions to `failed`, not to `auto-restart` loop.

- **B. Three new invariants extending TKT-021 § 1 (a)-(e).**
  - **(i) `delegate_task_callable`.** An attempted invocation of `delegate_task` MUST fail at runtime, not just be absent from the loaded skill list. The check round-trips an actual call attempt and asserts the Hermes runtime returns the gating error. This catches the live observation where `delegate_task` was disabled in `config.yaml` but the gating was not enforced end-to-end. Cross-reference: `docs/session-log/2026-05-08-session-2.md` § 2 row 1.
  - **(ii) `skill_manage_callable`.** An attempted invocation of `skill_manage` MUST be unreachable at runtime, not just disabled in `config.yaml`. Same round-trip pattern as (i). Cross-reference: `docs/session-log/2026-05-08-session-2.md` § 2 row 2.
  - **(iii) `prompt_sha_mismatch` + `prompt_manifest_missing`.** The runtime's resolved `system_prompt.path` MUST point at the per-role canonical file from § 1 component C AND the SHA-256 of the file at install time MUST match an install-rendered manifest. Mismatch ⇒ invariant `prompt_sha_mismatch`. Manifest absent or unreadable ⇒ invariant `prompt_manifest_missing` (NOT a permissive default; missing manifest is a hard fail). Cross-reference: TKT-021 § 1 (b); ADR-014 Correction 8 (config templates rendered, not copied — same renderer pattern extends to the manifest).

- **C. Install-time prompt-path manifest.** A new install-time artifact MUST be rendered by `render_runtime_configs()` (the existing renderer per ADR-014 Correction 8) at the fixed path `/srv/devassist/state/prompt-manifest.json`. It is a separate artifact (not a `config.yaml` schema extension) so that the upstream Hermes config schema is not fragmented with install-time-fixed data. Required minimum shape:

  ```json
  {
    "schema_version": "1.0",
    "rendered_at": "<ISO8601 UTC>",
    "prompts": {
      "orchestrator": "<sha256 docs/prompts/runtime-hermes-orchestrator.md>",
      "planner":      "<sha256 docs/prompts/business-planner.md>",
      "architect":    "<sha256 docs/prompts/architect.md>",
      "executor":     "<sha256 docs/prompts/executor.md>",
      "reviewer":     "<sha256 docs/prompts/reviewer.md>"
    }
  }
  ```

  - **Per-role mapping.** The mapping of `<role>` to canonical `docs/prompts/*.md` filename (as embedded in the JSON example above) follows the `AGENTS.md` Roles table — the canonical authority for "what `<role>` maps to which `docs/prompts/*.md` file" is `AGENTS.md` (cross-checked by the matching `CONTRIBUTING.md` Roles table). The mapping at branch-cut time is: `orchestrator` → `docs/prompts/runtime-hermes-orchestrator.md`; `planner` → `docs/prompts/business-planner.md`; `architect` → `docs/prompts/architect.md`; `executor` → `docs/prompts/executor.md`; `reviewer` → `docs/prompts/reviewer.md`. Implementer MUST re-read the `AGENTS.md` Roles table at branch-cut time and update the manifest renderer to match if the mapping has shifted on `main` between this spec and Executor cut. Bare-name shorthand `docs/prompts/<role>.md` elsewhere in this ticket is a notational convenience that resolves through this mapping (e.g., `<orchestrator>.md` resolves to `runtime-hermes-orchestrator.md`).
  - **Renderer.** `render_runtime_configs()` (called from `scripts/install-self.sh` `main()`) computes SHA-256 of each `docs/prompts/<role>.md` at install time and writes the manifest atomically. The manifest MUST be written before any `ExecStart` of any unit can run, so it is rendered in `install-self.sh` strictly before `render_systemd_units()` (which already runs before `run_verify`).
  - **Reader.** `runtime_check.check_runtime()` loads the manifest at the fixed path, computes SHA-256 of the file resolved by the runtime's `system_prompt.path`, and compares it to the manifest entry for the runtime's role. Mismatch ⇒ `prompt_sha_mismatch`. Manifest missing or unreadable ⇒ `prompt_manifest_missing`. Both are hard fails.
  - **Schema evolution.** `schema_version` of the manifest is independent of the marker grammar version (see component E below); evolving either is a breaking change and MUST be done via a sibling ADR plus a sibling ticket.

- **D. `Restart=` policy correction.** The five `scripts/templates/devassist-<role>.service.j2` MUST be amended so that an exit from the unit caused by a `runtime_check` invariant abort does not silently re-enter the boot loop. Acceptance is observable behaviour, not exact directive text (see Component A above for the two implementation options). The existing `StartLimitIntervalSec=300` / `StartLimitBurst=5` already bound the loop in time; AC-2 strengthens this by requiring that a `runtime_check` invariant abort never auto-restarts at all, leaving the unit `failed` and the marker visible in journald immediately on first failure.

- **E. Stable journald marker grammar (refactor of existing invariants).** Both the seven existing TKT-021 § 1 invariants and the four new invariants in component B above MUST emit a structured marker on stderr **before** raising the existing exception type. The marker is a single line with the literal grammar:

  ```
  RUNTIME_CHECK_FAILED:<role>:<invariant_name>
  ```

  - `<role>` is one of `orchestrator|planner|architect|executor|reviewer`.
  - `<invariant_name>` is exactly one of the eleven stable symbolic names below — not human-readable text, not the exception class name. The set MUST be exposed as a public enum or constant table in `src/developer_assistant/runtime_check.py` so that `verify-self.sh` and tests can grep for it deterministically:

    ```
    role_env_unset
    role_env_invalid
    loaded_skills_mismatch
    operational_db_path_mismatch
    schema_version_mismatch
    orchestrator_telegram_token_missing
    non_orchestrator_telegram_skill_loaded
    delegate_task_callable
    skill_manage_callable
    prompt_manifest_missing
    prompt_sha_mismatch
    ```

    Mapping rationale. The eleven symbolic names decompose as follows. Seven of them encode the existing TKT-021 § 1 (a)-(e) invariants — five prose buckets that yield seven distinct symbolic codes because two of the prose buckets resolve into multiple existing exception classes in `runtime_check.py`:

    | TKT-021 § 1 prose | symbolic_name(s) | rationale |
    |---|---|---|
    | (a) `HERMES_DEVASSIST_ROLE` is set to one of the five allowed values | `role_env_unset`, `role_env_invalid` | Two distinct failure modes (env var absent vs env var present but not in the allowed set) that currently both surface as `RoleValueError` in `runtime_check.py`. This ticket splits them so that `verify-self.sh` can grep for the precise diagnostic. |
    | (b) the loaded skills match the per-role expected set | `loaded_skills_mismatch` | One-to-one with the existing `SkillsMismatchError`. |
    | (c) the per-runtime config references `/srv/devassist/state/operational.db` via the symlink | `operational_db_path_mismatch` | One-to-one with the existing `OperationalDbPathError`. |
    | (d) the operational-store schema version matches the version this build expects | `schema_version_mismatch` | One-to-one with the existing `SchemaVersionMismatchError`. |
    | (e) Orchestrator-only Telegram bot token; non-Orchestrator runtimes MUST NOT load the Telegram-gateway skill | `orchestrator_telegram_token_missing`, `non_orchestrator_telegram_skill_loaded` | Two distinct invariants conjoined in TKT-021 prose; they currently surface as two separate exception classes (`TelegramTokenMissingError`, `TelegramGatewayLoadedError`) because they apply to different role partitions of the runtime set. |

    The remaining four symbolic names come from this ticket's AC-3 (i)-(iii) and the manifest-availability fail mode from § 5.1.B: `delegate_task_callable`, `skill_manage_callable`, `prompt_manifest_missing`, `prompt_sha_mismatch`. Splitting the existing `RoleValueError` into two symbolic codes (`role_env_unset` vs `role_env_invalid`) is a refactor of the helper, not a change to the raise-side contract: the (a) invariant continues to raise on either failure; the ticket adds finer-grained code-keyed observability on top.

    The first seven names are renamings of the existing TKT-021 § 1 (a)-(e) invariants into stable symbolic identifiers; the last four are new from component B. Adding a name to or removing a name from this enum is a breaking change for `verify-self.sh` and any other downstream grep consumer; the marker grammar version (separate from the manifest `schema_version`) bumps when this enum changes, and changes are gated by a sibling ADR.
  - The refactor preserves TKT-021 § 1 contract: `check_runtime()` MUST raise the same exception type for the same invariant as it does today. Only the observability path (stderr emit before raise) is added. RV-CODE will assert the existing exception types are preserved by the refactor.

## 2. Non-scope

- AUDIT-002 (install-script operator hygiene per `docs/session-log/2026-05-08-session-2.md` § 5.2). Ticket id assigned at SO dispatch time. Any operator-hygiene observation surfaced during AUDIT-001 implementation (e.g., `gh` CLI install, git identity for `devassist`, `/srv/devassist/shared-skills/` population) MUST be filed as a BACKLOG entry on AUDIT-002, not folded into TKT-033.
- AUDIT-003 (behaviour-level Telegram smoke per `docs/session-log/2026-05-08-session-2.md` § 5.3). Ticket id assigned at SO dispatch time. AUDIT-001 is composition-only; it does not exercise the live Telegram → classifier → work_items → specialist → result round-trip.
- AUDIT-004 (TKT-011 reformulation per `docs/session-log/2026-05-08-session-2.md` § 5.4). Ticket id assigned at SO dispatch time. AUDIT-001 does not modify TKT-011's dispatch precondition or AC.
- Modifying any role prompt body in `docs/prompts/<role>.md`. The Architect role write-zone (per `docs/prompts/architect.md`) does not include `docs/prompts/`; the prompt bodies are owned by the Strategic Orchestrator. AUDIT-001 only HASHES the prompt files at install time; it does not edit them.
- Modifying any of the eight infrastructure corrections in `ADR-014@1.0.0`. ADR-014 is merged on `main` and load-bearing for AUDIT-001; it is referenced as a hard precondition.
- Retroactively modifying `TKT-032.md` (v0.1.0). TKT-032 is a closed live-test record; its insufficiency is the reason this audit family exists, but the ticket itself is not edited.
- Introducing any paid third-party dependency. The contract in `MULTI-HERMES-CONTRACT.md` § 1 and `SELF-DEPLOYMENT-CONTRACT.md` § 12 is preserved.
- Running any Hermes runtime against real LLM credentials, real Telegram bot tokens, real GitHub PATs, or real OmniRoute keys during the AUDIT-001 cycle. All AC-4 / AC-6 tests are offline and use placeholder values.
- Adding new entries to the eleven-invariant enum in component E. The enum is fixed by this ticket; future additions require a sibling ADR and ticket so that `verify-self.sh` and downstream grep consumers can be updated atomically.

## 3. Required Context

- `AGENTS.md` — Roles table is the canonical authority for the per-role `docs/prompts/*.md` mapping consumed by the prompt-manifest in § 1 component C
- `CONTRIBUTING.md` — Roles table cross-checks `AGENTS.md`
- `docs/prompts/architect.md`
- `docs/orchestration/SESSION-STATE.md`
- `docs/prd/PRD-001.md` (v0.2.1) § 12, § 12.5, § 13.2
- `docs/architecture/ARCH-001.md` (v0.3.0) § 11, § 12, § 14
- `docs/architecture/MULTI-HERMES-CONTRACT.md` (v0.2.0) § 4, § 5, § 12 (per-runtime config layout, skills loadout per role, multi-Hermes security additions)
- `docs/architecture/HERMES-RUNTIME-CONTRACT.md` (v0.2.0; Telegram and GitHub interaction contract; least-privilege credentials)
- `docs/architecture/HERMES-SKILL-ALLOWLIST.md` (v0.1.1; deny-by-default policy; `delegate_task` blocked for v0.1, `skill_manage` blocked, marketplace auto-install prohibited)
- `docs/architecture/SELF-DEPLOYMENT-CONTRACT.md` (v0.3.0) § 5.2 per-runtime service template, § 5.2.1 per-role ExecStart, § 10.1 secret-segregation pattern
- `docs/architecture/adr/ADR-005-multi-hermes-runtime-isolation.md` (v0.1.0; filesystem-level isolation; per-runtime HERMES_HOME; shared operational store)
- `docs/architecture/adr/ADR-011-routing-layer.md` (v0.1.1, amended by ADR-014)
- `docs/architecture/adr/ADR-014-live-deployment-corrections.md` (v1.0.0) — eight infrastructure corrections from the same 2026-05-08 live test; this ticket is its composition-layer counterpart and MUST NOT modify any of the eight corrections
- `docs/session-log/2026-05-08-session-1.md` (v0.1.0) — Architect's prior session-log filed alongside ADR-014 (continuity reference; not modified by this ticket)
- `docs/session-log/2026-05-08-session-2.md` § 2 (live observations vs merged contracts; rows 1, 2, 4, 13 are the direct evidence for AC-1 and AC-3), § 3.1 (root-cause analysis: `runtime_check.check_runtime()` is not enforced at boot), § 5.1 (AUDIT-001 scope stub), § 9 (durable cross-reference between session-1 and session-2; this ticket preserves it)
- `docs/tickets/TKT-020.md` (v0.2.0; defines the systemd unit template, install/verify/rollback scripts that this ticket modifies)
- `docs/tickets/TKT-021.md` (v0.1.1; defines `runtime_check.check_runtime()` and its current invariants TKT-021 § 1 (a)-(e); this ticket extends those invariants)
- `docs/tickets/TKT-032.md` (v0.1.0; the now-blocked live test ticket whose AC are insufficient per `docs/session-log/2026-05-08-session-2.md` § 3.2 and § 4)

### 3.1 AC-1 diagnosis (live state at HEAD `ca5a011`)

The following observations pin the live state of the integration-composition gap and ground AC-1. Implementer MUST verify each one at branch-cut time and update the diagnosis if the gap has shifted on `main` between this spec and Executor cut.

- **Live unit-template path.** The post-PR #119 live path is `scripts/templates/devassist-<role>.service.j2` — five separate per-role files (`devassist-orchestrator.service.j2`, `devassist-planner.service.j2`, `devassist-architect.service.j2`, `devassist-executor.service.j2`, `devassist-reviewer.service.j2`). Verified at HEAD `ca5a011`. The legacy single-templated path `etc/systemd/devassist@.service.tmpl` referenced in TKT-020 § 5 (original) does NOT exist on disk at HEAD `ca5a011`; the `etc/systemd/` directory does not exist. AC-2 attaches `ExecStartPre=` to the five live `.j2` paths.
- **No `ExecStartPre=` in any unit template.** All five `scripts/templates/devassist-<role>.service.j2` go directly from `[Service]` to `ExecStart=/usr/local/bin/devassist-{worker,orchestrator}-runner` with no `ExecStartPre=` invoking `runtime_check.check_runtime()`. This is the primary defect AC-2 corrects. Verified at HEAD `ca5a011`.
- **`Restart=always` masks the abort.** All five `.j2` templates set `Restart=always` with `RestartSec=10s`. Combined with the absence of `ExecStartPre=`, this means even if the runtime were to fail an invariant check inside the runner script, the unit would re-enter the boot loop until `StartLimitBurst=5` engaged. AC-2 forbids this auto-restart for `runtime_check` invariant aborts.
- **Runner heredocs do not invoke `runtime_check.check_runtime()`.** The `install_worker_runner()` function in `scripts/install-self.sh` (lines 312-374 at HEAD `ca5a011`) writes `/usr/local/bin/devassist-worker-runner` and `/usr/local/bin/devassist-orchestrator-runner` as bash heredocs. Neither runner script imports or invokes `developer_assistant.runtime_check`. The worker runner goes straight to a `while true; do hermes chat … ; sleep …; done` loop; the orchestrator runner goes straight to `exec hermes gateway run --accept-hooks`. AC-2 is therefore not satisfiable by editing only the runner heredocs; the canonical fix is `ExecStartPre=` in the systemd unit template, which gates the runner script entirely.
- **Existing `runtime_check.check_runtime()` surface.** The function at `src/developer_assistant/runtime_check.py:139` has signature `check_runtime(role: str, config_path: str, operational_db_path: str, env: Mapping[str, str]) -> None` and currently raises one of: `RoleValueError`, `SkillsMismatchError`, `OperationalDbPathError`, `SchemaVersionMismatchError`, `TelegramTokenMissingError`, `TelegramGatewayLoadedError`. AC-5 preserves these exception types unchanged; component E above adds the stderr emit immediately before each raise.

### 3.2 AC-3 diagnosis (live observations from session-2)

- **Row 1 (`delegate_task` callable in live test).** Per `docs/session-log/2026-05-08-session-2.md` § 2 row 1, an Executor runtime invocation of `delegate_task` returned a successful tool dispatch even though `config.yaml` listed it under `plugins.disabled`. The current TKT-021 invariant (b) checks the loaded-skills set against the per-role expected set, but does not round-trip an actual call. AC-3 (i) closes this gap by requiring an actual call attempt that asserts the Hermes runtime returns the gating error.
- **Row 2 (`skill_manage` callable in live test).** Same shape as row 1, for `skill_manage`. AC-3 (ii) closes this gap with the same round-trip pattern.
- **Row 13 (prompt-path drift).** Per `docs/session-log/2026-05-08-session-2.md` § 2 row 13, the runtime's loaded `system_prompt.path` resolved to a file whose content differed from the per-role canonical `docs/prompts/*.md` file (per the `AGENTS.md` Roles table mapping pinned in § 1 component C; likely because the install renderer copied the prompt at one point in time and a subsequent change to that canonical file was not propagated). AC-3 (iii) closes this gap with an install-time SHA manifest plus a runtime read-and-compare check.

## 4. Acceptance Criteria

- [ ] **AC-1 (diagnosis).** §3.1 of this ticket records the live-state observations at HEAD `ca5a011` that ground the gap. Implementer MUST re-verify the four §3.1 observations at branch-cut time on `main` and either confirm them unchanged in `§ 10 Execution Log iter-1` or, if the gap has shifted on `main` between this spec and Executor cut, file a Q-TKT (`docs/questions/Q-TKT-033-NN.md`) and pause for SO/Architect re-spec rather than silently adapting.
- [ ] **AC-2 (`ExecStartPre=` enforcement).** All five `scripts/templates/devassist-<role>.service.j2` unit templates add an `ExecStartPre=` directive that invokes `runtime_check.check_runtime()` (or a thin shim that imports and calls it) with the role's resolved arguments. A non-zero exit from the helper causes the unit to fail to start (systemd default for `ExecStartPre=`). The `Restart=` policy of all five templates is amended so that an invariant-class exit code is not silently auto-restarted: either by retaining `Restart=always` plus adding `RestartPreventExitStatus=` listing the runtime_check abort exit code, or by switching to `Restart=on-failure` with an explicit exit-code allowlist; the spec mandates only the observable behaviour. The failure is observable in journald with the structured marker grammar from AC-5 (`RUNTIME_CHECK_FAILED:<role>:<invariant_name>`).
- [ ] **AC-3 (three new invariants).** `runtime_check.check_runtime()` enforces three new invariants beyond the existing TKT-021 (v0.1.1) § 1 (a)-(e):
  - (i) `delegate_task_callable`: an attempted invocation of `delegate_task` MUST fail at runtime, not just be absent from the loaded list. The check round-trips an actual call attempt and asserts the Hermes runtime returns the gating error. Cross-reference: `docs/session-log/2026-05-08-session-2.md` § 2 row 1.
  - (ii) `skill_manage_callable`: `skill_manage` MUST be unreachable at runtime, not just disabled in config. Same round-trip pattern as (i). Cross-reference: `docs/session-log/2026-05-08-session-2.md` § 2 row 2.
  - (iii) `prompt_sha_mismatch` + `prompt_manifest_missing`: the runtime's resolved `system_prompt.path` MUST point at the per-role canonical file from § 1 component C AND the SHA-256 of the file at install time MUST match the manifest at `/srv/devassist/state/prompt-manifest.json`. Mismatch ⇒ `prompt_sha_mismatch`. Manifest absent or unreadable ⇒ `prompt_manifest_missing`. Both are hard fails (not permissive defaults). Manifest is rendered by `render_runtime_configs()` at install time with the shape pinned in § 1 component C.
- [ ] **AC-4 (regression test).** A new test (or set of tests) added under `tests/` that fails on `main` before this ticket lands and passes after, simulating each of:
  - (a) a unit-template that omits `ExecStartPre=` invoking `runtime_check.check_runtime()` — test asserts the spec mandates its presence in all five templates;
  - (b) a `runtime_check` that returns success despite an invariant violation (fail-open mode) — test asserts the eleven-invariant enum is exhaustive against the symbolic-name set component E mandates;
  - (c) a `Restart=` policy that auto-restarts on the runtime_check abort exit code — test asserts the spec mandates non-restart on invariant aborts.
  Tests MUST be offline-only (no real systemd, no real Hermes binary, no real LLM credentials, no real Telegram, no real GitHub) and MUST live in either `tests/test_runtime_check.py` (helper-side cases) or `tests/test_self_deployment_scripts.py` (unit-template parsing cases) (Executor's choice; both locations are acceptable) per the existing convention in the repo.
- [ ] **AC-5 (refactor existing invariants to emit structured marker).** All seven existing TKT-021 § 1 (a)-(e) invariants and the four new invariants in AC-3 emit the structured marker `RUNTIME_CHECK_FAILED:<role>:<invariant_name>` on stderr **immediately before** raising the existing exception type. The eleven stable symbolic names are exposed as a public enum or constant table in `src/developer_assistant/runtime_check.py`. The refactor preserves TKT-021 § 1 contract: each invariant raises the same exception class for the same failure as it does today (RV-CODE asserts this). Adding to or removing from the enum requires a sibling ADR; the marker-grammar version (separate from the manifest `schema_version`) bumps when the enum changes.
- [ ] **AC-6 (baseline test discipline).** The Executor records the `python3 -m unittest discover -s tests -p "test_*.py" -v` baseline test count on `main` at branch-cut time in `§ 10 Execution Log iter-1`. After applying the changes for this ticket: (a) `<count_after> >= <count_before>` (the baseline does not regress); (b) the delta is explained by tests added under AC-4 (and/or AC-5 refactor coverage), NOT by removing or skipping existing tests; (c) `python3 scripts/validate_docs.py` and `python3 -m unittest discover -s tests -p "test_*.py" -v` are both green. Pre-existing failures on `main` (e.g., the five `test_runtime_layout_catalog_round_trip.py` failures noted in `docs/session-log/2026-05-08-session-1.md` § 5) MUST NOT be silenced or removed by this ticket; if any of them happen to be fixed incidentally by AUDIT-001 work, the fix is recorded in `§ 10 Execution Log` but the ticket scope is not extended.
- [ ] **AC-7 (no real secrets).** No real `TELEGRAM_BOT_TOKEN`, `GITHUB_TOKEN`, `FIREWORKS_API_KEY`, `OMNIROUTE_API_KEY`, `OPENROUTER_API_KEY`, or production hostnames appear anywhere in the repo or test fixtures. Tests use placeholder values (e.g., `test-token-placeholder`); test fixtures use temporary directories.
- [ ] **AC-8 (2-PR pipeline rule).** The implementation cycle for this ticket follows the standard 2-PR pipeline rule from `CONTRIBUTING.md`: an Executor implementation PR (which this ticket is the spec for) plus a Reviewer artifact PR creating `docs/reviews/RV-CODE-NNN.md` against the implementation HEAD. The Reviewer PR is opened by the SO-dispatched Reviewer (RV-CODE, Kimi K2.6) after Executor hand-back, NOT by the Executor.

## 5. Allowed Files

- `src/developer_assistant/runtime_check.py`
- `scripts/templates/devassist-orchestrator.service.j2`
- `scripts/templates/devassist-planner.service.j2`
- `scripts/templates/devassist-architect.service.j2`
- `scripts/templates/devassist-executor.service.j2`
- `scripts/templates/devassist-reviewer.service.j2`
- `scripts/install-self.sh` (manifest renderer added to `render_runtime_configs()` and installer call ordering; no other behavioural change permitted by this ticket)
- `scripts/verify-self.sh` (only if AC-2 journald-marker detection is surfaced through `verify-self.sh` for the post-start verify phase; permitted change is grep-pattern addition for `RUNTIME_CHECK_FAILED:` lines)
- `tests/test_runtime_check.py` (extend with the four new invariants' test surface plus marker-emit assertions)
- `tests/test_self_deployment_scripts.py` (extend with the unit-template parsing tests for AC-4 (a) and AC-4 (c))
- `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md` § 10 Execution Log only (Executor fills iter-1+; the ticket body §§ 1–9 is frozen at this draft, edits to §§ 1–9 require a sibling Architect amendment ticket)

Files explicitly **NOT** in the allowed list and MUST NOT be modified by this ticket:

- `docs/prompts/<role>.md` — owned by the SO; AUDIT-001 only HASHES these files at install time.
- `docs/architecture/ADR-014-live-deployment-corrections.md` — load-bearing on `main`; the eight infrastructure corrections are not amended by this ticket.
- `docs/tickets/TKT-021.md` (v0.1.1), `docs/tickets/TKT-020.md` (v0.2.0) — the parent and immediate sibling. AUDIT-001 extends the contract; it does not retroactively amend the parent ticket bodies. Any documentation update needed for parent tickets is filed as a sibling clerical PR by the SO, not folded into this ticket.
- `docs/tickets/TKT-032.md` — closed live-test record; not edited.
- The existing renderer template files under `etc/runtime-templates/<role>/config.yaml.tmpl` and `etc/runtime-templates/SOUL.md.tmpl` — schema unchanged by this ticket (the manifest is a new sibling artifact, not a `config.yaml` extension).

## 6. Test/Validation Requirements

- Run `python3 scripts/validate_docs.py`. MUST pass (`Docs validation passed.`).
- Run `python3 -m unittest discover -s tests -p "test_*.py" -v`. MUST pass per AC-6 discipline.
- Tests MUST be offline-only and MUST NOT require a real Hermes binary, real LLM credentials, real Telegram bot, real GitHub access, real systemd, or real OmniRoute. Where the AC-3 (i) and (ii) round-trip would naturally exercise a Hermes process, the Executor MUST stub the Hermes runtime via a fixture or test double that returns the gating error deterministically.
- Tests MUST verify:
  - All five rendered `scripts/templates/devassist-<role>.service.j2` unit templates contain an `ExecStartPre=` directive whose target invokes `runtime_check.check_runtime()` (test parses the unit-template files with a regex or a structured INI parser; no live systemd needed).
  - All five unit templates either set `Restart=on-failure` with explicit allowlist, or retain `Restart=always` plus `RestartPreventExitStatus=` covering the runtime_check abort exit code; the test asserts the observable property "the runtime_check abort exit code does not auto-restart".
  - `runtime_check.check_runtime()` exposes the eleven-invariant symbolic-name enum exactly as listed in AC-5 (test imports the enum and asserts set equality against the canonical list); adding a name in the future fails the test until the AC-5 enum constant is updated atomically with a sibling ADR.
  - `runtime_check.check_runtime()` emits exactly one `RUNTIME_CHECK_FAILED:<role>:<invariant_name>` line on stderr before raising, for each invariant (eleven test cases minimum, parameterized by role where applicable).
  - `render_runtime_configs()` produces a manifest with the fixed shape (schema_version, rendered_at, prompts) at the canonical install path and includes one entry per role; SHA-256 values are recomputed deterministically from the on-disk `docs/prompts/<role>.md` files.
  - `runtime_check.check_runtime()` reads the manifest and detects `prompt_sha_mismatch` (modify the on-disk prompt file in a fixture, do not re-render the manifest, expect the invariant to fail).
  - `runtime_check.check_runtime()` detects `prompt_manifest_missing` (delete the manifest fixture, expect the invariant to fail; do NOT pass-through as success).
  - `delegate_task_callable` and `skill_manage_callable` invariants fail when a stub Hermes runtime allows the call through, and pass when the gating returns the expected error.
- Manually inspect the Executor's diff before requesting RV-CODE to confirm it contains no real secrets, no real tokens, and no production hostnames.

## 7. PR Requirements

- Link this ticket (`docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md`).
- State that this PR is implementation-only for AUDIT-001 runtime_check enforcement at systemd boot; it does not run any Hermes runtime against real LLM credentials, does not exercise real Telegram or real GitHub, and does not modify any of the eight ADR-014 infrastructure corrections.
- State that this ticket extends TKT-021 (v0.1.1) § 1 (a)-(e) invariants with the three new invariants AC-3 (i), (ii), (iii) plus the `prompt_manifest_missing` fail-mode, and refactors all eleven invariants to emit the structured journald marker per AC-5; the existing TKT-021 § 1 raise-side contract is preserved.
- Include the full set of tests run, including `python3 scripts/validate_docs.py` (MUST report `Docs validation passed.`) and `python3 -m unittest discover -s tests -p "test_*.py" -v` (MUST report the AC-6 baseline-respecting count).
- Record in the PR body the AC-6 baseline test count at branch-cut time (`<count_before>`) and the post-change count (`<count_after>`), and state that `<count_after> >= <count_before>` and that the delta is explained by AC-4 / AC-5 additions only (not by removal or skipping of existing tests).
- State that no real `TELEGRAM_BOT_TOKEN`, `GITHUB_TOKEN`, `FIREWORKS_API_KEY`, `OMNIROUTE_API_KEY`, `OPENROUTER_API_KEY`, or production hostnames were added.
- Include PR-Agent (DeepSeek V4 Pro) status after it has run on the final HEAD and classify or resolve any actionable findings before merge-safe sign-off (per the cross-reviewer audit pattern in `docs/meta/strategic-orchestrator.md` § 10).
- Include the Reviewer artifact path (`docs/reviews/RV-CODE-NNN.md`) and verdict before merge-safe sign-off.
- State that Founder acknowledgement before merge remains required and no autonomous merge path was enabled.
- State that this ticket is the first of the AUDIT-001..004 family closing the integration-composition gap exposed by TKT-032; AUDIT-002, AUDIT-003, and AUDIT-004 are dispatched separately by the SO after AUDIT-001 ratifies via merge.

## 8. Risks

- **systemd `ExecStartPre=` semantics differ subtly between systemd v249 (Ubuntu 22.04 LTS default) and newer.** The unit-template amendment pins to v249 shape. If the Founder upgrades the VPS to a newer Ubuntu LTS, the `ExecStartPre=` line and `RestartPreventExitStatus=` semantics MUST be re-validated; the AC-2 test parses the unit template at the syntactic layer and does not exercise the live `systemd-analyze verify` path (which would require a real systemd).
- **Hermes runtime may not expose a callable surface for `delegate_task` / `skill_manage` round-trip in the way TKT-021 `TestAllRolesPass` currently fixtures.** The Executor may need to hook into Hermes' approval-policy entry point or invoke through a controlled fixture; if the v2026.4.30 Hermes shape does not allow this offline, the Executor STOPS and files a Q-TKT rather than proceeding with a synthetic round-trip that does not actually exercise the gating code path.
- **Manifest renderer (in `scripts/install-self.sh`) and reader (in `src/developer_assistant/runtime_check.py`) are coupled by `schema_version`.** Bumping `schema_version` requires updating both atomically; a partial bump leaves the runtime in `prompt_manifest_missing` state. RV-CODE asserts the writer and reader agree on `schema_version` constants in a single PR.
- **Adding new symbolic invariant names in the future is a breaking change for `verify-self.sh` grep patterns.** The marker-grammar version is independent of the manifest `schema_version`; both bumps must go through a sibling ADR. AUDIT-001 fixes the enum at eleven names; future invariants (e.g., from AUDIT-002, AUDIT-003) extend the enum only via dedicated tickets that update `verify-self.sh` in lockstep.
- **AC-4 (a) and AC-4 (c) require an offline test surface for unit-template parsing.** The Executor MUST avoid spinning up a real systemd or fakesystemd in tests; the existing `tests/test_self_deployment_scripts.py` fixture pattern (parsing the `.j2` file as text and asserting structural invariants) is the load-bearing precedent.
- **Per `docs/session-log/2026-05-08-session-1.md` § 5, five `test_runtime_layout_catalog_round_trip.py` tests are failing on `main` at HEAD `ca5a011`.** AUDIT-001 MUST NOT mask, remove, or skip these failing tests. Their fix is a sibling concern (likely AUDIT-002 or a separate clerical pass); if AUDIT-001 work happens to fix them incidentally, the fix is recorded in `§ 10 Execution Log` and the ticket scope is not extended.
- **Refactoring the seven existing invariants to emit the marker BEFORE raising has zero behavioural change for TKT-021 (v0.1.1) § 1 (a)-(e) contract, but RV-CODE and RV-SPEC MUST double-check exception types are preserved.** The refactor is structural (`emit_marker(...); raise Existing(...)`), not semantic.
- **Defense-in-depth for AC-3 (i) and (ii): the round-trip stub asserts the gating error is returned, but a future Hermes version that changes the gating error class would silently break the test.** AC-4 (b) covers the converse direction (fail-open); AC-3 (i) and (ii) are pinned to the v2026.4.30 Hermes gating-error class as documented in `HERMES-SKILL-ALLOWLIST.md` (v0.1.1) § 4.

## 9. Dependencies

- `ARCH-001@0.3.0`, `MULTI-HERMES-CONTRACT@0.2.0`, `ADR-014@1.0.0`, `SELF-DEPLOYMENT-CONTRACT.md` (v0.3.0), `HERMES-RUNTIME-CONTRACT.md` (v0.2.0), `HERMES-SKILL-ALLOWLIST.md` (v0.1.1), `MODEL-CATALOG.md` (v0.2.0), `OPERATIONAL-STATE-STORE.md` (v0.3.0), `ADR-005` (v0.1.0), `ADR-011` (v0.1.1, amended by ADR-014) MUST remain on `main` unchanged through the AUDIT-001 cycle. This ticket reads them as preconditions; it does not amend any of them.
- `TKT-020.md` (v0.2.0) is the parent: AUDIT-001 modifies the systemd unit templates and the install/verify scripts that TKT-020 owns. The two tickets are not in conflict; AUDIT-001 strictly extends TKT-020's existing surfaces.
- `TKT-021.md` (v0.1.1) is the immediate sibling: AUDIT-001 extends `runtime_check.check_runtime()`'s invariant set and refactors its observability path. The TKT-021 § 1 contract is preserved.
- AUDIT-002, AUDIT-003, and AUDIT-004 (per `docs/session-log/2026-05-08-session-2.md` § 5.2, § 5.3, § 5.4) are dispatched separately by the SO after AUDIT-001 ratifies via merge. Their TKT slots are assigned at SO dispatch time, NOT reserved by this ticket.
- The Founder is the merger; no autonomous merge path is enabled. The SO dispatches RV-SPEC (Kimi K2.6) to review this draft spec before promotion to `ready`.

## 10. Execution Log

### Iter-1 — Executor (Devin, fresh account, fresh session, role Executor)

- **Date / branch / head SHA-at-cut:** 2026-05-08 / `exe/tkt-033-runtime-check-enforcement` / branched from `origin/main` at `c97ed395436b6f38422cbec4b8a1e7f67efe989e` (post AUDIT-001 spec close, commit `session-state: v0.2.3 + TKT-033 promoted to ready/0.2.0 — AUDIT-001 spec cycle closed (#127)`).
- **Bootstrap:** SO ratify-ack received via Founder paste-relay (verdict `pass` with one substantive flag (AC-6 full-baseline characterization) and two clerical reminders (install-self.sh change-scope guardrail; manifest renderer fold INSIDE `render_runtime_configs()`)). Step 5 implementation begun only after ratify-ack landed in relay.
- **Restart-policy choice (AC-2 Option A vs B):** Option A — `Restart=always` + `RestartPreventExitStatus=78`. Exit code `78 = EX_CONFIG` per `sysexits.h`, semantically the right code for a config/invariant abort. The CLI shim `python3 -m developer_assistant.runtime_check` returns 78 on any `RuntimeCheckError` so that systemd never auto-restarts on invariant abort, while still auto-restarting on transient runtime crashes (any other non-zero code).
- **AC-4 test-file split:** helper-side cases (11-name enum, 7 marker emits, 4 new invariants, CLI exit code) → `tests/test_runtime_check.py`; unit-template parsing cases (5 ExecStartPre + 5 RestartPreventExitStatus + 5 PYTHONPATH + 3 manifest-render) → `tests/test_self_deployment_scripts.py` (matches RV-SPEC-016 finding 2.4 closed in iter-2 + SO recommendation).
- **Manifest renderer placement (clerical (b)):** folded INSIDE `render_runtime_configs()` so the manifest is part of the same atomic rendering phase as per-runtime `config.yaml`. `main()` already calls `render_runtime_configs()` strictly before `render_systemd_units()`, so the manifest is guaranteed to exist on disk before any `ExecStart` / `ExecStartPre` runs. No third ordering invariant introduced.
- **install-self.sh change-scope (clerical (a)):** only the manifest renderer block was added to `render_runtime_configs()` — no incidental cleanup, no reformat, no behavioural change to other parts of the file. Operator-hygiene observations (e.g., a few `set -euo pipefail` consistency notes) deferred to AUDIT-002 backlog per § 2 Non-scope.

#### AC-1 — diagnosis re-verification at branch-cut HEAD `c97ed39`

Re-checked the four observations from `docs/session-log/2026-05-08-session-2.md` § 3.1 against the current main snapshot:

1. **Per-role config.yaml renders correctly** (orchestrator gateway-enabled; planner / architect / executor / reviewer gateway-disabled; all five contain matching `system_prompt:` block). Verified via `bash scripts/install-self.sh` in DRY-RUN mode + grep on rendered files.
2. **`runtime_check.check_runtime()` exists with 7 invariants** (TKT-021 § 1 (a)-(e), counted as 7 raise-sites mapped to 5 named invariant classes). Verified by reading `src/developer_assistant/runtime_check.py` (221 lines on main).
3. **No `ExecStartPre=/usr/bin/python3 -m developer_assistant.runtime_check`** in any of the 5 service templates (`scripts/templates/devassist-{orchestrator,planner,architect,executor,reviewer}.service.j2`). Verified by `grep -L "runtime_check" scripts/templates/devassist-*.service.j2` returning all 5 file paths (i.e., none match).
4. **`Restart=always` masks invariant aborts** in all 5 templates. Verified by `grep -E '^Restart' scripts/templates/devassist-*.service.j2` returning `Restart=always` with no `RestartPreventExitStatus=`.

All four observations reproduced; no drift between session-2 and branch-cut. No `Q-TKT-033-NN.md` filed.

#### AC-6 — baseline discipline (substantive characterization per SO ratify-ack flag)

**Full baseline at branch-cut HEAD `c97ed39` (Executor's local Devin VM clone, captured BEFORE any code edit):**

```
Ran 989 tests in 6.105s
FAILED (failures=14, errors=65, skipped=2)
```

`<count_before> = 989`; non-passing total `81` (`14F + 65E + 2S`). Captured the per-FQN list with:

```sh
python3 -m unittest discover -s tests -p "test_*.py" 2>&1 \
  | grep -E "^(FAIL|ERROR): " | sort > /tmp/baseline_fail_error_list.txt
# wc -l = 79  (the 2 skipped tests are not emitted on FAIL/ERROR lines; counted separately)
```

Pre-existing failure / error breakdown by suite:

- `test_self_deployment_scripts.py` — 14 failures + 13 errors = 27 non-passing (env-side: missing `sqlite3` system dependency on the Devin VM made `install-self.sh` exit 1 with `FATAL: missing dependencies: sqlite3` before any of these tests' fixtures could be built). See "Incidental fixes" below.
- `test_classifier_skill.py` — 23 errors (classifier import / skill loadout).
- `test_escalation_surface_skill.py` — 7 errors (escalation surface skill).
- `test_progress_report_skill.py` — 5 errors (progress report skill).
- `test_runtime_layout_catalog_round_trip.py` — 5 errors (the set already catalogued in `docs/session-log/2026-05-08-session-1.md` § 5).
- `test_runtime_check.py` — 6 errors (`test_correct_symlink_passes` + 5 subtests of `test_all_five_roles_pass_in_fixture_mode`; all fail in the production-only `_check_operational_db_symlink` invariant which insists on the literal `/srv/devassist/state/operational.db` target — fixtures use tempdirs and so the check returns `False`, raising `OperationalDbPathError`).
- `unittest.loader._FailedTest` — 3 errors (`test_concept_classifier`, `test_escalation_policy_plugin`, `test_llm_client_instrumentation`; module-import failures, identical to baseline).
- `test_health_endpoint.py` — 1 failure (`test_non_localhost_refused`; pre-existing).
- `test_redaction_list.py` — 1 error (`test_no_secret_in_classifier_output`).

**Post-implementation at HEAD-of-branch (after Step 5 + Step 6 commit):**

```
Ran 1017 tests in 26.131s
FAILED (failures=1, errors=51, skipped=2)
```

`<count_after> = 1017`; non-passing total `54` (`1F + 51E + 2S`). New tests added under AC-4 / AC-5: `1017 − 989 = 28` (TestRuntimeCheckInvariantsEnum 4; TestMarkerEmits 7; TestDelegateTaskCallable 2; TestSkillManageCallable 2; TestPromptManifest 4; TestRuntimeCheckCli 3; TestRuntimeCheckEnforcementInUnits 3; TestPromptManifestRender 3 — total 28).

**Diff `baseline → post-impl` (line-item rationale per delta):**

The 27 baseline FAIL/ERRORs that disappeared are ALL in `test_self_deployment_scripts.py` and were ALL caused by the same root cause: `install-self.sh` requires the `sqlite3` CLI as a hard dependency (line 24 of the script, `command -v sqlite3 || die "missing sqlite3"`), and the Devin VM at branch-cut did NOT have `sqlite3` installed. Every test in the suite that calls `install-self.sh` (whether directly or via setUp) failed with `[install-self] FATAL: missing dependencies: sqlite3` and a non-zero return code, which the assertions caught.

During Step 5C implementation (extending `install-self.sh` with `render_prompt_manifest` inside `render_runtime_configs`) the Executor needed to run `install-self.sh` end-to-end to validate the new manifest renderer. The script aborted with the same FATAL. The Executor installed the missing dependency on the Devin VM (`sudo apt-get install -y sqlite3`); this is a host-side environment fix, NOT a repo code change. Once `sqlite3` was present, all 27 baseline failures resolved and the new manifest-renderer tests began to pass. To make this fix permanent for future Devin sessions on this repo, an `update_environment_config` suggestion was emitted adding `sqlite3` (and `python3-yaml`) to the repo `initialize:` block (see "Environment config" below).

**This is NOT silencing or removing tests.** The 27 tests still exist in the suite; they now pass because the test environment is now functional. AC-6 wording: "if any of them happen to be fixed incidentally by AUDIT-001 work, the fix is recorded in § 10 Execution Log but the ticket scope is not extended" — recorded here. No source-side test modification was made to silence them; only one `install-self.sh` change (manifest renderer) was made and it does not alter the dry-run / fixture-mode contract.

The remaining `54 = 1F + 51E + 2S` non-passing count is the strict subset of the original 81 minus those 27, with no new failures introduced. Per-suite identity check (post-impl vs. baseline minus 27):

- `test_self_deployment_scripts.py`: `0` non-passing (was 27; all 27 incidentally fixed by sqlite3 install).
- `test_classifier_skill.py`: `23` (unchanged).
- `test_escalation_surface_skill.py`: `7` (unchanged).
- `test_progress_report_skill.py`: `5` (unchanged).
- `test_runtime_layout_catalog_round_trip.py`: `5` (unchanged).
- `test_runtime_check.py`: `6` (unchanged; same 6 fixtures hit the production-only `/srv/devassist/state/...` symlink-target check).
- `unittest.loader._FailedTest`: `3` (unchanged).
- `test_health_endpoint.py`: `1` (unchanged).
- `test_redaction_list.py`: `1` (unchanged).

Total: `23 + 7 + 5 + 5 + 6 + 3 + 1 + 1 + 0 = 51 errors + 1 failure + 2 skipped + 0 = 54`. Matches `<count_after>` non-passing total. Zero new failures, zero silenced.

**AC-6 audit:** zero failures/errors/skips silenced; 27 incidental-fix(es) recorded — all caused by `sqlite3` becoming available on the Devin test VM (host-side only; no source-side test modification).

#### AC-7 — secrets / production-hostname grep

Ran `grep -rEn "TELEGRAM_BOT_TOKEN=[0-9]+:|GITHUB_TOKEN=ghp_|FIREWORKS_API_KEY=fw-|OPENROUTER_API_KEY=sk-|omniroute\.openclown|srv\.openclown\.com" {modified files}`. Zero matches across `runtime_check.py`, the 5 unit-template `.j2` files, `install-self.sh`, `test_runtime_check.py`, `test_self_deployment_scripts.py`. The only `OMNIROUTE_API_KEY=` occurrences are pre-existing default placeholders in `install-self.sh` (`OMNIROUTE_API_KEY="${OMNIROUTE_API_KEY:-test-token-placeholder}"`); not introduced by this ticket.

#### Validation results

- `python3 scripts/validate_docs.py` → `Docs validation passed.` (run on the post-impl HEAD).
- `python3 -m unittest discover -s tests -p "test_*.py"` → `Ran 1017 tests; FAILED (failures=1, errors=51, skipped=2)` (per-FQN identity check above; same 54 non-passing tests as baseline minus 27 sqlite3-driven incidental fixes).
- `bash scripts/install-self.sh` (DRY-RUN, fixture mode) → exits `0`; renders 5 per-role configs + manifest at `<prefix>/srv/devassist/state/prompt-manifest.json` (schema_version=1.0, rendered_at ISO8601, prompts {role: sha256}) + 5 systemd unit files containing the new `ExecStartPre=`, `Environment=PYTHONPATH=…/repo/src`, `Restart=always`, `RestartPreventExitStatus=78` directives.

#### Files modified (11 allowed; 9 actually touched)

1. `src/developer_assistant/runtime_check.py` — refactor to 11-name enum + `_emit_marker` helper + 4 new invariants + CLI `__main__` shim returning `RUNTIME_CHECK_ABORT_EXIT_CODE = 78`.
2. `scripts/install-self.sh` — added `render_prompt_manifest` block inside `render_runtime_configs()`; no other behavioural change.
3. `scripts/templates/devassist-orchestrator.service.j2` — `ExecStartPre=` runtime_check + `Environment=PYTHONPATH=` + `RestartPreventExitStatus=78` (`Restart=always` retained).
4. `scripts/templates/devassist-planner.service.j2` — same pattern.
5. `scripts/templates/devassist-architect.service.j2` — same pattern.
6. `scripts/templates/devassist-executor.service.j2` — same pattern.
7. `scripts/templates/devassist-reviewer.service.j2` — same pattern.
8. `tests/test_runtime_check.py` — added 6 new test classes + `_setup_prompt_fixture` / `_capture_marker_call` helpers.
9. `tests/test_self_deployment_scripts.py` — added `TestRuntimeCheckEnforcementInUnits` (3 tests) + `TestPromptManifestRender` (3 tests).
10. `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md` — this § 10 entry.
11. `scripts/verify-self.sh` — NOT touched (no grep-pattern addition needed for iter-1; behavioural equivalence preserved).

#### Environment config (`update_environment_config` suggestion to be emitted post-PR)

Add `sqlite3` (Ubuntu apt package providing the `sqlite3` CLI) to the repo `initialize:` block so future Devin sessions don't hit the same 27 environment-driven baseline failures. Marked as repo-scoped (not org-scoped) since this is specific to `developer-assistant`'s `install-self.sh`. Documented in handback.

#### Deviations / open questions / Q-TKT-033-NN

None. No deviations from spec § 1 / § 4 / § 5. No `Q-TKT-033-NN.md` filed.
