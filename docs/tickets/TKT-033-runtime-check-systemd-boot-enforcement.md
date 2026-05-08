---
id: TKT-033
version: 0.1.0
status: draft
arch_ref: ARCH-001@0.3.0
---

# TKT-033: runtime_check enforcement at systemd boot (AUDIT-001 spec)

## 1. Scope

Make `runtime_check.check_runtime()` (TKT-021) actually block boot of every developer-assistant Hermes runtime by attaching it to the systemd unit's `ExecStartPre=` directive with abort-on-failure semantics, extending its invariant set with three new round-trip checks, and adding a structured journald marker grammar so that `verify-self.sh` (TKT-020) can detect every invariant failure deterministically. This ticket promotes the scope stub in `docs/session-log/2026-05-08-session-2.md` § 5.1 (AUDIT-001) into a full implementation contract; it is the first of a four-ticket family (AUDIT-001..004) closing the integration-composition gap exposed by the 2026-05-08 live VPS deployment of TKT-032.

The work is the **composition layer** counterpart to ADR-014 (the eight infrastructure corrections from the same live test). ADR-014 corrected what the runtime needs to be reachable; AUDIT-001 corrects what the runtime is allowed to do once it boots. Sibling: this ticket extends the existing TKT-021 § 1 (a)-(e) invariants — it does not retrofit them and it does not change their raise-side behaviour; it only adds an observability emit before raise and adds new invariants alongside.

Five components in scope:

- **A. `ExecStartPre=` enforcement.** The five per-role systemd unit templates at `scripts/templates/devassist-<role>.service.j2` (post-PR #119 path; see § 3) MUST add an `ExecStartPre=` line that invokes `runtime_check.check_runtime()` (or a thin shim wrapping it) with the role's resolved arguments. A non-zero exit from the helper MUST cause the systemd unit to fail to start. The `Restart=` policy MUST NOT silently auto-restart the unit on a `runtime_check` abort exit code (the live test showed `Restart=always` masking invariant violations under the boot loop). Whether the Executor solves this with `RestartPreventExitStatus=` on top of the existing `Restart=always` or by switching to `Restart=on-failure` with an explicit exit-code allowlist is left to implementation; the spec mandates only the observable behaviour: a `runtime_check` invariant failure surfaces in journald and the unit transitions to `failed`, not to `auto-restart` loop.

- **B. Three new invariants extending TKT-021 § 1 (a)-(e).**
  - **(i) `delegate_task_callable`.** An attempted invocation of `delegate_task` MUST fail at runtime, not just be absent from the loaded skill list. The check round-trips an actual call attempt and asserts the Hermes runtime returns the gating error. This catches the live observation where `delegate_task` was disabled in `config.yaml` but the gating was not enforced end-to-end. Cross-reference: `docs/session-log/2026-05-08-session-2.md` § 2 row 1.
  - **(ii) `skill_manage_callable`.** An attempted invocation of `skill_manage` MUST be unreachable at runtime, not just disabled in `config.yaml`. Same round-trip pattern as (i). Cross-reference: `docs/session-log/2026-05-08-session-2.md` § 2 row 2.
  - **(iii) `prompt_sha_mismatch` + `prompt_manifest_missing`.** The runtime's resolved `agent.system_prompt_path` MUST point at `docs/prompts/<role>.md` AND the SHA-256 of the file at install time MUST match an install-rendered manifest. Mismatch ⇒ invariant `prompt_sha_mismatch`. Manifest absent or unreadable ⇒ invariant `prompt_manifest_missing` (NOT a permissive default; missing manifest is a hard fail). Cross-reference: TKT-021 § 1 (b); ADR-014 Correction 8 (config templates rendered, not copied — same renderer pattern extends to the manifest).

- **C. Install-time prompt-path manifest.** A new install-time artifact MUST be rendered by `render_runtime_configs()` (the existing renderer per ADR-014 Correction 8) at the fixed path `/srv/devassist/state/prompt-manifest.json`. It is a separate artifact (not a `config.yaml` schema extension) so that the upstream Hermes config schema is not fragmented with install-time-fixed data. Required minimum shape:

  ```json
  {
    "schema_version": "1.0",
    "rendered_at": "<ISO8601 UTC>",
    "prompts": {
      "orchestrator": "<sha256 docs/prompts/orchestrator.md>",
      "planner":      "<sha256 docs/prompts/business-planner.md>",
      "architect":    "<sha256 docs/prompts/architect.md>",
      "executor":     "<sha256 docs/prompts/executor.md>",
      "reviewer":     "<sha256 docs/prompts/reviewer.md>"
    }
  }
  ```

  - **Renderer.** `render_runtime_configs()` (called from `scripts/install-self.sh` `main()`) computes SHA-256 of each `docs/prompts/<role>.md` at install time and writes the manifest atomically. The manifest MUST be written before any `ExecStart` of any unit can run, so it is rendered in `install-self.sh` strictly before `render_systemd_units()` (which already runs before `run_verify`).
  - **Reader.** `runtime_check.check_runtime()` loads the manifest at the fixed path, computes SHA-256 of the file resolved by the runtime's `agent.system_prompt_path`, and compares it to the manifest entry for the runtime's role. Mismatch ⇒ `prompt_sha_mismatch`. Manifest missing or unreadable ⇒ `prompt_manifest_missing`. Both are hard fails.
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

    The first seven names are renamings of the existing TKT-021 § 1 (a)-(e) invariants into stable symbolic identifiers; the last four are new from component B. Adding a name to or removing a name from this enum is a breaking change for `verify-self.sh` and any other downstream grep consumer; the marker grammar version (separate from the manifest `schema_version`) bumps when this enum changes, and changes are gated by a sibling ADR.
  - The refactor preserves TKT-021 § 1 contract: `check_runtime()` MUST raise the same exception type for the same invariant as it does today. Only the observability path (stderr emit before raise) is added. RV-CODE will assert the existing exception types are preserved by the refactor.

## 2. Non-scope

- AUDIT-002 (install-script operator hygiene per `docs/session-log/2026-05-08-session-2.md` § 5.2). Ticket id assigned at SO dispatch time. Any operator-hygiene observation surfaced during AUDIT-001 implementation (e.g., `gh` CLI install, git identity for `devassist`, `/srv/devassist/shared-skills/` population) MUST be filed as a BACKLOG entry on AUDIT-002, not folded into TKT-033.
- AUDIT-003 (behaviour-level Telegram smoke per `docs/session-log/2026-05-08-session-2.md` § 5.3). Ticket id assigned at SO dispatch time. AUDIT-001 is composition-only; it does not exercise the live Telegram → classifier → work_items → specialist → result round-trip.
- AUDIT-004 (TKT-011 reformulation per `docs/session-log/2026-05-08-session-2.md` § 5.4). Ticket id assigned at SO dispatch time. AUDIT-001 does not modify TKT-011's dispatch precondition or AC.
- Modifying any role prompt body in `docs/prompts/<role>.md`. The Architect role write-zone (per `docs/prompts/architect.md`) does not include `docs/prompts/`; the prompt bodies are owned by the Strategic Orchestrator. AUDIT-001 only HASHES the prompt files at install time; it does not edit them.
- Modifying any of the eight infrastructure corrections in `ADR-014@1.0.0`. ADR-014 is merged on `main` and load-bearing for AUDIT-001; it is referenced as a hard precondition.
- Retroactively modifying `TKT-032.md`. TKT-032 is a closed live-test record; its insufficiency is the reason this audit family exists, but the ticket itself is not edited.
- Introducing any paid third-party dependency. The contract in `MULTI-HERMES-CONTRACT.md` § 1 and `SELF-DEPLOYMENT-CONTRACT.md` § 12 is preserved.
- Running any Hermes runtime against real LLM credentials, real Telegram bot tokens, real GitHub PATs, or real OmniRoute keys during the AUDIT-001 cycle. All AC-4 / AC-6 tests are offline and use placeholder values.
- Adding new entries to the eleven-invariant enum in component E. The enum is fixed by this ticket; future additions require a sibling ADR and ticket so that `verify-self.sh` and downstream grep consumers can be updated atomically.

## 3. Required Context

- `AGENTS.md`
- `CONTRIBUTING.md`
- `docs/prompts/architect.md`
- `docs/orchestration/SESSION-STATE.md`
- `docs/prd/PRD-001.md` (v0.2.1) § 12, § 12.5, § 13.2
- `docs/architecture/ARCH-001.md` (v0.3.0) § 11, § 12, § 14
- `docs/architecture/MULTI-HERMES-CONTRACT.md` (v0.2.0) § 4, § 5, § 12 (per-runtime config layout, skills loadout per role, multi-Hermes security additions)
- `docs/architecture/HERMES-RUNTIME-CONTRACT.md` (Telegram and GitHub interaction contract; least-privilege credentials)
- `docs/architecture/HERMES-SKILL-ALLOWLIST.md` (deny-by-default policy; `delegate_task` blocked for v0.1, `skill_manage` blocked, marketplace auto-install prohibited)
- `docs/architecture/SELF-DEPLOYMENT-CONTRACT.md` (v0.3.0) § 5.2 per-runtime service template, § 5.2.1 per-role ExecStart, § 10.1 secret-segregation pattern
- `docs/architecture/adr/ADR-005-multi-hermes-runtime-isolation.md` (filesystem-level isolation; per-runtime HERMES_HOME; shared operational store)
- `docs/architecture/adr/ADR-011-routing-layer.md` (v0.1.1, amended by ADR-014)
- `docs/architecture/adr/ADR-014-live-deployment-corrections.md` (v1.0.0) — eight infrastructure corrections from the same 2026-05-08 live test; this ticket is its composition-layer counterpart and MUST NOT modify any of the eight corrections
- `docs/session-log/2026-05-08-session-1.md` (v0.1.0) — Architect's prior session-log filed alongside ADR-014 (continuity reference; not modified by this ticket)
- `docs/session-log/2026-05-08-session-2.md` § 2 (live observations vs merged contracts; rows 1, 2, 4, 13 are the direct evidence for AC-1 and AC-3), § 3.1 (root-cause analysis: `runtime_check.check_runtime()` is not enforced at boot), § 5.1 (AUDIT-001 scope stub), § 9 (durable cross-reference between session-1 and session-2; this ticket preserves it)
- `docs/tickets/TKT-020-self-deployment-implementation.md` (defines the systemd unit template, install/verify/rollback scripts that this ticket modifies)
- `docs/tickets/TKT-021.md` (defines `runtime_check.check_runtime()` and its current invariants TKT-021 § 1 (a)-(e); this ticket extends those invariants)
- `docs/tickets/TKT-032.md` (the now-blocked live test ticket whose AC are insufficient per `docs/session-log/2026-05-08-session-2.md` § 3.2 and § 4)

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
- **Row 13 (prompt-path drift).** Per `docs/session-log/2026-05-08-session-2.md` § 2 row 13, the runtime's loaded `agent.system_prompt_path` resolved to a file whose content differed from the committed `docs/prompts/<role>.md` (likely because the install renderer copied the prompt at one point in time and a subsequent change to `docs/prompts/<role>.md` was not propagated). AC-3 (iii) closes this gap with an install-time SHA manifest plus a runtime read-and-compare check.

## 4. Acceptance Criteria

- [ ] **AC-1 (diagnosis).** §3.1 of this ticket records the live-state observations at HEAD `ca5a011` that ground the gap. Implementer MUST re-verify the four §3.1 observations at branch-cut time on `main` and either confirm them unchanged in `§ 10 Execution Log iter-1` or, if the gap has shifted on `main` between this spec and Executor cut, file a Q-TKT (`docs/questions/Q-TKT-033-NN.md`) and pause for SO/Architect re-spec rather than silently adapting.
- [ ] **AC-2 (`ExecStartPre=` enforcement).** All five `scripts/templates/devassist-<role>.service.j2` unit templates add an `ExecStartPre=` directive that invokes `runtime_check.check_runtime()` (or a thin shim that imports and calls it) with the role's resolved arguments. A non-zero exit from the helper causes the unit to fail to start (systemd default for `ExecStartPre=`). The `Restart=` policy of all five templates is amended so that an invariant-class exit code is not silently auto-restarted: either by retaining `Restart=always` plus adding `RestartPreventExitStatus=` listing the runtime_check abort exit code, or by switching to `Restart=on-failure` with an explicit exit-code allowlist; the spec mandates only the observable behaviour. The failure is observable in journald with the structured marker grammar from AC-5 (`RUNTIME_CHECK_FAILED:<role>:<invariant_name>`).
- [ ] **AC-3 (three new invariants).** `runtime_check.check_runtime()` enforces three new invariants beyond the existing TKT-021 § 1 (a)-(e):
  - (i) `delegate_task_callable`: an attempted invocation of `delegate_task` MUST fail at runtime, not just be absent from the loaded list. The check round-trips an actual call attempt and asserts the Hermes runtime returns the gating error. Cross-reference: `docs/session-log/2026-05-08-session-2.md` § 2 row 1.
  - (ii) `skill_manage_callable`: `skill_manage` MUST be unreachable at runtime, not just disabled in config. Same round-trip pattern as (i). Cross-reference: `docs/session-log/2026-05-08-session-2.md` § 2 row 2.
  - (iii) `prompt_sha_mismatch` + `prompt_manifest_missing`: the runtime's resolved `agent.system_prompt_path` MUST point at `docs/prompts/<role>.md` AND the SHA-256 of the file at install time MUST match the manifest at `/srv/devassist/state/prompt-manifest.json`. Mismatch ⇒ `prompt_sha_mismatch`. Manifest absent or unreadable ⇒ `prompt_manifest_missing`. Both are hard fails (not permissive defaults). Manifest is rendered by `render_runtime_configs()` at install time with the shape pinned in § 1 component C.
- [ ] **AC-4 (regression test).** A new test (or set of tests) added under `tests/` that fails on `main` before this ticket lands and passes after, simulating each of:
  - (a) a unit-template that omits `ExecStartPre=` invoking `runtime_check.check_runtime()` — test asserts the spec mandates its presence in all five templates;
  - (b) a `runtime_check` that returns success despite an invariant violation (fail-open mode) — test asserts the eleven-invariant enum is exhaustive against the symbolic-name set component E mandates;
  - (c) a `Restart=` policy that auto-restarts on the runtime_check abort exit code — test asserts the spec mandates non-restart on invariant aborts.
  Tests MUST be offline-only (no real systemd, no real Hermes binary, no real LLM credentials, no real Telegram, no real GitHub) and SHOULD live in either `tests/test_runtime_check.py` (helper-side cases) or `tests/test_self_deployment_scripts.py` (unit-template parsing cases) per the existing convention in the repo.
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
- `docs/tickets/TKT-021.md`, `docs/tickets/TKT-020-self-deployment-implementation.md` — the parent and immediate sibling. AUDIT-001 extends the contract; it does not retroactively amend the parent ticket bodies. Any documentation update needed for parent tickets is filed as a sibling clerical PR by the SO, not folded into this ticket.
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
- State that this ticket extends TKT-021 § 1 (a)-(e) invariants with the three new invariants AC-3 (i), (ii), (iii) plus the `prompt_manifest_missing` fail-mode, and refactors all eleven invariants to emit the structured journald marker per AC-5; the existing TKT-021 § 1 raise-side contract is preserved.
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
- **Refactoring the seven existing invariants to emit the marker BEFORE raising has zero behavioural change for TKT-021 § 1 (a)-(e) contract, but RV-CODE and RV-SPEC MUST double-check exception types are preserved.** The refactor is structural (`emit_marker(...); raise Existing(...)`), not semantic.
- **Defense-in-depth for AC-3 (i) and (ii): the round-trip stub asserts the gating error is returned, but a future Hermes version that changes the gating error class would silently break the test.** AC-4 (b) covers the converse direction (fail-open); AC-3 (i) and (ii) are pinned to the v2026.4.30 Hermes gating-error class as documented in `HERMES-SKILL-ALLOWLIST.md` § 4.

## 9. Dependencies

- `ARCH-001@0.3.0`, `MULTI-HERMES-CONTRACT@0.2.0`, `ADR-014@1.0.0`, `SELF-DEPLOYMENT-CONTRACT.md` (v0.3.0), `HERMES-RUNTIME-CONTRACT.md`, `HERMES-SKILL-ALLOWLIST.md`, `MODEL-CATALOG.md` (v0.2.0), `OPERATIONAL-STATE-STORE.md` (v0.3.0), `ADR-005`, `ADR-011` (v0.1.1, amended by ADR-014) MUST remain on `main` unchanged through the AUDIT-001 cycle. This ticket reads them as preconditions; it does not amend any of them.
- `TKT-020-self-deployment-implementation.md` is the parent: AUDIT-001 modifies the systemd unit templates and the install/verify scripts that TKT-020 owns. The two tickets are not in conflict; AUDIT-001 strictly extends TKT-020's existing surfaces.
- `TKT-021.md` is the immediate sibling: AUDIT-001 extends `runtime_check.check_runtime()`'s invariant set and refactors its observability path. The TKT-021 § 1 contract is preserved.
- AUDIT-002, AUDIT-003, and AUDIT-004 (per `docs/session-log/2026-05-08-session-2.md` § 5.2, § 5.3, § 5.4) are dispatched separately by the SO after AUDIT-001 ratifies via merge. Their TKT slots are assigned at SO dispatch time, NOT reserved by this ticket.
- The Founder is the merger; no autonomous merge path is enabled. The SO dispatches RV-SPEC (Kimi K2.6) to review this draft spec before promotion to `ready`.

## 10. Execution Log

(empty; Executor fills iter-1 onward)
